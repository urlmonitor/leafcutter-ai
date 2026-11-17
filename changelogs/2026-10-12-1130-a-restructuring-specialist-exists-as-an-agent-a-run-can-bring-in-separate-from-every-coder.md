---
title: "A restructuring specialist exists as an agent a run can bring in, separate from every coder"
date: "2026-10-12"
time: "11:30"
type: manual
components:
  - infrastructure
  - agent_registry
summary: "A new agent, restructuring-specialist, is registered under its own id and role, with its own template, so a run that is refused for complexity or file size can bring in a party that is not the coder who wrote the change. It applies the complexity-reduction skill only when the demand is about complexity."
description: "Adds restructuring-specialist to config/agent_registry.json (role restructuring, never coding; empty spawn allowlist; requires_verification and sign-off on) with templates/agents/restructuring-specialist.md, a docs/agents/README.md row and a generated agent card. The agent returns a machine-readable skills_applied field and one of three endings: demand met, attempted but short, could not act. Two eval rows are registered for it in scripts/evals/agent_eval_config.json (a complexity demand that must report complexity-reduction, and a file-size demand that must not), with triggers limited to the agent's own files. The eval trigger test now lists the fourth agent. Wiring the specialist into the build drivers belongs to BO-3800b-3; the /code-refactoring-specialist command stays a human surface."
commits: []
breaking: false
---

## Entry

A run that is refused because a function is too complex, or a file too long,
now has an agent it can bring in to fix that: the restructuring specialist.
It is a different party from every coder, so the change is not restructured
by the same agent that wrote it.

The specialist picks its method from the demand. For a complexity demand it
applies the complexity-reduction skill and says so in its report. For a
file-size demand it does not. Its report lists the skills it applied in a
field the run can read, and ends in one of three outcomes: demand met,
attempted but short, or could not act.

No run engages it yet. Connecting it to the build drivers is the work of
BO-3800b-3.
