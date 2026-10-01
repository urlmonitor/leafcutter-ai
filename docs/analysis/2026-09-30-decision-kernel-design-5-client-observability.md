---
title: "Decision Kernel V0 Design - Part 5 of 6: Client and Observability"
description: "The client-independent application service (start, resume, get, cancel), the CLI JSON protocol with RunEnvelope and exit codes, the thin Claude Code skill and how it is installed without shipping to adopters, Langfuse v4 integration with trace continuity across process restarts and correlation IDs, redaction, degraded observability, and the Langfuse data MCP inspection setup."
type: explanation
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

# Decision Kernel V0 Design — Part 5 of 6: Client and observability

Spec: §5.1, §11, §12 ([spec part 2](2026-09-30-leafcutter-kernel-spec-rev3-2-runtime-and-registry.md),
[spec part 5](2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md)).
Back to [part 1](2026-09-30-decision-kernel-design.md).

## Application service (`service.py`: P1 protocol, P7 implementation)

```python
class RunService(Protocol):
    async def start_run(self, task_input: TaskInput, *, run_id: str | None = None) -> RunEnvelope: ...
    async def resume_run(self, run_id: str, submission: InteractionSubmission) -> RunEnvelope: ...
    async def get_run(self, run_id: str) -> RunEnvelope: ...
    async def cancel_run(self, run_id: str, actor: Actor) -> RunEnvelope: ...
```

- **Client independence.** The service is the only API that clients call: the CLI, tests, a future MCP tool, or other Python code. Nothing in `kernel/`, `capabilities/` or `providers/` imports `adapters/`.
- **`KernelService`** (P7) opens a `KernelRuntime` per call as an async context manager. The runtime owns the aiosqlite connection, the Jev adapter, the tracer and the stores, and `__aexit__` flushes the tracer.
- **Graph invocation.** Each call invokes the compiled graph with `thread_id=run_id` and builds the envelope from `aget_state` plus `run.json`.
- **Errors:**
  - `InvalidTaskInput`
  - `RunNotFound`
  - `SubmissionRejected(code, message, details)`, where `code` is one of `stale_revision`, `not_pending` (a conflicting duplicate carries `details.reason=conflicting_duplicate`), `wrong_kind`, `actor_mismatch`, `schema_invalid`, `semantic_invalid`, `forged_id` or `cancelled_or_superseded`
  - `ProviderUnavailable`
- **Composition root.** `bootstrap.py` (P7) builds the trusted `BindingTable`. It is the only place where binding keys map to Python classes:
  - `decision`: `DecisionCapability`
  - `research`: `ResearchCapability`
  - `retrieve.repository`: `RepositoryRetrieval`
  - `host.*`: the host-handoff marker executor

## CLI (`adapters/cli.py`, `adapters/envelope.py`, P7)

The spec's `leafcutter …` command is `python -m kernel …` here: the repo has no
`pyproject.toml`. Request content always travels as JSON files or on stdin (`-`). A free-form
goal is never interpolated into a shell command (§11.2).

```bash
python -m kernel run     --input task-input.json --json [--config F] [--env-file F]
python -m kernel resume  --run-id RUN --response response.json --json
python -m kernel status  --run-id RUN --json
python -m kernel cancel  --run-id RUN --actor human:<id> --json
python -m kernel install-skill --target-dir <dir>/.claude/skills --name <name> [--force]
python -m kernel gaps    --json          # aggregated gap view (P9)
```

- stdout carries exactly one JSON document; logs go to stderr.
- The run directory is resolved from config. User-supplied paths are read, never written, except `install-skill --target-dir`.

| Exit | Meaning | stdout |
|---|---|---|
| 0 | An envelope was produced. `waiting_human`, `waiting_host`, `blocked`, `failed`, `partial` and `cancelled` are normal workflow states, not crashes. | `RunEnvelope` |
| 2 | CLI usage error (argparse) | nothing (argparse writes to stderr) |
| 3 | Input or submission rejected; state is unchanged | `{"error": {code, message, details}, "envelope": <current envelope or null>}` |
| 4 | Unknown run id | `{"error": {"code": "run_not_found", …}}` |
| 5 | Internal error; the traceback goes to stderr | `{"error": {"code": "internal", "message": …}}` |

