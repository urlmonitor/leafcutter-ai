---
title: "KI-ACD-20261022-rule-check-resolves-the-store-root-against-the-session-cwd — /plan-feature's stage rule check passes a relative --store-root and never enters the workspace, so from the workspace parent the store resolves 'outside the repository' and the stage fails on good records"
description: "high — runRuleCheck() (plan-feature.js:2003-2005) sends `--store-root \"docs/acceptance-criteria\"` (acStoreDir, :2283; the maker never supplies ac_store_path) with no cd into the workspace. requirement_rule_check.py:164 resolves it against the shell's cwd, the workspace parent, and _rc_changed.py:55 refuses it. The IT PO stage failed after 2 attempts on valid records. Code verified at origin/main 411b87761."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260925-shared-root-resolver-accepts-non-repo-workspace-parent.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-20260927-repo-anchor-picks-the-in-repo-install-copy.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-20261022-plan-feature-entry-omits-the-permission-verdict.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20261022-pause-persist-failed-at-gate-ba-in-a-maker-workspace.md
---

# KI-ACD-20261022-rule-check-resolves-the-store-root-against-the-session-cwd — /plan-feature's stage rule check passes a relative --store-root and never enters the workspace, so from the workspace parent the store resolves "outside the repository" and the stage fails on good records

- **Severity:** high. A stage fails on records that are valid. The run aborts after its edit
  retries, and the failure message lists draft paths that do not exist. A user who trusts the
  message re-authors or discards good work.
- **Status:** open. No AC. Traced to code. The cwd of the dispatched shell is inferred from the
  observed path; it is not printed by the workflow.
- **Occurrences:** 1 (IT PO stage, `/plan-feature` for KM-400d-4-i..iii from a workspace made by
  `.leafcutter/scripts/worktree.py ensure --kind ac`, 2026-10-22)
- **First seen:** 2026-10-22 · **Last seen:** 2026-10-22
- **Where:** `templates/workflows-js/plan-feature.js:1999-2021` (`runRuleCheck()`, command built at
  `:2003-2005`) and `:2283` (`acStoreDir`). The same relative store root goes to
  `runStageScript()` (`:2025-2030`, design pre-pass and approval holds). The refusal is
  `scripts/ac_store/requirement_rule_check.py:164` plus `scripts/ac_store/_rc_changed.py:55`.

## Symptom

The IT PO stage "failed after 2 attempts". The rule check said the store root
`/home/henzeh/projects/leafcutter/docs/acceptance-criteria` was "outside the repository". That
path is the session's directory (the workspace parent), not the workspace. The records were fine.
This manual run against the same workspace passed:

```bash
python requirement_rule_check.py --changed-since HEAD --stage itpo --before-ref HEAD \
  --repo-root <workspace> --store-root <workspace>/docs/acceptance-criteria
```

Without `--before-ref` it fails "before-state unavailable" (`requirement_rule_check.py:232`); the
workflow does pass `--before-ref HEAD`, so that is not the defect. The failure message also listed
"uncommitted drafts" at paths that did not exist. `git status` in the workspace was the truth.

## Mechanism

1. `acStoreDir` is `authoringWorkspace.answer.ac_store_path` or, failing that, the relative
   `"docs/acceptance-criteria"` (`:2283`). The maker never emits `ac_store_path`: no file under
   `templates/scripts/` (where `worktree.py` lives) or `scripts/worktree/` contains that key. So `acStoreDir` is always relative.
2. `runRuleCheck()` builds `_buildRepoRootResolutionSnippet(...)` + `python ... --store-root
   "docs/acceptance-criteria" --repo-root "<workspace>" --before-ref HEAD` (`:2003-2005`). Unlike
   `buildPauseStoreCommand()` (`:1977`), it does not `cd` into the workspace first. The shell runs
   wherever the dispatched agent's shell starts.
3. `requirement_rule_check.py:164` does `Path(args.store_root).resolve()`, which is relative to the
   process cwd, not to `--repo-root`. From the workspace parent that gives
   `<parent>/docs/acceptance-criteria`.
4. `_rc_changed.py:55` then refuses: "store root ... is outside the repository <workspace>". The
   verdict is `failed`, so the gate forces `edit` (`:2917`). After `MAX_EDIT_RETRIES + 1` = 2
   attempts the stage aborts (`:2936-2941`).
5. The draft paths in the abort message are made up. When the failed report has no
   `records_to_commit`, `buildCancelMessage()` prints `<store>/<id>.yaml` (`:567-569`). The store
   is hierarchical, so those flat paths never exist.
6. Inferred: from a non-repo cwd the snippet also resolves `$REPO_ROOT` by probing child
   directories (`:1922-1944`), so the script that runs is the main checkout's gitignored
   `.leafcutter/` copy, not the workspace's. That is the wrong-copy defect of
   `KI-ACD-20260927-repo-anchor-picks-the-in-repo-install-copy`.

## Related

`KI-CG-20260925-shared-root-resolver-accepts-non-repo-workspace-parent` is the same class in the
commit-guardian hooks: a path resolved from a non-repo workspace parent is accepted as if it were
the repository. Here the script does refuse, which is better, but the refusal is reported as a
record failure.

## Detection

A stage rule-check failure whose finding says "store root <path> is outside the repository", where
`<path>` is not under the workspace. Re-run the manual command above with absolute paths. If it
passes, this is the defect. Trust `git -C <workspace> status`, not the listed draft paths.

## Workaround

Verify the records with the manual command above. Commit the stage output from the main loop, then
start a new run, which resumes past the committed stage. Starting the session with cwd inside the
workspace should also avoid it (inferred, not tried).

## Fix direction

1. Pass an absolute store root: `acStoreDir = <workspace_path>/docs/acceptance-criteria` when the
   maker gives no `ac_store_path`. Apply it to every `runStageScript()` call too.
2. Prefix the rule-check and stage-script commands with `cd "<workspace>" || exit 1;`, as
   `buildPauseStoreCommand()` does.
3. In `requirement_rule_check.py`, resolve a relative `--store-root` against `--repo-root`, not the
   cwd.
4. In `buildCancelMessage()`, do not invent paths. When the record paths are unknown, say so and
   point at `git status`.

**Pattern:** a relative path handed across a process boundary. The caller meant "relative to the
workspace"; the callee read "relative to wherever I started".
