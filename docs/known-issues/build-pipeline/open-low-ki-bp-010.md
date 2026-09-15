---
title: "KI-BP-010 — Clean-mode's `workflows` entry has a doubled path segment, so it has never run and a real orphan survives every `--clean`"
description: "KI-BP-010 — Clean-mode's `workflows` entry has a doubled path segment, so it has never run and a real orphan survives every `--clean`"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-010 — Clean-mode's `workflows` entry has a doubled path segment, so it has never run and a real orphan survives every `--clean`

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_phases.py:2820-2825` (`_MANAGED_ARTIFACT_DIRS`), `:2859-2864`
  (the join in `clean_stale_artifacts`)

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

---
