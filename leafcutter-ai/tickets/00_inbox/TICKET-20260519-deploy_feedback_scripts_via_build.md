---
title: "Deploy feedback scripts to consumer projects via build.py"
status: todo
components:
  - build_system
  - feedback
created: 2026-05-19
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
requires_documentation:
  - README update in scripts/feedback/
files_touched:
  - leafcutter-ai/scripts/build.py
  - leafcutter-ai/scripts/feedback/submit_feedback.py
  - leafcutter-ai/scripts/feedback/emit_hook_finding.py
  - leafcutter-ai/scripts/feedback/list_tags.py
  - leafcutter-ai/config/feedback_categories.yaml
agents:
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  test-writer: needed
  architect-review: not_needed
  adr-author: not_needed
  sql-coder: not_needed
  documentation-expert: not_needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# Deploy feedback scripts to consumer projects via build.py

## Actor / Goal

As a **consumer project using leafcutter**, I need the feedback scripts (`submit_feedback.py`, `emit_hook_finding.py`, `list_tags.py`) and `feedback_categories.yaml` to be deployed into my project so that agents can actually emit structured feedback to `feedback.jsonl` during signoff.

## Problem

The signoff skill (§2a) instructs every phase agent to call:

```bash
python leafcutter/scripts/feedback/submit_feedback.py \
  --ticket <ticket_path> \
  --phase <agent_name> \
  --category <category> \
  --tags <tags> \
  --note "<note>"
```

But `build.py` never copies `scripts/feedback/` into the consumer project. The result:

1. Agents read the signoff skill, see the instruction, can't find the script.
2. They either silently fail (using `(submit-failed)` fallback) or skip entirely.
3. `feedback.jsonl` is never created — the entire feedback loop is a dead letter.
4. Downstream tools (`aggregate.py`, `list_tags.py`) have nothing to query.

## Acceptance Criteria

- [ ] `build.py` has a `build_feedback` phase that deploys feedback scripts to the consumer project.
- [ ] The deployed path matches what the signoff skill references (or the signoff skill is updated to match).
- [ ] `debugging/logs/` directory is created (or `submit_feedback.py` creates it on first write).
- [ ] Path resolution in `submit_feedback.py` works correctly from the consumer project's perspective.
- [ ] `feedback_categories.yaml` is deployed alongside the scripts so validation works.
- [ ] An integration test verifies that calling `submit_feedback.py` from a deployed consumer layout produces a valid JSONL entry.

## Implementation Notes

- `submit_feedback.py` currently resolves `feedback.jsonl` via `Path(__file__).resolve().parents[3] / "debugging" / "logs" / "feedback.jsonl"` — this relative-parent calculation will need to match the deployed location.
- Consider whether `aggregate.py` and `link_feedback.py` should also be deployed (they're query tools, not write-path — lower priority).
- The signoff skill is already deployed by `build_skills` — only the scripts it references are missing.

## Sign-offs

- [ ] python-coder
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
