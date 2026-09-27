---
title: "EPIC: Every piece of separate work gets its workspace one dependable way"
epic_name: EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace
created: 2026-09-27
status: in_progress
components:
  - build_orchestration
  - build_pipeline
  - testing_quality
  - worktree_manager
source_ac: BO-4300
depends_on: []
---
# EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace

## Goal

This epic implements AC BO-4300: Every piece of separate work gets its workspace one dependable way. It consists of 59 ticket(s) generated from the leaf ACs beneath BO-4300, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260927-BO-4300a-1.md](./01_TICKET-20260927-BO-4300a-1.md) | Every route that asks gets the same kind of workspace from the same maker | BO-4300a-1 | — |
| 02 | [02_TICKET-20260927-BO-4300a-1-ia.md](./02_TICKET-20260927-BO-4300a-1-ia.md) | No workflow body asks an agent to make a workspace in its own words | BO-4300a-1-ia | 01_TICKET-20260927-BO-4300a-1.md |
| 03 | [03_TICKET-20260927-BO-4300a-1-ib.md](./03_TICKET-20260927-BO-4300a-1-ib.md) | Entry skills run the one maker and hand its answer to the workflow unchanged | BO-4300a-1-ib | 01_TICKET-20260927-BO-4300a-1.md |
| 04 | [04_TICKET-20260927-BO-4300a-1-ii.md](./04_TICKET-20260927-BO-4300a-1-ii.md) | A ready workspace made for a ticket states where that ticket is inside the workspace | BO-4300a-1-ii | 01_TICKET-20260927-BO-4300a-1.md |
| 05 | [05_TICKET-20260927-BO-4300a-2.md](./05_TICKET-20260927-BO-4300a-2.md) | The same piece of work is always recognised as the same workspace | BO-4300a-2 | TICKET-20260927-BO-4300a-1.md |
| 06 | [06_TICKET-20260927-BO-4300a-3.md](./06_TICKET-20260927-BO-4300a-3.md) | How-to: getting a workspace, for agents and people alike | BO-4300a-3 | 01_TICKET-20260927-BO-4300a-1.md |
| 07 | [07_TICKET-20260927-BO-4300a-4.md](./07_TICKET-20260927-BO-4300a-4.md) | Component diagram: the one workspace maker and everyone who calls it | BO-4300a-4 | 01_TICKET-20260927-BO-4300a-1.md |
| 08 | [08_TICKET-20260927-BO-4300b-1.md](./08_TICKET-20260927-BO-4300b-1.md) | The same request from any folder in or around the project gives the same workspace | BO-4300b-1 | TICKET-20260927-BO-4300a-1.md |
| 09 | [09_TICKET-20260927-BO-4300b-1-i.md](./09_TICKET-20260927-BO-4300b-1-i.md) | Starting inside another workspace never nests the new one there or roots it on that work | BO-4300b-1-i | 08_TICKET-20260927-BO-4300b-1.md |
| 10 | [10_TICKET-20260927-BO-4300b-2.md](./10_TICKET-20260927-BO-4300b-2.md) | A project that installed the tools gets its workspaces the same way | BO-4300b-2 | TICKET-20260927-BO-4300b-1.md |
| 11 | [11_TICKET-20260927-BO-4300b-2-i.md](./11_TICKET-20260927-BO-4300b-2-i.md) | Two projects in the same folder never share or collide on a workspace | BO-4300b-2-i | 10_TICKET-20260927-BO-4300b-2.md |
| 12 | [12_TICKET-20260927-BO-4300b-2-ii.md](./12_TICKET-20260927-BO-4300b-2-ii.md) | An out-of-date installed copy inside the project does not change which project is found | BO-4300b-2-ii | 10_TICKET-20260927-BO-4300b-2.md |
| 13 | [13_TICKET-20260927-BO-4300b-3.md](./13_TICKET-20260927-BO-4300b-3.md) | When more than one project could be meant, the request is refused and names them | BO-4300b-3 | TICKET-20260927-BO-4300b-1.md |
| 14 | [14_TICKET-20260927-BO-4300b-3-i.md](./14_TICKET-20260927-BO-4300b-3-i.md) | Started where no project can be found, the request is refused and says where it looked | BO-4300b-3-i | 13_TICKET-20260927-BO-4300b-3.md |
| 15 | [15_TICKET-20260927-BO-4300b-4.md](./15_TICKET-20260927-BO-4300b-4.md) | On Windows without permission to create links, the workspace is still fully ready | BO-4300b-4 | TICKET-20260927-BO-4300a-1.md |
| 16 | [16_TICKET-20260927-BO-4300b-5.md](./16_TICKET-20260927-BO-4300b-5.md) | The location handed back works from every shell on the machine | BO-4300b-5 | — |
| 17 | [17_TICKET-20260927-BO-4300b-5-i.md](./17_TICKET-20260927-BO-4300b-5-i.md) | A project under a folder whose name contains spaces gets a usable workspace | BO-4300b-5-i | 16_TICKET-20260927-BO-4300b-5.md |
| 18 | [18_TICKET-20260927-BO-4300c-1.md](./18_TICKET-20260927-BO-4300c-1.md) | Ready is only answered when every part of readiness holds on the workspace as it exists | BO-4300c-1 | TICKET-20260927-BO-4300a-1.md |
| 19 | [19_TICKET-20260927-BO-4300c-1-i.md](./19_TICKET-20260927-BO-4300c-1-i.md) | A failed install inside the workspace is a refusal, never a warning | BO-4300c-1-i | 18_TICKET-20260927-BO-4300c-1.md |
| 20 | [20_TICKET-20260927-BO-4300c-1-ii.md](./20_TICKET-20260927-BO-4300c-1-ii.md) | Every protection the project declares must fire; one that is present but does not fire produces a refusal | BO-4300c-1-ii | 18_TICKET-20260927-BO-4300c-1.md |
| 21 | [21_TICKET-20260927-BO-4300c-1-iii.md](./21_TICKET-20260927-BO-4300c-1-iii.md) | Setting up a workspace never leaves stray changes in the project's own files | BO-4300c-1-iii | 18_TICKET-20260927-BO-4300c-1.md |
| 22 | [22_TICKET-20260927-BO-4300c-2.md](./22_TICKET-20260927-BO-4300c-2.md) | The maker's answer is one readable answer and nothing else | BO-4300c-2 | TICKET-20260927-BO-4300a-1.md |
| 23 | [23_TICKET-20260927-BO-4300c-3.md](./23_TICKET-20260927-BO-4300c-3.md) | Every caller stops on anything but a ready answer | BO-4300c-3 | TICKET-20260927-BO-4300c-2.md |
| 24 | [24_TICKET-20260927-BO-4300a-5.md](./24_TICKET-20260927-BO-4300a-5.md) | Reference: the answer every caller receives, and what a caller must do with it | BO-4300a-5 | 01_TICKET-20260927-BO-4300a-1.md, 22_TICKET-20260927-BO-4300c-2.md, 23_TICKET-20260927-BO-4300c-3.md |
| 25 | [25_TICKET-20260927-BO-4300c-3-i.md](./25_TICKET-20260927-BO-4300c-3-i.md) | Success reported with output that is not a valid answer is a failure, never 'use the current checkout' | BO-4300c-3-i | 23_TICKET-20260927-BO-4300c-3.md |
| 26 | [26_TICKET-20260927-BO-4300c-3-ii.md](./26_TICKET-20260927-BO-4300c-3-ii.md) | An agent that declines the workspace step ends the run, and no other command is substituted | BO-4300c-3-ii | 23_TICKET-20260927-BO-4300c-3.md |
| 27 | [27_TICKET-20260927-BO-4300c-4.md](./27_TICKET-20260927-BO-4300c-4.md) | The workspace location comes only from the maker's ready answer | BO-4300c-4 | TICKET-20260927-BO-4300c-2.md |
| 28 | [28_TICKET-20260927-BO-4300c-4-ii.md](./28_TICKET-20260927-BO-4300c-4-ii.md) | After a whole run, the main copy is exactly as it was | BO-4300c-4-ii | 27_TICKET-20260927-BO-4300c-4.md |
| 29 | [29_TICKET-20260927-BO-4300c-5.md](./29_TICKET-20260927-BO-4300c-5.md) | Sequence diagram: a caller, the workspace maker, and the halt path | BO-4300c-5 | 23_TICKET-20260927-BO-4300c-3.md |
| 30 | [30_TICKET-20260927-BO-4300d-1.md](./30_TICKET-20260927-BO-4300d-1.md) | Asking again for a healthy workspace hands it back re-readied, with the work in it untouched | BO-4300d-1 | TICKET-20260927-BO-4300c-1.md |
| 31 | [31_TICKET-20260927-BO-4300d-1-i.md](./31_TICKET-20260927-BO-4300d-1-i.md) | Re-readying never overwrites a change the work made to a file the set-up also writes | BO-4300d-1-i | 30_TICKET-20260927-BO-4300d-1.md |
| 32 | [32_TICKET-20260927-BO-4300d-1-ii.md](./32_TICKET-20260927-BO-4300d-1-ii.md) | Two requests for the same work at the same moment never make two workspaces | BO-4300d-1-ii | 30_TICKET-20260927-BO-4300d-1.md |
| 33 | [33_TICKET-20260927-BO-4300d-2.md](./33_TICKET-20260927-BO-4300d-2.md) | A workspace left half-made by an interrupted request is finished by the next one | BO-4300d-2 | TICKET-20260927-BO-4300a-1.md |
| 34 | [34_TICKET-20260927-BO-4300d-2-i.md](./34_TICKET-20260927-BO-4300d-2-i.md) | A half-made workspace is never answered ready while the cause remains | BO-4300d-2-i | 33_TICKET-20260927-BO-4300d-2.md |
| 35 | [35_TICKET-20260927-BO-4300d-2-ii.md](./35_TICKET-20260927-BO-4300d-2-ii.md) | Whatever stage an interruption hit, the next request ends fully ready | BO-4300d-2-ii | 33_TICKET-20260927-BO-4300d-2.md |
| 36 | [36_TICKET-20260927-BO-4300d-2-iii.md](./36_TICKET-20260927-BO-4300d-2-iii.md) | A half-made workspace in which work has since been done is not wiped to finish it | BO-4300d-2-iii | 33_TICKET-20260927-BO-4300d-2.md |
| 37 | [37_TICKET-20260927-BO-4300d-3.md](./37_TICKET-20260927-BO-4300d-3.md) | A location already holding different work is left untouched and reported | BO-4300d-3 | TICKET-20260927-BO-4300a-1.md |
| 38 | [38_TICKET-20260927-BO-4300d-3-i.md](./38_TICKET-20260927-BO-4300d-3-i.md) | A workspace for the same work made the old way is not quietly taken over | BO-4300d-3-i | 37_TICKET-20260927-BO-4300d-3.md |
| 39 | [39_TICKET-20260927-BO-4300d-4.md](./39_TICKET-20260927-BO-4300d-4.md) | Asking for work whose line already exists on the shared project resumes that line | BO-4300d-4 | TICKET-20260927-BO-4300a-1.md |
| 40 | [40_TICKET-20260927-BO-4300d-5.md](./40_TICKET-20260927-BO-4300d-5.md) | State diagram: a workspace's states and what each request does to it | BO-4300d-5 | 30_TICKET-20260927-BO-4300d-1.md, 33_TICKET-20260927-BO-4300d-2.md, 37_TICKET-20260927-BO-4300d-3.md |
| 41 | [41_TICKET-20260927-BO-4300e-1.md](./41_TICKET-20260927-BO-4300e-1.md) | Asking where a piece of work's workspace is gets a definite answer from the same maker | BO-4300e-1 | TICKET-20260927-BO-4300a-1.md |
| 42 | [42_TICKET-20260927-BO-4300c-4-i.md](./42_TICKET-20260927-BO-4300c-4-i.md) | A location handed in by a caller is confirmed with the maker before any step runs | BO-4300c-4-i | 27_TICKET-20260927-BO-4300c-4.md, 41_TICKET-20260927-BO-4300e-1.md |
| 43 | [43_TICKET-20260927-BO-4300e-1-i.md](./43_TICKET-20260927-BO-4300e-1-i.md) | Looking a workspace up never creates or changes one | BO-4300e-1-i | 41_TICKET-20260927-BO-4300e-1.md |
| 44 | [44_TICKET-20260927-BO-4300e-2.md](./44_TICKET-20260927-BO-4300e-2.md) | Clearing a workspace answers at once and never waits for someone to say yes | BO-4300e-2 | TICKET-20260927-BO-4300a-1.md |
| 45 | [45_TICKET-20260927-BO-4300e-2-i.md](./45_TICKET-20260927-BO-4300e-2-i.md) | A workspace with very long file paths on Windows is cleared completely | BO-4300e-2-i | 44_TICKET-20260927-BO-4300e-2.md |
| 46 | [46_TICKET-20260927-BO-4300e-2-ii.md](./46_TICKET-20260927-BO-4300e-2-ii.md) | A workspace with a program still running inside it is never left half-cleared | BO-4300e-2-ii | 44_TICKET-20260927-BO-4300e-2.md |
| 47 | [47_TICKET-20260927-BO-4300e-3.md](./47_TICKET-20260927-BO-4300e-3.md) | Loss of unsent work happens only when authorised up front | BO-4300e-3 | TICKET-20260927-BO-4300e-2.md |
| 48 | [48_TICKET-20260927-BO-4300e-3-i.md](./48_TICKET-20260927-BO-4300e-3-i.md) | Authorisation given for one workspace clears no other | BO-4300e-3-i | 47_TICKET-20260927-BO-4300e-3.md |
| 49 | [49_TICKET-20260927-BO-4300e-4.md](./49_TICKET-20260927-BO-4300e-4.md) | Temporary comparison workspaces come and go through the same maker and leave nothing behind | BO-4300e-4 | TICKET-20260927-BO-4300e-2.md |
| 50 | [50_TICKET-20260927-BO-4300e-5.md](./50_TICKET-20260927-BO-4300e-5.md) | How-to: clearing a workspace by hand, and authorising the loss of unsent work | BO-4300e-5 | 47_TICKET-20260927-BO-4300e-3.md |
| 51 | [51_TICKET-20260927-BO-4300f-1.md](./51_TICKET-20260927-BO-4300f-1.md) | Every existing route now gets its workspace from the one maker | BO-4300f-1 | TICKET-20260927-BO-4300a-1-ia.md, TICKET-20260927-BO-4300a-1-ib.md |
| 52 | [52_TICKET-20260927-BO-4300f-2.md](./52_TICKET-20260927-BO-4300f-2.md) | The former ways of making a workspace are gone from what an install delivers | BO-4300f-2 | TICKET-20260927-BO-4300f-1.md |
| 53 | [53_TICKET-20260927-BO-4300f-2-ia.md](./53_TICKET-20260927-BO-4300f-2-ia.md) | Agent charters, skills, workflow texts and the rules file carry no second recipe for workspaces | BO-4300f-2-ia | 52_TICKET-20260927-BO-4300f-2.md, 06_TICKET-20260927-BO-4300a-3.md |
| 54 | [54_TICKET-20260927-BO-4300f-2-ib.md](./54_TICKET-20260927-BO-4300f-2-ib.md) | How-to guides carry no second recipe for workspaces | BO-4300f-2-ib | 52_TICKET-20260927-BO-4300f-2.md, 06_TICKET-20260927-BO-4300a-3.md |
| 55 | [55_TICKET-20260927-BO-4300f-3.md](./55_TICKET-20260927-BO-4300f-3.md) | Workspaces made the old way are brought over or retired without losing work | BO-4300f-3 | TICKET-20260927-BO-4300a-1.md |
| 56 | [56_TICKET-20260927-BO-4300f-3-i.md](./56_TICKET-20260927-BO-4300f-3-i.md) | Running the cut-over again changes nothing further | BO-4300f-3-i | 55_TICKET-20260927-BO-4300f-3.md |
| 57 | [57_TICKET-20260927-BO-4300f-3-ii.md](./57_TICKET-20260927-BO-4300f-3-ii.md) | Until the cut-over completes, automatic housekeeping cannot prune the shared history | BO-4300f-3-ii | 55_TICKET-20260927-BO-4300f-3.md |
| 58 | [58_TICKET-20260927-BO-4300f-4.md](./58_TICKET-20260927-BO-4300f-4.md) | The proof runs the copy of the maker that a project actually receives | BO-4300f-4 | TICKET-20260927-BO-4300a-1.md |
| 59 | [59_TICKET-20260927-BO-4300f-4-i.md](./59_TICKET-20260927-BO-4300f-4-i.md) | Running the proof leaves the developer's own project unchanged | BO-4300f-4-i | 58_TICKET-20260927-BO-4300f-4.md |

