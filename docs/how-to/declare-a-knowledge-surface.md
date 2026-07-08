---
title: "How to declare a new knowledge surface"
description: "Step-by-step guide for registering a new source of knowledge in config/paths.json so it participates in the cross-surface knowledge map."
type: how-to
status: active
created: 2026-06-22
last_updated: 2026-06-22
components:
  - knowledge_system
related_docs:
  - config/paths.json
  - templates/skills/knowledge-query/SKILL.md
  - docs/architecture/agent_knowledge_system.md
---

# How to declare a new knowledge surface

This guide shows a maintainer how to register a new source of knowledge in
the cross-surface knowledge map by adding one entry to `config/paths.json`.
After completing this guide the new surface will appear in
`knowledge_query.py` output and its inter-surface edges will be included in
the force-directed visualization.

---

## Prerequisites

- You have write access to `config/paths.json`.
- You know the project-relative path where the new knowledge lives (a file or
  a directory with a trailing slash).
- You know which fields in that knowledge source represent relationships to
  other surfaces — these become the graph edges.

---

## Step 1 — Open `config/paths.json`

The file lives at `config/paths.json` from the project root. It contains two
top-level keys: `surfaces` and `paths`. Knowledge surfaces are declared under
the `surfaces` key.

```bash
cat config/paths.json
```

Locate the `"surfaces"` object. Each key under it is a surface name
(lowercase, kebab or underscore — follow the existing convention). For
example:

```json
"surfaces": {
  "agents": { ... },
  "tickets": { ... },
  "docs": { ... },
  "acs": { ... }
}
```

---

## Step 2 — Add an entry for the new surface

Add a new key under `"surfaces"` with the following fields:

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `path` | yes | string | Project-relative POSIX path. Directories must have a trailing slash; files must not. |
| `edge_fields` | yes | array of strings | Field names in each document of this surface whose values are references to other nodes. These become directed edges in the knowledge graph. Use `[]` when the source carries no outbound references. |
| `file_path_fields` | no | array of strings | Subset of `edge_fields` whose values are file system paths (rather than symbolic IDs). The map builder resolves these to graph nodes by path lookup. |
| `_optional` | no | boolean | Set `true` if the path may not exist in all project clones. Suppresses the missing-path check in `check_paths_integrity.py`. |

**Minimum required entry:**

```json
"my-surface": {
  "path": "docs/my-surface/",
  "edge_fields": ["depends_on", "components"]
}
```

---

## Step 3 — Save and verify

There is nothing else to change. The map-building code in
`scripts/knowledge_query.py` and `scripts/visualise_knowledge_graph.py` reads
`config/paths.json` at runtime — no code edits are needed. Adding the entry
to `"surfaces"` is the only step.

Verify the new surface is recognized:

```bash
python scripts/knowledge_query.py --list-surfaces
```

Your new surface name should appear in the output list.

---

## Verification

Run the path integrity check to confirm the entry is valid:

```bash
python scripts/check_paths_integrity.py
```

Expected output when the entry is correct and the path exists:

```
check_paths_integrity: all paths OK.
```

If the path does not yet exist on disk and the surface is optional, add
`"_optional": true` to the entry to suppress the failure.

---

## Worked example — the `acs` surface

The acceptance-criteria store is declared in `config/paths.json` as:

```json
"acs": {
  "path": "docs/acceptance-criteria/",
  "edge_fields": ["implemented_by", "covered_by", "depends_on", "components"],
  "file_path_fields": ["implemented_by", "covered_by"],
  "_optional": true
}
```

What each field does:

- `"path": "docs/acceptance-criteria/"` — the map builder scans every YAML
  file in this directory tree to build AC nodes.
- `"edge_fields": [...]` — when an AC YAML file contains an
  `implemented_by:` list, each entry becomes a directed edge from that AC
  node to the target node. The same applies to `covered_by`, `depends_on`,
  and `components`.
- `"file_path_fields": ["implemented_by", "covered_by"]` — the values in
  these two fields are file system paths (e.g.
  `scripts/commit_guardian/check_ac_limits.py`). The builder resolves them to
  file nodes rather than treating them as symbolic IDs.
- `"_optional": true` — projects that have not yet run `build.py` will not
  have `docs/acceptance-criteria/` on disk. The `_optional` flag prevents
  `check_paths_integrity.py` from failing in that state.

To query the `acs` surface after it is declared:

```bash
python scripts/knowledge_query.py --surface acs --query "traceability"
```

---

## Troubleshooting

**Surface does not appear in `--list-surfaces` output**

Check that the new entry is nested directly under the `"surfaces"` key (not
under `"paths"`). The two keys are siblings; adding an entry under `"paths"`
registers a folder alias used by the build system, not a knowledge surface.

**`check_paths_integrity.py` reports a missing path**

Either the directory has not been created yet (create it, or add
`"_optional": true` to the entry) or the `path` value contains a typo.

**Edges are absent in the graph visualization**

Verify that the field names listed in `edge_fields` exactly match the YAML
keys used in documents on that surface. Field names are case-sensitive.

---

## See Also

- `config/paths.json` — full surface registry and path aliases.
- `templates/skills/knowledge-query/SKILL.md` — reference for all
  `knowledge_query.py` flags and output modes.
- `docs/architecture/agent_knowledge_system.md` — explanation of how agents
  classify, route, and persist learnings across surfaces.
- `scripts/visualise_knowledge_graph.py` — renders the full graph as an
  interactive HTML visualization.
- `docs/how-to/declare-component-membership.md` — how to add the `components`
  list to a knowledge item so it joins the component view, and how to query a
  component back to its criteria and delivering code.
