---
title: "An instruction to load an ability that does not exist now stops the build, and the noisy cross-reference warnings are gone (AR-400 slice 2b-i)"
date: "2026-10-15"
time: "13:00"
type: manual
components: 
  - agent_registry
summary: "The build and the registry validator now fail when an agent definition or a shared guide tells its reader to load an ability the package does not ship, naming the agent or guide, the ability, the file and the line; a check that examined no definitions or no guides fails instead of passing. The advisory skills_invoked cross-reference that printed some twenty warnings nobody acted on is removed."
description: "New check_skill_refs.ability_reference_verdict() runs inside registry_validator.validate_agent_registry, so its findings are returned errors: build.py stops before deploying and the validator CLI exits 1. It reuses check_skill_refs' existing reading of instruction-form references (path references used with Load/Read/python and similar, HTML comments such as DECISION HISTORY blocks excluded), now applied to every agent definition and every other template Markdown file (shared guides), and reports how many of each it examined; zero of either is a failure. An unreadable file is now an error rather than a skipped warning. check_skills_invoked_xref and its print loop are deleted, so a grant the instructions never mention prints nothing. KI-BP-007 (no gate checked skill references written in template prose) is resolved. INF-600g-3 and INF-600g-3-i, which specified the removed advisory check, still read done: the AC store's gates refuse to mark a record superseded honestly, which is filed as KI-ACS-20261015-superseded-records-held-to-forward-rules."
breaking: false
---

## Entry
