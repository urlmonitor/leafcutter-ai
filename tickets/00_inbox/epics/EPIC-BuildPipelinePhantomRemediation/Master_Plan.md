---
title: "EPIC: Build-pipeline phantom-done remediation — wire missing guards, flip opposite-behavior checks"
type: epic
status: todo
components:
  - build_pipeline
  - commit_guardian
  - finalize
created: 2026-07-14
depends_on: []
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: contract_boundary
last_updated: 2026-08-17
---

# EPIC: Build-Pipeline Phantom-Done Remediation

## Goal

Close the six build_pipeline acceptance criteria that the 2026-07-14 implementation
audit found to be **phantom-done**: each carries a green (or xfail-masked) test, but
the shipped code either implements the *opposite* of the criterion, resolves against
the wrong tree, downgrades a required block to INFO, was deliberately disabled, leaves
the CI gate advisory, or asserts a workaround instead of the real guard. Every ticket
is a single root-cause fix — "wire/correct, don't rewrite".

## Context / Root cause (audit 2026-07-14)

See [reports/build_pipeline-implementation-audit-2026-07-14.md](../../../../reports/build_pipeline-implementation-audit-2026-07-14.md).
The store marks several of these `done`/`todo` while the audit found sign-offs on code
that runs the wrong behaviour (opposite-of-AC), on orphaned/absent guards, or on tests
that lock in the inverse of the criterion. This is the exact failure class the repo
exists to prevent (green tests over a guard that does not guard).

## Parallelism

**CORRECTED 2026-08-17 — the original "six tickets touch disjoint files → parallel-safe"
claim was false.** Three file collisions exist and must be serialized:

| File | Tickets | Handling |
|---|---|---|
| `scripts/build_phases.py` | **02** and **06** | Sequential: 02 → 06. Never concurrent. |
| `templates/scripts/commit_guardian/commit_guardian.json` | **08** and **09** | Serialize; whichever lands second rebases onto the first rather than re-writing the config object. |
| `templates/workflows-js/finalize-feature.js` | **04** and **09** | Serialize. (09 touches it via the BP-1100b-4 journal re-authoring.) |

Plus one logical dependency: **08 depends on 07** — the drift gates cannot report
"compared and matched" until the manifest records something to compare against.

Parallel-safe groups: **{02 → 06}** · **{03}** · **{04 → 09}** · **{07 → 08}**, with
08/09 serialized against each other on the guardian config.

Within each ticket the change is still one root-cause fix.

## Systemic enabler — RESOLVED

The original plan described the **xfail-masking** enabler as being fixed separately in
the same PR via `scripts/ac_store/pytest_ac_enforcement.py`. That is now **stale**: the
mask is already defeated on the CI gate, which runs under `AC_ENFORCE_STRICT: "1"`
(EPIC-RedTestClusterRepair, ticket 09). Genuinely-failing tests surface as real failures
rather than being downgraded to xfail. The per-finding tickets below can assume a
trustworthy red/green signal.

The successor concern — tests that are green because they only *grep* for a symbol rather
than execute the behaviour — is now ticket **09** (BP-1100b-4 / BP-1100b-5), inside this
epic rather than alongside it.

## Tickets

| # | File | Fixes (leaf ACs) | Root-cause file | Depends On | Status |
|---|------|------------------|-----------------|------------|--------|
| 01 | [01_bp900c3_allowlist_masks_templates_commit.md](./01_bp900c3_allowlist_masks_templates_commit.md) | BP-900c-3 | scripts/build_propagation_audit.py (`_suggest_action`) | — | **SUPERSEDED — already fixed on main** (`status: done`) |
| 02 | [02_bp1300a1_canonical_skill_resolution.md](./02_bp1300a1_canonical_skill_resolution.md) | BP-1300a-1, BP-1300a-1-i, BP-1300a-1-ii | scripts/build_phases.py (~L1867 `in_project`) | — | `[ ]` |
| 03 | [03_bp100i3_deployed_parity_blocking.md](./03_bp100i3_deployed_parity_blocking.md) | BP-100i-3 | templates/scripts/commit_guardian/check_hook_parity.py (`check_deployed_parity`) | — | `[ ]` |
| 04 | [04_fin100e_autoticketing_decision.md](./04_fin100e_autoticketing_decision.md) | FIN-100e-1, FIN-100e-2 | templates/workflows-js/finalize-feature.js (Step 6a) | — | `[ ]` |
| 05 | [05_bp1200b1_ci_test_gate_blocking.md](./05_bp1200b1_ci_test_gate_blocking.md) | BP-1200b-1, BP-1200b-1-i, BP-1200b-1-ii | .github/workflows/ci.yml (`continue-on-error`) | — | **SUPERSEDED — already fixed on main** (`status: done`) |
| 06 | [06_bp900g1_command_reachability_guard.md](./06_bp900g1_command_reachability_guard.md) | BP-900g-1, BP-900g-1-i | scripts/build_phases.py (command-reachability check) | 02 (same file) | `[ ]` |
| 07 | [07_bp100k12_manifest_records_what_the_gates_compare.md](./07_bp100k12_manifest_records_what_the_gates_compare.md) | BP-100k-1, BP-100k-2 | scripts/build_helpers.py (`write_build_manifest`) | — | `[ ]` |
| 08 | [08_bp100k3_drift_gates_report_gaps_not_passes.md](./08_bp100k3_drift_gates_report_gaps_not_passes.md) | BP-100k-3, BP-100k-3-i | templates/scripts/commit_guardian/check_build_drift.py + check_output_drift.py | 07 | `[ ]` |
| 09 | [09_bp1100b45_presence_only_assertions_stop_counting.md](./09_bp1100b45_presence_only_assertions_stop_counting.md) | BP-1100b-4, BP-1100b-5 | new templates/scripts/commit_guardian/check_presence_only_assertions.py + unit_tests/_workflow_engine_harness.py | — | `[ ]` |

