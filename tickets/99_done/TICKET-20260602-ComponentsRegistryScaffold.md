---
title: "Add components.json scaffold to build pipeline (write-if-absent)"
status: done
components:
  - build_pipeline
created: 2026-06-02
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/docs/components.json.template
  - leafcutter-ai/scripts/build_phases.py
  - leafcutter-ai/scripts/build.py
  - leafcutter-ai/tests/test_components_registry_scaffold.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  sql-query: not_needed
  frontend-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
  status-checker: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# Add components.json scaffold to build pipeline (write-if-absent)

## Actor / Goal

In order to ensure that `docs/components.json` is present in every new leafcutter
installation, we need to add a template file and a `build_components_registry()`
phase to the build pipeline so that the file is created automatically on first
`build.py` run — with write-if-absent semantics so existing projects are never
overwritten.

## Context

`docs/components.json` is treated as mandatory by several parts of the installed
system:

- `templates/rules/documentation.md` references it four times as the canonical
  source of component IDs.
- `templates/agents/create-ticket.md`, `architect-review.md`, and `adr-author.md`
  all reference it to validate or emit component lists.
- Pre-commit hooks `check_doc_frontmatter.py` and `check_components_integrity.py`
  attempt to read it at runtime.

Despite this, `build.py` has never included a phase to create the file. All other
analogous scaffolds (`docs/vision.md`, `docs/glossary.md`, `docs/roadmap.json`)
have their own template and build phase using the established `write_if_absent`
pattern, but `docs/components.json` does not. The validators degrade gracefully
when the file is absent, but new users following the documentation rules encounter
confusing failures because the file they are told to populate does not exist.

The fix is narrow and additive: one new template file, one new function in
`build_phases.py` (modelled exactly on `build_vision()`), and one entry in the
`scaffold_phases` list in `build.py`.

### Analogous code (build_vision pattern to replicate)

`build_vision()` in `scripts/build_phases.py` (lines 810–843) is the canonical
reference implementation:

```python
def build_vision(target_root, config, dry_run, force):
    template_path = TEMPLATES_DIR / "vision" / "VISION.template.md"
    if not template_path.exists():
        return 0
    docs_dir = config.get("docs_root", "docs/").rstrip("/")
    target_path = target_root / docs_dir / "vision.md"
    if target_path.exists():
        print(f"  vision: {docs_dir}/vision.md exists (skipped)")
        return 0
    content = inject_config(template_path.read_text(encoding="utf-8"), config)
    if _write(target_path, content, dry_run, force=False):
        print("  vision: created from template (PLEASE FILL — see <!-- QUESTION --> markers)")
        return 1
    return 0
```

`build_components_registry()` must follow this same shape: read from a
`templates/docs/components.json.template` file, write to
`{docs_root}/components.json`, always pass `force=False`, print a guidance
message if created.

### Wiring location in `build.py`

The `scaffold_phases` list (lines 384–390) is:

```python
scaffold_phases = [
    ("Ticket lifecycle", build_ticket_lifecycle),
    ("Vision", build_vision),
    ("Roadmap", build_roadmap),
    ("Glossary", build_glossary),
    ("Config scaffolds", build_config_scaffolds),
]
```

Insert `("Components registry", build_components_registry)` between
`("Roadmap", build_roadmap)` and `("Glossary", build_glossary)`.

## Acceptance Criteria

```gherkin
Given a target project directory where docs/components.json does not exist
When python build.py --target-dir <project> is run
Then docs/components.json is created with valid JSON containing {"components": {}}

Given a target project directory where docs/components.json already exists with content
When python build.py --target-dir <project> is run
Then docs/components.json is NOT modified and build.py prints a "exists (skipped)" message

Given the newly created docs/components.json
When python -m json.tool docs/components.json is run
Then it exits 0 (valid JSON)

Given build.py is run with --dry-run
When the components.json scaffold phase is reached
Then no file is written and the phase reports intent only
```

