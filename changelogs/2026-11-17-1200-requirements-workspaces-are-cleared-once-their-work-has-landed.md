---
title: "Requirements: workspaces are cleared once their work has landed"
date: "2026-11-17"
time: "12:00"
type: manual
components: 
  - build_orchestration
  - worktree_manager
summary: "Approved requirements (BO-4400g, priority high) so finished workspaces stop piling up: clear a workspace by naming its work, an unattended pass that clears landed and long-idle workspaces, and every flow clearing through that one place."
description: "Requirements only, no code. New records under docs/acceptance-criteria/build-orchestration/BO-4400-nothing-accumulates/: BO-4400g, BO-4400g-1 (+ -i, -ii), BO-4400g-2 (+ -i..-v), BO-4400g-3, BO-4400g-4 (+ -i, -ii), BO-4400g-5. Amends BO-4400, BO-4400a and its children, BO-4400d and its children, and BO-4300g, BO-4300g-2, BO-4300g-2-i to one rule: cleared once landed."
breaking: false
---

## Entry

New approved requirements under BO-4400 ("Your machine stays clean no matter how much
automation runs on it"):

- BO-4400g-1 (+ -i, -ii): `remove` accepts the work's name (`--kind/--slug` or `--branch`), the
  same identity `ensure` takes. Asking again for work that is already gone answers ok; names
  that disagree clear nothing.
- BO-4400g-2 (+ -i..-v): a new `clear-landed` pass on the workspace maker clears this project's
  workspaces whose work reached main (fast-forward, merge commit or squash, judged over the
  branch's commits together), workspaces with no commits of their own after 7 days idle, and
  pushed-but-never-merged workspaces holding nothing unsent after 14 days idle. It never prompts,
  never deletes a branch on the shared project, and keeps anything unsent, in use or unconfirmed.
- BO-4400g-3: a preview of the pass lists what it would clear and keep, and changes nothing.
- BO-4400g-4 (+ -i, -ii): every flow that makes a workspace clears it by name through the one
  clearing command once its pull request has merged (a flow with nothing to deliver clears at
  once); a pull request still open at the end leaves the workspace to the pass. Includes the
  ship skill and finalize's scratch copy.
- BO-4400g-5: the clearing how-to covers clearing by name, the pass and its preview.

Amended to the same rule: BO-4400 and BO-4400a (cleared once landed, not once up for review),
BO-4400a-1..-5, the routine sweep BO-4400d-1..-5 (its workspace step runs the pass), and
BO-4300g / BO-4300g-2 / BO-4300g-2-i (a flow's own name-based clear through shell-runner is the
one permitted exception; finalize's step 7 is unchanged).

Build order: BO-4400g-1, then BO-4400g-2 and its children; BO-4300g-2-i's parser and
BO-4400g-4's test-harness bridge before the flow records. Leftovers without a record wait for
the door's own rule (open PR #1414).
