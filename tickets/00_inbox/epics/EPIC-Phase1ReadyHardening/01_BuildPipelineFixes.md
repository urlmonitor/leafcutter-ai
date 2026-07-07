---
title: "Build-pipeline reachability + hook false-positive fixes (workflows shim, check_secrets prose, goal_to_epic root)"
status: todo
components:
  - build_pipeline
created: 2026-07-07
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/3
source_acs:
  - BP-811
  - BP-812
  - BP-901
ac_path: docs/acceptance-criteria/build_pipeline/
files_touched:
  - scripts/build_phases.py
  - scripts/commit_guardian/check_secrets.py
  - templates/scripts/commit_guardian/check_secrets.py
  - scripts/goal_to_epic.py
  - unit_tests/commit_guardian/test_check_secrets.py
  - unit_tests/test_goal_to_epic.py
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

# Build-pipeline reachability + hook false-positive fixes

## Actor / Goal

As the leafcutter package, we need the `.claude/workflows` shim to actually point
at the deployed workflow `.js` files, `check_secrets.py` to treat
`templates/skills/` prose as prose, and `goal_to_epic.py` to skip worktree-root
resolution when explicit paths are supplied — so consumer installs get reachable
workflows, no false-positive secret findings, and no spurious FileNotFoundError.

## Context

All three ACs are approved under `docs/acceptance-criteria/build_pipeline/`. Each
is a targeted symptom fix. Follow the project error-handling policy.

## Acceptance Criteria

### BP-811 — Workflow .js scripts reachable via the .claude/workflows shim
```gherkin
Given a consumer build runs with workflows enabled and a supported Claude Code version,
When build_workflow_scripts() deploys the workflow .js files and install_shims() runs,
Then the .claude/workflows shim resolves to the directory that actually contains the
  deployed workflow .js files (plan-feature.js reachable via target_root/.claude/workflows/),
And the build does NOT log "shim source missing: workflows/ — Skipping .claude/workflows shim",
And workflow .js files are never orphaned in .leafcutter/.claude/workflows/ with no shim.
```

### BP-812 — check_secrets.py treats templates/skills/ prose as prose
```gherkin
Given the deployed check_secrets.py and a staged file under templates/skills/ that
  contains a documentation placeholder such as a TICKET-YYYYMMDD-style token in prose,
When the check-secrets pre-commit hook scans that file,
Then templates/skills/ is treated as a prose-only prefix (in _PROSE_FILE_PREFIXES)
  and the placeholder is NOT flagged as a secret/high-entropy finding,
And no .security-allowlist workaround is required.
```

### BP-901 — goal_to_epic.py resolves worktree root only when a default path is needed
```gherkin
Given the deployed goal_to_epic.py running from .leafcutter/scripts/ (outside any git
  worktree) and the caller supplies BOTH --store-root and --inbox-dir explicitly,
When main() is invoked,
Then _find_worktree_root() is NOT called (neither default path is needed) and the
  script proceeds to run() using the supplied paths,
And it does NOT crash with FileNotFoundError "Could not locate worktree root".
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
