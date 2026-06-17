---
title: "Reconcile precommit-autofix.json to documented schema with blocking_hook_ids"
status: in_progress
components:
  - precommit_hooks
  - commit_guardian
  - build_pipeline
created: 2026-06-17
depends_on: []
priority: high
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - .claude/precommit-autofix.json
  - templates/scripts/precommit-autofix.json
ac_traceability:
  - BO-210a
  - BO-210a-1
  - BO-210a-2
  - BO-210a-1-i
ac_coverage: 4/4
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
user_facing_surface: null
---

# 01: Reconcile precommit-autofix.json to documented schema with blocking_hook_ids

## Actor / Goal

In order to enable the originator re-dispatch path (ticket 04), we need a
populated `precommit-autofix.json` that conforms to its documented schema and
carries a single `blocking_hook_ids` gating array, so that the downstream
re-dispatch logic has an authoritative list of which hooks gate a commit and
how each is routed.

## Context

The current `.claude/precommit-autofix.json` is a dead stub containing only
`{"routes":{}}`. The `precommit-autofix` SKILL.md documents a richer schema
with `defaults`, `commit_review`, and `rules[]` sections, but the deployed
config never matched it. This ticket reconciles both sides.

This ticket is a prerequisite for ticket 04 (originator re-dispatch) which
reads `blocking_hook_ids` to decide which hooks trigger originator re-dispatch
vs the generic mechanical route.

### Relevant architecture

- `templates/skills/precommit-autofix/SKILL.md` — documents the config schema
- `.claude/precommit-autofix.json` — deployed consumer config (currently a dead stub)
- Template source location: the packaged template under `templates/scripts/`
  (exact path TBD by python-coder reading the build.py source; follow the
  same path-discovery convention used for `commit_guardian.json`)
- `docs/build-pipeline.md` — describes the template-to-deploy round-trip

### Blocking hook ids (from AC BO-210a-2)

The `blocking_hook_ids` array must contain:
`check-complexity`, `check-docstrings`, `check-exception-handling`,
`check-file-size`, `check-ac-schema`, `check-ac-limits`,
`check-contract-shrinking`

### Delivers to ticket 04

The populated `blocking_hook_ids` array in `precommit-autofix.json` is the
input the originator re-dispatch logic (ticket 04) reads. AC BO-210a-2
`delivers_to: llm-expert` with contract: "A top-level blocking_hook_ids JSON
array that the re-dispatch skill logic reads to decide which failures trigger
originator re-dispatch."

## AC References

- Implements BO-210a (config populated to documented schema with single gating list)
- Implements BO-210a-1 (rewritten from dead stub to defaults/commit_review/rules shape)
- Implements BO-210a-2 (blocking_hook_ids array is sole authority on gating hooks)
- Implements BO-210a-1-i (packaged template source matches deployed config)

## Acceptance Criteria

- [x] AC-1 (BO-210a-1): The deployed `.claude/precommit-autofix.json` contains a
  `defaults` section (model + agent), a `commit_review` section (enabled flag,
  model, agent), and a `rules` list — the empty `routes` object is gone and no
  field outside the documented schema exists.
- [x] AC-2 (BO-210a-2): The config contains exactly one `blocking_hook_ids` array
  listing all seven gating hook ids: `check-complexity`, `check-docstrings`,
  `check-exception-handling`, `check-file-size`, `check-ac-schema`,
  `check-ac-limits`, `check-contract-shrinking`. No other field independently
  determines whether a hook gates a commit.
- [x] AC-3 (BO-210a-1-i): The packaged template source under `templates/scripts/`
  contains the same `defaults`, `commit_review`, `rules`, and `blocking_hook_ids`
  content as the deployed config. A fresh consumer install receives the populated
  config, not the empty stub.
- [x] AC-4 (BO-210a): The build.py round-trip verifies parity between the deployed
  config and the template source — neither diverges after reconcile.

## AC Coverage

| AC | AC ID | Test | Implementation | Validated |
|----|-------|------|----------------|-----------|
| AC-1 | BO-210a-1 | | Rewrote `.claude/precommit-autofix.json` with defaults/commit_review/rules; removed routes key | |
| AC-2 | BO-210a-2 | | Added `blocking_hook_ids` array with all 7 gating hook ids as sole authority | |
| AC-3 | BO-210a-1-i | | Created `templates/scripts/precommit-autofix.json`; updated `build_config_scaffolds.py` to load from it; diff confirms byte-identical parity | |
| AC-4 | BO-210a | | build_config_scaffolds loads template at build time; `diff` of both files shows no divergence | |

## Implementation Tasks

- [x] Read `templates/skills/precommit-autofix/SKILL.md` to extract the exact
  documented schema fields (`defaults`, `commit_review`, `rules[]`).
- [x] Read `scripts/build.py` to find the template source path for
  `precommit-autofix.json` (look for how `commit_guardian.json` template path
  is referenced as a model).
- [x] Rewrite `.claude/precommit-autofix.json` with:
  - `defaults` section (model: haiku tier, agent: generic)
  - `commit_review` section (enabled: true, model: sonnet tier, agent: commit-reviewer)
  - `rules` list (per-hook overrides for the documented hook ids)
  - `blocking_hook_ids` array with all seven hook ids listed above
  - Remove the empty `routes` key
- [x] Apply the same change to the packaged template source under `templates/scripts/`
  (never edit one side only).
- [x] Run the build.py round-trip to verify parity between deployed and template.
- [x] Validate the result parses as valid JSON conforming to the schema.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Yes — both files are JSON config; revert via git.
- Template parity: must edit both the deployed `.claude/precommit-autofix.json`
  AND the template source in a single PR so no install sees a mismatch.
- Shell convention: all Bash commands in any edited template block must be
  single simple invocations (no `&&`, `;`, `||`, or `cd`-prefixed chains).

## Sign-offs
- [x] python-coder — 2026-06-17 12:00
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-17 12:00 — python-coder (status: ok)
feedback-id: fb_2026-06-17_1d546f22
completion_manifest:
  deployed_config_written: true
  template_source_created: true
  build_config_scaffolds_updated: true
  json_parity_verified: true
  blocking_hook_ids_correct: true
  ruff_clean: true
Created `templates/scripts/precommit-autofix.json` as the canonical template source containing the full documented schema (`defaults`, `commit_review`, `blocking_hook_ids`, `rules`). Wrote the same content to `.claude/precommit-autofix.json` (gitignored deployed config). Updated `build_config_scaffolds.py` to load the scaffold content from the template file at build time instead of using an inline stub, establishing the build.py round-trip parity required by AC-4. `diff` of both JSON files confirms byte-identical parity; ruff check passes; all 7 blocking hook IDs are present.
