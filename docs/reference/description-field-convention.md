---
title: "Reference: Description Field Convention"
description: "Lookup for the required description frontmatter field on documentation files: what it is for, how it is enforced, what to write, and which files are in scope."
type: reference
status: active
created: 2026-10-25
last_updated: 2026-10-25
components:
  - knowledge_system
  - documentation_system
related_docs:
  - docs/architecture/agent_knowledge_system.md
  - docs/architecture/components/knowledge-system.md
---

# Description Field Convention

Every structured documentation file in the leafcutter project (`docs/**/*.md`,
`docs/architecture/adrs/*.md`, `docs/architecture/components/*.md`) MUST include
a `description:` field in its YAML frontmatter. This requirement exists so that
`knowledge_query.py` and `generate_doc_index.py` can use the structured field
for all files rather than falling back to body-text parsing. This page was moved
out of `docs/architecture/agent_knowledge_system.md` to keep that document under
the doc-length limit.

---

## Why the field is required

`generate_doc_index.py` uses `description:` if present and falls back to the
first non-blank body line if absent. The fallback produces lower-quality
summaries — it picks up headers, preamble boilerplate, or context sentences
rather than a purpose-statement. Consistent `description:` coverage ensures
every doc surface is queryable via structured metadata.

---

## Enforcement

| Mechanism | What it does |
|---|---|
| Pre-commit hook `templates/scripts/commit_guardian/check_description_field.py` | Blocks commits that introduce new `.md` files in target directories without a `description:` field. The primary mechanical gate for new files. |
| Backfill script `scripts/backfill_descriptions.py` | One-time migration that inserts a `description:` field into every existing docs/ADR/component file that lacks one. Run with `--dry-run` first to review candidates, then `--write` to apply. |

---

## What to write

- One sentence (or phrase), at most 120 characters.
- Captures the **purpose** of the document, not its title or category.
- Plain prose, not metadata labels.

Good examples:

```yaml
description: "Enumerates all 11 channels through which agents receive context at invocation time."
description: "Operational runbook for ticket-supervisor: control flow, retry caps, and escalation ladder."
```

Avoid:

```yaml
description: "ADR"              # too generic — tells the reader nothing
description: "Reference"        # category label, not a purpose statement
```

---

## Scope

| Location | In scope | Reason |
|---|---|---|
| `docs/**/*.md`, `docs/architecture/adrs/*.md`, `docs/architecture/components/*.md` | Yes | Indexed by `generate_doc_index.py`. |
| `tickets/**/*.md` | No | Tickets use `title:` as their primary label. |
| `templates/agents/`, `templates/skills/` | No | These use their registry entries as the description layer. |

---

## See Also

- [Agent Knowledge System](../architecture/agent_knowledge_system.md) — the document this convention was moved out of.
- `scripts/backfill_descriptions.py` — the one-time migration script.
- `templates/scripts/commit_guardian/check_description_field.py` — the enforcing hook.
