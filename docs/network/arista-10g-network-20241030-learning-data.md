# Arista 10G Network Learning Data

Source PDF: `D:\02. 메뉴얼\네트워크\10G 네트워크_20241030.pdf`
PDF last modified: `2024-11-06 09:54:17`
Recorded in workspace: `2026-05-29`

This file is a local knowledge-base record for the network maintenance AI agent. It is based on the uploaded PDF text extraction plus the live read-only check performed against Cisco backbone `172.16.1.1`.

## Source Confidence

- PDF has one page and contains extractable text.
- The PDF is a diagram, so line/cable relationships may not be fully recoverable from text extraction alone.
- Items marked `확인 필요` should not be used for automated changes until verified from live device output or the original drawing.

## High-Level Topology

- Network name in diagram: `업무망`
- Firewall: `BLUEMAX NGF 300`
- Cisco backbone: `WS-C4503-E`
- Arista 10G aggregation/core switch in diagram: `7050SX3 48*25GBE-E`
- Backbone and Arista are connected through a `10G` segment.
- Separate floor L2 switch area is shown as `1G 층간 구성`.

## Live Backbone Facts

Observed from Telnet read-only session to `172.16.1.1`.

- Hostname: `BACKBONE-SW`
- Platform: `Cisco WS-C4503-E`
- Supervisor: `Supervisor 7`
- OS: `Cisco IOS-XE 03.05.03.E`
- Management SVI observed: `Vlan1 172.16.1.1`
- SSH TCP/22 from management PC: failed
- Telnet TCP/23 from management PC: succeeded
- Uptime at check time: about `1 year, 31 weeks`

## Backbone to Arista 10G Link

Observed from live LLDP, LACP, trunk, and interface status.

- Arista neighbor name seen from Cisco LLDP: `9F_BB_ARI_17`
- Arista live hostname from device CLI: `9F_BB_ARI_17.2`
- Arista management IP confirmed by operator: `172.17.17.2/24`
- Cisco local interfaces:
  - `TenGigabitEthernet1/3`
  - `TenGigabitEthernet1/4`
- Arista neighbor ports:
  - `Ethernet47`
  - `Ethernet48`
- Cisco port-channel: `Port-channel10`
- EtherChannel protocol: `LACP`
- EtherChannel status: `Po10(SU)`, `Te1/3(P)`, `Te1/4(P)`
- Cisco interface state: `Te1/3` and `Te1/4` are `connected`, `full`, `10G`
- Cisco trunk status: `Po10` is operational trunk
- Native VLAN: `1`
- Trunk allowed VLANs on Cisco: `1-4094`
- Active VLANs forwarding on trunk: `1,10,11,22,33,44,55,66,77,88,99,101,102,254`

Observed from Arista `172.17.17.2` operator-supplied output and direct read-only Telnet verification:

- Platform: `Arista DCS-7050SX3-48YC8-F`
- Hardware version: `12.20`
- Serial number: `JMX2246A1BP`
- EOS version: `4.26.4M`
- System MAC: `ac3d.9482.2aae`
- Uptime at check time: `84 weeks`
- `Ethernet47` is connected, `10G`, `full`, member of `Port-Channel10`
- `Ethernet48` is connected, `10G`, `full`, member of `Port-Channel10`
- Arista `Po10(U)` uses `LACP(a)`
- `Et47(PG+)` and `Et48(PG+)` are bundled and in-sync
- Arista trunk native VLAN: `1`
- Arista trunk allowed VLANs: `All`
- Arista active VLANs on `Po10`: `1,10-11,22,33,44,55,66,77,88,99,101-102`
- Arista active VLANs differ from Cisco by VLAN `254`; operator confirmed VLAN `254` is for Cisco-backbone-to-firewall connectivity and is not related to the Arista 10G network
- Arista Ethernet MTU on `Et47/Et48`: `9214`
- Arista `Et47` counters: `1 output error`, `0 CRC`, `0 input errors`
- Arista `Et48` counters: `0 output errors`, `0 CRC`, `0 input errors`

Conclusion:

