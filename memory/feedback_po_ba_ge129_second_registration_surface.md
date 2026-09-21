# PO → BA/IT-PO — GE-129, the second registration surface (2026-09-14)

Authored `GE-129` (L0) + `GE-129a` (L1) in `guardrail-engine`, folder
`GE-129-proven-wherever-it-runs/`. Subject: liveness — has a guard ever been seen to
refuse — on the **session-hook** surface (`templates/settings.json` +
`templates/hooks/`), which `GE-120f`'s regime structurally cannot reach.

## The gap, verified before authoring (do not re-derive)

- `grep -c readme_read_guard templates/commit-guardian/commit_guardian.json` → **0**.
  The epic's own worked example is absent from `hooks_manifest`, which ADR-045 §2 fixes
  as the liveness run's population. So `GE-120f-1`'s runner would never examine it.
- It is wired at `templates/settings.json:57`, **PreToolUse on the `Edit|Write` matcher**,
  through the `bash -c` walk-up. Re-measured 2026-09-14: `templates/hooks/` holds 13
  scripts, `settings.json` names 11 — unchanged from the 2026-09-07 figure.
- ADR-045 records this itself twice, under *Consequences → Negative* and *Unresolved
  boundary*, and says extending the population to a second surface "is a separate
  decision requiring its own record". GE-129 is that record.

## Cap table — the 2026-09-01 BA table in `feedback_ba_guard_liveness_placement.md` is STALE

Re-parsed from the store 2026-09-14: **GE-120 is at 7/7 L1 (a..g)**, not 5. GE-120f is
at 5/5 L2. GE-126 is 5/7. GE-129 is 1/7.

## Placement findings that are reusable

1. **Pattern A (horizontal L0 split) is mechanically inert for freeing a GE-120 slot.**
   `check_ac_limits.py` derives the parent from the **id string**, so moving `GE-120g`
   to a new L0 leaves it counted under `GE-120`. Freeing a slot means renaming an
   existing `GE-120x` plus every descendant — which breaks test module names, ticket
   references and ADR-045's links. The `ac-tree-split` skill documents this in its own
   Pattern A note; read it before proposing a split as a capacity fix.
2. **A new root L0 is the working move, and it has three in-repo precedents inside three
   weeks**: BP-1600 (over a capped BP-100), BP-1300 before it, GE-125 in this component.
   No existing record is renamed and no `child_limit_override` is needed.
3. **A deliberately sparse L0 (one L1) is acceptable and precedented** — BP-1600 shipped
   that way on 2026-09-07 and said so. The sparse advisory is non-blocking. Padding to
   the three-child floor with L1s that belong to another owner is worse than sparseness.
4. **GE-126's two free L1 slots have now been examined and rejected on SUBJECT three
   times** (GE-120f, GE-128, GE-129). Stop re-litigating them. Its reader is someone
   *interrogating* the guard system; the liveness records already sitting there are
   recorded by GE-120f as a capacity artifact to be undone, not a precedent to extend.
5. **ACS-800 is NOT a placement precedent** — it is the unbuilt opaque-UID restructure.
   The only thing it supplies is the statement (ACS-800.yaml) that `child_limit_override`
   is a temporary stopgap it exists to retire.

## The seam the BA must not blur

| | population | question | verdict |
|---|---|---|---|
| `BP-1600a-1` (approved, high) | scripts on **disk** under the hook dir | is it invoked by the settings surface **at all**? | wired / run-by-nothing / grounded-unwired |
| `GE-129a` | entries the **settings surface** names, read at run time | can an invoked one **refuse**? | the four-value observed state |

`readme_read_guard.py` is wired, so BP-1600a-1 reports it as WIRED and is right to, and
it still cannot refuse. Neither implies the other. **No `depends_on`** — GE-129a never
needs the disk walk, so the dependency is not real and would only park it behind an
unbuilt record.

## Two surfaces, genuinely different shapes (the BA's real work)

- `hooks_manifest` entries are JSON objects **with ids**, so ADR-045 §3 hangs
  `negative_control` / `entry_point` on the entry. `settings.json` entries are **command
  strings** inside matcher groups — no id, no field to hang a declaration on. Where the
  declaration lives and how it binds to the script is open; **reusing
  `config/verification_flow.schema.json`'s vocabulary is not**.
- The entry point is a **harness tool-call event with its payload**, not `run_hook.py`.
  Invoking one of these as a bare command with a path in argv is not that entry point.
- A PreToolUse hook's observable rejection is **the tool call being denied**, not a
  commit being blocked.

## Incidental: `check_doc_length` now ratchets, and that changed the safe-edit rule

`commit_guardian.json` `doc_length.severity` flipped `warn` → **`block`** on 2026-09-14,
but with a GE-127a-1/GE-127b-1 ratchet: a doc already over 300 lines may not **grow**;
shrinking or holding steady passes. Filter is `^docs/.*\.md$`. Consequence for authoring
agents: **appending to `docs/acceptance-criteria/<component>/PROJECT_CONTEXT.md` is now
refused** once that file is over the limit (guardrail-engine's is ~624 lines), which is
why this learning is in `memory/` rather than there. `memory/` is outside the filter.
