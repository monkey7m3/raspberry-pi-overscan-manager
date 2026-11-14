#!/usr/bin/env bash
# Download exact Raspberry Pi wlroots source package for offline analysis.
# Does NOT install packages, edit APT sources, or alter the running compositor.
set -euo pipefail
VERSION='0.20.2-1+rpt4'
BASE='https://archive.raspberrypi.com/debian/pool/main/w/wlroots'
DEST="${1:-$HOME/wlroots-source-review}"
mkdir -p "$DEST"
cd "$DEST"
for file in "wlroots_0.20.2.orig.tar.bz2" "wlroots_${VERSION}.debian.tar.xz" "wlroots_${VERSION}.dsc"; do
  curl --fail --location --show-error --silent --retry 3 --output "$file" "$BASE/$file"
done
echo 'Downloaded exact source archives:'
sha256sum wlroots_*
echo
echo 'Source package metadata and expected checksums:'
grep -A 12 '^Checksums-Sha256:' "wlroots_${VERSION}.dsc" || true
echo
echo 'Extracting into a separate review directory (no system files changed).'
mkdir -p extracted
tar -xf wlroots_0.20.2.orig.tar.bz2 -C extracted
root="$(find extracted -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [[ -z "$root" ]]; then
  echo 'Cannot locate extracted source root' >&2
  exit 1
fi
tar -xf "wlroots_${VERSION}.debian.tar.xz" -C "$root"
echo "Source root: $root"
echo 'Raspberry Pi Debian patch series:'
if [[ -f "$root/debian/patches/series" ]]; then
  cat "$root/debian/patches/series"
else
  echo '(no quilt patch series)'
fi
echo
echo 'DRM files of interest:'
find "$root/backend/drm" -maxdepth 1 -type f \( -name 'atomic.c' -o -name 'properties.c' -o -name 'drm.c' \) -print
echo
echo 'Read-only source retrieval completed. No patches applied or system components replaced.'