## Sign-offs

- [x] test-writer — 2026-06-02 10:00
- [x] python-coder — 2026-06-02 10:15
- [x] pr-reviewer — 2026-06-02 10:20
- [x] commit — 2026-06-02 10:25
- [ ] pull-request

## Comments

### 2026-06-02 10:00 — test-writer (status: ok)
feedback-id: fb_2026-06-02_ece72fb5
completion_manifest:
  test_file_created: true
  all_five_test_cases_present: true
  tests_import_correctly: true
Created tests/test_components_registry_scaffold.py with 5 test cases covering all acceptance criteria (create-when-absent, skip-when-exists, dry-run, missing-template, force-ignored). Tests are currently red (ImportError on build_components_registry) as expected before python-coder implements the function.

### 2026-06-02 10:15 — python-coder (status: ok)
feedback-id: fb_2026-06-02_dc6ff4f9
completion_manifest:
  template_created: true
  build_components_registry_added: true
  build_py_wired: true
  decision_history_added: true
  change_log_added: true
  all_five_tests_green: true
  no_regressions: true
Implemented all 3 deliverables: templates/docs/components.json.template (with _comment key, tolerated by check_components_integrity.py which only reads data["components"]), build_components_registry() in build_phases.py after build_vision() with identical write-if-absent pattern, and wired into scaffold_phases in build.py between Roadmap and Glossary. All 5 acceptance-criteria tests pass; full suite shows 4 pre-existing failures unrelated to this ticket.

### 2026-06-02 10:20 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-02_c8800692
completion_manifest:
  scope_matches_plan: true
  pattern_fidelity: true
  template_valid_json: true
  import_correct: true
  wiring_position_correct: true
  hook_compatibility_verified: true
  tests_green: true
  logs_added: true
Reviewed full diff: additive only (build.py +6, build_phases.py +41, 2 new files). build_components_registry() is a faithful replica of build_vision() with force=False hardcoded. Template is valid JSON; _comment key is silently ignored by check_components_integrity.py (it reads data.get("components", {}) only). All 5 tests pass. No blockers.

### 2026-06-02 10:25 — commit (status: ok)
feedback-id: fb_2026-06-02_1be56b7f
completion_manifest:
  staged_explicit_paths_only: true
  commit_created: true
  no_unintended_files: true
Committed SHA 6d83bf4: 5 files (scripts/build.py, scripts/build_phases.py, templates/docs/components.json.template, tests/test_components_registry_scaffold.py, tickets/01_todo/TICKET-20260602-ComponentsRegistryScaffold.md). Staged by explicit path — no wildcard add used.

## Implementation Tasks

### python-coder

**Deliverable 1 — Create `templates/docs/components.json.template`**

- [x] Create the file `leafcutter-ai/templates/docs/components.json.template`
  with the following content (no YAML frontmatter — this is a JSON template):

  ```json
  {
    "_comment": "Component registry for this project. Each key is a component ID used in ticket frontmatter (components: field) and agent references. Add an entry here for each logical module, service, or subsystem. Valid fields per entry: id (string, matches key), name (string), type (string), description (string), status (string: active|reviewed|deprecated), primary_code (list of relative paths), detail_ref (optional path to architecture doc).",
    "components": {}
  }
  ```

  The `_comment` key serves as in-file documentation since JSON does not support
  comments. The hook `check_components_integrity.py` must tolerate this key
  (check whether it currently does and note in comments if a follow-up is needed).

**Deliverable 2 — Add `build_components_registry()` to `scripts/build_phases.py`**

