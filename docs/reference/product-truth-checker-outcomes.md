---
title: "Reference: What Each Product-Truth Checker Outcome Licenses You to Conclude"
description: "The four-value outcome vocabulary validate_product_truth.py reports on its last stdout line -- checked-and-sound, nothing-examined, degraded, failed -- what a reader may and may not conclude from each, the soundness rule that produces nothing-examined, how that rule differs from the project's fail-open convention, and which checks are deliberately exempt from it."
type: reference
status: active
created: 2026-09-16
last_updated: 2026-09-17
components:
  - ux_prototyping
  - documentation_system
related_docs:
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml
  - docs/reference/ac-schema.md
  - docs/architecture/adrs/ADR-042-product-truth-checker-outcome-vocabulary.md
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700b-1.yaml
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700b-2.yaml
  - docs/reference/product-truth-size-bounds.md
  - docs/product-truth/README.md
related_code:
  - docs/product-truth/scripts/validate_product_truth.py
  - docs/product-truth/scripts/product_truth_outcome.py
  - docs/product-truth/scripts/product_truth_checks.py
  - unit_tests/product_truth/test_uxp_700b_1.py
  - unit_tests/product_truth/test_uxp_700b_1_i.py
  - unit_tests/product_truth/test_uxp_700b_2.py
  - unit_tests/product_truth/test_uxp_700c_1_i.py
---

# What Each Product-Truth Checker Outcome Licenses You to Conclude

`docs/product-truth/scripts/validate_product_truth.py` is the checker for the project
record (journeys/`flows`, example datasets/`mock-data`, screens/`mockups`). Every run
prints one JSON object on its **last stdout line** carrying an `outcome` field drawn
from a closed, four-value vocabulary. This page is the lookup table for that field:
what each value means, what a reader may conclude from it, and — just as important —
what a reader may **not** conclude from it. The vocabulary itself is governed by
[ADR-042](../architecture/adrs/ADR-042-product-truth-checker-outcome-vocabulary.md);
this page restates it as a reader's lookup table rather than a decision record.

The underlying house principle is
[`GE-120` — "green means it was checked, never 'it could not run'"](../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml).
This checker is one instance of that principle, applied to the record's own
truthfulness: a run that found no errors because it looked and found nothing wrong
must never be reported the same way as a run that found no errors because it never
looked at all.

---

## The four outcomes

