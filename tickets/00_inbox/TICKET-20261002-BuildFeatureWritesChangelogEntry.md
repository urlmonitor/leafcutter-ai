---
title: "/build-feature: a ticket drive writes the changelog entry that the required CI check demands"
status: todo
components:
  - build_orchestration
  - changelog
created: 2026-10-02
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: internal
tags:
  - build-feature
  - changelog
  - ci
last_updated: 2026-10-02
files_touched:
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/skills/build-single-ticket/SKILL.md
  - unit_tests/workflows/test_build_feature_changelog_step.py
agents:
  test-writer: needed
  python-coder: needed
  llm-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# /build-feature: a ticket drive writes the changelog entry that the required CI check demands

## Actor / Goal
In order to land a `/build-feature` pull request without manual work, we need the drive to
write the `changelogs/*.md` entry itself, before the commit it pushes, whenever the change
needs one. That way the required "Changelog entry present" check passes on the first push.

## Context
- **Observed 2026-10-02.** No single-ticket `/build-feature` run today wrote a
  `changelogs/*.md` entry. CI requires the "Changelog entry present" check
  (`.github/workflows/ci.yml`, `scripts/release/check_changelog_presence.py`) on every PR,
  so the orchestrator had to write an entry by hand for every PR.
- **Already known as KI-CL-002**
  (`docs/known-issues/changelog/open-high-ki-cl-002.md`, open, high, 3 occurrences in
  August). No ticket or AC routes it yet.
  - `build-feature.js` and its twin `build-ticket.js` contain no changelog step: neither
    `phaseOrder` mentions one.
  - `changelog-agent` is registered with `is_ticket_phase: false`, and
    `generate_ticket_from_ac.py` never adds it to an agents map.
  - The drive therefore reports success on a PR that cannot merge.
- **Other routes already do this**, so a working pattern exists:
  - `fast-lane-ship.js` has a Changelog phase (BO-2400f-4, KI-BO-001). It decides whether an
    entry is required with `compute_changelog_requirement()`
    (`scripts/build_orchestration/_fl_changelog.py`), which reads the CI checker's own
    `EXEMPT_PREFIXES`. It writes the entry through `scripts/changelog/emit_entry.py` and halts
    if no entry appears.
  - `quick-fix.js` has its own Changelog phase.
- **The skill describes a step the workflow never runs.**
  `templates/skills/build-single-ticket/SKILL.md` Step 4b describes writing a
  ticket-completion entry after the PR. `/build-feature` always runs the `build-feature`
  workflow (`templates/commands/build-feature.md`), which never reaches that step.
- **Choice of rule.** KI-CL-002 suggests gating on the ticket's `files_touched`. This ticket
  gates on the drive's actual diff instead, as the fast lane does. `files_touched` is a
  prediction, while CI judges the real diff, so only the diff-based rule cannot disagree
  with CI.
- **Related, not the same.** FIN-200 (todo) plans to write an entry during
  `finalize-feature`. See Open Questions.

## Scope
- After the last phase that produces content and before `commit`, add a changelog step to
  the single-ticket drive in `build-feature.js`, and the same step in `build-ticket.js`
  (TWIN).
- The step decides whether an entry is required from the drive's diff against
  `origin/main`, using the CI checker's own exempt-prefix rule as the fast lane does. It
  never keeps its own copy of that list.
- When an entry is required, the step writes it with `emit_entry.py` into the worktree's
  `changelogs/`, and the entry goes into the commit the pull-request phase pushes.
- A drive that needed an entry but did not get one is not reported as completed.
- Update `build-single-ticket` Step 4b so that exactly one place describes writing the
  entry, and that description matches what the workflow does.

## Out of Scope
- Epic drives: the epic PR's changelog entry. This ticket covers single-ticket drives only.
  Follow up from KI-CL-002 if epic PRs show the same gap.
- `finalize-feature`'s changelog behaviour (FIN-200).

## Acceptance Criteria
- [ ] AC-1: In a behavioural replay of `build-feature.js` for a single-ticket target, with
  stubbed agents, where the drive's diff includes a path outside `EXEMPT_PREFIXES` (for
  example `scripts/x.py`), a changelog step is dispatched after the last content-producing
  phase and before `commit`. Its entry file under `changelogs/` is among the files that the
  `commit` dispatch is asked to commit.
- [ ] AC-2: In the same replay, where the diff touches only exempt paths (`changelogs/`,
  `tickets/`, `docs/acceptance-criteria/`, `docs/known-issues/`), no changelog step is
  dispatched and no entry is written.
- [ ] AC-3: The requirement decision reads `EXEMPT_PREFIXES` from
  `check_changelog_presence.py` at run time. In a fixture where `scripts/` is added to that
  tuple, the AC-1 drive no longer dispatches the changelog step, and no other file was
  edited.
- [ ] AC-4: When an entry is required and the changelog step reports `ok` but no new
  `changelogs/*.md` file exists in the worktree, the drive's result has
  `ticket_completed: false` and names the changelog step in `outstanding_phases`. The
  `pull-request` phase is not dispatched.
- [ ] AC-5: The AC-1, AC-2 and AC-4 replays give the same outcomes against `build-ticket.js`.
- [ ] AC-6: Run against the AC-1 drive's resulting branch, `check_changelog_presence.py`
  exits 0. The entry written by the drive has the same frontmatter shape as entries written
  by `/changelog` and the fast lane, because all of them write through `emit_entry.py`.

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
  - name: test_build_feature_changelog_step
    file: unit_tests/workflows/test_build_feature_changelog_step.py
    description: Behavioural replay of build-feature.js and build-ticket.js for a single-ticket target with stubbed agents and a real temporary git repository. It covers: a releasable diff dispatches the changelog step before commit and the entry is committed; an exempt-only diff dispatches nothing; the exempt list is read from the CI checker at run time; an ok reply with no entry on disk leaves the ticket not completed and the PR undispatched; check_changelog_presence.py passes on the resulting branch.
```

## Open Questions
- FIN-200 has `finalize-feature` write an entry before merge. If both land, finalize must
  not add a second entry for work that already has one. Decide when FIN-200 is built.

## Comments

## Implementation Tasks
- [ ] Write the replay test against today's workflows and watch AC-1 and AC-4 fail.
- [ ] Add the changelog step to `build-feature.js` and `build-ticket.js`, reusing the fast
  lane's requirement and payload helpers where they fit.
- [ ] Make a required-but-missing entry leave the ticket not completed (AC-4).
- [ ] Update `build-single-ticket` Step 4b to match.

## Risk & Safety
- Touches money? No.
- Touches data? Writes one new file under `changelogs/` per drive that needs one.
- Reversibility: revert the workflow change. Entries already written are ordinary files.
