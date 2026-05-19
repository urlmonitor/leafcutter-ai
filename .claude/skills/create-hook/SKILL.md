---
allowed-tools: Read, Edit, Write, Bash(git add *), Bash(python *)
description: 'Scaffold a new pre-commit hook fully embedded in the leafcutter package.
  A single invocation creates the hook script template, registers the hook in commit_guardian.json
  (config key + hooks_manifest entry), and adds a row to the hook documentation index.
  Invoked by workflow-architect.

  '
name: create-hook
---

# create-hook

Scaffold a new pre-commit hook completely and atomically. No partial installs.

## Inputs

The caller must supply:

| Field | Required | Description |
|-------|----------|-------------|
| `hook_name` | yes | Python-identifier name, e.g. `check_my_rule` |
| `hook_id` | yes | Kebab-case YAML id, e.g. `check-my-rule` |
| `hook_display_name` | yes | Human-readable name for the YAML `name:` field |
| `hook_description` | yes | One-sentence description of what the hook enforces |
| `hook_files_pattern` | no | `files:` regex (omit for always-run hooks) |
| `hook_types` | no | `types:` list (e.g. `["python"]`; omit if no type filter) |
| `hook_stages` | no | Stages list (default: `["pre-commit"]`) |
| `config_section_key` | yes | Top-level key in commit_guardian.json for this hook's config |
| `config_defaults` | yes | Dict of default config values for the new section |
| `pass_filenames` | no | Boolean (default false) |

## Step 1 — Idempotency check

Before writing anything:

1. Confirm `leafcutter/templates/commit-guardian/<hook_name>.py` does NOT exist.
   If it does, stop with: "Hook `<hook_name>` already exists at that path. Delete it first if you intend to replace it."
2. Confirm `commit_guardian.json` does not already have a `config_section_key` matching `config_section_key`.
   If it does, stop with: "Config section `<config_section_key>` already exists in commit_guardian.json."

## Step 2 — Write the hook script template

Create `leafcutter/templates/commit-guardian/<hook_name>.py` with this exact structure:

```python
"""
MODULE: <hook_name>.py
GOAL: Pre-commit hook — <hook_description>.
BUSINESS CONTEXT: <one sentence on why this matters>.
ARCHITECTURE: Reads staged files from git, applies <rule>, exits 1 when violations found.

# DECISION HISTORY
# - YYYY-MM-DD HH:MM [Author]: Initial implementation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _get_staged_files() -> list[Path]:
    """Return a list of staged files from git diff --cached.

    Returns:
        List of Path objects for currently staged files.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRT"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [
        Path(line)
        for line in result.stdout.splitlines()
        if line.strip() and Path(line.strip()).exists()
    ]


def main() -> int:
    """Pre-commit hook entry point.

    Returns:
        Exit code: 0 = clean, 1 = violations found (blocks commit).
    """
    staged = _get_staged_files()
    if not staged:
        return 0

    violations: list[str] = []
    for path in staged:
        # TODO: implement check logic for <hook_name>
        pass

    if not violations:
        return 0

    print(f"[<hook_name>] VIOLATIONS FOUND — commit blocked\n")
    for v in violations:
        print(f"  {v}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

Substitute `<hook_name>`, `<hook_description>`, and `<rule>` with the actual values.

Also copy this template to `scripts/commit_guardian/<hook_name>.py` in the target project (the live hook location that pre-commit executes). Both files must be created.

## Step 3 — Update commit_guardian.json

Two locations within `leafcutter/templates/commit-guardian/commit_guardian.json` (and the live copy at `scripts/commit_guardian/commit_guardian.json`):

### 3a. Add a config section for hook settings

Insert a new top-level key `config_section_key` after the existing sections:

```json
"<config_section_key>": {
    "_comment": "<hook_display_name> — <hook_description>",
    <config_defaults as key-value pairs>
}
```

### 3b. Add a hooks_manifest entry

Append to `hooks_manifest.hooks`:

```json
{
    "id": "<hook_id>",
    "name": "<hook_display_name>",
    "entry": "python scripts/commit_guardian/run_hook.py scripts/commit_guardian/<hook_name>.py",
    "language": "system",
    <"files": "<hook_files_pattern>",  if provided>
    <"types": [<hook_types>],  if provided>
    "stages": [<hook_stages, default ["pre-commit"]>],
    "pass_filenames": <pass_filenames, default false>
}
```

## Step 4 — Update the hook documentation index

If `leafcutter/README.md` has a "Commit-Guardian Hooks" table, add a row:

```
| `<hook_name>.py` | <hook_description> |
```

Anchor on an adjacent row — never use Write on the README. Use Edit.

## Step 5 — Register config constants in config.py

In `leafcutter/templates/commit-guardian/config.py` and the live `scripts/commit_guardian/config.py`:

1. Add a new `# ---------------------------------------------------------------------------` section
2. Add a constant for each key in `config_defaults`:
   ```python
   # ---------------------------------------------------------------------------
   # <hook_name>
   # ---------------------------------------------------------------------------
   <CONST_NAME>: <type> = _get("<config_section_key>", "<key>", <default>)
   ```
3. Append a DECISION HISTORY entry: `# - YYYY-MM-DD HH:MM [Author]: Added <CONST_NAME> constant for <hook_name>.`

### Step 5a — Verify ALL `from config import` names exist (mandatory)

Before declaring this step complete, scan the hook's import statement:

```bash
grep -E "^from config import" leafcutter/templates/commit-guardian/<hook_name>.py
```

For every name on the right-hand side, confirm a matching constant exists in
both copies of `config.py` (the template and the live one). A missing constant
causes `ImportError` at startup in any consumer project that builds from the
template — the exact failure mode that produced unplanned blockers during
EPIC-WorkflowArchitect (T09, hooks `check_doc_length` and `check_structural_change`).

This check is mandatory whether the hook is being **scaffolded fresh** (this
skill's normal flow) or being **migrated** from a project-local
`scripts/commit_guardian/` location into the package template. In the migration
case, the imported constants may exist in the live `config.py` but be missing
from the template `config.py` — sync both.

## Step 6 — Rebuild .pre-commit-config.yaml

Run `build.py --target-dir . --force` from the project root to regenerate `.pre-commit-config.yaml` with the new hook entry. Verify the new `hook_id` appears in the generated file.

## Step 7 — Verify

1. `build.py --validate-only` must pass (no errors).
2. Confirm the new hook appears in `.pre-commit-config.yaml`.
3. Confirm `leafcutter/templates/commit-guardian/<hook_name>.py` exists.
4. Confirm the new section exists in both `commit_guardian.json` files.

## Invariants

- NEVER overwrite an existing hook script (idempotency check in Step 1).
- ALWAYS update BOTH the template copy and the live copy of `commit_guardian.json` and `config.py`.
- ALWAYS run `build.py --force` after editing templates so the generated output stays in sync.
- DECISION HISTORY entries must follow the format: `# - YYYY-MM-DD HH:MM [Author]: <description>.`
