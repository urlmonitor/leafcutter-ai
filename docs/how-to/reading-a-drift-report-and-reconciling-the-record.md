---
title: "How to read a drift report and reconcile the record"
description: "What each finding the product-truth checker can report means, what to open first, a full walkthrough of reconciling one behind journey, what to do when the code was right versus when the record was right, and why a separator-only difference between platforms is never drift."
type: how-to
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - ux_prototyping
related_docs:
  - docs/how-to/authoring-product-truth-artifacts.md
  - docs/product-truth/README.md
  - docs/reference/product-truth-checker-outcomes.md
  - docs/architecture/adrs/ADR-042-product-truth-checker-outcome-vocabulary.md
  - docs/architecture/adrs/ADR-043-journey-record-carries-its-own-behind-mark.md
  - docs/architecture/components/ux-prototyping.md
---

# How to read a drift report and reconcile the record

You ran `validate_product_truth.py` yourself, or the pre-commit gate ran it for you
([managing pre-commit hooks](managing-pre-commit-hooks.md), UXP-700c-3), and it told
you part of the project record is behind. This guide gets you from "the automatic
checks flagged something" to "the record and the code agree again" — what each
finding means, what to open first, how to reconcile one journey end to end, and one
finding that looks like drift but is not.

---

## Part 1 — The four kinds of finding

Every finding the checker can report about the record's agreement with the code and
with itself falls into one of these. Each is a distinct message prefix on the
checker's `errors`/`warnings` output.

