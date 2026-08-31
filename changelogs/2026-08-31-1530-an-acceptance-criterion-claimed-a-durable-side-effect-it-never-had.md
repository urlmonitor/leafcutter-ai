---
title: "An acceptance criterion claimed a durable side effect it never had, and the ratchet that knew shrinks by one"
date: "2026-08-31"
time: 1530
type: manual
components: 
  - build_pipeline
  - ac_store
summary: "BP-1100g-5-i declared a durable side effect while every clause in it only reports; the value is corrected and the pinned disagreement allowlist shrinks accordingly."
description: "BP-1100g-5-i carried declares_side_effect: true while its own Then clause derives false, which check-ac-schema rejects under BO-2900g-2. The derivation asks whether a durable object outliving the run is written and explicitly excludes transient destinations; every clause in this AC reports a shortfall and writes no file, so false is the honest value and true was wrong from the 2026-08-17 enrichment. The practical consequence of the stale value was routing user-surface-smoker at priority 11.5 for an AC with no durable surface to smoke. Two guards disagreed about whether this was visible and both were right about their own scope: the commit-time AC hooks read only the staged index and had never been handed the file, while the BO-2900g-2-ii store-wide test walks the real store and had recorded the disagreement in its pinned allowlist. Correcting the AC made that allowlist entry stale, the staleness ratchet failed in CI exactly as designed, and the entry is now removed with the reasoning recorded inline. The same amendment pins the shape BP-1100g-5 shipped earlier the same day so the reader this AC specifies is built against emitted strings rather than a re-derivation."
breaking: false
---

## Entry

`BP-1100g-5-i` declared `declares_side_effect: true`. Its own Then clause derives `false`, and
`check-ac-schema` refuses the disagreement under BO-2900g-2 — *"a derived value must never be
silently overwritten and a disagreement must never be silently ignored."*

The derivation asks a narrow question: does the Then clause assert a **durable** effect, an
object whose being written outlives the run? Transient destinations — stdout, stderr, the
console — are explicitly excluded. Every clause in this AC is *"is reported"* or *"is not
reported"*. The reader observes record shape and emits findings; it writes nothing. So `false`
is correct and `true` had been wrong since the 2026-08-17 enrichment whose own note lists
`declares_side_effect` among the fields it added.

The stale value was not inert. It routed `user-surface-smoker` at priority 11.5 for an AC with
no durable surface to smoke.

### Two guards, two scopes, and only one of them blind

It is tempting to record this as "nothing noticed for four months". That is not what happened,
and the difference is the useful part.

The commit-time AC hooks validate only the files present in **that commit's index**. They do
not read the store. This record had not been staged since it was written, so those hooks had
never been handed the file and never fired. Their silence was not a pass.

The `BO-2900g-2-ii` store-wide test does walk the real store, and it **had** seen the
disagreement — someone pinned `BP-1100g-5-i` into `_KNOWN_PRE_EXISTING_DISAGREEMENTS` rather
than fixing it. So the defect was known and tracked all along; what could not see it was the
per-commit gate.

That allowlist is a deliberate ratchet: shrinking it is progress, growing it is a regression.
Correcting the AC made the entry stale, and the staleness test failed in CI with exactly the
message it exists to produce — *"These ids no longer disagree (fixed or removed) … shrinking
that set is the point."* `BP-1100g-4` had left the same set the same way. `BP-1100g-5-i` now
leaves it by being fixed rather than by aging out.

`BP-1100g-4-i` remains pinned: a real, still-open disagreement in the same AC family, to be
decided when that criterion is built rather than excused now.

### Also pinned, in the same amendment

The shape `BP-1100g-5` shipped earlier the same day, so the reader this AC specifies is built
against what actually gets emitted rather than a re-derivation of it: the key
`cross_layer_seam_answer`, with conforming shapes `{result: covered, producing_side,
consuming_side}` and `{result: not_applicable, reason, remediation}`.

The negative spells `not_applicable` and not the literal `false`. A reader built against
`result: false` would report every conforming negative as a shortfall — precisely the
false-shortfall failure mode this AC's own `it_requirements` forbid.

One correction carried into the record while doing this: `not_applicable` is new **in the
completion_manifest context**, not new to the repository. It already exists in
`config/verification_flow.schema.json` as an unrelated boolean field name. That same schema
turns out to state this whole line of work's founding principle in its own words — *"The
known-bad input that MUST be rejected. A check without one can pass on dead code"* — and
already models an unrun control as `unverified` rather than an omitted block. The AC now
points at it so the reader aligns with existing vocabulary instead of a parallel one.

No behavioural change: the AC remains `work_status: todo` and unimplemented. This corrects
technical metadata and clears the way for its build.
