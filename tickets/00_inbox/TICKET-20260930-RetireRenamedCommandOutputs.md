---
title: "Build removes installed command/workflow files whose package template was renamed or deleted"
status: in_progress
components:
  - build_pipeline
created: 2026-09-30
depends_on:
  - TICKET-20260930-RenameLeafcutterHubCommand.md
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - build
  - upgrade
  - ownership
  - adr-041
files_touched:
  - scripts/build_retired_outputs.py
  - scripts/build_phases_local_change.py
  - scripts/build_main_helpers.py
  - unit_tests/build_guards/test_retired_command_outputs.py
  - unit_tests/build_guards/test_retired_command_outputs_build.py
  - tickets/00_inbox/TICKET-20260930-RetireRenamedCommandOutputs.md
  - tickets/00_inbox/TICKET-20260930-RenameLeafcutterHubCommand.md
  - changelogs/2026-09-30-2111-the-package-knowledge-hub-command-is-now-leafcutter-help.md
last_updated: 2026-10-02
---

# Build removes installed command/workflow files whose package template was renamed or deleted

## Actor / Goal
In order to let the package rename or retire a slash command without stranding the old
one in every adopter's project, the build needs to remove an installed command/workflow
file when the package can prove it produced that file and no longer ships it. An upgrade
then leaves exactly the commands the package ships, and `check-output-drift` stays green,
with no manual cleanup.

## Context
Found while doing TICKET-20260930-RenameLeafcutterHubCommand (`/leafcutter` becomes
`/leafcutter-help`). A scratch adopter built before and after the rename kept the old
`leafcutter.md` in `.leafcutter/commands/`, `.claude/commands/` and
`.gemini/workflows/`. This happened under a plain build and under `--clean`. The deployed
`check-output-drift` then reported both canonical copies as `GAP` and exited 2 on every
commit. Rerunning `build.py`, as the hook advises, cannot clear it because the template is
gone.

Why nothing removes it today:
- `_cleanup_stale_paths` (`scripts/build.py`) walks only `_PRE_CONSOLIDATION_PATHS`, and
  treats co-claimed containers such as `.claude/commands` as containers, never per item.
- `clean_stale_artifacts` (`scripts/build_phases_clean.py`, `--clean` only) sweeps
  `.claude/{agents,skills,hooks,workflows}`. Its source manifest lists only
  `templates/workflows-js/*.js`, never the `.md` command/workflow templates that deploy
  to `commands/` and `gemini/workflows/`.

The record needed to attribute these files already exists. The previous install's
`.build_manifest.json` `output_mappings` holds, for every installed file, its canonical
path, the template that produced it, and the SHA-256 of what the build wrote
(`expected_output_hash`, CRLF-normalised). `build_phases_local_change` snapshots that
record before any phase writes, as the ACD-2100d-2-i local-change baseline.

Design, following ADR-041 (recomputed attribution at item granularity; non-attribution
means keep, and kept items are reported):
- **Candidates.** A path is a candidate only when the previous install recorded it
  (`output_mappings`), its recorded template is a `templates/commands/*.md` or
  `templates/workflows/*.md` template, and this run's source-derived phase mappings
  (`_compute_phase_mappings`, canonicalised through `shim_map`) no longer produce it.
  The recorded path must also sit inside a directory those mappings still write into. A
  record in another key spelling (an older manifest format, a pre-shim path, backslash
  separators) therefore can never make a still-shipped file look retired. Deriving the
  current set from sources rather than from the existence-gated manifest keeps
  `--dry-run` correct. `.claude/workflows/*.js` is out of scope. Those outputs
  are not in the phase mappings, so including them would misread every live workflow
  script as retired.
- **Per-file verdict.** Each physical copy (canonical path and its `.leafcutter/`
  pre-shim source, deduplicated through the symlink shim) is removed only when its
  current CRLF-normalised hash equals the recorded `expected_output_hash`
  (`package_produced`). A changed file (`adopter_owned`) or one that cannot be read, is a
  symlink, or is a directory (`unattributable`) is kept and named in the run output. A
  file the build never recorded is not a candidate at all. It is neither touched nor
  named, which is consistent with BP-1500b-4.
- **Wiring.** The step runs on every build, before shim install, so a copy-strategy
  shim cannot merge a retired file back. It lives in a new module, called from
  `build_main_helpers._run_shim_and_hook_install`, so it runs with `--no-shims` too.
  `scripts/build.py` and `scripts/build_helpers.py` are already over the file-size limit
  and are left untouched.

