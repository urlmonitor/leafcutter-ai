---
title: "Retrospective: EPIC-PrecommitSafetyNet"
description: "Epic retrospective for EPIC-PrecommitSafetyNet — pre-commit safety net for the leafcutter-ai package."
date: 2026-06-17
epic_branch: EPIC-PrecommitSafetyNet
pr: "https://github.com/urlmonitor/leafcutter-ai/pull/89"
---

# Retrospective: EPIC-PrecommitSafetyNet

Date: 2026-06-17
Epic duration: 2026-06-17 (single-day drive, ~6 hours wall clock)
Merge commit: 386236a
First feature commit: bdca001 (2026-06-17 08:44)
Last feature commit: 656b6d6 (2026-06-17 13:37)

## Summary

EPIC-PrecommitSafetyNet shipped the pre-commit safety net for the leafcutter-ai
package. The core problem was that when a coder agent signed off and the commit
agent's `git commit` later failed a pre-commit hook, the `precommit-autofix`
skill spawned a fresh fixer with none of the original coder's design context.
That agent had to re-derive intent, re-look up consumers, and re-read the test
baseline — pure rework.

The epic delivered four interrelated components: (1) reconciled the previously
dead `precommit-autofix.json` stub to its documented schema with a
`blocking_hook_ids` gating array; (2) added two new pure-Python transform-tier
hooks (`transform_doc_frontmatter`, `transform_description_field`) that
self-heal mechanical doc violations in place, plus a `tier` field on every
hooks-manifest entry, plus `AUTOFIX_AGENT` emission from
`check_exception_handling.py`; (3) added gated `context_capsule` emission to
all three coder agent templates (python-coder, sql-coder, frontend-coder) with
backward-compatible absence handling; and (4) wired the originator re-dispatch
routing into `precommit-autofix` SKILL.md so that judgment-tier failures are
fixed by the same agent type that authored the work.

All 5 tickets closed done with no blocker comments in any sign-off log. One
post-merge follow-up fix (656b6d6) was required for an integration gap in
ticket 04 (described under Friction Points).

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 5 |
| Completed tickets | 5 (100%) |
| Blocker comments | 0 |
| Handoff comments | 0 |
| Post-merge fix commits | 1 (656b6d6) |
| Git commits (feature, incl. chore) | ~19 on epic branch |
| Merge commit | 386236a |
| PR | #89 |

Note: `extract_epic_facts.py` is absent from this installation; facts derived
from ticket Comments sections and git log.

## Category Breakdown (Feedback System)

No structured feedback entries are tagged to EPIC-PrecommitSafetyNet in
`debugging/logs/feedback.jsonl`. The feedback corpus covers EPIC-GoalToEpic and
EPIC-DefineABehaviorOnce — this epic predates or was not wired to the feedback
sink during the drive. Quantitative category breakdown is unavailable.

## Metrics

Phase sign-off state derived from ticket frontmatter `agents:` maps:

| Phase | Signed Off | Failed | Needed |
|-------|-----------|--------|--------|
| test-writer | 1 | 0 | 4 (not_needed) |
| python-coder | 2 | 0 | 3 (not_needed) |
| llm-expert | 2 | 0 | 3 (not_needed) |
| documentation-expert | 1 | 0 | 4 (not_needed) |
| test-runner | 1 | 0 | 4 (not_needed) |
| pr-reviewer | 5 | 0 | 0 |
| commit | 5 | 0 | 0 |
| pull-request | 5 | 0 | 0 |

All tickets ran to completion with zero failed phases. The ticket-02 commit
phase shows two duplicate pull-request sign-off chore commits (a6a2bfd,
4e25d90) — a minor chore-commit duplication, not a retry.

## What Went Well

- **All 5 tickets closed without a single blocker comment.** Every agent phase
  signed off (status: ok) on the first attempt. No adjudication ladder was
  triggered.
