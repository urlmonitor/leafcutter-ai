---
title: "Agents read package config from where the build deploys it, so documentation-expert no longer halts in consumer projects"
date: "2026-10-22"
time: "10:00"
type: manual
components:
  - build_pipeline
summary: "Agent, skill and workflow templates that told the agent to read a package config file (doc_types.json, paths.json, agent_registry.json, diagram_types.json, guardrail_gates.yaml) named it as config/<file> or leafcutter/config/<file>. A consumer install has these files only under .leafcutter/config/, so documentation-expert's mandatory pre-flight read failed and the agent stopped before writing anything (seen in DIAGraph on v15.0.9, ticket INF-120c-3). The templates now write these paths as {{config.output_root}}/config/<file>, which the build resolves for every layout."
description: "BP-900b-4. Fixed templates: documentation-expert, it-po, ticket-supervisor, architect-review agents; ticket-authoring and building-epics skills; the documentation workflow/command. New test unit_tests/build_guards/test_bp_900b_4_prompt_config_reads.py scans every compiled prompt in the shared consumer-layout build and fails when a read line names a deployed package config file at a path that does not exist in the install."
commits:
breaking: false
---

## Entry

In projects that install leafcutter, the documentation agent could not find its own settings
file and stopped every documentation task before it began. Agents now look for their settings
where the install actually puts them, so documentation tasks run again in every project.
