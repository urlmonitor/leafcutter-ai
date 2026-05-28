---
title: "Add default_artifact_checklist to python-coder"
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

# 02_02: Add default_artifact_checklist to python-coder

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/python-coder.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The python-coder agent (priority 6, role: coding) is the primary implementation agent. Its checklist should confirm code was written, tests pass, doc-enforcer is clean, and complexity checks pass.

Source of truth: `config/agent_registry.json` entry with `"id": "python-coder"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - code_implemented
  - tests_passing
  - doc_enforcer_clean
  - complexity_check_clean
```

## Acceptance Criteria
```gherkin
Given templates/agents/python-coder.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: code_implemented, tests_passing, doc_enforcer_clean, complexity_check_clean
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/python-coder.md` frontmatter: add `default_artifact_checklist: [code_implemented, tests_passing, doc_enforcer_clean, complexity_check_clean]`
- [ ] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments
