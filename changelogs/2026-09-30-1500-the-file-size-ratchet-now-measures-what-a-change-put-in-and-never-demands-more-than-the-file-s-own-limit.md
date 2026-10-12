---
title: "The file-size ratchet now measures what a change put in, and never demands more than the file's own limit"
date: "2026-09-30"
time: "15:00"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
  - ac_store
summary: "Fixed the file-size guardrail so an edit that removes and re-adds the same amount of code is no longer waved through as if nothing changed, stopped it from ever requiring an oversized file to shrink below the length its own published limit already permits, made three of its refusals say clearly what they do and do not know, and filed (without yet fixing) two defects found in a related guardrail while doing this work."
description: "9 commits completing tickets 05-09 of the GE-127 tree (01-04 shipped in PR #937): _file_size_ratchet.py now diffs stripped previous vs current content and counts inserted lines rather than net length change; the ratchet cap is max(limit, previous - added) so it can never exceed the absolute rule; three commit_guardian refusal paths were made to state explicitly when guidance could not be produced, present a suggested split as a starting point rather than an instruction, and refuse cleanly naming which of two situations applies instead of crashing; two check-output-drift defects were filed as known issues (KI-CG-20260929, both unfixed); and an ac-store fulfillment-gate disagreement that left GE-127c/GE-127d recorded as unfinished despite all children being done was corrected."
commits: 
  - 39009593
  - 75dcc7a2
  - 9104af22
  - 0374b637
  - b18112ef
  - 8ecddd7c
  - 1680cee4
  - d17fc463
  - e0b5b4a4
breaking: false
---

## Entry

This is the second and final PR of EPIC-FilesStayWorkable (tickets 05-09 of
nine; 01-04 shipped in PR #937).

**The ratchet now measures what a change put in, not how much the file changed
size.** Previously an already-oversized file was judged only on "did it get
longer" — a change removing forty measured lines and adding forty back read
as no change at all, and committed. It now diffs the stripped previous
content against the stripped current content and counts inserted lines.

**And it will never demand more than the file's own limit.** The new
comparison is `max(limit, previous - added)`. Before this cap, a 410-line
file with 50 lines added was asked to reach 360 — sixty lines below the 400
the standard actually permits. An incremental ratchet that can demand more
than the absolute rule is not incremental.

**Three ways the refusal became honest about what it knows.** It now says
when it could not produce guidance at all, rather than silently printing
nothing. It presents the suggested division as a starting point rather than
an instruction. And when it cannot establish what a change added, it refuses
cleanly, saying which of two situations it is in, rather than crashing with a
traceback.

**Two guardrail defects were filed, not fixed** — both in
`check-output-drift`, both found while committing this epic's own work. One
reports a GAP on a gitignored runtime cache with a remedy that can never
clear it; the other is an unexplained rewrite that strips the deployed
config's em-dashes so the next commit fails. The second is filed with its
cause explicitly unidentified rather than guessed.

**An AC-store correction worth naming:** `GE-127c` and `GE-127d` were
recorded as unfinished while all their children were done — the inverse of
phantom-done, understating shipped work. Caused by this epic's own
fulfillment gates disagreeing on whether closing a parent is in scope.

Scope note: `GE-127f-3` remains blocked on `INF-800f` and `GE-127` stays
open.
