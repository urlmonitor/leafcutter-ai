---
title: "A hand-off entry already covered by 'every ticket-phase agent', or listed twice, now stops the build; AR-400 is complete"
date: "2026-10-21"
time: "18:00"
type: manual
components: 
  - agent_registry
  - build_orchestration
summary: "A specialist's spawn_allowlist that names an agent which __ticket_phase_agents__ already covers, or names any entry twice, is now a refusing error. The error names the specialist, the entry and what covers it. Before, it was a warning that never failed. The validator, the build and the commit hook report the same line, read from the specialist's own declaration and never the registry copy. The self-description proposer now proposes a skills: declaration change using the same instruction rule the build checks, instead of editing the derived registry field. The 60 stale proposal files are removed. architecture-diagram-author now grants the signoff ability its sign-off block tells it to load. The AR-400 epic is closed: every child and all seven parents are done, each parent proven by end-to-end tests of its own."
description: "scripts/agent_spawn_declaration.redundancy_findings reads the raw spawn_allowlist ('redundant hand-off entry', 'listed twice') and is called from check_skill_refs._own_declarations, so one computation serves the registry validator CLI, build.py and check-agent-registry (AR-400f-1, f-1-i, f-1-ii). spawn_bidirectionality_validator.warn_redundant_phase_agents is removed, so the build's ability and hand-off output carries no warning lines (AR-400c-4). propose_agent_self_description.py uses skill_ref_recognition.recognise and writes proposed_frontmatter.skills with no skills_invoked and no default signoff; scripts/proposals/*.yaml are deleted (AR-400e-3). docs/reference/agent-template-frontmatter.md gains a 'Redundant hand-off entries' section that quotes the printed line (AR-400f-3). The AR-400 parents AR-400 and AR-400a-f gain test contracts and 13 end-to-end tests, and AR-400 and every child are marked done. Breaking for adopters: a specialist definition with a redundant or repeated spawn_allowlist entry now stops the build; remove the entry the error names."
migration_steps:
  - "If the build reports 'redundant hand-off entry' or 'listed twice' for one of your specialists, remove the named spawn_allowlist entry; __ticket_phase_agents__ already includes every ticket-phase agent."
breaking: true
---

## Entry
