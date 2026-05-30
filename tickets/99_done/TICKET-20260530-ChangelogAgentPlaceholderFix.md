---
title: "Fix changelog-agent template: replace hardcoded changelogs/ path with {{config.changelog_folder}} placeholder"
status: done
components:
  - build_pipeline
  - config_loader
created: 2026-05-30
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/changelog-agent.md
  - scripts/build.py
  - unit_tests/test_build_changelog_placeholder.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  status-checker: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
---

# Fix changelog-agent template: replace hardcoded changelogs/ path with {{config.changelog_folder}} placeholder

## Actor / Goal

In order for the automated versioning pipeline to find changelog entries reliably,
we need to replace the two hardcoded `"changelogs/"` literals in
`templates/agents/changelog-agent.md` with `{{config.changelog_folder}}` and
inject that value from `commit_guardian.json` during the build so that
the changelog-agent always writes to the project-configured directory.

## Context

The changelog-agent template already declares the config key it needs:

```yaml
config_keys:
  changelog_folder: "changelogs/"
```

And it already uses the `{{config.*}}` pattern for another path:

```
cat "{{config.changelog_categories_path}}" 2>/dev/null
```

However, Steps 7 and 8 of the template body use hardcoded literals instead:

- Step 7 (emit_entry.py invocation): `--changelog-dir "changelogs/"`
- Step 8 (git add): `git add "changelogs/"`

When a consumer project configures a different output directory via
`commit_guardian.json` → `"changelogs_dir"`, the changelog-agent ignores
that setting and writes to `docs/changelog/` (or whichever incorrect default
the agent resolves to at runtime), breaking the version-bump pipeline.

The root cause was discovered during EPIC-CompletionManifestSignoff: the
changelog entry was written to `docs/changelog/` instead of `changelogs/`,
causing `compute_next_version.py` to see zero relevant entries and silently
skip the v0.3.0 bump despite 27 new commits.

The fix mirrors how `build.py` already injects `file_size_limit_py` from
`commit_guardian.json` (via `_inject_file_size_limits`): add a parallel
`_inject_changelogs_dir` function that reads `changelogs_dir` from the
commit-guardian template JSON and writes it into the config dict as
`changelog_folder`. The template placeholder `{{config.changelog_folder}}`
then resolves correctly at build time via the existing `inject_config` call in
`compile_agent_template`.

Related:
- `TICKET-20260528-FixComputeNextVersionBugs.md` — fixes the version-bump
  consumer; this ticket fixes the changelog-agent producer.
- `scripts/build.py::_inject_file_size_limits` — the existing pattern to follow.
- `scripts/template_compiler.py::inject_config` — resolves `{{config.key}}`
  placeholders during template compilation.

## Acceptance Criteria

```gherkin
Given a project with commit_guardian.json containing "changelogs_dir": "changelogs"
When build.py compiles the changelog-agent template
Then the compiled agent body contains "changelogs/" (not the literal placeholder)
 And the --changelog-dir argument in Step 7 resolves to "changelogs/"
 And the git add path in Step 8 resolves to "changelogs/"

Given a project with commit_guardian.json containing "changelogs_dir": "release_notes"
When build.py compiles the changelog-agent template
Then the compiled agent body contains "release_notes/" in both Step 7 and Step 8
 And no occurrence of the raw placeholder "{{config.changelog_folder}}" remains

Given commit_guardian.json is absent (fallback case)
When build.py runs _inject_changelogs_dir
Then "changelog_folder" in config defaults to "changelogs/"
 And the build does not raise an exception

Given the changelog-agent template is compiled with the existing inject_config mechanism
When build.py calls compile_agent_template for changelog-agent.md
Then {{config.changelog_folder}} is replaced by the injected value
 And {{config.changelog_categories_path}} (the existing placeholder) is also still resolved correctly
```

## Sign-offs

- [x] test-writer — 2026-05-30 10:00
- [x] python-coder — 2026-05-30 10:05
- [x] pr-reviewer — 2026-05-30 10:10
- [x] commit — 2026-05-30 10:15
- [x] pull-request — 2026-05-30 10:20

## Comments

### 2026-05-30 10:00 — test-writer (status: ok)
feedback-id: fb_2026-05-30_e276dcb5
completion_manifest:
  test_file_created: true
  tests_red: true
  all_six_tests_written: true
