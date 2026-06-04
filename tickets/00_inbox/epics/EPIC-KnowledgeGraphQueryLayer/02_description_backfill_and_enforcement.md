---
title: "Backfill description: field on all docs/ADRs/components and add pre-commit enforcement"
status: todo
components:
  - knowledge-management
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/13
files_touched:
  - scripts/backfill_descriptions.py
  - scripts/commit_guardian/check_description_field.py
  - docs/architecture/adrs/*.md
  - docs/architecture/components/*.md
  - docs/**/*.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Backfill description: field on all docs/ADRs/components and add pre-commit enforcement

## Actor / Goal

In order to make the `description:` frontmatter field consistently present on all
structured doc files so that `knowledge_query.py` and `generate_doc_index.py` never
fall back to parsing body text, we need a one-time migration script that adds a
one-line `description:` field to every docs, ADR, and component file that lacks one,
plus a lightweight pre-commit check that blocks future commits of such files without
the field.

## Context

`generate_doc_index.py` already uses `description:` if present and falls back to the
first non-blank body line if absent. The fallback works but produces lower-quality
summaries (it picks up headers, preamble boilerplate, or context sentences rather
than a purpose-statement). The agent-registry and skill-registry already have
`description` on every entry — this ticket brings the doc surfaces to the same standard.

**Scope boundary (settled — do not reopen):**
- Backfill target: `docs/**/*.md`, `docs/architecture/adrs/*.md`,
  `docs/architecture/components/*.md`
- Excluded: agent template files in `templates/agents/`, skill SKILL.md files in
  `templates/skills/` — these surfaces use their registry entries as the description
  layer and must not be modified here.
- Excluded: ticket files (`tickets/**/*.md`) — tickets already have `title:` as their
  primary label; adding `description:` to tickets is out of scope.

### Backfill strategy

The migration script (`backfill_descriptions.py`) must operate in two modes:
- `--dry-run` (default): prints every file that would be changed and the proposed
  description, without writing anything.
- `--write`: rewrites files, inserting `description: "<generated_description>"` as
  the first field after `title:` in the YAML frontmatter block.

Description generation for each file: use the same heuristic as `generate_doc_index.py`
(first non-blank, non-heading line of the body). The human must review the dry-run
output and correct any generated descriptions before running `--write`.

### Enforcement strategy

A new commit-guardian check (`check_description_field.py`) validates that all staged
`.md` files in the three target directories have a non-empty `description:` frontmatter
field. It follows the same pattern as `scripts/commit_guardian/check_ac_schema.py` and
`check_paths_integrity.py`: reads staged files from stdin or as CLI args, parses YAML
frontmatter, exits non-zero with a list of violations.

The check is registered in the commit-guardian configuration. It does NOT block commits
of ticket files, skill SKILL.md files, or agent template files.

## Agent Contracts

### python-coder

- [ ] AC-1: Running `python scripts/backfill_descriptions.py --dry-run` prints every
  doc/ADR/component file that lacks a `description:` field and the proposed description
  value; it writes zero files.
- [ ] AC-2: Running `python scripts/backfill_descriptions.py --write` inserts
  `description: "<value>"` into the YAML frontmatter of each target file that lacked the
  field; all other frontmatter fields and the full body are unchanged.
- [ ] AC-3: After `--write` completes, running `--dry-run` again reports zero files
  needing backfill (idempotent: re-running `--write` a second time makes no further
  changes).
- [ ] AC-4: `scripts/commit_guardian/check_description_field.py` exits 0 when all
  staged target files have a non-empty `description:` field and exits non-zero with a
  per-file list of violations when any staged target file is missing the field.
- [ ] AC-5: `check_description_field.py` does NOT flag ticket files, skill SKILL.md
  files, or agent template files — only files under `docs/`, `docs/architecture/adrs/`,
  and `docs/architecture/components/`.
- [ ] AC-6: The backfill script is pure stdlib Python (no third-party imports).
- [ ] AC-7: The backfill script accepts a `--project-root <path>` flag so it can be
  run from outside the project root (consistent with other scripts in this repo).
- [ ] AC-8: `check_description_field.py` is registered in the commit-guardian configuration
  and runs on staged `.md` files following the `check_ac_schema.py` pattern.

