---
title: "Kernel: the kernel skill follows the same build path as other skills (Claude Code and Codex)"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: true
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - build
  - skill
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# Kernel: the kernel skill follows the same build path as other skills (Claude Code and Codex)

## Actor / Goal
In order for the whole team to use the kernel from any PC where the repository runs, we need the kernel skill to be produced and installed the same way as every other Leafcutter skill: from source through `build.py` to the hosts' skill folders. Today it is installed by hand with `python -m kernel install-skill`.

## Context
- **User requirement (2026-10-02):** "leafcutter shall be used by the whole team and from any PC where the repo runs", and "in future it must follow the same path as other skills".
- **Interim placement:** `dec-73b6db1907adc960` placed the Codex skill in the workspace root on one PC. The user said that placement is only for now.
- **The conflict to settle first** is with the earlier decision that the kernel lives in leafcutter-ai only and is not shipped to adopters. `build.py` copies `templates/skills/*` into adopter projects. "The same path" must therefore either:
  - keep the kernel skill to leafcutter-ai's own build, for example a build target or flag limited to this repo; or
  - change the adopter decision.

  That choice needs a recorded decision (and an ADR) before code.
- **The same path needs:**
  - a portable command, with no machine paths: today's install renders `C:/Users/...` paths;
  - Codex output at `.agents/skills/` (see `config/codex_agent_compatibility.v1.json`);
  - Claude Code output at `.claude/skills/` via the `.leafcutter/skills/` shim;
  - a portable equivalent of the Codex `prefix_rule` and the Claude Code `allowed-tools`.

## Scope (to be refined after the decision)
- Decide: leafcutter-ai-only build target, or shipping to adopters.
- Move the skill sources into the build pipeline's skill path for both hosts, with a portable command line.

## Out of Scope
- The interim install (`TICKET-20261002-KernelCodexSkill`).

## Comments
