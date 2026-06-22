import tempfile
import unittest
from pathlib import Path

from network_ai_mvp.executor import CommandResult
from network_ai_mvp.inventory import get_device, load_devices
from network_ai_mvp.observations import (
    find_latest_port,
    read_latest_observation,
    read_observation_index,
    store_collection_observation,
)


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

            self.assertEqual(record["run_id"], "2026-06-01T00_00_00Z_interfaces")
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
            index = read_observation_index(temp_dir, device.device_id)
            self.assertEqual(index[0]["run_id"], "2026-06-01T00_00_00Z_interfaces")
            self.assertEqual(index[0]["purpose"], "interfaces")
            self.assertEqual(index[0]["summary"]["high_error_ports"], 1)

    def test_corrupt_latest_observation_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            latest_path = Path(temp_dir) / "observations" / "arista-2f-outpatient" / "latest.json"
            latest_path.parent.mkdir(parents=True)
            latest_path.write_text("{not-json", encoding="utf-8")

            self.assertIsNone(read_latest_observation(temp_dir, "arista-2f-outpatient"))
            self.assertIsNone(find_latest_port(temp_dir, "arista-2f-outpatient", "Et6"))


if __name__ == "__main__":
    unittest.main()
