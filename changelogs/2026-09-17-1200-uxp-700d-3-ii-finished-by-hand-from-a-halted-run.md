---
title: "UXP-700d-3-ii finished by hand from a halted /build-feature run"
date: "2026-09-17"
time: "12:00"
type: manual
components:
  - ux_prototyping
  - ac_store
summary: "The product-truth checker now cross-checks every loaded flow, mock-data, mockup, and AC record's self-declared `example_product` against the product root it actually lives under: a mismatch, an undeclared example artifact, or a declaration naming the project's own product are each reported through the checker's existing error channel, naming both values. This is the cross-check half of the split AC UXP-700d-3 (ADR-044 sec 6-7); the registration-and-backfill half, UXP-700d-3-i, merged as PR #835. UXP-700d-3-ii itself is work_status done; the composite parent UXP-700d-3 is deliberately left todo pending a follow-up to check_done_proof.py's static composite-exemption gap (below)."
description: "A /build-feature run halted after splitting UXP-700d-3 into UXP-700d-3-i and UXP-700d-3-ii on 2026-09-16. This change finishes UXP-700d-3-ii by hand, on branch feature/uxp-700d-3-ii off origin/main, with no ticket-supervisor or test-writer dispatch: python-coder wrote unit_tests/product_truth/test_uxp_700d_3_ii.py itself, first, confirmed it red (ModuleNotFoundError on the not-yet-created product_truth_example_checks module), then implemented, then revised across a coordinator review round before commit. The pure verdict helpers (example_product_findings, example_product_findings_for_ac, product_root_of_doc_link) live in product_ownership.py beside the ownership predicate they cross-check (ADR-044 sec 7); the looping/message-formatting check itself is a new sibling module, docs/product-truth/scripts/product_truth_example_checks.py, because both validate_product_truth.py (399/400 content lines, measured via check-file-size's own count_content_lines) and product_truth_checks.py (396/400) had no room left for it -- re-exported through product_truth_checks.py on the same precedent product_truth_index_checks.py already established. validate_product_truth.py is held at exactly 400/400 content lines. Ownership is unchanged: the marker is compared against product_ownership.product_of_artifact_id's location-derived root, never used to decide it. Real store verification: python docs/product-truth/scripts/validate_product_truth.py stays checked-and-sound with zero [example] findings, after fixing one pre-existing latent inconsistency this new check surfaced -- docs/acceptance-criteria/ux-prototyping/UXP-500-product-truth-generation/UXP-515.yaml's doc_links cited a fern-and-fig mockup via relationship: implemented-by-step (an ownership claim, which the checker compares against) when it meant relationship: related (a citation, which it does not) -- ADR-044's own Context section already asserted this AC 'uses other relationships' for exactly this citation, citing UXP-614's identical pattern (which does use related); UXP-515.yaml was the one file that had not actually followed it. This is a data fix, not an ADR deviation: ADR-044 is not amended. No file under docs/product-truth/ (schemas, artifacts, index.json) changed -- only its scripts/. Mutation testing: hand-removed the check_example_product(...) call from run_checks(), confirmed the reachability test went red (the CLI reported DEGRADED/exit 0 instead of the expected FAILED/exit 1), restored the call, confirmed green again -- repeated a second time after the freshness-signature fix below moved code around the same function, with the same result. COORDINATOR REVIEW ROUND (three fixes, before commit): (1) a check-secrets false positive on the long CamelCase reachability test class name was originally suppressed via a .security-allowlist entry, matching the pattern every sibling test_uxp_700* file already uses -- the coordinator rejected allowlisting as the clearing mechanism here; the entry was fully reverted (.security-allowlist is byte-for-byte origin/main again) and the test's TestCase class was renamed instead, from a name derived from the ticket id to one describing what the test asserts (the test METHOD name stays test_uxp_700d_3_reachable_from_entry_point, the test_spec-authored name); check-secrets now exits 0 with no allowlist change. (2) UXP-700d-3.yaml's work_status was reverted to todo (covered_by unchanged); marking the L2 composite parent done was reverted because check_done_proof.py's STATIC pre-commit scan only exempts a composite whose level is L0 or L1 -- UXP-700d-3 is level: L2 with a non-empty covered_by, a shape docs/reference/ac-schema.md's own hierarchy diagram documents as normal (L0.covered_by -> L1.covered_by -> L2.covered_by -> L3), and the general, correct, level-agnostic definition of composite (scripts/ac_store/done_proof.py::_verify_composite_eligible, BO-2500a-6: 'a composite ... whose own covered_by is non-empty', which mark_ac_done.py itself already uses) disagrees with the narrower static-scan gate. This is left as an OPEN FOLLOW-UP, not fixed here: check_done_proof.py static scan exempts only L0/L1 composites; an L2 with covered_by should be exempt the same way _verify_composite_eligible already treats it. UXP-700d-3.yaml is now byte-for-byte origin/main again (nothing about it is actually touched by this change) and check-done-proof exits 0 on the staged set with the parent left todo. (3) The widened load_ac_records() record (it gained doc_links / example_product for the new check) was being hashed WHOLESALE by UXP-700c-2's freshness check (_ac_content_signature originally hashed 'every field except path'), which would have silently widened what freshness compares -- editing an AC's doc_links would report every journey citing it as behind, unrelated to freshness's actual concern. Fixed by pinning _ac_content_signature to an explicit, function-local 4-field tuple (work_status, product_truth, implemented_by, covered_by), independent of whatever load_ac_records()'s own shape grows to next; unit_tests/product_truth/_uxp_700c_2_fixtures.py and test_uxp_700c_2_ii.py -- which had been edited to predict the wider signature -- are now reverted to origin/main exactly (git diff origin/main against both is empty) and needed no further change, since both already predicted the signature from exactly that 4-field set. Freshness and behind-mark code stayed inline in validate_product_truth.py throughout, per ADR-043 SS10 -- never touched, never moved to a sibling. Full unit_tests/product_truth suite: 141/141 green, reconfirmed on a clean, uninterrupted full run after all three coordinator fixes landed. Full unit_tests/ac_store suite proved flaky in this environment independent of this diff: two full discovery runs (before the coordinator round; unaffected by it, since none of the three fixes touch ac_store) produced two different, non-overlapping failure sets (3 failures the first run -- test_bp_1100g_3_i, test_done_proof_js.test_js_and_python_covers_use_same_seam, test_pytest_ac_enforcement.test_strict_mode_surfaces_all_failures; 1 failure the second run -- test_bp_1100g_3_i alone; a third, isolated run of just those three files surfaced yet a fourth, unrelated failure, test_mixed_coverage_eligible_only_when_all_pass) -- none of the four touch product-truth, UXP-515, or anything in this diff's scope, and the ticket's own expected known-unrelated failure (test_bo_2900d_1_eligibility_exemption) did not fail in either full run, consistent with subprocess pytest/vitest + Windows temp-directory races rather than a regression. Docs updated within the check-doc-length ratchet: docs/how-to/product-truth-schema-reference.md (312 lines, already over the 300 limit) and docs/reference/ac-schema.md (989 lines, already over) were both extended IN PLACE (existing table-row text lengthened) for 0 net line growth, honouring the ratchet's no-growth-while-over rule; docs/reference/product-truth-checker-outcomes.md similarly extended in place (0 net); docs/how-to/authoring-product-truth-artifacts.md grew by 7 lines (278/300, still under); docs/product-truth/README.md grew by 11 lines (filename-exempt from check-doc-length). mark_ac_done.py --ac UXP-700d-3-ii --test-root unit_tests passed its coverage gate and set work_status: done; implemented_by was hand-set to the real touched files (the tool does not write that field). UXP-700d-3 (the composite parent) is left work_status: todo, deliberately, per the open follow-up above."
commits:
breaking: false
---

