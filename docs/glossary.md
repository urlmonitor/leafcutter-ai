---
title: Project Glossary
description: Authoritative glossary of leafcutter-ai project jargon and terminology,
  seeded by /glossary-bootstrap and maintained by the check_glossary_coverage pre-commit
  hook.
type: reference
created: '2026-07-09'
last_updated: '2026-08-18'
status: active
components: []
---
<!--
GLOSSARY AUTHORING GUIDE (invisible in rendered docs)

1. Initial population: run `/glossary-bootstrap` once after install or after a
   significant codebase merge to seed this file from the existing codebase.

2. Ongoing additions: the pre-commit hook `check_glossary_coverage.py` detects
   novel jargon in staged .md/.py/.sql files, dispatches the haiku
   `glossary-triage` agent, and automatically appends approved entries here.

3. Do NOT hand-edit to add new entries. Always go through the triage flow so
   the blacklist stays consistent with the glossary. Manual edits are only for
   correcting or refining existing entries.

4. Entry format: each term uses a ### heading followed by a definition paragraph.
   Example:
       ### candle_horizon
       The number of candles in the rolling context window used for pattern matching.
-->
# Glossary

This file is auto-maintained by the glossary-automation system.
Run `/glossary-bootstrap` to populate it after initial install or after a
significant codebase merge.

<!-- Terms are added automatically. Each term uses a ### heading. -->

### Antigravity
An AI IDE/agent runner platform supported by leafcutter-ai, alongside Claude Code. Antigravity uses standard Model Context Protocol (MCP) tool declarations rather than bespoke CLI definitions.

### ticket_frontmatter_guard
A pre-commit hook (`scripts/commit_guardian/check_ticket_frontmatter.py`) that validates every staged ticket file's YAML frontmatter against the required field schema. It enforces the presence of `requires_diagram`, `requires_adr`, `agents`, and `files_touched` fields, and verifies that the `## Sign-offs` section lists exactly those agents whose `agents:` map value is `needed`. Generated tickets (from `generate_ticket_from_ac.py`) must pass this guard before their commit is accepted.

### create-ticket.js
The `templates/workflows-js/create-ticket.js` workflow script — **retired as of ADR-012 (2026-06-16)**. It was introduced under ADR-006 (flatten the supervisor chain) to provide a flat sequential dispatch path for ticket creation. It consumed four fields from the pre-v3 business-analyst JSON contract (`routing_decision`, `open_questions`, `requires_architect_review`, `ticket_path`); the v3 business-analyst produces AC YAML instead, making all four fields undefined at runtime. No ticket file was ever produced since the v3 BA was shipped. The canonical ticket-creation path is `/plan-feature + /build-ac` (see ADR-010, ADR-012, and `docs/how-to/ticket-creation-workflow.md`).

### ticket creation pipeline
The end-to-end process for producing a ticket file from a feature request. The canonical path is `/plan-feature` (PO → BA → IT PO authoring pipeline that produces AC YAML in `docs/acceptance-criteria/`) followed by `/build-ac` (`scan_ac_store.py` selects the next ready leaf AC, `generate_ticket_from_ac.py` writes the ticket file with `implemented_by` back-link). This path enforces `depends_on` ordering and maintains full AC-to-ticket traceability. The pre-ADR-010 path via `create-ticket.js` is retired. See `docs/how-to/ticket-creation-workflow.md`.

### build_ac_store
A `build.py` deployment phase (`build_ac_store()` in `scripts/build_phases.py`) that copies the six AC pipeline scripts from the leafcutter-ai source tree into the consumer project's `.leafcutter/scripts/ac_store/` directory (the `output_root` path, not the project-root `scripts/` directory). Added in EPIC-AcPipelineDeployGaps to close the portability gap between the `ac-scanner` and `build-ac` skills (marked `portable: true` in `skill_registry.json`) and their dependency scripts. Without this phase running, the skills are deployed as SKILL.md files but their scripts are absent, causing runtime failures. See ADR-013 for the canonical definition of `portable: true`.

