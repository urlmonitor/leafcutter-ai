---
epic: EPIC-QuickFixWorkflow
source_ac: BP-600
pr: "#83"
date: 2026-07-10
---

# Retrospective: EPIC-QuickFixWorkflow
Date: 2026-07-10
Epic duration: 2026-06-08 to 2026-06-10 (merge date)
Commits in epic branch: 19 (16 docs-spec + 3 implementation)
Merge: PR #83 (2026-06-10) — "feat(quick-fix): implement EPIC-QuickFixWorkflow — AC BP-600 /quick-fix slash command"

---

## Summary

EPIC-QuickFixWorkflow delivered AC BP-600: a fast-path `/quick-fix` slash command that
lets users patch a diagnosed bug in the current worktree — without branch switching,
without the full `/build-feature` pipeline overhead — while preserving quality discipline
(AC traceability, TDD red/green cycle, commit gating, escalation path to full pipeline).

The epic produced a 516-line `templates/skills/quick-fix/SKILL.md`, a 440-line
`templates/workflows-js/quick-fix.js`, a new `templates/commands/quick-fix.md` slash
command, and thorough spec documentation across `docs/architecture/agent_delivery_workflows.md`
and `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md`.

All 16 tickets were completed on 2026-06-08; the implementation commits landed
2026-06-10 (same day as the merge). Two post-merge defects required hotfix commits:
BP-600f (no main-branch guard) on 2026-06-10 and ACS-700 (missing `origin_agent`
field in the AC scaffold) on 2026-06-17.

---

## Metrics

### Phase Agent Counts (across 16 tickets)

| Agent | Signed Off | Failed | Not Needed |
|-------|-----------|--------|------------|
| llm-expert | 16 | 0 | 0 |
| test-writer | 16* | 0 | 0 |
| test-runner | 14 | 0 | 2 |
| pr-reviewer | 16 | 0 | 0 |
| commit | 16 | 0 | 0 |
| pull-request | 0 | 0 | 16 |
| documentation-expert | 0 | 0 | 16 |
| sql-coder | 0 | 0 | 16 |

\* All 16 test-writer sign-offs are supervisor-auto-skips (`test_requirements` block absent
on every ticket). No actual test file was written by the test-writer agent during this drive.

### Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 16 |
| Completed tickets | 16 (100%) |
| Git commits (epic branch, ex. merge) | 19 |
| Blocker comments | 0 |
| Handoff comments | 0 |
| `feedback-id: (submit-failed)` events | ~23 (across 10 tickets) |
| Pre-commit hooks active during drive | 0 (all commits used `PRE_COMMIT_ALLOW_NO_CONFIG=1`) |
| Post-merge hotfix defects | 2 (BP-600f, ACS-700) |

### Feedback System

No structured feedback is available for this epic. The `debugging/logs/` directory did not
exist in the epic worktree; all `submit_feedback.py` calls failed silently with
`(submit-failed)`. Approximately 23 feedback events were lost across 10 of the 16 tickets.
Quantitative category breakdown is unavailable. This is the same missing-sink pattern
documented in TICKET-20260527-FeedbackSinkPreDriveCheck.

---

## What Went Well

- **Zero blockers across all 16 tickets.** The dependency graph (5 AC branches: 600a
  through 600e) was respected throughout; no ticket blocked a sibling.
- **Single-day ticket completion.** All 16 documentation-spec tickets reached `status: done`
  on 2026-06-08, allowing the implementation sprint to begin immediately.
- **llm-expert delivered consistent, internally cross-referenced documentation.** Each of
  the 16 sections it added to `agent_delivery_workflows.md` and ADR-006 is aligned on
  Gherkin contract, dispatch contract table, ordering invariant, and DECISION HISTORY.
  No rewrite was needed post-merge.
- **pr-reviewer surfaced and resolved a medium finding inline (ticket 09).** The missing
  `last_updated` date in `agent_delivery_workflows.md` was caught and fixed by the
  pr-reviewer without creating a new ticket — the right outcome for a trivial omission.
- **Commit message discipline held.** All 16 documentation commits follow the
  `docs(quick-fix): ... (AC BP-600x-y)` convention, making the git log readable and
  bisect-friendly.
- **Escalation path was clean.** No ticket triggered the brainstorm-lead or required
  user input. The pr-reviewer surfaced one medium concern (ticket 05 lock file) without
  misclassifying it as a blocker.

---

## Friction Points

- **FP-1 — Implementation not governed by any ticket.**
  The three commits that deliver the runnable feature — `dddf50b6` (skill + slash command),
  `6601fe68` (quick-fix.js), `d0f419bf` (slash command wiring fix) — were pushed outside
  the 16-ticket structure. No ticket carried `files_touched` pointing to
  `templates/skills/quick-fix/SKILL.md`, `templates/workflows-js/quick-fix.js`, or
  `templates/commands/quick-fix.md`. No test-writer ran against these files. No AC
  traceability exists for the implementation. This produced two post-merge defects that
  required independent hotfix commits (BP-600f, ACS-700).

