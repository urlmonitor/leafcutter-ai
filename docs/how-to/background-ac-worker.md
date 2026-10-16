---
title: "Run the local background AC worker"
description: "Configure, supervise and recover the opt-in local background AC worker."
type: how-to
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
  - docs/reference/background-ac-worker.md
  - docs/how-to/background-ac-worker-wsl.md
---

# Run the local background AC worker

The background lane turns approved, dependency-ready feature groups into reviewed
draft pull requests. It is disabled after installation. Enabling this lane does
not change the ordinary build queue.

A candidate is a whole canonical feature: all remaining executable leaves must
be approved, have no unanswered questions, and be estimated S or M; inherited
obligations must also be approved and question-free. Real prerequisites must be
satisfied, with external prerequisites proven complete on the target branch.
The worker selects the least urgent dependency-ready feature first, using the
strongest urgency of its remaining work and ancestors, then canonical feature
ID for ties. Each AC shares at most three attempts and sixty implementation
minutes across initial work and repairs. Each feature gets at most two automatic
reviews; exhaustion requires human attention, and restarting does not reset
these limits.

The native Windows Codex runtime used during validation rejects the required
filesystem policy. A dedicated WSL2 runtime now passes the real sandbox probe:
writing inside the owned workspace succeeds, while host files outside the owned
worktree remain inaccessible and unchanged. Linux Git-hook integration tests also pass, including attempts to write
outside the worktree or change protected Git metadata. These checks establish
the execution boundary; full live local-model delivery acceptance is still in
progress. `on --no-start` does not bypass that boundary during execution.

Install Leafcutter into your consumer repository with the usual build command.
The installed entry point is `.leafcutter/scripts/background_worker_cli.py`.
Use absolute paths for that script, the repository and configuration file; you
can then invoke it from another working directory.

## Windows runtime setup

Use the [dedicated WSL runtime setup guide](background-ac-worker-wsl.md) to install
Linux dependencies and register the Windows launcher before continuing below.

## Prepare execution

Install the Python worker dependencies from the deployed
`background_worker/requirements.txt`, Git, the Codex CLI and Ollama. Start
Ollama locally and download the implementation model yourself; the worker does
not download models. The pilot implementation uses Qwen3.5 9B with a local
Ollama endpoint. Install and authenticate the selected reviewer SDK as described
in the [reference](../reference/background-ac-worker.md).

```text
python -m pip install -r /absolute/project/.leafcutter/scripts/background_worker/requirements.txt
npm ci --prefix /absolute/project/.leafcutter/scripts/background_worker/reviewer_sdk
```

The reviewer bridge requires Node.js 20 or later. Run the Python installation
with the same interpreter that will start the worker.
Run `npm ci` in the execution runtime after deployment, and again when an upgrade
changes the deployed reviewer lockfile. Deployment copies the bridge manifest
and lockfile; it does not install npm dependencies. Neither a model nor the
background scheduler installs missing reviewer packages. A missing SDK is a
prerequisite error to resolve before enabling work.
The coordinator's virtual environment is granted read access inside the model
and check sandbox, so install check tools in that environment. This grant covers
runtime dependencies, not arbitrary home directories. Install repository hook
dependencies before enabling work; hooks cannot download packages inside their
network-disabled sandbox. For pre-commit hooks, prepare a dedicated cache in
advance and configure `hook_runtime.read_paths` and `hook_runtime.pre_commit_cache`
as shown in the [reference](../reference/background-ac-worker.md). For a project
using pre-commit, install its hook environments before sandboxed execution:

```bash
/opt/leafcutter-worker/venv/bin/python -m pip install pre-commit
worker_runtime=/opt/leafcutter-worker
export PRE_COMMIT_HOME="$worker_runtime/pre-commit-cache"
worker_python="$worker_runtime/venv/bin/python"
"$worker_python" -m pre_commit install-hooks --config /absolute/project/.pre-commit-config.yaml
```

Grant only the dedicated virtualenv/cache and any additional runtime directories
the hooks actually require. Hooks that reformat tracked files stop the run so
required checks can be repeated.

Create a JSON file with your chosen reviewer model and real project checks:

```json
{
  "max_agent_calls": 1,
  "implementation": {
    "executor": "codex-cli",
    "provider": "ollama",
    "model": "qwen3.5:9b-q4_K_M",
    "endpoint": "http://localhost:11434",
    "context_window": 65536
  },
  "reviewer": {
    "executor": "codex-sdk",
    "provider": "openai",
    "model": "gpt-6-sol"
  },
  "checks": [["/opt/leafcutter-worker/venv/bin/python", "-m", "pytest"]],
  "target_ref": "origin/main",
  "poll_seconds": 5
}
```

The last two implementation fields are optional. The requested context defaults
to 65,536 tokens and is capped by the model's advertised native context capacity.
Configure the Ollama server with at least that resulting context; this setting
does not resize the server. Reasoning follows the validated provider default
unless explicitly overridden. Without an advertised default it uses `none`
when supported. Preflight rejects unsupported advertised or explicit efforts. Omit `reasoning_effort` when switching models
unless you have selected a supported value.

