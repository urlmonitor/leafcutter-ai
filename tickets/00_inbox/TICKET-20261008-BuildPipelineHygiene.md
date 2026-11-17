---
title: "Build-pipeline hygiene: durations job gets the web toolchain, dead manifest helpers go, copy shims stop resurrecting retired commands"
status: todo
components:
  - build_pipeline
created: 2026-10-08
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - build
  - ci
  - hygiene
  - copy-shims
  - adr-041
  - windows
last_updated: 2026-10-08
files_touched:
  - .github/workflows/test-durations.yml
  - scripts/build_deploy_manifest_helpers.py
  - scripts/build_ownership.py
  - docs/acceptance-criteria/knowledge-management/KM-300-docs-same-everywhere/KM-300b-1.yaml
  - docs/acceptance-criteria/knowledge-management/KM-300-docs-same-everywhere/KM-300b-2.yaml
  - docs/acceptance-criteria/knowledge-management/KM-300-docs-same-everywhere/KM-300b-3.yaml
  - unit_tests/build_guards/test_copy_shim_mirrors_only_produced_files.py  # new
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Build-pipeline hygiene: durations job gets the web toolchain, dead manifest helpers go, copy shims stop resurrecting retired commands

## Actor / Goal
In order that the build pipeline's own housekeeping stops producing wrong signals, we need three
small fixes:
- (a) the durations job runs the vitest-backed tests for real;
- (b) dead copies of two deploy-manifest helpers stop misleading implementers;
- (c) a copy-mode build stops putting a retired command back into the canonical command folders.

Then shard balance, deploy-list edits and `check-output-drift` all reflect the real state.

## Context

### (a) `test-durations.yml` lacks the web toolchain
- `.github/workflows/test-durations.yml` (job `record`) runs the whole suite to record
  per-test durations for pytest-split. Its steps are checkout, setup-python, dev deps, build,
  corpus fetch and the suite. There is no `actions/setup-node` and no
  `npm ci --prefix leafcutter-web` (0 matches, 2026-10-08).
- The vitest-backed proof tests (`test_done_proof_composite_js.py`,
  `test_done_proof_js_integration.py`) fail fast there by design ("Required runtime proof cannot
  run"). Their recorded durations are therefore near zero. pytest-split then treats them as
  free and packs them onto one shard: the same failure mode the workflow's own `fetch-depth`
  comment warns about.
- `ci.yml`'s `test-shard` job already has the two steps (:348-363, TICKET-20261006-CiShardsInstallWebToolchain,
  commit `37b622b27`). That ticket listed this workflow as a follow-up in its Out of Scope.

### (b) Dead copies of `_manifest_workflow_tool_scripts` and `_manifest_knowledge_scripts`
- `scripts/build_deploy_manifest_helpers.py` defines both (:137-164, :167-181). `scripts/build.py`
  imports them from `build_phases_knowledge` (:69), and only the other eight helpers from this
  module (:70-79). Nothing else imports the two copies (grep, 2026-10-08).
- The copies are stale. The live workflow-tool tuple has five entries the copy lacks:
  - `knowledge_frontmatter_reader.py`
  - `frontmatter_path_resolver.py`
  - `knowledge_file_nodes.py`
  - `knowledge_surface_check.py`
  - `knowledge_rendering.py`

  The live knowledge tuple lists seven scripts; the copy lists only `harvest_learnings.py`.
  TICKET-20260928-GE-118d had already called it "a second, already-stale copy ... confirmed dead
  code".
- The module docstring still says "ten" helpers, all imported by `build.py`.
- The it_requirements of KM-300b-1, KM-300b-2 and KM-300b-3 (todo), and of the done KM-300a-1
  and KM-300a-2, tell implementers to add any module extracted from `generate_doc_index.py` to
  "every deploy list that already names generate_doc_index.py (scripts/build_deploy_manifest_helpers.py, ...)".
  That list is dead, so an edit there changes nothing and the real list can be missed.

