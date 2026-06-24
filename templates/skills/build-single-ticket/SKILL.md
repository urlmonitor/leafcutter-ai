---
name: build-single-ticket
internal: true
description: Drive a single standalone ticket (not part of an epic) through its phase agents. Creates an isolated worktree, dispatches ticket-supervisor, and on success the ticket lifecycle folder is reconciled on main by finalize-feature.js. Invoked by /build-feature when its argument resolves to a `.md` file outside an `EPIC-*/` folder.
---

# build-single-ticket

> **Move-on-main-only (EPIC-MoveOnMainOnly):** As of EPIC-MoveOnMainOnly, branches no longer
> move ticket files between lifecycle folders. This skill's job is to drive the ticket through
> phase agents. Folder reconciliation (inbox → done) happens on `main` after merge via
> `finalize-feature.js` Step 5.

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
6. **Delete `.build-feature.lock` (inline-work-guard handoff).** Before
   dispatching `ticket-supervisor`, remove the sentinel lock written by
   `/build-feature` so phase agents are not blocked by `inline_work_guard.py`:

   ```bash
   REPO_ROOT="$PWD"
   while [ ! -d "$REPO_ROOT/.git" ] && [ "$REPO_ROOT" != "/" ]; do
     REPO_ROOT="$(dirname "$REPO_ROOT")"
   done
   rm -f "$REPO_ROOT/.build-feature.lock"
   ```

   This deletion signals that a supervisor has taken ownership of the drive.
   Phase agents that subsequently call Edit/Write will find no lock and be
   allowed through. If the lock file does not exist, the `rm -f` is a no-op.