| Prefix | What it means | Channel | What to open first |
|---|---|---|---|
| `[pointer]` | A flow step or branch `implements` an AC id that is well-formed but **absent from the AC store right now** — a pointer that does not resolve. | `errors` — blocks the commit | The flow named in the message, at the step/branch it names, in `docs/product-truth/flows/`; then the AC id it points at, in `docs/acceptance-criteria/` — was it renamed, moved, or deleted? |
| `[pointer-unresolvable]` | The `implements` target is not shaped like an AC id at all (a screen name, a path, a URL, free text) — a pointer the checker **could not classify**. It is not counted as resolved and not reported as broken. | `warnings` — non-blocking | The same flow/step; is the value a typo of a real AC id, or was it never meant to be an AC pointer? |
| `[freshness]` | A **confirmed** journey (Part 6 of [authoring product-truth artifacts by hand](authoring-product-truth-artifacts.md#part-6--confirm-a-journey-against-what-it-describes-freshness)) where one or more of the AC ids it named in `confirmed.state` have changed content since — a journey **behind**. | `warnings` — never a build failure by itself | The journey's `confirmed` and `behind` blocks, then each named changed AC id, to see what actually moved. |
| `[freshness-never-confirmed]` | The journey has no `confirmed` record at all — never confirmed. Not judged current or behind (there is nothing earlier to judge it against), and it does not count toward the run's `compared N journey(s) for freshness` figure. | `warnings` | Whether the journey is worth confirming now, given what it currently describes — see Part 2 below. |

There is a fifth, closely related message worth knowing about while you are in a
journey's freshness block: `[freshness-unresolvable]`, logged when `confirmed.state`
names an AC id that has since **vanished from the AC store entirely**. That id is
reported separately and is never folded into `changed` — a vanished target is not the
same claim as "this AC's content moved," and treating it as `[freshness]`-behind would
misreport why the journey needs a fresh look. Treat it the same way you would treat a
`[pointer]` finding on the same id: find out whether the AC was legitimately
retired/renamed, or whether something was deleted that should not have been.

For the run-level picture these individual findings roll up into
(`checked-and-sound` / `nothing-examined` / `degraded` / `failed`), see
[the checker-outcomes reference](../reference/product-truth-checker-outcomes.md) —
this page is about the findings themselves, that one is about what the overall verdict
licenses you to conclude.

---

## Part 2 — Reconcile one journey, end to end

Walk through this once on a real `[freshness]` finding and the rest of this section
generalises. Say the checker printed:

```
[freshness] fern-and-fig/customer-buys-a-plant: behind -- changed: ['UXP-590a-2']
```

1. **Open the journey.** In `docs/product-truth/flows/<product>/<name>.flow.json`,
   find the top-level `confirmed` object (`against` + `state`) and, if present, the
   durable `behind` mark the checker wrote next to it
   ([ADR-043](../architecture/adrs/ADR-043-journey-record-carries-its-own-behind-mark.md)).
   `behind.changed` names exactly the AC ids that moved.
2. **Open each changed AC.** For `UXP-590a-2` in this example, look at what actually
   changed since `confirmed.against` — usually `work_status`, `product_truth`,
   `implemented_by`, or `covered_by` (the four fields `_ac_content_signature` hashes;
   `path` is deliberately excluded, so a file move alone never trips this).
3. **Decide which side moved.** See Part 3 below — this is the step people skip, and
   skipping it is how a real behind journey gets silently rubber-stamped.
4. **Actually walk the journey again against the current code** — read or click
   through the steps the flow describes, against what the product does today. Do not
   skip straight to re-confirming: the point of `confirmed` is that a person (or an
   agent acting on their behalf) vouches for the match, not that the checker's
   signature happens to line up.
5. **Update the flow if it needs it** (Part 3), then re-confirm:

   ```json
   "confirmed": {
     "against": "<a fresh explicit id you supply — e.g. today's commit SHA>",
     "state": {
       "UXP-590a-2": "<UXP-590a-2's current content signature>"
     }
   }
   ```

   `against` must be a string **you** provide — a commit SHA, an AC-store version
   tag, or another explicit confirmation id. Never hand-write a hash yourself; ask
   the validator to state the current signature for the AC you are confirming
   against, and copy that into `state`, exactly as
   [Part 6 of the authoring how-to](authoring-product-truth-artifacts.md#part-6--confirm-a-journey-against-what-it-describes-freshness)
   describes.
6. **Re-run the validator.** The `[freshness]` line for this journey disappears, the
   `behind` mark is removed from the journey file automatically (never hand-edit it
   — the validator writes and removes it), and `compared N journey(s) for freshness`
   in stdout reflects the re-confirmation.

`[pointer]` and `[pointer-unresolvable]` findings reconcile the same way in miniature:
open the named step, decide whether the target or the code moved (Part 3), fix
whichever side is wrong, and re-run the validator until the finding is gone.

---

## Part 3 — Which side was wrong?

A behind or broken finding tells you the record and the code disagree. It does not
tell you which one is right. Work that out before you touch anything — reconciling
in the wrong direction quietly launders a real regression into "the record was just
out of date."

**The code was right, the record was wrong.** The journey's `summary`, a step's
`human` line, an `acceptance_scenarios` entry, or an `implements` pointer describes
behaviour the product no longer has, or never quite had. Fix the flow's prose,
steps, or pointers to match what the code actually does, then re-confirm (Part 2,
steps 4–6). This is ordinary authoring — follow
[the add-vs-create protocol](authoring-product-truth-artifacts.md#part-2--the-add-vs-create-protocol-mandatory)
if the fix needs a new step or dataset rather than an edit to an existing one.

**The record was right, the code was wrong.** The journey describes the approved,
correct behaviour, and the product has since diverged from it — a regression, an
unintended side effect of an unrelated change, or a change that shipped without
updating the thing it was supposed to keep true. **Do not edit the record to match
broken code.** Re-confirming a journey against code that regressed does not make the
regression go away; it deletes the only signal that it happened. Instead:

- Leave the journey `behind` (or the pointer broken) — that is the checker doing its
  job.
- Raise it through this project's normal path: every code change needs a ticket
  (see this repository's `CLAUDE.md` — "no untracked code changes," "every code
  change must be driven by a ticket"). Do not fix the code inline just because you
  are the one who noticed the drift.
- Only re-confirm the journey once the code is fixed and genuinely matches what the
  record describes again.

If you cannot tell which side is right from the AC and the journey alone, that is a
reason to go read the actual, current behaviour of the product (or ask whoever owns
it) — not a reason to guess by re-confirming and hoping.

---

## Part 4 — A separator-only difference is not drift

If you are comparing the record across two platforms — say, a checker run on Windows
against one on a POSIX system, or two people's local index rebuilds — you may see a
difference that is **only** how each platform spells a path: `docs\product-truth\…`
versus `docs/product-truth/…`. **That is not drift, and it must not be reconciled as
though it were.**

Two things back this up:

- The checker itself normalises path separators to a canonical form (forward slash)
  before it ever compares an index entry to a fresh rebuild, specifically so a
  spelling-only difference between platforms can never be reported as `[index]`
  drift (UXP-700c-3-i, "the verdict does not depend on which operating system the
  check ran on").
- Even so, you can still *see* a raw, separator-only difference by eye — reviewing a
  diff opened on the other OS, or comparing two on-disk rebuilds directly, rather
  than through the checker's own comparison. Do not read that as several journeys or
  index entries having drifted. Nothing about what the record describes has changed;
  only how one platform happens to write a path separator has.

Concretely: **do not** re-confirm a journey, edit `confirmed.state`, or otherwise
touch the record to "fix" a difference that turns out — on inspection — to be
nothing but `\` versus `/` in a path. If every difference you are looking at is
separator-only, the record has not drifted; move on. If you are not sure, diff the
two versions with separators normalised first (or just re-run the checker, which
already does this for you) before concluding anything is behind.

---

## Verification

- After reconciling, re-run:

  ```bash
  python docs/product-truth/scripts/validate_product_truth.py
  ```

- The finding you were chasing is gone from `errors`/`warnings`.
- For a freshness fix: `compared N journey(s) for freshness` still accounts for the
  journey you re-confirmed, and its `behind` mark (if it had one) is gone from the
  flow file on disk.
- For a pointer fix: `resolved N pointer(s)` reflects the corrected pointer, and the
  `[pointer]`/`[pointer-unresolvable]` line for that step no longer appears.
- The run's overall `outcome` (last stdout line) is `checked-and-sound` if nothing
  else is outstanding — see
  [the checker-outcomes reference](../reference/product-truth-checker-outcomes.md)
  if it is not and you are unsure what that means.

---

## See Also

- [How to author a Flow, Mockup, or Mock Data artifact by hand](authoring-product-truth-artifacts.md) — Part 6 covers authoring a `confirmed` record in the first place.
- [docs/product-truth/README.md](../product-truth/README.md) — the store's operational README, including its own Validation section.
- [What each product-truth checker outcome licenses you to conclude](../reference/product-truth-checker-outcomes.md) — the run-level `checked-and-sound` / `nothing-examined` / `degraded` / `failed` vocabulary these findings roll up into.
- [ADR-042 — Product-Truth Checker Outcome Vocabulary](../architecture/adrs/ADR-042-product-truth-checker-outcome-vocabulary.md) — the decision behind the resolved/broken/unresolvable pointer split.
- [ADR-043 — A Journey Known to Be Behind Carries a Durable `behind` Mark in the Record Itself](../architecture/adrs/ADR-043-journey-record-carries-its-own-behind-mark.md) — the `confirmed.against` identity contract and why the checker never synthesises it.
- [UX Prototyping component](../architecture/components/ux-prototyping.md) — the store's architecture, including the Lifecycle & Validation section these checks live in.
