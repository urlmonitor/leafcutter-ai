---
allowed-tools: Bash, Read
description: Query the cross-surface knowledge graph built from all paths.json
  surfaces (agents, tickets, docs, skills, ADRs, and more). Use when you need
  to search for a keyword across all knowledge surfaces, restrict a search to
  one surface, or export the full node+edge index for graph analysis.
name: knowledge-query
portable: true
---

# /knowledge-query — Cross-Surface Knowledge Query

## When to Use

- You want to search for a term or keyword across all knowledge surfaces (agents, tickets, docs, skills, ADRs, etc.)
- You want to see all nodes in one specific surface (e.g. all agents, or all tickets)
- You want a machine-readable JSON export of the full knowledge graph for downstream analysis
- You want to inspect the edge list showing relationships between knowledge nodes
- You are tracing how a concept flows through the codebase across multiple surfaces

## Invocation

```bash
# Full graph scan — all surfaces, text output (default)
python scripts/knowledge_query.py

# Keyword filter — search across all surfaces
python scripts/knowledge_query.py --query roadmap

# Surface filter — restrict to one named surface
python scripts/knowledge_query.py --surface agents

# Format flag — machine-readable JSON output
python scripts/knowledge_query.py --format json

# Edge list — include full edge section in text output
python scripts/knowledge_query.py --edges

# Project root override — scan a different project
python scripts/knowledge_query.py --project-root /path/to/other/project

# Combined example — JSON output for one surface
python scripts/knowledge_query.py --surface tickets --format json

# Combined example — keyword search with edges
python scripts/knowledge_query.py --query coder --edges
```

Add `--project-root <path>` when running from outside the project root.

## Output Modes

### Default (no flags)

Scans all surfaces defined in `paths.json` and prints a flat node list. Each node shows its surface name, title, and description.

Example:
```
Knowledge Graph: 42 nodes across 6 surfaces
============================================================

[agents] python-coder
  Phase agent for Python implementation tasks.

[tickets] 01_some_ticket.md
  Implement feature X.

...
```

### --query KEYWORD

Filters nodes by keyword (case-insensitive). Matches against title and description fields.

Example:
```
python scripts/knowledge_query.py --query roadmap

Knowledge Graph: 3 matching nodes (filtered by: 'roadmap')
============================================================

[skills] roadmap-query
  Query ticket alignment against docs/roadmap.json.

[tickets] 02_roadmap_audit.md
  Audit all tickets for roadmap_phase coverage.

[docs] roadmap.json
  Current phase, exit criteria, and outcome tickets.
```

### --surface NAME

Restricts output to one named surface. Valid surface names are defined by the keys in `paths.json` (e.g. `agents`, `tickets`, `docs`, `skills`, `adrs`, `hooks`).

Example:
```
python scripts/knowledge_query.py --surface agents

Knowledge Graph: 18 nodes in surface 'agents'
============================================================

[agents] python-coder
  Phase agent for Python implementation tasks.

[agents] sql-coder
  Phase agent for SQL/database implementation tasks.

...
```

### --format json

Returns the full graph (or filtered subset) as a JSON object with `nodes` and `edges` arrays. Suitable for piping to `jq` or loading into analysis tools.

Example output structure:
```json
{
  "nodes": [
    {
      "id": "agents/python-coder",
      "surface": "agents",
      "title": "python-coder",
      "description": "Phase agent for Python implementation tasks."
    }
  ],
  "edges": []
}
```

### --edges

Includes the full edge list section in text output. Edges represent relationships between knowledge nodes (e.g. skill-uses-agent, ticket-touches-file).

Example:
```
Knowledge Graph: 42 nodes, 12 edges
============================================================

[agents] python-coder
  Phase agent for Python implementation tasks.

...

Edges (12):
============================================================
  agents/python-coder → skills/signoff [uses]
  tickets/01_ticket.md → agents/python-coder [dispatches]
  ...
```

## Surfaces Queried

The script scans all surfaces defined in `paths.json` at invocation time. The default set for a leafcutter-ai installation includes:

| Surface key | Path | What is indexed |
|-------------|------|-----------------|
| `agents` | `.claude/agents/` | Agent template files (`.md`) |
| `skills` | `.claude/skills/` | Skill template files (`SKILL.md`) |
| `tickets` | `tickets/` | Ticket markdown files (frontmatter + title) |
| `docs` | `docs/` | Documentation files (`.md`) |
| `adrs` | `docs/architecture/adrs/` | Architecture Decision Records |
| `hooks` | `.claude/hooks/` | Hook scripts |

The exact surface list is read dynamically from `paths.json` at runtime, so new surfaces added to the project configuration are picked up automatically without updating this skill.

