---
title: "Fix build system to respect config-driven folder paths and inject them into agent prompts"
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-06-03
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build_phases.py
  - scripts/injection_builders.py
  - scripts/template_compiler.py
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
  l1: BP-100c
  l2:
    - BP-100c-1
    - BP-100c-2
    - BP-100c-3
    - BP-100c-4
    - BP-100c-5
  l3:
    - BP-100c-1-i
    - BP-100c-2-i
    - BP-100c-3-i
  ac_path: docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
---

# Fix build system to respect config-driven folder paths and inject them into agent prompts

## Actor / Goal

In order to make the build system portable and self-hosting-correct, we need to replace
hardcoded `tickets/` and `docs/` path assumptions in `build_phases.py` and
`injection_builders.py` with config-derived paths so that `build-self.sh` no longer
creates dead scaffold folders at the workspace root (`leafcutter/tickets/`,
`leafcutter/docs/`) and agents always receive accurate path information.

## Context

Three independent bugs interact to produce two observable defects.

### Bug 1 — `build_ticket_lifecycle()` hardcodes `target_root / "tickets"`

`build_phases.py` line 669 reads:

```python
tickets_root = target_root / "tickets"
```

`skills_config.json` for the self-hosting build has:

```json
"tickets_inbox_path": "leafcutter-ai/tickets/00_inbox"
```

The inbox is under `leafcutter-ai/`, not at `tickets/`. Because the build system ignores
this config key when scaffolding the ticket lifecycle, every `build-self.sh` run writes
to `leafcutter/tickets/` (a dead directory never used by agents or humans) instead of
`leafcutter-ai/tickets/`. The correct root should be derived as
`Path(config["tickets_inbox_path"]).parent` → `leafcutter-ai/tickets/`.

An additional "already populated" guard is missing: unlike `build_vision()` (which skips
when `docs/vision.md` already exists), `build_ticket_lifecycle()` always reruns. Adding
a skip-if-manifest-exists guard matches the write-if-absent pattern established
throughout the codebase.

### Bug 2 — `build_project_paths_table()` reads only `paths.json` (no config overlay)

`injection_builders.py` line 285 defines `build_project_paths_table(package_root=None)`.
It reads `leafcutter/config/paths.json` which has static defaults like
`"tickets.inbox": "tickets/00_inbox/"`. These defaults are correct for consumer projects
but wrong for the self-hosting build where `skills_config.json` says
`"tickets_inbox_path": "leafcutter-ai/tickets/00_inbox"`.

At build time, `{{project_paths_table}}` injected into agent prompts (e.g.
`create-ticket.md`, `business-analyst.md`, `architect-review.md`) shows
`tickets/00_inbox/` when the self-hosting project's actual path is
`leafcutter-ai/tickets/00_inbox/`. Agents that read this table and use it verbatim
navigate to the wrong directory.

The fix: add a `config` parameter to `build_project_paths_table()`. After flattening
`paths.json`, overlay matching config values using the mapping:

| config key              | paths.json dotted key  |
|-------------------------|------------------------|
| `tickets_inbox_path`    | `tickets.inbox`        |
| `tickets_inbox_epics_path` | `tickets.inbox_epics` |
| `tickets_todo_path`     | `tickets.todo`         |
| `tickets_done_path`     | `tickets.done`         |
| `tickets_rejected_path` | `tickets.rejected`     |
| `docs_root`             | `docs.root`            |

When a config key is present and non-empty, its value replaces the corresponding
`paths.json` value in the flat list before the markdown table is rendered.

### Bug 3 — `compile_agent_template()` does not thread `config` to `_apply_registry_injection()`

`template_compiler.py` line 386 calls `_apply_registry_injection(...)` without passing
`config`. Inside `_apply_registry_injection()` (line 297), the `{{project_paths_table}}`
placeholder is resolved via `build_project_paths_table()` with no arguments, so the
config overlay from Bug 2's fix would never be applied even after that fix lands unless
`config` is threaded through.

