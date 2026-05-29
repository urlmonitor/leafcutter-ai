---
title: "How to drive an epic manually when epic-supervisor is unavailable"
type: how-to
status: active
created: 2026-05-29
last_updated: 2026-05-29
components:
  - build_pipeline
related_docs:
  - docs/agents/supervisor/epic-supervisor.md
  - docs/agents/supervisor/ticket-supervisor.md
  - docs/build-pipeline.md
  - templates/skills/build-feature-ops-notes/SKILL.md
  - templates/skills/building-epics/SKILL.md
---

# How to drive an epic manually when epic-supervisor is unavailable

This guide explains how to orchestrate an epic by hand when `epic-supervisor`
is itself the artifact being changed, deprecated, or broken — the
chicken-and-egg scenario. Following this procedure lets you dispatch
`ticket-supervisor` directly at depth 0, respect the dependency graph in
`Master_Plan.md`, and complete the epic safely without the normal
`/build-feature` → `epic-supervisor` path.

The pattern was established during EPIC-FlattenSupervisorChain (2026-05-29,
PR #23), where all seven tickets completed without a blocker or retry using
exactly this procedure.

---

## Prerequisites

- You have a git worktree for the epic branch, or you are about to create one.
- The epic folder exists in `tickets/00_inbox/epics/<EPIC-Name>/` and contains
  a `Master_Plan.md` with a dependency graph and sub-ticket table.
- `ticket-supervisor` is functional (only `epic-supervisor` is unavailable).
- You have push access to `origin/main` and can run `gh pr create`.
- You have read `docs/agents/supervisor/ticket-supervisor.md` for the
  `ticket-supervisor` invocation contract.

---

## Steps

### Step 1 — Read Master_Plan.md and map the dependency graph

Open the epic's `Master_Plan.md` and extract two things:

1. The sub-ticket table (ticket number, file path, description, status).
2. The dependency graph section — which tickets must complete before others
   can start, and which tickets are safe to run in parallel.

```bash
cat tickets/00_inbox/epics/<EPIC-Name>/Master_Plan.md
```

Write down the execution order before touching anything. For example, if the
plan says `06 → 01 → {02, 03, 04} → 05 → 07`, record that sequence explicitly.
Parallel batches are shown with braces; serial dependencies are shown with
arrows.

### Step 2 — Push any unpushed local commits (KI-1 prevention)

Before creating the worktree, verify that every commit your epic folder depends
on is on `origin/main`. If commits exist locally but are not yet pushed, the
worktree will be created from `origin/main` and will not contain the epic files.

```bash
git log --oneline origin/main..main
```

If this command lists any commits, push them now:

```bash
git push origin main
```

Confirm the output is empty before proceeding:

```bash
git log --oneline origin/main..main
```

Expected output: no lines (empty). If lines appear, push again and re-check.

### Step 3 — Create the worktree via EnterWorktree

Use the `EnterWorktree` tool to create a fresh worktree for the epic branch.
Do not use any shell script that may not exist.

The tool creates a worktree at the path it returns. Note the exact path — you
will need it in every subsequent step.

### Step 4 — Verify the epic folder is reachable in the worktree

After `EnterWorktree` returns, confirm the epic folder is present in the new
worktree:

```bash
ls "<WORKTREE_PATH>/tickets/00_inbox/epics/<EPIC-Name>/Master_Plan.md"
```

Expected output: the filename is printed with no error. If the file is absent,
the worktree was created from a commit that predates the epic folder commit.
Resolve with a cherry-pick (see Troubleshooting §1) before continuing.

### Step 5 — Identify the first ready ticket

A ticket is ready when all tickets listed in its `depends_on` field are already
in `tickets/99_done/<EPIC-Name>/`. On first run, the initial ticket (the one
with no dependencies) is always ready.

Read the first ready ticket file and note its path:

```bash
cat "<WORKTREE_PATH>/tickets/00_inbox/epics/<EPIC-Name>/<ticket-file>.md"
```

### Step 6 — Dispatch ticket-supervisor directly at depth 0

Invoke `ticket-supervisor` as a sub-agent at depth 0 (directly from your
session — not from inside another agent). Pass the full absolute path to the
ticket file as the `ticket_path` context.

Repeat this step for each ticket in the current serial position. Do not dispatch
the next ticket until the current one is signed off and committed.

After `ticket-supervisor` returns, verify the ticket has been signed off by
checking that its status is updated and the ticket file appears (or has moved)
in the done folder:

```bash
ls "<WORKTREE_PATH>/tickets/99_done/<EPIC-Name>/" 2>/dev/null || \
  grep "status:" "<WORKTREE_PATH>/tickets/00_inbox/epics/<EPIC-Name>/<ticket-file>.md"
```

### Step 7 — Verify disjoint file sets before dispatching a parallel batch

When the dependency graph specifies a parallel batch (e.g. `{02, 03, 04}`),
verify that no two tickets in the batch touch the same file before dispatching
them simultaneously.

For each pair of candidate tickets, extract and compare their `files_touched`
lists:

```bash
grep "files_touched" \
  "<WORKTREE_PATH>/tickets/00_inbox/epics/<EPIC-Name>/02_ticket.md" \
  "<WORKTREE_PATH>/tickets/00_inbox/epics/<EPIC-Name>/03_ticket.md" \
  "<WORKTREE_PATH>/tickets/00_inbox/epics/<EPIC-Name>/04_ticket.md" \
  | sort | uniq -d
```

Expected output: no lines (empty). If any path appears in more than one ticket,
those two tickets must be run serially — do not include them in the same
parallel batch.

### Step 8 — Dispatch the parallel batch simultaneously

Once you have confirmed disjoint file sets, dispatch all tickets in the batch
at the same time by invoking `ticket-supervisor` as separate sub-agents in a
single turn, one per ticket in the batch.

Monitor all dispatched agents. Wait until every agent in the batch returns
before proceeding.

### Step 9 — Verify done status for every batch before dispatching the next

After a parallel batch completes, confirm every ticket in the batch is done
before moving to the next serial step:

```bash
ls "<WORKTREE_PATH>/tickets/99_done/<EPIC-Name>/"
```

Cross-check the listed files against the Master_Plan sub-ticket table. Only
proceed to the next batch or serial ticket when all expected tickets from the
current batch appear as done.

If a ticket is not done (agent returned with a blocker or failed sign-off),
resolve it before continuing — see Troubleshooting §2.

### Step 10 — Repeat Steps 5–9 for each remaining serial or parallel step

Continue walking the dependency graph, dispatching each ready ticket or batch
in order, verifying done status after each step, until all tickets in the
Master_Plan sub-ticket table are complete.

### Step 11 — Mark Master_Plan status as done

Once all sub-tickets are done, update the `status:` field in the epic's
`Master_Plan.md` frontmatter to `done`:

```yaml
status: done
```

Commit this change:

```bash
git -C "<WORKTREE_PATH>" add tickets/00_inbox/epics/<EPIC-Name>/Master_Plan.md
git -C "<WORKTREE_PATH>" commit -m "chore: mark <EPIC-Name> Master_Plan done"
```

### Step 12 — Run the changelog and retrospective

Open a PR for the epic branch, then run the changelog and retrospective
agents as the final step:

```bash
gh pr create --title "<EPIC-Name>: <one-line summary>" \
  --body "$(cat <<'EOF'
## Summary
<bullet points>

## Test plan
- [ ] All tickets signed off in tickets/99_done/
- [ ] build.py --validate-only passes
- [ ] No unresolved placeholders in compiled output
EOF
)"
```

After the PR is open, dispatch `changelog-agent` and the retrospective agent
to produce the structured records. These must complete before the epic is
declared done.

---

## Verification

After all tickets are done and the PR is open, run this final check:

```bash
ls "<WORKTREE_PATH>/tickets/99_done/<EPIC-Name>/"
```

The output must list every sub-ticket filename from the Master_Plan table. If
any ticket is missing, do not open the PR — dispatch `ticket-supervisor` for
the missing ticket first.

Also confirm the epic branch build is clean:

```bash
git -C "<WORKTREE_PATH>" status --short
```

Expected output: no lines (clean working tree). If unstaged or untracked files
appear, commit or discard them before pushing.

---

## Troubleshooting

1. **Epic folder absent from worktree after EnterWorktree**

   The worktree was created from a commit that predates the epic folder commit.
   Identify the missing commit on the host repo:

   ```bash
   git log --oneline origin/main..main
   ```

   Cherry-pick it into the worktree:

   ```bash
   git -C "<WORKTREE_PATH>" cherry-pick <SHA>
   ```

   Re-run Step 4 to confirm the epic folder is now present. If multiple commits
   are missing, cherry-pick them in chronological order (oldest first).

   See `templates/skills/build-feature-ops-notes/SKILL.md` §KI-1 for the full
   incident record and automated detection method.

2. **A ticket-supervisor dispatch returns a blocker**

   Read the ticket's `## Comments` section to identify the blocker:

   ```bash
   grep -A 10 "## Comments" "<WORKTREE_PATH>/tickets/00_inbox/epics/<EPIC-Name>/<ticket>.md"
   ```

   Resolve the blocker manually (fix the root cause, not just the symptom),
   then re-dispatch `ticket-supervisor` for that ticket. Do not advance the
   dependency graph until the ticket is signed off.

3. **Two tickets in a candidate parallel batch share a file**

   The `uniq -d` check in Step 7 returned one or more paths. Serialise the
   conflicting tickets: run the one whose output is needed by the other first,
   then run the second ticket after the first is done. If neither depends on the
   other's output, pick an arbitrary order.

4. **agent-nesting depth limit exceeded**

   If you see an error like `Agent tool depth limit reached`, you are invoking
   `ticket-supervisor` from inside another agent (depth 1 → depth 2 attempted).
   `ticket-supervisor` must be dispatched from your top-level session (depth 0).
   Return to the top-level session and dispatch from there.

---

## See Also

- `docs/agents/supervisor/ticket-supervisor.md` — `ticket-supervisor` invocation
  contract and phase ordering.
- `docs/agents/supervisor/epic-supervisor.md` — the deprecated orchestrator this
  guide replaces when unavailable.
- `docs/build-pipeline.md` — how the build pipeline compiles and validates
  agent templates.
- `templates/skills/build-feature-ops-notes/SKILL.md` — operational knowledge
  items including KI-1 (unpushed commits) and KI-2 (stream-watchdog recovery).
- `templates/skills/building-epics/SKILL.md` — the supervisor runbook used by
  `epic-supervisor`; useful background on how normal epic orchestration works.
- `docs/retrospectives/EPIC-FlattenSupervisorChain.md` — the source incident
  that established this pattern.
