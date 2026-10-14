---
title: "A feature whose children include documentation can now be marked done (#CompositeDoneIgnoresDocWaiver)"
date: "2026-10-12"
time: "15:10"
type: manual
components: 
  - ac_store
  - decision_kernel
summary: "The proof that a parent acceptance criterion is done now accepts a documentation child that records test_required false with a reason, the same way a single criterion already did; before, every parent with a documentation child stayed in progress forever. With it, the whole DK-600 decision-lifecycle tree is done."
description: "Completes BO-2500a-1-ii (one shared rule at every layer). Both composite paths, the commit-time check and mark_ac_done's oracle, now consult is_covers_tag_waived. DK-600c-5, DK-600d-5, DK-600a to DK-600e and DK-600 were marked done through mark_ac_done.py."
---

## Entry
