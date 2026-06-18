---
title: "Changelog EPIC-Oneagenthandlesboththelookandthecodefor — 2026-06-18"
date: "2026-06-18"
time: "11:31"
type: manual
components: 
  - frontend_coding
  - build_pipeline
  - agent_registry
  - skills_system
  - supervisor_system
  - documentation_system
  - testing_quality
summary: "Unified the frontend-coder agent with the frontend-design skill so adopters get design principles built in automatically, without installing a separate skill."
description: "18 tickets across 1 PR (#116, squash SHA 8f360b3). Categories: Features (embed design principles, deprecate skill, migration logic, build pipeline skip, onboard wizard removal), Tests (5 LLM trigger tests), Documentation (upgrade guide, how-to guide, reference capabilities doc, ADR-005 + ADR-001 updates, dispatch topology diagram)."
pr: 116
adrs: 
  - ADR-005-frontend-coder-agent
  - ADR-001-self-hosting-boundary
diagrams: 
  - docs/architecture/agent_delivery_workflows.md
commits: 
  - 8f360b3
breaking: false
---

## Entry
