---
title: "Reference: Workflow Authoring Contract (E2 Canonical + E1-Wrap Shim)"
description: "Copy-paste reference for workflow script authors covering the E2 canonical execution contract, E1-wrap shim pattern, primitive mapping table, and non-transparent edge handling conventions."
type: reference
status: active
created: 2026-07-01
last_updated: 2026-07-01
components:
  - supervisor_system
related_docs:
  - docs/architecture/adrs/ADR-017-dual-engine-workflow-support.md
  - docs/architecture/diagrams/df-001-dual-engine-workflow-build-transform.md
  - docs/reference/workflow-constraints.md
---

# Workflow Authoring Contract

This is the copy-paste reference for workflow script authors. It covers the E2
canonical execution contract (the form all new scripts must use), the E1-wrap shim
pattern for compatibility with E1-engine hosts, a complete primitive mapping table,
and all five non-transparent E1/E2 edges with their required handling conventions.

**E2 is the canonical engine.** All new workflow scripts must be authored in E2
top-level-body form. The E1-compatible shim wrapper is generated mechanically at
build time from the E2 source — no hand-authored E1 variants are created.

---

## 1. Overview

Claude Code's workflow engine has two execution contracts:

- **E2 (current, Claude Code ≥ 2.1.154):** The engine executes the script's
  top-level body directly. Globals (`agent`, `parallel`, `pipeline`, `phase`,
  `log`, `args`, `workflow`, `budget`) are injected into scope. A top-level
  `return` statement surfaces the workflow result.

- **E1 (legacy):** The engine calls `export async function run({ agent, workflow, parallel, userInput })`.
  The `agent()` primitive returns raw text; the caller must `JSON.parse` any
  structured response. **On an E2 host, E1 scripts are silent no-ops** — the
  body defines the export function but never calls it, so the workflow returns
  `undefined`.

The build pipeline generates E1-compatible shim wrappers from E2 source scripts
so that the same codebase can be deployed to both engine versions without
hand-maintaining two sets of files.

**Canonical working reference:** `templates/workflows-js/quick-fix.js`

---

## 2. Canonical E2 Skeleton

Copy-paste this skeleton when creating a new workflow script. Replace the
placeholder comments with your script's logic.

```javascript
/**
 * <script-name>.js — Claude Code Workflow script
 * <one-line description of what this workflow does>
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 */

// ---------------------------------------------------------------------------
// JSON Schemas for agent() responses
// ---------------------------------------------------------------------------
// Define one schema per agent call. Schemas are enforced by the E2 engine;
// agent() returns an already-parsed, schema-validated object when schema is
// provided — do NOT call JSON.parse() on the result.

const RESULT_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    message: { type: 'string' },
  },
  required: ['status'],
}

// ---------------------------------------------------------------------------
// Phase labels (optional but recommended for UI feedback)
// ---------------------------------------------------------------------------
// phase() sets a visible label in the workflow UI. Call it at the top of each
// logical phase. It is an E2-only primitive — not available on E1.

phase('Main')

// ---------------------------------------------------------------------------
// CLI args
// ---------------------------------------------------------------------------
// args is the E2 global for CLI arguments passed to the workflow.
// On E1, the equivalent is the userInput parameter of run().

const input = args  // { key: value, ... }

if (!input || !input.target) {
  log('Missing required arg: target')
  return {
    status: 'blocked',
    phase: 'Main',
    message: 'Pass args: { target: "..." }',
  }
}

// ---------------------------------------------------------------------------
// Agent call
// ---------------------------------------------------------------------------
// agent(prompt, opts) — prompt is always a STRING.
// opts.schema: when provided, the return value is already parsed and validated.
// opts.agentType: the registered agent type to dispatch.
// opts.label: human-readable label for this call in the workflow log.
// opts.phase: associates the call with a phase label (for UI grouping).
// opts.effort: optional effort hint ('low' | 'medium' | 'high').

const result = await agent(
  `Your task: ${JSON.stringify(input)}. Return structured JSON.`,
  {
    agentType: 'general-purpose',  // or any registered agent type
    schema: RESULT_SCHEMA,          // result is already-parsed, schema-validated
    label: 'main-task',
    phase: 'Main',
  }
)

if (!result || result.status === 'blocked') {
  return {
    status: 'blocked',
    phase: 'Main',
    message: result ? result.message : 'Agent returned null',
    detail: result,
  }
}

log(`Task complete: ${result.message}`)

// ---------------------------------------------------------------------------
// Top-level return surfaces the workflow result
// ---------------------------------------------------------------------------
// The value of the top-level return statement becomes the workflow result.
// It is returned as-is to the caller (no additional serialization).

return { status: 'ok', result }
```

