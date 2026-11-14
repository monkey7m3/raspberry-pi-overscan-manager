# Compositor-owned live-margin request: implementation contract

Target: labwc 0.20.2, Raspberry Pi wlroots 0.20.2-1+rpt4, VC4 DRM.

## Why the two current wlroots patches are not a working feature

The patches add property discovery and an optional `set_margins` branch to the atomic request builder. No caller sets this flag. The `wlr_drm_connector_state` is a **temporary transaction state**, not persistent connector state, and it is assembled by the DRM backend. A labwc client cannot simply set these fields; they are private wlroots internals.

Furthermore, a compositor-triggered output commit must be created through the existing wlroots output transaction path. A separate root process cannot commit on the DRM device while labwc holds DRM master. Merely calling `wlr_output_commit_state()` without extending the backend's state preparation will not populate `set_margins`.

## Required integration work

1. Add a dedicated **backend-internal** pending-margin request per connector, including original values, target values, and a generation ID. Query the originals using the compositor's existing DRM fd (not the external probe's fd).
2. During construction of `wlr_drm_connector_state`, copy pending margin values into that transaction. Use the normal output-commit path and atomic commit handling. Distinguish TEST_ONLY from real commits.
3. On a successful real commit, record the applied generation. On failure, retain the original state and report failure. Avoid accidentally resending the test values on unrelated output commits.
4. Expose a narrow, explicitly enabled local test command to labwc; validate the output name and bounds. Do not expose raw DRM property IDs.
5. Schedule the restore **inside the compositor** with a monotonic timer after five seconds, not in the GUI or a helper that might die. On compositor exit or loss of DRM master, the guarantee is only best effort: document and test a recovery path.
6. Do not start testing until the original values can be restored and a session recovery method has been documented.

## Critical safety and correctness notes

- The initial probe saw nonzero margins. Never assume the original values are zero.
- The four properties may be missing on another connector. All must be present before enabling a test.
- An atomic commit can require a modeset; a margin-only request must be validated with the compositor's real active CRTC/plane state. Do not claim the kernel will accept it until hardware testing.
- The previous patches have only been checked for application; a compile and functional test are still required.
- Never replace `/lib/aarch64-linux-gnu/libwlroots-0.20.so` in place for an exploratory test.
