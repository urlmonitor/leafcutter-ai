---
title: "A shortened journey description now says it was shortened, and a hand edit to it says where to edit instead"
date: "2026-09-14"
time: "06:36"
type: manual
components: 
  - ux_prototyping
summary: "The index's short form of a long journey description is now its opening followed by an ellipsis, and editing that short form by hand is reported with the file and field that actually hold the description."
description: "The product-truth index shows a shortened form of each journey's description, derived from the journey's own text rather than typed separately. It used to cut from both ends -- 'opening ... closing' -- so a reader saw text that ended mid-thought with nothing to say more had been removed at the end. It now keeps the description's opening, cut at a word boundary, and ends with an ellipsis, so nobody takes it for the whole description (UXP-700e-2-i). The derivation stays reproducible and within its 200-character bound, measured against the longest description in the store. When someone edits the short form in the index directly -- the one copy regeneration throws away -- the report now names the journey file and its 'summary' field as the place to make that edit, rather than only saying the copy is stale. Also closes six UXP-700 criteria whose tests already passed on main, after mutation-checking them."
commits: 
breaking: false
---

## Entry
