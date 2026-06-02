---
title: "Fix broken import in mermaid complexity hook template"
status: todo
components:
  - build_pipeline
created: 2026-06-02
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/scripts/commit_guardian/check_mermaid_complexity.py
  - leafcutter-ai/templates/commit-guardian/check_mermaid_complexity.py
  - leafcutter-ai/templates/commit-guardian/_resolve_root.py
  - leafcutter-ai/docs/pre-commit-hooks.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  frontend-coder: not_needed
  sql-query: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
---

# Fix broken import in mermaid complexity hook template

## Actor / Goal

In order to prevent ModuleNotFoundError when the mermaid complexity pre-commit
hook fires, we need to update the template source to use the canonical
`_resolve_root` import pattern so that fresh installs via `build.py` deploy a
working hook.

## Context

Fix commits dc4b462 and 408db20 updated the deployed
`scripts/commit_guardian/check_mermaid_complexity.py` to use
`from _resolve_root import find_project_root` for path resolution. However,
the template version at
`templates/commit-guardian/check_mermaid_complexity.py` still uses the old
hardcoded `parent.parent` approach:

```python
# Broken (template version — templates/commit-guardian/check_mermaid_complexity.py)
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
```

```python
# Working (deployed version — scripts/commit_guardian/check_mermaid_complexity.py)
from _resolve_root import find_project_root
project_root = find_project_root()
```

Because `build.py` copies from the template, any project that installs from
this template will deploy the broken version. The hook will fire correctly
only if `_resolve_root.py` is co-located in the same directory — the
hardcoded `parent.parent` path skips that entirely and resolves to the wrong
root when the project is installed in a non-standard layout.

A second issue: the deprecated template directory
`templates/commit-guardian/` was never fully migrated. The canonical location
is `templates/scripts/commit_guardian/`, which already contains `_resolve_root.py`
and nearly every other hook — but `check_mermaid_complexity.py` was never
copied there. The deprecated directory also lacks `_resolve_root.py`, meaning
even a targeted fix to the deprecated copy cannot succeed at runtime without
that helper.

Finally, `docs/pre-commit-hooks.md` documents the hook execution sequence
but omits the mermaid complexity hook entirely.

Related files:
- Working deployed version: `leafcutter-ai/scripts/commit_guardian/check_mermaid_complexity.py`
- Deprecated template: `leafcutter-ai/templates/commit-guardian/check_mermaid_complexity.py`
- Canonical template dir: `leafcutter-ai/templates/scripts/commit_guardian/` (missing the file)
- Hook documentation: `leafcutter-ai/docs/pre-commit-hooks.md`

## Acceptance Criteria

```gherkin
Given a fresh install via build.py
When check_mermaid_complexity.py is executed as a pre-commit hook
Then no ModuleNotFoundError is raised

Given the canonical template directory templates/scripts/commit_guardian/
When listing its contents
Then check_mermaid_complexity.py is present and imports _resolve_root

Given the canonical template check_mermaid_complexity.py
When diffed against scripts/commit_guardian/check_mermaid_complexity.py
Then the import section is identical (both use from _resolve_root import find_project_root)

Given the deprecated template at templates/commit-guardian/check_mermaid_complexity.py
When the deprecated directory is kept (not removed)
Then the file is updated to use _resolve_root AND _resolve_root.py is present in that directory

Given docs/pre-commit-hooks.md
When viewing the Hook Execution Sequence section
Then the mermaid complexity hook is listed with its description

Given python leafcutter-ai/scripts/commit_guardian/check_mermaid_complexity.py
When run directly
Then it exits without import errors

Given python leafcutter-ai/scripts/build.py --validate-only
When run after the changes
Then it completes successfully with no drift errors
```

## Sign-offs

- [ ] python-coder
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

**Deliverable 1 — Create canonical template copy**

- [ ] Copy `leafcutter-ai/scripts/commit_guardian/check_mermaid_complexity.py`
  verbatim to `leafcutter-ai/templates/scripts/commit_guardian/check_mermaid_complexity.py`.
  This is the working version that already uses `from _resolve_root import find_project_root`.
  Do not alter its content — the deployed and template versions must be identical so
  `build.py --validate` does not flag drift.

**Deliverable 2 — Fix or remove the deprecated template copy**

The `DEPRECATED.md` notice in `templates/commit-guardian/` signals the directory
is on its way out. Choose one of the following paths and document the decision in
a code comment:

- **Option A (preferred): Remove** `templates/commit-guardian/check_mermaid_complexity.py`.
  The canonical copy in `templates/scripts/commit_guardian/` is now the source of truth.
  Verify that `build.py` does not reference the deprecated path for this file; if it does,
  update the reference to point at the canonical location.

- **Option B (fallback): Update in place** if removing triggers unresolved `build.py`
  references. Replace the `current_dir / parent.parent` block with
  `from _resolve_root import find_project_root` and ensure
  `templates/commit-guardian/_resolve_root.py` exists (copy from
  `templates/scripts/commit_guardian/_resolve_root.py` if absent).

- [ ] Pick and execute Option A or Option B above.
- [ ] Confirm `build.py --validate-only` passes after the change.

### documentation-expert

**Deliverable — Update `docs/pre-commit-hooks.md`**

- [ ] Add `check-mermaid-complexity` to the Hook Execution Sequence mermaid
  flowchart in `docs/pre-commit-hooks.md`. Insert it alongside the other
  quality-gate hooks (`H1`–`H10`). Use a label consistent with the existing
  hook label style, e.g.:
  `H11[check-mermaid-complexity\nmermaid diagrams under complexity limits]`
- [ ] Add a corresponding `H11 -->|pass| COMMIT` and `H11 -->|fail| FIX` edge
  to match the pattern of the surrounding hooks.
- [ ] Verify the mermaid diagram still renders correctly (balanced flowchart syntax).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible. The canonical template create is additive;
  the deprecated template edit or removal can be reverted with `git revert`.
- Build pipeline: Both the template copy and the deployed `scripts/` copy must
  remain identical after this fix. Run `python leafcutter-ai/scripts/build.py
  --validate-only` to confirm no drift is introduced by the changes.
- Backward compatibility: Projects that already deployed the broken hook via
  `build.py` will need to re-run `build.py` after upgrading to this version to
  receive the fixed copy.
