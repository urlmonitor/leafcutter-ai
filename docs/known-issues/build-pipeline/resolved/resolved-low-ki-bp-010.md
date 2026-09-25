---
title: "KI-BP-010 — Clean-mode's `workflows` entry has a doubled path segment, so it has never run and a real orphan survives every `--clean`"
description: "KI-BP-010 — Clean-mode's `workflows` entry has a doubled path segment, so it has never run and a real orphan survives every `--clean`"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-010 — Clean-mode's `workflows` entry has a doubled path segment, so it has never run and a real orphan survives every `--clean`

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** **RESOLVED** (`e5965006`, PR #793; verified 2026-09-25 by running
  `unit_tests/build_guards/test_ki_bp_010_clean_workflows.py` (3 passed) and a scratch-target
  probe of `clean_stale_artifacts` that removed an orphaned workflow, removed=1)
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-25
- **Where:** originally `scripts/build_phases.py:2820-2825` (`_MANAGED_ARTIFACT_DIRS`),
  `:2859-2864` (the join in `clean_stale_artifacts`). Both moved to
  `scripts/build_phases_clean.py` in #806 (`_MANAGED_ARTIFACT_DIRS` at `:48-53`, the join at
  `:124`), re-exported from `build_phases.py`.

**Symptom.** `_MANAGED_ARTIFACT_DIRS` mixes two path conventions in one dict. Three entries
are bare subdirectory names; the fourth carries a `.claude/` prefix:

```python
_MANAGED_ARTIFACT_DIRS = {
    "agents": "agents",
    "skills": "skills",
    "hooks": "hooks",
    "workflows": ".claude/workflows",
}
```

The consumer joins the value onto `claude_dir`, which is *already* `<target>/.claude`:

```python
claude_dir = target_dir / ".claude"
...
managed_dir = claude_dir / subdir_name        # <target>/.claude/.claude/workflows
if not managed_dir.exists():
    continue
```

That path never exists, so the loop `continue`s every time and clean-mode has **never**
cleaned workflows — silently, since the function only prints when it removes something or
when the total is zero.

**The manifest side is fine, and this correction matters.** `_build_source_manifests`
(`scripts/build.py:1246-1258`) *does* populate a `workflows` key, from
`templates/workflows-js/*.js`. An earlier draft of this finding — which reached `main` inside
KI-BP-009 via `#520` — asserted the opposite: that no such key exists, that `expected_names`
would therefore be empty, and that repairing the path would delete every deployed workflow on
the first `--clean`. That was wrong, and wrong in the expensive direction: it recommended
leaving a broken cleanup step in place. Repairing the path is safe.

**Evidence — there is a real orphan it should have caught.** In the self-hosted workspace
`.leafcutter/workflows/` holds **ten** files while `templates/workflows-js/` holds **nine**.
The extra one is `pause-resume-substrate.js`, which has no template and is claimed by
nothing:

```text
$ ls <package>/templates/workflows-js/ | wc -l
9
$ ls <workspace>/.leafcutter/workflows/ | wc -l
10
$ ls <package>/templates/workflows-js/pause-resume-substrate.js
No such file or directory
```

It is exactly the artifact the `workflows` entry was added to remove, and it survives every
`--clean` while the run reports success. This is a live instance of KI-BP-005 that the
mechanism intended to catch it cannot see.

Found while verifying KI-BP-009, not by any failure report — nothing surfaces it, because a
no-op cleanup and a genuinely clean tree produce identical output.

**Related — the other half of the workflows story.** KI-BP-008 records a *deploy* path that
can silently skip the workflow-install phase, leaving deployed workflows stale. This entry
records the *cleanup* path for the same directory never running at all. Between them,
`.leafcutter/workflows/` has neither a reliable writer nor a working reaper, and both failure
modes print success. Whoever fixes either should read the other first.

**Relationship to KI-BP-009.** Same function, same `--clean` invocation, distinct defects with
distinct fixes: BP-009 is about *whose files* clean-mode is entitled to touch; this is about a
path it cannot reach. Sequence them deliberately — repairing this one activates a code path
that BP-009 shows is unsafe for any directory an adopter also writes into. Workflows are not
currently such a directory, so the two are separable here, but only by accident of which trees
adopters happen to use.

**Fix direction.** Normalise the dict to one convention — all values relative to `.claude/`,
or all absolute from `target_dir` — and add a test that asserts every entry resolves to a real
directory in a freshly built target. A dict where three entries follow one rule and the fourth
follows another is the actual defect; the unreachable path is just where it surfaced first.
Then confirm the orphan is removed rather than assuming it: run `--clean` on a scratch target
and check `pause-resume-substrate.js` is gone.

While in there, decide whether `pause-resume-substrate.js` is dead or whether its template was
lost — clean-mode deleting it is only the right outcome if the answer is "dead".

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 — a step that checks less than it
claims to and reports success.

## Resolution

Verified 2026-09-25 against `main` at `d2fe85a1`.

- **Fix:** `e5965006` — "fix(commit-guardian): four gates that reported success while seeing
  nothing (#793)", which changed `_MANAGED_ARTIFACT_DIRS["workflows"]` from
  `".claude/workflows"` to `"workflows"`. The constant had moved to
  `scripts/build_phases_clean.py` in #806 (`058c4bba`), and the fix was reapplied there. Its
  DECISION HISTORY records the reapply.
- **Convention normalised:** the dict now reads
  `{'agents': 'agents', 'skills': 'skills', 'hooks': 'hooks', 'workflows': 'workflows'}`, so
  every value is bare and relative to `.claude/`.
- **Guard tests:** `python -m pytest unit_tests/build_guards/test_ki_bp_010_clean_workflows.py -q`
  gave **3 passed**. The tests are `test_managed_artifact_dirs_workflows_entry_is_bare_relative`,
  `test_clean_removes_orphaned_workflow_file` and `test_clean_leaves_a_current_workflow_untouched`.
  `python -m pytest tests/test_build_clean.py -q` gave 8 passed.
- **Live probe:** a scratch target had `.claude/{agents,skills,hooks,workflows}` with
  `keep.js` and `pause-resume-substrate.js`. A first `clean_stale_artifacts` run seeded the
  provenance ledger. On the second run, the manifest held only `keep.js`, and the output was
  `Removing stale artifact: ...\.claude\workflows\pause-resume-substrate.js`. The run
  returned `removed: 1`. The orphan was gone and `keep.js` was kept.
- **The named orphan:** `.leafcutter/workflows/` and `templates/workflows-js/` now each
  hold 8 files, and the file names match. `pause-resume-substrate.js` is absent from both, so
  the live instance of KI-BP-005 described above no longer exists.
- **Caveat, not a residual of this KI:** since the KI-BP-009 / BP-1500g-1 work, clean-mode
  removes a file only if the provenance ledger recorded it in an earlier `--clean`. An item
  the ledger has never seen is kept, and clean-mode prints a WARNING for it. That is intended
  ADR-041 behaviour. The unreachable path this KI describes is fixed.

---
