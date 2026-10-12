import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from network_ai_mvp.api import create_app
from network_ai_mvp.executor import CommandResult
from network_ai_mvp.services.port_connections import PortConnections, stamp


def cisco_log(clock="09:39:45", event="09:34:55", state="up", interface="GigabitEthernet3/23"):
    return (f"===== show clock =====\n{clock}.334 KST Mon Oct 12 2026\n"
            f"===== show logging =====\nOct 12 2026 {event} KST: %LINK-3-UPDOWN: "
            f"Interface {interface}, changed state to {state}\n")


class PortConnectionTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.tracker = PortConnections(self.db)
        self.now = datetime(2026, 10, 12, 0, 44, 55, tzinfo=UTC)

    def observe(self, before, after, at=None, continuous=True, name="Gi3/23"):
        at = at or self.now
        self.tracker.observe("sw", [{"interface": name, "status": before}],
                             [{"interface": name, "status": after}],
                             stamp(at - timedelta(minutes=2)), stamp(at), continuous)

    def test_baseline_missing_unknown_and_logical_ports_are_not_new(self):
        for before, after, continuous in [(None, "connected", True), ("unknown", "connected", True),
                                           ("down", "connected", False), ("connected", "connected", True)]:
            self.observe(before, after, continuous=continuous)
        self.observe("down", "up", name="Po10")
        self.assertEqual(self.tracker.snapshot(self.now), {})

    def test_observed_transition_has_interval_and_expires_at_exactly_24_hours(self):
        self.observe("down", "connected")
        event = self.tracker.snapshot(self.now)["sw"]["Gi3/23"]
        self.assertEqual(event["source"], "observation")
        self.assertEqual(event["interval_start"], stamp(self.now - timedelta(minutes=2)))
        self.assertIn("sw", self.tracker.snapshot(self.now + timedelta(hours=24, microseconds=-1)))
        self.assertEqual(self.tracker.snapshot(self.now + timedelta(hours=24)), {})
        self.assertEqual(self.tracker.snapshot(self.now - timedelta(seconds=1)), {})

    def test_disconnect_keeps_recent_marker_and_history(self):
        self.observe("down", "connected")
        self.observe("connected", "notconnect", self.now + timedelta(minutes=2))
        self.assertEqual(self.tracker.snapshot(self.now + timedelta(minutes=2))["sw"]["Gi3/23"]["connection_count"], 1)
        self.assertEqual([e["state"] for e in self.tracker.history("sw", "Gi3/23")], ["down", "up"])

    def test_repeat_connection_requires_three_distinct_ups(self):
        for minute in (0, 4, 8):
            self.observe("down", "connected", self.now + timedelta(minutes=minute))
            self.observe("connected", "down", self.now + timedelta(minutes=minute + 2))
        event = self.tracker.snapshot(self.now + timedelta(minutes=10))["sw"]["Gi3/23"]
        self.assertEqual(event["connection_count"], 3)
        self.assertTrue(event["repeated"])

    def test_clock_skew_dedup_and_protocol_up_not_double_counted(self):
        stdout = cisco_log() + "Oct 12 2026 09:34:56 KST: %LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet3/23, changed state to up\n"
        self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.tracker.consume_logs("sw", stdout, stamp(self.now + timedelta(minutes=2)))
        event = self.tracker.snapshot(self.now)["sw"]["Gi3/23"]
        self.assertEqual(event["connection_count"], 1)
        self.assertEqual(event["clock_offset_seconds"], 310)
        self.assertEqual(event["connected_at"], "2026-10-12T00:40:05.000000Z")
        self.assertEqual(event["device_at"], "2026-10-12T00:34:55.000000Z")

    def test_clock_adjusted_old_log_is_not_marked_recent(self):
        stdout = cisco_log().replace("Oct 12 2026 09:34:55", "Oct 10 2026 09:34:55")
        self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.assertEqual(len(self.tracker.history("sw", "Gi3/23")), 1)

    def test_log_replaces_sample_in_its_interval_and_not_another_transition(self):
        self.observe("down", "connected", self.now)
        # Device clock and log are 5 minutes behind. Actual event falls in the sample interval.
        self.tracker.consume_logs("sw", cisco_log(clock="09:39:55", event="09:39:00"), stamp(self.now))
        events = self.tracker.history("sw", "Gi3/23")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "device_log")

    def test_missing_clock_retains_unverified_history_without_new_marker(self):
        stdout = cisco_log().split("===== show logging =====")[1]
        self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.assertEqual(self.tracker.history("sw", "Gi3/23")[0]["source"], "device_log_unverified")
        self.tracker.consume_logs("sw", cisco_log(), stamp(self.now))
        self.assertEqual(len(self.tracker.history("sw", "Gi3/23")), 1)
        self.assertIn("sw", self.tracker.snapshot(self.now))

    def test_bad_dates_unknown_zones_and_future_events_are_ignored(self):
        for stdout in (cisco_log().replace("Oct 12 2026 09:34:55", "Oct 32 2026 09:34:55"),
                       cisco_log().replace("KST:", "XYZ:"), cisco_log(event="09:59:59")):
            self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.assertEqual(self.tracker.snapshot(self.now), {})

    def test_arista_yearless_log_and_clock(self):
        stdout = ("===== show clock =====\nMon Oct 12 09:43:54 2026\nTimezone: Asia/Seoul\n"
                  "===== show logging =====\nOct 12 09:42:00 switch Ebra: %LINEPROTO-5-UPDOWN: "
                  "Line protocol on Interface Ethernet42, changed state to up\n")
        self.tracker.consume_logs("sw", stdout, stamp(self.now))
        event = self.tracker.snapshot(self.now)["sw"]["Et42"]
        self.assertEqual(event["connected_at"], "2026-10-12T00:43:01.000000Z")
        self.assertEqual(event["clock_offset_seconds"], 61)

    def test_arista_new_year_uses_device_local_year(self):
        now = datetime(2026, 12, 31, 15, 2, tzinfo=UTC)
        stdout = ("===== show clock =====\nFri Jan 1 00:02:00 2027\nTimezone: Asia/Seoul\n"
                  "===== show logging =====\nDec 31 23:59:00 sw Ebra: %LINEPROTO-5-UPDOWN: "
                  "Line protocol on Interface Ethernet1, changed state to up\n")
        self.tracker.consume_logs("sw", stdout, stamp(now))
        self.assertEqual(self.tracker.snapshot(now)["sw"]["Et1"]["device_at"], "2026-12-31T14:59:00.000000Z")

    def test_pruning_and_failed_collection(self):
        self.observe("down", "connected")
        self.tracker.consume_logs("sw", cisco_log(), stamp(self.now), success=False)
        self.assertFalse(self.tracker.log_status("sw")["success"])
        self.tracker.prune(self.now + timedelta(days=31))
        self.assertEqual(self.tracker.history("sw", "Gi3/23"), [])

    def test_restart_replay_does_not_clear_newer_log_failure(self):
        self.tracker.consume_logs("sw", "", stamp(self.now), success=False)
        self.tracker.consume_logs("sw", cisco_log(), stamp(self.now - timedelta(minutes=2)))
        self.assertFalse(self.tracker.log_status("sw")["success"])

    def test_collection_latency_does_not_double_count_sample_and_log(self):
        self.observe("down", "connected")
        self.tracker.consume_logs("sw", cisco_log(clock="09:39:55", event="09:39:54"), stamp(self.now + timedelta(seconds=3)))
        self.assertEqual(len(self.tracker.history("sw", "Gi3/23")), 1)


