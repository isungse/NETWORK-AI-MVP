"""Persistent physical-link events; a first observation is never a new connection."""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from ..parsers import short_interface_name

WINDOW = timedelta(hours=24)
RETENTION = timedelta(days=30)
UNUSED_MINIMUM = timedelta(minutes=10)
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
    """Uses FaultMonitor's connection and lock; callers commit and persist together."""

    def __init__(self, db):
        self.db = db
        db.execute("""CREATE TABLE IF NOT EXISTS port_connections (
            id INTEGER PRIMARY KEY, device TEXT NOT NULL, interface TEXT NOT NULL,
            state TEXT NOT NULL, at TEXT NOT NULL, observed_at TEXT NOT NULL,
            source TEXT NOT NULL, device_at TEXT, clock_offset_seconds REAL,
            interval_start TEXT, event_key TEXT UNIQUE)""")
        db.execute("CREATE INDEX IF NOT EXISTS port_connections_lookup ON port_connections(device, interface, at)")
        db.execute("CREATE INDEX IF NOT EXISTS port_connections_time ON port_connections(at)")
        db.execute("""CREATE TABLE IF NOT EXISTS connection_log_status (
            device TEXT PRIMARY KEY, checked_at TEXT, success INTEGER, clock_verified INTEGER)""")
        # Additive migration: old link events remain history, without inventing unused evidence.
        columns = {row[1] for row in db.execute("PRAGMA table_info(port_connections)")}
        for column in ("unused_since", "unused_confirmed_at"):
            if column not in columns:
                db.execute(f"ALTER TABLE port_connections ADD COLUMN {column} TEXT")
        db.execute("""CREATE TABLE IF NOT EXISTS port_unused_baselines (
            device TEXT NOT NULL, interface TEXT NOT NULL, since TEXT NOT NULL,
            checked_at TEXT NOT NULL, PRIMARY KEY(device,interface))""")

    def break_continuity(self, device):
        self.db.execute("DELETE FROM port_unused_baselines WHERE device=?", (device,))

    def observe(self, device, previous_ports, ports, previous_at, at, continuous):
        current = instant(at)
        prior = instant(previous_at)
        if current is None:
            return
        at = stamp(current)
        continuous = continuous and prior is not None and prior < current
        if not continuous:
            self.break_continuity(device)
        previous_at = stamp(prior) if prior else None
        previous = {short_interface_name(p.get("interface", "")): p for p in previous_ports}
        baselines = {row[0]: row[1:] for row in self.db.execute(
            "SELECT interface,since,checked_at FROM port_unused_baselines WHERE device=?", (device,))}
        self.break_continuity(device)
        for port in ports:
            name = short_interface_name(port.get("interface", ""))
            before = self._state(previous.get(name, {}).get("status"))
            after = self._state(port.get("status"))
            if not PHYSICAL.fullmatch(name):
                continue
            baseline = baselines.get(name) if continuous else None
            if baseline and (baseline[1] != previous_at or not self._unused(previous.get(name, {}).get("status"))):
                baseline = None
            if self._unused(port.get("status")):
                self.db.execute("INSERT INTO port_unused_baselines VALUES (?,?,?,?)",
                                (device, name, baseline[0] if baseline else at, at))
            if not continuous or before is None or after is None or before == after:
                continue
            unused = baseline if after == "up" and baseline and prior - instant(baseline[0]) >= UNUSED_MINIMUM else None
            # A manual log collection may have already captured this transition.
            found = self.db.execute("""SELECT id,at FROM port_connections WHERE device=? AND interface=?
                AND state=? AND source='device_log' AND at>=? AND at<=?""",
                (device, name, after, stamp(instant(previous_at) - timedelta(seconds=30)),
                 stamp(current + timedelta(seconds=30)))).fetchall()
            if len(found) == 1:
                if unused and instant(found[0][1]) >= prior - timedelta(seconds=30):
                    self.db.execute("UPDATE port_connections SET unused_since=?,unused_confirmed_at=? WHERE id=?",
                                    (*unused, found[0][0]))
            elif not found:
                self.db.execute("""INSERT INTO port_connections
                    (device,interface,state,at,observed_at,source,interval_start,event_key,unused_since,unused_confirmed_at)
                    VALUES (?,?,?,?,?,'observation',?,?,?,?)""",
                    (device, name, after, at, at, previous_at, f"sample:{device}:{name}:{at}:{after}",
                     *(unused or (None, None))))
        self._validate_unused(device)

    @staticmethod
    def _unused(value):
        # Administratively disabled and error-disabled are never evidence of an unused socket.
        return str(value or "").lower() in {"down", "notconnect"}

    def _validate_unused(self, device):
        # Late logs can contradict sampled inactivity, including a flap between two down samples.
        self.db.execute("""UPDATE port_connections AS candidate
            SET unused_since=NULL,unused_confirmed_at=NULL WHERE device=? AND unused_since IS NOT NULL
            AND EXISTS (SELECT 1 FROM port_connections AS event WHERE event.device=candidate.device
                AND event.interface=candidate.interface AND event.source='device_log' AND event.id!=candidate.id
                AND event.at>candidate.unused_since AND event.at<=candidate.at
                AND (event.state='up' OR julianday(event.at)>julianday(candidate.unused_since)+30.0/86400))""", (device,))
        self.db.execute("""DELETE FROM port_unused_baselines AS baseline WHERE device=?
            AND EXISTS (SELECT 1 FROM port_connections AS event WHERE event.device=baseline.device
                AND event.interface=baseline.interface AND event.source='device_log'
                AND event.at>baseline.since AND event.at<=baseline.checked_at
                AND (event.state='up' OR julianday(event.at)>julianday(baseline.since)+30.0/86400))""", (device,))

    @staticmethod
    def _state(value):
        value = str(value or "").lower()
        if value in {"up", "connected"}:
            return "up"
        if value in {"down", "notconnect", "disabled", "administratively down", "admin-down",
                     "admin down", "errdisabled", "err-disabled"}:
            return "down"
        return None

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
            unused = (None, None)
            if clock:
                # Allow bounded command/session latency when reconciling an approximate sample.
                samples = self.db.execute("""SELECT unused_since,unused_confirmed_at FROM port_connections
                    WHERE device=? AND interface=? AND state=? AND source='observation'
                    AND interval_start<=? AND at>=?""",
                    (device, name, match["state"], stamp(effective + timedelta(seconds=30)),
                     stamp(effective - timedelta(seconds=30)))).fetchall()
                if len(samples) == 1 and samples[0][0] and effective >= instant(samples[0][1]) - timedelta(seconds=30):
                    unused = samples[0]
                self.db.execute("""DELETE FROM port_connections WHERE device=? AND interface=?
                    AND state=? AND source='observation' AND interval_start<=? AND at>=?""",
                    (device, name, match["state"], stamp(effective + timedelta(seconds=30)),
                     stamp(effective - timedelta(seconds=30))))
            self.db.execute("""INSERT INTO port_connections
                (device,interface,state,at,observed_at,source,device_at,clock_offset_seconds,event_key,unused_since,unused_confirmed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (device, name, match["state"], stamp(effective), at, source, stamp(raw_time), offset, event_key, *unused))
        self._validate_unused(device)

    def prune(self, now):
        self.db.execute("DELETE FROM port_connections WHERE at<?", (stamp(now - RETENTION),))

    def history(self, device, interface, limit=100):
        rows = self.db.execute("""SELECT interface,state,at,observed_at,source,device_at,
            clock_offset_seconds,interval_start,unused_since,unused_confirmed_at FROM port_connections
            WHERE device=? AND interface=? ORDER BY at DESC,id DESC LIMIT ?""", (device, interface, limit)).fetchall()
        return [dict(zip(("interface", "state", "at", "observed_at", "source", "device_at",
                         "clock_offset_seconds", "interval_start", "unused_since", "unused_confirmed_at"), row)) for row in rows]

    def snapshot(self, now):
        # Group on the backend: no dependence on the workstation's clock.
        rows = self.db.execute("""SELECT device,interface,MAX(at),COUNT(*) FROM port_connections
            WHERE state='up' AND unused_since IS NOT NULL AND source!='device_log_unverified' AND at>? AND at<=?
            GROUP BY device,interface ORDER BY MAX(at) DESC""", (stamp(now - WINDOW), stamp(now))).fetchall()
        result = {}
        for device, name, at, count in rows:
            latest = self.db.execute("""SELECT source,device_at,clock_offset_seconds,interval_start,unused_since,unused_confirmed_at
                FROM port_connections WHERE device=? AND interface=? AND state='up' AND at=?
                AND unused_since IS NOT NULL
                ORDER BY CASE source WHEN 'device_log' THEN 0 ELSE 1 END LIMIT 1""", (device, name, at)).fetchone()
            result.setdefault(device, {})[name] = {
                "interface": name, "connected_at": at, "expires_at": stamp(instant(at) + WINDOW),
                "connection_count": count, "repeated": count >= 3,
                "source": latest[0], "device_at": latest[1], "clock_offset_seconds": latest[2],
                "interval_start": latest[3], "age_seconds": int((now - instant(at)).total_seconds()),
                "unused_since": latest[4], "unused_confirmed_at": latest[5],
                "unused_minimum_seconds": int(UNUSED_MINIMUM.total_seconds()),
            }
        return result

    def log_status(self, device):
        row = self.db.execute("SELECT checked_at,success,clock_verified FROM connection_log_status WHERE device=?", (device,)).fetchone()
        return dict(zip(("checked_at", "success", "clock_verified"), row)) if row else None
