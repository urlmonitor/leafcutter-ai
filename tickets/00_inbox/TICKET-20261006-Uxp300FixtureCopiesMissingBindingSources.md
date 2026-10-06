---
title: "UXP-300 bounded-store fixture copies the planning sources that missing bindings declare"
status: todo
components:
  - ux_prototyping
created: 2026-10-06
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - product-truth
  - test-fixture
  - uxp-300
last_updated: 2026-10-06
files_touched:
  - unit_tests/product_truth/_uxp_300_store.py
agents:
  test-writer: not_needed
  python-coder: signed_off
  commit: needed
---

# UXP-300 bounded-store fixture copies the planning sources that missing bindings declare

## Actor / Goal
In order to keep the UXP-300 behavioural proofs meaningful, we need the bounded-store
fixture to copy every repo-relative path the real flows declare. That includes the
planning sources named by `io_contracts.missing_bindings[].source`. Then a private copy
of the store passes its own validator, and the negative cases again prove exactly one
finding each.

## Context
- **Covers AC UXP-300.** See
  `docs/acceptance-criteria/ux-prototyping/UXP-300-product-truth-store/UXP-300.yaml` and
  the done ticket `tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/01_TICKET-20260909-UXP-300.md`.
- **What the fixture copies.** `copy_contract_dependencies` in
  `unit_tests/product_truth/_uxp_300_store.py` copies three kinds of dependency into the
  bounded store:
  - every `contract_definitions[*].schema`;
  - every `io_contracts.examples[*].source.path`;
  - the `kernel` / `integrations` / `knowledge` model packages.
- **The gap.** The fixture never copies `io_contracts.missing_bindings[*].source`.
- **What the validator requires.** `docs/product-truth/scripts/product_truth_contracts.py`
  (`_check_node`) requires each such source to be an existing, non-empty file under
  `docs/product-truth/` or `docs/analysis/`.
- **The breaking binding.** Flow `leafcutter/criteria-library`, step `suggest-grouping`,
  declares the source `docs/analysis/2026-10-03-jev-trial-criteria-grouping/summary.md`.
  That file lies outside `docs/product-truth/`, so the bounded store lacks it.
- **Effect.** The baseline validator run in `TestUxp300BoundedBehavior.setUp` fails. That
  turns all 8 bounded tests red, and `TestTheStorePassesItsOwnValidator` fails the same way,
  for 9 red tests in `unit_tests/product_truth/test_uxp_300.py`. The validator's error
  ("missing binding needs an existing nonempty planning source") does not name the path,
  which made the gap slow to diagnose.
- **Only gap today.** That file is the only declared root missing from the fixture.
  Copying it alone makes the bounded store `checked-and-sound`.
- **Why no shared helper.** `docs/product-truth/scripts/product_truth_contract_sources.py`
  does not enumerate declared paths; the validator collects them inline in `_check_node`.
  Extracting a shared enumerator would change the deployed validator. So the collection
  stays on the fixture side, and an independent self-check guards against future drift
  between the validator and the fixture.

## Acceptance Criteria
- [x] AC-1: `copy_contract_dependencies` copies every `missing_bindings[].source` the real
  flows declare, for every step and every branch, and copies only declared paths. It never
  copies all of `docs/analysis/` and never writes placeholder files.
- [x] AC-2: All tests in `unit_tests/product_truth/test_uxp_300.py` pass under
  `AC_ENFORCE_STRICT=1`.
- [x] AC-3: A fixture self-check fails when any repo-relative path a flow declares is
  missing from the fixture, and its error names that path and the flow. The check finds
  declared paths independently of the copy list, so a new kind of declared path is caught
  too.
- [x] AC-4: In a temporary copy of the repository, add a new `missing_binding` that points
  at a new `docs/analysis/` file, and regenerate the store presentation. The
  `test_uxp_300.py` tests stay green with no fixture edit.
