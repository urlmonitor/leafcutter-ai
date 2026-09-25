---
title: "ADR-049: The Record's Checker Triggers on a Scope Derived From Its Own Resolvable-Pointer Surface"
description: "The product-truth checker joins the automatic checks as one blocking pre-commit hook whose files: scope is derived from the checker's own declared resolvable-pointer roots rather than hand-written, because a hand-written regex and a growing pointer surface drift apart silently and a record that points somewhere the gate does not watch is a gate that reports green on a record nobody checked."
type: "adr"
status: "active"
created: "2026-09-25"
last_updated: "2026-09-25"
deciders:
  - adr-author
  - architect-review
components:
  - ux_prototyping
  - precommit_hooks
  - commit_guardian
related_docs:
  - docs/architecture/adrs/ADR-042-product-truth-checker-outcome-vocabulary.md
  - docs/architecture/adrs/ADR-038-commit-guardian-shared-change-set-derivation.md
  - docs/architecture/components/ux-prototyping.md
  - docs/architecture/components/commit-guardian.md
  - docs/how-to/managing-pre-commit-hooks.md
  - docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-3.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml
related_code:
  - docs/product-truth/scripts/validate_product_truth.py
  - docs/product-truth/scripts/product_truth_checks.py
  - scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/commit_guardian.json
  - .pre-commit-config.yaml
---

# ADR-049: The Record's Checker Triggers on a Scope Derived From Its Own Resolvable-Pointer Surface

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-09-25 |
| Author | adr-author, on the `architect-review` escalation recorded in [`24_TICKET-20260909-UXP-700c-3.md`](../../../tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/24_TICKET-20260909-UXP-700c-3.md) (AC `UXP-700c-3`) |
| Supersedes | — |

## Context

The product-truth store is the project's record of what it is building. Its checker
(`docs/product-truth/scripts/validate_product_truth.py`) already knows how to judge
that record: [ADR-042](ADR-042-product-truth-checker-outcome-vocabulary.md) fixed the
four-value outcome vocabulary it reports, and `UXP-700c-1` gave it per-pointer
resolution — every `implements` pointer is classified resolved, broken or unresolvable
against the project as it stands right now.

What was never decided is **when that checker runs**. `UXP-700c-3`'s AC-store entry
records the evidence from a repo-wide search on 2026-09-07: the checker was "referenced
only by ACs, agent cards, ADRs and how-to docs … not wired to anything." It has since
been registered (`check-product-truth-validate`, present in both
`.pre-commit-config.yaml` and `hooks_manifest.hooks[]` in
`scripts/commit_guardian/commit_guardian.json`) with a hand-written activation regex:

```
files: (^docs/product-truth/|^docs/acceptance-criteria/.*\.yaml$)
```

That regex is correct **today, by coincidence**. The checker's resolvable-pointer
surface is currently exactly one kind — an acceptance-criterion id
(`is_resolvable_pointer_target()` in `product_truth_checks.py` returns `True` only for
`PREFIX-NUMBER…`-shaped strings); a path, a screen reference or a URL is classified
*unresolvable* and never resolved. So "the record" plus "everything the record
resolvably points at" happens to be exactly `docs/product-truth/**` plus the AC-store
YAMLs, which is what the regex names.

The cost of not deciding is the moment that coincidence ends. `UXP-700c-1`'s own
criteria already promise pointers at "files in the project", and `_check_pointers()`
carries a `mockups` parameter documented as accepted "so the signature can grow to
screen pointers." The instant a new pointer kind becomes resolvable, the checker starts
making claims about files that the hand-written regex does not watch. A commit that
breaks one of those pointers is then offered to the automatic checks, the record's
checker is never invoked, and the commit passes green — the record silently falls behind
the code while the gate reports that it did not. That is precisely the failure
[GE-120](../../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml)
exists to forbid: green must mean *checked*, not *not looked at*. Nothing mechanical
connects the checker's pointer surface to the hook's trigger scope, so this drift is
invisible until someone audits both by hand.

Two further constraints bound the answer. `check-hook-trigger-reachability` (BP-100k-4)
rejects any `hooks_manifest` entry whose activation condition cannot match a path this
repository tracks, and rejects an `always_run` gate that also carries an unconsulted
`files` filter. [ADR-038 Amendment 2](ADR-038-commit-guardian-shared-change-set-derivation.md)
requires every manifest entry to declare a `change_set_source` from a closed vocabulary,
and fails any entry that declares `self_derived` while obtaining its change set by other
means.

`UXP-700c-3`'s third clause — "a change that touches neither the record nor anything the
record points at does not run the record's checker" — is the clause that stops the fix
being "run it on every commit", and its wording is ambiguous between *the process is
never launched* and *no verdict about the record is produced*. That ambiguity must be
resolved here, before `test-writer` picks an assertion, or the hook will be under- or
over-constrained relative to every sibling hook in the registry.

## Decision

