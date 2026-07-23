# Retrospective: EPIC-InFlightVisibility
Date: 2026-07-23
Epic duration: 2026-07-20 to 2026-07-23
Merged: PR #360, commit 8c3b43f3

## Summary

EPIC-InFlightVisibility delivered AC BO-1000 — verbose in-flight progress narration for the finalize
workflow. The 16 tickets implemented four coherent layers: start-of-step narration (BO-1000a-1/a-2/a-3,
with error-path and counting edge cases), per-step outcome recording and end-of-run recap
(BO-1000b-1/b-2/b-3 and halt variants), a durable run-progress journal written incrementally
to disk (BO-1000c-1a), and a launcher poll-and-relay protocol that surfaces live lines into
the main conversation (BO-1000c-1b/c-2/c-2-i). Two Mermaid architecture sequence diagrams
(BO-1000a-4, BO-1000c-3) document the end-to-end emission and relay paths.

The epic ran over 4 calendar days against a heavily-contested main branch. Environmental
disruptions (multiple background-build kills, a Portkey API quota halt, a git shadow-object
corruption) required repeated recoveries and left the drive fragmented. A real runtime
duplicate-outcome bug (BO-1000b-1-i) was caught only by code-review + logic-check — static
regex tests were blind to it because they did not account for template-literal quoting. An
origin/main merge silently dropped two hardened deploy-parity guards; caught by re-review at
finalize. A finalize step-3.5 false-success left 7 of 16 ticket frontmatter entries at
`status: todo` despite implementation being complete and merged.

## Metrics

| Phase | Signed Off | Failed | Needed |
|-------|-----------|--------|--------|
| python-coder | 11 | 0 | 0 |
| test-writer | 11 | 0 | 0 |
| test-runner | 11 | 0 | 0 |
| pr-reviewer | 13 | 2 | 1 |
| commit | 15 | 1 | 0 |
| pull-request | 14 | 1 | 1 |
| llm-expert | 3 | 0 | 0 |
| architecture-diagram-author | 2 | 0 | 0 |

Notes: pr-reviewer failures on tickets 07 (BO-1000b-1) and 08 (BO-1000b-1-i); commit
failure on ticket 08; pull-request blocker on ticket 08; pull-request still-needed on
ticket 12 (BO-1000c-1a). `aggregate.py` is absent from the project (only
`submit_feedback.py` present in `scripts/feedback/`), so structured category breakdowns
are not available; counts above are derived from ticket-file Comments parsing.

## Category Breakdown (Feedback System)

No structured feedback available for this epic — `aggregate.py` is absent from
`scripts/feedback/`. Individual agent comments show a mix of `status: ok` and
`status: blocker` tags; no `knowledge-gap` or `convention-ambiguity` entries were
explicitly tagged. Quantitative breakdown is unavailable.

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 16 |
| Completed tickets (all phases ok/pushed) | 14 |
| Tickets with frontmatter `status: done` | 9 |
| Tickets left `status: todo` by finalize closure-skip | 7 |
| Phase blocker comments | 3 (BO-1000b-1 pr-reviewer; BO-1000b-1-i pr-reviewer + commit + pull-request) |
| TDD order violations (coder before test-writer) | 1 (BO-1000a-3) |
| Runtime bugs caught only post-static-tests | 1 (BO-1000b-1-i duplicate outcome) |
| Ruff style-fix commits required post-drive | 2 (F541 f-string prefixes) |
| Merge-corruption events (origin/main merge dropping guards) | 1 |
| Environmental disruption recoveries | 3+ (multiple build-kills, Portkey 412, git shadow-object) |
| Git commits on branch (approx., including chore + merges) | ~36 |

## What Went Well

- **Python-coder, test-writer, test-runner: zero failures across 11 tickets.** The TDD
  cycle on the straightforward narration tickets (BO-1000a-1, BO-1000a-2, BO-1000b-2,
  BO-1000b-2-i, BO-1000b-3, BO-1000c-1a) proceeded cleanly with proper red baselines.

- **pr-reviewer caught two real blockers before merge.** BO-1000b-1's H-1 (contract shape
  mismatch: `executed|skipped` field absent from `step_outcomes`) and BO-1000b-1-i's H-1
  (duplicate outcome entries at runtime) were both surfaced by the review phase. Neither
  was caught by the test suite.

- **Architecture diagrams (BO-1000a-4, BO-1000c-3) passed frontmatter, parent-link, and
  mermaid hooks cleanly on first attempt.** The diagram-author correctly matched the
  `*-sequence.md` convention and established bidirectional `c2-006` parent links.

- **llm-expert tickets (BO-1000c-1b, BO-1000c-2, BO-1000c-2-i) landed without blockers.**
  The progress relay protocol, over-time delivery guarantee, and halt-flush protocol were
  all authored and reviewed without friction.