### Resulting observable defects

1. `build-self.sh` creates `leafcutter/tickets/00_inbox/`, `leafcutter/tickets/01_todo/`,
   `leafcutter/docs/` — stale folders in the workspace root that confuse navigation and
   are never used by the installed system.
2. Compiled agent prompts in `.claude/agents/` show `tickets/00_inbox/` as the inbox
   path when the actual path used by all agents is `leafcutter-ai/tickets/00_inbox/`.

### Reference: `build_vision()` pattern (lines 810–843 of `build_phases.py`)

```python
def build_vision(target_root, config, dry_run, force):
    ...
    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    target_path = target_root / docs_dir / "vision.md"
    if target_path.exists():
        print(f"  vision: {docs_dir}/vision.md exists (skipped)")
        return 0
    ...
```

`build_ticket_lifecycle()` must adopt the same `config.get(...)` pattern for path
derivation and the same existence-check skip guard.

## Acceptance Criteria

```gherkin
Given a self-hosting build config with tickets_inbox_path = "leafcutter-ai/tickets/00_inbox"
When build-self.sh is run
Then leafcutter/tickets/ is NOT created
And leafcutter-ai/tickets/00_inbox/ already exists and is not modified

Given a self-hosting build config with tickets_inbox_path = "leafcutter-ai/tickets/00_inbox"
When build-self.sh is run
Then the compiled .claude/agents/create-ticket.md project_paths_table block
     shows "leafcutter-ai/tickets/00_inbox/" not "tickets/00_inbox/"

Given a consumer project with no tickets_inbox_path override in skills_config.json
When python build.py --target-dir <project> is run
Then <project>/tickets/00_inbox/ is created (standard default preserved)

Given leafcutter-ai/tickets/ticket_lifecycle.json already exists
When build-self.sh is run (no --force)
Then build_ticket_lifecycle() prints "exists (skipped)" and writes 0 files

Given build.py is run with --force on a project where ticket_lifecycle.json exists
When build_ticket_lifecycle() is reached
Then the write-if-absent guard is bypassed and files are overwritten
```

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
| BP-100c-1 | L2 | Ticket lifecycle scaffold uses config-driven inbox path instead of hardcoded default | python-coder |
| BP-100c-2 | L2 | Ticket lifecycle skips scaffold when manifest already exists | python-coder |
| BP-100c-3 | L2 | Project paths table overlays config values onto paths.json defaults | python-coder |
| BP-100c-4 | L2 | Template compiler threads config to project paths table generation | python-coder |
| BP-100c-5 | L2 | Consumer project with no config override gets standard default paths | python-coder |
| BP-100c-1-i | L3 | Folder remap applies config overrides to all lifecycle subdirectories | python-coder |
| BP-100c-2-i | L3 | Force flag bypasses the skip guard and overwrites existing manifest | python-coder |
| BP-100c-3-i | L3 | Partial config overlay leaves unspecified paths at their defaults | python-coder |

AC files: `docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100c-*.yaml`

## Comments

## Implementation Tasks

### python-coder

**Deliverable 1 — `build_ticket_lifecycle()` in `scripts/build_phases.py`**

1. Replace `tickets_root = target_root / "tickets"` (line 669) with:
   ```python
   inbox_path_str = config.get("tickets_inbox_path", "tickets/00_inbox")
   tickets_root = (target_root / inbox_path_str).parent
   ```

2. Add skip guard immediately after `written = 0`:
   ```python
   target_manifest = tickets_root / "ticket_lifecycle.json"
   if target_manifest.exists() and not force:
       print(f"  ticket_lifecycle: {tickets_root.relative_to(target_root)}/ticket_lifecycle.json exists (skipped)")
       return 0
   ```

3. Add folder remap dict for manifest folder paths:
   ```python
   _folder_remap = {
       "tickets/00_inbox":    config.get("tickets_inbox_path",    "tickets/00_inbox"),
       "tickets/01_todo":     config.get("tickets_todo_path",     "tickets/01_todo"),
       "tickets/99_done":     config.get("tickets_done_path",     "tickets/99_done"),
       "tickets/99_rejected": config.get("tickets_rejected_path", "tickets/99_rejected"),
   }
   ```

