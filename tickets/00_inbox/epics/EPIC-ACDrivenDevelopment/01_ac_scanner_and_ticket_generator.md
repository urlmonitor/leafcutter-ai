---
title: "AC scanner and ticket generator"
status: todo
components:
  - ac-store
  - ticket-creation
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: true
files_touched:
  - scripts/ac_store/scan_ac_store.py
  - scripts/ac_store/generate_ticket_from_ac.py
  - tests/ac_store/test_scan_ac_store.py
  - tests/ac_store/test_generate_ticket_from_ac.py
  - templates/skills/ac-scanner/SKILL.md
  - docs/architecture/adrs/ADR-XXX-ac-store-as-authoritative-backlog.md
  - scripts/commit_guardian/check_no_print.py
  - tests/commit_guardian/test_check_no_print.py
agents:
  architect-review: needed
  adr-author: needed
  architecture-diagram-author: needed
  test-writer: needed
  python-coder: needed
  llm-expert: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_coverage: 0/9
---

# 01: AC scanner and ticket generator

## Actor / Goal

As the leafcutter-ai system, I want a script that scans the AC store,
identifies `work_status: todo` leaf-level ACs (L2 and L3), and generates a
valid, wired ticket file from each selected AC — so that the AC store can
drive the build backlog without a human writing tickets from scratch.

## Context

The AC store already holds 100 structured requirements in
`docs/acceptance-criteria/`. Each leaf-level AC (L2 or L3) carries everything
needed to produce a ticket: `criteria` (Gherkin), `assigned_agent`,
`doc_links` (maps to `files_touched`), `depends_on`, and
`estimated_complexity`. Nothing currently reads these files to produce
actionable work.

This ticket delivers the two core scripts:

1. `scan_ac_store.py` — walks `docs/acceptance-criteria/`, reads every YAML
   file, filters to those at level L2 or L3 with `work_status: todo` and
   `status: active`, resolves `depends_on` to determine which are unblocked
   (all their dependencies have `work_status: done`), and returns a
   priority-sorted list.

2. `generate_ticket_from_ac.py` — takes a single AC id (or path), reads its
   YAML, and writes a ticket file in the standard format to
   `tickets/00_inbox/TICKET-YYYYMMDD-<ac-id>.md` with:
   - `files_touched` populated from `doc_links[*].path` (filtered to local
     file paths).
   - `agents` map built from `assigned_agent` plus the canonical supporting
     agents (`test-writer`, `test-runner`, `pr-reviewer`, `commit`,
     `pull-request`).
   - `## Acceptance Criteria` section containing the AC's `criteria` field
     verbatim (Gherkin is already in the correct format).
   - `implemented_by` back-reference written into the source AC YAML
     immediately after the ticket is written (`implemented_by: [<ticket_path>]`).
   - Frontmatter `source_ac: <ac_id>` field to make the provenance explicit.

The `ac-scanner` skill wraps both scripts with the prose contract agents need
to invoke them correctly.

An ADR is required because this ticket establishes the AC store as the
authoritative backlog — a source-of-truth inversion that affects every future
ticket-creation workflow.

A component diagram is required to document the AC→scanner→generator→ticket
pipeline before any coding begins.

## Architecture Plan

### Diagrams

- `component` diagram at `docs/architecture/diagrams/ac-driven-pipeline.md`
  (parent: `docs/architecture/diagrams/agent_delivery_workflows.md`)

### ADRs

- `ADR: AC store as authoritative backlog (source-of-truth inversion)` — new
  ADR to be authored before coding begins. This decision affects all future
  ticket-creation flows and must be captured before implementation.

## Acceptance Criteria

