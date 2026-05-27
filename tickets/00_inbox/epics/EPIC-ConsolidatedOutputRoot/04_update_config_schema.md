---
title: "Update skills_config schema to configure the output root"
status: todo
components:
  - config_loader
created: 2026-05-26
depends_on:
  - 01_adr_output_layout.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/config/skills_config.default.json
  - leafcutter-ai/config/skills_config.schema.json
  - leafcutter-ai/scripts/config_loader.py
  - leafcutter-ai/scripts/path_resolver.py
agents:
  architect-review: needed
  python-coder: needed
  test-writer: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  documentation-expert: not_needed
  adr-author: not_needed
---

# 04: Update skills_config Schema for Output Root

## Goal
In order for consumer projects to control the output root name and shim
strategy via `skills_config.json`, we need to add `output_root` and
`shim_strategy` keys to the schema, update the default config, and teach
`config_loader.py` to validate and expose them.

## Context
This is the config-plumbing ticket that ticket 03 (phase redirect) depends
on at the schema level. It is sequenced after ticket 01 (ADR) because the
field names and defaults are settled by the ADR.

The `output_root` field controls where `build.py` concentrates its outputs.
The `shim_strategy` field controls how canonical-path tools (Claude Code,
pre-commit) are bridged. Both were designed in ticket 02 (shim layer) and
formalised in the ADR (ticket 01).

This ticket is intentionally narrow: schema + config_loader + validation
only. No build phase code is changed here (that is ticket 03).

## Acceptance Criteria

```gherkin
Given skills_config.json does not include output_root
When build.py runs
Then it defaults to output_root = ".leafcutter" without error

Given skills_config.json sets output_root = ".leafcutter"
When build.py runs
Then all phase outputs go to .leafcutter/ and the build log confirms the path

Given skills_config.json sets shim_strategy = "copy"
When build.py runs install_shims()
Then file copies (not symlinks) are created at canonical paths

Given skills_config.json contains an invalid shim_strategy value "teleport"
When build.py --validate-only runs
Then it exits non-zero with "Invalid shim_strategy: teleport. Valid values:
  symlink, copy, auto"
```

## Sign-offs

- [x] architect-review
- [x] python-coder
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### python-coder — 2026-05-27
(status: ok) Added output_root and shim_strategy to schema, defaults, and config_loader. ConfigValidationError raised on invalid shim_strategy. Keys are top-level in the merged config dict (no nesting needed).

### architect-review — 2026-05-27
(status: ok) Two fields sufficient for initial release. shim_paths can be added later if power users need fine-grained control over which canonical paths get shimmed.

## Implementation Tasks

### architect-review
- [ ] Confirm the two new fields (`output_root`, `shim_strategy`) are the full
  config surface needed, or whether `shim_paths` (a list of which canonical
  paths need shims) should also be configurable for power users

### python-coder
- [ ] Add to `leafcutter-ai/config/skills_config.schema.json`:
  ```json
  "output_root": {
    "type": "string",
    "description": "Folder name under target_root where build.py writes all outputs. Default: .leafcutter",
    "default": ".leafcutter"
  },
  "shim_strategy": {
    "type": "string",
    "enum": ["symlink", "copy", "auto"],
    "description": "How to bridge canonical tool paths to output_root. auto=symlink with copy fallback.",
    "default": "auto"
  }
  ```
- [ ] Add defaults to `leafcutter-ai/config/skills_config.default.json`:
  ```json
  "output_root": ".leafcutter",
  "shim_strategy": "auto"
  ```
- [ ] Update `config_loader.py` `validate_config()` to check `shim_strategy`
  against the enum and raise `ConfigValidationError` on invalid values
- [ ] Update `config_loader.py` `load_config()` to return `output_root` and
  `shim_strategy` as first-class keys (not nested) so phase functions can
  read them without dict navigation
- [ ] Update the `/onboard` wizard flow's generated `skills_config.json`
  template to include the new keys with defaults (in
  `leafcutter-ai/templates/agents/onboard-config-section.md` or whichever
  template produces the initial config)

### test-writer
- [ ] `leafcutter-ai/tests/test_config_loader_output_root.py`:
  - `test_output_root_default` — omitting `output_root` returns
    `".leafcutter"`
  - `test_output_root_custom` — setting `output_root = ".leafcutter"` is
    returned verbatim
  - `test_shim_strategy_invalid` — `"teleport"` raises `ConfigValidationError`
  - `test_shim_strategy_defaults_to_auto` — omitting `shim_strategy` returns
    `"auto"`

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? Additive schema change. Existing `skills_config.json` files
  without the new keys will use defaults, so no existing install breaks.
