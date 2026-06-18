---
title: "Project Glossary"
description: "Authoritative glossary of leafcutter-ai project jargon and terminology, seeded by /glossary-bootstrap and maintained by the check_glossary_coverage pre-commit hook."
type: "reference"
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
