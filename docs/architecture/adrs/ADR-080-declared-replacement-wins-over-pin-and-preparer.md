---
title: "ADR-080: A Declared Replacement Wins over a Pin and over the Preparer"
description: "A requirement's test_spec entry may declare the exact replacement for one of its own must_catch names. A declaration is used ahead of any pin and ahead of the preparer, goes through the same checks as a pin, never falls back when a check fails, and is never written to the pin store. It is the one way an author can fix the alteration a name stands for, rather than accept whatever the preparer guessed first."
type: "adr"
status: "active"
created: "2026-10-30"
last_updated: "2026-10-30"
deciders:
  - BrainCandy
  - adr-author
components:
  - testing_quality
  - build_orchestration
  - ac_store
related_docs:
  - docs/architecture/adrs/ADR-079-wrong-version-pins-replay-replacements-per-work.md
  - docs/architecture/adrs/ADR-050-runtime-reachability-guard-refuses-not-warns.md
  - docs/analysis/2026-10-23-the-wrong-version-gate-tests-a-different-guess-each-run.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261023-test-breaker-no-op-alterations.md
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-xvii.yaml
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-xiii.yaml
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-xi.yaml
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-ix.yaml
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-2.yaml
  - docs/reference/ac-schema.md
  - docs/architecture/components/build-orchestration.md
related_code:
  - config/ac_store_schema.json
  - scripts/ac_store/_ac_schema_test_spec_validators.py
  - scripts/build_orchestration/_wvr_scope.py
  - scripts/build_orchestration/_wvp_plan.py
  - scripts/build_orchestration/_wvw_write.py
  - scripts/build_orchestration/_wvr_verdict.py
---

# ADR-080: A Declared Replacement Wins over a Pin and over the Preparer

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-30 |
| Author | adr-author (for BrainCandy), from ticket `TQ-500g-1-xvii` |
| Supersedes | — (extends [ADR-079](ADR-079-wrong-version-pins-replay-replacements-per-work.md); does not replace it) |

## Context

The wrong-version gate checks that a test can fail. For each `must_catch` name on a
requirement's `test_spec` entry, it needs an alteration of the code, and it runs the test
against that altered copy. [ADR-079](ADR-079-wrong-version-pins-replay-replacements-per-work.md)
(requirement
[TQ-500g-1-xi](../../acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-xi.yaml))
gives each name one of two sources: a pin replayed from an earlier run of the same work,
or a new guess from the test-breaker agent (the preparer). ADR-079 §8 already reserves a
third source, "a declaration (TQ-500g-1-xvii)", without defining it.

Pins stop the gate from testing a different guess on every run. They do not let anyone
choose the guess. The first alteration that passes its checks is locked in, even when it
is not what the author meant by the name. The
[2026-10-23 analysis](../../analysis/2026-10-23-the-wrong-version-gate-tests-a-different-guess-each-run.md)
shows the problem with "propagation that reaches only one level deep": across rounds I to
III the preparer gave it two different alterations, and both looked faithful. Remedy
option (iii) and recommendation item 6 of that analysis say the requirement should carry
the alteration itself. Without that, an author who knows exactly which line a name
means has only two options. They can wait for a reset (TQ-500g-1-xvi) and hope the next
guess is better, or they can rename the name.

Two facts from the code limit the design:

- The `check-ac-schema` hook and `validate_ac_schema.py` do not enforce the JSON schema's
  shape rules. The entry-naming checks that actually run are the hand-written ones in
  `scripts/ac_store/_ac_schema_test_spec_validators.py` (`test_spec_entry_errors`, beside
  the `must_catch` check of
  [TQ-500f-2](../../acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-2.yaml)).
  The schema is still read, by `_declared_entry_keys`, to refuse unknown keys.
- The runner side already loads the AC records once (`_wvr_records.load_records`) and
  derives `must_catch` and `in_scope_files` per name from them, in `_wvr_scope`. A second
  reading of the store would be a second source of truth for what a name owes.

Ticket `TQ-500g-1-xvii` (epic `EPIC-OnceANamedWrongVersionIsPreparedAnd`) records the
shape of the field as an IT-PO decision. architect-review asked for this ADR because the
change crosses three components (`ac_store`, `build_orchestration`, `testing_quality`).

## Decision

1. **The field.** A `test_spec` item MUST accept one new optional field,
   `declared_replacements`. It is an object. Each key MUST be a `must_catch` name of the
   same entry, spelled exactly as that entry's `must_catch` spells it. Each value MUST be a
   non-empty list of `{path, old, new}` objects. `path` and `old` MUST be strings with at
   least one non-whitespace character. `new` MUST be a string, and the empty string is accepted. No other
   key is allowed in a replacement. Replacements MUST be applied in list order, each
   against the result of the one before, exactly as the writer applies a reply's
   replacements.