class ConnectionApiTests(unittest.TestCase):
    def test_collection_to_dashboard_history_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inventory = root / "devices.csv"
            inventory.write_text("device_id,hostname,management_ip,vendor,platform,role,access_method,credential_ref,notes\n"
                                 "sw,TEST,192.0.2.1,cisco,WS-C4503-E,backbone,telnet,test,\n", encoding="utf-8")
            config = root / "monitoring.json"
            config.write_text(json.dumps({"devices": {"sw": {"building": "시험동", "floor": "9F", "uplinks": [], "important_ports": []}}}), encoding="utf-8")
            now = datetime.now(UTC)
            local = now + timedelta(hours=9)
            event = local - timedelta(minutes=5)
            clock_text = f"{local:%H:%M:%S} KST Mon {local:%b} {local.day} {local.year}"
            event_text = f"{event:%b} {event.day} {event.year} {event:%H:%M:%S} KST"
            stdout = (f"===== show clock =====\n{clock_text}\n"
                      "===== show interfaces status =====\nGi3/23 connected 1 a-full a-1000 10/100/1000-TX\n"
                      f"===== show logging =====\n{event_text}: %LINK-3-UPDOWN: Interface GigabitEthernet3/23, changed state to up\n")

            class Executor:
                def run(self, plan, *, credential_path):
                    return CommandResult(device_id=plan.device.device_id, hostname=plan.device.hostname,
                                         management_ip=plan.device.management_ip, purpose=plan.purpose,
                                         commands=plan.commands, stdout=stdout, stderr="", returncode=0)

            def app():
                return create_app(inventory_path=inventory, monitoring_config_path=config,
                                  backbone_neighbors_path=root / "neighbors.json", data_dir=root / "data",
                                  audit_log_path=root / "audit.jsonl", change_audit_log_path=root / "changes.jsonl",
                                  executor=Executor(), credential_resolver=lambda _: root / "fake.cred",
                                  polling_enabled=False, change_enabled=False)

            with TestClient(app()) as client:
                client.post("/devices/sw/collect/interfaces")
                result = client.post("/devices/sw/collect/connection-events")
                self.assertEqual(result.status_code, 200, result.text)
                self.assertTrue(result.json()["success"])
                panel = client.get("/fault-monitor").json()["devices"][0]
                self.assertEqual(panel["panel_ports"][0]["status"], "connected")
                self.assertEqual(panel["recent_connections"]["Gi3/23"]["connection_count"], 1)
                self.assertTrue(panel["port_data_current"])
                history = client.get("/fault-monitor/devices/sw/ports/Gi3%2F23/connections")
                self.assertEqual(history.status_code, 200)
                self.assertEqual(len(history.json()["events"]), 1)
                self.assertEqual(client.get("/fault-monitor/devices/missing/ports/Gi3%2F23/connections").status_code, 404)
                self.assertIn("recentConnections", client.get("/operations").text)
            with TestClient(app()) as client:
                row = client.get("/fault-monitor").json()["devices"][0]
                self.assertEqual(row["recent_connections"]["Gi3/23"]["connection_count"], 1)
            with patch("network_ai_mvp.api.IS_VERCEL", True), TestClient(app()) as client:
                self.assertEqual(client.get("/fault-monitor").json()["devices"][0]["recent_connections"], {})


if __name__ == "__main__":
    unittest.main()
