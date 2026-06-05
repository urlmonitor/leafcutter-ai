---
title: "Add --surface and --project-root CLI flags to visualise_knowledge_graph.py"
status: todo
components:
  - knowledge-management
created: 2026-06-04
depends_on:
  - tickets/00_inbox/epics/EPIC-KnowledgeGraphQueryLayer/03a_knowledge_graph_visualization_core.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/4
files_touched:
  - scripts/visualise_knowledge_graph.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Add --surface and --project-root CLI flags to visualise_knowledge_graph.py

## Actor / Goal

In order to let users visualize a subset of knowledge surfaces or run the
visualization script from outside the project root, we need to add `--surface`
and `--project-root` argparse flags to the existing `visualise_knowledge_graph.py`
script.

## Context

Ticket 03a delivers the core visualization script with `--output` and `--no-open`
flags. This ticket extends it with two additional flags that control which surfaces
are included in the graph and where the project root is located. These are additive
argparse changes to the existing script.

### Invocation (this ticket)

```bash
python scripts/visualise_knowledge_graph.py --surface agents skills
# Only include nodes and edges from the specified surfaces.

python scripts/visualise_knowledge_graph.py --project-root <path>
# Run from outside project root.
```

## Agent Contracts

### python-coder

- [ ] AC-1: Running with `--surface agents skills` produces a graph containing only
  nodes from the `agents` and `skills` surfaces and edges between them; nodes from
  all other surfaces are absent from the embedded JSON.
- [ ] AC-2: The script accepts `--project-root <path>` and passes it to
  `knowledge_query.py`'s surface loader without error.

**Delivers to test-writer:**
```json
{
  "module_path": "scripts/visualise_knowledge_graph.py",
  "new_cli_flags": ["--surface", "--project-root"],
  "surface_flag_type": "nargs='+' — accepts one or more surface names",
  "project_root_flag_type": "positional Path argument passed to load_surfaces()"
}
```

**Depends on:** ticket 03a's `visualise_knowledge_graph.py` with working argparse, data assembly, and HTML generation.

#### Implementation guidance

1. **`--surface` flag** — add `parser.add_argument("--surface", nargs="+", default=None)`.
   In the data assembly step, if `args.surface` is not None, filter the surfaces dict
   returned by `load_surfaces()` to only include keys present in `args.surface`.
   Edges whose source or target node is not in the filtered set are excluded.

2. **`--project-root` flag** — add `parser.add_argument("--project-root", type=Path, default=None)`.
   Pass the value to `_kq.load_surfaces(project_root=args.project_root, ...)`.
   When None, the existing default behavior (auto-detect from script location) applies.

---

### test-writer

- [ ] AC-3: `unit_tests/test_visualise_knowledge_graph.py` contains tests:
  `test_surface_filter_excludes_others` and `test_project_root_flag_passed_to_kq`.
- [ ] AC-4: All new tests fail (RED) before python-coder runs and pass (GREEN) after
  python-coder delivers. <!-- scope: integration -->

**Depends on python-coder:** new CLI flags and filtering behavior from the Delivers-to block above.

#### Test specification

Add to existing `unit_tests/test_visualise_knowledge_graph.py`:

- `test_surface_filter_excludes_others`: call with `--surface agents`, mock data
  with agent and ticket nodes, assert only agent nodes in embedded JSON.
- `test_project_root_flag_passed_to_kq`: mock `load_surfaces`, assert it is called
  with the value passed to `--project-root`.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      |                |           |
| AC-2 |      |                |           |
| AC-3 |      |                |           |
| AC-4 |      |                |           |

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Risk & Safety

- Touches money? No.
- Touches data? No — read-only. Output goes to `/tmp` and is never committed.
- Reversibility? Fully reversible — remove the two argparse lines to revert.
- Risk of regressions: minimal. Additive flags only; existing `--output` and
  `--no-open` behavior is unchanged.