2. **Enforced by the validator that actually runs.**
   `config/ac_store_schema.json` MUST add the property to the `test_spec` item, keep
   `additionalProperties: false` on the item, and set `additionalProperties: false` on each
   replacement object. That way `_declared_entry_keys` accepts the new key and still
   refuses every other unknown key. The checks that refuse a bad declaration MUST live in
   `_ac_schema_test_spec_validators.py` and MUST be called from `test_spec_entry_errors`,
   beside the `must_catch` check. A key the entry's `must_catch` does not list MUST be
   refused with a message naming the file, the entry and the name. A non-object value, an
   empty list, a replacement missing `path`, `old` or `new`, a non-string value, and a
   blank `path` or `old` MUST each be refused with a message naming the entry and the
   rule. A shape rule that exists only in the JSON schema does not count as enforced. No
   new `ac_store` module is created. If one is, it MUST be added to the `ac_store` deploy
   map in the same change, because the hook runs the deployed validator.

3. **Read once, on the runner side.** `_wvr_scope` MUST read `declared_replacements` from
   the records `_wvr_records.load_records` already returns, beside `_must_catch_by_name`
   and `_in_scope_by_name`. It MUST attach to each owed name its declaration and
   `declared_by: [{ac_id, entry}]`. The store MUST NOT be parsed a second time for this.
   Names are matched through `_wvr_scope.norm_name`, the one normaliser ADR-079 §4 fixes.
   When two entries declare different replacements for the same normalised name, the name
   MUST be unfinished with a reason naming both requirement ids and both entries.
   Identical declarations count as one declaration, and `declared_by` lists every entry.

4. **Precedence is declared > pinned > prepared.** In `_wvp_plan`, a name with a
   declaration MUST be planned as `declared`. It MUST NOT be put in `to_prepare`, and its
   pin MUST NOT be applied. A declaration MUST NOT be treated as one of several candidates
   competing with the pin. If the reply also answers a declared name, the answer MUST be
   listed in `ignored_reply_names` and MUST NOT be used (ADR-079 §8). Names on the same
   entry that have no declaration MUST be planned exactly as they would be with no
   declaration on the entry at all.

5. **A declaration never touches the pin store.** While a declaration exists, the name's
   pin MUST stay byte-identical. It MUST NOT be applied, changed, reset or cleared. A
   declaration MUST NOT be written to the pin store, and the pin step MUST skip entries
   whose source is `declared` (ADR-079 §9). Once the declaration is removed from the entry,
   the next plan MUST plan the stored pin again, through every check of
   [TQ-500g-1-xiii](../../acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-xiii.yaml).

6. **The same checks as a pin, with no fallback.** The declared replacements MUST go
   through the same `_wvp_checks` functions as a pin (TQ-500g-1-xiii). These are: the
   path is in scope for the name and passes the writer's path refusals (a test file,
   outside the repository, inside the version-control folder); the old text occurs exactly
   once; the replacement changes something; the result loads; and it reaches a line. A
   second set of checks MUST NOT be written. When any check fails, the manifest entry MUST
   be `could_not_prepare` with the reason exactly
   `"declared on <ac_id>, entry <entry name>: <failed check>"`. The name is then
   unfinished. It MUST NOT be sent to the preparer, and the pin MUST NOT be used in its
   place. A stale declaration is a fault the author fixes in the requirement. The gate
   MUST NOT quietly swap in another alteration, for the same refuse-not-warn reason set out
   in [ADR-050](ADR-050-runtime-reachability-guard-refuses-not-warns.md).

7. **The row says where the alteration came from.** The manifest entry for a declared name
   MUST have `source: "declared"` and the additive key `declared_by: [{ac_id, entry}]`.
   Its `alteration_id` MUST come from `_wvp_store.alteration_id` (ADR-079 §6). The writer
   (`_wvw_write`) MUST write that entry, and the runner (`_wvr_verdict`) MUST copy
   `declared_by` onto every row of that wrong version, beside `alteration_id`, `source` and
   `replacements` (TQ-500g-1-xv). That way a row names the requirement and the entry
   that fixed the alteration.

8. **Not copied onto generated tickets.** `generate_ticket_from_ac.py` is not changed by
   this decision, and `config/test_requirements.schema.json` MUST NOT gain the field. The
   AC store is the only place a declaration lives.

