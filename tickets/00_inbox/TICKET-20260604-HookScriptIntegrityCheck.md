---
title: "Add build-time hook referential integrity check"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build_precommit.py
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
ac_traceability:
  l1: BP-100a
  l2:
    - BP-100a-1
    - BP-100a-2
    - BP-100a-4
    - BP-100a-5
  l3: []
  ac_path: docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
---

# Add build-time hook referential integrity check

## Actor / Goal

In order to prevent the class of silent failure where hooks are registered in
`commit_guardian.json` but their `.py` scripts are absent at the canonical
template path, we need a build-time integrity check that emits a WARNING listing
any gaps, so the problem is surfaced before runtime.

## Context

### Background: how the gap occurred

EPIC-PortableInstallHardening (2026-05-18) migrated `build_commit_guardian()` in
`scripts/build_phases.py` to read from the canonical path
`templates/scripts/commit_guardian/` with a legacy fallback to
`templates/commit-guardian/`. Several hook scripts written before and after the
migration were placed at the legacy path only. Because no build-time check
validated the presence of each registered script at the canonical path, 7 scripts
were registered in `commit_guardian.json` but never deployed from the canonical
location.

This was discovered during TICKET-20260604-FixAcStoreDocsBuildPaths when
pre-commit hooks failed with "No such file or directory". A band-aid was applied
(copying the 7 scripts from legacy to canonical), but the structural guard is
needed to prevent recurrence.

The same `build_precommit.py::build_precommit_config()` function that reads
`hooks_manifest.hooks` is the natural insertion point — it already has access to
`cg_dir` (the canonical template path) and iterates every hook entry.

A parallel module, `scripts/build_referential_integrity.py`, demonstrates the
established pattern for build-time integrity warnings: iterate a set of
path-valued fields, verify existence, emit a WARNING (non-blocking). The hook
script integrity check follows the same pattern.

### Pattern reference: `build_referential_integrity.py`

```python
def check_referential_integrity(target_root, config) -> list[dict[str, str]]:
    missing = []
    for key in _PATH_KEYS:
        value = config.get(key)
        if not value:
            continue
        if not (target_root / value).exists():
            missing.append({"config_key": key, "expected_path": value})
    return missing
```

The hook integrity check follows the same non-blocking warning convention.

### Hook entry format in `commit_guardian.json`

Each entry in `hooks_manifest.hooks` has an `entry` field of the form:

```
python {{config.output_root}}/scripts/commit_guardian/run_hook.py {{config.output_root}}/scripts/commit_guardian/check_XXXX.py
```

The script filename is always the last whitespace-delimited token of the `entry`
field after template-variable stripping. For example:

```
entry: "python {{config.output_root}}/scripts/commit_guardian/run_hook.py {{config.output_root}}/scripts/commit_guardian/check_contract_shrinking.py"
→ script filename: "check_contract_shrinking.py"
```

### Files not to modify

- `scripts/build_phases.py` line 781 legacy fallback — do NOT remove the
  `cg_dir = _canonical if _canonical.exists() else TEMPLATES_DIR / "commit-guardian"`
  fallback. The optional legacy-path deprecation is out of scope for this ticket
  (see "Out of Scope" below).
- `check_build_drift.py` explicitly excludes commit_guardian scope by design
  (comments in that file confirm this). Do not change it.

## Acceptance Criteria

- [ ] AC-1: After `build_precommit_config()` reads `hooks_manifest.hooks`, it iterates every hook entry, extracts the script filename from the `entry` field, and checks for `<cg_dir>/<filename>`. For any script not found at `cg_dir`, a `_log.warning(...)` is emitted listing the hook id and the expected path. The build does NOT fail — it continues and returns its normal count.
- [ ] AC-2: When all hook scripts exist at `cg_dir`, no warning is emitted and the function behaves identically to before the change.
- [ ] AC-4: Unit test `test_hook_script_integrity_check_warns_on_missing` — given a mock `hooks_manifest` referencing `check_missing.py` and a `cg_dir` that does not contain it, calling `build_precommit_config()` (or an extracted helper) emits a warning and does not raise.
- [ ] AC-5: Unit test `test_hook_script_integrity_check_silent_when_all_present` — given a `cg_dir` that contains all referenced scripts, no warning is emitted.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | AC-4 | build_precommit.py — post-hooks-load integrity loop | |
| AC-2 | AC-5 | same loop — no-op when all present | |
| AC-4 | unit_tests/commit_guardian/test_build_precommit.py | build_precommit.py | |
| AC-5 | unit_tests/commit_guardian/test_build_precommit.py | build_precommit.py | |

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## AC Traceability

