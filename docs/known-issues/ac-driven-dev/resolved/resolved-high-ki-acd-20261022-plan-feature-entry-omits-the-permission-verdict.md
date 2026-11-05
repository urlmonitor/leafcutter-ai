---
title: "KI-ACD-20261022-plan-feature-entry-omits-the-permission-verdict — the /plan-feature command and skill pass only args.workspace, but the workflow halts unless args.workspace_setup_permission is also passed, so every run started as documented stops before Stage 0"
description: "high — templates/commands/plan-feature.md:38 and the plan-feature skill's §WS.2 pass only `workspace`. plan-feature.js:2203-2218 halts with 'No workspace-setup permission pre-flight verdict' when args.workspace_setup_permission is absent. The skill dropped its §WSP pre-flight on 2026-10-10; the workflow kept the check. Code verified at origin/main 411b87761."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-11-04'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/how-to/get-a-workspace.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-20261022-rule-check-resolves-the-store-root-against-the-session-cwd.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20261022-pause-persist-failed-at-gate-ba-in-a-maker-workspace.md
---

# KI-ACD-20261022-plan-feature-entry-omits-the-permission-verdict — the /plan-feature command and skill pass only args.workspace, but the workflow halts unless args.workspace_setup_permission is also passed, so every run started as documented stops before Stage 0

- **Severity:** high. Every `/plan-feature` run started the documented way halts before any
  authoring agent runs. The halt is loud and nothing is lost, but the message points at a skill
  step that no longer exists, so the user cannot fix it from the docs.
- **Status:** RESOLVED 2026-11-04 by ACD-2100d-5 (and -i..-iv), fix direction 2: the workflow no
  longer requires `args.workspace_setup_permission` when the maker's answer is supplied, and a start
  with neither stops before authoring naming only remedies that exist. Proved by
  `unit_tests/workflows/test_acd_2100d_5*.py`, which start the installed workflow with the arguments
  read from the installed command and skill (ACD-2100d-5-i), and
  `unit_tests/reference/test_acd_2100d_5_iv.py`.
