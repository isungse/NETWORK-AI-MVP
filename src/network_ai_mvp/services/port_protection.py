"""Protection is enforced by the backend, independent of the UI and latest collection purpose."""
import json
from pathlib import Path

from ..parsers import short_interface_name
from ..inventory import InventoryError


class PortProtection:
    def __init__(self, inventory, monitor, neighbors_path):
        self.inventory = inventory
        self.monitor = monitor
        self.reference = {}
        self.history_cache = {}
        if Path(neighbors_path).exists():
            try:
                devices = {d.management_ip: d.device_id for d in inventory.list_devices()}
            except InventoryError:
                devices = {}
            for row in json.loads(Path(neighbors_path).read_text(encoding="utf-8-sig")):
                self.reference.setdefault(row["source_device_id"], set()).add(short_interface_name(row["local_interface"]))
                target = devices.get(row.get("management_ip"))
                if target and row.get("remote_interface"):
                    self.reference.setdefault(target, set()).add(short_interface_name(row["remote_interface"]))

    def reason(self, device_id, interface):
        device = self.inventory.get_device(device_id)
        cfg = self.monitor.config["devices"].get(device_id, {})
        interface = short_interface_name(interface)
        if "backbone" in device.role:
            return "백본 장비의 포트는 일반 액세스 포트 제어에서 보호됩니다."
        if cfg.get("uplinks") is None:
            return "업링크 목록이 확정되지 않아 포트 변경이 제한됩니다."
        protected = {short_interface_name(p["interface"]) for p in cfg.get("uplinks") or []}
        protected |= self.reference.get(device_id, set())
        if interface in protected:
            return "지정 업링크 또는 백본 연결 포트는 차단할 수 없습니다."
        # Interface-only observations omit neighbors: retain earlier observed uplink evidence.
        if interface in self._observed_protected(device_id):
            return "이웃 장비 또는 업링크 연결 이력이 있는 보호 포트입니다."
        return None

    def _observed_protected(self, device_id):
        history_dir = self.monitor.data_dir / "observations" / device_id
        revision = history_dir.stat().st_mtime_ns if history_dir.exists() else None
        cached = self.history_cache.get(device_id)
        if cached and cached[0] == revision:
            return cached[1]
        protected = set()
        for path in sorted(history_dir.glob("*.json"), reverse=True):
            if path.name == "index.json":
                continue
            try:
                observation = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for port in observation.get("ports", []):
                if (
                    port.get("neighbor_name") or port.get("neighbor_ip") or
                    "uplink" in str(port.get("description", "")).lower()
                ):
                    protected.add(short_interface_name(port.get("interface", "")))
        self.history_cache[device_id] = (revision, protected)
        return protected
