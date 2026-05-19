---
title: "Disambiguate build-feature skill name collision complete"
date: "2026-05-19"
time: "18:00"
type: ticket_completion
components: 
  - build_system
summary: "Renamed build-feature ops-notes skill and added internal: true flag to eliminate skill panel name collision."
description: "Renamed the build-feature knowledge skill to build-feature-ops-notes and marked both it and build-single-ticket as internal: true in their SKILL.md frontmatter and skill_registry.json. Updated skill_registry.schema.json to accept the new field. Added 6 unit tests."
commits: 
  - 5c439ad
  - e84c870
  - ec63f91
ticket: "TICKET-20260519-disambiguate_build_feature_skills"
---

## Entry
