---
title: "How to write a how-to guide"
description: "Canonical guide for authoring how-to documents in this repo: genre definition, the Location Decision Rule, the required frontmatter and skeleton, and the closing index step for docs/how-to/."
type: how-to
status: active
created: 2026-09-14
last_updated: 2026-09-14
components:
  - documentation_system
related_docs:
  - docs/how-to/documentation/write-reference.md
  - docs/how-to/documentation/write-adr.md
related_code:
  - templates/agents/how-to-author.md
---

# How to write a how-to guide

A how-to is a **task-oriented artifact** — a reader arrives with a concrete goal
("I need to X") and follows numbered steps to reach it. It is not a reference
(a lookup table of fields or values), not an explanation (narrative "why" prose),
and not an ADR (a committed decision with rejected alternatives). If your draft
reads as a sequence of scannable facts rather than actions to perform, or if it
argues for a choice instead of executing one, it belongs in a different genre.

This guide is the single source of truth `how-to-author` loads before writing
anything (see `templates/agents/how-to-author.md`, opening line: "Before writing
anything, load and read `docs/how-to/documentation/write-how-to.md` in full.").
It is the third member of the set alongside
[`write-reference.md`](write-reference.md) and [`write-adr.md`](write-adr.md),
and follows their shape: genre check, placement rule, frontmatter, body
skeleton, verification checklist, common mistakes.

---

## Prerequisites

- A genuinely task-oriented request — a "how do I X?" question, not a lookup
  or a decision (see Step 1).
- The source material the guide will draw facts from (a script, a hook, a
  workflow, or another doc) — do not invent steps from memory.
- Read access to `docs/components.json` to select valid `components:` values
  (Step 3).

---

## Step 1 — Confirm the genre

Choose the how-to genre when the consumer question is **"how do I do X?"**:

| Consumer question | Correct genre |
|---|---|
| How do I create a new skill? | How-to |
| How do I verify pre-commit hooks are active? | How-to |
| What fields does `skills_config.json` accept? | Reference |
| Why does leafcutter route ACs before tickets? | Explanation |
| Should we use JSONL or SQLite for telemetry? | ADR |

A request that mixes lookup tables with task steps should still produce a
how-to for the steps; put the tables in a linked reference doc instead of
inlining them here.

---

## Step 2 — Apply the Location Decision Rule

Before writing, decide where the guide lives by answering three questions, in
order:

1. **Who needs this guide?** A general contributor working anywhere in the
   repo → `docs/how-to/`. A domain-specific audience (documentation authors,
   output-layout migrators) → the matching topical folder.
2. **Where will they look first?** The how-to index, or a topical README?
   (As of this writing `docs/how-to/` has no index and no README — see Step 7.
   Until one exists, "where they'll look first" defaults to browsing
   `docs/how-to/` directly or following a link from `docs/INDEX.md`.)
3. **Does an existing topical folder already cover this domain?** If yes,
   place the guide beside its siblings rather than starting a new folder.
   Observed precedent: `docs/how-to/documentation/` holds the three
   genre-authoring guides (this file plus its two siblings);
   `docs/how-to/output-layout/` holds output-root migration guides. Everything
   else defaults to the flat `docs/how-to/` directory.

If a task spec's "Existing location hint" disagrees with this rule, override it
and state the reason in the response payload — do not silently follow a
disagreeing hint.

---

## How-To Skeleton

Every how-to guide in this repo contains these sections, in this order:

1. **Frontmatter** — `title`, `description`, `type: how-to`, `status`,
   `created`, `last_updated`, `components`, `related_docs` (see Step 3).
2. **H1** — `# How to <Verb Phrase>`.
3. **One-sentence overview** — what the reader accomplishes and why.
4. **`## Prerequisites`** — environment, skills, and prior-reading links as
   tight bullets.
5. **Steps** — each step is exactly one action (see Step 4).
6. **`## Verification`** — a runnable command with its exact expected output
   or a clearly described shape (see Step 5).
7. **`## Troubleshooting`** — only when known failure modes exist; numbered
   cause → fix pairs (see Step 6).
8. **`## See Also`** — cross-links to sibling docs (see Step 7).

Select `components:` values only from the live registry — do not guess:

```bash
python -c "import json; print('\n'.join(sorted(json.load(open('docs/components.json',encoding='utf-8'))['components'])))"
```

---

## Step 3 — Write the frontmatter

```yaml
---
title: "How to <Verb Phrase>"
description: "One sentence: what the reader accomplishes and when to reach for this guide."
type: how-to
status: active
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
components:
  - <component_id>
related_docs:
  - <path to a related how-to, reference, or ADR>
---
```

`type` MUST be exactly `how-to` (hyphen). Several older guides in this repo use
`type: how_to` (underscore) — that is a divergence from the two sibling genre
docs, not a second valid spelling; do not copy it into new guides. A `category:
how-to` field appears in some newer guides alongside `type`; it is redundant
with `type` and not part of this skeleton — omit it.

`created` never changes after the file is first committed; `last_updated`
moves on every content change. `components` values must come from the
`docs/components.json` command in the previous section, not be guessed from a
plausible-sounding name.

---

## Step 4 — Write the Steps

Each step is **exactly one action** the reader performs. Existing guides use
two shapes:

- **Flat H2 steps** — `## Step 1 — <imperative phrase>`, `## Step 2 — ...`,
  directly under the H1 (the majority shape: `creating-a-skill.md`,
  `declare-component-membership.md`, `ac-driven-development.md`).
- **Wrapped H3 steps** — a single `## Steps` heading containing
  `### Step 1 — <imperative phrase>` sub-headings (seen in
  `output-layout/adopt-consolidated-output-root.md`).

Both shapes exist in the corpus; this guide does not retroactively require
converting one to the other. For a **new** guide, use H3 steps nested under a
single `## Steps` heading when any step needs sub-content (a code block plus
explanatory prose, or a table); use flat H2 steps when every step is a short,
single action. Whichever shape you pick, apply it consistently within one
guide — do not mix flat and wrapped steps in the same file.

Every code fence carries a language tag (` ```bash `, ` ```yaml `, ` ```json `,
never a bare ` ``` `). Commands are complete and runnable as written — no
`...` truncation the reader has to guess at.

---

## Step 5 — Write the Verification section

`## Verification` gives the reader one command to confirm the guide worked,
plus the exact output or a clearly described shape:

`````markdown
## Verification

````bash
<runnable command>
````

Expected output: `<exact string>`, or: a description of the shape when the
output is not a fixed string (e.g. "a JSON object with `"binary": true` for
all four keys").
`````

Link to `## Troubleshooting` from here when a failing check has a known fix,
rather than repeating the fix inline.

---

## Step 6 — Write the Troubleshooting section

Add `## Troubleshooting` only when the guide's subject has known failure
modes — do not add an empty or speculative one. Each entry is a numbered
cause → fix pair naming the concrete symptom, not a vague "if something goes
wrong":

```markdown
## Troubleshooting

1. **`config` check fails.** No `.pre-commit-config.yaml` is resolvable in
   this worktree. Run `python scripts/commit_guardian/ensure_precommit_config.py`
   from the worktree root, then re-run Verification.
```

---

## Step 7 — Write the See Also section, and the index step

`## See Also` closes every how-to with cross-links to sibling explanation and
reference docs, and to `docs/INDEX.md` when a navigation entry point helps the
reader. **Never link `docs/README.md`** — it does not exist and never has.

`write-reference.md` Step 9 tells its author to add back-links from the how-to
that uses the new reference doc. The equivalent step for a how-to would be:
add an entry to `docs/how-to/README.md` (flat guides) or the topical folder's
`README.md` (topical guides). **As of this writing, neither exists**:
`docs/how-to/` has no `README.md`, and topical folders such as
`docs/how-to/output-layout/` have none either — only `docs/INDEX.md`
(auto-generated by `scripts/generate_doc_index.py`, listing components,
diagrams, and ADRs, not individual how-tos) fills any index-like role today.

Do not fabricate a step that edits a file that is not there, and do not create
the how-to index yourself — that is a separate, larger undertaking (parallel
to `docs/reference/README.md`, authored independently). Instead:

1. Check whether `docs/how-to/README.md` (or the topical folder's `README.md`)
   exists before writing.
2. If it exists, add an entry for the new guide.
3. If it does not, report `README updated: no — not present` in the response
   payload rather than inventing an edit, and name the gap so a future pass can
   decide whether to scaffold one.

---

## Verification checklist

Before declaring a how-to done, confirm:

- [ ] `type: how-to` is set in frontmatter (hyphen, not underscore).
- [ ] `last_updated` is today's date.
- [ ] The H1 reads `How to <Verb Phrase>`.
- [ ] `## Prerequisites` lists environment, skill, and reading requirements as
  bullets, not prose.
- [ ] Every step is one action; every code fence has a language tag; no
  truncated commands.
- [ ] `## Verification` gives a runnable command with an exact or clearly
  described expected output.
- [ ] `## Troubleshooting` is present only if real failure modes are known,
  and every entry is a cause → fix pair.
- [ ] `## See Also` is present and does not link `docs/README.md`.
- [ ] `related_docs` / `related_code` frontmatter paths all exist on disk.
- [ ] The how-to index step (Step 7) was checked honestly — an edit was made
  only if the target file exists.

---

## Common mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| `type: how_to` (underscore) | Diverges from the sibling genre docs and from most existing how-tos | Use `type: how-to` (hyphen) |
| Explanation prose inside a step | The step stops being a single action; the reader loses the thread | Move "why" content to a linked explanation doc or a one-line aside |
| A lookup table doing the guide's real work | Reference content masquerading as a how-to | Extract the table to a reference doc and link it |
| Claiming a `## See Also` back-link into `docs/how-to/README.md` that does not exist | The claimed step cannot be performed; a reviewer finds a broken promise | Check the file exists first; report "not present" instead of fabricating the edit |
| Mixing flat and wrapped step headings in one guide | Inconsistent scannability within a single file | Pick one shape (Step 4) and use it throughout |

---

## See Also

- [How to write a reference doc](write-reference.md) — the sibling guide for
  lookup-genre documentation.
- [How to write an Architecture Decision Record](write-adr.md) — the sibling
  guide for decision-record documentation.
- `templates/agents/how-to-author.md` — the agent template that loads this
  guide as its mandatory pre-flight step.
- [Documentation Index](../../INDEX.md) — auto-generated index of components,
  diagrams, and ADRs; the closest existing navigation entry point until
  `docs/how-to/` has its own index (see Step 7).
