---
name: build-single-ticket
description: Drive a single standalone ticket (not part of an epic) through its phase agents. Moves the ticket file from 00_inbox → 01_todo, creates an isolated worktree, dispatches ticket-supervisor, and on success moves the ticket to 99_done. Invoked by /build-feature when its argument resolves to a `.md` file outside an `EPIC-*/` folder.
---

# build-single-ticket

This skill is the single-ticket analogue of `/build-feature`'s epic
flow. It owns the ticket-file lifecycle (inbox → todo → done) and the
worktree dance; everything *inside* the ticket (phase agents,
sign-offs, commit-phase lock, failure adjudication) belongs to
`ticket-supervisor` and the runbook in
`.claude/skills/building-epics/SKILL.md`.

## Input

`$ARGUMENTS` is one absolute, repo-relative, or `./`-prefixed path to
a single ticket markdown file. The file MUST live directly under
`tickets/00_inbox/` or `tickets/01_todo/` and MUST NOT live inside any
`EPIC-*/` subfolder — those are driven by the epic supervisor.

If `$ARGUMENTS` is empty, print usage and exit non-zero. Do not spawn
`ticket-supervisor`.

## Step 1 — Validate the ticket file

1. Resolve `$ARGUMENTS` to an absolute path. Call it `TICKET_PATH`.
2. Confirm the file exists and ends in `.md`.
3. Confirm its parent directory is exactly `tickets/00_inbox` or
   `tickets/01_todo` (no `EPIC-*` segment between).
4. If under `tickets/99_done/`, refuse with:
   `"Ticket is already in 99_done/. Move it back to 01_todo/ manually
   to re-drive."` and exit non-zero.
5. Read the frontmatter. Confirm it has an `agents:` map with at least
   one entry. If empty, refuse with:
   `"Ticket has no `agents:` map — re-create it via /create-ticket so
   business-analyst + refinement populate the map before driving."`
   Exit non-zero. (This guards against the `feedback_use_create_ticket_agent.md`
   trap codified in user-memory.)

## Step 2 — Set up the worktree and promote the ticket (mandatory, blocking)

Per the project convention (`feedback_epic_worktree.md`): standalone tickets
large enough to invoke `/build-feature` should run in their own worktree,
NEVER on `main`. The bootstrap recipe is implemented in
`scripts/setup_ticket_worktree.py` — do not re-implement inline steps here.

Call the script via a Bash tool call:

```bash
python scripts/setup_ticket_worktree.py setup-ticket "$TICKET_PATH"
```

Parse the JSON output (single line on stdout):

- `worktree_path` → `WORKTREE_PATH`
- `branch` → `BRANCH`
- `ticket_path_new` → `TICKET_PATH` (updated location inside the worktree)

On non-zero exit, surface stderr verbatim and stop — do NOT fall through to
running on `main`. Silent-main-branch execution is the exact bug the worktree
convention exists to prevent.

Do NOT dispatch `worktree-agent` as a separate Agent tool call.
Do NOT run a separate `git mv` shell step.
The script handles both concerns atomically and idempotently.

## Step 3 — Pre-move the ticket to `99_done/` (inside the worktree)

After `setup_ticket_worktree.py` returns, the ticket file lives at
`tickets/01_todo/<basename>` inside the worktree. Move it directly to
`tickets/99_done/<basename>` BEFORE dispatching `ticket-supervisor`:

```bash
git -C "$WORKTREE_PATH" mv \
    "tickets/01_todo/<basename>" \
    "tickets/99_done/<basename>"
```

Update the path you pass to `ticket-supervisor` so it reads / edits the
file at its new `99_done/` location.

**Why pre-move instead of post-move.** The `commit` phase agent stages
every uncommitted worktree change (including the rename + every sign-off
edit phase agents wrote during the drive). The `pull-request` phase then
opens a PR whose diff contains the move alongside the implementation —
the reviewer sees the completed ticket file in the same PR as the code.
Moving the ticket *after* `pull-request` opens (the old behaviour) leaves
a stray `chore(tickets): mark <basename> done` commit on the branch that
never makes it into the PR and has to be cleaned up separately.

