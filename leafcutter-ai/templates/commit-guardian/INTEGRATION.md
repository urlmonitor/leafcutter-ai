# Commit Guardian + Doc Compliance — Integration Guide

> **Audience:** A developer setting up a fresh project (e.g. CubeCoder or any new
> Bybit-Trader-style repo) who wants commit-time quality gates without tribal knowledge.
> Following this guide end-to-end takes under an hour and leaves you with a working
> pre-commit pipeline.

---

## Prerequisites

Before you start, confirm the following are in place on your development machine:

| Requirement | Notes |
|-------------|-------|
| **Python ≥ 3.11** | The hooks are Python-based and use 3.11+ syntax |
| **Poetry** | Used for dependency management; install via `pip install poetry` |
| **pre-commit** | Install via `pip install pre-commit` or `pipx install pre-commit` |
| **Git repo with ≥ 1 commit** | `pre-commit install` requires at least one commit |
| **Empty or seeded `docs/` tree** | The doc-compliance scanner writes into `docs/`; the directory must exist |

**Windows-specific notes:**

- `!` inside double-quoted bash strings triggers history expansion in Git Bash — use
  heredocs (`<<'EOSQL'`) or single quotes when passing SQL or JSON on stdin.
- `?` is a glob character in bash — use heredocs for JSONB `?` operator queries.
- `run_hook.py` (see §Step 3) auto-detects git worktrees and resolves the correct `.venv`
  Python; you do **not** need `--no-verify` for worktree commits on Windows.

---

## Step 1 — Copy the Package

Copy the following directories and files from this project into your target repo,
preserving the directory structure:

```
scripts/
  commit_guardian/      ← entire directory (all files)
  doc_compliance/       ← entire directory (includes BOOTSTRAP_GUIDE.md)
```

Minimal copy list:

```bash
# From the root of your source (this) repo, run:
cp -r scripts/commit_guardian  <target-repo>/scripts/
cp -r scripts/doc_compliance   <target-repo>/scripts/
```

**Key files you are copying:**

| File | Purpose |
|------|---------|
| `scripts/commit_guardian/run_hook.py` | Worktree-aware venv resolver — all pre-commit entries delegate through this |
| `scripts/commit_guardian/commit_guardian.json` | Central config: thresholds, whitelists, excluded dirs (edit for your project) |
| `scripts/commit_guardian/config.py` | Loads `commit_guardian.json` and exposes named constants to all checkers |
| `scripts/commit_guardian/check_*.py` | Individual hook scripts (one responsibility each) |
| `scripts/doc_compliance/BOOTSTRAP_GUIDE.md` | Step-by-step guide for creating `docs/components.json` and `docs/doc_compliance.json` |

**Starter `.pre-commit-config.yaml` snippet** (wire the core hooks):

```yaml
repos:
  - repo: local
    hooks:
      - id: check-root-files
        name: "Guard: root file whitelist"
        entry: python scripts/commit_guardian/run_hook.py check_root_files
        language: system
        pass_filenames: false
        always_run: true

      - id: check-complexity
        name: "Guard: cyclomatic complexity"
        entry: python scripts/commit_guardian/run_hook.py check_complexity
        language: system
        types: [python]

      - id: check-documentation
        name: "Guard: module header enforcement"
        entry: python scripts/commit_guardian/run_hook.py check_documentation
        language: system
        types: [python, sql]

      - id: check-docstrings
        name: "Guard: Google-style docstrings"
        entry: python scripts/commit_guardian/run_hook.py check_docstrings
        language: system
        types: [python]

      - id: run-unit-tests
        name: "Guard: live-trader unit tests"
        entry: python scripts/commit_guardian/run_hook.py run_tests
        language: system
        pass_filenames: false
        types: [python]
```

> For the full hook list, hook IDs, and their config keys, see
> [`scripts/commit_guardian/README.md`](README.md).

---

## Step 2 — Run Scanner `--init`

EPIC-DocTraceability ticket 14 added an `--init` mode to the doc-compliance scanner.
This mode bootstraps `docs/components.json` and frontmatter scaffolding for a fresh repo,
so you don't have to write those files by hand from scratch.

**Invocation:**

```bash
poetry run python scripts/doc_compliance/scanner.py --init
```

What it generates:

- A skeleton `docs/components.json` populated from the patterns in `docs/doc_compliance.json`
- YAML frontmatter stubs for existing `.md` files that lack them

**Before running `--init`**, you need `docs/doc_compliance.json` — the scanner's
permanent configuration that defines scan paths, component source patterns, and
ignore lists. Creating that file is the topic of
[`scripts/doc_compliance/BOOTSTRAP_GUIDE.md`](../doc_compliance/BOOTSTRAP_GUIDE.md),
which walks you through every field in order.

