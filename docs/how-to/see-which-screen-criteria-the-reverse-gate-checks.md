---
title: "How to See Which Screen Criteria the Reverse Gate Checks"
description: "Run the reverse-direction UI declaration gate against the acceptance-criteria store and read which criteria it selects, skips, or leaves out of scope."
type: how-to
status: active
created: 2026-10-23
last_updated: 2026-10-23
components:
  - commit_guardian
  - ac_store
related_docs:
  - docs/architecture/components/commit-guardian.md
  - docs/architecture/components/phantom-done-prevention.md
  - docs/acceptance-criteria/guardrail-engine/GE-124-frontend-declares-what-it-renders/GE-124e.yaml
  - docs/product-truth/mock-data/guardrails/frontend-ac-declarations.mock.json
  - docs/how-to/declare-frontend-acceptance-criteria.md
related_code:
  - templates/scripts/commit_guardian/check_ui_ac_declared.py
---

# How to See Which Screen Criteria the Reverse Gate Checks

Run the reverse gate and read its report, so you know which screen criteria it will check and why every other criterion was not checked (GE-124e-1).

## Prerequisites

- A repository with an acceptance-criteria store at `docs/acceptance-criteria/`.
- Python 3 and a built install, so `scripts/commit_guardian/check_ui_ac_declared.py` exists. If it is missing, rebuild with `build.py`; the script is copied from `templates/scripts/commit_guardian/`.
- Background on the declaration side of the gate: [How to Declare the Acceptance Criteria a Frontend Component Serves](declare-frontend-acceptance-criteria.md).

## Steps

### Step 1 — Run the gate from the repository root

```bash
python3 scripts/commit_guardian/check_ui_ac_declared.py --mode ci --base origin/main
```

The gate reads the store through the shared index. It does not walk the store itself. The `--base` value is accepted and ignored for now; diff scoping belongs to GE-124e-4.

### Step 2 — Ask for the full report

```bash
python3 scripts/commit_guardian/check_ui_ac_declared.py --mode ci --json
```

The JSON report has three keys: `selected` (sorted ids), `outcomes` (one entry per criterion in the store) and `passed` (always an empty list, because selecting a criterion passes nothing).

### Step 3 — Read each criterion's outcome

Every criterion gets exactly one of three outcomes:

| Outcome | Meaning | Reason |
|---|---|---|
| `selected` | `change_target` includes `ui` and `work_status` is `done`. The gate will check it. | none |
| `skip` | A UI criterion that is not done yet. It is skipped, never failed. | `not-done` |
| `out-of-scope` | `change_target` does not include `ui`. | `not-ui` |

`change_target` may be a single value or a list. Both forms are read, so a criterion whose `change_target` is `[ui, code]` is selected once it is done.

An out-of-scope criterion is not a pass. Counting it as one would inflate every figure built on this gate by the whole non-UI store.

## Verification

Run the text form against the store:

```bash
python3 scripts/commit_guardian/check_ui_ac_declared.py --mode ci
```

Expected output is one line of this shape, where the counts depend on your store:

```text
[check-ui-ac-declared] selected=7 skipped=40 total=5319
```

Check the worked cases in the JSON report:

- A done UI criterion such as `UXP-607-2` is listed in `selected`.
- An in-progress UI criterion such as `KM-ADM-003` has `"outcome": "skip"` and `"reason": "not-done"`, and is absent from `passed`.
- A code criterion such as `GE-111f` has `"outcome": "out-of-scope"` and `"reason": "not-ui"`.

## Troubleshooting

1. **Exit code 1 and `AC store ... is missing or empty; no evidence produced`.** The gate could not read the store. In `ci` and `ci-changed` modes this blocks, because a run that read nothing produced no evidence. Run from the repository root, or pass `--ac-root docs/acceptance-criteria`.
2. **Exit code 1 and `cannot read AC store`.** An OS error stopped the read. Fix the file permission or path named on the stderr line, then re-run.
3. **`ModuleNotFoundError` for `_ac_store_index` or `_resolve_root`.** The deployed copy is stale. Rebuild with `build.py` so the helpers are copied beside the script.
4. **A UI criterion you finished is listed as `skip`.** Its `work_status` is not `done` in the store. Update the record, then re-run.
5. **`--mode precommit` exits 0 on an unreadable store.** That is intended for the pre-commit tier. The CI tier blocks.

## See Also

- [Commit guardian component](../architecture/components/commit-guardian.md) — where the gate sits among the commit-time and CI checks.
- [Phantom-done prevention](../architecture/components/phantom-done-prevention.md) — why a finished criterion needs evidence.
- [GE-124e acceptance criterion](../acceptance-criteria/guardrail-engine/GE-124-frontend-declares-what-it-renders/GE-124e.yaml) — the parent criterion.
- [Frontend AC declarations mock data](../product-truth/mock-data/guardrails/frontend-ac-declarations.mock.json) — the skip record `gf-ci-km-adm-003-skipped`.
- [Documentation Index](../INDEX.md)
