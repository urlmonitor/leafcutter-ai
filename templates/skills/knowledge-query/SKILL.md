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
| `acs` | `docs/acceptance-criteria/` | Acceptance-criteria store files (`.yaml`); each AC contributes `implemented_by`, `covered_by`, `depends_on`, and `components` edges |

This table is illustrative, not exhaustive — the exact surface list is read dynamically from `paths.json` at runtime, so new surfaces added to the project configuration are picked up automatically without updating this skill.

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

This section is the single reference for how any agent template should invoke
`knowledge-query` and handle its results. An agent template can reference the
full protocol with one line:

> "Load the `knowledge-query` skill and follow its **Agent Protocol** section."

No inline repetition of these rules is needed.

### Invocation

You MUST invoke `knowledge-query` using the Bash tool — not `Read`, `Write`,
or any other tool. Two standard patterns are:

**Keyword query** (use the term most relevant to your current task):

```bash
python scripts/knowledge_query.py --query <term>
```

`<term>` is derived from your current context — the ticket goal, the
component name, the concept you are working with. Choose a term that
narrows the graph to nodes related to your task.

**Surface-scoped query** (use when you need all nodes in one surface):

```bash
python scripts/knowledge_query.py --surface <name>
```

`--project-root` is not required when your working directory is the
project root. Omit it in the standard case.

### Zero-Result Handling

Two non-error conditions may occur after a successful script invocation.
Neither triggers a user-facing prompt, a retry, or a `blocked` status.
Your output quality MUST NOT degrade — no empty or placeholder fields:

- **Zero results** — the graph has nodes but none match your query. Log:
  `"knowledge-query returned 0 nodes for '<query-term>' — proceeding with file-based context only"`
- **Empty graph** — the graph has zero nodes total (fresh project). Log:
  `"knowledge-query: graph contains 0 nodes (fresh project) — proceeding with file-based context only"`

Continue with file-based reads in both cases.

### Graceful Error Degradation

Two failure modes may occur. In both cases You MUST capture the error
output, log a warning, and continue. You MUST NOT abort, return
`blocked`, retry, or surface the error to the user unless verbose output
was explicitly requested:

- **Script not found** — the Bash tool returns a "command not found" or
  "No such file or directory" error. Use the literal text `"script not found"`
  as the `<error_message>` portion of the warning.
- **Non-zero exit** — the script exits with a non-zero code. Use the
  script's actual output as `<error_message>`.

Warning format (identical degradation path for both modes):

```
knowledge-query failed: <error_message> — skipping graph context, proceeding with file-based reads only
```

The consuming agent can distinguish the two modes by the Bash tool output
format, but the degradation behaviour is the same.

### Citation and Deduplication

**Citation format** for overlapping nodes (use at confirmation gates, not
inline in output YAML):

```
[<surface>] <title>
```

Example: `[agents] python-coder`

**Deduplication warning** (applies ONLY to nodes whose surface is `acs`
or whose id matches the AC ID pattern):

```
<ac-id> already specifies this behavior — skipping or creating a variant
```

**`doc_links` auto-population** (applies ONLY to `docs` or `adrs` surface
nodes): when a query returns a `docs` or `adrs` node that overlaps with
your work, add the path to `doc_links` with `relationship: context`.

**Nodes from other surfaces** (`agents`, `skills`, `hooks`): cite for
information only — they do NOT trigger deduplication warnings or
`doc_links` additions.

When a single query returns both an overlapping AC and an overlapping doc,
You MUST present BOTH the deduplication warning AND add the doc to
`doc_links` in the same confirmation gate output.

When no overlapping nodes are found, log:

```
knowledge-query returned no related nodes for '<query-term>' — proceeding with file-based context only
```

and present no deduplication warning.

### Mandatory-Invocation Rule

You MUST invoke `knowledge-query` during your knowledge-acquisition phase
even if prior file reads appear to provide sufficient context.

**Rationale:** file reads cannot detect cross-component overlap, recently
registered agents or skills, or ACs authored in sibling components since the
last template update. Skipping `knowledge-query` when files seem sufficient
produces invisible gaps in cross-surface awareness.

The only acceptable reason to skip `knowledge-query` is a script failure
covered by the error-handling rules above.

This protocol does NOT prescribe WHEN or WHICH surfaces to query — those
decisions remain agent-specific and depend on the task at hand.
