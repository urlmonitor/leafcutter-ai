---
title: "A learning counts as written only once the work's own commit carries it"
date: "2026-10-09"
time: "09:30"
type: manual
components: 
  - knowledge_system
  - build_orchestration
summary: "The knowledge-durability step (completion_routing.py) existed but nothing could reach it. It is now deployed, has a command-line entry point, and both wired completion paths (/fast-lane-build and /quick-fix) run it. Learnings are written into the worktree, staged by name in the path's own commit, and reported as written only once git shows the commit carries them. A record is never marked routed until its text is on origin/main, so an abandoned branch no longer loses it. build-epic is excluded, because no commit follows its routing step."
description: "Two content commits: 8fccddf7d (fast-lane-ship, CLI, deploy, build-epic exclusion) and 902cc711c (quick-fix, reuse of harvest_cli.apply_state_defaults, docs). New scripts/knowledge/completion_routing_cli.py has two subcommands, stage and observe; each prints one JSON line and exits 0. New completion_routing_git.py holds the read-only git questions. completion_routing.stage_completion now drives harvest_learnings.harvest() with its writes redirected into the worktree and its state write held back; harvest() gains persist_state (default True). Check-the-base-branch confirmation: a stage first claims, flock-arbitrated, only records whose text is already on origin/main, and stages the rest again. A destination origin/main changed since the branch left it is left out (conflicts_with_merged_tree). observe asks git what HEAD carries for each staged write and names each unwritten one with reason and eligibility, plus records emitted after the stage as waiting. Both modules and their siblings are added to build_knowledge_scripts and _manifest_knowledge_scripts. fast-lane-ship.js and quick-fix.js run stage before their commit, stage the manifest by name, and run exactly one knowledge-routing-observe dispatch after the commit, on success and failure alike. settleKnowledgeRouting makes that observation the terminal knowledge_routing, and an unobtainable observation counts nothing as written. quick-fix's routedStageEntries keeps #1063's guards but reads the manifest instead of a git-status diff. build-epic.js loses its routing step and is moved to knowledge_routing_wiring.excluded in config/guardrail_gates.yaml. Both workflow files shrink under the GE-127b-1 ratchet. The reference and how-to are updated. INF-700a-5 and its three L3s stay todo; the PR body gives the reasons."
commits: 
  - 8fccddf7d
  - 902cc711c
breaking: false
---

## Entry

`completion_routing.py` was marked done, but nothing called it, it was in no deploy list, and
it had no entry point. The routing step that did run, the harvester, wrote learnings against
whatever directory the agent's shell stood in. It also marked each record routed the moment
it wrote it, even when the write never reached a commit.

- **One command, two halves.** `completion_routing_cli.py stage --working-dir <worktree>` runs
  before the path's own commit. It drives the harvester, writes learnings into the worktree,
  and marks nothing. `observe` runs after the commit and asks git what the commit actually
  carries. Only those learnings count as written.
- **Both wired paths use it.** `/fast-lane-build` and `/quick-fix` stage the step's manifest
  by name in their commit and report the observation as `knowledge_routing`, including on a
  failed or blocked commit. A routing problem never fails the work.
- **Nothing is marked early.** A record is claimed only once its text is on `origin/main`, so
  an abandoned branch leaves it eligible and the next unit of work writes it once. Two
  unmerged runs can duplicate a learning; neither can lose one.
- **build-epic no longer routes.** No commit follows its routing step, so its writes could
  never be published. It is listed as excluded, with the move into the building-epics skill
  named as the fix.

Known limits: the teardown announcement (INF-700a-5-i) has no host, because finalize-feature
is not wired. A read-only "what is waiting" surface (INF-700a-5-ii) does not exist yet. And
INF-700a-5-iii's "written once" clause needs amending to match the accepted duplicate.
