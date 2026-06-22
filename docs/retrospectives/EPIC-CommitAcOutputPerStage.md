---
description: Retrospective for EPIC-CommitAcOutputPerStage (ACD-300g)
epic: EPIC-CommitAcOutputPerStage
date: 2026-06-22
---

# Retrospective: EPIC-CommitAcOutputPerStage
Date: 2026-06-22
Epic duration: 2026-06-18 to 2026-06-22
PR: #114

## Summary

This epic implemented ACD-300g: each stage's AC output is committed to git before
the /plan-feature workflow advances to the next authoring agent. Six leaf-AC tickets
(01-06) were generated from the ACD-300g family via goal_to_epic.py and driven to
`status: done` with all phase-agent sign-offs green. A post-build spot-check run on
2026-06-22 — three independent angle-testing agents — found the feature DID NOT WORK
as-built, producing a rare high-signal "phantom-done" failure that escaped six
supervisors and the PR reviewer.

The root cause split across four independent defects: the commit step dispatched a
`status-checker` agent that instructed it to run raw `git commit`, which the
`enforce_commit_delegation` hook blocks at runtime; ticket 04's partial-run recovery
was written as SKILL.md prose (not executable code) because `files_touched` pointed at
SKILL.md and ADRs; staging was silently broken for fresh AC stores (untracked-file
invisibility) and for prefix-nested AC IDs; and the final gate's `|| "edit"` condition
let edit-after-exhaustion auto-approve and commit unreviewed ACs.

Four remediation tickets (07-10) were authored on 2026-06-22 targeting the real
integration point (`scripts/workflows/plan-feature.js`), using vm.Script behavioral-replay
tests instead of string scans. A re-verification spot-check confirmed all five issues
fixed across 54 behavioral tests.

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 10 (6 original + 4 remediation) |
| Completed tickets | 10 |
| Source AC | ACD-300g |
| Implementation PR | #114 |
| Git commits (epic-related) | ~12 (original + remediation + sign-off commits) |
| Blocker comments | 0 (no `status: blocker` in any ticket) |
| Handoff comments | 0 (no `status: handoff` in any ticket) |
| submit-failed events | 2 (tickets 06, 10 ticket-supervisor comments: `(submit-failed)`) |
| Pre-commit autofix cycles | 4 (feedback-id and IO-001 fixes across commits) |

## Category Breakdown (Feedback System)

No structured feedback entries exist in feedback.jsonl for this epic. The epic was
outside the feedback system epoch for this drive. Ticket-level `## Comments` sections
were used as the primary data source.

## Phase Agent Counts (from ticket frontmatter)

| Phase | Signed Off | Failed | Needed |
|-------|-----------|--------|--------|
| python-coder | 10 | 0 | 0 |
| test-writer | 10 | 0 | 0 |
| test-runner | 10 | 0 | 0 |
| pr-reviewer | 10 | 0 | 0 |
| commit | 10 | 0 | 0 |
| pull-request | 10 | 0 | 0 |
| documentation-expert | 0 | 0 | 10 (not_needed) |
| sql-coder | 0 | 0 | 10 (not_needed) |

Note: The phase counts above are all `signed_off` because the phantom-done mechanism
meant the original 6 tickets reached `status: done` with false-green sign-offs. The
remediation tickets (07-10) were authored with correct `files_touched` and passed
genuine behavioral tests. The table does NOT distinguish original-6 from remediation-4
because frontmatter shows the same outcome for both sets.

## What Went Well

- Zero structural blockers across all 10 tickets — no `status: blocker` or
  `status: handoff` comments in any ticket.
- The post-build spot-check mechanism worked exactly as intended: three independent
  angle-testing agents caught five defects that six in-loop supervisors and PR review
  all missed. This is strong confirmation that the BO-1300 spot-check automation epic
  is justified.
- Remediation tickets (07-10) used vm.Script behavioral-replay tests (not string scans),
  which gave genuine RED baselines that turned GREEN after fixes. 54 behavioral tests
  now provide ongoing regression protection.
- All four remediation tickets pointed at the correct integration point
  (`scripts/workflows/plan-feature.js`) and kept `scripts/` and `templates/` byte-identical
  throughout. Template parity was tested mechanically in each ticket.
