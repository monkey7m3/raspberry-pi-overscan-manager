#!/usr/bin/env bash
# Safe host-only tests. Never accesses DRM, changes the desktop, or installs files.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cc -std=c11 -Wall -Wextra -Werror -pedantic -O2 \
  -I "$root/experiments" "$root/experiments/test-margin-state.c" \
  -o "$tmp/test-margin-state"
"$tmp/test-margin-state"
echo "PASS: margin state machine assertions"
echo "NOTE: no compositor integration or hardware atomic commit tested"
