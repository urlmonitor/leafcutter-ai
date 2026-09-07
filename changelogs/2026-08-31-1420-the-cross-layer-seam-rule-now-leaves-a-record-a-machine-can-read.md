---
title: "The cross-layer seam rule now leaves a record a machine can read"
date: "2026-08-31"
time: 1420
type: manual
components: 
  - build_pipeline
  - testing_quality
summary: "Every hand-off from the test-writing side now carries exactly one machine-readable answer to the cross-layer seam rule, under one fixed key, with an honest no as a first-class outcome."
description: "Implements BP-1100g-5. The seam rule — decide whether the work sits at a boundary between two layers and, if it does, feed the real producer's real output into the real consumer — is one of the highest-value rules in the corpus and was the only one mandating nothing observable. Rule 1 next to it demands an exact machine-checkable label; Rule 3 demanded nothing, so a reachability mandate could be satisfied by a renamed criterion test and nothing downstream could tell. The answer now rides the existing completion_manifest under the fixed key cross_layer_seam_answer, spelled verbatim in both templates/agents/test-writer.md Rule 3 and templates/skills/signoff/SKILL.md §2b.2, in one of two conforming shapes: {result: covered, producing_side, consuming_side}, where naming both sides is required because 'seam covered: yes' is not an answer a reader can act on, or {result: not_applicable, reason, remediation}. The negative is a first-class conforming outcome rather than a failure or a skip, because a writer forced to produce a seam will invent one, and a fabricated covered claim costs a real test's worth of effort and produces a false record. The three non-conforming states are named for the reader that BP-1100g-5-i will build: absent, reasonless, answered-more-than-once. A reasonless negative is deliberately left physically writable so that reader has something to detect. The record is a declaration by the writer: it is not evidence the seam test is any good, it feeds no done, pass or eligibility decision, and nothing here inspects a test to check it."
breaking: false
---

## Entry

The cross-layer seam rule has applied to all work since it was rescoped on 2026-08-14, and
until now it was unfalsifiable. Sitting directly beside it, Rule 1 requires an exact
machine-checkable token in the work record. Rule 3 required nothing at all. That asymmetry is
the whole defect: the failure mode named in `docs/testing/test-angles.md` is that a
reachability mandate "can quietly be satisfied by a renamed criterion test", and a writer
handed an unresolvable request does the cheapest thing while nothing downstream can tell.

Every hand-off now carries exactly one answer per work item, under `cross_layer_seam_answer`,
in the sign-off's existing `completion_manifest` — not in a second artifact, and not in prose
a reader has to interpret.

Two shapes conform. A covered answer must name **both** the producing side and the consuming
side; `result: covered` on its own is rejected, because a reader cannot act on it without
knowing which two things were pinned together. A not-applicable answer must carry a non-empty
reason. "No seam applies, because this work is a pure function with no consumer outside its
own module" is a complete and honest answer with the same standing as a covered seam.

That last point is load-bearing rather than decorative. If an honest negative were treated as
a failure or a skip, the rule would pressure writers into fabricating seam claims, and a
fabricated claim is strictly worse than no artifact — it costs a real test's worth of effort
and leaves a false record behind.

### The negative spells `not_applicable`, not `false`

The obvious encoding would reuse `{result: false, reason, remediation}`, the nested shape the
manifest already uses elsewhere. This deliberately does not. What protects the key from the
§2b Bare-False Rule's automatic supervisor retry is the nested-object **structure** — never a
bare scalar — and that is a structural property, independent of which string fills `result`.
Given the choice is free, `not_applicable` is the honest one: a reasoned negative is not a
failed checklist item, and generic tooling that scans a manifest for `result: false` to find
failures must not trip over it.

`not_applicable` is a new enum value — it had zero occurrences anywhere under `templates/` or
`scripts/` before this change — so nothing validates its spelling yet. That validator is
`BP-1100g-5-i`, and the exact strings have been pinned into both ACs so the reader is built
against what this change actually emits rather than against a re-derivation of it.

### What this change is not

The recorded answer is a **declaration**. It is a statement the writer wrote about their own
work. It is not evidence that the seam test is any good, it contributes to no done, pass or
eligibility decision, and nothing here inspects a test to check whether the declaration is
true. Whether the seam was really covered is a separate question belonging to an execution
observer, and conflating the two would turn a useful record into a false proof.

No tests accompany this change, and that is deliberate rather than an omission: every clause
describes what an LLM agent writes into its own sign-off record, which no unit test can
produce. The two available proxies are both dishonest — grepping the template for the mandate
asserts prose presence rather than compliance, and validating a hand-typed manifest asserts
the fixture rather than the writer. The falsifiable half lives in `BP-1100g-5-i`, which reads
the records a run actually emitted; `BP-1100g-5` is composite and takes its proof from there.
