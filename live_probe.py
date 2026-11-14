"""Read-only probe for live DRM/KMS margin write feasibility.

No ioctl writes, no privilege escalation, and no changes to the display.
"""
import argparse
import errno
import fcntl
import json
import os
from pathlib import Path

# DRM_IOCTL_GET_MAGIC: _IOWR('d', 0x02, struct drm_auth), 4-byte unsigned int.
# This is a read-only query and does not acquire DRM master.
DRM_IOCTL_GET_MAGIC = 0xC0046402


def inspect_card(path: Path) -> dict:
    item = {"device": str(path)}
    try:
        fd = os.open(path, os.O_RDWR | os.O_CLOEXEC | os.O_NONBLOCK)
    except OSError as exc:
        item["open"] = {"ok": False, "errno": exc.errno,
                        "error": errno.errorcode.get(exc.errno, "unknown")}
        return item
    try:
        item["open"] = {"ok": True}
        import array
        value = array.array("I", [0])
        try:
            fcntl.ioctl(fd, DRM_IOCTL_GET_MAGIC, value, True)
            item["drm_get_magic"] = "supported"
        except OSError as exc:
            item["drm_get_magic"] = errno.errorcode.get(exc.errno, "unknown")
    finally:
        os.close(fd)
    return item


def gather() -> dict:
    return {
        "probe_version": 1,
        "session_type": os.environ.get("XDG_SESSION_TYPE", ""),
        "wayland_present": bool(os.environ.get("WAYLAND_DISPLAY")),
        "drm_cards": [inspect_card(p) for p in sorted(Path("/dev/dri").glob("card[0-9]*"))],
        "interpretation": (
            "Opening a DRM device does NOT imply permission to modeset or "
            "modify connector properties. This probe does not request DRM "
            "master or perform a test commit. DRM master is normally held "
            "by the running Wayland compositor."
        ),
        "safety": "Read-only ioctl; no display or boot settings changed.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write report as JSON")
    args = parser.parse_args()
    report = json.dumps(gather(), indent=2) + "\n"
    if args.output:
        args.output.write_text(report)
        print("Saved " + str(args.output))
    else:
        print(report)


if __name__ == "__main__":
    main()
