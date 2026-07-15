---
title: "DECISION+ACTION: finalize Step 6a auto-ticketing — re-enable to satisfy FIN-100e-1/e-2 or formally supersede them"
status: todo
components:
  - finalize
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
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
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
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

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
