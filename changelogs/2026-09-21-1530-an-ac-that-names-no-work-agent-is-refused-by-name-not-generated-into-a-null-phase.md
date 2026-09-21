---
title: "An AC that names no work agent is refused by name, not generated into a null phase"
date: "2026-09-21"
time: "15:30"
type: manual
components:
  - ticket_creation_pipeline
  - build_orchestration
summary: "generate_ticket_from_ac now refuses, naming the AC id and the assigned_agent field, instead of emitting a ticket with a literal null phase or crashing inside sorted()."
description: "Quick-fix of TKT-600b-5 (branch fix/gtfa-assigned-agent-null). An acceptance criterion whose assigned_agent is null reached _build_agents_map as None. With exactly one non-canonical agent, sorted() never compared, so None flowed through and the generated ticket carried a literal 'null: needed' entry in its agents map and a '- [ ] None' row in its Sign-offs checklist; with a second non-canonical agent, sorted() raised an undiagnosed TypeError. 355 of the store's 4,138 records carry assigned_agent: null — 317 produced the silent null entry and 38 crashed. Generation now refuses at the single _build_agents_map entry point (covering both the computed and the legacy path), and both CLI paths print a diagnosed refusal naming the AC id and the field, exit non-zero, and write no ticket file. Files modified: scripts/ac_store/_gtfa_agents_inputs.py, scripts/ac_store/_gtfa_agents_map.py, scripts/ac_store/_gtfa_cli.py."
breaking: false
---

## Entry

A null `assigned_agent` is refused, not papered over. Silently dropping the work
agent would have emitted a structurally valid ticket with every gate phase wired
and nobody assigned to build it — the phantom-done shape one level up. The 355
affected records need authoring; the generator's job is to say so.