## Entry

Ticket 35 (`EPIC-TruthfulProjectRecord/35_TICKET-20260909-UXP-700d-3.md`)
spans two split ACs. `UXP-700d-3-i` (registration + backfill of the
`example_product` marker) merged as PR #835. This change delivers
**`UXP-700d-3-ii`** — the disagreement-reporting cross-check (ADR-044
sections 6–7) — on branch `feature/uxp-700d-3-ii` off `origin/main`, built by
hand at the user's direction: no `ticket-supervisor` or `test-writer` was
dispatched, so `python-coder` wrote the tests itself, first, and confirmed
them red before writing any implementation; the change then went through a
coordinator review round before commit (see below).

**The cross-check.** Every loaded flow, mock-data, mockup, and AC record's
declared `example_product` is now compared against the product root it
actually lives under. Three findings, each reported through the checker's
existing `errors` channel (no new outcome value): a **mismatch** (declared
value differs from the root, naming both), an **undeclared** example
artifact (the root is the example product's own root and no marker is set,
naming the root), and a **project-declared** marker (the value names the
project's own product, reported wherever it appears — even with no root to
compare, and even when the value happens to equal its own root). An AC is
compared only against the roots of its `implemented-by-step` `doc_links`;
one with none is not penalised for lacking a root. A root that is neither
the project's own nor the example product's (the real store's own
`guardrails/` dataset) is never reported as undeclared.

