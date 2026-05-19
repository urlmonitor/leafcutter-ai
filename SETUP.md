# SETUP.md — AI-Assisted Setup Guide

> **Audience:** An AI assistant that has been asked to "set up the dev workflow"
> for a project. Read this file, follow the steps, and configure the system
> without requiring the human to read any other documentation.

> **Human quick path:** If you prefer a step-by-step human guide, read
> `BOOTSTRAP.md` instead.

---

## Overview

This file teaches an AI assistant how to:

1. Detect project-specific values from the codebase
2. Generate a valid `skills_config.json` for the target project
3. Run `build.py` to install agents, skills, workflows, and hooks
4. Report what was configured and what to customise later

The entire setup takes under 10 minutes in a conversation.

---

## Prerequisites

Before starting, verify:

- Git repo with at least one commit (pre-commit requires history)
- Python ≥ 3.11 installed
- Poetry installed (`pip install poetry`)
- pre-commit installed (`pip install pre-commit`)

---

## Config Schema Reference

Every key in `skills_config.json` is described below. For each key, use the
auto-detection recipe if available; otherwise ask the user.

### Ticket paths

| Key | Type | Description | Auto-detect? |
|-----|------|-------------|-------------|
| `tickets_inbox_path` | string | Folder for proposed tickets | Check for `tickets/00_inbox/`; use if exists, else ask |
| `tickets_inbox_epics_path` | string | Folder for proposed epics | Derive from inbox: `{tickets_inbox_path}/epics` |
| `tickets_todo_path` | string | Folder for in-flight tickets | Check for `tickets/01_todo/`; use if exists, else ask |
| `tickets_done_path` | string | Folder for completed tickets | Check for `tickets/09_done/` or `tickets/99_done/`; use first found, else ask |

### Test commands

| Key | Type | Description | Auto-detect? |
|-----|------|-------------|-------------|
| `test_command_live_trader` | string | Fast test suite (< 5s) | See recipe below |
| `test_command_sql` | string | Slow SQL/DB tests | See recipe below |
| `test_command_single_file_pattern` | string | Run one test file | Derive from live_trader command pattern |

### Other keys

| Key | Type | Description | Auto-detect? |
|-----|------|-------------|-------------|
| `precommit_autofix_config_path` | string | Path to precommit-autofix.json | Default: `.claude/precommit-autofix.json` |
| `default_branch` | string | Main branch name | See recipe below |
| `worktree_base_path` | string | Where epic worktrees are created | Default `../`; ask if non-standard |
| `top_level_packages` | array | Top-level Python packages | See recipe below |
| `test_output_dir` | string | Temp dir for test file output | Use `%TEMP%/<project-name>-tests/` on Windows, `/tmp/<project-name>-tests/` on Unix |
| `settings_module` | string | Python settings module name | Check for `settings.py` at repo root; ask if absent |

---

## Auto-Detection Recipes

### `default_branch`

```bash
git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||'
# Falls back to:
git branch --show-current
# If still empty: ask user ("main" is the most common default)
```

### `top_level_packages`

```bash
# Find directories with __init__.py at depth ≤ 2
find . -maxdepth 2 -name "__init__.py" -not -path "./.venv/*" -not -path "./.git/*" \
  | xargs -I{} dirname {} \
  | sed 's|^\./||' \
  | grep -v "^$"
```

Only include packages that are actual code modules (exclude `tests/`, `unit_tests/`,
`alembic/`, `docs/`, `.claude/`).

### `test_command_live_trader`

Check `pyproject.toml` for test configuration:

```bash
python -c "
import tomllib, pathlib
data = tomllib.loads(pathlib.Path('pyproject.toml').read_text())
pytest_conf = data.get('tool', {}).get('pytest', {}).get('ini_options', {})
testpaths = pytest_conf.get('testpaths', [])
print(testpaths)
" 2>/dev/null
```

Fallback heuristics (in order):
1. If `unit_tests/` exists with subdirectories: `poetry run python -m unittest discover -s unit_tests/<subdir> -t . -p "test_*.py"`
2. If `tests/` exists: `poetry run pytest tests/ -v`
3. Ask user

### `worktree_base_path`

```bash
git worktree list --porcelain 2>/dev/null | grep "^worktree " | head -1 | awk '{print $2}'
# If multiple worktrees exist, infer the common parent directory relative to repo root
```

Default `../` works for the project convention of placing worktrees as siblings of
the main repo.

---

## Interactive Questions

Ask the user these questions when auto-detection is not definitive:

1. **What is the fast unit test command?**
   "I'll use this to validate code before committing. It should complete in < 5 seconds."

2. **Are there any top-level packages I missed?**
   "I detected these: [list]. Are there others, or should any be removed?"

3. **What is the test output directory?**
   "Tests that write files should use a temp directory. I'll default to `%TEMP%/<project>-tests/`."

4. **What is the settings module name?**
   "The settings module provides project-wide configuration constants.
   Common names: `settings`, `config`, `core.settings`. Leave blank if none."

---

## Validation Step

