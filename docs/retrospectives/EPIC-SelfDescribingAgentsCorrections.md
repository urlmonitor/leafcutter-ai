---
description: Retrospective for EPIC-SelfDescribingAgentsCorrections
---

# Retrospective: EPIC-SelfDescribingAgentsCorrections
Date: 2026-07-01
Epic duration: 2026-06-08 (scaffold / AC authoring) to 2026-06-30 (final ticket sign-off)
Squash-merge PR: #179 — merged 2026-07-01
Git commit (merge): 2406aa87

## Summary

EPIC-SelfDescribingAgentsCorrections implemented the post-rollout corrections to the
self-describing agents system (INF-600), batching 10 leaf ACs under three L1s:
INF-600g (build validation gate — spawn-graph and skills_invoked cross-reference checks),
INF-600d (spawn-graph accuracy — skill-vs-delegation boundary in agent registry entries),
and INF-600b (card content enrichment — hyperlinks, missing-link handling, per-agent AC
assignment surfaces). All 10 tickets were driven serially via ticket-supervisor under a
single epic branch (EPIC-SelfDescribingAgentsCorrections), squash-merged as PR #179.

The epic delivered: bidirectional spawn-graph symmetry validation with a new commit-time
hook (`check_agent_spawn_consistency`); `__ticket_phase_agents__` redundancy detection
and `.claude/skills/` fallback resolution; corrected spawn_allowlist/skills_invoked
boundary for python-coder and documentation-expert; and a significantly enriched card
generator (`generate_agent_cards.py`) producing hyperlinked References sections, missing-
link annotations, and per-agent AC assignment groupings across all 51 agent cards.

A post-drive code review (code-review-architect) found 2 HIGH defects that were fixed
on-branch before merge and 2 MEDIUM findings deferred to follow-up ticket #194.

## Metrics

### Phase Agent Summary (derived from ticket ## Comments sections)

| Phase | Signed Off | Failed / Blocked | Notes |
|-------|-----------|-----------------|-------|
| test-writer | 10 | 0 | Skipped (not_needed) on 9 tickets; 1 respawn on T09 (missing coverage) |
| python-coder | 10 | 0 | All first-pass sign-offs |
| test-runner | 10 | 0 | All first-pass sign-offs |
| pr-reviewer | 10 | 2 | T06: second-pass blocker (stale card); T09: missing-test blocker |
| commit | 10 | 0 | Minor autofix on 4 tickets (feedback-id / check-description-field) |
| pull-request | 10 | 0 | All pushed to single epic branch / PR #179 |

