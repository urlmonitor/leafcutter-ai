# Retrospective: TICKET-20260601-FixHooksDeploymentPipeline

Date: 2026-06-01
Scope: single ticket (lightweight retrospective — fewer than 3 completed tickets)
Commits: 4 (bdc71f6, 6161462, 61b4676, c9b3e71)

---

## Summary

This ticket fixed a silent gap in the leafcutter build pipeline: the
`build_hooks` phase was never implemented, so `install_shims` silently skipped
the `.claude/hooks` directory every time a consumer project ran `build.py`.
Claude Code's hook walker then fell through to the project root and either
degraded or failed entirely on every tool call.

The fix added `build_hooks()` to `build_phases.py` (mirroring the `build_agents`
pattern), wired it into `artifact_phases` in `build.py`, removed the now-
redundant hook-copying logic from `build_claude_settings.py`, and added 5 unit
tests covering platforms, dry-run, and compare-before-write. The root cause of
the `/finalize-feature` discovery failure in a consuming agent was confirmed to
be a cascade from this same gap — once `.claude/hooks` was populated the
command resolves correctly.

---

## Metrics

| Phase | Signed Off | Failed | Needed |
|-------|-----------|--------|--------|
| architect-review | 1 | 0 | 1 |
| python-coder | 1 | 0 | 1 |
| test-writer | 1 | 0 | 1 |
| pr-reviewer | 1 | 0 | 1 |
| commit | 1 | 0 | 1 |
| pull-request | 1 | 0 | 1 |

All planned phases completed. No failures. No retries.

---

## Category Breakdown (Feedback System)

No structured `feedback.jsonl` entries exist for this ticket. The ticket
pre-dates feedback-system coverage for this specific run; the ticket
`## Comments` section and commit history served as the primary record.

---

## Ticket Facts

| Metric | Value |
|--------|-------|
| Priority | high |
| Component | build_pipeline |
| Commits | 4 |
| Files touched | 4 source files + 1 test file |
| Blockers | 0 |
| Handoffs | 0 |

---

## What Went Well

- Root cause was diagnosed precisely on the first investigation pass: the
  `_MANAGED_ARTIFACT_DIRS` map in `build_phases.py` already declared `"hooks"`
  as a managed type, proving the intent existed — only the build phase was missing.
- The `build_agents` pattern was a clean reference; `build_hooks` was implemented
  by direct analogy with no architectural ambiguity.
- The `/finalize-feature` discovery failure was correctly identified as a cascade
  rather than a separate bug, avoiding a duplicate ticket.
- Unit test coverage was added in the same commit as the implementation — no
  follow-up test ticket needed.
- Pre-commit hooks passed cleanly on the first attempt.

---

## Friction Points

- The redundant hook-copying code in `build_claude_settings.py` was not obvious
  from the ticket description alone; it was discovered during implementation.
  Removing it was the right call but required ad-hoc architect judgment during
  the python-coder phase rather than being specified up front.
- The ticket's sign-off checklist in the frontmatter used `needed` / `not_needed`
  but the implementation proceeded without formal per-phase `status: ok` comment
  entries — the feedback system gap noted above means phase completions are only
  traceable via commit messages.

---

## Knowledge Gaps Found

- The existence of duplicate hook-copying logic (in both `build_phases.py`
  via the new `build_hooks` and in `build_claude_settings.py`) was not documented
  anywhere. Any future build-pipeline contributor could re-introduce the same
  duplication.
- The silent-skip behavior of `install_shims` when a source directory does not
  exist is correct defensively, but it produces no warning — making the gap
  invisible in build output. A warning log line when a shim source is absent
  would surface this class of bug immediately.

---

## Subagent Quality Trends

No supervisor feedback entries found for this ticket (ticket pre-dates
EPIC-SupervisorFeedback coverage or no adjudication events occurred).

---

## Proposed Improvements

### KI: Document install_shims silent-skip behavior

install_shims silently skips any shim whose source directory does not exist.
This is correct defensively but makes missing build phases invisible. Add a
`logger.warning` (or print in dry_run mode) when a shim source path is absent,
so missing build phases surface immediately rather than after downstream failure.

Routing: `docs/how-to/` how-to guide for build pipeline contributors, or a
comment added directly in `build_helpers.py` at the `if not source_path.exists():
continue` guard.

*This KI is proposed — not applied. Confirm "yes" to apply or "skip" to defer.*

### Rule Update: Require explicit mention of code duplication risks in ticket Context

When a ticket touches a build phase that mirrors an existing phase, the Context
section should explicitly list all locations where analogous logic may exist (to
surface duplication risk before implementation begins).

```diff
- Context section: describe the missing piece and reference pattern
+ Context section: describe the missing piece, reference pattern, AND list all
+   known locations where analogous or duplicate logic exists that may need
+   consolidation
```

*This rule update is proposed — not applied. Confirm "yes" to apply or "skip" to defer.*
