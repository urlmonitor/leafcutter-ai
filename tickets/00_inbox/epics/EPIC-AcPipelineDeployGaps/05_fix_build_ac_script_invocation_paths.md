---
title: "Fix build-ac/ac-scanner script invocation paths for consumer-install reachability"
status: todo
components:
  - skills_system
  - build_pipeline
  - ac_store
created: 2026-06-17
depends_on:
  - 03_reconcile_ac_scanner_portability.md
priority: high
requires_diagram: false
requires_adr: false
epic: EPIC-AcPipelineDeployGaps
files_touched:
  - templates/agents/build-ac.md
  - templates/skills/build-ac/SKILL.md
  - templates/skills/ac-scanner/SKILL.md
  - scripts/goal_to_epic.py
  - scripts/commit_guardian/hooks/check_ac_done_on_merge.py
  - scripts/build_phases.py
  - docs/architecture/adrs/ADR-013-portable-skill-script-deployment-boundary.md
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 05: Fix build-ac/ac-scanner Script Invocation Paths

## Goal

In order for the `portable: true` skills `ac-scanner` and `build-ac` to actually
run on a consumer install, the deployed `build-ac` agent template and the two
skill SKILL.md files must invoke the six AC-pipeline scripts at the path where
the build actually deploys them, and `goal_to_epic.py` must resolve its sibling
scripts correctly from its deployed location.

## Context

Ticket 03 (ADR-013) added `build_ac_store()` to deploy the six AC scripts so the
portable skills become functional on consumer installs. A post-epic manual
behavioral spot-check, followed by an architecture + build-layer + coupling
review, found the deliverable does **not** achieve end-to-end reachability:

**Verified facts (real build into a temp target dir):**

1. `build_ac_store()` is dispatched via the `artifact_phases` loop in
   `scripts/build.py` as `fn(output_root, ...)`, so the scripts physically land
   at `<target>/.leafcutter/scripts/ac_store/` — NOT at `<target>/scripts/ac_store/`.
   Confirmed: a real build placed `goal_to_epic.py` and `ac_prioritizer.py` under
   `.leafcutter/scripts/ac_store/`; no project-root `scripts/ac_store/` exists.
   (The `build_ac_store()` docstring and ADR-013 body claiming `<target_root>/scripts/`
   are stale — same `target_root`-vs-`output_root` naming confusion as BP-811.)

2. `templates/agents/build-ac.md` invokes the scripts as bare `scripts/ac_store/...`
   and `scripts/goal_to_epic.py` / `scripts/build_ac_mode_detection.py`. These bare
   paths resolve in **neither** a consumer install **nor** the self-build — both
   deploy under `.leafcutter/scripts/`.

3. The build-blessed, proven convention for referencing a deployed script from a
   compiled template is the `{{config.output_root}}/scripts/...` placeholder, which
   `scripts/template_compiler.py` (`inject_config`) substitutes to `.leafcutter/scripts/...`
   at build time. This is exactly how the commit_guardian pre-commit `entry:` lines
   reach their scripts (`templates/scripts/commit_guardian/commit_guardian.json`).
   `build-ac.md` contains no placeholder at all.

4. `build_ac_store()` deploys all six scripts into `ac_store/` (including
   `goal_to_epic.py` and `build_ac_mode_detection.py`, whose source lives at
   `scripts/` root), but `build-ac.md` references those two at `scripts/` root —
   a subdir-level mismatch on top of the path-base problem.

5. `scripts/goal_to_epic.py` finds its siblings via
   `Path(__file__).parent / "ac_store" / "<x>.py"` (lines ~361, ~1037, ~1526) and a
   `sys.path.insert(0, Path(__file__).parent / "ac_store")`. When `goal_to_epic.py`
   is itself deployed **into** `ac_store/`, this resolves to the non-existent
   `ac_store/ac_store/<x>.py`. It must be location-aware.

**Chosen direction (review consensus): Option A** — keep the top-level
`scripts/ac_store/` deploy layout per ADR-013 (do NOT move scripts into the skill
dirs; that breaks the unit-test imports and the cross-script `sys.path`/subprocess
web), and do NOT add a generic `scripts/` shim (violates the deliberate
`.leafcutter` explicit-path convention). Instead, fix the invocation paths to the
placeholder convention and make `goal_to_epic.py` deploy-location-aware.

The six scripts are coupled by subprocess calls + one `sys.path` import
(`goal_to_epic.py` → `scan_ac_store`, `→ generate_ticket_from_ac` subprocess;
`ac_prioritizer.py` → `scan_ac_store` subprocess; `check_ac_done_on_merge.py` →
`mark_ac_done.py` subprocess), so paths must be corrected in concert.

## AC References

- Builds on AC of ticket 03 (`build_ac_store()` deployment phase).
- Sibling to BP-811 (workflow-shim path mismatch) — same `output_root` root cause family.

## Acceptance Criteria

