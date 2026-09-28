---
title: A work item whose requirement was narrowed now matches the narrowed requirement
date: "2026-09-28"
time: "11:23"
type: manual
components: 
  - ac_driven_dev
summary: "One work item was written from a requirement that was later narrowed, and still described the wider behaviour. It has been brought back in line with what the requirement now says."
description: "A requirement about leftover workspaces was narrowed three days after the work item for it was written: it now covers only leftovers that are NOT recognisable as the piece of work being asked for, because a half-finished copy of that same work should be picked up and finished rather than turned away. The work item still carried the wider wording, so building it would have produced the wrong behaviour -- refusing the very workspace it should have completed. The narrowing had already been noted as an open follow-up by the team that made it; this closes that note. The item was corrected in place rather than thrown away and rewritten, because two other records point at it by name and would have been left pointing at nothing, and because its creation date is genuinely three days ago -- it was re-scoped now, not written now. The correction was checked by regenerating the item from scratch and comparing: apart from that creation date, the two are identical."
commits: 
  - 4ddf83fd
breaking: false
---

## Entry
