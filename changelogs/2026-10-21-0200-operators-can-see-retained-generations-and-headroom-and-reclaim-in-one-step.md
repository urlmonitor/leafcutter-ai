---
title: "Operators can see retained generations and headroom, and reclaim in one step"
date: "2026-10-21"
time: "02:00"
type: manual
components: 
  - knowledge_management
summary: "The knowledge status command now lists every retained generation with whether it can be reclaimed and why, and shows node and relationship usage for the repository and the whole database against the declared ceiling; a new reclaim command removes everything the retention bound allows in one step."
description: "Status used to show only the active generation, so an operator could not see generations piling up or how close the hosted store was to its cap. With --retention-max-generations and --retention-min-age-seconds, status now lists every retained generation with its identifier, source revision, retirement time, whether it is reclaimable under the declared bound and the reason, plus the number retained and the number exceeding the bound; without a bound, reclaimability is stated as undetermined rather than guessed. With the four --capacity-* flags it reports measured node and relationship usage for this repository and for the whole database against the ceiling and the remaining headroom; an undeclared ceiling is shown as unknown, never omitted. Status writes nothing. A new reclaim command, which requires the retention bound, reclaims every generation the bound permits in one operation through the same reclamation a successful publication uses, keeping the active generation, unfinished publications and generations a continuation may still need, and reports what was reclaimed and why each other generation was kept, including an explicit zero. The operational how-to gained a capacity and retention step."
---

## Entry
