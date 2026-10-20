"""Operator-confirmed downstream hubs and separately timestamped endpoint evidence."""
from __future__ import annotations

import ipaddress
import json
import unicodedata
from datetime import UTC, datetime

from ..parsers import command_sections, parse_ip_arp, parse_mac_address_table


class HubPortConflict(ValueError):
    pass


def instant(value):
    try:
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return value.astimezone(UTC) if value.tzinfo else None
    except (ValueError, TypeError):
        return None


class HubPorts:
    def __init__(self, db):
        self.db = db
        db.execute("""CREATE TABLE IF NOT EXISTS hub_ports (
            device TEXT, interface TEXT, confirmed INTEGER NOT NULL, name TEXT NOT NULL,
            revision INTEGER NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(device,interface))""")
        db.execute("""CREATE TABLE IF NOT EXISTS hub_port_audit (
            id INTEGER PRIMARY KEY, device TEXT, interface TEXT, previous TEXT NOT NULL,
            current TEXT NOT NULL, changed_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS hub_endpoint_evidence (
            device TEXT, kind TEXT, payload TEXT NOT NULL, observed_at TEXT,
            success INTEGER NOT NULL, PRIMARY KEY(device,kind))""")

    def get(self, device, interface):
        row = self.db.execute("SELECT confirmed,name,revision,updated_at FROM hub_ports WHERE device=? AND interface=?",
                              (device, interface)).fetchone()
        return dict(zip(("confirmed", "name", "revision", "updated_at"), (bool(row[0]), *row[1:]))) if row else {
            "confirmed": False, "name": "", "revision": 0, "updated_at": None}

    def registered(self, device=None):
        rows = self.db.execute("SELECT device,interface FROM hub_ports WHERE confirmed=1").fetchall()
        return {interface: self.get(owner, interface) for owner, interface in rows if owner == device} if device else bool(rows)

    def save(self, device, interface, confirmed, name, expected_revision, at):
        if type(confirmed) is not bool or not isinstance(name, str) or type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("허브 연결 여부, 장비명과 기존 정보 버전을 올바르게 지정하세요.")
        if len(name) > 80 or any(unicodedata.category(c).startswith("C") for c in name):
            raise ValueError("허브 장비명은 제어 문자 없이 80자 이내로 입력하세요.")
        name = name.strip() if confirmed else ""
        previous = self.get(device, interface)
        if previous["revision"] != expected_revision:
            raise HubPortConflict("다른 직원이 허브 정보를 수정했습니다. 편집 창을 닫고 최신 정보에서 다시 편집하세요.")
        if previous["confirmed"] == confirmed and previous["name"] == name:
            return previous
        current = {"confirmed": confirmed, "name": name, "revision": previous["revision"] + 1, "updated_at": at}
        self.db.execute("INSERT OR REPLACE INTO hub_ports VALUES (?,?,?,?,?,?)",
                        (device, interface, confirmed, name, current["revision"], at))
        self.db.execute("INSERT INTO hub_port_audit(device,interface,previous,current,changed_at) VALUES (?,?,?,?,?)",
                        (device, interface, json.dumps(previous, ensure_ascii=False), json.dumps(current, ensure_ascii=False), at))
        return current

    def consume(self, response):
        """Never derive hub registration from a MAC count or touch interface health."""
        if not response.get("success"):
            if response.get("purpose") in {"endpoints", "port-endpoints", "switching", "check", "link-diagnostics"}:
                self.db.execute("UPDATE hub_endpoint_evidence SET success=0 WHERE device=?", (response["device_id"],))
                return True
            return False
        at = response.get("collected_at")
        when = instant(at)
        if not when or when > datetime.now(UTC):
            return False
        sections = command_sections(str(response.get("stdout") or ""))
        changed = False
        for kind, command, parser in (("mac", "show mac address-table", parse_mac_address_table),
                                       ("arp", "show ip arp", parse_ip_arp)):
            if command not in sections or not response.get("success"):
                continue
            section = sections[command]
            if not section.strip() or any(error in section.lower() for error in ("invalid input", "not authorized", "permission denied", "% error")):
                self.db.execute("UPDATE hub_endpoint_evidence SET success=0 WHERE device=? AND kind=?", (response["device_id"], kind))
                changed = True
                continue
            row = self.db.execute("SELECT observed_at FROM hub_endpoint_evidence WHERE device=? AND kind=?",
                                  (response["device_id"], kind)).fetchone()
            if row and instant(row[0]) and when <= instant(row[0]):
                continue
            payload = parser(section)
            if kind == "mac":
                payload = {port: sorted(macs) for port, macs in payload.items()}
            else:
                payload = [entry for entry in payload if self._valid_ip(entry["ip"])]
            self.db.execute("INSERT OR REPLACE INTO hub_endpoint_evidence VALUES (?,?,?,?,1)",
                            (response["device_id"], kind, json.dumps(payload), at))
            changed = True
        return changed

    @staticmethod
    def _valid_ip(value):
        try:
            return bool(ipaddress.IPv4Address(value))
        except ipaddress.AddressValueError:
            return False

    def endpoints(self, device, interface, *, now, stale_after):
        def stale(at):
            when = instant(at)
            return not when or not 0 <= (now - when).total_seconds() <= stale_after

        mac_row = self.db.execute("SELECT payload,observed_at,success FROM hub_endpoint_evidence WHERE device=? AND kind='mac'", (device,)).fetchone()
        mac_at = mac_row[1] if mac_row else None
        macs = json.loads(mac_row[0]).get(interface, []) if mac_row else []
        # Use only the latest complete ARP table per source; an empty table removes old bindings.
        bindings = {}
        for source, payload, at, success in self.db.execute("SELECT device,payload,observed_at,success FROM hub_endpoint_evidence WHERE kind='arp'"):
            for entry in json.loads(payload):
                if entry["mac"] not in macs:
                    continue
                key = (entry["mac"], entry["ip"])
                if key not in bindings or at > bindings[key]["observed_at"]:
                    bindings[key] = {"ip": entry["ip"], "source_device_id": source, "observed_at": at, "stale": not success or stale(at)}
        return {"mac_observed_at": mac_at, "mac_stale": not mac_row or not mac_row[2] or stale(mac_at),
                "endpoints": [{"mac": mac, "ips": sorted([value for (owner, _), value in bindings.items() if owner == mac],
                                                          key=lambda value: ipaddress.IPv4Address(value["ip"]))} for mac in macs]}