## Error Behaviour

When `paths.json` is absent or malformed, the script exits with:
```
ERROR: paths.json not found or could not be parsed.
Ensure the leafcutter build has been run (python scripts/build.py --target-dir .).
```

When an unknown surface name is passed to `--surface`, the script exits with:
```
ERROR: Unknown surface '<name>'. Valid surfaces: agents, tickets, docs, skills, adrs, hooks
```

No Python traceback is shown for user-facing errors. Internal exceptions are propagated normally so the caller can diagnose unexpected failures.

---

## Agent Protocol

This section defines the standard behaviour every consuming agent MUST follow
when using the knowledge-query skill. An agent template can reference this
entire section with a single line such as:

> "Load the knowledge-query skill and follow its Agent Protocol section."

No rules need to be repeated inline — all shared handling logic lives here.

### Invocation

You MUST invoke knowledge-query using the Bash tool. Do NOT use `Read`, `Write`,
or any other tool for this purpose.

Two invocation patterns are available:

**Keyword query** — search for a term derived from your current context:

```bash
python scripts/knowledge_query.py --query <term>
```

**Surface-scoped query** — restrict results to one surface:

```bash
python scripts/knowledge_query.py --surface <name>
```

`--project-root` is NOT required when your working directory is the project
root. Omit it unless you are running from a different directory.

### Zero-Result and Empty-Graph Handling

Two non-error conditions can occur:

- **Zero results** — the graph has nodes but none match your query. Log this
  message and continue:
  ```
  knowledge-query returned 0 nodes for '<query-term>' — proceeding with file-based context only
  ```

- **Empty graph** — the graph has zero nodes total (fresh project). Log this
  message and continue:
  ```
  knowledge-query: graph contains 0 nodes (fresh project) — proceeding with file-based context only
  ```

Neither condition triggers a user-facing prompt, a retry, or a `blocked` status.
You MUST NOT degrade your output quality — no empty or placeholder fields.

### Graceful Error Degradation

Two failure modes are possible:

- **Script not found** — the `knowledge_query.py` script does not exist at the
  expected path. Use `"script not found"` as the `<error_message>`.
- **Non-zero exit** — the script ran but exited with a non-zero status. Use the
  actual script output as the `<error_message>`.

For both modes, capture the error output, log a warning in this exact format,
and continue:

```
knowledge-query failed: <error_message> — skipping graph context, proceeding with file-based reads only
```

You MUST NOT abort, return `blocked`, retry, or surface the error to the user
unless verbose output was explicitly requested.

### Citation and Deduplication Formats

When query results contain overlapping nodes, cite each matching node using this
format:

```
[<surface>] <title>
```

For example: `[agents] python-coder`.

Present citations at confirmation gates, NOT inline in output YAML.

**Surface-type routing:**

- **AC overlap** (`acs` surface, or id matching the AC ID pattern): emit a
  deduplication warning in this format:
  ```
  <ac-id> already specifies this behavior — skipping or creating a variant
  ```
- **Doc or ADR overlap** (`docs` or `adrs` surface): add the path to `doc_links`
  with `relationship: context`. Do NOT emit a deduplication warning.
- **Other surfaces** (`agents`, `skills`, `hooks`): cite the node for information
  only. Do NOT emit a deduplication warning and do NOT add to `doc_links`.

When a single query returns both an overlapping AC and an overlapping doc, you
MUST present BOTH the deduplication warning AND the `doc_links` addition in the
same confirmation gate output.

When no overlapping nodes are found, log this message and present no deduplication
warning:

```
knowledge-query returned no related nodes for '<query-term>' — proceeding with file-based context only
```

### Mandatory-Invocation Rule

You MUST invoke knowledge-query during your knowledge-acquisition phase **even if
prior file reads appear to provide sufficient context**. File reads cannot detect:

- Cross-component overlap with other agents or skills
- Recently-registered agents or skills added since the last template update
- ACs authored in sibling components since the last template update

The only acceptable reason to skip knowledge-query is script failure (covered by
the error-handling rules above). This protocol does NOT prescribe WHEN or WHICH
surfaces to query — those remain agent-specific decisions.

### Failure Mode Distinction

The consuming agent can distinguish between the two failure modes by the Bash
tool output:

- **Script not found**: the Bash tool returns a non-zero exit with a
  file-not-found message (e.g. `No such file or directory`). Use
  `"script not found"` as `<error_message>`.
- **Non-zero exit**: the script ran and produced output before failing. Use that
  actual output as `<error_message>`.

The degradation path is identical for both modes: log the warning, skip graph
context, and continue with file-based reads.
