# skills_config.json Field Reference

Configuration fields for the leafcutter agent/skill stack. Adopt by copying `config/skills_config.default.json` to `.claude/skills_config.json` and editing values that differ.

## Output Layout

| Field | Type | Default | Valid Values | Description |
|-------|------|---------|-------------|-------------|
| `output_root` | string | `.leafcutter` | any valid folder name | Folder name under target_root where build.py writes all artifacts |
| `shim_strategy` | enum | `auto` | `symlink`, `copy`, `auto` | How canonical tool paths (.claude/, .gemini/) are bridged to output_root. `auto` = symlink with copy fallback on PermissionError |

## Ticket Paths

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tickets_inbox_path` | string | `tickets/00_inbox` | Root folder for standalone ticket files |
| `tickets_inbox_epics_path` | string | `tickets/00_inbox/epics` | Root folder for proposed epics |
| `tickets_todo_path` | string | `tickets/01_todo` | Root folder for in-flight tickets and epics |
| `tickets_done_path` | string | `tickets/99_done` | Root folder for completed tickets |
| `tickets_rejected_path` | string | `tickets/99_rejected` | Root folder for rejected tickets |
| `ticket_lifecycle_path` | string | `tickets/ticket_lifecycle.json` | Path to the ticket_lifecycle.json manifest |

## Testing

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `test_command_live_trader` | string | (project-specific) | Command to run the fast unit test suite |
| `test_command_sql` | string | (project-specific) | Command to run SQL/database integration tests |
| `test_command_single_file_pattern` | string | (project-specific) | Pattern for running a single test file (`<file>` placeholder) |

## Build Behavior

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `default_branch` | string | `main` | Default/main branch for PR targets and merge operations |
| `docs_root` | string | `docs/` | Root directory for project documentation |
| `changelog_folder` | string | `changelogs/` | Folder for per-entry changelog Markdown files |
| `changelog_categories_path` | string | `.claude/changelog_categories.md` | Path to commit categorization rules |
| `precommit_autofix_config_path` | string | `.claude/precommit-autofix.json` | Path to the precommit-autofix routing config |

## Platforms

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `platforms.claude` | boolean | `true` | Generate outputs for Claude Code |
| `platforms.antigravity` | boolean | `true` | Generate outputs for Gemini/Antigravity |
| `platforms.cursor` | boolean | `false` | Generate outputs for Cursor |
| `platforms.copilot` | boolean | `false` | Generate outputs for GitHub Copilot |
| `platforms.cline` | boolean | `false` | Generate outputs for Cline |

## Testing Context

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `testing_context.test_root` | string | `unit_tests/` | Root directory containing all test subdirectories |
| `testing_context.readme_path` | string | `unit_tests/README.md` | Path to the primary test README |
| `testing_context.max_test_duration_seconds` | integer | `5` | Maximum wall-clock duration for auto-running tests |
| `testing_context.manual_test_suffix` | string | `_MANUAL` | Suffix for tests excluded from pre-commit suite |
| `testing_context.naming_pattern` | string | `test_*.py` | Glob pattern that test files must match |
