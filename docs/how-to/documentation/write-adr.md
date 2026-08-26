---
title: "How to write an Architecture Decision Record"
description: "Canonical guide for authoring ADRs in this repo: genre definition, filename and numbering handoff, required frontmatter, the mandatory section order, Status lifecycle values, decision-clarity language rules, Alternatives presentation, cross-linking conventions, and the post-write handoff file adr-author writes for downstream coders."
type: how-to
status: active
created: 2026-08-18
last_updated: 2026-08-26
components:
  - documentation_system
  - commit_guardian
related_docs:
  - docs/conventions/adr-numbering.md
  - docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md
  - docs/how-to/documentation/write-reference.md
related_code:
  - templates/agents/adr-author.md
  - scripts/adr_refs.py
  - templates/scripts/commit_guardian/check_adr_collision.py
---

# How to write an Architecture Decision Record

An ADR is a **decision-record artifact** — it captures one committed architectural or
cross-cutting policy choice, the context that forced it, the alternatives that were
rejected and why, and the consequences the repository now lives with. It is not a
how-to (that documents a repeatable task), not a reference (that is a lookup table),
and not an explanation (that discusses "why" without binding anyone to a choice). If
the content you are writing does not commit the codebase to a specific, testable
choice, it does not belong in an ADR.

This guide is the single source of truth `adr-author` loads before writing anything
(see `templates/agents/adr-author.md` §"Mandatory Pre-Flight Steps"). It governs the
file itself — filename pattern, frontmatter, section order, Status values,
decision-clarity language, Alternatives presentation, cross-linking, and the post-write
handoff file. **Number allocation and collision-avoidance procedure live in
[`docs/conventions/adr-numbering.md`](../../conventions/adr-numbering.md)** — follow
that guide's Step 1–Step 2 to get a confirmed free number before you reach Step 2 below.

---

## 1. Confirm the genre

Choose the ADR genre when the content is a **committed decision**, not a task guide or
a lookup table:

| Consumer question | Correct genre |
|---|---|
| Should we use JSONL or SQLite for the telemetry sink? | ADR |
| Why is the whole-collection pass a library instead of a hook? | ADR (the "why", bound to a decision) |
| How do I register a new pre-commit hook? | How-to |
| What fields does `UniquenessVerdict` expose? | Reference |
| How does the fail-open narrowing in ADR-029 work in general? | Explanation (only if no new decision is being made) |

A change that only **implements** an already-accepted ADR's contract does not need a
new ADR — it needs a citation to the existing one in the code's `DOC_LINKS`. Write a
new ADR only when the decision itself has not been recorded yet, per
`check-adr-coverage` and `check-structural-change`'s structural-change trigger.

---

## 2. Determine the file name

Filename pattern: `docs/architecture/adrs/ADR-NNN-<slug>.md`

- `NNN` — zero-padded three-digit integer, allocated by the free-number procedure in
  [`docs/conventions/adr-numbering.md`](../../conventions/adr-numbering.md) §3 (Step
  1: highest existing number; Step 2: run `check_adr_collision.py` and prefer
  `scripts/adr_refs.py`'s "Unclaimed numbers" audit, which also excludes numbers that
  own no file but are still cited somewhere — reusing one of those would
  false-resolve a dangling citation into ambiguity rather than into the record it was
  waiting for).
- `<slug>` — lowercase, hyphen-separated, 3–6 words naming the decision, not the
  ticket (`whole-collection-uniqueness-pass`, not `ge-122a-1`).

Never hard-code a number from memory or from a suggestion made in a ticket comment
without re-verifying it is still free — the corpus grows between the suggestion and
the write.

---

## 3. Write the frontmatter

```yaml
---
title: "ADR-NNN: <Decision Title>"
description: "One to two sentences: what was decided and the single strongest reason."
type: "adr"
status: "active"
created: "YYYY-MM-DD"
last_updated: "YYYY-MM-DD"
deciders:
  - <name or agent that authored/approved this>
components:
  - <component_id>
related_docs:
  - <path to any ADR this amends, supersedes, or is adopted by>
related_code:
  - <path to every module or config file the decision governs>
---
```

### Frontmatter field rules

