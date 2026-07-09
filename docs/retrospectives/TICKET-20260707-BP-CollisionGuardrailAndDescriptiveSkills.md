---
title: 'Retrospective: BP-100m-1 + BP-1300a Build-Pipeline Remediation'
type: retro
status: active
created: 2026-07-08
last_updated: 2026-07-08
components:
- build_pipeline
description: 'Overview of Retrospective: BP-100m-1 + BP-1300a Build-Pipeline Remediation.'
---
# Retrospective: BP-100m-1 + BP-1300a Build-Pipeline Remediation

Date: 2026-07-08
Scope: two standalone tickets (lightweight retrospective — not an epic)
PRs: #228 (BP-100m-1), #233 (BP-1300a)
Git date range: 2026-07-07 to 2026-07-08

---

## Summary

Two standalone high-priority build-pipeline tickets shipped together over two
days to fix the root cause of `/build-feature` being silently replaced by a 21 KB
prose body on every build, and to clear the resulting CI red without discarding
AC-mandated metadata.

**TICKET-20260707-BP-100m-1** added a deploy-path collision guardrail to
`build.py` (BP-100m), retired the three shadowing prose workflow templates that
caused the collisions (BP-300d), and updated the clean command templates to use
name-based `Workflow()` invocations (BP-900g-1). The scope was necessarily
expanded mid-drive: the collision guardrail could not land green on its own
because enabling it immediately made three real collisions fatal. The test suite
expanded from 8 to 14 tests; all 14 shipped green.

**TICKET-20260708-BP-1300a-descriptive-skills** resolved a follow-on: the
`validate_agent_self_description` validator was treating `run-tests` (python-coder)
and `direct-write` (documentation-expert) as dangling skill_ids (no deployed skill
dir exists), causing the build to exit non-zero in error mode. The correct fix was
a `descriptive_only: true` marker so the validator skips directory resolution for
intentional capability-documentation entries while still failing on genuine dangling
pointers. This preserved the INF-600d-1 metadata mandate (python-coder's
skills_invoked must document its inline test-running capability). A follow-on
M-1 fix extended the same exemption to `registry_validator.check_skills_invoked_xref`
to suppress spurious advisory warnings.

---

## Metrics

### BP-100m-1 (TICKET-20260707-BP-100m-1)

| Phase | Passes | Blockers | Notes |
|-------|--------|----------|-------|
| test-writer | 2 | 0 | Round 1: 8 RED tests. Round 2 (scope expansion): expanded to 14 tests after scope grew to include BP-300d + BP-900g-1 |
| python-coder | 2 | 0 | Round 1: all 14 tests green. Round 2: ruff fixes + TestStepMapDoc repointing |
| test-runner | 1 blocker + 1 ok | 1 | Blocker: 4 ruff violations (F401/F841/E741x2) + 4 TestStepMapDoc FileNotFoundError regressions after BP-300d deleted the prose template |
| pr-reviewer | 1 blocker + 1 ok | 1 | H-1 blocker: removing run-tests/direct-write skill_ids regressed INF-600d-1; resolved by reverting registry + adding --self-description-enforcement warning flag to subprocess tests |
| commit | needed | — | |
| pull-request | needed | — | Shipped as PR #228 |

### BP-1300a (TICKET-20260708-BP-1300a-descriptive-skills)

| Phase | Passes | Blockers | Notes |
|-------|--------|----------|-------|
| test-writer | 2 | 0 | Round 1: 4 RED + 2 green regression guards. Round 2 (M-2 guards): 4 additional strict-identity guard tests |
| python-coder | 2 | 0 | Round 1: descriptive_only guard + registry entries. Round 2 (M-1 follow-on): xref suppression in registry_validator.py |
| test-runner | 1 | 0 | 6/6 passed + 22/22 after M-1 follow-on. Real build (error mode): exit 0 |
| pr-reviewer | 1 | 0 | Advisory M-1 (xref warnings for descriptive_only entries in registry_validator): non-blocking; addressed in M-1 follow-on |
| commit | needed | — | |
| pull-request | needed | — | Shipped as PR #233 |

---

## Category Breakdown (Feedback System)

No structured `feedback.jsonl` entries are available for these tickets
(all agent `feedback-id` fields are `(submit-failed)`, consistent with the
missing `.leafcutter/feedback_categories.yaml` worktree gap noted in the
Pre-Drive Checklist). The `## Comments` sections in each ticket served as
the primary phase record.

