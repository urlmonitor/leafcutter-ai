---
title: "docs(ac-store): reopen nine more phantom-done ACs, close two coverage gaps, hand the build-orchestration findings over"
date: "2026-08-25"
time: "19:30"
type: manual
components:
  - ac_store
  - ac_driven_dev
  - build_orchestration
  - build_pipeline
  - guardrail_engine
summary: "Nine acceptance criteria that claimed to be finished were checked against the code, found to be false, and reopened with the evidence written into each record; two genuinely missing rules were written; and the findings that belong to another team were handed over as a ticket rather than edited into their files."
description: "Completes the known-issues triage across five registers, 65 entries, with no production code. Nine acceptance criteria marked done were verified against the code, found false, and reopened to todo with the evidence and a note on how not to close them again. Two genuinely missing rules were authored, and the findings belonging to another component were handed over as a ticket rather than edited into its register. Full per-record detail is in the entry below and in the linked PR."
breaking: false
---

## Entry

Reopened `done` → `todo`, each with the verified evidence written into the record:

| AC | why it is false |
|---|---|
| `BP-600e-2` | the divergence gate compares the first whitespace token of the prose root cause against pytest output, then terminates instead of waiting for confirmation |
| `BO-2400f-3` | the reconnect path runs `git worktree add <path> <branch>` with no start point, so a re-run rebuilds on a stale branch tip |
| `BO-2400e-4` | read and write are both default-newline, so a CRLF record is rewritten LF end-to-end. Current exposure is zero |
| `BO-2200c-5` | the generator emits no pipe delimiters and the verifier demands them, so the verifier's format spec *is* the second list the criterion forbids |
| `BO-202` | the `covered_by` auto-fix skips L3 entirely and greps only `tests/`, while the tags live in `unit_tests/` |
| `BO-2300a-1`, `BO-2300a-2` | one bug: "headless" was implemented as "the agent returned null", so a well-formed refusal is accepted as the user's consent, and the cancel path returns `status: ok` against its own never-`ok` constraint |
| `BO-1500f-1` | a failed registry read collapses into a permission denial, and `worktree-agent` is never dispatched |
| `ACD-1200a-3-iii` | reproduced: `_to_pascal_case` returns `'ShipPartsTreeTheFastPath,Quickly'` inside the criterion's own `Given` |

`BO-2400f-10` and `BO-2400c-1-iii` were **not** reopened — both moved to
`in_progress` while the triage was running.

Authored: `GE-122a-4` (+ `-i`) requiring an allocator to enumerate every id
already present by walking the tree and refuse a taken one — every existing
`GE-122` child is a detector and none obliges the allocator; `ACD-1200a-3-iv`
for phrase-aware truncation; and `ACD-1200a-8-i` requiring a generated
`Master_Plan` to pass the gate guarding a hand-written ticket without weakening
it.

`ACD-1200a-6` and `-7` were deliberately **not** reclaimed. `goal_to_epic.py`
cites them nine times and neither exists, but `git log --all -S` shows no record
ever reached any ref while four ticket files use the ids — so authoring new
promises at those ids would make nine live citations resolve confidently to the
wrong criterion, which is worse than dangling because it is invisible.

Three of the nine reopened criteria were held up by **presence-only assertions
over JavaScript source**. `BO-2400f-10`'s entire covering evidence was
`self.assertIn("release", content)` — which passes while all eleven release
dispatches go to an agent that refuses the role, and whose behavioural tests
call the released function directly so it works and only its caller is dead.
`BP-1100b-5` (`work_status: todo`) already specifies the guard that would
reject this shape, and its scanned-source globs already include
`templates/workflows-js/**/*.js`. Building it and running it retroactively is
the highest-leverage item in the handover.

The sharpest finding is a line of documentation. `docs/reference/ac-schema.md:739`,
the ID-assignment procedure, instructs a scan of

> all YAML files directly under `docs/acceptance-criteria/<component-id>/`
> (non-recursively — only root-level L0 and L1 files; subdirectories are skipped)

which is `KI-ACD-008` — the id allocator missing ids owned by feature folders,
which minted a live duplicate earlier the same day — **written down as the
specification.** The allocator is not violating the documented procedure; it is
following it. `GE-122a-4` carries a `modifies` doc_link flagging the line.

Two gates fired during the commit and both earned their keep.
`check-product-truth-validate` caught that reopening `BO-202` made the
`acfulfill` step of `leafcutter/how-acs-are-built` derive `in_progress` against
a declared `done` — the store is coupled and the gate proved it, so the step
and the regenerated index are included here. `check-ac-schema` rejected
`ACD-1200a-8` for carrying no `test_spec` as an approved code AC: pre-existing
non-compliance, invisible until the record was staged to add a `covered_by`
entry, which is `KI-CG-001` for the fourth time in one day.