**Why the move is safe before work is done.** `ticket-supervisor` works
on whatever ticket path it is given — it does not check directory name.
Phase agents (architect-review, python-coder, …) write sign-offs and
comments to the file at the path they receive. The `99_done/` location
is a filesystem fact, not a state machine: the `## Sign-offs` checklist
and `Comments` section are still the source of truth for "done-ness",
and the parity guard in Step 5 enforces that they are consistent before
this skill returns success.

If the worktree is dirty for the ticket file path at this point
(uncommitted edits from a previous attempt), abort with a clear error —
do NOT silently overwrite.

## Step 4 — Dispatch `ticket-supervisor`

Dispatch the `ticket-supervisor` agent via the `Agent` tool with input:

```
{
  "ticket_path":   "<absolute path inside the worktree>",
  "worktree_path": "<WORKTREE_PATH>",
  "branch":        "<BRANCH>",
  "via":           "/build-feature (build-single-ticket)"
}
```

The `via` marker satisfies `ticket-supervisor`'s "refuse direct user
invocation" rule — this skill is its sanctioned entry path for
standalone tickets, analogous to how `epic-supervisor` is the
sanctioned entry for epic tickets.

`ticket-supervisor` walks the phase agents per
`.claude/skills/building-epics/SKILL.md` §2 (the five-step ticket
loop), holding the worktree-root commit-phase lock per §5 around
`commit` and `pull-request`.

## Step 5 — Verify done state (post-supervisor)

When `ticket-supervisor` returns `{"status": "done"}`, the ticket file
is already at `tickets/99_done/<basename>` (placed there by Step 3) and
the rename + all sign-off edits are already in the PR opened by the
`pull-request` phase. This skill performs no further file moves on the
success path — Step 5 is purely a verification gate.

**Preflight guard (parity + clean working tree):**

```bash
python scripts/commit_guardian/check_ticket_signoff_parity.py \
    --enforce "<current-ticket-path>"
```

```bash
git status --porcelain "<current-ticket-path>"
```

Run the worktree-age check (defence-in-depth; warning only, exit 0):

```bash
BEHIND=$(git rev-list --count HEAD..main 2>/dev/null || echo 0)
if [ "$BEHIND" -gt 0 ]; then
  TICKET_CREATION_SHA=$(git log --diff-filter=A --format=%H -- "<ticket_path>" | tail -1)
  if [ -n "$TICKET_CREATION_SHA" ] && git merge-base --is-ancestor "$TICKET_CREATION_SHA" HEAD 2>/dev/null; then
    echo "INFO: worktree contains ticket-creation commit ($TICKET_CREATION_SHA); the $BEHIND commit(s) on main are unrelated activity (likely concurrent merges during the drive)."
  elif [ -n "$TICKET_CREATION_SHA" ]; then
    echo "WARNING: worktree HEAD does NOT contain the ticket-creation commit at $TICKET_CREATION_SHA. The worktree may have been bootstrapped from a stale base ref. Verify ticket content is current and consider rebasing."
  else
    echo "WARNING: worktree branch is $BEHIND commit(s) behind local main."
    echo "Could not locate ticket-creation commit in git history — unable to determine reachability."
    echo "The worktree may have been bootstrapped from origin/main before a local create-ticket commit was made. Verify ticket content is current."
  fi
fi
```

This check distinguishes two cases when `BEHIND > 0`:

- **Case A (real defect)**: the ticket-creation commit is NOT in the worktree's
  ancestry (`git merge-base --is-ancestor` returns false). The worktree was
  bootstrapped from a stale base ref and may be missing local changes. The check
  emits a `WARNING` directing the operator to verify ticket content and consider
  rebasing.
- **Case B (benign concurrency)**: the ticket-creation commit IS an ancestor of
  `HEAD`. `main` moved forward while the drive was running (unrelated merges).
  The check emits an `INFO` line so the operator can confirm the drive is clean
  without alarm.

If the ticket-creation commit cannot be located in git history (edge case — e.g.
the ticket was not committed before the worktree was created), the check degrades
to the original generic `WARNING` text.

