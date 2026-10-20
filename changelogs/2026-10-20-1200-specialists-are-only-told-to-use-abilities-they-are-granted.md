---
title: "A specialist is only told to use abilities it is granted, and a project can supply abilities of its own (AR-400 slices 3a+3b)"
date: "2026-10-20"
time: "12:00"
type: manual
components: 
  - agent_registry
  - skills_system
  - build_pipeline
summary: "The build now checks every instruction in a specialist's definition that tells it to use an ability. It recognises the prose and path phrasings the package uses, and stops the build when the ability does not exist, is not in the specialist's own skills: grant, differs only in letter case, or is actually another specialist to hand work to. Negations, sentences about other specialists, citations and installer steps are not instructions. A grant marked provided_by: project is supplied by the consumer project from .leafcutter/skills. The build reports such an ability once when the project lacks it and carries on, uses the project's own copy in place of a packaged one, and never overwrites or cleans it away. sql-coder's postgres and sql-test are now marked this way."
description: "New scripts/skill_ref_recognition.py (one recognise() rule) and scripts/agent_skill_ref_grants.py (the four finding kinds) replace the path-only heuristics in check_skill_refs.py. The grant compared is the definition's own skills: declaration, never the derived registry copy, so editing config/agent_registry.json neither causes nor clears a finding. The build, the registry validator and the commit hook print identical ERROR lines. New scripts/project_ability_slots.py is the single probe for project-supplied abilities at <target>/<output_root>/skills; the gate, the ability verdict, the prompt compile and the deploy all read it. An unmarked grant no longer falls back to a project-local ability. A marked grant resolves only against the project area and is reported with one of three informational lines (absent, override, packaged fallback) that never fail a build. provided_by must be 'project' (schema, declaration shape check and transform hook). The compiled abilities table marks a project copy '(supplied by the project)' and states 'not installed in this project' when it is missing. A marked id's project copy survives rebuild and --clean. A packaged fallback copy carries a .packaged-fallback hash marker. The abilities resolver moves to render_effective_skills.py. Docs: docs/reference/agent-template-frontmatter.md and the new docs/reference/specialist-ability-references.md (finding lines, own-grant rule, provided_by) and docs/how-to/supply-a-project-ability-to-a-package-specialist.md. Breaking for adopters: a project-local ability referenced by an unmarked grant now stops the build as 'ability does not exist'; mark the grant provided_by: project."
migration_steps:
  - "A specialist granted an ability that your project supplies (under .leafcutter/skills) must now mark that grant provided_by: project; an unmarked grant to an ability the package does not ship stops the build with 'ability does not exist'."
  - "Fix any 'ability exists but is not granted', 'differs only in case' or 'names an agent, not an ability' finding the build now reports in your own specialist definitions: add the grant to the specialist's own skills:, correct the spelling, or hand the work to the named specialist."
breaking: true
---

## Entry