- Cisco `Te1/3` maps to Arista `Et47`.
- Cisco `Te1/4` maps to Arista `Et48`.
- Cisco `Po10` and Arista `Po10` are the same LACP 10G bundle.
- LACP state is healthy on both sides at the time of observation.
- VLAN `254` is `Firewall-Network` on Cisco backbone. Operator confirmed it is not intended for the Arista 10G network.

## VLAN and Gateway Data

From live backbone output:

| VLAN | Gateway / SVI | Status | Notes |
| --- | --- | --- | --- |
| 1 | `172.16.1.1` | up/up | Management SVI observed live |
| 10 | `172.17.17.1` | up/up | PDF labels `V10 : 172.17.17.1/24` |
| 11 | `172.16.11.1` | up/up | PDF labels `V11 : 172.16.11.1/24` |
| 22 | `172.16.22.1` | up/up | PDF labels `V22 : 172.16.22.1/24` |
| 33 | `172.16.33.1` | up/up | Floor network inferred from live SVI |
| 44 | `172.16.44.1` | up/up | Floor network inferred from live SVI |
| 55 | `172.16.55.1` | up/up | Floor network inferred from live SVI |
| 66 | `172.16.66.1` | up/up | Floor network inferred from live SVI |
| 77 | `172.16.77.1` | up/up | Floor network inferred from live SVI |
| 88 | `172.16.88.1` | up/up | Floor network inferred from live SVI |
| 99 | `172.16.99.1` | up/up | Floor network inferred from live SVI |
| 101 | `172.16.101.1` | up/up | PDF labels `V101 : 172.16.101.1/24` |
| 102 | `172.16.102.1` | up/up | B2F network inferred from live SVI |
| 254 | `172.16.254.1` | up/up | Firewall network inferred from description |

PDF secondary address notes:

- `172.16.104.1/24 secondary` appears under the `V11` area. Operator clarified this is the 1F outpatient IP range.
- `172.16.105.1/24 secondary` appears under the `V22` area. Operator clarified this is the 2F outpatient IP range.
- `172.16.103.1/24 secondary` appears under the `V101` area.

## Arista Device Inventory From PDF

Operator-provided text clarification:

- B2F has no Arista equipment.
- `172.16.101247` means `172.16.101.247`.

| Area/Floor | Device/IP from PDF | Model from PDF | Confidence | Notes |
| --- | --- | --- | --- | --- |
| Core/10G aggregation | `172.17.17.2/24` | PDF: `7050SX3 48*25GBE-E`; live: `DCS-7050SX3-48YC8-F` | High | Confirmed live hostname `9F_BB_ARI_17.2`; Cisco LLDP shows `9F_BB_ARI_17`; uplinks are `Et47/Et48` to Cisco `Te1/3/Te1/4` |
| 4F Arista | `172.17.17.3` | `DCS-7050TX3` | High | Confirmed by operator text |
| 4F Arista | `172.17.17.4` | `DCS-7050TX3` | High | Confirmed by operator text |
| 4F Arista | `172.16.104.250` | PDF: `DCS-7010TX-48F`; live: `DCS-7010TX-48-F` | High | 1F outpatient IP range; live hostname is `4F_1F_ARI_104.259`; see direct check section |
| 4F Arista | `172.16.105.249` | `DCS-7010TX-48F` | High | 2F outpatient IP range; live hostname is `4F_2F_ARI_105.249`; see direct check section |
| 3F Arista | `172.16.33.251` | `DCS-7010TX-48F` | High | Confirmed by operator text |
| 2F Arista | `172.16.105.247` | `DCS-7010TX-48F` | High | Confirmed by operator text |
| 2F Arista | `172.16.105.248` | `DCS-7010TX-48F` | High | Confirmed by operator text |
| 1F Arista | `172.16.104.247` | `DCS-7010TX-48F` | High | Confirmed by operator text |
| 1F Arista | `172.16.104.248` | `DCS-7010TX-48F` | High | Confirmed by operator text |
| B1F Arista | `172.16.101.247` | `DCS-7010TX-48F` | High | Operator confirmed PDF text `172.16.101247` means `172.16.101.247` |
| B1F Arista | `172.16.101.248` | `DCS-7010TX-48F` | High | Confirmed by operator text |
| B1F Arista | `172.16.101.249` | `DCS-7010TX-48F` | High | Confirmed by operator text |
| B2F Arista | None | None | High | Operator confirmed there is no Arista device on B2F |

