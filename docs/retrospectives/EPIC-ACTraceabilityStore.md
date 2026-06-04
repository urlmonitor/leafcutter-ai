# Retrospective: EPIC-ACTraceabilityStore

Date: 2026-06-04
Epic duration: 2026-06-04 (branch opened) to 2026-06-04 (PR #46 merged)
Commits: ~40 (branch: EPIC-ACTraceabilityStore, PR #46)

---

## Summary

EPIC-ACTraceabilityStore promoted Acceptance Criteria from prose buried in
ticket bodies to first-class, addressable, versionable YAML entities. The
epic delivered a portable `docs/acceptance-criteria/` store (scaffolded by
`build.py`), a JSON Schema validator (ADR-007), two bidirectional pre-commit
hooks, and AC-aware integrations in five agents (BA, test-writer,
ticket-authoring, test-failure-triage, debug skill). The `origin_agent` field
(ticket 10) and the debug-skill AC query step (ticket 11) were scope additions
added mid-epic after the core scaffold was proven.

The epic merged cleanly after one mid-epic `git merge origin/main` rebase to
absorb the EPIC-FinalizeFeatureHardening and EPIC-TestFixtureConvention
deliverables. A single post-merge test failure (`parity_test` not listing
`acceptance-criteria` in `non_artifact_dirs`) was fixed immediately as a
follow-up commit on main.

---

## Metrics

| Ticket | Description | Status |
|--------|-------------|--------|
| 01 | AC YAML schema + JSON Schema validator + ADR-007 | done |
| 02 | build.py scaffold phase for docs/acceptance-criteria/ | done |
| 03 | Pre-commit hook: test tagging (covers:) | done |
| 04 | Pre-commit hook: AC coverage enforcement | done |
| 05 | BA agent AC query step | done |
| 06 | Test-writer AC integration + covers: tag emission | done |
| 07 | Ticket-authoring AC wiring (Step 2.5) | done |
| 08 | Test-failure-triage AC status lookup | done |
| 09 | How-to and reference docs for AC store | done |
| 10 | origin_agent field in schema + authoring stamp | done |
| 11 | Debug skill AC query step | done |

All 11 tickets completed. No blockers. No retries recorded.

---

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 11 |
| Completed tickets | 11 |
| Git commits (branch) | ~40 |
| Mid-epic merges from main | 2 (union resolution + conflict resolution) |
| Post-merge fixes | 1 (parity test) |
| PR | #46 (urlmonitor/leafcutter-ai) |
| Blocker comments | 0 |

---

## What Went Well

- **ADR-007 authored first (ticket 01).** Writing the schema decision record
  before any YAML files were created gave tickets 02–11 a stable canonical
  reference. No schema churn occurred mid-epic — the ID format, field names,
  and status lifecycle were settled once and stayed settled.

- **Scaffold-first ordering (01 → 02 → hooks → agents) paid off.** Each
  layer built on a solid prior layer. The pre-commit hooks (03, 04) could
  reference the schema from 01; the agent integrations (05–08) could reference
  the live scaffold from 02. There were no circular dependency issues.

- **Scope additions (tickets 10, 11) were clean extensions.** `origin_agent`
  (ticket 10) extended the schema with a backward-compatible optional field.
  The debug-skill AC query (ticket 11) touched only the debug skill template
  and added no cross-cutting changes. Both were added after the core was
  proven without requiring any rework of earlier tickets.

- **Mid-epic main merges were uneventful (mostly).** The first union-
  resolution merge was clean. The second surfaced a single conflict in
  `test-failure-triage.md` that was resolved correctly in place.

- **Post-merge failure was diagnosed and fixed in one commit.** The parity
  test failure after merge was a straightforward `non_artifact_dirs` list
  omission — root cause obvious from the test output. Fix took one commit and
  all 295 tests passed.

---

## Friction Points

- **Mid-epic conflict in test-failure-triage.md.** EPIC-FinalizeFeatureHardening
  (PR #45, merged just before) also touched `test-failure-triage.md`. The
  conflict required a manual union resolution. The deliverable was correct but
  added merge overhead. Root cause: two epics modifying the same agent template
  concurrently without coordination.

- **Post-merge parity test regression.** The `docs/acceptance-criteria/`
  directory was not added to `non_artifact_dirs` in the parity test. This
  test enforces that every directory in `docs/` is either in the known-
  artifacts list or the known-non-artifacts list. The new directory was
  neither. A pre-merge test run in the worktree would have caught this
  (the worktree `docs/acceptance-criteria/` was empty, so the test likely
  passed there but failed post-merge when the directory existed in the target
  project layout). The fix was trivial but the regression escaped to main.

- **11 tickets is at the upper bound for a single epic.** Tickets 10 and 11
  were scope additions. While both were clean, the epic spanned a large
  surface area (build pipeline, 2 pre-commit hooks, 5 agent templates, 2 docs
  pages, 1 ADR, 1 schema file). Future epics of this scope should be
  considered for splitting at the "store + enforcement" vs "agent integration"
  seam.

---

## Knowledge Gaps Found

### KG-1: Parity test must be updated when new docs/ directories are scaffolded

Any ticket that adds a new directory under `docs/` (or to the `build.py`
scaffold output) must also update the parity test's `non_artifact_dirs` or
`artifact_dirs` list. This is currently undocumented — the hook that enforces
it (parity test) is only run on `main`, not in the worktree during development.

**Proposed addition to ticket-authoring AC workflow (ticket 07 deliverable):**

> When a ticket adds a new scaffold directory to build.py (e.g. a new
> `docs/<name>/` entry), the ticket's AC checklist must include: "Update
> `unit_tests/` parity test to list the new directory in `non_artifact_dirs`
> or `artifact_dirs`."

Routing: addition to `tickets/` ticket-authoring AC workflow doc and the
test-writer agent's awareness of parity test implications.

### KG-2: Concurrent agent template modifications need a cross-epic coordination signal

Two epics (EPIC-ACTraceabilityStore and EPIC-FinalizeFeatureHardening) both
modified `test-failure-triage.md` in parallel. Neither epic's ticket had
visibility into the other's modifications, making the merge conflict
undetectable pre-flight.

**Proposed mechanism:** `Master_Plan.md` for each epic should declare
`shared_files` — a list of template paths the epic modifies. Before a new
epic branch is created, a pre-flight check could detect overlap with open
epic PRs and warn the operator.

Routing: future ticket against the epic-planning tooling or the
worktree-agent's pre-flight checks.

---

## Proposed Improvements

### PI-1: Add parity-test guard to AC acceptance criteria checklist

**Proposed AC addition to the ticket-authoring skill (Step 2.5):**

> If the ticket scaffolds a new directory via `build.py`, the AC set must
> include:
>
> ```
> Given a fresh build.py scaffold run,
> When the parity test is executed on main,
> Then the new directory appears in non_artifact_dirs or artifact_dirs
>   and the test passes.
> ```

### PI-2: Shared-files overlap detection in worktree pre-flight

**Proposed worktree-agent enhancement:**

Before creating a new epic worktree, query all open PRs for `files_touched`
(or `shared_files` if declared in Master_Plan) and emit a warning if overlap
is detected:

```
Warning: EPIC-<new> and EPIC-<existing> (PR #N, open) both modify:
  - leafcutter/templates/agents/test-failure-triage.md
Proceed anyway? The merge may require a conflict resolution.
```

Routing: worktree-agent pre-flight check sequence.

---

*Proposed improvements above require explicit user approval before being applied.
No files beyond this retrospective have been modified.*
