# Raspberry Pi Overscan Manager

Early-development GTK3 interface for Raspberry Pi OS (initially tested against Pi 4 Trixie / labwc DRM data).

**Status: experimental, not a finished overscan solution.** The Pi 4 VC4 DRM driver exposes four KMS margin properties, but the compositor can override boot-time margins. Live changes under Wayland and persistence across desktop initialization have **not** been demonstrated.

## Features in this first development branch

- Detect connected DRM outputs using sysfs, and read VC4 KMS margin properties with `modetest`.
- Edit four independent edge margins (0–100, restricted to the driver's reported range).
- Save local drafts in `~/.config/raspberry-pi-overscan-manager/settings.json`.
- Optionally write a per-connector `video=...` kernel command-line option to `/boot/firmware/cmdline.txt` using interactive administrator authorization, preserving existing mode options and creating a timestamped backup.
- Build ARM64 and ARMHF `.deb` packages automatically through GitHub Actions.

## Install for experimental evaluation

Download a package from [Actions](../../actions) on the development branch. Unzip its uploaded artifact, then run:

```bash
sudo apt install ./raspberry-pi-overscan-manager_0.3.0_arm64.deb
```

Use the ARMHF package on 32-bit Raspberry Pi OS. Launch from Preferences or run `raspberry-pi-overscan-manager`.

**First tests:** use **Refresh** and inspect the detected margin values, then **Save draft**. Saving a draft does not alter the screen or boot configuration.

**Risk of boot changes:** `Apply at next reboot…` changes the kernel command line, not the current desktop, and requires reboot. **There is no automatic rollback**. In this preview the changes might have no effect under labwc. Do not use the boot-change operation unless you have an alternative way to recover the Pi (SSH or access to the boot card). To undo, restore a `cmdline.txt.overscan-manager.*.bak` backup or remove the added `video=` margin arguments.

## Read-only diagnostic test (v0.2.0)

Open the application and click **Export diagnostics…**. Save the JSON report and share it for analysis. This reads connector state, KMS margin metadata, labwc version, and `wlr-randr` output. It does **not** write display properties, alter boot settings, or request administrator access. The report deliberately excludes raw EDID, the kernel command line, and user settings.

The exported report helps identify the available compositor interfaces but cannot, by itself, prove that live margin writes are possible.

## Live access investigation (v0.3.0)

Click **Probe live access…** and save `overscan-live-probe.json`. This test opens DRM card devices as the current desktop user and makes only a read-only `DRM_IOCTL_GET_MAGIC` query. It does **not** acquire DRM master, change margins, restart labwc, or edit boot settings.

Please upload the report to the project discussion. A successful open does **not** mean a separate process can change margins while the compositor is running; this probe is an initial permissions check, not a proof of live adjustment.

**Do not run `modetest -w` or stop labwc as part of this test.** A truly safe live change-and-rollback experiment requires a compositor-coordinated mechanism or independently tested restoration.

See [Live adjustment architecture](docs/live-adjustment-architecture.md) for the compositor feasibility findings, proposed backend design, and safety requirements.

See also the [VC4 kernel and compositor source review](docs/vc4-source-review.md) for the evidence supporting atomic margin updates and the remaining integration risks.

## Not yet implemented

- Live adjustment, countdown rollback, and verified persistent compensation under labwc
- Alternative compositor-specific underscan mechanisms and Wayland output scaling controls
- Reliable cross-model and multi-card support beyond VC4
- Automated UI or hardware tests

Wayland output scaling is not equivalent to KMS overscan correction. The planned multi-backend design will keep those concepts separate.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q backend.py app.py boot_helper.py diagnostics.py live_probe.py
sh ./build-deb.sh arm64
```

The CI workflow produces two Debian packages. It does not publish GitHub Releases automatically.
