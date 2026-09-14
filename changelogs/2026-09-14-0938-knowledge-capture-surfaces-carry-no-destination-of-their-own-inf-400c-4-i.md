---
title: "Knowledge-capture surfaces carry no destination of their own (INF-400c-4-i)"
date: "2026-09-14"
time: "09:38"
type: ticket_completion
components: 
  - infrastructure
  - build_orchestration
  - knowledge_system
  - product_ownership
  - ticket_creation_pipeline
  - skills_system
summary: "Fixed the four places agents were told to log captured knowledge so records now reach the project's declared knowledge sink instead of disappearing into the operational telemetry stream."
description: "9027eefd8 removed the hardcoded debugging/logs/agent_telemetry.jsonl destination from the signoff skill's knowledge-capture section and the emission sections of the product-owner, business-analyst, and it-po agent templates. All four now carry byte-identical wording telling the agent to obtain the sink by running harvest_learnings.py --print-sink, which was hardened to refuse (exit 1) instead of falling back to a CWD-relative path when no build-time sink declaration exists. A new scripts/ci/check_sink_parity.py gate verifies all four surfaces by real execution rather than by grep. Also amended BO-2000a-5, whose it_requirements still named two skills retired by ADR-034 and never present on disk. Scope: this fixes the write path only (records now land in the declared sink and the harvester finds them) — it does not make the knowledge loop route end to end; the record still comes back unroutable pending INF-400c-5's entry_kind vocabulary, and nothing yet invokes the harvester automatically pending INF-700a-1."
pr: 779
adrs: 
  - ADR-034
commits: 
  - 9027eefd8
breaking: false
ticket: "INF-400c-4-i"
---

## Entry
