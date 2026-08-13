---
title: "guardrail-engine — AC store context"
description: Conventions and standing notes for authoring/decomposing ACs in the guardrail-engine
  component (prefix GE).
created: '2026-08-14'
last_updated: '2026-08-14'
type: tutorial
status: active
components:
  - commit_guardian
  - precommit_hooks
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

> **Amendment (2026-08-14):** the "no L0 root file" convention above describes
> the ORIGINAL GE-1xx family only. Newer trees (GE-113, GE-116, GE-118, GE-119)
> are authored as a proper L0 root + L1 children in a `GE-NNN-<slug>/` folder.
> Follow the newer pattern for new work; the note above is retained because the
> older GE-100/GE-107 files still have the flat shape.

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

## GE-119 green-means-checked: framing note for the BA/IT-PO (2026-08-14, PO)

GE-119 ("Trust that a green check actually checked something") is a NEW root L0
in guardrail-engine, slug folder `GE-119-green-means-checked/`, four L1 children
GE-119a..d, origin_agent BrainCandy, readiness draft, priority medium,
roadmap_phase phase_1. It generalises a defect class: a commit-guardian check
that cannot reach what it needs exits 0 and reports success, so "green" is
indistinguishable from "did not run".

PLACEMENT PRECEDENT (reuse this reasoning): triage suggested grafting onto
GE-118a. Rejected — GE-118a is an L1 whose SUBJECT is one check (check-secrets)
and whose only child is done; hanging a cross-cutting policy under a
single-instance L1 inverts containment and reopens a complete node. GE-118's L0
was also rejected as parent: its scope is dependency RESOLUTION from the
deployed layout, while two of GE-119's L1s cover degrade paths that are not
resolution failures. Standing rule for this component: **GE-118 = the point
fixes that landed (GE-118a-1, GE-118b, both done); GE-119 = the class they are
instances of.** GE-118 was deliberately NOT amended or superseded.

FAIL-OPEN CONTRADICTION — load-bearing, do NOT let decomposition flatten it:
this component has a deliberate fail-open convention (internal error → exit 0 +
stderr warning so a script bug never blocks an unrelated commit), documented in
the ac-store PROJECT_CONTEXT and approved as GE-116a-1-iii ("Unparseable agent
definition fails open and does not block the commit"). GE-119 does NOT repeal
it. The line it draws: fail-open on ONE bad input while the check still ran is
fine; reporting SUCCESS for a check that never ran is not. The unit of the rule
is **visibility**, not blocking. Whether a cannot-run condition should also
BLOCK is a per-check L2 decision — there is no blanket default.

L1 split (decompose each into L2; do NOT re-cut at L1):

- **GE-119a** — the POLICY: a check that cannot run says so. Cross-cutting over
  the 18 checks sharing the `_find_project_root` / `parents[]` root-walk
  pattern. `documentation_triggers: [reference-doc]` — the opposite rule is what
  is currently written down.
- **GE-119b** — PARITY: same work, same verdict from any working copy. The
  acceptance shape is the observed pair — `check_ac_parent_covered_by.py`
  exiting 0 with "skipping check (fail-open)" without the deployed-layout link
  vs. blocking with 6 violations WITH it, on identical staged files. The how-to
  trigger is a REPLACEMENT: the manual "link `.leafcutter` into your worktree"
  pre-drive step must be deleted, not left beside the fix.
- **GE-119c** — PROOF: verified by running the deployed checks from a separate
  working copy. Today's unit tests import from the source tree — the one layout
  where the bug cannot reproduce — so they are not evidence.
  `[component-diagram]` for the new harness.
- **GE-119d** — SET-UP: `setup_ticket_worktree.py`'s own "graceful no-op" on
  `verify_precommit_active.py` / `install_pre_commit_shims.py`. Different
  script, so it is its own L1; may be folded into GE-119b ONLY if decomposition
  proves the same root cause — and say so explicitly rather than dropping it.

EVIDENCE CONFIDENCE (carry the labels through — do not upgrade them): the
`check_ac_parent_covered_by` pair is DIRECTLY OBSERVED AND REPRODUCIBLE. The
"26 schema-violating files looked clean" figure from `check_ac_schema.py`'s
silent degrade to manual field validation is REPORTED BY A PARALLEL SESSION AND
UNVERIFIED — GE-119c is what makes it checkable.

REPEAT-DEFECT HISTORY: GE-112 already fixed an adjacent defect in
`check_ac_schema.py`. Three prior point patches exist in this area (GE-112,
GE-118a-1, GE-118b). Favour a structural fix; a fourth point patch is the
failure mode to avoid.

SEQUENCING WITH ac-store: GE-119b and ACS-1200a touch the same file
(`check_ac_parent_covered_by.py`) for opposite-direction reasons — GE-119b makes
it run everywhere, ACS-1200a makes it enforce the right rule. A check that
starts running reliably everywhere while still holding the wrong rule blocks
every parked idea MORE consistently. Sequence ACS-1200a with or before GE-119b,
or land them in the same release.
