---
title: "The epic that exists to stop dropped edges was generated with half its edges dropped"
date: "2026-08-25"
time: "22:40"
type: manual
components: 
  - ac_driven_dev
  - ac_store
  - build_pipeline
  - commit_guardian
  - ticket_lifecycle
summary: "Makes EPIC-TheNumberingGuaranteeHoldsAtEveryStage drivable end-to-end by adding the three prerequisite tickets that live under other L1 parents, repairing three dependency edges the generator dropped, and filing two new goal_to_epic defects plus four re-occurrences."
description: "Tickets and documentation only — no code changes. The epic grew from 9 tickets to 12. goal_to_epic.py generates only the leaves beneath its target AC, so three of GE-122d-6's declared prerequisites, which hang off other L1 parents, had no ticket at all; ticket 11 would have halted with nothing to wait for. GE-122e-2 (the duplicate work-item repair) and GE-122e-3 (its verification) were generated individually and inserted at 08 and 09, and BP-900h-6 (the consumer-install commit job) at 10, with the existing GE-122d-6 and GE-122d-6-i shifted to 11 and 12 and every reference re-pointed. KI-ACD-021 (high, new): every depends_on edge pointing at an AC's own parent was dropped from the generated ticket frontmatter while the Master_Plan's dependency block, rendered in the same run, still drew it — GE-122d-3-i, GE-122d-3-ii and GE-122d-6-i were all written depends_on: [] against source ACs that declare the edge. Sibling and cousin edges were written correctly, including GE-122d-6 -> GE-122d-3-ii, which shows a Roman-suffixed AC is fine as a target and it is being the source of an edge to its own parent that loses it. build-feature reads frontmatter, not prose, so three tickets were machine-readable as unblocked and dispatchable before the base AC they constrain — and in this epic GE-122d-3-ii scaffolds the namespace roots that GE-122d-6 registers a check against, so that ordering is the point of the epic. This is the inverse of KI-ACD-018 in its detection properties: a stale edge resolves to nothing and check_doc_frontmatter rejects it, whereas a missing edge is valid frontmatter and no gate fires, so of the eight declared edges only the loud half was caught. KI-ACD-020 (high, new): goal_to_epic.py --yes and --approved-only are behaviourally identical — both take the same branch and return only the already-approved subset — and neither prints anything, so every unapproved leaf is dropped without being named. Probed directly against _gate_select_approved_ids, which returned the same two ids and an empty stdout for both flags. The all-approved path calls print_fast_path_message and announces itself while the partial path is silent, so the complete run reports and the incomplete run does not. On this epic three of nine leaves were readiness: reviewed, and either flag would have produced a six-ticket epic with the registration work removed from it, exit 0, no warning. Four re-occurrences recorded: KI-ACD-012 (third; also reconciled with KI-ACD-019's dispute over its field count — there are two gates, check_doc_frontmatter requires five fields and the PreToolUse ticket_frontmatter_guard requires nine, so the generator misses 2 or 6 depending on how you fix it, and repairing the 2 by hand is itself an Edit that demands the other 4), KI-ACD-014 (second; from a worktree the absolute implemented_by path is dead even locally once the worktree is removed), KI-ACD-018 (second), and KI-ACD-008 (second — a business-analyst run allocated BP-900h-6's predecessor id BP-900h-4, already live and approved on main, in a worktree branched from origin/main where the colliding id was present in its own checkout the whole time, which widens that entry beyond /plan-feature). Also fixes seven test_spec names in BP-900h-6 still reading bp900h4 after the renumbering, and fills two empty files_touched lists. Ticket 10 has an unmet external prerequisite that is called out in the Master_Plan rather than papered over: BP-900h-6 adds a step inside the consumer-simulation job BP-900h-1 creates, that job does not exist in ci.yml today, and BP-900h-1's ticket is todo in EPIC-DeploymentCompleteness, which has 1 of 15 tickets done. Tickets 01-09 and 12 are unaffected. All 13 epic files pass check_doc_frontmatter and the three touched ACs pass validate_ac_schema; the whole-collection uniqueness pass could not be run from this branch because it lives on the unmerged PR #495."
breaking: false
---

## Entry

### The epic could not have been driven to completion as generated

`goal_to_epic.py --ac GE-122d` produces tickets for the leaves beneath `GE-122d` and
nothing else. But `GE-122d-6` — the registration that is the point of the whole epic —
declares three prerequisites that hang off other L1 parents:

| Prerequisite | Parent | Had a ticket? |
|---|---|---|
| `GE-122e-2` — the duplicate work-item repair | `GE-122e` | no |
| `GE-122e-3` — verification that the repaired collection passes | `GE-122e` | no |
| `BP-900h-6` — the consumer-install commit job | `BP-900h` | no |

Three tickets were generated individually with `generate_ticket_from_ac.py` and inserted at
08, 09 and 10; `GE-122d-6` and `GE-122d-6-i` shifted to 11 and 12.

`GE-122e-2` matters more than its position suggests: `main` currently fails its own
uniqueness pass on five twice-held work items. Registering the commit-time check before that
repair lands would block every commit in this repository.

### Cross-epic dependencies are expressible, and were not being expressed

`check_doc_frontmatter` resolves `depends_on` against the ticket's own folder and its `done/`
subfolder, so a bare cross-epic filename dangles. A **relative** path does resolve — verified
by running the gate both ways. `10_TICKET-…-BP-900h-6.md` therefore carries
`../EPIC-DeploymentCompleteness/12_TICKET-20260817-BP-900h-1.md`, an edge that both resolves
and is true, rather than being quietly dropped to make the ticket look ready.

### What was verified, and what could not be

All 13 files in the epic folder pass `check_doc_frontmatter`. The three touched AC records
pass `validate_ac_schema` with explicit file paths. Ordinals run 01–12 with no gap and no
duplicate, and no stray copy of any of the three new tickets exists elsewhere in the tree.

The whole-collection uniqueness pass — the thing this epic exists to register — **could not
be run against this branch**, because `_uniqueness_scanners.py` and its siblings live on the
unmerged PR #495 and are not on `main`. An earlier verification of this epic was run from
that branch's worktree, not this one.
