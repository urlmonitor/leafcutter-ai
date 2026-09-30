---
title: "UXP-700d-3-i finished by hand from a halted /build-feature run"
date: "2026-09-17"
time: "09:00"
type: manual
components:
  - ux_prototyping
  - ac_store
summary: "Every example artifact and example acceptance criterion now carries a self-declared `example_product` key naming its product-root slug, held in the artifact's own content rather than inferred from its location; the project's own record carries no such key at all; and the AC-level `product` marker UXP-700d-2 introduced is retired in favour of the same spelling. This is the registration-and-backfill half of the split AC UXP-700d-3 (ADR-044); the disagreement-reporting cross-check is UXP-700d-3-ii, a separate, not-yet-landed ticket."
description: "A /build-feature run halted after splitting UXP-700d-3 (\"every piece of example content says it is an example, read on its own\") into UXP-700d-3-i and UXP-700d-3-ii on 2026-09-16, once the unsplit work was found to span about 38 files. This change finishes UXP-700d-3-i by hand, on a fresh branch off origin/main, with no ticket-supervisor or test-writer dispatch: tests were written first by python-coder itself, confirmed red, then made green. Measured first against the real store: 3 fern-and-fig flows, 10 mockups, 1 mock-data dataset (unchanged from the scratchpad draft's own measurement), and 18 AC yaml files carrying `product: fern-and-fig`. One measured figure in both the draft AC and ADR-044 itself was wrong and was corrected rather than carried forward: scan_ac_store.py's own reported `set_aside_count`, under its default --level leaf --work-status todo filters (leaf, active, readiness: approved), is 3, not 18 -- most of the 18 example ACs are not yet readiness: approved and so never reach the set-aside classification regardless of the marker. The AC's own closing clause and this changelog verify against the real, smaller figure. Implementation: registered `example_product` (optional, pattern `^[a-z0-9-]+$`, never required) on flow.schema.json, mockup.schema.json, and mock-data.schema.json; backfilled it onto all 14 fern-and-fig product-truth artifacts; renamed the AC-level `product` field to `example_product` on all 18 example AC yaml files and in config/ac_store_schema.json's field definition (the old spelling was retired, not duplicated, so it no longer validates); updated scripts/ac_store/scan_ac_store.py's `_is_example_content` to read the new field; found and updated a second, independent copy of the identical predicate in check_done_proof.py (templates/scripts/commit_guardian/, canonical source, rebuilt via build.py) that an initial repo-wide grep for dict-style `.get(\"product\")` access missed because its fixture test wrote raw YAML text (`f\"product: {product}\"`) rather than a dict key -- caught by running the full unit_tests/ac_store/ suite, not by the grep. Three pre-existing unit tests (test_uxp700d2_ready_leaf_scan.py, test_uxp700d2_ii_component_namespace.py, test_uxp700d2_reachability.py) whose fixture builders wrote the old `product:` key were updated in lockstep -- explicitly authorised by test_uxp700d2_ready_leaf_scan.py's own prior note anticipating exactly this rename (Source-of-Truth Discipline Rule 1, test drift). Documentation: added the `example_product` field to docs/reference/ac-schema.md's field table (which also lacked the pre-existing `product` field entirely -- a gap now closed for the surviving name only), docs/how-to/product-truth-schema-reference.md's shared-conventions table, and docs/how-to/authoring-product-truth-artifacts.md's per-kind authoring steps. Several docs (ac-schema.md, product-truth-schema-reference.md) were already over their check-doc-length ratchet limit before this change; new content was kept net line-neutral (a merged See-Also bullet, tightened prose) so the ratchet's crossing/growth refusal was never tripped, rather than the file being split. docs/architecture/adrs/README.md's ADR index was regenerated via `python scripts/adr_refs.py --index --write` to register ADR-044, which surfaced a pre-existing tool defect worth a follow-up ticket: the generator drops the `status`/`created`/`last_updated`/`components` frontmatter fields on every regeneration, requiring a manual restore here to pass check-doc-frontmatter. Running `scripts/build.py --force` (required because check_done_proof.py's canonical source lives under templates/) also surfaced ~70 files of unrelated pre-existing drift between templates/agents/*.md and docs/agents/cards/*.card.md as a CRLF/LF flip-flop across repeated runs; none of it is check-output-drift's concern (verified: output-drift passes identically whether those files are included or reverted to HEAD), and six of them have genuine content drift that would trip check-doc-length if staged, so all ~70 were left untouched as out of this ticket's scope. ADR-044 (copied from an untracked draft in worktree ki-20260914, that source left unmodified) was checked against the split AC criteria and amended: its Operational section named a single monolithic test file (`test_uxp_700d_3.py`) covering all four test angles, contradicting the actual split (`test_uxp_700d_3_i.py` owns real_artifact/boundary, `test_uxp_700d_3_ii.py` owns failure/reachability, not yet authored); its `set_aside_count` operational claim stated 18, which is the wrong (unfiltered) figure per the measurement above; and its Decision sections 5/6 were annotated with the delivering ticket ids to make the registration-before-checker ordering explicit. related_docs was widened to include both child AC files."
commits:
breaking: false
---