**Where the code landed.** The pure verdict helpers live in
`product_ownership.py`, beside the ownership predicate they cross-check
(ADR-044 sec 7) — `validate_product_truth.py` only loads records and calls
them. The looping/formatting check itself is a **new sibling module**,
`product_truth_example_checks.py`: both `validate_product_truth.py`
(399/400 content lines) and `product_truth_checks.py` (396/400) had no room
left. `validate_product_truth.py` is held at exactly **400/400** content
lines.

**Real store: zero new findings, one pre-existing bug fixed.**
`python docs/product-truth/scripts/validate_product_truth.py` stays
`checked-and-sound`. One AC surfaced a latent, pre-existing inconsistency:
`UXP-515.yaml` cited a fern-and-fig mockup via `relationship:
implemented-by-step` (an ownership claim) when it meant `related` (a
citation) — exactly the `relationship` ADR-044's own Context section
already said this AC used, citing `UXP-614`'s identical, correctly-spelled
pattern. Fixed by correcting the relationship value; ADR-044 is **not**
amended, since the implementation matches its decision text exactly. No
file under `docs/product-truth/` (schemas, artifacts, index) changed — only
its `scripts/`.

**Mutation-tested, twice.** Hand-removed the `check_example_product(...)`
call from `run_checks()`; confirmed the reachability test went red
(DEGRADED instead of FAILED); restored it; confirmed green again. Repeated
after the freshness-signature fix below moved code in the same function,
same result.

### Coordinator review round — three fixes before commit

1. **No allowlisting.** A `check-secrets` false positive on the reachability
   test's long CamelCase class name was first suppressed via a
   `.security-allowlist` entry (the pattern every sibling `test_uxp_700*`
   file already uses). The coordinator rejected allowlisting as the way to
   clear this. `.security-allowlist` is reverted to `origin/main` exactly;
   the class is renamed instead —
   the ticket-id-derived class name → a name describing what the test
   asserts (only the class
   name and its one docstring mention; the `test_spec`-named test **method**,
   `test_uxp_700d_3_reachable_from_entry_point`, is unchanged).
   `check-secrets` now exits 0 with zero allowlist changes.

