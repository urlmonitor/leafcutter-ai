# Retrospective: EPIC-MoveOnMainOnly

Date: 2026-06-03
Epic duration: 2026-06-03 to 2026-06-03 (single-day drive, merged as PR #36)
Commits: 1 merge commit on main (f10594f); 6+ commits on epic branch

---

## Summary

EPIC-MoveOnMainOnly eliminated the root cause of ticket-file duplication during
worktree merges: branches were using `git mv` to move ticket files between lifecycle
folders (`00_inbox → 01_todo → 99_done`). Because git's rename-tracking fails when
the merge base predates the file's creation, stale copies accumulated in `00_inbox/`
alongside canonical copies in `99_done/`. Two confirmed live duplicates existed at
epic start.

The fix establishes the "move-on-main-only" pattern: branches now only edit the
frontmatter `status:` field; `finalize-feature.js` Step 5 reconciles folder position
on main after merge (single-writer, no conflict possible). Three structural changes
delivered this: `_move_ticket()` was removed from `setup_ticket_worktree.py` (ticket
01), the pre-move Step 3 was excised from `build-single-ticket/SKILL.md` (ticket 02),
and a new `reconcileFolderPositions` sub-step was added to `finalize-feature.js` Step
5 (ticket 03). Belt-and-suspenders enforcement arrived as two new hooks: a pre-commit
guard that blocks branch-side ticket renames (`check_ticket_no_branch_move.py`,
ticket 04) and a post-merge informational scanner that surfaces duplicates and
status-folder mismatches (`check_ticket_state_integrity.py`, ticket 05). Finally,
the two existing duplicate `00_inbox/` stale copies were cleaned up directly (ticket
06). The epic ran in three parallel batches (01+06, 02+04, 03+05) and merged as a
squash-merge PR #36 the same day it was created.

---

## Metrics

| Phase | Signed Off | Failed | Needed |
|-------|-----------|--------|--------|
| architect-review | 5 | 0 | 0 |
| test-writer | 3 | 0 | 0 |
| python-coder | 3 | 0 | 0 |
| sql-coder | 0 | 0 | 0 |
| test-runner | 3 | 0 | 0 |
| documentation-expert | 1 | 0 | 0 |
| pr-reviewer | 6 | 0 | 0 |
| commit | 6 | 0 | 0 |
| pull-request | 4 | 1 | 1 |
| adr-author | 0 | 0 | 0 |
| architecture-diagram-author | 0 | 0 | 0 |
| user-surface-smoker | 2 | 0 | 0 |

Note on `pull-request` counts: 4 tickets pushed to the shared epic branch and noted
the existing PR #36 as covering them (one-PR-per-epic convention). Ticket 03 still
shows `needed` because the pull-request phase was not reached before the epic merged.
Ticket 06 shows `failed` due to the EMU restriction (see Friction Points).

---

## Category Breakdown (Feedback System)

| Category | Count |
|----------|-------|
| complete | 24 |
| tooling-issue | 1 |

25 feedback entries recorded for this epic across all phases. The single
`tooling-issue` entry corresponds to the EMU restriction on `gh pr create` in ticket
06 (pull-request phase blocker).

---

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 6 |
| Completed tickets | 5 (ticket 03 pull-request phase still marked `needed` at archive; all implementation complete) |
| Git merge commit | f10594f (PR #36) |
| Files changed in PR | 18 (2,661 insertions, 618 deletions) |
| Blocker comments | 1 |
| Handoff comments | 0 |
| New hook files | 2 (check_ticket_no_branch_move.py, check_ticket_state_integrity.py) |
| New test files | 3 (560+ lines of tests across 3 test modules) |
| Stale ticket copies deleted | 2 |

---

## What Went Well

- **Zero phase failures outside the EMU blocker.** All implementation phases
  (architect-review, python-coder, test-writer, test-runner, documentation-expert,
  pr-reviewer, commit) completed with `signed_off` on every ticket. No retries.

- **TDD discipline held throughout.** Tickets 04 and 05 both had test-writer produce
  RED baselines before python-coder implemented the hooks — all tests were confirmed
  green after implementation. Test counts: 5/5 for ticket 04, 9/9 for ticket 05.

- **Parallel batching was effective.** The 01+06 / 02+04 / 03+05 grouping respected
  the dependency chain (01 before 02 and 04; 03 after 01+02) while maximising
  concurrency. No cross-batch merge conflicts were reported.

- **Ruff compliance was clean throughout.** Python-coder noted and fixed TRY300
  violations proactively (ticket 04) and all hooks passed E722/BLE001/TRY checks
  without post-implementation rework.

- **PR-reviewer caught stale docstrings.** In ticket 01, pr-reviewer identified that
  the module-level docstring, argparse description, and `cmd_setup_ticket` docstring
  still referenced "ticket move" behavior after `_move_ticket()` was removed. These
  were fixed in the same review pass — demonstrating the value of the pr-reviewer
  phase on a subtraction-heavy ticket.

- **user-surface-smoker validated both new hooks end-to-end.** Ticket 04's hook
  correctly blocked a simulated ticket rename on a feature branch (exit 1, correct
  message format). Ticket 05's hook correctly emitted WARNING lines and exited 0.

- **One-PR-per-epic convention was followed consistently.** All 6 tickets pushed to
  the same `EPIC-MoveOnMainOnly` branch; only one PR (#36) was opened, covering the
  full epic scope. Commit agents on tickets 02–06 correctly identified the existing PR
  and did not open duplicates.

- **The worktree cherry-pick recovery was handled without user intervention.** When
  local main was ahead of origin/main, the epic branch was created from the correct
  base using cherry-pick. This did not cause any ticket-level friction.

---

## Friction Points

- **Ticket 06 — pull-request phase blocked by EMU restriction.**
  `gh pr create` failed with "Unauthorized: As an Enterprise Managed User, you cannot
  access this content (createPullRequest)". The commit was on the remote branch but
  the PR was already open for the epic, so this was a false alarm operationally — the
  work was covered by PR #36. However, the agent correctly recorded a `blocker`
  status and surfaced the manual remediation path (GitHub web UI). The EMU restriction
  is a known recurring issue (previously hit on TICKET-20260527-WireVersionIntoBuild).
  Root cause: `gh pr create` is blocked for EMU accounts; only PR #36's initial
  creation via the web UI worked.

- **Ticket 03 — pull-request phase left as `needed` at epic close.**
  Ticket 03's implementation was complete and committed (SHA 430d86a), and its changes
  were included in PR #36. However, the `pull-request` frontmatter field was never
  updated from `needed` to `signed_off` before the epic was archived. This is a minor
  bookkeeping gap with no operational impact — the code landed — but it means the
  extract_epic_facts report shows `completed_ticket_count: 5` rather than 6.

- **user-surface-smoker feedback-id was `(submit-failed)` on both tickets 04 and 05.**
  The completion manifests recorded correctly, but the feedback.jsonl submission
  failed for both user-surface-smoker entries. The cause was not diagnosed in the
  ticket comments. This is a minor telemetry gap.

---

## Knowledge Gaps Found

- **No existing guidance on the EMU / `gh pr create` restriction for epic-level PRs.**
  The restriction has now been hit on at least two separate epics (TICKET-20260527-
  WireVersionIntoBuild and now ticket 06). The correct workaround (open the initial
  epic PR via the GitHub web UI before the drive begins, then let push-only phases
  update it) is not documented anywhere that agents consult.

- **No pre-drive checklist item for "ensure epic PR already exists if EMU account".**
  The CLAUDE.md Pre-Drive Checklist covers feedback sink reachability but not PR
  existence under EMU accounts. An EMU-aware epic drive should open the PR manually
  before dispatching any ticket, so the pull-request phase on every ticket correctly
  resolves to "PR already exists — push only."

- **`completed_ticket_count` in extract_epic_facts.py counts frontmatter `status:
  done` tickets only; a ticket with `status: todo` and all phases `signed_off` is not
  counted.** Ticket 03 hit this: all implementation phases signed off but `status:`
  field was not updated to `done` before archiving. The count metric therefore
  under-represents true completion in this case.

---

## Subagent Quality Trends

No supervisor feedback entries found for this epic (supervisors may pre-date
EPIC-SupervisorFeedback or no adjudication events occurred during this drive).

The `--category subagent-quality` query against `feedback.jsonl` returned
`"total": 0`. No brainstorm-escalations, cross-agent-rework events, or halt
decisions were recorded for EPIC-MoveOnMainOnly.

---

## Proposed Improvements

### KI-1: EMU Pre-Drive PR Convention

**Proposed Knowledge Item:**

> When operating under an Enterprise Managed User (EMU) GitHub account, `gh pr create`
> is blocked at the CLI level. For epic drives:
> 1. Open the epic PR manually via the GitHub web UI before dispatching any tickets
>    (push the epic branch first with `git push -u origin EPIC-<name>`).
> 2. In each ticket's pull-request phase, the agent should detect that the PR already
>    exists (`gh pr list --head EPIC-<name>`) and mark the phase `signed_off` without
>    attempting `gh pr create`.
> This pattern avoids the `blocker` status that results from `gh pr create` failing
> under EMU restrictions.

**Routing decision (route-knowledge applied):**

This is a project-scoped procedural rule that every agent driving a pull-request phase
must know. It is not user-preference (other engineers on the repo need it), not a
reference lookup table, and not narrow enough for agent-frontmatter alone. It is
broad enough for `CLAUDE.md-inline` — a short bullet every agent should have at
spawn time — with a link to a how-to for the full procedure.

Proposed destinations:
- Primary: `CLAUDE.md-inline` — add a bullet to the Pre-Drive Checklist:
  "If operating under an EMU account, open the epic PR via GitHub web UI before
  dispatching tickets (gh pr create is blocked for EMU accounts)."
- Secondary: `docs/how-to/emu-epic-drive.md` — full procedure with the push + web UI
  PR opening steps.

**Diff for CLAUDE.md Pre-Drive Checklist (primary):**

```diff
 ## Pre-Drive Checklist

 Run through these checks before invoking `/build-feature` or starting any epic drive.
 Skipping them risks silent failures that are hard to diagnose after the fact.

 ### Feedback sink reachable
 ...

+### EMU account: open epic PR before drive (if applicable)
+
+**What to check:** If you are operating under an Enterprise Managed User (EMU) GitHub
+account, `gh pr create` is blocked at the CLI level. Before dispatching any tickets:
+
+```bash
+# Push the epic branch to origin first
+git push -u origin EPIC-<name>
+# Then open the PR manually at:
+# https://github.com/<org>/<repo>/compare/main...EPIC-<name>
+```
+
+Once the PR exists, the `pull-request` phase on each ticket should detect it via
+`gh pr list --head EPIC-<name>` and record `signed_off` without re-opening.
+
+**If you skip this:** The pull-request phase on the first ticket that tries `gh pr
+create` will fail with "Unauthorized: As an Enterprise Managed User, you cannot access
+this content (createPullRequest)". The commit will be on the remote but the phase
+will be recorded as `blocker`.
```

**Action required:** Type `yes` to apply to CLAUDE.md, `skip` to skip, or `edit` to revise.

---

### KI-2: Ticket `status:` Field Must Be Set to `done` Before Epic Archive

**Proposed Knowledge Item:**

> Before running `/finalize-feature` (or manually archiving an epic to `99_done/`),
> verify that every completed sub-ticket has `status: done` in its frontmatter. The
> `extract_epic_facts.py` script counts `completed_ticket_count` by reading frontmatter
> `status:` — a ticket with all phases `signed_off` but `status: todo` is not counted
> as complete and may be missed by downstream tooling.
>
> Checklist before archiving:
> ```bash
> grep -rn "^status: " tickets/01_todo/EPIC-<name>/done/
> # All entries should show "status: done"
> ```

**Routing decision (route-knowledge applied):**

This is an operational checklist item scoped to epic finalization, relevant to any
agent or human closing an epic. It fits `CLAUDE.md-inline` as a short addition to
the Pre-Drive / finalization checklist, OR as a how-to doc if a longer procedure is
warranted. Given its brevity, `CLAUDE.md-inline` is preferred.

Note: `.agents/rules/` is being retired; route-knowledge selected `CLAUDE.md-inline`
instead.

**Diff for CLAUDE.md (proposed addition near the finalization workflow reference):**

```diff
+## Epic Archive Checklist
+
+Before archiving an epic folder to `tickets/99_done/`:
+- [ ] Every completed sub-ticket has `status: done` in its YAML frontmatter.
+      (`grep -rn "^status: " tickets/01_todo/EPIC-<name>/done/` — all should be `done`)
+- [ ] The `pull-request` phase on every ticket is either `signed_off` or explicitly
+      recorded as blocked with a reason in the `## Comments` section.
+- [ ] `extract_epic_facts.py` `completed_ticket_count` matches the expected number of
+      tickets (if it does not, a frontmatter `status:` field is likely not set to `done`).
```

**Action required:** Type `yes` to apply to CLAUDE.md, `skip` to skip, or `edit` to revise.

---

### KI-3: user-surface-smoker feedback-id submit-failed pattern

**Proposed Knowledge Item:**

> The `user-surface-smoker` agent has been observed recording `feedback-id:
> (submit-failed)` on multiple tickets (EPIC-MoveOnMainOnly tickets 04 and 05). The
> completion manifest is correctly captured in the ticket comment, but the entry is not
> written to `feedback.jsonl`. This means user-surface-smoker runs are invisible to
> `aggregate.py` queries and health reports. Investigate whether the smoker's feedback
> submission path uses the correct absolute path for `feedback.jsonl` when running
> inside a worktree.

**Routing decision:** This is a project-scoped bug / investigation item — it belongs
as a ticket rather than a documentation entry, since the root cause is unknown. However,
the pattern should be noted as a known issue in the agent's frontmatter or a reference
doc so future retrospectives can cite it.

Route: `agent-frontmatter` (add a KNOWN ISSUES note to the user-surface-smoker agent
template, if one exists) or `ticket-body` (open a bug ticket).

**Proposed diff (reference doc entry):**

```diff
--- a/docs/reference/feedback-system.md (if this file exists)
+++ b/docs/reference/feedback-system.md
+## Known Issues
+
+### user-surface-smoker: submit-failed on feedback.jsonl write
+Observed in EPIC-MoveOnMainOnly tickets 04 and 05 (2026-06-03). The smoker
+correctly executes the smoke fixture and records the completion manifest in the
+ticket comment, but the feedback.jsonl write fails silently with
+`feedback-id: (submit-failed)`. Suspected cause: worktree path resolution for
+the feedback sink. Tracked for investigation.
```

**Action required:** Type `yes` to apply, `skip` to skip, or `edit` to revise.
(Alternatively, open a bug ticket — recommended over the doc entry.)