4. In the manifest folder-scaffolding loop, replace `folder_path = target_root / folder["path"]` with:
   ```python
   canonical = folder["path"]
   actual_rel = _folder_remap.get(canonical, canonical)
   folder_path = target_root / actual_rel
   ```

5. Update docstring and add DECISION HISTORY entry.

**Deliverable 2 — `build_project_paths_table()` in `scripts/injection_builders.py`**

1. Add `config: dict[str, Any] | None = None` parameter.

2. After `flat = _flatten(nested)`, insert config overlay:
   ```python
   if config:
       _config_to_paths_key = {
           "tickets_inbox_path":       "tickets.inbox",
           "tickets_inbox_epics_path": "tickets.inbox_epics",
           "tickets_todo_path":        "tickets.todo",
           "tickets_done_path":        "tickets.done",
           "tickets_rejected_path":    "tickets.rejected",
           "docs_root":                "docs.root",
       }
       flat_dict = dict(flat)
       for cfg_key, paths_key in _config_to_paths_key.items():
           val = config.get(cfg_key)
           if val:
               flat_dict[paths_key] = val
       flat = list(flat_dict.items())
   ```

3. Update docstring and add DECISION HISTORY entry.

**Deliverable 3 — Thread `config` through `scripts/template_compiler.py`**

1. Add `config: dict[str, Any] | None = None` to `_apply_registry_injection()` signature.
2. Change line 297 to `paths_table = build_project_paths_table(config=config)`.
3. Add `config=config` to the `_apply_registry_injection(...)` call in `compile_agent_template()` (line 386).
4. Update docstrings and add DECISION HISTORY entry.

**Deliverable 4 — Verification (run after tests pass)**

1. `rm -rf /home/henzeh/projects/leafcutter/tickets/ /home/henzeh/projects/leafcutter/docs/`
2. Run `./leafcutter-ai/build-self.sh`
3. Assert `leafcutter/tickets/` does NOT exist
4. Assert `leafcutter/docs/` does NOT exist
5. Grep `.claude/agents/create-ticket.md` for `tickets.inbox` and confirm it shows `leafcutter-ai/tickets/00_inbox`

### test-writer

Create `tests/test_config_driven_build_paths.py`:

- `test_ticket_lifecycle_uses_config_inbox_path`: call with `config={"tickets_inbox_path": "sub/tickets/00_inbox"}`, assert `target_root / "tickets"` does NOT exist, `target_root / "sub/tickets"` IS used.
- `test_ticket_lifecycle_skip_guard_when_manifest_exists`: pre-create manifest, call with `force=False`, assert return is `0`.
- `test_ticket_lifecycle_skip_guard_bypassed_by_force`: same setup, `force=True`, assert return > 0.
- `test_ticket_lifecycle_default_path_for_consumer_project`: `config={}`, assert `target_root / "tickets"` is the tickets root.
- `test_project_paths_table_overlays_config_values`: call with config override, assert output contains the override value.
- `test_project_paths_table_no_config_uses_paths_json`: `config=None`, assert output contains paths.json defaults.
- `test_compile_agent_template_threads_config_to_paths_table`: template with `{{project_paths_table}}`, call with config override, assert result contains override.

## Risk & Safety

- Touches money? No.
- Touches data? No — the fix avoids writing to wrong directories; existing content
  in `leafcutter-ai/tickets/` is protected by the skip guard.
- Reversibility? Config-path derivation falls back to `"tickets/00_inbox"` when
  `tickets_inbox_path` is absent. All parameter additions use default `None` —
  no existing callers break.
- Risk of regressions: medium. `build_ticket_lifecycle()` is called by `build.py`'s
  main orchestration loop; a bug here skips ticket scaffold for new installs. Test suite
  must explicitly cover the consumer-project default-path case.
