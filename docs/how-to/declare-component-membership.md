---
title: "How to declare component membership and query the component knowledge graph"
description: "Step-by-step guide for adding a components list to a knowledge item so it joins the cross-surface component view, and for querying a component back to its criteria, source files, and tests."
type: how-to
status: active
created: 2026-07-08
last_updated: 2026-07-08
components:
  - knowledge_management
related_docs:
  - docs/reference/ac-schema.md
  - docs/acceptance-criteria/index.yaml
  - config/paths.json
  - templates/skills/knowledge-query/SKILL.md
  - docs/how-to/declare-a-knowledge-surface.md
---

# How to declare component membership and query the component knowledge graph

> **Two distinct axes — do not conflate them.**
> The scalar `component` field is the AC-store **namespace/prefix key** — its valid
> values are the kebab ids in `docs/acceptance-criteria/index.yaml` (e.g.
> `knowledge-management`). The `components` **list** field is the **graph membership
> vocabulary** — its valid values are the underscore ids in `docs/components.json`
> (e.g. `knowledge_system`). An AC can legitimately have both at the same time:
> `component: knowledge-management` (namespace) and
> `components: [knowledge_system]` (graph). They are different registries.

This guide covers two tasks:

1. **Declare component membership** — add the `components` list field to a
   knowledge item (acceptance criterion, ticket, doc, agent, or skill) so it
   participates in the component view of the cross-surface knowledge graph.

2. **Query a component** — use `scripts/knowledge_query.py` to retrieve the
   criteria that belong to a component and, through them, the source files
   and tests that deliver it.

---

## Prerequisites

- The project has a leafcutter build deployed (run `python scripts/build.py --target-dir .`
  from the workspace root, or verify that `config/paths.json` exists in the project root).
- You know which component the item belongs to. For the `components` list (graph
  membership), valid ids are the underscore keys in `docs/components.json`. For the
  scalar `component` field (AC-store namespace), valid ids are the kebab keys in
  `docs/acceptance-criteria/index.yaml`.
- For acceptance criteria: write access to the AC YAML file.

---

## Part 1 — Declare component membership on a knowledge item

### Step 1 — Look up the valid component IDs

For the `components` **list** (graph membership), open `docs/components.json`. Each
entry has an `id` field (underscore notation, e.g. `knowledge_system`). These are the
values that go in the `components` list.

For the scalar `component` field (AC-store namespace/prefix), open
`docs/acceptance-criteria/index.yaml`. Each entry has an `id` field (kebab notation,
e.g. `knowledge-management`). These are the values for the scalar `component` field,
file placement, and ID prefixes. **Do not use index.yaml ids in the `components` list.**

```yaml
# docs/components.json — graph membership registry (use for the `components` LIST)
{
  "knowledge_system": { ... },
  "build_pipeline": { ... },
  "testing_quality": { ... }
}

# docs/acceptance-criteria/index.yaml — namespace registry (use for the scalar `component`)
components:
  - id: knowledge-management   # kebab — for scalar `component` field only
    prefix: KM
    description: "ACs for the cross-surface knowledge graph..."
  - id: ac-store
    prefix: ACS
    ...
```

If the graph component you need is not listed in `docs/components.json`, add a new
entry there before proceeding. If the AC namespace you need is not in `index.yaml`,
add a new entry to `index.yaml`.

### Step 2 — Add the `components` list to the item

#### Acceptance criteria (required, enforced at commit time)

An AC YAML file must carry a `components` list. This is the authoritative field
the knowledge graph reads to build `component_membership` edges — the legacy scalar
`component` field is retained for backward compatibility but is not what the graph
or enforcement hooks use.

Add the `components` key immediately after the `id` line:

```yaml
id: KM-KGS-100a-1
components:
  - knowledge_management
title: "Graph ingests all surfaces declared in paths.json"
component: knowledge-management    # keep in sync with components[0] for backward compatibility
status: active
criteria: |
  Given the project has a valid paths.json ...
```

Rules enforced by `scripts/ac_store/validate_ac_schema.py` (and the
`check-ac-schema` pre-commit hook):

- `components` must be present and non-null.
- It must be a non-empty list (empty list or list of blank strings is rejected).
- Every entry must be an `id` from `docs/components.json` (underscore ids). These
  are the graph membership ids — not the kebab ids from `index.yaml`.

An AC that spans two components can declare both:

```yaml
components:
  - build-pipeline
  - infrastructure
```

#### Tickets (encouraged, not enforced)

A ticket's YAML frontmatter may carry a `components` list. The `tickets` surface
in `config/paths.json` lists `components` as an edge field, so the knowledge
graph will build `component_membership` edges for any ticket that declares it.