```gherkin
# AC-1: Leaf scanner identifies todo, unblocked L2/L3 ACs

Given docs/acceptance-criteria/ contains 100 YAML files at levels L0–L3,
When scan_ac_store.py --level leaf --work-status todo is run,
Then only files with level L2 or L3 AND work_status: todo AND status: active
  are included in the output,
And files whose depends_on references include any AC with work_status != done
  are excluded (blocked),
And the output is sorted by estimated_complexity ascending, then by AC id
  ascending.

# AC-2: Generator produces a valid ticket from an AC YAML

Given AC file docs/acceptance-criteria/ac-store/ACS-100-structured-requirements/ACS-100a-1.yaml
  exists with work_status: todo, assigned_agent: python-coder, and non-empty criteria,
When generate_ticket_from_ac.py --ac ACS-100a-1 is run,
Then a ticket file is written to tickets/00_inbox/TICKET-<YYYYMMDD>-ACS-100a-1.md,
And the ticket frontmatter contains source_ac: ACS-100a-1,
And files_touched is populated from the AC's doc_links[*].path entries
  (filtering to paths that begin with a local directory, not http),
And the agents map contains assigned_agent set to needed and the canonical
  supporting agents (test-writer, test-runner, pr-reviewer, commit, pull-request)
  each set to needed,
And the ## Acceptance Criteria section contains the AC's criteria field verbatim.

# AC-3: Generator writes implemented_by back-reference into source AC

Given generate_ticket_from_ac.py --ac ACS-100a-1 has just written the ticket file,
When the source AC YAML is read back,
Then the implemented_by field contains the relative path of the newly-written ticket,
And no other fields in the AC YAML were modified.

# AC-4: Generator is idempotent — re-run with existing ticket does not duplicate

Given generate_ticket_from_ac.py --ac ACS-100a-1 was already run once and the ticket
  exists at tickets/00_inbox/TICKET-<YYYYMMDD>-ACS-100a-1.md,
When generate_ticket_from_ac.py --ac ACS-100a-1 is run again,
Then the script exits with a non-zero code and a message naming the existing file,
And no second ticket file is written,
And the source AC YAML's implemented_by list is unchanged (no duplicate appended).

# AC-5: Scanner JSON output is machine-consumable

Given scan_ac_store.py --level leaf --work-status todo --json is run,
When the output is parsed as JSON,
Then it conforms to the schema:
  { "ready": [{ "ac_id": str, "title": str, "assigned_agent": str,
                "estimated_complexity": str, "path": str }],
    "blocked": [{ "ac_id": str, "blocked_by": [str] }] }
And every ac_id in ready resolves to an existing YAML file.

# AC-6: Ticket passes ticket_frontmatter_guard without errors

Given generate_ticket_from_ac.py --ac ACS-100a-1 has been run,
When the ticket_frontmatter_guard pre-commit hook runs against the written ticket,
Then the hook exits 0 (no validation errors),
And requires_diagram and requires_adr fields are present in the frontmatter,
And ## Sign-offs contains exactly the agents whose map value is needed.

# AC-7: Leafcutter scripts use logging.debug, never print()

Given any .py file under scripts/ or tests/ in the leafcutter-ai repo,
When the file is staged for commit,
Then the check_no_print pre-commit hook scans the file's AST for print() calls,
And any print() call that is NOT inside a `if __name__ == "__main__":` block
  OR inside a function named `main` causes the hook to exit non-zero,
And the error message names the file, line number, and suggests using
  `logger.debug(...)` instead,
And the project documents the debug logging convention in CLAUDE.md under a
  "## Logging Convention" section (use `logging.getLogger(__name__)` +
  `logger.debug()`; never bare `print()` for diagnostic output).

# AC-8: check_no_print pre-commit hook is registered and enforced

Given scripts/commit_guardian/check_no_print.py exists,
When a developer stages a .py file containing `print("some debug info")`
  outside of a `main()` function or `if __name__ == "__main__":` guard,
Then the pre-commit hook exits non-zero and blocks the commit,
And the hook is registered in commit_guardian.json under hooks_manifest
  with id "check-no-print" and files pattern "\.py$",
And the hook has a corresponding config section in commit_guardian.json
  with exempt_patterns (e.g. click.echo, sys.stdout.write for CLI tools)
  and exempt_paths (e.g. scripts/commit_guardian/ itself for hook output).

# AC-9: [Phase 2] Customer codebase print-convention detection and hook generation

Given a consumer project has installed leafcutter-ai,
When the user invokes a "detect logging convention" command (future skill),
Then the system scans the customer's codebase for print/logging/debug patterns,
And presents the detected convention to the user (e.g. "your project uses
  structlog", "your project uses logging.getLogger", "your project uses print"),
And asks which convention to enforce going forward,
And on confirmation generates a project-specific pre-commit hook template
  under templates/skills/ that enforces the chosen convention,
And registers it in the consumer's .pre-commit-config.yaml via build.py.
```

## Agent Contracts

### architect-review

- [ ] AC-1: The component diagram spec (inputs, outputs, boundaries) is reviewed
  and approved before `generate_ticket_from_ac.py` is coded.
- [ ] AC-2: The ADR scope statement for "AC store as authoritative backlog" is
  validated against existing ADRs to confirm no collision.

