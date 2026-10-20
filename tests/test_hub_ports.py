"""Manual hub registration must survive collection/restarts and retain evidence provenance."""
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from network_ai_mvp.api import create_app
from network_ai_mvp.executor import CommandResult


MAC = "004e.01fc.789c"
ARP = "===== show ip arp =====\nInternet  172.16.101.16  0  004e.01fc.789c  ARPA  Vlan101\n"
TABLE = "===== show mac address-table =====\nVlan Mac Address Type Ports\n101 004e.01fc.789c DYNAMIC Et17 0 0:00:01 ago\n"


class Executor:
    def __init__(self):
        self.calls = []

    def run(self, plan, *, credential_path):
        self.calls.append((plan.device.device_id, plan.purpose, plan.commands))
        return CommandResult(device_id=plan.device.device_id, hostname=plan.device.hostname,
                             management_ip=plan.device.management_ip, purpose=plan.purpose,
                             commands=plan.commands, stdout=TABLE if plan.device.vendor == "arista" else ARP,
                             stderr="", returncode=0)


class HubPortsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.executor = Executor()
        self.app = self.new_app()
        self.monitor = self.app.state.fault_monitor
        self.monitor.record("arista-b1f-1", success=True, ports=[
            {"interface": "Et17", "status": "connected", "vlan": "101"},
            {"interface": "Et18", "status": "notconnect"}, {"interface": "Vl101"}, {"interface": "Ma1"}])
        self.client = TestClient(self.app)
        self.url = "/fault-monitor/devices/arista-b1f-1/ports/Et17/hub"

    def new_app(self):
        return create_app(data_dir=self.root / "data", audit_log_path=self.root / "audit.jsonl",
                          change_audit_log_path=self.root / "changes.jsonl", executor=self.executor,
                          credential_resolver=lambda _: self.root / "test.cred", polling_enabled=False, change_enabled=False)

    def save(self, confirmed=True, name="", revision=0):
        return self.client.post(self.url, json={"confirmed": confirmed, "name": name, "expected_revision": revision})

    def consume(self, device, stdout, at=None, success=True, purpose="endpoints"):
        self.monitor.consume({"device_id": device, "purpose": purpose, "success": success,
                              "stdout": stdout, "collected_at": at or datetime.now(UTC).isoformat()})

    def test_manual_registration_persistence_audit_conflict_and_removal(self):
        self.assertEqual(self.client.get(self.url).json()["hub"]["revision"], 0)
        before = self.client.get("/fault-monitor/devices/arista-b1f-1").json()
        result = self.save(name="  지하 검사실 허브  ").json()
        self.assertEqual(result["hub"]["name"], "지하 검사실 허브")
        self.assertEqual(self.save(name="다른 직원").status_code, 409)
        self.assertEqual(self.save(name="지하 검사실 허브", revision=1).status_code, 200)
        self.assertEqual(self.monitor.db.execute("SELECT count(*) FROM hub_port_audit").fetchone()[0], 1)
        after = self.client.get("/fault-monitor/devices/arista-b1f-1").json()
        self.assertTrue(after["hub_ports"]["Et17"]["confirmed"])
        for field in ("history", "checked_at", "status", "config", "port_states"):
            self.assertEqual(after[field], before[field])
        self.assertIn("허브", after["ports"][0]["protection_reason"])
        restarted = TestClient(self.new_app())
        self.assertEqual(restarted.get(self.url).json()["hub"]["name"], "지하 검사실 허브")
        result = restarted.post(self.url, json={"confirmed": False, "name": "", "expected_revision": 1})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(restarted.get("/fault-monitor/devices/arista-b1f-1").json()["hub_ports"], {})
        self.assertFalse(TestClient(self.new_app()).get(self.url).json()["hub"]["confirmed"])
        self.assertEqual(self.executor.calls, [])

    def test_validation_reference_and_exact_physical_target(self):
        for payload in ({}, {"confirmed": 1, "name": "", "expected_revision": 0},
                        {"confirmed": True, "name": "a" * 81, "expected_revision": 0},
                        {"confirmed": True, "name": "두\n줄", "expected_revision": 0},
                        {"confirmed": True, "name": "숨김\u202e문자", "expected_revision": 0},
                        {"confirmed": True, "name": None, "expected_revision": 0},
                        {"confirmed": True, "name": "", "expected_revision": False}):
            self.assertEqual(self.client.post(self.url, json=payload).status_code, 422)
        body = {"confirmed": True, "name": "", "expected_revision": 0}
        for interface in ("Vl101", "Ma1", "Po10", "Fa0"):
            self.assertEqual(self.client.post(self.url.replace("Et17", interface), json=body).status_code, 422)
        self.assertEqual(self.client.post(self.url.replace("Et17", "Et99"), json=body).status_code, 404)
        self.assertEqual(self.client.post(self.url.replace("arista-b1f-1", "missing"), json=body).status_code, 404)
        self.assertEqual(self.client.post(self.url.replace("Et17", "Ethernet17"), json=body).status_code, 200)
        with patch("network_ai_mvp.api.IS_VERCEL", True):
            reference = TestClient(self.new_app())
        reference.app.state.fault_monitor.record("arista-b1f-1", success=True,
                                                ports=[{"interface": "Et17", "status": "connected"}])
        self.assertEqual(reference.post(self.url, json=body).status_code, 403)
        self.assertEqual(reference.post(self.url + "/refresh").status_code, 403)
        self.assertFalse(reference.get(self.url).json()["editable"])
        self.assertEqual(reference.get("/fault-monitor/devices/arista-b1f-1").json()["hub_ports"], {})

    def test_endpoint_evidence_cross_device_age_failure_and_empty_replacement(self):
        now = datetime.now(UTC)
        self.consume("arista-b1f-1", TABLE, now.isoformat())
        self.consume("cisco-backbone", ARP, now.isoformat())
        # Learning multiple MACs never registers a hub; ordinary interface polling must not erase evidence.
        self.assertFalse(self.client.get(self.url).json()["hub"]["confirmed"])
        self.monitor.record("arista-b1f-1", success=True, ports=[{"interface": "Et17", "status": "connected"}])
        evidence = self.client.get(self.url).json()
        self.assertFalse(evidence["mac_stale"])
        binding = evidence["endpoints"][0]["ips"][0]
        self.assertEqual((binding["ip"], binding["source_device_id"]), ("172.16.101.16", "cisco-backbone"))
        self.assertFalse(binding["stale"])
        stale = self.monitor.hubs.endpoints("arista-b1f-1", "Et17", now=now + timedelta(seconds=601), stale_after=600)
        self.assertTrue(stale["mac_stale"])
        self.assertTrue(stale["endpoints"][0]["ips"][0]["stale"])
        self.consume("cisco-backbone", "", success=False)
        self.assertTrue(self.client.get(self.url).json()["endpoints"][0]["ips"][0]["stale"])
        self.consume("arista-b1f-1", "", success=False)
        self.assertTrue(self.client.get(self.url).json()["mac_stale"])
        self.consume("cisco-backbone", "===== show ip arp =====\nProtocol Address Age Hardware Addr Type Interface\n")
        self.assertEqual(self.client.get(self.url).json()["endpoints"][0]["ips"], [])
        self.assertEqual(TestClient(self.new_app()).get(self.url).json()["endpoints"][0]["mac"], MAC)
        self.assertEqual(self.executor.calls, [])

    def test_old_future_and_unrelated_data_cannot_invent_port_bindings(self):
        now = datetime.now(UTC)
        self.consume("arista-b1f-1", TABLE, now.isoformat())
        self.consume("arista-b1f-1", TABLE.replace("Et17", "Et18"), (now - timedelta(seconds=10)).isoformat())
        self.consume("arista-b1f-1", TABLE.replace("Et17", "Et18"), (now + timedelta(days=1)).isoformat())
        self.consume("cisco-backbone", ARP.replace(MAC, "ffff.ffff.ffff"))
        evidence = self.client.get(self.url).json()
        self.assertEqual(evidence["endpoints"], [{"mac": MAC, "ips": []}])
        self.assertEqual(self.client.get(self.url.replace("Et17", "Et18")).json()["endpoints"], [])

    def test_refresh_uses_only_fixed_read_only_endpoint_plans(self):
        self.assertEqual(self.client.post(self.url + "/refresh").status_code, 409)
        self.save()
        response = self.client.post(self.url + "/refresh")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual([(d, p) for d, p, _ in self.executor.calls], [("arista-b1f-1", "endpoints"), ("cisco-backbone", "endpoints")])
        self.assertTrue(all(command == "terminal length 0" or command.startswith("show ")
                            for _, _, commands in self.executor.calls for command in commands))
        self.assertEqual(response.json()["detail"]["endpoints"][0]["ips"][0]["ip"], "172.16.101.16")

    def test_periodic_endpoint_collection_is_limited_to_registered_switch_and_backbone(self):
        self.save()
        calls = []
        def collect(device, purpose):
            calls.append((device, purpose))
            if device == "arista-b1f-1" and purpose == "connection-events":
                raise RuntimeError("log permission denied")
            return {"success": True}
        with self.assertLogs("network_ai_mvp.services.fault_monitor", level="WARNING"), patch.object(
                self.monitor.stop_event, "wait", side_effect=lambda _: self.monitor.stop_event.set()):
            self.monitor._poll(collect)
        self.assertCountEqual([device for device, purpose in calls if purpose == "endpoints"],
                              ["arista-b1f-1", "cisco-backbone"])


if __name__ == "__main__":
    unittest.main()
