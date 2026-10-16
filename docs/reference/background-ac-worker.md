---
title: "Background AC worker reference"
description: "CLI, configuration, evidence and execution limitations for the background AC worker."
type: reference
status: active
created: 2026-09-24
last_updated: 2026-09-25
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

Native Windows execution fails closed when Codex cannot enforce the filesystem
profile that denies host-root access. The dedicated WSL2 runtime has passed the
real inside-write and outside-host-file isolation probe. Complete live local-model
delivery acceptance remains in progress. The configuration-only `on --no-start`
mode does not establish runtime readiness. Windows users can route the CLI to a
preinstalled WSL runtime; see the [setup guide](../how-to/background-ac-worker.md).
On Linux, coordinator Git hooks run through bubblewrap with the owned worktree
writable, Git metadata read-only, no network, and private index/object storage.
Real Git tests verify project checks, outside-write/ref/config denial, normal
commit-message handling and rejection of hook formatting that requires new checks.
Post-commit failures block for reconciliation even when Git reports success.

Optional `hook_runtime` configuration admits explicit absolute Linux dependency
directories as read-only `read_paths`. A `pre_commit_cache` directory must be
prepared before execution; each invocation receives a private writable copy,
while original cache paths remain read-only for installed environment references.
The sandbox cannot download missing dependencies. For example:

```json
{"hook_runtime":{"read_paths":["/opt/leafcutter-worker/venv"],"pre_commit_cache":"/opt/leafcutter-worker/pre-commit-cache"}}
```

Only select runtime dependency directories; never supply a home directory or
credential store. Hook configuration changes invalidate an active run's execution
configuration. Hooks are never skipped when their runtime is unavailable.
Target fetches use the same hook boundary. Coordinator status/diff operations
disable filesystem-monitor callbacks, external diffs and text conversion.
An active executable clean/process filter blocks staging with a diagnosis;
required content transforms are never silently skipped. Unused registered filters
do not block an ordinary repository.

When hooks reference deployed `.leafcutter` entrypoints, worktree preparation
copies the package's explicit `hook_assets.json` allowlist into ignored worktree
paths, including guard scripts, approved configuration assets and scanner helpers.
It does not copy credentials, worker state, arbitrary deployment files or installed
Node packages. Symlinks, tracked destinations and conflicting preserved copies
block preparation. Model tools and hooks receive these runtime assets read-only.
The active `.pre-commit-config.yaml` is protected too, including a tracked copy;
features that require changing hook policy need a separate supervised path.
The actual pre-commit hook runs once on the prepared baseline before model work;
missing dependencies or unsupported hooks fail there without starting inference.
This does not run the configured project check suite on its own. A project hook
that requires baseline tests to pass still enforces its normal policy.

| Command | Effect |
| --- | --- |
| `runtime configure-wsl --distribution NAME --python PATH` | Windows only: register and probe a preinstalled Linux runtime while disabled and drained. |
| `configure --config FILE` | Validate and save a JSON settings object; does not enable the worker. |
| `on` | Check prerequisites, enable admission and launch a background process. |
| `on --no-start` | Enable saved configuration for a supervisor without a live preflight or process launch. |
| `off` | Stop subsequent admission; permit bounded active work to drain. |
| `status` | Return `settings`, durable `runs`, `startup` lifecycle/launch records, last observed `queue` exclusions and notification outcomes. |
| `inbox` | Return durable attention `items`. |
| `run` | Run the foreground scheduler until disabled or interrupted. |
| `run --once` | Process one scheduling pass; return waiting if no work is ready. |
| `answer RUN_ID --request-id ID --answer TEXT` | Bind an explicit answer to a pending request for this run. |
| `reconcile RUN_ID --confirm-processes-stopped --note TEXT` | Reconcile uncertain execution only after a proven Linux runtime restart, while disabled and exclusively locked. |

## Settings

`on` waits up to ten seconds for its child to acquire the service lock and
acknowledge the matching launch token, before reporting startup success. Early
exit or missing acknowledgement disables that failed launch and records its
failure; an existing service makes activation idempotent. Read `startup` in
`status` and the reported `worker.log` path for diagnostics. Readiness confirms
the scheduler started; subsequent queue/runtime failures remain visible in its
durable state. `on --no-start` only changes enablement for an external supervisor.

