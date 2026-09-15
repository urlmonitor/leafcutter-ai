---
title: "KI-AR-001 — `agent_registry.schema.json` is inert: nothing validates the registry against it"
description: "KI-AR-001 — `agent_registry.schema.json` is inert: nothing validates the registry against it"
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

# KI-AR-001 — `agent_registry.schema.json` is inert: nothing validates the registry against it

> One known issue, split out of `docs/known-issues/agent-registry.md` on
> 2026-09-14. Index: [agent-registry.md](../agent-registry.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

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
