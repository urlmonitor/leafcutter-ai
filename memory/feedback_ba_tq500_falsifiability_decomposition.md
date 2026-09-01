# BA learnings — TQ-500 (a passing test shown able to fail) L2/L3 decomposition

Captured 2026-08-31 (business-analyst) decomposing TQ-500a..e into 15 L2 and 6 L3
in testing-quality, from KI-TQ-010 and the PO hand-off
`feedback_po_ba_tq500_falsifiable_checks.md`. For IT-PO (enrichment) and future BA runs.

## The four PO constraints, and where each landed as a Then clause

None of these survive as prose — each is a clause an implementation can fail:

1. **No automatic classification.** TQ-500a-1 clause 2 forbids the requirement text
   from being an input at all. Its falsifiable half is **TQ-500a-1-i**: run the same
   two records twice with the requirement text swapped and require byte-identical
   output. "No classifier was built" is not observable; "the text is not an input" is.
2. **Per item, never one verdict.** TQ-500c-1 records one outcome per *(test,
   alteration)* pair — not per test. The incident table is 4 tests x 3 alterations and
   the collapse survives one level of aggregation, so TQ-500c-2 reads it row-wise
   (which test never objected) and **TQ-500c-3** reads it column-wise (which alteration
   nothing noticed). Both are needed; neither implies the other.
3. **Honest negative stays expressible.** TQ-500a-2 mirrors the signoff SKILL §2b
   nested `{result, reason, remediation}` shape. A bare false is malformed under the
   existing Bare-False Rule, so a bare negative would make the whole hand-off record
   malformed and trigger a retry — reusing the nested shape gets reason + next step
   recorded for free and gives the reader a shape it already parses.
4. **Anti-grep.** Every reader AC carries a clause pinning the finding to emitted
   records. **TQ-500b-2** goes further and is the pattern worth copying: *withhold only
   this finding, everything else identical, and the completion decision must flip.*
   That is a named repeatable alteration written into the requirement — the criteria's
   own substitute evidence. Without it, "the finding is reported" is satisfied by a run
   that prints it and decides on other grounds (the fast-lane inert-runner shape).

## Pattern: an AC about negative controls is itself a negative control

Six of the 21 ACs assert mostly that *nothing is reported* (carve-outs, false-shortfall
controls). Every one of them is green on arrival by construction — the exact defect the
tree exists to fix, reproduced inside the fix. Each therefore carries a deliberate
must-report case in the same scenario (TQ-500b-1-i piece G, TQ-500c-2-i's flipped cell,
TQ-500e-2-i clause 5) and a note naming the alteration its implementer should record.
**Rule for future BA runs: any AC whose Then clauses are all absences needs one
adversarial case in the same Given, or it cannot fail.**

## Composition, not a second parser

TQ-500b-1 and TQ-500e-2 `depends_on: BP-1100g-5-i` — a hard, deliberate cross-tree
dependency. That AC builds the mechanical reader over the sign-off completion manifest
(shortfall naming, no-record-vs-bad-record, pre-epoch legacy carve-out). The
falsifiability answer is a **second key on the same reading**, not a second reader.
TQ-500b-1's last clause makes that observable: a record missing two required answers
must yield both findings from one reading.

## Agent split used (IT-PO may revise)

- `llm-expert` — record shape ACs (what the writer must state): a-1, a-2, a-3, c-1,
  d-1, e-1. change_target `prompt`.
- `python-coder` — every reader / decision AC and all six L3s. change_target `code`.
- `documentation-expert` / `architecture-diagram-author` — the three doc ACs.

Note the pattern from BP-1100g-5-i: an L3 whose parent is a `prompt` AC is usually a
`code` AC, because the falsifiable half of "the writer must state X" is always "the
reader reports a missing X". Do not inherit change_target from the parent on these.

## Documentation triggers were consolidated, not skipped

All five L1s carry `reference-doc`; a, d carry `how-to`; b carries `state-diagram`.
Five copies of one reference would drift onto the reader trying to check an answer, so:
one how-to (TQ-500d-2), one state diagram (TQ-500b-3), one reference (TQ-500e-3), each
noting which siblings' triggers it answers. Each doc AC's notes carry an explicit
firewall: **its deliverable is the document only, and no behavioural AC in the tree may
be closed by pointing at it** — otherwise the doc AC becomes the prose-presence proxy
the anti-grep clause forbids.

## Field conventions (validated)

Matched the TQ-400 siblings. `components` graph ids (`testing_quality` plus
`build_orchestration` / `build_pipeline` / `ac_store`); scalar `component:
testing-quality`. `origin_agent: BrainCandy`, `readiness: draft`, `req_status: draft`,
`work_status: todo`, `priority: medium`, `roadmap_phase: phase_1`, `created:
2026-08-31`. `estimated_complexity: null`, no `it_requirements`, no `test_spec` — left
for IT-PO. Every L1 got exactly 3 L2 children: under the hard cap of 5 and above the
sparse advisory of 3. `validate_ac_schema.py` on the folder: "OK: all 27 AC YAML files
are valid"; `scan_ac_orphans.py` and `check_ac_tree_limits.py` report nothing for
TQ-500.