## Arista 172.17.17.2 Downstream LLDP Map

Observed from operator-supplied output and direct read-only `show lldp neighbors` on `9F_BB_ARI_17.2`.

| Local Port | Neighbor Device ID | Neighbor Port | Notes |
| --- | --- | --- | --- |
| `Et1` | `B1F_ARI_101.247` | `Ethernet52` | B1F Arista |
| `Et2` | `B1F_ARI_101.248` | `Ethernet52` | B1F Arista |
| `Et3` | `B1F_ARI_101.249` | `Ethernet52` | B1F Arista |
| `Et5` | `1F_ARI_104.247` | `Ethernet52` | 1F Arista |
| `Et6` | `1F_ARI_104.248` | `Ethernet52` | 1F Arista |
| `Et8` | `4F_1F_ARI_104.259` | `Ethernet52` | Confirmed: reachable at management IP `172.16.104.250`; hostname uses `.259` |
| `Et9` | `2F_ARI_105.247` | `Ethernet52` | 2F Arista |
| `Et10` | `2F_ARI_105.248` | `Ethernet52` | 2F Arista |
| `Et11` | `4F_2F_ARI_105.249` | `Ethernet52` | 4F/2F aggregation naming |
| `Et36` | `b483.5100.d032` | `b483.5100.d032` | 확인 필요: hostname not advertised |
| `Et47` | `BACKBONE-SW.test.local` | `Te1/3` | Cisco backbone LACP member |
| `Et48` | `BACKBONE-SW.test.local` | `Te1/4` | Cisco backbone LACP member |
| `Et49/1` | `4F_10G_UTP_1_17.3` | `Ethernet56/1` | Management IP shown in LLDP detail as `172.17.17.3` |
| `Et51/1` | `4F_10G_UTP_2.17.4` | `Ethernet56/1` | Management IP shown in LLDP detail as `172.17.17.4` |

## Cisco 1G Floor L2 Inventory From PDF

PDF shows a separate `1G 층간 구성` section with Cisco `WS-C2960X-24TS-L` switches.

| Floor | Model from PDF | Live CDP correlation |
| --- | --- | --- |
| 9F | `WS-C2960X-24TS-L` | Live CDP shows `Data_9F_99.250` on `Gi2/21` |
| 8F | `WS-C2960X-24TS-L` | Live CDP shows `Data_8F_88.250` on `Gi2/19` |
| 7F | `WS-C2960X-24TS-L` | Live CDP shows `Data_7F_77.250` on `Gi2/17` |
| 6F | `WS-C2960X-24TS-L` | Live CDP shows `Data_6F_66.250` on `Gi2/15` |
| 5F | `WS-C2960X-24TS-L` | Live CDP shows `Data_5F_55.250` on `Gi2/13` |
| 4F | `WS-C2960X-24TS-L` | Live CDP shows `Data_4F_44.250` on `Gi2/11` |
| 3F | `WS-C2960X-24TS-L` | Live CDP shows `Data_3F_33.250` on `Gi2/9` |
| 2F | `WS-C2960X-24TS-L` | Live Cisco description shows `Gi2/7 =2F-SW-Connected=`, but CDP neighbor was not seen in captured output |
| 1F | 확인 필요 | PDF text extraction shows floor label but no clear model association |
| B1F | 확인 필요 | Live CDP shows `Data_B1F_101.251` on `Gi2/3` |
| B2F | `WS-C2960X-24TS-L` | Live CDP shows `Data_B2F_102.250` on `Gi2/1` |

## Live Backbone Port Description Correlation

Important Cisco backbone port descriptions from live output:

| Backbone Port | Status | Description |
| --- | --- | --- |
| `Te1/3` | up/up | Arista 10G LACP member inferred from LLDP |
| `Te1/4` | up/up | Arista 10G LACP member inferred from LLDP |
| `Gi2/1` | up/up | `=B2-SW-Connected=` |
| `Gi2/3` | up/up | `=B1-SW-Connected=` |
| `Gi2/5` | down/down | `=1F-SW-Connected=` |
| `Gi2/7` | down/down | `=2F-SW-Connected=` |
| `Gi2/9` | up/up | `=3F-SW-Connected=` |
| `Gi2/10` | down/down | `=3F-ARISTA-1G-Connect=` |
| `Gi2/11` | up/up | `=4F-SW-Connected=` |
| `Gi2/13` | up/up | `=5F-SW-Connected=` |
| `Gi2/15` | up/up | `=6F-SW-Connected=` |
| `Gi2/17` | up/up | `=7F-SW-Connected=` |
| `Gi2/19` | up/up | `=8F-SW-Connected=` |
| `Gi2/21` | up/up | `=9F-SW-Connected=` |
| `Gi2/23` | down/down | `=Firewall-Connected=` |
| `Gi2/24` | down/down | Unused/not connected at time of check |
| `Gi3/24` | up/up | Cisco PoE switch for 3F WiFi/AP segment, CDP neighbor `KCL_PTSM_3F_WiFi` |
| `Gi3/45` | down/down | `=Firewall-Connected=` |
| `Gi3/46` | up/up | `=Firewall-Connected=` |
| `Gi3/47` | up/up | `=IPScan-Connected=` |
| `Gi3/48` | up/up | `=IPScan-Connected=` |

## 3F WiFi / Aruba AP Path

Confirmed from Cisco backbone read-only checks.

- The relevant Cisco backbone "24번 포트" is `GigabitEthernet3/24`.
- `GigabitEthernet2/24` is not connected.
- `GigabitEthernet3/24` is connected as an access port in VLAN `33` (`3F-Network`).
- `GigabitEthernet3/24` speed/duplex: `100Mb/s`, full-duplex.
- CDP neighbor on `Gi3/24`: `KCL_PTSM_3F_WiFi`
- Neighbor platform: `Cisco WS-C2960-24PC-L`
- Neighbor management IP: `172.16.33.63`
- Neighbor port facing backbone: `FastEthernet0/2`
- Interpretation: the Aruba AP is not directly connected to Cisco backbone `Gi3/24`; Cisco PoE switch `KCL_PTSM_3F_WiFi` is connected there, and the AP is downstream of that PoE switch.

## Arista 172.16.104.250 Direct Check

Confirmed by direct read-only Telnet check.

- Management IP used for access: `172.16.104.250`
- Network role/range: 1F outpatient IP range
- Hostname: `4F_1F_ARI_104.259`
- Note: hostname does not match management IP. Operator indicated IP/hostname should normally match, so this is likely a naming mistake.
- Platform: `Arista DCS-7010TX-48-F`
- Serial number: `HBG224500RP`
- EOS version: `4.31.4M`
- Uptime at check time: `38 weeks, 4 days`
- Uplink/neighbor-facing port from 10G aggregator LLDP: `Ethernet52`
- Local `Ethernet52` status: `connected`, VLAN `11`, `full`, `10G`, `10GBASE-SR`
- Management `Ma1`: `notconnect`, routed
- All access ports are assigned to VLAN `11`.

Connected access ports at check time:

- `Et1`, `Et2`, `Et3`, `Et4`, `Et6`, `Et7`, `Et8`, `Et10`, `Et12`, `Et14`, `Et16`, `Et18`, `Et20`, `Et22`, `Et29`

Not connected access ports at check time:

- `Et5`, `Et9`, `Et11`, `Et13`, `Et15`, `Et17`, `Et19`, `Et21`, `Et23`-`Et28`, `Et30`-`Et48`

Current IP-to-port correlation from Arista MAC table plus Cisco backbone ARP:

