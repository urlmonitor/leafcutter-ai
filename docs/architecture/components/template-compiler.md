---
title: "Template Compiler — Build-Time Artifact Generation"
description: "Build-time template compilation system that transforms Jinja-style agent and skill templates into deployed artifacts during the leafcutter build phase."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-08-18
components:
  - template_compiler
---

# Template Compiler

## Overview

The Template Compiler transforms templates from `templates/agents/`, `templates/skills/`, and `templates/hooks/` into deployed artifacts in `.claude/agents/`, `.claude/skills/`, and `.claude/hooks/` respectively. It runs as part of the `build.py` build pipeline.

## Responsibilities

- Interpolate template variables with project-specific values
- Validate template outputs against schema constraints
- Stage compiled artifacts for the consumer project's `.claude/` directory

## Entry Points

- `scripts/template_compiler.py` — core compilation logic
- `scripts/build.py` — main build entry point
- `scripts/build_phases.py` — phase-by-phase build orchestration

## Integration

The `build-self.sh` script invokes the compiler for local development. Consumer installs run `python leafcutter-ai/scripts/build.py --target-dir .` to deploy compiled artifacts.

## Standalone Script Deployment

`build_template_standalone_scripts` (scripts/build_phases.py) deploys every
top-level `.py` file under `templates/scripts/` (non-recursive) verbatim to
`<output_root>/scripts/`. This includes `goal_to_epic.py` (a thin delegator
to the full implementation deployed separately at
`<output_root>/scripts/ac_store/goal_to_epic.py` by `build_ac_store`, kept
this way to stay under the 400-line file-size limit) and
`build_ac_mode_detection.py` (a full copy, small enough to duplicate
safely). `install_shims()` (scripts/build_helpers.py) then creates a
relative-symlink shim at `<target>/scripts/<name>` for each, resolving to
the deployed copy (AC BP-900a-2).

## Deployed ac_store Import Contract (AC BP-900a-3)

Once `build_ac_store` has deployed the ac_store scripts to a consumer project
(AC BP-900a-1), the deployed `<output_root>/scripts/ac_store/` directory is
guaranteed **importable** as a Python package by any process that adds it to
`sys.path` — this is the contract the agent templates rely on at runtime.
`templates/agents/build-ac.md` embeds the exact mechanism twice (its
`readiness-check-drift` and `dry-run` steps), and
`templates/skills/ac-scanner/SKILL.md` documents the underlying script the
same templates shell out to:

```python
import sys
sys.path.insert(0, "{{config.output_root}}/scripts/ac_store")
from scan_ac_store import traverse_ac_tree
```

Two properties make this importable:

- **`__init__.py` is present.** `build_ac_store`'s `deploy_map` deploys all
  13 ac_store files, including `scripts/ac_store/__init__.py`, so the
  deployed directory is a valid Python package rather than a bare directory
  of scripts. `__init__.py` is intentionally empty (zero bytes) — it
  introduces no import-time side effects, so importing the package (or any
  of `ac_prioritizer`, `generate_ticket_from_ac`, `scan_ac_store` from
  within it) never runs unexpected code as a side effect of the `sys.path`
  insert.
- **No broken internal cross-module imports.** None of `ac_prioritizer.py`,
  `generate_ticket_from_ac.py`, or `scan_ac_store.py` import each other via a
  path that only resolves when `ac_store`'s *parent* directory (rather than
  `ac_store` itself) is on `sys.path`, so inserting
  `<output_root>/scripts/ac_store` directly — as the templates above do — is
  sufficient for all three modules to import without `ImportError`.

Regression coverage for this contract runs the real `build.py --target-dir`
into a fresh directory, then imports the three named modules from a fresh
subprocess seeded only with the deployed `scripts/ac_store` path — reproducing
the templates' own `sys.path.insert` pattern rather than importing from the
source tree, which would mask a deploy-manifest gap (`unit_tests/test_bp_900a_3.py`).

## Missing ac_store Source Hard-Fails the Build (AC BP-900a-1-1)

