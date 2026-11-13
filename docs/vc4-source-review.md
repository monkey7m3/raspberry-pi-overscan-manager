# VC4 margin handling: source review

Status: feasibility research, not a functioning live adjustment implementation.

## Confirmed kernel mechanism

The DRM core documents `left margin`, `right margin`, `top margin`, and `bottom margin` as pixel-sized black borders, with the CRTC's content scaled into the remaining area. These are not Wayland logical scaling parameters.

- DRM connector documentation: https://code.googlesource.com/linux/torvalds/linux/+/4bf54e47525dcacd4c6cdd97fb5902592414dd7a/drivers/gpu/drm/drm_connector.c
- VC4 HDMI driver: https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/vc4/vc4_hdmi.c
- Historical VC4 implementation: https://gbmc.googlesource.com/linux/+/7e16ae558a87ac9099b6a93a43f19b42d809fd78/drivers/gpu/drm/vc4/vc4_hdmi.c
- VC4 CRTC state: https://git.zx2c4.com/linux-dev/tree/drivers/gpu/drm/vc4/vc4_crtc.c?id=411472ae5bb4ffe1404dc5f1505f07e0f04770a8

`vc4_hdmi_connector_atomic_check()` compares the old and new `connector_state->tv.margins` and requests the affected CRTC state if they differ. The VC4 CRTC atomic check propagates connector margins into VC4 CRTC state. This is evidence of real hardware support for atomic margin changes, not proof of a safe second-client update under Wayland.

## Userspace boundary

The wlroots DRM backend owns the normal display commit path and builds atomic KMS requests: https://github.com/swaywm/wlroots/blob/master/backend/drm/drm.c

The standard `zwlr_output_management_v1` protocol does not include four-edge margins. It cannot be used unchanged to express these properties. A separate client opening `/dev/dri/card1` successfully is not equivalent to having DRM master.

## Candidate implementation path

1. **Version-specific audit**: check the exact wlroots 0.20.2 source, including `backend/drm` connector property lookup, atomic request assembly, and state rollback. Do not assume current upstream main matches the installed version.
2. Add four optional margin property IDs to the wlroots DRM connector state, discovered by property name at runtime. Do not hard-code property IDs from the Pi.
3. Extend the compositor's output state/commit path to include margin values in an atomic commit while it owns DRM master. The kernel's VC4 connector atomic check may require CRTC revalidation or modeset-related handling.
4. Provide a narrow, locally authorized labwc control interface; expose only connector identity, supported range, current values, and apply/restore operations.
5. Implement **compositor-owned** rollback on timeout, disconnect, error, or client exit; a GTK-owned timer is not sufficient.
6. Only after independent testing of rollback, add opt-in GUI controls.

## Important compatibility tradeoff

A patched wlroots library or labwc executable can impose substantial maintenance cost and compatibility risk. This is a prototype research path, **not** yet the recommended distribution model for general Raspberry Pi OS users.

Alternative: determine whether a safe, compositor-respected startup configuration can produce equivalent underscan without replacing the compositor. The existing boot-time option remains unverified on labwc.

## Test gate

**No live property write should be offered in the GUI** until the exact wlroots/labwc versions, atomic commit path, and rollback are validated. Keep the existing v0.3.0 read-only tools usable.
