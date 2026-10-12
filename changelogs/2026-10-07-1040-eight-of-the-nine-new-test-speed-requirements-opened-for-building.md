---
title: "Eight of the nine new test-speed requirements opened for building"
date: "2026-10-07"
time: "10:40"
type: manual
components: 
  - testing_quality
summary: "The requirements written for removing duplicated build work in the test suite are now marked ready to build. One of the nine is deliberately held back, because acting on it would revise a decision someone else recorded and that person has not been asked yet."
description: "Promotes TQ-600a-9, TQ-600a-9-i, TQ-600a-9-ii, TQ-600a-10, TQ-600a-10-i, TQ-600a-10-ii, TQ-600a-13 and TQ-600a-13-i from readiness reviewed to approved, so they enter the ready set the build pipeline draws from. TQ-600a-9-iii is deliberately left at reviewed: it would change test_acd_2100d_2_i.py in a way that revises a written order-independence decision recorded by that test's author, and its own technical requirements state in capitals that it must not be built without that owner agreeing. It was authored as a separate record precisely so the roughly thirty-nine seconds it covers can be declined without blocking the uncontested savings in its siblings. For TQ-600a-13, which leaves open whether the documentation or the behaviour changes, the recorded steer is to correct the documentation rather than add real deselection, because the prior analysis found those tests catch silent corruption of the shared layout and should keep running."
---

## Entry