- [x] AC-5: The validator is unchanged. The fix is confined to the test fixture. The
  following stay as they are:
  - the validator itself;
  - the `setUp` baseline assertion (exit 0, no failures, `checked-and-sound`);
  - the binding in `criteria-library.flow.json`.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | `test_uxp_300.py` (all bounded cases) + scratch proof | `_uxp_300_store.py::declared_dependency_paths` | yes — fixture `docs/analysis/` holds exactly the 1 declared file (repo has 108); bytes equal the repo; a branch-level binding is copied |
| AC-2 | `test_uxp_300.py` | `_uxp_300_store.py` | yes — 15 passed, 12 subtests (was 9 failed / 6 passed) |
| AC-3 | scratch proof (fixture self-check raises naming the path) | `_uxp_300_store.py::assert_declared_paths_present`, `declared_repo_files` | yes — names `leafcutter/criteria-library: docs/analysis/2026-10-03-jev-trial-criteria-grouping/summary.md`; also names a path held in an unknown field kind |
| AC-4 | scratch proof (tmp repository copy with a new analysis binding) | `_uxp_300_store.py::declared_dependency_paths` | yes — 15 passed in the copy, no fixture edit |
| AC-5 | `git diff --stat` touches only the fixture and this ticket | — | yes |

## Implementation Tasks

### python-coder
- [x] In `copy_contract_dependencies`, add `io_contracts.missing_bindings[*].source` of
  every step and branch to the declared-path set.
- [x] Add a self-check that runs after copying. It walks each fixture flow outside example
  payload values (`io_contracts.examples[*].value` is data, not a dependency), treats every
  path-shaped string that names a repository file as declared, and raises `ValueError`
  naming each flow and path the fixture lacks.
- [x] Run `AC_ENFORCE_STRICT=1 pytest unit_tests/product_truth/test_uxp_300.py`, then the
  wider `unit_tests/product_truth`, and `ruff`.

## Out of Scope
- Any change to the validator scripts, the flow schema, or the authored flows.
- Unrelated `unit_tests/product_truth` failures, for example the hook scope of
  `test_uxp_700c_3` or the timeout in `test_uxp_700d_3_i`.

## Risk & Safety
- Touches money? No.
- Touches data? No. Test-fixture only; it copies real repository bytes into a temp dir.
- Reversibility: a single-file revert.

## Sign-offs
- [x] python-coder — 2026-10-06 12:00
- [ ] commit

## Comments

### 2026-10-06 12:00 — python-coder (status: ok)
feedback-id: fb_2026-10-06_1dc432ab
red_baseline_results:
  - suite: unit_tests/product_truth/test_uxp_300.py (AC_ENFORCE_STRICT=1)
    before: "9 failed, 6 passed"
    after: "15 passed, 12 subtests passed"
**Fixture change.** `_uxp_300_store.py`:
- `declared_dependency_paths(flow)` now also collects every
  `io_contracts.missing_bindings[].source` on steps and branches.
- `copy_contract_dependencies` copies only those declared paths.
- A new `assert_declared_paths_present(store)` runs after copying. It uses
  `declared_repo_files`, an independent walk over each fixture flow that skips example
  `value` payloads. It raises `ValueError` naming `<flow id>: <path>` for any declared
  repository file the fixture lacks.

**Validator, flows, setUp.** Unchanged. There is no shared enumerator in
`product_truth_contract_sources.py`, and adding one would change the deployed validator.

**Scratch proofs.**
- AC-1/AC-3: 9/9 checks.
  - The pre-fix copier is caught, naming
    `leafcutter/criteria-library: docs/analysis/2026-10-03-jev-trial-criteria-grouping/summary.md`.
  - A path held in an unknown field is named.
- AC-4: a temporary repo copy with a new `docs/analysis` binding on
  `decision-forming#judge-gap`, regenerated with the real generator, gives 15 passed.

**Wider suite and lint.**
- `unit_tests/product_truth`: 216 passed, 1 skipped (Windows symlink).
- ruff is clean.