- [x] Add the following function immediately after `build_vision()` (around line 844,
  before `build_feedback()`):

  ```python
  def build_components_registry(target_root: Path, config: dict[str, Any],
                                dry_run: bool, force: bool) -> int:
      """Materialise docs/components.json from the components template — write-if-absent only.

      This phase intentionally overrides the ``force`` flag passed by the caller.
      A project's components.json is a human-curated living registry; once it exists
      it must never be clobbered by a build run.

      Args:
          target_root: Absolute path to the target project root directory.
          config: Merged config dictionary used for placeholder injection.
          dry_run: When True, logs intent but writes nothing.
          force: Ignored — this phase always uses write-if-absent semantics.

      Returns:
          1 if the file was (or would be in dry-run mode) written; 0 if skipped.
      """
      template_path = TEMPLATES_DIR / "docs" / "components.json.template"
      if not template_path.exists():
          return 0
      docs_dir = config.get("docs_root", "docs/").rstrip("/")
      target_path = target_root / docs_dir / "components.json"
      if target_path.exists():
          print(f"  components: {docs_dir}/components.json exists (skipped)")
          return 0
      content = inject_config(template_path.read_text(encoding="utf-8"), config)
      if _write(target_path, content, dry_run, force=False):
          print(
              "  components: created from template "
              "(PLEASE POPULATE — add one entry per module; "
              "see templates/docs/components.json.template for the schema)"
          )
          return 1
      return 0
  ```

- [x] Add a `# DECISION HISTORY` entry at the bottom of `build_phases.py` documenting
  the addition (date: 2026-06-02, ticket: this ticket basename).

**Deliverable 3 — Wire the phase into `build.py`**

- [x] In `build.py`, add the import alongside the existing `build_vision` import:
  ```python
  from build_phases import build_components_registry
  ```
  (or extend the existing `from build_phases import build_vision, ...` line)

- [x] Add the phase entry to `scaffold_phases` between `("Roadmap", build_roadmap)`
  and `("Glossary", build_glossary)`:
  ```python
  ("Components registry", build_components_registry),
  ```

- [x] Add a `# CHANGE LOG` entry at the bottom of `build.py` documenting the
  addition (date: 2026-06-02, ticket: this ticket basename).

### test-writer

- [x] Create `leafcutter-ai/tests/test_components_registry_scaffold.py` with these
  test cases (use `tmp_path` fixture — never write to project dirs):

  - `test_creates_components_json_when_absent`:
    Set up a temp target_root with no `docs/components.json`. Set
    `TEMPLATES_DIR` to a temp templates dir containing a minimal
    `docs/components.json.template` with `{"components":{}}`. Call
    `build_components_registry(target_root, config={}, dry_run=False, force=False)`.
    Assert return value is `1` and `target_root / "docs" / "components.json"` exists
    and contains valid JSON with a `"components"` key.

  - `test_skips_when_components_json_exists`:
    Same setup but pre-create `docs/components.json` with some content. Call
    `build_components_registry(...)`. Assert return value is `0` and file content
    is unchanged (write-if-absent respected).

  - `test_dry_run_does_not_write`:
    Call with `dry_run=True`. Assert return value is `1` (would write) but the
    file was NOT created on disk.

  - `test_missing_template_returns_zero`:
    Set up a temp `TEMPLATES_DIR` with no `docs/components.json.template`.
    Assert return value is `0` (graceful no-op when template is absent).

  - `test_force_flag_is_ignored`:
    Pre-create `docs/components.json`. Call with `force=True`. Assert the file
    is still not overwritten (force is explicitly ignored by write-if-absent
    contract).

## Risk & Safety

- Touches money? No.
- Touches data? No — creates a new file only; never overwrites.
- Reversibility? Fully reversible. The template file, function, and wiring
  entry can each be reverted independently. Existing projects are unaffected
  (write-if-absent). New projects that ran build.py and got an empty
  `components.json` can delete it and re-run to regenerate.
- Scope: changes are isolated to the build pipeline. No hooks, no agents, no
  skills are modified. The `check_components_integrity.py` pre-commit hook
  already degrades gracefully when the file is absent; it will now find the file
  on new installations and must tolerate the `_comment` key — verify this does
  not introduce a new rejection and add a follow-up ticket if it does.
