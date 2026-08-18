---
title: "Known issues — agent-registry"
description: "Open, observed defects in the agent-registry component: config/agent_registry.json, its JSON Schema, and scripts/registry_validator.py — the declared contract for what each agent is and who may spawn it. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - agent_registry
related_docs:
  - docs/architecture/components/agent-registry.md
  - docs/architecture/components/supervisor-spawn-topology.md
---

# Known issues — agent-registry

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-AR-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-AR-001 — `agent_registry.schema.json` is inert: nothing validates the registry against it

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `config/agent_registry.schema.json` (`additionalProperties: false` at `:189`, `:192`, `:216`, `:233`); `scripts/registry_validator.py`

**Symptom.** The schema file looks authoritative — it enumerates every permitted agent
property and closes the object with `additionalProperties: false`, which by its own terms
makes any undeclared field invalid. No code enforces it. `registry_validator.py` performs
bespoke Python checks (template paths, spawn bidirectionality, `skills_used` existence,
`produces` enum, `category` values) and never loads the schema. `build.py`'s only
`jsonschema` usage is in `_handle_config_errors` (`:198-223`), which validates
`skills_config.json`, not the registry. So the strictest-looking contract in this component
is documentation that reads like enforcement.

**Evidence.** `category` is present on essentially every agent entry and absent from the
schema — which, with `additionalProperties: false`, should fail every entry that has one:

```text
$ grep -c '"category"' config/agent_registry.json
58
$ grep -c '"category"' config/agent_registry.schema.json
0
```

58 violations, zero reported, indefinitely. The drift is harmless *only* because the schema
is inert; the moment anyone wires up real validation, the registry fails wholesale. The
schema is also missing `skills_invoked`, `knowledge_channels`, `components`,
`requires_verification`, `doc_links` and `behavioral_patterns`, all in live use.

**Why it matters now.** `BO-1500f-1` (merged 2026-08-18, `f3c65ff8b`) added a
`permits_shell` field that gates which agent may receive the repository-mutating
workspace-setup dispatch. It was correctly added to both the registry and the schema — but
"added to the schema" currently buys nothing. A future agent entry that omits
`permits_shell`, or sets it to the string `"true"`, is caught by no mechanical check;
`plan-feature.js` fails closed on it, which is the right behaviour but only converts a data
error into a halted run rather than a flagged one.

**Fix direction.** Either enforce the schema (load it in `registry_validator.py` and
validate every entry, after reconciling the seven undeclared fields so the first run is not
a wall of failures), or delete `additionalProperties: false` and stop implying a guarantee
nothing provides. The current state is the worst of the three: it reads as enforced, is not,
and quietly accumulates drift.

**Pattern:** `docs/reference/false-green-mechanisms.md` → the family in M1 — a declared
constraint that no code executes is indistinguishable from a satisfied one.

---

### KI-AR-002 — `_EXTERNAL_CALLERS` is a hardcoded two-item set, so documenting a real spawn relationship fails the build

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
