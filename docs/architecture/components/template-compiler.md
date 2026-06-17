---
title: "Template Compiler — Build-Time Artifact Generation"
description: "Build-time template compilation system that transforms Jinja-style agent and skill templates into deployed artifacts during the leafcutter build phase."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
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

## AC Store Script Deployment

The `build_ac_store_scripts` phase (AC BP-900a-1) deploys the following 13 files from `scripts/ac_store/` to `{consumer}/.leafcutter/scripts/ac_store/`:

- `ac_prioritizer.py` — ranks unimplemented ACs by priority
- `generate_ticket_from_ac.py` — scaffolds a ticket file from an AC store entry
- `scan_ac_store.py` — scans the AC YAML store for entries
- `mark_ac_done.py` — marks an AC as implemented in the store
- `validate_ac_schema.py` — validates AC YAML against schema
- `ac_triage.py` — fast triage agent for /plan-feature workflow
- `create_ac_workflow.py` — creates AC workflow scaffolds
- `cross_reference_audit.py` — audits cross-references between ACs
- `backfill_readiness.py` — checks readiness for AC backfill
- `ac_parent_id.py` — resolves parent AC IDs
- `scan_ac_orphans.py` — finds ACs without parent linkage
- `fix_ac_orphans.py` — repairs orphaned AC entries
- `__init__.py` — makes the directory a valid Python package

Each deployed file is byte-identical to its source (no template compilation). The phase runs in `internal_phases` so output goes into `.leafcutter/scripts/ac_store/` under the consumer project's output root.

The `__init__.py` is included in the deployed directory, making `scripts/ac_store/` a valid Python package.

## AC Store Script Importability (BP-900a-3)

After deployment, a directory shim is installed by `install_shims()` in `build_helpers.py`:

```
{consumer}/scripts/ac_store  →  {consumer}/.leafcutter/scripts/ac_store/
```

This shim means that any process running from `{consumer}/` can add `scripts/ac_store` to `sys.path` and import `ac_prioritizer`, `generate_ticket_from_ac`, and `scan_ac_store` without error. Agent templates (e.g. `build-ac.md`) and skills (e.g. `ac-scanner/SKILL.md`) rely on this importability contract.

## Post-Compile Script Path Reference Extraction (BP-900b-1)

After `build.py` compiles agent templates and skill files to the output directory, a post-compile validation phase can scan every `.md` file in the compiled `agents/` and `skills/` directories and extract all script path references. This extraction is implemented by `extract_script_path_refs()` in `scripts/build_referential_integrity.py`.

### Patterns matched

The extractor recognises four reference forms:

| Pattern form | Example |
|---|---|
| `python3 scripts/<path>` | `python3 scripts/ac_store/ac_prioritizer.py` |
| `python scripts/<path>` | `python scripts/goal_to_epic.py` |
| `sys.path.insert(<N>, 'scripts/<path>')` | `sys.path.insert(0, 'scripts/ac_store')` |
| `sys.path.insert(<N>, "scripts/<path>")` | `sys.path.insert(0, "scripts/ac_store")` |

### API

```python
from build_referential_integrity import extract_script_path_refs
from pathlib import Path

compiled_root = Path("/path/to/consumer/.claude")
refs = extract_script_path_refs(compiled_root)
# refs is a set[str] — e.g. {"scripts/ac_store/ac_prioritizer.py", ...}
```

`compiled_root` is typically `<target>/.leafcutter` or `<target>/.claude`. The function looks for `.md` files recursively under `compiled_root/agents/` and `compiled_root/skills/`. It is intentionally fail-open: unreadable files are silently skipped and the function never raises.

### Minimum expected paths

When the compiled output includes templates that reference these scripts, the returned set will include at minimum:

- `scripts/ac_store/ac_prioritizer.py`
- `scripts/ac_store/generate_ticket_from_ac.py`
- `scripts/goal_to_epic.py`

## External-Dependency Allowlist and Broken-Reference Guard (BP-900b-1-1)

After script path references are extracted, a cross-check guard compares them against the set of scripts actually deployed to the target project. References that are neither deployed nor allowlisted are classified as **broken references**.

