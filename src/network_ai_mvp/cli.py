from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .inventory import get_device, load_devices
from .policy import allowed_purposes, build_command_plan, validate_commands

DEFAULT_INVENTORY = Path(__file__).resolve().parents[2] / "inventory" / "devices.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Network AI MVP read-only helper")
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-devices", help="List inventory devices")

    purposes_parser = subparsers.add_parser("list-purposes", help="List allowlisted purposes by vendor")
    purposes_parser.add_argument("--vendor", required=True, choices=["arista", "cisco"])

    plan_parser = subparsers.add_parser("plan-commands", help="Build a read-only command plan")
    plan_parser.add_argument("--device-id", required=True)
    plan_parser.add_argument("--purpose", required=True)

    check_parser = subparsers.add_parser("check-command", help="Validate one command against policy")
    check_parser.add_argument("--vendor", required=True, choices=["arista", "cisco"])
    check_parser.add_argument("--command", required=True)

    args = parser.parse_args()

    if args.command == "list-devices":
        devices = load_devices(args.inventory)
        _print_json([asdict(device) for device in devices])
    elif args.command == "list-purposes":
        _print_json({"vendor": args.vendor, "purposes": allowed_purposes(args.vendor)})
    elif args.command == "plan-commands":
        devices = load_devices(args.inventory)
        device = get_device(devices, args.device_id)
        plan = build_command_plan(device, args.purpose)
        _print_json(asdict(plan))
    elif args.command == "check-command":
        validate_commands(args.vendor, [args.command])
        _print_json({"allowed": True, "vendor": args.vendor, "command": args.command})


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
