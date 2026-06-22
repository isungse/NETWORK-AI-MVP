from __future__ import annotations

from ..thresholds import has_high_error_counters, is_low_speed_connected_port


def build_check_items(
    *,
    success: bool,
    ports: object,
    summary: object,
    error_summary: str,
) -> list[dict[str, str]]:
    if not success:
        message = error_summary or "Read-only collection failed."
        return [
            _check_item("low_speed", "저속 협상 포트 자동 탐지", "fail", message),
            _check_item("high_errors", "CRC/error 많은 포트 탐지", "fail", message),
            _check_item("uplink_lacp_trunk", "uplink/LACP/trunk 자동 판정", "fail", message),
            _check_item("ip_mac_port", "IP-MAC-Port 자동 추적", "fail", message),
            _check_item("topology_mismatch", "구성도와 실제 연결 상태 불일치 탐지", "fail", message),
        ]

    port_rows = ports if isinstance(ports, list) else []
    summary_map = summary if isinstance(summary, dict) else {}
    interface_findings = build_interface_findings(port_rows)
    low_speed = interface_findings["low_speed_connected_ports"]
    high_errors = interface_findings["high_error_ports"]
    endpoint_ports = [
        port
        for port in port_rows
        if isinstance(port, dict) and (port.get("endpoint_ips") or port.get("endpoint_macs"))
    ]
    neighbor_ports = [
        port
        for port in port_rows
        if isinstance(port, dict) and (port.get("neighbor_name") or port.get("neighbor_ip"))
    ]

    items = [
        _check_item(
            "low_speed",
            "저속 협상 포트 자동 탐지",
            "warn" if low_speed else "ok",
            _port_list(low_speed) if low_speed else "저속으로 연결된 포트가 수집 결과에서 발견되지 않았습니다.",
        ),
        _check_item(
            "high_errors",
            "CRC/error 많은 포트 탐지",
            "warn" if high_errors else "ok",
            _port_list(high_errors, include_errors=True) if high_errors else "높은 오류 카운터 포트가 수집 결과에서 발견되지 않았습니다.",
        ),
        _check_item(
            "uplink_lacp_trunk",
            "uplink/LACP/trunk 자동 판정",
            "not_evaluated",
            "read-only switching/topology 명령은 수집했습니다. LACP/trunk 자동 판정 파서는 아직 구현되지 않아 정상/이상 여부를 판정하지 않았습니다.",
        ),
        _check_item(
            "ip_mac_port",
            "IP-MAC-Port 자동 추적",
            "ok" if endpoint_ports else "unknown",
            f"{len(endpoint_ports)}개 포트에서 IP/MAC 상관관계를 확인했습니다."
            if endpoint_ports
            else "MAC/ARP 상관관계가 수집 결과에서 확인되지 않았습니다.",
        ),
        _check_item(
            "topology_mismatch",
            "구성도와 실제 연결 상태 불일치 탐지",
            "ok" if neighbor_ports else "unknown",
            f"{len(neighbor_ports)}개 포트에서 live neighbor 관측값을 확인했습니다. 문서 대비 자동 비교는 다음 단계입니다."
            if neighbor_ports
            else "live LLDP/CDP neighbor 관측값이 부족해 문서 대비 불일치를 판정하지 않았습니다.",
        ),
    ]
    if not port_rows and int(summary_map.get("total_ports") or 0) == 0:
        for item in items[:2]:
            item["status"] = "unknown"
            item["detail"] = "수집은 성공했지만 파싱 가능한 포트 상태가 없습니다."
    return items


def build_interface_findings(ports: object) -> dict[str, list[dict[str, object]]]:
    port_rows = ports if isinstance(ports, list) else []
    low_speed = []
    disabled = []
    high_errors = []
    for port in port_rows:
        if not isinstance(port, dict):
            continue
        if is_low_speed_connected_port(port):
            low_speed.append(_port_finding(port))
        if port.get("status") in {"disabled", "errdisabled"}:
            disabled.append(_port_finding(port))
        if has_high_error_counters(port):
            high_errors.append(_port_finding(port, include_errors=True))
    return {
        "low_speed_connected_ports": low_speed,
        "disabled_ports": disabled,
        "high_error_ports": high_errors,
    }


def _check_item(key: str, label: str, status: str, detail: str) -> dict[str, str]:
    return {"key": key, "label": label, "status": status, "detail": detail}


def _port_list(ports: list[object], *, include_errors: bool = False) -> str:
    rows = []
    for port in ports[:12]:
        if not isinstance(port, dict):
            continue
        finding = _port_finding(port, include_errors=include_errors)
        base = f"{finding['interface']}: status={finding['status']}, vlan={finding['vlan']}, speed={finding['speed']}"
        if include_errors:
            base += (
                f", FCS={finding['fcs_errors']}, Rx={finding['rx_errors']}, "
                f"Runts={finding['runts']}, Tx={finding['tx_errors']}"
            )
        rows.append(base)
    if len(ports) > 12:
        rows.append(f"... 외 {len(ports) - 12}개")
    return "\n".join(rows)


def _port_finding(port: dict[str, object], *, include_errors: bool = False) -> dict[str, object]:
    finding = {
        "interface": port.get("interface") or "-",
        "status": port.get("status") or "-",
        "vlan": port.get("vlan") or "-",
        "duplex": port.get("duplex") or "-",
        "speed": port.get("speed") or "-",
    }
    if include_errors:
        finding.update(
            {
                "fcs_errors": int(port.get("fcs_errors") or 0),
                "rx_errors": int(port.get("rx_errors") or 0),
                "runts": int(port.get("runts") or 0),
                "tx_errors": int(port.get("tx_errors") or 0),
            }
        )
    return finding
