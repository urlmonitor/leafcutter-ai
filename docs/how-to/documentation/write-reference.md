---
title: "How to write a reference doc"
description: "Canonical guide for authoring reference documents in this repo: genre definition, when to choose reference over other genres, required frontmatter, canonical skeleton, voice conventions, placement rule, and cross-linking."
type: how-to
status: active
created: 2026-07-22
last_updated: 2026-07-22
components:
  - documentation_system
related_docs:
  - docs/reference/skills-config-fields.md
  - docs/reference/build-telemetry.md
  - docs/reference/fixture-policy.md
  - docs/reference/agent-template-frontmatter.md
---

# How to write a reference doc

A reference doc is a **lookup artifact** — a single place an agent or developer can
consult to find every field, value, constraint, or parameter for a particular surface.
It is not a guide (that is a how-to), not an explanation (that is an explanation doc),
and not a decision record (that is an ADR). If you find yourself writing narrative prose
that explains why something works the way it does, stop: that content belongs in an
explanation doc, not here.

This guide covers every step required to produce a valid, correctly placed, and
accurately structured reference doc in this repository.

---

## Prerequisites

Before authoring, answer these two questions:

1. **Is this genuinely lookup content?** The reader should be able to scan a table or
   heading, find the specific item they need, and leave. If the content requires
   sequential reading to make sense, consider a how-to or explanation doc instead.

2. **Does the content already exist?** Check `docs/reference/` with
   `ls docs/reference/` before creating a new file. An existing doc that needs a new
   section is preferable to a second doc covering overlapping ground.

---

## Step 1 — Confirm the genre

Choose the reference genre when the primary consumer question is **"what are the
allowed values / fields / parameters for X?"** — not "how do I do X?" or "why does X
work this way?"

| Consumer question | Correct genre |
|---|---|
| What fields does `emit_agent_telemetry` accept? | Reference |
| What are all the valid `skills_config.json` keys? | Reference |
| How do I configure the fast-lane build? | How-to |
| Why does leafcutter put files in `.leafcutter/`? | Explanation |
| Should we use JSONL or SQLite for the telemetry sink? | ADR |

When a single ticket requires both lookup content (tables) and task steps, write
separate docs. The reference doc holds the tables; the how-to links to them.

---

## Step 2 — Choose the file name and placement

All reference docs live in:

```
docs/reference/<topic>.md
```

Naming rules:

- Use lowercase kebab-case: `skills-config-fields.md`, `build-telemetry.md`, `fixture-policy.md`.
- Prefer a noun phrase that names the artifact being documented: `ac-schema.md`,
  `agent-template-frontmatter.md`, `skill-frontmatter.md`.
- Avoid verbs in the name (`configuring-`, `using-`). Those belong in how-to filenames.
- One topic per file. If a topic has sub-sections that are independently queryable,
  use section anchors within the same file rather than splitting into multiple files.

---

## Step 3 — Write the frontmatter

Every reference doc opens with a YAML frontmatter block bounded by `---`. All fields
listed below are required unless marked optional.

```yaml
---
title: "Reference: <What This Covers>"
description: "One sentence: what an agent finds here and when to use this doc."
type: reference
status: active
created: YYYY-MM-DD
last_updated: YYYY-MM-DD
components:
  - <component_id>
related_docs:
  - docs/how-to/<related-how-to>.md
  - docs/architecture/adrs/<related-adr>.md
---
```

### Frontmatter field rules

| Field | Type | Rule |
|---|---|---|
| `title` | string | Prefix with `"Reference: "` for clarity in search results and the agent registry. |
| `description` | string | One sentence. State what the reader finds here and when to consult it. Not a restatement of the title. |
| `type` | enum | Must be exactly `reference`. |
| `status` | enum | `active` for a live doc; `deprecated` when superseded (add a `superseded_by:` key pointing to the replacement). |
| `created` | date (YYYY-MM-DD) | The date this file was first written. Do not update on revision. |
| `last_updated` | date (YYYY-MM-DD) | Update to today's date every time content changes. |
| `components` | list of strings | One or more component ids from `docs/architecture/components/`. Use underscore format matching the component filenames (e.g. `agent_telemetry`, `build_orchestration`). |
| `related_docs` | list of paths | Optional but strongly encouraged. Link to the how-to that uses this reference, the ADR that motivated it, and the architecture component doc that owns the surface. |

---

## Step 4 — Write the H1 heading and lead paragraph

The H1 heading is the topic name without the "Reference:" prefix:

```markdown
# <Topic Name>

One to two sentences describing what this document covers and who its primary
consumer is. State the artifact, surface, or API the doc describes. Do not
restate the frontmatter description verbatim.
```

Follow immediately with a `---` horizontal rule, then the first section.

---

## Step 5 — Structure the body

Reference docs use a flat, section-per-logical-group structure. Each section is an
`## H2` heading grouping related fields or concepts. Do not use deep nesting
(`### H3` headings are allowed for sub-groups, `#### H4` should be avoided).

### Canonical skeleton

```markdown
## <Group 1 Name>

One sentence describing what this group covers and when it applies.

| Field | Type | Default | Description |
|---|---|---|---|
| `field_name` | type | `default` | What it controls and any constraints. |

---

## <Group 2 Name>

...

---

## See Also

- [<Related how-to title>](<relative path>) — one-line description of what the reader
  gains from following that how-to.
- [<Related ADR title>](<relative path>) — one-line description of the decision context.
- `<path/to/source/file.py>` — one-line description of the implementation.
```

### Section heading conventions

