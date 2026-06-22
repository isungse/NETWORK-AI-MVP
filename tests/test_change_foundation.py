import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from network_ai_mvp.api import create_app
from network_ai_mvp.auth import AuthorizationError, Principal
from network_ai_mvp.inventory import load_devices
from network_ai_mvp.policy import CommandPolicyError, validate_commands
from network_ai_mvp.services.change import append_change_audit, prepare_interface_admin_change
from network_ai_mvp.write_policy import (
    WritePolicyError,
    build_interface_admin_change_plan,
    validate_write_commands,
)


class ChangeFoundationTests(unittest.TestCase):
    def test_read_only_policy_still_rejects_write_commands(self) -> None:
        with self.assertRaises(CommandPolicyError):
            validate_commands("arista", ("configure terminal", "interface Ethernet1", "shutdown", "end"))

    def test_write_policy_is_separate_and_narrow(self) -> None:
        device = load_devices("inventory/devices.csv")[1]
        plan = build_interface_admin_change_plan(device, interface="Ethernet1", desired_state="shutdown")

        self.assertFalse(plan.read_only)
        self.assertEqual(plan.purpose, "interface-admin-state")
        self.assertEqual(plan.commands, ("configure terminal", "interface Ethernet1", "shutdown", "end"))
        validate_write_commands(plan.commands)
        with self.assertRaises(WritePolicyError):
            build_interface_admin_change_plan(device, interface="Vlan10", desired_state="shutdown")

    def test_change_proposal_requires_distinct_operator_and_approver(self) -> None:
        device = load_devices("inventory/devices.csv")[1]
        operator = Principal("operator-a", "operator")
        approver = Principal("approver-a", "approver")

        proposal, plan = prepare_interface_admin_change(
            device,
            interface="Ethernet1",
            desired_state="no shutdown",
            operator=operator,
            approver=approver,
        )

        self.assertEqual(proposal.status, "approved-not-executed")
        self.assertEqual(plan.commands[2], "no shutdown")
        with self.assertRaises(AuthorizationError):
            prepare_interface_admin_change(
                device,
                interface="Ethernet1",
                desired_state="shutdown",
                operator=operator,
                approver=Principal("operator-a", "approver"),
            )

    def test_change_audit_is_dedicated_and_no_execution_route_is_exposed(self) -> None:
        device = load_devices("inventory/devices.csv")[1]
        proposal, _ = prepare_interface_admin_change(
            device,
            interface="Ethernet1",
            desired_state="shutdown",
            operator=Principal("operator-a", "operator"),
            approver=Principal("approver-a", "approver"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / "change_audit.jsonl"
            append_change_audit(audit_path, proposal)
            record = json.loads(audit_path.read_text(encoding="utf-8"))

        self.assertEqual(record["status"], "approved-not-executed")
        self.assertEqual(record["commands"], ["configure terminal", "interface Ethernet1", "shutdown", "end"])

        client = TestClient(create_app())
        response = client.post("/changes/interface-admin-state")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
