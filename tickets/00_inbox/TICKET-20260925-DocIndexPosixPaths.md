---
title: "Doc index links use forward slashes on every platform"
status: todo
components:
  - documentation_system
  - precommit_hooks
created: 2026-09-25
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - docs
  - windows
  - portability
  - bugfix
files_touched:
  - scripts/generate_doc_index.py
  - unit_tests/commit_guardian/test_generate_doc_index_posix_paths.py
  - docs/INDEX.md
last_updated: 2026-09-25
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# Doc index links use forward slashes on every platform

## Actor / Goal
In order to keep `docs/INDEX.md` usable on every platform, we need the doc-index
generator to emit forward-slash link paths regardless of the operating system it runs
on, so that a commit made on Windows no longer rewrites every link in the index into
a broken, platform-specific form.

## Context
`scripts/generate_doc_index.py` builds each link from `Path.relative_to(repo_root)`
and interpolates the `Path` object straight into the Markdown (lines 261 and 298 on
`origin/main` 4b05997a). On Windows that renders as `docs\reference\foo.md`, so every
row of the regenerated index carries backslash separators.

The `transform-doc-index` pre-commit hook (`templates/scripts/commit_guardian/transform_doc_index.py`)
imports `generate_doc_index.generate_index()` and re-stages the result on any commit
that stages a `docs/*.md` file. So on Windows the corruption is not a manual-regeneration
hazard: **every docs commit rewrites the whole index**.

Evidence:
- Measured 2026-09-25: `docs/INDEX.md` has 179 links with 0 backslashes on `origin/main`,
  but commit `c24e4ec2` (branch `acs/bo-3200f-chartered-executor`, already pushed, PR
  not yet opened) carries an index where all 173 links contain backslashes. The hook
  staged that rewrite automatically.
- The same defect was observed and worked around by hand at least four times without
  being ticketed: `EPIC-TruthfulProjectRecord` tickets 12 (UXP-700b-1-i), 23 (UXP-700c-2-ii),
  24 (UXP-700c-3) and 29 (UXP-700d-1) each record reverting a backslash-corrupted
  regeneration.
- It currently blocks committing `EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs` ticket 01
  (GE-120f-1), whose docs changes would trigger the hook.
- **Scope amended 2026-09-25 (user decision): the corruption has reached `main`.** After
  this ticket was written, `origin/main` moved to `4b05997a` and its `docs/INDEX.md`
  now has 183 of 183 links with backslashes, introduced by `e3a9b34b` (PR #895,
  EPIC-TruthfulProjectRecord). `e919a24f` and `ccd77adb` were clean. The user chose to
  repair the committed index in this same PR (AC-6), so `main` is fixed as soon as it
  merges rather than staying broken until a follow-up. Nothing in this commit would
  regenerate the index on its own: the hook fires only when a `docs/*.md` file is staged.

Existing tests of the generator that must keep passing:
`unit_tests/commit_guardian/test_generate_doc_index_last_updated.py`,
`unit_tests/commit_guardian/test_km_dbf_014_doc_index_idempotent.py`,
`unit_tests/commit_guardian/test_transform_doc_index.py`,
`unit_tests/build_guards/test_doc_index_frontmatter.py`.

## Acceptance Criteria
- [ ] AC-1: Every link target and link text that `generate_index()` emits uses `/` as the path separator, on Windows as well as POSIX — no emitted link contains a backslash.
- [ ] AC-2: Every link target in a freshly generated index resolves, relative to the repository root, to a file that exists (so the fix does not trade backslashes for broken paths).
- [ ] AC-3: Through the real `transform-doc-index` hook entry point (`run_hook.py` + `transform_doc_index.py`), a commit that stages a `docs/*.md` change on Windows leaves `docs/INDEX.md` with no backslash link paths.
- [ ] AC-4: The test for AC-1 fails against the current code on the platform the suite runs on — on POSIX as well as Windows — so the guard is not silently green in CI (e.g. by driving the path-formatting step with Windows-style paths rather than relying on the host `os.sep`).
- [ ] AC-5: The existing doc-index test modules listed in Context still pass.
- [ ] AC-6: The committed `docs/INDEX.md` is regenerated with the fixed generator: it contains no link with a backslash, every link target resolves to an existing file relative to the repository root, and regenerating it again produces no change.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Test Requirements