1. **One registration.** The record's checker MUST join the project's automatic checks
   as exactly one `pre-commit` hook, `check-product-truth-validate`, present in both
   `.pre-commit-config.yaml` and `hooks_manifest.hooks[]` of
   `scripts/commit_guardian/commit_guardian.json` (and its `templates/` mirror). A
   second, parallel registration of the same checker MUST NOT be added; a CI-only
   invocation MUST NOT substitute for the pre-commit registration.

2. **The trigger scope is derived, not restated.** `docs/product-truth/scripts/product_truth_checks.py`
   MUST export a single named constant enumerating the repository roots the checker's
   *resolvable* pointer surface can name — the record's own root `docs/product-truth/`,
   plus one root per resolvable pointer kind (today: `docs/acceptance-criteria/` for
   acceptance-criterion ids). The hook's `files:` regex MUST be the union of exactly
   those roots. A test MUST assert that equality by computing the expected regex from
   the exported constant and comparing it against the regex actually configured in both
   `.pre-commit-config.yaml` and `hooks_manifest`; a literal regex restated in the test
   MUST NOT be used as the expected value, because a restatement drifts in lockstep with
   the thing it is meant to police.

3. **Adding a pointer kind widens the gate in the same change.** Making a new pointer
   kind resolvable — that is, changing `is_resolvable_pointer_target()` to return `True`
   for a shape it previously rejected — MUST add that kind's root to the constant in
   sub-decision 2, and therefore to the hook's trigger scope, within the same commit.
   The test in sub-decision 2 MUST fail when it does not. **Unless** the new kind's
   target set cannot be expressed as a bounded set of repository roots (for example, a
   pointer that may name any tracked file), in which case the widening MUST NOT be done
   by substituting a catch-all regex — a new ADR MUST be written to choose a different
   activation shape, because a catch-all regex would silently abandon sub-decision 5.

4. **The hook's verdict is the gate's verdict.** The hook MUST propagate the checker's
   process exit status unchanged as the pre-commit hook's result. The manifest entry
   MUST NOT carry `fail_open: true`, and the hook MUST NOT be wired as advisory output
   that prints a finding and exits zero. A run the checker reports as `failed` MUST
   block the commit; per [ADR-042 Amendment 1](ADR-042-product-truth-checker-outcome-vocabulary.md),
   a run holding an unresolvable pointer is `degraded` and MUST NOT be reported as
   `checked-and-sound`.

5. **The hook MUST NOT be `always_run`.** `check-product-truth-validate` MUST keep a
   `files:` filter and MUST NOT declare `always_run: true`. Activation is decided
   statically by `pre-commit` from the derived regex of sub-decision 2 — the checker
   MUST NOT be invoked on every commit and then decide internally whether it applies.

6. **AC-3's "does not run" means no verdict is reported.** The binding, testable
   observable for "a change that touches neither the record nor anything the record
   points at does not run the record's checker" is: **no product-truth verdict appears
   among the results those automatic checks report for that commit.** The assertion MUST
   be made against the configured trigger scope — the change set's paths do not match the
   hook's `files:` regex — and MUST NOT be made by instrumenting process launches. Under
   sub-decisions 2 and 5 non-invocation follows from non-matching, so the two readings
   coincide today; sub-decision 3's `unless` clause is the only route by which they could
   diverge, and it requires a new ADR before that happens.

7. **`change_set_source` stays `handed_by_commit_path`.** The checker sweeps the whole
   record on every run and derives nothing from the staged diff, so its manifest entry
   MUST declare `change_set_source: handed_by_commit_path` per
   [ADR-038 Amendment 2](ADR-038-commit-guardian-shared-change-set-derivation.md)'s
   closed vocabulary. The checker MUST NOT call
   `_authored_change.get_authored_change()`. This supersedes the `self_derived`
   recommendation in `architect-review`'s sign-off on `UXP-700c-3` — see Alternatives.

8. **Reachability.** The derived regex of sub-decision 2 MUST match at least one path
   this repository tracks, so `check-hook-trigger-reachability` reports the entry
   reachable. A root that this checkout can never produce MUST NOT be added to the
   constant.

## Consequences

### Positive

- The failure this ADR was opened to prevent becomes mechanically impossible to
  introduce quietly: a pointer kind cannot become resolvable without the gate that
  watches it widening in the same commit, because the test in sub-decision 2 derives
  its expectation from the checker itself.
- `UXP-700c-3`'s three clauses each land on a single named artifact — AC-1 on
  sub-decision 1, AC-2 on sub-decision 4, AC-3 on sub-decision 6 — so `test-writer` has
  an unambiguous assertion for each and `ac-validator` has something to check against.
- The gate stays narrow. Unrelated commits pay no checker cost at all, which keeps the
  local commit path fast and keeps the hook's failures attributable to the change that
  caused them.
- The declared `change_set_source` stays truthful, so ADR-038's determination check
  continues to pass without a refactor of the checker.

### Negative

- Sub-decision 2 adds a coupling the codebase did not have: `product_truth_checks.py`,
  a pure-logic module, now exports a constant whose consumer is the hook registry. A
  reader of the checker must know that editing that constant changes commit behaviour.
- The derived-regex test is a third place the trigger scope is asserted (config, mirror
  config, test). Keeping the `templates/` mirror and the live `scripts/` copy in step
  remains a manual duplication this ADR does not remove.
