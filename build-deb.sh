#!/bin/sh
set -eu
ARCH="${1:-arm64}"
case "$ARCH" in arm64|armhf) ;; *) echo "Use arm64 or armhf" >&2; exit 2;; esac
PKG="raspberry-pi-overscan-manager"
VERSION="0.5.0"
ROOT="dist/${PKG}_${VERSION}_${ARCH}"
rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/lib/$PKG" "$ROOT/usr/bin" "$ROOT/usr/share/applications" "$ROOT/lib/systemd/system"
cp backend.py app.py boot_helper.py diagnostics.py live_probe.py boot_audit.py boot_rollback.py "$ROOT/usr/lib/$PKG/"
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: $PKG
Version: $VERSION
Section: x11
Priority: optional
Architecture: $ARCH
Maintainer: Raspberry Pi Overscan Manager contributors
Depends: python3 (>= 3.11), python3-gi, gir1.2-gtk-3.0, libdrm-tests, pkexec, systemd
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

cat > "$ROOT/lib/systemd/system/raspberry-pi-overscan-rollback.service" <<'UNIT'
[Unit]
Description=Raspberry Pi Overscan Manager boot recovery
DefaultDependencies=no
After=local-fs.target
Before=display-manager.service multi-user.target
ConditionPathExists=/var/lib/raspberry-pi-overscan-manager/pending.json

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/lib/raspberry-pi-overscan-manager/boot_rollback.py recover

[Install]
WantedBy=multi-user.target
UNIT
cat > "$ROOT/lib/systemd/system/raspberry-pi-overscan-timeout.service" <<'UNIT'
[Unit]
Description=Restore unconfirmed Raspberry Pi overscan settings
After=raspberry-pi-overscan-rollback.service
ConditionPathExists=/var/lib/raspberry-pi-overscan-manager/pending.json

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/lib/raspberry-pi-overscan-manager/boot_rollback.py expire
UNIT
cat > "$ROOT/lib/systemd/system/raspberry-pi-overscan-timeout.timer" <<'UNIT'
[Unit]
Description=Overscan display confirmation timeout

[Timer]
OnBootSec=3min
AccuracySec=1s
Unit=raspberry-pi-overscan-timeout.service

[Install]
WantedBy=timers.target
UNIT
cat > "$ROOT/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
if [ "$1" = configure ] && command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
    systemctl enable raspberry-pi-overscan-rollback.service
    systemctl enable raspberry-pi-overscan-timeout.timer
    systemctl start raspberry-pi-overscan-timeout.timer
fi
POST
chmod 755 "$ROOT/DEBIAN/postinst"

dpkg-deb --build --root-owner-group "$ROOT" "dist/${PKG}_${VERSION}_${ARCH}.deb"