**Recommended order:**

1. Follow `BOOTSTRAP_GUIDE.md` Phase 1 → create `docs/doc_compliance.json`
2. Follow `BOOTSTRAP_GUIDE.md` Phase 2 → flesh out `docs/components.json`
3. Run `--init` to fill any remaining gaps or regenerate from the config

---

## Step 3 — Wire Pre-commit

**Install the hooks:**

```bash
# Install the pre-commit stage hook (runs before every git commit)
pre-commit install

# Install the post-commit stage hook (required for the async SQL test pipeline)
pre-commit install --hook-type post-commit
```

**Verify all hooks can see your staged files:**

```bash
pre-commit run --all-files
```

This runs every hook against every tracked file. Expect some warnings on a fresh
repo where documentation headers haven't been written yet; address them incrementally.

**How `run_hook.py` works:**

All pre-commit entries delegate to `scripts/commit_guardian/run_hook.py`, which:

1. Detects whether the current working directory is a git worktree or the main clone
2. Resolves the correct `.venv` Python (always the main clone's `.venv`, even inside
   a worktree where Poetry would otherwise create an empty per-directory venv)
3. Re-invokes the target hook script under that Python interpreter

This means `ModuleNotFoundError` for `docstring-parser`, `psycopg2`, and similar
packages is eliminated for worktree commits without any `--no-verify` bypass.

> Full `run_hook.py` internals are documented in
> [`scripts/commit_guardian/README.md`](README.md).

---

## Step 4 — Blocking vs Advisory Hooks

`commit_guardian.json` is the single source of truth for every hook's behaviour.
Each hook section has a `"blocking"` key (or inherits the default) that controls
whether the hook exits with code 1 (blocking the commit) or code 0 with a warning
(advisory).

**Suggested starting configuration for a fresh repo:**

| Hook | Recommended mode | Rationale |
|------|-----------------|-----------|
| `check-file-size` | **Blocking** | Prevents runaway files from day one |
| `check-complexity` | **Blocking** | Cyclomatic complexity > 15 is an objective signal |
| `check-root-files` | **Blocking** | Root pollution is hard to undo |
| `check-doc-links` | **Advisory** | Doc graph is empty early; let it warn |
| `check-documentation` | **Advisory** | Teams adopt headers incrementally |
| `check-docstrings` | **Advisory** | Retrofit takes time; advisory prevents stalls |

**Example `commit_guardian.json` excerpt:**

```json
{
  "file_size": {
    "line_limits": { ".py": 400, ".sql": 600 },
    "default_limit": 400,
    "checked_extensions": [".py", ".sql"],
    "blocking": true
  },
  "complexity": {
    "max_score": 15,
    "excluded_dirs": ["alembic", "legacy"],
    "blocking": true
  },
  "doc_links": {
    "blocking": false
  }
}
```

**Project-specific values to adjust:**

- `"excluded_dirs"` — list directories that are vendor/generated code (e.g. `alembic/`, `legacy/`)
- `"line_limits"` — tune to your team's file-size norms
- `"allowed_files"` under `root_files` — whitelist root files specific to your repo

> Every key that `config.py` reads from `commit_guardian.json` is documented in
> [`scripts/commit_guardian/README.md`](README.md).

---

## Step 5 — Smoke Test

Run this quick end-to-end verification after completing Steps 1–4.

**Trigger a file-size violation:**

```bash
# Create a throwaway Python file that exceeds the default 400-line limit
python -c "print('\n'.join(['# line ' + str(i) for i in range(1, 450)]))" \
  > scripts/smoke_test_oversized.py

git add scripts/smoke_test_oversized.py
git commit -m "smoke: trigger file-size hook"
```

**Expected output:**

```
Guard: root file whitelist..................................................Passed
Guard: cyclomatic complexity................................................Passed
Guard: file size check......................................................Failed
- hook id: check-file-size
- exit code: 1

scripts/smoke_test_oversized.py: 449 lines exceeds limit of 400 for .py files.
```

**Reading the block message:**

- The hook ID (`check-file-size`) maps to the section key `file_size` in `commit_guardian.json`
- The threshold that fired is `line_limits[".py"]` — change it there if the default is too tight

**Clean up:**

```bash
git restore --staged scripts/smoke_test_oversized.py
rm scripts/smoke_test_oversized.py
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'docstring_parser'` (or `psycopg2`)

**Cause:** Pre-commit is invoking the hook with a Python that doesn't have project
dependencies installed — typically because you're inside a git worktree and Poetry
created an empty per-directory `.venv`.