- The `enforce_commit_delegation` hook correctly identified the commit-delegation defect
  when the spot-check agent attempted to simulate runtime execution — the hook did its job.
- Commit autofixes (feedback-id additions, IO-001 wrapping) resolved within the
  mechanical retry cycle without escalating to the user.
- Tickets 07-10 correctly depended on their predecessors (07 before 09, 05+06 before 10),
  preventing the remediation batch from introducing new ordering issues.

## Friction Points

- **Phantom-done (headline finding — tickets 01-06, discovered 2026-06-22):** All six
  original tickets reached `status: done` with green sign-offs, but none of the behavior
  specified in the ACs existed in the runtime. See "Phantom-Done Anatomy" below for the
  full breakdown. No single `status: blocker` was ever recorded.

- **files_touched seeded the wrong target (ticket 04 root cause):** goal_to_epic.py
  derives `files_touched` from `doc_links` in the AC store entry. ACD-300g-2-i's
  `doc_links` pointed at SKILL.md and ADRs. The coder correctly wrote to `files_touched`,
  producing a §PRR (Partial-Run Recovery) section in `templates/skills/create-ac/SKILL.md`
  — correct for documentation but entirely absent from the executable workflow.
  Ticket-supervisor, pr-reviewer, and the unit tests all passed because SKILL.md changes
  look like a legitimate completion. See Proposed Improvement KI-1.

- **String-scan tests passed on phantom implementations:** The original tests for
  tickets 01-03 were either skipped ("docs-only" classification, test-writer phase
  skipped) or were string-scan checks against plan-feature.js. String scans confirm
  that certain text is present in the source file, but they do not prove the code
  executes correctly at runtime. The commit-delegation defect, the fail-open coercion,
  the untracked-file invisibility, and the final-gate edit-fallthrough all survived
  string-scan regimes. See Proposed Improvement KI-2.

- **"Docs-only" test skip on executable-behavior tickets (tickets 01-06):** The
  ticket-supervisor comment on tickets 01, 02, 03, 04, 05, 06 all read "test_requirements
  empty — test-writer phase skipped (docs-only or config-only ticket)." The tickets were
  behaviorally significant — they modified `commitStageOutput()` in plan-feature.js —
  but because the test-requirements block was empty (generated by goal_to_epic.py
  without behavioral test requirements), the test-writer was skipped and no behavioral
  tests were created in the first place. See Proposed Improvement KI-3.

- **Two `(submit-failed)` events:** Tickets 06 and 10 both have `feedback-id:
  (submit-failed)` in their ticket-supervisor comment headings. This is a recurrence of
  the telemetry sink issue documented in TICKET-20260527-FeedbackSinkPreDriveCheck.
  The pre-drive checklist item "Feedback sink reachable" was either skipped or the sink
  became unreachable mid-drive.

- **Commit-message subject used retired `create-ac(` prefix (ticket 05):** The commit
  message format was introduced in ticket 05 using the old command name `create-ac`
  rather than `plan-feature`. This was caught as a LOW finding in the post-build
  spot-check and corrected in ticket 10. The in-loop pr-reviewer on ticket 05 noted the
  spec ambiguity around the `"final"` stage label but accepted it as non-blocking; the
  retired prefix was not flagged at all.

## Phantom-Done Anatomy

The headline finding of this epic deserves a dedicated section. The original 6 tickets
all reached `status: done` but shipped a feature that could not execute:

| Defect | Affected AC | Root Cause | Detection |
|--------|------------|------------|-----------|
| commitStageOutput() instructs status-checker to run raw `git commit` — blocked by enforce_commit_delegation at runtime | ACD-300g-1 | Wrong agent dispatched in commit step; hook would block every real invocation | Spot-check agent 1 |
| Fail-open coercion: unparseable result mapped to `{status:"ok"}` | ACD-300g-1-i | Result-coercion catch block defaulted to success | Spot-check agent 1 |
| Partial-run recovery written as SKILL.md prose only (ticket 04 phantom-done) | ACD-300g-2-i | files_touched pointed at SKILL.md; coder wrote prose, not code | Spot-check agents 2 + 3 + grep |
| Untracked AC files invisible: `git status --porcelain` collapses untracked dir to one `?? dir/` line | ACD-300g-2 | Missing `--untracked-files=all` flag | Spot-check agent 2 |
| AC-ID match was substring (prefix false-match): `written=["ACD-300"]` staged `ACD-300g.yaml` | ACD-300g-2 | "matches" prose not specifying exact equality | Spot-check agent 2 |
| Final-gate `|| finalAction === "edit"` auto-approved and committed unreviewed ACs | ACD-300g-4 | Inclusive condition in approval branch | Spot-check agent 3 |

