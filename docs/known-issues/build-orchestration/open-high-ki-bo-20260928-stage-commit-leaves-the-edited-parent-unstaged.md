---
title: "KI-BO-20260928-stage-commit-leaves-the-edited-parent-unstaged — plan-feature's stage commit stages only the AC ids the stage agent reported, never the parent whose covered_by the agent was required to edit, so check-ac-parent-covered-by refuses every stage that adds children to an existing parent"
description: "high — commitStageOutput tells the commit agent to keep only files whose stem equals an id in acs_written (plan-feature.js:392-413). The business-analyst template requires a covered_by edit on the parent (business-analyst.md:417-441), and that edit is never staged. Observed in wf_a2fd1222-f54: BP-100k-4-iv..vii were refused. Related gap: a done parent cannot take todo children (check-done-proof) and the workflow has no path for it."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-001.md
  - docs/known-issues/ac-store/open-low-ki-acs-016.md
---

# KI-BO-20260928-stage-commit-leaves-the-edited-parent-unstaged — plan-feature's stage commit stages only the AC ids the stage agent reported, never the parent whose covered_by the agent was required to edit, so check-ac-parent-covered-by refuses every stage that adds children to an existing parent

- **Severity:** high. Every behavioral-route BA stage that adds children to an existing parent
  fails at its commit, after the human has approved the ACs. The run ends `status: "error"` with
  the drafts left uncommitted in the authoring worktree.
- **Status:** open. No AC. Traced to code.
- **Occurrences:** 1 (`/plan-feature` run `wf_a2fd1222-f54`, run id
  `plan-ki-cg-20260831-0713-20260927`, BA stage, 2026-09-27)
- **First seen:** 2026-09-27 · **Last seen:** 2026-09-27
- **Where:** `templates/workflows-js/plan-feature.js:287` (`commitStageOutput()`), its staging
  rule at `:392-397` and the stem filter at `:408-413`. The id list comes from the stage agent's
  `acs_written` (`:3206`) and is passed at `:3323` (mid-pipeline commit) and `:3499` (final
  commit). The orphan-recovery commit at `:917` passes orphan ids the same way.

## Symptom

The BA wrote `BP-100k-4-iv`, `-v`, `-vi` and `-vii` and, as its template requires, appended them
to `BP-100k-4.yaml`'s `covered_by`. It returned `acs_written: ["BP-100k-4-iv", "BP-100k-4-v",
"BP-100k-4-vi", "BP-100k-4-vii"]`. After `gate-ba` was approved (on resume), the run ended with:

```
Commit of business-analyst AC output failed. Hook "check-ac-parent-covered-by" rejected the staged files.
  Conflicting/failing files:
    - docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100k-4-iv.yaml
    - .../BP-100k-4-v.yaml
    - .../BP-100k-4-vi.yaml
    - .../BP-100k-4-vii.yaml
    - .../BP-100k-4.yaml
```

The parent was not staged. It appears in the list because the hook names it in its message
("Parent file: ... stage the parent file"), and the commit agent collects every path from the
hook output (`:451-462`).

## Mechanism

1. The BA's edit to the parent is mandatory. `templates/agents/business-analyst.md:417-441`
   ("Parent covered_by update (mandatory)") says to append the child id to the parent's
   `covered_by` in the same pass as writing the child.
2. The commit prompt forbids staging it. `:392-397`: *"You MUST stage ONLY the files that
   correspond to the AC IDs listed above."* `:408-413` keeps only paths *"whose filename stem ...
   is exactly equal to one of the AC IDs above"*. The parent's stem, `BP-100k-4`, is not in
   `acs_written`, so it stays unstaged. The docstring at `:268-269` states the same rule.
3. The hook then sees the old parent. `pre-commit` stashes unstaged changes before it runs the
   hooks, so during the hook run `BP-100k-4.yaml` holds its committed content, without the four
   new ids. `check_ac_parent_covered_by.py` finds each staged child missing from the parent's
   `covered_by` and fails (`templates/scripts/commit_guardian/check_ac_parent_covered_by.py:515`,
   `_check_file()`).
4. The repo's `CLAUDE.md` ("AC-store commits — stage the parent alongside the child", line 358)
   requires the opposite of step 2: stage the parent in the same commit whenever a commit adds a
   child or changes `covered_by`.

The rule in step 2 exists for a good reason: it keeps a stage from sweeping up other stages' or
the user's files. It stops one hop short, because the stage agent's write set is its children
plus their parents, and only the children are reported.

## Related gap: a `done` parent cannot take `todo` children

Staging the parent would not have been enough here. `BP-100k-4` is `work_status: done`. Staging
it with four `todo` children in `covered_by` makes it a composite whose children do not prove it
done, and `check-done-proof` refuses that
(`templates/scripts/commit_guardian/check_done_proof.py:406`, `_unproven_composite_children()`;
a child not `done` is unproven at `:468`). Observed with `BP-100k-4` in the same session.

The workflow has no path for this. It is a human decision, not a mechanical fix: either reopen
the parent (which records a regression in a record whose own scope is still met) or re-home the
new children under a new, not-done parent. `/plan-feature` neither detects the case before the
BA writes nor offers the choice. It fails at the commit, after approval, via
`formatCommitError()` (`:514`).

## Detection

A BA or PO stage commit that fails on `check-ac-parent-covered-by`, where `git -C
<authoring-worktree> status --porcelain` shows the parent AC modified but not staged. For the
done-parent case, check the parent's `work_status` before the BA stage runs.

## Workaround

In the authoring worktree, stage the children and the parent together and commit through the
commit agent. If the parent is `done`, decide first whether to reopen it or re-home the children.

## Fix direction

1. Have the stage agent report the parents it edited (for example `parents_updated: [...]`, next
   to `acs_written`), and have `commitStageOutput()` stage those too. Alternatively, derive each
   written id's structural parent and stage it when it shows as modified. Either way the explicit,
   per-file staging rule is kept.
2. Before a behavioral-route BA stage runs, check whether the target parent is `done`. If so,
   stop at a gate that offers "reopen the parent" or "re-home under a new parent", rather than
   failing at commit after approval.
3. Cover it with a test that runs a BA stage adding a child to an existing parent through the real
   hooks. None of the `unit_tests/test_commit_stage_output_*.py` tests covers a child whose parent
   was edited.

**Pattern:** a staging rule scoped to what an agent reports, when the agent's contract makes it
write more than it reports.
