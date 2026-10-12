---
title: "Decision Kernel V0 Design - Part 1 of 6: Stage 0 Mapping and Package Layout"
description: "Implementation design for the Leafcutter decision kernel (Revision 3 spec, Stage 0 + Stage 1 MVP): the Stage 0 mapping of existing repo assets to spec interfaces, verified environment and live smoke evidence, package location, full module map with phase ownership, and the deliberate deviations from the specification."
type: explanation
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - decision_kernel
---

# Decision Kernel V0 Design — Part 1 of 6: Stage 0 mapping and package layout

This series is the implementation plan for
[TICKET-20260930-KernelBootstrapV0](../../tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md).
The specification is **Revision 3**
([part 1](2026-09-30-leafcutter-kernel-spec-rev3.md) … [part 8](2026-09-30-leafcutter-kernel-spec-rev3-8-audit-links-handoff.md)).
Where this design and the spec disagree, the "Deliberate deviations" section below explains why.
Coder agents implement one phase at a time. Each phase owns the files listed for it in
[part 6](2026-09-30-decision-kernel-design-6-tests-phases-risks.md).

## Series map

| Part | File | Covers |
|---|---|---|
| 1 | this file | Stage 0 mapping, verified environment, package location, module map, deviations |
| 2 | [contracts, registry, config](2026-09-30-decision-kernel-design-2-contracts-registry-config.md) | Pydantic contracts, schema catalog, capability registry and adapter, config, secrets |
| 3 | [kernel scheduler](2026-09-30-decision-kernel-design-3-kernel-scheduler.md) | KernelState, LangGraph node map, scheduling algorithm, guards, persistence, resume, cancel |
| 4 | [Jev and capabilities](2026-09-30-decision-kernel-design-4-jev-and-capabilities.md) | Jev port and adapter, decision graph, research graph, retrieval adapter, host operations, gaps |
| 5 | [client and observability](2026-09-30-decision-kernel-design-5-client-observability.md) | Application service, CLI and RunEnvelope, `/leafcutter` skill, Langfuse, redaction, MCP |
| 6 | [tests, phases, risks](2026-09-30-decision-kernel-design-6-tests-phases-risks.md) | Test plan, phase plan with file ownership, coding conventions, risks |

## Verified environment (Stage 0 evidence, 2026-09-30)

Installed in `C:\Users\Hendrik\Code\leafcutter\.venv` (Python 3.14.2) and pinned `==` in
`requirements-dev.txt`. CI runs Python 3.13, and every pin declares `Requires-Python >=3.10`.

| Package | Version | Note |
|---|---|---|
| langgraph | 1.2.12 | latest on the index; brings langgraph-checkpoint 4.2.0, langchain-core 1.6.4 |
| langgraph-checkpoint-sqlite | 3.1.1 | `AsyncSqliteSaver` (aiosqlite 0.22.1) |
| langchain-typesafe | 0.0.1a3 | pre-release, `@beta` (emits `LangChainBetaWarning`) |
| langchain | 1.4.3 | required by `langfuse.langchain.CallbackHandler` |
| langfuse | 4.16.0 | OpenTelemetry-based v4 SDK |
| pydantic | 2.13.5 | contracts |

Live smoke tests used synthetic, non-sensitive input only. The scripts stayed in the session
scratchpad and were not committed.

- **Jev through `TypeSafeClassifier`.** One Choice question (`decision`, `research`, `__NONE__`,
  `__NEEDS_CONTEXT__`) and one Noul question.
  - The service returned `model="jev-1.13.0"` for the `jev-latest` alias, with a request id.
  - 459 input and 69 output tokens; latency 0.33 s.
  - Route answer: `decision` with p=0.96 and confidence 0.94.
  - The API key was passed explicitly. The class reads `TYPESAFE_API_KEY` by default, but our
    `.env` names it `JEV_API_KEY`.
- **Langfuse.**
  - `auth_check()` returned true against `LANGFUSE_BASE_URL`.
  - The run used a deterministic trace id, `Langfuse.create_trace_id(seed=run_id)`. It had one
    `agent` root observation, one custom span, and one `CallbackHandler` observation for the
    classifier.
  - Read-back through `api.observations.get_many(trace_id=…)` returned all 3 observations.
  - **The legacy `GET /api/public/traces/{id}` returns HTTP 410** for organisations created on or
    after 2026-09-16. Read-back and MCP inspection must use the v2 observations API.
  - The callback recorded the Jev call as a `CHAIN` with no usage, so the adapter must add its
    own `generation` observation (part 5).
