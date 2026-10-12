---
title: "KI-AR-005 — No project-local agent definition location: declared sub-agents can only resolve to packaged templates"
description: "KI-AR-005 — a declared sub-agent resolves only to a packaged templates/agents/<id>.md; the project-local lookup exists but finds nothing because no project-local agent location has been designed"
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - agent_registry
related_docs:
  - docs/known-issues/agent-registry.md
  - docs/known-issues/README.md
---

# KI-AR-005 — No project-local agent definition location: declared sub-agents can only resolve to packaged templates

> Index: [agent-registry.md](../agent-registry.md).

- **Severity:** low
- **Status:** open — no AC (design deferred by BrainCandy, 2026-10-09)
- **Occurrences:** 1
- **First seen:** 2026-10-09 · **Last seen:** 2026-10-09
- **Where:** `scripts/agent_ability_verdict.py` (`_project_local_agent_exists`, which always returns False; `verify_spawn_allowlists`, which reports both lookups as failed for an unresolvable sub-agent)

**What was found.** AR-300c-5-iii makes the build refuse when an agent's `spawn_allowlist` names a
sub-agent that resolves to no deployable definition, and its finding states which lookups came back
empty: `packaged` (no `templates/agents/<id>.md`) and `project_local` (no agent of the project's own).
Skills have a project-local surface (`<output_root>/skills/<id>/SKILL.md`), so the same two-surface
report was specified for agents. Agents do not: this package has no defined place where a consuming
project keeps an agent definition of its own, so there is nothing for a project-local lookup to read.

**What was done now.** BrainCandy decided (2026-10-09) to resolve declared sub-agents against the
packaged templates only. The project-local lookup is its own small function and currently finds
nothing for every id, so a finding still lists both lookups as failed and the report keeps its
two-surface shape. Neither a registry row nor a compiled prompt left under `<output_root>/agents/` by
an earlier build counts as a definition — they are not authored sources and would let a deleted
template keep "resolving".

**The follow-up this entry holds.** Design where a project-local agent definition lives, how a build
discovers it, whether it is compiled into the same platform roots as a packaged agent, and what a
packaged agent of the same id does to it (the capability-collision rule skills already follow). When
that is decided, only `_project_local_agent_exists` changes, and a project can then declare a
sub-agent it defines itself.

**Pattern:** a two-surface lookup whose second surface has no defined location — the report promises
a place to add the missing definition that does not exist yet.
