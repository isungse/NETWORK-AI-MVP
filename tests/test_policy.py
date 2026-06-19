import unittest

from network_ai_mvp.inventory import load_devices
from network_ai_mvp.policy import CommandPolicyError, build_command_plan, validate_commands


class PolicyTests(unittest.TestCase):
    def test_builds_read_only_command_plan(self) -> None:
        device = load_devices("inventory/devices.csv")[0]
        plan = build_command_plan(device, "interfaces")

        self.assertTrue(plan.read_only)
        self.assertIn("show interfaces status", plan.commands)

    def test_cisco_endpoint_plan_collects_correlation_inputs(self) -> None:
        device = load_devices("inventory/devices.csv")[0]
        baseline = build_command_plan(device, "baseline")
        endpoints = build_command_plan(device, "endpoints")
        port_endpoints = build_command_plan(device, "port-endpoints")

        self.assertIn("show interfaces description", baseline.commands)
        self.assertNotIn("show mac address-table", baseline.commands)
        self.assertNotIn("show ip arp", baseline.commands)
        self.assertIn("show interfaces description", endpoints.commands)
        self.assertIn("show mac address-table", endpoints.commands)
        self.assertIn("show ip arp", endpoints.commands)
        self.assertIn("show interfaces status", port_endpoints.commands)
        self.assertIn("show interfaces description", port_endpoints.commands)
        self.assertIn("show mac address-table", port_endpoints.commands)
        self.assertIn("show ip arp", port_endpoints.commands)

    def test_arista_security_logs_plan_is_read_only(self) -> None:
        device = [item for item in load_devices("inventory/devices.csv") if item.device_id == "arista-2f-1"][0]
        plan = build_command_plan(device, "security-logs")

        self.assertTrue(plan.read_only)
        self.assertEqual(plan.commands, ("terminal length 0", "show logging", "show users"))

    def test_rejects_config_commands(self) -> None:
        with self.assertRaises(CommandPolicyError):
            validate_commands("arista", ["configure terminal"])

    def test_rejects_unlisted_show_command(self) -> None:
        with self.assertRaises(CommandPolicyError):
            validate_commands("cisco", ["show running-config"])


if __name__ == "__main__":
    unittest.main()
