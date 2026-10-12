---
title: "The fast lane's claim is run by an agent with no grounds to refuse it (BO-2400a-1-v)"
date: "2026-09-30"
time: "16:00"
type: manual
components:
  - build_orchestration
summary: "The claim command step now goes to the dedicated command-step-runner instead of worktree-agent, and a refusal to run it is structurally distinguishable from the store reporting a hold."
description: "BO-2400a-1-i built a dedicated command-step-runner — an agent whose entire role is to run one given command in one named workspace — and nothing adopted it; its own adopter_notes recorded the adoption as routed elsewhere, so the gap was invisible. This is that adoption, for the fast lane's claim step only. The performer was worktree-agent, chosen in BO-2400f-7-iii when it was the only registry entry declaring permits_shell true, with a stated weakness that its charter is 'exactly two actions: create and remove' and it could decline a store mutation exactly as status-checker had. KI-BO-20260927 names this agent as the durable fix for that whole class, about forty dispatches across six workflows; one is adopted here so the first adoption is proven before it is repeated. The contract change is the substance, not the agentType line. command-step-runner returns {command, workspace, exit_status, stdout, stderr} and never interprets what the command printed, so the gate payload is now parsed caller-side out of stdout by interpretClaimRunnerReply. The previous prompt had asked the performer to both run the command and, on failure, synthesise target_refused — the gate's own vocabulary — which is why a role refusal and real contention were the same token, separable only if the agent also remembered to leave excluded_claimed empty. That split is now structural: a decline carries no exit_status key, and target_refused can only reach the lane from _fl_lifecycle.py's stdout, so no reply the agent can produce forges a claim the store never made. The dispatch schema deliberately requires nothing, because a result and a decline share no mandatory key and requiring either rejects the other — the mirror image of the BO-2400f-7-iv defect. Two test defects were found while verifying, both more serious than the drift that exposed them. BO-2400f-7-iii's non-regression arm, whose docstring claims it 'fails any fix that turns EVERY claim failure into not attempted', did not: its fixture message said 'already in_progress, held by run wf_abc123' and the lane echoes the reply into the halt detail, so the words it searched for were its own, and its inline marker list included in_progress which the not-attempted halt also contains. It passed against a lane that had stopped classifying contention entirely. It now uses a neutral fixture and the shared strict _CONTENTION_MARKERS, and is mutation-proven: reintroducing the exact regression turns that one test red. BO-2400f-7-iv's schema extractor walked backwards from the claim label to the nearest preceding required list; when this dispatch stopped declaring one, the walk did not fail — it found an unrelated dispatch's ['producible'] and reported it as the claim's contract. It is now anchored on the schema's own named const and raises when that anchor is absent. Seven test files each carried their own literal copy of the reply shape and went stale together; that shape is now defined once in _fast_lane_claim_fixtures.py, which is the drift BO-2400f-7-iv's own it_requirements argues against. The claim's performer test was also strengthened from a deny-list of one name to a registry lookup asserting permits_shell true, defaulting to False when absent since absent means read-only. Verified: 94 tests green across all 13 files that reach the claim step, ruff clean on every changed file (the repo's 46 pre-existing errors are unchanged from main), AC store valid at 1194 records, registry validator consistent. Not in scope and still live: RELEASE_EXECUTOR_AGENT_TYPE is still python-coder, and two read-only status-checker dispatches remain at the resolve and producibility steps."
---

## Entry

### Changed

- `templates/workflows-js/fast-lane-ship.js` — the claim step dispatches to
  `command-step-runner` with the request shape that agent requires (step,
  command, and a target naming workspace, branch and ac_id — a request with no
  workspace named is a decline, not a run). Adds `interpretClaimRunnerReply`,
  which reduces the runner's reply to the lifecycle payload the phase already
  speaks, or to `null` meaning the store was never reached. The three-way
  decline / contention / success decision below it is unchanged.

- `config/agent_registry.json` — `command-step-runner.spawned_by` gains
  `fast-lane-ship.js`; the description's "Not yet listed under fast-lane-ship.js"
  sentence is replaced with what is now true.

- `scripts/registry_validator.py` — `_EXTERNAL_CALLERS` gains
  `fast-lane-ship.js`, alongside the existing `finalize-feature.js` precedent.
  Without this the asymmetric-spawn check rejects a non-agent dispatcher.

- `templates/agents/command-step-runner.md` — adopter_notes replaced. The old
  text described the adoption as not yet done and routed elsewhere; the new text
  records what an adopter must do (send the full request shape; parse the
  command's output caller-side) and points at the remaining candidates.

- `docs/agents/cards/command-step-runner.card.md` — regenerated for the new
  `spawned_by`. Four other cards also regenerate differently from what is
  committed on main; that pre-existing drift is left alone.

### Fixed

- `unit_tests/workflows/test_bo2400f_7_iii_claim_refusal_workflow.py` — the
  contention arm was vacuous in both directions and is now mutation-proven. The
  performer check is now a registry `permits_shell` lookup rather than a
  deny-list naming `status-checker`. The boundary sweep grows from 4 cases to 7,
  keeping the legacy agent-synthesised shapes to assert they can no longer
  authorise a claim.

- `unit_tests/workflows/test_bo2400f_7_iv_claim_reply_contract_workflow.py` —
  the schema extractor no longer silently measures a neighbouring dispatch.

### Added

- `unit_tests/workflows/_fast_lane_claim_fixtures.py` — one definition of the
  claim reply shape, replacing seven divergent literals. A decline is
  deliberately not given an `exit_status`, since that absence is the whole
  distinction.

- `docs/acceptance-criteria/.../BO-2400a-1-v.yaml` — the adoption criterion,
  with `BO-2400a-1`'s `covered_by` updated in the same commit.

- `templates/scripts/commit_guardian/hooks/check_agent_spawn_consistency.py` —
  both mermaid edge patterns accept `[\w.]+` instead of `\w+`. A spawner that is
  a workflow script rather than an agent encodes to a node id containing a dot
  (`fast_lane_ship.js`), which `\w+` could not match at all, so the edge
  vanished from the parsed set and the mirror check accused the registry of
  claiming an edge the card showed plainly. Latent for five cards carrying a
  `finalize-feature.js` edge, because the check only reads staged cards and
  cards are build output nobody stages. Its `_EXTERNAL_CALLERS` — a separate
  copy from `registry_validator.py`'s — gains `fast-lane-ship.js` for the same
  reason the validator's did.

### Resolved

- `KI-BO-20260921-worktree-base-resolver-defaults-to-cwd` — closed against
  `BO-4000f`, verified by reading `templates/workflows-js/build-feature.js` on
  `origin/main` rather than the deployed copy, which was hand-patched on
  2026-09-21 and would have looked fixed either way. The closure note records
  that the remedy was broader than the reported defect (one shared `repoAnchor`
  for all four calls, not a patch to the one that omitted it) and that the cwd
  fallback still exists for relative targets — narrower than the original, not
  currently known to occur, and not closed.

### Filed

- `KI-BO-20260930-fast-lane-ship-is-649-lines-over-and-cannot-grow` —
  `fast-lane-ship.js` stands at 1649 counted lines against a 1000 limit, so the
  ratchet refuses every non-shrinking commit to the fast lane and each one needs
  a written skip. This change took such a skip (user-authorised, +24 lines) and
  filed the entry rather than absorbing it quietly. The usual remedy does not
  apply directly: "extract, don't compress" is right, but workflow scripts are
  self-contained bundles, so the split needs its own design decision about how a
  workflow may be composed at all — recorded in the entry as step 1 of the fix,
  ahead of any mechanical extraction.
