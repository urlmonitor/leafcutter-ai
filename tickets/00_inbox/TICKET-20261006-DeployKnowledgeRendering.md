---
title: "Deploy knowledge_rendering.py with knowledge_query.py so consumer installs can import it"
status: todo
components:
  - knowledge_management
created: 2026-10-06
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - deploy
  - knowledge-query
  - build
  - regression
last_updated: 2026-10-06
files_touched:
  - scripts/build_phases_knowledge.py
  - scripts/build_phases_workflows.py
  - unit_tests/build_guards/test_workflow_tool_sibling_modules_deployed.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  commit: needed
---

# Deploy knowledge_rendering.py with knowledge_query.py so consumer installs can import it

## Actor / Goal
In order for every consumer install to run the knowledge-query skill, we need the build to ship
`scripts/knowledge_rendering.py` next to the deployed `knowledge_query.py`, and a guard that fails
the next time a sibling module that a deployed tool loads is left out of the deploy set.

## Context
- **Defect.** `scripts/knowledge_query.py:1284` loads a sibling module at import time:
  `_rendering = _load_sibling_module("knowledge_rendering")` (loader at `:205`). Commit
  `c2ddb6f12` (2026-10-01) moved rendering into `scripts/knowledge_rendering.py` but added it to
  neither deploy list:
  - the `deploy_scripts` list in `build_workflow_tools()`,
    `scripts/build_phases_workflows.py:502-514`;
  - the tuple in `_manifest_workflow_tool_scripts()`, `scripts/build_phases_knowledge.py:649-661`.
- **Effect.** Every consumer's `.leafcutter/scripts/knowledge_query.py` crashes on import with
  `FileNotFoundError: ...scripts/knowledge_rendering.py`. This workspace's own deployed copy is
  affected too.
- **Regressed AC.** KM-KGS-100a-3-xi is `done`, and its CI test
  `unit_tests/test_km_kgs_100a_3_xi_deploy.py::test_deployed_knowledge_query_reads_ac_record_same_as_source`
  now fails.
- **Why no guard caught it.**
  - Both hand lists missed the file, so the manifest/deploy parity checks still agreed.
  - The BP-900g-8 intra-package closure guard follows `import` statements only. A
    `_load_sibling_module("X")` call is a dynamic load, so the guard does not see it.
- `knowledge_rendering.py` imports only the stdlib (`json`, `typing`), so it has no further
  dependencies to deploy.
- **Duplication.** The same eleven-name list was kept twice by hand. Each of the last four
  sibling modules (KM-KGS-100a-3-xi, KM-KGS-100d-4, KM-KGS-100c-1, GE-118d) had to be added in
  both places. This ticket keeps one ordered tuple, `WORKFLOW_TOOL_SCRIPTS` in
  `scripts/build_phases_knowledge.py`. Both `_manifest_workflow_tool_scripts()` and
  `build_workflow_tools()` read it, and the missing-source warning
  (`record_deploy_failure`, BP-900g-9) is unchanged.
- Restores KM-KGS-100a-3-xi. No new AC is introduced.

## Acceptance Criteria
- [x] AC-1: `build_workflow_tools` deploys `scripts/knowledge_rendering.py` next to
  `knowledge_query.py`, byte-identical to its source.
- [x] AC-2: `_manifest_workflow_tool_scripts(package_root)` includes
  `scripts/knowledge_rendering.py`.
- [x] AC-3: `unit_tests/test_km_kgs_100a_3_xi_deploy.py` passes under `AC_ENFORCE_STRICT=1`,
  including `test_deployed_knowledge_query_reads_ac_record_same_as_source`.
- [x] AC-4: A new guard test scans every deployed workflow tool for `_load_sibling_module("X")`
  literals. It fails when any named module is missing from what `build_workflow_tools` deploys or
  from `_manifest_workflow_tool_scripts`. This is proven by temporarily removing one entry: the
  guard goes red, then green again once the entry is restored.
- [x] AC-5: After `python scripts/build.py --target-dir <workspace>`, the consumer's
  `.leafcutter/scripts/knowledge_query.py --help` exits 0.

```gherkin
Scenario: consumer-facing reachability
  Given a consumer install rebuilt with python scripts/build.py --target-dir <workspace>
  When .leafcutter/scripts/knowledge_query.py --help is invoked
  Then it exits 0 without a file-not-found or import-resolution error
  And it prints the knowledge_query usage line
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_every_sibling_module_a_deployed_tool_loads_is_deployed_and_in_the_manifest | WORKFLOW_TOOL_SCRIPTS entry | yes |
| AC-2 | test_every_sibling_module_a_deployed_tool_loads_is_deployed_and_in_the_manifest | WORKFLOW_TOOL_SCRIPTS entry | yes |
| AC-3 | test_deployed_knowledge_query_reads_ac_record_same_as_source | WORKFLOW_TOOL_SCRIPTS entry | yes |
| AC-4 | test_guard_names_a_sibling_module_left_out_of_the_deploy_set + manual mutation | guard test | yes |
| AC-5 | manual: rebuilt workspace, `--help` | build | yes |

## Test Requirements

```yaml
tests:
  - name: test_deployed_knowledge_query_reads_ac_record_same_as_source
    location: unit_tests/test_km_kgs_100a_3_xi_deploy.py
    type: behavioral
    covers: KM-KGS-100a-3-xi
    description: |
      Existing test. Deploys via build_workflow_tools into a temp package, then loads the
      DEPLOYED knowledge_query.py in a subprocess with no scripts/ on sys.path. Red today with
      FileNotFoundError on knowledge_rendering.py; green once it ships.

  - name: test_every_sibling_module_a_deployed_tool_loads_is_deployed_and_in_the_manifest
    location: unit_tests/build_guards/test_workflow_tool_sibling_modules_deployed.py
    type: behavioral
    covers: KM-KGS-100a-3-xi
    description: |
      Runs the real build_workflow_tools into a temp target. For every _load_sibling_module("X")
      literal found (by AST) in a deployed workflow tool, asserts scripts/X.py was deployed
      byte-identical to source AND is in _manifest_workflow_tool_scripts(package_root). All gaps
      are reported together. Red today for knowledge_rendering.

  - name: test_guard_names_a_sibling_module_left_out_of_the_deploy_set
    location: unit_tests/build_guards/test_workflow_tool_sibling_modules_deployed.py
    type: behavioral
    covers: KM-KGS-100a-3-xi
    description: |
      Non-vacuity check. The guard's own gap finder, given the real deployed set minus
      knowledge_rendering.py, names (knowledge_query.py, knowledge_rendering). Given the full set,
      it reports nothing.