Each implementation call receives a temporary model catalog built from the
verified local model metadata, plus explicit context and reasoning settings.
The worker removes it after the call. No manual shared `~/.codex/model.json`
or shared Codex profile changes are needed; user profiles are not imported into
the isolated implementation runtime. Local completion still requires actual
tool evidence and a strictly parsed final outcome.

The reviewer model is configurable per role; select one available to your
authenticated reviewer. Checks are argument arrays, not shell
command strings. Replace the example with the checks your project actually uses.
Each check must exit successfully and report a positive inspected count. The
worker recognizes a pytest passing summary. For other tools, use a project-owned
wrapper that runs the real check, propagates failure, and prints a final JSON line:

```json
{"leafcutter_check":{"inspected":12,"passed":true}}
```

Here `12` illustrates the field; your wrapper must calculate it from the tool's
actual inspected tests, files or cases. Never use a dummy constant or report
success when the tool inspected nothing. Bounded, redacted check output is saved
with the run's evidence for review.

Do not put API keys or tokens in this file; use the executor's authentication or
its supported credential reference.

```text
python /absolute/project/.leafcutter/scripts/background_worker_cli.py --repo /absolute/project configure --config /absolute/worker-config.json
python /absolute/project/.leafcutter/scripts/background_worker_cli.py --repo /absolute/project status
python /absolute/project/.leafcutter/scripts/background_worker_cli.py --repo /absolute/project on
```

`configure` validates and saves settings without enabling work. `on` checks
runtime prerequisites and starts the background process. Model availability and
execution failures can still arise during a run. Missing prerequisites are errors
to correct; they never select a cloud implementation automatically. Background
output goes to `.leafcutter/background-worker/worker.log`.

For a service manager or a supervised one-shot run, enable without launching:

```text
python /absolute/project/.leafcutter/scripts/background_worker_cli.py --repo /absolute/project on --no-start
python /absolute/project/.leafcutter/scripts/background_worker_cli.py --repo /absolute/project run --once
```

`--no-start` validates saved configuration only. It deliberately skips the live
preflight and does not prove that executors or model endpoints are available.
`run --once` processes available work and returns; an empty queue reports waiting
without inference. Omit `--once` for the foreground polling loop.

## Inspect, stop and answer

```text
python /absolute/project/.leafcutter/scripts/background_worker_cli.py --repo /absolute/project status
python /absolute/project/.leafcutter/scripts/background_worker_cli.py --repo /absolute/project inbox
python /absolute/project/.leafcutter/scripts/background_worker_cli.py --repo /absolute/project off
python /absolute/project/.leafcutter/scripts/background_worker_cli.py --repo /absolute/project answer RUN_ID --request-id REQUEST_ID --answer "Use the existing public interface"
```

Use the identities returned by the inbox. An answer belongs to one unresolved
request and run; it is not a blanket approval for unrelated work. Continuation
requires enablement, remaining budget and revalidation. `off` prevents new work
while an already running bounded action can finish and save its result. Keep the
worktree and local state when stopping or recovering a run.

When implementation reports `needs_input`, the worker preserves the question
in the inbox and stops that run. Answering continues the same preserved worktree
after revalidation; it does not reset attempts or elapsed-time budgets.

The CLI returns JSON for status and outcomes. Inspect `notifications` in status
if a desktop notification did not appear; the durable inbox remains the source
of pending attention items. A delivered draft PR remains a human review and merge
decision. Closing a proposal unmerged does not authorize an automatic new build.

See [configuration and recovery](../reference/background-ac-worker.md) and the
[state diagram](../architecture/diagrams/background-ac-worker-state.md).


## Reconcile an interrupted process

An ordinary `off` drains the current action and needs no reconciliation. If the
worker crashes with an uncertain action, `answer` alone cannot establish that
an orphan process has stopped. Preserve its database and worktree, disable the
worker, and inspect the interruption before proceeding.

Reconciliation requires proof that the Linux runtime which started the action
has ended. It records the kernel boot identity, PID namespace and PID 1 start
time before execution. Stop other work in the dedicated worker distribution,
then use `wsl --terminate leafcutter-worker` and start it again. A new namespace
and init start time prove the prior processes ended even when Docker keeps the
shared WSL kernel running. This command never restarts the runtime for you.

After restarting, inspect the preserved worktree and run:

```text
python /absolute/project/.leafcutter/scripts/background_worker_cli.py --repo /absolute/project reconcile RUN_ID --confirm-processes-stopped --note "Restarted worker VM and inspected the preserved worktree"
```

The command requires the worker to remain disabled and rejects active service
or run locks. It records the operator note, runtime identities, current Git head,
worktree status and released capacity. Same-runtime interruptions and legacy runs
without a recorded runtime identity remain blocked; expiry alone is never proof
that a process stopped.

An uncertain implementation consumes its remaining AC time allowance and stays
in the human inbox. No attempts or review calls are refunded. An interrupted
validation or first review can resume through fresh validation after explicit
`on`, provided no other inbox questions remain. Two consumed reviews require
human handling. Reconciliation does not accept unknown changes as completed work,
modify the worktree, or publish a proposal.