`build_ac_store` (`scripts/build_phases.py`) validates that every source file
in its `deploy_map` exists on disk **before copying any of them**. If one or
more sources are absent (e.g. `scripts/ac_store/__init__.py` was deleted or
renamed from the package), `build_ac_store` raises `RuntimeError` naming
every missing source path, and `build.py`'s `main()` catches it around the
`_run_phases()` call, prints a single `[ERROR] Build aborted: ...` line, and
returns exit code 1 — before any `scripts/ac_store/` output is written to the
target project.

This replaced the previous per-file behaviour: a missing source used to log a
`WARNING` and `continue` inside the copy loop, so the build exited `0` while
depositing a **partial** `scripts/ac_store/` directory on the target (e.g.
every file except the missing one). That silent partial deployment is exactly
the "ships half-deployed" failure mode this AC closes — a capability that
looks successfully installed (exit 0) but is missing a script another
template or skill depends on at runtime.

This guard is distinct from `_check_script_reference_guard`
(`scripts/build.py`) and the deployed-manifest cross-check below: those scan
what templates *reference* and what is *deployed*, so they never flag a
`deploy_map` entry that no template invokes via a `python3 scripts/...`
pattern (`scripts/ac_store/__init__.py` is one such entry — it is imported as
a package member, never shelled out to directly). `build_ac_store`'s own
pre-write existence check is the only guard that validates its `deploy_map`
sources are complete, independent of how (or whether) any template
references them.

## Compiled-Output Script Reference Scan (AC BP-900b-1)

`build_referential_integrity.extract_compiled_script_path_refs(compiled_root)`
is the post-compile counterpart to `extract_script_path_refs()` /
`extract_script_path_refs_with_sources()` (which scan the SOURCE `templates/`
tree and are wired into `build.py`'s pre-build guard,
`_check_script_reference_guard`, before `_run_phases()` writes any output).
`extract_compiled_script_path_refs` instead scans the COMPILED output tree
(e.g. `<target>/.claude/agents/` and `<target>/.claude/skills/`) written by a
`build.py --target-dir` run, recursively over every `.md` file, and returns
`set[tuple[str, str]]` of `(relative_template_path, referenced_script_path)`
so each script-path reference can be traced back to the compiled template
that names it. It reuses the same three extraction patterns
(`python3 scripts/<path>`, `python scripts/<path>`, and both quote variants of
`sys.path.insert(<N>, 'scripts/<path>')`) as its source-tree siblings.

As of this AC, `extract_compiled_script_path_refs` is a standalone, read-only
scan (it never raises; unreadable files are skipped) — no production call
site invokes it as part of `build.py`'s phase list yet. Wiring it into an
actual post-compile validation phase is a documented follow-up, not part of
this AC's scope.

## Broken-Reference Report Entry Schema (AC BP-900c-1)

When the build-time guard finds a script path referenced by a compiled
template but absent from the deployable script set, it reports the failure as
a `BrokenRefEntry` (`scripts/build_propagation_audit.py`). Every entry names
all three of the following fields — none may be empty or omitted:

- **`missing_path`** — the `scripts/<path>` string that was referenced but is
  not in the deployable script set (e.g. `scripts/ac_store/ac_prioritizer.py`).
- **`referencing_templates`** — the compiled template path(s) that reference
  the missing script (e.g. `agents/build-ac.md`). When multiple templates
  reference the same missing path, `build_broken_ref_report` consolidates them
  into a single entry's `referencing_templates` tuple instead of emitting one
  entry per template (AC BP-900c-1-1). `emit_broken_ref_report_jsonl` writes
  this field to JSONL as `referencing_template` (singular key, string or list
  value) (AC BP-900c-2).
- **`suggested_action`** — a corrective action drawn from a finite, named set
  of constants: `ACTION_ADD_DEPLOY_PHASE` ("add a deploy phase in
  build_phases.py"), `ACTION_ADD_TO_ALLOWLIST` ("add to the
  external-dependency allowlist"), or `ACTION_COMMIT_UNDER_TEMPLATES` (the
  directory already has a deploy phase, so the source file is merely missing
  or untracked — commit it under `templates/scripts/`) (AC BP-900c-3). The
  three-field entry shape is stable across all three action values; only the
  chosen action varies with the missing path's classification.

`build_broken_ref_report(refs_to_sources, deployed_scripts, allowlist=None)`
is the factory that produces the list of `BrokenRefEntry` instances for a
build run.

## External-Dependency Allowlist (AC BP-900b-1-1)

