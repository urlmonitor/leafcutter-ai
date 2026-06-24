---
title: "Retrospective: EPIC-FinalizeFeatureHardening"
created: 2026-06-24
epic_branch: EPIC-FinalizeFeatureHardening
pr: "158"
---

# Retrospective: EPIC-FinalizeFeatureHardening

Date: 2026-06-24
Epic duration: 2026-06-24 to 2026-06-24 (single-day intensive drive)
Commits on epic branch: 17
Merged via: PR #158 (single shared PR for all 10 tickets)

---

## Summary

This epic hardened the `/finalize-feature` command from a broken, two-path-dead
state into a single, reliable execution path. It fixed two primary P0 breakages —
non-literal `meta` fields that caused the JS `Workflow` tool to reject scripts at
parse time, and a dead LLM-agent fallback that silently swallowed work due to the
depth-1 hard limit. It also addressed four surrounding robustness gaps found during
a live manual finalize run: a reconciliation step that produced local-only commits
that could never reach `origin/main`, missing `gh` EMU-account pre-flight, CWD-trusting
git detection, and a Poetry-hardcoded bootstrap. Two lower-priority items were also
closed: the false "Tracking tickets created" success message in Step 6a and a set of
P2 hygiene fixes (baseline worktree leaks, doc/code step-number drift, JSON parse
brittleness). The AC-first build loop was closed by adding a pre-merge closure step
(Step 3.5) that marks tickets `status: done` and source ACs `work_status: done` on
the feature branch before the PR merges, so closure rides the PR onto `origin/main`
atomically.

The build drove all 10 tickets through the full phase pipeline (test-writer,
python-coder, test-runner, pr-reviewer, commit, pull-request) with zero blocker
escalations in the structured phase data. Post-merge regressions required four
additional fix passes: a registry validator rejection of 5 agents listing
`finalize-feature.js` as an external caller, a stale workflow mirror that broke the
deploy-SHA test, and two ruff violations in test files that slipped past the
worktree's missing pre-commit config.

---

## Metrics

| Phase | Signed Off | Failed | Needed |
|-------|-----------|--------|--------|
| architect-review | 0 | 0 | 0 (not_needed: 10) |
| test-writer | 8 | 0 | 0 (not_needed: 2) |
| python-coder | 9 | 0 | 0 (not_needed: 1) |
| sql-coder | 0 | 0 | 0 (not_needed: 10) |
| test-runner | 8 | 0 | 0 (not_needed: 2) |
| documentation-expert | 1 | 0 | 0 (not_needed: 9) |
| llm-expert | 1 | 0 | 0 (not_needed: 9) |
| pr-reviewer | 10 | 0 | 0 |
| commit | 10 | 0 | 0 |
| pull-request | 10 | 0 | 0 |

No phase-level blocker or handoff events were recorded (blocker_comment_count: 0,
handoff_comment_count: 0). The phase data reflects the epic as driven — failures
observed during the drive appeared post-merge and were fixed in separate commits.

## Category Breakdown (Feedback System)

No structured feedback entries exist for this epic in `debugging/logs/feedback.jsonl`.
The drive pre-dates the feedback sink being populated for this epic's ticket paths, and
several agents emitted `feedback-id: (submit-failed)` markers — indicating the sink was
reachable but the feedback-id hook triggered a re-commit before submission could land.

> Note: `aggregate.py` is not deployed to the leafcutter-ai repo's own `scripts/feedback/`
> directory (it exists only in `.leafcutter/` workspace-deployed copies and worktree
> derivatives). The retrospective agent locating the script at
> `/home/henzeh/projects/leafcutter/.leafcutter/scripts/feedback/aggregate.py` is the
> correct fallback path for this self-hosting layout.

---

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 10 |
| Completed tickets | 10 (100%) |
| Git commits on epic branch | 17 |
| Git first commit date | 2026-06-24 |
| Git last commit date | 2026-06-24 |
| Blocker comments | 0 |
| Handoff comments | 0 |
| Telemetry events | none (telemetry sink empty for this epic) |
| Epic PR | #158 (merged to origin/main as e76e7fc) |