Tickets 01 and 05 were closed `status: done` on 2026-08-17 with the verification evidence
recorded in each ticket's `## Comments`. They remain in the folder as the audit trail for
why they are not being driven — **do not dispatch them**. Effective drivable set: **02,
03, 04, 06, 07, 08, 09**.

## Scope refresh (2026-08-17)

A three-agent review (product-owner / business-analyst / it-po) re-read the six original
tickets against today's tree and against the 49 `build_pipeline` ACs authored since
2026-07-15. Findings:

**Two original findings self-healed and the store was never told.**

- **01 / BP-900c-3 — superseded.** `scripts/build_propagation_audit.py::_suggest_action`
  now evaluates the `_PREFIXES_WITH_EXISTING_DEPLOY_PHASE` branch **before** the allowlist
  branch, with the BP-900c-3 rationale in a comment. `unit_tests/test_build_tracked_source_guard.py`
  is green under `AC_ENFORCE_STRICT=1`. The AC still reads `work_status: not_started`.
- **05 / BP-1200b-1 — superseded.** `.github/workflows/ci.yml` job `test` /
  `name: "Test suite (pytest)"` carries no `continue-on-error`, runs under
  `AC_ENFORCE_STRICT: "1"`, and its name is pinned as the BP-1200c branch-protection
  contract. It is a required check as of 2026-08-17. The AC still reads `work_status: todo`.

Driving either as written would dispatch a test-writer onto an already-green suite — a
TDD-order violation, not a pass. **Do not drive 01 or 05.**

**BP-100i-3 (ticket 03) is the inverse and is the flagship phantom.** Its AC now reads
`work_status: done` with `covered_by: …::TestDeployedParityContentHash` — the
*content-hash* class, which only covers scripts present in **both** trees — while
`check_hook_parity.py::check_deployed_parity` still prints
`INFO — … (Non-blocking.)` for the missing-script case the criterion demands exit 1 for.
Ticket 03 must therefore also **reset `work_status` off `done` and repoint `covered_by`**,
or the AC-enforcement layer will read the new RED proof test as a done-AC regression
rather than a red baseline.

**Six newer ACs joined the epic**, bundled by root-cause file into tickets 07-09 — not
one ticket per AC. `BP-1100b-4` and `BP-1100b-5` required an IT-PO enrichment pass first
(`assigned_agent`/`estimated_complexity` were `null`, which made the generator emit a
literal `- [ ] None` sign-off line); `BP-100k-1/-2/-3/-3-i` needed explicit `test_spec`.
All six remain `readiness: draft` — they still need the approval gate.

**Deliberately excluded**, with grounds:

| Group | Grounds |
|---|---|
| `BP-1400` + 11 children | Owned by `EPIC-ChangesToTheWebAppCantReachUsersBroken`; all leaf ACs have live tickets there. A new gate for a new surface, not a lying guard. |
| `BP-300e` + 12 children | Prose-tolerant reply parsing — runner robustness, not verdict trust. Already built and green (`parseAgentJson`, PRs #339/#340). Residual: five delivery workflows still bypass it (BP-300e-5) — own follow-up. |
| `FIN-100g-2/-3/-4` + `-i` children | Already implemented, covered and green; loose tickets read `status: done`. The ACs simply have no `work_status`. Reconciliation, not work. |
| `FIN-100c-5/-6/-8` | Already implemented and cited by id in `finalize-feature.js`. Reconciliation. |
| `FIN-100c-10/-11/-12/-13/-14/-15` | Doc + code-quality follow-ups on the shipped recovery block, all touching `finalize-feature.js` (collides with 04). `-14` is on-theme but is one child of a five-AC family — keep the family intact; ticket 09's gate will catch it mechanically. |
| `BP-017` | Symlink shim target relativity — a correctness bug, not a guard that fails to guard. Also an **orphan**: `parent: null`, loose at the component root. Needs an L1 home before anyone builds it. |