### Key rules for E2 scripts

- **No `export` at the top level.** The E2 engine executes the top-level body;
  an `export async function run(...)` is silently ignored (never called).
- **`agent()` prompt is always a string.** Pass a string, not an object.
- **Do not call `JSON.parse()` on `agent()` results** when `schema` is provided.
  The engine already parses and validates the response.
- **Do not use `Date.now()`, `new Date()`, or `Math.random()`.** Workflow
  validation rejects scripts that reference these. Use `args` to pass timestamps
  or seeds from outside.
- **Top-level `return` is the result.** There is no other mechanism to surface
  a result from an E2 script.

---

## 3. E1-Wrap Shim Pattern

The shim pattern enables an E2-authored script to run on an E1-engine host. It is
generated mechanically at build time from the E2 source — authors do not write it
by hand. It is documented here so the build transformer can be audited and so
authors understand what is generated.

```javascript
// ---------------------------------------------------------------------------
// Engine-detection predicate
// ---------------------------------------------------------------------------
// workflow() throws on E2 (leaf-invariant guard — the script IS the workflow).
// On E1, workflow is a passed function; typeof returns 'function'.
//
// The IIFE-with-try pattern is the safe detection form. Never call workflow()
// for side effects — only use it to probe the engine type.

const IS_E2 = (function detectEngine() {
  try { workflow(); return false } catch (_) { return true }
})()

// ---------------------------------------------------------------------------
// callAgent adapter
// ---------------------------------------------------------------------------
// Bridges E2 agent(prompt, opts) to E1 agent({ agentType, input }).
//
// On E2: agent() returns an already-parsed object when schema is provided.
// On E1: agent() returns raw text; the adapter calls JSON.parse().
//
// Replace all direct agent() calls in the script body with callAgent().

async function callAgent(prompt, opts = {}) {
  if (IS_E2) {
    // E2: native API — result is already parsed and schema-validated.
    return agent(prompt, opts)
  } else {
    // E1: structured object API; result is raw text.
    const raw = await agent({
      agentType: opts.agentType || 'general-purpose',
      input: prompt,
    })
    // Parse the text response if a schema was requested.
    return opts.schema ? JSON.parse(raw) : raw
  }
}

// ---------------------------------------------------------------------------
// E1 export shim (the entry point for E1-engine hosts)
// ---------------------------------------------------------------------------
// This export is invoked by an E1 engine. An E2 engine executes the
// top-level body directly and ignores this export.

export async function run({ agent: _agentE1, workflow: _wf, parallel: _par, userInput }) {
  // Delegate to the E2 body logic via callAgent.
  // The E2 body is inlined or called here by the build-time transformer.
  //
  // Example: if the E2 body makes one callAgent call and returns a result:
  const result = await callAgent(
    `Your task: ${JSON.stringify(userInput)}. Return structured JSON.`,
    { agentType: 'general-purpose', schema: RESULT_SCHEMA }
  )
  return result
}
```

### Engine-detection contract

| Condition | IS_E2 value | Meaning |
|---|---|---|
| `workflow()` throws | `true` | E2 host — use native `agent(prompt, opts)` |
| `workflow()` does not throw | `false` | E1 host — use `callAgent` adapter |

**Never use `workflow()` for any purpose other than engine detection.** On E2 it
always throws. On E1 it has side effects that may interfere with the calling harness.

---

## 4. Primitive Mapping Table