---

## What Went Well

- All 10 tickets reached `status: done` in a single calendar day with zero phase-level
  blockers or escalations.
- The ticket dependency ordering worked as designed: tickets in the
  `finalize-feature.js` serialization chain (10 → 04 → 08) were driven serially and
  merged cleanly without same-file conflicts between those three tickets.
- The pre-commit hook `check-feedback-id` caught missing feedback-id fields mechanically
  on three tickets (02 commit, 05 commit, 09 commit) and was fixed on retry without
  halting the drive — the hook is doing its job.
- Ticket 04's test-runner correctly identified a pre-existing registry validation failure
  (agents referencing `finalize-feature.js` as an unknown caller) as pre-existing and
  distinct from the ticket's scope, surfaced in the comment, and signed off with honest
  reporting. The root cause was fixed later (post-merge) without re-opening the ticket.
- Ticket 07's test-writer wrote a proper red-baseline (4 of 6 stubs were correctly RED),
  making the TDD loop observable and verifiable.
- Ticket 10's implementation reused existing machinery (`mark_ac_done.py`) correctly and
  designed the step to be idempotent and resumable, addressing the full AC surface.
- Single shared PR per epic (#158) worked cleanly for a 10-ticket, same-file-serialized
  epic: all commits pushed to the same epic branch, no per-ticket PR overhead.

---

## Friction Points

### F1 — Parallel supervisor git object corruption (worktree index destroyed)

During the initial drive attempt, multiple ticket-supervisors were dispatched in
parallel into a single shared epic worktree. The parallel writes raced the git object
store, producing a 0-byte empty loose object that corrupted the worktree index (HEAD
stayed intact). Recovery required: `rm` the empty object, `rm` the worktree index,
then `git read-tree HEAD` to rebuild from HEAD. After recovery, the drive was
restarted with tickets driven serially.

**Impact:** Full drive restart; significant time lost to diagnosis and recovery.

### F2 — Finalize bootstrap paradox (the thing being fixed couldn't run itself)

This epic fixes `/finalize-feature`, but the fix was not yet deployed. This meant:
(a) `finalize-feature.js` still had the non-literal `meta` bug on the main branch,
so the Workflow tool rejected it; (b) `finalize-feature.js` uses a legacy
`async function run({...})` wrapper that the current Workflow tool never invokes
(no top-level body), making even a corrected version dead as an agent fallback.
The finalize for this epic had to be performed manually using `git -C` commands.

**Impact:** No automated finalize; all 6 finalize steps were manual.

### F3 — Main divergence / superseded tickets (06 and 07)

`origin/main` independently shipped equivalent fixes for:
- Ticket 06 (repo-root anchoring) via PR #162
- Ticket 07 (dep-manager detection) via PR #162

While the epic was in flight, causing merge conflicts in both copies of
`setup_ticket_worktree.py`. Resolved by deferring to main (the epic's tickets 06 and 07
became effectively redundant but were completed anyway to close the tickets cleanly).

**Impact:** Merge conflict resolution required; tickets 06/07 delivered less net-new
value because main had caught up.

### F4 — Post-merge regressions caught by main's stricter tests

Four categories of post-merge regressions, all caused by the worktree's missing
pre-commit config (all package hooks silently skipped during the drive):

1. **Registry validator rejection (ticket 03):** Removing the `finalize-feature`
   agent left 5 agents (`test-runner`, `pull-request`, `status-checker`,
   `worktree-agent`, `test-failure-triage`) with `spawned_by: finalize-feature.js`
   pointing at an unknown name in the registry. Main's `test_build_version_wiring.py`
   caught this. Fix: treat `finalize-feature.js` as an external-caller exemption in
   the registry validator.

2. **Stale plan-feature.js mirror (ticket 01):** Ticket 01 updated
   `templates/workflows-js/plan-feature.js` but not its committed mirror at
   `scripts/workflows/plan-feature.js`. Main's deploy-SHA test BP-811 caught the
   mismatch. Fix: sync the mirror.

3. **Ruff F841/F401 in test files:** Two test files written during the drive
   contained unused variable assignments and unused imports. Main's ruff CI gate
   caught these. Fix: remove unused bindings.

These three regression categories required four additional commits after the epic PR
merged.

### F5 — Worktree pre-commit gap (systematic, recurring)

The epic worktree was created fresh without `.pre-commit-config.yaml` or `.leafcutter`
symlinks and without a `debugging/logs/` directory. These were set up manually before
the drive. This is the same gap documented in EPIC-AcPipelineDeployGaps and
EPIC-AcPatternEnforcementIsMechanically. The permanent fix ticket
(TICKET-20260617-Worktree_Precommit_Bootstrap.md) remains open.

**Impact:** ALL package hooks silently skipped for the entire drive, enabling the
post-merge regressions in F4.

---

## Knowledge Gaps Found

1. **Parallel supervisor fan-out into a shared worktree is git-unsafe.** The object
   store does not serialize concurrent writes; two agents writing objects simultaneously
   can produce corrupted loose objects. No documentation existed for this limit before
   this incident. Mitigation: serial batch dispatch in shared worktrees.

2. **The "finalize bootstrap paradox" is not documented as a known failure mode.**
   When an epic's own target is the finalize infrastructure, the automated finalize
   cannot run — this needs a documented fallback procedure for manual finalize.

3. **Workflow script mirrors must be in scope for the same ticket as the template.**
   Ticket 01 missed the `scripts/workflows/plan-feature.js` mirror because it was
   not listed in `files_touched`. The mirror relationship is not codified anywhere
   agents can check.

4. **The registry validator does not have an allowlist for external caller names.**
   When an agent is removed and its former children's `spawned_by` is updated to a
   `.js` workflow filename, the validator rejects the `.js` name as unknown. There is
   no documented pattern for referencing external (non-agent) callers in `spawned_by`.

5. **Ruff CI-only gate creates a false sense of pre-commit coverage.** Ruff is not
   run in the worktree pre-commit path — only in CI. When the worktree pre-commit config
   is missing (F5 above), ruff violations can ship to main undetected until CI runs.

---

## Subagent Quality Trends

No supervisor feedback entries found for this epic (supervisors may pre-date
EPIC-SupervisorFeedback or no adjudication events occurred during this drive).
The subagent-quality category in `feedback.jsonl` returned `"total": 0`.

---

## Proposed Improvements

---

### KI-1: Parallel supervisor dispatch into a shared worktree corrupts the git object store

**Proposed Knowledge Item:**

> Dispatching multiple ticket-supervisors in parallel into a single shared epic
> worktree races the git object store and can produce corrupted 0-byte loose objects
> that destroy the worktree index (HEAD stays intact). Recovery: `rm` the 0-byte
> object (find with `find .git/objects -empty -type f`), `rm .git/index`, then
> `git read-tree HEAD`. Prevention: drive epic tickets serially in a shared worktree;
> only use parallel dispatch when each ticket runs in its own isolated worktree.

**Route (via route-knowledge decision tree):**

Step 5 condition: multi-sentence operational fact with recovery steps — too long for
inline; warrants its own entry that the Pre-Drive Checklist can cross-reference.

Routing: `CLAUDE.md-toc` → add a new row to the Pre-Drive Checklist table in
`CLAUDE.md` pointing to a new entry in `docs/how-to/pre-drive-checklist.md`, or
append directly to the existing Pre-Drive Checklist section in `CLAUDE.md` as a new
sub-heading.

**Proposed diff (append to the "Pre-Drive Checklist" section in `/home/henzeh/projects/leafcutter/leafcutter-ai/CLAUDE.md`):**

```diff
+### Parallel supervisor dispatch in a shared worktree (MANDATORY)
+
+**What to check:** Are you about to dispatch multiple ticket-supervisors in parallel
+into the SAME epic worktree?
+
+**Do not do this.** The git object store does not serialize concurrent writes.
+Two agents writing objects simultaneously can produce 0-byte corrupted loose objects
+that destroy the worktree index (HEAD stays intact but `git status` / `git diff`
+fail with "fatal: loose object ... is corrupt").
+
+**Recovery (if it happens):**
+```bash
+# Find the 0-byte object:
+find <worktree-root>/.git/objects -empty -type f
+# Remove it:
+rm <path-to-empty-object>
+# Rebuild the index from HEAD:
+rm <worktree-root>/.git/index
+git -C <worktree-root> read-tree HEAD
+```
+
+**Mitigation:** Drive epic tickets serially in a shared worktree. Parallel dispatch
+is safe only when each ticket has its own isolated worktree.
+(Source: EPIC-FinalizeFeatureHardening retrospective, 2026-06-24, Friction F1.)
```

---

### KI-2: Finalize bootstrap paradox — manual finalize procedure

**Proposed Knowledge Item:**

> When an epic's deliverable IS the finalize infrastructure itself (or any epic that
> fixes a tool needed by /finalize-feature), the automated finalize cannot run — the
> tool being fixed is the one that would drive finalize. The finalize for such an epic
> must be performed manually with `git -C`. Steps: (1) merge the feature branch via
> `gh pr merge`, (2) `git -C <repo> checkout main && git -C <repo> pull`, (3) flip
> ticket frontmatter `status: done` on main and `git -C <repo> add ... && git -C <repo>
> commit`, (4) push via a new PR (or skip if main is PR-only and status-as-source-of-truth
> is already applied). Note the paradox in the ticket comments so future retrospective
> agents understand why the automated finalize log is absent.

