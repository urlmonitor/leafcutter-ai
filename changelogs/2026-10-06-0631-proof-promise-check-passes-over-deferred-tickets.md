---
title: "Proof-promise check passes over deferred tickets"
date: "2026-10-06"
time: "06:31"
type: manual
components: 
  - build_pipeline
  - commit_guardian
summary: Parking a ticket as deferred is no longer refused for proofs that are not due yet.
description: "The proof-promise pre-commit check refused any staged ticket with promised proofs and no matching tests unless it was still marked todo. Deferring a ticket that was never started was therefore blocked. Deferred tickets are now passed over like todo ones, and the output names the real status. In-progress, blocked, done and unreadable states are still checked. The governing requirement is amended to match."
tickets: 
  - TICKET-20261006-ProofPromiseCheckPassesOverDeferredTickets
---

## Entry

### Changed

- `templates/scripts/commit_guardian/check_proof_promise_claim.py` — `deferred` joins `todo` as not yet due.
- `BP-1100g-4-ii` — passed-over set widened to `todo` or `deferred`.

### Added

- Two behavioural tests in `unit_tests/commit_guardian/test_bp_1100g_4_ii_parked.py`; shared
  helpers moved to `unit_tests/commit_guardian/_bp_1100g_4_ii_fixture.py`.
