---
title: "KI-BO-20261025-template-ticket-commit-and-redrive-dead-ends — in an epic workspace, a ticket that edits an agent template cannot pass its commit phase, and a ticket that halts after creating a new script blocks every re-drive of the epic"
description: "high — the commit agent's remedy for a check-build-drift refusal is to rebuild through the workspace maker, but the maker's rebuild records the committed template hashes, so the refusal repeats until the drive halts. A direct build clears it only after the deployed agent copies are refreshed by hand. Separately, the build's tracked-source guard refuses while any new script is uncommitted, so after such a halt the next /build-feature run stops at Resolve Target. Both seen on 2026-10-25 in EPIC-OnceANamedWrongVersionIsPreparedAnd."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - build_orchestration
  - build_pipeline
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-pipeline/open-low-ki-bp-20261009-epic-worktree-install-goes-stale-per-ticket.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261009-one-halted-ticket-stops-the-whole-epic-run.md
---

# KI-BO-20261025-template-ticket-commit-and-redrive-dead-ends — two dead ends after one halt

> Filed 2026-10-25. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high. Nothing wrong is committed, because every guard fails closed. But a drive
  cannot finish on its own: every ticket that edits a template in check-build-drift's scope
  halts at commit, and a halt after a new script is created stops every later drive at its first
  step.
- **Status:** open, no AC.
- **Occurrences:** 1 drive, run `wf_c4f8ba47-9c0` (ticket 01 TQ-500f-2-iii: three commit attempts,
  all refused; ticket 02 TQ-500g-1-xi left two new scripts uncommitted).
- **First seen:** 2026-10-25 · **Last seen:** 2026-10-25

## Symptom 1: the commit phase cannot clear check-build-drift

Ticket 01 changed `templates/agents/test-designer.md` and `templates/agents/test-breaker.md`.
The commit step answered `hook_failed` on check-build-drift (`drifted=2`, `remedy: null`) three
times. The commit agent's stated remedy each time: "re-run build.py through the workspace maker
(scripts/worktree.py), stage the regenerated outputs, and dispatch commit again".

That remedy does not work. `worktree.py ensure` re-readied the workspace (`build_ok: true`), but
afterwards `.build_manifest.json` held, for `templates/agents/test-breaker.md`, the sha256 of the
**committed** file (`9456c75a…`, equal to `HEAD` and `origin/main`), not of the edited file
(`6adaac6a…`). Staging the edits first and re-running ensure changed nothing.

What did clear it:

1. `python <ws>/scripts/build.py --target-dir <ws> --log-root <recorded root> --config-path
   <ws>/.leafcutter/derived_skills_config.json`. This recorded the edited hashes. It ended with
   `[ERROR] Build cannot complete cleanly` for the adopter-owned `.claude/settings.json` and
   `.pre-commit-config.yaml`, and left `.claude/agents/` and `.gemini/agents/` untouched
   ("adopter_owned").
2. check-output-drift then refused, because those two copies no longer matched the manifest's
   expected output. Copying the new `.leafcutter/agents/<name>.md` over both cleared it.

## Symptom 2: a halted ticket's new script blocks every re-drive

Ticket 02 halted at the wrong-version gate with two new files, `scripts/build_orchestration/_wvp_plan.py`
and `_wvp_store.py`, uncommitted. The next `worktree.py ensure` for the epic (the first step of
any `/build-feature` run) answered:

```
{"status": "refused", "code": "BOOTSTRAP_FAILED", ... "failure_excerpt": "[TRACKED-SOURCE GUARD]
UNTRACKED SOURCE: scripts/build_orchestration/_wvp_plan.py | ... Build aborted: commit the above
sources to git before running the build."}
```

`git add -N` does not satisfy the guard. So the only ways forward are to commit the halted
ticket's unfinished work, or to stash it.

## Workaround

Stash the other tickets' work, build directly as above, refresh the two agent copies, commit
from the main loop, then pop the stash. Finish a halted wrong-version gate by hand (`list`, the
journal's own test-breaker reply, `finish`) instead of re-driving.

## Fix direction (not decided)

- The commit phase, or the step before it, rebuilds from the working tree when the ticket's
  diff touches check-build-drift's scope, and refreshes the deployed agent copies.
- The maker's re-ready either builds from the working tree or says it built from `HEAD`.
- A halted ticket's new sources do not block the next drive's workspace step.
