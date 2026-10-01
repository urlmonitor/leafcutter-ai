---
title: "How to inspect kernel traces with the Langfuse MCP server"
description: "Connect your MCP client to Langfuse's authenticated data MCP server, restrict it to read-only tools and read a decision-kernel run's observations (segments, Jev generations, key events) by trace id."
type: how-to
status: active
created: 2026-10-01
last_updated: 2026-10-01
components:
  - decision_kernel
related_docs:
  - docs/how-to/run-the-decision-kernel.md
  - docs/analysis/2026-09-30-decision-kernel-design-5-client-observability.md
  - docs/analysis/2026-10-01-decision-kernel-v0-demo-report.md
related_code:
  - kernel/observability/langfuse_tracer.py
  - kernel/observability/correlation.py
  - tests/kernel/live/live_support.py
---

# How to inspect kernel traces with the Langfuse MCP server

Langfuse ships an authenticated MCP server for your project's data. Connected read-only, it lets
an AI client answer questions about a kernel run (what was routed, which Jev calls ran, what the
decision saw) without leaving the editor.

This is a **read path only**. The kernel exports traces through the Langfuse SDK
(OpenTelemetry), never through MCP, and the MCP server is not a tracing transport. Do not point
the kernel at it. The steps below are for you to perform: nothing in this repository configures
MCP or edits Claude Code settings.

