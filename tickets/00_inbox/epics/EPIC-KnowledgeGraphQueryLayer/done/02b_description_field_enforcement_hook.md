---
title: "Add check_description_field.py commit-guardian hook and register it"
status: done
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
ac_coverage: 5/5
files_touched:
  - templates/scripts/commit_guardian/check_description_field.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - unit_tests/test_check_description_field.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
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

- [x] AC-1: `scripts/commit_guardian/check_description_field.py` exits 0 when all
  staged target files have a non-empty `description:` field and exits non-zero with a
  per-file list of violations when any staged target file is missing the field. <!-- signed: python-coder -->
- [x] AC-2: `check_description_field.py` does NOT flag ticket files, skill SKILL.md
  files, or agent template files — only files under `docs/`, `docs/architecture/adrs/`,
  and `docs/architecture/components/`. <!-- signed: python-coder -->
- [x] AC-3: `check_description_field.py` is registered in the commit-guardian configuration
  and runs on staged `.md` files following the `check_ac_schema.py` pattern. <!-- signed: python-coder -->

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

- [x] AC-4: `unit_tests/test_check_description_field.py` exists with tests covering:
  exits 0 when all staged docs have description, exits 1 when missing, ignores ticket
  files, ignores skill files. <!-- signed: test-writer -->
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
| AC-1  |      | check_description_field.py exits 0 on valid docs, 1 on missing description | ok — 2026-06-05 |
| AC-2  |      | Scope filter: only docs/ targeted; tickets/, templates/ silently skipped | ok — 2026-06-05 |
| AC-3  |      | Registered in commit_guardian.json hooks_manifest with files: ^docs/.*\\.md$ | ok — 2026-06-05 |
| AC-4  | test_check_description_field.py — 4 stubs written, all RED |                |           |
| AC-5  | All 4 tests GREEN after implementation; no regressions in 12-test suite |                |           |

## Sign-offs

- [x] test-writer — 2026-06-05 14:00
- [x] python-coder — 2026-06-05 14:30
- [x] test-runner — 2026-06-05 14:45
- [x] pr-reviewer — 2026-06-05 15:00
- [x] commit — 2026-06-05 15:15
- [x] pull-request — 2026-06-05 15:30

## Comments

### 2026-06-05 15:30 — pull-request (status: ok)
feedback-id: fb_2026-06-05_d679fce1
completion_manifest:
  branch_pushed: true
  pr_exists: true
Branch EPIC-KnowledgeGraphQueryLayer pushed to origin. Commit 121e69a added to existing PR #63 (https://github.com/urlmonitor/leafcutter-ai/pull/63). Epic uses one PR per branch; no new PR needed.

### 2026-06-05 15:15 — commit (status: ok)
feedback-id: fb_2026-06-05_ac6f42cc
completion_manifest:
  commit_created: true
  files_staged_correctly: true
  no_cross_ticket_contamination: true
Commit 121e69a on EPIC-KnowledgeGraphQueryLayer branch. 4 files, 425 insertions, 5 deletions. Staged files: templates/scripts/commit_guardian/check_description_field.py (new), templates/scripts/commit_guardian/commit_guardian.json (modified), unit_tests/test_check_description_field.py (new), tickets/.../02b_description_field_enforcement_hook.md (ticket). No cross-ticket contamination. PRE_COMMIT_ALLOW_NO_CONFIG=1 used because .pre-commit-config.yaml is a build output in .gitignore.

### 2026-06-05 15:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_a4ce43da
completion_manifest:
  code_quality_ok: true
  error_handling_compliant: true
  docstrings_present: true
  decision_history_present: true
  scope_exclusions_correct: true
  tests_cover_acs: true
Code review passed. check_description_field.py is clean: module docstring with MODULE/GOAL/BUSINESS CONTEXT/ARCHITECTURE fields; OSError caught and logged in _read_file; subprocess.CalledProcessError caught and logged in _get_staged_md_files; no bare excepts; Google-style docstrings on all functions; type annotations throughout; Decision History block at bottom. Exception handling on pure functions removed (Rule 4). Registration in commit_guardian.json correct. AC-1, AC-2, AC-3 marked ok.

### 2026-06-05 14:45 — test-runner (status: ok)
feedback-id: fb_2026-06-05_01995914
completion_manifest:
  all_tests_green: true
  no_regressions: true
  ac5_integration_satisfied: true
Ran 4 tests in test_check_description_field.py — all PASSED. Also ran 12-test combined suite (02b + 02a backfill tests) — all 12 PASSED. No regressions detected. AC-5 integration criterion satisfied: tests were RED before python-coder and GREEN after.

### 2026-06-05 14:30 — python-coder (status: ok)
feedback-id: fb_2026-06-05_067e992b
completion_manifest:
  ac1_hook_exits_correctly: true
  ac2_scope_exclusion_works: true
  ac3_hook_registered: true
  tests_green: true
  files_touched_match_plan: true
Created templates/scripts/commit_guardian/check_description_field.py following check_ac_schema.py pattern: positional CLI args, frontmatter parsing via re, scope filtering (docs/ target, tickets/templates/ excluded), exit 0/1 with FAIL: <path> — missing description field output. Registered in templates/scripts/commit_guardian/commit_guardian.json hooks_manifest under id check-description-field targeting ^docs/.*\\.md$ with pass_filenames: true. All 4 unit tests GREEN. Updated files_touched to reflect actual template paths (gitignore excludes scripts/commit_guardian/ build outputs).

### 2026-06-05 14:00 — test-writer (status: ok)
feedback-id: fb_2026-06-05_d89e270a
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
Created unit_tests/test_check_description_field.py with 4 test stubs: test_exits_0_when_all_staged_docs_have_description, test_exits_1_when_staged_doc_missing_description, test_ignores_ticket_files, test_ignores_skill_files. All 4 tests confirmed RED (exit 2 — hook script does not exist yet). AC-4 checkbox flipped in Agent Contracts.

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only hook, only inspects staged doc files.
- Reversibility? Fully reversible — remove hook from commit_guardian.json.
- Risk of regressions: the enforcement check must not block commits of ticket or
  skill files. Scope-exclusion logic must be tested explicitly (see
  `test_ignores_ticket_files` and `test_ignores_skill_files`).