- **TDD was clean on ticket 02.** test-writer established a red baseline of 12
  stubs; python-coder turned all 12 green in one pass; test-runner confirmed
  12/12 with only pre-existing unrelated failures.
- **Template parity enforced throughout.** Every deployed file that has a
  template counterpart (`commit_guardian.json`, `check_exception_handling.py`,
  both transform hooks) was edited in both locations and verified via the
  build.py round-trip. Zero parity drift introduced.
- **Backward-compatibility design held.** Context capsule absence was
  explicitly documented as warn-and-proceed in both signoff/SKILL.md and
  precommit-autofix/SKILL.md. Pre-capsule tickets remain functional.
- **Shell convention enforced.** ticket-04 llm-expert found and split
  pre-existing `|| true` chains in `commit.md` Step 0 into proper
  single-command blocks as a by-product of the AC-5 check.
- **PR-reviewer medium-confidence findings were correctly triaged.** The
  ticket-02 pr-reviewer surfaced three medium observations (missing
  check-doc-frontmatter validator, pre-existing JSON manifest divergence,
  `_restage_file` unchecked returncode) and correctly did not block on any —
  all were fail-open by design.
- **Dependency sequencing worked.** Tickets 1, 2, 3 ran before ticket 4 as
  planned. ticket 5 correctly waited on ticket 2.

## Friction Points

- **TICKET 04 — Integration gap not caught by unit tests (656b6d6).** The
  originator re-dispatch SKILL.md shipped done with all 7 ACs covered. A
  post-merge read-only integration spot-check found that the tier lookup was
  broken end-to-end: the skill read the tier from a `hooks_manifest` field in
  a file it never opened during the re-dispatch path. Additionally, 4 of the 7
  `blocking_hook_ids` entries had no corresponding `hooks_manifest` entry, so
  the tier lookup silently returned null rather than `"judgment"`. Ticket 02's
  AC-5 was signed done without the manifest entries it mandated for those 4
  IDs. Fix commit 656b6d6 derived the tier from the `category` field in the
  `rules[]` config instead, which is always in scope. Root cause: ac-validator
  and pr-reviewer verified within-ticket unit behavior; neither traced the
  cross-file contract (ticket 02 delivers `tier` on all hooks → ticket 04
  reads it) to confirm the consuming side could actually reach the data.

- **WORKFLOW TOOL INCOMPATIBILITY — build-epic.js and finalize-feature.js.**
  Both workflow entry points failed the Claude Code Workflow tool validator
  because their `export const meta` blocks use string concatenation
  (a `BinaryExpression`) in the description field; the validator requires a
  pure string literal. Both drove fell back to manual / agent dispatch paths.
  This forced manual coordinator work that should have been automated.

- **SUBAGENT CONFIRMATION-GATE DEADLOCK (highest-value process finding).** The
  `commit` agent, `finalize-feature` agent, and `worktree-agent` all refuse
  to accept a confirmation relayed via SendMessage from a dispatching
  coordinator ("coordinator message carries no user authority"). As subagents
  they have no direct user-turn channel, so every destructive confirmation gate
  (git commit, PR merge, worktree removal) dead-ended. The coordinator had to
  complete those steps directly with raw git/gh commands, bypassing the safety
  gates those agents exist to provide. This makes gated agents effectively
  unusable when dispatched as subagents.

- **COMMIT AGENT IGNORES EXPLICIT STAGING CONSTRAINTS.** During epic close-out
  the commit agent swept unrelated untracked/modified files into the index via
  its "stage all in-scope" sweep, despite explicit per-file staging instructions.
  The status-checker had to unstage 3 times before a clean commit. This is a
  real commit-pollution risk when the checkout has pre-existing uncommitted work
  from adjacent activities.

- **STALE .build-feature.lock blocked a planning agent.** A stale lock file
  (dead PID) blocked a planning agent's writes via inline_work_guard. Required
  manual clearance. Minor friction but detectable with a PID-liveness check.