- **FP-2 — Pre-commit hooks silently disabled for the entire drive.**
  Every commit in this epic used `PRE_COMMIT_ALLOW_NO_CONFIG=1`. The epic worktree lacked
  a `.pre-commit-config.yaml` (or the `.leafcutter` symlink that deploys it). This is the
  same gap documented in the pre-drive checklist under "Worktree pre-commit config". The
  checklist was not run before the drive began. As a result, `check-feedback-id`,
  `check-description-field`, `check-secrets`, and all other package hooks were silent
  throughout — the two post-merge defects might have been caught earlier if hooks had been
  active.

- **FP-3 — Feedback sink unreachable for ~23 events across 10 tickets.**
  The `debugging/logs/` directory was absent from the worktree. The pre-drive checklist
  item "Feedback sink reachable" was not run. Retrospective quantitative data is
  unavailable as a result.

- **FP-4 — Lock file in tracked docs/ tree (unresolved medium, ticket 05).**
  The pr-reviewer on ticket 05 flagged that the `/quick-fix` ID-assignment lock file
  (`docs/acceptance-criteria/<component-id>/.quick-fix-lock`) lives in the tracked `docs/`
  tree and may be accidentally committed. The finding was noted but no follow-up ticket was
  created and the quick-fix.js workflow script was authored without addressing it.

- **FP-5 — No main-branch guard in initial implementation (post-merge BP-600f).**
  The `/quick-fix` skill spec (ticket 01, AC BP-600a-1) documented that the workflow
  operates "in the current worktree without branch switching" but did not specify behaviour
  when the current branch IS main. The first post-merge hotfix (2026-06-10) added a
  user-confirmation gate for the main branch case. This gap was present in the spec and
  propagated to the implementation.

- **FP-6 — Missing `origin_agent` field in AC scaffold (post-merge ACS-700).**
  The quick-fix workflow's AC creation phase produced YAML files missing the `origin_agent`
  field required by the `check-ac-governance` hook. This was not caught during the drive
  because the hook was silently disabled (FP-2). The fix arrived 2026-06-17, one week after
  merge.

---

## Knowledge Gaps Found

- **Gap-1: No ticket governing implementation when an epic is doc-spec-then-implement.**
  When an epic splits into a documentation/spec phase (16 tickets) and a later
  implementation phase (ad-hoc commits), the implementation phase is ungoverned. The
  AC→ticket→test-writer→python-coder→pr-reviewer chain never ran for the 516-line SKILL.md
  or the 440-line quick-fix.js. Future epics with this two-phase structure should either
  (a) include implementation tickets in the original plan, or (b) create an implementation
  follow-up ticket before pushing the implementation commits.

- **Gap-2: Pre-drive checklist is documented but not enforced.**
  The CLAUDE.md pre-drive checklist covers worktree pre-commit config and feedback sink
  reachability, but it is advisory. Both gaps (FP-2, FP-3) were already documented and
  still occurred. There is no automated pre-flight gate at the start of a `/build-feature`
  invocation.

- **Gap-3: Spec omission propagates silently to implementation.**
  The main-branch guard (BP-600f) and the `origin_agent` requirement (ACS-700) were
  both spec gaps in the 16-ticket documentation. Because the implementation commits were
  not governed by tickets, there was no ac-validator or pr-reviewer pass that would have
  caught the discrepancy between the spec and the implementation.

- **Gap-4: Lock file location for quick-fix ID atomicity is unsafe.**
  The quick-fix ID-assignment algorithm uses a lock file under the tracked `docs/` tree.
  A stale lock file would get staged and committed unintentionally. A gitignored path
  (e.g. `/tmp/` or a `.git/`-adjacent path) would be safer. This gap was surfaced in
  ticket 05 and never resolved.

---

## Subagent Quality Trends

No supervisor feedback entries found for this epic. The feedback sink (`debugging/logs/`)
was absent from the epic worktree; all `submit_feedback.py` calls failed silently with
`(submit-failed)`. Subagent quality data is unavailable.

---

## Unresolved Feedback

The `debugging/logs/feedback.jsonl` file is absent from this worktree (the entire
`debugging/` directory did not exist during the drive). Approximately 23 feedback events
were lost. The `aggregate.py --unresolved` check cannot be run against a missing sink.
Run `/feedback-review` against the main checkout to check for any surviving entries.

---

## Proposed Improvements

### KI-1: Implementation commits must be governed by a ticket when an epic uses a doc-spec-then-implement split

**Proposed Knowledge Item text:**