```markdown
---
title: "Add component coverage to build reports"
components:
  - build-pipeline
---
```

No pre-commit hook enforces this on tickets; it is opt-in and advisory.

#### Documentation files (how-tos, ADRs, reference docs)

Documentation files under `docs/` carry a `components` list in their YAML
frontmatter. The `docs` and `adrs` surfaces both declare `components` as an
edge field. Every newly authored how-to, reference doc, or ADR should include
a `components` list. This guide is an example:

```yaml
---
type: how-to
components:
  - knowledge_management
---
```

The `check-doc-frontmatter` pre-commit hook enforces required frontmatter fields
on staged docs files; whether `components` is among the required fields depends
on the project's `commit_guardian.json` configuration.

#### Agents and skills

Agent templates (`.claude/agents/*.md`) and skill files
(`.claude/skills/*/SKILL.md`) carry `components` in their YAML frontmatter.
Both the `agents` and `skills` surfaces declare `components` as an edge field:

```markdown
---
name: python-coder
components:
  - build-pipeline
---
```

### Step 3 — Which surfaces require `components` and which are exempt

Whether a surface is expected to carry `components` is driven entirely by the
`edge_fields` setting in `config/paths.json` — not by a fixed list in code.
Any surface whose `edge_fields` includes `"components"` can carry the field
and will have `component_membership` edges built for it.

| Surface | Requires `components`? | Enforcement |
|---------|------------------------|-------------|
| `acs` (acceptance criteria) | **Yes — required, non-empty, registry-valid** | `check-ac-schema` pre-commit hook blocks the commit |
| `tickets` | Encouraged; graph reads it when present | No hook enforcement |
| `docs` | Encouraged; graph reads it when present | `check-doc-frontmatter` hook (project-configurable) |
| `agents` | Encouraged; graph reads it when present | No hook enforcement |
| `skills` | Encouraged; graph reads it when present | No hook enforcement |
| `adrs` | Encouraged; graph reads it when present | No hook enforcement |
| `glossary` | **Exempt** | The `glossary` surface declares `edge_fields: []` in `config/paths.json` — no `component_membership` edges are built from glossary entries and no `components` field is expected |

The `glossary` is the only surface in a standard leafcutter installation that
is explicitly exempt. Any future surface added to `config/paths.json` without
a `"components"` entry in its `edge_fields` list will also be exempt by the
same mechanism.

### Step 4 — Verify the field is accepted (acceptance criteria)

Run the AC schema validator directly:

```bash
python scripts/ac_store/validate_ac_schema.py \
  docs/acceptance-criteria/<component>/<feature-folder>/<id>.yaml
```

Expected output when valid:

```
OK: docs/acceptance-criteria/knowledge-management/KM-KGS-100-knowledge-graph-surfaces/KM-KGS-100a-1.yaml is valid.
```

If the `components` field fails validation:

```
AC schema validation FAILED:
  docs/acceptance-criteria/.../KM-KGS-100a-1.yaml: Field 'components' names
  unknown component(s) ['my-component']. Valid components
  (docs/acceptance-criteria/index.yaml): ['ac-store', 'build-pipeline', ...]
```

The commit-time hook (`check-ac-schema`) runs the same validation automatically
on every staged AC YAML file when you run `git commit`.

---

### Background — backfill

When the `components` list field was first made required (replacing the earlier
scalar-only convention), `scripts/ac_store/backfill_components.py` was run once
across the full AC store. The script reads each AC's scalar `component` field
and inserts `components: [<component>]` when the scalar names a valid registry
ID. It is idempotent — ACs that already carry a non-empty `components` list are
skipped unchanged.

After the backfill run, AC component coverage rose from approximately 0% to
approximately 97%. The remaining ~3% required human review because their
`component` scalar was missing, blank, or pointed to an unregistered value
(the script leaves these untouched and reports them for review rather than
guessing).

To check whether any ACs in your working tree still lack `components`, run:

```bash
python scripts/ac_store/backfill_components.py --dry-run
```

---

## Part 2 — Query a component in the knowledge graph

Once ACs declare `components`, the knowledge graph can answer: "give me all
criteria for component X, and through them the source files and tests that
deliver it."

The graph structure is: each AC node has an outbound `component_membership`
edge to the component hub node. Each AC also has `implemented_by` edges
pointing to source files and `covered_by` edges pointing to test files.

```
AC node (KM-KGS-100a-1)
  ──[component_membership]──> knowledge-management   (hub node)
  ──[implemented_by]────────> scripts/knowledge_query.py
  ──[covered_by]────────────> unit_tests/test_knowledge_query.py
```

### Step 1 — Locate the component hub node (human-readable)

```bash
python scripts/knowledge_query.py --query <component-id>
```

