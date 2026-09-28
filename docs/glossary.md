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
