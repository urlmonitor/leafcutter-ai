---
title: "KI-TQ-20260914-test-fixtures-hand-enumerate-their-production-dependencies — the deploy-manifest failure mode one layer down, where the error message names something other than its cause"
description: "medium — it cannot reach production, because the only thing that breaks is a test fixture. What it costs is diagnosis time and false attribution: the failure surfaces on descriptors belonging to *other* ACs, phrased as something unrelated t"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-20260914-test-fixtures-hand-enumerate-their-production-dependencies — the deploy-manifest failure mode one layer down, where the error message names something other than its cause

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — it cannot reach production, because the only thing that breaks is a test fixture. What it costs is diagnosis time and false attribution: the failure surfaces on descriptors belonging to *other* ACs, phrased as something unrelated to the real fault.
- **Status:** open — no AC. The two known instances are annotated in place; nothing checks the general case.
- **Occurrences:** 1 (2026-09-14), hitting 6 descriptors across 2 fixtures simultaneously
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `unit_tests/commit_guardian/_ge_127a_1_ordinary_commit_fixture.py` (`PRODUCTION_MODULES`) and `unit_tests/commit_guardian/_ge_127c_1_scope_fixture.py` (`CHECK_FILE_SIZE_SIBLINGS`)

**Symptom.** `GE-127e-1` added `_file_description.py` and a new import of it to `check_file_size.py`. After rebasing that branch onto a main that had just taken `GE-127a-1` (#777) and `GE-127c-1` (#781), **six descriptors went red** — none of them `GE-127e-1`'s own, all of them belonging to the two ACs whose fixtures had just merged.

The message named the wrong thing:

```text
AssertionError: 0 != 1 : baseline commit failed: Check File Size...Failed
- hook id: check-file-size
- exit code: 1
```

The actual cause appeared only inside the captured traceback the assertion happened to embed:

```text
ModuleNotFoundError: No module named '_file_description'
```

**Mechanism.** Both fixtures build a real temporary git repository and copy `check_file_size.py` into it alongside a **hand-enumerated list** of the modules it imports. The source tree resolves the new import fine — only the copied temp repo is missing it. Nothing anywhere compares either list against the real import graph, so adding an import to `check_file_size.py` silently invalidates both.

This is structurally the same defect as the build's deploy map (CLAUDE.md, "New Hook / Gate Dependencies Must Be in the Build Deploy-Manifest"), one layer down — and worse in one respect: the deploy-map version at least fails as a recognisable `ModuleNotFoundError` at hook runtime, whereas here it is wrapped in a commit failure attributed to the gate.

**Why no amount of care on the new AC would have caught it.** `GE-127e-1`'s own seven descriptors were green throughout, including its deployed and reachability arms. The fixtures that break belong to *other* records. It was caught only by rebasing onto main and running the whole `unit_tests/commit_guardian/` suite — 1459 tests — which is not something a focused AC build does by default.

**Fix direction.** Derive the copied set rather than enumerate it: walk `check_file_size.py`'s imports and copy what it actually needs, so the fixture cannot drift from the module. Failing that, a single shared helper both fixtures call, with one list to maintain instead of two. The weakest acceptable option — done today as a stopgap — is a comment on each list saying nothing checks it; that records the hazard without removing it.

Note this generalises beyond these two: any fixture that copies production modules into a temp tree by name has the same exposure, and `commit_guardian` has several.

**Related.**
- CLAUDE.md "New Hook / Gate Dependencies Must Be in the Build Deploy-Manifest" — the same defect at the build layer, already documented.
- `GE-127f-1` / `-2` / `-2-i` `it_requirements` — carry this hazard forward explicitly, since that tree's implementation is likely to add another import.

**Pattern:** a hand-maintained mirror of a dependency graph, with no check that the mirror still matches — surfacing as a failure attributed to whatever was running when it broke.
