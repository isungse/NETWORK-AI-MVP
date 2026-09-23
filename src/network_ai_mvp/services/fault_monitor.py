"""Explicit-scope fault monitoring. Collection results, never page views, advance counters."""
from __future__ import annotations

import json
import logging
import socket
import sqlite3
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, RLock, Thread

from ..audit import read_audit_events
from ..observations import read_latest_port_observation
from ..inventory import InventoryError
from ..parsers import short_interface_name

LOG = logging.getLogger(__name__)
UP = {"connected", "up"}
ADMIN_DOWN = {"disabled", "administratively down", "admin-down", "admin down"}
DOWN = {"notconnect", "down", "errdisabled", "err-disabled", *ADMIN_DOWN}
DEFAULT_SETTINGS = {
    "interval_seconds": 120, "stale_after_seconds": 600,
    "failure_threshold": 3, "recovery_threshold": 2,
    "confirmation_spacing_seconds": 10, "workers": 3,
    "collection_timeout_seconds": 30,
}


def stamp(value=None):
    return (value or datetime.now(UTC)).isoformat().replace("+00:00", "Z")


def instant(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def load_config(path):
    if not Path(path).exists():
        return {"settings": dict(DEFAULT_SETTINGS), "devices": {}}
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    settings = {**DEFAULT_SETTINGS, **config.get("settings", {})}
    bounds = {"interval_seconds": (30, 3600), "stale_after_seconds": (60, 86400),
              "failure_threshold": (1, 10), "recovery_threshold": (1, 10),
              "confirmation_spacing_seconds": (1, 3600), "workers": (1, 4), "collection_timeout_seconds": (10, 120)}
    for key, (low, high) in bounds.items():
        if type(settings[key]) is not int or not low <= settings[key] <= high:
            raise ValueError(f"Invalid monitoring setting: {key}")
    if settings["stale_after_seconds"] < settings["interval_seconds"] * 2:
        raise ValueError("stale_after_seconds must allow at least two collection intervals")
    if settings["confirmation_spacing_seconds"] > settings["interval_seconds"]:
        raise ValueError("confirmation spacing must not exceed collection interval")
    if not isinstance(config.get("devices", {}), dict):
        raise ValueError("devices must be an object")
    for device in config.get("devices", {}).values():
        for key in ("building", "floor", "location_source"):
            if device.get(key) is not None and not isinstance(device[key], str):
                raise ValueError(f"{key} must be a string or null")
        for key in ("uplinks", "important_ports"):
            if device.get(key) is None:
                continue
            if not isinstance(device[key], list):
                raise ValueError(f"{key} must be an array or null")
            seen = set()
            for port in device[key]:
                interface = short_interface_name(str(port.get("interface", "")))
                if not interface or interface in seen or not port.get("source"):
                    raise ValueError(f"{key} requires unique interfaces and an explicit source")
                seen.add(interface)
                if port.get("expected", "up") not in {"up", "disabled"}:
                    raise ValueError("expected must be up or disabled")
                if key == "uplinks" and port.get("expected", "up") != "up":
                    raise ValueError("Uplinks must be expected up")
    return {"settings": settings, "devices": config.get("devices", {})}


def management_reachable(device):
    """Only an explicit transport timeout/unreachable signal means no response.

    Connection refused means the host responded, not that the device lost power.
    Authentication, local permissions and unsupported transports stay unknown.
    """
    if device.access_method not in {"telnet", "ssh"}:
        return None
    try:
        with socket.create_connection((device.management_ip, 23 if device.access_method == "telnet" else 22), timeout=3):
            return True
    except ConnectionRefusedError:
        return True
    except TimeoutError:
        return False
    except OSError as exc:
        return False if getattr(exc, "winerror", None) in {10060, 10065} else None


class FaultMonitor:
    def __init__(self, *, inventory, config_path, data_dir, audit_path, db_path,
                 reference_only=False, probe=management_reachable):
        self.inventory = inventory
        self.config_path = Path(config_path)
        self.config = load_config(config_path)
        self.settings = self.config["settings"]
        self.data_dir = Path(data_dir)
        self.reference_only = reference_only
        self.probe = probe
        self.lock = RLock()
        self.stop_event = Event()
        self.thread = None
        self.running = False
        self.last_cycle = None
        self.next_cycle = None
        self.scheduler_error = None
        self.db_path = None if str(db_path) == ":memory:" else Path(db_path)
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        if self.db_path and self.db_path.exists():
            with closing(sqlite3.connect(str(self.db_path))) as saved:
                saved.backup(self.db)
        self.db.execute("CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY, device TEXT, metric TEXT, kind TEXT, interface TEXT, first_seen TEXT, confirmed_at TEXT, last_checked TEXT, recovered_at TEXT, ended_reason TEXT)")
        self.db.commit()
        try:
            self._bootstrap(audit_path)
        except InventoryError:
            LOG.warning("Monitoring inventory is unavailable")

    def _state(self, device_id):
        row = self.db.execute("SELECT payload FROM devices WHERE id=?", (device_id,)).fetchone()
        return json.loads(row[0]) if row else {"metrics": {}}

    def _save(self, device_id, state):
        self.db.execute("INSERT OR REPLACE INTO devices VALUES (?, ?)", (device_id, json.dumps(state, ensure_ascii=False)))

    def _bootstrap(self, audit_path):
        # Imported snapshots are a single observation, never fabricated repeated checks.
        audits = read_audit_events(audit_path, limit=5000)
        for device in self.inventory.list_devices():
            observation = read_latest_port_observation(self.data_dir, device.device_id)
            state = self._state(device.device_id)
            if observation and (not state.get("checked_at") or str(observation.get("timestamp")) > state["checked_at"]):
                self.record(device.device_id, success=True, ports=observation.get("ports", []),
                            at=observation.get("timestamp"), source="stored")
            latest_failure = next((e for e in reversed(audits) if e.get("device_id") == device.device_id
                                   and e.get("purpose") in {"interfaces", "baseline", "check", "port-endpoints", "link-diagnostics"}), None)
            state = self._state(device.device_id)
            if latest_failure and not latest_failure.get("success") and (not state.get("checked_at") or
                    (instant(latest_failure.get("timestamp")) or datetime.min.replace(tzinfo=UTC)) >
                    (instant(state.get("checked_at")) or datetime.min.replace(tzinfo=UTC))):
                self.record(device.device_id, success=False, at=latest_failure["timestamp"], source="stored")

    def consume(self, response):
        # Endpoint/topology-only results cannot refresh interface health.
        if response.get("purpose") not in {"interfaces", "baseline", "check", "port-endpoints", "link-diagnostics"}:
            return
        device_id = response["device_id"]
        try:
            device = self.inventory.get_device(device_id)
        except InventoryError:
            # Preserve the original API error; invalid requests are not device outages.
            return
        success = bool(response.get("success"))
        reachable = None
        if not success and not self.reference_only:
            reachable = self.probe(device)
        self.record(device_id, success=success, ports=response.get("parsed_ports") or [], reachable=reachable)

    def _values(self, device_id, state):
        cfg = self.config["devices"].get(device_id, {})
        values = {}
        if not state.get("success"):
            values["device"] = {"kind": "device", "raw": "bad" if state.get("reachable") is False else "unknown",
                                "label": "장비 통신 불가·원인 확인 필요" if state.get("reachable") is False else "수집 실패·상태 확인 불가",
                                "impact": cfg.get("impact") or "해당 장비 경유 통신 · 하위 영향 범위 미확인"}
        elif not any(p.get("status") for p in state.get("ports", [])):
            values["device"] = {"kind": "device", "raw": "unknown", "label": "포트 상태 수집 불완전", "impact": "장비 상태 확인 필요"}
        else:
            values["device"] = {"kind": "device", "raw": "ok", "label": "장비 통신 정상", "impact": "관리 접속 확인"}
        by_port = {short_interface_name(p.get("interface", "")): p for p in state.get("ports", [])}
        for group, kind in (("uplinks", "uplink"), ("important_ports", "important")):
            for spec in cfg.get(group) or []:
                interface = short_interface_name(spec["interface"])
                port = by_port.get(interface, {})
                status = str(port.get("status") or "").lower()
                raw = "unknown"
                label = "포트 상태 확인 불가"
                if values["device"]["raw"] == "ok":
                    if spec.get("expected", "up") == "disabled" or interface in state.get("approved_disabled", {}):
                        raw = "maintenance" if status in ADMIN_DOWN else ("bad" if status in UP | DOWN else "unknown")
                        label = "관리자 비활성화 · 감시 예외" if raw == "maintenance" else "승인된 비활성 상태와 다름"
                    elif status in UP:
                        raw, label = "ok", "정상 연결"
                    elif status in DOWN:
                        raw = "bad"
                        label = ("업링크 장애" if kind == "uplink" else "중요 포트 장애")
                        label += " · 관리상 비활성" if status in ADMIN_DOWN else " · 링크 끊김"
                values[f"{kind}:{interface}"] = {
                    "kind": kind, "interface": interface, "raw": raw, "label": label,
                    "impact": spec.get("impact") or "영향 범위 미설정", "port_status": status or "미확인",
                    "expected": spec.get("expected", "up"), "source": spec.get("source"),
                }
        return values

    def record(self, device_id, *, success, ports=None, reachable=None, at=None, source="live"):
        at = at or stamp()
        when = instant(at)
        if not when:
            return
        at = stamp(when)
        with self.lock, self.db:
            state = self._state(device_id)
            previous = instant(state.get("checked_at"))
            if previous and when <= previous:
                return
            # A gap breaks both failure and recovery streaks, but never resolves an incident.
            gap = not previous or (when - previous).total_seconds() > self.settings["stale_after_seconds"]
            state.update(checked_at=at, success=bool(success), reachable=reachable, source=source)
            if success:
                state["ports"] = ports or []
            metrics = state.setdefault("metrics", {})
            values = self._values(device_id, state)
            for key, value in values.items():
                prior = metrics.get(key, {})
                counted_at = instant(prior.get("counted_at"))
                can_count = not counted_at or (when - counted_at).total_seconds() >= self.settings["confirmation_spacing_seconds"]
                raw = value["raw"]
                bad = (prior.get("bad", 0) if not gap else 0) if raw == "bad" else 0
                good = (prior.get("good", 0) if not gap else 0) if raw == "ok" else 0
                first_seen = prior.get("first_seen") if bad else at
                if raw == "unknown" and prior.get("raw") == "unknown" and not gap:
                    first_seen = prior.get("first_seen") or at
                if can_count:
                    bad += int(raw == "bad")
                    good += int(raw == "ok")
                incident = self.db.execute("SELECT id,first_seen FROM incidents WHERE device=? AND metric=? AND recovered_at IS NULL AND ended_reason IS NULL", (device_id, key)).fetchone()
                if raw == "bad" and bad >= self.settings["failure_threshold"] and not incident:
                    cursor = self.db.execute("INSERT INTO incidents (device,metric,kind,interface,first_seen,confirmed_at,last_checked) VALUES (?,?,?,?,?,?,?)",
                                             (device_id, key, value["kind"], value.get("interface"), first_seen, at, at))
                    incident = (cursor.lastrowid, first_seen)
                if incident:
                    first_seen = incident[1]
                    self.db.execute("UPDATE incidents SET last_checked=? WHERE id=?", (at, incident[0]))
                    if raw == "ok" and good >= self.settings["recovery_threshold"]:
                        self.db.execute("UPDATE incidents SET recovered_at=? WHERE id=?", (at, incident[0]))
                        incident = None
                metrics[key] = {**value, "bad": bad, "good": good, "first_seen": first_seen,
                                "counted_at": at if can_count else prior.get("counted_at"),
                                "active": bool(incident), "checked_at": at}
            # Removing a target is not recovery; keep the incident history with an explicit end reason.
            for key in set(metrics) - set(values):
                self.db.execute("UPDATE incidents SET ended_reason='감시 설정 변경' WHERE device=? AND metric=? AND recovered_at IS NULL AND ended_reason IS NULL", (device_id, key))
                del metrics[key]
            if success and values["device"]["raw"] == "ok":
                state["last_success_at"] = at
            if values and all(v["raw"] in {"ok", "maintenance"} for v in values.values()) and not any(m.get("active") for m in metrics.values()):
                state["last_healthy_at"] = at
            self._save(device_id, state)
        self._persist()

    def _persist(self):
        with self.lock:
            if self.db_path:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                with closing(sqlite3.connect(str(self.db_path))) as saved:
                    self.db.backup(saved)

    def admin_change(self, device_id, interface, desired_state):
        interface = short_interface_name(interface)
        with self.lock, self.db:
            state = self._state(device_id)
            disabled = state.setdefault("approved_disabled", {})
            if desired_state == "shutdown":
                disabled[interface] = stamp()
                # Suppression is explicit and separately recorded, never presented as recovery.
                self.db.execute("UPDATE incidents SET ended_reason='관리자 승인 차단' WHERE device=? AND interface=? AND recovered_at IS NULL AND ended_reason IS NULL", (device_id, interface))
            else:
                disabled.pop(interface, None)
            state.get("metrics", {}).pop(f"important:{interface}", None)
            self._save(device_id, state)
        self._persist()

    def snapshot(self, now=None):
        now = now or datetime.now(UTC)
        devices = []
        with self.lock:
            for device in self.inventory.list_devices():
                state = self._state(device.device_id)
                cfg = self.config["devices"].get(device.device_id, {})
                checked = instant(state.get("checked_at"))
                stale = not checked or (now - checked).total_seconds() > self.settings["stale_after_seconds"] or checked > now + timedelta(seconds=30)
                issues = []
                missing = []
                for key, label in (("building", "건물"), ("floor", "층"), ("uplinks", "업링크"), ("important_ports", "중요 포트")):
                    if cfg.get(key) is None or (key in {"building", "floor"} and not cfg.get(key)):
                        missing.append(label)
                if missing:
                    issues.append({"kind": "configuration", "state": "unknown", "label": f"{', '.join(missing)} 미설정", "impact": "감시 범위 확인 필요", "first_seen": None, "checked_at": state.get("checked_at")})
                if stale or self.reference_only:
                    issues.append({"kind": "freshness", "state": "unknown", "label": "참고 스냅샷 · 실시간 확인 불가" if self.reference_only else ("수집 데이터 지연" if checked else "수집 기록 없음"),
                                   "impact": "현재 상태 확인 불가", "first_seen": stamp(checked + timedelta(seconds=self.settings["stale_after_seconds"])) if checked and stale else None,
                                   "checked_at": state.get("checked_at")})
                port_states = []
                current_values = self._values(device.device_id, state)
                for key, value in current_values.items():
                    metric = state.get("metrics", {}).get(key, {})
                    raw = value["raw"]
                    if stale or self.reference_only or raw == "unknown":
                        status = "unknown"
                    elif metric.get("active"):
                        status = "critical" if raw == "bad" else "pending"
                    elif raw == "bad":
                        status = "pending"
                    else:
                        status = "maintenance" if raw == "maintenance" else "normal"
                    label = value["label"]
                    if status == "pending":
                        label += " · " + (f"장애 재확인 {metric.get('bad', 0)}/{self.settings['failure_threshold']}" if raw == "bad" else f"복구 재확인 {metric.get('good', 0)}/{self.settings['recovery_threshold']}")
                    if stale or self.reference_only:
                        label = "상태 확인 불가 · 과거 수집값"
                    rendered = {**value, "state": status, "label": label, "first_seen": metric.get("first_seen"), "checked_at": state.get("checked_at")}
                    if value["kind"] != "device":
                        port_states.append(rendered)
                    if status in {"critical", "pending", "unknown"} and not stale and not self.reference_only:
                        # A device outage does not assert a simultaneous fault on every downstream port.
                        if value["kind"] == "device" or current_values["device"]["raw"] == "ok":
                            issues.append(rendered)
                status = "critical" if any(i["state"] == "critical" for i in issues) else "unknown" if issues else "normal"
                devices.append({"device_id": device.device_id, "hostname": device.hostname, "management_ip": device.management_ip,
                                "platform": device.platform, "role": device.role,
                                "building": cfg.get("building"), "floor": cfg.get("floor"), "location_source": cfg.get("location_source"),
                                "status": status, "issues": issues, "port_states": port_states, "configuration_missing": missing,
                                "checked_at": state.get("checked_at"), "last_success_at": state.get("last_success_at"),
                                "last_healthy_at": state.get("last_healthy_at") if not missing else None,
                                "stale": stale or self.reference_only,
                                "port_data_current": not stale and not self.reference_only and bool(state.get("success")) and current_values["device"]["raw"] == "ok",
                                "ports": state.get("ports", []), "config": cfg})
            rows = self.db.execute("SELECT device,kind,interface,first_seen,confirmed_at,last_checked,recovered_at,ended_reason FROM incidents ORDER BY id DESC LIMIT 300").fetchall()
        devices.sort(key=lambda d: ({"critical": 0, "unknown": 1, "normal": 2}[d["status"]], d["hostname"]))
        metrics = {"critical_devices": sum(d["status"] == "critical" for d in devices),
                   "uplink_faults": 0, "device_unreachable": 0, "important_faults": 0,
                   "unknown_devices": sum(any(i["state"] in {"unknown", "pending"} for i in d["issues"]) for d in devices),
                   "last_checked": max((d["checked_at"] for d in devices if d["checked_at"]), default=None)}
        for d in devices:
            for i in d["issues"]:
                if i["state"] == "critical" and i["kind"] in {"uplink", "device", "important"}:
                    metrics[{"uplink": "uplink_faults", "device": "device_unreachable", "important": "important_faults"}[i["kind"]]] += 1
        return {"generated_at": stamp(now), "metrics": metrics, "devices": devices,
                "total_devices": len(devices), "normal_devices": sum(d["status"] == "normal" for d in devices),
                "settings": self.settings, "scheduler": {"enabled": self.running, "last_cycle": self.last_cycle, "next_cycle": self.next_cycle, "error": self.scheduler_error},
                "reference_only": self.reference_only,
                "history": [dict(zip(("device_id", "kind", "interface", "first_seen", "confirmed_at", "last_checked", "recovered_at", "ended_reason"), row)) for row in rows]}

    def start(self, collect):
        if self.reference_only or self.thread:
            return
        self.running = True
        self.thread = Thread(target=self._poll, args=(collect,), name="network-fault-monitor", daemon=True)
        self.thread.start()

    def _poll(self, collect):
        def run(device):
            if self.stop_event.is_set():
                return
            try:
                collect(device.device_id, "interfaces")
            except Exception:
                LOG.exception("Scheduled collection failed for %s", device.device_id)
        while not self.stop_event.is_set():
            try:
                with ThreadPoolExecutor(max_workers=self.settings["workers"]) as pool:
                    list(pool.map(run, self.inventory.list_devices()))
                self.last_cycle = stamp()
                self.scheduler_error = None
            except Exception:
                LOG.exception("Fault monitor cycle failed")
                self.scheduler_error = "수집 주기 실행 실패 · 로그 확인 필요"
            self.next_cycle = stamp(datetime.now(UTC) + timedelta(seconds=self.settings["interval_seconds"]))
            self.stop_event.wait(self.settings["interval_seconds"])
        self.running = False

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=130)
        self.running = False