- **Origin/main merge corruption caught at re-review.** The guard-dropping merge was
  detected before the PR was approved. The fix (additive-only diff vs main) was applied
  cleanly.

- **Git shadow-object recovery succeeded.** The poisoned worktree cache-tree was repaired
  with `git read-tree HEAD`, and the drive resumed without losing work.

## Friction Points

- **FP-1 — BO-1000b-1-i: duplicate-outcome runtime bug invisible to static tests
  (tickets 08).** Python-coder added `outcome()` calls inside 7 skip-condition branches
  using template-literal first arguments, but left the pre-existing unconditional
  `outcome()` calls (using string-literal first arguments) in place after each if/else
  block. At runtime, any skipped step produced two `stepOutcomes[]` entries. The static
  test used a regex that matched only single/double-quoted first arguments; template
  literals were invisible to it. Three downstream phases (pr-reviewer, commit,
  pull-request) all recorded blocker status. A dedicated fix commit (`17735a2ed`) was
  required outside the original ticket phase.

- **FP-2 — BO-1000b-1: pr-reviewer failed on contract shape mismatch (ticket 07).**
  The `step_outcomes` record shipped as `{step, outcome}` instead of the
  `{position, step name, outcome text, executed|skipped}` shape declared in the
  Delivers To contract. Tests did not validate record shape. The commit phase proceeded
  with the blocker noted; the ticket frontmatter `pr-reviewer: failed` was never
  remediated, leaving it permanently marked failed.

- **FP-3 — BO-1000a-3: TDD order violation (ticket 05).** Python-coder pre-committed
  both the test file and the implementation in a single commit (`e47699abc`) before
  test-writer was dispatched. Test-writer received an already-green suite with no
  red baseline. The implementation was correct but the TDD guarantee was lost.

- **FP-4 — Finalize step-3.5 closure skip left 7 tickets status:todo.** The finalize
  workflow's step-3.5 detected "closure already present" and skipped the ticket-closure
  step, leaving tickets 02, 04, 05, 08, 12, 13, and one other at `status: todo` in their
  frontmatter despite all implementation being committed and pushed to the merged PR.
  This is a known finalize false-success (see project memory `project_finalize_step35_crossepic_closure.md`).

- **FP-5 — Origin/main merge silently dropped H-1/H-2 deploy-parity guards.** When
  origin/main was merged into the epic branch, git's 3-way merge dropped sections of
  `finalize-feature.js` that had been added on main for deploy-parity hardening. The
  merged result compiled and passed tests. The deletion was caught only by a fresh
  diff-vs-main at re-review.

- **FP-6 — Environmental disruptions fragmented the drive.** Multiple background build
  workflow kills (pull-request approval-gate stalls), a Portkey API 412 quota-exceeded
  halt, and a git shadow-object / poisoned cache-tree corruption each required manual
  recovery. Each kill left tickets in a committed-but-status:todo limbo; the re-drive
  had to skip already-committed tickets and re-run outstanding phases.

- **FP-7 — BO-1000a-2 STEP_COUNT declared but not referenced in calls (ticket 03).**
  The pr-reviewer noted that all 9 `narrate()` calls still embed `"9"` as a
  double-quoted string literal rather than referencing the `STEP_COUNT` constant. Tests
  passed because the test's `_NARRATE_BARE_LITERAL_PATTERN` targeted only single-quoted
  literals. Policy intent partially violated; drift risk remains if the step count changes.

- **FP-8 — Ruff F541 violations in test files required two post-drive style commits.**
  Extraneous f-string prefixes (`f""`) in `test_bo_1000a_1.py` and `test_bo_1000b_1_i.py`
  were not caught during per-ticket sign-off (worktree pre-commit hooks may not have been
  fully established), requiring post-drive fix commits (`9ce84ec00`, `1aa16d292`).

## Knowledge Gaps Found

- The skip-branch outcome-recording pattern (when adding outcome() to a skip branch,
  conditionalize vs. add) was not documented anywhere. Agents had to discover it through
  a blocker.

- The test-regex quoting-bias gap (static tests must account for all JS quote styles:
  single, double, and template literal) was not documented in any test-writer guidance.
  The gap directly caused FP-1 to pass all tests undetected.

- The post-origin/main-merge diff audit requirement (verify the merged result is
  additive-only before approving) was not in the Pre-Drive Checklist or any agent
  instruction. Relying on compile + test green as the signal for a clean merge is
  insufficient when the deleted content is a behavior guard.

- The finalize step-3.5 closure-skip behavior (when "closure already present" is detected,
  ticket status is not flipped) was known from earlier epics but not surfaced prominently
  enough to prevent it recurring. No post-drive cleanup protocol is documented in CLAUDE.md.

## Subagent Quality Trends

