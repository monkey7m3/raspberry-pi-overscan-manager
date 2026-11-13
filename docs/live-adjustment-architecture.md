# Live margin adjustment: architecture decision

Status: research/design, **not implemented**.

## Verified environment

Pi 4, Raspberry Pi OS Trixie, labwc 0.20.2 / wlroots 0.20.2, vc4 DRM on /dev/dri/card1, HDMI-A-1 connected. Four connector properties (`left margin`, `right margin`, `top margin`, `bottom margin`) are readable with ranges 0–100 and initial values 76, 76, 44, 30. The normal user can open the DRM card and perform a read-only DRM ioctl. **No write or live change has been demonstrated.**

## Findings from upstream interfaces

1. `zwlr_output_management_v1` supports modes, position, transform, scale, and adaptive sync, **not** arbitrary connector properties or underscan margins. See https://wayland.app/protocols/wlr-output-management-unstable-v1
2. labwc's `<margin>` setting reserves desktop work-area space for windows; it is not hardware underscan and does not shrink the entire rendered desktop. See https://github.com/labwc/labwc/blob/master/docs/labwc-config.5.scd
3. wlroots exposes an output state/commit API, but no documented general-purpose margin setter in that public output-state interface. See https://wlroots.pages.freedesktop.org/wlroots/wlr/types/wlr_output.h.html
4. Direct KMS connector-property changes from a second client are not assumed safe or authorized while labwc controls DRM master. An openable `/dev/dri/card1` does not establish modeset permission.

## Decision

Maintain separate backend capabilities:

- `drm_readonly`: enumerate connectors and properties (implemented).
- `boot_kms_experimental`: existing boot-command-line helper; disabled from recommended test path pending persistence validation.
- `compositor_underscan`: future optional backend, only if a compositor-coordinated implementation can be developed and validated.
- `wayland_scale`: distinct display-density feature, **not** a substitute for overscan compensation.

### Proposed compositor-coordinated prototype

Investigate whether a narrowly scoped labwc/wlroots change can commit the VC4 four margin properties along with the compositor's normal atomic KMS state. This requires source-level validation of the VC4 margin semantics, wlroots DRM property enumeration, and whether connector property changes can be included safely in its atomic commits. **Do not assume that adding a Wayland protocol request alone changes the KMS hardware.**

If feasible, define a small authenticated local IPC API in the compositor for `get_margins`, `test_margins`, `commit_margins`, and `restore_margins`. This is a design proposal, not a supported labwc API.

### Safety criteria before any on-device write

- Preserve original connector properties, display mode, and desktop session.
- Validate connector and property IDs from live enumeration, not fixed IDs.
- Explicit confirmation and automatic restore with a timeout.
- Restoration must survive GUI exit/crash; a separate watchdog or compositor-owned timer is required.
- Reject unsupported outputs and avoid taking DRM master away from labwc.
- Prove rollback in a test environment before enabling a physical-display experiment.
- Do not modify `/boot/firmware/cmdline.txt` during live tests.

## Next development task

Source-level feasibility review against **labwc 0.20.2 / wlroots 0.20.2** and the Raspberry Pi VC4 KMS driver. Identify the precise insertion point for a connector property update, confirm whether the driver permits it, and only then build an opt-in test harness. If this is not feasible without maintaining a compositor fork, investigate a persistent non-live alternative and clearly disclose its limitations.
