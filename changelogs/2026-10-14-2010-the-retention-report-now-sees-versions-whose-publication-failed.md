---
title: "The retention report now sees versions whose publication failed"
date: "2026-10-14"
time: "20:10"
type: manual
components: 
  - knowledge_management
summary: "The report of which stored versions may be removed used to look only at versions that finished publishing, and every version filling the database was one that had failed. It now assesses every stored version and says how many it looked at."
description: "The report that says which stored versions of the knowledge graph may be removed only ever considered versions whose publication had finished. On the live database every stored version was one whose publication had failed, so the report found nothing to consider and said nothing could be removed, while the database filled until it stopped accepting writes. The report now assesses every stored version whatever happened to its publication, gives each one's publication outcome, and states how many versions it assessed, so an empty database can be told apart from a full one in which nothing is yet old enough to remove. The version currently in use is still never reported removable, even when its own publication never finished. The report still removes nothing. Two limits remain and are written into the reference page: a version that never finished publishing is aged from when it was created, because it was never retired, and stating that basis properly is separate work; and a version whose publication is still running is now visible and can be reported removable if it is old enough, so the step that actually removes versions must refuse anything whose publication has not finished."
---

## Entry
