# leafcutter/scripts

Python utility scripts for the leafcutter package. These scripts are
domain-agnostic and can be used by any adopter project.

## Purpose

Provides runtime utility modules that support the agent/skill/workflow system:
evaluation engines, validators, and build tools.

Contains the build toolchain for the leafcutter package. The main script
compiles agent templates and skill directories into a target project, injecting config
values and stripping adopter-facing metadata that the AI runtime would never act on.

## Key Files

- `selection_criteria_evaluator.py` — Two-tier DSL-first evaluator for
  `agent_registry.json` `selection_criteria.trigger_conditions`. Called by
  `business-analyst` to decide which agents to assign to a new ticket. Supports
  the v1 DSL grammar (see ADR-018) and stubs the LLM path.
- `build.py`: CLI entry point and orchestrator. Parses args, dispatches build phases.
  Supports `--dry-run`, `--validate-only`, `--force`, `--target-dir`, `--config-path`, `--no-shims`.
- `build_phases.py`: Seven build phase functions (agents, skills, workflows, rules,
  ticket-lifecycle, commit-guardian, doc-compliance). Called by `build.py`.
- `template_compiler.py`: Template compilation — YAML frontmatter parsing, metadata
  section stripping, config placeholder injection, agent/skill compilation.
- `config_loader.py`: Config I/O — loads and merges defaults + project config,
  validates against JSON schema.

## Critical Context

- Import: The package directory uses hyphens (`leafcutter`) which
  prevents direct Python import. Use `importlib.util.spec_from_file_location`
  when importing from test code (see test shim in
  `unit_tests/portable_dev_workflow/test_selection_criteria_evaluator.py`).
- The `evaluate()` function is the primary entry point. `evaluate_all()` is the
  batch helper for processing a full `trigger_conditions` list.
- `build.py` overwrites existing files by default so template edits always propagate.
  Use `--no-overwrite` to skip existing files (legacy behaviour). `--force` is a no-op
  alias for the default overwrite mode.
- Schema validation requires `jsonschema` (optional dependency); without it, build proceeds
  with a warning.
- The `install_shims` final step is skipped under `--dry-run` and can be disabled with `--no-shims`.
- Config is merged: `config/skills_config.default.json` (base) + `<target>/.claude/skills_config.json`
  (override). Project-specific values always win.

## Maintenance

- Adding a new DSL field: update `_VALID_FIELDS` in `_parse_atom()` and add
  handling in `_evaluate_atom()`. Add tests for the new field.
- Adding a new operator: update `_VALID_OPS` in `_parse_atom()` and add
  handling in `_evaluate_atom()`.
- The LLM stub (`type: llm`) will be wired in a follow-up ticket; change
  `LLMEvaluationRequired` from a `NotImplementedError` to an actual LLM call.
- When adding new template categories (e.g. `templates/hooks/`), add a corresponding
  `build_<category>` function in `build.py` and call it from `main()`.
- When adding new stripped headings, update the `STRIPPED_HEADINGS` set in `build.py`.
- All code changes must maintain the `DECISION HISTORY` block at the bottom of `build.py`.
