---
title: "Add build-time SKILL.md frontmatter validation to build.py"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build_phases.py
  - templates/agents/pr-reviewer.md
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  sql-query: not_needed
  frontend-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
---

# Add build-time SKILL.md frontmatter validation to build.py

## Actor / Goal

In order to prevent malformed skill files from reaching consumers silently, we
need `build.py` to validate every SKILL.md it deploys so that authoring errors
surface as a clear build failure rather than a runtime crash mid-flight.

## Context

`build_phases.py::build_skills()` iterates over `templates/skills/*/SKILL.md`,
compiles each via `compile_skill_template`, and writes the result to
`.claude/skills/*/SKILL.md` (and the Gemini equivalent). The function already
reads the frontmatter once to detect the `internal` flag (line ~306), but does
no further validation before writing.

A malformed SKILL.md — missing `name`, missing `allowed-tools`, or
unparseable YAML — deploys silently. The error only surfaces when an agent
or skill runner tries to load the compiled file at invocation time, typically
mid-epic, with a confusing parse error far from the authoring point.

This gap was discovered during EPIC-FrontendAgent (2026-05-28), which shipped
the first two optional skills (`webapp-testing`, `frontend-design`). See
`docs/retrospectives/EPIC-FrontendAgent.md` § Knowledge Gaps Found, item 3.

### Validation rules

The `build_skills()` loop already calls `parse_frontmatter()` on the SKILL.md.
The three additional checks to layer in are:

1. **YAML parseable** — `parse_frontmatter()` must not raise; if it raises,
   surface the parse error and abort.
2. **`name` key present and correct** — `fm["name"]` must equal the skill
   directory name (e.g. the SKILL.md inside `templates/skills/frontend-design/`
   must have `name: frontend-design`).
3. **`allowed-tools` key present and valid** — `fm["allowed-tools"]` must be
   present. Its value (a comma-separated string or YAML list) may only contain
   items from the canonical set: `Bash`, `Read`, `Write`, `Edit`, `Agent`, and
   any token matching `mcp__*`. Any other token is an error.

On validation failure, `build.py` must:
- Print a clear error message identifying the offending file path and the
  specific rule that failed (e.g. `ERROR: templates/skills/webapp-testing/SKILL.md:
  'allowed-tools' contains unknown tool 'Grep'`).
- Exit non-zero (`sys.exit(1)` or raise a handled exception that causes a
  non-zero exit).
- NOT write the file for that skill (fail fast before compile+write).

### PR reviewer interim guard

Until the validation is fully wired, `templates/agents/pr-reviewer.md` should
include a skill-file checklist so human reviewers catch regressions in PRs that
touch skill templates. Append to the agent's existing checklist (or add a new
`### Skill files` subsection if none exists):

```
- [ ] YAML frontmatter parses without error
- [ ] `name` key is present and matches the skill directory name
- [ ] `allowed-tools` key is present
- [ ] Input contract section (`## Input Contract`) is present
- [ ] Output contract section (`## Output Contract`) is present
```

## Acceptance Criteria

```gherkin
Given a SKILL.md with syntactically invalid YAML frontmatter
When python scripts/build.py --target-dir <target>
Then build.py exits non-zero
 And the error message identifies the offending file path
 And the file is not written to the target

Given a SKILL.md where `name` does not match the skill directory name
When python scripts/build.py --target-dir <target>
Then build.py exits non-zero
 And the error message names the file and states the name mismatch

Given a SKILL.md where `allowed-tools` contains an unrecognised tool name
When python scripts/build.py --target-dir <target>
Then build.py exits non-zero
 And the error message names the file and the offending tool token

Given all SKILL.md files have valid frontmatter
When python scripts/build.py --target-dir <target>
Then all skills deploy successfully and build.py exits 0

Given a SKILL.md where `allowed-tools` contains `mcp__my_server__tool`
When python scripts/build.py --target-dir <target>
Then that skill deploys successfully (mcp__ prefix is allowed)

Given templates/agents/pr-reviewer.md
When a reviewer checks a PR that modifies any templates/skills/*/SKILL.md
Then the five skill-file checklist items are visible in pr-reviewer.md
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] In `scripts/build_phases.py::build_skills()`, after the existing
  `parse_frontmatter()` call (~line 306), add a `_validate_skill_frontmatter()`
  helper that runs the three checks (parseable, name match, allowed-tools).
  Return a list of error strings (empty = pass).
- [ ] Define the canonical allowed-tools set as a module-level constant:
  `_ALLOWED_SKILL_TOOLS = {"Bash", "Read", "Write", "Edit", "Agent"}`. Tokens
  matching the regex `mcp__\S+` are also allowed (check with `re.match`).
- [ ] Parse `allowed-tools` from the frontmatter: accept either a YAML list or
  a comma-separated string; split and strip whitespace before validating each
  token.
- [ ] On validation failure, `print` each error to stderr, then call
  `sys.exit(1)` (or accumulate errors across all skills and fail at the end —
  implementer's choice; document the chosen strategy in a `# DECISION HISTORY`
  comment in `build_phases.py`).
- [ ] In `templates/agents/pr-reviewer.md`, locate the existing checklist
  section (search for `- [ ]` blocks) and append a `### Skill files` subsection
  (or integrate into an existing PR checklist block) with the five items listed
  in the Context section above.

### test-writer

- [ ] Add `unit_tests/test_build_skill_validation.py` (new file):
  - `test_invalid_yaml_exits_nonzero` — create a fixture SKILL.md with broken
    YAML; assert `build_skills()` raises or the process exits non-zero.
  - `test_name_mismatch_exits_nonzero` — fixture where `name: wrong-name` for
    a dir called `my-skill`; assert non-zero exit / error raised.
  - `test_unknown_tool_exits_nonzero` — fixture with `allowed-tools: Grep`
    (not in canonical set); assert non-zero.
  - `test_mcp_tool_allowed` — fixture with `allowed-tools: mcp__myserver__do`;
    assert validation passes.
  - `test_valid_skill_deploys` — fixture with correct frontmatter; assert the
    compiled file is written to `target_root/.claude/skills/<skill>/SKILL.md`.
  - `test_error_message_names_file` — capture stderr; assert offending file
    path appears in the output.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — removing the validation guard restores
  prior behaviour. No schema changes, no database changes.
- Fail-fast behaviour: if `build.py` starts exiting non-zero on existing
  skill templates, those templates must be audited and fixed before the change
  ships. Run `python scripts/build.py --validate-only` against the current
  template set to identify any pre-existing violations before merging.
- `templates/agents/pr-reviewer.md` is a template deployed to consumers;
  the checklist addition is additive and safe.
