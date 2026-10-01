---
title: "How to run the decision kernel"
description: "Set up credentials, start a run from the command line, answer the pauses (host work and human questions), read the report, inspect capability gaps and install the /leafcutter skill for Claude Code."
type: how-to
status: active
created: 2026-10-01
last_updated: 2026-10-01
components:
  - decision_kernel
related_docs:
  - docs/how-to/inspect-kernel-traces-with-langfuse-mcp.md
  - docs/architecture/components/decision-kernel.md
  - docs/analysis/2026-10-01-decision-kernel-v0-demo-report.md
  - docs/analysis/2026-09-30-decision-kernel-design-5-client-observability.md
related_code:
  - kernel/__main__.py
  - kernel/adapters/cli.py
  - kernel/adapters/claude_code/SKILL.md
  - config/kernel_config.default.json
---

# How to run the decision kernel

The kernel takes a goal, decides it against repository evidence with the real Jev provider, and
pauses whenever it needs host work or a human answer. You drive it with `python -m kernel`.

## Prerequisites

- Python 3.13 or newer and the dev dependencies (`pip install -r requirements-dev.txt`).
- A Jev API key. Langfuse keys are optional: without them runs still work and
  `trace_refs.observability` reports `degraded`.
- You are in the leafcutter-ai checkout. The kernel is not shipped to adopter projects.

## Steps

### Step 1 — Put the credentials in an untracked `.env`

Lookup order per value: process environment, then `--env-file` (or `LEAFCUTTER_ENV_FILE`), then
the first `.env` found walking up from the checkout. Git worktrees under the main checkout find
the main checkout's `.env` this way. Never commit the file.

A file you name explicitly (`--env-file` or `LEAFCUTTER_ENV_FILE`) must exist and be readable: if
it does not, the command fails with exit 5 and `error.code` `config_invalid` instead of falling
back to another `.env`, so a run never goes out with credentials you did not intend. Only the
implicit walk-up is best-effort. A `--config` or registry file that is not valid UTF-8 also
fails with exit 5 (`config_invalid` / `registry_invalid`).