**Why it escaped in-loop review:** All original tests were either string-scans (confirm
text is present in the source) or were skipped entirely (test_requirements empty). No
test asserted that `commitStageOutput()` produced a commit via the correct agent,
that the coercion block was fail-closed, or that the staging discovery used
`--untracked-files=all`. The in-loop pr-reviewers reviewed the diff against the
acceptance criteria text and found structural consistency — the code LOOKED like it
satisfied the AC. Only runtime execution (or a behavioral replay test) would expose
the defects.

## Knowledge Gaps Found

1. **files_touched on an executable-behavior AC must point at the workflow script,
   not documentation.** goal_to_epic.py copies `doc_links` into `files_touched`
   verbatim. For ACs that modify runtime behavior, the real target (e.g.
   `scripts/workflows/plan-feature.js`) must appear in `files_touched`. If it doesn't,
   the coder writes to the wrong surface and the feature ships absent from the runtime.

2. **String-scan tests cannot verify runtime behavior.** A string scan confirms textual
   presence but not execution correctness. The vm.Script behavioral-replay pattern
   (established in tickets 07-10) should be the default for any AC that adds or modifies
   JavaScript workflow logic.

3. **The "docs-only" test-skip is a false negative for workflow-modifying tickets.**
   When goal_to_epic.py generates a ticket whose `test_requirements` block is empty
   (typical for doc-link-derived tickets), ticket-supervisor skips the test-writer.
   For tickets that ultimately modify executable code, this skip removes the primary
   behavioral safety net.

4. **Post-epic spot-check agents catch defects that in-loop supervisors reliably miss.**
   Six independent supervisor chains all passed the phantom implementation. Three
   spot-check agents found five defects in one pass. The angle-testing (adversarial,
   behavior-from-the-outside) stance is qualitatively different from the in-loop
   "does this look like it satisfies the AC" review.

5. **enforce_commit_delegation scope:** Workflow code that needs to commit must
   dispatch the `commit` agent (or operate under `COMMIT_AGENT_MODE=1`). Instructing a
   non-commit agent to run `git commit` directly is always wrong in any properly-configured
   install. This requirement was not documented at the point where workflow coders
   implement commit steps.

## Subagent Quality Trends

No supervisor feedback entries found for this epic (supervisors may pre-date
EPIC-SupervisorFeedback or no adjudication events occurred during this drive; all
tickets reached status: done without `status: blocker` escalations in the ticket
comment log).

---

## Proposed Improvements

### KI-1: files_touched must include the executable integration point for behavior ACs

**Proposed Knowledge Item text:**

When a ticket implements an AC that changes runtime behavior (adds a function call,
modifies a workflow step, changes execution logic), `files_touched` MUST include the
executable file (e.g. `scripts/workflows/plan-feature.js`), not just documentation
or skill files. If `files_touched` lists only SKILL.md, ADRs, or diagrams, the
assigned coder will write exclusively to those surfaces and the behavior will not
exist at runtime. The resulting `status: done` is a phantom-done — green sign-offs
on a feature that does not run.

This pattern is seeded by `goal_to_epic.py` copying `doc_links` from the AC store
entry into `files_touched`. When reviewing generated tickets before a drive, verify
that every ticket whose AC modifies runtime behavior names the runtime file in
`files_touched`.

**Routing:** `docs/conventions/` — specifically a new section or entry in
`docs/how-to/` under ticket-authoring conventions, or as a note in the
pre-drive checklist in `CLAUDE.md`. The refinement agent is the correct enforcement
point (five-lens pass, lens 1: `files_touched` completeness).

