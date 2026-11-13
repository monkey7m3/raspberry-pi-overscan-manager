#!/bin/sh
set -eu
ARCH="${1:-arm64}"
case "$ARCH" in arm64|armhf) ;; *) echo "Use arm64 or armhf" >&2; exit 2;; esac
PKG="raspberry-pi-overscan-manager"
VERSION="0.4.0"
ROOT="dist/${PKG}_${VERSION}_${ARCH}"
rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/lib/$PKG" "$ROOT/usr/bin" "$ROOT/usr/share/applications"
cp backend.py app.py boot_helper.py diagnostics.py live_probe.py boot_audit.py "$ROOT/usr/lib/$PKG/"
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VERSION
Section: x11
Priority: optional
Architecture: $ARCH
Maintainer: Raspberry Pi Overscan Manager contributors
Depends: python3 (>= 3.11), python3-gi, gir1.2-gtk-3.0, libdrm-tests, pkexec
Description: GTK app for Raspberry Pi DRM/KMS overscan margins
 Find connected outputs and four independent margin properties.
 Boot-time adjustment needs authorization and a reboot.
CONTROL
cat > "$ROOT/usr/bin/$PKG" <<'SCRIPT'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/raspberry-pi-overscan-manager/app.py "$@"
SCRIPT
chmod 755 "$ROOT/usr/bin/$PKG"
cat > "$ROOT/usr/share/applications/$PKG.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Raspberry Pi Overscan Manager
Comment=Configure DRM/KMS display margins
Exec=raspberry-pi-overscan-manager
Icon=video-display
Terminal=false
Categories=Settings;HardwareSettings;
DESKTOP
chmod -R a+rX "$ROOT"
chmod g-s "$ROOT/DEBIAN"
chmod 755 "$ROOT/DEBIAN"
dpkg-deb --build --root-owner-group "$ROOT" "dist/${PKG}_${VERSION}_${ARCH}.deb"