- [ ] AC-1: The deployed `build-ac` agent template references every AC-pipeline
  script via the `{{config.output_root}}/scripts/ac_store/<name>` placeholder
  (compiled to `.leafcutter/scripts/ac_store/<name>` on a default consumer build),
  for all of: `ac_prioritizer.py`, `generate_ticket_from_ac.py`, `mark_ac_done.py`,
  `scan_ac_store.py`, `goal_to_epic.py`, `build_ac_mode_detection.py`. No bare
  `scripts/...` invocation of these scripts remains in `templates/agents/build-ac.md`.
- [ ] AC-2: The inline-Python `sys.path.insert(...)` snippets in `build-ac.md`
  (for importing `goal_to_epic`, `scan_ac_store`, `build_ac_mode_detection`) point
  at the deployed `ac_store/` directory via the same placeholder convention, so the
  imports resolve on a consumer install.
- [ ] AC-3: `templates/skills/build-ac/SKILL.md` and `templates/skills/ac-scanner/SKILL.md`
  reference the scripts at paths consistent with AC-1 (including the `goal_to_epic` /
  `build_ac_mode_detection` `ac_store/` subdir), with no stale `scripts/<x>` references
  that would mislead the agent.
- [ ] AC-4: `scripts/goal_to_epic.py` resolves its sibling scripts
  (`generate_ticket_from_ac.py`, `scan_ac_store`, and any `ac_store/` siblings) in a
  deploy-location-aware way: it works both when run from its source location
  (`scripts/goal_to_epic.py`, siblings under `scripts/ac_store/`) and when deployed
  into `.../scripts/ac_store/goal_to_epic.py` (siblings alongside it). No path
  resolves to a doubled `ac_store/ac_store/` segment.
- [ ] AC-5: `scripts/commit_guardian/hooks/check_ac_done_on_merge.py` invokes
  `mark_ac_done.py` at a path that resolves on a consumer install (deployed under
  `.leafcutter/scripts/ac_store/`), not a hardcoded project-root `scripts/ac_store/`
  path that does not exist there.
- [ ] AC-6: The stale `<target_root>/scripts/...` wording in the `build_ac_store()`
  docstring (`scripts/build_phases.py`) and in ADR-013 is corrected to reflect that
  deployment is under the consolidated output root (`.leafcutter/scripts/ac_store/`).
- [ ] AC-7: A test asserts end-to-end consistency — every AC-pipeline script path
  referenced by `build-ac.md` (after compilation) matches a path actually produced by
  `build_ac_store()` under the output root; and `goal_to_epic.py`'s sibling resolution
  finds an existing file when invoked from a simulated deployed `ac_store/` location.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Test Requirements

Tests for the path-consistency contract and `goal_to_epic.py` deploy-aware sibling
resolution.

### Test Cases

#### test_build_ac_template_script_paths_match_deploy_layout
- **Path:** `tests/test_build_ac_paths.py`
- **Asserts:**
  - After compiling `templates/agents/build-ac.md` through the template compiler
    with the default config, every AC-pipeline script invocation resolves under
    `.leafcutter/scripts/ac_store/`.
  - The set of script filenames referenced by `build-ac.md` is a subset of the
    filenames deployed by `build_ac_store()` into `ac_store/`.
  - No bare `scripts/<name>.py` invocation of the six scripts remains post-compile.

#### test_goal_to_epic_sibling_resolution_when_deployed_in_ac_store
- **Path:** `tests/test_build_ac_paths.py`
- **Asserts:**
  - When `goal_to_epic.py` is copied into a temp `.../scripts/ac_store/` alongside
    its siblings, its sibling-path resolution points at existing files (no
    `ac_store/ac_store/` doubling).
  - When run from the source layout (`scripts/goal_to_epic.py`, siblings under
    `scripts/ac_store/`), resolution still finds the siblings.

## Risk & Safety

- **Touches money?** No.
- **Touches data?** No — affects build deployment + agent/skill prompt paths only.
- **Blast radius?** Bounded: 2 agent/skill prompt files, 2 SKILL.md, `goal_to_epic.py`
  sibling resolution, one commit_guardian hook path, plus docstring/ADR text. The
  source locations of the scripts in the repo do NOT move (Option A), so the
  `unit_tests/ac_store/*` and `unit_tests/agents/*` imports that insert `scripts/`
  or `scripts/ac_store/` on `sys.path` are unaffected.
- **Reversibility?** High — path-string and resolution-logic changes; revert restores
  prior behavior.

### Failure Modes & Mitigations

1. Placeholder not substituted (template not compiled through `inject_config`) →
   mitigation: AC-1/AC-7 test compiles the template and asserts the resolved path.
2. `goal_to_epic.py` guard mis-detects its location → mitigation: AC-4 test runs both
   the source-layout and deployed-layout cases.
3. commit_guardian hook path regressed → mitigation: AC-5 + existing hook tests.
