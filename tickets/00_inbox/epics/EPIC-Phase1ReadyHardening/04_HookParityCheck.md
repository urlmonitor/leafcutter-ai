---
title: "check_hook_parity.py — enforce commit-guardian hook parity across all template directories"
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
ac_coverage: 0/9
source_acs:
  - BP-100i-1
  - BP-100i-2
  - BP-100i-3
  - BP-100i-4
  - BP-100i-5
  - BP-100i-1-i
  - BP-100i-1-ii
  - BP-100i-2-i
  - BP-100i-3-i
ac_path: docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
files_touched:
  - scripts/commit_guardian/check_hook_parity.py
  - templates/scripts/commit_guardian/check_hook_parity.py
  - templates/commit-guardian/check_hook_parity.py
  - scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/commit-guardian/commit_guardian.json
  - unit_tests/commit_guardian/test_check_hook_parity.py
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

# check_hook_parity.py — commit-guardian hook parity across template directories

## Actor / Goal

As the leafcutter package, we need a pre-commit hook that blocks a commit whenever
a commit-guardian hook script or manifest entry exists in one location but is
missing from another (runtime dir, canonical template, legacy template, deployed
output) — so a hook can never silently fail to ship to consumer projects (the
exact ACS-400 incident that motivated this epic).

## Context

New hook `check_hook_parity.py`, deployed to all three tracked source dirs and
registered in every `commit_guardian.json`. Follow the established
`check_build_drift.py` pattern: read directory/manifest paths from
`commit_guardian.json` config (a new `hook_parity` section), never hardcode; exit
0 (fail-open) on unexpected errors and exit 1 only on detected parity violations;
complete within 2s; be idempotent. All 9 leaf ACs approved under
`docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/`.

## Acceptance Criteria

### BP-100i-1 — Script parity: runtime dir vs canonical template dir
```gherkin
Given the runtime dir has a hook script (check_delta.py) absent from the canonical template dir,
When the parity check runs at pre-commit,
Then the commit is blocked (exit 1), the error names check_delta.py as missing from
  the canonical template dir, and states the expected location.
```

### BP-100i-2 — Manifest parity: legacy vs canonical commit_guardian.json
```gherkin
Given the legacy manifest registers hooks (check-epsilon, check-zeta) absent from the canonical manifest,
When the parity check runs,
Then the commit is blocked (exit 1) and each violation names the hook ID and the
  manifest file where it is missing.
```

### BP-100i-3 — Deployed output parity: canonical template vs build output
```gherkin
Given the canonical template has scripts absent from the deployed output directory,
When the parity check runs,
Then the commit is blocked (exit 1), the error lists the missing scripts and names
  the deployed output directory checked.
```

### BP-100i-4 — Hook fires at pre-commit when commit_guardian files are staged
```gherkin
Given commit_guardian.json registers check-hook-parity (files pattern matching
  scripts/commit_guardian/, templates/scripts/commit_guardian/, templates/commit-guardian/;
  stages: [pre-commit]),
And a developer stages scripts/commit_guardian/check_new_hook.py without its template counterpart,
When the pre-commit framework runs,
Then the parity check detects the missing counterpart, blocks the commit before the
  commit object is created, and shows an actionable "add which file and where" message.
```

### BP-100i-5 — No violations when all directories are in sync (silent pass)
```gherkin
Given runtime, canonical, legacy, and deployed dirs all hold the same scripts and
  the manifests register the same hooks,
When the parity check runs,
Then no violations are reported, the hook exits 0, and nothing is emitted to stdout/stderr.
```

### BP-100i-1-i — Exclusion allowlist suppresses expected asymmetries
```gherkin
Given commit_guardian.json has hook_parity.excluded_scripts: ["check_legacy_only.py"]
  and check_legacy_only.py is in runtime but not canonical,
When the parity check runs,
Then no violation is reported for check_legacy_only.py (exit 0), but other genuinely
  missing, non-excluded scripts still trigger a blocking violation.
```

### BP-100i-1-ii — Non-hook utility files excluded from script parity
```gherkin
Given runtime holds check_alpha.py, __init__.py, README.md, __pycache__/*.pyc and
  canonical holds only check_alpha.py,
When the parity check runs,
Then no violation is reported for __init__.py, README.md, or __pycache__ contents
  (exit 0); only hook-script-pattern files (check_*.py, run_hook.py, regenerate_*.py)
  are compared, and __pycache__/ is not traversed.
```

### BP-100i-2-i — Disabled hooks still require canonical presence
```gherkin
Given the legacy manifest registers check-future-feature with enabled: false and the
  canonical manifest lacks it,
When the parity check runs,
Then the commit is blocked (exit 1); the error names check-future-feature (enabled: false)
  as present-in-legacy/absent-in-canonical and explains disabled hooks still require
  parity because build.py reads the canonical manifest regardless of enabled state.
```

### BP-100i-3-i — Graceful degradation when deployed output dir is absent
```gherkin
Given the canonical template exists but the deployed output dir does not (fresh clone,
  build.py not yet run),
When the parity check runs,
Then it skips the deployed-output comparison, still performs runtime-vs-canonical and
  manifest parity checks, exits 0 if no other violations, and emits a single-line
  informational message that the deployed output dir was not found (to stderr).
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
