---
title: "ADR-017: Dual-Engine Workflow Support — Canonical E2 Authoring + Build-Time E1 Shim"
description: "Records the decision to author all new workflow scripts exclusively in E2 top-level-body form, generate E1-compatible shim wrappers at build time, use a runtime engine-detection predicate to route execution, and explicitly fail on unrecognised engines rather than fall back to LLM. Establishes the canonical E2 authoring contract based on empirical probes of the Claude Code 2.1.185 workflow engine."
type: "adr"
status: "active"
created: "2026-07-01"
last_updated: "2026-07-01"
deciders:
  - supervisor_system
components:
  - supervisor_system
tags:
  - workflow-engine
  - e1-e2-compat
  - build-transform
related_docs:
  - docs/reference/workflow-authoring-contract.md
  - docs/architecture/diagrams/df-001-dual-engine-workflow-build-transform.md
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
related_code:
  - templates/workflows-js/quick-fix.js
---

# ADR-017: Dual-Engine Workflow Support — Canonical E2 Authoring + Build-Time E1 Shim

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-07-01 |
| Deciders | supervisor_system |
| Author | documentation-expert |
| Supersedes | — |

## Context

### The E1 → E2 contract shift

Claude Code's workflow engine has two distinct execution contracts, referred to in
this repo as **E1** and **E2**:

- **E1 (legacy)**: a workflow script exports an async function
  `export async function run({ agent, workflow, parallel, userInput }) { ... }`.
  The engine invokes this export directly. The `agent()` primitive accepts a
  structured object `{ agentType, input }` and returns raw text. The caller is
  responsible for `JSON.parse`-ing any structured response.

- **E2 (current, Claude Code ≥ 2.1.154)**: a workflow script is a top-level body
  with no mandatory export. The engine executes the body directly. Globals
  (`agent`, `parallel`, `pipeline`, `phase`, `log`, `args`, `workflow`, `budget`)
  are injected into scope. The `agent()` primitive accepts a string prompt and an
  options object `{ agentType, schema, label, phase, effort }`; when `schema` is
  provided, the return value is an already-parsed, schema-validated object.

### The no-op problem

The E1 export pattern silently does nothing on an E2 engine. If a script
begins with `export async function run(...)`, the E2 engine executes the
top-level body (which defines the function but never calls it) and returns
`undefined`. The script appears to run but produces no result. This was
confirmed empirically (see "Probe Evidence" below) and explains why
`/plan-feature` and `/finalize-feature` were observed to be no-ops in
production: their `.js` scripts used the E1 export pattern.

### No official hand-authoring documentation

Anthropic does not publish a hand-authoring reference for E2 workflow scripts.
The canonical working reference is `templates/workflows-js/quick-fix.js`,
which was authored in E2 top-level-body form and confirmed to work correctly
in Claude Code 2.1.185.

### The design question this ADR resolves

Before porting existing E1 scripts to E2 and writing a build-time transformer
(tickets 04/05/06 of EPIC-DualEngineWorkflowSupport), this ADR pins down:

1. Exactly how E2 surfaces the result of a top-level `return`.
2. Which E1/E2 differences cannot be made transparent by a shim.
3. The canonical authoring shape for new scripts.
4. How to handle hosts whose engine cannot be identified.

## Probe Evidence

Two zero-side-effect probes were executed against Claude Code 2.1.185 to answer
the open empirical questions. The results are recorded verbatim here because no
official documentation covers them.

### Probe 1 — E1 export is not auto-invoked on E2

**Script dispatched:**
```javascript
// probe-e1-noop.js
let runWasCalled = false

export async function run({ agent }) {
  runWasCalled = true
}

// Top-level body — E2 executes this
return { runWasCalled }
```

**Result returned by the engine:** `{ runWasCalled: false }`

**Finding:** The exported `async function run(...)` is NEVER auto-invoked on
the E2 engine. The top-level body is the execution entry point. `runWasCalled`
remained `false`, confirming that E1-style scripts are silent no-ops.

### Probe 2 — Top-level return surfaces the workflow result

**Script dispatched:**
```javascript
// probe-return-surface.js
const value = { status: 'ok', probe: 'top-level-return', verified: true }
return value
```

**Result returned by the engine:** `{ status: 'ok', probe: 'top-level-return', verified: true }`

**Finding:** The top-level `return` statement value becomes the workflow result
directly. No intermediate serialization or extraction is needed. When `schema:`
is passed to `agent()`, the result is already parsed and schema-validated — no
caller-side `JSON.parse` is required.

## Decision

**Canonical-E2 authoring + build-time-wrap-for-E1, no LLM fallback.**

This decision has four concrete components:

### 1. All new scripts authored in E2 top-level-body form

Every new workflow script is written as a top-level-body E2 script. No hand-authored
E1 `export async function run(...)` variants are created. The `quick-fix.js` template
is the canonical example to follow (see `docs/reference/workflow-authoring-contract.md`
for the minimal skeleton).

### 2. Build-time transformer generates E1-compatible shim wrappers

A build-time transformer reads each E2 source script and emits an E1-compatible shim
wrapper alongside it. The shim wraps the E2 body inside an
`export async function run({ agent, workflow, parallel, userInput })` export and
embeds a `callAgent` adapter that bridges the E2 `agent(prompt, {schema})` API to
the E1 `agent({ agentType, input })` API. The transformer is purely mechanical — no
LLM is involved in shim generation.

### 3. Runtime engine-detection predicate routes execution

Both variants (E2 native and E1 shim) ship together. At runtime, the shim uses the
following deterministic predicate to identify the host engine:

```javascript
// workflow() throws on E2 (leaf-invariant guard).
// On E1, workflow is a passed function — typeof returns 'function'.
const IS_E2 = (function detectEngine() {
  try { workflow(); return false } catch (_) { return true }
})()
```

- `IS_E2 = true` (workflow() threw) → E2 host; use native `agent(prompt, {schema})`.
- `IS_E2 = false` (workflow() did not throw) → E1 host; use `callAgent` adapter.

### 4. No LLM fallback on unrecognised engines

If neither the E2 predicate nor the E1 predicate can be satisfied — i.e., the
engine behaves in an unexpected way — the script fails explicitly with a structured
error payload. There is no LLM-mediated "try to figure it out" fallback path.
Silent degradation is worse than an explicit failure.

## Consequences

### What changes

- All future workflow scripts are authored in E2 top-level-body form.
- The build pipeline (ticket 04) gains a transform step that generates E1 shim
  wrappers from E2 sources.
- Existing E1-form scripts (`plan-feature.js`, `finalize-feature.js`, and others)
  are ported to E2 form in tickets 05/06.
- The runtime routing predicate (`typeof workflow !== 'function'` / `IS_E2`) is
  standard across all shim-wrapped scripts.

### What stays the same

- The `quick-fix.js` reference script already conforms to E2 form; it requires
  no changes.
- The `agent()` call signature (prompt string + options object) is the canonical
  pattern going forward.
- Ticket-supervisor and epic-supervisor dispatch logic is unchanged.

### Non-transparent edges (cannot be bridged by the shim)

The following E1/E2 differences remain visible to the caller regardless of which
execution path is taken. Each edge has a mandated handling convention:

| Edge | Affected engine | Handling convention |
|---|---|---|
| **`Date.now()` / `new Date()` / `Math.random()` banned in E2** | E2 only | Workflow validation rejects scripts that mention these symbols. Pass timestamps or seeds from outside via `args`. Never call these inside a workflow script body. |
| **`parallel()` cap: 4096 items / ~16 concurrent** | E2 only | Keep parallel fan-out below 16 branches. E1 has no such cap. Document the cap in any script that fans out more than 4 branches. |
| **Schema-enforcement asymmetry** | E2 enforces; E1 ignores | E2: `agent()` returns an already-parsed object when `schema` is provided. E1: `agent()` returns raw text; the callAgent adapter calls `JSON.parse`. Do not call `JSON.parse` on E2 results; the callAgent adapter handles this transparently on E1. |
| **User gate asymmetry** | E1 had `userInput` param; E2 has none | E1 supported an interactive `prompt(userInput, ...)` gate. E2 has no `userInput` global — user gates must be implemented as an agent turn. Design gates as `agent()` calls that ask the user a yes/no question and return `status: ok` or `status: blocked`. |
| **`workflow()` leaf-invariant** | E2 only | In E2, calling `workflow()` throws because the script IS the workflow (leaf-level guard). In E1, `workflow` was a passed function. Use `typeof workflow !== 'function'` to detect E2 (or the IIFE-with-try pattern above) — never call `workflow()` for detection, only to probe its type. |

## Alternatives Considered

### Alternative 1: LLM fallback on unrecognised engines

**Description:** When the engine cannot be identified by the predicate, invoke an
LLM agent to inspect the invocation context and determine the correct execution path.

**Why rejected:** Silent degradation is the worst failure mode for a deterministic
build pipeline. An LLM fallback introduces unreliable, non-reproducible behaviour at
the point where the system is already in an unexpected state. It also increases cost
and latency on every uncertain invocation. If an engine is unrecognised, the correct
action is an explicit fast fail with a descriptive error payload — not a silent retry
with an LLM.

### Alternative 2: E1-only authoring

**Description:** Continue writing all scripts in E1 form (`export async function run`)
and live with the no-op behaviour on E2 hosts.

**Why rejected:** E1 is now a no-op on the E2 engine (proven by Probe 1 above). Scripts
written in E1 form do not execute. Adopting E1-only authoring would mean the entire
workflow infrastructure remains non-functional on the current engine version. This is
not a viable path.

### Alternative 3: Maintain two separate script sets (E1 and E2)

**Description:** Write each workflow script twice — once in E1 form for E1 hosts and
once in E2 form for E2 hosts — and deploy the correct variant based on host detection.

**Why rejected:** Double maintenance burden. Every logic change must be applied to two
files. The two sets will inevitably diverge. The build-time-transform approach achieves
the same compatibility goal from a single authoritative source. The cost of maintaining
the transformer is bounded and one-time; the cost of hand-maintaining two sets is
unbounded and ongoing.

## References

- `templates/workflows-js/quick-fix.js` — canonical working E2 reference.
- `docs/reference/workflow-authoring-contract.md` — copy-pasteable E2 skeleton and E1-wrap shim spec.
- `docs/architecture/diagrams/df-001-dual-engine-workflow-build-transform.md` — data flow diagram of the build-time transform and runtime routing.
- `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md` — the earlier decision that introduced workflow scripts as the depth-1 supervisor mechanism.
- EPIC-DualEngineWorkflowSupport ticket 03 — the spike that produced the probe evidence recorded here.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-01 [documentation-expert]: Initial creation. Records the dual-engine
  workflow support decision (canonical E2 authoring + build-time E1 shim +
  runtime engine-detection predicate + no LLM fallback). Probe evidence from
  two zero-side-effect Claude Code 2.1.185 workflow probes recorded verbatim.
  Non-transparent edges enumerated with handling conventions.
  Created as part of ticket 03 of EPIC-DualEngineWorkflowSupport.
====================================================================
-->