## Consequences

### Positive

- An author can fix the exact alteration a name stands for, in the requirement, under
  review, and get that alteration on every run in every workspace. Pins are
  workspace-private and are lost with the workspace (ADR-079 §3). A declaration is not.
- A declared name is never sent to the preparer, so a test-breaker dispatch is skipped
  when every owed name is declared or pinned.
- A declaration that has gone stale (the old text was edited away) is reported, naming
  the requirement, the entry and the failed check. The gate never quietly tests some other
  alteration in its place.
- A declaration goes through the same checks as a pin. It cannot reach a test file or a
  file outside the name's scope, or name an alteration that changes nothing.
- The pin is kept untouched, so removing a declaration returns to the earlier,
  already-checked alteration without a new preparation.

### Negative

- Declarations are hand-written code fragments inside YAML. They go stale when the code
  moves, and each time the gate stops until someone edits the requirement. This is the
  cost of refusing to fall back.
- A declared name is no longer explored by fresh guesses at all. If the author's
  declaration is a weak reading of the name, nothing in the gate will point that out
  beyond the usual caught/survived verdict.
- One more source value (`declared`) and one more additive key (`declared_by`) for every
  consumer of manifests and verdict rows to accept.
- The validator grows a second structured field beside `must_catch`. It must stay at or
  under the 400 counted-line limit (`_ac_schema_test_spec_validators.py` is at 84 lines
  before this change).

### Operational

- To force an alteration, add `declared_replacements` to the `test_spec` entry and commit
  the AC file. `check-ac-schema` checks it at commit time. To go back to the pin, delete
  the declaration. No pin-store edit is needed or allowed.
- A `could_not_prepare` row whose reason starts with `declared on` means the requirement
  needs editing, not the code or the pin store.
- Anything that parses manifests or verdict rows MUST accept `source: "declared"` and the
  `declared_by` key.
- The validator change takes effect in consumer projects only after a rebuild, because
  the hook runs the deployed copy.

## Alternatives

- **Write the declaration into the pin store as a pin.** Rejected. Pins are
  workspace-private and are replaced by compare-and-swap on new preparations (ADR-079 §9),
  so a declaration stored there would be lost with the workspace or overwritten by a later
  run. It would also make "remove the declaration" leave a pin behind that nobody checked
  as a pin.
- **Fall back to the pin, or to the preparer, when a declaration fails a check.**
  Rejected. The gate would then test an alteration the author explicitly replaced, and the
  run would look green while testing the wrong thing. The analysis recorded exactly that
  silent-substitution pattern across rounds I to III.
- **Pin wins over a declaration (pinned > declared).** Rejected. Once any guess had been
  pinned, a declaration added afterwards would never take effect in that workspace. The
  author's choice would silently lose to the earlier guess it was written to replace.
- **Enforce the shape only in `config/ac_store_schema.json`.** Rejected. The hook and
  `validate_ac_schema.py` do not enforce the JSON schema's shape rules, so a malformed
  declaration would pass at commit time and fail only at gate time, without naming the
  entry.
- **Allow `additionalProperties` on the `test_spec` item to admit the new field.**
  Rejected. That would also admit every misspelled key on every entry. The unknown-key
  refusal from `_declared_entry_keys` is the protection against that.
- **A separate store or file for declarations.** Rejected. It would be a second reading
  of what a requirement owes, apart from the `must_catch` list it qualifies. It could also
  name a must_catch name that no entry lists, which Decision §2 refuses.
- **Copy declarations onto generated tickets.** Rejected. A ticket copy would drift from
  the AC store, and the runner reads the store, not the ticket. That would add a second
  copy nobody reads.

## References

- Ticket: `tickets/00_inbox/epics/EPIC-OnceANamedWrongVersionIsPreparedAnd/08_TICKET-20261024-TQ-500g-1-xvii.md`
- Requirement: [TQ-500g-1-xvii](../../acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-xvii.yaml)
- Pins and the plan module: [ADR-079](ADR-079-wrong-version-pins-replay-replacements-per-work.md), §3, §4, §6, §8 and §9
- Checks reused unchanged: [TQ-500g-1-xiii](../../acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-xiii.yaml)
- Precedent for a new optional `test_spec` field and the writer's path refusals: [TQ-500g-1-ix](../../acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-ix.yaml)
- Evidence: [The wrong-version gate tests a different guess each run](../../analysis/2026-10-23-the-wrong-version-gate-tests-a-different-guess-each-run.md), remedy option (iii) and recommendation item 6
- Field reference: [AC schema](../../reference/ac-schema.md)
