"""Boot transaction state machine. No display access.

A pending transaction is armed before reboot. The first distinct boot records
its boot ID; a second distinct boot restores the exact original cmdline bytes.
Confirmation removes pending state and leaves the new configuration in place.
"""
import json
import fcntl
import errno
import os
import stat
from pathlib import Path

STATE = Path("/var/lib/raspberry-pi-overscan-manager/pending.json")
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
CMDLINE = Path("/boot/firmware/cmdline.txt")


def atomic_write(path, data, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(path.name + ".tmp." + str(os.getpid()))
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        dirfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            try:
                os.fsync(dirfd)
            except OSError as exc:
                # FAT boot partitions may not support syncing a directory.
                # The replacement file itself has already been fsynced.
                if exc.errno not in (errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP):
                    raise
        finally:
            os.close(dirfd)
    finally:
        tmp.unlink(missing_ok=True)


def current_boot_id():
    return BOOT_ID.read_text().strip()


def arm(original_bytes, new_bytes, state=STATE):
    if state.exists():
        raise RuntimeError("A boot test is already pending")
    record = {
        "version": 1,
        "created_boot_id": current_boot_id(),
        "first_test_boot_id": None,
        "original_hex": original_bytes.hex(),
        "expected_hex": new_bytes.hex(),
    }
    atomic_write(state, (json.dumps(record) + "\n").encode())


def load(state=STATE):
    if not state.exists():
        return None
    data = json.loads(state.read_text())
    if data.get("version") != 1:
        raise RuntimeError("Unsupported rollback state version")
    return data


def recover(state=STATE, cmdline=CMDLINE):
    data = load(state)
    if data is None:
        return "No pending boot test"
    boot = current_boot_id()
    if boot == data["created_boot_id"]:
        return "Waiting for first reboot"
    # If power failed after arming but before updating cmdline, do not
    # treat this as a display test. Remove the stale transaction safely.
    original = bytes.fromhex(data["original_hex"])
    expected = bytes.fromhex(data["expected_hex"])
    actual = cmdline.read_bytes()
    if actual == original:
        # The original may already have been restored after a failed reboot
        # request. If this boot is the first test boot, request a reboot to
        # activate the original cmdline rather than leaving the bad display.
        if data["first_test_boot_id"] == boot:
            import subprocess
            subprocess.run(["/usr/bin/systemctl", "--no-block", "reboot"], check=True)
            state.unlink()
            return "Original configuration present; reboot requested"
        state.unlink()
        return "Original configuration present; pending transaction cleared"
    if actual != expected:
        raise RuntimeError("Boot configuration changed externally; refusing to overwrite")
    if data["first_test_boot_id"] is None:
        data["first_test_boot_id"] = boot
        atomic_write(state, (json.dumps(data) + "\n").encode())
        return "First test boot; awaiting confirmation"
    if boot == data["first_test_boot_id"]:
        return "Awaiting confirmation"
    return restore_and_reboot(state, cmdline, original)


def restore_and_reboot(state, cmdline, original):
    """Restore exact boot bytes and request a reboot to activate them."""
    import subprocess
    original_mode = stat.S_IMODE(cmdline.stat().st_mode)
    atomic_write(cmdline, original, mode=original_mode)
    # Leave pending state intact if systemctl fails.
    subprocess.run(["/usr/bin/systemctl", "--no-block", "reboot"], check=True)
    state.unlink()
    return "Original boot configuration restored; reboot requested"


def expire(state=STATE, cmdline=CMDLINE):
    """Restore unconfirmed test settings, then request a reboot.

    This runs from an independent systemd timer. It must never reboot during
    the staging boot or when no test transaction is pending.
    """
    data = load(state)
    if data is None or current_boot_id() == data["created_boot_id"]:
        return "No active test boot"
    if cmdline.read_bytes() != bytes.fromhex(data["expected_hex"]):
        raise RuntimeError("Boot configuration changed externally; refusing timed rollback")
    if data["first_test_boot_id"] is None:
        raise RuntimeError("Boot recovery service has not marked the test boot")
    if current_boot_id() != data["first_test_boot_id"]:
        return recover(state, cmdline)
    return restore_and_reboot(state, cmdline, bytes.fromhex(data["original_hex"]))


def confirm(state=STATE, cmdline=CMDLINE):
    data = load(state)
    if data is None:
        raise RuntimeError("No pending boot test")
    if current_boot_id() == data["created_boot_id"]:
        raise RuntimeError("Reboot and verify the display before confirming")
    if data["first_test_boot_id"] != current_boot_id():
        raise RuntimeError("Recovery service has not registered this test boot; cannot confirm")
    if cmdline.read_bytes() != bytes.fromhex(data["expected_hex"]):
        raise RuntimeError("Boot configuration changed; cannot confirm")
    state.unlink()
    return "Display settings confirmed"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("recover", "confirm", "expire", "status"))
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("root permission required")
    # Serialize recovery, expiry and confirmation. Otherwise the timeout can
    # read pending state while confirmation is removing it and reboot anyway.
    STATE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = STATE.parent / "recovery.lock"
    with open(lock_path, "a+b") as lock:
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if args.action == "recover":
            print(recover())
        elif args.action == "confirm":
            print(confirm())
        elif args.action == "expire":
            print(expire())
        else:
            data = load()
            print(json.dumps({
                "pending": data is not None,
                "first_test_boot_seen": bool(data and data["first_test_boot_id"]),
            }))


if __name__ == "__main__":
    main()
