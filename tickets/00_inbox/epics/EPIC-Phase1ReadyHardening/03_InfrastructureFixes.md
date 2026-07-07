---
title: "Feedback config resolution anchoring + phase-agent allowed_writers coverage"
status: todo
components:
  - infrastructure
created: 2026-07-07
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/2
source_acs:
  - INF-100c-1
  - INF-100c-3
ac_path: docs/acceptance-criteria/infrastructure/
files_touched:
  - scripts/feedback/submit_feedback.py
  - templates/scripts/feedback/submit_feedback.py
  - config/feedback_categories.yaml
  - templates/config/feedback_categories.yaml
  - unit_tests/feedback/test_submit_feedback.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
complexity: standard

---

# Feedback config resolution anchoring + phase-agent allowed_writers coverage

## Actor / Goal

As the feedback subsystem, we need `submit_feedback.py` to resolve
`feedback_categories.yaml` relative to the script's own location (not the working
directory) and every standard phase agent to be listed in `allowed_writers` for
the categories it interacts with — so feedback submission works from the deployed
`.leafcutter/scripts/feedback/` location and no phase agent is silently rejected.

## Context

Both ACs approved under `docs/acceptance-criteria/infrastructure/`. Config
resolution must work on WSL2 and native Linux and follow the project
error-handling policy. `allowed_writers` changes are additive/backward-compatible.

## Acceptance Criteria

### INF-100c-1 — Config resolution uses the script's own location as anchor
```gherkin
Given submit_feedback.py running from <project>/.leafcutter/scripts/feedback/,
When the script resolves the path to feedback_categories.yaml,
Then it finds the file at <project>/.leafcutter/config/feedback_categories.yaml
  (resolved relative to the script file's own directory, not the working directory),
And feedback submission succeeds,
And existing callers invoking the script from the source repo location still work.
```

### INF-100c-3 — All phase agents recognized as valid writers for their categories
```gherkin
Given feedback_categories.yaml defines allowed_writers per category,
When the frontend-coder agent submits feedback to the success-pattern category,
Then the submission is accepted,
And all standard phase agents (python-coder, sql-coder, frontend-coder, llm-expert,
  test-writer, test-runner, pr-reviewer, commit) are listed in allowed_writers for
  the categories they interact with,
And no existing allowed_writers entry is removed.
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
