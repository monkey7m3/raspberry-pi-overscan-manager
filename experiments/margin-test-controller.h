/* Compositor event-loop adapter for temporary margins.
 * No libdrm or labwc dependencies: caller supplies DRM transaction and timer
 * callbacks. This does NOT itself integrate with labwc/wlroots.
 */
#ifndef RPI_MARGIN_TEST_CONTROLLER_H
#define RPI_MARGIN_TEST_CONTROLLER_H
#include "margin-test-state.h"

struct margin_test_controller {
 struct margin_test_state state;
 void *context;
 /* Synchronous submission: true only if a real atomic commit succeeded. */
 bool (*commit)(void *context, const uint64_t margins[4]);
 /* Schedule a one-shot callback after delay_ms; false means unavailable. */
 bool (*arm_restore)(void *context, uint64_t delay_ms);
};

/* A failed timer installation must immediately attempt restoration. */
static inline bool margin_controller_restore(struct margin_test_controller *c) {
 if (c->state.phase == MARGIN_ACTIVE) {
  c->state.phase = MARGIN_RESTORE_PENDING;
 } else if (!margin_test_retry_restore(&c->state)) {
  return false;
 }
 bool ok = c->commit(c->context, c->state.original);
 margin_test_restore_result(&c->state, ok);
 return ok;
}

static inline bool margin_controller_start(struct margin_test_controller *c,
 const uint64_t original[4], unsigned edge, uint64_t delta,
 uint64_t now_ms, uint64_t hold_ms) {
 if (!c->commit || !c->arm_restore || hold_ms == 0 ||
     !margin_test_start(&c->state, original, edge, delta)) return false;
 if (!c->commit(c->context, c->state.requested)) {
  margin_test_apply_failed(&c->state);
  return false;
 }
 if (!margin_test_applied(&c->state, now_ms, hold_ms)) {
  /* Conservative fallback: never leave a successful write untracked. */
  c->state.phase = MARGIN_ACTIVE;
  margin_controller_restore(c);
  return false;
 }
 if (!c->arm_restore(c->context, hold_ms)) {
  margin_controller_restore(c);
  return false;
 }
 return true;
}

static inline bool margin_controller_timer_fired(struct margin_test_controller *c,
 uint64_t now_ms) {
 if (!margin_test_due(&c->state, now_ms)) return false;
 bool ok = c->commit(c->context, c->state.original);
 margin_test_restore_result(&c->state, ok);
 return ok;
}
#endif
