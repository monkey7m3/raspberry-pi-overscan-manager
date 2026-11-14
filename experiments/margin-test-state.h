/* Pure state machine for a compositor-owned temporary margin test.
 * No DRM access here: the compositor must call margin_test_start() only after
 * reading the current values, then submit the requested atomic commit.
 * Restoration is requested on monotonic deadline and must be retried on failure.
 * This is a reusable component, NOT wired into labwc/wlroots yet.
 */
#ifndef RPI_MARGIN_TEST_STATE_H
#define RPI_MARGIN_TEST_STATE_H
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

enum margin_test_phase {
 MARGIN_IDLE, MARGIN_APPLY_PENDING, MARGIN_ACTIVE, MARGIN_RESTORE_PENDING,
 MARGIN_RESTORE_FAILED
};
struct margin_test_state {
 enum margin_test_phase phase;
 uint64_t original[4], requested[4];
 uint64_t restore_at_ms;
};
static inline bool margin_test_start(struct margin_test_state *s,
 const uint64_t original[4], unsigned edge, uint64_t delta) {
 if (s->phase != MARGIN_IDLE || edge >= 4 || delta == 0 || delta > 25 ||
     original[edge] > UINT64_MAX - delta) return false;
 memcpy(s->original, original, sizeof(s->original));
 memcpy(s->requested, original, sizeof(s->requested));
 s->requested[edge] += delta;
 s->restore_at_ms = 0;
 s->phase = MARGIN_APPLY_PENDING;
 return true;
}
/* Called only after a successful *real* DRM commit, never a TEST_ONLY commit. */
static inline bool margin_test_applied(struct margin_test_state *s,
 uint64_t monotonic_ms, uint64_t hold_ms) {
 if (s->phase != MARGIN_APPLY_PENDING || hold_ms == 0 ||
     monotonic_ms > UINT64_MAX - hold_ms) return false;
 s->restore_at_ms = monotonic_ms + hold_ms;
 s->phase = MARGIN_ACTIVE;
 return true;
}
static inline bool margin_test_due(struct margin_test_state *s,
 uint64_t monotonic_ms) {
 if (s->phase != MARGIN_ACTIVE || monotonic_ms < s->restore_at_ms) return false;
 s->phase = MARGIN_RESTORE_PENDING;
 return true;
}
static inline void margin_test_apply_failed(struct margin_test_state *s) {
 if (s->phase == MARGIN_APPLY_PENDING) s->phase = MARGIN_IDLE;
}
static inline void margin_test_restore_result(struct margin_test_state *s,
 bool success) {
 if (s->phase != MARGIN_RESTORE_PENDING) return;
 s->phase = success ? MARGIN_IDLE : MARGIN_RESTORE_FAILED;
}
static inline bool margin_test_retry_restore(struct margin_test_state *s) {
 if (s->phase != MARGIN_RESTORE_FAILED) return false;
 s->phase = MARGIN_RESTORE_PENDING;
 return true;
}
#endif
