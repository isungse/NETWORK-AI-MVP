import json
import tempfile
import unittest
from pathlib import Path

from network_ai_mvp.correlation import build_port_endpoint_trace
from network_ai_mvp.services.check import build_check_items


class ServiceTests(unittest.TestCase):
    def test_build_check_items_flags_low_speed_and_high_error_ports(self) -> None:
        items = build_check_items(
            success=True,
            summary={"total_ports": 1},
            error_summary="",
            ports=[
                {
                    "interface": "Et6",
                    "status": "connected",
                    "vlan": "22",
                    "speed": "a-100M",
                    "speed_mbps": 100,
                    "fcs_errors": 1000,
                }
            ],
        )

        by_key = {item["key"]: item for item in items}
        self.assertEqual(by_key["low_speed"]["status"], "warn")
        self.assertEqual(by_key["high_errors"]["status"], "warn")
        self.assertIn("Et6", by_key["low_speed"]["detail"])

    def test_port_endpoint_trace_uses_latest_stored_arp_ips(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir) / "raw" / "cisco-backbone"
            raw_dir.mkdir(parents=True)
            (raw_dir / "20260602T000000Z.json").write_text(
                json.dumps(
                    {
                        "stdout": (
                            "===== show ip arp =====\n"
                            "Internet  172.16.11.9  0  5c60.ba3c.725f  ARPA  Vlan11\n"
                        )
                    }
                ),
                encoding="utf-8",
            )
            stdout = (
                "===== show interfaces status =====\n"
                "Port      Name               Status       Vlan       Duplex  Speed Type\n"
                "Et29                         connected    11         a-full  a-1G  1000BASE-T\n"
                "===== show interfaces description =====\n"
                "Interface                      Status         Protocol Description\n"
                "Et29                           up             up       Problem endpoint\n"
                "===== show mac address-table =====\n"
                "Vlan    Mac Address       Type        Ports      Moves   Last Move\n"
                "11      5c60.ba3c.725f    DYNAMIC     Et29       1       1 day, 3:10:37 ago\n"
            )

            trace = build_port_endpoint_trace(stdout, temp_dir)

        self.assertEqual(trace[0]["interface"], "Et29")
        self.assertEqual(trace[0]["description"], "Problem endpoint")
        self.assertEqual(trace[0]["endpoints"][0]["ips"], ("172.16.11.9",))


if __name__ == "__main__":
    unittest.main()
