---
title: "Reconcile PR #495 with main so CI can finally run on the uniqueness guard"
date: "2026-08-26"
time: "07:15"
type: manual
components:
  - commit_guardian
  - guardrail_engine
summary: "Merges 94 commits of main into feat/ge-122-integrity-guard, resolving sixteen doc/AC/known-issues conflicts in main's favour and preserving every source file byte-for-byte, so PR #495 becomes MERGEABLE and gets its first status checks after eight days as a CONFLICTING PR with zero CI history."
description: "PR #495 had been open since 2026-08-18 and was 89 commits behind main. A CONFLICTING PR has no computable merge ref, so GitHub withheld every status check and nothing on the branch had ever been CI-verified. Two merge commits bring it level with origin/main. Sixteen files conflicted and all sixteen are documentation, acceptance criteria, or known-issues registers — zero source conflicts, and that property is preserved: every source file the branch adds or modifies is byte-identical to its pre-merge state and every source file main changed is byte-identical to main's, verified by diffing the merge result against both parents restricted to templates/ and scripts/. Main's side was taken in all sixteen cases: the GE-122d/GE-122e and BP-900h acceptance criteria re-authored on main today through PRs #555 and #566; BP-900h-4, whose branch content was renumbered to BP-900h-6 on main and is byte-identical to the discarded copy; the five known-issues registers, where the branch had invented a parallel KI-<COMP>-<n> scheme against main's established KI-<COMP>-NNN one; docs/reference/architecture-docs-layout.md; and docs/INDEX.md, which was then regenerated rather than hand-merged. commit_guardian.json auto-merged to the exact union of both sides' hook registrations. Two defects the merge surfaced are reported rather than patched, because resolving either requires a decision about main-owned content: ADR-034 is now claimed twice (main minted ADR-034-knowledge-write-ownership while the branch's whole-collection-uniqueness-pass ADR — then also numbered 034, since renumbered to ADR-037 — was in flight, and main separately authored docs and ACs citing the uniqueness ADR at that number), which git cannot see because the filenames differ and the diff-scoped collision hook does not fire on, but which the branch's own whole-collection uniqueness pass detects correctly; and a lifecycle-move collision where the branch moved TICKET-20260817-GE-122e-1.md to 99_done while main added a ticket whose depends_on pointed at the old 00_inbox path — that one is repaired here, since a dangling dependency path is a link fix rather than a content decision."
breaking: false
---

## Entry

The point of this change is not the content — it is that PR #495 now has status
checks at all. A CONFLICTING pull request gets zero checks, because the workflows
build the merge ref and there is no merge ref to build. Eighteen commits of guard
code had therefore never been through lint, the test suite, the AC store gate, or
the proof-of-done gate.

### Source preservation

The audit that matters for a merge this size is not "does it build" but "did the
3-way merge silently drop a hunk one side added". Checked by diffing the merge
result against the pre-merge branch tip, restricted to every source path the branch
touches: empty. And against `origin/main`, restricted to `templates/` and
`scripts/`: exactly the branch's own additions and nothing of main's missing. The
only file both sides edited was `commit_guardian.json`, and its merged form carries
both `check-decision-number-uniqueness` (branch) and
`check-package-surface-declaration` plus its config block (main).

### What CI found on the first run

Five checks pass, including Lint and Proof-of-done. Three fail, and none of the
three is caused by the merge resolution itself:

- **Test suite** — six failures. Two are the branch's own uniqueness pass correctly
  reporting the duplicate `ADR-034`. Four are the placeholder detector flagging
  `TODO:` and `todo:` inside main's known-issues prose, which is the second half of
  `KI-CG-017`, already filed on main against this branch.
- **AC store valid** — `BP-900e-3.yaml` is `readiness: approved` with no `test_spec`.
  Byte-identical to `origin/main` on that field; it fires only because the branch
  edits the file for an unrelated `doc_links` cross-reference and CI stages the whole
  branch diff. `KI-CG-001`'s index-scoping, exactly.
- **Changelog entry present** — this file.

### Hooks skipped, and why

`check-predone-scope`, `check-ticket-ac-status-parity` and
`check-package-surface-declaration` were skipped on both merge commits, with the
reason written into each commit message. All three read a merge commit as if it
were ordinary work: the first treats every modified ticket as the commit's
authoriser, the second sees a `done` ticket and a `todo` AC that are both already
on main, and the third counts main's already-declared registry entries as newly
registered. None can be satisfied by a merge, and `--no-verify` was not used.
