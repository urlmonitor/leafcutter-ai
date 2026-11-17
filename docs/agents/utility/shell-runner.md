---
title: 'Agent Reference: shell-runner'
type: reference
status: active
created: 2026-10-12
last_updated: 2026-10-12
components:
- build_orchestration
- agent_registry
related_docs:
- docs/agents/conventions.md
- docs/architecture/adrs/ADR-070-shell-runner-runs-workflow-shell-commands.md
- docs/architecture/components/agent-registry.md
related_code:
- templates/agents/shell-runner.md
- templates/workflows-js/_shared/workspace-answer.js
- config/agent_registry.json
description: 'Reference for shell-runner, the one narrow executor every workflow shell step is dispatched to.'
---
# Agent Reference: `shell-runner`

Implementing agent: `shell-runner` (Haiku, internal, dispatched by workflow scripts only).
Family: `utility/`. Registry: tier `utility`, `permits_shell: true`,
`is_ticket_phase: false`, empty `spawn_allowlist`, tools: `Bash` only.

Runs one exact command line, once, unchanged, and relays its exit status,
stdout and stderr verbatim. It decides nothing and holds no allow-list of
commands. Decision record: [ADR-070](../../architecture/adrs/ADR-070-shell-runner-runs-workflow-shell-commands.md).

---

## 1. When It Is Used

| Caller | Step |
|---|---|
| Every workflow in `templates/workflows-js/` | The workspace step (`workspace-ensure`): the workspace maker command, run unchanged |
| `build-epic`, `build-feature`, `build-ticket`, `create-ticket`, `finalize-feature`, `plan-feature`, `quick-fix`, `fast-lane-ship` | Every other step whose prompt runs a shell command (git, gh, python, node, pytest and similar) |

Exception: the fast lane's command steps stay with `command-step-runner`
(BO-2400f-5-i). Both executors use the same reply shapes, so one reply check
in the workflow runtime serves both.

Do not use it for: choosing, fixing, retrying or substituting a command;
editing files; writing code or tests; acting as another agent's role.

---

## 2. Input

One command line with absolute paths. Compound lines (`&&`, `||`, `;`,
newline-separated scripts) are declined.

## 3. Reply Contract

Exactly one JSON value, never a hybrid.

| Reply | Shape | Meaning |
|---|---|---|
| Result | `{command, exit_status, stdout, stderr}` | The command ran. A non-zero exit is still a result. JSON printed by the command stays an unparsed string inside `stdout`. |
| Decline | `{declined: true, agent: "shell-runner", reason}` with no `exit_status` key | Nothing was run. |

## 4. Caller Rule

Workflows read every reply through the shared `shellStepReply` check in the
WORKSPACE-ANSWER block (`templates/workflows-js/_shared/workspace-answer.js`).
A decline, prose, non-JSON or result-less reply ends the run with an error that
quotes the reply (up to 2 KB). Nothing is dispatched afterwards, and a refusal
is never taken as the step having run.

## 5. Enforcement

`unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py` lints every
`templates/workflows-js/*.js` and fails when a shell-running dispatch targets
an agent whose registry entry lacks `permits_shell: true`. No existing agent's
charter changed to make this pass.
