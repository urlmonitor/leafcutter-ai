---
title: "Redirect all build phase outputs into leafcutter-project/ root"
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-05-26
depends_on:
  - 02_design_shim_layer.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/scripts/build_phases.py
  - leafcutter-ai/scripts/build_precommit.py
  - leafcutter-ai/scripts/build_helpers.py
  - leafcutter-ai/scripts/build_glossary.py
  - leafcutter-ai/scripts/build_propagation_audit.py
  - leafcutter-ai/scripts/build_claude_settings.py
  - leafcutter-ai/scripts/build_roadmap_phase.py
  - leafcutter-ai/scripts/build_config_scaffolds.py
  - leafcutter-ai/scripts/build_antigravity_instructions.py
  - leafcutter-ai/scripts/build.py
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

# 03: Redirect All Build Phase Outputs into leafcutter-project/

## Goal
In order to isolate leafcutter artifacts from consumer project files, we need
to update every `build_*.py` phase module so that its output root is
`<target_root>/leafcutter-project/` (configurable) rather than the project
root directly, then invoke the shim layer (ticket 02) to forward canonical
paths.

## Context
`build.py` currently dispatches 17+ phase functions that emit to:
- `.claude/` — agents, skills, commands, hooks, settings
- `scripts/` — commit_guardian, security_scanner, doc_compliance, glossary, etc.
- `docs/` — vision.md, roadmap.json, glossary.md, architecture scaffolds
- project root — `.pre-commit-config.yaml`, `.gemini/`, `.antigravity/`,
  build manifest

After this ticket, all phase functions redirect their writes to
`<target_root>/leafcutter-project/<same-relative-path>`. The `install_shims()`
function from ticket 02 then creates the canonical-path shims.

Phase modules affected:
`build_agents`, `build_skills`, `build_workflows`, `build_rules`,
`build_ticket_lifecycle`, `build_commit_guardian`, `build_precommit_config`,
`build_doc_compliance`, `build_feedback`, `build_vision`,
`build_antigravity_instructions`, `build_sync_platforms`, `build_glossary`,
`build_propagation_audit`, `build_claude_settings`, `build_roadmap`,
`build_config_scaffolds`, `seed_docs`, `update_diagrams`.

The `output_root` for each phase is derived from
`config.get("output_root", "leafcutter-project")`, which resolves relative to
`target_root`.

## Acceptance Criteria

```gherkin
Given build.py runs on a clean consumer project
When examining the filesystem after build
Then all leafcutter-owned files exist under <target_root>/leafcutter-project/
And .claude/, scripts/, docs/, and the project root contain no leafcutter files
  except shim symlinks or copies placed by install_shims()

Given a consumer project that ran the old build.py (files scattered at root)
When build.py --migrate runs
Then old scattered files are detected and the user is warned to remove them
  (migration is covered in ticket 05; this ticket only adds the new output path)

Given build.py runs with --dry-run
When examining the output
Then the phase log shows "would write to leafcutter-project/<path>" for every
  file that would be created
```

## Sign-offs

- [ ] architect-review
- [ ] python-coder
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review
- [ ] Review the output-root indirection in each phase function and confirm the
  abstraction is clean — phase functions should receive `output_root` as a
  resolved `Path`, not re-derive it themselves
- [ ] Confirm the manifest (build_helpers.write_build_manifest) records the new
  paths so future `--validate-only` runs can verify the layout

### python-coder
- [ ] Add `output_root` parameter to `config_loader.py` `load_config()`:
  reads `config.get("output_root", "leafcutter-project")`, resolves it
  relative to `target_root`, and adds it to the returned config dict
- [ ] Thread `output_root` path through `build.py` into every phase function
  call (each phase takes `target_root` — change signature to also accept
  `output_root` or derive it inside `build.py` before dispatch)
- [ ] Update each phase function in `build_phases.py` to write under
  `output_root` instead of `target_root` directly:
  - `build_agents`: `.claude/agents/` → `output_root/agents/`
  - `build_skills`: `.claude/skills/` → `output_root/skills/`
  - `build_workflows`: `.claude/commands/` → `output_root/commands/`
  - `build_rules`: `.claude/rules/` → `output_root/rules/`
  - `build_ticket_lifecycle`: `tickets/` → `output_root/tickets/`
  - `build_commit_guardian`: `scripts/commit_guardian/` →
    `output_root/scripts/commit_guardian/`
  - `build_doc_compliance`: `scripts/doc_compliance/` →
    `output_root/scripts/doc_compliance/`
  - `build_feedback`: `scripts/feedback/` → `output_root/scripts/feedback/`
  - `build_vision`: `docs/vision.md` → `output_root/docs/vision.md`
  - `build_antigravity_instructions`: `.gemini/` → `output_root/gemini/`,
    `.antigravity/` → `output_root/antigravity/`
  - `build_sync_platforms`: platform scripts → `output_root/scripts/`
  - `build_glossary`: `docs/glossary.md` → `output_root/docs/glossary.md`
  - `build_propagation_audit`: audit script → `output_root/scripts/`
  - `build_claude_settings`: `.claude/settings.json` →
    `output_root/settings.json`
  - `build_roadmap`: `docs/roadmap.json` → `output_root/docs/roadmap.json`
  - `build_config_scaffolds`: `leafcutter/config/` →
    `output_root/config/`
  - `build_precommit_config`: `.pre-commit-config.yaml` →
    `output_root/pre-commit-config.yaml`
- [ ] Call `install_shims(target_root, output_root, config, dry_run, force)` at
  the end of `main()` in `build.py` after all phase functions complete
- [ ] Update `write_build_manifest()` to record `output_root` in the manifest

### test-writer
- [ ] `leafcutter-ai/tests/test_build_phases_output_root.py`:
  - `test_build_agents_uses_output_root` — verifies agents are written under
    `output_root`, not `target_root/.claude/agents/`
  - `test_build_precommit_uses_output_root` — verifies `.pre-commit-config.yaml`
    is written under `output_root`, not target root
  - `test_output_root_default_is_leafcutter_project` — verifies the default
    config value is `leafcutter-project`
  - `test_dry_run_logs_output_root_paths` — verifies dry-run logs show
    `leafcutter-project/<path>`

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? The phase redirect is a one-way change in this ticket. A
  consumer running the old build.py will still have old files at root; the
  migration ticket (05) adds the detection/cleanup path. Reversing requires
  reverting this ticket and ticket 05.
- Breaking change for existing installs: after this ticket lands, running
  `build.py` will write to `leafcutter-project/` but NOT clean up old files
  at their previous locations. Existing installs need the migration step
  (ticket 05) to remove stale files.
