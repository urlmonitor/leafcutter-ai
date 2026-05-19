---
name: sql-query-past-queries
description: |
  Scans the project's past-queries folder and surfaces prior queries relevant
  to the current request. The past-queries folder path is read from a sibling
  PROJECT_CONTEXT.md (if present) or from caller args. Returns a ranked list
  of candidate queries for reuse.
allowed-tools:
  - Read
  - Bash
---

# sql-query-past-queries Skill

## Purpose

Surface prior SQL queries from the past-queries library that partially or
fully cover the current query request. Prefer reuse over authoring from
scratch — this reduces query drift and accumulates shared institutional
knowledge.

## Inputs

This skill accepts one optional argument:

- `past_queries_folder` — the path to scan for `.md` query files. If not
  provided, read the path from the sibling `PROJECT_CONTEXT.md` under
  `## Past queries folder`. If neither is available, use the generic default
  `.agents/skills/db/queries/` and log a warning.

## Procedure

### Step 1 — Resolve the past-queries folder path

1. Check if the caller passed `past_queries_folder` as an argument.
2. If not, read the sibling `PROJECT_CONTEXT.md` and extract the path under
   `## Past queries folder`.
3. If neither is available, default to `.agents/skills/db/queries/` and log:
   `sql-query-past-queries: past_queries_folder not configured; using default .agents/skills/db/queries/`

### Step 2 — List available query files

```bash
ls <past_queries_folder>/*.md 2>/dev/null || echo "no query files found"
```

If no files are found, return immediately:

```
## Past Queries Scan
No past queries found in <folder>. Authoring from scratch.
```

### Step 3 — Read and score each query file

For each `.md` file found, read its content. Score its relevance to the
current request using keyword overlap on:

- The query title (first `#` heading)
- The `## Purpose` section
- The table names mentioned in the `## Query` section

Score 0–3:
- 3: high overlap — query directly addresses the current request
- 2: partial overlap — query covers related tables or a similar pattern
- 1: low overlap — query is from the same domain but covers a different use case
- 0: no overlap — different domain entirely

### Step 4 — Return ranked results

Return only files with score >= 1. Format:

```
## Past Queries Scan

### Folder scanned
<path>

### Relevant prior queries (score >= 1)
| Score | File | Summary |
|-------|------|---------|
| 3 | <filename>.md | <one-line summary from ## Purpose> |
| 2 | <filename>.md | <one-line summary> |
| 1 | <filename>.md | <one-line summary> |

### Recommendation
<"Adapt <filename>.md — it covers <X>." or "No sufficiently close match; author from scratch.">
```

If no files score >= 1:

```
## Past Queries Scan

No relevant prior queries found. Author from scratch.
```

## Constraints

- Read files only — do not modify or delete any query file.
- Do not execute any SQL.
- Do not use `Grep`, `Glob`, or MCP search tools directly. If cross-file
  lookups are needed beyond the past-queries folder, delegate to the caller.
- Return the ranked list and recommendation. The final reuse decision belongs
  to the calling agent, not this skill.
