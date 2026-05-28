---
title: "Add default_artifact_checklist to test-writer"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 01_signoff_skill_manifest_section.md
priority: high
requires_diagram: false
requires_adr: false
agents:
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 02_03: Add default_artifact_checklist to test-writer

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/test-writer.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The test-writer agent (priority 5, role: quality) writes failing test stubs before coders implement. Its checklist should confirm stubs were created, all are red, and the red_baseline was captured.

Source of truth: `config/agent_registry.json` entry with `"id": "test-writer"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - test_stubs_created
  - all_tests_red
  - red_baseline_captured
```

## Acceptance Criteria
```gherkin
Given templates/agents/test-writer.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: test_stubs_created, all_tests_red, red_baseline_captured
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/test-writer.md` frontmatter: add `default_artifact_checklist: [test_stubs_created, all_tests_red, red_baseline_captured]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