## Entry

Ticket 35 (`EPIC-TruthfulProjectRecord/35_TICKET-20260909-UXP-700d-3.md`) was
generated from the unsplit AC `UXP-700d-3`. The user split that AC into
`UXP-700d-3-i` and `UXP-700d-3-ii` on 2026-09-16 after a `/build-feature` run
halted on discovering the unsplit work spanned about 38 files. This change
delivers **`UXP-700d-3-i` only** — registration and backfill, with no
cross-check — on branch `feature/uxp-700d-3-i` off `origin/main`, built by
hand at the user's direction: no `ticket-supervisor` or `test-writer` was
dispatched, so `python-coder` wrote the tests itself, first, and confirmed
them red before writing any implementation.

**The marker.** Every example artifact (a fern-and-fig journey, screen, or
dataset) and every example acceptance criterion now carries a top-level
`example_product` key whose value is the product-root slug (`fern-and-fig`),
readable from the artifact's own file content alone. The project's own
record carries no such key — not even an empty or null one. The three
product-truth schemas register the key as optional and never required; the
AC store's older `product` field (UXP-700d-2) is retired in the same change,
not kept alongside the new spelling.

**Measured, not assumed.** Before touching anything: 3 fern-and-fig flows,
10 mockups, 1 mock-data dataset; 18 AC yaml files carrying
`product: fern-and-fig`. These matched the scratchpad draft's own
measurement. One figure did not match ADR-044's own operational claim:
`scan_ac_store.py`'s reported `set_aside_count` (its default filters — leaf,
`work_status: todo`, active, `readiness: approved`) is **3**, not 18 — 15 of
the 18 example ACs are not yet `readiness: approved` and never reach the
set-aside classification regardless of the marker. ADR-044 and this
changelog verify against the real figure.

**A predicate had a second, independent copy the first grep missed.**
`scripts/ac_store/scan_ac_store.py::_is_example_content` was the known
target. `scripts/commit_guardian/check_done_proof.py` (canonical source:
`templates/scripts/commit_guardian/check_done_proof.py`) turned out to carry
an identical, hand-duplicated copy of the same predicate, exempting done
example ACs from the covers-tag gate. A repo-wide grep for
`.get("product")`/`["product"]` missed it because its own test fixture
built AC yaml as raw text (`f"product: {product}"`), not a dict literal —
the gap surfaced only when the full `unit_tests/ac_store/` suite was run and
`test_uxp700d2_done_proof_exempts_example.py` went red. Both copies were
renamed in lockstep, and three further pre-existing fixture files
(`test_uxp700d2_ready_leaf_scan.py`, `test_uxp700d2_ii_component_namespace.py`,
`test_uxp700d2_reachability.py`) that wrote the old field were updated —
`test_uxp700d2_ready_leaf_scan.py`'s own prior note had explicitly
anticipated exactly this rename as permitted test drift.

