---
title: "Reference: Knowledge Graph Visualization"
description: "Lookup for visualise_knowledge_graph.py: what it generates, its output format, its command-line invocations and its failure exit."
type: reference
status: active
created: 2026-10-25
last_updated: 2026-10-25
components:
  - knowledge_system
related_docs:
  - docs/architecture/agent_knowledge_system.md
  - docs/architecture/components/knowledge-system.md
---

# Knowledge Graph Visualization

The `scripts/visualise_knowledge_graph.py` script generates a self-contained
D3.js force-directed HTML graph from all knowledge surfaces defined in
`config/paths.json`. It delegates surface traversal to `knowledge_query.py`
(sibling module, loaded via `importlib.util`) and embeds node and edge JSON
directly into an HTML template — no external build step, no files committed to
the repo. This page was moved out of `docs/architecture/agent_knowledge_system.md`
to keep that document under the doc-length limit.

---

## Output format

A single `.html` file written to `/tmp/` (default:
`/tmp/leafcutter_knowledge_graph.html`). The file is self-contained: it
references D3.js from the CDN (`https://d3js.org/d3.v7.min.js`) and contains
the full node+edge dataset as an embedded `const DATA = {...}` JSON block.
Nodes are coloured by surface type and sized proportionally to their edge
degree (min 4px, max 18px radius). Hovering a node highlights its direct
neighbours; clicking pins it in place.

---

## Invocation

```bash
# Write to default path and open in browser:
python scripts/visualise_knowledge_graph.py

# Write to a custom path:
python scripts/visualise_knowledge_graph.py --output /tmp/my_graph.html

# Write without opening the browser (useful in headless CI):
python scripts/visualise_knowledge_graph.py --no-open
```

The script exits with code 1 if `knowledge_query.py` is not found at the
expected sibling path and prints a clean error message (`ERROR: knowledge_query.py
not found at <path>.`) without a Python traceback.

---

## See Also

- [Agent Knowledge System](../architecture/agent_knowledge_system.md) — the document this section was moved out of.
- `scripts/visualise_knowledge_graph.py` — the implementation.
- `scripts/knowledge_query.py` — the surface traversal the script delegates to.
