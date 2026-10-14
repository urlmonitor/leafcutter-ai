---
title: "Spawn Graph Consistency Validation"
description: "How the build (registry_validator.py) and the check-agent-spawn-consistency commit hook enforce that spawn_allowlist and spawned_by entries in config/agent_registry.json are reciprocal, and which entries are exempt."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - agent_registry
related_docs:
  - docs/agents/README.md
  - config/agent_registry.json
---

# Spawn Graph Consistency Validation

The build system enforces bidirectional consistency of the spawn graph at two levels:

**Build-time (registry_validator.py):** Every build run calls `validate_agent_registry()` which checks that:
- For each agent A with `spawn_allowlist` entry B: B's `spawned_by` must include A.
- For each agent A with `spawned_by` entry B: B's `spawn_allowlist` must include A.

Violations are reported using the `"asymmetric spawn:"` prefix to clearly name both agents involved:
```
asymmetric spawn: A.spawn_allowlist includes B, but B.spawned_by does not include A
asymmetric spawn: A.spawned_by includes B, but B.spawn_allowlist does not include A
```

**Commit-time (check-agent-spawn-consistency hook):** When `config/agent_registry.json` is staged, the `check-agent-spawn-consistency` pre-commit hook runs the same bidirectional check and exits 1 with named-pair errors before a bad registry state can be committed.

Exemptions:
- `__ticket_phase_agents__` special token in `spawn_allowlist` is silently skipped.
- External callers (`user`, `finalize-feature.js`) in `spawned_by` are silently skipped.

**Reference**: AC INF-600g-1 — Build validates that spawned_by entries are reciprocal with spawn_allowlist entries.

Parent document: [Agents README](README.md).
