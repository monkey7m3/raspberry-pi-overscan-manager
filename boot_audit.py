"""Read-only audit of KMS boot margins versus current DRM margins.

Only selected video= tokens are exported; unrelated kernel arguments are omitted.
No display writes, privilege escalation, or boot-file modifications.
"""
import json
from pathlib import Path
from backend import EDGES, discover

CMDLINE = Path("/boot/firmware/cmdline.txt")


def parse_margin_tokens(line):
    results = {}
    for token in line.split():
        if not token.startswith("video="):
            continue
        value = token[6:]
        connector, sep, settings = value.partition(":")
        if not sep:
            continue
        margins = {}
        for part in settings.split(","):
            key, equal, raw = part.partition("=")
            if not equal or key not in {f"margin_{e}" for e in EDGES}:
                continue
            try:
                number = int(raw)
            except ValueError:
                continue
            if 0 <= number <= 100:
                margins[key[7:]] = number
        if margins:
            results.setdefault(connector, []).append(margins)
    return results


def gather(cmdline_path=CMDLINE):
    try:
        boot = parse_margin_tokens(cmdline_path.read_text())
        boot_status = "readable"
    except OSError:
        boot, boot_status = {}, "unavailable"
    outputs = []
    for output in discover():
        actual = {edge: output["margins"][edge].value
                  for edge in EDGES if edge in output["margins"]}
        configured = boot.get(output["name"], [])
        match = (len(configured) == 1 and len(configured[0]) == 4
                 and actual == configured[0])
        outputs.append({
            "connector": output["name"], "card": output["card"],
            "current_drm_margins": actual,
            "boot_margin_entries": configured,
            "boot_matches_current": match if configured else None,
        })
    return {
        "audit_version": 1,
        "boot_cmdline_status": boot_status,
        "outputs": outputs,
        "interpretation": (
            "A match does not prove that the boot option persists after a "
            "reboot or that labwc will preserve it. A mismatch does not "
            "identify which component changed the margins. No settings "
            "were changed."
        ),
        "safety": "Read-only; unrelated kernel arguments are not exported.",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(gather(), indent=2) + "\n"
    if args.output:
        args.output.write_text(report)
        print("Saved " + str(args.output))
    else:
        print(report)


if __name__ == "__main__":
    main()
