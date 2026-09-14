---
title: "KI-TQ-013 — `git commit` in a temp fixture forks a background auto-gc, which races `rmtree` at teardown and fails the required CI suite at random"
description: "medium — never wrong about the code, but it blocks merges and trains people to re-run"
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

# KI-TQ-013 — `git commit` in a temp fixture forks a background auto-gc, which races `rmtree` at teardown and fails the required CI suite at random

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — never wrong about the code, but it blocks merges and trains people to re-run
- **Status:** open
- **Occurrences:** 2 on 2026-09-01, in a single afternoon, on two **different** pull requests —
  both of which changed **only Markdown**
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `unit_tests/portability/test_bp_900h6i.py:175-181` —
  `TestBp900h6iEntitlement::test_bp900h6i_step_refuses_an_unentitled_target_and_leaves_it_byte_identical`

**Symptom.** The required `Test suite (pytest)` gate fails with a teardown error, not an
assertion:

```text
FAILED unit_tests/portability/test_bp_900h6i.py::TestBp900h6iEntitlement::
  test_bp900h6i_step_refuses_an_unentitled_target_and_leaves_it_byte_identical
  - OSError: [Errno 39] Directory not empty: '/tmp/tmpbmd7r91e/developer_tree/.git'
```

The path differs each time (`tmpbmd7r91e`, `tmp7v5k_chs`). The test's own assertions never
fail; the body completes and the error is raised on the way out.

**Cause.** The fixture builds a real repository inside a `tempfile.TemporaryDirectory()`:

```python
with tempfile.TemporaryDirectory() as tmp:
    target_dir = Path(tmp) / "developer_tree"
    self._fresh_copy(target_dir)
    _git(["init"], target_dir)
    ...
    pre_commit = _git(["commit", "-m", "developer's pre-existing commit"], target_dir)
```

`git commit` runs `gc --auto` by default, which **forks a background process** and returns
immediately. That process is still creating and removing files under `.git/` after `_git(...)`
has returned and the `with` block has exited. `TemporaryDirectory.__exit__` calls
`shutil.rmtree`, which enumerates a directory, deletes its contents, then calls `rmdir` — and
`rmdir` fails with `ENOTEMPTY` if the background process wrote anything in between.

This is a race, so it is timing-dependent: it passes locally every time (verified — 4 passed),
and fails in CI at a rate somewhere around one run in three based on today's two hits.

**Why it deserves an entry rather than a re-run.** It is a **false red on a required gate**. Both
occurrences were on documentation-only pull requests, which cannot possibly have caused it, and
each cost a full ~13-minute suite re-run. The real damage is behavioural: a required check that
fails for reasons unrelated to the change teaches everyone that a red suite means "re-run it",
which is precisely the reflex that lets a genuine failure through. It also makes the pytest gate
useless as a merge signal without a human adjudicating every red.

**Suggested fix, in preference order.**

1. **Disable auto-gc in the fixture** — treat the cause. `git -c gc.auto=0 commit …`, or set
   `gc.auto=0` alongside the existing `user.email` / `user.name` config calls, or export
   `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0` for the subprocess environment. A
   test fixture has no use for garbage collection; it exists for a few seconds.
2. **Wait for the repository to go quiet before teardown** — sound but harder to get right, and
   it treats the symptom.
3. **`shutil.rmtree(..., ignore_errors=True)` or a retry** — makes the symptom go away and hides
   any *real* teardown failure with it. Only acceptable if 1 proves insufficient.

Sweep for siblings when fixing: any fixture that runs `git commit`, `git clone` or `git fetch`
inside a `TemporaryDirectory` or `tmp_path` has the same exposure. This test is unlikely to be
the only one; it is just the one that lost the race twice in one afternoon.

**Related.** `KI-TQ-008` (a repository-global tree-purity guard false-positives under concurrent
agents) is the same category from a different angle — a check reporting a failure that is about
the environment rather than the change. `KI-TQ-012` (a fixture leaking git identity into the real
repository) is the same *file family* mishandling git state, though a different mechanism.

**Pattern:** a fixture that treats a subprocess as finished when it returns, while the tool it
invoked has deliberately left work running behind it.

---