`EXTERNAL_DEPENDENCY_ALLOWLIST` (`scripts/build_propagation_audit.py`) is a
`frozenset[str]` of `scripts/<path>` strings that the reference guard treats
as intentionally external — scripts that agent or skill templates reference
but that this repository does not, and is not expected to, deploy itself
(e.g. `scripts/build.py`'s own self-reference, or
`scripts/inline_adr/append_entry.py`, which doc-enforcer's SKILL.md already
guards with an explicit "if present" check). Each entry carries an inline
comment explaining why the path is legitimately out of scope rather than a
deploy-phase gap.

`check_broken_references(refs, deployed_scripts, allowlist=None)` and
`build_broken_ref_report(refs_to_sources, deployed_scripts, allowlist=None)`
both resolve a reference against `deployed_scripts | allowlist` before
deciding it is broken, defaulting `allowlist` to
`EXTERNAL_DEPENDENCY_ALLOWLIST` (merged with the empty
`KNOWN_UNDEPLOYED_ALLOWLIST`) when the caller passes `None` — which is the
path `build._check_script_reference_guard` exercises in production, since it
calls `build_broken_ref_report` without an explicit `allowlist` argument.
Per AC BP-900b-1-1: when a referenced script path (e.g.
`scripts/external_tool.py`) is listed in `EXTERNAL_DEPENDENCY_ALLOWLIST`,
the guard treats the reference as resolved, and it does NOT appear in the broken-reference
set or report, even though the path is absent from `deployed_scripts` — so
the build exits zero on that reference alone (assuming no other broken
references exist). A reference that is neither deployed nor allowlisted is
still reported broken; the allowlist only resolves the paths it explicitly
names.

## Deployed-Manifest Cross-Check Guard (AC BP-900b-2)

`scripts/build_phases.py` provides two functions that close the loop between
`extract_compiled_script_path_refs` (post-compile reference extraction, AC
BP-900b-1) and the deployed output of a real build run:

- **`get_deployable_script_manifest(target_root)`** — scans an
  already-built project's `<target_root>/.leafcutter/scripts/` (the
  consolidated output root, populated by phases such as `build_ac_store` and
  `build_template_standalone_scripts`) and `<target_root>/scripts/` (the
  `install_shims()` shim location) directly from disk, and returns the set
  of `"scripts/<path>"` strings for every deployed `.py` file. It reads the
  real filesystem output of a build — it does not hardcode or duplicate
  `build_ac_store`'s `deploy_map`, avoiding the drift class that produced the
  BP-900g-4/-5/-6 hotfixes.
- **`cross_check_refs_against_manifest(refs, manifest)`** — takes the
  `set[tuple[str, str]]` returned by `extract_compiled_script_path_refs`
  (`(referencing_template, "scripts/<path>")` tuples) and the manifest above,
  and returns `list[dict]` with one `{"missing_path": str,
  "referencing_template": str}` entry per reference whose script path is
  absent from the manifest. A reference whose script is present is marked
  resolved simply by its absence from the result. Unlike
  `build_broken_ref_report` (which groups all referencing templates for one
  missing script into a single entry), this guard reports one entry **per
  reference**, matching AC BP-900b-2's `delivers_to` contract.

Like `extract_compiled_script_path_refs`, both functions are standalone and
read-only; wiring them into `build.py`'s phase list as an active post-compile
validation gate is a documented follow-up, not part of this AC's scope.

## CI and Fresh-Clone Test Requirements

The full test suite requires the build step to run **before** `pytest` on any
fresh checkout (including CI). The build step's `install_shims()` phase creates
symlinks at `scripts/commit_guardian/`, `scripts/doc_compliance/`, and
`scripts/feedback/` pointing into `.leafcutter/scripts/`. Test files add those
`scripts/<name>/` paths to `sys.path` at import time; without the shims, ~36
tests fail at import on a clean checkout.

The documented CI test command is:

```bash
# 1. Install development dependencies
pip install -r requirements-dev.txt

# 2. Run the build step to deploy shims and artifacts
python scripts/build.py --target-dir .

# 3. Run the full test suite
python -m pytest tests/ unit_tests/ -x -q
```

See [ADR-016](../adrs/ADR-016-ci-fresh-clone-test-dependencies.md) for the
full decision record on this design.
