import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from network_ai_mvp.mac_diagnostics import build_interface_mac_diagnostic
from network_ai_mvp.port_diagnostics import (
    build_port_connection_diagnostic,
    build_recent_link_diagnostic,
    ping_target,
)


class PortConnectionDiagnosticTests(unittest.TestCase):
    def test_builds_state_history_and_deduplicated_link_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observations = root / "observations" / "cisco-backbone"
            raw = root / "raw" / "cisco-backbone"
            observations.mkdir(parents=True)
            raw.mkdir(parents=True)
            down = {
                "timestamp": "2026-06-15T02:58:51Z",
                "purpose": "check",
                "ports": [{"interface": "Gi3/15", "status": "notconnect", "vlan": "1"}],
            }
            up = {
                "timestamp": "2026-07-14T02:47:41Z",
                "purpose": "port-endpoints",
                "ports": [
                    {
                        "interface": "Gi3/15",
                        "status": "connected",
                        "vlan": "1",
                        "speed": "a-1000",
                        "duplex": "a-full",
                        "endpoint_ips": ["172.16.1.31"],
                        "endpoint_macs": ["9009.d096.cbc5"],
                        "fcs_errors": 0,
                        "rx_errors": 0,
                        "tx_errors": 0,
                    }
                ],
            }
            (observations / "2026-06-15_check.json").write_text(json.dumps(down), encoding="utf-8")
            (observations / "2026-07-14_port-endpoints.json").write_text(json.dumps(up), encoding="utf-8")
            (observations / "latest.json").write_text(json.dumps(up), encoding="utf-8")
            log_line = (
                "Jul 14 2026 11:39:03 KST: %LINK-3-UPDOWN: "
                "Interface GigabitEthernet3/15, changed state to up"
            )
            for name in ("first.json", "second.json"):
                (raw / name).write_text(json.dumps({"stdout": log_line}), encoding="utf-8")

            payload = build_port_connection_diagnostic(
                root,
                device_id="cisco-backbone",
                interface="GigabitEthernet3/15",
            )

            self.assertTrue(payload["data_available"])
            self.assertEqual(payload["severity"], "normal")
            self.assertEqual(payload["endpoint_ips"], ["172.16.1.31"])
            self.assertEqual(payload["mac_diagnostic"]["reason"], "single_mac_learned")
            self.assertEqual(payload["mac_diagnostic"]["count"], 1)
            self.assertEqual([item["status"] for item in payload["history"]], ["notconnect", "connected"])
            self.assertEqual(len(payload["link_events"]), 1)
            self.assertEqual(payload["last_link_event"]["timestamp"], "2026-07-14T11:39:03+09:00")
            self.assertEqual(payload["diagnostic_window"]["minutes"], 10)

    def test_limits_link_diagnostic_to_latest_ten_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observations = root / "observations" / "cisco-backbone"
            raw = root / "raw" / "cisco-backbone"
            observations.mkdir(parents=True)
            raw.mkdir(parents=True)
            observation = {
                "timestamp": "2026-07-14T02:47:41Z",
                "purpose": "port-endpoints",
                "ports": [
                    {
                        "interface": "Gi3/15",
                        "status": "connected",
                        "vlan": "1",
                        "speed": "a-1000",
                        "duplex": "a-full",
                    }
                ],
            }
            (observations / "latest.json").write_text(json.dumps(observation), encoding="utf-8")
            stdout = "\n".join(
                (
                    "Jul 14 2026 11:37:00 KST: %LINK-3-UPDOWN: Interface GigabitEthernet3/16, changed state to down",
                    "Jul 14 2026 11:39:03 KST: %LINK-3-UPDOWN: Interface GigabitEthernet3/15, changed state to up",
                    "Jul 14 2026 11:39:04 KST: %LINEPROTO-5-UPDOWN: Line protocol on Interface GigabitEthernet3/15, changed state to up",
                )
            )
            (raw / "latest.json").write_text(
                json.dumps({"timestamp": "2026-07-14T02:48:29Z", "stdout": stdout}),
                encoding="utf-8",
            )

            payload = build_port_connection_diagnostic(
                root,
                device_id="cisco-backbone",
                interface="Gi3/15",
            )
            recent = build_recent_link_diagnostic(root, device_id="cisco-backbone")

            self.assertEqual(len(payload["link_events"]), 2)
            self.assertEqual(payload["event_sequence"]["delay_seconds"], 1)
            self.assertEqual(payload["other_port_event_count"], 0)
            self.assertIn("10-minute", payload["other_port_assessment"])
            self.assertEqual(payload["diagnostic_window"]["start"], "2026-07-14T02:38:29+00:00")
            self.assertTrue(recent["data_available"])
            self.assertEqual(recent["interface"], "Gi3/15")

    def test_explains_multiple_empty_and_uncollected_mac_evidence(self) -> None:
        multiple = build_interface_mac_diagnostic(
            {
                "status": "connected",
                "endpoint_macs": ["0000.0000.0002", "0000.0000.0001"],
                "source_purpose": "check",
            }
        )
        empty_connected = build_interface_mac_diagnostic(
            {
                "status": "connected",
                "endpoint_macs": [],
                "source_purpose": "check",
            }
        )
        not_collected = build_interface_mac_diagnostic(
            {
                "status": "connected",
                "endpoint_macs": [],
                "source_purpose": "interfaces",
            }
        )

        self.assertEqual(multiple["reason"], "multiple_macs_learned")
        self.assertEqual(multiple["macs"], ["0000.0000.0001", "0000.0000.0002"])
        self.assertEqual(empty_connected["reason"], "no_mac_learned")
        self.assertTrue(empty_connected["data_available"])
        self.assertEqual(not_collected["reason"], "mac_table_not_collected")
        self.assertFalse(not_collected["data_available"])

    def test_ping_parses_successful_replies(self) -> None:
        def fake_runner(command, **kwargs):
            self.assertIn("172.16.1.31", command)
            self.assertTrue(kwargs["capture_output"])
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="\n".join("Reply from 172.16.1.31: bytes=32 time<1ms TTL=64" for _ in range(4)),
                stderr="",
            )

        payload = ping_target("172.16.1.31", runner=fake_runner)

        self.assertTrue(payload["success"])
        self.assertEqual(payload["packets_received"], 4)
        self.assertEqual(payload["packet_loss_percent"], 0)


if __name__ == "__main__":
    unittest.main()
