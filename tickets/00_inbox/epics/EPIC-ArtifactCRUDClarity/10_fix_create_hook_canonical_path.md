---
title: "Fix: create-hook canonical path"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/skills/create-hook/SKILL.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 10: Fix: create-hook canonical path

## Actor / Goal

In order to stop directing developers to a deprecated directory when creating pre-commit hooks, we need to update `create-hook/SKILL.md` to reference `templates/scripts/commit_guardian/` instead of `templates/commit-guardian/` so that newly created hooks land in the correct location.

## Context

The `create-hook` skill currently instructs users to place new hook scripts in `templates/commit-guardian/`, which is the deprecated path. The canonical path is `templates/scripts/commit_guardian/`. This was identified in the audit as problem #4. The fix is a simple find-and-replace in the skill body. No logic changes are needed.

Deprecated path: `leafcutter-ai/templates/commit-guardian/`
Canonical path: `leafcutter-ai/templates/scripts/commit_guardian/`

## Acceptance Criteria

```gherkin
Given the updated create-hook SKILL.md exists
When it is read
Then every reference to templates/commit-guardian/ has been replaced with templates/scripts/commit_guardian/

Given no other references to the deprecated path remain in create-hook/SKILL.md
When grep is run for "templates/commit-guardian"
Then zero matches are found in that file

Given the canonical path is documented
When create-hook SKILL.md is followed
Then the developer creates hook scripts in the correct location
```

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] Read `leafcutter-ai/templates/skills/create-hook/SKILL.md` and identify all occurrences of `templates/commit-guardian/`.
- [ ] Replace every occurrence of `templates/commit-guardian/` with `templates/scripts/commit_guardian/` using Edit (replace_all).
- [ ] Verify with `grep -n "commit-guardian" leafcutter-ai/templates/skills/create-hook/SKILL.md` returns zero matches on the replaced path (the deprecated directory name itself can appear only in a "deprecated path" callout if one is added).
- [ ] Optionally add a one-line callout note: "Note: `templates/commit-guardian/` is a deprecated path. Always use `templates/scripts/commit_guardian/`." — but only if the skill body has a natural place for it; do not add noise.

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies a Markdown skill procedure only.
- Reversibility? Fully reversible. Change is a string replacement in one file.
- Side effects? No — `create-hook/SKILL.md` is a procedural document; changing the path string does not affect any running system. Developers invoking the skill after this fix will use the correct path.