```yaml
tests:
  - file: unit_tests/commit_guardian/test_generate_doc_index_posix_paths.py
    covers: [AC-1, AC-4]
    description: Emitted link targets and texts contain no backslash; the check is driven so it fails on the current code on both POSIX and Windows hosts.
  - file: unit_tests/commit_guardian/test_generate_doc_index_posix_paths.py
    covers: [AC-2]
    description: Generate the index for the real docs tree; every link target resolves to an existing file relative to the repository root.
  - file: unit_tests/commit_guardian/test_generate_doc_index_posix_paths.py
    covers: [AC-3]
    description: Run the transform-doc-index hook through its registered entry point against a staged docs change in a temporary repository; the resulting docs/INDEX.md has no backslash link paths.
```

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-09-25 18:40 — test-writer (status: ok)
feedback-id: fb_2026-09-25_8944b93f
completion_manifest:
  tests_written: true
  tests_red_for_right_reason: true
  ac2_test_honestly_green_documented: true
  existing_baseline_tests_pass: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "scripts/generate_doc_index.py generate_index() (and its two interpolation sites, _render_single_file / _render_directory)"
    consuming_side: "templates/scripts/commit_guardian/transform_doc_index.py main(), invoked through its REAL registered entry point (python .leafcutter/scripts/commit_guardian/run_hook.py .leafcutter/scripts/commit_guardian/transform_doc_index.py) against a fresh temp git repo, asserting on the docs/INDEX.md bytes it writes and stages"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python .leafcutter/scripts/commit_guardian/run_hook.py .leafcutter/scripts/commit_guardian/transform_doc_index.py (CLI subprocess) — named verbatim in the dispatch request as the exact command .pre-commit-config.yaml wires; copied through unchanged, not re-resolved"
