---
title: "KI-TQ-20260927-full-pytest-run-has-114-collection-errors — a bare pytest run imports scripts/ac_store as the top-level package ac_store, so all 112 test modules in unit_tests/ac_store fail to collect; two more modules import POSIX-only stdlib at module level"
description: "medium — scripts/ac_store/test_enforcement.py matches pytest's test_*.py pattern and, with no scripts/__init__.py, is imported under the default prepend mode as ac_store.test_enforcement; unit_tests/ac_store/test_X then resolves against the wrong package. Reproduced 2026-09-27 by collection order alone. CI is unaffected because it passes tests/ unit_tests/; bare pytest and finalize-feature's baseline are affected."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260927-finalize-triage-baseline-predates-merged-main.md
---

# KI-TQ-20260927-full-pytest-run-has-114-collection-errors — a bare pytest run imports scripts/ac_store as the top-level package ac_store, so all 112 test modules in unit_tests/ac_store fail to collect; two more modules import POSIX-only stdlib at module level

- **Severity:** medium. 756 tests go uncollected in any bare `pytest` run. The errors are printed, but `--continue-on-collection-errors` (`pytest.ini`) lets the run finish, and finalize-feature's baseline parser does not read `ERROR` lines.
- **Status:** open — no AC. The package collision is reproduced and traced. The two POSIX imports are confirmed in code.
- **Occurrences:** 1 (a local full run on Windows, 2026-09-25, reported 112 errors; reproduced with `--collect-only` on 2026-09-27: `5912 tests collected, 114 errors`)
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-27
- **Where:** `pytest.ini` (no `testpaths`, default import mode); `scripts/ac_store/test_enforcement.py` (a library module whose name matches `test_*.py`); `unit_tests/ac_store/__init__.py`; `scripts/port_registry.py:12`; `unit_tests/build_orchestration/test_bo2400e_3_durable_write.py:58`.

## Symptom

```text
$ python -m pytest --collect-only -q
5912 tests collected, 114 errors
   112 ERROR unit_tests/ac_store/...        ModuleNotFoundError: No module named 'ac_store.test_<name>'
     1 ERROR tests/test_port_registry.py    ModuleNotFoundError: No module named 'fcntl'
     1 ERROR unit_tests/build_orchestration/test_bo2400e_3_durable_write.py
                                            ModuleNotFoundError: No module named 'resource'
```

## Mechanism

1. **Package-name collision, decided by collection order.** `pytest.ini` sets no `testpaths`, so
   a bare `pytest` walks the whole tree, `scripts/` included. `scripts/ac_store/test_enforcement.py`
   is production code (the covers-tag enforcement library the `-p scripts.ac_store.pytest_ac_enforcement`
   plugin loads), but its name matches `test_*.py`. There is no `scripts/__init__.py`, so under the default
   `prepend` import mode pytest takes `scripts/` as the base directory and imports the file as
   `ac_store.test_enforcement`. That puts `sys.modules['ac_store']` = `scripts/ac_store/__init__.py`.
   `unit_tests/ac_store/` is also a package named `ac_store`, because it has an `__init__.py` and
   `unit_tests/` has none. Each of its modules is imported as `ac_store.test_<name>`, which now
   resolves against `scripts/ac_store/` and fails.
   Reproduced by order alone:
   ```text
   pytest --collect-only scripts/ac_store/test_enforcement.py unit_tests/ac_store  -> 112 errors
   pytest --collect-only unit_tests/ac_store                                       -> 756 collected
   ```
   A collection-time probe confirmed `sys.modules['ac_store'].__file__` is `scripts\ac_store\__init__.py`
   before any `unit_tests/ac_store` module is collected.
2. **POSIX-only imports at module level.** `scripts/port_registry.py:12` runs `import fcntl`
   unconditionally, although its own lock helper (`:251-252`) documents a `filelock` fallback
   for Windows. The module cannot be imported on Windows at all, so the documented fallback is
   unreachable, and `tests/test_port_registry.py:26` fails on import. `test_bo2400e_3_durable_write.py:58`
   runs `import resource` (POSIX-only) at module level instead of skipping.
3. `test_bo202_covered_by_autofix_scope.py` errored in the 2026-09-25 run but collected cleanly on
   2026-09-27. Observed, not yet traced to code.

**Why CI does not see it.** `.github/workflows/ci.yml:178` runs `pytest tests/ unit_tests/`, which
never collects `scripts/`, and CI runs on Linux. Bare `pytest` is affected, and so is
`/finalize-feature` Step 0, which runs `pytest --tb=no -q` with no paths
(`templates/workflows-js/finalize-feature.js:810`).

## Fix direction

- Add `testpaths = tests unit_tests` to `pytest.ini`, so a bare run matches CI.
- Rename `scripts/ac_store/test_enforcement.py` (for example to `covers_enforcement.py`), or set
  `python_files` so production modules never match. Either change alone removes the collision.
- Consider `--import-mode=importlib`, or give one of the two `ac_store` packages a distinct name.
- Move `fcntl` in `port_registry.py` inside the POSIX branch of the lock helper. Make the `resource`
  import conditional, with `pytest.importorskip` or a platform skip.

**Pattern:** a production module named like a test, so what the suite contains depends on which directory pytest happens to walk first.