---

## Ticket Facts

| Metric | Value |
|--------|-------|
| Tickets | 2 (BP-100m-1, BP-1300a) |
| Components | build-pipeline |
| Git PRs | #228, #233 |
| Files touched (BP-100m-1) | 10 (scripts/build.py, scripts/build_phases.py, scripts/generate_agent_cards.py, templates/commands/build-feature.md, templates/commands/finalize-feature.md, 3 deleted workflow templates, unit_tests/build/test_deploy_collision_guard.py, unit_tests/test_finalize_feature_step6a.py) |
| Files touched (BP-1300a) | 4 (scripts/build_phases.py, scripts/registry_validator.py, config/agent_registry.json, unit_tests/build/test_self_description_descriptive_only.py) |
| Tests added (BP-100m-1) | 14 (collision guard suite) |
| Tests added (BP-1300a) | 12 (descriptive_only suite) |
| Blocker comments (BP-100m-1) | 1 (test-runner) + 1 (pr-reviewer H-1) |
| Blocker comments (BP-1300a) | 0 |
| Handoff comments | 0 |

---

## What Went Well

- The TDD red-baseline discipline worked cleanly on both tickets. python-coder
  received a precisely specified list of failing tests and resolved all of them
  without weakening assertions.
- pr-reviewer caught the INF-600d-1 regression (H-1) before merge. The
  registry revert was clean: `git diff HEAD -- config/agent_registry.json`
  produced empty output after the revert, confirming zero drift.
- The `--self-description-enforcement warning` isolation in subprocess-based
  tests was an elegant solution: it avoided weaking collision assertions while
  letting the build proceed past the self-description check. The 6 pure-function
  unit tests and the monkeypatched integration test were unaffected.
- The `descriptive_only: true` resolution on BP-1300a satisfied both competing
  constraints simultaneously: the guardrail (unmarked dangling pointers still
  fail) and INF-600d-1 (run-tests entry preserved with documented semantics).
- The M-1 follow-on (xref suppression) was completed in the same ticket round
  as the pr-reviewer advisory, keeping the ticket self-contained.
- Scope expansion on BP-100m-1 was user-approved before test-writer began the
  revision round. The scope note in the test-writer's second sign-off clearly
  documented what changed and why.
- The test count increase from 8 to 14 (BP-100m-1) was traceable: test-writer
  documented which tests were kept, changed, and added.
- generate_agent_cards.py dry-run fast-path fix (moving `if dry_run:` before
  the expensive `generate_card()` call) was kept as an opportunistic fix after
  pr-reviewer confirmed it was behavior-preserving and unblocked a 3m42s test
  timeout. The verdict (KEEP) and rationale were explicitly documented.

---

## Friction Points

- **Coupling discovered at red-baseline (BP-100m-1):** The guardrail ticket
  could not land green in isolation — enabling it immediately made 3 real
  collisions fatal. The scope had to expand mid-drive (user-approved) to include
  de-confliction (BP-300d) and command repointing (BP-900g-1). The 8-test suite
  was partially revised (1 test inverted from "assert non-zero" to "assert zero
  after de-confliction") and 6 new tests added. This was handled correctly but
  required a full second round from test-writer.

- **ruff violations in new test file despite python-coder claiming ruff_clean:
  true (BP-100m-1):** test-runner's blocker identified 4 ruff violations (F401,
  F841, E741x2) in `unit_tests/build/test_deploy_collision_guard.py` that
  python-coder had missed. Root cause: python-coder likely ran ruff against
  `scripts/` only, not the broader `unit_tests/` tree. The subsequent fix round
  was clean.

- **TestStepMapDoc regressions triggered by BP-300d (BP-100m-1):** Deleting
  `templates/workflows/finalize-feature.md` (intentional, part of BP-300d) broke
  4 pre-existing tests in `unit_tests/test_finalize_feature_step6a.py` that read
  that file directly. This was a legitimate side-effect but was not anticipated
  during ticket planning. The fix required repointing 2 tests to the live JS
  source and adding a `FileNotFoundError` guard to `_md_text()`. This added a
  file (`unit_tests/test_finalize_feature_step6a.py`) to `files_touched` mid-drive.

