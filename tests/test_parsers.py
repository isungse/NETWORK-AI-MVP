import unittest

from network_ai_mvp.inventory import get_device, load_devices
from network_ai_mvp.parsers import parse_collection_ports


SAMPLE_STDOUT = """===== show interfaces status =====
Port       Name   Status       Vlan     Duplex Speed  Type
Et2               connected    22       a-full a-1G   1000BASE-T
Et6               connected    22       a-full a-100M 1000BASE-T
Et15              disabled     22       auto   auto   1000BASE-T
Et52              connected    22       full   10G    10GBASE-SR
4F_2F_ARI_105.249>
===== show interfaces counters errors =====
Port               FCS    Align   Symbol       Rx    Runts   Giants       Tx
Et2                  0        0        0        0        0        0        0
Et6            7846661        0  7831865  9687745  1841084        0        0
Et15                 0        0        0        0        0        0        0
Et52                 0        0        0        0        0        0        0
===== show interfaces description =====
Interface                      Status         Protocol           Description
Et2                            up             up                 Desk terminal
Et6                            up             up                 Slow endpoint
Et15                           admin down     down               Operator disabled
Et52                           up             up                 Uplink to core
===== show mac address-table =====
          Mac Address Table
Vlan    Mac Address       Type        Ports
22      b42e.9906.7712    DYNAMIC     Et6
22      5c60.ba3c.725f    DYNAMIC     Et29       1       1 day, 3:10:37 ago
22      e0d5.5e48.dd9e    DYNAMIC     Et2
===== show ip arp =====
Address         Age (sec)  Hardware Addr   Interface
172.16.22.153   0:01       b42e.9906.7712  Vlan22
172.16.22.41    0:03       e0d5.5e48.dd9e  Vlan22
===== show lldp neighbors =====
show lldp neighbors
Port Neighbor Device ID Neighbor Port ID TTL
Et52 9F_BB_ARI_17.2 Ethernet9 120
"""


class ParserTests(unittest.TestCase):
    def test_parses_port_status_errors_and_endpoint_correlation(self) -> None:
        device = get_device(load_devices("inventory/devices.csv"), "arista-2f-outpatient")

        ports = parse_collection_ports(
            device=device,
            purpose="interfaces",
            commands=("show interfaces status", "show interfaces counters errors"),
            stdout=SAMPLE_STDOUT,
            timestamp="2026-06-01T00:00:00Z",
        )

        by_port = {port["interface"]: port for port in ports}
        self.assertEqual(by_port["Et6"]["status"], "connected")
        self.assertEqual(by_port["Et6"]["speed_mbps"], 100)
        self.assertEqual(by_port["Et6"]["fcs_errors"], 7846661)
        self.assertEqual(by_port["Et6"]["rx_errors"], 9687745)
        self.assertEqual(by_port["Et6"]["runts"], 1841084)
        self.assertEqual(by_port["Et6"]["endpoint_ips"], ("172.16.22.153",))
        self.assertEqual(by_port["Et6"]["endpoint_macs"], ("b42e.9906.7712",))
        self.assertEqual(by_port["Et29"]["endpoint_macs"], ("5c60.ba3c.725f",))
        self.assertNotIn("ago", by_port)
        self.assertNotIn("show", by_port)
        self.assertEqual(by_port["Et52"]["neighbor_name"], "9F_BB_ARI_17.2")
        self.assertEqual(by_port["Et15"]["status"], "disabled")
        self.assertEqual(by_port["Et52"]["speed_mbps"], 10000)


if __name__ == "__main__":
    unittest.main()
