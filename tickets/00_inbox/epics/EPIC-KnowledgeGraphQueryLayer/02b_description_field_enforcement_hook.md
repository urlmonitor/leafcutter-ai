---
title: "Add check_description_field.py commit-guardian hook and register it"
status: todo
components:
  - knowledge-management
  - build_pipeline
created: 2026-06-04
depends_on:
  - tickets/00_inbox/epics/EPIC-KnowledgeGraphQueryLayer/02a_description_backfill_migration.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/5
files_touched:
  - scripts/commit_guardian/check_description_field.py
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
---

# Add check_description_field.py commit-guardian hook and register it

## Actor / Goal

In order to prevent future commits from introducing doc files without a
`description:` frontmatter field (undoing the backfill from ticket 02a), we need
a lightweight pre-commit hook that validates all staged `.md` files in the target
directories and blocks commits that are missing the field.

## Context

The backfill script (ticket 02a) ensures every existing doc file has a `description:`
field. This hook enforces the invariant going forward so new files or edits cannot
regress coverage.

The hook follows the same pattern as `scripts/commit_guardian/check_ac_schema.py` and
`check_paths_integrity.py`: reads staged files from stdin or as CLI args, parses YAML
frontmatter, exits non-zero with a list of violations.

**Scope boundary (settled — do not reopen):**
- Targets: `docs/**/*.md`, `docs/architecture/adrs/*.md`, `docs/architecture/components/*.md`
- Excluded: ticket files (`tickets/**/*.md`), skill SKILL.md files (`templates/skills/`),
  agent template files (`templates/agents/`)

## Agent Contracts

### python-coder

- [ ] AC-1: `scripts/commit_guardian/check_description_field.py` exits 0 when all
  staged target files have a non-empty `description:` field and exits non-zero with a
  per-file list of violations when any staged target file is missing the field.
- [ ] AC-2: `check_description_field.py` does NOT flag ticket files, skill SKILL.md
  files, or agent template files — only files under `docs/`, `docs/architecture/adrs/`,
  and `docs/architecture/components/`.
- [ ] AC-3: `check_description_field.py` is registered in the commit-guardian configuration
  and runs on staged `.md` files following the `check_ac_schema.py` pattern.

**Delivers to test-writer:**
```json
{
  "hook_script": "scripts/commit_guardian/check_description_field.py",
  "hook_cli": {
    "args": "file paths as positional arguments",
    "exit_codes": {"0": "no violations", "1": "one or more violations"},
    "output_format": "FAIL: <path> — missing description field"
  },
  "scope_rules": {
    "targets": ["docs/", "docs/architecture/adrs/", "docs/architecture/components/"],
    "excludes": ["tickets/", "templates/skills/", "templates/agents/"]
  }
}
```

#### Implementation guidance

Follow `check_ac_schema.py` pattern. Accept file paths as CLI args, skip non-target
paths silently, exit 1 with violation list on failure.

Key implementation points:

1. **Input** — file paths as positional CLI arguments (same interface as other commit-guardian hooks).
2. **Path filtering** — only check files whose path starts with a target prefix; silently skip all others.
3. **Frontmatter parsing** — `re` to split at `---` pairs; check for `description:` key with non-empty value.
4. **Output** — one line per violation: `FAIL: <path> — missing description field`.
5. **Exit codes** — 0 if all target files pass; 1 if any violation found.
6. **Registration** — add entry to `commit_guardian.json` targeting `docs/.*\.md$` files.

---

### test-writer

- [ ] AC-4: `unit_tests/test_check_description_field.py` exists with tests covering:
  exits 0 when all staged docs have description, exits 1 when missing, ignores ticket
  files, ignores skill files.
- [ ] AC-5: All tests fail (RED) before python-coder runs and pass (GREEN) after. <!-- scope: integration -->

**Depends on python-coder:** hook script path, CLI args interface, exit codes, output
format, and scope rules from the Delivers-to block above.

#### Test specification

Create `unit_tests/test_check_description_field.py`:

- `test_exits_0_when_all_staged_docs_have_description`
- `test_exits_1_when_staged_doc_missing_description`
- `test_ignores_ticket_files`
- `test_ignores_skill_files`

## AC Coverage

| AC    | Test | Implementation | Validated |
|-------|------|----------------|-----------|
| AC-1  |      |                |           |
| AC-2  |      |                |           |
| AC-3  |      |                |           |
| AC-4  |      |                |           |
| AC-5  |      |                |           |

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only hook, only inspects staged doc files.
- Reversibility? Fully reversible — remove hook from commit_guardian.json.
- Risk of regressions: the enforcement check must not block commits of ticket or
  skill files. Scope-exclusion logic must be tested explicitly (see
  `test_ignores_ticket_files` and `test_ignores_skill_files`).
