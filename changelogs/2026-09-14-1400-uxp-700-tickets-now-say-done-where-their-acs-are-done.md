---
title: "UXP-700 tickets now say done where their acceptance criteria are done"
date: "2026-09-14"
time: "14:00"
type: manual
components: 
  - ux_prototyping
summary: "28 tickets in the EPIC-TruthfulProjectRecord folder still read status: todo although their acceptance criteria were done. They now read done, so /build-feature skips them and builds only the 14 criteria still open."
description: "The UXP-700 tranches (#773 to #792) were built directly, not through /build-feature's phase pipeline, so their tickets never moved: 28 tickets read status: todo while their source acceptance criteria read work_status: done. /build-feature's planner skips a ticket only when its own frontmatter says done, so it would have rebuilt all 28. Each of those tickets now reads status: done, plus a dated comment. The comment explains that the ticket was built outside the phase pipeline, so its sign-offs were never ticked, and names the AC's evidence fields and covers-tagged tests as the proof. Marking them done surfaced one real gap. The proof-promise gate found that UXP-700c-3-i's promised criterion-angle test had never been tagged. The test existed, asserting that index path keys use forward slashes, but under another name and without covers or angle tags, so nothing credited it. It was renamed to the promised name and tagged in #798, which had to land first, because the pre-done scope hook compares the whole branch against main. The 14 tickets whose criteria are still open are unchanged. The UXP-700e goal has no ticket and stays todo until KI-ACS-20260914-composite-proof-drops-path-leaves is fixed."
commits: 
breaking: false
---

## Entry
