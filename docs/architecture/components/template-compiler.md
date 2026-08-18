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
