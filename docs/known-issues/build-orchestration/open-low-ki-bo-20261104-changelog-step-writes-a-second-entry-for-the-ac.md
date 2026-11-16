---
title: "KI-BO-20261104-changelog-step-writes-a-second-entry-for-the-ac — the fast lane's changelog step always emits a new entry when the change touches a releasable file, even when the change already carries an entry for the AC, so the AC ends up with two"
description: "low — on 2026-11-04 (run wf_39ec449a-05e, TQ-200d-2-iii) the coder had already written a changelogs/ entry naming the AC. The changelog step then emitted a second one, titled from the AC's title, and its own message noted the existing entry. The AC's docs test (exactly one entry naming the AC) failed. fast-lane-ship.js decides the requirement from releasable paths only (:1610-1614) and never asks whether an entry is already in the change."
type: reference
category: reference
status: active
created: '2026-11-04'
last_updated: '2026-11-04'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261009-fast-lane-changelog-publishes-absolute-local-paths.md
---

# KI-BO-20261104-changelog-step-writes-a-second-entry-for-the-ac — the changelog step writes a second entry when one for the AC already exists

> Filed 2026-11-04. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. The duplicate is loud: here the AC's own test caught it. It is easy to fix by
  hand (delete one file). But the lane leaves the change in a state that fails a test, and a
  change without such a test merges with two entries for one change.
- **Status:** open. No AC.
- **Occurrences:** 1 (run `wf_39ec449a-05e`, `TQ-200d-2-iii`, 2026-11-04; the change became
  PR #1397).
- **First seen:** 2026-11-04 · **Last seen:** 2026-11-04
- **Where** (at `origin/main` `72ddec43f`):
  - `templates/workflows-js/fast-lane-ship.js:1610-1614` — `filesModified` is filtered by
    `CHANGELOG_EXEMPT_PREFIXES` (`:375`, which includes `changelogs/`), and
    `changelogRequired` is `releasablePaths.length > 0`. An entry the coder already wrote is just
    dropped as exempt. It is never counted as meeting the requirement.
  - `:1618-1650` — the changelog dispatch always runs `changelog_payload` and `emit_entry.py`
    when required. The prompt has no step that looks for an existing entry for the AC.
  - `scripts/build_orchestration/_fl_changelog.py:90` — `build_changelog_payload()` takes the
    entry title from the target AC's `title`, not its id, so the new file's slug does not match
    an entry named after the id.
  - `scripts/changelog/emit_entry.py:204` — `generate_filename()` avoids a filename collision by
    adding `-2`, `-3`. It does not look for another entry about the same AC.

## Symptom

The coder wrote `changelogs/2026-11-04-1200-tq-200d-2-iii-<slug>.md` as part of its change. The
changelog step then emitted `changelogs/2026-11-04-0809-a-database-test-<slug>.md` for the same
AC. The step's own `message` said an entry for the AC already existed, and it still reported
`entry_added: true`. The AC's docs test asserts exactly one changelog entry names the AC, and it
failed with two.

## Mechanism

1. The requirement is computed from paths. "Touches a releasable file" means "owes an entry",
   whatever else the change contains.
2. The coder is not told the changelog step will write the entry, and the step is not told the
   coder may have written one. Both acted correctly on what they were told.
3. The step's success check is "an added `changelogs/*.md` file is present". The coder's entry
   would already pass that check, so the step cannot detect a duplicate this way.

## Detection

`git diff --name-only origin/main... -- changelogs/` on the lane's branch lists two or more added
files, and more than one of them names the same AC id in its body or filename.

## Workaround

Delete the entry the step emitted (or the coder's, whichever is worse) before the commit, or in a
follow-up commit on the PR branch.

## Fix direction

1. Before dispatching the changelog agent, check whether `filesModified` already contains an added
   `changelogs/*.md` that names the target AC. If it does, skip the emit and report
   `entry_added: true` with that path. This check belongs in Python next to
   `compute_changelog_requirement()`, not in the prompt.
2. Or tell the coder in its prompt that the lane writes the changelog entry and the coder must
   not.
3. Size ratchet: `fast-lane-ship.js` is over the file-size limit
   (`KI-BO-20260930-fast-lane-ship-is-649-lines-over-and-cannot-grow`); prefer the Python side.

**Pattern:** two steps that each own "make sure X exists", where neither is told about the other.
