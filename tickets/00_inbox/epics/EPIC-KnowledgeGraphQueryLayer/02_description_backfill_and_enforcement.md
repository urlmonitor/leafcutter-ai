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
ac_coverage: 0/8
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

## Acceptance Criteria

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
- [ ] AC-8: After `--write` completes, `python scripts/generate_doc_index.py` runs
  without error and its output contains zero fallback-derived descriptions (every entry
  uses the frontmatter `description:` value).

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      |                |           |
| AC-2 |      |                |           |
| AC-3 |      |                |           |
| AC-4 |      |                |           |
| AC-5 |      |                |           |
| AC-6 |      |                |           |
| AC-7 |      |                |           |
| AC-8 |      |                |           |

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

**Deliverable 1 — `scripts/backfill_descriptions.py`**

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

Implementation details:

1. **Target directories** — resolve from `paths.json` using the same surface
   resolution logic as `knowledge_query.py` (do not hardcode paths). Targets:
   `docs.root`, `docs.architecture_adrs`, `docs.architecture_components`.

2. **Frontmatter parsing** — extract the YAML block between the first `---` pair.
   Use `re` to split; do not import `yaml` (stdlib only). A minimal frontmatter
   reader is acceptable since we only need to detect presence/absence of `description:`
   and the position of `title:`.

3. **Insertion position** — insert `description: "<value>"` as the line immediately
   after the `title:` line in the raw frontmatter string. If `title:` is absent,
   insert as the first field after the opening `---`.

4. **Description candidate** — iterate body lines (after the closing `---`), skip
   blank lines and lines that start with `#`, return the first remaining line,
   stripped. Truncate at 120 characters.

5. **Dry-run output format**:
   ```
   [WOULD ADD] docs/architecture/adrs/ADR-001-self-hosting-boundary.md
     description: "Defines the boundary between the leafcutter package root..."
   
   Total: 7 files would be updated.
   ```

6. **Write output format**:
   ```
   [UPDATED] docs/architecture/adrs/ADR-001-self-hosting-boundary.md
   [SKIPPED] docs/architecture/agent_knowledge_system.md  (description already present)
   
   Total: 7 files updated, 4 skipped.
   ```

7. **Error handling** — wrap all `open()` calls per repo error-handling rules.
   On parse error (malformed frontmatter), print a warning and skip the file
   rather than aborting the entire run.

**Deliverable 2 — `scripts/commit_guardian/check_description_field.py`**

Follow the pattern of `check_ac_schema.py`. Accept file paths as CLI arguments.
For each file:
- If path is not under a target directory (`docs/`, `docs/architecture/adrs/`,
  `docs/architecture/components/`), skip silently.
- Parse YAML frontmatter.
- If `description` key is absent or its value is blank/null, record a violation.

Exit codes:
- 0: no violations.
- 1: one or more violations (print a list of `FAIL: <path> — missing description field`).

**Deliverable 3 — Register the hook**

Add `check_description_field.py` to the commit-guardian configuration so it runs
on staged `.md` files. Follow the registration pattern used by `check_ac_schema.py`
in `build_precommit.py` or the equivalent config file.

### test-writer

Create `unit_tests/test_backfill_descriptions.py`:

- `test_dry_run_prints_files_without_writing`: create temp dir with a doc file
  missing `description:`, run `--dry-run`, assert stdout contains file path and
  proposed value, assert file is unchanged.
- `test_write_inserts_description_after_title`: doc file with `title:` but no
  `description:`, run `--write`, assert `description:` appears on the line after
  `title:` in the written file.
- `test_write_skips_files_with_existing_description`: doc file already has
  `description:`, run `--write`, assert file is byte-for-byte unchanged.
- `test_idempotent_second_write_makes_no_changes`: run `--write` twice, assert
  output of second run shows zero updated files.
- `test_excludes_ticket_files`: place a file under `tickets/`, run script, assert
  it is not touched.
- `test_excludes_skill_files`: place a file named `SKILL.md` under
  `templates/skills/`, run script, assert it is not touched.
- `test_description_candidate_skips_headings_and_blank_lines`: body starts with
  blank line then `## Section`, then `Real sentence.`, assert candidate is
  `"Real sentence."`.
- `test_missing_paths_json_exits_cleanly`: no `paths.json`, assert `SystemExit`
  with message containing "paths.json not found".

Create `unit_tests/test_check_description_field.py`:

- `test_exits_0_when_all_staged_docs_have_description`: all input files have
  `description:`, assert exit code 0.
- `test_exits_1_when_staged_doc_missing_description`: one file missing `description:`,
  assert exit code 1 and file path in output.
- `test_ignores_ticket_files`: ticket file path passed as argument, assert exit 0
  (silently skipped).
- `test_ignores_skill_files`: SKILL.md path passed, assert exit 0.

### documentation-expert

After python-coder and test-runner sign off:

1. Run `python scripts/backfill_descriptions.py --dry-run` and review the output.
   Correct any generated descriptions that are inaccurate before the `--write` pass.
2. Run `python scripts/backfill_descriptions.py --write` to apply.
3. Verify `python scripts/generate_doc_index.py` runs cleanly after backfill.
4. Add a one-paragraph note to `docs/architecture/agent_knowledge_system.md` under
   a new `## Description Field Convention` section explaining the requirement and
   pointing to `check_description_field.py`.

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
