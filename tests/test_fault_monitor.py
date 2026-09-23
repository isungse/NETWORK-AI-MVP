import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from network_ai_mvp.api import create_app
from network_ai_mvp.inventory import InventoryRepository
from network_ai_mvp.services.fault_monitor import FaultMonitor, load_config, stamp, management_reachable
from network_ai_mvp.services.port_protection import PortProtection
from network_ai_mvp.services.change_workflow import ChangeWorkflowError


class FaultMonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inventory = self.root / "devices.csv"
        self.inventory.write_text("device_id,hostname,management_ip,vendor,platform,role,access_method,credential_ref,notes\n"
                                  "test-switch,시험 스위치,192.0.2.10,arista,test,access,telnet,test,\n", encoding="utf-8")
        self.config_path = self.root / "monitoring.json"
        self.config = {"settings": {"failure_threshold": 2, "recovery_threshold": 2}, "devices": {"test-switch": {
            "building": "시험동", "floor": "B1F", "location_source": "재현 시나리오",
            "uplinks": [{"interface": "Et52", "source": "시험 설정", "impact": "B1층 상위 연결"}],
            "important_ports": [{"interface": "Et3", "source": "시험 설정", "impact": "업무 단말"}],
        }}}
        self.config_path.write_text(json.dumps(self.config, ensure_ascii=False), encoding="utf-8")
        self.monitor = self.new_monitor()
        self.at = datetime(2026, 9, 23, 1, 0, tzinfo=UTC)

    def new_monitor(self, **options):
        return FaultMonitor(inventory=InventoryRepository(self.inventory), config_path=self.config_path,
                            data_dir=self.root / "data", audit_path=self.root / "audit.jsonl",
                            db_path=self.root / "state.sqlite3", **options)

    def record(self, uplink="connected", important="connected", unused="notconnect", success=True, reachable=None, advance=120):
        self.monitor.record("test-switch", success=success, reachable=reachable, at=stamp(self.at), ports=[
            {"interface": "Et52", "status": uplink, "vlan": "101"},
            {"interface": "Et3", "status": important, "vlan": "101"},
            {"interface": "Et8", "status": unused, "vlan": "101"},
        ])
        result = self.monitor.snapshot(self.at)
        self.at += timedelta(seconds=advance)
        return result

    def test_all_normal_and_unused_down(self):
        snapshot = self.record()
        self.assertEqual(snapshot["normal_devices"], 1)
        self.assertEqual(snapshot["metrics"]["critical_devices"], 0)
        self.assertEqual(snapshot["metrics"]["unknown_devices"], 0)
        self.assertEqual(snapshot["history"], [])

    def test_uplink_failure_confirmed_only_by_distinct_collections(self):
        first = self.record(uplink="notconnect")
        self.assertEqual(first["metrics"]["uplink_faults"], 0)
        for _ in range(3):
            self.assertEqual(self.monitor.snapshot(self.at)["metrics"]["uplink_faults"], 0)
        second = self.record(uplink="notconnect")
        self.assertEqual(second["metrics"]["uplink_faults"], 1)
        self.assertEqual(second["metrics"]["critical_devices"], 1)
        self.assertEqual(second["history"][0]["first_seen"], first["metrics"]["last_checked"])

    def test_important_failure_and_admin_disabled_are_distinct(self):
        self.record(important="notconnect")
        result = self.record(important="disabled")
        self.assertEqual(result["metrics"]["important_faults"], 1)
        self.assertIn("관리상 비활성", result["devices"][0]["issues"][0]["label"])

    def test_intentional_disabled_exception_is_not_link_failure(self):
        self.monitor.config["devices"]["test-switch"]["important_ports"][0]["expected"] = "disabled"
        result = self.record(important="disabled")
        self.assertEqual(result["normal_devices"], 1)
        self.assertEqual(result["devices"][0]["port_states"][1]["state"], "maintenance")

    def test_unreachable_does_not_claim_power_failure_or_multiply_port_faults(self):
        self.record(success=False, reachable=False)
        result = self.record(success=False, reachable=False)
        self.assertEqual(result["metrics"]["device_unreachable"], 1)
        self.assertEqual(result["metrics"]["uplink_faults"], 0)
        self.assertEqual(result["metrics"]["important_faults"], 0)
        self.assertIn("장비 통신 불가·원인 확인 필요", result["devices"][0]["issues"][0]["label"])
        self.assertNotIn("전원 장애", json.dumps(result, ensure_ascii=False))

    def test_collection_failure_cannot_reuse_previous_healthy_state(self):
        self.record()
        result = self.record(success=False, reachable=True)
        self.assertEqual(result["normal_devices"], 0)
        self.assertEqual(result["metrics"]["unknown_devices"], 1)
        self.assertEqual(result["metrics"]["device_unreachable"], 0)
        self.assertFalse(result["devices"][0]["port_data_current"])

    def test_approved_shutdown_is_suppression_not_recovery(self):
        self.record(important="notconnect")
        self.record(important="notconnect")
        self.monitor.admin_change("test-switch", "Et3", "shutdown")
        result = self.record(important="disabled")
        self.assertEqual(result["metrics"]["important_faults"], 0)
        self.assertEqual(result["devices"][0]["port_states"][1]["state"], "maintenance")
        self.assertEqual(result["history"][0]["ended_reason"], "관리자 승인 차단")
        self.assertIsNone(result["history"][0]["recovered_at"])
        self.monitor.admin_change("test-switch", "Et3", "no shutdown")
        self.assertEqual(self.record()["normal_devices"], 1)

    def test_stale_data_and_monitor_restart(self):
        self.record()
        self.at += timedelta(seconds=601)
        result = self.new_monitor().snapshot(self.at)
        self.assertEqual(result["metrics"]["unknown_devices"], 1)
        self.assertEqual(result["normal_devices"], 0)
        self.assertTrue(result["devices"][0]["stale"])

    def test_failure_streak_resets_after_stale_gap(self):
        self.record(uplink="down")
        self.at += timedelta(seconds=601)
        result = self.record(uplink="down")
        self.assertEqual(result["metrics"]["uplink_faults"], 0)

    def test_recovery_requires_new_healthy_samples_and_persists(self):
        first = self.record(uplink="down")
        self.record(uplink="down")
        pending = self.record()
        self.assertEqual(pending["normal_devices"], 0)
        self.assertIsNone(pending["history"][0]["recovered_at"])
        self.assertEqual(pending["devices"][0]["issues"][0]["first_seen"], first["metrics"]["last_checked"])
        recovered = self.record()
        self.assertEqual(recovered["normal_devices"], 1)
        self.assertIsNotNone(recovered["history"][0]["recovered_at"])
        self.assertEqual(self.new_monitor().snapshot(self.at)["history"], recovered["history"])

    def test_missing_configuration_never_inferred_from_hostname(self):
        self.monitor.config["devices"]["test-switch"] = {}
        result = self.record()
        self.assertIsNone(result["devices"][0]["building"])
        self.assertIsNone(result["devices"][0]["floor"])
        self.assertEqual(result["normal_devices"], 0)
        self.assertEqual(len(result["devices"][0]["configuration_missing"]), 4)

    def test_missing_expected_port_is_unknown_not_normal(self):
        self.monitor.record("test-switch", success=True, ports=[{"interface":"Et3","status":"connected"}], at=stamp(self.at))
        result = self.monitor.snapshot(self.at)
        self.assertEqual(result["normal_devices"], 0)
        self.assertEqual(result["devices"][0]["port_states"][0]["state"], "unknown")

    def test_repeated_timestamp_does_not_confirm(self):
        self.record(uplink="down", advance=0)
        result = self.record(uplink="down", advance=0)
        self.assertEqual(result["metrics"]["uplink_faults"], 0)

    def test_reference_deployment_never_reports_live_normal(self):
        self.record()
        result = self.new_monitor(reference_only=True).snapshot(self.at)
        self.assertEqual(result["normal_devices"], 0)
        self.assertTrue(result["reference_only"])

    def test_config_validation(self):
        self.config["settings"]["interval_seconds"] = 0
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_config(self.config_path)

    def test_removed_target_is_not_falsely_marked_recovered(self):
        self.record(uplink="down")
        self.record(uplink="down")
        self.monitor.config["devices"]["test-switch"]["uplinks"] = []
        result = self.record()
        self.assertEqual(result["history"][0]["ended_reason"], "감시 설정 변경")
        self.assertIsNone(result["history"][0]["recovered_at"])

    def test_connection_refused_is_not_unreachable(self):
        with patch("socket.create_connection", side_effect=ConnectionRefusedError()):
            self.assertIs(management_reachable(self.monitor.inventory.get_device("test-switch")), True)

    def test_unknown_device_request_does_not_probe_or_record_outage(self):
        with patch.object(self.monitor, "probe") as probe:
            self.monitor.consume({"device_id": "missing", "purpose": "interfaces", "success": False})
        probe.assert_not_called()
        self.assertEqual(self.monitor.db.execute("SELECT COUNT(*) FROM devices").fetchone()[0], 0)

    def test_api_configuration_protects_access_vlan_uplink(self):
        neighbors = self.root / "neighbors.json"
        neighbors.write_text("[]", encoding="utf-8")
        app = create_app(inventory_path=self.inventory, backbone_neighbors_path=neighbors,
                         monitoring_config_path=self.config_path, data_dir=self.root/"api-data",
                         audit_log_path=self.root/"audit.jsonl", change_audit_log_path=self.root/"changes.jsonl",
                         polling_enabled=False, change_enabled=True, approval_token="test-only")
        with TestClient(app) as client:
            result = client.post("/devices/test-switch/port-admin-state/proposals", json={"interface":"Et52","desired_state":"shutdown"})
            self.assertEqual(result.status_code, 409)
            self.assertIn("업링크", result.json()["detail"])
            self.assertEqual(client.get("/fault-monitor").status_code, 200)
            self.assertNotIn("ports", client.get("/fault-monitor").json()["devices"][0])
            app.state.fault_monitor.record("test-switch", success=True, ports=[
                {"interface": "Et52", "status": "connected", "speed": "10G", "endpoint_macs": ["00:11:22:33:44:55"]}
            ])
            panel = client.get("/fault-monitor").json()["devices"][0]["panel_ports"]
            self.assertEqual(panel, [{"interface": "Et52", "status": "connected", "speed": "10G"}])

    def test_neighbor_protection_survives_interface_only_collection(self):
        history = self.root/"data"/"observations"/"test-switch"
        history.mkdir(parents=True)
        (history/"old_topology.json").write_text(json.dumps({"ports":[{"interface":"Et4","neighbor_name":"Core"}]}), encoding="utf-8")
        protection=PortProtection(self.monitor.inventory,self.monitor,self.root/"missing.json")
        self.assertIsNotNone(protection.reason("test-switch","Et4"))
        self.assertIsNone(protection.reason("test-switch","Et5"))
        self.assertIsNotNone(protection.reason("test-switch","Ethernet52"))


if __name__ == "__main__":
    unittest.main()
