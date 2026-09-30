---
title: "KI-AR-002 — `_EXTERNAL_CALLERS` is a hardcoded two-item set, so documenting a real spawn relationship fails the build"
description: "KI-AR-002 — `_EXTERNAL_CALLERS` is a hardcoded two-item set, so documenting a real spawn relationship fails the build"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - agent_registry
related_docs:
  - docs/known-issues/agent-registry.md
  - docs/known-issues/README.md
---

# KI-AR-002 — `_EXTERNAL_CALLERS` is a hardcoded two-item set, so documenting a real spawn relationship fails the build

> One known issue, split out of `docs/known-issues/agent-registry.md` on
> 2026-09-14. Index: [agent-registry.md](../agent-registry.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/registry_validator.py:36`, used at `:291` and `:317`

**Symptom.** The spawn-graph check requires `spawn_allowlist` and `spawned_by` to agree in
both directions, exempting a fixed set of callers that are not themselves agents:

```python
_EXTERNAL_CALLERS = {"user", "finalize-feature.js"}
```

`plan-feature.js` is not in it, and `plan-feature.js` dispatches agents — around thirty call
sites, including the workspace-setup step. So the accurate `spawned_by` entry for any agent
that workflow spawns cannot be written down: adding `"plan-feature.js"` to an agent's
`spawned_by` makes `:291` look for a matching agent named `plan-feature.js`, find none, and
fail `build.py`. The registry is therefore forced to under-describe the real topology, and
`build.py` fails as the penalty for making it more correct.

**Evidence.** Surfaced while implementing `BO-1500f-1`, which re-points the workspace-setup
dispatch from `status-checker` to `worktree-agent`. Recording that relationship in
`worktree-agent`'s `spawned_by` would have broken the build, so it was left unrecorded.
`ADR-021` (`:181-183`) has already ruled that plan-feature's dispatches need no registry
change — which resolves the immediate question but leaves the asymmetry: `finalize-feature.js`
is exempt and `plan-feature.js` is not, for no stated reason.

**Fix direction.** Derive the exemption set rather than hardcoding it — any `.js` caller
under `templates/workflows-js/` is by construction not an agent — or at minimum add
`plan-feature.js` alongside `finalize-feature.js` and note why the set exists. Any new
workflow that dispatches agents hits this the same way.

**Re-verified 2026-09-23:** STILL TRUE, verbatim. `scripts/registry_validator.py:36`
still reads `_EXTERNAL_CALLERS = {"user", "finalize-feature.js"}` — unchanged;
`plan-feature.js` is still absent. Confirmed the consequence directly: loaded
`config/agent_registry.json` and read `worktree-agent`'s `spawned_by` field — it is
`['user', 'epic-supervisor', 'finalize-feature.js']`, with `plan-feature.js` still
missing despite `plan-feature.js` dispatching `worktree-agent` for its workspace-setup
step (see KI-BP-012's re-verification, same worktree, same date). `plan-feature.js`
itself now carries 37 `agentType:` dispatch sites (`grep -c "agentType:"
templates/workflows-js/plan-feature.js`), up from "around thirty" at filing — the
asymmetry with `finalize-feature.js` has not narrowed. Affects `/plan-feature`: yes,
unambiguously — `plan-feature.js` is the specific caller named as excluded from
`_EXTERNAL_CALLERS`, and the unrecorded relationship is `/plan-feature`'s own
workspace-setup dispatch, not some other workflow's.

---