- **LangGraph probes**, run under `LANGGRAPH_STRICT_MSGPACK=true`:
  - Pydantic models in state round-tripped through `SqliteSaver` and `AsyncSqliteSaver`, with
    `JsonPlusSerializer(allowed_msgpack_modules=[…models…])`, without warnings.
  - `interrupt(value, response_schema=dict)` resumed correctly in a **new process** via
    `Command(resume=…)`.
  - Two `Send` workers overlapped in time: 0.54 s for 2 × 0.5 s.
  - `ainvoke(…, version="v2")` returns `GraphOutput(value, interrupts)`.
- **Existing suite collection** (`pytest --collect-only` on `unit_tests/` and `tests/`):
  7058 collected, 2 errors. Both errors are pre-existing POSIX-only imports (`resource`,
  `fcntl`) on Windows. The new dependencies introduce no regressions.

## Stage 0 mapping: existing assets to spec interfaces (§15.1)

| Spec interface | What exists in the repo | Kernel decision |
|---|---|---|
| Capability registry | `config/agent_registry.json`, `config/skill_registry.json` (+ draft-07 schemas), slash commands in `templates/commands/*.md` and `templates/workflows/*.md` | **Excluded** (user decision). These describe Claude Code agents, skills and commands. They are write-capable, have no typed I/O contracts, and are shipped to adopters. The kernel reads only the new `config/capability_registry.json`, which starts empty. A legacy asset enters only through an `admission` record (part 2). |
| Glossary / components | `docs/glossary.md` (`### term`; no lookup API), `docs/components.json` (dict keyed by id) | `Scope.component_ids` is validated against `components.json`. Both are knowledge-map surfaces for retrieval. Deeper use is Stage 2. |
| Configuration | `scripts/config_loader.py` (build-time `skills_config` only): JSON defaults in `config/` + schema + project override | Same convention: `config/kernel_config.default.json` + `.schema.json`, validated by a Pydantic `KernelConfig`. No second config framework. |
| Secrets | No `.env` helper and no python-dotenv. `debugging/test_judge/judge.py::load_api_key` checks env first, then parses a `.env` file | Same pattern in `kernel/secrets.py`, with a walk-up search for `.env`. The workspace `.env` sits above the repo, and worktrees do not receive it. |
| Model clients | None shared. `judge.py` is a direct-HTTP prototype; `scripts/evals` shells out to `claude -p` | `langchain-typesafe` (spec §9.1) behind `providers/jev.py`. `judge.py` stays the reference for request/response shapes and the `uid` self-consistency trick. |
| Source / repo access | `scripts/knowledge_query.py::build_knowledge_map` (title/description substring match over `config/paths.json` surfaces; about 11.7 s for a full map). `knowledge_frontmatter_reader.py`, `adr_refs.scan`. No grep helper | Retrieval adapter = knowledge-map bridge (loaded by path, filtered by surface, cached per process) plus a bounded lexical search over allowlisted roots (part 4). |
| Logging / observability | `logging.getLogger(__name__)`; `basicConfig` only in `main()`. JSONL sinks in gitignored `debugging/logs/` | Same logger convention. Run events go to the run directory. Langfuse is new. |
| Persistence | No sqlite anywhere. `scripts/pause_store.py` keeps one JSON per run in `.leafcutter/paused_runs/` (gitignored, survives build clean) | Run root `.leafcutter/kernel/` by the same precedent, holding `AsyncSqliteSaver` checkpoints plus run records (part 3). |
| Redaction | None. `templates/skills/security-scanner/scripts/scan_secrets.py` *detects* secrets (`_RULES`, entropy) but does not mask them | New `observability/redaction.py`: exact masking of loaded secret values, reuse of `_RULES` loaded by path (with a local fallback), truncation. |
| Human pause / resume | ADR-024 substrate (`resolveGate`, `.leafcutter/paused_runs/`) in the JS workflow engine | Not reusable from Python. Its durable pending-question pattern informs the interaction ledger. |
| CLI and tests | argparse CLIs printing JSON. `pytest.ini`: `pythonpath = .`, `strict_markers`. `tests/` is a package; `unit_tests/` is not | `python -m kernel …`. Tests go in `tests/kernel/`: a `unit_tests/kernel/` package would shadow the real package. |
| Claude Code surfaces | `.claude/commands` and `.claude/skills` are gitignored build outputs of `templates/` (shipped). `/leafcutter` already exists as the knowledge hub (`templates/workflows/leafcutter.md`) | The kernel skill source is tracked in-package and installed by an explicit command. The name collision is an open user decision (part 5). |

## Package location

A new top-level package, **`kernel/`**, at the repository root.

- `build.py` deploys `templates/` and `scripts/`. A top-level package is never shipped to
  adopters, which satisfies user decision 2 with no package-boundary changes.
