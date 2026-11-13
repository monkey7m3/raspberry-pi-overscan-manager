"""DRM/KMS property discovery and boot command-line helpers."""
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

EDGES = ("left", "right", "top", "bottom")
CONNECTOR = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
PROPERTY = re.compile(r"^\s*\d+\s+(left|right|top|bottom) margin:\s*$")
VALUES = re.compile(r"^\s*values:\s*(\d+)\s+(\d+)\s*$")
VALUE = re.compile(r"^\s*value:\s*(\d+)\s*$")


@dataclass
class Margin:
    value: int
    low: int
    high: int


def extract_margins(text: str, connector: str) -> dict[str, Margin]:
    match = re.search(
        r"(?m)^\s*\d+\s+\d+\s+(?:connected|disconnected|unknown)\s+"
        + re.escape(connector) + r"\s+", text
    )
    if not match:
        return {}
    rest = text[match.end():]
    end = re.search(
        r"(?m)^(?:\s*\d+\s+\d+\s+(?:connected|disconnected|unknown)\s+\S+|CRTCs:)",
        rest,
    )
    block = rest[:end.start()] if end else rest
    lines = block.splitlines()
    found = {}
    for i, line in enumerate(lines):
        prop = PROPERTY.match(line)
        if not prop:
            continue
        limits, current = None, None
        for sub in lines[i + 1:i + 6]:
            if PROPERTY.match(sub) or re.match(r"^\s*\d+\s+\S[^:]*:", sub):
                break
            if m := VALUES.match(sub):
                limits = (int(m[1]), int(m[2]))
            if m := VALUE.match(sub):
                current = int(m[1])
        if limits and current is not None:
            found[prop[1]] = Margin(current, *limits)
    return found


def discover() -> list[dict]:
    outputs = []
    root = Path("/sys/class/drm")
    if not root.exists():
        return outputs
    try:
        result = subprocess.run(
            ["modetest", "-M", "vc4", "-c"],
            capture_output=True, text=True, timeout=8, check=False
        )
        report = result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        report = ""
    for path in sorted(root.glob("card*-*")):
        status = path / "status"
        if not status.is_file():
            continue
        try:
            state = status.read_text().strip()
        except OSError:
            continue
        if state != "connected":
            continue
        card, _, name = path.name.partition("-")
        if not CONNECTOR.fullmatch(name):
            continue
        outputs.append({
            "name": name, "card": card, "status": state,
            "margins": extract_margins(report, name),
        })
    return outputs


def validate_margins(values: dict, limits=None) -> dict[str, int]:
    out = {}
    for edge in EDGES:
        value = values.get(edge)
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError(f"Invalid {edge} margin (integer 0..100 required)")
        if limits and edge in limits:
            if not limits[edge].low <= value <= limits[edge].high:
                raise ValueError(f"{edge} margin is outside supported range")
        out[edge] = value
    return out


def replace_video_argument(line: str, connector: str, margins: dict) -> str:
    if not CONNECTOR.fullmatch(connector):
        raise ValueError("Invalid DRM connector")
    margins = validate_margins(margins)
    if "\n" in line.strip("\n") or "\r" in line:
        raise ValueError("Kernel command line must have one line")
    tokens = line.strip().split()
    prefix = f"video={connector}:"
    matches = [i for i, token in enumerate(tokens) if token.startswith(prefix)]
    if len(matches) > 1:
        raise ValueError("Multiple video settings for connector")
    settings = [f"margin_{edge}={margins[edge]}" for edge in EDGES]
    if matches:
        index = matches[0]
        old = tokens[index][len(prefix):].split(",")
        old = [part for part in old if part and not any(
            part.startswith(f"margin_{edge}=") for edge in EDGES
        )]
        tokens[index] = prefix + ",".join(old + settings)
    else:
        tokens.append(prefix + ",".join(settings))
    return " ".join(tokens) + "\n"


def settings_path() -> Path:
    return Path.home() / ".config" / "raspberry-pi-overscan-manager" / "settings.json"


def load_settings() -> dict:
    try:
        value = json.loads(settings_path().read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n")
    temp.replace(path)
