---
title: "KI-BO-014 — `goal_to_epic`'s `--ac` entry path never received the BO-2600a-5 hygiene fixes, so it writes absolute `implemented_by` and untranslated `depends_on`"
description: "KI-BO-014 — `goal_to_epic`'s `--ac` entry path never received the BO-2600a-5 hygiene fixes, so it writes absolute `implemented_by` and untranslated `depends_on`"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-014 — `goal_to_epic`'s `--ac` entry path never received the BO-2600a-5 hygiene fixes, so it writes absolute `implemented_by` and untranslated `depends_on`

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **RESOLVED 2026-09-14 — verified behaviourally on both entry paths, with one
  residual noted below.** Both symptoms were closed on `main` *before* this register's
  citations were retargeted: TKT-016 (`4711c9c79`) relativised the `implemented_by` pair in
  `run()`, TKT-017 (`88c6b58e8`) back-ported the `depends_on` translation to it. Each landed
  a *second inline copy*, so the root cause this entry names — two copies that can disagree —
  survived those fixes. `8b2b899ae` removed it: both entrypoints now call one
  `_epic_filename_map` / `_wire_epic_depends_on` / `_apply_epic_backrefs`
  (`scripts/ac_store/epic_phases.py`).
  *Evidence, behavioural not structural.* A three-leaf store with a within-epic chain
  A←B←C, driven through the real CLI. At `4711c9c79^` the `--ac` route wrote absolute
  `implemented_by` and `depends_on` entries naming files that do not exist, and
  `ticket_frontmatter_guard._check_depends_on` rejected 2 of 3 tickets. At `8b2b899ae` the
  `--ac` and `--ids` routes emit **byte-identical** ticket files (only Master_Plan's epic
  name and goal summary differ, both documented), repo-relative `implemented_by`, and the
  guard accepts both. `test_tkt_016_*`, `test_tkt_017_*` (which *does* parametrise `--ac`
  and `--ids`) and `test_bo_2600a_5`: 10/10 green.
  *What remains.* (a) `_apply_epic_backrefs` still takes `warn_unrelativisable` — True for
  `run()`, False for `build_epic_from_ids()`. Given an inbox outside the
  `<worktree>/tickets/00_inbox` convention both routes record a non-portable
  back-reference, but only `--ac` says so (3 warnings vs 0, reproduced). The wiring
  converged; the diagnostic did not. (b) The fix direction below was followed in spirit,
  not to the letter: `test_bo_2600a_5.py` still exercises only `build_epic_from_ids`, and
  its single `run()` test is a signature/`getsource` check — the grep-shaped kind. The
  cross-entrypoint behavioural coverage lives in `test_tkt_017_*` instead.
  *Two corrections to the text below, which is otherwise left as the historical record.*
  The `:9xx`/`:19xx`/`:21xx`/`:23xx` citations in the body are pre-split monolith lines and
  are stale; the owners today are `epic_phases.py`, `epic_tickets.py` and `epic_pipeline.py`.
  And symptom 2's "stays an AC id" was true when filed, but TKT-600a-1 later made the
  generator emit the loose ticket basename, so the bad value observed at repro time was
  `TICKET-…-KIT-100b.md` with no `NN_` prefix — same dangling reference, different string.
  **Do not delete this entry** — acceptance criteria and commit messages cite it by id.
  The filename still reads `open-` because residual (a) is a live behavioural difference;
  rename to `resolved-` only when that is closed or explicitly accepted.
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/ac_store/epic_pipeline.py` — `run()` (`:60`), against
  `build_epic_from_ids()` (`:175`); call sites at `:135` and `:237`
- **Reported by:** customer bug report 2026-08-25

**This entry deliberately covers two symptoms under one root cause.** They present as
separate bugs — bad paths in one place, bad dependency ids in another — but they are the
same defect seen twice, and filing them apart would invite two point-fixes that patch the
symptoms and leave the divergence itself untested. The finding worth recording is that
this generator has two entry paths that have drifted, not that two fields are wrong.

**Root cause.** `goal_to_epic.py` exposes two ways to build an epic. `build_epic_from_ids()`
serves the `--ids` path and received both hygiene fixes under BO-2600a-5. `run()` serves
the `--ac` path and received neither. Everything below follows from that one asymmetry.

**Symptom 1 — absolute paths in `implemented_by`.** `run()` passes the absolute
`epic_path` straight through to `_replace_implemented_by_entry()` (`:2344`), so
machine-absolute paths are written into the AC store. That is precisely the condition
`scripts/normalize_ac_paths.py` exists to clean up, re-introduced by the generator that
should never create it. `build_epic_from_ids()` handles the same step correctly: it
relativises **both** the old and the new path against the worktree root (`:2127-2135`)
before calling the same helper, so the values it writes start with `tickets/`.

**Symptom 2 — untranslated `depends_on`.** `_translate_ticket_depends_on()` (`:1918`)
converts AC ids in a ticket's `depends_on` into the co-located epic-folder filenames the
guard expects. Its **only** call site is inside `build_epic_from_ids()` (`:2113`);
`run()` never calls it. So on the `--ac` path a within-epic dependency stays an AC id and
does not match the `NN_`-prefixed filename `assemble_epic_folder()` actually wrote
(`{index:02d}_` + source name, `:948`), and every such ticket fails
`ticket_frontmatter_guard`. Cross-epic dependencies fare no better: they name something
outside the folder, which the guard rejects outright.

**Consequence, stated plainly.** `goal_to_epic` cannot currently emit an epic that passes
this repository's own pre-commit hooks for any AC that has internal dependencies — which
is most of them. The `--ids` path is fine; the `--ac` path is not.

**Evidence — the divergence was known when the fix was written.** The comment at the fix
site in `build_epic_from_ids()` names `run()`'s behaviour explicitly, as the thing being
corrected in the other function (`:2117-2120`):

```python
    # Hygiene fix (BO-2600a-5): the existing run() passes absolute epic_path as
    # new_path to _replace_implemented_by_entry, producing absolute paths in
    # implemented_by. Here both old and new paths are relativised against the
    # worktree root so implemented_by values start with "tickets/" (never "/…").
