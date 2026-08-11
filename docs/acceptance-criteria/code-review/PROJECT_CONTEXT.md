# code-review (CR) — component context

First-authored 2026-08-11 by product-owner. Component: `code-review` (prefix CR).
Graph component id (`components:` list): `review_system`.

## What this component covers

The Fowler code-smell review capability. A developer points `/code-smell-review`
at code (file, folder, or pasted snippet) and gets ONE prioritised, plain-English,
severity-ranked report. Every finding names the specific Martin Fowler code smell
(the "Modern 12", Refactoring 2nd ed), names the refactoring move that removes it,
and shows a verbatim "before" snippet plus a direction-only "after" sketch
(guidance, never a full rewrite).

Distinct from `guardrail-engine` (GE): GE is commit-time quality gates; CR is a
review *capability* the developer invokes on demand.

## Tree shape (CR-100 refactoring-guidance)

- CR-100  (L0) — Know exactly what to refactor and why, without noise.
  - CR-100a — every finding names the exact smell (diagnosis)
  - CR-100b — every finding names the exact refactoring (prescription)
  - CR-100c — verbatim "before" + direction-only "after" sketch
  - CR-100d — one consolidated, severity-ranked report
  - CR-100e — review a file, a folder, or a pasted snippet (the command surface)
  - CR-100f — full breadth without the wait/cost (breadth + speed/cost efficiency)

## Framing decisions the PO made (do NOT re-litigate; decompose at L2)

- The "how" behind CR-100f was deliberately kept OUT of L0/L1: under the hood the
  review fans out to two specialised reviewers in parallel — a fast pass for the
  simple/mechanical structural smells and a deeper pass for the judgment-heavy
  design smells — then merges into one severity-ranked report. That parallel-
  fan-out + merge, and the tiering, is L2 territory, not customer-value language.
- The capability is already BUILT. Existing surfaces (see index.yaml
  directory_patterns) the BA/IT-PO should map to: skills `review-for-code-smells`
  (core method), `review-for-structural-code-smells` + `review-for-design-code-smells`
  (the two Modern-12 bucket catalogues), agents `find-structural-smells`
  (Sonnet tier — 6 local/mechanical smells) and `find-design-smells`
  (Opus tier — 6 cross-cutting/judgment smells), skill `code-smell-review`
  (the orchestration), and command `/code-smell-review`.
- The Modern-12 split: structural bucket = Mysterious Name, Duplicated Code,
  Long Function, Long Parameter List, Loops, Repeated Switches. Design bucket =
  Global Data, Mutable Data, Feature Envy, Data Clumps, Primitive Obsession,
  Shotgun Surgery. Each maps to its named Fowler refactoring.
- Finding anatomy (CR-100a/b/c) is one reference doc; CR-100e is the new
  slash-command how-to + sequence-diagram; CR-100f wants a component-diagram +
  sequence-diagram for the fan-out/merge topology.

## Store conventions confirmed here

- scalar `component: code-review` (index.yaml kebab); `components: [review_system]`
  (components.json graph id). Two distinct axes — keep both.
- `status: active` (schema enum — NOT `draft`; use `readiness: draft` for the
  draft lifecycle). New PO ACs: `readiness: draft`, `priority: high` (explicit
  instruction on this feature), `work_status: todo`.
- Since the capability is already built but no `# covers:`-tagged tests were
  linked at authoring time, `work_status` was left `todo` and `implemented_by`/
  `covered_by` empty — reconcile against real code + tests during build/ac-audit
  rather than claiming done without test evidence.
