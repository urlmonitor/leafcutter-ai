---
title: "Reference: Claude Code Hooks"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
requires_documentation:
  - reference
files_touched:
  - leafcutter-ai/docs/reference/claude-code-hooks.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  reference-author: signed_off
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 08: Reference: Claude Code Hooks

## Actor / Goal

In order to give developers a comprehensive reference for all deployed Claude Code hooks, we need a doc listing every hook, its event type, matcher, stdin/stdout contract, timeout guidance, and the fail-open convention so that developers can reason about the hook pipeline without reading source code.

## Context

Claude Code hooks (PreToolUse / PostToolUse) are deployed to `.claude/hooks/` and registered in `.claude/settings.json`. Currently there is no reference doc enumerating them. The hooks are discovered by reading individual Python files or the settings JSON directly. This makes it hard to understand the full hook pipeline, diagnose unexpected behaviour, or add a new hook without conflicts.

This reference complements the how-to guide (ticket 04) which covers creation; this doc covers the catalogue and contracts.

Key source locations:
- `leafcutter-ai/templates/hooks/` — source hook scripts
- `leafcutter-ai/templates/settings.json` — hook registration
- `.claude/hooks/` (built output) — what is actually deployed

## Acceptance Criteria

```gherkin
Given the reference doc exists at leafcutter-ai/docs/reference/claude-code-hooks.md
When a developer reads it
Then they find a table of all deployed hooks with: name, event type, matcher, and one-line description of what it does

Given the doc covers stdin/stdout contracts
When it is read
Then it documents the exact JSON format for PreToolUse and PostToolUse events and the expected response structure for each

Given the doc covers timeout guidance
When it is read
Then it specifies the default timeout for hooks and recommendations for keeping hooks fast

Given the doc covers fail-open convention
When it is read
Then it explains that hooks must catch all exceptions and exit 0 on unexpected errors to prevent blocking Claude Code

Given the doc is authored
When it passes the doc frontmatter guard
Then it has valid frontmatter including type: reference
```

## Sign-offs

- [x] documentation-expert — 2026-05-28 14:00
- [x] reference-author — 2026-05-28 14:05
- [x] pr-reviewer — 2026-05-28 14:10
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-28 14:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-28_16692c61
Read all 7 hook scripts and templates/settings.json. Authored docs/reference/claude-code-hooks.md covering: hook catalogue table, PreToolUse/PostToolUse stdin payload schemas, stdout block-decision contract, exit code semantics, per-hook timeout table, fail-open convention with code template, registration schema, bypass env vars, and the session-ID/marker-file mechanism. Named-collision callout links to managing-pre-commit-hooks.md. Frontmatter set with type: reference.

### 2026-05-28 14:05 — reference-author (status: ok)
feedback-id: fb_2026-05-28_c30e21f4
Reference doc structure verified against all acceptance criteria: catalogue table has all 7 hooks with name/event/matcher/description/file columns; stdin payload schema covers tool_name, tool_input sub-keys for all four tools, and session_id; stdout contract documents block-decision JSON for PreToolUse and observational semantics for PostToolUse; exit-code table present; timeout table with 500ms recommendation; fail-open code template; registration schema with all fields; naming-collision callout cross-linking pre-commit hooks guide; bypass env-var table; session-ID/marker-file mechanism documented. Frontmatter type: reference confirmed.

### 2026-05-28 14:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_81ab9c8f
Reviewed docs/reference/claude-code-hooks.md against all acceptance criteria. PASS on all 5 gherkin criteria: (1) catalogue table present with all 7 hooks including name, event type, matcher, description, file; (2) stdin/stdout contracts documented with JSON examples for PreToolUse (block decision JSON + empty-allow) and PostToolUse (observational); (3) timeout guidance present with per-hook table and 500ms recommendation; (4) fail-open convention documented with code template and rationale; (5) frontmatter includes type: reference. Naming-collision callout in the opening blockquote is clear and links to managing-pre-commit-hooks.md. No blockers. Approved.

## Implementation Tasks

### documentation-expert / reference-author

- [x] Read all hook scripts in `leafcutter-ai/templates/hooks/` (or `.claude/hooks/` if templates not present) and `leafcutter-ai/templates/settings.json` to build the catalogue.
- [x] Write `leafcutter-ai/docs/reference/claude-code-hooks.md` with:
  - **Hook catalogue table**: one row per deployed hook with columns: Hook Name, Event Type (PreToolUse | PostToolUse), Matcher (tool name / glob / regex), Description (one line), File.
  - **stdin contract**: full JSON schema for the object Claude Code sends to hooks on stdin. Cover `tool_name`, `tool_input` (and its sub-keys for common tools), `session_id`, etc.
  - **stdout contract for PreToolUse**: the JSON structure a hook must write to stdout to block tool execution (`{"block": true, "message": "..."}`). Document that exit 0 + no output = pass-through.
  - **PostToolUse contract**: observational — Claude Code reads stdout but does not act on it. Document exit code semantics.
  - **Exit codes**: 0 = success, non-zero = error. For PreToolUse: non-zero = block. For PostToolUse: non-zero = log warning only (fail-open).
  - **Timeout guidance**: default timeout value, recommendation to keep hooks under 500ms, pattern for long-running hooks (background process + return immediately).
  - **Fail-open convention**: every hook MUST wrap its body in a try/except and exit 0 on unexpected errors, with the error printed to stderr for diagnostics.
  - **Registration schema**: document the `settings.json` entry structure (`event`, `matcher`, `command`).
- [x] Add a "Naming collision" callout: Claude Code hooks vs pre-commit hooks — link to the pre-commit hooks guide (ticket 03).
- [x] Ensure the doc has valid frontmatter (type: reference).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible.