Sources: the [Langfuse MCP server page](https://langfuse.com/docs/api-and-data-platform/features/mcp-server)
and the generated [MCP reference](https://mcp.reference.langfuse.com), which lists the current
tools and schemas. The reference says clients should discover tools dynamically, so treat the
tool names below as a snapshot of 2026-10-01.

## Prerequisites

- A Langfuse project that receives the kernel's traces (the keys in your `.env`, see
  [How to run the decision kernel](run-the-decision-kernel.md)).
- A project-scoped API key pair (`pk-lf-...`, `sk-lf-...`). A key can read and write, so the
  read-only restriction in Step 3 is enforced by your client, not by Langfuse.
- Langfuse v4 observation APIs. `listObservations` and its sibling tools are marked
  "Requires v4" in the reference.
- Claude Code, or another client that supports streamable-HTTP MCP servers.

## Steps

### Step 1 — Build the Basic-auth token

The server uses Basic auth over HTTPS. Encode `public:secret` without typing the keys into a
shared shell history; this reads them from environment variables you already loaded:

```bash
printf '%s:%s' "$LANGFUSE_PUBLIC_KEY" "$LANGFUSE_SECRET_KEY" | base64
```

On PowerShell:

```powershell
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("${env:LANGFUSE_PUBLIC_KEY}:${env:LANGFUSE_SECRET_KEY}"))
```

### Step 2 — Register the server in your user-private Claude Code scope

The endpoint for Langfuse Cloud EU is `https://cloud.langfuse.com/api/public/mcp` (US:
`us.cloud.langfuse.com`; Japan: `jp.cloud.langfuse.com`; self-hosted: your domain over HTTPS).
Use the default `local` scope, or `--scope user`, so the header lands in your private
`~/.claude.json`. **Never use `--scope project`**: it writes `.mcp.json`, which is committed to
git.

```bash
claude mcp add --transport http langfuse https://cloud.langfuse.com/api/public/mcp \
  --header "Authorization: Basic <your-base64-token>"
```

Claude Code names this server's tools `mcp__langfuse__<toolName>`.

### Step 3 — Restrict the client to read-only tools

Both read and write tools are available by default (the reference lists 86 tools: prompts,
datasets, evaluators, dashboards and more). Allow only the observation and score readers and deny
every write family. Per the Claude Code permission docs, allow-rule globs are accepted only after
the literal `mcp__langfuse__` prefix, partial globs work, and **deny overrides allow**. Put this
in your own `~/.claude/settings.json` (or `.claude/settings.local.json`):

```json
{
  "permissions": {
    "allow": [
      "mcp__langfuse__listObservations",
      "mcp__langfuse__getObservation",
      "mcp__langfuse__getObservationFieldSchema",
      "mcp__langfuse__getObservationFilterSchema",
      "mcp__langfuse__getObservationFilterValues",
      "mcp__langfuse__queryMetrics",
      "mcp__langfuse__getMetricsSchema",
      "mcp__langfuse__listScores",
      "mcp__langfuse__getScore",
      "mcp__langfuse__listComments",
      "mcp__langfuse__getComment",
      "mcp__langfuse__getHealth"
    ],
    "deny": [
      "mcp__langfuse__create*",
      "mcp__langfuse__update*",
      "mcp__langfuse__delete*",
      "mcp__langfuse__upsert*",
      "mcp__langfuse__batchUpsert*",
      "mcp__langfuse__add*",
      "mcp__langfuse__attach*",
      "mcp__langfuse__detach*",
      "mcp__langfuse__test*",
      "mcp__langfuse__submitFeedback"
    ]
  }
}
```

Re-check the tool list in the reference when you upgrade: a new write tool whose name matches no
deny pattern would still prompt (it is not in the allow list), but would not be blocked.

### Step 4 — Know that traces are read as observations

The MCP server has no `getTrace` or `listTraces` tool. Traces are read as their observations:
call `listObservations` with `traceId`. The legacy get-trace REST endpoint returns **410** for
this organisation, so do not fall back to it; the kernel's own live tests use the observations
API (`api.observations.get_many`) for the same reason.

### Step 5 — Find the trace id of a run

Every run envelope carries `trace_refs.trace_id` and `trace_refs.trace_url`; `run.json` keeps the
same values. The id is deterministic: the first 16 bytes of `sha256(run_id)` as 32 hex characters,
so every process segment of one run lands in the same trace.

```bash
python -m kernel status --run-id <run_id> --json
```

### Step 6 — Ask for the observations

Ask your client for the observations of the trace. It should call `listObservations` with
`traceId` and compact fields; request `input`, `output` or `metadata` only with `traceId` (or an
id filter, or a date range of at most 14 days). Metadata values are cut at 200 characters unless
you name the keys in `expandMetadataKeys`.

```json
{
  "traceId": "<trace_refs.trace_id>",
  "fields": ["id", "name", "type", "startTime", "parentObservationId", "level"],
  "limit": 100
}
```

What to expect in a kernel trace:

- One `AGENT` segment per CLI call: `leafcutter.run` (start), then `leafcutter.run.resume`,
  `leafcutter.run.status`, `leafcutter.run.cancel`. Every observation is nested under the segment
  of the process that created it.
- `GENERATION` observations named `jev.<purpose>` (for example `jev.decision.assess`) with
  `usageDetails` (input, output, total tokens), a cost and the Jev model id.
- `CHAIN` spans for the scheduler nodes (`kernel.intake`, `kernel.route`, `kernel.schedule`,
  `kernel.integrate`, `kernel.finalize`), `AGENT` spans `capability.<id>`, `RETRIEVER` spans for
  repository retrieval.
- `EVENT` observations for the key moments: `routing.assessed`, `interaction.opened`,
  `submission.accepted`, `host.<operation>`, `decision.combine`, `decision.status`,
  `gap.recorded` and `run.finalized`.
- Correlation ids in metadata (`run_id`, `work_item_id`, `invocation_id`, `capability_id`,
  `decision_id`, `interaction_id`; null ones are omitted), so you can filter by capability or
  work item with `getObservationFilterValues`.

## Verification

Ask your client: "List the observations of Langfuse trace `<trace_id>` and count the generations
that report token usage." The client should call `listObservations` (not a write tool) and report
that every `GENERATION` has `usageDetails`.

Expected output: a non-empty list whose names include `leafcutter.run`, at least one
`jev.*` generation, and (for a finished run) a `run.finalized` event. A request to create a
prompt or a dataset must be refused by the deny rules.

## Troubleshooting

1. **Empty result right after a run.** Ingestion is asynchronous. Wait one to two minutes and
   ask again; `trace_refs.observability: ok` means the kernel flushed.
2. **401 Unauthorized.** The key pair belongs to another project, or the base64 token was built
   from stale keys. Rebuild it (Step 1) and re-register (remove with `claude mcp remove langfuse`).
3. **403 on a self-hosted server behind a proxy.** Preserve the public `Host` header, or set
   `LANGFUSE_MCP_ALLOWED_HOSTS` on the server (see the Langfuse page).
4. **"Requires v4" or an unknown-tool error.** The project does not have the v4 observation APIs
   enabled. Use the Langfuse UI with the `trace_url` from the envelope meanwhile.
5. **Truncated metadata.** Pass `expandMetadataKeys` with the keys you need in full.

## See Also

- [How to run the decision kernel](run-the-decision-kernel.md)
- [Client and observability design](../analysis/2026-09-30-decision-kernel-design-5-client-observability.md)
- [V0 demo and run report](../analysis/2026-10-01-decision-kernel-v0-demo-report.md)
- [Documentation Index](../INDEX.md)
