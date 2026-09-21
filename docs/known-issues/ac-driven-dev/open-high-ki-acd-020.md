---
title: "KI-ACD-020 — Non-interactive epic generation drops every unapproved leaf AC without naming one of them"
description: "KI-ACD-020 — Non-interactive epic generation drops every unapproved leaf AC without naming one of them"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-020 — Non-interactive epic generation drops every unapproved leaf AC without naming one of them

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py:1449-1455` — `_gate_select_approved_ids()`, the
  `if yes or approved_only:` branch; and its caller `run()` at `:2252-2264`

**Symptom.** `goal_to_epic.py --ac <goal> --yes` (or `--approved-only`) generates an epic
containing only the leaves that were already `readiness: approved`. Every leaf below
`approved` is silently excluded: it is not listed, not counted, not warned about. The run
exits 0 and reports success, and the epic looks complete because nothing in its output
refers to what is missing.

**Evidence — probed directly against the real function.**

```text
--yes            returns=['GE-999a-1', 'GE-999a-2']
--yes            stdout=''
--approved-only  returns=['GE-999a-1', 'GE-999a-2']
--approved-only  stdout=''
```

Input was two approved and two unapproved ids (`reviewed`, `draft`). Both flags returned
the identical two-element list and **wrote nothing to stdout at all**. The caller then does
`leaf_ids = approved_ids` with no further notice.

**Two distinct defects, and the second is the reason the first is invisible.**

1. **The two flags are behaviourally identical.** Both enter the same branch and return
   `list(readiness["approved"])`. Their help text presents them as different operations —
   `--yes` as *"equivalent to choosing 'yes' at the interactive prompt"*, `--approved-only`
   as *"filter to only already-approved leaf ACs and skip unapproved ones"*. A caller
   reading that help reasonably expects `--yes` to be the permissive option. There is no
   non-interactive way to include an unapproved leaf; `--yes` is a misleading name for
   "skip everything not approved".

2. **The exclusion is never reported.** `_print_readiness_report()` — which exists and
   names every unapproved id and its readiness value — is called only from
   `readiness_gate_prompt()`, the interactive path. The flag branch returns before it.
   Note the asymmetry this creates in `run()`: the **all-approved** path calls
   `print_fast_path_message()` and announces itself, while the **partial** path says
   nothing. The complete run is the one that reports; the incomplete run is silent.

**Why this matters more than a missing log line.** Epic generation is the step that decides
what gets built. A goal AC is decomposed into leaves precisely because the leaves are the
work; dropping a subset produces a well-formed epic that omits part of its own goal, with a
Master_Plan that reads as authoritative. Encountered on `--ac GE-122d`, where three of the
nine leaves were `readiness: reviewed` — and those three were the registration work the
epic exists to deliver. Either flag would have produced a six-ticket epic whose purpose had
been removed from it, exit 0, no warning. Caught only because the readiness values were
checked by hand first.

This is a false-green of the `M1` family (`docs/reference/false-green-mechanisms.md`): a
successful-looking result whose scope silently shrank.

**Fix direction.** Two things, and the second matters even if the first is contested:

- Print the readiness report in the non-interactive branch too, and follow it with an
  explicit line naming the count and ids being excluded. Reuse `_print_readiness_report()`
  — it already formats exactly this.
- Give the flags distinct meanings, or collapse them. If `--yes` is meant to be
  "proceed with what is approved", it should say so; `--approved-only` is then a redundant
  alias and should be documented as one. If instead `--yes` was intended to mean "treat
  reviewed leaves as good enough", that is a real behaviour to build, and its absence is
  why the current naming misleads.

A regression test should assert on **stdout**, not just on the returned list — the returned
list is correct under the current design, and the defect lives entirely in what is not
said.

**Pattern:** a narrowing applied silently on the path that has no human watching, while the
path that does have one reports fully.

---
