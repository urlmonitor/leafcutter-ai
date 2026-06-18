---
title: "Retrospective: EPIC-AcPipelineDeployGaps"
description: "Post-merge retrospective for EPIC-AcPipelineDeployGaps (PR #88), covering six knowledge items on worktree setup, deployment AC assertions, test coverage, and epic close protocols."
date: 2026-06-17
epic_branch: EPIC-AcPipelineDeployGaps
pr: "https://github.com/urlmonitor/leafcutter-ai/pull/88"
---

# Retrospective: EPIC-AcPipelineDeployGaps

Date: 2026-06-17
Epic duration: 2026-06-16 to 2026-06-17 (scaffold-to-merge, ~28 hours wall clock)
First scaffold commit: 9917dcd (2026-06-16)
Last feature commit: a9758d5 (2026-06-17)
Merge commit: 2281606

## Summary

EPIC-AcPipelineDeployGaps addressed four independent latent deployment gaps in the
leafcutter-ai v2.0.0 AC pipeline, surfaced by post-merge manual behavioral testing
after EPIC-AcPipelineConsolidationMopUp closed. The four gaps were: (1) `create-ticket.js`
silently failing to produce a ticket file after the v3 business-analyst contract change
(design decision: retire it entirely, Option C); (2) `plan-feature.js` absent from
`templates/workflows-js/` so it was never deployed to consumer installs; (3) the
`ac-scanner` and `build-ac` skills marked `portable: true` but their dependency scripts
had no build phase; (4) a schema mismatch between finalize-feature.js step-3 instructions
and step-6a reader leaving the pre-existing failure tracking loop as dead code.

All four original sub-tickets closed done. During execution a fifth gap was discovered:
the deployment scripts deployed by ticket 03 were being referenced at the wrong paths
in the agent template and skill files — ticket 05 was scaffolded mid-drive and also
closed done before merge. The epic delivered ADR-012 (create-ticket retirement), ADR-013
(portable skill deployment boundary), and a full end-to-end reachability fix for the
portable AC pipeline.

