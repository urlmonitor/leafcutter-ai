---
allowed-tools: Bash(git *), Read, Agent
description: Knowledge items and operational notes for the /build-feature entry point.
  Documents failure modes, detection methods, and recovery procedures observed during
  epic drives. Read by epic-supervisor and worktree-agent to understand edge cases
  in the worktree-creation + supervisor-dispatch pipeline.
name: build-feature-ops-notes
internal: true
---

# build-feature-ops-notes — Knowledge Items

This skill file collects operational knowledge items (KIs) discovered during
real epic drives. It is the companion to `.claude/commands/build-feature.md`
(the executable workflow) and `.claude/skills/building-epics/SKILL.md` (the
supervisor runbook). The KIs here document **failure modes and remedies** — not
enforcement rules. Enforcement rules live in `build-feature.md` Step A.

---

## Knowledge Items

### KI-1: Stray-on-main commits cause epic folder to be absent from new worktree

**Root cause.** When `/build-feature` is invoked, `worktree-agent` creates a
fresh worktree from `origin/main`. If the epic folder (e.g.
`tickets/00_inbox/epics/EPIC-Foo/`) was committed to local `main` but those
commits were **not yet pushed to `origin/main`**, the new worktree will not
contain the epic files. The supervisor is then dispatched into an empty context
and cannot find the tickets it is supposed to drive.

This happened during EPIC-PortableWorkflowHardening: the epic folder was
committed as local `main` commit `6b4ee0ae` but had not been pushed. The
worktree created by `/build-feature` was based on `origin/main` and did not
contain the epic. See `docs/retrospectives/EPIC-PortableWorkflowHardening.md`
§Friction Points (item 1) for the full incident record.

**Detection.** After `worktree-agent` returns:

```bash
ls "<WORKTREE_PATH>/<EPIC_FOLDER_REPO_RELATIVE>/"
```

If the directory is empty or absent, the epic folder is not reachable from the
worktree HEAD. Cross-check with:

```bash
git log --oneline origin/main..main
```

on the **host repo** (not the worktree). Any commit listed here is on local
`main` but not yet pushed — one of these is likely the commit containing the
epic folder.

**Remedy.**

1. Identify the missing commit SHA from the `git log --oneline origin/main..main`
   output above.
2. Cherry-pick the commit onto the epic branch (run inside the worktree):

   ```bash
   git -C "$WORKTREE_PATH" cherry-pick <SHA>
   ```

3. Verify the epic folder is now present:

   ```bash
   ls "$WORKTREE_PATH/$EPIC_FOLDER_REPO_RELATIVE/Master_Plan.md"
   ```

4. If still absent after the cherry-pick (e.g. multiple missing commits), repeat
   steps 1–3 for each missing SHA in chronological order.
5. If still absent after all cherry-picks, abort `/build-feature` with a clear
   error — do **not** dispatch the supervisor on an empty epic.

**Prevention.** Push local `main` to `origin/main` before invoking
`/build-feature`. The automated Reachability Check (codified in
`.claude/commands/build-feature.md` Step A step 6) will surface this
condition at dispatch time and block the supervisor dispatch until resolved.

---

## KI-2: Recovering from supervisor stream-watchdog timeout

### Detection

The epic-supervisor has stalled when the task notification body contains one of:

- `"stalled: no progress for 600s"`
- `"stream watchdog did not recover"`
- `"stream-watchdog timeout"`

The agent thread is dead. No further output will appear. The worktree filesystem
may contain partial work (uncommitted edits, a ticket file mid-sign-off, a
dangling `.epic-commit-lock`).

### Disk-state capture checklist (run before respawn)

Run these commands from the **host repo root** (not the worktree):

```bash
WORKTREE="C:/path/to/EPIC-Name"   # set to your worktree path

# 1. What branch + HEAD is the worktree on?
git -C "$WORKTREE" branch --show-current
git -C "$WORKTREE" log --oneline -5

# 2. What commits exist on the epic branch vs main?
git -C "$WORKTREE" log --oneline origin/main..HEAD

# 3. What files changed but are uncommitted?
git -C "$WORKTREE" status --short
git -C "$WORKTREE" diff --stat

# 4. Which tickets are in inbox / todo / done?
ls "$WORKTREE/tickets/00_inbox/epics/EPIC-Name/"
ls "$WORKTREE/tickets/01_todo/EPIC-Name/" 2>/dev/null
ls "$WORKTREE/tickets/99_done/EPIC-Name/" 2>/dev/null

# 5. Is there a stale commit-phase lock?
cat "$WORKTREE/.epic-commit-lock" 2>/dev/null && echo "LOCK PRESENT" || echo "no lock"

# 6. Full uncommitted diff (paste into resume prompt)
git -C "$WORKTREE" diff
```

