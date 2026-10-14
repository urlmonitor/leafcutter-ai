---
title: "Agent templates no longer point at abilities that do not exist, and a contradictory signoff grant stops the build (AR-400 slice 2a)"
date: "2026-10-15"
time: "09:00"
type: manual
components: 
  - agent_registry
summary: "Twelve specialist definitions stop referring to abilities that do not exist, were retired, or were never granted; python-coder's trading-project collector-enforcer section and setting are removed; and the build now refuses an agent that declares signoff: false while being granted the signoff ability."
description: "research-agent no longer routes questions to three abilities inherited from a trading project (find-context-candle, import-scanner, trade-analysis) and is granted knowledge-query; retrospective-agent routes proposed knowledge items with route-knowledge instead of the retired route-learning; the skills catalogue guide uses only shipped abilities as examples; python-coder loads signoff by its real name (the shared sign-off block too); architecture-diagram-author names write-c4-diagram in its real casing; sql-coder hands query scaffolding to the sql-query specialist instead of calling it an ability; adr-author loses its unused doc-enforcer grant and product-owner its signoff grant; llm-expert no longer tells authors to hand-write an abilities section; ticket-supervisor's redundant llm-expert hand-off entry is removed (it still reaches llm-expert as a ticket-phase agent). python-coder's collector-enforcer section is deleted and the collector_enforcer_paths setting is removed from the config schema, the shipped defaults and the reference (a project config that still sets it keeps loading). New scripts/agent_signoff_grant_check.py makes the registry validator - and therefore the build - fail when an agent's own template declares signoff: false and grants signoff; agents whose registry tier is supervisor are exempt, and an absent signoff key is not a declaration. Affected agent cards and the registry are regenerated."
breaking: false
---

## Entry
