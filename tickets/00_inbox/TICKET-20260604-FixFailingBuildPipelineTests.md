---
title: "Fix three failing build-pipeline test suites"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - config/skill_registry.json
  - scripts/build_helpers.py
  - scripts/build_phases.py
  - tests/test_install_hooks.py
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Fix three failing build-pipeline test suites

## Actor / Goal

In order to keep the CI test suite green and prevent regressions going undetected,
we need to fix four failing test cases across three test files so that the full
test run passes without modification to the assertions.

## Context

Three independent defects were discovered when running the test suite. They are
grouped in a single ticket because they are all small, isolated fixes in the
build pipeline and have no inter-dependencies.

### Failure 1 — `tests/test_skill_registry.py::TestSkillRegistryBidirectional::test_no_orphaned_directories`

The `registry_validator.validate_skill_registry()` function compares the set of
directory names under `templates/skills/` against the `id` field of every entry
in `config/skill_registry.json`. Three skill directories exist on disk but have
no corresponding registry entry:

- `templates/skills/debug/`
- `templates/skills/feedback-analysis/`
- `templates/skills/feedback-review/`

The test asserts `orphaned_dirs == []` and fails with:

```
AssertionError: ['debug', 'feedback-analysis', 'feedback-review'] != []
```

**Fix**: add three entries to `config/skill_registry.json` under the `skills`
array. Each entry needs `id`, `name`, `portable`, `domain`, `template_path`,
`dependencies`, and an optional `description` (sourced from the SKILL.md
frontmatter of each skill).

Skill descriptions (from SKILL.md frontmatter `description` field):

- **debug**: Multi-angle debugging workflow. Spawns three parallel investigative
  agents (database, backend, frontend/docs) to diagnose an issue from different
  perspectives, synthesizes findings, creates a fix ticket via create-ticket agent,
  and builds it via build-feature. Asks the user for clarification when
  investigators are uncertain.
- **feedback-analysis**: Read-side analysis pipeline for the Central Feedback
  Collection System. Provides trend_report.py — an orchestrator that calls
  aggregate.py and list_tags.py, groups results by category, runs trend detection,
  and produces a prioritized report structure. Use when an operator wants an
  on-demand "inbox triage" view of accumulated feedback data across all
  categories, without requiring a completed epic. Distinct from
  retrospective-agent, which requires an EPIC-Name and produces a full post-epic
  analysis document.
- **feedback-review**: Use when the user wants to triage unresolved feedback
  entries from feedback.jsonl. Presents each unresolved entry grouped by
  category and prompts the user to create a ticket, dismiss with a rationale,
  or skip. Calls resolve_feedback.py after each user decision. Exits with a
  summary of N resolved, M tickets created, K skipped.

### Failure 2 — `tests/test_install_hooks.py` (all 6 tests fail)

`test_install_hooks.py` loads `scripts/build_helpers.py` via
`importlib.util.spec_from_file_location` and then calls
`spec.loader.exec_module(mod)`. Because `importlib` exec-mode bypasses the
normal import machinery, the `scripts/` directory is not on `sys.path` at the
moment the module body executes. `build_helpers.py` line 27 attempts:

```python
from build_colors import dry_run as _dry_run
```

This raises `ModuleNotFoundError: No module named 'build_colors'` before any
test class runs, crashing all 6 tests in the file.

**Fix**: In `tests/test_install_hooks.py`, the `_get_install_hooks()` helper
must insert `_REPO_ROOT / "scripts"` into `sys.path` before calling
`spec.loader.exec_module(mod)`, so that `build_colors` is resolvable when the
module body executes. The `sys.path` insert must guard against duplicate entries
(check `if str(scripts_dir) not in sys.path` before inserting).

Alternatively (if modifying the test is not preferred), `build_helpers.py` could
use a `sys.path`-safe import pattern — but modifying the test is lower-risk and
does not change the production module.

### Failure 3 — `unit_tests/test_build_workflow_phase.py` (2 of 5 tests fail)

`build_phases.build_workflow_scripts()` computes the output directory as:

```python
output_dir = target_root / "workflows"
```

The tests assert files are written to:

```python
target_root / ".claude" / "workflows" / "build-feature.js"
target_root / ".claude" / "workflows" / "finalize-feature.js"
```

The code writes to `target_root/workflows/` but the tests expect
`target_root/.claude/workflows/`. The correct output path for Claude Code
workflow scripts is under `.claude/workflows/` — all other Claude Code artefacts
(agents, skills, hooks, rules) are written under `.claude/`. The `"workflows"`
subdir at the repo root is the wrong destination.

Two tests fail with `AssertionError: assert False` at the `.exists()` check:

- `test_workflow_scripts_installed_when_enabled_and_version_ok`
- `test_workflow_scripts_installed_when_version_unknown`

**Fix**: Change line in `build_phases.py`:

```python
output_dir = target_root / "workflows"
```

to:

```python
output_dir = target_root / ".claude" / "workflows"
```

The `dry_run` print statement on line 376 (`would write .claude/workflows/{js_file.name}`)
already uses the correct `.claude/workflows/` path — indicating the original
author intended `.claude/workflows/` but introduced a bug in the `output_dir`
assignment.

## Acceptance Criteria

```gherkin
Given the skill_registry.json has entries for debug, feedback-analysis, and feedback-review
When tests/test_skill_registry.py is run
Then TestSkillRegistryBidirectional.test_no_orphaned_directories passes
And TestSkillRegistryBidirectional.test_no_orphaned_entries passes

Given scripts/ is on sys.path when build_helpers.py is exec'd by the test loader
When tests/test_install_hooks.py is run
Then all 6 test cases pass without ModuleNotFoundError

Given build_workflow_scripts() writes to target_root / ".claude" / "workflows"
When unit_tests/test_build_workflow_phase.py is run with enabled config and valid version
Then test_workflow_scripts_installed_when_enabled_and_version_ok passes
And test_workflow_scripts_installed_when_version_unknown passes
And all 5 tests in test_build_workflow_phase.py pass
```

## Sign-offs

- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

**Fix 1 — `config/skill_registry.json`**

Add three entries (insert in alphabetical order by `id`; `debug` goes after
`create-hook`, `feedback-analysis` and `feedback-review` go after `feature`):

```json
{
  "id": "debug",
  "name": "Debug",
  "portable": true,
  "domain": null,
  "template_path": "leafcutter/templates/skills/debug/",
  "dependencies": [],
  "description": "Multi-angle debugging workflow. Spawns three parallel investigative agents (database, backend, frontend/docs) to diagnose an issue from different perspectives, synthesizes findings, creates a fix ticket via create-ticket agent, and builds it via build-feature."
},
{
  "id": "feedback-analysis",
  "name": "Feedback Analysis",
  "portable": true,
  "domain": null,
  "template_path": "leafcutter/templates/skills/feedback-analysis/",
  "dependencies": [],
  "description": "Read-side analysis pipeline for the Central Feedback Collection System. Produces a prioritized report structure from accumulated feedback data across all categories."
},
{
  "id": "feedback-review",
  "name": "Feedback Review",
  "portable": true,
  "domain": null,
  "template_path": "leafcutter/templates/skills/feedback-review/",
  "dependencies": [],
  "description": "Triage unresolved feedback entries from feedback.jsonl. Presents each entry grouped by category and prompts the user to create a ticket, dismiss, or skip."
}
```

**Fix 2 — `tests/test_install_hooks.py`**

In the `_get_install_hooks()` helper, insert `scripts/` into `sys.path` before
calling `exec_module`:

```python
def _get_install_hooks():
    """Late-load install_hooks so tests can fail at test-run time, not collection."""
    _scripts_dir = str(_MODULE_PATH.parent)
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    spec = importlib.util.spec_from_file_location("build_helpers_ih", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "install_hooks")
```

**Fix 3 — `scripts/build_phases.py`**

Change the `output_dir` assignment in `build_workflow_scripts()` (approximately
line 353):

```python
# Before:
output_dir = target_root / "workflows"

# After:
output_dir = target_root / ".claude" / "workflows"
```

Also update the DECISION HISTORY block at the bottom of `build_phases.py` with
a new entry:

```
# - 2026-06-04 [python-coder/TICKET-20260604-FixFailingBuildPipelineTests]:
#   Fixed build_workflow_scripts() output path from target_root/"workflows" to
#   target_root/".claude"/"workflows" to match .claude/ layout convention and
#   fix unit_tests/test_build_workflow_phase.py assertions.
```

### test-runner

After applying the three fixes above, run all affected test files and confirm
zero failures:

```bash
python3 -m pytest leafcutter-ai/tests/test_skill_registry.py -v
python3 -m pytest leafcutter-ai/tests/test_install_hooks.py -v
python3 -m pytest leafcutter-ai/unit_tests/test_build_workflow_phase.py -v
```

All tests must exit 0 with 0 failures.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? All three changes are trivially reversible: JSON additions
  can be reverted, the `sys.path` insert is test-only, the path constant
  change is a one-line edit.
- Regression risk: Low. Fix 1 adds JSON entries (additive only). Fix 2
  modifies only the test helper (no production code change). Fix 3 corrects
  an output path in `build_workflow_scripts()` — the `.claude/workflows/`
  path is the intended destination per the `dry_run` log message already
  in the code.