red_baseline:
  - test_name: test_inject_changelogs_dir_reads_from_commit_guardian
    file: unit_tests/test_build_changelog_placeholder.py
    error: "AttributeError: module 'build' has no attribute '_inject_changelogs_dir'"
  - test_name: test_inject_changelogs_dir_custom_path
    file: unit_tests/test_build_changelog_placeholder.py
    error: "AttributeError: module 'build' has no attribute '_inject_changelogs_dir'"
  - test_name: test_inject_changelogs_dir_trailing_slash_normalised
    file: unit_tests/test_build_changelog_placeholder.py
    error: "AttributeError: module 'build' has no attribute '_inject_changelogs_dir'"
  - test_name: test_inject_changelogs_dir_fallback_when_json_absent
    file: unit_tests/test_build_changelog_placeholder.py
    error: "AttributeError: module 'build' has no attribute '_inject_changelogs_dir'"
  - test_name: test_changelog_folder_custom_path_resolved_in_compiled_template
    file: unit_tests/test_build_changelog_placeholder.py
    error: "AssertionError: Found hardcoded 'changelogs/' in a coder-injected line: '--changelog-dir \"changelogs/\" \\'"
Created unit_tests/test_build_changelog_placeholder.py with 6 tests (5 red, 1 pre-passes). The _inject_changelogs_dir unit tests fail with AttributeError as expected. The custom-path integration test fails because the template still has the hardcoded literal. python-coder must add _inject_changelogs_dir to build.py and replace hardcoded literals in changelog-agent.md.

### 2026-05-30 10:05 — python-coder (status: ok)
feedback-id: fb_2026-05-30_99750c15
completion_manifest:
  template_step7_placeholder_replaced: true
  template_step8_placeholder_replaced: true
  template_constraints_placeholder_replaced: true
  inject_changelogs_dir_function_added: true
  inject_changelogs_dir_call_added: true
  decision_history_updated: true
  all_six_tests_green: true
Added _inject_changelogs_dir() to scripts/build.py (after _inject_file_size_limits) and replaced 3 hardcoded changelogs/ literals in templates/agents/changelog-agent.md with {{config.changelog_folder}}. All 6 unit tests pass.

### 2026-05-30 10:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-30_26f701a0
completion_manifest:
  all_acceptance_criteria_met: true
  implementation_matches_tasks: true
  tests_written_and_green: true
  no_regressions: true
  code_quality_acceptable: true
PR review passed. All 4 acceptance criteria satisfied by 6 passing tests. Implementation exactly follows _inject_file_size_limits pattern. No regressions detected.

### 2026-05-30 10:15 — commit (status: ok)
feedback-id: fb_2026-05-30_1c7d836c
completion_manifest:
  files_staged_correctly: true
  pre_commit_hooks_passed: true
  commit_created: true
Committed 4 files (changelog-agent.md, build.py, test file, ticket) in commit 6e74018. All 23 pre-commit checks passed (10 applicable, 13 skipped).

### 2026-05-30 10:20 — pull-request (status: ok)
feedback-id: fb_2026-05-30_067c32ef
completion_manifest:
  changes_pushed_to_main: true
  commit_sha_confirmed: true
Pushed commit 6e74018 directly to origin/main (standalone ticket — no feature branch). Changes are live at https://github.com/urlmonitor/leafcutter-ai/commit/6e74018.

## Implementation Tasks

### python-coder

- [x] In `templates/agents/changelog-agent.md`, Step 7 — replace:
  ```bash
  python leafcutter/scripts/changelog/emit_entry.py \
    --changelog-dir "changelogs/" \
  ```
  with:
  ```bash
  python leafcutter/scripts/changelog/emit_entry.py \
    --changelog-dir "{{config.changelog_folder}}" \
  ```

- [x] In `templates/agents/changelog-agent.md`, Step 8 — replace:
  ```bash
  git add "changelogs/"
  ```
  with:
  ```bash
  git add "{{config.changelog_folder}}"
  ```

- [x] In `templates/agents/changelog-agent.md`, Constraints section — replace:
  ```
  The `changelogs/` directory is created automatically by
  ```
  with:
  ```
  The `{{config.changelog_folder}}` directory is created automatically by
  ```

