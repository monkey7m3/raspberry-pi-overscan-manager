#!/usr/bin/env bash
# Validate the two wlroots margin patches against the exact supplied source.
# This script never installs a library, starts a compositor, or writes DRM state.
set -euo pipefail
if (( $# != 3 )); then
  echo "Usage: $0 wlroots_0.20.2.orig.tar.bz2 wlroots_0.20.2-1+rpt4.debian.tar.xz patch-directory" >&2
  exit 2
fi
orig="$(realpath "$1")"
debian="$(realpath "$2")"
patches="$(realpath "$3")"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
tar -xf "$orig" -C "$work"
root="$work/wlroots-0.20.2"
test -d "$root"
tar -xf "$debian" -C "$root"
cd "$root"
for p in 0001-discover-connector-margins.patch 0002-stage-atomic-connector-margins.patch; do
  echo "Checking $p"
  patch --dry-run --fuzz=0 -p1 < "$patches/$p"
  patch --fuzz=0 -p1 < "$patches/$p"
done
echo 'Checking margin property discovery and optional atomic staging symbols'
grep -q '"left margin", INDEX(margin_left)' backend/drm/properties.c
grep -q '"right margin", INDEX(margin_right)' backend/drm/properties.c
grep -q '"top margin", INDEX(margin_top)' backend/drm/properties.c
grep -q '"bottom margin", INDEX(margin_bottom)' backend/drm/properties.c
grep -q 'if (state->set_margins)' backend/drm/atomic.c
echo 'PASS: both patches applied with zero fuzz and expected code present'
echo 'NOTE: no compile, labwc integration, DRM test, or restoration test was performed'