The check is advisory only and exits 0 in all branches — it never blocks the
drive.

**Residual triage rule**: if the uncommitted delta is in a file that the
current ticket already touches (e.g. the same agent instruction file that
was the ticket's primary edit target), prefer fixing it in-scope rather than
proposing a follow-up ticket. The marginal cost of the in-scope fix is near
zero. Reserve follow-up tickets for residuals that are out-of-scope or
require a separate design decision.

Lesson: TICKET-20260513-Fix_PullRequest_Agent_Dangling_Signoffs had a 3-line
supervisor `status: done` residual in `.claude/agents/pull-request.md` — the
same file the ticket had already edited. Punting it would have opened a
second ticket for a trivial in-scope change.

**Step 5c — Emit feedback on residuals (best-effort)**

When Step 5 preflight detects an in-scope uncommitted delta and commits it:

1. Determine the category:
   - `subagent-quality` if the residual is a sign-off frontmatter change or a
     `## Sign-offs` / `## Comments` body edit attributable to the `commit` or
     `pull-request` phase agents.
   - `tooling-issue` for any other in-scope residual.

2. Run (best-effort — log stderr and continue on any error):
   ```bash
   python leafcutter/scripts/feedback/submit_feedback.py \
     --ticket "<ticket_path>" \
     --phase ticket-supervisor \
     --category <category> \
     --tags "dangling-signoff,step5-residual" \
     --note "Step 5 in-scope residual committed: <brief description of the delta>"
   ```

3. If `submit_feedback.py` exits non-zero or raises an exception, print the
   error to stderr and continue — do NOT fail the drive.

If either command indicates a problem (non-zero exit from the parity
guard, or the porcelain status shows uncommitted sign-off deltas), return
a `failed` payload to `/build-feature`:

```
{
  "status": "failed",
  "payload": {
    "ticket_path":           "<absolute path>",
    "phase":                 "supervisor",
    "blocker_summary":       "sign-offs missing or uncommitted after supervisor returned done",
    "suggested_remediation": "Check the ticket file for missing sign-offs; the phase agents may not have written their edits to disk. Re-run the drive or manually verify and commit the sign-offs."
  }
}
```

### Step 5b — Changelog entry (success path, mirrors epic-supervisor Step 2)

Once the parity guard passes, write a per-file changelog entry capturing the
ticket completion. This mirrors `epic-supervisor` Step 2 (the
`type=epic_completion` write) and uses the same canonical helper
(`leafcutter/scripts/changelog/emit_entry.py`) so all three call
sites — standalone `/changelog`, epic post-completion, and single-ticket
post-completion — share one write path.

1. Read the ticket file's YAML frontmatter (the file is at its `99_done/`
   path). Extract:
   - `title` → entry `title` (suffix with " complete" to mirror epic
     wording, e.g. `"<frontmatter title> complete"`).
   - `components` → entry `components` (use directly; if missing, fall back
     to the top-level package names touched in `files_touched`).
2. Capture the ticket basename (without `.md` suffix) → entry `ticket` field.
3. Collect commits with:

   ```bash
   git -C "$WORKTREE_PATH" log --oneline --no-pager origin/main...HEAD
   ```

   Extract short SHAs into the `commits` list (cap at 20). If the range is
   empty, omit `commits`.
4. If the `pull-request` phase returned a PR number/URL via the supervisor
   payload, record it as `pr` (integer). Otherwise omit `pr`.
5. Build the payload (use `date "+%Y-%m-%d"` / `date "+%H:%M"` for current
   timestamps; project current date is available via `Today's date` in
   conversation context):

   ```bash
   python leafcutter/scripts/changelog/emit_entry.py \
     --changelog-dir "changelogs/" \
     --payload '{
       "title": "<frontmatter title> complete",
       "date": "YYYY-MM-DD",
       "time": "HH:MM",
       "type": "ticket_completion",
       "ticket": "<ticket basename without .md>",
       "components": ["<component1>", "..."],
       "description": "<1-3 line summary; pull from ticket Goal section>",
       "commits": ["<sha1>", "..."],
       "pr": <PR-number or omit>
     }'
   ```

