---
title: "KI-BO-20260925-finalize-gate-accepts-agent-answers — finalize-feature's copy of the human-gate code still asks an agent to answer live and never checks the answer came from the person, so the merge-to-main gate can be passed by an agent reply"
description: "blocker — resolveGate/pauseAtGate are hand-copied between plan-feature and finalize ('keep them in sync'); the KI-ACD-005 and KI-ACD-004 fixes reached plan-feature only. Code-verified; the merge-path consequence is inferred, not reproduced."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-27'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/ac-driven-dev/resolved/resolved-blocker-ki-acd-005.md
  - docs/known-issues/ac-driven-dev/resolved/resolved-blocker-ki-acd-004.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md
---

# KI-BO-20260925-finalize-gate-accepts-agent-answers — finalize-feature's copy of the human-gate code still asks an agent to answer live and never checks the answer came from the person, so the merge-to-main gate can be passed by an agent reply

- **Severity:** blocker. The gate in front of "merge PR to main" — the most destructive step in the package — has the same shape KI-ACD-005 fixed elsewhere.
- **Status:** open — no AC. Code read and diffed 2026-09-25; **the end-to-end merge scenario is inferred, not reproduced.** Verify before fixing.
- **Where:** `templates/workflows-js/finalize-feature.js:291-295` ("keep them in sync"), `:386-402` (`resolveGate` live path), `:372`, `:444` (pause store), `:2033-2067` (step-4 merge gate).

## Mechanism

When no matching `resume_answer` is present, finalize's `resolveGate` calls the live gate and returns any
object with an `action` or `choice` string:

```js
if (typeof liveGateFn === "function") {
  try { gateAnswer = await liveGateFn(); } catch (_err) { gateAnswer = null; }
}
if (gateAnswer !== null && ... typeof gateAnswer.action === "string" ...) {
  return gateAnswer;
}
```

The step-4 live gate dispatches status-checker to "Ask the user" (`:2033-2049`); an `{action: "ok"}`-shaped reply
proceeds to the merge (`:2067`). There is no `channel === "person"` check anywhere in the file (grep: 0 hits).

## Divergence from plan-feature's copy

| Behaviour | plan-feature | finalize-feature |
|---|---|---|
| Live agent answering | removed (`void liveGateFn`, `:1807`) | still active (`:394`) |
| `channel === "person"` provenance check | `:1671` | absent |
| Pause-store command | repo-anchored `buildPauseStoreCommand` (`:2178`) | cwd-relative `{{config.output_root}}/scripts/pause_store.py` |
| Persist verification | `pause-persist-verify` → `pause_persist_failed` | none |
| Clear record after resume | yes | no |

Function bodies differ by 67 lines (`resolveGate`), 34 (`pauseAtGate`), 4 (`applyAnswerByType`).
`unit_tests/.../test_acd_2100c_1.py` extracts `resolveGate` from plan-feature only, so finalize's copy is untested.

## Fix direction

One gate module shipped as a marker-delimited block (precedent: `BO-3900-PATH-HELPERS-START/END`) inlined by the
build into every workflow, with a byte-identity parity test; no live-answer path, `channel: "person"` required,
repo-anchored store, persist-verify. Cluster 3 of the 2026-09-25 duplication analysis.

## Added 2026-09-27 — the pause-store dispatches go to an agent chartered not to run them

A second divergence from plan-feature. It affects the headless path this entry's table already lists as unverified.

- **Where (re-verified on main at 93bd801c):** `templates/workflows-js/finalize-feature.js:374` (`read-pause-record`) and `:446` (`pause-persist`). The `:372` / `:444` citations above are the command lines these two dispatches carry. Both call `agent(..., { agentType: "status-checker", ... })` and tell it to run `python {{config.output_root}}/scripts/pause_store.py read|write ...` (`:372`, `:444`).
- **The agent's charter:** `config/agent_registry.json:1296-1300` gives `status-checker` `permits_shell: false`. Its template scopes it to ticket investigation: *"Edits restricted to `tickets/**/*.md` ... Never edit code"* (`templates/agents/status-checker.md:221`). The one agent with `permits_shell: true` is `worktree-agent` (`config/agent_registry.json:1364-1368`).
- **Observed in plan-feature (session observation, not re-verified here):** in `/plan-feature` run `wf_734389cf-248` (2026-09-25), the identical pause-persist dispatch was refused by `status-checker`, which declined to run `pause_store.py write`. The run ended `pause_persist_failed`, the outcome of plan-feature's persist-verify step. The run left no artifacts on disk, so this rests on the session record.
- **plan-feature was fixed; finalize was not.** BO-2300a-1-ii (PR #896, `06bfbddf`, merged 2026-09-25) moved plan-feature's six pause-store dispatches to a local `_shellPermittedAgentId = "worktree-agent"` (`plan-feature.js:1604`, `:1652`, `:1836`; dispatches `:1610`, `:1695`, `:1739`, `:1768`, `:1865`, `:1886`). finalize-feature.js got no equivalent change. This is the same hand-copied-twin failure as the table above.
- **Why it is worse here than in plan-feature:** finalize has no persist-verify (see the table). If `status-checker` refuses the write at `:446`, `pauseAtGate` still returns `paused_awaiting_input` (`:447`) with no record on disk. The run then reports a pause that no later run can resume. That is inferred from the code path, not reproduced.
- **Fix direction:** fold this into the shared gate module above, with one executor for all pause-store calls. Until then, apply the #896 change to `:374` and `:446`. The residual in `KI-BO-20260927-status-checker-runs-workflow-shell-commands` applies too: `worktree-agent`'s charter names worktree create/remove only, so it is a stopgap, not a chartered executor.
