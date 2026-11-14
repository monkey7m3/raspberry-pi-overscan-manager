#include <assert.h>
#include <stdint.h>
#include "margin-test-state.h"

int main(void) {
 struct margin_test_state s = {0};
 uint64_t original[4] = {77, 76, 44, 30};
 assert(margin_test_start(&s, original, 0, 10));
 assert(s.original[0] == 77 && s.requested[0] == 87);
 assert(s.requested[1] == 76);
 assert(!margin_test_start(&s, original, 0, 10));
 assert(margin_test_applied(&s, 1000, 5000));
 assert(!margin_test_due(&s, 5999));
 assert(margin_test_due(&s, 6000));
 margin_test_restore_result(&s, false);
 assert(s.phase == MARGIN_RESTORE_FAILED);
 assert(margin_test_retry_restore(&s));
 margin_test_restore_result(&s, true);
 assert(s.phase == MARGIN_IDLE);
 assert(!margin_test_start(&s, original, 0, 26));
 assert(!margin_test_start(&s, original, 4, 1));
 assert(margin_test_start(&s, original, 3, 1));
 margin_test_apply_failed(&s);
 assert(s.phase == MARGIN_IDLE);
 return 0;
}