6. Print the path of the written changelog file to the user.
7. Commit and push the new entry so it lands on the PR branch the
   `pull-request` phase already opened:

   ```bash
   git -C "$WORKTREE_PATH" add "changelogs/"
   git -C "$WORKTREE_PATH" commit -m "chore(changelog): add ticket-completion entry for <ticket basename>"
   git -C "$WORKTREE_PATH" push origin "$BRANCH"
   ```

   Per `feedback_background_commit_silent_kill.md` — run the commit
   synchronously and verify `HEAD` advanced via `git log -1` before pushing.

**Failure tolerance.** If `emit_entry.py` fails (e.g. missing template
fields, write error), surface the error to the user but DO NOT mark the
drive itself failed — the ticket is otherwise done and signed-off. The
changelog gap is a recoverable bookkeeping miss, not a regression on the
ticket itself; treat it the same way `epic-supervisor` Step 2 failures are
treated (warn-and-continue, never re-open the ticket).

**Failure path (supervisor returns `blocked` or `failed`):**

Because Step 3 pre-moved the ticket to `99_done/`, a failed drive leaves
the ticket in the wrong directory. Revert the rename so future re-drives
find it where they expect:

```bash
git -C "$WORKTREE_PATH" mv \
    "tickets/99_done/<basename>" \
    "tickets/01_todo/<basename>"
```

If the supervisor's phase agents had already committed the rename
(rare — only possible if the `commit` phase ran before the failure),
add a corresponding revert commit instead of a working-tree mv.

Then surface the supervisor's `payload` verbatim to the user and return
non-zero so the user knows the drive did not complete.

**Failure path return (supervisor returns `blocked` or `failed`):** return the
supervisor's payload verbatim. Do not summarise, do not add a preamble.

### Step 5c — End-of-run summary (success path)

After the changelog commit in Step 5b succeeds, emit the following summary to the
user (fill in the actual PR number from the `pull-request` phase payload):

---
**Ticket complete.** PR #<N> is open.

Review it in GitHub (or skip review for trivial changes), then run `/finalize-feature`
— it will:
1. Gate on your confirmation before merging.
2. Run `gh pr merge` (Step 2).
3. Sync `main` and run tests (Steps 3–4).
4. Close the ticket and remove the worktree (Steps 5–6).

Per `feedback_merge_before_worktree_remove.md`: the worktree will not be removed
until the merge succeeds — `/finalize-feature` enforces this ordering internally;
you do not need to merge manually first.

---

Do not add any other preamble or summary text.

## What this skill does NOT do

- **Does not handle epics.** If `$ARGUMENTS` resolves to an epic
  folder (one containing `Master_Plan.md`), `/build-feature` routes
  to `epic-supervisor` directly — this skill is never invoked.
- **Does not open the PR or commit the ticket implementation.** Those
  flow through the `commit` and `pull-request` phase agents under
  `ticket-supervisor`, with the commit-phase serialization lock from
  `building-epics` §5. The pre-move in Step 3 stages a rename but never
  commits it — the `commit` phase picks the staged rename up alongside
  the regular implementation diff, so the move travels into the PR as
  part of the normal commit, not as a follow-up bookkeeping commit.
  The one exception is the post-completion changelog commit in Step 5b,
  which mirrors `epic-supervisor` Step 2 and lands on the same PR branch
  the `pull-request` phase opened.
- **Does not bypass user escalation.** When the supervisor surfaces
  a `(status: question)` or a `failed` payload, this skill is a
  passthrough — it does not try to answer on the user's behalf.

## References

- `.claude/commands/build-feature.md` — the slash command that
  dispatches this skill for single-ticket arguments.
- `.claude/agents/ticket-supervisor.md` — the inner driver this
  skill spawns.
- `scripts/setup_ticket_worktree.py` — canonical worktree + ticket-move
  script called in Step 2. Edit this script to change the bootstrap steps.
- `.claude/skills/building-epics/SKILL.md` — operational runbook
  the supervisor follows.
- `.claude/skills/signoff/SKILL.md` — ticket-state schema the
  supervisor reads (and phase agents write).
