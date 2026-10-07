---
title: "KI-BP-20261007-product-truth-gate-fails-closed-on-an-undeclared-dependency — check-product-truth-validate blocks every AC-touching commit because aiosqlite is imported but declared nowhere"
description: "high — a registered gate that cannot run and fails closed, so it blocks commits it has no opinion about. The dependency it needs is in no requirements file, so a correctly-provisioned environment still cannot satisfy it."
type: reference
category: reference
status: active
created: '2026-10-07'
last_updated: '2026-10-07'
components:
  - build_pipeline
  - ux_prototyping
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20261007-product-truth-gate-fails-closed-on-an-undeclared-dependency — check-product-truth-validate blocks every AC-touching commit because aiosqlite is imported but declared nowhere

> One known issue, filed on sight while landing GE-108d and GE-127f-4.
> Index: [build-pipeline.md](../build-pipeline.md).
> Filed under `build-pipeline` because the defect is a dependency-closure gap, the
> same family as KI-BP-003 and KI-BP-006. The code it fails in belongs to
> `ux_prototyping`, which has no register of its own — see "Ownership" below.

- **Severity:** high — the gate is `files:`-matched on `^docs/acceptance-criteria/.*\.yaml$` among others, so it fires on any AC-store commit, and it fails **closed**. Four consecutive commits on 2026-10-07 could only be landed with `SKIP=check-product-truth-validate`. It is not reporting a finding about the commit; it cannot run at all.
- **Status:** open — no AC. Two distinct causes, one fixed in passing and one not; see below.
- **Occurrences:** 4 commits across 2 worktrees on 2026-10-07, every one of them blocked. Structural — it will block any AC-touching commit in an environment matching this one.
- **First seen:** 2026-10-07 · **Last seen:** 2026-10-07
- **Where:** gate `check-product-truth-validate`, entry `python .leafcutter/scripts/commit_guardian/run_hook.py docs/product-truth/scripts/validate_product_truth.py --quiet`; the failing import is reached via `kernel/persistence/checkpointer.py`

**Symptom.** The gate emits a wall of `FAIL:` lines naming contracts it could not
resolve, then exits 1:

```text
FAIL: contracts leafcutter/criteria-library/decision_record: No module named 'aiosqlite'
FAIL: contracts leafcutter/criteria-library#mine: unknown contract: decision_record
FAIL: contracts leafcutter/criteria-library#publish: unknown contract: decision_record
...
244 error(s), 146 warning(s)
```

The cascade is misleading: the `unknown contract:` lines are not independent findings,
they are downstream of the single import failure that prevented `decision_record` from
being defined. One missing module presents as hundreds of errors.

**Two causes, and only the first is fixed.**

1. **`pydantic` — stale environment, fixed in passing.** The first 244 errors were
   `No module named 'pydantic'`. `pydantic==2.13.5` **is** declared, at
   `requirements-dev.txt:58`; the main-tree `.venv` simply predated the pin. Installing
   the pinned version cleared all 244. This half is an environment-provisioning gap, not
   a code defect, and is recorded here only so the next reader does not re-diagnose it.

2. **`aiosqlite` — undeclared, NOT fixed.** With pydantic present, 5 errors remain, all
   from `aiosqlite`. Unlike pydantic, `aiosqlite` appears in **no** requirements file —
   `grep` over `requirements-dev.txt` returns nothing, and this repository has no
   `pyproject.toml`. So a developer who provisions their environment exactly as
   documented still cannot run this gate. That is the real defect.

   `kernel/persistence/checkpointer.py`, which imports it, landed on `main` on
   2026-09-30 (`1669d6fd`, "feat(kernel): add Phase 2 durable persistence and Langfuse
   tracer"). The dependency came with the feature; the declaration did not.

**Why this is the KI-BP-003 family.** This repository's own convention — CLAUDE.md,
"New Hook / Gate Dependencies Must Be in the Build Deploy-Manifest" — states that when
a gate imports a module, that module must be reachable from the deployed layout, and
that the failure mode is a `ModuleNotFoundError` at hook runtime that blocks every
commit once the gate is required. That convention is written about the deploy manifest;
this is the same defect one layer out, in the dependency manifest. The check that
catches the deployed-closure version of this does not catch the
not-declared-anywhere version.

**Detection.** The load-bearing part, because the gate's output actively disguises it:
grep the run for `No module named` before reading any `FAIL:` line. A run reporting
hundreds of contract errors and a single missing module is reporting **one** problem.
Confirm the gate is the cause and not your diff by checking whether any failing line
names a file you touched — on all four 2026-10-07 commits, none did.

**Workaround.** `SKIP=check-product-truth-validate` on the commit. This is a real
suppression of a real gate and should not become habitual; it is only defensible while
the gate is incapable of running at all.

**Fix direction.** Declare `aiosqlite` in `requirements-dev.txt` alongside the other
kernel-persistence dependencies, pinned, in the same style as `pydantic==2.13.5`. Then
re-run the gate and confirm it reaches a real verdict rather than an import failure —
a clean exit is not evidence here unless the run also reports a non-zero count of
examined artifacts.

Worth considering separately, and larger than this entry: a gate that cannot import its
own dependencies currently reports that as hundreds of content findings. Reporting
"could not run" distinctly from "ran and found problems" is the `GE-120a` /
`GE-126b` shape, and this gate does neither.

**Ownership.** `docs/product-truth/scripts/validate_product_truth.py` is `primary_code`
for component `ux_prototyping` in `docs/components.json`. There is no
`docs/known-issues/ux-prototyping/` register, so this is filed in `build-pipeline` as
the nearest register that owns dependency closure, with `ux_prototyping` carried in
`components` so it is findable from either side. If a UXP register is created later,
move this entry rather than duplicating it.

**Pattern:** a dependency that arrives with a feature but not with its declaration, so
the gate that needs it fails closed in every environment provisioned from the
documented requirements — and reports the single cause as hundreds of unrelated-looking
findings.

---
