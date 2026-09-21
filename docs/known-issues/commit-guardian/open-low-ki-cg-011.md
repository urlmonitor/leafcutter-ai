---
title: "KI-CG-011 — The roadmap mirror strips its own `description` frontmatter and backdates `created` to today"
description: "KI-CG-011 — The roadmap mirror strips its own `description` frontmatter and backdates `created` to today"
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

# KI-CG-011 — The roadmap mirror strips its own `description` frontmatter and backdates `created` to today

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/regenerate_roadmap_mirror.py:155-163` — the frontmatter block

**Symptom.** The generator emits a fixed six-line frontmatter: `title`, `type`, `status`,
`created`, `last_updated`, `components`. Two defects follow.

It never emits `description`, so any `description` present in `docs/roadmap.md` is **deleted
on every regeneration**. The comment above the block says the frontmatter is "required by
check_doc_frontmatter.py", which is exactly the convention the omission violates.

And `created` is written from the regeneration timestamp
(`date_only = generated_at[:10]`, line 154), so a file created on one date silently claims
it was created today, every time the mirror is rebuilt. `created` is supposed to be
immutable; only `last_updated` should move.

**Evidence.** Verified 2026-08-25 in the commit that reworded a phase_1 exit criterion. A
one-line change to `docs/roadmap.json` produced a 16-line diff in `docs/roadmap.md`: the
criterion itself, the two generated timestamps, quoting and indentation churn, and the
removal of `description: Overview of Project Roadmap.`. `created` moved `2026-08-17` →
`2026-08-25` on a file that plainly was not created that day.

Not currently merge-blocking — `check-description-field` is not among the six required CI
checks — so this erodes quietly.

**Fix direction.** Emit `description` in the generated frontmatter, and preserve the
existing `created` value when the mirror already exists rather than stamping the
regeneration date. Both are small, and both are worth doing together with a test that
regenerates twice and asserts the only field that moves is `last_updated`.

**Related — and note why `BP-1500a` cannot reach this.** This is `KI-BP-002`'s shape in
another file: a tracked generated artifact that drifts every time it is rebuilt, and
`BP-1500a` is the acceptance criterion written against that class. It cannot catch either
defect here, and the reason is structural rather than a matter of scope. `BP-1500a` promises
that *"a rebuild that would change [a tracked generated file] fails a check that names the
file"* — a comparison of committed content against regenerated content. But
`regenerate-roadmap-mirror` is a **transform-tier** hook: when `docs/roadmap.json` is staged
it rewrites `docs/roadmap.md` and then `git add`s it (`run()` →
`_git_add(mirror_path, root)`), so the mirror that lands in the commit *is* the generator's
own output, by construction. Committed and generated can never disagree about content, so a
drift check finds nothing to name. The only thing a later rebuild can move is the wall-clock
date stamp — which is noise, not either defect. `BP-1500a`'s guarantee therefore holds
**vacuously** over this file while both defects survive underneath it. Adding the roadmap
mirror to `BP-1500a`'s scope would not change that; these two want a test that asserts what
the generator *emits*, not one that compares it to what was committed.

---
