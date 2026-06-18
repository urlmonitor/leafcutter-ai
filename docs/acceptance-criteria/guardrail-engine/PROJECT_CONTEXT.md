---
description: "Conventions and standing notes for authoring/decomposing ACs in the guardrail-engine component (prefix GE)."
---

# guardrail-engine — AC store context

Conventions and standing notes for authoring/decomposing ACs in the
`guardrail-engine` component (prefix `GE`). Best-effort knowledge, captured by
authoring agents across runs.

## Store structure convention (GE-1xx family)

- GE-1xx ACs are authored as **L1 directly under the component** — there is no
  separate L0 root file (see GE-100, GE-107). Each L1 lives in its own
  feature folder `GE-NNN-<slug>/` and its `depends_on` is `[]`.
- L2 leaves use the **alpha suffix** on the L1 id: `GE-107` (L1) →
  `GE-107a` (L2). Deeper leaves add a numeric segment: `GE-100a` → `GE-100a-1`.
- `created_by` on a root L1 points to **its own file path** (self-reference),
  not a ticket path — see GE-107 and GE-108.
- The `validate_ac_schema.py` wrapper accepts the workflow fields that the raw
  JSON schema's `additionalProperties: false` appears to forbid
  (`req_status`, `work_status`, `level`, `doc_links`, `origin_agent`,
  `created`, `amended_by`, `superseded_by`, `covered_by`, `implemented_by`,
  `assigned_agent`, `estimated_complexity`, `it_requirements`, `delivers_to`,
  `expects_from`). Mirror an existing sibling file's field set rather than the
  bare schema.

## Exception-handling guard lineage (GE-107 / GE-108)

The `check_exception_handling.py` pre-commit guard enforces CLAUDE.md Error
Handling Policy Rules 1 and 3. Two sibling L1s govern distinct axes:

- **GE-107** — *scope*: WHERE the guard applies (production code only; test
  files exempt). Done (GE-107a leaf).
- **GE-108** — *faithfulness/accuracy*: HOW faithfully the guard matches the
  documented policy. Authored 2026-06-17 (readiness: draft, origin BrainCandy).

### GE-108 intended L2 decomposition (for the BA)

The three gaps below are framed at L1 in benefit language; each becomes one L2
leaf (likely `GE-108a` / `GE-108b` / `GE-108c`):

1. **Subprocess as an I/O boundary.** Rule 1 names "subprocess calls" as
   external I/O that must be wrapped. The guard currently detects only
   `requests.*`, `open()`, and `cursor.execute/executemany/callproc`. Unwrapped
   `subprocess.run / Popen / call / check_call / check_output / getoutput` pass
   with no IO-001 violation — close this gap.
2. **Blind-catch logging heuristic precision (Rule 3).** The guard treats any
   call whose name looks logging-like (`log/logger/warn/error/info/debug/print`)
   as "non-silent". Two false negatives: (a) a user-defined function
   coincidentally named `error()/info()/debug()` that is not a real logger is
   wrongly accepted; (b) a handler that only logs at DEBUG/INFO/print level is
   accepted, violating Rule 3's WARNING-or-higher requirement.
3. **Tuple exception label accuracy.** For `except (ValueError, Exception):` the
   BLE001 message reports the caught type as just "Exception" instead of the
   full tuple. Detection and line/col are already correct — only the
   human-readable label is imprecise.

## Framing preference (user: BrainCandy)

- User-authored ACs set `origin_agent: BrainCandy`; BA-created ACs set
  `origin_agent: business-analyst`.
- Priority is finalised at the workflow's final gate, not at authoring time —
  new L0/L1 ACs are written `priority: medium`, `readiness: draft`.