| Arista Port | IP Address | MAC Address | LLDP Neighbor |
| --- | --- | --- | --- |
| `Et1` | `172.16.11.41` | `448a.5b3f.1e52` | Not seen |
| `Et2` | `172.16.11.120` | `24f5.aaaf.23e6` | `24f5.aaaf.23e6` |
| `Et3` | `172.16.11.18` | `107c.614f.7f05` | `DESKTOP-0VFGNK5` |
| `Et4` | `172.16.11.20` | `08bf.b805.a0b8` | `DESKTOP-DURBLAF` |
| `Et6` | `172.16.11.157` | `448a.5b3f.1c0e` | Not seen |
| `Et7` | `172.16.11.112` | `24f5.aae5.2d9a` | `24f5.aae5.2d9a` |
| `Et8` | `172.16.11.99` | `24f5.aae4.d23f` | Not seen |
| `Et10` | `172.16.11.6` | `448a.5b3f.1c92` | `448a.5b3f.1c92` |
| `Et12` | `172.16.11.5` | `24f5.aae2.7ec2` | `24f5.aae2.7ec2` |
| `Et14` | `172.16.11.209` | `448a.5b3f.1ba3` | `448a.5b3f.1ba3` |
| `Et16` | `172.16.11.30` | `24f5.aae2.4ecb` | `24f5.aae2.4ecb` |
| `Et18` | `172.16.11.123` | `24f5.aae2.95d8` | `24f5.aae2.95d8` |
| `Et20` | `172.16.11.43` | `24f5.aae2.4d7e` | `24f5.aae2.4d7e` |
| `Et22` | `172.16.11.92` | `107c.61d6.1541` | `DESKTOP-1OSD116` |
| `Et29` | `172.16.11.9` | `5c60.ba3c.725f` | `DESKTOP-3CA24UO` |
| `Et52` | uplink/many upstream MACs | many | `9F_BB_ARI_17.2` |

## Arista 172.16.105.249 Direct Check

Confirmed by direct read-only Telnet check.

- Management IP used for access: `172.16.105.249`
- Network role/range: 2F outpatient IP range
- Hostname: `4F_2F_ARI_105.249`
- Platform: `Arista DCS-7010TX-48-F`
- Serial number: `HBG224401CP`
- EOS version: `4.31.4M`
- Uptime at check time: `38 weeks, 4 days`
- Uplink/neighbor-facing port from 10G aggregator LLDP: `Ethernet52`
- Local `Ethernet52` status: `connected`, VLAN `22`, `full`, `10G`, `10GBASE-SR`
- Management `Ma1`: `notconnect`, routed
- All access ports are assigned to VLAN `22`.

Connected access ports at check time:

- `Et1`, `Et2`, `Et4`-`Et11`, `Et13`-`Et28`, `Et30`, `Et43`, `Et45`, `Et52`

Not connected access ports at check time:

- `Et3`, `Et12`, `Et29`, `Et31`-`Et42`, `Et44`, `Et46`-`Et48`

Speed notes:

- `Et1` and `Et15` negotiated `10M/full`.
- `Et6`, `Et10`, and `Et20` negotiated `100M/full`.
- Most other connected access ports negotiated `1G/full`.

Operational note:

- Operator confirmed `Et1` and `Et15` were both shut down because they negotiated `10M` and the maintenance goal was to identify the connected endpoint/terminal.
- Treat this as an approved historical maintenance action, not a current live-state assumption. Re-check live status before any recovery action.

Current IP-to-port correlation from Arista MAC table plus Cisco backbone ARP:

