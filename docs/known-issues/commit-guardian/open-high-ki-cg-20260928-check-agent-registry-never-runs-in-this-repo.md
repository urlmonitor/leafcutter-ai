---
title: "KI-CG-20260928-check-agent-registry-never-runs-in-this-repo — the commit-time agent-registry check looks for a leafcutter/ folder this repository does not have, and passes having checked nothing"
description: "high — check_agent_registry.py resolves the package as <repo root>/leafcutter and returns 0 when that path is missing. In this repository the package sits at the repo root, so every 'Check Agent Registry … Passed' has validated nothing. build.py --validate-only still validates the registry, so it is checked at build time but never at commit time."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - commit_guardian
  - agent_registry
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/acceptance-criteria/guardrail-engine/GE-113-artifacts-cant-land-in-the-wrong-place/GE-113c-1-vi.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400a-1-iii.yaml
---

# KI-CG-20260928-check-agent-registry-never-runs-in-this-repo — the commit-time registry check has never run here

- **Severity:** high. A required check reports success without looking. A registry error
  staged in this repository (an agent entry with no template, a bad field, or an unknown
  step kind once BO-2400a-1-iii lands) reaches `main` without being refused at commit time.
- **Status:** open. AC **GE-113c-1-vi** specifies the fix, which is to be built straight after
  BO-2400a-1-iii.
- **Where:** `templates/scripts/commit_guardian/check_agent_registry.py` (live copy
  `scripts/commit_guardian/check_agent_registry.py`), `main()`.

## Symptom

`main()` finds the repository root with `git rev-parse --show-toplevel`, then sets
`package_root = repo_root / "leafcutter"`. If that path does not exist, it returns 0 with no
message:

```python
package_root = repo_root / "leafcutter"

if not package_root.exists():
    # Package not present in this repo — nothing to validate
    return 0
```

In this repository the package is the repository itself (`config/agent_registry.json`,
`scripts/registry_validator.py` at the root), and there is no `leafcutter/` folder. So on
every commit that stages a registry file, the hook passes before it validates anything.

## Detection

- Pre-commit prints `Check Agent Registry ... Passed` on commits that stage
  `config/agent_registry.json`, even when the staged registry is invalid.
- Found on 2026-09-27 by the test-writer for BO-2400a-1-iii. To exercise the hook at all, its
  tests had to build a fixture with a bare `leafcutter/` folder.
- `build.py --validate-only` calls the same `validate_agent_registry()` and does report
  errors, so the registry is checked at build time. It is not checked at commit time.

## Workaround

Run `PYTHONUTF8=1 python scripts/build.py --validate-only` before committing any change to
the registry, its schema or an agent template.

## Suggested fix

See GE-113c-1-vi.
- Find the package root the same way the build and the other commit-time checks do, in every
  layout the package ships: the repo root here, and `leafcutter/` in a consumer project.
- When a registry file is staged and no package root can be found, block the commit and name
  the locations tried. Never exit 0 having checked nothing.
- Registry errors that surface once the check really runs are fixed or recorded here. The
  check must not be switched off again to let them through.
