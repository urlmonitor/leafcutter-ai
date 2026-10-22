---
title: "The knowledge sync's closing status report uses the declared limits"
date: "2026-10-21"
time: "15:00"
type: manual
components: 
  - knowledge_management
summary: "The status report printed at the end of every knowledge sync run now evaluates capacity and retention against the same declared limits as the sync step, instead of showing the ceiling as unknown and reclaimability as undetermined."
description: "The knowledge-sync workflow passed the retention bound and capacity ceiling to the sync command but not to the status command that runs after it, so every run's closing report showed capacity verdict unknown and reclaimability undetermined even though the sync had measured headroom correctly. The status call now receives the same six flags (--retention-max-generations, --retention-min-age-seconds and the four --capacity-* flags), so the closing report lists each retained generation's reclaimability and the remaining headroom against the declared ceiling."
---

## Entry
