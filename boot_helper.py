"""Privileged boot editor: only edits the kernel's video argument."""
import argparse
import fcntl
import stat
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend import CONNECTOR, EDGES, replace_video_argument, validate_margins
from boot_rollback import arm, STATE, atomic_write


def apply(connector, margins, path=Path("/boot/firmware/cmdline.txt")):
    """Serialize the entire edit with recovery and confirmation."""
    STATE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(STATE.parent / "recovery.lock", "a+b") as lock:
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        return _apply_locked(connector, margins, path)


def _apply_locked(connector, margins, path):
    if not CONNECTOR.fullmatch(connector):
        raise ValueError("Invalid connector")
    validate_margins(margins)
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"Expected regular file: {path}")
    old_bytes = path.read_bytes()
    old = old_bytes.decode("utf-8")
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
    try:
        arm(old_bytes, new.encode("utf-8"))
        atomic_write(path, new.encode("utf-8"), mode=stat.S_IMODE(path.stat().st_mode))
    except Exception:
        # If the boot file has not changed, disarm the incomplete transaction.
        if path.read_bytes() == old_bytes:
            STATE.unlink(missing_ok=True)
        raise
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
