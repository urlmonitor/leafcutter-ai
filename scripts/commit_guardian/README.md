# Commit Guardian

## What is Commit Guardian?

Commit Guardian is a **portable, project-agnostic pre-commit enforcement package**. It ships as a self-contained directory (`scripts/commit_guardian/`) that plugs into any project's [pre-commit](https://pre-commit.com/) framework. Every hook reads its settings from a single JSON file (`commit_guardian.json`) and delegates execution through a worktree-safe Python resolver (`run_hook.py`), so the package works identically in Git worktrees, CI runners, and developer machines without any per-environment wiring.

**A hook** is a script that pre-commit runs automatically before (or after) you create a commit. Blocking hooks exit with code 1 to abort the commit; advisory hooks print warnings but always exit 0 and let the commit proceed.

This README is intentionally self-contained. It covers every hook, its config surface, and the extension protocol — so a developer landing here directly (or an adopter copying this package to a new project) has everything they need without opening the top-level `docs/` tree.

For installation, `.pre-commit-config.yaml` wiring, and porting steps see `scripts/commit_guardian/INTEGRATION.md` _(forthcoming — will cover one-time `pre-commit install` commands, environment requirements, and a step-by-step porting checklist for adopters)_.

---

## Key Files

| File | Role |
|------|------|
| `run_hook.py` | Worktree-aware Python resolver. All pre-commit entries delegate through this script to find the correct `.venv`. Stdlib-only; any system Python can invoke it. |
| `commit_guardian.json` | Single source of truth for every hook's settings — thresholds, whitelists, patterns, and per-hook overrides. |
| `config.py` | JSON loader that reads `commit_guardian.json` and exposes named constants. All hook scripts import from here. |

---

## Hook Reference Table

Every script present in `scripts/commit_guardian/` that acts as a hook has a row below.