This finds all nodes whose title or description mentions the component name,
including the synthetic component hub node (surface: `components`). Example:

```bash
python scripts/knowledge_query.py --query knowledge-management
```

Sample output:

```
# Knowledge Index
Surfaces: 1   Nodes: 3   Edges: 0

## components (1)
  [components] knowledge-management — Component hub: knowledge-management

## acs (2)
  [acs] KM-KGS-100a-1 — Graph ingests all surfaces declared in paths.json
  [acs] KM-KGS-100e-7 — How-to guide: declare a component on a knowledge item...
```

The component hub node (`surface: components`) is a synthetic node created by
the graph builder for each distinct component value seen in `component_membership`
edges. It has no outbound edges of its own; the membership edges run from ACs
to the hub.

### Step 2 — Get all ACs for a component with their code and test links (JSON)

The complete traversal — component → all its ACs → source files + test files —
requires filtering the graph's edge list. Export the `acs` surface as JSON to
get all AC nodes and their edges in a machine-readable form:

```bash
python scripts/knowledge_query.py --surface acs --format json --edges
```

The output is a JSON object with `nodes` (one per AC) and `edges` arrays.
Edges of interest:

| Edge type | Meaning |
|-----------|---------|
| `component_membership` | AC belongs to the named component hub |
| `implemented_by` | Source file path that delivers the criterion |
| `covered_by` | Test file path (or test function) that proves the criterion |
| `depends_on` | Another AC this one depends on |

Filter in Python to collect the full picture for one component:

```python
import json
import subprocess

result = subprocess.run(
    ["python", "scripts/knowledge_query.py",
     "--surface", "acs", "--format", "json", "--edges"],
    capture_output=True, text=True, check=True,
)
data = json.loads(result.stdout)
edges = data["edges"]

component = "ac-store"   # replace with your component id

# All AC IDs whose component_membership edge points to this component
ac_ids = {
    e["source"] for e in edges
    if e["type"] == "component_membership" and e["target"] == component
}

# Source files and test files reached through those ACs
source_files = {
    e["target"] for e in edges
    if e["source"] in ac_ids and e["type"] == "implemented_by"
}
test_files = {
    e["target"] for e in edges
    if e["source"] in ac_ids and e["type"] == "covered_by"
}

print(f"{component}: {len(ac_ids)} ACs, "
      f"{len(source_files)} source files, {len(test_files)} test files")
for src in sorted(source_files):
    print(f"  source: {src}")
for tst in sorted(test_files):
    print(f"  test:   {tst}")
```

Example figures observed after the initial backfill run:
- `ac-store`: 455 ACs linked to 5 source files and 210 test files.
- `build-pipeline`: 706 ACs linked to 22 source files and 363 test files.

### Step 3 — Component with ACs but no implementing code

A component whose ACs do not yet have `implemented_by` or `covered_by` entries
returns its AC nodes with no error; the edge sets for source files and test files
are simply empty. Querying a work-in-progress component is safe and shows
exactly which criteria are waiting to be delivered.

---

## Verification

1. Run a knowledge graph scan and confirm the component hub node appears:

   ```bash
   python scripts/knowledge_query.py --query <component-id>
   ```

   The hub node should appear with `surface: components` and the description
   `Component hub: <component-id>`.

2. Confirm the AC you edited is linked:

   ```bash
   python scripts/knowledge_query.py \
     --surface acs --format json --edges
   ```

   In the JSON output, find an edge whose `source` is your AC ID, `type` is
   `component_membership`, and `target` is your component ID.

3. For AC files specifically, the `check-ac-schema` pre-commit hook verifies the
   `components` field on every `git commit` that stages a file under
   `docs/acceptance-criteria/`. A missing, empty, or unregistered value blocks
   the commit.

---

## See Also

- `docs/reference/ac-schema.md` — complete field-by-field reference for AC YAML
  files; the `components` field specification is authoritative there.
- `docs/components.json` — graph component registry (the 42 underscore ids used in
  the `components` list field for knowledge-graph membership).
- `docs/acceptance-criteria/index.yaml` — AC-store namespace/prefix registry (kebab
  ids used in the scalar `component` field, file placement, and ID prefixes).
- `templates/skills/knowledge-query/SKILL.md` — full reference for all
  `knowledge_query.py` flags and output modes.
- `docs/how-to/declare-a-knowledge-surface.md` — how to register an entirely new
  knowledge surface in `config/paths.json`.
- `scripts/ac_store/backfill_components.py` — the idempotent backfill tool used
  when the `components` list field was first made required.
- `scripts/ac_store/validate_ac_schema.py` — the schema validator that enforces
  the `components` field (and other required AC fields) at commit time.
