---
title: "Leafcutter Kernel Specification Rev 3 - Part 5 of 8"
description: "In-tree copy of the Revision 3 Leafcutter decision-kernel specification (30 September 2026), part 5 of 8: Claude Code client, Langfuse, persistence and safeguards (sections 11-13). Text is verbatim; only cross-part anchor links were rewritten."
type: reference
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

> Source-of-truth specification for TICKET-20260930-KernelBootstrapV0, copied from the workspace file `leafcutter_kernel_bootstrap_specification.md`. Part 5 of 8 ([previous part](2026-09-30-leafcutter-kernel-spec-rev3-4-scheduler-jev-capabilities.md) | [next part](2026-09-30-leafcutter-kernel-spec-rev3-6-gaps-build-verification.md)). Split only to satisfy the 300-line doc limit.

## 11. Claude Code client and LLM handoff [MVP]

### 11.1 Choose a real invocation mechanism

Use a project skill at:

```text
.claude/skills/leafcutter/SKILL.md
```

Expose it as `/leafcutter`. Claude Code skills support slash invocation and accompanying scripts; a slash command by itself does not create an automatic Python-to-Claude callback. See [C1](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#c1-claude-code-skills).

Therefore, the MVP uses a **cooperative, checkpointed host handoff**:

```text
Claude Code invokes Leafcutter CLI
    |
Leafcutter performs native work
    |
Leafcutter persists pending host work or a human question
    |
CLI returns a structured RunEnvelope and exits normally
    |
Claude performs exactly the requested host work,
or presents the question to the human
    |
Claude submits a structured response through resume
    |
Leafcutter validates it and continues its own workflow
```

Do not recursively launch unrestricted Claude Code sessions. Do not assume a shell process can inject a new instruction into its already-running parent conversation.

### 11.2 Proposed CLI contract

Implement these commands, or map them onto an existing compatible Leafcutter CLI. These are commands to build, not claims about commands already present in the repository.

```bash
leafcutter run --input task-input.json --json
leafcutter resume --run-id RUN_ID --response response.json --json
leafcutter status --run-id RUN_ID --json
leafcutter cancel --run-id RUN_ID --json
```

Prefer JSON files or JSON on stdin for request content. Never interpolate free-form goals into an executable shell command. Keep output artifacts within the run's approved directory and prevent arbitrary path traversal.

Stdout contains machine-readable JSON. Diagnostic logs go to stderr. A valid `waiting_host`, `waiting_human`, or `blocked` envelope is not a process crash. Document exit codes so the client can distinguish protocol failures from normal workflow states.

### 11.3 Host-work packet example

Illustrative complete packet shape; IDs and locators are fixtures:

```json
{
  "schema_version": "1.0",
  "run_id": "run-demo-001",
  "state_revision": 7,
  "status": "waiting_host",
  "interaction": {
    "id": "interaction-demo-003",
    "kind": "host_work",
    "work_item_id": "work-demo-004",
    "invocation_id": "invocation-demo-008",
    "operation": "synthesize_evidence",
    "goal": "Extract decision criteria and unresolved conflicts from the supplied evidence.",
    "input_artifact_refs": ["artifact:evidence-bundle-demo-002"],
    "output_schema_id": "leafcutter.findings.v1",
    "allowed_operations": ["read_supplied_artifacts", "synthesize"],
    "forbidden_operations": ["edit_repository", "approve_policy", "change_permissions"],
    "trace_context": {
      "root_task_id": "task-demo-001",
      "correlation_id": "correlation-demo-001"
    }
  }
}
```

The host receives only the artifacts and tools relevant to that operation. A code research handoff may receive an approved source scope; a synthesis handoff should not need unrestricted browsing.

### 11.4 Minimal skill behavior

The skill contains **transport instructions, not the engineering methodology**:

```markdown
---
name: leafcutter
description: Run Leafcutter's decision and research workflow for a supplied goal.
argument-hint: [goal]
disable-model-invocation: true
---

Serialize the user's goal into the documented Leafcutter TaskInput format.
Start the Leafcutter run using the local CLI.

Inspect the returned RunEnvelope:
- waiting_host: perform only the specified operation with the allowed context;
  save the schema-conforming response and resume the run.
- waiting_human: present the pending question; wait for the user's answer,
  then submit that answer for the same interaction ID.
- completed, partial, blocked, failed, or cancelled: present the result faithfully.

Do not independently choose the next capability, change policies,
mark unresolved decisions as complete, or approve on the user's behalf.
Preserve run IDs, interaction IDs, state revisions, and evidence references.
```

This is a skeleton to adapt to the implemented CLI and schemas, not a substitute for implementing them.

### 11.5 Limits of the bootstrap host

The kernel validates submissions and owns the next transition. Nevertheless, skill instructions alone do not isolate Claude Code from its broader context or enforce filesystem/network permissions. Do not describe a skill's instruction list as a security sandbox.

Use existing host permission controls and read-oriented operations for the MVP. Record host execution as host-reported unless independently verified. A direct, isolated SDK executor is a later-stage improvement, not something the MVP should pretend to provide.

### 11.6 Human questions and approval

Ask humans only for information that cannot reasonably be obtained from evidence: product intent, preferences, unknown requirements, or required approval.

The question should explain what is missing, why it matters, available alternatives and consequences, and whether free-text answers are accepted. Claude may formulate the wording, but the pending interaction is created by Leafcutter.

No answer is inferred from silence. Cancelled, rejected, expired, or superseded interactions cannot resume a run. A user selecting an option does not authorize unrelated repository edits or external actions.

### 11.7 Authentication, billing, and observability limits

Claude Code uses its existing host authentication for host operations. Jev and Langfuse require their own configured credentials. Do not assume a Claude Code subscription supplies unrestricted API credentials for future SDK calls.

Record exact submitted prompts/work packets, returned results, elapsed time, visible execution metadata, and any available model/usage data. Unknown host billing or token counts must stay unavailable, not be inferred as zero or exact totals.

## 12. Langfuse from the beginning [MVP]

### 12.1 Runtime instrumentation

Use the Langfuse LangChain integration for LangGraph callbacks and add custom observations around deterministic decisions, source calls, and host handoffs. The documented callback import is `from langfuse.langchain import CallbackHandler`; match the SDK version installed in the project. See [L1](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#l1-langchain-and-langgraph-instrumentation) and [L2](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#l2-langgraph-cookbook).

At minimum record:

- Root task, run ID, work item, invocation, and parent/causation IDs.
- Registry snapshot and candidates considered; deterministic exclusions and route outcome.
- Jev model ID, package/adapter version, question template version, input fingerprint, raw response/distributions, confidence, and thresholds used.
- Source requests and evidence IDs, exact version/locator when available, inaccessible sources, and truncation.
- Decision criteria, evidence references, changes in assessment, and approval provenance.
- Capability invocation inputs/outputs, child requests, continuations, and fallback reliance.
- Human/host interruptions and resume events.
- Durations, reported tokens, known or estimated costs with provenance, retry/budget/cycle events, and final status.

Automatic callbacks may classify a Jev invocation as an LLM-like observation. Ensure the typed decision outputs and provider usage are still visible through metadata or custom observations. Do not depend on a provider-specific dashboard feature to retain the record.

### 12.2 Trace continuity across process restarts

Create stable application-level run/correlation IDs and persist the necessary trace context. Resume must not sever the causal chain merely because a new CLI process or callback instance was created.

Prefer one correlated trace for a logical run where supported by the configured SDK. If a host boundary requires linked traces, preserve explicit parent/correlation metadata and expose all trace references in the run report. Do not claim a single automatic trace across external host activity without verifying it.

The durable local event/run record is authoritative for workflow state. Langfuse is observability, not the checkpointer or decision database.

### 12.3 MCP inspection is not tracing transport

Document and configure the **authenticated Langfuse data MCP** for inspection. Distinguish it from the public documentation MCP. The data MCP exposes project data and may expose write tools; restrict the client to the read-only tools needed for the demo. See [L3](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#l3-langfuse-data-mcp).

A working MCP connection does not instrument application execution. The SDK/callback path must still export observations.

MVP verification includes retrieving a demonstration run's trace through the configured inspection path. Use current documented tool names rather than inventing an MCP API. If account configuration prevents the smoke test, report that as a remaining setup blocker instead of marking the integration verified.

### 12.4 Redaction and observability failure

Persist decisions and pending interactions before handing work externally. Redact credentials and restricted content before telemetry export, and honor the configured region and retention policy.

Telemetry failure must not erase runtime state. Reuse an existing durable retry/spool facility if present; otherwise persist enough local events to diagnose missing exports and report `observability_degraded`. Do not introduce a separate distributed telemetry platform for the MVP.

Flush supported SDK exporters before a short-lived CLI exits. The delivery must include at least one genuinely visible trace; mock-only instrumentation is not proof of live integration.

## 13. Persistence, safeguards, and failure semantics [MVP]

### 13.1 Durable state and replay

Reuse Leafcutter's persistence if compatible. Otherwise choose the smallest durable LangGraph checkpointer appropriate to local MVP use. A specific graph database is not required. LangGraph persistence and interrupt behavior are documented in [G3](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#g3-persistence-and-checkpoints) and [G4](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md#g4-interrupts-and-resume).

Interrupted nodes may execute again on resume. Keep work before an interrupt side-effect-free or explicitly idempotent. Do not replay completed model calls, external writes, or accepted human answers simply because a parent node restarts.

Use stable invocation IDs, persisted results, explicit continuation state, and an idempotent resume boundary. Test a restart immediately before and after an accepted submission.

### 13.2 Proposed conservative development limits

These are initial configurable engineering limits, not empirically optimal values:

| Limit | Initial proposal |
|---|---:|
| Work items per root task | 32 |
| Work dependency depth | 4 |
| Concurrent native work items | 4 |
| Concurrent cooperative host interactions | 1 |
| Retries after an initial invocation | 2, only for retryable errors |
| Consecutive no-progress evaluations | 2 |
| Jev calls per root task | 40 |
| Host generation operations per root task | 8 |
| Active execution time | 5 minutes; human waiting tracked separately |

Configure per-call timeouts and payload/context limits against the pinned integrations. Record an explicit monetary cap when reliable billing data is available. Call and token caps must still apply when host cost is unknown.

Routing and semantic decision thresholds belong in configuration and trace records. Any initial threshold—such as `0.90`—is an uncalibrated starting policy, not a correctness claim.

### 13.3 Security and trust

Allowlist executor bindings and source roots. Protect against path traversal, shell interpolation, untrusted import paths, source-driven instruction injection, and unsafe deserialization.

Do not send repository secrets or restricted content to Jev, Claude, or Langfuse unless the configured data policy permits that transfer. Read-only does not mean privacy-neutral: retrieval itself may export source text.

Model output cannot:

```text
expand permissions
remove mandatory gates
rewrite active policies
approve its own proposed ADR
register or execute a new capability
impersonate a human answer
change the declared scope of the run
```

The cooperative Claude Code host cannot provide a complete adversarial isolation guarantee. State that limitation explicitly and keep MVP operations low-risk.

### 13.4 Failure handling

| Condition | Required outcome |
|---|---|
| Jev timeout/rate limit/service failure | Bounded retry; then explicit provider failure or configured fallback, never a capability-gap claim |
| Invalid provider or host result | Schema/ID validation error; no state corruption; bounded repair only when allowed |
| Missing evidence or unknown options | Typed research/options request, not an exception |
| Incompatible schema/version | Explicit compatibility blocker |
| Source inaccessible | Evidence bundle records unavailable source and resulting limitation |
| No suitable capability | Deduplicated gap plus approved fallback or blocker |
| Suitable capability forbidden | Permission outcome; do not evade through generic host work |
| Mandatory child failed | Parent explicitly blocked or partial, not complete |
| Budget/no-progress guard | Partial or blocked result with unresolved work and trace references |
| Cancellation | Persist cancelled state, signal running work where possible, reject later stale resumes |
| Langfuse unavailable | Preserve local state, report degraded observability, retry export according to configured policy |