When an epic's ticket batch is entirely documentation/specification work (all tickets
assign only `llm-expert` or `documentation-expert`), the implementation commits that
follow MUST be governed by at least one additional ticket with `files_touched` listing
the implementation files, and that ticket must pass the full phase chain (test-writer,
python-coder or llm-expert, pr-reviewer, commit). Ad-hoc implementation commits pushed
outside the ticket system have no AC traceability, no test-writer coverage, and no
pr-reviewer gate — and are the same phantom-done risk documented in
EPIC-PhantomDoneFilesTouched. If the implementation is too large for one ticket, create
a follow-up sub-epic before pushing the first implementation commit.

Routing (route-knowledge decision tree, Step 4/5):
The rule is 4+ sentences with a rationale — it warrants a bullet addition to the
Pre-Drive Checklist section of CLAUDE.md (Step 5 → `CLAUDE.md-toc`).

**Proposed diff (addition to the "Pre-Drive Checklist" section in CLAUDE.md):**

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ Pre-Drive Checklist section @@
+### Implementation coverage for doc-spec epics
+
+**What to check:** If the epic's Master_Plan shows all `agents:` maps contain only
+`llm-expert` or `documentation-expert` (no `python-coder`, `frontend-coder`, or
+`llm-expert` writing implementation files), verify that at least one implementation
+ticket exists (status: todo or in_progress) with `files_touched` pointing to the
+source files the feature will create or modify.
+
+**If missing:** Create an implementation ticket before pushing any source-file commit.
+Ad-hoc implementation commits pushed outside the ticket system have no AC traceability,
+no test-writer gate, and no pr-reviewer gate — this is the same phantom-done pattern as
+EPIC-PhantomDoneFilesTouched. Reference: EPIC-QuickFixWorkflow FP-1 (2026-06-10).
```

Destination: `CLAUDE.md` (Pre-Drive Checklist section, after "Real-artifact behavioral
spot-check before declaring done")

---

### KI-2: quick-fix lock file should use a gitignored path

**Proposed Knowledge Item text:**

The `/quick-fix` ID-assignment algorithm uses an atomicity lock file. The lock file
path must be in a gitignored location (e.g. `$TMPDIR` or `.git/quick-fix-lock`) and
must never reside under `docs/acceptance-criteria/`. A tracked lock file will be staged
and committed unintentionally by the commit agent. Reference: EPIC-QuickFixWorkflow
ticket 05 pr-reviewer medium finding (2026-06-08), never resolved.

Routing (route-knowledge decision tree, Step 7):
This is agent-specific knowledge for the `quick-fix` skill. Route to
`templates/skills/quick-fix/SKILL.md`.

**Proposed diff (addition to templates/skills/quick-fix/SKILL.md):**

```diff
--- a/templates/skills/quick-fix/SKILL.md
+++ b/templates/skills/quick-fix/SKILL.md
@@ ID Assignment section @@
+## Lock File Safety
+
+The ID-assignment atomicity lock file MUST be written to a gitignored path.
+Acceptable locations:
+- `$TMPDIR/quick-fix-<component>.lock`
+- `.git/quick-fix-<component>.lock`  (inside .git, not tracked)
+
+MUST NOT be placed under `docs/acceptance-criteria/` or any other tracked
+directory. A tracked lock file will be staged and committed by the commit
+agent, causing phantom files in the AC store.
+(Source: EPIC-QuickFixWorkflow retrospective KI-2, 2026-07-10.)
```

Destination: `templates/skills/quick-fix/SKILL.md` (ID Assignment section or equivalent)

---

### KI-3: /quick-fix spec must include main-branch guard as an explicit AC

**Proposed Knowledge Item text:**

When designing a workflow that "operates in the current worktree," the spec must
explicitly state the behaviour when the current branch is `main` (or another protected
branch). Omitting this creates an unstated assumption that callers will only use the
workflow on feature branches. The AC should be: "Given the user is on main, When they
invoke /quick-fix, Then the workflow prompts for confirmation before proceeding." This
gap produced post-merge hotfix BP-600f (2026-06-10) one day after the epic merged.
Reference: EPIC-QuickFixWorkflow FP-5.

Routing (route-knowledge decision tree, Step 4):
Short, universal AC-authoring rule — fits as a bullet in CLAUDE.md inline.

**Proposed diff (addition to CLAUDE.md, under ## Implementation Conventions):**

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ ## Implementation Conventions @@
+### Workflow specs must include a protected-branch guard AC
+
+When a workflow spec says it "operates in the current worktree" or "on the current
+branch," add an explicit AC for the case where the branch is `main` or another
+protected ref. Default behaviour should be: warn the user and require confirmation
+before proceeding. Omitting this produced post-merge hotfix BP-600f one day after
+EPIC-QuickFixWorkflow merged (2026-06-10).
```

Destination: `CLAUDE.md` (Implementation Conventions section)

---

*Retrospective written by retrospective-agent. Per protocol, none of the above KI/rule
diffs are applied automatically. Type "yes" to apply an item, "skip" to skip it, or
"edit" to revise the proposed text.*
