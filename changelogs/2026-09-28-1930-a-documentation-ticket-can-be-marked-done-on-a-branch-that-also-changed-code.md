---
title: "A documentation ticket can be marked done on a branch that also changed code"
date: "2026-09-28"
time: "19:30"
type: manual
components: 
  - commit_guardian
  - build_pipeline
summary: "Closing a documentation-only ticket failed whenever the branch it sat on had also changed source code, listing as undeclared the very files the ticket had already declared out of scope. The advice the check printed could not be followed: the files were already listed, and the other route it suggested would have made the ticket claim code it never touched. The check now keeps those out-of-scope declarations, while a docs ticket that declares nothing still cannot quietly absorb code changes it never mentioned."
description: "Resolves KI-BO-20260923-0700, observed on BO-400e-5. _get_ticket_scope's docs-only branch in check_files_touched_reconciliation.py returned a bare empty set before out_of_scope was unioned in, so for any ticket whose files_touched is entirely non-source the declared scope was empty and every source file in the branch range was reported undeclared. The branch now returns the normalised out_of_scope set. This is a narrowing, not a removal: a docs-only ticket declaring nothing out of scope still yields an empty scope, so BP-1100e-1-iii's original anti-absorption guard is preserved in effect, and a source file in neither list is still flagged. BP-1100e-1-iii is amended rather than given a new child — it already stated the union rule in it_requirements[0] and is a leaf, so no parent staging is needed and check-done-proof's ci-changed scope never reaches BP-1100e-1's seven unproven children. That correction retires the blocker the KI recorded; KI-BP-20260923-0730's proof debt is untouched and still open. Three tests against real column-0 YAML tickets; two mutations verified they discriminate: restoring the empty-set return fails the first test, deleting the docs-only branch fails the second. Length-neutral at 572 content lines."
commits: []
breaking: false
---

## Entry

A ticket that only changes documentation still lives on a branch with other
tickets, and those other tickets change code. The pre-done check compares a
ticket's declaration against everything the branch touched, so a documentation
ticket meets the whole branch's accumulated code changes when it is closed.

Tickets have a field for exactly this: `out_of_scope`, the place to say "this
changed, and it is not mine". The documentation ticket had listed all 24 files
there. The check read them correctly and then threw them away, because the
branch handling documentation-only tickets returned an empty declaration before
those entries were added in.

So the check reported 24 undeclared files and advised listing them in
`out_of_scope` — where they already were. Its only other suggestion was to add
them to `files_touched`, which would have recorded the documentation ticket as
having edited code it never opened. The check was switched off twice to get the
work committed.

Documentation tickets now keep their out-of-scope declarations, like every other
ticket. The protection that branch existed for is unchanged: a documentation
ticket that declares nothing out of scope still declares nothing, so it cannot
quietly take responsibility for code changes it never mentioned, and a file
named in neither list is still flagged.
