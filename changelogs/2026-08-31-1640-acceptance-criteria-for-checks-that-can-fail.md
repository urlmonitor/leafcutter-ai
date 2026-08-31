---
title: "Acceptance criteria for checks that can fail, and a documented hook that never runs"
date: "2026-08-31"
time: 1640
type: manual
components: 
  - testing_quality
  - commit_guardian
summary: "KI-TQ-010 gets its first AC coverage — 27 records specifying that a pass counts as proof only once the test is shown it could have failed — and authoring them turned up 24 hook scripts no pre-commit entry invokes."
description: "KI-TQ-010 had been open since 2026-08-26 with zero AC coverage, so it could not reach a build queue. This authors a TQ-500 tree of 27 records through the full product-owner to business-analyst to it-po pipeline: one L0, five L1, fifteen L2, six L3, with 65 test descriptors across the twelve code-bearing criteria. Six of the criteria are themselves negative controls, green on arrival by construction, so twelve carry a named mutation in test_spec — the concrete leak to inject, the expectation that the descriptor goes red under it, and green again on revert. Verifying the hook host those criteria pin, rather than trusting the README that documents it, surfaced KI-CG-20260831-hook-scripts-never-invoked: check_ticket_signoff_parity.py is deployed and documented as a live hook with --enforce, and is named by no entry line in the pre-commit config, along with 23 other scripts. The guard that exists to find unreachable hooks iterates the registered ones, so a script never wired up is outside the set it walks."
breaking: false
---

## Entry

`KI-TQ-010` has been open since 2026-08-26 with no acceptance-criteria coverage at all — a
grep over the AC store and `tickets/` returned zero references — so nothing about it could
enter a build queue.

The defect it records: the pipeline's only evidence that a test constrains anything is the
**red baseline**, the suite failing before the coder runs. That is structurally unavailable to
a **negative control**, a test asserting an *absence*, which is green on arrival by
construction. `CLAUDE.md`'s rule that a green `test-writer` phase is a TDD-order violation
**inverts** here, so the one mechanism that would ask "can this fail?" is not merely absent —
it is documented to mean the opposite.

## TQ-500

> A pass counts as proof only once the test is shown it could have failed.

27 records: one L0, five L1, fifteen L2, six L3, with 65 test descriptors across the twelve
code-bearing criteria.

A new L0 rather than an attachment, after rejecting four candidate hosts. The instructive
rejection is `BO-2500c` — "tests check the real thing, not convenient fakes". The recorded
defect *had* textbook fixture realism: real on-disk artifacts, the real serializer, the real
production entry point, explicit anti-vacuity assertions. It was still inert. Fixture realism
and failure capability are different properties, and folding one into the other would blur the
distinction the incident exists to teach.

The sharper way to put it: a test that cannot fail satisfies `BO-2500`, `BP-1100` and `TQ-400`
**perfectly and permanently**. It is present, it passes, its code runs, and it will still pass
at every future re-check. That is precisely why none of them could host this.

### The tree is at risk from its own subject matter

Six of these criteria are themselves negative controls — they assert mostly that *nothing* is
reported. An implementer who signs those off "green on arrival, nothing to prove" reproduces
`KI-TQ-010` inside the fix for `KI-TQ-010`.

So twelve carry a **named mutation** in `test_spec`: the concrete leak to inject, the
expectation that the descriptor goes red under it, and green again on revert. One replays
`KI-TQ-010`'s original leak against its own fix. One more gained an anti-vacuity descriptor
its criteria did not contain, because all four of that criterion's clauses are absences — an
implementation where the reading was never wired up would have passed it permanently.

Outcomes are specified per *(test, alteration)* pair rather than per test. The source incident
is a 4×3 table in which three of four tests caught the injected fault and the fourth — the one
carrying the headline claim — slept through it. Per-test aggregation still hides a column
nothing objected to.

## A documented hook that never runs

Checking the host these criteria pin, instead of trusting the README documenting it, surfaced
a separate defect. `check_ticket_signoff_parity.py` exists, is deployed, is documented as hook
id `check-ticket-signoff-parity` "with `--enforce`" — and is named by no `entry:` line
anywhere. `grep -c signoff .pre-commit-config.yaml` returns `0`.

```
registered hook ids in .pre-commit-config.yaml     54
check_*.py in templates/scripts/commit_guardian/   66
scripts named by NO entry: line                    24
```

Counted from `entry:` lines rather than ids, because name-to-id matching over-reports —
`check_ac_limits.py` is registered under `check-ac-tree-limits`.

`check_hook_parity` compares the four directory copies of the hook tree, answering "is this
file present everywhere" rather than "is it ever invoked". `check_hook_trigger_reachability`
does ask a reachability question, but iterates the **registered** hooks — so a script never
wired up is outside the set it walks. The gap is in the enumeration, not the predicate.

This is load-bearing rather than tidy-up: `BP-1100g-5-i` pins its whole mechanical reader onto
that host, and four `TQ-500` criteria now share it. Registration is written in as an asserted
precondition rather than trusted.

Filed as `KI-CG-20260831-hook-scripts-never-invoked`, and the register's stale "next free id"
note is retired in the same change — that line had held three values in turn, and picking the
next free number is what produced the id collision this entry had to be renamed out of.