**Docs.** `example_product` was added to `docs/reference/ac-schema.md`'s
field table (which had never documented the pre-existing `product` field
either — closed for the surviving name only), to
`docs/how-to/product-truth-schema-reference.md`'s shared-conventions table,
and to `docs/how-to/authoring-product-truth-artifacts.md`'s per-kind
authoring steps. Two of those docs were already over their `check-doc-length`
ratchet limit; new content was kept net line-neutral (merged a `See Also`
bullet, tightened prose) rather than triggering a split.

**ADR-044**, copied verbatim from an untracked draft in worktree
`ki-20260914` (left unmodified there), was checked against the actual `-i`
/ `-ii` split and corrected: its Operational section named one monolithic
test file for all four test angles, when the split puts `real_artifact` +
`boundary` in `test_uxp_700d_3_i.py` (this change) and `failure` +
`reachability` in `test_uxp_700d_3_ii.py` (not yet authored); its
`set_aside_count` claim of "18" was corrected to the real measured figure
of 3; and Decision sections 5 and 6 were annotated with the delivering
ticket id, making explicit that registration-and-backfill (`-i`) lands
strictly before the cross-check (`-ii`) — landing the checker first would
report every existing example item as undeclared and refuse its own commit.
`related_docs` was widened to include both child AC yaml files. The ADR
index (`docs/architecture/adrs/README.md`) was regenerated via
`python scripts/adr_refs.py --index --write`, which surfaced a pre-existing
generator defect (worth its own ticket): it drops the `status`/`created`/
`last_updated`/`components` frontmatter fields on every run, requiring a
manual restore here to pass `check-doc-frontmatter`.

**Out-of-scope drift, deliberately left untouched.** `scripts/build.py
--force` was required (`check_done_proof.py`'s canonical source lives under
`templates/`) and surfaced roughly 70 files of pre-existing drift between
`templates/agents/*.md` and `docs/agents/cards/*.card.md` — mostly a
CRLF/LF flip-flop that reappears on every rerun, plus six cards with genuine
content drift. `check-output-drift` was verified to pass identically whether
those six files are staged or reverted to `HEAD`; staging them trips
`check-doc-length` (three are already over its limit and would grow
further). All ~70 were left at their committed content — unrelated to this
ticket's scope.

**Verification.** `unit_tests/product_truth/test_uxp_700d_3_i.py`'s three
tests (real_artifact, boundary, and an added seam test comparing
`scan_ac_store`'s reported `set_aside_count` against an independent recount
using the module's own filter predicates, so the assertion never hard-codes
a figure) were confirmed red before implementation and green after.
Mutation-tested: removed `example_product` from one fern-and-fig flow,
confirmed the real_artifact test went red for exactly that reason, restored
it, confirmed green again. Full suites: `unit_tests/product_truth/` — 131
passed (128 pre-existing + 3 new, matching the ticket's own stated
baseline); `unit_tests/ac_store/` — 687 passed, 3 skipped, 1 pre-existing
failure unrelated to this change deselected (`test_bo_2900d_1_eligibility_exemption`,
an exemption-inventory reachability test with no reference to the `product`/
`example_product` field at all). `python docs/product-truth/scripts/validate_product_truth.py`
reports `"outcome": "checked-and-sound"` against the real store, unchanged.
`generate_product_truth.py` was not run standalone this pass since no
generator-derived field changed; the validator's own run against the
already-backfilled store produced zero unexpected findings. `mark_ac_done.py
--ac UXP-700d-3-i --test-root unit_tests` passed its coverage gate and set
`work_status: done`; `implemented_by` was hand-set to the real touched files
(the tool does not write that field). Ticket 35 itself is left `status: todo`
with its Sign-offs unchecked — no phase agent ran against it directly — and
its `ac_traceability` was widened from the two-key `{id, path}` form (which
names exactly one AC) to the list form (`l3: [UXP-700d-3-i, UXP-700d-3-ii]`,
`ac_path: ...`), since this ticket now spans two ACs and only one has
landed.