## Step 2 — Set up the worktree (mandatory, blocking)

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
- `ticket_path_final` → `TICKET_PATH` (the ticket's path inside the worktree)

On non-zero exit, surface stderr verbatim and stop — do NOT fall through to
running on `main`. Silent-main-branch execution is the exact bug the worktree
convention exists to prevent.

The script creates and bootstraps the worktree. It does NOT move the ticket
file — folder position is reconciled on main by `finalize-feature.js` after
merge.

Do NOT dispatch `worktree-agent` as a separate Agent tool call.

## Step 3 — Dispatch `ticket-supervisor`

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

## Step 4 — Verify done state (post-supervisor)

When `ticket-supervisor` returns `{"status": "done"}`, all sign-off edits
are already in the PR opened by the `pull-request` phase. The ticket file
remains in its original lifecycle folder on the branch (no `git mv` was
performed). This skill performs no file moves on the success path — Step 4
is purely a verification gate.

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

**Step 4c — Emit feedback on residuals (best-effort)**

When Step 4 preflight detects an in-scope uncommitted delta and commits it:

1. Determine the category:
   - `subagent-quality` if the residual is a sign-off frontmatter change or a
     `## Sign-offs` / `## Comments` body edit attributable to the `commit` or
     `pull-request` phase agents.
   - `tooling-issue` for any other in-scope residual.

2. Run (best-effort — log stderr and continue on any error):
   ```bash
   python scripts/feedback/submit_feedback.py \
     --ticket "<ticket_path>" \
     --phase ticket-supervisor \
     --category <category> \
     --tags "dangling-signoff,step4-residual" \
     --note "Step 4 in-scope residual committed: <brief description of the delta>"
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

### Step 4b — Changelog entry (success path, mirrors epic-supervisor Step 2)

Once the parity guard passes, write a per-file changelog entry capturing the
ticket completion. This mirrors `epic-supervisor` Step 2 (the
`type=epic_completion` write) and uses the same canonical helper
(`leafcutter/scripts/changelog/emit_entry.py`) so all three call
sites — standalone `/changelog`, epic post-completion, and single-ticket
post-completion — share one write path.

1. Read the ticket file's YAML frontmatter. Extract:
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

Because the ticket file was never pre-moved, no revert is needed on failure.
Surface the supervisor's `payload` verbatim to the user and return non-zero.

**Failure path return (supervisor returns `blocked` or `failed`):** return the
supervisor's payload verbatim. Do not summarise, do not add a preamble.

### Step 4c — End-of-run summary (success path)

After the changelog commit in Step 4b succeeds, emit the following summary to the
user. Fill in all placeholders from context (PR number from the `pull-request`
phase payload, BRANCH from Step 2, Goal section and files_touched from the ticket
frontmatter, and ACs from the ticket body):

---
## Summary
<2–3 sentences derived from the ticket's `# Goal` section and `files_touched`
frontmatter — describe what was built, not how. Example: "Updated build-epic.js
Step 6 return to include worktree_path and manual_tests fields. Standardized the
completion output in build-single-ticket/SKILL.md and build-feature.md to always
show a four-section format.">

PR #<N> is open.

## Worktree path
<WORKTREE_PATH>

## Things to manually test
<3–5 concrete smoke-test suggestions derived from the ticket's Acceptance Criteria
and files_touched. Example:>
- Run /build-feature on a test ticket and confirm the completion output shows all
  four sections: Summary, Worktree path, Things to manually test, and Finalize command.
- Verify the finalize command in the output reads `/finalize-feature <BRANCH>` with
  the branch name pre-filled (not a raw ticket path).
- Inspect `templates/workflows-js/build-epic.js` Step 6 return object and confirm
  it includes `worktree_path` and `manual_tests` fields.
- Inspect `templates/skills/build-single-ticket/SKILL.md` Step 4c and confirm the
  four-section template is present with `<BRANCH>` pre-filled.
- Inspect `templates/workflows/build-feature.md` and confirm the inline fallback
  completion message includes all four sections.

## Finalize command
/finalize-feature <BRANCH>

---

Fill in BRANCH with the actual branch name from Step 2 (e.g. `feature/standardizebuildcompletionoutput`).

Review the PR in GitHub (or skip review for trivial changes), then run the finalize
command above — it will:
1. Gate on your confirmation before merging.
2. Run `gh pr merge` (Step 2).
3. Sync `main` and run tests (Steps 3–4).
4. Close the ticket and remove the worktree (Steps 5–6).

Per `feedback_merge_before_worktree_remove.md`: the worktree will not be removed
until the merge succeeds — `/finalize-feature` enforces this ordering internally;
you do not need to merge manually first.

Do not add any other preamble or summary text.

## What this skill does NOT do

- **Does not handle epics.** If `$ARGUMENTS` resolves to an epic
  folder (one containing `Master_Plan.md`), `/build-feature` routes
  to `epic-supervisor` directly — this skill is never invoked.
- **Does not open the PR or commit the ticket implementation.** Those
  flow through the `commit` and `pull-request` phase agents under
  `ticket-supervisor`, with the commit-phase serialization lock from
  `building-epics` §5. The commit phase stages only sign-off edits and
  implementation changes — no ticket file rename is staged because the
  ticket file is never pre-moved on the branch.
  The one exception is the post-completion changelog commit in Step 4b,
  which mirrors `epic-supervisor` Step 2 and lands on the same PR branch
  the `pull-request` phase opened.
- **Does not bypass user escalation.** When the supervisor surfaces
  a `(status: question)` or a `failed` payload, this skill is a
  passthrough — it does not try to answer on the user's behalf.
- **Does not create AC-authoring worktrees.** The dedicated AC-authoring
  worktree (branched from `origin/main`) is created by `/create-ac` and
  `/plan-feature` via `scripts/setup_ticket_worktree.py create-ac-worktree`
  (AC BO-1500a-1). This skill creates implementation worktrees (branched
  from local `main`) for ticket execution — a separate concern from AC
  authoring.

## Contrast: this skill vs. `/quick-fix`

This skill (`build-single-ticket`) always creates a **new isolated worktree** (Step 2 via
`setup_ticket_worktree.py`) and drives the ticket on a **new branch**. The ticket persists
in the inbox until `finalize-feature.js` reconciles it on `main` after the PR is merged.

The `/quick-fix` workflow (AC BP-600a-1; `templates/workflows-js/quick-fix.js`) is the
**current-worktree** counterpart. It differs from this skill in four key ways:

| Aspect | `build-single-ticket` (this skill) | `/quick-fix` |
|--------|-----------------------------------|----|
| Worktree | New isolated worktree created | **Current worktree — no new directory** |
| Branch | New branch per ticket | **Current branch — no switch** |
| Entry | Invoked by `/build-feature` for single-ticket paths | Invoked directly by `/quick-fix` |
| Ticket lifecycle | Full inbox → PR → finalize | Single-shot — ticket created and driven to commit inline |

**When to use this skill vs. `/quick-fix`:** use this skill when the fix requires a clean
branch and a full PR lifecycle. Use `/quick-fix` when you have already diagnosed a bug,
want the fix committed on your current branch immediately, and do not want a new worktree
directory created (AC BP-600a-1).

See `docs/architecture/agent_delivery_workflows.md` §5 for the full quick-fix workflow diagram.

### Close phase of `/quick-fix` vs. this skill (AC BP-600d-4)

The `/quick-fix` close phase (AC BP-600d-4) runs three inline operations at depth 0
after the `commit` agent returns:

1. **Push** — `git push origin HEAD` sends the committed change to the remote
   tracking branch.
2. **PR check** — `gh pr list --head <branch>` logs the PR URL if one exists. If
   no PR exists, the close phase logs a URL for the user to open one manually. The
   push makes the commit visible to the PR automatically — no `gh pr update` command
   is needed.
3. **Ticket close** — `python scripts/set_ticket_status.py --ticket <ticket_path> --status done`
   marks the internal quick-fix ticket as done in its frontmatter.

These three steps are the quick-fix equivalent of this skill's `pull-request` phase agent
(Step 4) and `finalize-feature.js` Step 5 (ticket lifecycle reconciliation). The key
difference: `/quick-fix` performs all three inline at depth 0 rather than dispatching
dedicated phase agents, because the quick-fix close phase produces no reviewable
artefacts and needs no sign-off audit trail beyond the commit message.

**Idempotency:** all three close-phase operations are idempotent. A re-drive of
`/quick-fix` after a partial close (e.g. push succeeded but `set_ticket_status.py`
failed) completes the remaining steps without duplicating the push or logging a
spurious PR URL.

**Push failure halt:** if `git push origin HEAD` fails, the close phase halts and
prints a structured recovery message. The ticket is NOT marked done until the push
succeeds. This preserves consistency: `status: done` implies the change is visible
on the remote, not just committed locally.

See `docs/architecture/agent_delivery_workflows.md` §5 "AC BP-600d-4" for the full
push contract, PR update contract, ticket close contract, ordering invariant, and
push failure halt message.

### Handling `/quick-fix` escalation (AC BP-600e-3)

When the `/quick-fix` workflow escalates to the full build pipeline — either because the
python-coder modified more than one source file (BP-600e-1) or because the red-phase test
revealed a different root cause than diagnosed (BP-600e-2) — the user receives a structured
escalation summary with:

- An **AC ID** (e.g. `BP-600e-3`) identifying the traceability artefact in the AC store.
- A **test file path** pointing to the failing test that was written during the quick-fix run.
- A **diagnosed file** and **root cause** from the original diagnosis.

When the user then invokes `/build-feature` (or `/create-ticket`) to continue the fix, this
skill (`build-single-ticket`) is the vehicle. The workflow for continuing from a `/quick-fix`
escalation:

1. **Stage and commit the preserved artefacts** before invoking this skill. The AC YAML file
   and test file are already in the working tree (left by `/quick-fix`). Commit them as a
   starting point on the current branch:
   ```
   git add <ac_path> <test_file_path>
   git commit -m "chore: stage quick-fix artefacts for escalated fix (AC <ac_id>)"
   ```
   This pre-commit is the user's responsibility — this skill does not stage or commit
   pre-existing artefacts from a prior `/quick-fix` run.

2. **Create a ticket** referencing the AC ID. The ticket's `## Acceptance Criteria` section
   should include the AC ID from the escalation summary so the `ac-validator` phase can
   locate the coverage evidence:
   ```
   /create-ticket
   > Fix the multi-file bug diagnosed by /quick-fix. AC ID: <ac_id>.
   >   Test file already written: <test_file_path>
   >   Target file: <target_file>
   >   Root cause: <root_cause>
   ```

3. **Invoke this skill** (via `/build-feature`) on the resulting ticket. This skill creates
   a new isolated worktree, bootstraps the branch, and drives the full phase-agent pipeline
   (including `python-coder` for the fix and `pr-reviewer` for review).

**AC ID continuity contract (BP-600e-3):**

The AC YAML file created during the `/quick-fix` run remains `status: active` throughout this
escalated flow. The escalated ticket's `python-coder` phase writes the fix to the target file;
the `test-runner` phase verifies the test written during the quick-fix turns green; the
`commit` phase references the same AC ID in the commit message. The AC YAML file is not
re-created — the same file that `/quick-fix` created is the traceability artefact for the
full-pipeline fix.

See `docs/architecture/agent_delivery_workflows.md` §5 "AC BP-600e-3" for the full
escalation summary output format and artefact preservation rules.

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
- EPIC-MoveOnMainOnly — the design decision that removed branch-side `git mv`; folder
  reconciliation now happens on `main` after merge via `finalize-feature.js`.
