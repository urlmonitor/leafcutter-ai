---
title: "KI-CG-20260826-package-surface-refuses-merge-commits — merging `origin/main` into a branch is refused as if the branch had added every registry entry landed upstream since it forked"
description: "KI-CG-20260826-package-surface-refuses-merge-commits — merging `origin/main` into a branch is refused as if the branch had added every registry entry landed upstream since it forked"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260826-package-surface-refuses-merge-commits — merging `origin/main` into a branch is refused as if the branch had added every registry entry landed upstream since it forked

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **First entry in this file using the date-and-slug id form.** See `build-pipeline.md` →
> "Why not the next free number", `KI-BO-024`, and
> `knowledge-management.md` → `KI-KM-20260826-id-convention-diverged-across-registers`.
> The sequential `KI-CG-NNN` entries above keep their ids.

- **Severity:** high
- **Status:** **being fixed 2026-09-01** — AC: `ACS-100i-8-ii` ("An entry a merge carries from
  a parent is not an entry the merge registers"), an L3 technical constraint on ACS-100i-8.
  The fix scopes the added-entry computation to what the commit introduces relative to its own
  parents: an entry counts as added only when absent from EVERY parent. Single-parent
  behaviour is unchanged. The negative control is preserved — an entry present in no parent
  and cited by no declaring AC is still refused, including mid-merge alongside a legitimately
  carried one, so this is not a merge exemption.
  **Not addressed by that fix:** the `--diff-filter=AM` rename blindness in
  `KI-CG-20260826-1612` below, which is independent and still open.
- **Occurrences:** 4 observed — 2026-08-26 PRs #601 and #577; 2026-09-01 PR #661 (bypassed
  with an authorised `SKIP`, and misfiled at the time as
  `KI-BP-20260901-0812` in `build-pipeline.md` before this entry was found — see the
  correction there); reproducible on demand
- **First seen:** 2026-08-26 · **Last seen:** 2026-09-01
- **Where:** `templates/scripts/commit_guardian/check_package_surface_declaration.py`
  → `_new_entries()` (~:139-158)

**Symptom.** A merge commit that changes no registry at all is refused:

```text
[check-package-surface-declaration] REFUSED: this change adds a package-registry entry,
but none of the acceptance criteria it cites declares a package surface.
  templates/scripts/commit_guardian/commit_guardian.json: new entry
  '__drift_gate_exemption_registry_doc', 'check-hook-trigger-reachability',
  'check-presence-only-assertions', 'presence_only_assertion_guard', …
```

None of those entries came from the branch. `git diff origin/main -- <that file>` was **empty**
on both occasions — the registry in the index was byte-identical to `origin/main`.

**Mechanism — confirmed by reading the code, not inferred from the message.** `_new_entries()`
computes, per watched registry:

```python
staged = registry_entry_keys(parse_registry_document(_blob(repo, f":{rel_path}")), containers)
head   = registry_entry_keys(parse_registry_document(_blob(repo, f"HEAD:{rel_path}")), containers)
return sorted(staged - head)
```

During a merge, `HEAD` is still the **pre-merge tip of your own branch** — the merge commit does
not exist yet — while the index holds the **merged** content. So `staged - head` is not "what
this change adds"; it is "everything upstream added since this branch forked." The second parent
is never consulted: `MERGE_HEAD` appears **zero** times in the file.

**Reproduction (deterministic).** Using the hook's own `WATCHED_REGISTRIES`,
`parse_registry_document` and `registry_entry_keys`, with `OLD` = the branch base and
`NEW` = `origin/main`:

```text
config/agent_registry.json                          60 -> 60 keys   0 reported new
config/skill_registry.json                          42 -> 42 keys   0 reported new
config/paths.json                                   12 -> 12 keys   0 reported new
templates/scripts/commit_guardian/commit_guardian.json
                                                    85 -> 94 keys   9 reported new
```

Those nine include the exact seven the hook named when it refused the two real merges. The set
is not fixed — **it grows with every registry entry landed upstream**, so the longer a branch
lives the more entries it is accused of adding.

**Why it is easy to dismiss and therefore high, not medium.** Three of the four watched
registries reported zero, so the refusal only fires when upstream happened to touch
`commit_guardian.json`. That makes it intermittent and reads like a real finding on first
encounter. And the remedy the hook prints — *"Set `package_surface: true` on the criterion that
registers this surface"* — is actively wrong here: the branch registers no surface, so following
the advice means annotating **someone else's** already-merged AC with a claim about work you did
not do. The only paths through are `SKIP=check-package-surface-declaration` or `--no-verify`,
both of which disable the gate wholesale. Both merge commits in PRs #601 and #577 were landed
with `SKIP=`; the hook was verified beforehand to be firing on content identical to
`origin/main`, but that verification is a manual step nothing enforces, and the habit it trains
is the one this register exists to discourage.

**Fix direction.**

1. **Consult both parents when a merge is in progress.** When `.git/MERGE_HEAD` exists, a key is
   new only if it is absent from **both** `HEAD:<path>` and `MERGE_HEAD:<path>`. That is the
   whole fix, and it preserves the real obligation: an entry genuinely introduced by the branch
   is absent from both parents and is still caught. Octopus merges have several `MERGE_HEAD`
   lines — read them all rather than the first.
2. **Prefer the merge base over the first parent** if a general form is wanted:
   `staged - keys(merge_base)` restricted to keys not present in any parent. Equivalent for the
   two-parent case, and it also covers rebase and cherry-pick states.
3. **Do not fix this by exempting merge commits entirely.** A merge is a legitimate place to
   introduce a registry entry — conflict resolution can add one — and skipping the check there
   would open exactly the hole the hook exists to close.

**Related.** `KI-CG-20260826-1612` — **same hook, different and independent defect**, filed the
same day by another session. That entry reports `check_package_surface_declaration` among the
hooks whose `--diff-filter=AM` makes a staged *rename* invisible; this entry reports its
baseline being wrong on a merge. They do not overlap and neither fix addresses the other:
`--diff-filter` decides *which paths* the hook sees, `HEAD` vs `MERGE_HEAD` decides *what it
compares them against*. Both are worth fixing in one pass, since both live in the same twenty
lines of git plumbing. `KI-CG-012`, `KI-CG-019` (sibling checks that reach a verdict from an
incomplete read of git state). `KI-BP-20260826-1331` (the same class of wrong-baseline
comparison, there against the deployed tree rather than against `HEAD`).

**Pattern:** a check that treats `HEAD` as "the state before this change" — true for an ordinary
commit, false for every merge.

---