### Resume-prompt structure

A resume prompt sent to a new epic-supervisor invocation must contain these
four blocks:

1. **Ground-truth done-list** — list every ticket file in `done/` by name,
   confirmed from disk. One line per ticket.
2. **Partial-work-by-ticket** — for each in-progress ticket, paste the
   `git diff` hunks for that ticket's target files. If the diff is large,
   truncate to the first 100 lines and note the truncation.
3. **Standing-rules restatement** — quote the exact worktree path, epic
   branch name, and any mid-drive user instructions (e.g. "only kill idle
   processes").
4. **Return contract** — restate the expected output format
   (`## Epic Complete` or `## Epic Paused` payload) so the new supervisor
   knows what to emit when it finishes.

### Worked skeleton resume prompt

```
## Epic supervisor resume — EPIC-Name

**Worktree**: C:/path/to/EPIC-Name
**Branch**: EPIC-Name
**Date**: YYYY-MM-DD

### Ground-truth done-list (confirmed from disk)
- 01_first_ticket.md — done (in tickets/99_done/EPIC-Name/done/)
- 02_second_ticket.md — done

### Partial work (mid-stall diff summary)
Ticket 03 was in progress. The documentation-expert wrote the new section
to .claude/skills/build-feature-ops-notes/SKILL.md but had not yet signed off.
Uncommitted diff:

<paste first 100 lines of git diff here>

### Standing rules
- File-touch sets are disjoint; all remaining tickets are parallel-safe.
- Only kill idle orphan processes (parent dead + CPU near zero).
- Commit-phase lock was not present at capture time.

### Return contract
Emit the standard `## Epic Complete: EPIC-Name` payload once all tickets
are signed off, then run the post-completion chain.
```

---

## KI-3: `.leafcutter/` absent from new worktree — named workflow resolution fails

**Root cause.** `.leafcutter/` is a build output directory generated by
`scripts/build.py` and is listed in `.gitignore`. It is therefore never present
in a freshly checked-out branch. The `Workflow` tool resolves named workflows
from `.leafcutter/.claude/workflows/` at runtime — if that directory does not
exist, calls such as `workflow("build-epic")` fail silently or raise a resolution
error immediately after worktree creation.

**Detection.**

```bash
ls "<WORKTREE_PATH>/.leafcutter/.claude/workflows/"
```

If the command returns `No such file or directory`, the build step was skipped or
failed. Cross-check by looking for the build script:

```bash
ls "<MAIN_REPO>/scripts/build.py"
```

If the script exists but the `.leafcutter/` directory is absent, `build.py` was
not invoked after worktree creation.

**Remedy.** Run `build.py` manually inside the worktree:

```bash
python scripts/build.py --target-dir .
```

(Run from `<WORKTREE_PATH>` — the `--target-dir .` argument tells build.py to
write its outputs relative to the current directory.)

**Prevention.** `_bootstrap()` in `templates/scripts/setup_ticket_worktree.py`
now invokes `build.py` automatically after `poetry install --no-root`. Projects
that do not ship `scripts/build.py` receive a single `WARNING:` line to stderr
and continue; no error is raised.

---

## KI-4: `/finalize-feature` does NOT `git push` — unpushed local commits are dropped from the PR merge

**Root cause.** `finalize-feature.js` merges the epic PR via `gh pr merge` against the
**origin** PR head. It contains no `git push` anywhere. Any commit made locally on the
feature branch but not pushed to origin — e.g. a post-review fix committed with the
mistaken assumption that "finalize will handle the push" — is silently excluded from the
merge to `main`.

Observed during EPIC-TrustworthyTestGate finalization (2026-07-08): a code-review fix
commit (`2a377f91`) was committed locally but unpushed; had finalize run as-is, the merge
would have landed the pre-fix tree on `main` and dropped the fix.

**Detection.** Before invoking `/finalize-feature` (or `gh pr merge`), confirm origin and
local HEAD match:

```bash
git -C "<WORKTREE>" log HEAD -1 --format="%H"
git -C "<WORKTREE>" log "origin/<branch>" -1 --format="%H"
```

Different SHAs (local ahead) means unpushed commits the merge will drop.

**Remedy / prevention.** `git -C "<WORKTREE>" push origin <branch>` before finalize, then
re-verify the two SHAs match. The `pull-request` phase pushes per-ticket during a normal
drive, so this bites specifically for commits made *after* the last ticket signed off
(review fixes, manual edits at finalize time).

---

## KI-5: `/finalize-feature` resolves its target from a plain-STRING arg, not an object

**Root cause.** `finalize-feature.js` reads the target branch only when
`typeof args === 'string'`. Passing an object (`{branch: "EPIC-Name"}`) leaves the string
empty, so it falls back to CWD-based detection and — when the session CWD is the workspace
root or `main` — errors: `"must be run from a feature branch (detected branch: main ...)"`.

**Remedy.** Invoke with the epic name as a bare string:

- Right: `/finalize-feature EPIC-Name`  •  `Workflow("finalize-feature", "EPIC-Name")`
- Wrong: `Workflow("finalize-feature", { branch: "EPIC-Name" })`

(The slash-command doc's `{ branch: ... }` example is misleading; the script wants a
string.) Observed EPIC-TrustworthyTestGate finalization, 2026-07-08.

---

## KI-6: Validate a stale feature branch with a full-suite baseline regression diff before merge

**Root cause.** A feature branch far behind `origin/main` (this epic was 115 commits
behind) can integrate cleanly at the git level yet break unrelated tests once merged. A
globally-registered artifact is the classic trap: EPIC-TrustworthyTestGate added a root
`conftest.py` that shadowed `tests/conftest.py`, breaking an unrelated test's
`from conftest import load_fixture`. Per-ticket tests and the epic's own suite were green;
only a cross-suite run against a baseline surfaced it.

**Detection / remedy.** After merging `origin/main` into the feature branch, diff a
full-suite run against an `origin/main` baseline; treat only *new* failures/errors as
regressions (this repo has a known pre-existing failing set):

```bash
# Baseline (detached worktree at origin/main):
git -C "<WORKTREE>" worktree add --detach /tmp/base origin/main
python -m pytest /tmp/base/tests /tmp/base/unit_tests -q --continue-on-collection-errors
# Branch (origin/main already merged in):
python -m pytest tests/ unit_tests/ -q --continue-on-collection-errors
# Compare the FAILED/ERROR node-id sets; branch-only entries are the regressions.
```

Run `build.py` in each tree first so deploy-dependent tests don't read as false
regressions. (Source: EPIC-TrustworthyTestGate finalization, 2026-07-08.)

---

## KI-7: Audit CI pytest flags for interactions that defeat a shipped plugin

**Root cause.** When an epic ships a pytest plugin loaded via `pytest.ini addopts`, the
plugin's guarantee can be silently defeated by an unrelated flag in the CI invocation.
EPIC-TrustworthyTestGate shipped collection-error isolation
(`--continue-on-collection-errors`) but `.github/workflows/ci.yml` ran pytest with `-x`,
which aborts at the first failure — so CI never realised the isolation guarantee. The
epic's own subprocess tests didn't pass `-x` and were green (finding H-1).

**Detection / prevention.** Before declaring such an epic done, read the pytest command in
`.github/workflows/ci.yml` and confirm no flag contradicts the plugin's stated behavior
(`-x`/`--exitfirst` vs isolation; `-p no:<plugin>`). Ship a regression guard test that
asserts the CI command does NOT contain the defeating flag (see
`tests/testing_quality/test_ci_invocation_isolation.py`). (Source: EPIC-TrustworthyTestGate
H-1 fix, commit `2a377f91`, 2026-07-08.)

---

## References

- `.claude/commands/build-feature.md` — executable workflow; Step A step 6
  is the automated reachability check that operationalises KI-1.
- `.claude/skills/building-epics/SKILL.md` — supervisor runbook; §1.1 step 1
  documents the per-pass ticket scan that picks up mid-drive additions.
- `docs/retrospectives/EPIC-PortableWorkflowHardening.md` — source of KI-1.
- `docs/retrospectives/EPIC-ArchitectureDocsEnforcement.md` — source of KI-2
  (stream-watchdog timeout incident during ticket 03 of that epic).
- `docs/retrospectives/EPIC-TrustworthyTestGate.md` — source of KI-4 through KI-7
  (finalize no-push, string-arg resolution, stale-branch baseline diff, CI flag audit).