**Diff for user approval:**

```diff
--- a/docs/how-to/  (new entry, or addendum to existing ticket-authoring how-to)
+++ b/docs/how-to/ticket-authoring/files_touched_for_behavior_acs.md  (new)
+ ## Rule: files_touched must name the executable surface for behavior ACs
+
+ When an AC's acceptance criterion describes runtime behavior (a function is called,
+ a workflow step executes, an error is surfaced to the user), the implementing file
+ must be the runtime artifact — not documentation, skill prose, or ADRs.
+
+ goal_to_epic.py derives files_touched from doc_links. doc_links are documentation
+ references, not implementation targets. Before starting any drive, verify:
+
+   - Every ticket that modifies execution logic lists the workflow script
+     (e.g. scripts/workflows/plan-feature.js) in files_touched.
+   - If files_touched lists only SKILL.md / ADRs / diagrams for a behavioral AC,
+     correct it before dispatching the coder — not after the coder signs off.
+
+ The refinement agent enforces this at ticket-creation time (five-lens, lens 1).
+ Ticket-supervisor must also flag it during the "read ticket" step before dispatching
+ the first coder.
```

---

### KI-2: Prefer vm.Script behavioral-replay tests over string scans for workflow code

**Proposed Knowledge Item text:**

String-scan tests (grep/assertIn over source text) confirm that certain text is present
in a source file but do not prove the code executes correctly. For JavaScript workflow
code in `scripts/workflows/`, prefer vm.Script behavioral-replay tests that:

1. Extract the target function body from the source file at test time (using a regex
   or structured extraction).
2. Execute it via `vm.Script` in a mocked context (mock agent dispatcher, mock git
   subprocess).
3. Assert the runtime return value or side effect (e.g. `status: "error"` on bad
   input, correct `agentType` on the dispatch call).

The vm.Script pattern was established in tickets 07-10 of EPIC-CommitAcOutputPerStage.
Reference test files: `unit_tests/test_commit_stage_output_behavioral.py`,
`unit_tests/test_commit_stage_output_staging.py`, `unit_tests/test_partial_run_recovery.py`,
`unit_tests/test_final_gate_and_commit_message.py`.

When test-writer is dispatched for a ticket that modifies JavaScript workflow logic,
the test requirements block must specify vm.Script behavioral tests, not string scans.
The "docs-only / config-only" skip classification must not apply to tickets that
modify executable `.js` workflow files.

**Routing:** `docs/how-to/` or `templates/skills/building-epics/SKILL.md` test-requirements
section. Also a candidate for a pre-commit hook guard (flag when a new JS workflow
function is added without a corresponding behavioral test file).

**Diff for user approval:**

```diff
--- a/templates/skills/building-epics/SKILL.md
+++ b/templates/skills/building-epics/SKILL.md
@@ (test-writer dispatch section)
-   test-writer phase is skipped when test_requirements.tests is empty.
+   test-writer phase is skipped when test_requirements.tests is empty.
+   EXCEPTION: a ticket is never classified as "docs-only" if files_touched contains
+   a .js file under scripts/workflows/ or templates/workflows-js/. For JavaScript
+   workflow files, the test-writer must write at least one vm.Script behavioral-replay
+   test asserting the runtime behavior of the modified function. String-scan tests
+   (grep/assertIn over source text) are not sufficient — they do not detect runtime
+   defects such as wrong agentType dispatch, fail-open coercion, or missing flags.
```

---

### KI-3: Post-epic angle-testing is a required finalization step for behavioral epics

**Proposed Knowledge Item text:**

For epics that implement executable behavior (workflow steps, commit logic, AC authoring
pipeline changes), the finalization sequence must include a post-epic spot-check phase
with at least two independent angle-testing agents. These agents approach the feature
from the outside — attempting to invoke it, checking what happens at runtime, and
probing edge cases — rather than reviewing the diff against the AC text.

EPIC-CommitAcOutputPerStage is the canonical example: six in-loop supervisors and a
PR reviewer all missed five defects that three spot-check agents found in one pass.
The in-loop review answers "does this diff look like it satisfies the AC text?" The
spot-check answers "does this feature actually work when executed?"

