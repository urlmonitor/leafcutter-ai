---
title: "Kill orphan SQL test workers unconditionally before every commit attempt"
status: done
components:
  - build_system
created: 2026-05-22
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - .claude/skills/build-single-ticket/SKILL.md
  - .claude/skills/building-epics/SKILL.md
  - .claude/agents/commit.md
agents:
  architect-review: not_needed
  python-coder: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  test-writer: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  sql-coder: not_needed
  user-surface-smoker: not_needed
---

# 04: Kill orphan SQL test workers unconditionally before every commit attempt

## Actor / Goal

In order to prevent orphan SQL test worker processes from blocking the commit phase, the commit agent (or the commit phase preamble in the building-epics runbook) must terminate all SQL test worker processes unconditionally before staging and committing — not just idle ones.

## Context

Feedback IDs: fb_2026-05-17_e7510ecc, fb_2026-05-17_d39b0998.

When `test-runner` or `sql-test-writer` leaves background worker processes running (e.g. a pytest-xdist worker stuck in a DB connection wait), those processes hold file locks or open handles that cause `git commit` to fail or hang on Windows. The existing memory says "kill only idle workers" — but the block recurs because workers that are actively waiting on a lock are NOT idle and are therefore NOT killed.

The fix: before every `git commit` invocation in the commit phase, kill all SQL test worker processes unconditionally (idle OR active). The processes are ephemeral test harness workers — there is no state loss from killing them. Any actively-running test that was meaningful would have already written its result before blocking on the lock.

The kill step should run as a pre-commit preamble in the commit agent's instruction, not as a pre-commit hook (hooks are not the right place for process management — they run inside the git machinery and failures there can corrupt git state).

## Acceptance Criteria

```gherkin
Given a SQL test worker process is alive (idle or active) when the commit phase starts
When the commit agent runs its pre-commit preamble
Then all SQL test worker processes are terminated before git add or git commit is called
And git commit completes without a file-lock block

Given no SQL test worker processes are alive when the commit phase starts
When the commit agent runs its pre-commit preamble
Then the kill step is a no-op (exits 0 with no output or "no processes found" message)
And git commit proceeds normally
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-25 10:30 — documentation-expert (status: ok)

Added Step 0 ("Kill orphan test workers") to `templates/agents/commit.md` as an unconditional preamble before Step 1. Includes both `pkill -f "pytest"` (Unix) and `taskkill /F /FI ... *pytest*` (Windows) with `|| true` guards. Updated `templates/skills/building-epics/SKILL.md` §5.5 with a new "Exception" paragraph clarifying that the commit-phase preamble kill is deliberately unconditional (unlike the pre-flight idle-only sweep). Searched for "kill only idle" in skill and agent files — the idle-only rule in §5.5 is intentionally preserved for the pre-flight sweep context; the new exception paragraph disambiguates the two scopes.

### 2026-05-25 10:30 — pr-reviewer (status: ok)

Review passed. Step 0 uses `|| true` on both platform commands (no-op when no processes match). The unconditional kill is safe because by commit time all test phases have completed. The building-epics §5.5 exception paragraph correctly scopes the unconditional kill to the commit-phase preamble while preserving the idle-only rule for pre-flight sweeps. All acceptance criteria met.

## Implementation Tasks

### documentation-expert
- [x] Locate the commit-phase preamble in `.claude/agents/commit.md` — identify where the agent is instructed to stage files and run `git commit`. Add a new step immediately before staging:
  ```bash
  # Kill any orphan SQL test worker processes (idle or active) to prevent file-lock blocks
  taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *pytest*" 2>nul || true
  pkill -f "pytest" 2>/dev/null || true
  ```
  Use both commands (Windows + Unix) with `|| true` so the preamble never blocks on a no-match. Document that this is unconditional — not "only idle".
- [x] If `.claude/skills/building-epics/SKILL.md` or `.claude/skills/build-single-ticket/SKILL.md` has a commit-phase section that describes the staging preamble, add the kill step there as well so it is consistent.
- [x] Update the in-memory note (if any) that says "kill only idle" — change it to "kill all, unconditionally". Search for the old phrasing in the skills and agent files.

## Risk & Safety

- Touches money? No.
- Touches data? No — test workers are ephemeral. Killing them loses no test results that matter (if a test was meaningful, the result was already written to stdout before the lock blocked).
- Reversibility? Removing the kill step from the agent instructions is trivially reversible.
- Platform note: the `taskkill` command is Windows-only; `pkill` is Unix-only. Both must be present with `|| true` guards for the skill to be portable. The current platform is Windows 11 but the skill is portable by design.
