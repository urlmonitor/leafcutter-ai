---
title: "A claimed kind of proof is a declaration, not evidence — now legible on three surfaces"
date: "2026-09-01"
time: "09:15"
type: manual
components: 
  - build_pipeline
  - testing_quality
  - documentation_system
summary: "Closed out the BP-1100g reachability chain: writers now record which entry point they used (or that none exists), a new reference page states plainly what each kind of proof does and does not establish, and a new diagram shows exactly where that boundary sits — no production code or tests changed, by design."
description: "Three producers, one commit, all test_required: false. BP-1100g-2 (templates/agents/test-writer.md + templates/skills/signoff/SKILL.md): a five-way ordered decision procedure (CLI, hook runner, slash command, workflow dispatch, main(argv)) plus an explicit not-count list (import-and-call, hasattr, assertIn on a registry, call_args inspection); the resolved-or-not-found answer rides completion_manifest under the fixed key reachability_entry_point_answer, sibling to BP-1100g-5's cross_layer_seam_answer (resolved/not_found mirrors covered/not_applicable). BP-1100g-6: new docs/reference/proof-claims-and-completeness.md, tabulating all seven # angle: kinds (read from config/ac_store_schema.json's enum, not retyped) against what claiming each does and does NOT entitle a reader to conclude. BP-1100g-7: new docs/architecture/diagrams/c3-007-promise-versus-claim-sequence.md, an L3 sequence diagram whose strongest claim — zero arrows touch the execution observer's lifeline — was verified by parsing the mermaid source with its own grammar rather than by eye. Two incidental findings: the diagram's intended number c3-006 was already taken and next_diagram_seq.py caught the collision, landing it at c3-007; and the grammar-parse check found a semicolon inside a mermaid message severs the arrow (';' is a mermaid statement separator) — a defect that would have shipped visibly broken, and that check-mermaid-complexity, check-diagram-naming, and check-mermaid-parent-link (all regex-based) do not check for, since none of them validates that a diagram is parseable mermaid at all."
breaking: false
---

## Entry

A claimed kind of proof is a **declaration by an author**. It is not evidence. This closes
the BP-1100g chain by making that boundary legible on three different surfaces: the record a
test-writer leaves behind, the reference a reader looks up, and the diagram someone skims.

Three producers, one commit. No production code changed, and no tests accompany any of the
three (`test_required: false` on all — correctly, since each describes a written statement or
a document, not a runtime behaviour a unit test can exercise).

### The record — `reachability_entry_point_answer` (BP-1100g-2)

Roughly 80% of work arrives with no authored plan, so nothing upstream can name the way in.
Until now that judgement was made silently. `test-writer` must now resolve an entry point and
record the one it resolved, under the fixed key `reachability_entry_point_answer` in the
sign-off's `completion_manifest`.

Built deliberately as a sibling of `cross_layer_seam_answer` (BP-1100g-5, shipped earlier):
same naming pattern, same always-nested-object structure — so the honest negative never trips
the Bare-False Rule — and the same declaration-not-evidence framing. Its negative spells
`not_found`, for the same reason g-5's spells `not_applicable`: a reasoned "no way in" is a
first-class answer, not a failed checklist item.

Resolution follows a five-way ordered decision procedure, checked against real code: CLI,
pre-commit hook runner, slash command, workflow dispatch, and bare `main(argv)`. An explicit
list states what does **not** count, because each superficially resembles resolution:
importing the module and calling the function directly, asserting a symbol exists, an
`assertIn` against a registry, or asserting a value was merely passed as an argument.

### The reference — what a proof claim does and does not mean (BP-1100g-6)

New `docs/reference/proof-claims-and-completeness.md`. For each of the seven kinds of proof, a
table states what claiming it means and — the reason the page exists — what it does **not**
entitle a reader to conclude. The seven kind values are read verbatim from
`config/ac_store_schema.json`'s `angle` enum rather than retyped from prose, so a future schema
change is a visible drift signal instead of a silent one.

### The diagram — where the boundary to the execution observer lies (BP-1100g-7)

New `docs/architecture/diagrams/c3-007-promise-versus-claim-sequence.md`. An L3 sequence
diagram of promise, claim, and refusal, drawing the boundary to the execution observer
explicitly. Its strongest claim — zero arrows touch the observer's lifeline — was verified by
parsing the diagram with mermaid's own grammar, not by eye.

### Two incidental findings

- The diagram's intended number, `c3-006`, was already taken. Running `next_diagram_seq.py`
  caught the collision before it shipped; the diagram landed at `c3-007` instead.
- Parsing the diagram with mermaid's real grammar found a defect the repo's own hooks could
  not: a `;` inside a message severs the arrow, because `;` is a statement separator in
  mermaid. It would have shipped visibly broken. `check-mermaid-complexity`,
  `check-diagram-naming`, and `check-mermaid-parent-link` are all regex-based, and none of
  them validates that a diagram is parseable mermaid at all.