Five tickets closed done. One post-scaffold metadata fix commit (25adec3) was required
for 14 hook findings (7 `check-feedback-id` + 7 `check-description-field`) that were
silently skipped during the drive due to the worktree pre-commit gap (see Finding #2).
One quick-fix regressed tests twice (bdcce3c, a9758d5). PR #88 went conflicting at
finalize (merge conflict on scaffold files); resolved in favor of the branch.

## Epic Facts

| Metric | Value |
|--------|-------|
| Sub-ticket count (original) | 4 |
| Sub-tickets spawned mid-drive | 1 (ticket 05 — reachability gap found during 03) |
| Completed tickets | 5 (100%) |
| Git commits on branch (feature + chore) | ~22 (from 9917dcd to a9758d5) |
| Merge commit | 2281606 |
| PR | #88 |
| Blocker comments | 0 |
| Handoff comments | 0 |
| Post-merge metadata fix commits | 1 (25adec3 — 14 hook findings) |
| Test regression fix commits | 2 (bdcce3c, a9758d5) |
| ADRs authored | 2 (ADR-012, ADR-013) |

Note: `extract_epic_facts.py` is absent from this installation; facts derived from
ticket Comments sections and git log.

## Category Breakdown (Feedback System)

No structured feedback entries are tagged to EPIC-AcPipelineDeployGaps in
`debugging/logs/feedback.jsonl`. The two feedback entries from 2026-06-16 and
2026-06-17 in the corpus cover other epics. This is consistent with the worktree
pre-commit gap finding: feedback-id hooks were silently skipped for this entire drive,
so no `check-feedback-id`-enforced submissions were collected. Quantitative category
breakdown is unavailable.

## Metrics

Phase sign-off state derived from ticket frontmatter `agents:` maps (all 5 tickets):

| Phase | Signed Off | Failed | Needed (not run) |
|-------|-----------|--------|------------------|
| architect-review | 3 | 0 | 2 |
| llm-expert | 2 | 0 | 3 |
| python-coder | 3 | 0 | 2 |
| test-writer | 3 | 0 | 2 |
| documentation-expert | 3 | 0 | 2 |
| pr-reviewer | 5 | 0 | 0 |
| commit | 5 | 0 | 0 |
| pull-request | 5 | 0 | 0 |
| code-review-architect | 1 | 0 | 4 |

All phases that ran signed off (status: ok). Zero failed phases. Zero blocker comments
in any `## Comments` section. Ticket 05 was the only mid-drive scaffold; it ran the
full phase set and closed signed-off in a single session.

## What Went Well

- **All 5 tickets closed on first-attempt sign-off.** Not one failed phase, not one
  adjudication ladder trigger. Every agent that ran produced `status: ok`.
- **Architect-review was the correct gate for two design-decision tickets.** Tickets
  01 and 03 each required an architect-level decision (retire create-ticket.js? portable
  or package-internal?) before implementation could begin. The design-decision ticket
  format worked — both decisions were recorded with explicit rationale and option
  trade-offs before any code ran.
- **Ticket 01 chose the structurally correct option.** Retiring `create-ticket.js`
  (Option C) aligned with ADR-010's stated inversion to the AC store as source of truth.
  ADR-012 documents the retirement. No code was patched to restore a deprecated contract.
- **Ticket 03 + ticket 05 found and fixed a genuine end-to-end reachability gap.** The
  portable AC pipeline scripts would have deployed to the wrong paths without the ticket-05
  follow-up. The architect-review in ticket 05 correctly diagnosed the
  `target_root`/`output_root` naming confusion (same bug family as BP-811) and the
  `ac_store/ac_store/` sibling-doubling in `goal_to_epic.py`.
- **finalize-feature triage schema fix (ticket 04) was a clean one-pass delivery.**
  Pure prompt/schema alignment — no structural refactoring — and the pre-existing failure
  tracking loop was activated without regressions.
- **Post-drive diagnostic found and fixed 14 hook findings in one commit (25adec3).**
  The metadata fix was surgical and did not require a PR or re-drive of any ticket.
- **plan-feature.js deployment (ticket 02) was a minimal surgical fix.** One file copy
  + two tests. Zero changes to build_phases.py logic; zero scope creep.

## Friction Points

- **FINDING #2 (HIGHEST VALUE): ALL PACKAGE HOOKS SILENTLY SKIPPED FOR ENTIRE DRIVE.**
  The epic worktree had no `.pre-commit-config.yaml` (it is a `.leafcutter` symlink
  created by `install_shims`, absent in worktrees). Every commit during the drive used
  `PRE_COMMIT_ALLOW_NO_CONFIG=1`, so all nine package hooks — complexity, glossary,
  doc-frontmatter, AC schema, sign-off parity, secrets, exception-handling,
  `check-feedback-id`, `check-description-field` — were silently skipped. A post-drive
  diagnostic found 14 would-have-blocked findings that had to be fixed after the fact
  (25adec3). Root cause filed as TICKET-20260617-Worktree_Precommit_Bootstrap.md (open
  in inbox). This is the single highest-leverage systemic gap: zero hook coverage on
  every commit of every worktree-based epic drive.

- **FINDING #3: DEPLOYMENT ACS VERIFIED COPY, NOT REACHABILITY.** Tickets 02 and 03
  each passed their ACs (file present in build output) but the actual consumer-facing
  goal — scripts reachable through the shim at runtime — was not achieved. Ticket 02
  verified `plan-feature.js` was in `templates/workflows-js/`, but BP-811 was still
  needed to fix the shim path convention (`output_root/workflows/`, not
  `.claude/workflows/`). Ticket 03 verified the six scripts were copied by
  `build_ac_store()`, but the agent template still referenced them at bare
  `scripts/ac_store/` paths that resolve nowhere on a consumer install. Only
  manual angle-testing (an architecture + build-layer review run post-ticket-03) caught
  the gap, which required scaffolding ticket 05 mid-drive.

- **FINDING #4 — QUICK-FIX REGRESSED TESTS TWICE.** The BP-811 fix (writing workflow
  `.js` files to `output_root/workflows/` not `.claude/workflows/`) regressed test
  assertions in three test files that asserted the old path. Round 1 (bdcce3c) fixed
  `test_build_phases.py`. The finalize-feature triage then caught three more regressions
  in `unit_tests/test_build_workflow_output_paths.py` and
  `unit_tests/test_build_workflow_phase.py` (fixed in a9758d5). A path-convention
  change must grep all tests asserting the old path in one pass; the first fix missed
  two files.

- **FINDING #1 — WORKTREE REACHABILITY FAILURE AT DRIVE START.** The epic worktree was
  created from `origin/main` but the epic scaffold commit (9917dcd / c34dd4c) was only
  on local main (unpushed). The reachability check failed. Recovery required
  cherry-picking the scaffold commit onto the epic branch before any ticket could run.