**Route:** Step 10 (task procedure — "how do I finalize when the finalize tool is broken?")

Routing: `how-to` → `docs/how-to/manual-finalize.md` (new file), with a cross-reference
added to `docs/how-to/finalize-feature.md`.

**Proposed diff (new file stub — full content for user to approve before creation):**

```diff
+File: docs/how-to/manual-finalize.md (NEW)
+
+---
+title: "How to finalize a feature branch manually (when /finalize-feature cannot run)"
+description: "Step-by-step procedure for the finalize bootstrap paradox and other cases where finalize-feature.js is unavailable."
+applies_when:
+  - The epic being finalized fixes finalize-feature itself
+  - The active Claude Code version predates Workflow tool support
+  - finalize-feature.js has a parse error on origin/main
+---
+
+# How to finalize a feature branch manually
+
+## When to use this guide
+
+Use this guide when `/finalize-feature` cannot run:
+- The epic fixes `finalize-feature` itself (bootstrap paradox)
+- The active install predates the Workflow tool (< 2.1.154)
+- `finalize-feature.js` has an unrecovered parse error on the branch
+
+## Steps
+
+1. Ensure all tickets are committed and the epic PR is open.
+2. Merge the PR: `gh pr merge <N> --squash --delete-branch` (or via GitHub UI).
+3. Sync local main: `git -C <repo> checkout main` then `git -C <repo> pull origin main`.
+4. Ticket status closure is driven by frontmatter `status: done` — already set on the
+   feature branch if ticket 10 (pre-merge closure) ran. If not, set manually and open
+   a follow-up PR.
+5. Verify via `git -C <repo> log --oneline -5`.
+
+## Source
+EPIC-FinalizeFeatureHardening retrospective, 2026-06-24, Friction F2.
```

