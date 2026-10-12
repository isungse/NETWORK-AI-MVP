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
        self.tracker.observe("sw", [{"interface": name, "status": before}], [{"interface": name, "status": after}],
                             stamp(at - timedelta(minutes=2)), stamp(at), continuous)

    def confirm(self, at=None, confirmed=True, event=None):
        event = event or self.tracker.history("sw", "Gi3/23")[0]
        self.tracker.confirm_physical("sw", "GigabitEthernet3/23", event["id"], confirmed=confirmed,
                                      note="운영자가 실제 케이블 삽입 확인", now=at or self.now)

    def test_link_up_never_automatically_means_physical_insertion(self):
        self.observe("down", "notconnect", self.now - timedelta(minutes=20))
        self.observe("down", "notconnect", self.now - timedelta(minutes=2))
        self.observe("down", "connected")
        self.tracker.consume_logs("sw", cisco_log(), stamp(self.now))
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.assertTrue(self.tracker.history("sw", "Gi3/23"))

    def test_baseline_missing_unknown_and_logical_ports_do_not_invent_events(self):
        for before, after, continuous in [(None, "connected", True), ("unknown", "connected", True),
                                          ("down", "connected", False), ("connected", "connected", True)]:
            self.observe(before, after, continuous=continuous)
        self.observe("down", "up", name="Po10")
        self.assertEqual(self.tracker.history("sw", "Gi3/23"), [])
        self.assertEqual(self.tracker.snapshot(self.now), {})

    def test_confirmed_connection_needs_no_10_minute_baseline_and_expires_at_exactly_24_hours(self):
        self.observe("down", "connected")
        self.confirm()
        event = self.tracker.snapshot(self.now)["sw"]["Gi3/23"]
        self.assertTrue(event["physical_confirmed"])
        self.assertEqual(event["interval_start"], stamp(self.now - timedelta(minutes=2)))
        self.assertIn("sw", self.tracker.snapshot(self.now + timedelta(hours=24, microseconds=-1)))
        self.assertEqual(self.tracker.snapshot(self.now + timedelta(hours=24)), {})
        self.assertEqual(self.tracker.snapshot(self.now - timedelta(seconds=1)), {})

    def test_late_confirmation_cannot_restart_the_24_hour_window(self):
        self.observe("down", "connected")
        self.confirm(self.now + timedelta(hours=25))
        self.assertEqual(self.tracker.snapshot(self.now + timedelta(hours=25)), {})
        self.assertTrue(self.tracker.history("sw", "Gi3/23")[0]["physical_confirmed"])

    def test_disconnect_and_link_recovery_keep_original_physical_time_and_count(self):
        self.observe("down", "connected")
        self.confirm()
        self.observe("connected", "down", self.now + timedelta(minutes=2))
        self.observe("down", "connected", self.now + timedelta(minutes=4))
        event = self.tracker.snapshot(self.now + timedelta(minutes=4))["sw"]["Gi3/23"]
        self.assertEqual(event["connection_count"], 1)
        self.assertEqual(event["connected_at"], stamp(self.now))
        self.assertFalse(self.tracker.history("sw", "Gi3/23")[0]["physical_confirmed"])

    def test_confirmation_cancel_repeat_and_audit_are_persistent_and_idempotent(self):
        self.observe("down", "connected")
        self.confirm()
        self.confirm(self.now + timedelta(hours=1))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM port_physical_connection_audit').fetchone()[0], 1)
        original = self.tracker.snapshot(self.now)["sw"]["Gi3/23"]["expires_at"]
        self.confirm(self.now + timedelta(hours=2), confirmed=False)
        self.assertEqual(self.tracker.snapshot(self.now + timedelta(hours=2)), {})
        self.db.commit()
        self.tracker = PortConnections(self.db)
        self.confirm(self.now + timedelta(hours=3))
        self.assertEqual(self.tracker.snapshot(self.now + timedelta(hours=3))["sw"]["Gi3/23"]["expires_at"], original)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM port_physical_connection_audit').fetchone()[0], 3)

    def test_confirmation_is_bound_to_exact_device_port_up_event_and_verified_time(self):
        self.observe("connected", "down")
        with self.assertRaises(ValueError):
            self.confirm()
        self.observe("down", "connected", self.now + timedelta(minutes=2))
        with self.assertRaises(ValueError):
            self.confirm()
        event = self.tracker.history("sw", "Gi3/23")[0]
        for device, name in (("other", "Gi3/23"), ("sw", "Gi3/24")):
            with self.assertRaises(LookupError):
                self.tracker.confirm_physical(device, name, event["id"], confirmed=True, now=self.now)
        for event_id, confirmed in ((True, True), (None, True), (event["id"], "true")):
            with self.assertRaises(ValueError):
                self.tracker.confirm_physical("sw", "Gi3/23", event_id, confirmed=confirmed, now=self.now)

    def test_clock_skew_dedup_and_protocol_up_not_double_counted(self):
        stdout = cisco_log() + "Oct 12 2026 09:34:56 KST: %LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet3/23, changed state to up\n"
        self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.confirm()
        self.tracker.consume_logs("sw", stdout, stamp(self.now + timedelta(minutes=2)))
        events = self.tracker.history("sw", "Gi3/23")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["clock_offset_seconds"], 310)
        self.assertEqual(events[0]["at"], "2026-10-12T00:40:05.000000Z")
        self.assertEqual(events[0]["device_at"], "2026-10-12T00:34:55.000000Z")
        self.assertEqual(self.tracker.snapshot(self.now)["sw"]["Gi3/23"]["connection_count"], 1)

    def test_log_refines_confirmed_observation_without_losing_confirmation_or_resetting_expiry(self):
        self.observe("down", "connected")
        self.confirm()
        original = self.tracker.snapshot(self.now)["sw"]["Gi3/23"]["expires_at"]
        self.tracker.consume_logs("sw", cisco_log(clock="09:39:55", event="09:39:00"), stamp(self.now))
        events = self.tracker.history("sw", "Gi3/23")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "device_log")
        self.assertTrue(events[0]["physical_confirmed"])
        self.assertEqual(self.tracker.snapshot(self.now)["sw"]["Gi3/23"]["expires_at"], original)

    def test_missing_clock_retains_unverified_history_but_cannot_be_confirmed(self):
        self.tracker.consume_logs("sw", cisco_log().split("===== show logging =====")[1], stamp(self.now))
        with self.assertRaises(ValueError):
            self.confirm()
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.tracker.consume_logs("sw", cisco_log(), stamp(self.now))
        self.assertEqual(len(self.tracker.history("sw", "Gi3/23")), 1)
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.confirm()
        self.assertIn("sw", self.tracker.snapshot(self.now))

    def test_bad_dates_unknown_zones_and_future_events_are_ignored(self):
        for stdout in (cisco_log().replace("Oct 12 2026 09:34:55", "Oct 32 2026 09:34:55"),
                       cisco_log().replace("KST:", "XYZ:"), cisco_log(event="09:59:59")):
            self.tracker.consume_logs("sw", stdout, stamp(self.now))
        self.assertEqual(self.tracker.snapshot(self.now), {})

    def test_arista_new_year_uses_device_local_year(self):
        now = datetime(2026, 12, 31, 15, 2, tzinfo=UTC)
        stdout = ("===== show clock =====\nFri Jan 1 00:02:00 2027\nTimezone: Asia/Seoul\n"
                  "===== show logging =====\nDec 31 23:59:00 sw Ebra: %LINEPROTO-5-UPDOWN: "
                  "Line protocol on Interface Ethernet1, changed state to up\n")
        self.tracker.consume_logs("sw", stdout, stamp(now))
        self.assertEqual(self.tracker.history("sw", "Et1")[0]["device_at"], "2026-12-31T14:59:00.000000Z")

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

    def test_pruning_and_failed_collection(self):
        self.observe("down", "connected")
        self.confirm()
        self.tracker.consume_logs("sw", cisco_log(), stamp(self.now), success=False)
        self.assertFalse(self.tracker.log_status("sw")["success"])
        self.tracker.prune(self.now + timedelta(days=31))
        self.assertEqual(self.tracker.history("sw", "Gi3/23"), [])
        self.assertEqual(self.tracker.snapshot(self.now + timedelta(days=31)), {})

    def test_restart_replay_does_not_clear_newer_log_failure(self):
        self.tracker.consume_logs("sw", "", stamp(self.now), success=False)
        self.tracker.consume_logs("sw", cisco_log(), stamp(self.now - timedelta(minutes=2)))
        self.assertFalse(self.tracker.log_status("sw")["success"])

    def test_existing_10_minute_heuristic_does_not_become_a_physical_confirmation(self):
        self.observe("down", "connected")
        self.db.execute('ALTER TABLE port_connections ADD COLUMN unused_since TEXT')
        self.db.execute('ALTER TABLE port_connections ADD COLUMN unused_confirmed_at TEXT')
        self.db.execute('UPDATE port_connections SET unused_since=?,unused_confirmed_at=?',
                        (stamp(self.now - timedelta(minutes=12)), stamp(self.now - timedelta(minutes=2))))
        self.tracker = PortConnections(self.db)
        self.assertEqual(self.tracker.snapshot(self.now), {})
        self.assertFalse(self.tracker.history("sw", "Gi3/23")[0]["physical_confirmed"])


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
                calls = 0
                def run(self, plan, *, credential_path):
                    self.calls += 1
                    return CommandResult(device_id=plan.device.device_id, hostname=plan.device.hostname,
                                         management_ip=plan.device.management_ip, purpose=plan.purpose,
                                         commands=plan.commands, stdout=stdout, stderr="", returncode=0)

            executor = Executor()
            def app():
                return create_app(inventory_path=inventory, monitoring_config_path=config,
                                  backbone_neighbors_path=root / "neighbors.json", data_dir=root / "data",
                                  audit_log_path=root / "audit.jsonl", change_audit_log_path=root / "changes.jsonl",
                                  executor=executor, credential_resolver=lambda _: root / "fake.cred",
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
                physical = {"device_id": "sw", "interface": "GigabitEthernet3/23",
                            "event_id": history.json()["events"][0]["id"], "confirmed": True,
                            "note": "운영자가 실제 신규 케이블 연결을 확인"}
                calls_before_confirmation = executor.calls
                for wrong, status in (({"interface": "Gi3/24"}, 404), ({"event_id": True}, 422),
                                      ({"confirmed": "true"}, 422), ({"note": "x" * 301}, 422),
                                      ({"device_id": "missing"}, 404)):
                    self.assertEqual(client.post("/fault-monitor/physical-connections", json={**physical, **wrong}).status_code, status)
                self.assertEqual(client.post("/fault-monitor/physical-connections", json=physical).status_code, 200)
                self.assertEqual(executor.calls, calls_before_confirmation)
                panel = client.get("/fault-monitor").json()["devices"][0]
                self.assertTrue(panel["recent_connections"]["Gi3/23"]["physical_confirmed"])
                self.assertTrue(client.get("/fault-monitor/devices/sw/ports/Gi3%2F23/connections").json()["events"][0]["physical_confirmed"])
                self.assertEqual(client.post("/fault-monitor/physical-connections", json={**physical, "confirmed": False}).status_code, 200)
                self.assertEqual(client.get("/fault-monitor").json()["devices"][0]["recent_connections"], {})
                self.assertEqual(client.post("/fault-monitor/physical-connections", json=physical).status_code, 200)
            with TestClient(app()) as client:
                row = client.get("/fault-monitor").json()["devices"][0]
                self.assertEqual(row["recent_connections"]["Gi3/23"]["connection_count"], 1)
            with patch("network_ai_mvp.api.IS_VERCEL", True), TestClient(app()) as client:
                self.assertEqual(client.get("/fault-monitor").json()["devices"][0]["recent_connections"], {})
                self.assertEqual(client.post("/fault-monitor/physical-connections", json=physical).status_code, 403)


if __name__ == "__main__":
    unittest.main()