### io_boundary_calls
A configuration field in `commit_guardian.json` under `exception_handling` that specifies the set of external I/O function calls (e.g., `subprocess.run`, `requests.get`, `cursor.execute`, `open()`) that must be wrapped in typed `try/except` blocks in production code. The code table in `check_exception_handling.py` and this JSON spec must be kept in parity; see ADR-014 Decision 1.

### driveTicketPhases
A JavaScript loop function that orchestrates phase-dispatching for each ticket in a batch. Originally defined in `templates/workflows-js/build-ticket.js`, it dispatches each needed phase as a depth-1 `agent(agentType: phaseName)` call. In the current architecture (ADR-019), `driveTicketPhases` is inlined into `build-feature.js` to enable ticket batching at depth 0, replacing the prior pattern of dispatching a separate `ticket-supervisor` agent per ticket. `build-ticket.js` is the canonical twin and retains the reference implementation of the loop.

### ac_coverage_resolver
The single, importable, side-effect-free coverage-resolution module (`scripts/ac_store/ac_coverage_resolver.py`) that the `ac-fulfillment-gate` agent template's Step 1 calls to resolve which AC(s) a ticket's `ac_traceability` frontmatter block names, and whose `compute_verdict` makes an `ok` sign-off structurally impossible when zero ACs were resolved. It accepts both the two-key `{id, path}` form the ticket generator actually emits and the previously-accepted list form (`{l2, l3, ac_path}`, see BO-201), falling back to a ticket's `source_ac` field only when the block itself yields nothing. Added under `ACD-1900b-5-i` to close a vacuous-truth gap where the gate's "every AC in the working list passed or skipped" rule was always true over an empty list. Registered in `build_ac_store`'s `deploy_map` so the deployed gate template can invoke it via its CLI. See `docs/architecture/components/ac-driven-dev.md#coverage-resolution--ac_coverage_resolver`.

### NEGATIVE_CONTROL_LIVENESS_SELFTEST_OK
A string literal marker printed to stdout by `check_negative_control_liveness.py --selftest` to indicate successful cold-load verification — proves the deployed module and all its imports load correctly in a fresh process with no file side effects. See `docs/reference/commit-guardian-negative-control-liveness.md`.

### NEGATIVE_CONTROL_RESULT
A machine-readable stdout line-prefix emitted by `check_negative_control_liveness.py` to report each hook's examination result during a negative-control liveness sweep. Format: `NEGATIVE_CONTROL_RESULT check_id=<id> state=<state> entry_point=<entry_point> demonstration=<demonstration> discrimination=<discrimination> command=<command>` — one line per hook carrying a (non-`not_applicable`) `negative_control`, examined or not. `entry_point` is the identity of the invocation actually performed (never a declared value echoed back). Part of the commit_guardian family of structured `RESULT:`-style output vocabularies alongside `check_outcome.py`'s `RESULT: <outcome>` convention. See `docs/architecture/components/commit-guardian.md`, `docs/reference/commit-guardian-negative-control-liveness.md`, and `docs/reference/commit-guardian-negative-control-liveness-record.md#stdout-contract`.

### shared_reference_layout
A session-scoped pytest fixture defined in `scripts/suite_performance/pytest_shared_reference_layout.py` and registered via `pytest.ini`'s `addopts` (`-p scripts.suite_performance.pytest_shared_reference_layout`, mirroring the `-p scripts.ac_store.pytest_ac_enforcement` precedent). It provides a single, real deployed copy of the package produced lazily, on first demand, once for the whole test run and shared cross-process-safely across every pytest-xdist worker and every read-only consumer test. Read-only tests must request this fixture instead of spawning their own `python scripts/build.py --target-dir <tmp>` subprocess; tests that mutate the package before building (e.g. `unit_tests/test_bp_900g_8*.py`) must not route onto it. See CLAUDE.md's "Tests must not spawn their own `build.py`" section and TQ-600a-1.