```

## Comments

### 2026-10-06 10:36 — test-writer (status: ok)
feedback-id: fb_2026-10-06_e9e7f240
red_baseline:
  - test_name: test_deployed_knowledge_query_reads_ac_record_same_as_source
    file: unit_tests/test_km_kgs_100a_3_xi_deploy.py
    error: "FileNotFoundError: ...test_deployed_knowledge_query_0/scripts/knowledge_rendering.py (deployed knowledge_query.py exit 1)"
  - test_name: test_every_sibling_module_a_deployed_tool_loads_is_deployed_and_in_the_manifest
    file: unit_tests/build_guards/test_workflow_tool_sibling_modules_deployed.py
    error: "knowledge_query.py loads 'knowledge_rendering': missing from _manifest_workflow_tool_scripts / missing from build_workflow_tools deploy"
Added the guard test file. It has two tests: the real-deploy guard, red as shown above, and a
synthetic non-vacuity test, green. The synthetic test proves the gap finder names a sibling missing
on each side, ignores a non-literal loader argument, and reports nothing once both siblings ship.
The guard scans with `ast`, not a regex, so docstring prose such as
`_load_sibling_module(name)` never counts as a load.

### 2026-10-06 10:36 — python-coder (status: ok)
feedback-id: fb_2026-10-06_43a18947
red_baseline_results:
  - test_name: test_deployed_knowledge_query_reads_ac_record_same_as_source
    result: green
  - test_name: test_every_sibling_module_a_deployed_tool_loads_is_deployed_and_in_the_manifest
    result: green
- **Change.** The two hand lists became one tuple, `WORKFLOW_TOOL_SCRIPTS`
  (`scripts/build_phases_knowledge.py`), with `knowledge_rendering.py` added.
  `_manifest_workflow_tool_scripts()` iterates it. `build_workflow_tools()` imports it at call time
  and loops over it; it no longer keeps its own `deploy_scripts` list. The `record_deploy_failure`
  path is unchanged.
- **Tests.** `AC_ENFORCE_STRICT=1 pytest unit_tests/test_km_kgs_100a_3_xi_deploy.py <guard>`:
  8 passed.
- **Mutation.** Deleting the `"knowledge_rendering.py",` line made the deploy test and the guard
  fail, naming the module on both sides. The file was then restored and `cmp`-identical.
- **Rebuild.** `python scripts/build.py --target-dir <worktree>` exited 0 and deployed
  `scripts/knowledge_rendering.py`, `cmp`-identical to its source. `.leafcutter/scripts/knowledge_query.py --help`
  exited 0; before the rebuild it exited 1 with `FileNotFoundError`.
- **Lint.** ruff is clean, and `ast.parse` succeeds on every edited `.py` file.
- **Neighbouring suites.** test_km_kgs_100a_3_xi, test_bp_900b_1, test_bp_900g_4/8/8_i/8_ii,
  test_bp_closure_guard_correctness, test_build_guard_real_package, test_ge_118d(+_deployed) and
  test_bp_100k_2: 76 passed, 1 failed. The failure is
  `test_ge_118d_deployed_guard_accepts_bare_and_labelled_entries_in_all_three_fields`
  (`ModuleNotFoundError: frontmatter_path_resolver` in a temp-target build). It is PRE-EXISTING:
  it fails identically on an untouched checkout of 46a6033d7, so it is not caused by this change.

## Implementation Tasks
- [x] Move the workflow-tool name list into one ordered tuple, `WORKFLOW_TOOL_SCRIPTS`, in
  `scripts/build_phases_knowledge.py`, with `knowledge_rendering.py` added after
  `knowledge_surface_check.py`.
- [x] Make `_manifest_workflow_tool_scripts()` and `build_workflow_tools()` both read that tuple.
  The function-local import must keep the module's late-import convention.
- [x] Update the docstrings and DECISION HISTORY in both files.
- [x] Add the guard test under `unit_tests/build_guards/`.
- [x] Mutation proof: remove the entry, see the guard fail, restore it, and byte-compare.
- [x] Rebuild this workspace and run `.leafcutter/scripts/knowledge_query.py --help`.

## Out of Scope
- `scripts/build_deploy_manifest_helpers.py` still holds dead, stale copies of
  `_manifest_workflow_tool_scripts` and `_manifest_knowledge_scripts`, which `build.py` does not
  import. KM-300a/b ACs tell implementers to edit that copy. Removing it is a separate ticket.
- Teaching the BP-900g-8 closure guard about dynamic `_load_sibling_module` loads in general.

## Risk & Safety
- Touches money? No.
- Touches data? No. Only the build deploy list and a test change.
- Reversibility: a plain revert. The deployed file set only grows by one stdlib-only module.