- **Cross-AC conflict surfaced by scope-creep fix (BP-100m-1 → BP-1300a):**
  python-coder removed `run-tests` and `direct-write` from `config/agent_registry.json`
  as a quick fix to silence `validate_agent_self_description` failures (which were
  blocking `test_real_build_has_no_collisions_after_deconfliction`). This was
  the WRONG fix: it discarded metadata that INF-600d-1 explicitly mandates. The
  pr-reviewer correctly identified this as an H-1 blocker. The correct resolution
  (descriptive_only marker) required a second ticket (BP-1300a). The wrong fix
  was reverted; the right fix was implemented cleanly.

- **Local-passes / CI-fails via stale artifacts (BP-100m-1 diagnosis phase):**
  An earlier fact-check concluded a build-failure premise was "false" because
  `build.py` exited 0 locally. The premise was actually true — the local tree's
  stale `.claude/skills/` artifacts resolved `run-tests` and `direct-write` as
  present, while a clean checkout lacks them. A local run against a dirty tree
  is not evidence that a CI premise is false.

- **Premise shift and reframe honesty (BP-1300a):** The "live CI red" had already
  been partially silenced (wrongly) by the BP-100m-1 python-coder removing the
  registry entries. The proper fix (marking them descriptive_only) restored them.
  The ticket clearly documented this reframe: the premise shifted mid-drive
  (the CI red was caused by the right thing being absent, not by an error in the
  build logic) and was reported honestly in the context section.

- **Out-of-scope file edit during BP-100m-1 (python-coder scope-creep):**
  python-coder edited `config/agent_registry.json` — not in `files_touched` —
  to fix a build error blocking the integration test. One edit was reverted
  (removing run-tests: wrong fix, regressed INF-600d-1) and one was kept
  (generate_agent_cards.py dry-run fast-path: behavior-preserving, explicit
  KEEP verdict from pr-reviewer). The change-scope-reviewer phase was not invoked;
  the out-of-scope edit was caught only at pr-review.

---

## Knowledge Gaps Found

- **No documented rule that a guardrail ticket must ship with its latent-bug
  remediation.** The guardrail-plus-fix coupling was discovered at red-baseline,
  requiring mid-drive scope expansion. A pre-drive planning step that asks
  "does enabling this guardrail make any currently-passing state fatal?" would
  catch this before test-writer begins.

- **No documented rule against verifying a CI/build premise via a local dirty
  tree.** The stale-artifact false-negative is a well-known footgun that has
  now affected at least two drives. The rule "if a premise claims CI/build is
  red or failing, reproduce it on a clean checkout or via a subprocess with
  `--self-description-enforcement error` explicitly set" was not written down.

- **No documented pattern for `descriptive_only: true` in skills_invoked
  registry entries.** After BP-1300a, the marker exists and is enforced, but
  the convention — when to use it, what it means, how the validator treats it —
  is only in `validate_agent_self_description`'s docstring. Any future agent
  editing `config/agent_registry.json` will not discover it without reading
  the source.

- **No standing rule to check AC cross-impact before removing registry
  entries to fix a build error.** python-coder's quick fix (remove skill_id →
  build passes) was locally correct but globally wrong because INF-600d-1 owned
  that entry. A rule like "before removing a skills_invoked entry, grep the AC
  store for any AC whose criteria references that entry" would have prevented
  the H-1 blocker.

---

## Subagent Quality Trends

No supervisor feedback entries found for these tickets (all `feedback-id` fields
are `(submit-failed)` — the worktree lacks `.leafcutter/feedback_categories.yaml`,
consistent with the pre-drive checklist gap. No adjudication events were recorded
in the telemetry system).

---

## Proposed Improvements

### KI-1: Guardrail-plus-fix coupling rule

When a ticket's primary deliverable is a build guardrail that makes a previously-
silent defect fatal, the ticket scope MUST include the defect's remediation. The
guardrail and its fix must ship together: a guardrail that fails the build on real
code that has always been present cannot land green in isolation.

Planning check: before test-writer begins, ask "does enabling this guardrail make
any currently-passing state fatal? If yes, expand scope to fix the latent defect."

Routing: `CLAUDE.md-inline` (Step 4) — short universal rule, every agent planning
a guardrail ticket needs it.

