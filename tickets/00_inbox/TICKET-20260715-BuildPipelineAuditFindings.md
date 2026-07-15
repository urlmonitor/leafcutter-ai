---
title: "Fix 3 accuracy findings from the build_pipeline test-coverage backfill"
status: todo
components:
  - build_pipeline
created: 2026-07-15
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
test_required: true
files_touched:
  - docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100b-9.yaml
  - docs/agents/llm-expert/PROJECT_CONTEXT.md
  - config/agent_registry.json
  - docs/how-to/upgrade-frontend-coder-unified-agent.md
  - unit_tests/agents/test_llm_expert_artifacts.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
change_target: docs
risk_surface: internal
---

# Fix 3 accuracy findings from the build_pipeline test-coverage backfill

## Actor / Goal

In order to keep the build_pipeline AC store and its supporting docs/config
internally consistent, we need to correct three factual/consistency defects
surfaced (but deliberately not fixed) during EPIC-BuildPipelineTestBackfill, so
that the store's `covered_by`/criteria and the shipped artifacts describe reality.

## Context

Surfaced by the 2026-07-14 build_pipeline audit
([reports/build_pipeline-implementation-audit-2026-07-14.md](../../reports/build_pipeline-implementation-audit-2026-07-14.md))
and the backfill drive (PR #297). The backfill tests asserted **reality** and
these three items were flagged for a governance-/scope-appropriate follow-up
rather than being papered over. None is blocking; all are small.

## Acceptance Criteria

- [ ] AC-1: BP-100b-9's criterion is corrected via the AC-amendment mechanism.
  Its `criteria` currently requires a shimmed-outputs row with source
  `templates/scripts/workflows/`, but that directory does not exist — the real
  build source is `templates/workflows-js/` (`scripts/build_phases.py` :685,
  `workflows_js_src = TEMPLATES_DIR / "workflows-js"`). After the fix the
  criterion names `templates/workflows-js/`, matching the doc and the shipped
  build, and the amendment is recorded in the AC's `amended_by`.

- [ ] AC-2: The llm-expert `spawn_allowlist` is consistent across its two
  surfaces. `docs/agents/llm-expert/PROJECT_CONTEXT.md` §5 states the
  `spawn_allowlist` is `[]`, while `config/agent_registry.json` lists
  `["research-agent"]`. Determine the correct value (llm-expert does reference
  research-agent for context-gathering, so `["research-agent"]` is the likely
  truth) and make both artifacts agree. A test asserts the two surfaces match.

- [ ] AC-3: The frontend-coder upgrade how-to is corrected. `docs/how-to/
  upgrade-frontend-coder-unified-agent.md` claims `build.py --clean` removes an
  existing `.claude/skills/frontend-design/` directory. It does not:
  `frontend-design` is retained under `templates/skills/` with `deprecated: true`,
  so `_build_source_manifests()` treats it as still-managed and `clean_stale_
  artifacts()` never prunes it. The shipped removal mechanism is deploy-time
  exclusion (deprecated skip) + `skills_config.json` migration + template
  overwrite; the how-to must describe that, not a `--clean` prune.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] AC-1: amend `BP-100b-9.yaml` criteria to `templates/workflows-js/` via the
  governance-approved AC-amendment path (write-locked field); add an `amended_by`
  entry. Confirm `test_bp100_drift_docs_compile.py::...bp100b9...` still green.
- [ ] AC-2: pick the correct `spawn_allowlist` value; update whichever of
  `PROJECT_CONTEXT.md` §5 / `agent_registry.json` is wrong so they agree; add a
  test that fails if the two surfaces diverge (extend
  `unit_tests/agents/test_llm_expert_artifacts.py`).
- [ ] AC-3: rewrite the "removal" section of the upgrade how-to to describe the
  real mechanism (deprecated skip + skills_config migration + template
  overwrite); drop the false `--clean` prune claim.
- [ ] Run the affected suites green.

## Out of Scope

- The broader phantom/opposite-behaviour fixes (tracked in
  `EPIC-BuildPipelinePhantomRemediation`).
- Any change to the frontend-coder deprecation behaviour itself — this ticket
  only corrects the doc to match current behaviour.

## Risk & Safety

- Touches money? No.
- Touches data? No — doc/config/AC-criteria text only.
- Reversibility? Fully reversible (text edits); no schema or runtime change.
