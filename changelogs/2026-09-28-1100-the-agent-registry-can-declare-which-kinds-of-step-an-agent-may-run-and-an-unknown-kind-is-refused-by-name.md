---
title: "The agent registry can declare which kinds of step an agent may run, and an unknown kind is refused by name"
date: "2026-09-28"
time: "11:00"
type: manual
components: 
  - agent_registry
summary: "Registry entries can now carry an optional step_kinds list (reads_store, changes_store, changes_repository, publishes). The schema is the only place the kinds are written; validate_agent_registry reads them from it at run time, rejects an unknown or repeated kind naming the kind and the agent, and fails closed when the schema cannot be read. This is the field the fast lane's structural check will use to decide which agent may run which step."
description: "Builds BO-2400a-1-iii. config/agent_registry.schema.json defines step_kinds as an optional array of unique enum values. The new scripts/step_kinds_validator.py holds the shared reader get_agent_step_kinds (absent or [] means no kinds, re-exported from registry_validator for BO-2400f-5-ii) and check_step_kinds, wired into validate_agent_registry, which both build.py --validate-only and the commit-time hook call. To make room without growing the over-limit registry_validator.py, validate_verification_flags moved verbatim into scripts/registry_verification_flags.py (746 to 727 content lines). No registry entry declares step_kinds yet; that is BO-2400a-1-i. The commit-time hook still cannot find the package in this repository (KI-CG-20260928, fixed by GE-113c-1-vi)."
commits: []
breaking: false
---

## Entry

An agent's registry entry can now say which kinds of step it is allowed to
run: reading the criteria store, changing it, changing the repository, or
publishing. The fast lane will use this to decide which agent may run which
of its steps.

The allowed kinds are written in one place, the registry schema. A kind that
is not in the schema, or one listed twice, is refused with the kind and the
agent named. If the schema cannot be read, validation fails rather than
letting every kind through.
