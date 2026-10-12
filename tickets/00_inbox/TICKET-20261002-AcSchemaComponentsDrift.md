---
title: "AC schema: the graph-component list has drifted from docs/components.json"
status: in_progress
components:
  - ac_store
created: 2026-10-02
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: config
risk_surface: internal
tags:
  - ac-store
  - schema
  - drift
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# AC schema: the graph-component list has drifted from docs/components.json

## Actor / Goal
In order for an AC to name any registered component, we need the AC schema's allowed `components` values to match `docs/components.json`, and a check that keeps them in sync.

## Context
- **The drift:** `config/ac_store_schema.json` (deployed as `.leafcutter/config/ac_store_schema.json`) lists 44 graph component ids in `properties.components.items.enum`, while `docs/components.json` has 46.
  - Missing: `decision_kernel` (added by the kernel work, commit `54a09cbf`) and `epic_retrospective`.
- **Found while writing:** the decision-kernel ACs (`TICKET-20261002-DecisionLifecycleACs`, 2026-10-02). Every AC with `components: [decision_kernel]` fails validation with "'decision_kernel' is not one of [...]".
- **Rejected workaround:** naming another component would pass validation with a false value in the knowledge graph.

## Scope
- Add the missing ids to the enum, and redeploy the `.leafcutter` copy through `build.py`.
- Add a test that fails when the enum and `docs/components.json` disagree. Alternatively, generate the enum from `docs/components.json`, whichever fits the repo's existing schema-sync patterns.

## Out of Scope
- Renaming components.

## Comments

### 2026-10-02 12:00 — python-coder (status: ok)
feedback-id: fb_2026-10-02_3e4c60cb
- Added `decision_kernel` and `epic_retrospective` to `properties.components.items.enum` in `config/ac_store_schema.json` (enum now 46, sorted, equals the `docs/components.json` ids). The only copy is the gitignored `.leafcutter/config/` deploy, refreshed via `build.py --target-dir .`; CRLF churn reverted.
- New `unit_tests/ac_store/test_ac_schema_components_enum_parity.py` (4 tests, both directions + duplicates + key/id match). Red before fix (missing: decision_kernel, epic_retrospective), green after. No existing generator for this enum, so a test rather than generation.
- The schema-diff CI job only compares `skills_config.schema.json`; unaffected.
- DK ACs (6 files): `check_ac_schema.py` via HOOK_TEST_STAGED_FILES exit 0; `validate_ac_schema.py` exit 0.
- Pre-existing unrelated failures: components_minimum_schema (`infrastructure` primary_code), and 3 in unit_tests/ac_store (strict_on_ci, 500f_5_i, 500f_6_iii_a).
- feedback-id: fb_2026-10-02_3e4c60cb
