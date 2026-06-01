import tempfile
import unittest
from pathlib import Path

from network_ai_mvp.executor import CommandResult
from network_ai_mvp.inventory import get_device, load_devices
from network_ai_mvp.observations import find_latest_port, read_latest_observation, store_collection_observation


SAMPLE_STDOUT = """===== show interfaces status =====
Port       Name   Status       Vlan     Duplex Speed  Type
Et6               connected    22       a-full a-100M 1000BASE-T
Et15              disabled     22       auto   auto   1000BASE-T
===== show interfaces counters errors =====
Port               FCS    Align   Symbol       Rx    Runts   Giants       Tx
Et6            7846661        0  7831865  9687745  1841084        0        0
Et15                 0        0        0        0        0        0        0
===== show mac address-table =====
Vlan    Mac Address       Type        Ports
22      b42e.9906.7712    DYNAMIC     Et6
===== show ip arp =====
Address         Age (sec)  Hardware Addr   Interface
172.16.22.153   0:01       b42e.9906.7712  Vlan22
"""


class ObservationStoreTests(unittest.TestCase):
    def test_stores_redacted_raw_and_latest_parsed_ports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            device = get_device(load_devices("inventory/devices.csv"), "arista-2f-outpatient")
            result = CommandResult(
                device_id=device.device_id,
                hostname=device.hostname,
                management_ip=device.management_ip,
                purpose="interfaces",
                commands=("show interfaces status", "show interfaces counters errors"),
                stdout=SAMPLE_STDOUT + "\npassword=secret-value",
                stderr="",
                returncode=0,
            )

            record = store_collection_observation(
                temp_dir,
                device=device,
                result=result,
                timestamp="2026-06-01T00:00:00Z",
            )

            self.assertEqual(record["summary"]["low_speed_connected_ports"], 1)
            self.assertEqual(record["summary"]["disabled_ports"], 1)
            self.assertEqual(record["summary"]["high_error_ports"], 1)
            raw_files = list((Path(temp_dir) / "raw" / device.device_id).glob("*.json"))
            self.assertEqual(len(raw_files), 1)
            self.assertNotIn("secret-value", raw_files[0].read_text(encoding="utf-8"))

            latest = read_latest_observation(temp_dir, device.device_id)
            self.assertIsNotNone(latest)
            port = find_latest_port(temp_dir, device.device_id, "Ethernet6")
            self.assertIsNotNone(port)
            self.assertEqual(port["interface"], "Et6")
            self.assertEqual(port["endpoint_ips"], ["172.16.22.153"])


if __name__ == "__main__":
    unittest.main()
