---
title: "EPIC: Prompt-Assembly Hardening — phase agents get correct prompts by construction"
type: epic
status: in_progress
components:
  - supervisor_system
  - ticket_creation_pipeline
  - llm_authoring
created: 2026-07-08
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
---

# EPIC: Prompt-Assembly Hardening

## Goal

In order to stop phase agents receiving prompts that are missing the knowledge they
need, we make the prompt correct **by construction** — each information piece has one
owning channel and arrives automatically — so a single dispatch can no longer emit a
batch of avoidable defects.

## Context

An audit of a `python-coder` dispatch prompt (for `EPIC-Phase1ReadyHardening/04_HookParityCheck`)
found ~15 defects: wrong reference-file path, fictional hook-registration schema, wrong
sign-off skill path, a fail-open/`re-raise` error-handling contradiction, and
phantom-test-inviting AC wording. Root cause via the **Agent Knowledge Plane**
([docs/architecture/agent_knowledge_plane.md](../../../../docs/architecture/agent_knowledge_plane.md)):
the deterministic dispatcher `templates/workflows-js/build-ticket.js` emits a thin
prompt (phase name + ticket_path + files_touched only), so the missing task-specific
detail was hand-typed off-channel, drifted, and produced the defects.

The fix reuses the **ADR-004 pattern** (schema-validated section authored once by a
planning agent, enforced by hook/supervisor/template) applied to two channels:

- **Channel 6 (agent template/skill)** owns portable HOW-knowledge — Layer A.
- **Channel 8 (ticket body)** owns task-specific WHAT-knowledge — Layer B.

All acceptance criteria live in the AC store under
[docs/acceptance-criteria/build-orchestration/BO-2000-correct-prompts-by-construction/](../../../../docs/acceptance-criteria/build-orchestration/BO-2000-correct-prompts-by-construction/)
(L0 `BO-2000`, five L1s `BO-2000a`..`BO-2000e`, 34 leaf ACs).

**Layer A (BO-2000a, BO-2000b) is already implemented** in this session — the
`_signoff_block.md` and `python-coder.md` template edits have landed in the working
tree. Tickets 01 and 02 add the test coverage that verifies those edits. **Layer B
(BO-2000c, BO-2000d, BO-2000e) is pending** implementation in tickets 03–05.

## Sub-tickets

| # | File | Covers | Layer | Status |
|---|------|--------|-------|--------|
| 01 | [01_signoff_block_protocol.md](./01_signoff_block_protocol.md) | BO-2000a (+ 8 leaves) | A (impl done) | `[ ]` |
| 02 | [02_python_coder_craft.md](./02_python_coder_craft.md) | BO-2000b (+ 7 leaves) | A (impl done) | `[ ]` |
| 03 | [03_implementation_notes_emission.md](./03_implementation_notes_emission.md) | BO-2000c (+ 6 leaves) | B | `[ ]` |
| 04 | [04_package_surface_spec_schema.md](./04_package_surface_spec_schema.md) | BO-2000d (+ 4 leaves) | B | `[ ]` |
| 05 | [05_test_requirements_guard.md](./05_test_requirements_guard.md) | BO-2000e (+ 3 leaves) | B | `[ ]` |

## Out of Scope

- Remediating the shipped `check_hook_parity.py` implementation in
  `EPIC-Phase1ReadyHardening` (tracked separately).
- Fattening the deterministic dispatch prompt beyond the single "read the ticket
  first" pointer — the design intent is a thin dispatch (BO-2000c).

## Risk & Safety

- Touches money? No.
- Touches data? No — edits agent templates, the ticket generator, the AC schema, and
  the dispatch/supervisor. All changes are additive and behind existing gates.
- Reversibility? Fully reversible via git; `main` is PR-only so every change lands
  through review.
