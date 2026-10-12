---
title: "Any real workflow file is accepted as a caller in an agent's spawned_by"
date: "2026-09-28"
time: "18:00"
type: manual
components: 
  - agent_registry
  - commit_guardian
summary: "The registry validator and the spawn-consistency hook used to accept only two external callers by name, user and finalize-feature.js, so every other workflow (such as fast-lane-ship.js) was rejected as an unknown agent. Both now share one rule: a spawned_by entry is an external caller when it is user or the filename of a workflow that really exists under templates/workflows-js/. A made-up .js name is still rejected, and a new workflow needs no code change."
description: "Builds INF-600k-1. New templates/scripts/commit_guardian/agent_spawn_external_callers.py (is_recognized_external_caller) is the single definition; registry_validator loads it from the tracked source through the new scripts/commit_guardian_module_loader.py (scoped importlib load, deployed copy only as a fallback, a loud ImportError otherwise), so a fresh clone builds and the consumer registry check never swallows the failure into a pass. The spawn-consistency hook finds the package through _resolve_root.resolve_package_root, moved out of check_agent_registry.py so both hooks share it; it warns and falls back to the project root when no manifest exists. _resolve_root now derives the deploy root from the nearest commit_guardian ancestor, so hooks nested in commit_guardian/hooks/ resolve like top-level ones. To stay inside the size ratchet honestly, the spawn-bidirectionality checks moved to scripts/spawn_bidirectionality_validator.py and the card mermaid parser to templates/scripts/commit_guardian/card_mermaid_parser.py (registry_validator.py 708 to 650 content lines)."
commits: []
breaking: false
---

## Entry

An agent's registry entry can now name any real workflow as the thing that
starts it. Before, only two callers were accepted by name, so a new
workflow such as the fast lane was rejected as an unknown agent.

The registry validator and the commit check now follow one shared rule:
the direct user trigger, or a workflow file that really exists. A name
with no workflow behind it is still refused.