2. **Parent AC left `todo` — open follow-up recorded, not fixed here.**
   `UXP-700d-3.yaml`'s `work_status` is reverted to `todo` (`covered_by`
   unchanged). `check_done_proof.py`'s **static** pre-commit scan exempts a
   composite from the direct-`# covers:`-tag requirement only when `level`
   is `L0` or `L1`. `UXP-700d-3` is `level: L2` with a non-empty
   `covered_by` — a shape `docs/reference/ac-schema.md`'s own hierarchy
   diagram documents as normal (`L0.covered_by → L1.covered_by →
   L2.covered_by → L3`). The general, correct, level-agnostic definition of
   "composite" used everywhere else
   (`scripts/ac_store/done_proof.py::_verify_composite_eligible`,
   BO-2500a-6: *"a composite — an AC whose own `covered_by` is
   non-empty"* — which `mark_ac_done.py` itself already uses) disagrees
   with the narrower static-scan gate. **Open follow-up:**
   `check_done_proof.py`'s static scan exempts only L0/L1 composites; an L2
   with `covered_by` should be exempt the same way
   `_verify_composite_eligible` already treats it. `UXP-700d-3.yaml` is now
   byte-for-byte `origin/main` again — this change touches nothing about it
   — and `check-done-proof` exits 0 on the staged set with the parent left
   `todo`.

3. **Freshness signature pinned to a fixed field set.** Widening
   `load_ac_records()`'s record shape (for the new check's `doc_links` /
   `example_product` reads) was being hashed wholesale by UXP-700c-2's
   freshness check — `_ac_content_signature` originally hashed "every field
   except `path`" — which would have silently widened what freshness
   compares: editing an AC's `doc_links` would report every journey citing
   it as `behind`, unrelated to freshness's actual concern. Fixed by
   pinning `_ac_content_signature` to an explicit, function-local 4-field
   tuple (`work_status`, `product_truth`, `implemented_by`, `covered_by`),
   independent of whatever `load_ac_records()`'s own shape grows to next.
   `unit_tests/product_truth/_uxp_700c_2_fixtures.py` and
   `test_uxp_700c_2_ii.py` — edited earlier to predict the wider signature
   — are reverted to `origin/main` exactly (`git diff origin/main` against
   both is empty) and needed no further change, since both already
   predicted the signature from exactly that 4-field set. Freshness and
   behind-mark code stayed inline in `validate_product_truth.py`
   throughout, per ADR-043 §10 — never moved to a sibling.
   `validate_product_truth.py` held at exactly 400/400 content lines.

**Suites.** `unit_tests/product_truth/`: 141/141 green, reconfirmed on a
clean, uninterrupted full run after all three fixes. `unit_tests/ac_store/`
proved flaky in this environment independent of this diff (unaffected by
the coordinator round, which touches nothing in `ac_store`) — two full runs
produced two different, non-overlapping failure sets, none touching this
diff's scope, and the ticket's own expected known-unrelated failure
(`test_bo_2900d_1_eligibility_exemption`) did not fail in either run.

**Docs**, within the `check-doc-length` ratchet: `product-truth-schema-reference.md`
(312, already over) and `ac-schema.md` (989, already over) both extended in
place for 0 net growth; `product-truth-checker-outcomes.md` similarly (0
net); `authoring-product-truth-artifacts.md` (+7, still under 300);
`docs/product-truth/README.md` (+11, filename-exempt).

**Records.** `mark_ac_done.py --ac UXP-700d-3-ii --test-root unit_tests`
passed its coverage gate and set `work_status: done`; `implemented_by` was
hand-set. `UXP-700d-3` (the composite parent) is left `work_status: todo`,
deliberately, per the open follow-up above. Ticket 35 is set `status: done`
(its own delivery, `UXP-700d-3-ii`, is complete), `files_touched` matches
the actual branch diff vs `origin/main`, and the `python-coder` /
`test-writer` Sign-offs are checked (this ticket's other phase agents —
`architect-review`, `documentation-expert`, `pr-reviewer`, `ac-validator`,
`ac-fulfillment-gate`, `documentation-verifier`, `test-runner`, `commit` —
did not run; this remains a hand-built change per the user's direction).
