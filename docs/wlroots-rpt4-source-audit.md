# Exact Raspberry Pi wlroots 0.20.2-1+rpt4 source audit

The user supplied `wlroots_0.20.2.orig.tar.bz2` and `wlroots_0.20.2-1+rpt4.debian.tar.xz`. Both archives were extracted and inspected directly. This supersedes earlier findings based on upstream `master`.

## Verified code locations

- `include/backend/drm/properties.h`: `struct wlr_drm_connector_props` holds the connector property IDs, but has no margin fields.
- `backend/drm/properties.c`: `connector_info[]` is a sorted name-to-struct-offset table searched by `bsearch()`; no margin entries. `get_drm_connector_props()` calls `scan_properties()`.
- `backend/drm/drm.c:1565`: `get_drm_connector_props(drm->fd, wlr_conn->id, &wlr_conn->props)` populates connector IDs.
- `backend/drm/atomic.c`: `atomic_connector_add()` builds the connector/CRTC/plane entries for a normal atomic commit. `atomic_device_commit()` calls it for each connector, then `atomic_commit()`; modeset/nonblock flags are conditional.
- `debian/patches/series`: 27 patches listed (one named revert plus 0001–0026), including Raspberry Pi DRM, libliftoff, and color representation changes. Any runtime patch must be applied on top of the downstream patched tree, not vanilla upstream.

## Implementation plan and limits

First patch only the connector property discovery table and ID struct (no writes), to verify the names resolve on the installed hardware. This is deliberately non-invasive.

Next, add **opt-in** test margin state to the DRM connector, populate the four property values in `atomic_connector_add()`, and ensure a commit is triggered when values change. The property IDs from the earlier probe (37–40) are *not* to be hard-coded.

The current GUI and standalone probe cannot submit a privileged atomic commit while labwc owns DRM master. To trigger a change, a compositor-controlled interface or internal test hook is required. A library patch alone cannot cause a live update.

A robust test must retain original margins, schedule compositor-owned restoration after five seconds, handle failures/disconnect, and avoid overwriting boot configuration. Do not replace system libwlroots without a rollback plan. **No compositor-side live update has yet been implemented or hardware-tested.**
