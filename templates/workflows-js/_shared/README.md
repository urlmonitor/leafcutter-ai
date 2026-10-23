# `_shared/` -- single sources inlined into workflows

Files here are not deployed as workflows (the workflow glob is shallow). Each is the single
tracked source of a block that `scripts/build_phases_workflows.py` copies between a marker pair
in every consuming workflow template, because E2 workflow bodies cannot `require` (ADR-030).

| File | Markers | What it holds |
|---|---|---|
| `workspace-answer.js` | `// WORKSPACE-ANSWER-START` / `// WORKSPACE-ANSWER-END` | The acceptance predicate for the workspace maker's answer, the one shell-step reply check (`shellStepReply`), and the single dispatch helpers that send the maker command to `shell-runner` (BO-4300c-3, ADR-070) |
| `commit-answer.js` | `// COMMIT-ANSWER-START` / `// COMMIT-ANSWER-END` | `decideCommitAnswer(reply, history)`: a pure decision (continue / retry / engage / stop / report) for every commit-step reply; the configured retry ceiling and reason-code families are filled from `config/commit_step.json` at install; engages a specialist at most once and only for an `engage-specialist` remedy with a usable demand (BO-4500b-3). Awaiting adoption by routes: see `awaiting-adoption.json` |

Rules:
- Edit the source here, never a copy inside a workflow. A template whose marker pair already
  holds text fails the build; a second build writes nothing.
- A decline, prose, non-JSON or result-less reply ends the run quoting it (up to 2 KB); no
  fallback to the current checkout, epic folder or start folder.
- Related: [ADR-070](../../../docs/architecture/adrs/ADR-070-shell-runner-runs-workflow-shell-commands.md),
  [shell-runner reference](../../../docs/agents/utility/shell-runner.md).