No supervisor feedback entries found for this epic — `aggregate.py` is absent from
`scripts/feedback/` (the file `submit_feedback.py` is present but the aggregation
script that produces the subagent-quality breakdown has not been deployed). No
adjudication event data is available.

## Unresolved Feedback

Unable to check — `aggregate.py` is not present at
`scripts/feedback/aggregate.py`. Unresolved feedback count cannot be determined
programmatically. Recommend reviewing `debugging/logs/feedback.jsonl` manually
before closing the epic branch.

---

## Proposed Improvements

### KI-1: Skip-Branch Outcome Recording — Conditionalize, Don't Add

**Proposed Knowledge Item text:**

When adding an `outcome()` call (or any result-recording call) inside a skip /
already-satisfied branch, first check whether an unconditional `outcome()` call
already exists *after* the if/else block for the same step. If one does, move the
unconditional call into the execute (else) branch only — do NOT add a second call
alongside the existing unconditional one. At runtime only one branch executes, so
two unconditional-style calls in separate branches produce duplicate entries in the
per-step outcome record.

Additionally, static tests that count or detect `outcome()` calls by regex must
match ALL JS quoting styles: single-quoted (`'...'`), double-quoted (`"..."`),
and template-literal (`` `...` ``). A regex limited to one quoting style is blind
to calls using the others, and a coder can unwittingly use a different style for
the new skip-branch call — making the test green while the duplicate exists at
runtime. Verify the fix behaviorally: trace the skip control-flow path and confirm
exactly one outcome entry is written per step.

(Source: EPIC-InFlightVisibility BO-1000b-1-i, 2026-07-22.)

**Routing:** Step 4 in route-knowledge decision tree — short universal project-wide
implementation rule, fits as a convention item in CLAUDE.md under Implementation
Conventions.

Route to: `CLAUDE.md-inline` → Implementation Conventions section of
`/home/henzeh/projects/leafcutter/leafcutter-ai/CLAUDE.md`

**Proposed diff for user approval:**

```diff
--- a/CLAUDE.md (Implementation Conventions section)
+++ b/CLAUDE.md
@@ ## Implementation Conventions
 
+### Skip-Branch Outcome Recording — Conditionalize, Don't Add
+
+When adding an `outcome()` call (or any result-recording call) inside a skip /
+already-satisfied branch, first check whether an unconditional `outcome()` call
+already exists *after* the if/else block for the same step. If one does, move the
+unconditional call into the execute (else) branch only — do NOT add a second call
+alongside the existing unconditional one. At runtime only one branch executes, so
+two unconditional-style calls produce duplicate entries in the per-step record.
+
+Static tests that count or detect calls by regex must match ALL JS quoting styles
+(single-quoted, double-quoted, template-literal). A regex limited to one style is
+blind to calls using the others, allowing a duplicate to pass all tests undetected.
+Verify behaviorally: trace the skip control-flow path and confirm exactly one outcome
+entry is written per step.
+
+(Source: EPIC-InFlightVisibility BO-1000b-1-i, 2026-07-22.)
+
```

---

### KI-2: Post-Origin/Main-Merge Diff Audit (Pre-Drive Checklist addition)

**Proposed Knowledge Item text:**

After merging `origin/main` into a long-lived epic branch, always run a diff of the
merged result against `origin/main` for key files and confirm the result is
additive-only (no lines from main were dropped). Git's 3-way merge can silently
drop sections when both sides modified the same region — the merged result can
compile and pass tests while missing behavior guards that were on main.

```bash
# Check that the epic branch only adds relative to main (no deletions):
git diff origin/main...EPIC-<name> -- <key-files> | grep '^-' | grep -v '^---'
```

Any deletion lines that are not offset by equivalent additions on the epic branch
are candidates for a silent merge-drop and must be reviewed before the PR is approved.

(Source: EPIC-InFlightVisibility — origin/main merge dropped H-1/H-2 deploy-parity
guards from finalize-feature.js; caught by re-review at finalize, 2026-07-23.)

**Routing:** Step 4 (CLAUDE.md-inline) — short checklist item for the Pre-Drive /
pre-merge section of CLAUDE.md. Already fits the existing Pre-Drive Checklist
pattern.

Route to: `CLAUDE.md-inline` → Pre-Drive Checklist section of
`/home/henzeh/projects/leafcutter/leafcutter-ai/CLAUDE.md`

**Proposed diff for user approval:**