| AC ID | Level | Title | Agent |
|-------|-------|-------|-------|
| BP-100a-1 | L2 | Build emits a warning for each registered hook whose script file is absent | python-coder |
| BP-100a-2 | L2 | Build emits no integrity warnings when all hook scripts are present | python-coder |
| BP-100a-4 | L2 | Test verifies warning is emitted when a hook script is missing | test-writer |
| BP-100a-5 | L2 | Test verifies no warning is emitted when all hook scripts exist | test-writer |

AC files: `docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100a-*.yaml`

## Comments

## Implementation Tasks

### python-coder

**Deliverable 1 — Hook script integrity check in `scripts/build_precommit.py`**

After line 295 (`hooks = raw.get("hooks_manifest", {}).get("hooks", [])`), insert:

```python
# Integrity check: warn when a registered hook script is absent at cg_dir
for hook in hooks:
    entry = hook.get("entry", "")
    tokens = entry.split()
    if tokens:
        script_name = Path(tokens[-1]).name
        if script_name.endswith(".py") and not (cg_dir / script_name).exists():
            _log.warning(
                "Hook '%s': script '%s' not found at canonical path %s",
                hook.get("id", "?"),
                script_name,
                cg_dir / script_name,
            )
```

This must run BEFORE `_resolve_template_vars` strips the `{{config.output_root}}`
tokens — the last token of the raw `entry` string is always the `.py` filename
regardless of template vars.

Note: `Path(tokens[-1]).name` safely extracts the filename even if the token is
`{{config.output_root}}/scripts/commit_guardian/check_foo.py`.

### test-writer

Add tests to:

1. `unit_tests/commit_guardian/test_build_precommit.py` (or create it if absent):

   - `test_hook_script_integrity_check_warns_on_missing`: Mock `cg_dir` as a
     `tmp_path` that contains only `run_hook.py`. Mock `hooks` list with one
     entry whose `entry` references `check_missing.py`. Assert `_log.warning`
     is called with the missing script's name.

   - `test_hook_script_integrity_check_silent_when_all_present`: Same setup but
     create `check_missing.py` in `tmp_path`. Assert `_log.warning` is NOT called
     for the integrity check (other warnings unrelated to integrity are allowed).

## Out of Scope

- Removing the legacy fallback in `build_phases.py` line 781 or
  `build_precommit.py` lines 284–286 (`cg_dir = TEMPLATES_DIR / "commit-guardian"`).
  The legacy directory has `DEPRECATED.md` but the fallback aids projects that
  have not yet migrated. A separate deprecation ticket should handle removal once
  all known consumers confirm they use the canonical path.
- `check_build_drift.py` scope exclusion for commit_guardian — this exclusion is
  intentional and documented in that file; do not change it.
- Adding a schema-validation check that `entry` fields in `commit_guardian.json`
  follow the expected `run_hook.py <script.py>` two-argument pattern — this is a
  separate linting concern.
- The false-positive fix for `check_contract_shrinking.py` — this is now tracked
  separately in TICKET-20260605-ContractShrinkingSelfExclusion (L1: BP-100d).

## Risk & Safety

- Touches money? No.
- Touches data? No — build phase emits warnings only; no user data affected.
- Reversibility? The integrity check is a non-blocking warning. Removing it
  requires only deleting the added loop.
- Risk of regressions: low. The integrity check loop runs after hooks are loaded
  and before `_resolve_template_vars` — it cannot affect the generated
  `.pre-commit-config.yaml`.
- 295 tests pass before this change. The copied hook scripts are template files
  not imported by tests; no test coverage gap is introduced.
