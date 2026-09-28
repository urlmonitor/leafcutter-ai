---
title: "KI-BO-006 — `fast-lane-build.js` is deployed but orphaned"
description: "KI-BO-006 — `fast-lane-build.js` is deployed but orphaned"
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

# KI-BO-006 — `fast-lane-build.js` is deployed but orphaned

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low
- **Status:** **RESOLVED 2026-09-01** — the orphan is deleted; decision recorded below · AC **BO-2400c-1-v**
- **Occurrences:** 1
- **First seen:** 2026-08-14 · **Last seen:** 2026-08-18 · **Closed:** 2026-09-01
- **Where:** `templates/workflows-js/fast-lane-build.js` (deleted)

**Symptom.** Nothing invokes it. The only `Workflow("fast-lane...")` call anywhere is
`fast-lane-ship`, and `/fast-lane-build` routes there. The orphan is still built,
deployed, and maintained — it was updated alongside `fast-lane-ship` in the BO-2400a-3
amendment purely to keep it consistent.

**Evidence.** Grep for `fast-lane-build` call sites returns only the command template,
which dispatches `fast-lane-ship`.

**Fix direction.** Delete it. The blocker that previously made deletion unsafe is gone,
and the remaining work is a test migration — see below for the real size.

**Status update, 2026-08-18.** Until this date the orphan held the only production
reference to `assemble_context_bundle`, so deleting it would have silently retired the
prompt-caching layer. That is no longer true: BO-2400c-1-iii wired the layer into
`fast-lane-ship.js`, which now assembles a bundle through the module's real
`assemble-bundle` CLI once per run. The orphan holds nothing the running lane does not.

It also holds something actively wrong: its call still names the subcommand
`assemble_context_bundle`, which is not what the CLI added by BO-2400c-1-ii is called
(`assemble-bundle`). That invocation was a silent no-op before the CLI existed and is a
plain error now. It is unreachable because nothing invokes the file — which is the
point. This absorbs the former KI-BO-005, whose substance (the module had no
command-line entry point at all) is fixed and closed.

**Deleting this is a test MIGRATION, not a deletion — size it accordingly.**
`unit_tests/workflows/test_bo2400a_runner_wiring.py` (513 lines) and
`test_bo2400a_runner_structure.py` (574 lines) point at the orphan and nothing else,
and between them carry the only `# covers:` proof for **eight** criteria: BO-2400a-1,
-2, -3, -4, -5, BO-2400b-3, BO-2400c-1 and BO-2400d-1. Several are done. Deleting the
file and its tests together strips the done-proof from all eight and fails
**Proof-of-done**, a required merge check. Three architecture diagrams and
`docs/build-dataflow.json` describe the file as well.

The full plan, including the parts that must NOT be rewritten (changelogs, already-done
ACs citing the orphan as history, and the `CLAUDE.md` phantom-done lesson that names
it), is recorded in the notes of **BO-2400c-1-v**. One specific prohibition carries
over: `test_bo2400a_runner_wiring.py:401` asserts the literal string
`assemble_context_bundle` appears in the orphan. That assertion must be **deleted**, not
re-pointed at the live file — BO-2400c-1's proof now comes from the behavioural suite
in `test_bo2400c_prompt_cache_wiring.py`, and re-pointing a name-presence grep would
preserve, at a new address, exactly the test that let a dead reference read as alive.

**RESOLUTION, 2026-09-01 — the decision this entry asked for, and how it was taken.**
This entry explicitly asked for a *capability* decision: wire the prompt-caching layer
into the running lane and delete the orphan, or delete both and say plainly that prompt
caching is gone. **The first was taken.** `BO-2400c-1-iii` wired the layer into
`fast-lane-ship.js`, and the orphan has now been deleted along with
`test_bo2400a_runner_wiring.py`. No capability was retired.

**The size estimate above was wrong in both directions, and the correction is the
useful part.** It was written by reading the two test files. The real figure came from
*deleting the orphan and running the full covering-test set*, which is a different
activity and gave a different answer:

- **Overstated.** The two files do not hold the sole proof for eight criteria. Per-id
  audit: only `BO-2400a-1` and `BO-2400a-5` had sole proof there, both in
  `test_bo2400a_runner_structure.py`. `test_bo2400a_runner_wiring.py` held **no**
  criterion's sole proof and was simply deleted, as this entry's own prohibition
  anticipated.
- **Understated.** A third file was missed entirely — `test_bo2500d_gate_retirement.py`,
  whose `_FAST_LANE_PATH` pointed at the orphan and which carried sole proof for
  `BO-2500d-2` (`done`).

So the true blast radius was **three** ACs, not eight, and it included one this entry
never named.

**A path swap would not have worked, and that is why the migration was its own change.**
`fast-lane-ship.js` has ~20 non-comment `agent()` call sites against the orphan's
exactly 2, so the "exactly two agent dispatches" assertion failed outright; and the
gate-ordering assertion compared raw string positions, where a JSDoc mention of a coder
type precedes the real gate call in the live lane (measured: `python-coder` at 832,
`verify_red_baseline` at 952, while real control flow is 336 before 28512). The
assertions were rebuilt to count the unique dispatch labels and to compare
comment-stripped positions. `select_batch` does not exist in the live lane at all — it
uses `fast_lane.py select_connected`.

**Prohibitions honoured.** Nothing was kept alive by relaxing an assertion, marking it
skipped or xfailed, or re-aiming it at a file that merely contains the same string. The
`assemble_context_bundle` name-presence grep at `test_bo2400a_runner_wiring.py:401` was
**deleted with its file**, not re-pointed. The `BO-2500d-1`/`-1-i`/`-3` tests were
deliberately left pointing at the orphan's former path rather than re-aimed: they are
`in_progress`, and `BO-2500d-1` asserts the fast lane has no LLM review agent, which the
live lane deliberately contradicts by dispatching `pr-reviewer` at Phase 4.5 (PR #485).

**Absorbed and closed with it:** the former `KI-BO-005` (the module had no command-line
entry point), already noted above as fixed.

---