The envelope matches spec §7.9 and §11.3. `pending_interaction` holds the full `HostWorkRequest`
or `HumanQuestion`, including `interaction.id`, `state_revision`, `output_schema_id`, the inline
`output_json_schema`, `input_artifact_refs` (absolute paths inside `runs/<run_id>/artifacts/`),
`allowed_operations` and `forbidden_operations`.

## Claude Code skill (P7)

- **Source.** `kernel/adapters/claude_code/SKILL.md` is tracked in-package and never under `templates/`, so it is never shipped.
- **Install location.** In this repo `.claude/skills/` is gitignored build output. The user's Claude Code session runs from the **workspace root** (`C:\Users\Hendrik\Code\leafcutter`), whose `.claude/skills/` build.py manages. It keeps unknown directories and warns about them.
- **Install command.** `install-skill` renders the template, substituting the absolute repo root and the Python executable, and writes `<target-dir>/<name>/SKILL.md`. It refuses to overwrite a directory whose `SKILL.md` lacks the marker `<!-- leafcutter-kernel-skill -->` unless `--force` is given. Running it writes outside the repo, so **the user runs it once, or approves it**.
- **Name: open user decision.** `/leafcutter` already exists as the shipped knowledge-hub command (`templates/workflows/leafcutter.md` → `.claude/commands/leafcutter.md`). Claude Code documents neither which one wins nor a warning when a skill and a legacy command share a name. Options:
  - (a) Rename the hub command (a shipped change needing its own ticket), then install the skill as `leafcutter`, as the spec says.
  - (b) Install as `leafcutter` and let P7 verify precedence empirically in a real session.
  - (c) Use another name such as `leafcutter-run`.
- **Skill frontmatter:** `name`, `description`, `argument-hint: [goal]`, `disable-model-invocation: true`, and `allowed-tools: Bash(PYTHONPATH=<repo> <python> -m kernel:*), Read, Write, AskUserQuestion`.
- **Skill body** (transport only, per §11.4):

1. Write `$ARGUMENTS` verbatim as `goal` into a TaskInput JSON file in the session scratch directory, with `caller={"id":"user","kind":"human"}` and `scope.repository_root=<repo>`. Run `PYTHONPATH=<repo> <python> -m kernel run --input <file> --json`.
2. `waiting_human`:
   - Present `question`, `choices` and their consequences with AskUserQuestion, allowing free text only if `free_text_allowed`.
   - Write a `leafcutter.human_answer.v1` submission with `actor={"kind":"human","id":"user"}` and `relayed_by="claude_code"`, echoing `interaction_id` and `state_revision`.
   - Run `resume`.
3. `waiting_host`:
   - Perform **only** `operation`.
   - Read only the listed artifacts and evidence, use only `allowed_operations`, and never do anything in `forbidden_operations`.
   - Write JSON that conforms to `output_json_schema` as a submission with `actor={"kind":"host","id":"claude_code"}`.
   - Run `resume`. On exit 3, repair once, using `error.details`.
4. A terminal status: present `report_ref` (Markdown) faithfully, together with the evidence locators, limitations, gaps and the trace URL.
5. Never choose the next capability, edit repository files, approve anything, mark unresolved work complete, or answer on the user's behalf.

## Langfuse integration (`observability/`, P2; Tracer protocol in P1)

```python
class Tracer(Protocol):
    def open_segment(self, run_id: str, root_task_id: str, kind: str) -> TraceState  # start|resume|status|cancel
    def span(self, name: str, kind: str, corr: CorrelationIds, *, input=None, metadata=None) -> ContextManager[SpanHandle]
    def generation(self, name: str, corr: CorrelationIds, *, model: str, input, output, usage: Usage, metadata) -> None
    def event(self, name: str, corr: CorrelationIds, *, level: str, payload: dict) -> None
    def langchain_callbacks(self, corr: CorrelationIds) -> list
    def close_segment(self) -> ObservabilityStatus                                   # flush; ok|degraded
```