- [x] In `scripts/build.py`, add a new function `_inject_changelogs_dir` directly
  after `_inject_file_size_limits` (approx. line 238), following the exact same
  pattern:

  ```python
  def _inject_changelogs_dir(config: dict, package_root: Path) -> None:
      """Inject changelogs_dir from commit_guardian.json into the config dict.

      Reads ``changelogs_dir`` from the commit-guardian template JSON and adds
      ``changelog_folder`` to ``config`` so that the changelog-agent template
      can reference it as ``{{config.changelog_folder}}``.

      Falls back to ``"changelogs/"`` when the JSON is absent or malformed.

      Args:
          config: The mutable config dict returned by ``load_config``; modified
              in-place with the new ``changelog_folder`` key.
          package_root: Absolute path to the leafcutter package root,
              used to locate ``templates/scripts/commit_guardian/commit_guardian.json``.
      """
      cg_path = package_root / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"
      if not cg_path.exists():
          cg_path = package_root / "templates" / "commit-guardian" / "commit_guardian.json"
      changelogs_dir: str = "changelogs/"
      try:
          with cg_path.open(encoding="utf-8") as fh:
              cg = json.load(fh)
          raw = cg.get("changelogs_dir", "changelogs")
          # Normalise: ensure a trailing slash for use as a path prefix
          changelogs_dir = raw.rstrip("/") + "/"
      except (OSError, json.JSONDecodeError, TypeError, ValueError):
          pass  # Fallback already set
      config["changelog_folder"] = changelogs_dir
  ```

- [x] In `scripts/build.py`, call `_inject_changelogs_dir(config, package_root)`
  immediately after the existing `_inject_file_size_limits(config, package_root)`
  call (approx. line 572):

  ```python
  _inject_file_size_limits(config, package_root)
  _inject_changelogs_dir(config, package_root)   # <-- add this line
  ```

- [x] Update the module-level docstring comment block near the bottom of
  `build.py` (the `# Enables python-coder template...` comment) to document
  the new injection alongside `file_size_limit_py`.

### test-writer

- [x] Create `unit_tests/test_build_changelog_placeholder.py` with the following
  tests (follow the style of `unit_tests/test_build_version_wiring.py`):

  - `test_inject_changelogs_dir_reads_from_commit_guardian`:
    Create a temp `commit_guardian.json` containing `{"changelogs_dir": "changelogs"}`.
    Lay it out at the path `_inject_changelogs_dir` reads from. Call
    `_inject_changelogs_dir(config, package_root)`. Assert
    `config["changelog_folder"] == "changelogs/"`.

  - `test_inject_changelogs_dir_custom_path`:
    Same setup but `{"changelogs_dir": "release_notes"}`. Assert
    `config["changelog_folder"] == "release_notes/"`.

  - `test_inject_changelogs_dir_trailing_slash_normalised`:
    Set `{"changelogs_dir": "changelogs/"}` (already has trailing slash). Assert
    `config["changelog_folder"] == "changelogs/"` (no double slash).

  - `test_inject_changelogs_dir_fallback_when_json_absent`:
    Call `_inject_changelogs_dir(config, Path("/nonexistent"))`. Assert
    `config["changelog_folder"] == "changelogs/"`.

  - `test_changelog_folder_placeholder_resolved_in_compiled_template`:
    Load the `templates/agents/changelog-agent.md` template. Call
    `compile_agent_template(template_path, {"changelog_folder": "changelogs/",
    "changelog_categories_path": ".claude/changelog_categories.md"})`.
    Assert the compiled output does NOT contain the literal string
    `{{config.changelog_folder}}`. Assert it DOES contain `"changelogs/"`.

  - `test_changelog_folder_custom_path_resolved_in_compiled_template`:
    Same as above but with `{"changelog_folder": "release_notes/", ...}`.
    Assert the compiled output contains `"release_notes/"` and does NOT
    contain `"changelogs/"` in the emit_entry.py call or git add line.

## Risk & Safety

- Touches money? No.
- Touches data? No — template compilation is pure text transformation.
- Reversibility? Fully reversible. The two template edits are one-line
  substitutions. Reverting restores the hardcoded `"changelogs/"` behaviour,
  which is the current (broken) default.
- Shared contracts? The `config` dict is an internal build artefact — no
  consumer API is affected. `changelog_folder` is a new key; existing keys
  are untouched. Any consumer whose `commit_guardian.json` already has
  `"changelogs_dir": "changelogs"` (the default) will see identical compiled
  output to today.
- Build drift: after this fix, running `./build-self.sh` will regenerate
  `.claude/agents/changelog-agent.md` with the resolved path. The diff will
  be two line changes (Step 7 and Step 8). This is expected and correct.
- Edge case: consumers who have NOT yet run `build.py` after this change will
  still have the old compiled agent with `"changelogs/"` hardcoded. A rebuild
  is required to pick up the fix. This is normal build-pipeline behaviour.
