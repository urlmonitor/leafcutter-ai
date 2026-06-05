---
title: "ACS-400: AC Store Governance — write-lock criteria fields, audit trail, build deployment"
status: todo
components:
  - ac-store
  - infrastructure
  - build_pipeline
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/24
source_acs:
  - ACS-400
  - ACS-400a
  - ACS-400a-1
  - ACS-400a-2
  - ACS-400a-3
  - ACS-400a-3-i
  - ACS-400b
  - ACS-400b-1
  - ACS-400b-2
  - ACS-400b-3
  - ACS-400b-3-i
  - ACS-400c
  - ACS-400c-1
  - ACS-400c-2
  - ACS-400c-2-i
  - ACS-400d
  - ACS-400d-1
  - ACS-400d-2
  - ACS-400d-2-i
  - ACS-400e
  - ACS-400e-1
  - ACS-400e-1-i
  - ACS-400e-2
  - ACS-400e-3
ac_path: docs/acceptance-criteria/ac-store/ACS-400-ac-governance/
files_touched:
  - scripts/commit_guardian/check_ac_governance.py
  - scripts/commit_guardian/commit_guardian.json
  - templates/commit-guardian/check_ac_governance.py
  - templates/commit-guardian/commit_guardian.json
  - templates/CLAUDE.md.template
  - unit_tests/commit_guardian/test_check_ac_governance.py
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
complexity: standard
---

# ACS-400: AC Store Governance — write-lock criteria fields, audit trail, build deployment

## Actor / Goal

As the product team, we need the AC store's requirement-defining fields
(`criteria`, `title`, `req_status`, `depends_on`) to be mechanically
write-locked to authorized agents only (product-owner-v3, business-analyst-v3,
it-po-v3, and the human user), so that implementation agents can never silently
rewrite what they are being measured against.

## Context

The AC store is the authoritative definition of "done" for every piece of work
in the system. If an implementation agent can rewrite `criteria` without
detection, the team loses the trustworthy source of truth that makes
ticket-driven development tractable.

Three enforcement surfaces are needed:

1. **Pre-commit hook** (`check_ac_governance.py`): catches unauthorized field
   changes at commit time before they reach the repository.
2. **Build deployment**: the hook and governance rules are automatically
   installed into every consumer project via `build.py` / the templates
   mechanism — no manual opt-in required.
3. **Agent instruction injection**: the `CLAUDE.md.template` carries the
   governance rules so every agent in every consumer project inherits them
   at invocation time.

All ACs are pre-written at:
`docs/acceptance-criteria/ac-store/ACS-400-ac-governance/`

## Agent Contracts

### test-writer

Write the full test suite **before** `python-coder` begins implementation.
All tests must pass on the final implementation.

- [ ] AC-1: `unit_tests/commit_guardian/test_check_ac_governance.py` exists and
  covers the authorized-agent allow path (ACS-400a-1): given a staged AC YAML
  with a new `criteria` field and `origin_agent: business-analyst-v3`, the
  hook exits 0 and produces no blocking output.
- [ ] AC-2: Test covers the modification allow path (ACS-400a-2): given a staged
  diff where `criteria` changed and the committer is `it-po-v3`, the hook exits
  0.
- [ ] AC-3: Test covers the unauthorized agent block path (ACS-400a-3): given
  `criteria` changed by `python-coder`, the hook exits 1 and stdout contains the
  agent name, the file path, and the phrase "criteria field may only be written
  by requirement authors".
- [ ] AC-4: Test covers the human-user allow path (ACS-400a-3-i): given
  `origin_agent: BrainCandy` (not in `config/agent_registry.json`), the hook
  exits 0 — unknown identities are treated as human users.
- [ ] AC-5: Test covers the implementation-agent progress fields allow path
  (ACS-400b-1, ACS-400b-2): `python-coder` changing only `work_status`,
  `implemented_by`, or `covered_by` — hook exits 0.
- [ ] AC-6: Test covers the protected field rejection path (ACS-400b-3): an
  implementation agent changes `title` or `req_status` or `depends_on` —
  hook exits 1 and the error lists each modified protected field.
- [ ] AC-7: Test covers the mixed-commit rejection path (ACS-400b-3-i): same
  commit has `work_status` changed (allowed) AND `criteria` changed (blocked) —
  hook exits 1 for the criteria violation, and the error message acknowledges
  both changed fields.
- [ ] AC-8: Test covers the `origin_agent` audit check (ACS-400c-1): a new AC
  YAML file staged without an `origin_agent` field — hook exits 1 with "new AC
  file requires origin_agent to identify the criteria author".
- [ ] AC-9: Test covers the `amended_by` audit check (ACS-400c-2): an existing
  AC has `criteria` changed in the staged diff but `amended_by` list is
  identical to HEAD — hook exits 1 with "criteria was modified but amended_by
  was not updated".
- [ ] AC-10: Test covers the stale `amended_by` check (ACS-400c-2-i): the
  `amended_by` list exists but has no new entries compared to HEAD — hook exits
  1 and the error distinguishes "no new entry" from "list is empty".
- [ ] AC-11: Test covers the fail-open path (ACS-400e-1-i): the hook encounters
  a YAML parse exception — exits 0, no stdout, diagnostic message on stderr.
- [ ] AC-12: Test covers the no-AC-store early-exit path (ACS-400d-2-i): no
  `docs/acceptance-criteria/` directory exists — hook exits 0 in under 100 ms
  without creating any directories.
- [ ] AC-13: Test covers the staged-files-only scope (ACS-400e-2): 100 AC YAML
  files on disk but only 2 staged — hook parses only 2 files (assert via a
  counter or mock).
