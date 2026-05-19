---
allowed-tools: Bash(git *), Read, Agent
description: Knowledge items and operational notes for the /build-feature entry point.
  Documents failure modes, detection methods, and recovery procedures observed during
  epic drives. Read by epic-supervisor and worktree-agent to understand edge cases
  in the worktree-creation + supervisor-dispatch pipeline.
internal: true
name: build-feature-ops-notes
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

## References

- `.claude/commands/build-feature.md` — executable workflow; Step A step 6
  is the automated reachability check that operationalises KI-1.
- `.claude/skills/building-epics/SKILL.md` — supervisor runbook; §1.1 step 1
  documents the per-pass ticket scan that picks up mid-drive additions.
- `docs/retrospectives/EPIC-PortableWorkflowHardening.md` — source of KI-1.
- `docs/retrospectives/EPIC-ArchitectureDocsEnforcement.md` — source of KI-2
  (stream-watchdog timeout incident during ticket 03 of that epic).