`NoOpTracer` and `RecordingTracer` (P1) are the test doubles. `RecordingTracer` stores every
call, so tests can assert names, correlation IDs and nesting.

**`LangfuseTracer`** (P2) uses the verified v4.16 API:

- **Client construction.**
  - `Langfuse(public_key, secret_key, base_url, environment, release=__version__, mask=redactor.mask, tracing_enabled=…)`.
  - Tests pass an OpenTelemetry `InMemorySpanExporter` as `span_exporter`. This checks real SDK spans offline.
- **Trace identity and continuity (§12.2).**
  - `trace_id = Langfuse.create_trace_id(seed=run_id)`, which is deterministic, and is also persisted in state and `run.json`.
  - Each CLI process opens a segment root: `start_observation(trace_context={"trace_id": trace_id}, name="leafcutter.run" or "leafcutter.run.resume", as_type="agent")`.
  - `propagate_attributes(session_id=run_id, trace_name=cfg.trace_name, metadata={run_id, root_task_id}, tags=["leafcutter-kernel"])` runs inside it.
  - Every restart therefore appends to the same trace (verified live).
- **Explicit parents.** Node, capability and Jev observations are created from explicit parent handles (`segment.start_observation(...)`) and never from implicit OpenTelemetry context. `Send` workers run as concurrent tasks.
- **Automatic callbacks (§12.1).** `CallbackHandler(public_key=…, trace_context={"trace_id": …, "parent_span_id": segment_id})` goes into the graph config and into each Jev runnable config. The live smoke test recorded the Jev call as a `CHAIN` with no usage, so the adapter **also** emits a `generation` with `model=model_id`, `usage_details`, `cost_details` (provenance `estimated`), template ids, the input fingerprint, raw distributions, confidence and thresholds.
- **Observation map:**
  - `kernel.<node>`: chain
  - `capability.<id>`: agent for native graphs, tool for the retrieval adapter
  - `retrieval.<source>`: retriever
  - `jev.<purpose>`: generation
  - events: `routing.assessed`, `decision.status`, `guard.tripped`, `interaction.opened` / `submission.accepted` / `submission.rejected`, `gap.recorded`, `run.finalized`
- **Correlation IDs.** Every observation's metadata carries the non-null `CorrelationIds`: `run_id`, `root_task_id`, `task_id`, `work_item_id`, `request_id`, `invocation_id`, `decision_id`, `capability_id`, `interaction_id`, `parent_work_item_id` and `causation_seq`. Evidence is referenced by id and locator, never by full payload.
- **Colony-memory recording prerequisites (recommended by [ADR-056 §9](../architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md); a V0 decision, not yet V0 scope).** Traces recorded without these fields can never be counted retroactively: (1) policy, template and model version fields next to `CorrelationIds`; (2) an outcome event that references an earlier `decision_id`, across runs if needed (name and schema left to the build); (3) gap records that stay countable. The roadmap's founding exit criterion asks that each item is implemented or explicitly deferred by a recorded decision.
- **Degraded mode (§12.4).**
  - Triggers: missing keys, a failed `auth_check()` at segment open, or any SDK exception (caught and logged at WARNING).
  - Effect: the tracer writes observation records to `telemetry_spool.jsonl`, and the envelope reports `trace_refs.observability="degraded"`.
  - V0 keeps the spool for diagnosis and does not re-export it. That is a documented limitation.
- **Flush.** `close_segment()` calls `flush()` and then `shutdown()` in the CLI's `finally`.
- **Read-back.** The trace URL comes from `get_trace_url(trace_id=…)`. Live read-back uses `api.observations.get_many(trace_id=…)`. The legacy trace GET returns 410 for this organisation.

## Redaction (`observability/redaction.py`, P2)

`Redactor(secrets, cfg).mask(data)` walks dicts, lists and strings:

1. Exact loaded secret values become `[REDACTED:<name>]`.
2. The security-scanner rules are applied. `_RULES` is loaded by path from `templates/skills/security-scanner/scripts/scan_secrets.py`, with the same four regexes vendored as a fallback.
3. Tokens of 20+ characters with Shannon entropy above 4.5 become `[REDACTED:entropy]`.
4. Excerpts follow `data_policy.telemetry_excerpts`, and fields are truncated to `telemetry_max_field_chars`.

Where it applies:

- Langfuse `mask=`, which also covers callback observations.
- Jev state and host packets, before they are sent (§13.3).

It never touches persisted evidence, which stays exact for provenance.

## Langfuse data MCP inspection (§12.3; documented in P10, configured by the user)

P10 writes `docs/how-to/inspect-kernel-traces-with-langfuse-mcp.md` from the current L3 page.

- **Which MCP.** The authenticated **data** MCP, scoped to the project keys. It is not the public documentation MCP.
- **Tools.** Restrict the client to read-only tools, and use the tool names from the current docs.
- **Smoke test.** Fetch the demonstration run's observations by `trace_id`.
- **User step.** Adding the MCP server means `claude mcp add …` or editing `.mcp.json`, with credentials. The **user** must do it, or approve it. Agents do not edit Claude Code settings or MCP config.
- **Setup blocker.** If account configuration blocks the smoke test, report it as a setup blocker. Never mark it verified.

## As built (P6)

- **Resume entry point.** `kernel.interaction.submit_interaction(graph, config, runtime, run_store, run_id, raw)` is what `resume_run` calls. It checks cancellation, looks up the submission ledger (same hash: replay, or finish an interrupted resume; other hash: `not_pending` with `details.reason=conflicting_duplicate`), validates with `check_submission`, writes the ledger entry and only then resumes with `Command(resume=...)`. It returns `SubmitResult(status, state, pending)` or raises `SubmissionRejected`.
- **Repair.** Invalid host output (`schema_invalid`, `semantic_invalid`) is the only rejection that reaches the graph; `await_interaction` counts it against `host.max_repair_attempts` and then fails the item with `host_output_invalid`.
- **Rejection fork fix.** A rejected submission used to return `Command(goto="await_interaction")`, which left the static edge to `integrate` active and ran two branches. `await_interaction` now loops inside the node with repeated `interrupt()` calls; LangGraph replays earlier resume values, so the repair count survives a restart.
- **`current_wait` scoping.** A resumed parent still receives every finished child, but `ChildOutcome.current_wait` marks the children of its latest wait (`Continuation.wait_child_ids`). Decision applies only current human answers; `ChildOutcome.actor_id` attributes approvals to the answering actor.
- **Events.** `interaction.opened` and `submission.accepted` are traced by the nodes; `submission.rejected` (with the code) is traced by `submit_interaction`, because the node replays earlier rejections.
- **Resolved in P7.** `state["trace"]` was not refreshed on resume, so invocation and packet `trace_context` parent ids still pointed at the start segment (bug D); see below.

## As built (P7)

