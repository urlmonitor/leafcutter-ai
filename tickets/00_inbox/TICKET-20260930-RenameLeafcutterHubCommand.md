---
title: "Rename the /leafcutter knowledge-hub command to /leafcutter-help"
status: in_progress
components:
  - onboarding
  - build_pipeline
created: 2026-09-30
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: prompt
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - rename
  - slash-command
  - naming
files_touched:
  - templates/workflows/leafcutter-help.md
  - templates/workflows/leafcutter.md
  - scripts/leafcutter_inventory.py
  - templates/scripts/leafcutter_inventory.py
  - tickets/00_inbox/TICKET-20260930-RenameLeafcutterHubCommand.md
  - changelogs/2026-09-30-2111-the-package-knowledge-hub-command-is-now-leafcutter-help.md
last_updated: 2026-09-30
---

# Rename the /leafcutter knowledge-hub command to /leafcutter-help

## Actor / Goal
In order to give the Decision Kernel's new runtime skill the name `/leafcutter`, we
need to move the shipped package knowledge-hub command off that name, so that an
adopter's `/leafcutter` resolves to exactly one thing once the kernel skill ships.

## Context
The knowledge hub is the workflow template `templates/workflows/leafcutter.md`.
`build_workflows()` (`scripts/build_phases_workflows.py`) copies every
`templates/workflows/*.md` into `<output_root>/commands/` (and
`<output_root>/gemini/workflows/` for antigravity), and the shim installs it as
`.claude/commands/leafcutter.md`, i.e. the `/leafcutter` slash command.

The Decision Kernel's `/leafcutter` skill is being built on a separate branch. The
user approved this rename as its own small ticket, separate from the kernel work.

New name: `leafcutter-help`. It follows the kebab-case naming of the other
workflow templates (`pick-next-ticket`, `feedback-report`, `project-report`), keeps
the package name as its prefix so it still sorts beside the kernel skill, and
collides with no existing template, skill, agent or registry entry.

Reference sweep (grep for `/leafcutter` not followed by a path character,
`leafcutter.md`, and the bare command name in JSON/YAML/Python): the only
references to the command are the template itself and the module docstring of
`leafcutter_inventory.py` (package copy and deployed copy, kept identical). No
registry (`agent_registry.json`, `skill_registry.json`, `paths.json`,
`commit_guardian.json`), `skills_config` default/schema, package boundary file,
README/SETUP/BOOTSTRAP, how-to, command map, glossary, agent card or unit test
names the command. Workflow templates are not a watched package registry, so the
rename adds no registry entry.

No AC-store records: per user decision this rename carries no new acceptance
criteria.

## Done When
- [x] `templates/workflows/leafcutter.md` no longer exists and `templates/workflows/leafcutter-help.md` carries the unchanged hub content, with its heading and "Responding to" section naming `/leafcutter-help`.
- [x] Both copies of `leafcutter_inventory.py` name `/leafcutter-help` and stay byte-identical.
- [x] A build deploys `commands/leafcutter-help.md` and no new `commands/leafcutter.md`.
- [x] Existing build, deploy-collision and reachability unit tests still pass.

## Test Requirements

```yaml
tests: []
```

Rationale: a file rename plus two docstring lines. No behaviour changes, and no
existing test names the command. Existing build/collision/reachability suites are
re-run as regression checks.

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [x] `git mv templates/workflows/leafcutter.md templates/workflows/leafcutter-help.md`; update the two in-body `/leafcutter` mentions.
- [x] Update the `/leafcutter` mention in both `leafcutter_inventory.py` docstrings.
- [x] Build into a scratch consumer target before and after the rename to confirm what an upgrade leaves behind.
- [x] Run the relevant unit tests and `build.py --validate-only`.

## Upgrade Note (stale installed copy)
The build has no mechanism that removes a renamed or retired workflow template's
installed copy. Verified by building a scratch consumer target before and after this
rename: a plain build and a `--clean` build both leave the old `leafcutter.md` in
`.leafcutter/commands/`, `.claude/commands/` and `.gemini/workflows/` next to the new
`leafcutter-help.md`. `_cleanup_stale_paths` only handles pre-consolidation
directories; `clean_stale_artifacts` only sweeps `.claude/{agents,skills,hooks,workflows}`,
and its source manifest lists only `templates/workflows-js/*.js`, not the `.md`
workflow templates deployed to `commands/`. Adopters upgrading must delete the old
`leafcutter.md` by hand until a follow-up ticket teaches the build to retire it.

The stale copy also blocks commits. In this ticket's own worktree,
`check-output-drift` reported `GAP .claude/commands/leafcutter.md` and
`GAP .gemini/workflows/leafcutter.md` and exited 2 until those gitignored installed
copies (plus their `.leafcutter/` sources) were deleted by hand. Rerunning `build.py`,
as the hook suggests, does not help because the template no longer exists.

## Risk & Safety
- Touches money? No.
- Touches data? No. It renames one shipped prompt file.
- Reversibility: fully reversible by renaming back. Adopters who typed `/leafcutter`
  for the hub need `/leafcutter-help` from now on (see the changelog entry).