Angle-testing stances proven effective:
- Simulate runtime execution of the modified function with mocked dependencies.
- Grep for banned patterns (e.g. raw `git commit` in agent instructions dispatched by
  the workflow).
- Attempt to invoke the workflow and observe what the commit-delegation hook does.
- Inspect `files_touched` vs the actual commit diff — do the committed files include
  the runtime target?

This evidence base supports the BO-1300 spot-check automation epic as a high-priority
deliverable.

**Routing:** `docs/how-to/` finalization checklist, or as an explicit step in
`templates/skills/finalize-feature/SKILL.md` (if it exists) or the `/finalize-feature`
agent template. Also candidate for a required phase in epic-supervisor's ticket graph
for behavioral epics.

**Diff for user approval:**

```diff
--- a/CLAUDE.md  (Pre-Drive Checklist section, or a new Post-Drive section)
+++ b/CLAUDE.md
+## Post-Drive Checklist (behavioral epics)
+
+After all epic tickets reach status: done, before closing the PR:
+
+1. **Angle-testing spot-check (MANDATORY for epics that modify executable code):**
+   Dispatch at least two independent spot-check agents with angle-testing briefs —
+   agents that attempt to invoke the feature from the outside, probe edge cases, and
+   check runtime behavior rather than reviewing the diff for textual AC coverage.
+
+   Minimum checks:
+   - Does the modified function dispatch the correct agent type?
+   - Does the modified function fail closed on bad input (not succeed silently)?
+   - Do the behavioral tests exercise the function at runtime (vm.Script), not just
+     scan for text in the source file?
+   - Is the implementation present in the runtime file (not only in SKILL.md or ADRs)?
+
+2. Record spot-check findings in the retrospective before the PR merges.
+   If defects are found, open remediation tickets before closing.
```

---

### KI-4: enforce_commit_delegation scope must be documented for workflow coders

**Proposed Knowledge Item text:**

Any code in `scripts/workflows/` that needs to perform a git commit must dispatch the
`commit` agent (agentType: "commit"), not instruct another agent (e.g. status-checker)
to run `git commit` directly. The `enforce_commit_delegation` PreToolUse hook blocks
any `git commit` call not originating from the `commit` agent with `COMMIT_AGENT_MODE=1`.

This means: a workflow step that says "instruct the status-checker agent to run: git
commit -m ..." will fail silently or with a hook error on every properly-configured
install. The correct pattern is to dispatch agentType: "commit" with a pre-built
commit message and let the commit agent execute the commit through its standard flow.

The commit agent's SKILL.md documents the sanctioned path. When reviewing workflow code
that introduces a commit step, the pr-reviewer must explicitly check that agentType is
"commit" (not "status-checker" or any other agent) and that no raw `git commit` command
appears in the agent instructions.

**Routing:** `docs/conventions/` or inline in `templates/agents/commit.md` as a
caller-contract section. Also a candidate for a pre-commit hook that scans
staged `.js` workflow files for `agentType.*status-checker` near a `git commit` string.

**Diff for user approval:**

```diff
--- a/docs/conventions/  (new file or addendum to commit-delegation convention)
+++ b/docs/conventions/workflow-commit-delegation.md  (new)
+ ## Commit Delegation in Workflow Scripts
+
+ Workflow scripts (scripts/workflows/*.js, templates/workflows-js/*.js) that perform
+ git commits must dispatch the commit agent — they must NOT instruct another agent to
+ run git commit directly.
+
+ **Wrong** (blocked by enforce_commit_delegation hook at runtime):
+ ```javascript
+ // Inside commitStageOutput() — DO NOT DO THIS:
+ agentInstructions: `Run: git commit -m "${message}"`
+ agentType: "status-checker"
+ ```
+
+ **Correct** (hook-safe):
+ ```javascript
+ agentType: "commit"
+ // Let the commit agent use its standard flow with the pre-built message
+ ```
+
+ The enforce_commit_delegation PreToolUse hook will block the wrong pattern on every
+ run in a properly-configured install. The pr-reviewer must check agentType at commit
+ steps. See EPIC-CommitAcOutputPerStage ticket 07 for the canonical fix.
```
