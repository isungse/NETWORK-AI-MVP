import unittest
from pathlib import Path

from network_ai_mvp.inventory import get_device, load_devices


class InventoryTests(unittest.TestCase):
    def test_load_seed_inventory(self) -> None:
        path = Path(__file__).resolve().parents[1] / "inventory" / "devices.csv"
        devices = load_devices(path)

        self.assertGreaterEqual(len(devices), 2)
        self.assertEqual(devices[0].device_id, "cisco-backbone")
        self.assertEqual(devices[0].credential_ref, "backbone_admin")

    def test_lookup_device_by_id(self) -> None:
        path = Path(__file__).resolve().parents[1] / "inventory" / "devices.csv"
        devices = load_devices(path)

        device = get_device(devices, "arista-10g-core")

        self.assertEqual(device.hostname, "9F_BB_ARI_17.2")
        self.assertEqual(device.management_ip, "172.17.17.2")

    def test_backbone_cisco_neighbors_are_telnet_read_only_targets(self) -> None:
        path = Path(__file__).resolve().parents[1] / "inventory" / "devices.csv"
        devices = load_devices(path)

        device = get_device(devices, "cisco-9f-data")

        self.assertEqual(device.hostname, "Data_9F_99.250")
        self.assertEqual(device.management_ip, "172.16.99.250")
        self.assertEqual(device.access_method, "telnet")
        self.assertEqual(device.credential_ref, "backbone_admin")

    def test_1f_outpatient_inventory_keeps_reference_hostname(self) -> None:
        path = Path(__file__).resolve().parents[1] / "inventory" / "devices.csv"
        devices = load_devices(path)

        device = get_device(devices, "arista-1f-outpatient")

        self.assertEqual(device.hostname, "4F_1F_ARI_104.259")
        self.assertIn("live observation", device.notes.lower())


if __name__ == "__main__":
    unittest.main()
