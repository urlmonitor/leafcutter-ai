---
title: "KI-BP-002 — Generated agent cards are tracked but never regenerated, so every build dirties six of them"
description: "KI-BP-002 — Generated agent cards are tracked but never regenerated, so every build dirties six of them"
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

# KI-BP-002 — Generated agent cards are tracked but never regenerated, so every build dirties six of them

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

> **DUPLICATE of KI-BP-015 — verified 2026-08-25.** Both describe `docs/agents/cards/*.card.md`
> as tracked build outputs with no freshness gate that drift and get rewritten on every build;
> filed a week apart at different severities. Keep one and increment `Occurrences` on it.
>
> **Do not fix the cards themselves.** The mechanism wanted is a repo-wide generated-artifact
> ratchet, and BP-1500a already specifies it — including the trap that makes the naive version
> useless: the check must be computed over *every* tracked generated artifact, not the subset
> in the change under review, because the drifted artifact is by definition never in that
> subset.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 4
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-25
- **Where:** `scripts/build.py` — the agent-card generation phase; output at `docs/agents/cards/*.md`

**Earlier occurrence, 2026-08-19 — recovered from an unmerged branch.** PR #495's parallel
known-issues register recorded this independently as `KI-BO-2` while driving
`EPIC-GE122UniquenessPassAndRepair`. That register was discarded during reconciliation; the
occurrence is folded in here rather than duplicated, per this file's own rule. `build.py --force`
regenerated **eight** cards with AC-store content absent from the committed versions — entries
such as `ACD-1600g-*` and `ACD-1800a-*`, belonging to components unrelated to the work in hand.
The committed cards were simply older than the store.

It adds two things to the three occurrences below. First, it is the **earliest** recorded
instance and it is already purely AC-store drift, which dates the drift source to at least a
week before the 2026-08-25 occurrence that first isolated it. Second, it names the operational
cost precisely: eight modified files in `git status` during unrelated work, each of which must be
excluded from every commit by hand — and which makes a genuinely-related card change easy to miss
in the noise. The workaround used was `git restore docs/agents/cards/` for the unrelated ones
before staging, keeping any card that reflects a change actually made in the commit. That is the
same workaround `build-pipeline.md:162` prescribes, arrived at independently.

**Third occurrence, 2026-08-25.** Reproduced again on a clean worktree cut from `origin/main`,
this time rewriting **four** cards with 68 insertions and zero deletions:
`architecture-diagram-author`, `documentation-expert`, `frontend-coder`, `python-coder`. The
build printed nothing about it — the drift was noticed only because `git status` was checked
immediately afterwards for an unrelated reason.

This occurrence is **purely the AC-store drift source**, with no template-description component:
every added line is a new AC-index entry, e.g. `frontend-coder` gaining
`GE-124b-3: The pin is stripped from production builds and retained in dev, test and the Atlas`
after `#535` landed that record. So the sources are independent and either alone is enough —
a PR that touches no agent template at all still leaves the cards stale.

Not committed with the run that found it: those four files belong with whichever PR lands the
ACs that caused the drift, and picking them up in an unrelated change invites a conflict. Which
is itself the point — the cost of this defect is paid by whoever happens to run a build next,
and it is always someone with no reason to care.

**Same finding as `KI-BP-015`, recorded twice on the same day by two sessions.** That entry
reports the same four cards and 63 lines against this occurrence's 68, from an independent
build. Per this file's own rule — *"Hitting an existing issue. Increment `Occurrences` and
update `Last seen`. Do not add a duplicate entry"* — the occurrence increment is the correct
form and `KI-BP-015` should be folded into this entry rather than kept alongside it. Left for
whoever consolidates: deleting another session's entry mid-flight is how the `KI-BO-019`/`020`
collision got worse. Worth noting that two independent observers filing the same defect within
hours is itself evidence of how often this fires.

**Symptom.** The cards are generated from two sources that change constantly — each
agent's template `description`, and the AC store — but they are **tracked files**, and the
PRs that change those sources do not regenerate them. So the committed cards drift out of
date silently, and the next `build.py` run rewrites them, leaving a tracked-file diff on an
otherwise clean tree that has nothing to do with the work in hand.

**Evidence.** Reproduced twice on 2026-08-18 in a clean worktree at `origin/main`. The
second run (after `#474` merged) rewrote **six** cards, 99 insertions / 36 deletions:
`ac-fulfillment-gate`, `architecture-diagram-author`, `documentation-expert`, `llm-expert`,
`python-coder`, `test-writer`.

The two drift sources are both visible in that diff:

- **Template description drift.** `#474` changed `ac-fulfillment-gate`'s agent template
  description and did not regenerate its own card. The committed card still described the
  pre-fix behaviour (`status: ok if all ACs pass`) after the fix had shipped the stricter
  contract (`ok only when at least one AC was resolved`).
- **AC-store drift.** `llm-expert`'s card was missing the five `BO-2400g-*` entries merged
  in `#452`, still listed `BO-530-3-i` (since removed), and carried a superseded title for
  `BO-2400a-3-i`.

**Fix direction.** Pick one and hold it: either stop tracking the cards and generate them
on demand, or make card regeneration a required part of any PR that touches an agent
template or the AC store — a CI drift check that fails when a rebuild would change a card,
in the same spirit as the existing `check-build-drift` hook (which does not catch this,
because it only inspects files already staged).

**Trap.** Same shape as KI-BP-001 — a routine build silently modifies tracked files you
did not edit, so the diff is easy to sweep into an unrelated commit with `git add -A`. It
is also easy to mistake for another author's work. Restore with
`git restore docs/agents/cards/` after any build you did not intend to include them in.

---