| Field | Type | Rule |
|---|---|---|
| `title` | string | Prefix with `"ADR-NNN: "` — the number must match the filename exactly. |
| `description` | string | One to two sentences stating the decision and its strongest justification, not a restatement of the title. |
| `type` | enum | Must be exactly `adr`. |
| `status` | enum | `active` once the decision is committed to this file (see §5 for the in-body Status lifecycle, which is a separate, richer table). |
| `created` / `last_updated` | date (YYYY-MM-DD) | `created` never changes after the first commit; `last_updated` moves whenever the file's content changes (including amendments). |
| `components` | list of strings | Only IDs present in `docs/components.json` — every component whose behavior the decision binds. |
| `related_docs` | list of paths | Every ADR this one amends, supersedes, is superseded by, or is adopted alongside (e.g. an ADR that says "adopts ADR-029's rule; does not modify it" lists ADR-029 here). |
| `related_code` | list of paths | Every module, script, or config file the Decision section names as governed by this ADR. |

`status:` in frontmatter is a coarse doc-lifecycle flag consumed by `check-doc-frontmatter`
(`active` / `draft` / `deprecated` / `migrating`). It is distinct from — and must not be
confused with — the in-body Status table's richer ADR lifecycle values (§5).

---

## 4. Write the mandatory section order

Every ADR body follows this order. Do not omit a section; do not reorder them.

1. **Status metadata table** — Status, Date, Author, Supersedes (see §5 for allowed
   Status values).
2. **Context** — the problem or observation that forced a decision. State the cost of
   *not* deciding (a prior incident, a measured gap, a structural blindness) so a
   future reader understands why this was worth writing down.
3. **Decision** — the committed choice, numbered as sub-decisions when the ADR binds
   more than one behavior (see §6 for language rules). Each numbered sub-decision
   should be independently citable (e.g. "per ADR-037 §3").
4. **Consequences** — split into **Positive**, **Negative**, and **Operational**
   subsections. A Consequences section with only positives is a sign the tradeoffs
   were not examined honestly.
5. **Alternatives** — every seriously-considered, explicitly-rejected option (see §7).

A **References** section after Alternatives is permitted and encouraged (originating
ticket, related ADRs, related code) but is not one of the five mandatory sections.

---

## 5. Status values

The in-body Status table (first section of the body) uses these values:

| Value | Meaning |
|---|---|
| `Proposed` | Newly authored; not yet adopted. This is the starting status for every new ADR — `adr-author` never starts at `Accepted`. |
| `Accepted` | The decision is adopted and binding. The user (via `documentation-expert`) promotes a `Proposed` ADR to `Accepted`; `adr-author` does not self-promote. |
| `Superseded` | A later ADR has replaced this decision. Set `Supersedes` on the new ADR and add a `superseded_by` note here. |
| `Deprecated` | The decision no longer applies and has not been replaced by a new ADR. |

Keep the frontmatter `status:` (§3 — the coarse `active`/`deprecated` doc-lifecycle
flag) and the in-body Status table's value in sync at every edit: a body marked
`Superseded` with frontmatter still `status: active` is a self-contradiction that
`check-adr-cross-reference` cannot catch mechanically because the two fields live in
different places.

---

## 6. Apply decision-clarity language

The Decision section commits the repository to a choice. Use unambiguous, binding
language:

| Avoid | Use instead |
|---|---|
| "The pass may inspect the whole collection." | "The pass MUST inspect the whole collection." |
| "Consumers might prefer to import the function." | "Consumers MUST import the function; they MUST NOT shell out to a CLI." |
| "It would probably be better to adopt the existing comparator." | "The decision namespace MUST reuse the existing comparator. A second implementation MUST NOT be written." |

Rules:
- Use "will" / "MUST" / "MUST NOT" for binding commitments. Never "may" or "might" in
  the Decision section — hedged language in a decision record is a decision not yet
  made.
- State each sub-decision as a single unambiguous commitment. If a sub-decision needs
  an "unless" clause, write the exception explicitly rather than leaving it implied.
- Name the file paths, function signatures, or config keys the decision binds, so the
  ADR is checkable against the code rather than only against intent.

---

## 7. Present Alternatives

List only alternatives that were **seriously considered and explicitly rejected** —
not a straw-man. For each:

```markdown
- **<Short alternative name>.** Rejected. <One to three sentences: the specific
  mechanism by which it fails to meet the Context's requirement, or the specific
  cost it would impose.>
```

