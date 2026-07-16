from __future__ import annotations

from typing import Any


MAC_TABLE_PURPOSES = frozenset(
    {
        "check",
        "endpoints",
        "port-endpoints",
        "link-diagnostics",
        "switching",
    }
)


def build_interface_mac_diagnostic(port: dict[str, Any]) -> dict[str, Any]:
    """Explain the MAC-table evidence associated with one interface.

    A MAC learned on an interface is Layer-2 forwarding evidence. It is not
    necessarily a directly attached endpoint: an uplink, trunk, bridge, access
    point, phone, or virtualized host can legitimately expose multiple MACs.
    """

    macs = sorted({str(mac) for mac in (port.get("endpoint_macs") or []) if str(mac).strip()})
    source_purpose = str(port.get("source_purpose") or "").strip().lower()
    explicit_collection_state = port.get("mac_table_collected")
    collected = (
        bool(explicit_collection_state)
        if explicit_collection_state is not None
        else bool(macs) or source_purpose in MAC_TABLE_PURPOSES
    )
    status = str(port.get("status") or "unknown").strip().lower()

    if len(macs) > 1:
        reason = "multiple_macs_learned"
        scope = "multiple-downstream"
        message = (
            f"{len(macs)} MAC addresses were learned on this interface. "
            "This commonly indicates downstream Layer-2 connectivity such as an uplink, trunk, "
            "bridge, access point, phone plus PC, or virtualized host; verify topology before "
            "treating every MAC as directly attached."
        )
    elif len(macs) == 1:
        reason = "single_mac_learned"
        scope = "single"
        message = "One MAC address was learned on this interface in the stored snapshot."
    elif not collected:
        reason = "mac_table_not_collected"
        scope = "unavailable"
        message = (
            "The source collection did not include usable MAC address-table evidence. "
            "Run the read-only endpoints, port-endpoints, switching, link-diagnostics, or CHECK collection."
        )
    elif status not in {"connected", "up"}:
        reason = "port_not_up"
        scope = "none"
        message = (
            f"No MAC address was learned and the latest port status is {status or 'unknown'}. "
            "A down or disabled port normally has no current dynamic MAC entry."
        )
    else:
        reason = "no_mac_learned"
        scope = "none"
        message = (
            "The MAC table was collected, but no MAC address was learned on this connected interface "
            "at snapshot time. The endpoint may not have sent traffic, the dynamic entry may have aged "
            "out, or the device may be sleeping or not forwarding Layer-2 traffic."
        )

    return {
        "data_available": collected,
        "collected": collected,
        "reason": reason,
        "scope": scope,
        "count": len(macs),
        "macs": macs,
        "message": message,
        "source_purpose": port.get("source_purpose"),
        "source_timestamp": port.get("source_timestamp"),
    }