### get_or_produce_shared_layout
The public entry-point function (`scripts/suite_performance/_shared_layout_producer.py`, re-exported from the `pytest_shared_reference_layout` plugin module) underlying the `shared_reference_layout` fixture. Callers outside any fixture context (e.g. a plain function-scoped test) call it directly. It is cross-process-lock-safe and lazily produced: the first caller in a run triggers the real `build.py` deploy while every other caller — including callers on different pytest-xdist workers — waits and then receives the identical, fully-produced root path, exactly once per run regardless of how many callers ask. Added under TQ-600a-1.

### emit_execution_signal
A function (`scripts/suite_performance/_shared_layout_coordination.py`) that records when a shared reference layout subprocess actually executes (vs. hitting the cache), appending a JSONL event to a log file specified by `EXECUTION_LOG_ENV_VAR`. Used to verify — independently of any run's reported deploy count — that the `shared_reference_layout` fixture's production phase was genuinely reached, not skipped. TQ-600a-1-i's zero-consumer / one-consumer boundary tests observe this signal rather than the reported count, which has no instrumentation yet (deferred to TQ-600a-6). See also `worker_name()` in the same module, which attributes a signal to the pytest-xdist worker that emitted it.

### INSUFFICIENT_EVIDENCE

The explicit answer path every Jev decision specification carries for when the task or policy does not establish the facts needed to decide. It keeps an unanswerable question from being forced into a guess. See ADR-052 §8.

### NEEDS_HUMAN

Earlier discussion name for a result that needs a human answer: a preference, an authority decision or a risk acceptance. The kernel spec normalizes it to status `waiting` plus a persisted human interaction (a `human_question_request.v1`); the matching decision assessment status is `needs_human` (spec §7.6–7.7). See ADR-053.

### NEEDS_INFORMATION

Earlier discussion name for a result that lacks evidence. The kernel spec normalizes it to status `waiting` plus evidence (retrieval or research) requests; the matching decision assessment status is `needs_evidence` (spec §7.6–7.7). See ADR-053.

### NEEDS_OPTIONS

Earlier discussion name for a result whose decision options are not yet known. The kernel spec normalizes it to status `waiting` plus an options request (`options_request.v1`, served by `host.generate_options`); the matching decision assessment status is `needs_options` (spec §7.6–7.7). See ADR-053.

### NEEDS_REASONING

Earlier discussion name, grouped with `NEEDS_SYNTHESIS`, for a result whose evidence is sufficient but whose answer needs generative reasoning. The kernel spec normalizes both to status `waiting` plus a generative request (spec §7.6). See ADR-053.

### NEEDS_SYNTHESIS

Earlier discussion name for a result whose evidence is sufficient but needs synthesis by a generative model. The kernel spec normalizes it to status `waiting` plus a generative request such as `synthesis_request.v1`, served by `host.synthesize`; the matching decision assessment status is `needs_synthesis` (spec §7.6–7.7). See ADR-053.

### NO_CAPABILITY

Earlier discussion name for the case where no registered capability can serve a request. The kernel spec normalizes it to routing outcome `no_match`, a capability-gap record, and either an approved fallback or a `blocked` result (spec §7.6). See ADR-054 §5 and ADR-056 §6.

### choose_next_step

One of the operations forbidden to every host (`host.*`) operation in the Decision Kernel, alongside `edit_repository`, `approve_policy`, `change_permissions` and `run_other_leafcutter_commands`. Choosing the next process step stays with the kernel scheduler, never with the host doing the work (kernel design part 4).

### example_run_ids

Field of an aggregated capability-gap record: up to five run IDs that exemplify the gap. `load_gaps()` fills it together with `occurrence_count` and `first_seen`/`last_seen` (kernel design parts 2 and 4, spec §14).

### fallback_on_no_match

Kernel config flag `host.fallback_on_no_match` (default `true`) that lets an approved `host.*` capability take over a request that routed to `no_match`. Fallback also requires that the request kind maps to an eligible `host.*` capability, that budget remains, and that the gap type is not `permission` (kernel design part 4).

### human_question_request

Kernel request contract `leafcutter.human_question_request.v1` for a persisted human interaction, with fields `question`, `choices`, `free_text_allowed`, `why_research_cannot_settle` and `decision_id` (spec §7). Used when work needs a human answer (the `NEEDS_HUMAN` case).

### write_if_absent

