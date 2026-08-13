---
title: "Changelog ac/pattern-steward — pattern-producer ACs and files_touched enforcement"
date: "2026-08-14"
time: "01:43"
type: manual
components: 
  - ac_store
  - commit_guardian
summary: "Authored the missing producer half of the shared pattern system and tightened commit-time file-scope enforcement so tickets can no longer under-declare which source files they touched."
description: "ADDED: 9023f77c2 authors ACS-500g (L1) plus 16 child ACs, component ac_store, specifying the producer half of shared pattern specs — a pattern-steward agent and authoring-patterns skill that detect recurring behaviour and promote it into a reusable pattern. The repo already had the full consumer half (implements_pattern/pattern_bindings/pattern_slots schema fields, check-ac-pattern-refs hook, BA section 3a) but nothing ever created a pattern, so the inventory stayed empty (zero PTN-* records). Carries a documented child_limit_override: 7. These ACs are authored/backlog only — the pattern-steward agent and skill are not built yet. CHANGED: ac8b236b4 flips files_touched_reconciliation.strict from false to true in commit_guardian.json, component commit_guardian, upgrading the already-registered check-predone-scope hook from advisory to blocking: a ticket commit whose actual diff touches source files (.py/.sql/.ts/.tsx/.js) not declared in files_touched is now rejected at done-time instead of merely reported."
commits: 
  - 9023f77c2
  - ac8b236b4
breaking: true
migration_steps: 
  - Before staging a ticket as status: done, ensure files_touched lists every source file (.py/.sql/.ts/.tsx/.js) actually modified on the branch.
  - Use out_of_scope to explicitly declare any touched file that is intentionally excluded from files_touched.
  - If a commit is now blocked by check-predone-scope, update the ticket files_touched to match the real diff and retry the commit.
---

## Entry
