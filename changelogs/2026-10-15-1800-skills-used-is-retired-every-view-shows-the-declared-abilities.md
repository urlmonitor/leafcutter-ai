---
title: "skills_used is retired: the registry carries one derived abilities list and every view shows exactly what an agent declares (AR-400 slice 2b-ii)"
date: "2026-10-15"
time: "18:00"
type: manual
components: 
  - agent_registry
summary: "The agent registry now carries a single derived abilities field, skills_invoked, regenerated from each agent's own skills: declaration; skills_used is retired, removed from every record and the schema, and refused by the registry validator and the build if it reappears. The briefing, build validation, architecture diagram, knowledge graph, agent cards and done-verdict all show exactly the declared abilities, and the one-time migration helper is removed."
description: "The transform hook (templates/scripts/commit_guardian/_agent_ability_sync.py) writes only skills_invoked - the declared grants with their mode, condition and provided_by marking, plus preserved descriptive-only entries - and drops skills_used; the regenerated config/agent_registry.json has no skills_used left. registry_validator refuses any entry carrying skills_used (even an empty list) as a retired field that is regenerated from the declaration and must not be authored, which stops the build. Four specialists whose abilities lived only in skills_used (business-analyst, it-po, live-surface-tester, user-surface-smoker) now show them in their briefing and validation, and fourteen that had only skills_invoked now appear in the architecture diagram and the knowledge graph (whose agent-to-skill edge keeps its skills_used label). The diagram gives every specialist a node; agent cards read the template's own declaration with mode and condition; each view reports how many specialists it examined. scripts/migrate_agent_abilities.py (the one-time AR-300 migration) is deleted and the AR-300c tests that ran it now run the transform hook. The registry schema, the frontmatter and registry references, the authoring how-tos and the add-agent / add-skill skills describe one derived field, so new agents are no longer told to write skills_used. Six agent cards are regenerated."
breaking: false
---

## Entry