### (c) Retired hub command keeps reappearing; why #972 did not stop it (investigated 2026-10-08)
- **Symptom.** `.claude/commands/leafcutter.md` and `.gemini/workflows/leafcutter.md`, the old
  hub command renamed to `leafcutter-help`, reappear after `build.py --target-dir <worktree>`.
  `check-output-drift` then reports `gaps=2` until both are deleted by hand.
- **What #972 does** (TICKET-20260930-RetireRenamedCommandOutputs, `scripts/build_retired_outputs.py`).
  Following ADR-041, it removes a retired command only when the previous install's
  `.build_manifest.json` still records it, with a matching hash. A file the manifest does not
  record "is not a candidate at all: it is neither touched nor named". That ticket's Known Limit 2
  says this case "cannot be cleaned automatically". BP-1500b-4 requires the same for the general
  sweep. #972 therefore works as designed and does not reach these files.
- **Evidence that the files are unrecorded.** Worktree
  `TICKET-20261002-KernelResearchBeforeBlindEscalation.md` still holds
  `.leafcutter/commands/leafcutter.md` and `.leafcutter/gemini/workflows/leafcutter.md`
  (hash `cdecb31d…`, the old hub output). Its latest manifest (built 2026-10-06) has no record of
  either.
- **Why they reappear (reproduced 2026-10-08).** With copy-strategy shims (Windows without
  symlink rights), `install_shims` mirrors each output-root folder into its canonical folder
  with `shutil.copytree(source, canonical, dirs_exist_ok=True)` (`scripts/build_ownership.py:611-621`).
  That copies every file in `.leafcutter/commands/`, including ones this build did not produce.
  In a scratch install of main, the reproduction was:
  1. place the two unrecorded old files under `.leafcutter/`;
  2. run `build.py --target-dir`.

  The build re-created `.claude/commands/leafcutter.md` and `.gemini/workflows/leafcutter.md` and
  printed "(no command or workflow template retired since the last install)". The usual hand
  workaround deletes only the two canonical copies, so the next build brings them straight back.
- **Where the unrecorded copies came from (partly unconfirmed).** A fresh build of current main
  writes no `leafcutter.md` (verified). In worktree `TICKET-20261002-KernelChoiceWithCondition.md`
  (created 2026-10-02 14:25, after #972 merged at 2026-10-01 07:27), all of `.leafcutter/commands/`
  carries the 2026-09-25 09:31 mtimes of the main checkout's own `.leafcutter/commands/`. The
  folder was therefore copied with timestamps from the main checkout's older install, not built.
  No packaged step makes such a copy (searched `templates/workflows-js`, `worktree-agent`,
  `setup_ticket_worktree.py`), so it was most likely an agent improvising a worktree bootstrap.
  A survey of the worktrees folder on 2026-10-08 found no worktree created after 2026-10-02 14:25
  with the files.

## Acceptance Criteria
- [ ] AC-1 (a): `test-durations.yml`'s `record` job runs "Set up Node" (`actions/setup-node@v4`,
  `node-version: "20"`, `cache: "npm"`, `cache-dependency-path: leafcutter-web/package-lock.json`)
  and `npm ci --prefix leafcutter-web` before the suite step. They are copied from `ci.yml`
  `test-shard`, with a comment that the two must stay in step.
- [ ] AC-2 (a): After a manual dispatch of the workflow, the refreshed durations file records
  non-trivial durations for the `test_done_proof_composite_js.py` and
  `test_done_proof_js_integration.py` tests (none of them a fast-fail), checked in the run's PR.
- [ ] AC-3 (b): `_manifest_workflow_tool_scripts` and `_manifest_knowledge_scripts` are defined
  only in `scripts/build_phases_knowledge.py`. The copies in `build_deploy_manifest_helpers.py`
  are deleted, its docstring states the helpers it actually holds, and the build's
  manifest/deploy parity tests pass.
- [ ] AC-4 (b): No AC whose `work_status` is not `done` names `build_deploy_manifest_helpers.py`
  as a deploy list for `generate_doc_index.py`. KM-300b-1, -2 and -3 are amended with the reason,
  and the AC store validators pass.
