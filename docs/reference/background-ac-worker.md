---
title: "Background AC worker reference"
description: "CLI, configuration, evidence and execution limitations for the background AC worker."
type: reference
status: active
created: 2026-09-24
last_updated: 2026-09-24
components:
  - ac_driven_dev
related_code:
  - scripts/background_worker_cli.py
  - scripts/background_worker/engine.py
  - scripts/background_worker/store.py
related_docs:
  - docs/architecture/components/ac-driven-dev.md
  - docs/how-to/background-ac-worker.md
---

# Background AC worker reference

The approved requirements are the
[ACD-1300 acceptance-criteria tree](../acceptance-criteria/ac-driven-dev/ACD-1300-autonomous-delivery/ACD-1300.yaml)
and the [product flow](../product-truth/flows/leafcutter/background-ac-worker.flow.json).
These documents do not mark acceptance criteria implemented; execution evidence
and remaining platform limitations must be assessed separately.

Entry point after deployment:
`python <repo>/.leafcutter/scripts/background_worker_cli.py --repo <repo> COMMAND`.
In the package source, the entry point is `scripts/background_worker_cli.py`.
The explicit repository must be a Git repository. Successful commands return
JSON; handled operational errors return exit code 2 and an `error` object on
stderr. `--json` is an optional global alias because output is already JSON.

Native Windows compatibility is currently blocked: the installed Codex runtime
rejects the worker's filesystem profile that denies host-root access. The worker
must fail closed when that execution boundary is unavailable. No successful live
implementation run has been established here, and Linux/WSL execution remains
unverified. A supported isolated execution environment is a prerequisite; the
configuration-only `on --no-start` mode does not establish that support.
Active Git hooks are another deliberate execution blocker: the coordinator
neither executes repository hooks outside its sandbox nor disables them. Use
manual delivery for those repositories until sandboxed coordinator hooks are
supported.

| Command | Effect |
| --- | --- |
| `configure --config FILE` | Validate and save a JSON settings object; does not enable the worker. |
| `on` | Check prerequisites, enable admission and launch a background process. |
| `on --no-start` | Enable saved configuration for a supervisor without a live preflight or process launch. |
| `off` | Stop subsequent admission; permit bounded active work to drain. |
| `status` | Return `settings`, durable `runs`, last observed `queue` exclusions and notification outcomes. |
| `inbox` | Return durable attention `items`. |
| `run` | Run the foreground scheduler until disabled or interrupted. |
| `run --once` | Process one scheduling pass; return waiting if no work is ready. |
| `answer RUN_ID --request-id ID --answer TEXT` | Bind an explicit answer to a pending request for this run. |

## Settings

| Field | Contract |
| --- | --- |
| `max_agent_calls` | Positive integer, default 1. Shared capacity across roles and runs. |
| `implementation.executor` | `codex-cli` in this pilot. |
| `implementation.provider` | `ollama`. |
| `implementation.model` | Explicit local model identifier; pilot uses `qwen3.5:9b-q4_K_M`. |
| `implementation.endpoint` | HTTP loopback Ollama endpoint; remote and cloud implementation endpoints are rejected. |
| `reviewer.executor` | `codex-sdk` or `claude-agent-sdk`. |
| `reviewer.model` | Required user-selected model supported by the reviewer. |
| `credential_ref` | Optional role credential reference; never a raw secret. |
| `checks` | Required nonempty list of nonempty command argument arrays. |
| `target_ref` | Target Git ref, default `origin/main`. Must resolve for work admission. |
| `poll_seconds` | Polling interval between 1 and 60 seconds; default 15. |

`enabled` is managed by `on`/`off`, not by the configuration file. Executor,
provider and model are distinct: selecting a model does not switch harnesses.
The reviewer may use a paid hosted service. Implementation remains local; no
daily quota or token quota is imposed by the scheduler.

The Python requirements include LangGraph. The JavaScript reviewer bridge requires
Node.js 20 or later and needs
the selected package available to Node: `@openai/codex-sdk` or
`@anthropic-ai/claude-agent-sdk`. Use the installed bridge's package manifest
at `background_worker/reviewer_sdk/package.json` for the supported dependency
versions. Set `credential_ref` to `env:NAME` for an environment variable;
the variable is resolved when calling the selected reviewer and its value is not
stored in settings. Runtime and authentication failures are
reported rather than treated as successful review. A missing local model is not
downloaded automatically.

## Selection and recovery

Project checks must exit zero and produce positive inspected-item evidence: a
recognized pytest passing summary, or a final JSON line of the form
`{"leafcutter_check":{"inspected":12,"passed":true}}`. Wrappers for other tools
must derive the integer from actual inspected work and propagate the tool's
failure; a dummy success counter defeats the check contract. Zero-inspected or
unrecognized exit-zero output is insufficient. Bounded, redacted stdout/stderr
is retained in run evidence.

Required executable leaves are grouped by their canonical L1 feature. A whole
feature is excluded when remaining required work is unapproved, unresolved or
outside S/M. Effective urgency inherits the strongest urgency from ancestors
and remaining leaves. The background queue considers low urgency first; real
prerequisites override priority, and equal urgency uses stable feature-ID order.
Hierarchy membership alone is not a prerequisite.

Remote-tracking targets such as `origin/main` are refreshed before scheduling
and delivery revision checks, so merged prerequisites and target advancement
are observed. A local target branch can be used without a remote. Unavailable
remote or target evidence blocks admission; stale cached completion is not a
fallback.

An unreadable or malformed source catalogue stops admission and disables the
worker. `status.queue.error` retains the diagnosis across CLI invocations; this
catalogue failure does not create a feature inbox request. Repair the source
and explicitly enable the worker again with `on`.

One feature keeps an accumulating isolated worktree. Internal dependency evidence
can unlock its next AC locally; external dependencies require target-branch
completion. An existing delivered reservation prevents duplicate builds while
the proposal awaits disposition.

Local state is stored in `.leafcutter/background-worker/state.sqlite`; no hosted
orchestration service or Postgres is required. Preserve that database, its SQLite
sidecar files when present, and run worktrees during recovery. Do not delete
state to retry an exhausted run: automatic attempts and elapsed time must survive
restarts. Revalidation must reject stale scope or dependencies before new work.

A structured implementation `needs_input` outcome becomes a durable question
for that run. Its explicit answer returns to the same checkpoint and worktree,
without resetting attempt or time counters. Interrupted execution whose effects
are uncertain requires reconciliation before another call can start.

The execution policy allows up to three implementation attempts and sixty total
implementation minutes per AC, including repair, with at most two feature
reviews. Validation and positive review must identify the same current head
before draft publication. Failed or missing review is never approval.

The worker runs project checks and agent tools with local process access. Run
only against repositories and checks you trust; framework orchestration itself
does not provide an operating-system security boundary. Desktop notification
delivery is best effort and reported separately from the durable run outcome.

## Architecture views

- [State transitions](../architecture/diagrams/background-ac-worker-state.md)
- [Execution sequence](../architecture/diagrams/background-ac-worker-sequence.md)
- [Components and persistence](../architecture/diagrams/background-ac-worker-components.md)

The local Docker Desktop smoke test with official Codex 0.156.1 also refused
execution because Bubblewrap could not create an unprivileged user namespace.
No privileged-container override was used. Passing the mandatory sandbox probe
in a supported Linux or WSL environment is still required before live acceptance.