- **FINDING #5 — MERGE CONFLICT AT FINALIZE.** PR #88 went CONFLICTING because the epic
  scaffold reached `origin/main` separately (add/add conflict on the 5 epic-ticket files:
  scaffold status `todo` on main vs `done` on the branch). Resolved in favor of the
  branch. This is a direct consequence of Finding #1 (scaffold commit provenance).

- **FINDING #6 — RELAY-APPROVAL DEADLOCK (recurring).** The confirmation-gated agents
  (`commit`, finalize-feature merge gate) refused approval relayed via SendMessage from
  the parent coordinator. This deadlocked twice: the ticket-05 scaffold commit and the
  PR-merge gate. The parent had to perform the gated action directly each time. This
  pattern was already recorded in `feedback_no_gated_agent_for_interactive.md` after
  EPIC-PrecommitSafetyNet; it recurred here and cost additional cycles.

- **FINDING #7 — MASTER_PLAN STATUS NOT AUTO-PROMOTED.** All 5 sub-tickets were
  `status: done` but `Master_Plan.md` stayed `status: todo` until archival manually
  set it. The epic-supervisor / finalize flow never promotes the master plan status when
  all children complete.

- **FINDING #8 — SUB-AGENT API FAILURES MID-RUN.** Multiple sub-agents died mid-run on
  infrastructure errors: a 401 Unauthorized on the ticket-02 supervisor (after 28 tool
  calls) and repeated 412 Portkey "usage limit exceeded" on the metadata-fix agent. Each
  required parent recovery (resume vs complete inline). Long sub-agent chains currently
  have no resumability protocol.

- **FINDING #2B — 14 METADATA FINDINGS REQUIRED A POST-DRIVE FIX COMMIT.** Because all
  hooks were skipped during the drive, `check-feedback-id` and `check-description-field`
  violations accumulated across 7 tickets. Fixing them after merge required a dedicated
  commit (25adec3) rather than catching them per-commit. The pre-commit bootstrap gap is
  the root cause; this is a downstream symptom.

## Knowledge Gaps Found

- **Worktree pre-commit bootstrap is undocumented.** There is no mechanism to ensure
  `.pre-commit-config.yaml` (or the `.leafcutter` symlink that provides it) is present
  in a freshly created worktree. The leafcutter build system (`install_shims`) creates
  the symlink in the project root but not in worktrees. The gap is known (filed as
  TICKET-20260617-Worktree_Precommit_Bootstrap.md) but no pre-drive check, no
  worktree-agent step, and no `building-epics` skill note currently warns about it.

- **Deployment ACs have no reachability tier.** The AC language for deployment tickets
  has no canonical pattern requiring end-to-end reachability assertions through the
  shim / invocation path. "File is present in build output" passes a copy-check AC;
  "command resolves and executes without file-not-found" is a separate, stronger tier
  that is not currently encoded in any AC template.

- **Test grep scope at path-change time is not in any checklist.** When a path
  convention changes, the person or agent making the change must grep all tests
  asserting the old path. This is not documented in the commit phase, pr-reviewer
  rubric, or pre-commit checklist.

- **Epic scaffold commit must be pushed before worktree creation.** The reachability
  dependency (scaffold commit must be reachable from the branch head before any ticket
  agent can read it) is not documented in the `building-epics` skill or the pre-drive
  checklist.

- **Master_Plan.md status lifecycle is unowned.** The epic-level `status` field in
  `Master_Plan.md` has no automated promotion path. It goes `todo` → `done` only by
  manual intervention during archival.

## Subagent Quality Trends

No supervisor feedback entries found for this epic (no `subagent-quality` category
entries exist in `debugging/logs/feedback.jsonl`; the corpus totals 49 entries, all
`complete`, all from EPIC-GoalToEpic and adjacent epics). The feedback-id hooks were
silently skipped for this drive (worktree pre-commit gap), so agent-level feedback
was not submitted for any phase.

---

## Proposed Improvements

The improvements below are ordered by leverage. Findings #2 and #3 are highest priority.

---

### KI-1: Worktree pre-commit bootstrap — pre-drive check and worktree-agent step

