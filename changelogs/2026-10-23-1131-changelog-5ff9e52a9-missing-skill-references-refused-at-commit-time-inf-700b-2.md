---
title: "Changelog 5ff9e52a9 — missing-skill references refused at commit time (INF-700b-2)"
date: "2026-10-23"
time: "11:31"
type: manual
components: 
  - commit_guardian
  - skill_registry
summary: "Commits are now blocked when a package template refers to a skill that does not exist, instead of that mistake only being caught later by the build in CI."
description: "The check-agent-registry commit hook now also runs when any package template (templates/**/*.md, including skills and commands) is staged, and refuses one that names a nonexistent skill, naming the file and the skill; previously only agent templates were checked at commit time (CI build already refused them). A consumer project own templates/ are not checked. The standalone scripts/check_skill_refs.py diagnostic now uses the same verdict as the build and fails, naming the registry, on an unreadable, malformed or empty registry; a missing registry is tolerated. Adds tests covering INF-700b-2 and a hook scope section in docs/pre-commit-hooks.md."
commits: 
  - 5ff9e52a9
breaking: false
---

## Entry
