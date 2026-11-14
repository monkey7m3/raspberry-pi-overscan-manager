"""Experimental live DRM margin feasibility probe. Does not touch boot configuration.

Default: read-only. --write-test explicitly attempts a 10-pixel change,
holds it for 5 seconds, then restores the previous value. Never acquires/drops DRM master.
Run from SSH so the terminal remains available if the screen changes.
"""
import argparse
import ctypes
import errno
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

DRM_MODE_OBJECT_CONNECTOR = 0xC0C0C0C0
EDGES = ("left", "right", "top", "bottom")


def parse_connector(report, name):
    lines = report.splitlines()
    header = re.compile(r"^\\s*(\\d+)\\s+\\d+\\s+connected\\s+" + re.escape(name) + r"\\s")
    start = next((i for i, line in enumerate(lines) if header.search(line)), None)
    if start is None:
        raise RuntimeError("Connected connector not found: " + name)
    connector_id = int(header.search(lines[start]).group(1))
    properties = {}
    prop = None
    for line in lines[start + 1:]:
        if re.match(r"^\\s*\\d+\\s+\\d+\\s+(?:connected|disconnected|unknown)\\s+\\S+", line) or re.match(r"^CRTCs:", line):
            break
        match = re.match(r"^\\s*(\\d+)\\s+(left|right|top|bottom) margin:\\s*$", line)
        if match:
            prop = (match.group(2), int(match.group(1)))
            continue
        if prop:
            value = re.match(r"^\\s*value:\\s*(\\d+)\\s*$", line)
            if value:
                properties[prop[0]] = {"id": prop[1], "value": int(value.group(1))}
                prop = None
    if len(properties) != 4:
        raise RuntimeError("All four DRM margin properties are required")
    return connector_id, properties


def run(connector, edge, write_test, device, delta=10, hold_seconds=5):
    result = subprocess.run(["modetest", "-M", "vc4", "-c"], capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError("modetest failed: " + result.stderr.strip())
    connector_id, props = parse_connector(result.stdout, connector)
    output = {"device": device, "connector": connector, "connector_id": connector_id,
              "properties": props, "write_test": write_test}
    if not write_test:
        output["result"] = "read-only; no DRM properties changed"
        return output
    old = props[edge]["value"]
    new = old + delta if old + delta <= 100 else old - delta
    if not 0 <= new <= 100:
        raise RuntimeError("Cannot apply requested change within margin range 0..100")
    lib = ctypes.CDLL("libdrm.so.2", use_errno=True)
    setter = lib.drmModeObjectSetProperty
    setter.argtypes = [ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32,
                       ctypes.c_uint32, ctypes.c_uint64]
    setter.restype = ctypes.c_int
    try:
        fd = os.open(device, os.O_RDWR | os.O_CLOEXEC)
    except OSError as exc:
        output["result"] = "DRM device open rejected"
        output["errno"] = exc.errno
        output["error"] = str(exc)
        return output
    try:
        def set_value(value):
            ctypes.set_errno(0)
            rc = setter(fd, connector_id, DRM_MODE_OBJECT_CONNECTOR, props[edge]["id"], value)
            if rc:
                error = -rc if rc < 0 else ctypes.get_errno()
                raise OSError(error, os.strerror(error))
        try:
            set_value(new)
        except OSError as exc:
            output["result"] = "write rejected"
            output["errno"] = exc.errno
            output["error"] = str(exc)
            return output
        # A successful write MUST be restored even if an unexpected error occurs.
        try:
            output["result"] = "write accepted; restoration attempted after hold"
            output["tested_edge"] = edge
            output["test_value"] = new
            output["hold_seconds"] = hold_seconds
            print(f"DRM write accepted: {edge} {old} -> {new}; holding {hold_seconds:g}s before restore", file=sys.stderr, flush=True)
            time.sleep(hold_seconds)
        finally:
            try:
                set_value(old)
                output["restored"] = True
            except OSError as exc:
                output["restored"] = False
                output["restore_error"] = str(exc)
                output["result"] = "WARNING: restoration failed"
        return output
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connector", default="HDMI-A-1")
    parser.add_argument("--device", default="/dev/dri/card1")
    parser.add_argument("--edge", choices=EDGES, default="left")
    parser.add_argument("--write-test", action="store_true",
                        help="explicitly attempt a 10-pixel change, hold for 5 seconds, then restore")
    parser.add_argument("--delta", type=int, default=10, help="margin change in pixels (1..25; default 10)")
    parser.add_argument("--hold-seconds", type=float, default=5, help="duration before restore (1..15; default 5)")
    args = parser.parse_args()
    if not 1 <= args.delta <= 25:
        parser.error("--delta must be between 1 and 25")
    if not 1 <= args.hold_seconds <= 15:
        parser.error("--hold-seconds must be between 1 and 15")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", args.connector):
        parser.error("Invalid connector name")
    if not re.fullmatch(r"/dev/dri/card[0-9]+", args.device):
        parser.error("Device must be a DRM card node")
    try:
        result = run(args.connector, args.edge, args.write_test, args.device, args.delta, args.hold_seconds)
        print(json.dumps(result, indent=2))
        return 2 if result.get("restored") is False else 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc), "errno": getattr(exc, "errno", None)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
