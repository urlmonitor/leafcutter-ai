---
title: "Kernel: change requests go to the host as recorded missing-process requests, then a process-mining step records what the host decided and did"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: true
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - intake
  - capability-gaps
  - process-mining
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# Kernel: change requests go to the host as recorded missing-process requests, then a process-mining step records what the host decided and did

## Actor / Goal
In order to grow the colony from real work instead of refusing it, we need a request the kernel cannot serve natively (implementing, editing, fixing) to be recorded against the matching missing-process request and handed to the host LLM to carry out. When the host is done, a process-mining step asks the host which decisions it took and which steps it performed, and that account is stored with the missing-process request.

## Context
- **Today, intake refuses these requests.** It classifies a change request as `out_of_scope_write`, ends the run `blocked`, and records a `permission` gap.
  - Run `run-10f61b05cd9743d8` (2026-10-02) shows this.
  - The goal there was a question about a fix, "How should unit_tests/... be fixed", which was also misclassified as a change request.
- **The user's direction (2026-10-02):**
  - Don't refuse.
  - Map the request to the existing missing requests (capability-gap records with `gap_key` and `occurrence_count`).
  - Pass the work to an LLM that takes it.
  - Once that LLM is done, run a process-mining LLM that asks it which decisions it took and which steps it performed, and store the answer with the missing-process request.
- **Related decisions:**
  - ADR-056: capability gaps drive what gets built next, and paths gain evidence only from verified outcomes.
  - ADR-054: process knowledge matures from LLM-guided to workflow.
  - ADR-060: the kernel itself stays read-only. The host makes the change, and the kernel records.

## Scope (no ACs, by user decision; details decided through the kernel when built)
- **Intake:**
  - A question about how to change something stays a decision or evidence request.
  - Only an actual request to make a change becomes a change request.
  - A change request is matched to an existing gap (same `gap_key`) or creates one, and its occurrence count increments.
- **Host handoff:** a host-work packet asks the host to carry out the change under its own permission controls. The kernel never writes.
- **Process mining:** after the host reports done, the kernel issues a host-work packet with a fixed interview. The interview asks for the decisions taken (with reasons), the steps performed in order, the tools and commands used, and the outcome. Its answer is stored with the gap record as host-reported evidence, together with run and trace ids.
- **Store schema:** a schema for the stored process account, so later runs can propose a capability or a workflow from repeated accounts.
- **ADR:** amend ADR-053/ADR-056, or write a new ADR, for the handoff-and-mine loop.

## Out of Scope
- Promoting a mined process into a registered capability (later stage).

## Comments
