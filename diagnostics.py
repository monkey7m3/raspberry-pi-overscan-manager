"""Read-only diagnostic for Wayland/labwc and DRM/KMS margin support.

No display property writes, no elevated privileges, and no boot edits.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

from backend import EDGES, discover


def command(argv, timeout=8):
    if not shutil.which(argv[0]):
        return {"available": False, "error": "command not installed"}
    try:
        run = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {
            "available": True,
            "exit_code": run.returncode,
            "stdout": run.stdout[:30000],
            "stderr": run.stderr[:3000],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": True, "error": type(exc).__name__}


def sysfs_properties():
    root = Path("/sys/class/drm")
    outputs = []
    for entry in sorted(root.glob("card*-*")):
        status = entry / "status"
        if not status.is_file():
            continue
        try:
            state = status.read_text().strip()
            modes_file = entry / "modes"
            modes = modes_file.read_text().splitlines()[:12] if modes_file.exists() else []
            edid = entry / "edid"
            # EDID bytes are deliberately not exported; only presence is reported.
            outputs.append({
                "connector": entry.name,
                "status": state,
                "modes": modes,
                "edid_available": edid.exists(),
            })
        except OSError:
            continue
    return outputs


def gather():
    discovered = []
    for output in discover():
        discovered.append({
            "connector": output["name"],
            "card": output["card"],
            "margins": {
                edge: {
                    "current": output["margins"][edge].value,
                    "min": output["margins"][edge].low,
                    "max": output["margins"][edge].high,
                }
                for edge in EDGES if edge in output["margins"]
            },
        })
    return {
        "format_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "session": {
            "XDG_SESSION_TYPE": os.getenv("XDG_SESSION_TYPE", ""),
            "XDG_CURRENT_DESKTOP": os.getenv("XDG_CURRENT_DESKTOP", ""),
            "WAYLAND_DISPLAY_present": bool(os.getenv("WAYLAND_DISPLAY")),
        },
        "drm": {
            "connectors": sysfs_properties(),
            "discovered": discovered,
            "modetest_available": bool(shutil.which("modetest")),
        },
        "compositor": {
            "wlr_randr": command(["wlr-randr"]),
            "labwc_version": command(["labwc", "--version"]),
        },
        "notes": [
            "Read-only diagnostics. No DRM property or boot configuration writes.",
            "The presence of KMS margin properties does not prove live write access.",
            "The wlr-randr output-scale control is not equivalent to four-edge underscan.",
            "No raw EDID, kernel command line, IP addresses, or user settings exported.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Save JSON report to this file")
    args = parser.parse_args()
    data = json.dumps(gather(), indent=2) + "\n"
    if args.output:
        args.output.write_text(data)
        print(f"Saved read-only report to {args.output}")
    else:
        print(data)


if __name__ == "__main__":
    main()
