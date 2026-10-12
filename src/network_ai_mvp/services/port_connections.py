"""Persistent physical-link events; a first observation is never a new connection."""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from ..parsers import short_interface_name

WINDOW = timedelta(hours=24)
RETENTION = timedelta(days=30)
PHYSICAL = re.compile(r"^(?:Et|Gi|Te|Fa)\d+(?:/\d+)*$", re.I)
MONTHS = {name: i for i, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
ZONES = {"KST": 9, "UTC": 0, "GMT": 0}
LOG = re.compile(
    r"(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<year>\d{4})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})(?:\.\d+)?\s+(?P<zone>[A-Z]+):\s+"
    r"%LINK-\d+-UPDOWN:\s+Interface\s+(?P<interface>[^,]+),\s+changed state to\s+(?P<state>up|down)\b"
)
# Read the clock command's own section, never a timestamp inside show logging.
CLOCK_SECTION = re.compile(r"={3,}\s*show clock\s*={3,}\s*(.*?)(?=={3,}|\Z)", re.S)
CLOCK = re.compile(
    r"(?P<time>\d{2}:\d{2}:\d{2})(?:\.\d+)?\s+(?P<zone>KST|UTC|GMT)\s+"
    r"\w{3}\s+(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<year>\d{4})"
)
ARISTA_CLOCK = re.compile(
    r"\w{3}\s+(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<year>\d{4})"
)
ARISTA_LOG = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"\S+\s+\S+:\s+%LINEPROTO-\d+-UPDOWN:\s+Line protocol on Interface\s+"
    r"(?P<interface>[^,]+),\s+changed state to\s+(?P<state>up|down)\b", re.M,
)