The external-dependency allowlist lets agent templates legitimately reference scripts that are supplied by the user's own project or by an external tool — without triggering a broken-reference failure in the build.

### Allowlist constant

```python
# scripts/build_propagation_audit.py
EXTERNAL_DEPENDENCY_ALLOWLIST: frozenset[str] = frozenset()
```

The constant is a `frozenset[str]` where each entry is a `scripts/<relative-path>` string matching the form produced by `extract_script_path_refs()`. The default value is empty; consumers extend it either by editing the constant or by passing a custom `allowlist` argument to `check_broken_references()`.

### Guard function

```python
from build_propagation_audit import check_broken_references, EXTERNAL_DEPENDENCY_ALLOWLIST
from build_referential_integrity import extract_script_path_refs
from pathlib import Path

compiled_root = Path("/path/to/consumer/.claude")
refs = extract_script_path_refs(compiled_root)

deployed = {"scripts/ac_store/ac_prioritizer.py", "scripts/goal_to_epic.py"}
broken = check_broken_references(refs, deployed)
# broken is a set[str] — empty means build may exit zero
```

To exempt a known external script:

```python
custom_allowlist = frozenset({"scripts/external_tool.py"})
broken = check_broken_references(refs, deployed, allowlist=custom_allowlist)
# "scripts/external_tool.py" will NOT appear in `broken`
```

### Behaviour contract

| Ref present in `deployed_scripts` | Ref in `allowlist` | Result |
|---|---|---|
| Yes | — | Resolved — not broken |
| No | Yes | Resolved (allowlisted) — not broken |
| No | No | **Broken** — appears in return set |

The function is a pure predicate (no I/O, no side effects) and never raises. An empty return set means all references are accounted for and the build may exit zero, satisfying AC BP-900b-1-1.

## Three-Field Broken-Reference Report (BP-900c-1)

When a broken reference is detected, the error report entry must carry three fields so that the developer knows exactly what is wrong and how to fix it:

1. **Missing path** — the `scripts/<path>` string that was referenced but not deployed (e.g. `"scripts/ac_store/ac_prioritizer.py"`)
2. **Referencing template** — the relative path of the compiled template that contains the reference (e.g. `"agents/build-ac.md"`)
3. **Suggested action** — one of two canonical strings:
   - `"add a deploy phase in build_phases.py"` — for paths under leafcutter-owned directories (`scripts/ac_store/`, `scripts/feedback/`, `scripts/commit_guardian/`)
   - `"add to the external-dependency allowlist"` — for all other paths (externally-supplied scripts)

No field may be empty or omitted.

### Data types

```python
# scripts/build_propagation_audit.py
from dataclasses import dataclass

@dataclass(frozen=True)
class BrokenRefEntry:
    missing_path: str           # e.g. "scripts/ac_store/ac_prioritizer.py"
    referencing_template: str   # e.g. "agents/build-ac.md"
    suggested_action: str       # ACTION_ADD_DEPLOY_PHASE or ACTION_ADD_TO_ALLOWLIST
```

### Full-pipeline example

```python
from build_referential_integrity import extract_script_path_refs_with_sources
from build_propagation_audit import build_broken_ref_report
from pathlib import Path

compiled_root = Path("/path/to/consumer/.claude")
# Step 1 — extract refs WITH source template information
refs_to_sources = extract_script_path_refs_with_sources(compiled_root)
# e.g. {"scripts/ac_store/ac_prioritizer.py": {"agents/build-ac.md"}}

deployed = {"scripts/ac_store/generate_ticket_from_ac.py"}
# Step 2 — build the three-field report
report = build_broken_ref_report(refs_to_sources, deployed)
for entry in report:
    print(entry.missing_path)          # "scripts/ac_store/ac_prioritizer.py"
    print(entry.referencing_template)  # "agents/build-ac.md"
    print(entry.suggested_action)      # "add a deploy phase in build_phases.py"
```

The `extract_script_path_refs_with_sources()` function is provided by `build_referential_integrity.py` alongside the existing `extract_script_path_refs()`. It returns a `dict[str, set[str]]` mapping each script path to the set of template paths that reference it, preserving the per-template provenance required by BP-900c-1.
