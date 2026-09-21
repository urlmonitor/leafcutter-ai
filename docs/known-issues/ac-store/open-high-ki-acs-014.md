---
title: "KI-ACS-014 — `reference_file_path` can name a symlinked build output that git does not track, and nothing checks it resolves to a source file"
description: "KI-ACS-014 — `reference_file_path` can name a symlinked build output that git does not track, and nothing checks it resolves to a source file"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-014 — `reference_file_path` can name a symlinked build output that git does not track, and nothing checks it resolves to a source file

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `it_requirements.reference_file_path` in any AC record;
  `templates/scripts/commit_guardian/_ac_schema_validators.py` (no resolution check);
  `scripts/ac_store/generate_ticket_from_ac.py` (copies the value into `files_touched`)

**Symptom.** An AC's `reference_file_path` — the field that tells the implementer which file
the work lives in, and which the generator copies into the ticket's `files_touched` — can name a
path that exists on disk but is **not tracked by git**. Work done there is not wiped by the next
build. It is never committed at all.

**Evidence.** `BP-1100g-4` names `scripts/commit_guardian/commit_guardian.json`:

```
scripts/commit_guardian -> ../.leafcutter/scripts/commit_guardian
git ls-files scripts/commit_guardian                                 ->  (no output)
git ls-files templates/scripts/commit_guardian/commit_guardian.json  ->  tracked
```

`scripts/commit_guardian` is a symlink into the build-output tree created by `install_shims`.
The source is `templates/scripts/commit_guardian/`. An implementer following the AC literally
would register the new hook in the deployed manifest, watch it work locally — the deployed copy
is what the hooks actually load — and ship nothing.

**Why this is worse than the ordinary deployed-copy trap.** The familiar failure (KI-BP-004, and
the `.claude/agents` case corrected on the `BP-1100g-1` ticket) is *edit the output, lose it on
the next build*. There the change is at least visible in `git status` until then, so a routine
`git add -A` or a review catches it. Here the path is untracked, so:

- `git status` shows nothing,
- the commit contains nothing,
- the PR diff contains nothing,
- and every local check passes, because locally the change is real.

The failure is silent at every layer that would normally notice, and it presents as "the work is
done and working" right up until someone else pulls.

**It is not a flaw in this AC's authoring.** `BP-1100g-4`'s own constraint explains that the
primary implementation is a new module and that `reference_file_path` *must resolve to an
existing file* — the field's contract forces the author toward whatever path exists today, and
the deployed symlink resolves while the not-yet-created source module does not. The field's
validation rule ("must exist") and its purpose ("the file you will edit") are in tension, and the
rule that is mechanically checked is the one that does not matter.

**Scope.** Not yet measured across the store. The exposure is any AC whose `reference_file_path`
points under `scripts/commit_guardian/`, `scripts/doc_compliance/`, `scripts/feedback/`,
`.claude/`, or `.leafcutter/` — the symlinked shim roots listed in `build.py`'s `install_shims`
output. Worth a sweep; deliberately not asserted here without one.

**Fix direction.** Add a resolution check to `check-ac-schema`: `reference_file_path` must be a
path `git ls-files` reports as tracked. That is one call, it is exact, and it catches every
member of this family rather than the symlink roots someone remembers to enumerate. A path that
exists but is untracked should fail with the tracked source suggested where one can be inferred
(`scripts/X/...` → `templates/scripts/X/...`).

Then resolve the field's tension, which the check will expose rather than fix: either allow
`reference_file_path` to name a file the work will *create* (a `reference_file_status: planned`
sibling), or rename the field to what it currently means — the nearest existing anchor — and give
the generator a separate, honest surface field. As long as one field means both "where to look"
and "what to edit", tickets will keep being generated with the wrong one.

**Related.** `KI-ACS-002` (the generator copies this value into `files_touched` and the readiness
report passes it on a count, so nothing downstream catches it either). `KI-ACS-009` (a rule that
lives in `templates/` while agents grep the deployed copy — the same source-versus-output
confusion, one layer up).

**Pattern:** a required field validated for existence but not for the property that makes it
useful, where the wrong answer is silent at every layer that would normally catch it.

---