A `build_behavior` frontmatter value for templated docs: `build.py` writes the file only when it does not exist yet, so a human-curated living document such as `docs/vision.md` is never overwritten by a later build (enforced in `scripts/build_phases_docs.py`).

### Decision Kernel

The resumable runtime in leafcutter-ai (package `kernel/`) that takes a free-form engineering goal, routes it to a registered capability using Jev's bounded judgments, gathers evidence through native decision and research capabilities, hands generative or human work out as checkpointed handoffs, and ends every run in a typed terminal state with evidence and a Langfuse trace. Its capability registry starts empty (ADR-055). Not yet shipped to adopters. See `docs/architecture/components/decision-kernel.md` and ADR-052 to ADR-056.

### capability

In the Decision Kernel, the contract-driven unit of work that replaces the agent: an input contract, applicable policies, evidence preparation, decisions, an execution strategy, verification and a typed result. A capability may contain no model, one model call or a bounded worker loop, and callers do not depend on which. Every capability runs the same lifecycle: PREPARE → PRE-CHECK → COMPILE INVOCATION → EXECUTE → POST-CHECK → ACCEPT, REPAIR, REQUEST INFORMATION or ESCALATE (ADR-052 §4; see `docs/architecture/diagrams/decision-kernel-flows-capability-lifecycle.md`). See ADR-052.

### Jev

TypeSafe's bounded decision model (jev-1.13), used through `langchain-typesafe`. Jev receives a state and typed questions (kinds `noul`, `choice` and `score`) and returns bounded answers with probabilities. In the Decision Kernel it answers semantic questions against known options and criteria, such as routing and criterion assessment; it does not invent criteria or generate content. See ADR-053.

### invocation compiler

The deterministic code in the Decision Kernel design that builds a model's focused instructions from the capability definition, applicable policies, task, retrieved evidence, approved decisions and output contract. It is ordinary code, never an LLM that improvises prompts, so prompts become versioned compiled outputs rather than the source of truth. See ADR-052 §3.

### decision specification

A small, bounded, testable instruction for a Jev decision: it evaluates only the supplied criteria and has an explicit `INSUFFICIENT_EVIDENCE` path. It replaces open-ended judgement prompts such as "is this implementation good?". See ADR-052 §8.

### process maturity level

One of five levels describing how well an engineering process is understood: 0 Unknown, 1 LLM-guided, 2 Policy-guided, 3 Workflow-guided, 4 Deterministic. The kernel uses the most mature representation available, and knowledge is promoted upward as it recurs. Not every capability reaches Level 4. See ADR-054 §2.

### promotion rule

The ADR-054 principle to convert repeated LLM reasoning into policies and repeated policies into workflows whenever practical, moving process knowledge to cheaper, more reliable forms. Promotion is proposed from recorded outcome evidence and activated only after review (ADR-056). See ADR-054 §3.

### capability gap

A recorded observation that the kernel lacked a suitable native capability: a request that routed to `no_match`, or work only a `host.*` fallback could do. Gap types are `unsupported`, `host_only`, `provider_failure`, `permission` and `ambiguous`. Observations are deduplicated by `gap_key` and aggregated (`occurrence_count`, `example_run_ids`). Repeated gaps are the colony's pressure signal for new capabilities. See ADR-054 §5 and ADR-056 §6.

### colony memory

The execution statistics and decision outcomes the Decision Kernel records from capability invocations and important decisions. Verified outcomes strengthen a path, wrong decisions and dead ends weaken it, and usage alone is never evidence of correctness. See ADR-056 and `docs/vision.md`.

### stigmergy

Coordination without a central planner through traces left in a shared environment, as when ants follow each other's pheromone trails. In Leafcutter, run traces and decision outcomes are those traces, and routing and promotion read them. See ADR-056 §1 and `docs/vision.md`.

### pheromone trail

Colony-model name for a learned routing preference built from verified outcomes (post-check passed, tests green, human accepted). Trails fade through evaporation and may rank and propose but never legislate: turning a trail into a policy or workflow stays a reviewed step. A dead-end trail is a failed path or a decision later proven wrong. See ADR-056.

