---
title: "Pre-commit hook: enforce max ACs per agent and ticket-level AC limits"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 02_ac_format_and_frontmatter.md
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: pre_commit_hook
actuation_contract: "Blocks git commit when any ticket file in the staged diff has >7 ACs for a single agent or >20 ACs total, printing the agent name and count."
files_touched:
  - scripts/commit_guardian/hooks/check_ac_limits.py
  - scripts/commit_guardian/commit_guardian.json
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: needed
---

# 02b: AC Count Pre-Commit Hook

## Business Intent

Prompts can be ignored. Hooks cannot. If the IT PO or any agent writes a ticket
with 12 ACs for python-coder, the ticket is too big and should be split. A
pre-commit hook enforces this mechanically so no oversized ticket reaches the
implementation pipeline.

## Context

### The Limits

| Limit | Value | Rationale |
|-------|-------|-----------|
| Max ACs per agent | 7 | 3-5 is the sweet spot; 7 is the hard ceiling before splitting |
| Max total ACs per ticket | 20 | Beyond this, the ticket is an epic in disguise |
| Integration ACs | Excluded from per-agent count | They're cross-cutting, not owned by one agent |

### Detection Logic

The hook parses ticket files in the staged diff:

1. Find `## Agent Contracts` section
2. For each `### <agent-name>` subsection, count lines matching `- \[ \] AC-\d+:`
3. Exclude lines containing `<!-- scope: integration -->` from per-agent counts
4. Count total ACs across all agent blocks
5. Block if any agent exceeds 7 or total exceeds 20

### What About v1 Tickets?

v1 tickets (flat `## Acceptance Criteria` with Gherkin) don't have agent blocks.
The hook skips files without `## Agent Contracts`. No false positives on old tickets.

### Failure Routing

When the hook blocks, `precommit-autofix` routes the failure back to the IT PO
(not Haiku, not Sonnet — this is a design decision, not a mechanical fix). The
IT PO receives the error message and splits the ticket:

```
check_ac_limits.py blocks
  → precommit-autofix reads hook output
    → routes to IT PO (structural fix, requires Opus)
      → IT PO splits the oversized ticket into two+ tickets
        → commit retries
```

The IT PO's split protocol (§7 in its prompt) handles this: it creates new
sibling ticket files, redistributes ACs across them, updates `depends_on`
chains, and updates `Master_Plan.md` if in an epic.

### Override Mechanism

For rare cases where a legitimate ticket needs >7 ACs for one agent (e.g., a
comprehensive API with many endpoints), allow an explicit override in frontmatter:

```yaml
ac_limit_override: true  # Reviewed — splitting would create worse coupling
```

The hook prints a warning but does not block when this flag is set. The IT PO
may set this flag during the split protocol if it determines splitting would
create worse coupling than keeping the ACs together.

## Agent Contracts

### python-coder

- [x] AC-1: `check_ac_limits.py` exists and is registered in `commit_guardian.json` as a pre-commit hook
- [x] AC-2: Hook parses `## Agent Contracts → ### <agent-name>` blocks and counts `- [ ] AC-N:` lines per agent
- [x] AC-3: Hook excludes `<!-- scope: integration -->` ACs from per-agent counts (they count toward total only)
- [x] AC-4: Hook blocks with clear error on stderr (including structured JSON for precommit-autofix routing: `{"hook": "check_ac_limits", "fix_agent": "it-po", "violations": [...]}`) when any agent has >7 ACs or total >20
- [x] AC-5: Hook skips files without `## Agent Contracts` section (backward compatible with v1)
- [x] AC-6: Hook respects `ac_limit_override: true` in frontmatter — prints warning but does not block

## Sign-offs

- [x] test-writer — 2026-06-04 00:00
- [x] python-coder — 2026-06-04 10:30
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
- [ ] user-surface-smoker

## Smoke Fixture

```yaml
surface: check_ac_limits
fixture_input: |
  (stage a ticket file with 8 ACs under one agent block, run git commit)
assertion: "(?i)(BLOCKED|max 7|split the ticket)"
placeholder_signature: "(?i)(TODO|PLACEHOLDER|not implemented)"
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only hook, only inspects staged ticket files.
- Reversibility? Fully reversible — remove hook from commit_guardian.json.
- Risk: False positives on tickets that legitimately need many ACs.
  Mitigation: `ac_limit_override` escape hatch with explicit frontmatter flag.

## Comments

### 2026-06-04 00:00 — ticket-supervisor (status: ok)
test_requirements empty — test-writer phase skipped (docs-only or config-only ticket)

### 2026-06-04 10:30 — python-coder (status: ok)
feedback-id: fb_2026-06-04_0554253e
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
Created `scripts/commit_guardian/hooks/check_ac_limits.py` implementing all 6 ACs: parses `## Agent Contracts` subsections, counts non-integration `- [ ] AC-N:` lines per agent, blocks with structured JSON on stderr when any agent exceeds 7 or total exceeds 20, skips v1 tickets (no Agent Contracts section), and respects `ac_limit_override: true` frontmatter flag (warn-only). Registered in `commit_guardian.json` as `check-ac-limits` hook targeting `tickets/.*\.md$` files. Ruff E722/BLE001/TRY clean; smoke tests all pass.
