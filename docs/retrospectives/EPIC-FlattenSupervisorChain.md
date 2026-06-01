# Retrospective: EPIC-FlattenSupervisorChain

Date: 2026-05-29
Epic duration: 2026-05-29 (08:37 UTC+2) to 2026-05-29 (10:48 UTC+2)
Commits: 18 (branch: worktree-EPIC-FlattenSupervisorChain, PR #23)

---

## Summary

EPIC-FlattenSupervisorChain eliminated the three-tier `epic-supervisor` →
`ticket-supervisor` → phase-agent nesting that exceeded Claude Code's hard
depth-1 Agent-tool limit. The fix moved `ticket-supervisor` to depth 0
(dispatched directly by `/build-feature`), so phase agents run at depth 1 —
within the permitted budget. `epic-supervisor` was deprecated but not deleted,
preserving backward compatibility for existing worktrees during the transition
window; ADR-006 documents the decision and rationale.

This was a self-referential ("chicken-and-egg") epic: the `epic-supervisor`
tool that normally orchestrates epics was itself the thing being fixed. All
epic-level orchestration was therefore performed manually — dispatching
`ticket-supervisor` directly at depth 0, following the dependency graph
specified in `Master_Plan.md`. Despite that constraint, all 7 tickets
completed without a single blocker, handoff, or retry. The execution order
(06 → 01 → {02, 03, 04} parallel → 05 → 07) was followed faithfully, and the
parallel batch ran cleanly against disjoint file sets. The epic also self-
corrected an unpushed-commit condition (KI-1) detected before worktree creation.

---

## Metrics

| Phase | Signed Off | Failed | Needed |
|-------|-----------|--------|--------|
| adr-author | 1 | 0 | 1 |
| architect-review | 7 | 0 | 7 |
| architecture-diagram-author | 1 | 0 | 1 |
| commit | 7 | 0 | 7 |
| documentation-expert | 2 | 0 | 2 |
| pr-reviewer | 7 | 0 | 7 |
| pull-request | 7 | 0 | 7 |
| python-coder | 4 | 0 | 4 |

All phases across all 7 tickets signed off. No failures. No retries.

---

## Category Breakdown (Feedback System)

No structured `feedback.jsonl` entries exist for this epic. The feedback log
at `debugging/logs/feedback.jsonl` contains entries only from prior epics
(EPIC-FrontendAgent). The ticket `## Comments` sections served as the primary
structured record of phase outcomes; all entries carried `status: ok`.

---

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 7 |
| Completed tickets | 7 |
| Git commits | 18 |
| Epic duration | ~2 hours 11 minutes (08:37–10:48 UTC+2, 2026-05-29) |
| Blocker comments | 0 |
| Handoff comments | 0 |
| PR | #23 (urlmonitor/leafcutter-ai) |

Note: `extract_epic_facts.py` was not available in this worktree; facts were
derived from git log and ticket comment sections.

---

## What Went Well

- **Dependency graph execution was exact.** The six-step order (06 → 01 →
  {02, 03, 04} → 05 → 07) was followed without deviation. Parallel batch
  tickets 02, 03, and 04 touched disjoint files (`build-feature.md`,
  `agent_registry.json`, `building-epics/SKILL.md` respectively), preventing
  any merge conflicts.

- **Manual orchestration succeeded cleanly.** Because `epic-supervisor` was
  the broken tool, this epic was orchestrated by hand. Dispatching
  `ticket-supervisor` at depth 0 directly proved that the flattened model
  works exactly as designed, validating the fix in the same run that
  implemented it.

- **KI-1 (unpushed commit) caught and resolved pre-flight.** Before the
  worktree was created, a stale unpushed commit was detected and pushed. This
  prevented a hard-to-diagnose merge conflict mid-epic.

- **ADR-006 written first (ticket 06).** Authoring the architectural decision
  record as the first action gave every subsequent ticket a canonical citation
  target, keeping rationale out of individual template files and centralised
  in one place.

- **Backward compatibility preserved.** `epic-supervisor` was deprecated (not
  deleted) and `ticket-supervisor.spawned_by` retained `"epic-supervisor"` as
  a valid entry alongside the new `"user"` entry, ensuring existing worktrees
  referencing the old chain would not break.

- **build-self.sh validated at every step.** Tickets 01, 02, and 05 each ran
  `build-self.sh` as part of their acceptance criteria, catching any
  regression in the built-agent output before commit.

- **Zero feedback-submission failures from agent errors.** Three `commit`
  phase entries in ticket 02 show `feedback-id: (submit-failed)`, indicating
  the feedback client had a transient issue during that phase, but this did
  not affect implementation quality or ticket completion.

---

## Friction Points

- **Chicken-and-egg orchestration overhead.** The normal `/build-feature`
  → `epic-supervisor` path was unavailable. Manual orchestration required the
  operator to track the dependency graph, identify the parallel-safe batch,
  and dispatch `ticket-supervisor` in the right order. This is low-risk for a
  small 7-ticket epic but would not scale to a 20-ticket epic without a
  lightweight manual checklist or scaffold.

- **Feedback submission failures in ticket 02.** The `architect-review`,
  `python-coder`, and `pr-reviewer` phases of ticket 02 all recorded
  `feedback-id: (submit-failed)`. The underlying data exists in the ticket
  comments, but is absent from `feedback.jsonl`. Root cause is unclear
  (possible concurrent feedback writes during the parallel batch).

- **`extract_epic_facts.py` absent from the worktree.** The structured
  retrospective script that normally produces quantitative metrics was not
  present, requiring manual counting from git log and ticket comments. This
  is tracked separately (TICKET-20260528-HardenExtractEpicFacts).

- **PR #22 revert was a pre-epic cost.** The earlier attempt (PR #22) had
  incorrectly made `ticket-supervisor` an inline executor that read templates
  rather than spawning agents. That mis-design was discovered during review
  and reverted before this epic began. The revert and redesign were not
  themselves tickets in this epic, but they represent planning overhead that
  the ADR-006 Context section now documents for future reference.

---

## Knowledge Gaps Found

- **No formal checklist for self-referential epics.** When the tool being
  fixed is also the tool driving the epic, the team needs a documented
  fallback procedure for manual orchestration. Currently this is tribal
  knowledge. A short how-to or SKILL.md section covering "how to run an epic
  manually when epic-supervisor is unavailable" would prevent confusion in
  future structural epics.

- **Parallel batch safety is implicit.** The decision that tickets 02, 03,
  and 04 are safe to run in parallel was made by inspecting `files_touched`
  fields manually. There is no automated check that verifies disjoint file
  sets before the parallel batch runs. A pre-batch validation step (even a
  one-liner that greps `files_touched` across candidate tickets) would make
  this safety guarantee explicit.

- **Feedback client concurrency under parallel dispatch.** The three
  `submit-failed` feedback IDs in ticket 02's parallel batch suggest the
  feedback writer may not be concurrency-safe under simultaneous agent writes.
  This gap was not blocking, but should be investigated before the feedback
  system is relied on for audit purposes.

---

## Subagent Quality Trends

No supervisor feedback entries found for this epic (supervisors may pre-date
EPIC-SupervisorFeedback, or no adjudication events occurred during this drive).

The `subagent-quality` category returned 0 entries from `aggregate.py`.

---

## Proposed Improvements

### KI-1: How to run an epic manually when epic-supervisor is unavailable

**Proposed Knowledge Item text:**

> When the tool being fixed is the epic orchestrator itself (or when
> `epic-supervisor` is otherwise unavailable), follow this manual procedure:
>
> 1. Read `Master_Plan.md` to identify the dependency graph and execution
>    order.
> 2. Identify the first ready ticket (no unmet `depends_on`). Dispatch
>    `ticket-supervisor` directly at depth 0, passing the ticket path as
>    `context`.
> 3. After the ticket is signed off and committed, re-evaluate the dependency
>    graph. Tickets whose `depends_on` are all done form the next ready batch.
> 4. If the ready batch contains tickets with disjoint `files_touched` sets,
>    they may be dispatched in parallel. Verify disjoint-ness by comparing
>    `files_touched` entries before dispatching.
> 5. Repeat until all tickets are done, then open the epic PR manually with
>    `gh pr create`.

Routing: `docs/how-to/` (how-to document — procedural guide for a specific
situation; not a rule, not a skill extension)

---

### KI-2: Pre-batch disjoint-file-set validation note

**Proposed Knowledge Item text (addition to `building-epics/SKILL.md` §1):**

> Before dispatching a parallel batch, verify that no two tickets in the
> batch share a file in their `files_touched` lists. A quick check:
>
> ```bash
> grep "files_touched" tickets/.../ticketA.md tickets/.../ticketB.md | sort | uniq -d
> ```
>
> If any path appears in more than one ticket, those tickets must be
> serialised.

Routing: `templates/skills/building-epics/SKILL.md` (extends existing skill
documentation for the building-epics workflow)

---

### Rule Update: Document feedback client concurrency limitation

**Proposed rule change as a diff:**

```
- (no existing rule)
+ In debugging/logs/feedback.jsonl, concurrent writes from parallel agent
+ batches may silently fail (feedback-id recorded as "submit-failed"). Do not
+ rely on feedback.jsonl for audit completeness during parallel ticket batches
+ until the feedback writer is hardened with a file lock or queue mechanism.
+ Observed: ticket 02 parallel batch (EPIC-FlattenSupervisorChain, 2026-05-29).
```

Routing: `docs/conventions/` or a note in the feedback system's own
documentation (`docs/reference/feedback-system.md` if it exists), not
`CLAUDE.md` (this is an implementation limitation, not a workflow rule).

---

*All proposed KIs above require explicit user approval before being applied.
No files have been modified.*
