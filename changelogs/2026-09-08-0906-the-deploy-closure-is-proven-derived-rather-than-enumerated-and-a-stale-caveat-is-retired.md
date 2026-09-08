---
title: "The deploy closure is proven derived rather than enumerated, and a stale caveat is retired"
date: "2026-09-08"
time: "09:06"
type: manual
components:
  - build_pipeline
  - ac_store
summary: "Added the missing test proving that a deployed script's dependency list is genuinely computed from its real imports rather than a hand-maintained list that happens to be complete, and corrected a week-old note that had wrongly called a different, already-done fix incomplete."
description: "One commit (e32546f291). BP-900g-8-i was specified but never written: the decisive case (a brand-new module imported by an already-deployed script, no manifest edited) is the only test that can tell a derived closure from a secretly-enumerated one. unit_tests/test_bp_900g_8_i.py adds four tests covering that case plus a second-hop dependency, an out-of-package control, and an assertion against the produced target tree. Since the guard (_check_intra_package_closure_guard, live since 8cb6fbd36) was already correct, non-vacuity was proven by mutation rather than a red baseline. Also corrected: a stale caveat on BP-900g-8 claiming BP-900g-5 was falsely done, now annotated as superseded rather than acted on."
commits:
  - e32546f29
breaking: false
---

## Entry

`BP-900g-8` requires that a deployed script's intra-package dependency set be
**derived** from what the script actually resolves. Its own criteria say so
explicitly: a hand-maintained manifest "does not satisfy this criterion even
when it happens to be complete on the day it is written." The mechanism that
does the deriving is not new — `build.py`'s
`_check_intra_package_closure_guard` has computed the true transitive closure
via an AST walk, before any output is written, since `8cb6fbd36`. This commit
does not build that mechanism. It builds the test that can tell it apart from
a fake.

The problem a closure guard like this can hide is specific: a dependency set
that is secretly just a list, kept in sync by hand, passes every test that
only ever exercises modules already on the list. The one case that forces the
distinction is adding a brand-new module, having an already-deployed script
import it, and editing no manifest — if the build doesn't catch that, nothing
is actually being derived. That exact case was specified as `BP-900g-8-i` and
sat `work_status: todo` with no coverage; `BP-900g-8`'s own 2026-09-01
amendment had already flagged the omission as a recommendation, and nothing
had acted on it until now.

`unit_tests/test_bp_900g_8_i.py` implements all four `test_spec` entries:
the decisive newly-added-module case, a second-hop case (a dependency of a
dependency), an out-of-package control (stdlib, third-party, and host-project
imports must produce no finding), and an assertion made against the produced
target tree rather than the source tree.

Because the implementation was already correct, there was no way to capture a
red baseline from the tests themselves, so non-vacuity was proven by mutation
instead: stubbing `_check_intra_package_closure_guard` to return `0`
unconditionally turned three of the four tests red. The fourth is unaffected
by design — it asserts on the set `compute_intra_package_closure` returns,
not on block behaviour, so a stubbed-out guard has nothing to falsify there.
The mutation was reverted; `scripts/build.py` carries zero net diff from this
change.

Separately, the commit checked and retired a stale caveat. Since its
2026-08-17 authoring pass, `BP-900g-8`'s record had carried a note claiming
`BP-900g-5` was falsely marked done because the deploy map was still
hand-maintained. Checked against current source, that isn't so:
`BP-900g-5`'s requirements are implemented and covered, and the edge the
caveat doubted — that the manifest scripts are derived from
`AC_STORE_DEPLOY_MAP` — demonstrably exists. The caveat predates `8cb6fbd36`
by over a week. `BP-900g-5` was not modified; the caveat is now annotated as
superseded so it isn't actioned again.

`BP-900g-8-i` was flipped to `done` through `mark_ac_done.py`'s
coverage-gated path.