| Arista Port | IP Address | MAC Address | LLDP Neighbor |
| --- | --- | --- | --- |
| `Et2` | `172.16.22.41` | `e0d5.5e48.dd9e` | `e0d5.5e48.dd9e` |
| `Et4` | `172.16.22.20` | `24f5.aae1.b4f2` | Not seen |
| `Et5` | `172.16.22.62` | `408d.5cdc.b2e6` | `408d.5cdc.b2e6` |
| `Et6` | `172.16.22.153` | `b42e.9906.7712` | `b42e.9906.7712` |
| `Et7` | `172.16.22.116` | `9883.8980.9c4c` | `9883.8980.9c4c` |
| `Et8` | `172.16.22.4` | `b42e.999c.e94f` | `b42e.999c.e94f` |
| `Et9` | `172.16.22.167` | `408d.5cf4.683b` | `408d.5cf4.683b` |
| `Et10` | `172.16.22.13` | `5811.22ca.3f8a` | `DESKTOP-UF2BS7O` |
| `Et11` | `172.16.22.207` | `e0d5.5e49.c8f8` | `e0d5.5e49.c8f8` |
| `Et13` | `172.16.22.32` | `448a.5bf9.c5c1` | `448a.5bf9.c5c1` |
| `Et14` | `172.16.22.191` | `448a.5b3f.21a5` | Not seen |
| `Et16` | `172.16.22.145` | `b42e.9942.1861` | `b42e.9942.1861` |
| `Et17` | `172.16.22.157` | `448a.5bf9.9d2b` | Not seen |
| `Et18` | `172.16.22.114` | `1c1b.0d4c.796a` | `1c1b.0d4c.796a` |
| `Et19` | `172.16.22.56` | `448a.5bfb.2480` | Not seen |
| `Et20` | `172.16.22.118` | `24f5.aae7.c7c9` | `24f5.aae7.c7c9` |
| `Et21` | `172.16.22.33`, `172.16.22.74` | `b42e.9907.12da`, `b42e.999c.df0a` | `b42e.9907.12da` |
| `Et22` | `172.16.22.15` | `1c1b.0d4c.8109` | `1c1b.0d4c.8109` |
| `Et23` | `172.16.22.53` | `448a.5bf9.c6a0` | Not seen |
| `Et24` | `172.16.22.226` | `e0d5.5e78.b671` | `e0d5.5e78.b671` |
| `Et25` | `172.16.22.35` | `448a.5b3f.1c7e` | Not seen |
| `Et26` | `172.16.22.165` | `448a.5b3f.1e4f` | Not seen |
| `Et27` | `172.16.22.204` | `e0d5.5e67.7c8e` | `e0d5.5e67.7c8e` |
| `Et28` | `172.16.22.91` | `d8cb.8af9.c159` | `d8cb.8af9.c159` |
| `Et30` | `172.16.22.119` | `b42e.9907.4a52` | `b42e.9907.4a52` |
| `Et43` | `172.16.22.30` | `24f5.aaac.6682` | `24f5.aaac.6682` |
| `Et45` | `172.16.22.147` | `448a.5bf9.9d1a` | Not seen |
| `Et52` | uplink/many upstream MACs | many | `9F_BB_ARI_17.2` |

## Firewall Network

Confirmed by operator and Cisco backbone read-only checks.

- Firewall model/name from PDF and operator: `BLUEMAX NGF 300`
- VLAN: `254`
- VLAN name on Cisco backbone: `Firewall-Network`
- Cisco SVI: `Vlan254 172.16.254.1`
- Cisco firewall-facing access ports:
  - `Gi2/23`: `switchport access vlan 254`, `switchport mode access`, currently `down/down`
  - `Gi3/45`: `switchport access vlan 254`, `switchport mode access`, currently `down/down`
  - `Gi3/46`: `switchport access vlan 254`, `switchport mode access`, currently `up/up`
- VLAN `254` appears on Cisco trunks `Gi3/47`, `Gi3/48`, and `Po10` because those trunks allow `1-4094`.
- Arista `172.17.17.2` does not show VLAN `254` active on `Po10`; this is acceptable if VLAN `254` is intentionally scoped to Cisco backbone/firewall only.

## STP Notes

Observed live on `BACKBONE-SW`:

- STP mode: `mst`
- `Root bridge for: none`
- MST0 root ID shown as `32768 1cde.a70b.f400`
- MST0 root port on backbone: `Gi2/9`

Operational implication:

- If `BACKBONE-SW` is intended to be the STP root, the current state does not match that design.
- Do not change STP priority automatically. Require explicit design confirmation and a rollback plan.

## Agent Use Rules For This Data

- Treat this file as reference data, not as authoritative live state.
- Before any change, re-check the target device live.
- Do not infer a switch management IP from floor naming alone when confidence is `Medium` or `Low`.
- Do not automate changes over Telnet except in an explicitly approved maintenance window.
- Prefer SSH/API access for future MVP operation.
- For Arista validation, first run read-only checks against candidate IPs:
  - `show hostname`
  - `show version`
  - `show interfaces status`
  - `show interfaces description`
  - `show lldp neighbors`
  - `show port-channel summary`
  - `show interfaces port-channel <id> switchport`
  - `show vlan`
  - `show spanning-tree`

## Questions / 확인 필요

1. 백본 `BACKBONE-SW`가 STP root가 되어야 하는 설계입니까, 아니면 3F 쪽 장비가 root인 현재 상태가 의도된 설계입니까?
2. Cisco `Po10`의 trunk allowed VLAN을 `1-4094` 전체 허용으로 유지하는 것이 정책입니까, 아니면 필요한 VLAN만 허용해야 합니까?