def instant(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def stamp(value):
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def device_time(match):
    """Unknown zones/dates are unsupported, rather than guessed to be UTC."""
    if not match or match["zone"] not in ZONES or match["month"] not in MONTHS:
        return None
    try:
        h, m, s = map(int, match["time"].split(":"))
        return datetime(int(match["year"]), MONTHS[match["month"]], int(match["day"]),
                        h, m, s, tzinfo=UTC) - timedelta(hours=ZONES[match["zone"]])
    except ValueError:
        return None


def read_clock(stdout):
    section = CLOCK_SECTION.search(stdout)
    if not section:
        return None, None
    match = CLOCK.search(section[1])
    if match:
        return device_time(match), match["zone"]
    match = ARISTA_CLOCK.search(section[1])
    zone_match = re.search(r"Timezone:\s*(\S+)", section[1])
    zone = {"Asia/Seoul": "KST", "UTC": "UTC", "Etc/UTC": "UTC", "GMT": "GMT"}.get(zone_match[1]) if zone_match else None
    if match and zone:
        return device_time({**match.groupdict(), "zone": zone}), zone
    return None, None


def log_events(stdout, clock, zone):
    for match in LOG.finditer(stdout):
        yield match, device_time(match)
    if clock and zone:
        for match in ARISTA_LOG.finditer(stdout):
            # Syslog omits the year. Resolve only against the device clock, including New Year rollover.
            local_year = (clock + timedelta(hours=ZONES[zone])).year
            values = {**match.groupdict(), "zone": zone, "year": str(local_year)}
            event_time = device_time(values)
            if event_time and event_time > clock + timedelta(seconds=30):
                values["year"] = str(local_year - 1)
                event_time = device_time(values)
            yield match, event_time


class PortConnections:
    """Link telemetry is history; only explicit physical confirmation produces NEW."""

    def __init__(self, db):
        self.db = db
        db.execute("""CREATE TABLE IF NOT EXISTS port_connections (
            id INTEGER PRIMARY KEY, device TEXT NOT NULL, interface TEXT NOT NULL,
            state TEXT NOT NULL, at TEXT NOT NULL, observed_at TEXT NOT NULL,
            source TEXT NOT NULL, device_at TEXT, clock_offset_seconds REAL,
            interval_start TEXT, event_key TEXT UNIQUE)""")
        db.execute("CREATE INDEX IF NOT EXISTS port_connections_lookup ON port_connections(device,interface,at)")
        db.execute("CREATE INDEX IF NOT EXISTS port_connections_time ON port_connections(at)")
        db.execute("""CREATE TABLE IF NOT EXISTS connection_log_status (
            device TEXT PRIMARY KEY, checked_at TEXT, success INTEGER, clock_verified INTEGER)""")
        db.execute("""CREATE TABLE IF NOT EXISTS port_physical_connections (
            event_key TEXT PRIMARY KEY, device TEXT NOT NULL, interface TEXT NOT NULL,
            connected_at TEXT NOT NULL, confirmed_at TEXT NOT NULL, note TEXT NOT NULL,
            revoked_at TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS port_physical_connection_audit (
            id INTEGER PRIMARY KEY, event_key TEXT NOT NULL, device TEXT NOT NULL,
            interface TEXT NOT NULL, connected_at TEXT NOT NULL, recorded_at TEXT NOT NULL,
            confirmed INTEGER NOT NULL, note TEXT NOT NULL)""")

    def observe(self, device, previous_ports, ports, previous_at, at, continuous):
        if not continuous:
            return
        previous_at, at = stamp(instant(previous_at)), stamp(instant(at))
        previous = {short_interface_name(p.get("interface", "")): p for p in previous_ports}
        for port in ports:
            name = short_interface_name(port.get("interface", ""))
            before = self._state(previous.get(name, {}).get("status"))
            after = self._state(port.get("status"))
            if not PHYSICAL.fullmatch(name) or before is None or after is None or before == after:
                continue
            found = self.db.execute("""SELECT 1 FROM port_connections WHERE device=? AND interface=?
                AND state=? AND source='device_log' AND at>=? AND at<=?""",
                (device, name, after, stamp(instant(previous_at) - timedelta(seconds=30)),
                 stamp(instant(at) + timedelta(seconds=30)))).fetchone()
            if not found:
                self.db.execute("""INSERT OR IGNORE INTO port_connections
                    (device,interface,state,at,observed_at,source,interval_start,event_key)
                    VALUES (?,?,?,?,?,'observation',?,?)""",
                    (device, name, after, at, at, previous_at, f"sample:{device}:{name}:{at}:{after}"))

    @staticmethod
    def _state(value):
        value = str(value or "").lower()
        if value in {"up", "connected"}:
            return "up"
        if value in {"down", "notconnect", "disabled", "administratively down", "admin-down",
                     "admin down", "errdisabled", "err-disabled"}:
            return "down"
        return None

    def confirm_physical(self, device, interface, event_id, *, confirmed, note="", now=None):
        now = now or datetime.now(UTC)
        interface = short_interface_name(interface)
        if type(event_id) is not int or event_id < 1 or type(confirmed) is not bool:
            raise ValueError("연결 기록과 물리 연결 확인 여부가 올바르지 않습니다.")
        if not isinstance(note, str) or len(note) > 300:
            raise ValueError("확인 근거는 300자 이내로 입력하세요.")
        row = self.db.execute("""SELECT state,at,source,event_key FROM port_connections
            WHERE id=? AND device=? AND interface=?""", (event_id, device, interface)).fetchone()
        if not row:
            raise LookupError("해당 포트의 연결 기록을 찾을 수 없습니다.")
        state, at, source, key = row
        if not PHYSICAL.fullmatch(interface) or interface == "Fa0" or (device == "cisco-backbone" and interface == "Fa1") or state != "up":
            raise ValueError("물리 포트의 연결 기록만 확인할 수 있습니다.")
        if not key or source == "device_log_unverified" or not instant(at) or instant(at) > now:
            raise ValueError("연결 시각 근거가 확인된 기록만 물리 연결로 확인할 수 있습니다.")
        current = self.db.execute("SELECT revoked_at FROM port_physical_connections WHERE event_key=?", (key,)).fetchone()
        if (current is not None and (current[0] is None) == confirmed) or (current is None and not confirmed):
            return
        recorded, connected = stamp(now), stamp(instant(at))
        self.db.execute("""INSERT INTO port_physical_connections VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(event_key) DO UPDATE SET confirmed_at=excluded.confirmed_at,
                note=excluded.note,revoked_at=excluded.revoked_at""",
            (key, device, interface, connected, recorded, note.strip(), None if confirmed else recorded))
        self.db.execute("""INSERT INTO port_physical_connection_audit
            (event_key,device,interface,connected_at,recorded_at,confirmed,note) VALUES (?,?,?,?,?,?,?)""",
            (key, device, interface, connected, recorded, int(confirmed), note.strip()))

    def consume_logs(self, device, stdout, at, success=True):
        observed = instant(at)
        if observed is None:
            return
        at = stamp(observed)
        clock, zone = read_clock(stdout)
        offset = (observed - clock).total_seconds() if clock else None
        previous = self.log_status(device)
        if not previous or observed >= instant(previous["checked_at"]):
            self.db.execute("INSERT OR REPLACE INTO connection_log_status VALUES (?,?,?,?)",
                            (device, at, int(success), int(clock is not None)))
        if not success:
            return
        for match, raw_time in log_events(stdout, clock, zone):
            name = short_interface_name(match["interface"].strip())
            if raw_time is None or not PHYSICAL.fullmatch(name):
                continue
            effective = raw_time + timedelta(seconds=offset or 0)
            if effective > observed + timedelta(seconds=30) or effective < observed - RETENTION:
                continue
            source = "device_log" if clock else "device_log_unverified"
            event_key = f"log:{device}:{name}:{stamp(raw_time)}:{match['state']}"
            existing = self.db.execute("SELECT id,source FROM port_connections WHERE event_key=?", (event_key,)).fetchone()
            if existing and (existing[1] == "device_log" or not clock):
                continue
            if existing:
                self.db.execute("DELETE FROM port_connections WHERE id=?", (existing[0],))
            if clock:
                samples = self.db.execute("""SELECT event_key FROM port_connections WHERE device=? AND interface=?
                    AND state=? AND source='observation' AND interval_start<=? AND at>=?""",
                    (device, name, match["state"], stamp(effective + timedelta(seconds=30)),
                     stamp(effective - timedelta(seconds=30)))).fetchall()
                if len(samples) == 1:
                    # Refine the evidence link without restarting the physical connection's 24-hour window.
                    self.db.execute("UPDATE port_physical_connections SET event_key=? WHERE event_key=?",
                                    (event_key, samples[0][0]))
                self.db.execute("""DELETE FROM port_connections WHERE device=? AND interface=?
                    AND state=? AND source='observation' AND interval_start<=? AND at>=?""",
                    (device, name, match["state"], stamp(effective + timedelta(seconds=30)),
                     stamp(effective - timedelta(seconds=30))))
            self.db.execute("""INSERT INTO port_connections
                (device,interface,state,at,observed_at,source,device_at,clock_offset_seconds,event_key)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (device, name, match["state"], stamp(effective), at, source, stamp(raw_time), offset, event_key))

    def prune(self, now):
        self.db.execute("DELETE FROM port_connections WHERE at<?", (stamp(now - RETENTION),))
        self.db.execute("DELETE FROM port_physical_connections WHERE connected_at<?", (stamp(now - RETENTION),))
        self.db.execute("DELETE FROM port_physical_connection_audit WHERE recorded_at<?", (stamp(now - RETENTION),))

    def history(self, device, interface, limit=100):
        rows = self.db.execute("""SELECT e.id,e.interface,e.state,e.at,e.observed_at,e.source,e.device_at,
            e.clock_offset_seconds,e.interval_start,p.confirmed_at,p.revoked_at,p.note,p.connected_at
            FROM port_connections AS e LEFT JOIN port_physical_connections AS p ON p.event_key=e.event_key
            WHERE e.device=? AND e.interface=? ORDER BY e.at DESC,e.id DESC LIMIT ?""", (device, interface, limit)).fetchall()
        result = []
        for row in rows:
            event = dict(zip(("id", "interface", "state", "at", "observed_at", "source", "device_at",
                              "clock_offset_seconds", "interval_start", "physical_confirmed_at", "physical_revoked_at",
                              "physical_confirmation_note", "physical_connected_at"), row))
            event["physical_confirmed"] = bool(row[9] and not row[10])
            result.append(event)
        return result

    def snapshot(self, now):
        rows = self.db.execute("""SELECT device,interface,MAX(connected_at),COUNT(*) FROM port_physical_connections
            WHERE revoked_at IS NULL AND connected_at>? AND connected_at<=?
            GROUP BY device,interface ORDER BY MAX(connected_at) DESC""", (stamp(now - WINDOW), stamp(now))).fetchall()
        result = {}
        for device, name, at, count in rows:
            latest = self.db.execute("""SELECT e.source,e.device_at,e.clock_offset_seconds,e.interval_start,p.confirmed_at,p.note
                FROM port_physical_connections AS p LEFT JOIN port_connections AS e ON e.event_key=p.event_key
                WHERE p.device=? AND p.interface=? AND p.connected_at=? AND p.revoked_at IS NULL
                ORDER BY p.confirmed_at DESC LIMIT 1""", (device, name, at)).fetchone()
            result.setdefault(device, {})[name] = {
                "interface": name, "connected_at": at, "expires_at": stamp(instant(at) + WINDOW),
                "connection_count": count, "repeated": count >= 3,
                "source": latest[0], "device_at": latest[1], "clock_offset_seconds": latest[2],
                "interval_start": latest[3], "age_seconds": int((now - instant(at)).total_seconds()),
                "physical_confirmed": True, "physical_confirmed_at": latest[4],
                "physical_confirmation_note": latest[5],
            }
        return result

    def log_status(self, device):
        row = self.db.execute("SELECT checked_at,success,clock_verified FROM connection_log_status WHERE device=?", (device,)).fetchone()
        return dict(zip(("checked_at", "success", "clock_verified"), row)) if row else None