| Script | pre-commit hook id | Kind | What it checks | Primary config key | Deeper doc |
|--------|--------------------|------|----------------|--------------------|------------|
| `check_root_files.py` | `check-root-files` | Blocking | Blocks unauthorized files from the project root directory. | `root_files.allowed_files` / `root_files.allowed_extensions` | — |
| `check_debug_scripts.py` | `check-debug-scripts` | Blocking | Enforces metadata tags (`DEBUG SCRIPT`, `CATEGORY`, `DESCRIPTION`) on scripts under `debugging/scripts/`. | `debug_scripts.required_tags`, `debug_scripts.valid_categories` | — |
| `check_documentation.py` | `check-documentation` | Blocking | Every modified `.py` or `.sql` file must have a `README.md` in its parent directory. New `.sql` files need `Object Name:`, `Goal:`, `Business Context:` in the header; new `.py` files need `MODULE:`, `GOAL:`, `BUSINESS CONTEXT:` in the module docstring. | `documentation.sql_required_fields`, `documentation.python_required_fields` | [docs/how-to/database/create-procedure.md](../../docs/how-to/database/create-procedure.md) |
| `check_infra_docs.py` | `check-infra-docs` | Blocking | Enforces inline comments on high-impact infra settings in `docker-compose*.yml`, `docker/Dockerfile.*`, `init-db.sh`, `.env.example`. | `infra_docs.infra_file_patterns`, `infra_docs.high_impact_keywords` | — |
| `check_doc_frontmatter.py` | `check-doc-frontmatter` | Blocking | Validates YAML frontmatter on staged `docs/*.md` files: required fields, `type`, `status`, `flight_level`, `diagram_type` enums, `components` registry membership, path existence of `related_docs` / `related_code`. Stale `last_updated` is warn-only. | `doc_frontmatter.required_fields`, `doc_frontmatter.allowed_types`, `doc_frontmatter.allowed_statuses` | [docs/FRONTMATTER.md](../../docs/FRONTMATTER.md) |
| `check_doc_links.py` | `check-doc-links` | Advisory (always exits 0) | Validates `DOC_LINKS:` declarations in `.py` and `.sql` files point to existing docs, and checks bidirectional `related_code` back-links in doc frontmatter. Never blocks. | `doc_links.severity`, `doc_links.check_bidirectional` | — |
| `check_complexity.py` | `check-complexity` | Blocking | Blocks Python files where any function/method exceeds the cyclomatic complexity limit. | `complexity.max_score` (default: 15) | — |
| `check_sql_complexity.py` | `check-sql-complexity` | Blocking | Blocks SQL files where keyword-counted structural complexity exceeds the limit. | `sql_complexity.max_score` (default: 65) | — |
| `check_sql_dependencies.py` | `check-sql-dependencies` | Blocking | All staged SQL views and materialized views must declare a `Dependencies:` metadata tag in the header. | _(no config key — tag name is hardcoded)_ | — |
| `check_docstrings.py` | `check-docstrings` | Blocking | Enforces Google-style docstrings (summary, `Args:`, `Returns:`) on all Python functions, methods, and classes. Catches stale param names using `docstring-parser`. | `docstrings.style`, `docstrings.trivial_max_lines`, `docstrings.exempt_dunders` | — |
| `check_file_size.py` | `check-file-size` | Blocking | Blocks new Python (`.py`) and SQL (`.sql`) files that exceed the line-count limit. Modifications to existing large files are exempt (incremental refactor path). | `file_size.line_limits`, `file_size.default_limit` | — |
| `check_folder_density.py` | `check-folder-density` | Blocking | Blocks commits when any folder would exceed the maximum number of non-markdown files, encouraging sub-folder modularity. `__init__.py` and `.md` files are exempt. | `folder_density.max_files_per_folder` (default: 15) | — |
| `check_adr_cross_reference.py` | `check-adr-cross-reference` | Advisory by default; blocking with `--strict` | For staged ADRs, verifies each listed `components` entry has a back-link from its `detail_ref` doc. For staged `detail_ref` docs, checks the reverse direction. | _(no config key — `--strict` flag on hook entry)_ | — |
| `check_structural_change.py` | `check-structural-change` | Blocking | Detects structural additions (new `models/*.py`, new docker-compose service, new top-level package, new SQL procedure namespace, new `live_trader/*.py` module, new collector worker) and requires `docs/components.json` to be staged in the same commit. | _(no config key — signals are hardcoded patterns; see escape hatch below)_ | — |
| `check_components_integrity.py` | `check-components-integrity` | Blocking | Fires only when `docs/components.json` is staged. For each newly-added top-level key, requires a non-empty `detail_ref` pointing to an on-disk doc whose frontmatter includes `flight_level`. | _(no config key)_ | — |
| `check_ticket_signoff_parity.py` | `check-ticket-signoff-parity` | Warn-only by default; blocking with `--enforce` (current config uses `--enforce`) | Validates parity between a ticket's YAML frontmatter `agents:` map and its `## Sign-offs` checklist. Tickets in `done/` subdirectories are auto-enforced regardless of `--enforce`. Also enforces task-section parity (Check #6): a signed-off agent with `requires_ticket_section: true` must have all tasks checked. See [Task-Section Parity Check](#task-section-parity-check-check-6) below. | `ticket_frontmatter.required_fields`, `ticket_frontmatter.tickets_dir` | [docs/architecture/adrs/ADR-010-agent-supervisor-signoff-pattern.md](../../docs/architecture/adrs/ADR-010-agent-supervisor-signoff-pattern.md) |
| `check_alembic_chain.py` | `check-alembic-chain` | Blocking | Fires only when `alembic/versions/*.py` files are staged. Blocks commits that introduce broken `down_revision` chains or duplicate heads. | _(no config key — reads `alembic/versions/` directly)_ | — |
| `check_pytest_style.py` | `check-pytest-style` | Blocking | Rejects top-level `def test_*()` functions in `unit_tests/live_trader/test_*.py` that are not methods of a `unittest.TestCase` subclass (`unittest discover` silently skips them). | _(no config key — target path is hardcoded)_ | — |
| `apply_sql_changes.py` | `apply-sql-changes` | Blocking (local only) | Auto-applies staged SQL files to the local dev database before tests run. Skips automatically when not running locally (no Docker/prod side-effects). | _(reads `DATABASE_URI` from `settings.py` or environment)_ | [docs/how-to/database/create-procedure.md](../../docs/how-to/database/create-procedure.md) |
| `check_sql_test_results.py` | `check-sql-test-results` | Blocking | Reads `.sql_test_results.json` written by the background worker. Exits 0 (skips) when no result file exists; exits 0 and deletes the file when the previous run passed; exits 1 and prints captured output when the previous run failed. | _(no config key — reads `.sql_test_results.json`)_ | — |
| `trigger_sql_tests.py` | `trigger-sql-tests` | Post-commit, always exits 0 | Spawns `run_sql_tests_worker.py` as a detached background process after each commit. Writes the worker PID to `.sql_test.pid`. Never blocks the committing terminal. | _(no config key)_ | — |

