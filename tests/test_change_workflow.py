import json
import tempfile
import unittest
from pathlib import Path

from network_ai_mvp.collector.base import CommandResult
from network_ai_mvp.inventory import InventoryRepository
from network_ai_mvp.observations import find_latest_port, store_collection_observation
from network_ai_mvp.services.change_workflow import ChangeWorkflow, ChangeWorkflowError


class StatefulCollectionWorkflow:
    def __init__(self, inventory, data_dir, state):
        self.inventory = inventory
        self.data_dir = data_dir
        self.state = state

    def collect(self, device_id, purpose):
        device = self.inventory.get_device(device_id)
        status = self.state["status"]
        stdout = f"""===== show interfaces status =====
Port       Name   Status       Vlan     Duplex Speed  Type
Et19              {status:<12} 101      a-half a-10M  1000BASE-T
Et52              connected    101      full   10G    10GBASE-SR
===== show interfaces counters errors =====
Port               FCS    Align   Symbol       Rx    Runts   Giants       Tx
Et19                 0        0        0        0        0        0        0
Et52                 0        0        0        0        0        0        0
===== show interfaces description =====
Interface                      Status         Protocol           Description
Et19                           {"admin down     down" if status == "disabled" else "up             up"}                 Test endpoint
Et52                           up             up                 Uplink
"""
        result = CommandResult(
            device_id=device.device_id,
            hostname=device.hostname,
            management_ip=device.management_ip,
            purpose=purpose,
            commands=("show interfaces status", "show interfaces counters errors", "show interfaces description"),
            stdout=stdout,
            stderr="",
            returncode=0,
        )
        observation = store_collection_observation(self.data_dir, device=device, result=result)
        return {
            "success": True,
            "parsed_ports": observation["ports"],
            "error_summary": "",
        }


class StatefulWriteExecutor:
    def __init__(self, state):
        self.state = state
        self.calls = []

    def run(self, plan, *, credential_path, enable_credential_path=None):
        self.calls.append((plan, credential_path, enable_credential_path))
        self.state["status"] = "disabled" if plan.commands[2] == "shutdown" else "connected"
        return CommandResult(
            device_id=plan.device.device_id,
            hostname=plan.device.hostname,
            management_ip=plan.device.management_ip,
            purpose=plan.purpose,
            commands=plan.commands,
            stdout="controlled change completed",
            stderr="",
            returncode=0,
        )


class ChangeWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.inventory = InventoryRepository("inventory/devices.csv")
        self.state = {"status": "connected"}
        self.collection = StatefulCollectionWorkflow(self.inventory, self.root / "data", self.state)
        self.writer = StatefulWriteExecutor(self.state)
        self.workflow = ChangeWorkflow(
            inventory=self.inventory,
            data_dir=self.root / "data",
            audit_log_path=self.root / "change_audit.jsonl",
            collection_workflow=self.collection,
            write_executor=self.writer,
            credential_resolver=lambda _ref: self.root / "login.xml",
            enable_credential_resolver=lambda _ref: self.root / "enable.xml",
            enabled=True,
            approval_token="approved-secret",
        )
        self.collection.collect("arista-b1f-2", "interfaces")

    def test_shutdown_and_restore_are_live_verified_and_not_persisted(self):
        shutdown = self.workflow.prepare(
            device_id="arista-b1f-2",
            interface="Et19",
            desired_state="shutdown",
        )
        result = self.workflow.execute(
            proposal_id=shutdown["proposal_id"],
            approval_token="approved-secret",
        )
        self.assertTrue(result["verified"])
        self.assertEqual(result["verified_status"], "disabled")
        self.assertFalse(result["persistent"])
        self.assertEqual(find_latest_port(self.root / "data", "arista-b1f-2", "Et19")["status"], "disabled")

        restore = self.workflow.prepare(
            device_id="arista-b1f-2",
            interface="Et19",
            desired_state="no shutdown",
        )
        restored = self.workflow.execute(
            proposal_id=restore["proposal_id"],
            approval_token="approved-secret",
        )
        self.assertTrue(restored["verified"])
        self.assertEqual(restored["verified_status"], "connected")
        self.assertEqual([call[0].commands[2] for call in self.writer.calls], ["shutdown", "no shutdown"])

        records = [json.loads(line) for line in (self.root / "change_audit.jsonl").read_text().splitlines()]
        self.assertIn("prepared", [record["status"] for record in records])
        self.assertIn("executed-verified", [record["status"] for record in records])

    def test_wrong_approval_code_does_not_execute(self):
        proposal = self.workflow.prepare(
            device_id="arista-b1f-2",
            interface="Et19",
            desired_state="shutdown",
        )
        with self.assertRaises(ChangeWorkflowError) as context:
            self.workflow.execute(
                proposal_id=proposal["proposal_id"],
                approval_token="wrong",
            )
        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(self.writer.calls, [])

    def test_routed_port_is_rejected_by_backend(self):
        with self.assertRaises(ChangeWorkflowError) as context:
            self.workflow._require_eligible_port(
                {"interface": "Et20", "status": "connected", "vlan": "routed"},
                desired_state="shutdown",
            )
        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(self.writer.calls, [])


if __name__ == "__main__":
    unittest.main()
