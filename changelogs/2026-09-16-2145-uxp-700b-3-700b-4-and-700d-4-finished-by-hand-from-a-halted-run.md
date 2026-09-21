---
title: "UXP-700b-3, UXP-700b-4 and UXP-700d-4 finished by hand from a halted /build-feature run"
date: "2026-09-16"
time: "21:45"
type: manual
components:
  - ux_prototyping
  - documentation_system
summary: "Completes three tickets left uncommitted by the interrupted /build-feature run wf_3d2879c1-2ae: an every-record rule checked against zero records now reports that it was not exercised, and never as the run's own overall checked-and-sound outcome (UXP-700b-3); the record's checker gains a reader-facing reference naming every outcome it can report and what each does and does not license a reader to conclude (UXP-700b-4); and the product-truth checker now states, per artifact type, how many of its records belong to the project versus the example product, naming any type whose population is entirely example content (UXP-700d-4)."
description: "Run wf_3d2879c1-2ae drove EPIC-TruthfulProjectRecord and halted with tickets 16 (UXP-700b-3), 18 (UXP-700b-4) and 36 (UXP-700d-4) staged but uncommitted, each carrying a recorded blocker. UXP-700b-3's AC-4 test asserted the not-exercised CLI's exit code differs from the holds CLI's exit code, but both are correctly, independently pinned to 0 (this ticket's own reachability test, and the done sibling UXP-700b-3-i's) -- a structural contradiction, not an implementation gap. Resolved by reading AC-4's own text as being about the run's overall OUTCOME, not its exit code: the test was renamed test_ac4_not_exercised_outcome_differs_from_holds_outcome and rewritten to assert payload['outcome'] differs, which the existing, unmodified production code already satisfies. UXP-700b-4's documentation-verifier blocker was a mis-scoped Agent Contract line: its AC-1 target_path named GE-120.yaml, copy-pasted from the contract's own 'existing docs to update / cross-link' context list, while documentation-expert's real deliverable -- docs/reference/product-truth-checker-outcomes.md -- was cross-linked, not modified, exactly as its own sign-off comment said. Corrected the target_path to the real deliverable and independently verified the doc's claims (outcome table, precedence order, exempt-check list, not-executed reason strings) line-by-line against the current checker code. UXP-700d-4's ac-fulfillment-gate blocker was an open question (add the two implementing files to files_touched so the gate could auto-fix work_status/implemented_by, or hand-set them directly) that could not be auto-resolved because the ticket's files_touched was empty by construction; resolved per the user's direct decision by setting files_touched to the ticket's real files and hand-recording implemented_by (replacing a stale, non-existent ticket path) and covered_by on the AC YAML directly. The shared file docs/product-truth/scripts/validate_product_truth.py mixed this group's UXP-700d-4 wiring with unrelated UXP-700c-2/UXP-700c-2-ii freshness code (_check_freshness, _sync_behind_marks, confirmed/behind state) in the halted run's saved patch; only the three hunks UXP-700d-4 actually needs (the compute_type_population/compute_example_only_types import, run_checks()'s type_population entry, and main()'s example_only_types derivation plus extended contract tuple) were hand-extracted and applied, confirmed clean by grep for freshness/behind content afterward. docs/product-truth/schemas/flow.schema.json was correctly left untouched."
commits:
breaking: false
---

## Entry

Three tickets from the halted `/build-feature` epic run `wf_3d2879c1-2ae`
(EPIC-TruthfulProjectRecord) were finished by hand at the user's direction on
2026-09-16, on branch `feature/uxp-700b-3-b-4-d-4` off `origin/main`.

**UXP-700b-3 — an every-record rule with no records to test reports that it
was not exercised.** Three of this AC's four tests already passed as a side
effect of the done sibling ticket `UXP-700b-3-i`'s own implementation of
`docs/product-truth/scripts/universal_rule_check.py`. The fourth,
`test_ac4_not_exercised_exit_code_differs_from_holds_exit_code`, was
structurally unsatisfiable as written: it demanded the not-exercised CLI's
exit code differ from the holds CLI's, but both are correctly, independently
pinned to `0` by two already-passing tests (this ticket's own reachability
test, and the done sibling's). AC-4's own text names the run's overall
*outcome*, not its exit code, so the test was renamed
`test_ac4_not_exercised_outcome_differs_from_holds_outcome` and rewritten to
assert `payload["outcome"]` differs between the two runs — already true of
the unmodified production code. No production change was needed.

**UXP-700b-4 — a reference for what each outcome of the record's checker
licenses a reader to conclude.** `documentation-verifier` had blocked commit
because the ticket's `## Agent Contracts` AC-1 line named
`GE-120.yaml` as its `target_path` — copy-pasted from the contract's own
"existing docs to update / cross-link" context list rather than set to the
real deliverable. `documentation-expert`'s actual output,
`docs/reference/product-truth-checker-outcomes.md`, was already correct and
complete (verified here line-by-line against the current checker code: the
four-value outcome table, `_top_level_outcome`'s precedence order, the
`eval`/`labels` exempt-check list and their absence from `CHECK_READS`, and
the `record_check_not_executed` reason strings all match). Corrected the
contract line's `target_path` to the file actually produced.

**UXP-700d-4 — an artifact type whose whole population is example content is
reported.** `docs/product-truth/scripts/product_truth_outcome.py` gained
`compute_type_population` (per-artifact-type project/example split, built on
`UXP-700d-1`'s `is_example_artifact_id`) and `compute_example_only_types`
(names, by type, any type whose project count is zero while its example
count is not — a both-zero type stays in the pre-existing `empty_types`
vocabulary instead). Both figures now ride
`validate_product_truth.py`'s existing single stdout JSON outcome-contract
line as `type_population` / `example_only_types`. Against the real,
checked-in store: `mockups` (0 project / 10 example) and `mock-data` (0
project / 2 example) are entirely example content and are named
example-only; `flows` (11 project / 3 example) is mixed and is never
reported example-only. `ac-fulfillment-gate` had left an open question
(populate `files_touched` for auto-fix, or hand-set `work_status`/
`implemented_by`) because the ticket's `files_touched` was empty; resolved
per the user's direct decision by setting `files_touched` to the ticket's
real files and hand-recording `implemented_by`/`covered_by` on the AC YAML
directly (`work_status` was left for `mark_ac_done.py`'s own coverage-gated
flip).

All three tickets' implementation and tests were already largely complete in
the halted run's saved patches (`staged.patch` / `unstaged.patch`); this
entry records a hand takeover that re-applied only this group's files (the
shared `validate_product_truth.py` file was hand-split to exclude unrelated
`UXP-700c-2`/`UXP-700c-2-ii` freshness code destined for a later group),
completed the missing `UXP-700d-4` wiring, resolved each ticket's recorded
blocker, and independently re-verified the work: ran
`unit_tests/product_truth/` under `AC_ENFORCE_STRICT=1` against a disposable
pristine `origin/main` baseline (108 passed / 0 failures here, versus 100
passed / 0 failures on baseline — the 8-test delta is this group's two new
test files), and mutation-tested `UXP-700b-3`'s and `UXP-700d-4`'s core
behaviour (both went red under a targeted no-op mutation and green again
once restored). `UXP-700b-3`'s own `documentation-expert` AC-1 contract
(cross-linking `UXP-514.yaml`'s vacuous-truth note) remains unresolved — it
was blocked purely by the now-fixed test contradiction, but writing that
cross-link was out of this hand-takeover pass's explicit scope and is
recorded as a known follow-up rather than fabricated.