---

## Config Schema

All hook behaviour is governed by `commit_guardian.json`. The schema has one top-level key per hook domain. Global keys come first.

### Global

```
excluded_dirs  (array of strings)
```
Directories excluded from ALL hooks unless a hook section provides its own `excluded_dirs` override. Default: `["unit_tests", "alembic", "debugging", "legacy", "tests"]`.

### `file_size`

| Key | Type | Default | Governs |
|-----|------|---------|---------|
| `line_limits` | object | `{".py": 400, ".sql": 600}` | Per-extension hard limits for new files. |
| `default_limit` | integer | `400` | Fallback limit for extensions not in `line_limits`. |
| `checked_extensions` | array | `[".py", ".sql"]` | File extensions that are checked. |

### `complexity`

| Key | Type | Default | Governs |
|-----|------|---------|---------|
| `max_score` | integer | `15` | Maximum allowed cyclomatic complexity per function/method. |
| `excluded_dirs` | array | `["alembic", "legacy"]` | Override for global `excluded_dirs`. |

### `sql_complexity`

| Key | Type | Default | Governs |
|-----|------|---------|---------|
| `max_score` | integer | `65` | Maximum keyword-counted complexity score per SQL file. |
| `excluded_dirs` | array | `["alembic", "legacy"]` | Override for global `excluded_dirs`. |

### `docstrings`

| Key | Type | Default | Governs |
|-----|------|---------|---------|
| `style` | string | `"google"` | Docstring style to enforce. |
| `trivial_max_lines` | integer | `5` | Functions with a body at or below this many lines are exempt. |
| `enforce_type_annotations` | bool | `true` | Whether type annotations are required. |
| `exempt_dunders` | array | _(long list in JSON)_ | Dunder methods that do not require docstrings. |

### `documentation`

| Key | Type | Governs |
|-----|------|---------|
| `sql_required_fields` | array | Required tags in new SQL file headers (`Object Name:`, `Goal:`, etc.). |
| `python_required_fields` | array | Required tags in new Python module docstrings (`MODULE:`, `GOAL:`, etc.). |

### `root_files`

| Key | Type | Governs |
|-----|------|---------|
| `allowed_files` | array | Exact filenames permitted in the project root. |
| `allowed_extensions` | array | File extensions always permitted in the project root (e.g. `.md`, `.json`). |

### `folder_density`

| Key | Type | Default | Governs |
|-----|------|---------|---------|
| `max_files_per_folder` | integer | `15` | Maximum non-markdown, non-`__init__.py` files per directory. |
| `excluded_dirs` | array | `["__pycache__", ".git", …]` | Directories skipped during density counting. |
| `exempt_extensions` | array | `[".md"]` | File extensions that do not count toward the limit. |
| `exempt_filenames` | array | `["__init__.py"]` | Filenames that do not count toward the limit. |

### `debug_scripts`

| Key | Type | Governs |
|-----|------|---------|
| `valid_categories` | array | Allowed values for the `CATEGORY:` tag. |
| `required_tags` | array | Tags that must appear in every debug script header. |
| `context_tags` | array | Optional context tags recognised by the validator. |
| `exempt_names` / `exempt_dirs` | array | Files/directories skipped entirely. |

### `infra_docs`

| Key | Type | Governs |
|-----|------|---------|
| `infra_file_patterns` | array of regex | Which files are considered infra files. |
| `high_impact_keywords` | array of regex | Patterns in infra files that require an inline comment. |

### `doc_frontmatter`

| Key | Type | Governs |
|-----|------|---------|
| `required_fields` | object (glob → array) | Per-glob required frontmatter fields. `docs/architecture/**` requires `flight_level` in addition to the base set. |
| `allowed_types` | array | Valid `type:` values (`tutorial`, `how-to`, `reference`, `explanation`, `adr`, `cross-cutting`). |
| `allowed_statuses` | array | Valid `status:` values. |
| `flight_level_values` | array | Valid `flight_level:` values (`L1-Context`, `L2-Container`, `L3-Component`, `L4-Code`). |
| `diagram_type_values` | array | Valid `diagram_type:` values. |
| `components_registry` | string | Path to `docs/components.json` for membership validation. |
| `docs_dir` | string | Root docs directory (default: `docs`). |