- **Modules.** `service.py` (protocol and `KernelService`), `service_session.py` (one process segment), `service_envelope.py` (pure envelope mapping), `service_errors.py`, `bootstrap.py` (composition root), `adapters/cli.py`, `adapters/cli_io.py`, `adapters/claude_code/{SKILL.md,install.py}`, `__main__.py`. `SubmissionRejected` is P6's class (stable `RejectionCode`s); the P1 `RejectCode` list is gone.
- **One segment per call.** Each service call runs in `open_session`: `open_segment(kind)`, the checkpointer (`extra_types=[*ALL_MODELS, *STATE_MODELS]`, `thread_id` = run id), the Jev adapter (built in the running loop, only for start and resume, `aclose()`d in the same loop), then `close_segment()`. `shutdown()` runs once per process from the environment. Telemetry failures degrade (`trace_refs.observability`) and never break a run.
- **Bug D.** `KernelRuntime.trace` carries the current segment's `TraceState`; `build_invocation` prefers it over `state["trace"]`, so invocations and host packets created after a resume nest under the resuming segment. Verified live: a packet created after the second resume named that resume's segment, not the start segment.
- **run.json is the service's.** It creates the `RunRecord` (root task `pending`) before the first graph call, then sets status, `state_revision`, root task and the latest `TraceState` after each call. A cancellation flag wins over any graph status; a terminal record status (recursion limit) wins over a non-terminal graph status. After `ainvoke` the service calls `flush_events` once more, because `run.finished` cannot flush itself.
- **Failures.** `GraphRecursionError` is mapped to `blocked` with a `guard: langgraph_recursion_limit` limitation; the checkpoint is untouched. A rejected submission leaves state unchanged and the exception carries the current `envelope`. A changed registry refuses to continue a pinned, unfinished run (`registry_changed`, exit 5). No Jev credential fails `run` and `resume` before any state is written (`provider_unavailable`, exit 5); `status` and `cancel` need none.
- **Envelope `report_ref`** is the absolute path of `report.md` (else `report.json`), so a client opens it without knowing the run layout.
- **CLI flags.** `--input-file` (aliases `--input`, `--response`, `--response-file`; `-` or no flag reads stdin), `--config`, `--env-file`, `--json` (accepted; output is always JSON). The run root comes from config (`paths.run_root`, or `LEAFCUTTER_KERNEL_CONFIG`). Exit codes are as in the table, plus `provider_unavailable`, `registry_changed`, `config_invalid` and `registry_invalid` under exit 5, and `invalid_run_id`, `invalid_actor` and input errors under exit 3. While a command runs, `sys.stdout` points at stderr so a library cannot break the one-document contract.
- **Bindings.** `native`: `decision`, `research`, `retrieve.repository` at 1.0.0. Every `host_handoff` descriptor in the registry gets a `HostMarkerExecutor` placeholder (eligibility only; P8 replaces it with host operations).
- **Skill.** `install-skill --target-dir <dir>/.claude/skills --name <name> [--force]` writes `<dir>/<name>/SKILL.md` only (atomic), refuses a directory whose SKILL.md lacks `<!-- leafcutter-kernel-skill -->` unless `--force`, and rejects any name that is not `[a-z0-9][a-z0-9-]*`.

## As built (P9 and integration)

- **`gaps` command.** `python -m kernel gaps` prints the aggregated gaps (one row per dedup key, `occurrence_count`, `example_run_ids`) with a `build_opportunity` flag (only `unsupported` and `host_only` gaps are build opportunities) and the totals `total`, `build_opportunities` and `occurrences`.
- **Cancel.** `cancel_run` commits to `run.json` with `compare_and_update`, appends `run.cancelled` and closes a paused graph thread. Service events are numbered from `SERVICE_SEQ_BASE` (1e9), a range graph events (numbered from 0 by the reducer) cannot reach, so the two writers never collide.

## As built (intake intent)

- **Envelope.** `usage_summary.input_tokens` / `output_tokens` are the sums of the counts the providers reported (`Budgets.input_tokens/output_tokens`, null until one is known, never 0) and `usage` holds one aggregate `jev` entry. `gaps` shows the gap store's aggregate per gap key (original `first_seen`, summed occurrences) instead of the in-run observation.
- **Report.** `report.md` explains blocked and partial stops in plain words, names what the kernel can do (decide between options, find evidence in this repository, generate ideas) with a rephrasing example, and renders evidence bundles (findings, sources) and idea sets (under "proposals, not decisions") before the unchanged JSON block. A blocked run with no plain limitation gets a `can_do` limitation line.
- **Gap records.** `CapabilityGap.candidate_exclusions` maps each considered capability to its exclusion reason; `candidates_considered` is ranked (eligible first, then the closest reason) and capped at five; `need_title` is the readable goal used for titles while `normalized_need` stays the dedup identity.
- **Skill.** `/leafcutter` no longer sets `requested_output_schema` unless the user explicitly asks for a decision, an evidence lookup or ideas.
