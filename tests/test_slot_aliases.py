"""Shared display aliases must persist without affecting device state."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

from network_ai_mvp.api import create_app


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class SlotAliasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.new_app()
        self.client = TestClient(self.app)
        self.url = "/fault-monitor/devices/cisco-backbone/slots/1/alias"

    def new_app(self):
        return create_app(data_dir=self.root / "data", audit_log_path=self.root / "audit.jsonl",
                          change_audit_log_path=self.root / "changes.jsonl", polling_enabled=False,
                          change_enabled=False)

    def save(self, alias, expected="", url=None):
        return self.client.post(url or self.url, json={"alias": alias, "expected_alias": expected})

    def test_shared_alias_survives_restart_and_clear_is_audited(self):
        monitor = self.app.state.fault_monitor
        monitor.record("cisco-backbone", success=True, ports=[{"interface": "Gi1/1", "status": "connected"}])
        before = self.client.get("/fault-monitor/devices/cisco-backbone").json()
        alias = "서버룸 BACKBONE 슬롯2"
        self.assertEqual(self.save("  " + alias + "  ").json()["alias"], alias)
        second_client = TestClient(self.app)
        detail = second_client.get("/fault-monitor/devices/cisco-backbone").json()
        self.assertEqual(detail["slot_aliases"], {"1": alias})
        self.assertTrue(detail["slot_alias_editable"])
        for key in ("ports", "port_states", "history", "checked_at", "status", "config"):
            self.assertEqual(detail[key], before[key])
        restarted = self.new_app()
        client = TestClient(restarted)
        row = next(d for d in client.get("/fault-monitor").json()["devices"] if d["device_id"] == "cisco-backbone")
        self.assertEqual(row["slot_aliases"], {"1": alias})
        self.assertEqual(client.post(self.url, json={"alias": "", "expected_alias": alias}).status_code, 200)
        self.assertEqual(restarted.state.fault_monitor.db.execute(
            "SELECT previous_alias,alias FROM slot_alias_audit ORDER BY id").fetchall(), [("", alias), (alias, "")])
        self.assertEqual(TestClient(self.new_app()).get("/fault-monitor/devices/cisco-backbone").json()["slot_aliases"]["1"], "")

    def test_stale_editor_cannot_overwrite_another_staff_member(self):
        self.assertEqual(self.save("직원 A").status_code, 200)
        self.assertEqual(self.save("직원 B").status_code, 409)
        self.assertEqual(self.client.get("/fault-monitor/devices/cisco-backbone").json()["slot_aliases"]["1"], "직원 A")
        self.assertEqual(self.save("직원 B", "직원 A").status_code, 200)

    def test_input_and_target_validation(self):
        for alias in (None, 1, {}, "a" * 81, "별칭\n두 줄", "숨김\u202e제어"):
            with self.subTest(alias=alias):
                self.assertEqual(self.save(alias).status_code, 422)
        self.assertEqual(self.client.post(self.url, json={"alias": "누락"}).status_code, 422)
        self.assertEqual(self.save("별칭", url=self.url.replace("slots/1", "slots/4")).status_code, 422)
        self.assertEqual(self.save("별칭", url=self.url.replace("cisco-backbone/slots/1", "arista-10g-core/slots/999")).status_code, 422)
        self.assertEqual(self.save("별칭", url=self.url.replace("cisco-backbone", "missing-device")).status_code, 404)
        self.assertEqual(self.app.state.fault_monitor.db.execute("SELECT count(*) FROM slot_alias_audit").fetchone()[0], 0)

    def test_every_inventory_device_can_edit_its_display_slots(self):
        monitor = self.app.state.fault_monitor
        for device in monitor.inventory.list_devices():
            with self.subTest(device=device.device_id):
                interface = "Et1" if device.vendor == "arista" else "Gi1/1" if device.device_id == "cisco-backbone" else "Gi1/0/1"
                slot = "fixed" if device.vendor == "arista" else "1" if device.device_id == "cisco-backbone" else "1-0"
                monitor.record(device.device_id, success=True, ports=[{"interface": interface, "status": "connected"}])
                url = f"/fault-monitor/devices/{device.device_id}/slots/{slot}/alias"
                self.assertEqual(self.save("직원 지정 이름", url=url).status_code, 200)
                detail = self.client.get(f"/fault-monitor/devices/{device.device_id}").json()
                self.assertTrue(detail["slot_alias_editable"])
                self.assertIn(slot, detail["slot_alias_slots"])
                self.assertEqual(detail["slot_aliases"][slot], "직원 지정 이름")

    def test_stack_slots_are_independent_and_not_limited_to_one_through_three(self):
        monitor = self.app.state.fault_monitor
        monitor.record("arista-10g-core", success=True, ports=[
            {"interface": "Gi4/0/1"}, {"interface": "Te4/0/2"}, {"interface": "Gi5/0/1"}])
        for slot in ("4-0", "5-0"):
            url = f"/fault-monitor/devices/arista-10g-core/slots/{slot}/alias"
            self.assertEqual(self.save(f"슬롯 {slot}", url=url).status_code, 200)
        restarted = TestClient(self.new_app()).get("/fault-monitor/devices/arista-10g-core").json()
        self.assertEqual(restarted["slot_aliases"], {"4-0": "슬롯 4-0", "5-0": "슬롯 5-0"})

    def test_fixed_switch_lanes_share_one_alias_and_logical_ports_are_excluded(self):
        monitor = self.app.state.fault_monitor
        monitor.record("arista-10g-core", success=True, ports=[
            {"interface": "Et1"}, {"interface": "Et49/1"}, {"interface": "Et56/1"},
            {"interface": "Vl102"}, {"interface": "Po10"}, {"interface": "Fa0"}])
        detail = self.client.get("/fault-monitor/devices/arista-10g-core").json()
        self.assertEqual(detail["slot_alias_slots"], ["fixed"])
        self.assertEqual(self.save("10G 코어", url="/fault-monitor/devices/arista-10g-core/slots/fixed/alias").status_code, 200)
        self.assertEqual(self.save("분기 아님", url="/fault-monitor/devices/arista-10g-core/slots/49/alias").status_code, 422)

    def test_reference_runtime_rejects_edits_even_with_direct_post(self):
        with patch("network_ai_mvp.api.IS_VERCEL", True):
            client = TestClient(self.new_app())
        self.assertEqual(client.post(self.url, json={"alias": "참고", "expected_alias": ""}).status_code, 403)
        self.assertFalse(client.get("/fault-monitor/devices/cisco-backbone").json()["slot_alias_editable"])


if __name__ == "__main__":
    unittest.main()