**Fix:** This should not happen if `run_hook.py` is correctly wired as the `entry`
point for every hook. Verify that your `.pre-commit-config.yaml` entries all read:

```yaml
entry: python scripts/commit_guardian/run_hook.py <hook_module>
```

and NOT:

```yaml
entry: python scripts/commit_guardian/check_docstrings.py
```

If the error persists, confirm the main clone's `.venv` was created:

```bash
# From the main clone root (not a worktree):
poetry install
ls .venv/bin/python   # Linux/Mac
ls .venv/Scripts/python.exe   # Windows
```

### Hook not firing

**Cause 1:** `pre-commit install` was not run, or was run in the wrong directory.

```bash
# From the repo root:
pre-commit install
```

**Cause 2:** The hook `id` in `.pre-commit-config.yaml` does not match the `id` that
`run_hook.py` expects. Check [`scripts/commit_guardian/README.md`](README.md) for the
canonical hook ID list.

### `commit_guardian.json` key not found

`config.py` reads keys by name from `commit_guardian.json`. If a hook throws a
`KeyError`, the key name in `config.py` does not match what's in your JSON.

**Fix:** Open `config.py` and locate the `config[...]` access that's failing. Add the
missing key to `commit_guardian.json` (copy the block from this project's config as a
template).

### SQL tests blocking commits unexpectedly

The SQL test pipeline is intentionally asynchronous:

1. **Post-commit** (`trigger-sql-tests`): spawns `run_sql_tests_worker.py` in the
   background and exits immediately — the commit goes through.
2. **Background**: `run_sql_tests_worker.py` runs `pytest unit_tests/sql_functions -v`
   and writes the result to `.sql_test_results.json`.
3. **Next pre-commit** (`check-sql-test-results`): reads `.sql_test_results.json`;
   blocks the *next* commit if the previous SQL run failed.

If you see a block from `check-sql-test-results`, the previous background run failed.
Read the captured output in `.sql_test_results.json` to diagnose. Delete the file to
unblock if you've already fixed the underlying SQL issue and confirmed a clean run
manually.

**Post-commit hook missing:**

```bash
pre-commit install --hook-type post-commit
```

Without this, `trigger-sql-tests` never fires and `.sql_test_results.json` is never
written, so `check-sql-test-results` always exits 0 (skip). That's safe — but it
means SQL test failures won't surface at commit time.

---

## Living-Elsewhere Callouts

This section is the **portability map** for adopters. It separates what you must
customise from what is generic and can be carried over unchanged.

### Fully generic (copy as-is, no edits needed)

| Item | Why it's generic |
|------|-----------------|
| `scripts/commit_guardian/run_hook.py` | Pure stdlib; worktree detection is path-based |
| `scripts/commit_guardian/config.py` | JSON loader; key names follow the JSON schema |
| `scripts/commit_guardian/check_*.py` | All thresholds are read from `commit_guardian.json` |
| `scripts/doc_compliance/` (all scripts) | Scanner logic is project-agnostic |
| The async SQL test pipeline scripts | Pipeline wiring is generic; only the pytest path matters |

### Project-specific (must customise)

| Item | What to change |
|------|---------------|
| `scripts/commit_guardian/commit_guardian.json` | Thresholds (`line_limits`, `max_score`), `excluded_dirs`, `allowed_files` (root whitelist), `allowed_extensions` |
| `docs/components.json` | Your project's component registry — completely project-specific |
| `docs/doc_compliance.json` | `scan_paths`, `component_sources`, `ignore` lists — reflect your directory layout |
| `.pre-commit-config.yaml` | Which hooks to enable and in which stages |
| `commit_guardian.json` `"blocking"` flags | Which hooks are gates vs warnings — set per team maturity |

**Rule of thumb:** if a value is a number or a directory name, it belongs in
`commit_guardian.json`. If the value is structural (what to scan, what's a
component), it belongs in `docs/doc_compliance.json` or `docs/components.json`.
The hook scripts themselves never embed thresholds — everything flows through config.

---

## See Also

| Document | Purpose |
|----------|---------|
| [`scripts/commit_guardian/README.md`](README.md) | Full hook reference: every hook ID, its config key, accepted values, and example output. Internal reference for developers working on the hooks themselves. |
| [`scripts/doc_compliance/BOOTSTRAP_GUIDE.md`](../doc_compliance/BOOTSTRAP_GUIDE.md) | Step-by-step guide for creating `docs/components.json` and `docs/doc_compliance.json` from scratch. Start here before running `--init`. |
| EPIC-DocTraceability ticket 14 | Origin of the `--init` scanner mode (`python scripts/doc_compliance/scanner.py --init`). Adds boilerplate frontmatter and a skeleton `docs/components.json` for fresh repos. |
