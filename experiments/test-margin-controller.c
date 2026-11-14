#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "margin-test-controller.h"
struct fake { uint64_t last[4]; int commits; bool fail_commit, fail_timer; uint64_t timer; };
static bool commit(void *ctx, const uint64_t v[4]) {
 struct fake *f = ctx;
 f->commits++;
 if (f->fail_commit) return false;
 memcpy(f->last, v, sizeof(f->last));
 return true;
}
static bool arm(void *ctx, uint64_t ms) {
 struct fake *f = ctx;
 f->timer = ms;
 return !f->fail_timer;
}
int main(void) {
 const uint64_t orig[4] = {77,76,44,30};
 struct fake f = {0};
 struct margin_test_controller c = {.context=&f,.commit=commit,.arm_restore=arm};
 assert(margin_controller_start(&c,orig,0,10,1000,5000));
 assert(f.last[0] == 87 && f.timer == 5000);
 assert(!margin_controller_timer_fired(&c,5999));
 assert(margin_controller_timer_fired(&c,6000));
 assert(f.last[0] == 77 && c.state.phase == MARGIN_IDLE);
 f.fail_timer = true;
 assert(!margin_controller_start(&c,orig,0,10,7000,5000));
 assert(f.last[0] == 77 && c.state.phase == MARGIN_IDLE);
 f.fail_timer = false;
 f.fail_commit = true;
 assert(!margin_controller_start(&c,orig,0,10,8000,5000));
 assert(c.state.phase == MARGIN_IDLE);
 f.fail_commit = false;
 assert(margin_controller_start(&c,orig,0,10,9000,5000));
 f.fail_commit = true;
 assert(!margin_controller_timer_fired(&c,14000));
 assert(c.state.phase == MARGIN_RESTORE_FAILED);
 f.fail_commit = false;
 assert(margin_controller_restore(&c));
 assert(c.state.phase == MARGIN_IDLE && f.last[0] == 77);
 return 0;
}
