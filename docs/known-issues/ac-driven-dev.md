---
title: "Known issues — ac-driven-dev"
description: "Open, observed defects in the ac-driven-dev component: AC selection and prioritisation, ticket generation from AC records, and the traceability block the downstream gates read. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - ac_driven_dev
related_docs:
  - docs/architecture/components/ac-driven-dev.md
  - docs/architecture/components/phantom-done-prevention.md
---

# Known issues — ac-driven-dev

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-ACD-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-ACD-001 — `ac_prioritizer` discards each AC's `priority` field, so `critical` never surfaces

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/ac_prioritizer.py:209` — `complexity_to_priority(ac.get("estimated_complexity", ""))`

**Symptom.** The prioritiser never reads the `priority:` field that PO/BA/IT-PO author
on every AC. It derives the queue position **solely** from `estimated_complexity`, via
`COMPLEXITY_TO_PRIORITY` (`S → high`, `M → medium`, `L → low`, `XL → low`). Two
consequences:

1. No AC can ever be reported as `critical` — nothing in the mapping produces that
   value, even though `critical` is a valid `priority` in the AC schema and
   `PRIORITY_ORDER` ranks it first.
2. The ordering is **inverted from author intent**: a large critical defect (`L` →
   `low`) sorts *below* a small cosmetic one (`S` → `high`). Effort is being used as a
   proxy for importance.

**Evidence.** `ACD-1900b-5-i` — `priority: critical`, `estimated_complexity: L`, a live
vacuous-pass defect in the pre-commit path — was reported by `ac_prioritizer.py` as
`[ac] [low]` at position **465 of 477** in the READY queue. Grepping the full run output
for `critical` returns zero matches across all 477 entries. `/build-ac` selecting "the
next highest-priority unimplemented AC" would not have reached it; the ticket was only
built because the AC was targeted explicitly by id.

**Fix direction.** Rank on the AC's own `priority` when present, and fall back to the
complexity mapping only when it is absent. Complexity is a scheduling input (how big is
this), not a priority signal (how much does it matter) — the two should be separate sort
keys, not the same one. Note `PRIORITY_ORDER` already handles `critical` correctly, so
the fix is in what gets *fed* to it, not in the sort.

---

### KI-ACD-002 — Generated Agent Contracts lines have no pipe delimiters, so documentation-verifier fail-closes on every generated ticket

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the `## Agent Contracts` →
  `### documentation-expert` emitter

**Symptom.** `documentation-verifier` (priority 11.9, immediately before `commit`)
parses each `- [ ] AC-N:` line under `### documentation-expert` as three pipe-delimited
fields, `<genre> | <target_path> | <content_constraint>`, and emits `(status: blocker)`
on any line without them. The generator emits no pipes at all:

```
- [ ] AC-1: [(unspecified genre)] templates/agents/ac-fulfillment-gate.md — <criterion text>
```

So the verifier fail-closes at Step 2 on **every** generated ticket whose source AC
carries `doc_links`, and the documentation phase is never actually verified. Because the
blocker is correctly classified `cross_agent` (it names the ticket generator as the
responsible sibling), the phase is *skipped* — and the build still reports `status: ok`.

A second defect sits in the same line: `target_path` is populated from the AC's
`doc_links` **`describes`** entries, which point at whatever the AC references —
frequently an agent template or a Python module, not a documentation file. Even with
pipes added, the path named is often not a doc.

**Evidence.** `TICKET-20260818-ACD-1900b-5-i.md:262` carried exactly one such line,
naming `templates/agents/ac-fulfillment-gate.md` as the documentation target. The
verifier blocked with "Agent Contracts line is malformed (no pipe-delimited
target_path)". Repaired by hand on that branch — naming the two docs
`documentation-expert` actually wrote — so the phase could run; the generator itself is
unchanged and will reproduce this on the next generated ticket.

**Fix direction.** Emit the contract format the verifier documents, and source
`target_path` from the docs the change *requires* (the `creates`/`modifies` doc_links, or
the `requires_documentation` types) rather than from `describes` back-references. Whatever
lands should be covered by a test that runs the generator and then runs the verifier's
Step 2 parser over the output — the two sides have disagreed silently, which is the same
producer/consumer divergence class as the `ac_traceability` shape mismatch that
`ACD-1900b-5-i` fixes.

---

### KI-ACD-003 — `ac-fulfillment-gate` returns `ok` on an AC it left with `covered_by: []`

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/agents/ac-fulfillment-gate.md` — the Step 3 auto-fix / Step 5
  verdict, for the `covered_by` field specifically

**Symptom.** The gate's stated job is to verify that `work_status`, `implemented_by` and
`covered_by` are accurate before a commit is allowed. Observed outcome on a real run: it
returned `ok`, and the AC it verified was left with `work_status: done`,
`implemented_by` correctly populated with five paths, and **`covered_by: []`** — while
five `# covers:`-tagged tests for that AC existed and were passing. So `implemented_by`
is reconciled and `covered_by` is not, yet the verdict is `ok` either way.

An AC marked done with no `covered_by` is a phantom-done vector in the same sense as
KI-BO-002 (which is the mirror case: `mark_done` populates neither). Whichever of the
two fields is missing, the store loses the link between the claim and its proof.

**Evidence.** `ACD-1900b-5-i` after its build: gate verdict `ok` (journal
`wf_ebe75602-f98`), `covered_by: []` on disk, and
`done_proof.verify_done_eligible("ACD-1900b-5-i")` independently returning
`eligible: True` with all five test node-ids listed under `passing_tests`. The proof
existed and was discoverable by an existing helper — the gate simply did not write it
back. Populated by hand on that branch. The same run also failed to add the new
behavioural test to `BO-201`'s `covered_by`, even though the AC's own `it_requirements`
explicitly required BO-201 to gain its first executing coverage via a
`# covers: BO-201` tag; that tag was written into the test but never reflected in the
store.

**Fix direction.** Reuse `done_proof.verify_done_eligible`, which already returns the
passing covers-tagged tests, to populate `covered_by` during the same auto-fix pass that
populates `implemented_by`. Make an empty `covered_by` on a `work_status: done` AC a
blocking condition rather than a silent pass — the gate that exists to prevent
unevidenced "done" should not itself sign one off. Note the fix must also reconcile ACs
named in a `# covers:` tag other than the ticket's own (the BO-201 case), which the
current pass does not consider at all.

**Related.** KI-BO-002 (`mark_done` leaves `implemented_by: []`) — same family, other
field, other code path.
</content>
