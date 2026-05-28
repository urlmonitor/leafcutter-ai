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
  documentation-expert: needed
  reference-author: needed
  pr-reviewer: needed
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

- [ ] documentation-expert
- [ ] reference-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert / reference-author

- [ ] Read all hook scripts in `leafcutter-ai/templates/hooks/` (or `.claude/hooks/` if templates not present) and `leafcutter-ai/templates/settings.json` to build the catalogue.
- [ ] Write `leafcutter-ai/docs/reference/claude-code-hooks.md` with:
  - **Hook catalogue table**: one row per deployed hook with columns: Hook Name, Event Type (PreToolUse | PostToolUse), Matcher (tool name / glob / regex), Description (one line), File.
  - **stdin contract**: full JSON schema for the object Claude Code sends to hooks on stdin. Cover `tool_name`, `tool_input` (and its sub-keys for common tools), `session_id`, etc.
  - **stdout contract for PreToolUse**: the JSON structure a hook must write to stdout to block tool execution (`{"block": true, "message": "..."}`). Document that exit 0 + no output = pass-through.
  - **PostToolUse contract**: observational — Claude Code reads stdout but does not act on it. Document exit code semantics.
  - **Exit codes**: 0 = success, non-zero = error. For PreToolUse: non-zero = block. For PostToolUse: non-zero = log warning only (fail-open).
  - **Timeout guidance**: default timeout value, recommendation to keep hooks under 500ms, pattern for long-running hooks (background process + return immediately).
  - **Fail-open convention**: every hook MUST wrap its body in a try/except and exit 0 on unexpected errors, with the error printed to stderr for diagnostics.
  - **Registration schema**: document the `settings.json` entry structure (`event`, `matcher`, `command`).
- [ ] Add a "Naming collision" callout: Claude Code hooks vs pre-commit hooks — link to the pre-commit hooks guide (ticket 03).
- [ ] Ensure the doc has valid frontmatter (type: reference).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible.
