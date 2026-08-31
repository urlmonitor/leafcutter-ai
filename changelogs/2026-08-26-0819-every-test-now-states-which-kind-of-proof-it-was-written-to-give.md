---
title: "Every test now states which kind of proof it was written to give, read by the same scanner that reads its covers tag"
date: "2026-08-26"
time: "08:19"
type: manual
components:
  - build_pipeline
  - testing_quality
summary: "BP-1100g-1 taught test-writer seven proof kinds nobody asked it to use. This adds the ask: an `# angle: <kind>` tag beside the existing `# covers:` tag, collected for the same test function by one scanner in one pass, reporting any kind outside the taught set -- and feeding no pass, done, or eligibility decision anywhere."
description: "BP-1100g-3. The chain is: g-1 taught the vocabulary, g-3 makes the writer state it, g-4 will refuse a promised kind that was never claimed. g-1 alone changed nothing observable. This adds the second tag axis. templates/agents/test-writer.md gains a `2i.1` subsection instructing every test function to carry `# angle: <kind>` alongside `# covers:`, sourced in priority order from the matching `## Test Requirements` entry's `angle` field, falling back to `criterion` for Then-clause-derived tests and `reachability` for the mandatory reachability test, and never invented -- the tag must be spelled as one of the names inside the `<!-- TAUGHT-TEST-ANGLES:START/END -->` block g-1 added to the same file. Placement mirrors `# covers:` exactly (line above the def, first body line, or docstring) so the writer learns one convention rather than two. On the reading side, scripts/ac_store/done_proof.py's existing scanner is EXTENDED rather than duplicated: `_scan_test_file_for_all_tags` performs one read and one line-walk per file emitting both tag types discriminated by `tag_type`, `_build_function_records` folds them into one record per test function carrying both `covers` and `angles`, and `collect_test_tag_records` walks the tree once. A function present on only one axis keeps the other axis as an empty list -- never omitted, never dropped, never defaulted to None. The pre-existing covers-only view `_scan_single_test_file` is now derived by filtering that same pass, so a parallel second reader cannot drift; drift between two readers of one source is the EPIC-ComputedQualityGates layer-3 failure this AC's constraint exists to prevent. `find_unrecognised_angle_tags` reports any kind outside the permitted set naming the test and the value, without raising and without dropping the record, and reads that set fresh from config/ac_store_schema.json's `test_spec[].angle` enum -- BP-1100g-1's single source -- rather than restating it as a local literal. A latent bug was fixed in passing: the old top-to-bottom scan tracked only the most-recently-seen `def`, so a tag on the line(s) directly ABOVE a def was silently dropped; `_build_lineno_to_function_map` now attributes leading comment blocks forward. That is a change to an input of `verify_done_eligible`, so the blast radius was measured rather than assumed: across all 2,829 `# covers:` tags in unit_tests/, ZERO move. The fix is latent-only and no eligibility input changes today. The fourth Then clause -- that the new axis feeds no pass, done, or eligibility decision -- holds structurally: `_classify_outcomes` and `verify_done_eligible` are byte-for-byte unmodified. The reachability test imports the DEPLOYED .leafcutter/scripts/ac_store/done_proof.py in a fresh subprocess whose sys.path is restricted to that directory, asserting rather than skipping when it is absent, because the source-tree import is structurally blind to the deploy-manifest gap that broke this exact module on 2026-07-22. scripts/commit_guardian/check_test_ac_tags.py -- the second live reader of this tag surface, with its own COVERS_REGEX, in warn mode -- was deliberately not touched; its enforcement mode and verdict are unchanged. NOT CLOSED BY THIS ENTRY: AC-5, the negative control asserting the new tag changes nothing about how a failing test is treated, has implementation evidence but no dedicated test here. It is the subject of sibling AC BP-1100g-3-i, which remains work_status: todo. BP-1100g-3 is therefore an L2 marked done while its constraint child is unfinished -- the shape CLAUDE.md's AC-store-commits rule warns about -- and is recorded here rather than left for a later sweep to discover."
breaking: false
---

## Entry

`BP-1100g-1` taught `test-writer` seven proof kinds. Nothing asked it to use them. This adds the ask.

**The authoring side** — `templates/agents/test-writer.md` §2i.1. Every test function carries `# angle: <kind>` next to its `# covers:` line, in the same three accepted positions:

```python
def test_merge_executes_before_test_runner():
    # covers: FIN-001
    # angle: reachability
```

The kind is taken from the `## Test Requirements` entry when there is one, falls back to `criterion` (or `reachability` for the mandatory reachability test) when there is not, and is never invented — it must be spelled as one of the names in the `TAUGHT-TEST-ANGLES` anchor `g-1` added to the same file.

**The reading side** — one scanner, two axes. `_scan_test_file_for_all_tags` reads each file once and walks its lines once, emitting both tag types. The pre-existing covers-only view is now *derived* from that pass by filtering, so there is no second reader to drift. A test on only one axis keeps the other axis present-but-empty rather than vanishing.

**A latent bug fixed in passing, with its blast radius measured.** The old scan tracked only the nearest preceding `def`, so a tag on the line above a `def` was silently dropped. That is a change to an input of `verify_done_eligible`, so it was measured, not assumed:

```
covers tags attributed by OLD scanner: 2829
covers tags NEWLY attributed (were silently dropped): 0
```

Latent-only. No eligibility input moves today.

**The fourth clause holds structurally, not by assertion.** `_classify_outcomes` and `verify_done_eligible` are unmodified — the diff ends before either. The angle axis is a planning declaration; nothing consumes it in a verdict.

**The second reader was left alone.** `scripts/commit_guardian/check_test_ac_tags.py` has its own `COVERS_REGEX` and runs in warn mode. Its enforcement mode and verdict are unchanged.

**Not closed.** AC-5 — the negative control proving the new tag changes nothing about how a failing test is treated — has implementation evidence but no test of its own here. That is sibling `BP-1100g-3-i`, still `work_status: todo`. So `BP-1100g-3` is an L2 marked `done` with an unfinished constraint child: the exact shape the AC-store-commits rule in `CLAUDE.md` warns about. Recorded here rather than left for a later sweep to find.