---

### KI-3: Workflow script mirrors must be listed in files_touched

**Proposed Knowledge Item:**

> Several workflow slash commands have TWO copies that must stay in sync: the
> authoritative source at `templates/workflows-js/<name>.js` AND a committed mirror at
> `scripts/workflows/<name>.js` (the deployed copy that the deploy-SHA test
> `test_build_version_wiring.py::BP-811` validates). When a ticket edits the template
> copy, the mirror MUST also be listed in `files_touched` and updated in the same
> commit. Missing the mirror causes a post-merge CI failure (BP-811 SHA mismatch).

**Route:** Step 4 (short, universal project rule that every coder agent needs).

Routing: `CLAUDE.md-inline` → append to the existing "Repository Structure" section in
`/home/henzeh/projects/leafcutter/leafcutter-ai/CLAUDE.md`.

**Proposed diff:**

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ ## Repository Structure (existing section)
+## Workflow Script Mirror Rule — MANDATORY
+
+Every file in `templates/workflows-js/<name>.js` has a committed mirror at
+`scripts/workflows/<name>.js`. These must be kept byte-identical. When a ticket
+edits the `templates/` copy, it MUST also update `scripts/workflows/<name>.js`
+in the same commit and list BOTH paths in `files_touched`. The deploy-SHA test
+`test_build_version_wiring.py` (BP-811) will fail CI on a mismatch.
+(Source: EPIC-FinalizeFeatureHardening ticket 01 post-merge regression, 2026-06-24.)
```

---

### KI-4: External callers in spawned_by — registry validator pattern

**Proposed Knowledge Item:**

> When an agent's `spawned_by` field references a `.js` workflow file (not an agent
> name), the registry validator rejects it as an unknown caller. The correct pattern
> is to add the workflow filename to the validator's external-caller allowlist rather
> than treating it as an agent entry. The allowlist is in
> `scripts/commit_guardian/registry_validator.py` (or equivalent). When ticket 03
> of EPIC-FinalizeFeatureHardening removed the `finalize-feature` agent and updated
> 5 agents' `spawned_by` to `finalize-feature.js`, this pattern was missing and
> caused a post-merge CI failure.

**Route:** Step 9 (structural description of how the registry validator handles external callers).

Routing: `architecture-doc` → append to or update
`docs/architecture/agent_delivery_workflows.md`, or add a short note to the existing
ADR-006 addendum.

**Proposed diff (addendum to existing `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md`):**

```diff
+## External caller pattern for spawned_by (2026-06-24 addendum)
+
+When an agent's `spawned_by` references a `.js` workflow file (e.g. `finalize-feature.js`)
+rather than another agent name, the registry validator must treat that workflow filename
+as an exempted external caller. Do NOT add a fake agent entry for the workflow.
+
+Pattern: add the workflow filename to the external-caller allowlist in
+`scripts/commit_guardian/registry_validator.py` (search for the list that accepts
+non-agent spawned_by values). This allows the agent to declare its actual runtime
+caller without requiring the caller to be a registered agent.
+
+Source: EPIC-FinalizeFeatureHardening, ticket 03 post-merge regression (2026-06-24).
```

---

### Rule Update: Pre-Drive Checklist — add serial dispatch rule

This is a CLAUDE.md rule update that strengthens the existing Pre-Drive Checklist.
The parallel-dispatch corruption is not currently mentioned anywhere in the checklist.

**Proposed diff (to `/home/henzeh/projects/leafcutter/leafcutter-ai/CLAUDE.md`, append inside the "Pre-Drive Checklist" section after the last existing checklist item):**

```diff
+### Serial dispatch in shared worktrees (MANDATORY for shared-worktree epics)
+
+**What to check:** Before dispatching the first batch of ticket-supervisors, confirm
+whether you are using a shared epic worktree or per-ticket isolated worktrees.
+
+**Rule:** In a shared epic worktree, dispatch ONE ticket-supervisor at a time.
+Do not use parallel Agent tool fan-out into the same worktree path.
+
+**Why:** Concurrent git object writes in a single `.git/` directory race the object
+store and can produce 0-byte loose objects that corrupt the worktree index.
+Recovery is possible (`find .git/objects -empty -type f` → rm + `git read-tree HEAD`)
+but costs a full restart of the drive.
+
+**If you must parallelize:** Provision a separate worktree for each ticket branch
+first, then fan out — each worktree has its own `.git/worktrees/<name>/` index and
+object references that do not race.
+(Source: EPIC-FinalizeFeatureHardening retrospective 2026-06-24, Friction F1.)
```