| Primitive | E1 form | E2 form | Notes |
|---|---|---|---|
| **Script entry** | `export async function run({ agent, workflow, parallel, userInput }) { ... }` | Top-level body (no export) | E1 export is a no-op on E2; E2 body is a no-op on E1 (function defined but not called) |
| **Agent call** | `await agent({ agentType, input }) → string` | `await agent(prompt, { agentType, schema, label, phase, effort }) → object` | E2 returns an already-parsed object when `schema` is provided; E1 always returns raw text |
| **Result surfacing** | `return value` inside `run()` | Top-level `return value` | Same keyword; different scope |
| **Parallelism** | `await parallel([...])` | `await parallel([...])` (cap: 4096 items, ~16 concurrent) | E2 has a concurrency cap; E1 does not |
| **Pipeline** | `await pipeline([...])` | `await pipeline([...])` | Same interface on both engines |
| **Phase labels** | Not available | `phase('Name')` | E2-only; sets a visible label in the workflow UI |
| **Logging** | Not available | `log('message')` | E2-only; appears in the workflow run log |
| **CLI args** | `userInput` parameter of `run()` | `args` global | E1 uses the function parameter; E2 uses a global |
| **Budget** | Not available | `budget` global | E2-only; read-only token/cost budget object |
| **Engine probe** | Not available | `workflow()` throws | Use to detect E2 at runtime; never call for side effects |
| **User gate** | `await prompt(question)` via `userInput` | Agent turn: `await agent(question, { schema: GATE_SCHEMA })` | E2 has no interactive prompt primitive; model gates via a yes/no agent call |
| **Workflow nesting** | `await workflow(name, args)` via passed `workflow` fn | `workflow()` throws (leaf-invariant guard) | E2 forbids nested workflow invocation; use the engine-detection IIFE to probe |

---

## 5. Non-Transparent Edges and Handling Conventions

These five differences between E1 and E2 **cannot be made transparent by the
shim**. They remain visible to the caller regardless of which execution path is
active. Every workflow script author must understand and handle all five.

### Edge 1: `Date.now()` / `new Date()` / `Math.random()` banned in E2

**What:** The E2 workflow validation pass rejects scripts that mention
`Date.now()`, `new Date()`, or `Math.random()` in their source text.

**Why:** E2 enforces deterministic execution for reproducibility and testing.
Non-deterministic primitives break this guarantee.

**Which engine:** E2 only. E1 has no such restriction.

**Handling convention:** Never call these primitives inside a workflow script
body. If you need the current timestamp or a random seed, pass it from outside
via `args` before invoking the workflow:

```javascript
// Caller passes the timestamp:
// /my-workflow --timestamp 1751356800

const timestamp = args.timestamp  // use this instead of Date.now()
```

### Edge 2: `parallel()` cap — 4096 items total, ~16 concurrent

**What:** `parallel()` in E2 is capped at 4096 items total and approximately
16 concurrent branches. Exceeding these limits causes the parallel call to
fail or silently truncate.

**Why:** E2 enforces resource limits to protect the harness from runaway
fan-out.

**Which engine:** E2 only. E1 has no documented parallel cap.

**Handling convention:** Keep parallel fan-out below 16 concurrent branches.
For large collections, chunk the input and fan out in batches:

```javascript
// Instead of parallel([...thousandsOfItems]):
const BATCH_SIZE = 12  // well below the ~16 cap
for (let i = 0; i < items.length; i += BATCH_SIZE) {
  const batch = items.slice(i, i + BATCH_SIZE)
  await parallel(batch.map(item => agent(`Process: ${item}`, { schema: ITEM_SCHEMA })))
}
```

### Edge 3: Schema-enforcement asymmetry

**What:** On E2, when `schema` is passed to `agent()`, the engine enforces the
JSON Schema and returns an already-parsed object — the caller does NOT call
`JSON.parse`. On E1, `agent()` always returns raw text regardless of the options
passed; the caller must `JSON.parse` any structured response.

**Which engine:** Both — the asymmetry is between the two engines.

**Handling convention:** In E2-native scripts (the canonical form), do not call
`JSON.parse` on `agent()` results when `schema` is provided. In the E1 shim's
`callAgent` adapter, `JSON.parse` is called automatically when `opts.schema` is
present. Do not call `JSON.parse` again at the call site:

```javascript
// Correct in both E2 (native) and E1 (via callAgent):
const result = await callAgent('...', { schema: MY_SCHEMA })
// result is already an object — do NOT do JSON.parse(result)

if (result.status === 'ok') { ... }
```

### Edge 4: User gate asymmetry — `prompt()` vs agent-mediated gate

**What:** E1 had access to a `prompt(question, opts)` global (via the
`userInput` parameter) for interactive mid-workflow user gates. E2 has no
`userInput` global and no interactive `prompt()` primitive.

**Which engine:** E1 only (the `prompt()` gate). E2 does not support it.

**Handling convention:** In E2 scripts, implement user gates as a dedicated
agent turn. The agent presents the question to the user, waits for a response,
and returns `status: 'ok'` or `status: 'blocked'`:

```javascript
const GATE_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    message: { type: 'string' },
  },
  required: ['status'],
}

const gateResult = await agent(
  `WARNING: This action will modify production data.\n\nAsk the user: "Proceed? (yes/no)".\n\nReturn status:"ok" if yes; status:"blocked" with message if no.`,
  { label: 'user-gate', schema: GATE_SCHEMA }
)

if (!gateResult || gateResult.status === 'blocked') {
  return { status: 'blocked', phase: 'Gate', message: gateResult?.message ?? 'User declined.' }
}
```

### Edge 5: `workflow()` leaf-invariant

**What:** In E2, calling `workflow()` throws an error because the script IS the
workflow (leaf-level guard). There is no callable `workflow` function in scope.
In E1, `workflow` was a function passed to `run()` that could be used to invoke
nested workflows.

**Which engine:** E2 only (the leaf-invariant throw). E1 hosts pass `workflow`
as a live function.

**Handling convention:** Use `workflow()` exclusively as an engine-detection
probe, inside an IIFE that catches the throw:

```javascript
// Correct: engine-detection only — never for side effects.
const IS_E2 = (function detectEngine() {
  try { workflow(); return false } catch (_) { return true }
})()
```

Do not call `workflow()` for any other purpose in an E2-targeted script. Do not
use `typeof workflow` without the try/catch — the binding exists in E2 scope but
throws when called, so `typeof` alone does not distinguish E1 from E2 reliably.

---

## 6. Quick Reference — E2 Globals

| Global | Type | Description |
|---|---|---|
| `agent(prompt, opts)` | `async function` | Dispatch an agent. Prompt is a string. Returns a parsed object when `opts.schema` is provided. |
| `parallel(promises)` | `async function` | Fan out multiple agent calls concurrently. Cap: 4096 items / ~16 concurrent. |
| `pipeline(steps)` | `async function` | Execute a sequential pipeline of agent calls. |
| `phase(name)` | `function` | Set the current phase label in the workflow UI. |
| `log(message)` | `function` | Append a message to the workflow run log. |
| `args` | `object` | CLI arguments passed to the workflow invocation. Read-only. |
| `workflow` | (throws) | Leaf-invariant guard — throws when called. Use only in the engine-detection IIFE. |
| `budget` | `object` | Read-only token/cost budget information for this workflow run. |

---

## See Also

- `templates/workflows-js/quick-fix.js` — canonical working E2 workflow script.
- `docs/architecture/adrs/ADR-017-dual-engine-workflow-support.md` — the
  architectural decision this contract implements, including probe evidence.
- `docs/architecture/diagrams/df-001-dual-engine-workflow-build-transform.md` —
  data flow diagram of the build-time transform and runtime routing.
- `docs/reference/workflow-constraints.md` — runtime constraints (min version,
  token cost, crash-resume) for deployed workflow scripts.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-01 [documentation-expert]: Initial creation. Establishes the canonical
  E2 workflow authoring contract: top-level-body skeleton, E1-wrap shim pattern
  (callAgent adapter + engine-detection predicate), primitive mapping table,
  and all five non-transparent E1/E2 edges with handling conventions.
  Created as part of ticket 03 of EPIC-DualEngineWorkflowSupport.
====================================================================
-->