- `scripts/` is a flat `sys.path` script collection with no `__init__.py`. `templates/` is the
  shipped source. Neither fits an importable, packaging-ready runtime.
- `pytest.ini` sets `pythonpath = .`, so `import kernel` works in tests, and
  `python -m kernel` is the CLI.
- It is packaging-ready: the only cross-tree dependency is the knowledge-map bridge in
  `capabilities/retrieval/knowledge_map.py`, which loads `scripts/knowledge_query.py` by path
  and degrades to "source unavailable".
- Phase 0 created `kernel/__init__.py` in the same commit as the `decision_kernel`
  entry in `docs/components.json`, which `check-structural-change` requires.

## Module map

Each folder holds at most 15 non-markdown files (`check-folder-density`). Each `.py` file
targets 300 lines or fewer; the hard limit is 400 (`check-file-size`).
Pn = the owning phase (part 6).

```text
kernel/
  __init__.py            P0 version marker; P7 re-exports RunService
  __main__.py            P7 -> adapters.cli.main
  config.py              P1 KernelConfig + load_kernel_config()
  secrets.py             P1 SecretSettings + load_secrets() (.env walk-up, SecretStr)
  service.py             P1 RunService protocol + RunEnvelope builders; P7 implementation
  bootstrap.py           P7 composition root: real deps, trusted binding table; P8 adds host.* bindings
  contracts/             P1 all Pydantic contracts (part 2)
    base.py enums.py task.py evidence.py work.py capability.py decision.py
    interaction.py run.py payloads.py schema_catalog.py __init__.py
  schemas/               P1 exported JSON Schemas <schema_id>.schema.json (generated, committed)
  registry/              P1 adapter.py eligibility.py bindings.py __init__.py
  providers/             P1 base.py (JevPort + normalized answers), fakes.py (ScriptedJev)
                         P3 jev.py (TypeSafeClassifier adapter), jev_errors.py
  scheduler/             P4 state.py graph.py context.py guards.py fingerprint.py validation.py
                         P4 nodes_intake.py nodes_routing.py nodes_execution.py
                         P4 nodes_integration.py nodes_finalize.py routing_templates.py
                         P4 creates, P6 takes over: nodes_interaction.py
                         P4 creates, P9 takes over: nodes_gaps.py
  persistence/           P1 base.py (RunStore/GapStore/Artifact ports), memory.py (in-memory), __init__.py
                         P2 run_store.py checkpointer.py gap_store.py artifacts.py
  observability/         P1 tracer.py (Tracer protocol, NoOpTracer, RecordingTracer), correlation.py
                         P2 langfuse_tracer.py redaction.py spool.py
  capabilities/          P1 base.py (CapabilityExecutor protocol, ExecutionContext)
    decision/            P5 graph.py nodes.py templates.py combine.py __init__.py
    research/            P5 graph.py nodes.py templates.py __init__.py
    retrieval/           P5 repository.py knowledge_map.py sources.py terms.py __init__.py
    host/                P8 operations.py conversion.py __init__.py
  interaction/           P6 submissions.py packets.py __init__.py
  adapters/              P7 cli.py envelope.py __init__.py
    claude_code/         P7 SKILL.md install.py __init__.py
config/capability_registry.json          P1 creates empty; P5 adds all entries
config/capability_registry.schema.json   P1
config/kernel_config.default.json        P1 (every key in part 2; later phases read only)
config/kernel_config.schema.json         P1 (generated from KernelConfig)
tests/kernel/                 per phase; __init__.py in every directory (part 6)
```

## Deliberate deviations from the specification

1. **New, initially empty capability registry.** This is a user override of spec §2.1(3) and §6
   ("reuse the existing registry"). The eligibility filter, snapshot pinning and descriptor
   normalization of §6 still apply, but over `config/capability_registry.json`.
   Recorded in [ADR-055](../architecture/adrs/ADR-055-capability-registry-starts-empty.md).
2. **Skill location.** Spec §11.1 names `.claude/skills/leafcutter/SKILL.md`. In this repo that
   directory is gitignored build output, and `/leafcutter` is already the shipped knowledge-hub
   command. The source is therefore tracked at `kernel/adapters/claude_code/SKILL.md`
   and installed on request (part 5). The final name is an open user decision.
3. **JSON config, not YAML.** Spec §21 of V0 sketched YAML. Revision 3 forbids a second config
   system, and the repo convention is JSON + schema in `config/`.
4. **No console script.** The repo has no `pyproject.toml`, so the spec's
   `leafcutter run …` is `python -m kernel run …` with identical flags.
5. **Host output schemas are registered IDs only.** Spec §7.11 prefers registered IDs.
   Free-form `required_output_schema` JSON Schema from models is not accepted in V0.
