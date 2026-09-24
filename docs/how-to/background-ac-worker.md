---
title: "Run the local background AC worker"
description: "Configure, supervise and recover the opt-in local background AC worker."
type: how-to
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
  - docs/reference/background-ac-worker.md
---

# Run the local background AC worker

The background lane turns approved, dependency-ready feature groups into reviewed
draft pull requests. It is disabled after installation. Enabling this lane does
not change the ordinary build queue.

The installed native Windows Codex runtime currently rejects the worker's
filesystem profile that denies host-root access. Startup therefore fails closed
on this environment; live local implementation has not been demonstrated here.
Execution requires an isolated environment that supports the required profile.
A smoke test in the existing Docker Desktop Linux runtime also failed because
Bubblewrap could not create an unprivileged user namespace. A standalone Linux
or WSL environment with those namespaces enabled remains unverified. Do not remove the
profile or use `--no-start` as a way to bypass this execution requirement.

Repositories with active Git hooks also require manual delivery in this pilot.
The worker refuses to run those hooks outside its execution boundary and does
not skip them to force a commit through.

Install Leafcutter into your consumer repository with the usual build command.
The installed entry point is `.leafcutter/scripts/background_worker_cli.py`.
Use absolute paths for that script, the repository and configuration file; you
can then invoke it from another working directory.

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

Create a JSON file with your chosen reviewer model and real project checks:

```json
{
  "max_agent_calls": 1,
  "implementation": {
    "executor": "codex-cli",
    "provider": "ollama",
    "model": "qwen3.5:9b-q4_K_M",
    "endpoint": "http://localhost:11434"
  },
  "reviewer": {
    "executor": "codex-sdk",
    "model": "REPLACE_WITH_YOUR_REVIEWER_MODEL"
  },
  "checks": [["python", "-m", "pytest"]],
  "target_ref": "origin/main",
  "poll_seconds": 5
}
```

The reviewer model placeholder is not a working model identifier. Select a model
available to your authenticated reviewer. Checks are argument arrays, not shell
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
