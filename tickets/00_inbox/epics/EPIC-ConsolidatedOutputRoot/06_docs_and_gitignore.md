---
title: "Write how-to guide, explanation doc, and .gitignore guidance"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 05_migration_self_hosting.md
priority: medium
requires_diagram: false
requires_adr: false
requires_documentation:
  - how_to
  - explanation
  - reference
files_touched:
  - leafcutter-ai/docs/how-to/output-layout/adopt-consolidated-output-root.md
  - leafcutter-ai/docs/explanation/consolidated-output-root.md
  - leafcutter-ai/docs/reference/skills-config-fields.md
agents:
  architect-review: not_needed
  python-coder: not_needed
  test-writer: not_needed
  how-to-author: needed
  explanation-author: needed
  reference-author: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  documentation-expert: not_needed
  adr-author: not_needed
---

# 06: Write How-To Guide, Explanation Doc, and .gitignore Guidance

## Goal
In order to help developers understand and adopt the new `leafcutter-project/`
output layout, we need three documentation artifacts: a how-to guide for
migrating an existing install, an explanation of why files are consolidated and
what the shim layer does, and an updated reference for `skills_config.json`
fields including the new `output_root` and `shim_strategy` keys.

## Context
After tickets 01–05 implement the consolidated output root, consumers need:

1. **How-to guide** (`docs/how-to/output-layout/adopt-consolidated-output-root.md`):
   Step-by-step instructions for an existing leafcutter user to adopt the new
   layout. Covers: updating `skills_config.json`, running `build.py --migrate`
   to find stale files, removing them, and verifying the new layout works.

2. **Explanation doc** (`docs/explanation/consolidated-output-root.md`):
   "Why does leafcutter put all files in one folder?" Explains the motivation
   (consumer project isolation), the shim layer (how `.claude/` still works),
   and the trade-offs (Windows symlink caveat, gitignore posture).

3. **Reference update** (`docs/reference/skills-config-fields.md`):
   Add `output_root` and `shim_strategy` to the skills_config reference table
   with types, defaults, and valid values.

4. **`.gitignore` guidance**: The explanation doc should include a code block
   showing the recommended `.gitignore` entry for consumer projects that want
   to treat `leafcutter-project/` as a build artifact:
   ```
   # leafcutter build output — regenerate with: python leafcutter-ai/scripts/build.py
   leafcutter-project/
   ```

## Acceptance Criteria

```gherkin
Given the how-to guide is written
When a developer with an existing pre-consolidation leafcutter install reads it
Then they can follow the steps end-to-end without asking a question and end up
  with a working consolidated-output-root install

Given the explanation doc is written
When a developer asks "why are leafcutter files in leafcutter-project/ now?"
Then the explanation doc answers the question in under 5 minutes of reading

Given the reference doc is updated
When a developer reads the skills_config reference
Then they can find output_root and shim_strategy with their defaults and valid values

Given the .gitignore guidance is in the explanation doc
When a developer adds it to their .gitignore
Then git status no longer shows leafcutter-project/ as untracked
```

## Sign-offs

- [ ] how-to-author
- [ ] explanation-author
- [ ] reference-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### how-to-author
- [ ] Write `leafcutter-ai/docs/how-to/output-layout/adopt-consolidated-output-root.md`
  covering:
  1. Prerequisites (leafcutter installed, skills_config.json exists)
  2. Update skills_config.json (add output_root, shim_strategy)
  3. Run `python leafcutter-ai/scripts/build.py --migrate` and review report
  4. Delete stale files listed by the migration report
  5. Run `python leafcutter-ai/scripts/build.py` and verify leafcutter-project/
     exists with the expected structure
  6. Verify Claude Code still loads agents (test with `/help` or equivalent)

### explanation-author
- [ ] Write `leafcutter-ai/docs/explanation/consolidated-output-root.md`
  covering:
  - Why: consumer project isolation (the "mixed files" problem)
  - What: the leafcutter-project/ output root structure
  - How: the shim layer — what it does and why tools like Claude Code and
    pre-commit still work
  - Trade-offs: Windows symlink caveat, gitignore-vs-commit decision,
    two copies of files when using copy shims
  - Include recommended .gitignore entry

### reference-author
- [ ] Update `leafcutter-ai/docs/reference/skills-config-fields.md` (create
  if absent) to include a table row for each new field:
  | Field | Type | Default | Valid Values | Description |
  | `output_root` | string | `leafcutter-project` | any valid folder name | Output root for all build.py artifacts |
  | `shim_strategy` | enum | `auto` | `symlink`, `copy`, `auto` | Bridge strategy for canonical tool paths |

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? Docs-only; entirely reversible. No code impact.
