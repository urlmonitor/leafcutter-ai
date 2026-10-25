---
title: "KI-ACD-20261022-plan-feature-entry-omits-the-permission-verdict — the /plan-feature command and skill pass only args.workspace, but the workflow halts unless args.workspace_setup_permission is also passed, so every run started as documented stops before Stage 0"
description: "high — templates/commands/plan-feature.md:38 and the plan-feature skill's §WS.2 pass only `workspace`. plan-feature.js:2203-2218 halts with 'No workspace-setup permission pre-flight verdict' when args.workspace_setup_permission is absent. The skill dropped its §WSP pre-flight on 2026-10-10; the workflow kept the check. Code verified at origin/main 411b87761."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
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
- **Status:** open. No AC. Traced to code.
- **Occurrences:** 1 (driving `/plan-feature` for KM-400d-4-i..iii from a workspace made by
  `.leafcutter/scripts/worktree.py ensure --kind ac`, 2026-10-22)
- **First seen:** 2026-10-22 · **Last seen:** 2026-10-22
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
