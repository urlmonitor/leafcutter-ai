---
title: "Acceptance criteria for a fast lane whose steps are never refused as someone else's job"
date: "2026-09-27"
time: "12:00"
type: manual
components: 
  - build_orchestration
summary: "Eleven new acceptance criteria specify how the fast lane stops failing on role refusals: a dedicated command-step-runner agent runs every command step, the registry declares which step kinds an agent may run, a structural check fails a step sent to an agent not chartered for it, a declined step is reported as a declined step, every step is told the run's own workspace, and a decline never leaves a claim behind. Ten are approved; a large-output hand-off is kept as a draft follow-up."
description: "AC-only change under BO-2400-fast-lane-build. New L3s: BO-2400a-1-iii (step_kinds schema and registry gate), BO-2400a-1-i (command-step-runner agent), BO-2400f-5-i (route every command step to it), BO-2400f-5-ii (structural check driven by permits_shell and step_kinds), BO-2400f-5-iii (declined-step halt), BO-2400f-3-ii (named target workspace), BO-2400f-10-iii (release on decline), BO-2400a-6-i/-7-i/-8-i (how-to, sequence and component diagram updates), all approved; BO-2400a-1-ii (large output by file path and hash) stays draft. BO-2400f-5, BO-2400a-1, BO-2400a-6, -7 and -8 go from done to in_progress with dated notes because each now has unbuilt children; covered_by back-links updated on BO-2400f-3 and BO-2400f-10. Motivated by the 2026-09-25 runs where status-checker refused the claim step (reported as a concurrent claim) and python-coder refused the context-bundle step as misrouted."
commits: []
breaking: false
---

## Entry

On 2026-09-25 the fast lane could not finish a run without being driven by
hand. Some of its steps were sent to agents whose role does not cover them,
and those agents refused. One refusal was even reported as another run
holding the claim.

These criteria describe the fix before any code is written. One dedicated
agent runs every command step. The registry says which kinds of step each
agent may run, and a check fails if a step goes to an agent that may not run
it. A refusal is reported as a refusal. Every step is told which workspace it
works in, and a refused step never leaves criteria claimed.
