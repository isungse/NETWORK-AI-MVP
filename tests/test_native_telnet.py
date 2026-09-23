import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from network_ai_mvp.collector.base import ExecutionError
from network_ai_mvp.collector.native_telnet import NativeTelnetCollector, NativeTelnetWriteExecutor, TelnetSession
from network_ai_mvp.inventory import load_devices
from network_ai_mvp.models import CommandPlan
from network_ai_mvp.policy import build_command_plan


class NativeTelnetTests(unittest.TestCase):
    def setUp(self):
        self.device = load_devices("inventory/devices.csv")[0]
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "credential"
        self.path.write_text(json.dumps({"username": "operator", "password": "private-test-value"}))

    def test_fragmented_negotiation_and_subnegotiation(self):
        session = TelnetSession.__new__(TelnetSession)
        session.socket = Mock()
        session.state = "data"
        session.verb = 0
        self.assertEqual(session.decode(b"a\xff\xfb"), "a")
        self.assertEqual(session.decode(b"\x01b\xff\xfa\x01"), "b")
        self.assertEqual(session.decode(b"hidden\xff"), "")
        self.assertEqual(session.decode(b"\xf0c"), "c")
        session.socket.sendall.assert_called_once_with(b"\xff\xfe\x01")

    def test_policy_rejected_before_connection(self):
        with patch("network_ai_mvp.collector.native_telnet.TelnetSession") as session:
            with self.assertRaises(ValueError):
                NativeTelnetCollector().run(CommandPlan(self.device, "test", ("reload",)), credential_path=self.path)
            session.assert_not_called()

    def test_read_evidence_redacts_secret_and_closes(self):
        with patch("network_ai_mvp.collector.native_telnet.TelnetSession") as session:
            connection = session.return_value
            connection.authenticate.return_value = "SW#"
            connection.read.return_value = "private-test-value\nSW#"
            result = NativeTelnetCollector().run(build_command_plan(self.device, "interfaces"), credential_path=self.path)
            self.assertEqual(result.returncode, 0)
            self.assertNotIn("private-test-value", result.stdout)
            self.assertIn("===== show interfaces status =====", result.stdout)
            connection.close.assert_called_once()

    def test_write_stops_before_shutdown_when_interface_rejected(self):
        plan = CommandPlan(self.device, "change", ("configure terminal", "interface Gi1/1", "shutdown", "end"), False)
        with patch("network_ai_mvp.collector.native_telnet.TelnetSession") as session:
            connection = session.return_value
            connection.authenticate.return_value = "SW#"
            connection.read.side_effect = ["SW(config)#", "% Invalid input\nSW(config)#"]
            result = NativeTelnetWriteExecutor().run(plan, credential_path=self.path)
            self.assertEqual(result.returncode, 1)
            self.assertEqual([x.args[0] for x in connection.send.call_args_list], ["configure terminal", "interface Gi1/1"])

    def test_unprivileged_write_requires_enable_credential(self):
        plan = CommandPlan(self.device, "change", ("configure terminal", "interface Gi1/1", "no shutdown", "end"), False)
        with patch("network_ai_mvp.collector.native_telnet.TelnetSession") as session:
            session.return_value.authenticate.return_value = "SW>"
            with self.assertRaises(ExecutionError):
                NativeTelnetWriteExecutor().run(plan, credential_path=self.path)
            session.return_value.send.assert_not_called()

    def test_timeout_does_not_expose_credentials(self):
        with patch("network_ai_mvp.collector.native_telnet.TelnetSession", side_effect=TimeoutError("private-test-value")):
            with self.assertRaisesRegex(ExecutionError, "transport failed") as caught:
                NativeTelnetCollector().run(build_command_plan(self.device, "interfaces"), credential_path=self.path)
            self.assertNotIn("private-test-value", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
