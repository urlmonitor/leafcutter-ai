---
title: "DECISION+ACTION: finalize Step 6a auto-ticketing — re-enable to satisfy FIN-100e-1/e-2 or formally supersede them"
status: done
components:
  - finalize
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: internal
source_ac: FIN-100e-1
ac_coverage:
  - FIN-100e-1
  - FIN-100e-2
files_touched:
  - templates/workflows-js/finalize-feature.js
  - unit_tests/test_finalize_feature_step6a.py
  - docs/acceptance-criteria/build_pipeline/FIN-100-pre-merge-safety-gate/FIN-100e-1.yaml
  - docs/acceptance-criteria/build_pipeline/FIN-100-pre-merge-safety-gate/FIN-100e-2.yaml
agents:
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: signed_off
  pull-request: needed
---

# 04: Resolve the finalize auto-ticketing contradiction (decision + action)

## Actor / Goal

As the finalize-feature workflow, I want the Step 6a auto-ticketing contract reconciled
with reality — either the behaviour FIN-100e-1/e-2 describe actually runs, or those ACs
are formally retired with a documented rationale — so the store stops asserting a
behaviour the code was deliberately built to *not* perform.

## Remediation Context (audit 2026-07-14)

**Opposite/disabled behaviour, test locks it in.** FIN-100e-1 ("one tracking ticket is
created per pre-existing or flaky failure") and FIN-100e-2 ("ticket creation failure is
non-fatal and does not halt the workflow") describe a Step 6a auto-ticketing loop in
`templates/workflows-js/finalize-feature.js`. That loop was **deliberately DISABLED**
under EPIC-FinalizeFeatureHardening, and `unit_tests/test_finalize_feature_step6a.py`
locks in the disabled behaviour — so both the code and its test assert the opposite of the
two ACs. This is not a wiring bug; it is a live contradiction between an intentional
product decision and an unretired requirement.

**Do: force the decision, then act.** This ticket is a **DECISION + ACTION**:

- **Option (a) — re-enable** the non-fatal Step 6a auto-ticketing so FIN-100e-1/e-2 are
  satisfied: iterate pre_existing/flaky triage entries, dispatch create-ticket for each
  (including test_id, baseline_sha, triage_category, baseline_run_at; flaky entries note
  intermittence), wrap each dispatch in try/catch pushing a `null` sentinel on failure and
  continuing (never halting), and record ticket paths in `created_tracking_tickets`. Only
  choose this if re-enabling is trivial and still wanted.
- **Option (b) — supersede with rationale (DEFAULT).** If auto-ticketing is intentionally
  not-wanted (the EPIC-FinalizeFeatureHardening decision stands), formally retire
  FIN-100e-1 and FIN-100e-2: set `status` and `superseded_by`/rationale in their AC YAML
  documenting *why* auto-ticketing was disabled and what replaced it, and leave the
  existing test asserting the disabled behaviour (renaming/annotating it as the
  intentionally-disabled contract).

Default to **option (b)** unless the assignee confirms re-enabling is trivial and desired.
Do not leave the store/code contradiction standing either way.

## Acceptance Criteria

Reconciles FIN-100e-1, FIN-100e-2 (verbatim Gherkin under
`docs/acceptance-criteria/build_pipeline/FIN-100-pre-merge-safety-gate/`). Definition of
done: the code, the test, and the two AC records agree — either the auto-ticketing
behaviour runs and is tested green, OR the ACs are marked superseded/retired with a
rationale that references the disabling decision, and the test documents the intentional
disablement.

## Test Requirements

```yaml
tests:
  - name: test_step6a_contract_matches_decision
    file: unit_tests/test_finalize_feature_step6a.py
    covers: [FIN-100e-1, FIN-100e-2]
    asserts: (option a) auto-ticketing dispatches one ticket per pre_existing/flaky entry and is non-fatal on dispatch failure; OR (option b) the ACs are superseded and the test documents the intentionally-disabled Step 6a.
```

## Sign-offs

- [x] architect-review — 2026-08-18 13:59
- [x] test-writer — 2026-08-18 14:30
- [x] python-coder — 2026-08-18 15:10
- [ ] test-runner
- [ ] pr-reviewer
- [x] commit — 2026-08-18 15:45
- [ ] pull-request

## Comments

### 2026-08-18 13:59 — architect-review (status: ok)
feedback-id: fb_2026-08-18_80c98f0d
completion_manifest:
  blast_radius_reviewed: true
  rubric_applied: true
  frontmatter_gap_fixed: true
Classified SMALL: 4 files_touched, all within the single `finalize` component
(finalize-feature.js Step 6a, its lock-in test, and the two child AC YAMLs);
no always-large trigger fires (no Alembic migration, no hypertable change, no
FastAPI surface touched, no ADR-* file/contract touched) and no package
boundary is crossed. `requires_adr: false` confirmed correct — this formalizes
an existing EPIC-FinalizeFeatureHardening decision rather than introducing a
new cross-cutting contract, so no new ADR is warranted. Also filled in two
frontmatter fields (`change_target: pipeline`, `risk_surface: internal`) that
the `ticket_frontmatter_guard` hook flagged as missing on this ticket — these
were a pre-existing gap, not something introduced by this sign-off.

**Architectural note.** Code (`finalize-feature.js` Step 6a) and its test
(`test_finalize_feature_step6a.py`) already agree with each other — auto-
ticketing is deliberately disabled and the test locks that in with 15 grep-style
assertions (e.g. `createdTrackingTickets` must not exist, `untrackedFailures[]`
is the replacement, the success message must say "not auto-ticketed"). The
contradiction is external: FIN-100e-1 and FIN-100e-2 still describe the
opposite (a dispatch loop to `create-ticket` with a try/catch null-sentinel).
The ticket's default (option b — supersede with rationale) is architecturally
sound and lower-risk than option (a): re-enabling would resurrect a behaviour
an earlier epic explicitly killed for `create-ticket` being a workflow, not a
dispatchable agent (per the current code's own comment at line 617). One
layering risk to flag for the coder/test-writer: the parent AC `FIN-100e.yaml`
lists `covered_by: [FIN-100e-1, FIN-100e-2, FIN-100e-3]` and is itself still
`status: active` with a title ("Pre-existing failures are auto-ticketed, not
ignored") that will read as stale once its two children are superseded — that
parent file is NOT in this ticket's `files_touched`, so per the project's
"stage the parent alongside the child" convention, whoever implements option
(b) should at minimum flag the parent's staleness in a comment even if they
correctly leave it out of scope, so it does not silently rot. Also note
`FIN-100e-3.yaml` declares `parent: FIN-100e-1` (not `FIN-100e`), an existing
hierarchy inconsistency independent of this ticket — out of scope here, but
worth a follow-up ticket if not already tracked.

Acceptance-criteria adjustments: none required beyond what the ticket already
specifies; the Test Requirements section already correctly frames both options
as valid closes.

### 2026-08-18 14:30 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_written: true
  red_baseline_captured: true
  bug_fix_regression_test: false
Extended `unit_tests/test_finalize_feature_step6a.py` with a new
`TestStep6aContractMatchesDecision` class (`test_ac_status_matches_actual_js_dispatch_behaviour`,
`test_disabled_step6a_test_documents_ac_supersession`) covering FIN-100e-1/FIN-100e-2. Both
tests read the real on-disk AC YAML (`FIN-100e-1.yaml` / `FIN-100e-2.yaml`) and the real JS
source rather than mocks; the first fails today because the ACs are still `status: active` while
`finalize-feature.js` implements no create-ticket dispatch loop, and the second fails because
this test module's own top docstring does not yet name either AC (locking in the ticket's
stated option-(b) default — supersede with rationale — while leaving a comment noting the
assertion should be amended if option (a) is chosen instead). Verification run:
`python -m pytest unit_tests/test_finalize_feature_step6a.py -v` — 2 failed (both new tests,
both `AssertionError`), 17 pre-existing tests still pass; `ruff check` on the file is clean.
red_baseline:
  - test_name: test_ac_status_matches_actual_js_dispatch_behaviour
    file: unit_tests/test_finalize_feature_step6a.py
    error: "AssertionError: FIN-100e-1/FIN-100e-2 are still status:active (claiming Step 6a dispatches create-ticket per pre_existing/flaky entry, recording paths in created_tracking_tickets), but finalize-feature.js implements no such dispatch loop. Either re-enable the loop (option a) or formally supersede both ACs with a rationale (option b, the ticket's default) so the store stops asserting a behaviour the code was deliberately built not to perform."
  - test_name: test_disabled_step6a_test_documents_ac_supersession
    file: unit_tests/test_finalize_feature_step6a.py
    error: "AssertionError: This test module's top docstring must reference FIN-100e-1 so the intentional Step 6a disablement is traceable to the superseded AC from the lock-in test's own header"

### 2026-08-18 15:10 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  option_selected: true
  ac_yaml_reconciled: true
  red_baseline_green: true
  js_code_changed: false
Chose option (b) (the ticket's default, endorsed by architect-review as lower-risk):
no code change to `finalize-feature.js` was made — it already implements the
intentionally-disabled Step 6a (`untrackedFailures[]` report, no create-ticket
dispatch loop) and that behaviour is out of scope to change. Reconciled the store
by setting `status: superseded_by` on both `FIN-100e-1.yaml` and `FIN-100e-2.yaml`,
each with an `amended_by` entry recording the rationale (loop deliberately disabled
under EPIC-FinalizeFeatureHardening, replaced by the `untrackedFailures[]` report,
no successor AC authored since the replacement is already covered by the existing
lock-in test) and `by: python-coder`. Updated `unit_tests/test_finalize_feature_step6a.py`'s
module-level docstring (only the header text the test-writer's red-baseline test
specifically checks via `__doc__`) to name both FIN-100e-1 and FIN-100e-2, tracing the
intentional disablement back to the superseded AC records, per the ticket's explicit
instruction to annotate the existing lock-in test with the decision — no new test
assertions were authored (test-writer owns test logic). `python -m pytest
unit_tests/test_finalize_feature_step6a.py -v` — 19 passed (both red_baseline tests
now green: `test_ac_status_matches_actual_js_dispatch_behaviour`,
`test_disabled_step6a_test_documents_ac_supersession`; the 17 pre-existing tests
stayed green). `ruff check unit_tests/test_finalize_feature_step6a.py` clean.
`python scripts/ac_store/validate_ac_schema.py` on both edited AC YAML files: OK.
No Python production code was added, so doc-enforcer/complexity-reduction have no
new functions to check; the only Python touched is the test file's docstring text
and two AC YAML data files.

Flagging architect-review's noted follow-up per their sign-off comment (not in this
ticket's `files_touched`, left out of scope as instructed): the parent AC
`FIN-100e.yaml` still reads `status: active` with title "Pre-existing failures are
auto-ticketed, not ignored" and `covered_by: [FIN-100e-1, FIN-100e-2, FIN-100e-3]` —
now stale since its first two children are superseded. Recommend a follow-up ticket
to update `FIN-100e.yaml`'s status/title/covered_by (and separately reconcile
`FIN-100e-3.yaml`'s `parent: FIN-100e-1` hierarchy inconsistency, also noted by
architect-review as pre-existing and out of scope here).

### 2026-08-18 15:45 — commit (status: ok)
Auto-authorized commit gate: subject "docs(ac-store): supersede FIN-100e-1/e-2, reconcile Step 6a auto-ticketing contradiction"; staged files: docs/acceptance-criteria/build_pipeline/FIN-100-pre-merge-safety-gate/FIN-100e-1.yaml, docs/acceptance-criteria/build_pipeline/FIN-100-pre-merge-safety-gate/FIN-100e-2.yaml, unit_tests/test_finalize_feature_step6a.py.
feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Verified `templates/workflows-js/finalize-feature.js` was intentionally left
unmodified (python-coder's sign-off already confirmed no code change was
needed); staged only the three files that actually changed
(FIN-100e-1.yaml, FIN-100e-2.yaml, unit_tests/test_finalize_feature_step6a.py)
by name — left the unrelated concurrent modifications to
`scripts/build_phases.py` and the untracked `unit_tests/build_guards/test_bp_100k_1.py`
alone (shared worktree, out of this ticket's files_touched). Pre-flight checks:
`python -m pytest unit_tests/test_finalize_feature_step6a.py -q` — 19 passed;
`python scripts/ac_store/validate_ac_schema.py` on both edited AC YAML files — OK.
`.claude/skills/signoff` / commit_guardian probe scripts are not present in this
worktree (incomplete guardian install) — probe skipped per policy, proceeded to
commit.

## Escalation

Branch: none
Reason: 4 files_touched, all in one component (`finalize`); no always-large
trigger fired (no Alembic migration, no hypertable change, no FastAPI/public-API
change, no ADR-* file or contract touched); no cross-package boundary crossed.
