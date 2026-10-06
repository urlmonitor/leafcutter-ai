---
title: "How to run the decision kernel"
description: "Set up credentials, start a run from the command line, answer the pauses (host work and human questions), read the report, inspect capability gaps and install the /leafcutter skill for Claude Code."
type: how-to
status: active
created: 2026-10-01
last_updated: 2026-10-03
components:
  - decision_kernel
related_docs:
  - docs/how-to/supply-and-evaluate-kernel-context.md
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

The kernel takes a goal, recognizes repository terms before classifying intent, decides it against repository evidence with the real Jev provider, and
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
The run root resolves independently of the shell's current directory, in this order: (1) the
`LEAFCUTTER_KERNEL_RUN_ROOT` environment value, (2) `paths.run_root` from the config in effect
(absolute as given), (3) a relative `paths.run_root` resolved against the kernel's own checkout,
never the caller's cwd. A run started from one directory can be resumed from any other.

When you run the kernel from a host, put `-P` after the interpreter (`PYTHONPATH=<repo> python -P -m kernel ...`).
Without it `python -m kernel` puts the current directory first on `sys.path`, so a shell sitting in
another checkout of this repository imports that checkout's `kernel/` package, whose empty run store
answers `run_not_found`. The installed `/leafcutter` skill already includes `-P`.

A relative `paths.run_root` resolves against the checkout (default `.leafcutter/kernel`, which is
git-ignored). An invalid override exits 5 with `config_invalid`.

#### What native retrieval reads (sources and grounding)

`sources` in the config is the catalog of where evidence may come from; a need is searched only
in the sources whose `categories` include it. The defaults cover the repository's own project
metadata: principles and ADRs, code patterns, `repo.docs` (README, how-tos, reference, testing),
`repo.acceptance_criteria`, `repo.roadmap` (roadmap and vision), `repo.tickets` (read-only),
`repo.config` (secrets denied by `deny_globs`) and `repo.tests` (test READMEs, `pytest.ini`).
Override or extend them with a `sources` list in your override file (a list replaces the default
list, so copy the entries you keep). Every source is bounded by `retrieval.max_candidates`,
`max_excerpt_chars` and `max_file_bytes`; add secret-like paths to `retrieval.deny_globs` or to a
source's own `deny_globs`.

Files are read by section, not by one window: Markdown by heading (the locator reads
`path#L10-L40 (§Alternatives)`), YAML and JSON by top-level key, Python by top-level class or
function; other formats keep the old line window. Up to `retrieval.sections_per_file` sections
of a file are offered, best term match first. Before ranking, a file whose path or name carries
an identifier or word of the question (`ADR-057`, `decision.py`, `kernel.contracts.decision`,
a path) is always offered. A source offers at most
`max(source_candidate_floor, source_candidate_ratio x files scanned)` candidates, so a small
folder is fully considered while a large one stays bounded; `max_candidates` (default 60) is the
pool and `rerank_max_per_need` (20) the one Jev call per need. Cuts are named in limitations.

A retrieval request may also carry `explicit_locators` (at most `max_explicit_locators`): a
repo-relative path, `path#L10-L40`, `path#Heading text` or `path::Symbol` (a Python class,
function or `Class.method`). Each is fetched exactly, marked `explicit_locator` in provenance,
kept by ranking, and refused (with a limitation) outside the scope's read roots, under deny
globs, on path traversal, or outside every configured `repo_text` source.

A decision whose options are unknown first researches the option space (task context, existing
patterns, prior decisions) and then asks the host for options with that evidence attached. The
host has no repository access: it may only use the evidence in the packet's input artifact, and
each option must cite the evidence ids it rests on. `decision.require_option_grounding`
(default `true`) refuses options that cite nothing; set it to `false` to keep them flagged as
limitations instead. `decision.max_grounding_evidence` bounds how much evidence one options
request carries. A need counts as covered only by evidence at or above
`retrieval.coverage_relevance_threshold`.

#### Design decisions, targeted research and answer-aware coverage

