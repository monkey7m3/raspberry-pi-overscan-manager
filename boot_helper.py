"""Privileged boot editor: only edits the kernel's video argument."""
import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend import CONNECTOR, EDGES, replace_video_argument, validate_margins
from boot_rollback import arm, STATE


def apply(connector, margins, path=Path("/boot/firmware/cmdline.txt")):
    if not CONNECTOR.fullmatch(connector):
        raise ValueError("Invalid connector")
    validate_margins(margins)
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Expected regular file: {path}")
    old = path.read_text()
    new = replace_video_argument(old, connector, margins)
    if new == old:
        return "No changes required"
    if not Path('/etc/systemd/system/multi-user.target.wants/raspberry-pi-overscan-rollback.service').exists():
        raise RuntimeError('Rollback service is not enabled; refusing boot change')
    if not Path('/etc/systemd/system/timers.target.wants/raspberry-pi-overscan-timeout.timer').exists():
        raise RuntimeError('Rollback timeout timer is not enabled; refusing boot change')
    if STATE.exists():
        raise RuntimeError("A boot test is already pending; confirm or recover it first")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(
        path.name + f".overscan-manager.{timestamp}.{os.getpid()}.bak"
    )
    shutil.copy2(path, backup)
    temp = path.with_name(path.name + f".overscan-manager.{os.getpid()}.tmp")
    try:
        arm(old.encode(), new.encode())
        temp.write_text(new)
        shutil.copymode(path, temp)
        os.replace(temp, path)
    except Exception:
        # If the boot file has not changed, disarm the incomplete transaction.
        if path.read_text() == old:
            STATE.unlink(missing_ok=True)
        raise
    finally:
        temp.unlink(missing_ok=True)
    return f"Backup: {backup}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--connector", required=True)
    for edge in EDGES:
        parser.add_argument("--" + edge, type=int, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        print("Root permission required", file=sys.stderr)
        return 1
    try:
        message = apply(args.connector, {
            edge: getattr(args, edge) for edge in EDGES
        })
        print(message)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Unable to apply margins: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
