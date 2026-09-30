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
- **Status:** open — partially resolved 2026-09-30 (see Occurrence 2); the hardcoding
  itself, the duplication, and the `fast-lane-ship.js` case all remain.
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-09-30
- **Where:** `scripts/registry_validator.py:36`, used at `:291` and `:317`. A SECOND,
  independently-maintained copy of the same set lives in
  `templates/scripts/commit_guardian/hooks/check_agent_spawn_consistency.py:40`
  (found 2026-09-30; not noted at filing).

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

**Occurrence 2 — 2026-09-30. It stopped being theoretical and blocked a build.**

Fixing `KI-ACD-20260928` re-routed `/plan-feature`'s six pause-store dispatches to
`command-step-runner`. Recording that in the registry — `spawned_by: ["user",
"plan-feature.js"]` — made `build.py` exit 1:

```
[ERROR] [REGISTRY] Agent 'command-step-runner' spawned_by references unknown agent 'plan-feature.js'.
```

Four tests failed with it, all of which run a real build and assert exit 0. So the
prediction in this entry — "`build.py` fails as the penalty for making it more correct" —
played out exactly, this time on a change that could not simply be left unrecorded: the
workflow genuinely dispatches that agent now.

This entry's own stated minimum fix was applied: `"plan-feature.js"` added alongside
`"finalize-feature.js"`, in BOTH copies, with the comment rewritten to explain why the set
exists. Build back to exit 0, `agent_registry.json is consistent (no errors)`, full
workflows suite 838 passed / 0 failed. Landed in `179d5245`.

**What remains, and why this entry stays open:**

- **The set is still hardcoded.** The derived form this entry proposed — any `.js` caller
  under `templates/workflows-js/` is by construction not an agent — was not built. The next
  workflow to dispatch an agent hits this identically.
- **It is duplicated.** The same literal set is maintained by hand in `registry_validator.py`
  and in the `check_agent_spawn_consistency.py` hook. Nothing mechanical keeps them equal;
  updating one and not the other is silent. A shared module both import would turn "remember
  to edit both files" into "there is one file", and the deploy-manifest convention for shared
  hook dependencies already exists to carry it.
- **`fast-lane-ship.js` is still unrecordable.** `command-step-runner`'s own template says
  so in `adopter_notes`: *"the fast lane's own dispatcher (fast-lane-ship.js) is not yet
  listed there because scripts/registry_validator.py's _EXTERNAL_CALLERS set does not yet
  include it; adding it is a Python change (python-coder's area, routed separately)."* So the
  agent purpose-built to be dispatched by workflows could not, until this occurrence, be
  declared as dispatched by ANY workflow. It still cannot be declared for the fast lane.

**Pattern:** an allowlist that has to be edited by hand every time the system does something
it was designed to do, kept in two places that nothing compares.

---