**Delivers to adr-author:** Approved ADR scope statement.
**Delivers to python-coder:** Approved component boundary diagram and reviewed
script interface contracts.

**Depends on:** None (runs first).

### adr-author

- [ ] AC-3: ADR document authored at `docs/architecture/adrs/ADR-XXX-ac-store-as-authoritative-backlog.md`
  covering the source-of-truth inversion decision, alternatives considered
  (ticket-first vs AC-first), and consequences for the ticket-creation pipeline.

**Delivers to python-coder:** ADR path for `doc_links` entry in any generated
tickets that reference this architectural decision.

**Depends on architect-review:** Approved scope statement.

### architecture-diagram-author

- [ ] AC-4: Component diagram written at
  `docs/architecture/diagrams/ac-driven-pipeline.md` showing: AC YAML store →
  `scan_ac_store.py` → `generate_ticket_from_ac.py` → ticket file → `implemented_by`
  back-write → existing build pipeline.

**Depends on architect-review:** Approved diagram spec.

### test-writer

- [ ] AC-5: `tests/ac_store/test_scan_ac_store.py` written covering: leaf filter,
  blocked-AC exclusion, JSON schema conformance, empty-store edge case.
- [ ] AC-6: `tests/ac_store/test_generate_ticket_from_ac.py` written covering:
  ticket creation, back-reference write, idempotency guard, frontmatter guard
  pass assertion.

**Depends on architect-review:** Approved interface contracts for both scripts.

### python-coder

- [ ] AC-7: `scripts/ac_store/scan_ac_store.py` implemented per the interface
  contract: `--level`, `--work-status`, `--json` flags; depends_on resolution;
  sorted output; exits 0 on success, 1 on schema errors.
- [ ] AC-8: `scripts/ac_store/generate_ticket_from_ac.py` implemented per the
  interface contract: `--ac` flag; ticket writing; back-reference write;
  idempotency guard; frontmatter guard call.
- [ ] AC-9: `templates/skills/ac-scanner/SKILL.md` written as the prose contract
  for both scripts (invocation, output schema, error codes).

**Depends on test-writer:** Tests must exist before implementation begins.
**Depends on adr-author:** ADR path known so it can be wired into generated tickets.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |
| AC-8 | | | |
| AC-9 | | | deferred to phase_2 |

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [ ] architecture-diagram-author
- [ ] test-writer
- [ ] python-coder
- [ ] llm-expert
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Read `docs/acceptance-criteria/index.yaml` and sample 3–4 leaf ACs to
  confirm the interface contract for `scan_ac_store.py` (field names used,
  level values present, work_status enum values).
