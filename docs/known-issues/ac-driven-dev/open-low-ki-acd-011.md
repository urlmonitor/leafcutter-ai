---
title: "KI-ACD-011 — Epic-name truncation has no phrase awareness, so names end on a dangling preposition or article"
description: "KI-ACD-011 — Epic-name truncation has no phrase awareness, so names end on a dangling preposition or article"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-10-12'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-011 — Epic-name truncation has no phrase awareness, so names end on a dangling preposition or article

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-25 · **Last seen:** 2026-10-12
- **2026-08-31 recurrence:** `GE-123`'s title *"Trust that the last check between you and a
  leaked credential is still on"* yielded `EPIC-TrustThatTheLastCheckBetweenYouAndA` — ending
  on a bare article, exactly the shape described below. Two further facts from that run: the
  LLM summariser that would normally avoid truncation is silently unavailable when no `claude`
  binary is on `PATH` (it logs `claude --version probe failed` and falls through), so the
  truncation path is the *default* in any non-interactive environment, not the exception. And
  the script offers **no name override**, so the only remedy is to rename the folder and every
  `target_epic` stamp afterwards — 28 files for a 27-ticket epic. An `--epic-name` flag would
  make the defect survivable even unfixed.
- **Where:** `scripts/ac_store/epic_naming.py:251-299` — `_truncate_pascal_at()`
- **Reported by:** customer bug report 2026-08-25

**Symptom.** A long AC title yields an epic name that stops mid-phrase, on a word that
carries no meaning by itself.

**Root cause.** `_truncate_pascal_at()` locates word starts with
`re.finditer(r"[A-Z][a-z0-9]*")` and keeps the longest prefix that fits under the cap.
That is a PascalCase *word boundary* and nothing more. It has no notion of content words
versus function words, so a preposition or article that happens to fall inside the budget
is kept and becomes the last word of the name.

**Evidence.** AC `DTW-100r` produced `EPIC-WiringReconciliationActuallyLandsInThe`.

**AC-coverage note — a behaviour gap, not a regression.** No existing AC claims this.
`ACD-1200a-3-iii` requires only that truncation cut at a PascalCase word boundary, and
`…InThe` satisfies that requirement literally: it ends on a complete word, and it passes
the criterion's own trailing-character assertion because `e` is lowercase. File this as
new behaviour to specify rather than as a broken promise — the promise that exists was
kept.

**Note which path this is.** `_derive_epic_name()` (`:436`) reaches truncation only when
`_summarise_title_via_llm()` is unavailable or errors; when the summariser answers, the
concise name it returns is used instead. So this is the offline/fallback path — which
means it is the path CI takes, the path any key-less environment takes, and the path any
run takes when the API is having a bad minute. The degraded path is the common one, not
the rare one.

**Fix direction.** Drop trailing stopwords after truncating, or require the fallback to
cut at the last *content*-word boundary rather than the last word boundary. Either way,
keep the cap — the defect is where the cut lands, not that a cut happens.

**2026-10-12 recurrence, with a correction to the 2026-08-31 note.** `goal_to_epic.py --ids`
named a 48-ticket epic `EPIC-AnAcMissingFileTargetsOrATestContractIs`. The source title was
`ACD-1600c-1`'s "An AC missing file targets or a test contract is flagged not
implementation-ready", which is 68 characters as naive PascalCase. The name ends on the bare
verb `Is`. (That the name came from a prerequisite rather than the goal is a separate defect,
`KI-ACD-20261012-ids-mode-names-the-epic-after-its-first-prerequisite`.) The goal's own title
would have given `EveryPartOfARequirementIsWrittenBy`, which ends on a preposition. Both names
were reproduced with `_derive_epic_name()` on origin/main `a104d934`. Current line numbers are
`_truncate_pascal_at` `:251` and `_derive_epic_name` `:302`.

*The correction.* The summariser no longer probes a `claude` binary.
`_summarise_title_via_llm()` (`epic_naming.py:190`) imports the `anthropic` SDK and calls
`model="claude-3-5-haiku-latest"` (`:225`). The SDK is not a declared dependency
(`requirements-dev.txt`), so on a dev or CI machine the import fails and the function returns
`None` without logging anything. That was verified on Windows with Python 3.14. With the SDK
installed the call fails as well. Anthropic's model list records Claude Haiku 3.5 as retired on
2026-02-19, and the current Haiku-tier id is `claude-haiku-4-5`. The function catches that failure,
logs a WARNING and falls back. So the truncation path described above is not just the common
path: it is the only path that can produce a name. If the summariser is kept, it needs a live
model id and a declared dependency. Otherwise it is dead code that hides this entry's defect
behind an assumption that it rarely runs.

---