**Delivers to test-writer:**
```json
{
  "backfill_script": "scripts/backfill_descriptions.py",
  "hook_script": "scripts/commit_guardian/check_description_field.py",
  "backfill_cli": {
    "flags": ["--dry-run", "--write", "--project-root"],
    "exit_codes": {"0": "success", "1": "paths.json not found or runtime error"}
  },
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

**Delivers to documentation-expert:**
```json
{
  "backfill_script": "scripts/backfill_descriptions.py",
  "hook_script": "scripts/commit_guardian/check_description_field.py",
  "integration_test": "run --dry-run after --write to confirm zero remaining files"
}
```

#### Implementation guidance

Module-level docstring (follow `roadmap_query.py` convention):
```python
"""
MODULE: backfill_descriptions
GOAL: One-time migration script that inserts a `description:` frontmatter field
      into every docs/ADR/component file that lacks one.
BUSINESS CONTEXT: Consistent description coverage lets knowledge_query.py and
      generate_doc_index.py use the structured field for all files rather than
      falling back to body-text parsing.
ARCHITECTURE: Walk target directories discovered from paths.json. For each .md
      file, parse YAML frontmatter. If `description` is absent or empty, generate
      a candidate from the first non-blank body line. In --dry-run mode, print
      the candidate. In --write mode, insert it immediately after the `title:`
      field. Pure stdlib.
"""
```

Key implementation points:

1. **Target directories** — resolve from `paths.json` (do not hardcode paths).
2. **Frontmatter parsing** — `re` to split at `---` pairs; no `yaml` import.
3. **Insertion position** — immediately after `title:` line; fallback: after opening `---`.
4. **Description candidate** — first non-blank, non-heading body line, truncated at 120 chars.
5. **Error handling** — per repo rules; malformed frontmatter prints warning and skips file.

**Hook (`check_description_field.py`)** — follow `check_ac_schema.py` pattern. Accept file
paths as CLI args, skip non-target paths silently, exit 1 with violation list on failure.

---

### test-writer

- [ ] AC-9: `unit_tests/test_backfill_descriptions.py` exists with tests covering:
  dry-run (no writes), write (inserts after title), skip (existing description unchanged),
  idempotent (second write = zero changes), excludes tickets, excludes skill files,
  description candidate skips headings, and missing paths.json exits cleanly.
- [ ] AC-10: `unit_tests/test_check_description_field.py` exists with tests covering:
  exits 0 when all staged docs have description, exits 1 when missing, ignores ticket
  files, ignores skill files.
- [ ] AC-11: All tests fail (RED) before python-coder runs and pass (GREEN) after. <!-- scope: integration -->

**Depends on python-coder:** script paths, CLI flags, exit codes, scope rules, and output
format from the Delivers-to block above.

#### Test specification

`unit_tests/test_backfill_descriptions.py`:
- `test_dry_run_prints_files_without_writing`
- `test_write_inserts_description_after_title`
- `test_write_skips_files_with_existing_description`
- `test_idempotent_second_write_makes_no_changes`
- `test_excludes_ticket_files`
- `test_excludes_skill_files`
- `test_description_candidate_skips_headings_and_blank_lines`
- `test_missing_paths_json_exits_cleanly`

`unit_tests/test_check_description_field.py`:
- `test_exits_0_when_all_staged_docs_have_description`
- `test_exits_1_when_staged_doc_missing_description`
- `test_ignores_ticket_files`
- `test_ignores_skill_files`

---

### documentation-expert

- [ ] AC-12: After backfill `--write`, `python scripts/generate_doc_index.py` runs without
  error and its output contains zero fallback-derived descriptions (every entry uses the
  frontmatter `description:` value). <!-- scope: integration -->
- [ ] AC-13: `docs/architecture/agent_knowledge_system.md` contains a `## Description Field
  Convention` section explaining the requirement and pointing to `check_description_field.py`.

**Depends on python-coder:** backfill script path and integration test command from the
Delivers-to block above.

#### Tasks

1. Run `python scripts/backfill_descriptions.py --dry-run` and review output.
2. Run `--write` to apply. Verify `generate_doc_index.py` runs cleanly after.
3. Add `## Description Field Convention` section to `docs/architecture/agent_knowledge_system.md`.

## AC Coverage

| AC    | Test | Implementation | Validated |
|-------|------|----------------|-----------|
| AC-1  |      |                |           |
| AC-2  |      |                |           |
| AC-3  |      |                |           |
| AC-4  |      |                |           |
| AC-5  |      |                |           |
| AC-6  |      |                |           |
| AC-7  |      |                |           |
| AC-8  |      |                |           |
| AC-9  |      |                |           |
| AC-10 |      |                |           |
| AC-11 |      |                |           |
| AC-12 |      |                |           |
| AC-13 |      |                |           |

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Risk & Safety

- Touches money? No.
- Touches data? The `--write` mode modifies doc frontmatter. This is the highest-risk
  part of this ticket. Mitigation: `--dry-run` must be reviewed before `--write` is
  executed; all changes go through PR review.
- Reversibility? High — all modified files are tracked in git. `git diff` shows every
  change. Any incorrect description can be corrected in a follow-up commit.
- Risk of regressions: the enforcement check (AC-4, AC-5) must not block commits of
  ticket or skill files. Scope-exclusion logic must be tested explicitly (see
  `test_ignores_ticket_files` and `test_ignores_skill_files`).