### `doc_links`

| Key | Type | Governs |
|-----|------|---------|
| `severity` | string | Always `"warn"` — this hook never blocks. |
| `check_bidirectional` | bool | Whether to verify `related_code` back-links in doc frontmatter. |
| `check_mermaid_architecture_link` | bool | Whether files with ARCHITECTURE diagrams are checked for a `DOC_LINKS:` pointer. |

### `ticket_frontmatter`

| Key | Type | Governs |
|-----|------|---------|
| `required_fields` | array | Fields every ticket frontmatter must contain (`title`, `status`, `components`, `created`, `depends_on`). |
| `allowed_types` | array | Valid ticket `type:` values. |
| `allowed_statuses` | array | Valid ticket `status:` values. |
| `tickets_dir` | string | Root tickets directory (default: `tickets`). |

---

## Task-Section Parity Check (Check #6)

`check_ticket_signoff_parity.py` enforces six parity invariants. Checks #1–#5 validate the `agents:` frontmatter-to-`## Sign-offs` surface (enum membership, timestamp formats, orphan rows). **Check #6** is the task-section parity check introduced by EPIC-AgentRegistryAsSourceOfTruth.

### What Check #6 validates

For every agent whose entry in the ticket's `agents:` map is `signed_off` **and** whose registry entry has `requires_ticket_section: true`, the check scans the `## Implementation Tasks` body for a `### <agent-name>` sub-section and verifies that every task checkbox in that section is checked (`- [x]`).

Two distinct outcomes are possible:

| Situation | Behaviour |
|-----------|-----------|
| The `### <agent-name>` sub-section is **absent** | **Warn-only** — the guard prints a reminder and exits 0. Absent sections are accepted for backward compatibility with tickets authored before this convention was introduced. |
| The `### <agent-name>` sub-section is **present** but contains **unchecked items** (`- [ ]`) | **Hard error** — the guard exits 1 and blocks the commit. A signed-off agent must not leave tasks incomplete in its own section. |

### The `requires_ticket_section` registry field

The gate is driven by `leafcutter/config/agent_registry.json`. Each agent entry may carry:

```json
{
  "id": "python-coder",
  "is_ticket_phase": true,
  "requires_ticket_section": true
}
```

- `requires_ticket_section: true` — the agent is expected to complete a task section when one is present. Check #6 applies.
- `requires_ticket_section: false` (or field absent) — the agent does not require a task section. Check #6 is skipped for this agent. **Backward compatibility**: the field defaults to `false` when absent, so existing agents without the field are never affected.

Current agents with `requires_ticket_section: true`:

| Agent | Role |
|-------|------|
| `adr-author` | ADR authoring |
| `architecture-diagram-author` | C4 diagram authoring |
| `python-coder` | Python implementation |
| `sql-coder` | SQL implementation |
| `test-writer` | Test suite authoring |
| `documentation-expert` | Documentation updates |

### Interaction with the handoff workflow

When `python-coder` hands off to `test-writer` using `(status: handoff)`, the `### test-writer` task section in the ticket may contain unchecked items — those are `test-writer`'s tasks, not `python-coder`'s. Check #6 only scans the section that belongs to the agent that just signed off. It never validates other agents' sections.

This means:

- `python-coder` signing off: Check #6 validates `### python-coder` only. `### test-writer` items may remain unchecked.
- `test-writer` signing off: Check #6 validates `### test-writer` only.

### Developer experience when the check fires

If Check #6 fires on your commit, the guard output will identify the agent name and list the unchecked tasks. The resolution is to either:

1. Complete the remaining tasks and re-stage the ticket file, OR
2. If the task genuinely cannot be completed in this commit (dependency not met), emit `(status: blocker)` via the `signoff` skill and let the supervisor adjudicate — do NOT manually check off incomplete tasks.

---

## How to Add a New Hook

Follow this sequence to ship a new hook into Commit Guardian. All four steps must be completed in the same commit.

### Step 1 — Create the script

Place the script in `scripts/commit_guardian/` following the naming convention:

- `check_<what>.py` — validates something and blocks or warns.
- `apply_<what>.py` — performs a side-effect (database write, file generation) as part of the pre-commit flow.
- `trigger_<what>.py` — spawns a background process (post-commit only).

The script must:
1. Import settings from `config.py` (not directly from `commit_guardian.json`).
2. Use `sys.exit(0)` for pass, `sys.exit(1)` for blocking failure.
3. Include a module docstring with `MODULE:`, `GOAL:`, `BUSINESS CONTEXT:` fields.
4. Work correctly when invoked via `run_hook.py` (see Critical Context below).

### Step 2 — Add a config block to `commit_guardian.json`

Add a top-level key named after your domain (e.g. `my_check`). Document every key with an inline `_comment` field:

```json
"my_check": {
    "_comment": "check_my_check.py — description of what this governs",
    "threshold": 10,
    "excluded_dirs": ["alembic", "legacy"]
}
```

### Step 3 — Expose constants in `config.py`

Read your new section from the JSON and define named constants. Follow the existing pattern — one constant per leaf value, `UPPER_SNAKE_CASE`:

```python
MY_CHECK_THRESHOLD     = _cfg["my_check"]["threshold"]
MY_CHECK_EXCLUDED_DIRS = _cfg["my_check"]["excluded_dirs"]
```

### Step 4 — Register in `.pre-commit-config.yaml`

Add a new entry in the `hooks:` list under the `local` repo. Use `run_hook.py` as the entry:

```yaml
- id: check-my-check
  name: Check My Custom Rule
  entry: python scripts/commit_guardian/run_hook.py scripts/commit_guardian/check_my_check.py
  language: system
  types: [python]          # or files: regex, or omit for always_run
  stages: [pre-commit]
  pass_filenames: false
```

Append a `DECISION HISTORY` comment at the bottom of `.pre-commit-config.yaml` recording the date, author, and ticket that added the hook.

---

## Bypass / Debug Recipes

### Universal bypass (all hooks)

The `pre-commit` framework provides a `SKIP` environment variable that accepts a comma-separated list of hook IDs:

```bash
SKIP=check-complexity,check-file-size git commit -m "msg"
```

This skips only the listed hooks. All others still run. Do not use `--no-verify` unless absolutely necessary — it bypasses every hook silently.

### Hook-specific escape hatches

| Hook | Escape hatch | How to use |
|------|-------------|------------|
| `check-structural-change` | `[NO-ARCH-UPDATE]` in commit message | Add the literal string anywhere in the commit message body. Intended for pure refactors or vendored code that do not change the component surface. |
| `check-adr-cross-reference` | Default is warn-only; add `--strict` to block | To flip from warn to block: add `--strict` to the hook's `entry:` line in `.pre-commit-config.yaml`. |
| `check-doc-frontmatter` | `--file docs/some_file.md` flag | Run the script directly to check a single file without touching git staging: `python scripts/commit_guardian/check_doc_frontmatter.py --file docs/some_file.md` |
| `check-doc-links` | Always exits 0 — advisory only | No bypass needed; it never blocks. |
| `check-ticket-signoff-parity` | Remove `--enforce` from hook entry | Without `--enforce`, violations print warnings but do not block. Tickets in `done/` are auto-enforced regardless. |
| `check-alembic-chain` | Only fires on `alembic/versions/*.py` | The hook only runs when migration files are staged; no bypass needed for unrelated commits. |
| `apply-sql-changes` | Skips automatically when not running locally | Detects Docker/prod environment and exits 0. No manual bypass needed in CI. |

### Run a single hook manually

To run any hook against the currently staged files without committing:

```bash
pre-commit run check-complexity
pre-commit run check-doc-frontmatter
```

To run a single hook against all files (not just staged):

```bash
pre-commit run check-complexity --all-files
```

To run a hook against a specific file directly (bypassing git staging):

```bash
python scripts/commit_guardian/check_doc_frontmatter.py --file docs/myfile.md
python scripts/commit_guardian/check_doc_links.py --file live_trader/my_module.py
```

### Output logs

All hooks print to stdout/stderr. Pre-commit captures this output and displays it when a hook fails. There is no persistent log file — output appears in the terminal at commit time and is not retained.

To inspect output from the most recent pre-commit run in verbose mode:

