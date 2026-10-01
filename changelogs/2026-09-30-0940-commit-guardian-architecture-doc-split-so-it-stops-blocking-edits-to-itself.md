---
title: "Commit-guardian architecture doc split so it stops blocking edits to itself"
date: "2026-09-30"
time: "09:40"
type: manual
components: 
  - commit_guardian
  - doc_compliance
summary: "Split an oversized architecture doc into two linked pages so the file-size guardrail no longer refuses edits to it, with no change in behavior."
description: "1 commit (a134f79a): docs/architecture/components/commit-guardian.md (338 -> 67 body lines) split into a new sibling docs/architecture/components/commit-guardian-change-set-scoping.md (297 body lines), moving the merge-aware-checks and outcome-vocabulary sections together verbatim since they cross-reference each other; two anchor links in docs/how-to/managing-pre-commit-hooks.md were retargeted to the child and docs/INDEX.md picked up the new page."
commits: 
  - a134f79a
breaking: false
---

## Entry

`docs/architecture/components/commit-guardian.md` had grown to 338 body lines
against the 300-line limit enforced by `check-doc-length`, so the gate refused
any commit that grew the file further — which had already forced deferring an
unrelated architecture update. The doc is now two pages instead of one, with
no change in behavior.

The "Merge-Aware Checks" and "Machine-Readable Outcome Vocabulary" sections
moved together, verbatim and in original order, into a new sibling,
`docs/architecture/components/commit-guardian-change-set-scoping.md`. They
were kept together rather than split apart (the gate's own suggestion) because
they cross-reference each other — separating them would have forced rewriting
both sides. The parent dropped to 67 body lines; all 11 original headings
survive character-for-character across the pair. Two anchor links in
`docs/how-to/managing-pre-commit-hooks.md` were retargeted to the child, and
`docs/INDEX.md` picked up the new page automatically.

**For future authors:** the child sits at 297 lines against the 300 limit —
three lines of headroom. New commit-guardian architecture content should go in
the parent (233 lines free) unless it is specifically about change-set
scoping.
