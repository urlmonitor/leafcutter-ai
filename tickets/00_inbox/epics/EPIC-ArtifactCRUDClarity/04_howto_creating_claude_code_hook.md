---
title: "How-to: Creating a Claude Code Hook"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
requires_documentation:
  - how_to
files_touched:
  - leafcutter-ai/docs/how-to/creating-a-claude-code-hook.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  how-to-author: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 04: How-to: Creating a Claude Code Hook

## Actor / Goal

In order to fill the gap where Claude Code hooks have no creation automation and no canonical guide, we need a how-to guide covering event types, contracts, matchers, and the `bash -c` wrapper pattern so that any developer can add a new hook without reverse-engineering existing ones.

## Context

Claude Code hooks (PreToolUse / PostToolUse event hooks) are distinct from pre-commit hooks. They intercept Claude Code tool calls at runtime and are registered in `leafcutter-ai/templates/settings.json`. Currently:
- Pre-commit hooks have `create-hook` skill automation (though with the wrong path — fixed in ticket 10).
- Claude Code hooks have **no** equivalent skill — creation is fully manual.
- The two are both colloquially called "hooks", causing confusion in docs and conversation.

This guide should clearly establish the difference and give a step-by-step procedure for Claude Code hooks.

Key files:
- `leafcutter-ai/templates/settings.json` — hook registration
- `.claude/hooks/` — deployed hook scripts (Python files)
- `.claude/settings.json` (build output) — consumed by Claude Code at runtime

## Acceptance Criteria

```gherkin
Given the how-to guide exists at leafcutter-ai/docs/how-to/creating-a-claude-code-hook.md
When a developer follows it
Then they can create a new PreToolUse or PostToolUse hook, register it in templates/settings.json, and verify Claude Code fires it on the matching tool event

Given the guide covers the stdin/stdout contract
When it is read
Then it documents the exact JSON format Claude Code sends to the hook on stdin, and how to write exit codes and stdout to signal success/block/fail-open

Given the guide covers matchers
When it is read
Then it explains tool name matchers (exact, glob, regex) and how to scope a hook to specific tools only

Given the guide is authored
When it passes the doc frontmatter guard
Then it has valid frontmatter including type: how_to
```

## Sign-offs

- [ ] documentation-expert
- [ ] how-to-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert / how-to-author

- [ ] Read existing Claude Code hooks in `.claude/hooks/` (e.g. `ticket_frontmatter_guard.py`) to extract the stdin/stdout contract, exit code convention, and `bash -c` wrapper pattern.
- [ ] Read `leafcutter-ai/templates/settings.json` to document the hook registration schema.
- [ ] Write `leafcutter-ai/docs/how-to/creating-a-claude-code-hook.md` covering:
  1. **Naming note**: Claude Code hooks (PreToolUse / PostToolUse) vs pre-commit hooks — explain the difference up front, with a link to ticket 03's guide.
  2. **Event types**: `PreToolUse` (fires before the tool runs; can block) and `PostToolUse` (fires after; observational).
  3. **stdin contract**: JSON object Claude Code sends (`tool_name`, `tool_input`, etc.) — document the exact schema.
  4. **stdout contract**: what Claude Code reads back (for PreToolUse blockers: structured JSON with `block: true` and `message`).
  5. **Exit codes**: 0 = success/pass-through, non-zero = fail (semantics differ by event type). Document fail-open convention.
  6. **Matchers**: tool name exact match, glob pattern, regex — document all three and when to use each.
  7. **`bash -c` wrapper pattern**: explain why hooks are invoked via `bash -c "python .claude/hooks/<name>.py"` rather than directly.
  8. **Step-by-step creation**:
     - Write the hook script in `leafcutter-ai/templates/hooks/<name>.py`.
     - Register in `leafcutter-ai/templates/settings.json` under the appropriate event type with matcher.
     - Run `build.py` to deploy to `.claude/hooks/` and `.claude/settings.json`.
     - Test with a real tool invocation.
  9. **Fail-open convention**: hooks must never block Claude Code on an unexpected error — catch exceptions and exit 0.
- [ ] Add a "Common Mistakes" table (wrong exit code for PostToolUse, blocking stdin parse errors, overly broad matchers).
- [ ] Ensure the doc has valid frontmatter (type: how_to).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible.
