import unittest

from network_ai_mvp.inventory import load_devices
from network_ai_mvp.policy import CommandPolicyError, build_command_plan, validate_commands


class PolicyTests(unittest.TestCase):
    def test_builds_read_only_command_plan(self) -> None:
        device = load_devices("inventory/devices.csv")[0]
        plan = build_command_plan(device, "interfaces")

        self.assertTrue(plan.read_only)
        self.assertIn("show interfaces status", plan.commands)

    def test_rejects_config_commands(self) -> None:
        with self.assertRaises(CommandPolicyError):
            validate_commands("arista", ["configure terminal"])

    def test_rejects_unlisted_show_command(self) -> None:
        with self.assertRaises(CommandPolicyError):
            validate_commands("cisco", ["show running-config"])


if __name__ == "__main__":
    unittest.main()