## Dependencies

```
BO-4300a-1 (no dependencies)
BO-4300a-1-ia -> BO-4300a-1
BO-4300a-1-ib -> BO-4300a-1
BO-4300a-1-ii -> BO-4300a-1
BO-4300a-2 (no dependencies)
BO-4300a-3 -> BO-4300a-1
BO-4300a-4 -> BO-4300a-1
BO-4300a-5 -> BO-4300a-1, BO-4300c-2, BO-4300c-3
BO-4300b-1 (no dependencies)
BO-4300b-1-i -> BO-4300b-1
BO-4300b-2 (no dependencies)
BO-4300b-2-i -> BO-4300b-2
BO-4300b-2-ii -> BO-4300b-2
BO-4300b-3 (no dependencies)
BO-4300b-3-i -> BO-4300b-3
BO-4300b-4 (no dependencies)
BO-4300b-5 (no dependencies)
BO-4300b-5-i -> BO-4300b-5
BO-4300c-1 (no dependencies)
BO-4300c-1-i -> BO-4300c-1
BO-4300c-1-ii -> BO-4300c-1
BO-4300c-1-iii -> BO-4300c-1
BO-4300c-2 (no dependencies)
BO-4300c-3 (no dependencies)
BO-4300c-3-i -> BO-4300c-3
BO-4300c-3-ii -> BO-4300c-3
BO-4300c-4 (no dependencies)
BO-4300c-4-i -> BO-4300c-4, BO-4300e-1
BO-4300c-4-ii -> BO-4300c-4
BO-4300c-5 -> BO-4300c-3
BO-4300d-1 (no dependencies)
BO-4300d-1-i -> BO-4300d-1
BO-4300d-1-ii -> BO-4300d-1
BO-4300d-2 (no dependencies)
BO-4300d-2-i -> BO-4300d-2
BO-4300d-2-ii -> BO-4300d-2
BO-4300d-2-iii -> BO-4300d-2
BO-4300d-3 (no dependencies)
BO-4300d-3-i -> BO-4300d-3
BO-4300d-4 (no dependencies)
BO-4300d-5 -> BO-4300d-1, BO-4300d-2, BO-4300d-3
BO-4300e-1 (no dependencies)
BO-4300e-1-i -> BO-4300e-1
BO-4300e-2 (no dependencies)
BO-4300e-2-i -> BO-4300e-2
BO-4300e-2-ii -> BO-4300e-2
BO-4300e-3 (no dependencies)
BO-4300e-3-i -> BO-4300e-3
BO-4300e-4 (no dependencies)
BO-4300e-5 -> BO-4300e-3
BO-4300f-1 (no dependencies)
BO-4300f-2 (no dependencies)
BO-4300f-2-ia -> BO-4300f-2, BO-4300a-3
BO-4300f-2-ib -> BO-4300f-2, BO-4300a-3
BO-4300f-3 (no dependencies)
BO-4300f-3-i -> BO-4300f-3
BO-4300f-3-ii -> BO-4300f-3
BO-4300f-4 (no dependencies)
BO-4300f-4-i -> BO-4300f-4
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| ac-fulfillment-gate | 01, 02, 04, 05, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 52, 55, 56, 57, 58, 59 |
| ac-validator | 01, 02, 04, 05, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 52, 55, 56, 57, 58, 59 |
| architect-review | 01, 02, 03, 04, 05, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 52, 53, 55, 56, 57 |
| architecture-diagram-author | 07, 29, 40 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59 |
| documentation-expert | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59 |
| documentation-verifier | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59 |
| llm-expert | 03, 53 |
| pr-reviewer | 01, 02, 03, 04, 05, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 52, 53, 54, 55, 56, 57, 58, 59 |
| python-coder | 01, 02, 04, 05, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 52, 55, 56, 57, 58, 59 |
| test-runner | 01, 02, 03, 04, 05, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 52, 53, 54, 55, 56, 57, 58, 59 |
| test-writer | 01, 02, 03, 04, 05, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 52, 53, 54, 55, 56, 57, 58, 59 |