| Pattern | Use for |
|---|---|
| `## <Noun phrase>` | A group of related fields (e.g. `## Output Layout`, `## Ticket Paths`) |
| `## <Function or class name>` | A single API surface being fully described |
| `## See Also` | The final cross-links section — always the last section |

Do not use `## Introduction`, `## Background`, or `## Overview` as headings. Those
suggest explanation content. Start directly with the first field group.

---

## Step 6 — Write the tables

Tables are the primary structure of a reference doc. Every field, parameter, enum
value, or configuration key that the reader might look up should appear in a table.

### Standard field table columns

For configuration fields and API parameters, use these four columns:

| Column | What to put in it |
|---|---|
| `Field` | The exact field name or parameter name, formatted as inline code. |
| `Type` | The value type: `string`, `boolean`, `integer`, `enum`, `list of strings`, `object`, `Path`, etc. Include the Python type annotation for Python APIs. |
| `Default` | The default value (as inline code), or a dash (`—`) when there is no default (the field is required). |
| `Description` | A complete sentence. State what the field controls, any constraints (min/max, allowed values, format), and any relationship to other fields. |

For enum-valued fields, either add an `Allowed values` column or follow the field's
table row immediately with a sub-table listing each allowed value and its meaning.

### Required vs optional

Mark required fields explicitly when the distinction matters:

```markdown
| Field | Type | Required | Description |
|---|---|---|---|
| `lane` | string | Yes | Pipeline lane tag (`"fast"`, `"heavy"`). |
| `unit_id` | string | No | Ticket or AC identifier; written through unchanged when present. |
```

### Code blocks in tables

Embed short code examples in the `Description` column only when the example is a
single value (e.g. `` `"fast"` `` or `` `true` ``). Multi-line code belongs in a
separate fenced block after the table, not inside it.

---

## Step 7 — Apply voice conventions

Reference docs use a **dry, declarative, third-person voice**. The reader does not
appear; the artifact or function is the grammatical subject.

| Avoid | Prefer |
|---|---|
| "You should set `lane` to the pipeline name." | "`lane` — Pipeline lane tag." |
| "This field tells the system which lane was used." | "Pipeline lane tag used to group records in the comparison report." |
| "Note that the default is `false`." | "Default: `false`." |
| "Remember to include `created` in the frontmatter." | "`created` — Required. The date the file was first written." |

Rules:
- Omit "you", "we", and "our" entirely.
- Do not use hedges: "typically", "usually", "in most cases". State the rule.
- Every sentence in a `Description` column cell must be complete (not a fragment).
- Permitted fragments only in the `Type`, `Default`, and `Required` columns.

---

## Step 8 — Add the See Also section

Every reference doc ends with a `## See Also` section listing:

1. The how-to that uses this reference (task guide; linked as a doc path).
2. The ADR that motivated the design (decision context; linked as a doc path).
3. The architecture component doc that owns the surface (if one exists).
4. The source file(s) that implement the described API (linked as a source path, not a doc path).

Format:

```markdown
## See Also

- [<How-to title>](<relative doc path>) — <one-line description>.
- [<ADR title>](<relative doc path>) — <one-line description>.
- [<Component doc title>](<relative doc path>) — <one-line description>.
- `<path/to/source.py>` — <one-line description>.
```

Source file paths go in backticks, not as hyperlinks. Doc paths use relative Markdown
links. Do not include the repo root prefix (`/` or `leafcutter-ai/`) in relative links.

---

## Step 9 — Add back-links from related docs

After writing the reference doc:

1. Open any how-to that the reference doc supports and add it to the `related_docs`
   frontmatter field if not already present.
2. Open the architecture component doc for the same surface and verify it links to
   this reference doc. Add a cross-link under its `## Cross-links` section if absent.
3. Open any ADR that motivated the design and verify the `## References` or
   `## See Also` section mentions this reference doc.

Back-links are how agents discover related content. A reference doc that nothing links
to will be missed.

---

## Verification checklist

Before declaring the doc done, confirm:

- [ ] `type: reference` is set in frontmatter.
- [ ] `last_updated` is today's date.
- [ ] Every field or parameter the surface exposes has a table row.
- [ ] No narrative prose explains "why" — explanation content has been moved to a
  separate explanation doc or left out.
- [ ] The `## See Also` section has at least one entry.
- [ ] Back-links from the related how-to and component doc have been added.
- [ ] The doc is placed at `docs/reference/<topic>.md` (not in `docs/how-to/` or any other subtree).

---

## Common mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Missing `"Reference: "` title prefix | Doc is hard to distinguish from how-tos in search results | Prepend `"Reference: "` to the `title` value in frontmatter |
| Explanation prose in description cells | Cells become paragraphs; the table is hard to scan | Move "why" content to an explanation doc; keep cells to one sentence |
| Omitting `related_docs` | Agents cannot discover the corresponding how-to or ADR | Add at least the primary how-to and the owning component doc |
| Placing the file in `docs/how-to/` | The reference-author agent cannot find it at Step 0 | Move to `docs/reference/` |
| `last_updated` not updated on revision | Stale date makes it impossible to tell whether content is current | Always update `last_updated` when making any content change |
| No `## See Also` section | Readers cannot navigate to the task guide or source | Add the section with at least one entry before merging |

---

## See Also

- `docs/reference/skills-config-fields.md` — example of a multi-group field reference
  covering the full `skills_config.json` surface.
- `docs/reference/build-telemetry.md` — example of a function-API reference with
  parameter tables, return-value tables, and usage code blocks.
- `docs/reference/fixture-policy.md` — example of a rule-based reference with
  allowed/rejected comparison tables.
- `docs/reference/agent-template-frontmatter.md` — example of a frontmatter-schema
  reference covering all keys for a specific file type.
