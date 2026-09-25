---
title: "KI-BO-20260925-1309 — A phase agent wraps its whole reply in one `input` string, and the schema's misleading error sends every retry after the wrong field, so the drive halts with the work already done"
description: "KI-BO-20260925-1309 — documentation-expert and ac-fulfillment-gate pass their phase result as a JSON string inside a single `input` field; the phase schema's handoff conditional then reports a missing handoff_target, the agent retries on that, and the five-retry cap halts the drive."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260925-1309 — A phase agent wraps its whole reply in one `input` string, and the schema's misleading error sends every retry after the wrong field, so the drive halts with the work already done

- **Severity:** blocker
- **Status:** open — mitigated by BO-3000b and BO-2000c-5 (see *Fix*); the underlying contract conflict has no AC yet
- **Occurrences:** 3 drives halted, all on 2026-09-25 against EPIC-TruthfulProjectRecord:
  `wf_ee4e9d81-680` (documentation-expert and ac-fulfillment-gate), `wf_e1f3e873-096`
  (documentation-expert). An earlier run in the same series halted on the same retry cap.
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-25
- **Where:** `templates/workflows-js/build-feature.js` `PHASE_RESULT_SCHEMA` (~:283-342) and its
  twin in `build-ticket.js` (~:146) · the "Machine-Parsed Dispatch Output Contract" block in 36
  files under `templates/agents/`

**Symptom.** The drive halts at the end of a batch with the ticket's work already written:

```text
agent({schema}): StructuredOutput retry cap (5) exceeded — 5 failed calls with no valid
output — last StructuredOutput error: Output does not match required schema:
root: must have required property 'handoff_target', root: must match "then" schema,
root: must have required property 'status'
```

The ticket is then reported `undetermined` with "unknown error". In every observed case the
deliverables were on disk and sound; only the phase's reply was malformed. Each ticket had to
be closed by hand.

**What the agent actually sent.** All five attempts from `documentation-expert` in
`wf_e1f3e873-096` passed one field, `input`, whose value was the intended reply serialised as
a JSON string:

```text
StructuredOutput {"input": "{\n  \"status\": \"ok\",\n  \"message\": \"Authored docs/how-to/...\"}"}
```

Agents that passed in the same runs (`commit`, `architecture-diagram-author`,
`documentation-verifier`) called the same tool with `status`, `message` and so on as fields
of their own. The tool does not force the wrapper.

**Two causes that compound.**

1. *The templates describe a different reply than the driver enforces.* 36 agent templates
   carry a "Machine-Parsed Dispatch Output Contract" saying the reply "MUST be exactly one JSON
   value and nothing else". Under schema enforcement the reply is a tool call whose fields are
   the schema's properties, not a JSON text. An agent that follows the template literally
   serialises its JSON and wraps it. It is probabilistic: `architecture-diagram-author` carries
   the same block and got it right.
2. *The schema's error points the retry at the wrong field.* The conditional is
   `if: { properties: { status: { const: 'handoff' } } }` with no `required: ['status']`.
   `properties` passes vacuously when `status` is absent, so a reply missing `status` satisfies
   the `if`, and the `then` demands `handoff_target`. The agent believes the message: on
   retries 3 and 5 it added `handoff_target` (`""`, then `"commit"`) and never removed the
   wrapper. Five retries spent on the wrong field.

**Same family as.** This is the fourth instance of one pattern: the driver's reply contract
lives in its schema, the agents read a different contract in their templates, and nothing
reconciles the two.
- [KI-BO-20260901-1045](open-blocker-ki-bo-20260901-1045.md) — the driver routes handoffs on
  `handoff_target`, which only 2 agent templates mention.
- [KI-BO-20260901-1052](open-high-ki-bo-20260901-1052.md) — `python-coder` hands off exactly as
  its template says and is rejected for the missing field.
- [KI-BO-20260907-0851](open-low-ki-bo-20260907-0851.md) — two templates use `handoff` to mean
  "stop, I need a human".
- [KI-BO-20260907-0850](open-high-ki-bo-20260907-0850.md) — `build-ticket.js` carries the same
  defects as its twin.
- [KI-BO-019](open-blocker-ki-bo-019.md) — a large context bundle passed through an agent's JSON
  return value arrives as a file path.
- PR #888 (BO-4000d) fixed the same failure shape for the worktree-facts reply, where the
  agent nested a complete envelope inside the envelope's own `output` field.

**Fix.** Two mitigations, each a one-line change per driver (`build-feature.js` and its twin
`build-ticket.js`), neither growing either file:
- [PR #902](https://github.com/urlmonitor/leafcutter-ai/pull/902) (BO-3000b): the schema's `if`
  also requires `status`, so a missing `status` is reported as exactly that and a retry can
  recover;
- [PR #903](https://github.com/urlmonitor/leafcutter-ai/pull/903) (BO-2000c-5): both
  phase-dispatch prompts tell the agent to fill the reply tool's fields directly — `status`,
  `message`, and `handoff_target` when handing off — and never to pass the reply as a JSON
  string or inside an `input` field. The old wording asked for "a JSON result", which is
  itself a nudge toward the failure.

Neither removes the conflict. The durable fix is to state the phase reply contract once, in the
shared `signoff` skill, and replace the conflicting output block in all 36 templates; that would
also close KI-BO-20260901-1045, -1052, KI-BO-20260907-0850 and -0851. It needs ACs through
`/plan-feature`, not a quick fix.
