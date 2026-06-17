---
title: "Wire diagram_types.json / doc_types.json as the real SSOT (deploy + fix validator path resolution)"
status: todo
components:
  - precommit_hooks
  - build_pipeline
created: 2026-06-17
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/scripts/build_phases.py
  - leafcutter-ai/templates/scripts/commit_guardian/diagram_type_validators.py
  - leafcutter-ai/templates/commit-guardian/diagram_type_validators.py
  - leafcutter-ai/templates/scripts/commit_guardian/doc_type_validators.py
  - leafcutter-ai/templates/commit-guardian/doc_type_validators.py
  - leafcutter-ai/tests/commit_guardian/test_diagram_type_ssot.py
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Wire diagram_types.json / doc_types.json as the real SSOT (deploy + fix validator path resolution)

## Actor / Goal
In order for `diagram_types.json` (and `doc_types.json`) to actually be the single
source of truth they were declared to be, we need `build.py` to deploy them into the
consumer tree AND the validators to resolve their path correctly, so that adding or
renaming a diagram/doc type in one JSON file takes effect at commit time without
editing the duplicated enum lists in `commit_guardian.json`.

## Context
Discovered while fixing GE-103 / GE-105 (PR #91). EPIC-EmbeddedArchDiagramsHardening
ticket 07 declared `leafcutter/config/diagram_types.json` the SSOT for the
`diagram_type` enum and deprecated the `DOC_FM_DIAGRAM_TYPE_VALUES` constant. The same
pattern was applied to `doc_types.json` for the `type` enum (`doc_type_validators.py`).
**Neither migration actually took effect**, for two compounding reasons:

1. **The JSON is never deployed.** `build.py` / `build_phases.py` has zero references to
   `diagram_types.json` or `doc_types.json`. They exist only in the dev source clone, so
   no consumer `.leafcutter/` tree ever receives them.
2. **The path resolution is wrong even in dev.** Both `diagram_type_validators.py` and
   `doc_type_validators.py` resolve the JSON at
   `Path(__file__).resolve().parents[2] / "leafcutter" / "config" / "<file>.json"`, which
   evaluates to `<repo_root>/leafcutter/config/...`. The file actually lives at
   `<repo_root>/config/...`. The working hook `check_doc_types_agents.py` uses the correct
   pattern (`git rev-parse --show-toplevel` → `repo_root / "leafcutter" / "config"` in a
   consumer, or `repo_root / "config"` in this self-hosted repo) — but the validators do not.

Because both fail, the validators silently fall back to the stale hardcoded enum in
`commit_guardian.json`. GE-105 patched that fallback list as a symptom fix; this ticket
fixes the root cause so the JSON is the live source.

This affects BOTH validators identically — fix them together.

## AC References
- Relates to GE-103 (docs/acceptance-criteria/guardrail-engine/GE-100-code-quality-hooks/GE-103.yaml)
- Relates to GE-105 (docs/acceptance-criteria/guardrail-engine/GE-100-code-quality-hooks/GE-105.yaml)
- This ticket introduces the SSOT-deploy + path-resolution AC (to be authored by the BA).

## Acceptance Criteria
- [ ] AC-1: `build.py` deploys `diagram_types.json` and `doc_types.json` into the consumer
      tree at the location the validators resolve to, idempotently (compare-before-write).
- [ ] AC-2: `diagram_type_validators._load_diagram_types()` loads values from the deployed
      `diagram_types.json` at runtime (not the `commit_guardian.json` fallback) in both the
      self-hosted repo and a simulated consumer layout.
- [ ] AC-3: `doc_type_validators._load_doc_types()` loads values from the deployed
      `doc_types.json` at runtime under the same two layouts.
- [ ] AC-4: With the JSON loaded, `validate_diagram_type` accepts every key in
      `diagram_types.json` (incl. `data_flow`, `user_flow`, `agent_flow`) and rejects values
      absent from it; the `commit_guardian.json` fallback is exercised only when the JSON is
      genuinely absent.
- [ ] AC-5: A test reproduces the original path-resolution bug (asserts the JSON resolves to
      `<root>/config/...` not `<root>/leafcutter/config/...`) and would fail against the
      pre-fix code.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] Add a build phase (or extend an existing config-deploy phase) to copy
      `leafcutter/config/diagram_types.json` and `doc_types.json` into the deploy target,
      idempotently; register it in the `_run_phases()` dispatch list.
- [ ] Fix the JSON path resolution in `diagram_type_validators.py` and
      `doc_type_validators.py` to point at the real config location, mirroring the
      `check_doc_types_agents.py` repo-root resolution pattern. Apply to all tracked source
      copies (`templates/scripts/commit_guardian/`, `templates/commit-guardian/`).
- [ ] Keep the graceful fallback to the `commit_guardian.json` constant for genuinely
      absent JSON (backward compatibility).
- [ ] Add `test_diagram_type_ssot.py` covering AC-2 through AC-5 (both self-hosted and
      simulated-consumer layouts).
- [ ] Rebuild and confirm the deployed `.leafcutter/` validator loads the JSON.

## Out of Scope
- The GE-105 symptom fix (already merged via PR #91) — do not revert the widened
  `commit_guardian.json` fallback; it remains the correct backstop for absent JSON.
- Reconciling the `dataflow` → `data_flow` alias deprecation across existing docs.

## Risk & Safety
- Touches money? No.
- Touches data? No — config deployment + read-path resolution only.
- Reversibility? Fully reversible; no migrations. A regression would re-trigger the stale
  fallback (already proven safe by GE-105), so failure mode is graceful.