```bash
pre-commit run --verbose
```

The async SQL test pipeline is the one exception: `run_sql_tests_worker.py` writes its captured pytest output into `.sql_test_results.json`, which `check-sql-test-results` then prints and deletes on the next commit.

---

## Async SQL Tests

SQL tests (`unit_tests/sql_functions`) require a live Docker database and take 30+ seconds. Running them synchronously inside pre-commit would block every commit. Instead, the project uses a three-script async pipeline:

### Three-Script Pipeline

| Script | Stage | Role |
|--------|-------|------|
| `trigger_sql_tests.py` | post-commit | Spawns `run_sql_tests_worker.py` as a detached background process; writes the child PID to `.sql_test.pid`; exits immediately. |
| `run_sql_tests_worker.py` | background (no hook) | Runs `pytest unit_tests/sql_functions -v --tb=short`, captures stdout+stderr, writes the result atomically to `.sql_test_results.json`, then removes `.sql_test.pid`. |
| `check_sql_test_results.py` | pre-commit | Reads `.sql_test_results.json`; exits 0 (skip) if the file is absent; exits 0 and deletes the file if the previous run passed; exits 1 (blocking the commit) and prints the captured output if the previous run failed. |

### Ephemeral Files

Both of the following files are git-ignored (see `.gitignore`):
- **`.sql_test_results.json`** — written by `run_sql_tests_worker.py` after each background run; read and deleted by `check_sql_test_results.py` on the next pre-commit.
- **`.sql_test.pid`** — written by `trigger_sql_tests.py` and deleted by `run_sql_tests_worker.py` on completion. Its sole purpose is human diagnostics (e.g. `kill $(cat .sql_test.pid)` to abort a slow run).

### One-Time Local Setup

`pre-commit install` only registers the `pre-commit` stage. The `post-commit` hook that triggers the background SQL run must be installed explicitly — once per clone and once per worktree:

```bash
pre-commit install --hook-type post-commit
```

Without this step, `trigger-sql-tests` will never fire, no `.sql_test_results.json` will be written, and `check-sql-test-results` will always skip (it short-circuits on a missing result file). The pre-commit stage will silently appear to pass while the async pipeline is effectively disabled.

### Manual Validation

To verify the pipeline end-to-end:
1. Introduce a deliberate failure in a SQL test (e.g. `assert False`).
2. Make a commit — `trigger-sql-tests` fires and prints the background PID.
3. Wait a few seconds for the worker to finish, then attempt another commit.
4. The `check-sql-test-results` hook should fail, printing the pytest output and blocking the commit.
5. Revert the deliberate failure and commit again — the next pre-commit check should pass (`.sql_test_results.json` was deleted by step 4, so the check skips until the next background run completes).

---

## Critical Context

- **Git Worktree Support**: All hooks run through `run_hook.py`, which detects git worktrees and uses the main worktree's `.venv` Python. This is necessary because Poetry's `virtualenvs.in-project = true` creates an empty `.venv` per directory, causing `ModuleNotFoundError` for `docstring-parser`, `psycopg2`, etc. in worktrees. No `--no-verify` is needed for worktree commits.
- **New Files vs. Modified Files**: The file size check targets only newly-added files. Modifications to existing large files are exempt to allow for incremental refactoring.
- **Windows Compatibility**: File handling in this module is Windows-compatible (temporary file locking handled via stdlib).
- **Pre-commit Integration**: Scripts are intended to be run via `pre-commit`. They are configured in `.pre-commit-config.yaml` at the project root.

---

## Maintenance Instructions

- **Adjusting Settings**: Edit `commit_guardian.json`. All thresholds, whitelists, excluded dirs, and patterns live there.
- **Porting to Another Project**: Copy the `scripts/commit_guardian/` folder. Edit `commit_guardian.json` to match the new project's structure. Update `root_files.allowed_files`, `excluded_dirs`, and any hardcoded path patterns (e.g. `check_pytest_style.py` targets `unit_tests/live_trader/` by default). See `scripts/commit_guardian/INTEGRATION.md` _(forthcoming)_ for the full porting checklist.
- **Testing the hooks**: Run `poetry run python -m pytest unit_tests/commit_guardian/ -v`.
- **Architecture reference**: For the full design rationale behind each hook, see the `docs/` tree — the README deliberately references without duplicating that content.