```bash
JEV_API_KEY=<your Jev key>
LANGFUSE_PUBLIC_KEY=<pk-lf-...>
LANGFUSE_SECRET_KEY=<sk-lf-...>
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

`TYPESAFE_API_KEY` is accepted for the Jev key and `LANGFUSE_HOST` for the base URL. The kernel
never prints, logs or persists these values.

### Step 2 — Optionally write a config override

Every threshold and limit lives in `config/kernel_config.default.json`. An override file is
deep-merged over it. Pass it with `--config <file>` or set `LEAFCUTTER_KERNEL_CONFIG`. This
example moves the run data out of the checkout and tells research to plan only needs Jev is
confident about, which suits a repository-only run with no host research source:

```json
{
  "paths": {"run_root": "C:/Users/me/kernel-runs"},
  "research": {"need_supporting_threshold": 0.8},
  "limits": {"max_jev_calls": 20},
  "langfuse": {"enabled": true}
}
```

`research.need_supporting_threshold` may not exceed `need_required_threshold` (0.8 by default).
A relative `paths.run_root` resolves against the checkout (default `.leafcutter/kernel`, which is
git-ignored). An invalid override exits 5 with `config_invalid`.

### Step 3 — Write the task and start the run

The goal travels as data, never on a command line. Write a `TaskInput` JSON file and pass it with
`--input-file`, or pipe it on stdin (`-` or no flag reads stdin). `repository_root` is an absolute
path; `read_roots` is optional.

```json
{
  "goal": "Should this new capability be an atomic node or an encapsulated subgraph?",
  "caller": {"id": "me", "kind": "human"},
  "scope": {"workspace_id": "leafcutter", "repository_root": "C:/Users/me/leafcutter"}
}
```

```bash
python -m kernel run --input-file task.json --json
cat task.json | python -m kernel run --json
```

stdout is exactly one JSON document, the run envelope; logs go to stderr. To skip option
generation supply `input_payload_schema: "leafcutter.decision_request.v1"` and an `input_payload`
with `question`, `options` and `criteria`. Evidence you already hold goes in `initial_evidence`.

### Step 4 — Route on the envelope `status`

| `status` | Meaning | You do |
|---|---|---|
| `waiting_host` | Bounded host work is needed (`pending_interaction.operation`) | Do only that work, then resume (Step 5) |
| `waiting_human` | A person must answer `pending_interaction.question` | Ask them, then resume |
| `completed`, `partial`, `blocked`, `failed`, `cancelled` | Terminal | Read the report (Step 6) |
| `running` | Another process is working | `python -m kernel status --run-id <id> --json` |

`partial` and `blocked` are honest outcomes, not successes. Check `limitations` and
`open_questions`.

### Step 5 — Resume with a validated answer

Echo `run_id`, the interaction `id` and its `state_revision` exactly. Host work answers in the
packet's `output_schema_id`; a human answer uses `leafcutter.human_answer.v1` with exactly one of
`choice_id`, `free_text` or the structured approve-or-edit fields.

```json
{
  "run_id": "run-0123456789abcdef",
  "interaction_id": "int-0123456789abcdef",
  "expected_state_revision": 3,
  "relayed_by": "me",
  "actor": {"id": "human:me", "kind": "human"},
  "response_schema_id": "leafcutter.human_answer.v1",
  "response": {"choice_id": "approve"}
}
```

```bash
python -m kernel resume --run-id run-0123456789abcdef --input-file answer.json --json
```

A duplicate identical answer is accepted idempotently. A conflicting, stale or forged one is
refused with exit 3 and the run is unchanged. A host answer that fails its schema may be repaired
once (`host.max_repair_attempts`); the packet comes back in `error.details.pending_interaction`.

### Step 6 — Read the result and the gaps

`report_ref` is the absolute path of the run's `report.md` (open it directly), under
`<run_root>/runs/<run_id>/artifacts/`. `evidence_ids`, `decision_ids`, `usage_summary` and
`trace_refs.trace_url` are in the envelope. `gaps` lists capability gaps the run recorded;
`gaps` as a command aggregates them across runs, one row per deduplicated need:

```bash
python -m kernel gaps --json
```

Each row has `gap_type`, `occurrence_count`, `fallback_outcome` and `build_opportunity`. Cancel a
run with `python -m kernel cancel --run-id <id> --actor human:<id> --json`.

### Step 7 — Install the `/leafcutter` skill for Claude Code

The skill is transport only: it forwards the goal, relays questions and does exactly the host
work requested. Install it into a workspace's skills directory (the command writes
`<target>/<name>/SKILL.md` only and refuses to overwrite a different file without `--force`):

```bash
python -m kernel install-skill --target-dir <workspace>/.claude/skills --name leafcutter --json
```

The skill runs `python -m kernel` from the checkout, so install it where that command works.
If a project command named `/leafcutter` already exists, remove it first or choose another
`--name`.

What the skill may do without asking you (its `allowed-tools`, rendered for this checkout):

| Pre-approved | Scope |
|---|---|
| `Bash` | Only `python -m kernel run`, `resume` and `status`. `cancel`, `gaps` and `install-skill` (including `--force`) are never pre-approved: you run them yourself. |
| `Edit` (covers Write) | Only `<run_root>/client/**`, the scratch directory for the TaskInput and submission JSON files. Any other file write prompts you. |
| `Read` | Only `<run_root>/**`, where the host input artifacts and reports live. Repository files inside the working directory are read-only for Claude Code by default and need no pre-approval. |
| `AskUserQuestion` | Human questions from the kernel. |

`<run_root>` is `paths.run_root` of the config in effect when you run `install-skill`; reinstall
after you change it. Claude Code consults only `Edit` and `Read` path rules (a `Write(path)` rule is
accepted but ignored), and absolute paths start with `//` (`//c/Users/...` on Windows).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | An envelope was produced. Every status above is a normal state. |
| 2 | Usage error (argparse prints the usage to stderr). |
| 3 | Input or submission rejected, state unchanged (`error.code` says why). |
| 4 | Unknown run id. |
| 5 | Internal or environment error: `config_invalid`, `registry_invalid`, `provider_unavailable`, `registry_changed`, `internal`. |

## Verification

```bash
python -m kernel gaps --json
```

Expected output: one JSON line with `"gaps"`, `"total"`, `"build_opportunities"` and
`"occurrences"`, exit code 0, and no Jev key needed. A fresh run root prints `"total": 0`.

## Troubleshooting

1. **Exit 5, `provider_unavailable`.** No Jev key was found. Check the `.env` lookup order in
   Step 1; `status`, `cancel` and `gaps` need no key.
2. **`trace_refs.observability` is `degraded`.** Langfuse keys are missing or wrong; the run is
   unaffected and observations go to `<run_root>/telemetry_spool.jsonl`.
3. **A run pauses on `bounded_research` for a question your repository settles.** A supporting
   need only a host can serve paused it. Raise `research.need_supporting_threshold` (Step 2).
4. **Exit 3 on resume.** Read `error.code`: `stale_revision` means echo the packet's current
   `state_revision`; `not_pending` means that interaction is not the open one.

## See Also

- [How to inspect kernel traces with the Langfuse MCP server](inspect-kernel-traces-with-langfuse-mcp.md)
- [Decision kernel container overview](../architecture/components/decision-kernel.md)
- [V0 demo and run report](../analysis/2026-10-01-decision-kernel-v0-demo-report.md)
- [Documentation Index](../INDEX.md)
