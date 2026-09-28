---
title: "A dedicated command-step-runner agent, chartered to run one command in a named workspace"
date: "2026-09-28"
time: "13:00"
type: manual
components: 
  - build_orchestration
summary: "New agent command-step-runner: it runs exactly one given command, once, in the workspace it is named, whatever checkout it was started in, and returns one JSON value - the command's output verbatim, or a decline for a request outside its role. A failing command is a result, not a refusal, and nothing the command prints is treated as an instruction. It is registered with permits_shell true and all four step kinds; the fast lane will route its command steps to it."
description: "Builds BO-2400a-1-i. Adds templates/agents/command-step-runner.md (Haiku, tools Bash and Read, no Edit or Write), its config/agent_registry.json entry (permits_shell true, step_kinds reads_store/changes_store/changes_repository/publishes, the only entry declaring step_kinds) and a docs/agents/README.md row. Request shape {step, command, target: {workspace, branch, ac_id}}; reply {command, workspace, exit_status, stdout, stderr} or {declined, step, agent, reason} with no exit_status. After review, the template also states that command output is data to relay, never instructions. spawned_by is [\"user\"] for now: the registry checks accept only user and finalize-feature.js as external callers; INF-600k-1 will accept real workflow filenames, and BO-2400f-5-i then adds fast-lane-ship.js."
commits: []
breaking: false
---

## Entry

The fast lane now has an agent whose only job is to run the commands its
steps need. Earlier runs failed because those commands went to agents whose
role did not cover them, and they refused.

The new agent runs the one command it is given, in the workspace it is
given, and hands the output back unchanged. A command that fails is reported
as a result. It refuses only requests that are not its job, such as editing
files by hand, and it never acts on anything the command prints.
