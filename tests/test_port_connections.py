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

    def arm(self, at=None, name="Gi3/23"):
        at = at or self.now
        for minute in range(-12, 0, 2):
            self.observe("down", "notconnect", at + timedelta(minutes=minute), minute != -12, name)

    def test_baseline_missing_unknown_and_logical_ports_are_not_new(self):
        for before, after, continuous in [(None, "connected", True), ("unknown", "connected", True),
                                           ("down", "connected", False), ("connected", "connected", True)]:
            self.observe(before, after, continuous=continuous)
        self.observe("down", "up", name="Po10")
        self.assertEqual(self.tracker.snapshot(self.now), {})

    def test_observed_transition_has_interval_and_expires_at_exactly_24_hours(self):
        self.arm()
        self.observe("down", "connected")
        event = self.tracker.snapshot(self.now)["sw"]["Gi3/23"]
        self.assertEqual(event["source"], "observation")
        self.assertEqual(event["interval_start"], stamp(self.now - timedelta(minutes=2)))
        self.assertIn("sw", self.tracker.snapshot(self.now + timedelta(hours=24, microseconds=-1)))
        self.assertEqual(self.tracker.snapshot(self.now + timedelta(hours=24)), {})
        self.assertEqual(self.tracker.snapshot(self.now - timedelta(seconds=1)), {})

    def test_disconnect_keeps_recent_marker_and_history(self):
        self.arm()
        self.observe("down", "connected")
        self.observe("connected", "notconnect", self.now + timedelta(minutes=2))
        self.assertEqual(self.tracker.snapshot(self.now + timedelta(minutes=2))["sw"]["Gi3/23"]["connection_count"], 1)
        self.assertEqual([e["state"] for e in self.tracker.history("sw", "Gi3/23")], ["down", "up"])

    def test_repeat_connection_requires_three_distinct_ups(self):
        for minute in (0, 16, 32):
            self.arm(self.now + timedelta(minutes=minute))
            self.observe("down", "connected", self.now + timedelta(minutes=minute))
            self.observe("connected", "down", self.now + timedelta(minutes=minute + 2))
        event = self.tracker.snapshot(self.now + timedelta(minutes=34))["sw"]["Gi3/23"]
        self.assertEqual(event["connection_count"], 3)
        self.assertTrue(event["repeated"])

    def test_clock_skew_dedup_and_protocol_up_not_double_counted(self):
        stdout = cisco_log() + "Oct 12 2026 09:34:56 KST: %LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet3/23, changed state to up\n"
        self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.tracker.consume_logs("sw", stdout, stamp(self.now + timedelta(minutes=2)))
        self.assertEqual(self.tracker.snapshot(self.now), {})
        events = self.tracker.history("sw", "Gi3/23")
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["clock_offset_seconds"], 310)
        self.assertEqual(event["at"], "2026-10-12T00:40:05.000000Z")
        self.assertEqual(event["device_at"], "2026-10-12T00:34:55.000000Z")

    def test_clock_adjusted_old_log_is_not_marked_recent(self):
        stdout = cisco_log().replace("Oct 12 2026 09:34:55", "Oct 10 2026 09:34:55")
        self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.assertEqual(len(self.tracker.history("sw", "Gi3/23")), 1)

    def test_log_replaces_sample_in_its_interval_and_not_another_transition(self):
        self.arm()
        self.observe("down", "connected", self.now)
        # Device clock and log are 5 minutes behind. Actual event falls in the sample interval.
        self.tracker.consume_logs("sw", cisco_log(clock="09:39:55", event="09:39:00"), stamp(self.now))
        events = self.tracker.history("sw", "Gi3/23")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "device_log")
        self.assertIsNotNone(events[0]["unused_since"])
        self.assertEqual(self.tracker.snapshot(self.now)["sw"]["Gi3/23"]["connection_count"], 1)

    def test_missing_clock_retains_unverified_history_without_new_marker(self):
        stdout = cisco_log().split("===== show logging =====")[1]
        self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.assertEqual(self.tracker.history("sw", "Gi3/23")[0]["source"], "device_log_unverified")
        self.tracker.consume_logs("sw", cisco_log(), stamp(self.now))
        self.assertEqual(len(self.tracker.history("sw", "Gi3/23")), 1)
        self.assertEqual(self.tracker.snapshot(self.now), {})

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
        self.assertEqual(self.tracker.snapshot(self.now), {})
        event = self.tracker.history("sw", "Et42")[0]
        self.assertEqual(event["at"], "2026-10-12T00:43:01.000000Z")
        self.assertEqual(event["clock_offset_seconds"], 61)

    def test_arista_new_year_uses_device_local_year(self):
        now = datetime(2026, 12, 31, 15, 2, tzinfo=UTC)
        stdout = ("===== show clock =====\nFri Jan 1 00:02:00 2027\nTimezone: Asia/Seoul\n"
                  "===== show logging =====\nDec 31 23:59:00 sw Ebra: %LINEPROTO-5-UPDOWN: "
                  "Line protocol on Interface Ethernet1, changed state to up\n")
        self.tracker.consume_logs("sw", stdout, stamp(now))
        self.assertEqual(self.tracker.history("sw", "Et1")[0]["device_at"], "2026-12-31T14:59:00.000000Z")

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
        self.arm()
        self.observe("down", "connected")
        self.tracker.consume_logs("sw", cisco_log(clock="09:39:55", event="09:39:54"), stamp(self.now + timedelta(seconds=3)))
        self.assertEqual(len(self.tracker.history("sw", "Gi3/23")), 1)
        self.assertIsNotNone(self.tracker.history("sw", "Gi3/23")[0]["unused_since"])

    def test_short_flap_and_unproven_down_to_up_are_history_only(self):
        self.observe("connected", "down", self.now - timedelta(seconds=4))
        self.observe("down", "connected")
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.assertEqual(len(self.tracker.history("sw", "Gi3/23")), 2)

    def test_b1f_et45_four_second_arista_flap_is_never_new(self):
        stdout = ("===== show clock =====\nMon Oct 12 09:44:55 2026\nTimezone: Asia/Seoul\n"
                  "===== show logging =====\nOct 12 08:40:23 B1F Ebra: %LINEPROTO-5-UPDOWN: "
                  "Line protocol on Interface Ethernet45, changed state to down\n"
                  "Oct 12 08:40:27 B1F Ebra: %LINEPROTO-5-UPDOWN: "
                  "Line protocol on Interface Ethernet45, changed state to up\n")
        self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.assertEqual(self.tracker.snapshot(self.now), {})
        history = self.tracker.history("sw", "Et45")
        self.assertEqual([event["state"] for event in history], ["up", "down"])
        self.assertEqual((datetime.fromisoformat(history[0]["at"]) - datetime.fromisoformat(history[1]["at"])).total_seconds(), 4)

    def test_10_minutes_must_be_confirmed_before_the_connection_interval(self):
        self.observe("down", "down", self.now - timedelta(minutes=10), False)
        for minute in (-8, -6, -4, -2):
            self.observe("down", "down", self.now + timedelta(minutes=minute))
        self.observe("down", "up")
        self.assertEqual(self.tracker.snapshot(self.now), {})

    def test_disabled_unknown_missing_failed_and_gap_break_unused_evidence(self):
        for index, status in enumerate(("disabled", "errdisabled", "administratively down", "unknown", None)):
            with self.subTest(status=status):
                name = f"Gi3/{index}"
                self.arm(name=name)
                self.observe("notconnect", status, self.now - timedelta(minutes=1), name=name)
                self.observe(status, "connected", name=name)
                self.assertEqual(self.tracker.snapshot(self.now), {})
        self.arm()
        self.tracker.observe("sw", [], [], stamp(self.now - timedelta(minutes=2)), stamp(self.now - timedelta(minutes=1)), True)
        self.observe("down", "connected")
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.arm()
        self.observe("down", "connected", continuous=False)
        self.assertEqual(self.tracker.snapshot(self.now), {})

    def test_late_logs_remove_false_new_for_link_activity_during_unused_period(self):
        self.arm()
        self.observe("down", "connected")
        self.assertIn("sw", self.tracker.snapshot(self.now))
        self.tracker.consume_logs("sw", cisco_log(clock="09:44:55", event="09:40:23", state="down") +
            "Oct 12 2026 09:40:27 KST: %LINK-3-UPDOWN: Interface GigabitEthernet3/23, changed state to up\n", stamp(self.now))
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.assertTrue(self.tracker.history("sw", "Gi3/23"))

    def test_log_before_interface_sample_preserves_legitimate_unused_evidence(self):
        self.arm()
        self.tracker.consume_logs("sw", cisco_log(clock="09:44:55", event="09:44:00"), stamp(self.now))
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.observe("down", "connected")
        event = self.tracker.snapshot(self.now)["sw"]["Gi3/23"]
        self.assertEqual(event["source"], "device_log")
        self.assertEqual(event["unused_minimum_seconds"], 600)

    def test_log_replay_after_restart_preserves_qualified_event_and_baseline(self):
        self.arm()
        self.db.commit()
        self.tracker = PortConnections(self.db)
        self.observe("down", "connected")
        stdout = cisco_log(clock="09:44:55", event="09:44:00")
        self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.db.commit()
        self.tracker = PortConnections(self.db)
        self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.assertEqual(self.tracker.snapshot(self.now)["sw"]["Gi3/23"]["connection_count"], 1)

    def test_existing_schema_history_survives_without_retroactive_new(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.execute("""CREATE TABLE port_connections (id INTEGER PRIMARY KEY,device TEXT,interface TEXT,
            state TEXT,at TEXT,observed_at TEXT,source TEXT,device_at TEXT,clock_offset_seconds REAL,
            interval_start TEXT,event_key TEXT UNIQUE)""")
        db.execute("INSERT INTO port_connections (device,interface,state,at,observed_at,source) VALUES (?,?,?,?,?,?)",
                   ("sw", "Et45", "up", stamp(self.now), stamp(self.now), "device_log"))
        tracker = PortConnections(db)
        self.assertEqual(len(tracker.history("sw", "Et45")), 1)
        self.assertEqual(tracker.snapshot(self.now), {})


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
                self.assertEqual(panel["recent_connections"], {})
                self.assertTrue(panel["port_data_current"])
                history = client.get("/fault-monitor/devices/sw/ports/Gi3%2F23/connections")
                self.assertEqual(history.status_code, 200)
                self.assertEqual(len(history.json()["events"]), 1)
                self.assertEqual(client.get("/fault-monitor/devices/missing/ports/Gi3%2F23/connections").status_code, 404)
                self.assertIn("recentConnections", client.get("/operations").text)
            with TestClient(app()) as client:
                row = client.get("/fault-monitor").json()["devices"][0]
                self.assertEqual(row["recent_connections"], {})
            with patch("network_ai_mvp.api.IS_VERCEL", True), TestClient(app()) as client:
                self.assertEqual(client.get("/fault-monitor").json()["devices"][0]["recent_connections"], {})


if __name__ == "__main__":
    unittest.main()