### evaporation

The rule that colony-memory evidence is scoped to the policy, template and model versions that produced it and decays over time, so a record made under an old version carries little weight once a new one exists. A fading trail can lead to a proposal to retire a capability. See ADR-056 §3.

### performance store

ADR-056's name for the store of compact routing statistics that a learning evaluator derives from Langfuse traces and scores. ADR-057 realises it as the optional PostgreSQL **colony memory store** behind the `ColonyMemory` port. The kernel reads these statistics and never queries Langfuse directly, so observability data does not become operational state. See ADR-056 §8 and ADR-057.

### confidence calibration

How closely Jev's stated confidence matches observed accuracy: answers given at .95 should be right about 95% of the time. ADR-056 tracks calibration per decision type, and a poorly calibrated type is first read as a deficient decision basis (the policy or ADR behind it), not necessarily a Jev fault. See ADR-056 §4.

### policy gap

A proposal to change a decision rule (a policy, checklist or ADR) because recorded outcomes show it repeatedly produces wrong decisions, usually because a criterion or evidence is missing. It comes from decision-rule reinforcement in Stage 4 and is activated only after review. See ADR-056 §5.

### scout

Colony-model name for research and capability-gap handling: the work that goes where no capability exists yet. At founding the general-purpose model does scout work through approved fallback, and repeated gaps for the same need are the signal to build a specialized capability. See ADR-056 §6 and `docs/vision.md`.

### LEAFCUTTER_COLONY_DB_URL

Optional variable in the project-root `.env` holding a PostgreSQL connection URL for the colony memory store. When it is set, and `LEAFCUTTER_SELF_LEARNING` is not `false`, self-learning is enabled. Any Postgres URL works, including a Supabase project's Postgres connection string; the Supabase API is not used. Without it, Leafcutter works the same, just without cross-run learning. See ADR-057 §4.

### LEAFCUTTER_SELF_LEARNING

Optional opt-out in the project-root `.env`: `LEAFCUTTER_SELF_LEARNING=false` keeps self-learning off, so the kernel uses `NullColonyMemory`, even when `LEAFCUTTER_COLONY_DB_URL` is set. Otherwise enablement is inferred from the URL. See ADR-057 §4.

### JEV_API_KEY

The Jev credential, kept in the project-root `.env` next to the Langfuse keys (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`). The Decision Kernel needs it to call Jev.

### NEEDS_CONTEXT

A sentinel choice in the Decision Kernel's routing question (`kernel.route`). When Jev selects it, the request lacks the information needed to pick a capability safely: the routing outcome is `insufficient_context` and the kernel asks for clarification instead of routing. It sits alongside the `__NONE__` sentinel for "no matching capability". See `kernel/scheduler/routing.py`.

### PROJECT_CONTEXT

A `PROJECT_CONTEXT.md` file in an agent, skill or component directory that supplies project-specific context to legacy Leafcutter agents at spawn time. It is one of the channels of the agent knowledge plane. See `docs/architecture/agent_knowledge_plane.md`.

### assemble_context_bundle

A pure function in `scripts/injection_builders.py` that assembles the layered context bundle for agents dispatched by the fast-lane build: architecture docs, acceptance criteria, prior tests and working changes, ordered from most stable to most volatile so the stable prefix stays byte-identical for prompt caching. Exposed as the `assemble-bundle` CLI subcommand. See `docs/reference/fast-lane-prompt-caching.md`.

### agent_knowledge_plane

The architecture reference (`docs/architecture/agent_knowledge_plane.md`) for how legacy Leafcutter agents receive context at spawn time through the harness's injection channels, such as `CLAUDE.md`, auto-memory, the glossary, skills, agent frontmatter, folder `README.md` and `PROJECT_CONTEXT.md`. The Decision Kernel's context map contrasts with it (`docs/architecture/diagrams/decision-kernel-context-map.md`).

### agent_knowledge_system

The architecture reference (`docs/architecture/agent_knowledge_system.md`) for how legacy Leafcutter agents persist learnings after work completes. It is the persistence-side complement to `agent_knowledge_plane`.
