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
  documentation-expert: signed_off
  how-to-author: signed_off
  pr-reviewer: signed_off
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

- [x] documentation-expert — 2026-05-28 14:00
- [x] how-to-author — 2026-05-28 14:05
- [x] pr-reviewer — 2026-05-28 14:10
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-28 14:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-28_6668c69d
Researched Claude Code hook system: read all 7 built-in hooks in templates/hooks/, templates/settings.json, and the create-hook skill. Documented stdin payload schema, stdout block-decision contract, exit code semantics, matcher forms, bash-c walker pattern, and built-in hook inventory. Guide written to docs/how-to/creating-a-claude-code-hook.md with valid how_to frontmatter.

### 2026-05-28 14:05 — how-to-author (status: ok)
feedback-id: fb_2026-05-28_9f4d4087
Structured the guide into 8 procedural steps covering all ticket acceptance criteria: naming disambiguation (Claude Code vs pre-commit hooks), event types (PreToolUse/PostToolUse), stdin contract with per-tool field table, stdout block-decision pattern, exit code semantics, matcher forms, bash-c walker pattern, hook script template with fail-open pattern, settings.json registration, build.py deployment, and testing procedure. Added common mistakes table and built-in hooks reference table. Frontmatter uses type: how_to per doc_types.json.

### 2026-05-28 14:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_75712aa8
All 4 Gherkin acceptance criteria satisfied. Guide at leafcutter-ai/docs/how-to/creating-a-claude-code-hook.md with type: how_to frontmatter. Naming disambiguation between Claude Code hooks and pre-commit hooks present up front. stdin JSON contract documented with per-field and per-tool tables. Exit code semantics and fail-open convention documented. Matcher forms (exact, pipe-separated, regex) all covered. bash-c walker pattern explained with rationale. 8-step creation procedure complete including build.py deployment and manual test. Common mistakes table covers 7 failure patterns. No blockers — approved.

## Implementation Tasks

### documentation-expert / how-to-author

- [x] Read existing Claude Code hooks in `.claude/hooks/` (e.g. `ticket_frontmatter_guard.py`) to extract the stdin/stdout contract, exit code convention, and `bash -c` wrapper pattern.
- [x] Read `leafcutter-ai/templates/settings.json` to document the hook registration schema.
- [x] Write `leafcutter-ai/docs/how-to/creating-a-claude-code-hook.md` covering:
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
- [x] Add a "Common Mistakes" table (wrong exit code for PostToolUse, blocking stdin parse errors, overly broad matchers).
- [x] Ensure the doc has valid frontmatter (type: how_to).

## Risk & Safety

- Touches money? No.
- Touches data? No — documentation only.
- Reversibility? Fully reversible.
