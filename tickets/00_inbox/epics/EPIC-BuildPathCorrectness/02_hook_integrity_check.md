---
title: "Add build-time hook referential integrity check and fix check_contract_shrinking false-positive"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_fix_docs_root_git_root.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build_precommit.py
  - templates/scripts/commit_guardian/check_contract_shrinking.py
  - templates/commit-guardian/check_contract_shrinking.py
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
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Add build-time hook referential integrity check and fix check_contract_shrinking false-positive

## Actor / Goal

In order to prevent the class of silent failure where hooks are registered in
`commit_guardian.json` but their `.py` scripts are absent at the canonical
template path, we need a build-time integrity check that emits a WARNING listing
any gaps, so the problem is surfaced before runtime. Additionally, we need to fix
a false-positive in `check_contract_shrinking.py` that flags its own source code
patterns when it is staged alongside production files.

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

### Problem 2: `check_contract_shrinking.py` false-positive

`_PRODUCTION_FILE_RE` matches any `.py` diff header that is not in a test path.
The `_TEST_PATH_RE` exclusion list covers `unit_tests/`, `tests/`, `test_*.py`,
`conftest.py` — but not `commit_guardian/` or `scripts/commit_guardian/`. When
the hook script itself is staged (e.g. when adding the self-exclusion fix),
`check_contract_shrinking.py` at `templates/scripts/commit_guardian/` is
classified as a production file. If any `_WEAKENING_PATTERNS` appear in the diff
(including the hook's own source containing those pattern strings), the hook
blocks itself.

Fix: extend `_TEST_PATH_RE` to also exclude paths matching
`commit_guardian/` — hook infrastructure is not production application code.

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
- [ ] AC-3: `check_contract_shrinking.py`'s `_TEST_PATH_RE` is extended to exclude paths containing `commit_guardian/` (covering both `scripts/commit_guardian/check_*.py` and `templates/scripts/commit_guardian/check_*.py`). The same change is applied to both the canonical template (`templates/scripts/commit_guardian/check_contract_shrinking.py`) and the legacy copy (`templates/commit-guardian/check_contract_shrinking.py`).
- [ ] AC-4: Unit test `test_hook_script_integrity_check_warns_on_missing` — given a mock `hooks_manifest` referencing `check_missing.py` and a `cg_dir` that does not contain it, calling `build_precommit_config()` (or an extracted helper) emits a warning and does not raise.
- [ ] AC-5: Unit test `test_hook_script_integrity_check_silent_when_all_present` — given a `cg_dir` that contains all referenced scripts, no warning is emitted.
- [ ] AC-6: Unit test `test_contract_shrinking_excludes_commit_guardian_paths` — a diff that modifies `templates/scripts/commit_guardian/check_contract_shrinking.py` alongside a `pytest.mark.xfail` removal is NOT classified as contract-shrinking (because the commit_guardian path is excluded from production file classification).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | AC-4 | build_precommit.py — post-hooks-load integrity loop | |
| AC-2 | AC-5 | same loop — no-op when all present | |
| AC-3 | AC-6 | check_contract_shrinking.py _TEST_PATH_RE update | |
| AC-4 | unit_tests/commit_guardian/test_build_precommit.py | build_precommit.py | |
| AC-5 | unit_tests/commit_guardian/test_build_precommit.py | build_precommit.py | |
| AC-6 | unit_tests/commit_guardian/test_check_contract_shrinking.py | check_contract_shrinking.py | |

## Sign-offs

- [x] test-writer — 2026-06-04 12:00
- [x] python-coder — 2026-06-04 12:05
- [x] test-runner — 2026-06-04 12:10
- [x] pr-reviewer — 2026-06-04 12:15
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-04 12:00 — test-writer (status: ok)
feedback-id: fb_2026-06-04_f43c68ff
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
  ac_ids_covered: [UNKNOWN]
red_baseline:
  - test_name: test_hook_script_integrity_check_warns_on_missing
    file: unit_tests/commit_guardian/test_build_precommit.py
    error: "AssertionError: AttributeError: scripts.build_precommit does not expose _check_hook_script_integrity(). Extract the integrity-check loop as this helper function (AC-1, AC-4)."
  - test_name: test_hook_script_integrity_check_silent_when_all_present
    file: unit_tests/commit_guardian/test_build_precommit.py
    error: "AssertionError: AttributeError: scripts.build_precommit does not expose _check_hook_script_integrity(). Extract the integrity-check loop as this helper function (AC-1, AC-5)."
  - test_name: test_contract_shrinking_excludes_commit_guardian_paths
    file: unit_tests/commit_guardian/test_check_contract_shrinking.py
    error: "AssertionError: True is not false : has_production_changes should be False for commit_guardian/ paths, but got True. Production files detected: ['templates/scripts/commit_guardian/check_contract_shrinking.py']"
  - test_name: test_contract_shrinking_excludes_legacy_commit_guardian_path
    file: unit_tests/commit_guardian/test_check_contract_shrinking.py
    error: "AssertionError: True is not false : has_production_changes should be False for templates/commit-guardian/ paths. Got production files: ['templates/commit-guardian/check_contract_shrinking.py']"
Wrote 5 test stubs: 2 in test_build_precommit.py (AC-4, AC-5) and 3 in test_check_contract_shrinking.py (AC-6). 4/5 are red; 1 sanity-check (test_non_commit_guardian_py_still_detected_as_production) passes as expected since it verifies unchanged production detection behavior. Red baseline captured above. Verification: `python -m pytest unit_tests/commit_guardian/test_build_precommit.py unit_tests/commit_guardian/test_check_contract_shrinking.py -v` exits non-zero (exit 1).

### 2026-06-04 12:05 — python-coder (status: ok)
feedback-id: fb_2026-06-04_c6c73b93
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
Deliverable 1: Added `_check_hook_script_integrity(hooks, cg_dir)` helper to `scripts/build_precommit.py` (AC-1, AC-2) and called it between hooks load and `_resolve_template_vars`. Deliverable 2: Extended `_TEST_PATH_RE` in both `templates/commit-guardian/check_contract_shrinking.py` and new `templates/scripts/commit_guardian/check_contract_shrinking.py` to use `commit[_-]guardian/` exclusion (AC-3). All 5 new tests pass: `python -m pytest unit_tests/commit_guardian/test_build_precommit.py unit_tests/commit_guardian/test_check_contract_shrinking.py` exits 0.

### 2026-06-04 12:10 — test-runner (status: ok)
feedback-id: fb_2026-06-04_87b75034
completion_manifest:
  tests_green: true
  no_regressions: true
Full commit_guardian test suite: 114/114 passed. Full unit_tests suite (excluding 2 pre-existing broken imports): 233/234 passed. The 1 remaining failure (test_build_workflow_scripts_writes_to_output_root_workflows) is pre-existing and confirmed present on the base branch before our changes. No regressions introduced by this ticket.

### 2026-06-04 12:15 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_1245946f
completion_manifest:
  acs_covered: true
  no_out_of_scope_changes: true
  code_quality_acceptable: true
All 6 ACs satisfied. _check_hook_script_integrity() is correctly non-blocking, pre-template-var, well-documented. commit[_-]guardian/ regex covers both hyphen and underscore path variants and is applied to both template files. Tests are properly isolated using extracted helper. DECISION HISTORY entries present. No out-of-scope files touched.

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

**Deliverable 2 — False-positive fix in `check_contract_shrinking.py`**

In both:
- `templates/scripts/commit_guardian/check_contract_shrinking.py`
- `templates/commit-guardian/check_contract_shrinking.py`

Update `_TEST_PATH_RE`:

```python
# Before:
_TEST_PATH_RE = re.compile(
    r"(unit_tests/|tests/|test_[^/]+\.py$|[^/]+_test\.py$|conftest\.py$)",
    re.IGNORECASE,
)

# After:
_TEST_PATH_RE = re.compile(
    r"(unit_tests/|tests/|test_[^/]+\.py$|[^/]+_test\.py$|conftest\.py$"
    r"|commit_guardian/)",
    re.IGNORECASE,
)
```

The `commit_guardian/` segment matches any path containing that directory,
covering `scripts/commit_guardian/`, `templates/scripts/commit_guardian/`,
and `templates/commit-guardian/` (the latter contains `commit_guardian/`
as a substring via `commit-guardian/`). If a stricter match is preferred to
avoid false-negatives (e.g. some production file coincidentally containing
"commit_guardian" in its path), use:

```python
r"|(?:scripts/|templates/(?:scripts/)?)?commit[_-]guardian/"
```

Use whichever form is consistent with the codebase's pattern for exclusion
regexes in this file.

Also update the module docstring to note the self-exclusion logic was added.

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

2. `unit_tests/commit_guardian/test_check_contract_shrinking.py` (existing file):

   - `test_contract_shrinking_excludes_commit_guardian_paths`: Build a diff where
     `templates/scripts/commit_guardian/check_contract_shrinking.py` is modified
     (includes a `+pytest.mark.xfail` line). Assert `_scan_diff(diff).has_production_changes`
     is `False` (the commit_guardian file is excluded).

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

## Risk & Safety

- Touches money? No.
- Touches data? No — build phase emits warnings only; no user data affected.
- Reversibility? The integrity check is a non-blocking warning. Removing it
  requires only deleting the added loop. The `_TEST_PATH_RE` change is a safe
  regex extension; reverting it restores the previous (false-positive) behaviour.
- Risk of regressions: low. The integrity check loop runs after hooks are loaded
  and before `_resolve_template_vars` — it cannot affect the generated
  `.pre-commit-config.yaml`. The `_TEST_PATH_RE` change only broadens the
  exclusion set; it cannot cause a previously-blocked commit to pass unless the
  staged diff touches only commit_guardian paths.
- 295 tests pass before this change. The copied hook scripts are template files
  not imported by tests; no test coverage gap is introduced.
