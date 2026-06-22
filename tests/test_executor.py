import unittest
from base64 import b64decode
from dataclasses import replace
from pathlib import Path

from network_ai_mvp.collector import CollectorRegistry, ExecutionError, TelnetCollector
from network_ai_mvp.executor import CommandResult, PowerShellTelnetReadOnlyExecutor
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

    def test_registry_selects_telnet_collector_and_rejects_unsupported_devices(self) -> None:
        device = load_devices("inventory/devices.csv")[0]
        registry = CollectorRegistry((TelnetCollector(script_path=Path("scripts/backbone_telnet_readonly.ps1")),))

        self.assertIsInstance(registry.adapter_for(device), TelnetCollector)
        self.assertTrue(registry.supports(device))

        unsupported = replace(device, access_method="ssh")
        self.assertFalse(registry.supports(unsupported))
        with self.assertRaises(ExecutionError):
            registry.adapter_for(unsupported)

    def test_telnet_collect_batches_multiple_plans_into_one_script_invocation(self) -> None:
        device = load_devices("inventory/devices.csv")[0]
        plans = [build_command_plan(device, "interfaces"), build_command_plan(device, "endpoints")]
        collector = RecordingTelnetCollector(script_path=Path("scripts/backbone_telnet_readonly.ps1"))

        results = collector.collect(device, plans, credential_path="credential.xml")

        self.assertEqual(len(results), 1)
        self.assertEqual(len(collector.recorded_plans), 1)
        recorded = collector.recorded_plans[0]
        self.assertEqual(recorded.purpose, "check")
        self.assertIn("show interfaces status", recorded.commands)
        self.assertIn("show mac address-table", recorded.commands)
        self.assertEqual(len(recorded.commands), len(set(recorded.commands)))

    def test_telnet_helper_requires_explicit_host_and_credential_path(self) -> None:
        script = Path("scripts/backbone_telnet_readonly.ps1").read_text(encoding="utf-8")

        self.assertIn("[Parameter(Mandatory = $true)]", script)
        self.assertNotIn('[string]$HostName = "172.16.1.1"', script)
        self.assertNotIn("backbone_admin.cred.xml", script)


class RecordingTelnetCollector(TelnetCollector):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.recorded_plans = []

    def run(self, plan, *, credential_path):
        self.recorded_plans.append(plan)
        return CommandResult(
            device_id=plan.device.device_id,
            hostname=plan.device.hostname,
            management_ip=plan.device.management_ip,
            purpose=plan.purpose,
            commands=plan.commands,
            stdout="",
            stderr="",
            returncode=0,
        )


if __name__ == "__main__":
    unittest.main()
