"""Boot transaction state machine. No display access.

A pending transaction is armed before reboot. The first distinct boot records
its boot ID; a second distinct boot restores the exact original cmdline bytes.
Confirmation removes pending state and leaves the new configuration in place.
"""
import json
import os
from pathlib import Path

STATE = Path("/var/lib/raspberry-pi-overscan-manager/pending.json")
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
CMDLINE = Path("/boot/firmware/cmdline.txt")


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp." + str(os.getpid()))
    try:
        with open(tmp, "xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
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
    if data["first_test_boot_id"] is None:
        data["first_test_boot_id"] = boot
        atomic_write(state, (json.dumps(data) + "\n").encode())
        return "First test boot; awaiting confirmation"
    if boot == data["first_test_boot_id"]:
        return "Awaiting confirmation"
    original = bytes.fromhex(data["original_hex"])
    expected = bytes.fromhex(data["expected_hex"])
    if cmdline.read_bytes() != expected:
        raise RuntimeError("Boot configuration changed externally; refusing to overwrite")
    atomic_write(cmdline, original)
    state.unlink()
    return "Original boot configuration restored; reboot again to activate"


def confirm(state=STATE, cmdline=CMDLINE):
    data = load(state)
    if data is None:
        raise RuntimeError("No pending boot test")
    if current_boot_id() == data["created_boot_id"]:
        raise RuntimeError("Reboot and verify the display before confirming")
    if cmdline.read_bytes() != bytes.fromhex(data["expected_hex"]):
        raise RuntimeError("Boot configuration changed; cannot confirm")
    state.unlink()
    return "Display settings confirmed"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("recover", "confirm", "status"))
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error("root permission required")
    if args.action == "recover":
        print(recover())
    elif args.action == "confirm":
        print(confirm())
    else:
        data = load()
        print(json.dumps({
            "pending": data is not None,
            "first_test_boot_seen": bool(data and data["first_test_boot_id"]),
        }))


if __name__ == "__main__":
    main()