When a required criterion is a property of the proposed designs (a design judgement, not a fact
a file can state), when two assessments in a row barely move (`decision.progress_epsilon`), or
after `decision.max_research_rounds` rounds, the decision stops researching and asks a human a
**ranked question**: the options as `#1, #2, ...` ordered by required criteria passed, then the
required mean, then the supporting mean, each with its criteria in words and the evidence it
cites. Answer with `{"choice_id": "<option id>"}`, add an option of your own
(`added_options`), or answer in words (recorded only). A choice resolves the decision with you
as approver and the ranking in the rationale. `decision.design_judgement_threshold` sets how
sure Jev must be that a criterion is a design judgement.

Research uses what the decision already knows. An option that cites `kernel/contracts/decision.py`
(or `path#anchor`, `path::Symbol`) has that file fetched exactly, whatever the need's own sources;
evidence ids it cites stay context. Queries lead with the goal, then the approved criteria and
the option titles; `retrieval.max_query_terms` (48) bounds them. Gaps a synthesis named
(`unknowns`) and the claims of options a human added become supporting needs with their own
queries. Each option a human added gets its own claim need up to `research.max_claim_needs`
(25); gap needs are capped separately by `research.max_targeted_needs` (2). An option the claim
cap leaves out is named in the limitations, and the Jev-call budget may still trim needs (the
budget reserve: design docs, "As built round E").

A need is `satisfied` only if Jev also judges that the kept evidence **answers** the need's
question (one `answers.<need>` question per satisfied need, inside the existing assess call,
so no extra Jev call). Evidence that is on topic but does not answer leaves the need `partial`
with a limitation: `research.answer_threshold` (0.7) sets the bar and
`research.answer_aware_coverage` (`true`) switches it off.

### Step 3 - Prepare entity meanings, write the task and start the run

Prepare the local entity index for the repository and config you will use:

```bash
python -m kernel entities build --repository-root C:/Users/me/leafcutter
```

Rebuild after changing canonical source files or source configuration. This is explicit
maintenance; a run does not rebuild or search the repository before intent if the index is
missing or stale. It records limited coverage and continues to intent. See the
[context guide](supply-and-evaluate-kernel-context.md) for bounds, provenance and evaluations.

The goal travels as data, never on a command line. Write a `TaskInput` JSON file and pass it with
`--input-file`, or pipe it on stdin (`-` or no flag reads stdin). `repository_root` is an absolute
path; `read_roots` is optional. The goal may contain up to 16,000 characters, preserved verbatim.

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

For caller context, enrichment limits, saved snapshots and the isolated or live evals, see
[How to supply and evaluate kernel context enrichment](supply-and-evaluate-kernel-context.md).

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
`trace_refs.trace_url` are in the envelope (`usage_summary.usage` has one row per provider and
model; `report.md` repeats the trace link). `gaps` lists capability gaps the run recorded;
`gaps` as a command aggregates them across runs, one row per deduplicated need:

```bash
python -m kernel gaps --json
```

Each row has `gap_type`, `occurrence_count`, `fallback_outcome`, `build_opportunity` and the closest
capabilities with the reason each one was excluded (`candidate_exclusions`). Declined requests
(`permission`, `out_of_domain`) are never build opportunities. A blocked run's report says why it
stopped, what the kernel can do and how to rephrase. Cancel a
run with `python -m kernel cancel --run-id <id> --actor human:<id> --json`.

### Step 7 — Install the `/leafcutter` skill for Claude Code

The skill is transport only: it forwards the goal, relays questions and does exactly the host
work requested. Install it into a workspace's skills directory (the command writes
`<target>/<name>/SKILL.md` only and refuses to overwrite a different file without `--force`):

```bash
python -m kernel install-skill --target-dir <workspace>/.claude/skills --name leafcutter --json
```

`--repository-root <repo>` (default: this checkout) and `--workspace-id` are written into the skill,
so a session started in another folder still scopes the kernel to that repository. For Codex add
`--host codex`: [how to run the kernel from Codex](run-the-decision-kernel-from-codex.md).

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

- [How to inspect kernel traces with the Langfuse MCP server](inspect-kernel-traces-with-langfuse-mcp.md); [how to file approved decisions and reuse them as precedent](file-and-reuse-decisions-with-the-kernel.md)
- [Decision kernel container overview](../architecture/components/decision-kernel.md)
- [V0 demo and run report](../analysis/2026-10-01-decision-kernel-v0-demo-report.md)
- [Documentation Index](../INDEX.md)