After generating `skills_config.json`, validate it:

```bash
python leafcutter/scripts/build.py --validate-only
```

If validation fails:
- `Missing required key: <key>` → add the key with a value
- `Invalid type for <key>: expected <type>` → correct the value type
- `Schema validation error` → run `python -c "import json; json.load(open('.claude/skills_config.json'))"` to check JSON syntax

---

## Build Step

Run the build to install agents, skills, workflows, and hooks:

```bash
python leafcutter/scripts/build.py --target-dir <repo-root>
```

What this installs:

| Installed path | Source |
|----------------|--------|
| `.claude/agents/` | `leafcutter/templates/agents/` |
| `.claude/skills/` | `leafcutter/templates/skills/` |
| `.agents/workflows/` | `leafcutter/templates/workflows/` |
| `scripts/commit_guardian/` | `leafcutter/templates/commit-guardian/` |
| `scripts/doc_compliance/` | `leafcutter/templates/doc-compliance/` |
| `tickets/` | `leafcutter/templates/ticket-lifecycle/` |

Use `--force` to overwrite existing files:

```bash
python leafcutter/scripts/build.py --target-dir <repo-root> --force
```

---

## Post-Setup Checklist

After a successful build, verify:

- [ ] `.claude/skills_config.json` exists with correct values
- [ ] `CLAUDE.md` exists (generated by `build.py` from `templates/CLAUDE.md.template`; fill in any `<!-- TODO: fill in ... -->` sections)
- [ ] `.pre-commit-config.yaml` exists and references `run_hook.py`
- [ ] `pre-commit install` has been run
- [ ] `pre-commit install --hook-type post-commit` has been run
- [ ] `pre-commit run --all-files` exits cleanly (or with only advisory warnings)
- [ ] A test ticket exists in `tickets/00_inbox/` to verify `/build-feature`

### Verify the agent pipeline

Create a minimal test ticket:

```bash
cat > tickets/00_inbox/TICKET-smoke-test.md << 'EOF'
---
title: "Smoke test hello world"
status: todo
components:
  - infrastructure
created: 2026-05-13
depends_on: []
priority: low
agents:
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---
# Smoke test

## Goal
Add a hello_world() function to a new utils.py.

## Acceptance Criteria
- hello_world() returns "hello, world"
EOF
```

Then run `/build-feature tickets/00_inbox/TICKET-smoke-test.md` and confirm the
supervisor stack drives the ticket through all declared agents.

---

## What to Report to the User

After setup completes, summarise:

1. **Skills_config.json values set:** table of key → value
2. **Values that need manual review:** keys where auto-detection was uncertain
3. **CLAUDE.md:** generated by `build.py` from `templates/CLAUDE.md.template`; remind user to fill in any `<!-- TODO: fill in ... -->` sections
4. **Next step:** `/build-feature <ticket>` to drive the first real ticket

Example summary:

---

## Architecture Doc Scaffolds

After running `build.py`, optionally seed the project's `docs/architecture/` folder
with convention-compliant starter files by passing `--seed-docs`:

```bash
python leafcutter/scripts/build.py --target-dir . --seed-docs
```

What gets seeded (missing-only — existing files are never overwritten):

| File | Purpose |
|------|---------|
| `docs/architecture/README.md` | Folder guide: C4 levels, filename convention, frontmatter quick reference |
| `docs/architecture/FRONTMATTER.md` | Full frontmatter field reference with enum tables |
| `docs/architecture/c1-001-system-context.md` | Starter L1 system-context diagram (edit after seeding) |
| `docs/architecture/adrs/README.md` | ADR folder guide: naming, lifecycle, bidirectional-linking rule |
| `docs/architecture/adrs/ADR-template.md` | Canonical ADR template — copy when authoring a new ADR |

### Opt Out

Do not pass `--seed-docs` to skip seeding entirely. The build still runs all other
phases (agents, skills, hooks). Seeding is purely opt-in.

### Add a New Starter Scaffold

1. Create the file under `leafcutter/templates/docs/architecture/`.
2. Re-run `python leafcutter/scripts/build.py --seed-docs` in the project.
3. Register the new file in `docs/reference/architecture-scaffolds.md`.

For step-by-step guidance, see `docs/how-to/installation/seed-architecture-scaffolds.md`
once it has been seeded into the project.

---

```
Setup complete. Here is what I configured:

| Key                        | Value                                          |
|----------------------------|------------------------------------------------|
| default_branch             | main (detected from git)                       |
| top_level_packages         | [api, collector, live_trader, models] (detected)|
| test_command_live_trader   | poetry run python -m unittest discover ...     |
| test_output_dir            | %TEMP%/myproject-tests/                        |

Manual review recommended for:
- test_command_sql: I could not detect a SQL test suite. Set this if you add one.

Next steps:
1. Open CLAUDE.md (generated by build.py) and fill in any `<!-- TODO: fill in ... -->` sections
2. Run: pre-commit install && pre-commit install --hook-type post-commit
3. Run: /build-feature <your-first-ticket>
```
