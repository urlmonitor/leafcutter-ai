# Retrospective: EPIC-ErrorHandlingEnforcement

Date: 2026-06-01
Epic duration: 2026-05-31 (created) to 2026-06-01 (merged, PR #27)
Commits: 9 implementation + 1 merge = 10 total (branch: worktree-EPIC-ErrorHandlingEnforcement)

---

## Summary

EPIC-ErrorHandlingEnforcement delivered three complementary layers of exception-handling
enforcement across the leafcutter codebase and any project it installs into:

1. **Ruff pre-commit rules** (ticket 01) — E722, BLE001, and the TRY family block
   bare-except and silently-swallowed exceptions at commit time.
2. **commit-guardian AST hook** (ticket 02) — `check_exception_handling.py` uses
   Python's `ast` module to inspect staged files before commit, providing richer
   diagnostic messages than Ruff alone.
3. **Error Handling Policy in CLAUDE.md and python-coder template** (ticket 03) —
   four explicit rules with Ruff rule ID references prime every contributor at
   session start, reducing the frequency of violations before enforcement fires.

The epic had a clean linear dependency graph: ticket 01 (rules) -> ticket 02 (hook) ->
ticket 03 (policy). All three completed within one day. No retries and no merge
conflicts.

---

## Metrics

| Component | Status |
|-----------|--------|
| Ruff rules enabled in pre-commit (E722, BLE001, TRY) | Done |
| check_exception_handling.py AST hook | Done |
| Hook registered in commit_guardian.json + settings.json | Done |
| Error Handling Policy in CLAUDE.md | Done |
| Error Handling Policy in templates/agents/python-coder.md | Done |

All 3 tickets completed. No failures. No retries recorded.

---

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 3 sub-tickets |
| Completed tickets | 3 |
| Git commits | 10 (including merge commit) |
| PR | #27 (urlmonitor/leafcutter-ai) |
| Breaking change | No |
| ADRs authored | 0 |

---

## What Went Well

- **Three-layer design was coherent.** Mechanical enforcement (Ruff + AST hook) and
  declarative policy (CLAUDE.md) are complementary rather than redundant. The policy
  explains the rules to agents and humans before code is written; the mechanical layers
  catch violations after. No layer was skipped or partially implemented.

- **Execution speed.** The epic was planned on 2026-05-31 and merged by 2026-06-01.
  The linear dependency chain (01 -> 02 -> 03) kept the critical path short. There was
  no blocked waiting between tickets.

- **AST hook is specific enough to be useful.** The hook targets AST node patterns
  rather than text patterns. This avoids false positives from comments or strings that
  contain exception-handling vocabulary, and provides actionable line-level diagnostics.

- **Policy section is self-contained.** The `## Error Handling Policy` section in
  CLAUDE.md names the Ruff rule IDs (E722, BLE001, TRY) alongside the plain-English
  rules. A developer or agent seeing a linter failure can cross-reference immediately
  without needing to search external documentation.

- **Portability was treated as a first-class requirement.** All three layers install
  via `build.py` with no target-project-specific configuration. This is consistent with
  the leafcutter MVP goal of being portable across repos.

---

## Friction Points

- **Inbox ticket files were not tracked by git.** The epic's inbox folder
  (`tickets/00_inbox/epics/EPIC-ErrorHandlingEnforcement/`) contained untracked files
  at finalization time. The `done/` subfolder inside the inbox had stale copies of
  tickets 01 and 02 that were never committed to git. This created ambiguity during the
  archive step about which file was canonical. The worktree-local copy was ahead of
  main for these files.

- **03 already appeared in 99_done before archival.** Ticket 03's completed version
  was committed directly into `tickets/99_done/EPIC-ErrorHandlingEnforcement/` during
  the branch, while the inbox still held the original `status: todo` version. This
  left the epic's inbox in a partially-archived state at merge time.

- **No ADR was authored.** The AST hook represents a policy decision about what Python
  code patterns are permitted in the codebase. An ADR documenting the rationale for the
  four rules (and why BLE001 and TRY were selected over a simpler approach) would be
  valuable future reference. `requires_adr: false` was set in the ticket frontmatter —
  this should be reconsidered for enforcement-mechanism tickets.

---

## Knowledge Gaps Found

- **No convention for tracking partial inbox state across worktrees.** When a ticket's
  completed version lands in `99_done/` via a commit on the branch, the original
  `00_inbox/` copy becomes stale. There is no automated cleanup of the inbox copy at
  commit time. Finalization then has to reconcile two versions. A simple convention
  (e.g., commit a `git rm` of the inbox copy when the ticket is first moved to done)
  would prevent this drift.

- **Enforcement-mechanism tickets should default to `requires_adr: true`.** When a
  ticket introduces a rule that governs what code the project will accept, it is a
  system boundary decision. The current ticket-authoring guidance does not flag this
  category. An ADR trigger for "adds or modifies a lint/hook enforcement rule" would
  ensure the decision is documented.

---

## Proposed Improvements

### KI-1: Commit a `git rm` of the inbox ticket when first archiving to done

**Proposed convention:**

> When a ticket is moved to `tickets/99_done/` (either directly or via the
> `status-checker` agent), immediately stage a `git rm` of the original inbox copy
> in the same commit. Do not leave the inbox copy as an untracked or stale file.
> The `99_done/` copy is canonical from that point forward.

Routing: `templates/skills/status-checker/SKILL.md` — add as a note in the
ticket-close procedure.

---

### KI-2: Enforcement-mechanism tickets default to `requires_adr: true`

**Proposed rule addition to ticket-authoring guidance:**

> Set `requires_adr: true` in ticket frontmatter when the ticket:
> - Adds or modifies a pre-commit hook or commit-guardian hook
> - Enables or disables a Ruff/linter rule
> - Adds or modifies a policy section in CLAUDE.md that governs what code is
>   permitted in the codebase
>
> These are enforcement boundary decisions. An ADR documents the four Ws:
> what is being enforced, why this rule was chosen over alternatives, what the
> false-positive risk is, and what the migration path is for existing code.

Routing: `templates/skills/ticket-authoring/SKILL.md` — add alongside the existing
ADR trigger guidance.

---

*All proposed KIs above require explicit user approval before being applied.
No files have been modified by this retrospective.*