- [ ] AC-14: Test covers the non-AC-file neutrality (ACS-400e-3): commit
  includes `scripts/build.py` (valid change) plus an AC YAML with unauthorized
  `criteria` change — hook exit 1 message references only the AC file, not
  `build.py`.

**Delivers to python-coder:** Verified test suite that `check_ac_governance.py`
must satisfy before `test-runner` can sign off.

### python-coder

Implement three deliverables. Tests written by `test-writer` must pass.

- [ ] AC-15: `scripts/commit_guardian/check_ac_governance.py` exists, follows
  the same module-docstring + DECISION HISTORY + Google-style docstring
  conventions as `check_ac_limits.py`, and passes all 14 test-writer ACs
  (AC-1 through AC-14).
- [ ] AC-16: The hook reads the agent identity from `config/agent_registry.json`
  (not hard-coded): any string not in the registry is treated as a human user
  (ACS-400a-3-i). The registry is loaded once per hook invocation (not on every
  file iteration).
- [ ] AC-17: Protected fields (`criteria`, `title`, `req_status`, `depends_on`)
  and open fields (`work_status`, `implemented_by`, `covered_by`) are declared
  as named constants at module level (not inline strings), so future additions
  require a one-line change (ACS-400b-3 IT requirement).
- [ ] AC-18: Field comparison uses YAML-level comparison (load both staged and
  HEAD versions with PyYAML `safe_load`), not raw text diff, to avoid false
  positives from whitespace or formatting changes (ACS-400c-2 IT requirement).
- [ ] AC-19: Blocked commit output: stdout receives a JSON block decision
  `{"decision": "block", "reason": "..."}` matching the PreToolUse hook
  contract; stderr receives diagnostic detail. The `reason` string contains
  agent identity, file path, violated rule, and authorized agents list
  (ACS-400e-1 IT requirements).
- [ ] AC-20: The entire `main()` body is wrapped in `try/except Exception` that
  exits 0 on any unexpected error (fail-open per ACS-400e-1-i). The exception
  type and message are printed to stderr with a `[check-ac-governance]` prefix.
- [ ] AC-21: `scripts/commit_guardian/commit_guardian.json` gains a new entry in
  `hooks_manifest.hooks` for `check-ac-governance` following the same pattern as
  the existing `check-ac-tree-limits` and `check-ac-schema` entries:
  - `files` pattern: `^docs/acceptance-criteria/.*\\.yaml$`
  - `stages`: `["pre-commit"]`
  - `pass_filenames: false`
  - `_comment` referencing the ACS-400 family

**Delivers to test-runner:** Implemented `check_ac_governance.py` satisfying
the test suite.

**Delivers to pr-reviewer:** Updated `commit_guardian.json` with the hook
registered in `hooks_manifest.hooks`.

**Depends on test-writer:** Tests (AC-1 through AC-14) must exist before
implementation begins.

### python-coder (template deployment — can run in parallel with hook implementation)

Deploy the hook into the templates so `build.py` propagates it automatically
to every consumer project.

- [ ] AC-22: `templates/commit-guardian/check_ac_governance.py` is a verbatim
  copy of the final `scripts/commit_guardian/check_ac_governance.py` (ACS-400d
  deliverable: governance rules travel with the package). It is deployed to
  consumer projects by `build_commit_guardian()` in `build_phases.py` via the
  existing template-copy mechanism.
- [ ] AC-23: `templates/commit-guardian/commit_guardian.json` gains the same
  `check-ac-governance` entry in `hooks_manifest.hooks` as the source
  `scripts/commit_guardian/commit_guardian.json` (ACS-400d-2: no opt-in
  required; hook registered automatically alongside `check-ac-schema` and
  `check-test-ac-tags`).
- [ ] AC-24: `templates/CLAUDE.md.template` gains a new section headed
  `## AC Store — Write-Access Rules` that contains:
  - The list of authorized agents for protected fields:
    `product-owner-v3`, `business-analyst-v3`, `it-po-v3`, human user
  - The list of protected fields: `criteria`, `title`, `req_status`, `depends_on`
  - The list of open fields: `work_status`, `implemented_by`, `covered_by`
  - A one-sentence statement that violation blocks the commit (ACS-400d-1 IT
    requirement: human-readable and concise, suitable for an agent's context window).
  The section must not break existing `{{config.*}}` template placeholder
  resolution when `build.py` compiles the template (ACS-400d-1 IT requirement:
  "Must not break existing CLAUDE.md content").

**Delivers to pr-reviewer:** Deployed templates ready for consumer-project
propagation.

**Depends on test-writer:** Template deployment can proceed in parallel with
hook implementation; tests only gate `scripts/` deliverables.

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
| AC-14 |      |                |           |
| AC-15 |      |                |           |
| AC-16 |      |                |           |
| AC-17 |      |                |           |
| AC-18 |      |                |           |
| AC-19 |      |                |           |
| AC-20 |      |                |           |
| AC-21 |      |                |           |
| AC-22 |      |                |           |
| AC-23 |      |                |           |
| AC-24 |      |                |           |

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Risk & Safety

- Touches money? No.
- Touches data? No. The hook reads AC YAML files from the index; it never writes them.
- Reversibility? The hook is a standalone Python script added to
  `commit_guardian.json`. Removing it requires deleting the file and removing its
  entry from `hooks_manifest.hooks` — a single-commit rollback.
- Fail-open guarantee: any unexpected error in the hook exits 0, so no legitimate
  commit is ever blocked by a hook crash (ACS-400e-1-i).
- Risk of regressions: low for existing workflows. The hook only fires on
  `docs/acceptance-criteria/**/*.yaml` staged files. Projects without that
  directory exit early in under 100 ms (ACS-400d-2-i).
- The `CLAUDE.md.template` addition is a pure append with no placeholder tokens,
  so it does not interact with the existing `{{config.*}}` resolution path.