- **Occurrences:** 3 (driving `/plan-feature` for KM-400d-4-i..iii from a workspace made by
  `.leafcutter/scripts/worktree.py ensure --kind ac`, 2026-10-22; `/plan-feature` run
  `wf_d2396526-264` for the TQ-200d before-score fixes, workspace `ac/tq-200d-before-score-fixes`,
  2026-10-29 19:51 UTC, see [the occurrence section](#occurrence-2026-10-29--still-open-at-base-d62440669);
  run id `pf-entry-pause-20261104`, 2026-11-04, workaround applied up front)
- **First seen:** 2026-10-22 · **Last seen:** 2026-11-04
- **Where:** `templates/workflows-js/plan-feature.js:2203` (reads
  `args.workspace_setup_permission`) and `:2206-2218` (the fail-closed halt). The entry surfaces
  that omit it: `templates/commands/plan-feature.md:34-38` and
  `templates/skills/plan-feature/SKILL.md:157-163` (§WS.2).

## Symptom

The run returned `status: "error"` with: "No workspace-setup permission pre-flight verdict was
supplied in args (args.workspace_setup_permission). ... the plan-feature skill's pre-flight
(scripts/worktree/check_workspace_setup_permission.py) must run BEFORE this workflow is invoked".
The run had been started with `args.workspace` set to the maker's answer, as the command and skill
say.

## Mechanism

1. The command's Step 2 invokes `Workflow("plan-feature", { userInput: $ARGUMENTS, workspace:
   <maker-answer> })` (`templates/commands/plan-feature.md:38`). The skill's §WS.2 says the same:
   pass the maker's stdout as `args.workspace` (`SKILL.md:159`). Neither mentions
   `workspace_setup_permission`.
2. The skill's decision history records why: on 2026-10-10
   (`TICKET-20260928-BO-4300-entry-skills`) §WSP, the permission pre-flight, was replaced by §WS
   (`SKILL.md:682-685`). The §WSP entry that put the verdict into `args` is still listed below it
   (`SKILL.md:704-710`), but the section is gone.
3. The workflow kept the check. `:2203` reads `args.workspace_setup_permission`; `:2206` halts when
   it is missing or not an object. The check runs unconditionally, before the maker answer is read
   (`:2268-2279`), so a valid `args.workspace` does not get past it.
4. The halt message names the skill's pre-flight as the fix. That pre-flight no longer exists in
   the skill.

## Detection

A `status: "error"` whose message starts "No workspace-setup permission pre-flight verdict was
supplied". `grep -n workspace_setup_permission .claude/commands/plan-feature.md` finds nothing.

## Workaround

Run the pre-flight by hand and pass its JSON verbatim:

```bash
python "<workspace>/.leafcutter/scripts/worktree/check_workspace_setup_permission.py" --agent-id shell-runner
```

Then invoke the workflow with both `workspace: <maker-answer>` and
`workspace_setup_permission: <that JSON>`. This worked on 2026-10-22.

## Fix direction

Make the two halves agree, in one change:

1. Either restore the pre-flight to the command and skill (run the script, pass
   `args.workspace_setup_permission`), or
2. drop the check from the workflow when the maker's answer is supplied, since the workspace is
   already made and the workflow no longer runs the setup step itself. Update the halt message and
   the rationale doc either way.

Add a test that runs the workflow with exactly the args the command template builds, so the two
cannot drift apart again.

**Pattern:** a contract changed on one side. The skill's rewrite removed the producer of an
argument; the consumer still requires it and fails closed.

## Occurrence 2026-10-29 — still open at base d62440669

`/plan-feature` run `wf_d2396526-264` (session `741a653a`), started with `args.workspace` only, as
the skill says. It returned `status: "error"` with the same message, word for word, and dispatched
no agent: its `journal.jsonl` holds only `launched`. The session re-ran the workflow with a
hand-run verdict in `args.workspace_setup_permission` and it went past the check.

Both halves are unchanged at base `d62440669` (branch `ac/tq-200d-before-score-fixes`; line
numbers moved slightly since the first filing):

- **Skill**, `templates/skills/plan-feature/SKILL.md` (deployed as
  `.claude/skills/plan-feature/SKILL.md`; the two differ only in the frontmatter description):
  - The DECISION HISTORY entry at `:681-683`: "2026-10-10
    [TICKET-20260928-BO-4300-entry-skills/llm-expert]: Replaced §WSP (workspace-setup permission
    pre-flight) with §WS: the skill runs the one workspace maker once and passes its answer as
    args.workspace."
  - §WS.2 at `:157-163`: pass the maker's stdout "VERBATIM as `args.workspace`". It does not mention
    `workspace_setup_permission`.
  - The older §WSP entry is still listed at `:704-710` ("The verdict crosses into the workflow
    through args.workspace_setup_permission"), but the section it describes is gone.
- **Command**, `templates/commands/plan-feature.md:38`: `Workflow("plan-feature", { userInput:
  $ARGUMENTS, workspace: <maker-answer> })`.
- **Workflow**, `templates/workflows-js/plan-feature.js`:
  - `:2195-2196` comment: the verdict "arrives as `args.workspace_setup_permission` (the
    pre-flight check runs outside this body) and a missing verdict fails closed".
  - `:2203` reads `args.workspace_setup_permission`.
  - `:2206-2217` halts when it is missing: "No workspace-setup permission pre-flight verdict was
    supplied in args ... the plan-feature skill's pre-flight
    (scripts/worktree/check_workspace_setup_permission.py) must run BEFORE this workflow is
    invoked". The check still runs before the maker answer is used (`:2268` onwards).

Graded `high` at the first filing; the brief for this occurrence called it low. The grade is left
as filed: every run started the documented way still stops, even though the halt is loud and the
workaround above still works.

## Occurrence 2026-11-04 — workaround applied up front

The run that planned this fix (run id `pf-entry-pause-20261104`, base `c4bcf1c14`) ran
`check_workspace_setup_permission.py --agent-id shell-runner` by hand before the first start and
passed its verdict with `args.workspace`. All three starts went past the check. The verdict's
`location` was the main checkout's `.leafcutter/config/agent_registry.json`, not the workspace's,
which is worth checking when the fix lands.