- [ ] AC-5 (c): With copy-strategy shims, a file in an output-root shim source
  (`<output_root>/commands/`, `<output_root>/gemini/workflows/`, and the other folder shims) that
  the current build does not produce is not copied into the canonical folder. Replaying the
  2026-10-08 reproduction leaves `.claude/commands/leafcutter.md` and
  `.gemini/workflows/leafcutter.md` absent, and the deployed `check-output-drift` exits 0.
- [ ] AC-6 (c): Files the current build produces are still mirrored in copy mode. An
  adopter-owned file already in the canonical folder is still left untouched (ADR-041 2b). The
  BP-1500g ownership/shim suites and the `test_retired_command_outputs*` suites pass where they
  passed before.

## Test Requirements

```yaml
tests:
  - name: test_copy_shim_does_not_mirror_unproduced_output_root_files
    location: unit_tests/build_guards/test_copy_shim_mirrors_only_produced_files.py
    type: integration
    covers: [AC-5]
    description: |
      Real build.py into a temp target with shim_strategy copy; place an unrecorded
      .leafcutter/commands/leafcutter.md and .leafcutter/gemini/workflows/leafcutter.md; rebuild;
      assert neither canonical copy exists and the deployed check-output-drift exits 0. Red today
      on every platform once the copy strategy is forced.
  - name: test_copy_shim_still_mirrors_produced_files_and_keeps_adopter_files
    location: unit_tests/build_guards/test_copy_shim_mirrors_only_produced_files.py
    type: integration
    covers: [AC-6]
    description: |
      Same install: every produced command file is present in .claude/commands, and an
      adopter file placed in .claude/commands before the rebuild is byte-identical afterwards.
  - name: existing build manifest/deploy parity tests
    location: unit_tests/
    type: integration
    covers: [AC-3]
    description: |
      test_guard_source_paths_match_deployable_set and the deploy-manifest parity tests stay
      green after the dead helpers are deleted.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | YAML parse + actionlint of test-durations.yml | | |
| AC-2 | workflow_dispatch run and its PR | | |
| AC-3 | existing parity tests | | |
| AC-4 | AC store validators | | |
| AC-5 | test_copy_shim_does_not_mirror_unproduced_output_root_files | | |
| AC-6 | test_copy_shim_still_mirrors_produced_files_and_keeps_adopter_files; BP-1500g suites | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] (a) Add the two Node steps to `test-durations.yml` with a keep-in-step comment.
- [ ] (b) Delete the two dead helpers, fix the module docstring, amend KM-300b-1/-2/-3.
- [ ] (c) In the copy branch of the folder shim (`build_ownership.py`), mirror only files the
  current build's mappings produce for that folder, instead of the whole output-root folder.
- [ ] (c) One-off, outside the repo: delete all four stale copies in the affected local worktrees
  (the two canonical paths and the two `.leafcutter/` paths). Deleting only the canonical pair is
  undone by the next copy-mode build.
- [ ] Tests above.

## Design Notes
For (c), the alternative of attributing unrecorded files by content hash against a list of
retired outputs conflicts with BP-1500b-2 ("never from a maintained list of known-stale names")
and with ADR-041's non-attribution rule. The shim change avoids attribution entirely: it only
stops copying what this build did not produce. The unrecorded `.leafcutter/` copy stays where it
is, unreachable through the canonical folder. Under symlink shims it stays visible, but there a
single hand deletion is permanent, because no copy step recreates it.

## Risk & Safety
- Touches money? No.
- Touches data? (c) changes which files a copy-mode build writes into canonical folders. It
  writes fewer files and never deletes any.
- Reversibility: revert the commit; rebuild.

## Out of Scope
- Changing the retirement step or the BP-1500b sweep's attribution rules.
- Making the build create symlinks on Windows.
- Identifying the agent or tool that copied the main checkout's `.leafcutter/` into new worktrees
  on 2026-10-02. It has not recurred since.