```diff
  ## Implementation Conventions
  ...
+ ### Guardrail tickets must ship with their latent-bug remediation
+
+ If enabling a build guardrail makes a currently-silent defect fatal,
+ expand the ticket scope to de-conflict the defect before delivering the
+ guardrail. A guardrail that fails the build on pre-existing code cannot
+ land green in isolation.
+ (Source: TICKET-20260707-BP-100m-1, BP-100m coupling discovery, 2026-07-07.)
```

*This KI is proposed — not applied. Confirm "yes" to apply or "skip" to defer.*

---

### KI-2: Never verify a CI/build premise with a local dirty-tree run

If a premise claims that build.py (or CI) is failing, DO NOT verify it by running
build.py locally against a dirty tree. Stale `.claude/skills/` artifacts on a
local checkout can resolve skill_ids absent on a clean checkout, making the build
appear to pass when it would fail in CI. Always verify a CI/build premise either
on a clean checkout or by running the subprocess with the enforcement flag
explicitly set (e.g. `--self-description-enforcement error`).

Routing: `CLAUDE.md-inline` (Step 4) — short universal rule appended to the
existing "local-passes / CI-fails" memory note.

```diff
  ## Pre-Drive Checklist
  ...
+ ### Verifying CI/build premises — never use the local dirty tree
+
+ If a ticket premise claims build.py or CI is failing, reproduce it on a
+ clean checkout or via an explicit subprocess call with enforcement flags
+ set (e.g. `--self-description-enforcement error`). A local run against a
+ dirty tree can pass due to stale .claude/skills/ artifacts that resolve
+ skill_ids absent on a clean checkout — making a true failure appear false.
+ (Source: TICKET-20260707-BP-100m-1 stale-artifact false-negative, 2026-07-07.)
```

*This KI is proposed — not applied. Confirm "yes" to apply or "skip" to defer.*

---

### KI-3: Documenting the descriptive_only skills_invoked marker convention

The `descriptive_only: true` field in a `skills_invoked` registry entry marks an
inline capability that has no deployed skill directory by design. The validator
skips skill-dir resolution for such entries but still fails on unmarked unresolvable
entries. Use `descriptive_only: true` when a skills_invoked entry documents what an
agent does inline (e.g. running tests, writing files directly) rather than invoking
a deployed skill.

Routing: `CLAUDE.md-inline` (Step 4) — short convention every agent editing
`config/agent_registry.json` needs.

```diff
  ## Implementation Conventions
  ...
+ ### descriptive_only marker in agent_registry.json skills_invoked
+
+ A `skills_invoked` entry can be marked `{"skill_id": "...", "mode": "conditional",
+ "descriptive_only": true}` to document an inline capability that has no deployed
+ templates/skills/<id>/ directory. The validator skips skill-dir resolution for
+ marked entries but still fails on unmarked unresolvable skill_ids. Use this marker
+ for capabilities like inline test-running or direct file-writing that are real
+ agent behaviors but not deployed skills. Required by INF-600d-1 for python-coder
+ (run-tests) and documentation-expert (direct-write).
+ (Source: TICKET-20260708-BP-1300a, 2026-07-08.)
```

*This KI is proposed — not applied. Confirm "yes" to apply or "skip" to defer.*

---

### KI-4: Check AC cross-impact before removing skills_invoked entries

Before removing a `skills_invoked` entry from `config/agent_registry.json` to fix
a build error, grep the AC store for any AC whose criteria or requirements reference
that entry. Removing an entry to silence a validator is the WRONG fix if an existing
approved AC mandates its presence. The correct fix is either a stub skill dir, a
`descriptive_only` marker, or a dedicated ticket that explicitly amends the owning AC.

Routing: `CLAUDE.md-inline` (Step 4) — short rule for coders making quick registry
fixes.

```diff
  ## Implementation Conventions
  ...
+ ### AC cross-impact before removing registry entries
+
+ Before removing a skills_invoked entry from config/agent_registry.json to fix
+ a build error, grep the AC store for any AC that mandates the entry. Removing
+ an entry is the WRONG fix if an existing approved AC requires it. Use the
+ descriptive_only marker or a stub skill dir instead.
+ (Source: TICKET-20260707-BP-100m-1 pr-reviewer H-1 blocker / INF-600d-1 regression,
+ 2026-07-07.)
```

*This KI is proposed — not applied. Confirm "yes" to apply or "skip" to defer.*