Wrote unit_tests/commit_guardian/test_generate_doc_index_posix_paths.py (336 lines, under the 400-line cap) with 3 test functions covering AC-1/AC-2/AC-3/AC-4. AC-1/AC-4 (test_ac1_ac4_link_paths_have_no_backslash_on_any_host) monkeypatches pathlib.Path.relative_to to return a PureWindowsPath so the backslash bug reproduces identically on POSIX and Windows hosts (verified red here: 183 offending links) — confirmed by direct reasoning that PureWindowsPath's __str__ is platform-independent, not host-os-dependent. AC-3 (test_ac3_hook_via_run_hook_entrypoint_leaves_no_backslash_index) drives the real run_hook.py -> transform_doc_index.py entry point against a temp git repo and is red natively on this win32 host (1 offending link pair); it is NOT patched for POSIX reproduction because AC-4 only names the AC-1 test, and this integration test's host-dependence is inherent to a defect that only manifests through this exact pipeline on Windows — documented plainly in the module docstring. AC-2 (test_ac2_real_docs_tree_link_targets_resolve_to_existing_files) is honestly GREEN today even though the bug is confirmed present: on Windows, backslash-separated paths still resolve via Path(), so this AC's literal "resolves to an existing file" contract already holds; it remains a valuable regression guard once python-coder's as_posix() fix lands, per the ticket's own escape-hatch instruction to say so plainly rather than force it red. Ran all 4 existing baseline modules named in ## Context: 24 passed, 3 skipped (unrelated to this ticket), 0 failed. Tag choice: used the ticket's own literal AC ids (# covers: AC-1 / AC-4 / AC-2 / AC-3) plus # angle: criterion|real_artifact|reachability per function, placed on the line directly above each def per check_test_ac_tags's first checked location. Anomaly found: check_test_ac_tags.py's COVERS_REGEX requires exactly 3 digits after the dash (`[A-Z]{2,6}-[0-9]{3}`), so a literal "AC-1"/"AC-4" tag does NOT match it; this repo has no test_ac_tag_enforcement key set in commit_guardian.json, so enforcement defaults to "warn" mode (exit 0 regardless) — confirmed by reading read_enforcement_mode()'s fallback. This only produces a non-blocking stderr warning at commit time, never a blocker; flagging for python-coder/pr-reviewer awareness rather than silently reformatting the ticket's own AC ids. Second anomaly: this ticket has no ## Sign-offs section at all (confirmed by full-file read); following the established repo convention in scripts/repair_epic_member_pr_phase.py ("a ticket with no ## Sign-offs section at all is repaired by the frontmatter flip alone... none is invented"), I flipped only the frontmatter agents.test-writer line and did not fabricate a Sign-offs section.

### 2026-09-25 19:10 — python-coder (status: ok)
feedback-id: fb_2026-09-25_c61a0dd2
completion_manifest:
  red_baseline_results:
    - test_name: test_ac1_ac4_link_paths_have_no_backslash_on_any_host
      result: green
    - test_name: test_ac3_hook_via_run_hook_entrypoint_leaves_no_backslash_index
      result: green
  ac2_stayed_green: true
  existing_baseline_tests_still_pass: true
  build_synced: true
  ruff_clean: true
  doc_enforcer_fields_present: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "scripts/generate_doc_index.py _render_single_file / _render_directory"
    consuming_side: "templates/scripts/commit_guardian/transform_doc_index.py main(), exercised through the real run_hook.py -> transform_doc_index.py entry point by test_ac3 against a temp git repo"
Fixed the two interpolation sites named in the ticket (`_render_single_file` line ~261, `_render_directory` line ~298 on origin/main) by switching `path.relative_to(repo_root)` / `f.relative_to(repo_root)` to `.relative_to(repo_root).as_posix()`, and appended a DECISION HISTORY entry. Grepped the rest of the file for any other Path interpolated into emitted Markdown (`relative_to`, `{rel}`, `{path}`, `{f}` patterns) — found no other site; the two named sites were the only offenders. Ran the new test file (`unit_tests/commit_guardian/test_generate_doc_index_posix_paths.py`): 3/3 green, including the two previously-red tests (test_ac1_ac4_link_paths_have_no_backslash_on_any_host, test_ac3_hook_via_run_hook_entrypoint_leaves_no_backslash_index); test_ac2 stayed green. Ran the four existing baseline modules named in AC-5: 24 passed, 3 skipped (same skip set as test-writer's baseline; unrelated to this change), 0 failed. Ran `python scripts/build.py` to sync the deployed `.leafcutter/scripts/...` copy, then `git restore docs/INDEX.md docs/agents/cards/ LEAFCUTTER_VERSION` to drop the unrelated regenerated build output — `git status` now shows only `scripts/generate_doc_index.py` modified plus the test file and this ticket added, as required. Regenerated `docs/INDEX.md` with the fixed generator as a spot-check: 183 links, 0 containing a backslash; it does NOT byte-match the currently-committed `docs/INDEX.md` on this branch (the committed file itself has backslash-corrupted links from a prior regeneration — same defect this ticket fixes), then restored it per the ticket's Out-of-Scope note. `ruff check scripts/generate_doc_index.py` reports no issues; the module docstring already carried MODULE/GOAL/BUSINESS CONTEXT/ARCHITECTURE headers pre-existing this change, so no doc-enforcer fixes were needed beyond the new DECISION HISTORY entry. No `### python-coder` subsection exists under `## Implementation Tasks` (it is a flat, non-agent-scoped list authored by test-writer/architect), so per signoff §1.5 step 1 I left those checkboxes untouched rather than fabricating agent ownership of them.

### 2026-09-25 12:05 — test-runner (status: ok)
feedback-id: fb_2026-09-25_1619d7e3
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
Ran (1) unit_tests/commit_guardian/test_generate_doc_index_posix_paths.py — 3 passed, matching python-coder's report; (2) the four AC-5 baseline modules (test_generate_doc_index_last_updated.py, test_km_dbf_014_doc_index_idempotent.py, test_transform_doc_index.py, test_doc_index_frontmatter.py) — 24 passed, 3 skipped, matching the stated baseline exactly; (3) grepped unit_tests/ for other references to docs/INDEX.md, generate_doc_index, or transform_doc_index — no additional test files found beyond those already covered in (1) and (2). AC-6 verified directly: docs/INDEX.md has 0 backslash-containing link targets across 183 links, and all 183 targets resolve to existing files relative to repo root. Regenerating via `python scripts/generate_doc_index.py` reproduces byte-identical Markdown content (git diff against the staged copy showed zero content changes) but writes CRLF line endings (247/247 lines) where the staged blob is LF-only (0 CR, per `.gitattributes eol=lf`) — flagged per the dispatch instructions rather than committed, and the staged copy was restored with `git checkout -- docs/INDEX.md`; `git status` now shows the worktree back to exactly the original staged change set (docs/INDEX.md, scripts/generate_doc_index.py, the ticket, and the new test file). No test, source, or index file was modified. No failures observed; nothing to classify as related or unrelated.

### 2026-09-25 12:08 — pr-reviewer (status: ok)
feedback-id: fb_2026-09-25_b8a16144
completion_manifest:
  as_posix_covers_both_sites: true
  no_other_writer_or_consumer_expects_backslashes: true
  ac1_ac4_test_reproduces_cleanly: true
  ac3_test_drives_real_hook_entrypoint: true
  index_diff_is_separator_only: true
No high- or medium-confidence findings. Verified both `.as_posix()` sites cover link target AND link text (both interpolate the same `rel` string), confirmed via grep that `relative_to` appears nowhere else in `generate_doc_index.py`, and confirmed `scripts/build.py`'s `build_doc_index()` and the `transform-doc-index` hook are the only other readers/writers of `docs/INDEX.md`, both routed through the same fixed `generate_index()`. The AC-1/AC-4 `PureWindowsPath` monkeypatch is scoped via `patch.object` as a context manager (auto-restored, no leakage) and cannot mask other behaviour since `relative_to` has no other call site in the module. The AC-3 test's subprocess command (`run_hook.py` + `transform_doc_index.py`) matches `.pre-commit-config.yaml`'s `entry:` line verbatim, and its `tempfile.TemporaryDirectory()` context manager cleans up automatically. Ran all 3 new tests (3 passed) and all 4 AC-5 baseline modules (24 passed, 3 skipped) locally — matches prior agents' reports. Confirmed the `docs/INDEX.md` diff is separator-only by normalizing `\`→`/` on both sides and comparing as multisets (183 removed / 183 added, equal), and confirmed AC-6's regenerate-again claim by byte-comparing a fresh regeneration against the staged file with CRLF/LF normalized (identical — the CRLF-vs-LF divergence test-runner flagged is a pre-existing write-mode behavior orthogonal to this ticket's scope, not a content difference). On the `check_test_ac_tags.py` COVERS_REGEX anomaly test-writer flagged (`# covers: AC-1` doesn't match the `AC-[0-9]{3}` pattern): confirmed the repo has no `test_ac_tag_enforcement` key set, so it runs in warn mode (exit 0) — this does not block the commit and I am not treating it as one; it's a pre-existing hook/ticket-numbering-convention mismatch outside this ticket's scope, not a regression this diff introduces. Nothing blocks this commit.

### 2026-09-25 12:10 — commit (status: ok)
feedback-id: fb_2026-09-25_2045f1bd
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
User pre-authorized this fix being built and committed ("Ticket + fix it now", 2026-09-25); confirmation gate satisfied non-interactively per dispatch instructions. Step 0a probe passed clean (`failing_checks: []`). Preconditions verified: branch `fix/doc-index-posix-paths`, exactly the 4 named paths staged (docs/INDEX.md M, scripts/generate_doc_index.py M, this ticket A, unit_tests/commit_guardian/test_generate_doc_index_posix_paths.py A), nothing else staged/unstaged/untracked. This ticket has no `## Sign-offs` section (confirmed by prior agents' entries above), so per repo convention I flipped only the `agents.commit` frontmatter line to `signed_off` without fabricating a Sign-offs section. Proceeding to `git commit`.

## Implementation Tasks
- [ ] Write the failing tests (AC-1 to AC-4) first.
- [ ] Emit `rel.as_posix()` (or equivalent) for link targets and text at both sites in `scripts/generate_doc_index.py`.
- [ ] Run `python scripts/build.py` so deployed copies used by the hook match.
- [ ] Run the existing doc-index test modules (AC-5).

## Out of Scope
- Repairing the corrupted `docs/INDEX.md` on the unmerged branches `acs/bo-3200f-chartered-executor` (`c24e4ec2`) and `acs/bo-3200f-executor-prereqs`. They pick up the repaired index from `main` when they are next merged with it; resolve the resulting `docs/INDEX.md` conflict in favour of `main`'s regenerated copy. (`main`'s own index IS in scope — see AC-6.)
- Other Windows-encoding failures in the suite (`charmap` / em-dash mojibake) — separate defects.

## Risk & Safety
- Touches money? No.
- Touches data? Rewrites a generated docs index only; output becomes identical across platforms. On POSIX the emitted text is unchanged.
- Reversibility? Fully reversible; single generator change with no persisted state.
