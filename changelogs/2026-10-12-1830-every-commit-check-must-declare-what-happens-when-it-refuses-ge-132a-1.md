---
title: "Every commit check must declare what happens when it refuses (GE-132a-1)"
date: "2026-10-12"
time: "18:30"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
summary: "Registering a new commit check without a remedy declaration is now refused; the 48 checks that had none are on an excused list that can only shrink."
description: "check-hook-parity gains a remedy-declaration leg. Every hooks_manifest member with tier judgment and stage pre-commit must have a rules[] entry with a disposition in templates/scripts/precommit-autofix.json, or be on hook_parity.undeclared_remedy_baseline in commit_guardian.json. Three refusals, each naming the hook and its fix: a check with no declaration; an addition to the excused list (compared against HEAD and every MERGE_HEAD); a declaration for a check that is not registered. Removing the excused-list key once a parent carries it is also refused. The check's trigger now includes precommit-autofix.json, so a commit touching only the declarations is judged. One shared loader, _remedy_declarations.load, reads the project's local table and falls back to the package seed for any hook it does not declare, so existing installs see the new declarations. Unreadable or malformed input (skills_config.json, the routing table, or an existing canonical manifest) is reported as could-not-check with exit 2. In a consumer install, where the package's canonical manifest is absent, the leg says it is not applicable. In precommit-autofix.json the stale check-docstrings rule is removed, check-ac-limits is renamed check-ticket-ac-limits, and blocking_hook_ids shrinks to five ids; the precommit-autofix skill's Step 4 and the safety-net test match. Reference: docs/reference/remedy-declarations.md."
commits: []
breaking: false
---

## Entry