```diff
--- a/CLAUDE.md (Pre-Drive Checklist section)
+++ b/CLAUDE.md
@@ ### Full test suite + ruff at epic-finalize (before merge)
 ... (existing content) ...

+### Post-origin/main-merge diff audit (before PR approval)
+
+After merging `origin/main` into a long-lived epic branch, always verify the merged
+result is additive-only relative to `origin/main` for the key files the epic modifies:
+
+```bash
+git diff origin/main...EPIC-<name> -- <key-files> | grep '^-' | grep -v '^---'
+```
+
+Any deletion lines that are not offset by equivalent additions on the epic branch are
+candidates for a silent merge-drop. Git's 3-way merge can silently drop behavior guards
+when both sides modified the same region — the merged result compiles and passes tests
+while the guard is gone. Review every unexpected deletion before approving the PR.
+
+**Why this matters:** During EPIC-InFlightVisibility (2026-07-23), an origin/main merge
+silently dropped two deploy-parity guards (H-1/H-2) from `finalize-feature.js`; caught
+only by a fresh diff-vs-main at re-review, after tests passed on the merged branch.
+
```

---

### KI-3: Finalize Closure-Skip Cleanup Protocol (memory-project)

**Proposed Knowledge Item text:**

The finalize workflow's step-3.5 ticket-closure step skips with "closure already present"
when a prior partial finalize run already created the closure commit. When this happens,
ticket frontmatter is NOT flipped from `status: todo` to `status: done` for any ticket in
the epic, leaving them permanently at `status: todo` despite implementation being complete
and merged.

After any finalize run, verify every ticket in the epic has `status: done` in its
frontmatter:

```bash
grep -r "^status: todo" tickets/00_inbox/epics/EPIC-<name>/
```

If any tickets show `status: todo` but all their phases are signed off and committed,
manually flip those frontmatter fields and commit the change on a clean branch
(not the already-merged epic branch).

**Routing:** Step 2 (memory-project) — project-scoped operational fact that persists
across sessions. Extends the existing `project_finalize_step35_crossepic_closure.md`
entry.

Route to: `memory-project` → append to
`/home/henzeh/.claude/projects/-home-henzeh-projects-leafcutter/memory/project_finalize_step35_crossepic_closure.md`

**Proposed diff for user approval:**

```diff
--- a/memory/project_finalize_step35_crossepic_closure.md
+++ b/memory/project_finalize_step35_crossepic_closure.md
@@ (existing content) ...

+**Post-finalize verification (MANDATORY):** After any finalize run, grep the epic
+folder for `status: todo` tickets:
+
+    grep -r "^status: todo" tickets/00_inbox/epics/EPIC-<name>/
+
+If any are found with all phases signed off and committed, the step-3.5 closure-skip
+occurred. Manually flip the frontmatter `status:` fields and commit on a fresh branch.
+Do NOT attempt to amend the already-merged epic branch.
+
+(Confirmed recurring: EPIC-InFlightVisibility 2026-07-23 — 7 tickets left status:todo
+after step-3.5 skipped "closure already present".)
+
```

---

### KI-4: Rule Update — TDD Order Must Be Enforced at Dispatch, Not Only at Sign-Off

**Proposed Knowledge Item text:**

The ticket supervisor must dispatch test-writer before python-coder, and must verify
a red baseline exists before authorizing the coder phase. If the coder has already
written tests as part of their implementation (commit includes both test + impl),
test-writer cannot produce a red baseline and the TDD guarantee is lost.

When test-writer finds tests already green on handoff:
1. Document in the comment that TDD was out-of-order (as BO-1000a-3 correctly did).
2. Confirm the tests are correctly specified (would fail if implementation were removed).
3. Record `tests_red_on_handoff: false` with reason in the completion manifest.
4. Do NOT mark the ticket as TDD-compliant — flag it for retrospective capture.

The supervisor must check that coder and test-writer commits are in the correct order
before signing off on the test-writer phase.

**Routing:** Step 7 (agent-frontmatter) — behavioral rule specific to the ticket-supervisor
dispatch flow.

Route to: `agent-frontmatter` → ticket-supervisor skill or the build-feature ops notes
at `/home/henzeh/projects/leafcutter/leafcutter-ai/.claude/skills/build-feature-ops-notes/`

**Proposed diff for user approval (CLAUDE.md Implementation Conventions entry):**

```diff
--- a/CLAUDE.md (Implementation Conventions section)
+++ b/CLAUDE.md

+### TDD Order — test-writer Must Precede python-coder
+
+The ticket supervisor must dispatch test-writer before python-coder. If the coder
+commits a test file in the same commit as the implementation, test-writer cannot
+establish a red baseline and the TDD guarantee is lost for that ticket.
+
+When test-writer receives an already-green suite:
+- Document the violation in the comment (`tests_red_on_handoff: false`).
+- Confirm the tests would fail if the implementation were removed.
+- Flag the ticket in the retrospective — do NOT mark it TDD-compliant.
+
+The supervisor must verify test-writer ran before python-coder in the git log
+before signing off on the test-writer phase.
+
+(Source: EPIC-InFlightVisibility BO-1000a-3, 2026-07-21.)
+
```
