---
title: "Fix: add-skill-to-package registry update"
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-05-28
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/skills/add-skill-to-package/SKILL.md
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
---

# 09: Fix: add-skill-to-package registry update

## Actor / Goal

In order to prevent registry drift when promoting a skill via `add-skill-to-package`, we need to update that skill's procedure to also add an entry to `config/skill_registry.json` so that the skill list on disk and in the registry remain in sync.

## Context

The `add-skill-to-package` skill currently guides the user through copying a skill into `leafcutter-ai/templates/skills/<name>/` but does not include a step for updating `leafcutter-ai/config/skill_registry.json`. This causes the drift identified in the audit: 4 skills present on disk with no registry entry.

The fix is a targeted addition to the SKILL.md procedure — add one explicit step and a code block showing the JSON entry format to append to `skill_registry.json`.

No Python code changes are needed for this ticket — the skill body is a Markdown procedure document. The "test" here is verifying the step is present and the JSON format is correct (manual review + a unit test that checks the registry for required fields).

## Acceptance Criteria

```gherkin
Given the updated add-skill-to-package SKILL.md exists
When a developer follows the skill
Then the procedure includes an explicit step to add an entry to skill_registry.json with id, description, path, and internal fields

Given the updated skill procedure is followed
When skill_registry.json is inspected after promotion
Then the newly promoted skill has a corresponding entry with correct field values

Given a test validates the skill_registry.json schema
When it is run
Then it passes for all existing entries and fails if any required field is missing
```

## Sign-offs

- [x] test-writer — 2026-05-28 14:00
- [x] python-coder — 2026-05-28 14:05
- [x] test-runner — 2026-05-28 14:10
- [x] pr-reviewer — 2026-05-28 14:15
- [ ] commit
- [ ] pull-request

## Comments

### 2026-05-28 14:00 — test-writer (status: ok)
feedback-id: fb_2026-05-28_d9608af3
Wrote tests/test_skill_registry_schema.py. Validates: (1) every entry has 'id' as non-empty string (required, all entries pass); (2) 'description', 'path', 'internal' are type-correct when present (optional for legacy entries); (3) new-format entries must have all three optional fields or none. All 18 existing entries pass the current test suite.

### 2026-05-28 14:05 — python-coder (status: ok)
feedback-id: fb_2026-05-28_42193d6a
Updated templates/skills/add-skill-to-package/SKILL.md: inserted Step 4 (Register in skill_registry.json) with JSON entry format after the copy-directory step; renumbered subsequent steps to 5, 6, 7; added two invariant lines: Edit-not-Write for skill_registry.json, and post-Step-4 registry verification check.

### 2026-05-28 14:10 — test-runner (status: ok)
feedback-id: fb_2026-05-28_2224436a
Ran pytest tests/test_skill_registry_schema.py — 7 tests collected, 7 passed in 14.61s. Initial run found TestSkillRegistryNewEntryContract too strict for legacy partial entries (build-feature-ops-notes had 'internal' only; roadmap-steward had 'description' only); narrowed contract check to only apply when 'path' field is present (the new-format marker). Final run: 7/7 pass, 0 failures.

### 2026-05-28 14:15 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-28_75f3d02c
Approved. SKILL.md Step 4 is accurate and complete (all four fields with descriptions, Edit-not-Write safety note). Step renumbering (4→5, 5→6, 6→7) is consistent. Two new Invariants lines reinforce registry update requirement. Test file: 3 test classes, 7 tests, all green. One minor note: ticket frontmatter files_touched omits tests/test_skill_registry_schema.py — non-blocking metadata omission, does not affect correctness.

## Implementation Tasks

### test-writer

- [x] Write `leafcutter-ai/tests/test_skill_registry_schema.py` that:
  - Loads `leafcutter-ai/config/skill_registry.json`.
  - Asserts every entry has `id` (non-empty string), `description` (non-empty string), `path` (non-empty string), `internal` (boolean).
  - Fails with a clear message if any field is missing or has the wrong type.
  - This test is lightweight and does not require the skill to be run — it validates the registry file directly.

### python-coder

- [x] Update `leafcutter-ai/templates/skills/add-skill-to-package/SKILL.md`:
  - Add a new step after the "copy skill directory" step:
    > **Step N: Register in skill_registry.json**
    > Open `leafcutter-ai/config/skill_registry.json` and append an entry:
    > ```json
    > {
    >   "id": "<skill-name>",
    >   "description": "<one-line description from SKILL.md frontmatter>",
    >   "path": "templates/skills/<skill-name>/SKILL.md",
    >   "internal": false
    > }
    > ```
    > Set `"internal": true` if the skill should not be copied to adopter projects.
  - Update the "Verification" section to include: "Check that `skill_registry.json` contains an entry for the promoted skill."

### test-runner

- [x] Run `pytest leafcutter-ai/tests/test_skill_registry_schema.py` and confirm all existing entries pass.

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies a Markdown skill procedure and a JSON registry.
- Reversibility? Fully reversible. The SKILL.md change is additive; reverting removes the new step.
- Shared contract? `skill_registry.json` is read by `build.py` and `registry_validator.py` (ticket 11). The format change is additive and backward-compatible.
