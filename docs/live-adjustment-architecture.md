# Live margin adjustment: architecture decision

Status: research/design, **not implemented**.

## Verified environment

Pi 4, Raspberry Pi OS Trixie, labwc 0.20.2 / wlroots 0.20.2, vc4 DRM on /dev/dri/card1, HDMI-A-1 connected. Four connector properties (`left margin`, `right margin`, `top margin`, `bottom margin`) are readable with ranges 0–100 and initial values 76, 76, 44, 30. The normal user can open the DRM card and perform a read-only DRM ioctl. A root-run standalone `drmModeObjectSetProperty` write returned **EACCES (errno 13)** while labwc was running; no visible live change has been demonstrated. Boot-time changes and unattended rollback were subsequently hardware-tested successfully.

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


## 2026-11-13: post-EACCES source findings

The standalone live-write probe read connector HDMI-A-1 (object ID 35) and four margin properties (IDs 37–40; values 77, 76, 44, 30). Its root-run attempt to set the left margin returned EACCES before any hold/restore interval. This strongly suggests DRM-master authorization, although errno alone does not prove which DRM permission check rejected the operation.

In current upstream Linux VC4, `vc4_crtc_atomic_check()` compares the CRTC margins with `conn_state->tv.margins`, copies changed margins, and sets `crtc_state->zpos_changed = true` to force plane display-list updates. Thus VC4 has an atomic pathway to recalculate the visible image on margin changes: https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/vc4/vc4_crtc.c . This is *source-level evidence*, not a hardware-verified live update on the Pi's installed kernel.

wlroots' DRM backend uses its own connector state and `drm_crtc_commit` / atomic request construction for active outputs: https://github.com/swaywm/wlroots/blob/master/backend/drm/drm.c . The existing generic Wayland output-management interface does not express four-edge VC4 margin properties.

**Likely implementation boundary:** add connector margin property discovery and atomic-request population to the version-matched wlroots DRM backend; expose a compositor-owned test/restore command through a narrowly scoped labwc integration. Merely adding a client-side ioctl, a GUI slider, or a Wayland protocol message will not bypass DRM-master requirements.

**Before implementing a compositor fork:** inspect the *exact* wlroots 0.20.2 tag (not current main) for `backend/drm/atomic.c`, `backend/drm/properties.c`, `backend/drm/drm.c`, and connector state structs. Confirm whether margin property IDs are already enumerated, whether `DRM_MODE_ATOMIC_ALLOW_MODESET` or other CRTC/plane state is necessary, and whether commits can be triggered with no new framebuffer. The observed EACCES rules out the standalone approach in the current session but does not prove that a compositor-side atomic commit will visibly update margins.

**Next deliverable:** version-matched source patch plus isolated test interface with compositor-owned 5-second rollback; retain the working boot-based implementation as a fallback. Do not install replacement wlroots/labwc binaries on the Pi before validating the build and rollback.

## Source audit checkpoint: wlroots upstream DRM implementation

Inspected actual upstream files at `swaywm/wlroots` `master` (not yet verified to match the Pi's installed binary):

- `backend/drm/properties.c`: `connector_info[]` is a sorted lookup table of known connector properties; it does **not** contain any of the four `* margin` names. Thus simply using an existing wlroots output-setting interface cannot reach these properties.
- `backend/drm/atomic.c`: `atomic_add(&atom, conn->id, conn->props.crtc_id, ...)` shows the connector-property insertion point. The same request includes CRTC mode/active and plane properties; `DRM_MODE_ATOMIC_ALLOW_MODESET` is set only for a modeset. A patch would need to discover the margin property IDs, include margin values in the connector atomic request, and ensure a suitable commit is actually scheduled.
- **Version mismatch discovered:** GitHub does not have a `swaywm/wlroots` tag named `0.20.2` (404). The observed `0.20.2` may be the labwc version, a downstream package version, or a different library version. Do not base a binary patch on the upstream `master` files.

Sources:
- https://github.com/swaywm/wlroots/blob/master/backend/drm/properties.c
- https://github.com/swaywm/wlroots/blob/master/backend/drm/atomic.c

Before producing a version-specific patch, collect these non-mutating package/source identifiers on the Pi:

```sh
dpkg-query -W 'labwc' 'libwlroots*' 2>/dev/null
apt-cache policy labwc
ldd "$(command -v labwc)" | grep -Ei 'wlroots|libdrm'
```

This is a **read-only environment identification step**, not an instruction to install or replace desktop components. Next: audit the matching source tree and prototype margin-property atomic commit wiring with an opt-in compositor-owned rollback.