- [ ] Draft the component diagram spec (boxes and arrows, no Mermaid yet —
  that is `architecture-diagram-author`'s job).
- [ ] Confirm that `doc_links[*].path` is the correct field for
  `files_touched` extraction (check 5 ACs to verify the field is consistently
  populated with local paths).
- [ ] Produce the ADR scope statement with: decision to record, context,
  alternatives considered, consequences. Hand off to `adr-author`.

### adr-author

- [ ] Write the ADR at `docs/architecture/adrs/ADR-XXX-ac-store-as-authoritative-backlog.md`
  using the scope statement from `architect-review`.
- [ ] Follow the existing ADR numbering convention (check the highest current
  ADR number in `docs/architecture/adrs/` before choosing the `XXX` number).
- [ ] Ensure the ADR references `docs/acceptance-criteria/index.yaml` and the
  three domain folders as the current state of the AC store.

### architecture-diagram-author

- [ ] Write the Mermaid component diagram at
  `docs/architecture/diagrams/ac-driven-pipeline.md`.
- [ ] Parent link: reference
  `docs/architecture/diagrams/agent_delivery_workflows.md` in the diagram's
  frontmatter `parent:` field.

### test-writer

- [ ] Create `tests/ac_store/__init__.py` if the directory does not exist.
- [ ] Write `tests/ac_store/test_scan_ac_store.py`:
  - `test_leaf_filter_excludes_l0_l1`: fixture with L0, L1, L2 ACs; assert
    only L2 returned.
  - `test_blocked_ac_excluded_when_dep_not_done`: AC with depends_on pointing
    to a todo AC; assert it is in `blocked` not `ready`.
  - `test_unblocked_ac_included_when_dep_done`: AC with depends_on pointing to
    a done AC; assert it is in `ready`.
  - `test_json_output_schema`: run with `--json`; validate against schema
    definition in AC-5.
  - `test_empty_store_returns_empty_ready`: empty fixture dir; assert ready=[].
- [ ] Write `tests/ac_store/test_generate_ticket_from_ac.py`:
  - `test_ticket_written_with_correct_fields`: run generator; assert ticket
    exists; parse frontmatter; check source_ac, files_touched, agents keys.
  - `test_implemented_by_back_reference`: run generator; read source AC YAML;
    assert implemented_by contains the ticket path.
  - `test_idempotency_guard`: run generator twice; assert second run exits non-zero
    and does not write a second file.
  - `test_frontmatter_guard_passes`: run generator; invoke
    `scripts/commit_guardian/check_ticket_frontmatter.py` (or equivalent guard)
    on the written ticket; assert exit 0.

### python-coder

- [ ] Implement `scripts/ac_store/scan_ac_store.py` with:
  - CLI: `--level {leaf,all}`, `--work-status {todo,done,all}`,
    `--json`, `--ac-root <path>` (default: `docs/acceptance-criteria/`).
  - Walk all YAML files under `--ac-root`. Parse each with `yaml.safe_load`.
  - Filter: `level in {L2, L3}` AND `work_status == todo` AND `status == active`.
  - Dependency resolution: for each AC in `depends_on`, look up its file by id;
    if any dep has `work_status != done`, classify the current AC as blocked.
  - Sort ready ACs: `estimated_complexity` ascending (S < M < L < XL), then
    `id` ascending.
  - Human output: two sections READY and BLOCKED, matching ticket-prioritizer
    style.
  - JSON output: schema from AC-5.
  - Exits 0 on success, 1 on unreadable YAML (with per-file diagnostic), 2
    on dependency cycle (with cycle description).
  - Error handling: all YAML reads wrapped in `try/except yaml.YAMLError`.
  - Docstring: module-level + function-level, following project style.
- [ ] Implement `scripts/ac_store/generate_ticket_from_ac.py` with:
  - CLI: `--ac <ac_id>`, `--ac-root <path>`, `--tickets-root <path>`,
    `--dry-run` (print ticket body, don't write).
  - AC lookup: search `--ac-root` recursively for `id: <ac_id>`.
  - `files_touched` extraction: `doc_links[*].path` entries where the value
    starts with a letter (local path), not `http`.
  - `agents` map: `assigned_agent: needed` + canonical support agents at
    `needed`. `sql-coder: not_needed` unless `assigned_agent` is `sql-coder`.
  - Ticket body: `## Acceptance Criteria` section containing `criteria` verbatim.
  - Frontmatter: all required fields including `source_ac: <ac_id>`,
    `requires_diagram: false`, `requires_adr: false`.
  - Idempotency guard: search `--tickets-root` for any file with
    `source_ac: <ac_id>` in frontmatter; if found, exit non-zero.
  - Back-reference write: append ticket path to `implemented_by` in source AC
    YAML using `yaml.safe_load` / `yaml.dump` round-trip.
  - Error handling: `try/except` on all file I/O; `try/except yaml.YAMLError`
    on all YAML parsing.

### llm-expert

- [ ] Write `templates/skills/ac-scanner/SKILL.md` with:
  - `name: ac-scanner`
  - `allowed-tools: Bash, Read`
  - Purpose, Invocation (both scripts with all flags), Output schema (JSON),
    Error codes, Integration with `/build-ac` (forward reference to ticket 04).

**Depends on python-coder:** Needs the script CLI interfaces to be finalized
before writing the prose contract.

## Risk & Safety

- Touches money? No.
- Touches data? Writes new files (ticket + AC back-reference). The
  idempotency guard prevents accidental duplication. The AC YAML round-trip
  uses `yaml.safe_load` / `yaml.dump` — the dump will reformat YAML but
  preserve all field values.
- YAML round-trip risk: `yaml.dump` may reorder fields or change quoting style
  in the AC file. Mitigation: write only the `implemented_by` field using a
  targeted Edit (not a full dump) to minimise diff noise in the AC store.
  Python-coder should use `ruamel.yaml` (if available) or a targeted
  append-only write to the `implemented_by` list line rather than a full
  round-trip.
- Reversibility? The ticket can be deleted and the `implemented_by` entry
  removed from the AC YAML. Both are single-file operations with no
  downstream side effects until `/build-ac` (ticket 04) is invoked.