| `outcome` value | Meaning | You may conclude | You may **not** conclude |
|---|---|---|---|
| `checked-and-sound` | Zero errors, and the run genuinely examined the record: it did not examine nothing, no journey was unreadable, and no `implements` pointer was left unclassified. | Every check that ran found nothing wrong in what it read; the record is not currently empty; nothing was silently skipped by a check that then still claimed a clean pass. | That **every** artifact type is non-empty — a record can hold journeys but no screens or example data yet ("young, not defective" — see [Partial emptiness](#partial-emptiness-is-not-degradation) below) and still report `checked-and-sound`. Nor that every optional check ran — see [Exempt checks](#exempt-checks-not-executed-is-not-the-same-as-silently-omitted). Nor that there were zero warnings; a sound run can still log `WARN:` lines. |
| `nothing-examined` | Zero errors, but **every** one of the three core artifact types (`flows`, `mock-data`, `mockups`) held zero records. The run completed; there was nothing in the record for it to check. | The record currently holds no journeys, no example datasets and no screens; nothing about the record was verified this run. | That the record is broken or invalid — it isn't; the run exits `0`. And do not read this as "everything is fine" either: it is the opposite of that claim, stated plainly instead of hidden inside a clean-looking exit code. |
| `degraded` | Zero errors, but the run could not vouch for everything it was asked to check. Two distinct causes collapse into this one value (see [below](#degraded-has-two-causes-you-cannot-tell-apart-from-outcome-alone)): an unreadable journey file, or an `implements` pointer the checker could not classify. | Whatever the run *did* manage to read had zero errors; the run completed rather than crashing (the fail-open convention — see [next section](#the-soundness-rule-vs-fail-open-on-an-internal-error)). | That the excluded part is fine. The unreadable journey, or the unresolvable pointer, was never actually checked — that is precisely why it is not `checked-and-sound`. Nor can you tell *which* of the two causes fired from `outcome` alone; read `unreadable` and `unresolvable_pointers` on the same JSON line. |
| `failed` | One or more real schema or cross-reference errors were found (schema violation, broken AC pointer, phantom-done AC without implementation evidence, derived-data drift, a self-declared `example_product` disagreeing with the artifact's actual product root, etc.). | Something concrete is wrong; the process exits `1` and the pre-commit gate blocks the commit. | That the *rest* of the record is sound — errors are collected across every check in one run, so `failed` does not imply the run stopped early or that every other check passed; it implies at least one thing is provably wrong. |

Precedence is fixed and evaluated in this order (`_top_level_outcome` in
[`product_truth_outcome.py`](../../docs/product-truth/scripts/product_truth_outcome.py)):
one or more errors beats everything else (`failed`); otherwise an unreadable journey
beats emptiness (`degraded`); otherwise a wholly empty record beats an unresolvable
pointer (`nothing-examined`); otherwise an unresolvable pointer (`degraded`);
otherwise `checked-and-sound`. A reader who wants the exact rule, not just the
outcome each combination produces, should read that function's docstring — this page
gives you the conclusions, not the branch order.

---

## The soundness rule

**A sound verdict is reported only when every check that claims to have passed read
at least one record.** A check that never read anything is not entitled to be
credited as having passed, because "found nothing wrong" and "found nothing" are not
the same claim, and collapsing them is the exact failure `GE-120` exists to name.

Concretely, that rule is what makes `nothing-examined` exist as its own value instead
of folding into `checked-and-sound`: a run over a record holding zero journeys, zero
example datasets and zero screens produces zero errors — there is nothing to find an
error in — so a checker that only ever reported an exit code would say `0`, identical
to a fully populated record every one of whose checks genuinely passed. The two runs
are observably different only because the outcome field states, in words, that the
run examined nothing.

### Partial emptiness is not degradation

The rule above governs the **whole-run** case — did this run examine anything at
all — not a per-artifact-type completeness requirement. `checked-and-sound` does
**not** require every artifact type to hold at least one record. A record holding
journeys but no screens or example data yet is young, not defective, and reports
`checked-and-sound` if nothing else is wrong; which types are currently empty is
still reported, by name, in `empty_types` on the same JSON line, so the gap is
visible without being treated as a defect.

> This is a deliberate narrowing of ADR-042's original text. §2 of the ADR, as first
> written, withheld `checked-and-sound` from **any** run with an empty artifact type.
> Amendment 2 (2026-09-14) supersedes that clause, resolving a direct contradiction
> between two approved acceptance criteria (`UXP-700b-1-i` vs `UXP-700b-1-ii`) in
> favour of the "young, not defective" reading, per the recorded decision
> `KI-ACD-20260909-2130`. Read `outcome` together with `empty_types` if you need to
> know exactly which types were empty on a `checked-and-sound` run — the field is
> always present, including as an empty list.

### `degraded` has two causes you cannot tell apart from `outcome` alone

`degraded` is intentionally one value covering two different situations, because
`ADR-042` keeps the vocabulary closed at four values rather than growing a fifth:

1. **One or more journeys could not be parsed as JSON at all.** `load_flows()` skips
   the unreadable file, names it, and keeps going rather than crashing the whole run
   — this is the fail-open convention (below) exercised on one bad input. The journeys
   that *did* parse are still fully checked.
2. **One or more `implements` pointers targeted something the checker does not know
   how to classify** — anything that is not shaped like an acceptance-criterion id
   (`is_resolvable_pointer_target` in
   [`product_truth_checks.py`](../../docs/product-truth/scripts/product_truth_checks.py)
   recognises exactly one kind: an AC id). Such a pointer is neither counted as
   resolved nor reported as broken; it is logged at `WARNING` with the prefix
   `[pointer-unresolvable]` (distinct from a genuinely broken pointer's `[pointer]`
   prefix), naming the holding artifact, its position, the target, and the reason.

A reader who needs to know *which* cause produced `degraded` must read the same JSON
line's `unreadable` (list of journey ids) and `unresolvable_pointers` (count) fields
— `outcome` alone does not disambiguate. This is a named, accepted cost in ADR-042
Amendment 1's own consequences section, not an oversight.

---

## The soundness rule vs. fail-open on an internal error

This project has a separate, deliberate, standing convention that `GE-120` states
explicitly and does **not** repeal: a check that hits an **internal** error — a
crash, a parse failure, a git failure — exits `0` with a stderr warning, so a bug in
the checking script itself never hard-blocks an unrelated commit. The distinction
between that convention and the soundness rule above is narrow but load-bearing, and
this checker is the worked example `GE-120`'s own notes point at:

> Fail-open on ONE bad input while the check still ran is fine; reporting SUCCESS
> when the check never ran at all is not. — `GE-120`, "STANDING-RULE CONTRADICTION"

**Worked example — the empty-record run.** Point the checker at a product-truth store
holding zero journeys, zero example datasets and zero screens, with its derived index
regenerated. Every check still *runs* — there is simply nothing for any of them to
read — so no exception is raised, no check crashes, and the exit code is `0` exactly
as it would be for a genuinely sound record. That similarity is the whole problem
`UXP-700b-1` exists to fix: without the `outcome` field, this run and a fully
populated, fully sound run are byte-for-byte the same result from a caller's point of
view. The `outcome` field is what tells them apart: `nothing-examined`, not
`checked-and-sound`, precisely because the rule above treats "found nothing to check"
as disqualifying, while the fail-open convention treats "one input the check could
not parse" as *not* disqualifying the run from completing.

**Contrast — a fail-open (`degraded`) run.** Point the checker at the same kind of
store, but now holding several valid journeys and exactly one journey file containing
malformed JSON. The checker reads and fully checks the valid journeys, skips the
unreadable one (logging `SKIPPED: journey '<id>' is unreadable (invalid JSON) —
examined the other N`), and still exits `0`. This *is* the fail-open convention doing
its job: the bug is in one input, not in the checker, so the run does not hard-block.
But it is not silently rounded up to `checked-and-sound` either — it reports
`degraded`, because the rule above still applies to the part that could not be read.

The difference in one sentence: fail-open decides whether a bad input is allowed to
**stop the run** (it is not, for one malformed input; it is not, for the checker's
own internal errors); the soundness rule decides whether the run, having completed,
is allowed to be called **sound** (it is not, when it examined nothing, and it is
not, when part of what it examined could not be vouched for).

---

## Exempt checks — not-executed is not the same as silently omitted

Two of this checker's checks are structurally exempt from feeding the top-level
outcome at all when their one precondition file is absent, and this is a deliberate
exemption, not an omission that happens to leave them out:

| Check | Precondition | When absent |
|---|---|---|
| `eval` | `classifier/eval.jsonl` | Recorded as **not executed**, with a stated reason (`"precondition absent (not authored yet): ..."` or `"... (not installed): ..."`), via `record_check_not_executed`. |
| `labels` | `docs/acceptance-criteria/index.yaml` | Same: recorded as not executed with a stated reason. |

Both checks are deliberately excluded from `CHECK_READS` — the map `UXP-700b-2` uses
to compute each check's stated `examined` figure — because they state their own
finer figures (eval rows examined, labels resolved) rather than a population count,
and the comment in `product_truth_outcome.py` names the exclusion as intentional. More
importantly for this page: `_top_level_outcome`, the function that decides
`outcome`, takes only `examined`, `unreadable`, `has_errors`, `empty_types` and
`unresolvable_pointers` as inputs. Whether `eval` or `labels` executed at all is
**not** one of them. A run can report `checked-and-sound` while `eval` or `labels`
never ran, because both checks exist to validate an artifact — the classifier
evaluation set, the component registry — that a young record has not authored yet,
and the "young, not defective" reasoning from [partial
emptiness](#partial-emptiness-is-not-degradation) applies to them too.

This is told apart from a silent omission in two ways:

1. **It is named on the log**, every time: `_log_skipped_entries` emits `SKIPPED:
   check '<name>' did not execute — <reason>` for every not-executed check, on
   every run, so a reader watching the prose channel always sees it.
2. **One sub-case still blocks the commit, off the `outcome` channel.** If
   `eval`'s precondition is missing because the `classifier/` directory was never
   installed at all — not merely "not yet authored" — `main()` treats that as the
   tooling itself being incomplete (`UXP-700a-1-i`) and exits `1` with an
   `INCOMPLETE` error, independently of whatever value `_top_level_outcome` computed
   for the JSON `outcome` field on that same run. A reader relying on `outcome`
   alone, without also checking the process exit code, can miss this one case — it
   is called out explicitly here so it is read as a documented boundary of the
   vocabulary, not discovered by surprise.

No other check in this validator is exempt. The fifteen unconditional "population"
checks (`journey-shape`, `example-data-shape`, `screen-shape`, and the rest listed in
`CHECK_READS`) always execute — including over an empty store, where they simply
record an `examined` figure of `0` — and the `pointers` check always executes too.
None of those can be "not executed"; only `eval` and `labels` can.

---

## Where to read the fields yourself

Every run prints exactly one JSON-parseable line, the last line of stdout:

```json
{"outcome": "checked-and-sound", "examined": 12, "unreadable": [], "empty_types": [],
 "resolved_pointers": 9, "unresolvable_pointers": 0, "examined_by_check": {"journey-shape": 12, "...": "..."},
 "resolved_labels": 4, "bounds": {"...": "..."}}
```

Consumers compare `outcome` against exactly the four values in the table above and
must not assert an exact key set — the payload is additive-only (ADR-042 §A6). The
underlying decision record, precedence order, payload shape and full consequences
analysis live in
[ADR-042](../architecture/adrs/ADR-042-product-truth-checker-outcome-vocabulary.md);
this page exists so a reader who only needs "what does this value mean, and what am I
allowed to conclude from it" does not have to read the ADR's alternatives-considered
sections to find out.

---

## See Also

- [`GE-120` — green means it was checked](../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml) — the parent principle this checker implements; owns the fail-open-vs-soundness distinction for the whole commit-guardian surface, not just this checker.
- [ADR-042 — the outcome vocabulary decision record](../architecture/adrs/ADR-042-product-truth-checker-outcome-vocabulary.md) — full rationale, rejected alternatives, and both amendments.
- [`UXP-700b-1`](../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700b-1.yaml) — the AC requiring `nothing-examined` to be distinct from a sound run.
- [`UXP-700b-2`](../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700b-2.yaml) — the AC requiring every check to state how many records it read (`examined_by_check`).
- [Reference: AC Traceability Store Schema](ac-schema.md) — the house style this page follows.
- [Reference: Product-Truth Size Bounds and Shape Rollout](product-truth-size-bounds.md) — the sibling reference for the `bounds` object on the same JSON line.
- [Product-Truth Store](../product-truth/README.md) — what the checker validates.
- `docs/product-truth/scripts/validate_product_truth.py`, `product_truth_outcome.py`, `product_truth_checks.py` — governing code.
- `unit_tests/product_truth/test_uxp_700b_1.py`, `test_uxp_700b_1_i.py`, `test_uxp_700b_2.py`, `test_uxp_700c_1_i.py` — the tests that pin this vocabulary.