A rejection reason must name a concrete failure mode ("it can never observe that a
sibling file claims the same number, because it never sees the sibling") — not a vague
preference ("it felt less clean"). If you cannot state a concrete reason, the
alternative was not seriously considered and should not appear in the list.

---

## 8. Cross-link the decision

Every ADR must be discoverable from, and must point at, its neighbors:

1. **In the frontmatter:** list every ADR this one amends, supersedes, is superseded
   by, or explicitly adopts (without modifying) in `related_docs`; list every governed
   module or config file in `related_code`.
2. **In the prose body:** link the originating ticket/epic and every related ADR
   inline, in the Context or Decision section, the first time each is mentioned —
   don't make the reader wait for a closing References section to learn a related ADR
   exists.
3. **Back-link from the component doc.** Open the architecture component doc for the
   surface this ADR governs (`docs/architecture/components/<component>.md`) and add
   this ADR to its `related_docs` frontmatter if not already present, so an agent
   reading the component doc discovers the decision.
4. **Anchor links to amended sections must match the heading exactly.** When linking
   to a specific amendment or section of another ADR (e.g.
   `ADR-029-....md#amendment-1--2026-08-18--fail-open-is-narrowed-to-the-guards-own-defects`),
   copy the target heading's exact slug — a mismatched anchor silently resolves to the
   top of the file instead of erroring.

---

## 9. Write the post-write handoff file

After writing `ADR-NNN-<slug>.md`, `adr-author` also writes a handoff file so coders
can back-link the new ADR from their DECISION HISTORY entries without re-reading the
whole ADR:

```
tickets/<ticket-dir>/.pending/adr_handoff.json
```

```json
{
  "adr_id": "ADR-NNN",
  "affected_files": ["<path from the originating ticket's files_touched>", "..."],
  "one_line_summary": "<one sentence, present tense, 15-30 words, distilled from Decision>"
}
```

This file is the only coordination mechanism between `adr-author` and downstream
coders — it is not optional even when the ADR itself is complete.

---

## 10. Verification checklist

Before declaring the ADR done, confirm:

- [ ] Filename matches `docs/architecture/adrs/ADR-NNN-<slug>.md`, and `NNN` was
  verified free via `scripts/adr_refs.py`'s "Unclaimed numbers" audit — not just
  `ls | tail -1`.
- [ ] Frontmatter `title` number matches the filename number exactly.
- [ ] Body opens with the Status metadata table; Status starts at `Proposed` for a new
  ADR.
- [ ] All five mandatory sections are present, in order: Status, Context, Decision,
  Consequences, Alternatives.
- [ ] Consequences has Positive, Negative, and Operational subsections.
- [ ] Every sub-decision uses "will" / "MUST" / "MUST NOT" — no "may" / "might".
- [ ] Every Alternatives entry names a concrete rejection mechanism, not a vague
  preference.
- [ ] `related_docs` / `related_code` frontmatter lists every ADR and module the
  decision touches; any anchor link to another ADR's section matches that heading's
  exact slug.
- [ ] The governing component doc's `related_docs` was updated to cross-link back to
  this ADR.
- [ ] `tickets/<ticket-dir>/.pending/adr_handoff.json` was written.

---

## Common mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Allocating the number from `ls \| tail -1` alone | A number that is free of a *file* but still carries a dangling citation gets reused, papering over the citation instead of resolving it | Run `scripts/adr_refs.py`'s "Unclaimed numbers" audit, which excludes cited-but-fileless numbers |
| Hedged Decision language ("may", "might", "should probably") | Reviewers cannot tell what is actually binding | Rewrite every sub-decision with "MUST" / "MUST NOT" |
| Consequences section with only positives | Reads as marketing, not a decision record | Add Negative and Operational subsections honestly |
| Frontmatter `status: active` while the in-body Status table still says `Proposed` (or vice versa, after an amendment) | The two lifecycle fields silently disagree; no mechanical check catches it | Update both fields together on every status change |
| Anchor link to another ADR's amendment section with a paraphrased slug | Link silently resolves to the top of the target file instead of the amendment | Copy the exact heading text into the anchor, lowercased and hyphenated |
| Skipping the `.pending/adr_handoff.json` handoff file | Downstream coders have no back-link source for their DECISION HISTORY entries | Write it immediately after the ADR file, in the same turn |

---

## See Also

- [`docs/conventions/adr-numbering.md`](../../conventions/adr-numbering.md) — the number-allocation and collision-avoidance procedure that precedes this guide's Step 2.
- [ADR-029 — ADR Number Collision Prevention](../../architecture/adrs/ADR-029-adr-number-collision-prevention.md) — worked example of an amended ADR (see its Amendment 1 for a real Status-table-plus-amendment-section pattern).
- [ADR-037 — Whole-Collection Uniqueness Pass](../../architecture/adrs/ADR-037-whole-collection-uniqueness-pass.md) — worked example of a new ADR authored via this guide, including a six-consumer contract and ten rejected alternatives.
- [How to write a reference doc](write-reference.md) — the sibling guide for lookup-genre documentation.
- `templates/agents/adr-author.md` — the agent template that loads this guide as its mandatory pre-flight step.
- `scripts/adr_refs.py` — the retrospective audit (duplicates, gaps, dangling numbers, broken slugs) used to verify a number is genuinely free.
