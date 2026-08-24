---
title: "docs(known-issues): file four defects found from a consumer install, and add the skill-reference gate"
date: "2026-08-18"
time: 2210
type: manual
components: 
  - ac_store
  - build_pipeline
  - build_orchestration
summary: "Writes down four problems that were found while installing the package into another project and using it there, including six skills that agents are told to load and that were never written. Adds a checker for the last one so it cannot happen again unnoticed."
description: "Four known-issues entries, all found 2026-08-18, three of them from a consumer install rather than from this repo. KI-ACS-005: the components field is required and hand-authored on all 3,154 ACs while the package ships the deriver that would compute it — measured 86.8% derivable, and 972 of 973 ACs invalid in one consumer repo because the deriver is not deployed. KI-BP-006: build_ac_store's hand-maintained deploy_map omits validate_ac_schema.py and both its helpers; this is the fourth recurrence of that failure mode and five of the eleven entries now carry a warning comment, which is evidence the mechanism does not work. KI-BP-007: six skills are referenced by path in shipped agent and skill templates and none of them exist — route-learning, capture-learning, agent-telemetry, and three trading-domain skills inherited when research-agent was copied in from another project. Every call site treats not-found as a pass, so the post-execution half of the knowledge system has never run and the epic runbook has never emitted a telemetry event, while every agent reports a clean sign-off. KI-BO-010: /quick-fix's divergence gate compares the first whitespace token of a prose diagnosis against pytest output, so a leading backtick fails it and a leading 'The' passes it unconditionally, and its stated remedy — re-run with the same args — recomputes the same verdict. Also adds scripts/check_skill_refs.py, the gate for KI-BP-007: it resolves imperative prose skill references against the real directory set, strips HTML comments so retired-skill history does not fail it, and reproduces the 21-reference finding. It is deliberately NOT wired into CI or the build yet — wiring it is the fix, and it belongs with the work that resolves the six instances. Two entries were renumbered on landing (KI-ACS-003 to 005, KI-BO-008 to 010) because main published different entries under those numbers while this work sat uncommitted."
breaking: false
---

## Entry