- **PRE_COMMIT_ALLOW_NO_CONFIG=1 required in worktree.** Commits in the
  EPIC-PrecommitSafetyNet worktree required `PRE_COMMIT_ALLOW_NO_CONFIG=1`
  because `.pre-commit-config.yaml` lives only in the main repo root, not in
  worktrees. Noted in ticket-03 and ticket-05 commit comments. Not a blocker,
  but undocumented and surprising the first time.

## Knowledge Gaps Found

- **Cross-file contract tracing is not part of the ac-validator / pr-reviewer
  scope.** When ticket 02 delivers data that ticket 04 consumes, neither agent
  checked whether the consumer could actually reach that data at runtime.
  The gap was only found by a post-merge integration check.

- **The confirms-gate pattern for subagents is undocumented.** There is no
  convention for how a coordinator passes "user sanctioned this" authority to
  a gated subagent. The absence of this pattern forces coordinators to bypass
  gated agents entirely.

- **Workflow tool meta literal requirement is undocumented.** The constraint
  that `export const meta.description` must be a pure string literal (no
  concatenation) is not stated anywhere in the leafcutter authoring guides.

- **Lock file age-out / PID-liveness check is unimplemented.** The
  inline_work_guard lock mechanism has no automatic detection of stale locks.

## Subagent Quality Trends

No supervisor feedback entries found for this epic (supervisors may pre-date
EPIC-SupervisorFeedback or no adjudication events occurred during this drive).
The feedback corpus contains 49 entries but none are tagged `subagent-quality`
for this epic.

---

## Proposed Improvements

### KI-1: Cross-file contract tracing in AC validation

**Problem:** ticket-04 shipped done (green unit tests, ac-validator ok) but
broke in integration because it read tier data from a `hooks_manifest` entry
that ticket-02's AC-5 never actually populated for 4 of the 7 hook IDs.
Neither ac-validator nor pr-reviewer traced the `delivers_to` / `expects_from`
contract across ticket boundaries.

**Proposed Knowledge Item:**

```
When a ticket's AC has a delivers_to / expects_from contract linking two
tickets, pr-reviewer and ac-validator must verify the cross-file contract:
confirm that the consumer ticket's code can reach the data the producer
ticket claimed to deliver. Specifically: for each "delivers to" AC entry,
open the consuming file and verify the data path exists — do not rely only
on within-ticket unit tests that mock the dependency.
```

Routing: `templates/agents/pr-reviewer.md` and `templates/agents/ac-validator.md`
(instruction addition to the review rubric).

Note: `.agents/rules/` is being retired; route-learning selects the agent
template as the correct destination instead.

---

### KI-2: Subagent confirmation-gate authorization token

**Problem:** Gated agents (`commit`, `worktree-agent`, `finalize-feature`)
refuse to accept confirmation relayed via SendMessage from a coordinator.
When dispatched as subagents they have no direct user-turn channel, so every
destructive gate dead-ends. The coordinator is forced to run raw git/gh
commands, bypassing the safety gates entirely.

**Proposed fix direction:** Introduce an authorization token / flag the
dispatcher can pass that the agent accepts as coordinator-sanctioned. Analogous
to the existing `COMMIT_AGENT_MODE=1` env var and the `via: /build-feature`
marker already in use. For example:

```yaml
# coordinator passes in dispatch payload:
authorization: { granted_by: "coordinator", action: "commit", ticket: "..." }
```

The gated agent checks for this token and, when present and well-formed,
treats it as user-sanctioned without requiring an interactive "yes".

**Proposed Knowledge Item (interim, until the token is implemented):**

```
Gated agents (commit, worktree-agent, finalize-feature) refuse confirmation
relayed via SendMessage from a coordinator subagent. When dispatching these
agents as subagents, the coordinator must either (a) pass the required
COMMIT_AGENT_MODE=1 / equivalent authorization token in the dispatch payload,
or (b) complete the destructive step directly (raw git/gh) and document why
the gate was bypassed. Never silently bypass — always log the bypass reason
in a ticket comment.
```

