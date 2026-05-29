import unittest
from base64 import b64decode
from pathlib import Path

from network_ai_mvp.executor import PowerShellTelnetReadOnlyExecutor
from network_ai_mvp.inventory import load_devices
from network_ai_mvp.policy import build_command_plan


class ExecutorTests(unittest.TestCase):
    def test_builds_powershell_args_without_secret_values(self) -> None:
        device = load_devices("inventory/devices.csv")[0]
        plan = build_command_plan(device, "baseline")
        executor = PowerShellTelnetReadOnlyExecutor(
            script_path=Path("scripts/backbone_telnet_readonly.ps1"),
            powershell_executable="powershell",
        )

        args = executor.build_args(plan, credential_path="%USERPROFILE%\\backbone_admin.cred.xml")
        decoded_command = b64decode(args[-1]).decode("utf-16le")

        self.assertIn("-EncodedCommand", args)
        self.assertIn("-HostName '172.16.1.1'", decoded_command)
        self.assertIn("-Commands @(", decoded_command)
        self.assertIn("'show version'", decoded_command)
        self.assertNotIn("password", decoded_command.lower())


if __name__ == "__main__":
    unittest.main()