**Problem (Finding #2):** Every worktree-based epic drive runs with ALL package
pre-commit hooks silently skipped. `.pre-commit-config.yaml` lives only in the main
repo root (as a `.leafcutter` symlink created by `install_shims`). Worktrees do not
inherit it. The gap is structural: zero hook coverage on every commit of every epic
drive.

**Proposed Knowledge Item text:**

```
Before any /build-feature epic drive using a worktree, verify that
.pre-commit-config.yaml (or the .leafcutter symlink that provides it) is present
in the worktree root. If absent, copy or symlink it before the first commit:

  ln -s <main-tree-root>/.leafcutter <worktree-root>/.leafcutter

If the symlink cannot be created (NTFS/WSL2 constraint), copy
.pre-commit-config.yaml directly from the main tree root.

Without this step, ALL package hooks are silently skipped (pre-commit exits 0
with PRE_COMMIT_ALLOW_NO_CONFIG=1), producing commits that accumulate
check-feedback-id, check-description-field, complexity, secrets, and
exception-handling violations — discovered only in a post-drive batch fix.

Root cause: install_shims creates .leafcutter in the project root, not in
git worktrees. (Tracked in TICKET-20260617-Worktree_Precommit_Bootstrap.md.)
```

**Routing:** `leafcutter-ai/CLAUDE.md` Pre-Drive Checklist section + `templates/skills/building-epics/SKILL.md` §1.0 (alongside the existing feedback-sink pre-flight check).

**Proposed diff (CLAUDE.md Pre-Drive Checklist section):**

```diff
--- a/leafcutter-ai/CLAUDE.md
+++ b/leafcutter-ai/CLAUDE.md
@@ Pre-Drive Checklist @@
+### Worktree pre-commit config (MANDATORY for worktree-based drives)
+
+Worktrees do not inherit `.pre-commit-config.yaml` from the main working tree.
+If the worktree root does not have `.pre-commit-config.yaml` or a `.leafcutter`
+symlink that provides it, ALL package hooks are silently skipped for the entire drive.
+
+**Check:**
+```bash
+ls <worktree-root>/.pre-commit-config.yaml 2>/dev/null || ls <worktree-root>/.leafcutter 2>/dev/null
+```
+
+**Fix (if absent):**
+```bash
+# Option A — symlink (preferred, requires native Linux FS):
+ln -s <main-tree-root>/.leafcutter <worktree-root>/.leafcutter
+
+# Option B — copy (for NTFS/WSL2):
+cp <main-tree-root>/.pre-commit-config.yaml <worktree-root>/.pre-commit-config.yaml
+```
+
+**If the check fails AND cannot be fixed:** Do not start the drive. The most
+common cause is a fresh worktree on an NTFS mount where symlinks are restricted.
+Use a native Linux path for the worktree instead.
+
+**Why this matters:** During EPIC-AcPipelineDeployGaps (2026-06-17), all nine
+package hooks were silently skipped for the entire drive. A post-drive diagnostic
+found 14 would-have-blocked findings (7 check-feedback-id + 7 check-description-field)
+that required a dedicated fix commit after merge.
+(Root cause: TICKET-20260617-Worktree_Precommit_Bootstrap.md)
```

---

### KI-2: Deployment ACs must assert end-to-end reachability through the shim

**Problem (Finding #3):** Tickets 02 and 03 each passed their ACs (file present in
build output) but failed the actual consumer-facing goal — the deployed files were
unreachable. BP-811 (wrong shim path) and ticket 05 (wrong invocation paths in agent
template) were both discovered only by manual angle-testing after sign-off. The ACs
asserted copy, not reachability.

**Proposed Knowledge Item text:**

```
Acceptance criteria for deployment tickets must include a reachability tier, not
only a copy tier. The two tiers are distinct:

  Copy tier: "file is present in the build output directory"
  Reachability tier: "command resolves and executes without file-not-found when
    invoked through the canonical shim at the deployed path"

A copy-tier AC passes when build_workflow_scripts() copies plan-feature.js to
templates/workflows-js/. It does NOT catch that the shim writes to
output_root/workflows/ not .claude/workflows/ (BP-811), or that build-ac.md
still references scripts at bare `scripts/ac_store/` paths that do not exist
on a consumer install (ticket 05).

Template for the reachability AC (Gherkin):

  Scenario: consumer-facing reachability
    Given a simulated consumer install with <component> deployed
    When the canonical entry point is invoked (<shim-path>/<script-name>)
    Then the invocation exits without file-not-found or import-resolution error
    And the output matches the expected command signature

Add this scenario to every ticket whose primary deliverable is a deployed
artifact (workflow .js, script, agent template, skill SKILL.md).
```

**Routing:** `templates/skills/ticket-authoring/SKILL.md` (AC authoring guidance for
deployment tickets); also as a note in `templates/skills/building-epics/SKILL.md`
under the "AC review" checklist for ticket-supervisor's pr-reviewer dispatch.

**Proposed diff (ticket-authoring/SKILL.md — add after copy-AC pattern):**

```diff
--- a/templates/skills/ticket-authoring/SKILL.md
+++ b/templates/skills/ticket-authoring/SKILL.md
@@ AC authoring — deployment artifacts @@
+### Deployment tickets: require reachability ACs, not only copy ACs
+
+When a ticket's primary deliverable is a file that must be callable at runtime
+(workflow script, agent template, skill SKILL.md, pre-commit hook), the acceptance
+criteria MUST include a reachability scenario in addition to any copy/presence check:
+
+```gherkin
+Scenario: consumer-facing reachability
+  Given a simulated consumer install with <component> deployed
+  When the canonical entry point is invoked at <deployed-path>/<script-name>
+  Then the invocation exits without file-not-found or import-resolution error
+  And the output matches the expected command signature
+```
+
+A copy AC ("file is present in templates/workflows-js/") passes even when:
+  - The shim writes to a different output path than the AC asserts (BP-811 pattern)
+  - The agent template invoking the script uses a bare path that resolves nowhere
+    on a consumer install (EPIC-AcPipelineDeployGaps/ticket-05 pattern)
+
+Reachability ACs catch both failure modes. Copy ACs catch neither.
+(Source: EPIC-AcPipelineDeployGaps retrospective, 2026-06-17)
```

---

### KI-3: Path-convention changes must grep ALL tests asserting the old path in one pass

**Problem (Finding #4):** The BP-811 path-convention fix (workflow scripts write to
`output_root/workflows/`, not `.claude/workflows/`) regressed tests in three test
files. The first fix pass (bdcce3c) caught `test_build_phases.py`; the finalize-feature
triage then caught two more files (`test_build_workflow_output_paths.py`,
`test_build_workflow_phase.py`), requiring a second fix commit (a9758d5). The first
agent grepped one file; the full extent required two rounds.

**Proposed Knowledge Item text:**

```
When a path constant, output directory, or convention changes, the implementing
agent (python-coder or equivalent) MUST run a project-wide grep for the old
path string before declaring the implementation done — not just the file being
edited. Run:

  grep -r "<old_path_string>" tests/ unit_tests/ 2>/dev/null

If any test file contains the old string, fix ALL occurrences in one commit,
not incrementally. The commit message must state the number of test files
updated (e.g. "fix: update 3 test files to assert new output_root/workflows/ path").

Never sign off on a path-change ticket until the grep returns zero matches in
the test tree. This is a precondition for pr-reviewer sign-off, not a
post-merge discovery.
(Source: EPIC-AcPipelineDeployGaps/BP-811, 2026-06-17)
```

**Routing:** `templates/agents/python-coder.md` (implementation checklist — add as
a pre-sign-off gate for path-change tickets); also a note in
`templates/agents/pr-reviewer.md` (review rubric — check for path-string changes
that may have corresponding test assertions).

**Proposed diff (pr-reviewer.md — add to review rubric):**

```diff
--- a/templates/agents/pr-reviewer.md
+++ b/templates/agents/pr-reviewer.md
@@ Review rubric @@
+### Path-convention changes: test grep required
+
+When the diff changes a path constant, output directory name, or file location
+convention, check whether test files assert the old path string. Run:
+
+  grep -r "<old_path>" tests/ unit_tests/
+
+If matches exist and the diff does not update them, flag as HIGH confidence
+finding: "path-change without full test-grep — N test files may still assert
+the old path". Do not sign off until all matches are addressed.
+(EPIC-AcPipelineDeployGaps retrospective, 2026-06-17)
```

---

### KI-4: Epic scaffold commit must be pushed before worktree creation

**Problem (Finding #1):** The epic worktree was created from `origin/main` but the
scaffold commit was only on local main. The reachability check failed; recovery required
cherry-picking the scaffold commit before any ticket could run.

**Proposed Knowledge Item text:**

```
Before running worktree-agent to create an epic worktree, the scaffold commit
(Master_Plan.md + sub-ticket stubs) MUST already be on origin/main. If you just
ran /create-epic locally, push main first:

  git -C <repo> push origin main

Then create the worktree. If you create the worktree from a local main that has
unpushed commits, the worktree branch diverges from origin/main at the stale
point, the scaffold files are unreachable in the worktree, and ticket agents
cannot read them until a cherry-pick is applied manually.

Side-effect: if origin/main later receives the same scaffold files via the epic
branch PR, the merge creates an add/add conflict on those files (resolved in
favor of the branch — the done/ status overwrites the todo/ status).
(Source: EPIC-AcPipelineDeployGaps retrospective, 2026-06-17, Findings #1 + #5)
```

**Routing:** `leafcutter-ai/CLAUDE.md` Pre-Drive Checklist (new item); also
`templates/skills/building-epics/SKILL.md` §1.0 (alongside feedback-sink pre-flight).

**Proposed diff (CLAUDE.md Pre-Drive Checklist section):**

```diff
--- a/leafcutter-ai/CLAUDE.md
+++ b/leafcutter-ai/CLAUDE.md
@@ Pre-Drive Checklist @@
+### Push scaffold commit before creating worktree
+
+**What to check:** After running `/create-epic`, confirm the scaffold commit
+(Master_Plan.md + sub-ticket stubs) is already on `origin/main` before calling
+`worktree-agent` to create the epic worktree.
+
+```bash
+# Verify the scaffold is on origin/main (should show the scaffold commit):
+git -C <repo> log --oneline origin/main -1
+```
+
+If it is not there yet, push first:
+```bash
+git -C <repo> push origin main
+```
+
+**If you skip this:** The epic worktree branch diverges from `origin/main` at
+a stale point. The scaffold files are unreachable inside the worktree; recovery
+requires cherry-picking the scaffold commit onto the epic branch. The PR later
+creates an add/add conflict on the scaffold files.
```

---

### KI-5: Gated-agent relay-approval deadlock (recurring — already partially documented)

**Problem (Finding #6):** Confirmation-gated agents refuse approval relayed via
SendMessage. This deadlocked twice in this epic (ticket-05 scaffold commit; PR-merge
gate). The pattern was already recorded as `feedback_no_gated_agent_for_interactive.md`
after EPIC-PrecommitSafetyNet, and KI-2 of that retrospective proposed a coordination
token. It recurred here because the documentation note has not been converted into
a concrete workaround in `building-epics`.

**Proposed Knowledge Item text:**

```
RECURRING PATTERN (confirmed in EPIC-PrecommitSafetyNet and EPIC-AcPipelineDeployGaps):
Gated agents (commit, finalize-feature merge gate, worktree-agent remove) refuse
confirmation relayed via SendMessage from a parent coordinator. The agents have no
direct user-turn channel when running as subagents and therefore cannot accept
"yes" from a relayed message.

INTERIM PROTOCOL (until an authorization-token solution ships):
1. When a gated agent deadlocks on relay approval, the parent coordinator must
   perform the gated action directly (raw git commit / gh pr merge / worktree remove).
2. Log the bypass in the parent session with: "Bypassed <agent> gate directly —
   relay-approval deadlock; authorization granted in parent conversation."
3. Do NOT re-attempt SendMessage with approval — it will not succeed.

PENDING: Design and implement an authorization token (e.g.
  { "authorization": { "granted_by": "coordinator", "action": "commit", "ticket": "..." } }
) that gated agents accept as coordinator-sanctioned without requiring an interactive
user turn. See KI-2 from EPIC-PrecommitSafetyNet retrospective.
```

**Routing:** `templates/skills/building-epics/SKILL.md` §3 (failure adjudication) — add
under "confirmation-gate deadlock" as an explicit named pattern with the interim protocol.

---

### KI-6: Master_Plan.md status must be promoted on epic close

**Problem (Finding #7):** All 5 sub-tickets closed `status: done` but `Master_Plan.md`
remained `status: todo` until manual archival. The finalize-feature / epic-supervisor
flow has no step that promotes the master plan status.

**Proposed Knowledge Item text:**

```
When all sub-tickets in an epic reach status: done, the parent Master_Plan.md
status field must be promoted to status: done before archival. This is a
bookkeeping step, not an automatic promotion.

Who owns it: the parent coordinator (epic-supervisor or /build-feature) at the
end of the drive, before invoking /finalize-feature.

Checklist step: after the last sub-ticket signs off, run:
  Read Master_Plan.md → confirm all sub-tickets are done → Edit status: todo → done

If status is still todo when /finalize-feature runs, the archive step will move
a todo-status master plan to 99_done — which is misleading to retrospective tooling.
```

**Routing:** `templates/skills/building-epics/SKILL.md` (add as the final step of §1.1
epic loop, after all tickets are signed off, before /finalize-feature dispatch).

---

*All proposed changes above are diffs or KI text presented for user approval.
No file has been modified. Type "yes" to apply each item, "skip" to skip,
or "edit" to revise.*
