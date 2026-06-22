import json
import tempfile
import unittest
from pathlib import Path

from network_ai_mvp.diagnostics import (
    assess_device_risks,
    detect_error_counters,
    detect_low_speed_ports,
    summarize_findings,
)
from network_ai_mvp.inventory import get_device, load_devices
from network_ai_mvp.models import PortObservation


class DiagnosticsTests(unittest.TestCase):
    def test_detects_low_speed_access_port(self) -> None:
        findings = detect_low_speed_ports(
            [
                PortObservation(
                    device_id="arista-2f-outpatient",
                    interface="Ethernet1",
                    status="connected",
                    vlan="22",
                    speed_mbps=10,
                    duplex="full",
                )
            ]
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "warning")

    def test_detects_error_counters(self) -> None:
        findings = detect_error_counters(
            [
                PortObservation(
                    device_id="arista-2f-outpatient",
                    interface="Ethernet1",
                    rx_errors=474389,
                    fcs_errors=368549,
                    runts=105840,
                    tx_errors=28213216,
                )
            ]
        )

        self.assertEqual(findings[0].severity, "critical")
        self.assertIn("fcs_errors=368549", findings[0].evidence)

    def test_summarizes_no_findings(self) -> None:
        self.assertEqual(
            summarize_findings([]),
            "No diagnostic findings from the supplied observations.",
        )

    def test_assesses_known_device_risks(self) -> None:
        device = get_device(load_devices("inventory/devices.csv"), "arista-2f-outpatient")

        findings = assess_device_risks(device)

        titles = {finding.title for finding in findings}
        self.assertIn("Temporary insecure access method", titles)
        self.assertIn("Disabled historical high-error port", titles)
        self.assertIn("High FCS/Rx/Runts indication", titles)
        historical = next(finding for finding in findings if finding.title == "Disabled historical high-error port")
        self.assertIn("Not live truth", historical.evidence)
        latest = next(finding for finding in findings if finding.title == "High FCS/Rx/Runts indication")
        self.assertEqual(latest.interface, "Ethernet6")
        self.assertIn("Live observation", latest.evidence)

    def test_assesses_latest_errdisabled_seed_risk(self) -> None:
        device = get_device(load_devices("inventory/devices.csv"), "arista-3f")

        findings = assess_device_risks(device)

        latest = next(finding for finding in findings if finding.title == "Errdisabled uplink indication")
        self.assertEqual(latest.interface, "Ethernet52")
        self.assertIn("Live observation", latest.evidence)

    def test_known_risks_are_loaded_from_reference_file(self) -> None:
        device = get_device(load_devices("inventory/devices.csv"), "arista-10g-core")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "known_risks.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "device_id": "arista-10g-core",
                            "interface": "Ethernet99",
                            "severity": "warning",
                            "title": "Fixture-only reference risk",
                            "source_classification": "reference",
                            "evidence": "fixture evidence",
                            "next_step": "fixture next step",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            findings = assess_device_risks(device, known_risks_path=path)

        fixture = next(finding for finding in findings if finding.title == "Fixture-only reference risk")
        self.assertEqual(fixture.interface, "Ethernet99")
        self.assertIn("Not live truth", fixture.evidence)

    def test_assesses_recent_audit_failures(self) -> None:
        device = get_device(load_devices("inventory/devices.csv"), "arista-10g-core")

        findings = assess_device_risks(
            device,
            audit_events=[{"device_id": "arista-10g-core", "success": False}],
        )

        self.assertIn("Recent collection failures", {finding.title for finding in findings})


if __name__ == "__main__":
    unittest.main()
