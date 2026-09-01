---
title: "A build that broke nineteen other tests reported its gates green, and the register now says why"
date: "2026-08-31"
time: "15:20"
type: manual
components: 
  - build_orchestration
summary: "Records that the fast lane's green gate only ever runs the tests belonging to the criterion being built, that nothing in the lane runs anything wider, and that the resulting narrow pass is reported in language an operator reads as a verdict on the whole change."
description: "A fast-lane build widened one part of the epic driver and its own new tests passed, so the run reported itself complete with its gates green. The branch had in fact broken nineteen existing tests — every test that models an epic drive — and not one of them appeared anywhere in the run's report. The cause is not a mistake in the gate: it is told to run only the tests tagged for the criteria being built, which is deliberate and is what makes the lane fast. The problem is that nothing in the lane runs anything broader at any point, and the narrow result is then stated in words that sound like a judgement on the change as a whole. The review step does not close the gap either, because it reads the set of changes made, and tests that break without being touched are absent from that set by construction. The cost was concrete rather than theoretical: the review spent a full cycle on a branch that did not build, returned three real findings about the changes, and never mentioned that the suite was red; had those findings been clean, the run would have committed and opened a pull request in that state. This is not a defect that hides forever, because the full suite is a required check once a pull request exists, so the failure would have surfaced there. What it costs is ordering and trust — the lane pronounces its own work sound before anything has tested that claim, and the person reading the result has no way to tell that the pass was scoped. The entry records two fixes rather than one, and says they are not alternatives: running the whole suite once after the coding loop settles and before review, which also stops review cycles being spent on branches that do not build; and, whether or not that ships, making the gate state the scope it actually ran so the report carries the qualifier instead of an unqualified claim of success. It also notes that this project already wrote this rule down for its other pipeline, after per-ticket checks let cross-cutting breakage through in exactly the same way, and that the fast lane was built afterwards without inheriting it."
breaking: false
---

## Entry