Routing: `templates/skills/building-epics/SKILL.md` (dispatch guidance
section) and `docs/architecture/agent_delivery_workflows.md`.

---

### KI-3: Workflow tool meta must be a pure string literal

**Problem:** `build-epic.js` and `finalize-feature.js` use string
concatenation in `export const meta.description`, which fails the Claude Code
Workflow tool validator. Both fell back to manual paths.

**Proposed rule update (diff):**

```diff
--- a/docs/how-to/authoring-workflow-scripts.md (or equivalent guide)
+++ b/docs/how-to/authoring-workflow-scripts.md
@@ workflow meta authoring @@
-export const meta = {
-  description: "Part one " + "part two",   // allowed
-};
+export const meta = {
+  description: "Part one part two",         // REQUIRED: pure string literal only
+  // NEVER use string concatenation, template literals, or BinaryExpression
+  // in the description field — the Workflow tool validator rejects non-literals.
+};
```

If no authoring guide exists yet, this rule should be added to:
`templates/skills/building-epics/SKILL.md` under the "workflow entry points"
section, or a new `docs/how-to/authoring-workflow-tools.md`.

Routing: `docs/how-to/authoring-workflow-tools.md` (new, or existing if present).

---

### KI-4: Commit agent staging scope constraint

**Problem:** The commit agent swept unrelated untracked/modified files into the
index despite explicit per-file staging instructions. Required 3 unstage cycles.

**Proposed rule update (diff):**

```diff
--- a/templates/agents/commit.md
+++ b/templates/agents/commit.md
@@ Step 1 — Stage files @@
-Stage all in-scope files listed in the ticket's files_touched.
+Stage ONLY the specific files named in the coordinator's dispatch payload or
+the ticket's files_touched list. Do NOT run `git add .` or `git add -A`.
+Run `git status` first; if untracked or modified files exist outside the
+named set, log them and exclude them. If uncertain, return status: question
+listing the unexpected files rather than staging them.
```

Routing: `templates/agents/commit.md` (staging step instruction).

---

### KI-5: Lock file age-out / PID-liveness detection

**Problem:** A stale `.build-feature.lock` with a dead PID blocked a planning
agent's writes via inline_work_guard.

**Proposed Knowledge Item:**

```
The inline_work_guard lock mechanism should check whether the PID recorded in
the lock file is still alive before blocking. If the PID is dead, treat the
lock as stale and clear it automatically with a logged warning. Maximum lock
age: 4 hours regardless of PID state.

Detection command (single invocation):
  kill -0 <pid>     # exit 0 if alive, exit 1 if dead
```

Routing: The inline_work_guard implementation (if Python: the script that
reads/writes `.build-feature.lock`); and a note in the pre-drive checklist in
`CLAUDE.md` under the "Pre-Drive Checklist" section.

---

### KI-6: PRE_COMMIT_ALLOW_NO_CONFIG=1 required in worktrees

**Problem:** Worktrees lack `.pre-commit-config.yaml` (it lives only in the
main repo root). Commits from worktrees require `PRE_COMMIT_ALLOW_NO_CONFIG=1`
or they error. This was undocumented and surprised agents on first encounter.

**Proposed addition to Pre-Drive Checklist in CLAUDE.md (diff):**

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ Pre-Drive Checklist @@
+### Worktree pre-commit config
+
+Worktrees do not inherit `.pre-commit-config.yaml` from the main working tree.
+All git commits issued from inside a worktree must set the environment variable:
+
+```bash
+PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "..."
+```
+
+The `commit` agent handles this automatically when dispatched from a worktree
+context; manual commits (e.g. raw git during coordinator close-out) must set
+it explicitly.
```

Routing: `leafcutter-ai/CLAUDE.md` Pre-Drive Checklist section.

---

*All proposed changes above are presented as diffs/KI text for user approval.
No file has been modified. Type "yes" to apply each item, "skip" to skip, or
"edit" to revise.*