```

The defective behaviour is documented, in the source, by the author of the fix — and left
in place on the other path.

**AC-coverage note — another phantom-done instance.** `BO-2600a-5` is `work_status: done`
and claims repo-relative `implemented_by` and generation-time `depends_on` translation. It
separately claims that "the existing `--ac` mode is preserved unchanged", which is true and
is exactly the problem: both hygiene rules landed only on `build_epic_from_ids()`, so the
criterion's coverage is incomplete on the `run()` path while the store reports it satisfied.
Read together, the two clauses of that criterion are in tension — a hygiene rule stated
unconditionally cannot also be scoped to one entrypoint — and the resolution chosen at
implementation time was the narrower one, silently.

**Fix direction.** Hoist the hygiene step into a shared helper that both entrypoints call,
so there is one implementation rather than two that can disagree. Then parametrise the
existing BO-2600a-5 regression tests
(`unit_tests/build_orchestration/test_bo_2600a_5.py`) over **both** `run()` and
`build_epic_from_ids()`, so the paths cannot drift again. Parametrising is the load-bearing
half: a shared helper still permits a future caller to bypass it, and only a test that
exercises every entrypoint will notice.

**Related.** The sibling `goal_to_epic` defects found in the same review are filed under
`ac-driven-dev`: KI-ACD-010 (ASCII punctuation survives into the epic name), KI-ACD-011
(truncation ends on a dangling stopword), KI-ACD-012 (the generated Master_Plan fails
`ticket_frontmatter_guard`). KI-ACD-012 and this entry are the same shape from opposite
sides — a generator emitting artifacts its own repository's gates reject.

---