- Sub-decision 5 buys precision at the cost of flexibility: any pointer surface that is
  genuinely unbounded forces a new ADR rather than a one-line regex edit. That is
  deliberate, but it is real friction for whoever hits it first.
- Sub-decision 4 makes a checker defect a hard local blocker. A bug in the checker now
  wedges commits that have nothing wrong with them, with no fail-open escape hatch.

### Operational

- `docs/how-to/managing-pre-commit-hooks.md` must document the derived-scope rule, so an
  author adding a pointer kind finds the obligation where they are already reading.
- The regex must be kept identical in three files: `.pre-commit-config.yaml`,
  `scripts/commit_guardian/commit_guardian.json`, and
  `templates/scripts/commit_guardian/commit_guardian.json`.
- `check-hook-trigger-reachability` runs `always_run` on every commit and will report
  this entry unreachable if the derived regex ever names a root this checkout cannot
  produce — that is the intended early warning for a mis-declared root.
- Because the hook is blocking (sub-decision 4), a checker crash is a
  could-not-check condition, not a pass; `UXP-700c-3-ii` governs how that is reported and
  is unaffected by this ADR.

## Alternatives

- **Broad regex plus internal no-op** (the `check-eval-staleness` /
  `check-glossary-coverage` shape: match a deliberately over-wide root set, launch the
  checker on every match, and let it decide internally that it has nothing to do).
  Rejected. It cannot satisfy `UXP-700c-3`'s third clause under any reading that is
  observable from configuration: with a broad regex, a commit touching neither the record
  nor anything it points at *does* match, so the only remaining evidence that the checker
  "did not run" is the absence of a message it chose not to print — an assertion about
  the checker's own output, which passes just as well if the checker is broken and silent.
  `check-eval-staleness` can afford this because its `_comment` states "over-firing is
  harmless"; here over-firing is precisely what AC-3 forbids.

- **`always_run: true` with the checker filtering the staged diff itself.** Rejected.
  `check-hook-trigger-reachability` (BP-100k-4) explicitly blocks an `always_run` gate
  that also carries a `files` filter it never consults, and dropping the filter would
  make the checker run on every commit in the repository, paying a whole-store sweep for
  changes that cannot affect the record.

- **Self-derived change set** (declare `change_set_source: self_derived`, consume
  `get_authored_change()`, and compute per-commit which pointer targets moved) — the
  shape `architect-review` recommended in its `UXP-700c-3` sign-off. Rejected. The
  checker validates the whole record on every run and never consults a file list, so
  declaring `self_derived` without also calling `get_authored_change()` is exactly the
  drift ADR-038 Amendment 2 fails an entry for; and calling it would add a `git diff`
  dependency to a checker whose verdict does not depend on the diff, making it fail or
  degrade on commits where git is unreliable for no gain in accuracy.

- **A meta-hook that rewrites `.pre-commit-config.yaml` per commit** so the record's
  checker is literally absent from the hook list on unrelated commits, satisfying the
  strictest reading of "does not run." Rejected. There is no precedent for it in this
  codebase, it would mutate a `@package-managed` config file during the commit it is
  gating, and `ensure-precommit-config` — which verifies that same file matches the
  manifest — would object to the rewrite it produced.

- **Hand-maintained regex with a review checklist item** (keep the current literal regex;
  add "did you widen the hook?" to the reviewer's list when a pointer kind changes).
  Rejected. This is the status quo that produced the gap: the checker's pointer surface
  and the hook's regex already live in different files with nothing connecting them, and
  a checklist cannot fail a build. The evidence recorded in `UXP-700c-3`'s notes — the
  checker existed, fully written, wired to nothing, for long enough that a repo-wide
  search was needed to discover it — is what human vigilance on this seam already
  produced.

- **CI-only registration** (run the checker in the CI pipeline rather than at
  pre-commit). Rejected. `UXP-700c`'s benefit statement is "you are told, AT THE TIME IT
  HAPPENS"; a CI verdict arrives after the record has already fallen behind on a pushed
  commit, which is the timeliness property this AC exists to own.

## References

- Originating ticket: [`tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/24_TICKET-20260909-UXP-700c-3.md`](../../../tickets/00_inbox/epics/EPIC-TruthfulProjectRecord/24_TICKET-20260909-UXP-700c-3.md)
- Originating AC: [`UXP-700c-3`](../../acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/UXP-700c-3.yaml) (epic `EPIC-TruthfulProjectRecord`)
- [ADR-042 — The Product-Truth Checker Reports a Closed Outcome Vocabulary on a Structured Channel](ADR-042-product-truth-checker-outcome-vocabulary.md)
- [ADR-038 — Commit Guardian Shared Change-Set Derivation](ADR-038-commit-guardian-shared-change-set-derivation.md)
- [ADR-023 — Product-Truth Flow-First Upstream Layer](ADR-023-product-truth-flow-first-upstream-layer.md)
- [GE-120 — Green Means Checked](../../acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml)
- [How to manage pre-commit hooks](../../how-to/managing-pre-commit-hooks.md)