Cross-agent reworks (within retry caps): 2
- T06 (INF-600d-1): pr-reviewer second-pass blocker → python-coder respawn to fix test-runner.card.md
- T09 (INF-600b-1-i): pr-reviewer blocker on missing tests → test-writer respawn

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 10 |
| Completed tickets | 10 (100%) |
| Source AC L1s | 3 (INF-600g, INF-600d, INF-600b) |
| Source AC leaf nodes | 10 |
| Git squash-merge commits | 1 (PR #179, SHA 2406aa87) |
| Files changed at merge | 86 |
| Lines inserted | 4,665 |
| Lines deleted | 269 |
| Blocker comments | 2 (T06 pr-reviewer second pass; T09 pr-reviewer first pass) |
| Handoff comments | 0 |
| Parallel supervisor runs | 0 (serial drive, known git-object race avoided) |
| Post-drive HIGH defects found | 2 (fixed on-branch before merge) |
| Post-drive MEDIUM deferred | 2 (tracked in #194) |

## Category Breakdown (Feedback System)

No structured feedback entries are attributed to this epic's tickets in `feedback.jsonl`.
All agent submissions returned `feedback-id: (submit-failed)` — the feedback sink
(`scripts/feedback/submit_feedback.py`) was absent from the epic worktree for the
duration of the drive (pre-commit config / .leafcutter symlink gap prevented the
scripts from being deployed).

A small number of entries from other epics recorded in the same session do exist in the
feedback corpus but are not attributed to EPIC-SelfDescribingAgentsCorrections tickets.

## What Went Well

- **Serial drive discipline held.** All 10 tickets were driven one-at-a-time; no parallel
  supervisors were attempted, avoiding the 0-byte git object corruption seen in prior epics.
- **Dependency graph respected.** The four dependency edges (02 to 04, 03 to 05, 06 to 07,
  08 to 09) were observed correctly; no ticket was driven before its parent.
- **python-coder phase: 10/10 first-pass sign-offs.** Not a single python-coder phase
  required a retry or rework, despite significant implementation complexity on T01
  (new commit-time hook) and T08 (card generator overhaul regenerating 51 cards).
- **pr-reviewer caught the real defects.** Both cross-agent reworks were triggered by
  pr-reviewer finding genuine AC coverage gaps (stale card on T06; untested code path
  on T09) — not false positives. The blocker/respawn/sign-off cycle worked correctly.
- **Behavioral spot-check confirmed observable behavior.** All 10 ACs implement
  observable, testable behavior. No phantom-done tickets.
- **Code-review-architect post-drive review was productive.** The rstrip suffix bug
  (HIGH) and non-deterministic os.walk match (HIGH) were both found and fixed on-branch
  before merge; 6 regression tests were added.
- **Pre-commit hook autofixes were mechanical and bounded.** Hook autofixes (feedback-id
  insertion, check-description-field) succeeded on first retry on every ticket with no
  further escalation.
- **All 51 agent cards regenerated cleanly** in a single python-coder pass on T08.

## Friction Points

- **FP-1 — Pre-drive scaffold gap (BLOCKING, ~45 min delay).** The epic scaffold
  (Master_Plan.md + 10 ticket stubs) was created locally but never landed on
  `origin/main` before the epic worktree was created. The worktree diverged at a stale
  point where the scaffold files were absent. A dedicated scaffold-only PR (#178) had
  to be opened and merged before the drive could begin.
  (Recurrence of the pattern documented in CLAUDE.md Pre-Drive Checklist.)

- **FP-2 — Feedback sink absent from epic worktree (SILENT throughout).** All 10 tickets'
  agent phases emitted `feedback-id: (submit-failed)` because `scripts/feedback/` was
  not present in the epic worktree. This is the same .leafcutter symlink / pre-commit
  config gap documented from EPIC-AcPipelineDeployGaps. Zero telemetry was captured for
  this epic.

- **FP-3 — SEVERE git corruption at finalize.** After all 10 tickets were complete,
  finalization hit severe shared-repo corruption: 0-byte "shadow" objects left by an
  interrupted concurrent-writer commit session had corrupted HEAD, the index cache-tree,
  and shadowed real objects from origin. A plain `git fetch` could not restore them.
  Recovery required: `find .git/objects -empty -delete`, `git fetch --refetch`, and a
  fresh worktree to rebuild the poisoned cache-tree. This cost significant time and
  introduced risk of data loss (none occurred). Root cause: a concurrent commit process
  writing to the same `.git/objects` directory while another was in flight.

- **FP-4 — T06 pr-reviewer bidirectional card inconsistency (CROSS-AGENT REWORK).** The
  initial pr-reviewer pass on T06 (INF-600d-1) signed off without checking that the
  test-runner agent card still contained the stale `python-coder` spawn edge. A second-pass
  review caught it and issued a blocker, requiring a python-coder respawn.
  Root cause: `files_touched` listed only config/docs files, not both card files;
  pr-reviewer checked only listed files on first pass.

- **FP-5 — T09 test-writer skipped a ticket that needed tests (CROSS-AGENT REWORK).**
  Ticket 09 (INF-600b-1-i) listed doc/config files in `files_touched` but not
  `scripts/generate_agent_cards.py`. test-writer skipped because it saw no Python source
  file in scope. pr-reviewer caught that the new `render_references()` missing-doc branch
  was entirely untested and issued a blocker. test-writer was respawned and added 3
  behavioural tests.

- **FP-6 — Post-drive HIGH defects (rstrip and os.walk).** Two HIGH defects found by
  code-review-architect after all tickets signed off:
  (a) `filename.rstrip('.yaml')` strips a character set, not a suffix — corrupts AC ids
  when stem characters happen to be in `{'.', 'y', 'a', 'm', 'l'}`.
  (b) `_resolve_source_to_path` used first-match-wins from `os.walk` whose traversal
  order is filesystem-dependent — non-deterministic hyperlinks across environments.
  Both required on-branch fix commits and 6 new regression tests before merge.

- **FP-7 — `files_touched` frontmatter drift (RECURRING, 3 tickets).** Tickets 02, 09,
  and 10 had `files_touched` that did not match the actual files changed in their diffs.
  This cascades to test-writer skipping when it should not and pr-reviewer missing files
  on first pass.

## Knowledge Gaps Found

- **KG-1 — No documented recovery procedure for 0-byte shadow git objects.** The
  `find -empty -delete` + `git fetch --refetch` + fresh-worktree recipe was discovered
  ad hoc under pressure. The existing "No parallel supervisors" MEMORY.md entry addresses
  prevention but not recovery.

- **KG-2 — files_touched drift is not mechanically validated.** No hook or agent step
  cross-checks `files_touched` against the actual diff. pr-reviewer and test-writer both
  silently trust it.

- **KG-3 — Feedback sink deployment gap in worktrees is still not solved.** The worktree
  pre-commit config recipe covers `.pre-commit-config.yaml` and `scripts/commit_guardian/`
  but does not deploy `scripts/feedback/submit_feedback.py` into the worktree. The
  feedback sink remains absent from every epic worktree drive.

- **KG-4 — pr-reviewer does not check bidirectional card consistency by default.** When
  a registry change removes or adds a spawn edge, the mirror agent card is not
  automatically in scope for pr-reviewer unless `files_touched` includes it.

## Subagent Quality Trends

No supervisor feedback entries found for this epic (`subagent-quality` category returned 0
entries). The feedback sink was absent from the epic worktree throughout the drive —
all agent submissions returned `(submit-failed)`. No adjudication events were recorded.

---

## Proposed Improvements

The following KIs and rule updates are proposed for user approval. None are auto-applied.

---

### KI-1: Git object corruption recovery recipe

**Proposed Knowledge Item — destination: CLAUDE.md (project root)**

When `.git/objects/` contains 0-byte files (left by an interrupted concurrent-writer
commit), the repository is in a state where a plain `git fetch` cannot restore objects.

Recovery recipe (confirmed 2026-07-01, EPIC-SelfDescribingAgentsCorrections):

```bash
# Step 1: remove all empty object placeholders
find /path/to/.git/objects -empty -delete

# Step 2: force a full re-download of all objects from origin
git -C /path/to/repo fetch --refetch origin

# Step 3: if the index cache-tree is still corrupt, create a fresh worktree
git -C /path/to/repo worktree add /tmp/recovery-tree origin/main

# Step 4: rebuild the cache-tree index in the fresh worktree
git -C /tmp/recovery-tree read-tree HEAD
```

Root cause: concurrent processes writing to `.git/objects/` under WSL2 NTFS paths
can interrupt mid-write, leaving 0-byte placeholder files.

**Proposed CLAUDE.md diff (do NOT auto-apply — awaiting user approval):**

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ ## Pre-Drive Checklist @@
+## Git Object Corruption Recovery
+
+When `.git/objects/` contains 0-byte files from an interrupted concurrent commit,
+a plain `git fetch` cannot overwrite existing empty object files. Recovery:
+
+```bash
+# 1. Remove empty object placeholders:
+find /path/to/.git/objects -empty -delete
+# 2. Force full object re-download:
+git -C /path/to/repo fetch --refetch origin
+# 3. If index cache-tree is poisoned, rebuild via fresh worktree:
+git -C /path/to/repo worktree add /tmp/recovery-tree origin/main
+git -C /tmp/recovery-tree read-tree HEAD
+```
+
+Root cause: concurrent git writers on WSL2 NTFS leave 0-byte placeholder objects
+that block subsequent fetch/restore operations.
+(Source: EPIC-SelfDescribingAgentsCorrections finalize, 2026-07-01.)
```

---

### KI-2: Verify files_touched before test-writer runs

**Proposed Knowledge Item — destination: CLAUDE.md (project root), Pre-Drive Checklist**

`test-writer` skips silently when `files_touched` contains no Python source files, even
when the python-coder commit actually modified one. Confirm before dispatching
test-writer that `files_touched` includes every `.py` file in the last diff.

**Proposed CLAUDE.md diff (do NOT auto-apply — awaiting user approval):**

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ ## Pre-Drive Checklist (after "Commit agent in batch-drive mode") @@
+### Verify files_touched matches actual diff before test-writer
+
+`test-writer` skips silently when no Python source file appears in `files_touched`,
+even if the python-coder commit modified one. Before test-writer is dispatched,
+cross-check `files_touched` against the diff:
+
+```bash
+git -C <worktree> diff HEAD~1 --name-only
+```
+
+If the diff contains a `.py` file absent from `files_touched`, update the ticket
+frontmatter before invoking test-writer. Failure to do so silently produces untested
+code paths that only surface at the pr-reviewer phase as a blocker.
+(Source: EPIC-SelfDescribingAgentsCorrections T09 cross-agent rework, 2026-06-30.)
```

---

### KI-3: pr-reviewer registry edge check — mirror cards

**Proposed Knowledge Item — destination: templates/agents/pr-reviewer.md**

When a diff modifies `spawn_allowlist` or `spawned_by` for any agent in
`config/agent_registry.json`, the pr-reviewer must also inspect the agent card of the
OTHER side of the relationship (`docs/agents/cards/<agent>.card.md`), even when that
card is not listed in `files_touched`.

**Proposed pr-reviewer.md diff (do NOT auto-apply — awaiting user approval):**

```diff
--- a/templates/agents/pr-reviewer.md
+++ b/templates/agents/pr-reviewer.md
@@ <!-- review checklist section --> @@
+**Registry edge changes — bidirectional card check (HIGH confidence):**
+When the diff modifies `spawn_allowlist` or `spawned_by` for any agent in
+`config/agent_registry.json`, also inspect the agent card
+(`docs/agents/cards/<agent>.card.md`) for the OTHER agent in the relationship.
+The Mermaid spawn diagram and "Spawned By / Spawns" prose in that card must be
+consistent with the registry change, even when that card is absent from
+`files_touched`.
+(Source: EPIC-SelfDescribingAgentsCorrections T06 cross-agent rework, 2026-06-29.)
```

---

### KI-4: MEMORY.md — git corruption recovery entry

**Proposed Knowledge Item — destination: session MEMORY.md**

Add a short memory entry so future sessions surface the recovery path without searching.

**Proposed MEMORY.md diff (do NOT auto-apply — awaiting user approval):**

```diff
--- a/MEMORY.md
+++ b/MEMORY.md
@@ - [No parallel supervisors in shared worktree]... @@
+- [Git object corruption recovery](feedback_git_object_corruption_recovery.md) — 0-byte shadow objects from interrupted concurrent writes cannot be restored with plain git fetch; recipe: find -empty -delete + git fetch --refetch + worktree add + read-tree HEAD; confirmed 2026-07-01 EPIC-SelfDescribingAgentsCorrections
```

**New companion memory file content (do NOT auto-apply — awaiting user approval):**

Destination: `/home/henzeh/.claude/projects/-home-henzeh-projects-leafcutter/memory/feedback_git_object_corruption_recovery.md`

```markdown
# Git object corruption recovery

When `.git/objects/` contains 0-byte files from an interrupted concurrent commit:

1. `find /path/to/.git/objects -empty -delete` — remove empty object placeholders
2. `git -C /path/to/repo fetch --refetch origin` — force full object re-download
3. If index cache-tree is poisoned: `git -C /path/to/repo worktree add /tmp/rt origin/main`
4. Rebuild the index: `git -C /tmp/rt read-tree HEAD`

Root cause: concurrent git writers on WSL2 NTFS leave 0-byte placeholder object
files that a plain `git fetch` cannot overwrite (fetch skips existing paths).

First confirmed: 2026-07-01, EPIC-SelfDescribingAgentsCorrections finalize.
Prevention: drive tickets serially; never allow two processes to commit to the
same git object store concurrently.
```