| Field | Contract |
| --- | --- |
| `max_agent_calls` | Positive integer, default 1. Shared capacity across roles and runs. |
| `implementation.executor` | `codex-cli` in this pilot. |
| `implementation.provider` | `ollama`. |
| `implementation.model` | Explicit local model identifier; pilot uses `qwen3.5:9b-q4_K_M`. |
| `implementation.endpoint` | HTTP loopback Ollama endpoint; remote and cloud implementation endpoints are rejected. |
| `implementation.context_window` | Optional positive integer, default 65,536; capped by advertised native model context capacity. Configure Ollama server capacity separately. |
| `implementation.reasoning_effort` | Optional named effort: `none`, `minimal`, `low`, `medium`, `high` or `xhigh`; the selected model must advertise support. |
| `reviewer.executor` | `codex-sdk` or `claude-agent-sdk`. |
| `reviewer.model` | Required user-selected model supported by the reviewer. |
| `credential_ref` | Optional role credential reference; never a raw secret. |
| `checks` | Required nonempty list of nonempty command argument arrays. |
| `target_ref` | Target Git ref, default `origin/main`. Must resolve for work admission. |
| `poll_seconds` | Polling interval between 1 and 60 seconds; default 15. |
| `hook_runtime.read_paths` | Explicit Linux dependency directories granted read-only access to hooks. |
| `hook_runtime.pre_commit_cache` | Preinstalled cache copied privately for each hook invocation; downloads remain disabled. |

`enabled` is managed by `on`/`off`, not by the configuration file. Executor,
provider and model are distinct: selecting a model does not switch harnesses.
The reviewer may use a paid hosted service. Implementation remains local; no
daily quota or token quota is imposed by the scheduler.

Preflight reads local Ollama model metadata and validates the requested context
and effort before reporting runtime readiness. Without an explicit override, the effort follows the validated provider
thinking default. When no default is advertised, it uses `none` if supported,
otherwise the first supported effort; absent thinking metadata means `none`.
An unsupported advertised default is a prerequisite error. Boolean thinking modes map `false` to `none` and
`true` to `high`; recognized named efforts retain their names. An unsupported
explicit effort is rejected.

Each implementation call writes an ephemeral Codex model catalog into its
isolated `CODEX_HOME`, sets the resulting context window and an automatic
compaction threshold of three quarters of that window, and disables web search.
The catalog is removed with the temporary home after the call. It uses verified
local model metadata without importing a user catalog or shared Codex profile.
No manual `~/.codex/model.json` setup is required. This does not install a model
or configure Ollama's server context allocation. Final local output is validated
as a strict completion/clarification object; a completion claim without successful
tool execution does not count as implementation.

The Python requirements include LangGraph. The JavaScript reviewer bridge requires
Node.js 20 or later and needs
the selected package available to Node: `@openai/codex-sdk` or
`@anthropic-ai/claude-agent-sdk`. Use the installed bridge's package manifest
at `background_worker/reviewer_sdk/package.json` for the supported dependency
versions. Set `credential_ref` to `env:NAME` for an environment variable;
the variable is resolved when calling the selected reviewer and its value is not
stored in settings. Runtime and authentication failures are
reported rather than treated as successful review. For example, the selected
Codex reviewer uses `{"executor":"codex-sdk","provider":"openai","model":"gpt-6-sol"}`.
Changing an executor does not translate its model identifier to another provider.
A missing local model is not downloaded automatically. Configure Ollama context
and inference parallelism on the local server, separately from the worker's
`max_agent_calls` admission limit.

