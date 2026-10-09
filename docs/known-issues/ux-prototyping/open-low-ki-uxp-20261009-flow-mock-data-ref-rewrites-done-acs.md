---
title: "KI-UXP-20261009-flow-mock-data-ref-rewrites-done-acs — setting a flow's mock data reference rewrites the product-truth back-reference of every AC the flow implements, done ACs included, so a product-truth commit has to touch the AC store and the done-proof gate refuses it"
description: "medium — the generator copies flow-level fields into each AC's generator-owned product truth entry, so one flow-level change rewrites every linked AC file. A product-truth stage commit then either stages AC files, which plan-feature says it never does, or leaves them behind for the next commit. On 2026-10-09 the staged files included UXP-520, 521, 522 and 524, done ACs with no covers-tagged tests, and check-done-proof refused the commit. Workaround: leave the flow-level reference unset."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - ux_prototyping
related_docs:
  - docs/known-issues/ux-prototyping.md
  - docs/architecture/components/ux-prototyping.md
  - docs/how-to/authoring-product-truth-artifacts.md
---

# KI-UXP-20261009-flow-mock-data-ref-rewrites-done-acs — setting a flow's mock data reference rewrites the product-truth back-reference of every AC the flow implements, done ACs included, so a product-truth commit has to touch the AC store and the done-proof gate refuses it

- **Severity:** medium. The refusal is loud and there is a workaround, so nothing wrong lands.
  But two rules contradict each other, and the workaround costs product truth a link: the flow
  stops naming its dataset and reaches it only through its mockup.
- **Status:** open. No AC and no ticket for the coupling.
  `TICKET-20261009-AtlasFlowExplorerAcsProvenDone` (`tickets/00_inbox/`, PR #1065) gives UXP-520,
  521 and 522 real covers-tagged tests and reopens UXP-524. That clears this instance only. Any
  other done AC without proof that a flow links to hits the same refusal.
- **Occurrences:** 1 (2026-10-09, `/plan-feature` on branch `ac-authoring/ux-prototyping`, the
  flow `leafcutter/explore-flows-in-atlas` v5). Session observation of the refusal. The
  propagation is traced in code below.
- **First seen:** 2026-10-09 · **Last seen:** 2026-10-09
- **Where:** `docs/product-truth/scripts/generate_product_truth.py`, line numbers verified on
  origin/main `c79d41e34`: `build_by_ac()` (:226-252) copies flow-level fields into every
  per-AC entry, and `write_ac_product_truth()` (:411-437) rewrites each AC file whose entry
  changed. The commit rule it collides with is in `templates/workflows-js/plan-feature.js`
  (`commitStageOutputProductTruth`, header :1195-1201, prompt :1313-1316) and
  `templates/skills/plan-feature/SKILL.md:480`. The gate is `check-done-proof` (BO-2500b,
  `.pre-commit-config.yaml:422-428`, runs on any staged `docs/acceptance-criteria/*.yaml`).

## Symptom

On 2026-10-09 the flow `leafcutter/explore-flows-in-atlas` was extended to v5 with its
flow-level `mock_data_ref` set. Regenerating the store rewrote the generator-owned
`product_truth` block of every AC implementing one of the flow's steps. The product-truth commit
then staged those AC files. `check-done-proof` refused it for UXP-520, UXP-521, UXP-522 and
UXP-524: all four are `work_status: done` with `covered_by: []` and no covers tag anywhere in the
repo. The only change to them was the back-reference.

The v5 flow was committed with the field unset (`ae3dd8c16` on `ac-authoring/ux-prototyping`).
Its version note says so: "The flow-level mock_data_ref was left unset so this product-truth
commit does not rewrite the back-references of done UXP-520 ACs".

## Mechanism

1. `build_by_ac()` builds one entry per flow node and AC. Each entry carries the node's own
   fields (node id, node kind, screen, entities) and also flow-level fields: the flow's kind,
   its source and its mock data reference (`"mock_data": flow.get("mock_data_ref")`, :244).
2. `write_ac_product_truth()` compares each AC's stored block with the new entries and rewrites
   the file when they differ (:430-437). A done AC is rewritten like any other.
3. So one flow-level edit rewrites every AC linked from any node of that flow. From the code, the
   same holds for a change to the flow's kind or source; only the mock data reference was
   observed.
4. `/plan-feature` says a product-truth stage commit never stages `docs/acceptance-criteria/`
   (the AC store is a separate commit surface). With the generator above, that rule cannot hold
   and keep the store consistent:
   - **stage the AC files** (what happened): the commit breaks the rule and runs
     `check-done-proof`, which refuses any staged done AC without a covers-tagged test;
   - **leave them out** (what the workflow's commit prompt instructs, :1313-1316): the committed
     index and flow describe back-references the committed AC files do not carry, and the
     rewritten AC files stay modified in the authoring worktree until a later AC commit stages
     them and meets the same gate. Traced in code, not observed.

## Detection

After any flow edit, `git -C <authoring worktree> status --porcelain docs/acceptance-criteria/`.
Modified AC files whose only diff is inside the `product_truth` block are this propagation. Any of
them with `work_status: done` and no covers tag will fail `check-done-proof` when staged.

## Workaround

Leave the flow-level `mock_data_ref` unset and let the flow reach its dataset through its mockup.
That is what explore-flows-in-atlas v5 does. Set it once the linked done ACs have real
covers-tagged tests (for these four, once `TICKET-20261009-AtlasFlowExplorerAcsProvenDone` lands).
Do not pass `--no-verify` and do not add `test_required: false` to get past the gate.

## Fix direction

1. **Keep flow-level fields out of the per-AC entry.** Store the flow id, node id and node kind
   in the AC's back-reference, and let readers look up the flow's kind, source and dataset in the
   index's per-flow view, which already carries the mock data reference (:279-280). A flow-level
   edit then touches no AC file, and the product-truth commit rule can hold as written.
2. **Or state the rule honestly.** If AC back-references must carry flow-level fields, a
   product-truth commit must be allowed to stage generator-owned AC changes. The done-proof
   refusal is then the correct outcome, and the plan-feature skill and prompt should say so.
3. **Not recommended: narrow the gate.** Exempting AC files whose diff is confined to the
   `product_truth` block would let unproven done ACs pass whenever only their back-reference
   changes. The four ACs here are genuinely unproven (UXP-524 is a phantom done), and the gate
   found them. Fix the proof, not the gate.

**Related.** `KI-BP-20260910-1240` (Occurrence 5): the same generator writes these AC files with
CRLF on Windows.

**Pattern:** a derived back-reference that copies parent-level data into every child record, so
an edit to the parent rewrites records owned by another surface and wakes that surface's gates.