Relation to the AC store: the approved, not-yet-built BP-1500b family ("What you remove
from the source is gone from what you installed") specifies a general orphan sweep across
every family, with reporting and documentation obligations. This ticket is a narrow first
step for the command/workflow family only. It does not claim to satisfy BP-1500b or any
of its children, and it leaves their records untouched. Per user decision, it carries no
new ACs.

**Field note (2026-10-02).** New worktrees opened by single-ticket `/build-feature` runs
contained `.claude/commands/leafcutter.md` and `.gemini/workflows/leafcutter.md`.
`check-output-drift` then failed with `gaps=2` until both files were deleted by hand.
- **Where the files came from.** The likely source is the main checkout `leafcutter-ai/`.
  It is the only install here that still holds the old files: they are in its
  `.leafcutter/commands/`, `.claude/commands/` and `.gemini/workflows/`, and it has no
  `leafcutter-help.md`. Its `.build_manifest.json` still records both canonical paths, so by
  this ticket's design its next build should retire them. That was not verified here.
- **How they spread.** `build-feature.js` sets up a worktree by copying `.leafcutter`
  instead of building it, so anything the main checkout holds ends up in every new worktree.
  That part is covered by BO-4300a-1-ia and BO-4300c-1
  (EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace).

No new ticket was filed. The build side is covered by this ticket and the BP-1500b family.

## Done When
- [x] A test reproduces the defect first: a scratch adopter built with the hub template at its old name, then rebuilt after the rename, still holds the old `leafcutter.md` in all four installed locations. (Red on the previous build: all four copies left behind.)
- [x] After the fix, that rebuild (plain, and with `--clean`) removes the old file from `.leafcutter/commands/`, `.claude/commands/`, `.leafcutter/gemini/workflows/` and `.gemini/workflows/`, names each removal, and keeps `leafcutter-help.md`.
- [x] The deployed `check-output-drift` exits 0 on that upgraded adopter with no manual deletion.
- [x] An installed retired file whose content changed since install is kept byte-for-byte and named as kept. A command file the build never recorded is untouched and unnamed. `--dry-run` names what it would remove and removes nothing. No previous manifest means no removals.
- [x] Recorded outputs outside the command/workflow template family (for example `.claude/workflows/*.js`), and records in any other key spelling, are never removed by this step. Removing the directory guard makes the spelling tests fail, because the still-shipped file is deleted.

## Test Requirements

```yaml
tests:
  - name: test_retired_command_outputs_build
    file: unit_tests/build_guards/test_retired_command_outputs_build.py
    description: Real build.py subprocesses against a scratch adopter; build with the old hub template name, rebuild after the rename (plain and --clean), assert all four stale copies are gone and the deployed check-output-drift exits 0.
  - name: test_retired_command_outputs
    file: unit_tests/build_guards/test_retired_command_outputs.py
    description: The retirement step against synthetic installed trees; removal of package-produced copies, keeping and naming changed or unattributable ones, never touching unrecorded files or other families, dry-run, and the no-baseline case.
```

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [x] Write the build-subprocess reproduction and watch it fail on today's build.
- [x] Add `scripts/build_retired_outputs.py`: candidate selection, per-file verdict, removal and report.
- [x] Expose the previous-install baseline from `build_phases_local_change` and call the step from `build_main_helpers._run_shim_and_hook_install`.
- [x] Unit tests for the verdicts and guards; rerun the build, ownership, drift, collision and local-change suites and `build.py --validate-only`.
- [x] Update the rename ticket's upgrade note and the changelog entry.

## Known Limits
- A kept (adopter-edited) retired file is named only on the first build after the
  retirement. The next manifest no longer records it, so from then on it is simply an
  unrecorded file. `check-output-drift` keeps reporting it as a GAP, so it does not go
  silent.
- An install whose previous manifest already lost the record cannot be cleaned
  automatically. That happens after a build of the rename without this fix, which the
  shared PR prevents. Such a copy is left alone, per ADR-041's non-attribution rule.
- Other families (agents, hooks, skills, `.claude/workflows/*.js`) are still covered
  only by `--clean`'s ledger sweep or not at all. The BP-1500b family remains the place
  for the general sweep.
- On this Windows host, 41 existing BP-1500g ownership/shim tests fail with and without
  this change: they expect symlink shims, and without symlink privilege the build
  degrades to copy shims. The two symlink cases in `test_retired_command_outputs.py`
  skip here for the same reason and run where symlinks are available.

## Risk & Safety
- Touches money? No.
- Touches data? Yes. It deletes files in an adopter's installed tree. It is bounded to
  files the previous install recorded, from the command/workflow template family, whose
  content still matches byte-for-byte (after CRLF normalisation) what the package wrote.
  Anything else is kept and reported.
- Reversibility: a removed file was, by construction, identical to package output that
  the package no longer ships. Rebuilding with an older package restores it. Reverting
  the change restores today's behaviour.