Deployment copies `reviewer_sdk/package.json` and its lockfile, not installed
Node packages. Before enabling the worker, run
`npm ci --prefix /absolute/project/.leafcutter/scripts/background_worker/reviewer_sdk`
inside its execution runtime. Repeat this after a deployment changes the
lockfile. This is an explicit operator installation step; neither the scheduler
nor the implementation model invokes a package manager to repair a missing SDK.

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
are observed. Publication uses that target's remote for both Git push and explicit
GitHub repository selection. A local target branch uses its configured tracking
remote/branch, or `origin` and the same branch name when no tracking is configured.
Publication requires a GitHub destination even when local planning uses a local
branch. The freshly fetched remote base must equal the validated base SHA.
Unavailable remote or target evidence blocks admission; stale cached completion
is not a fallback.

Only same-repository publication is supported: fetch and push URLs must resolve
to one repository. Multiple destinations, divergent push URLs and implicit forks
are rejected. The destination is saved before publication; changing it during an
uncertain retry requires reconciliation rather than creating another PR elsewhere.

If the target advances after a feature worktree was created, the run blocks
before review/publication. This version has no automatic rebase or CLI command
that accepts a new base for that run. An inbox answer does not override the
recorded base. Preserve the branch and take over delivery manually, including
checks and review against the new target; do not edit the state database to
bypass the revision guard.

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

Explicit reconciliation records the operator note, runtime identities, Git head,
worktree status and released leases. A changed Linux kernel boot identity, or
both a changed PID namespace and PID 1 start time, proves the previous runtime
ended. Same-runtime and legacy runs without that evidence remain blocked. No
attempts or review calls are refunded; unknown implementation duration consumes
the remaining AC time allowance and requires human handling. Interrupted first
review or validation resumes through fresh validation, without retaining approval
proof. Other pending questions must still be answered individually.

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

An earlier Docker Desktop probe could not create an unprivileged user namespace.
That environment did not pass preflight; the separate WSL2 validation described
above did. Availability is checked on the actual runtime before execution.


## Explicit formatting before tests

Projects may configure a scoped formatter wrapper as the first required check,
followed by their test command, for example `python tools/format_labels.py` then
`python -m pytest -q`. The wrapper should run a prepared formatter on an explicit
nonempty file set, fail on formatter errors, and emit the normal inspected-check
JSON envelope only after successful inspection. Bare formatter output alone is
not accepted as check evidence. Keep formatting idempotent: feature validation
runs the checks again and rejects a dirty review worktree.

The live fixture formats only `labels.py` using Ruff before pytest and verifies
that its checker/configuration and original tests remain unchanged. Earlier
unformatted live trials exhausted their budgets on trailing whitespace despite
valid completion messages; they remain failed evidence. This fixture preparation
does not configure formatting for installed consumer repositories, skip Git
whitespace checks, or establish semantic correctness without tests and review.

## Declared runtime inputs

An approved AC may declare `required_inputs` with an `id`, a nonblank `question`,
and optional distinct `choices`. These are runtime human decisions, separate
from unresolved requirements that prevent admission. Declarations contain no
values or autofill rules. The planner rejects duplicate IDs within one AC.
After preparation, the graph separates read-only discovery, a deterministic
input gate and writable implementation. Missing declared inputs raise durable
questions before a model call, saving the attempt budget. Otherwise discovery
assesses supplied facts and inspects repository files only when needed. A ready
reply requires a nonblank assessment. Supplied context can suffice without tools;
the saved assessment is advisory coding context bound to the current input proof,
not approval. Discovery cannot write or invent answers; only a satisfied gate permits edits.

Saved answers survive restart and bind to the declaring AC, input ID and feature
digest. Descendants can reuse the same ancestor declaration; a sibling
declaration cannot borrow that answer. Changed scope requires revalidation; full live delivery remains unverified.

## Communication contract and provenance

The main-branch analysis `2026-09-25-duplication-clusters-that-produce-known-issues.md`
(C2/C3/C11) applies here: derive reply instructions from the shared schema and
validate final replies strictly after tool execution. Local calls omit generation
schemas, which blocked Qwen tools in a paired probe. Refusals/errors block; coding
completion still requires tool evidence and independent checks.
Human decisions come through the trusted operator command and scoped store, never
model-echoed fields. This is local process trust, not independent person authentication.
Executor capabilities enforce the no-delegation policy.
These worker requirements do not migrate JS workflows or establish live acceptance.
