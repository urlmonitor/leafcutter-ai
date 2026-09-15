---
title: "KI-BP-20260914-build-crashes-on-a-cp1252-stdout — build.py dies with UnicodeEncodeError when its output is piped on Windows, so every test that runs the build as a subprocess fails locally"
description: "medium. The build itself is sound, but it cannot run under capture on a default Windows console, which is how tests, hooks and CI wrappers run it. Locally this surfaces as a mass of unrelated-looking test failures and errors."
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

# KI-BP-20260914-build-crashes-on-a-cp1252-stdout — build.py dies with UnicodeEncodeError when its output is piped on Windows, so every test that runs the build as a subprocess fails locally

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium. The build itself is sound, but it cannot run under capture on a default Windows console, which is how tests, hooks and CI wrappers run it. Locally this surfaces as a mass of unrelated-looking test failures and errors.
- **Status:** open
- **Occurrences:** 1 session (2026-09-14). A local run of `unit_tests/portability` reported `38 failed, 178 passed, 20 errors`. Only `test_ge_120c_1.py` was inspected, and it failed on this crash. The other failures were not individually attributed, so treat the count as an upper bound, not a measurement.
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `scripts/build.py` and the phase printers it calls, which print `✓` (U+2713). Any `print` of non-cp1252 text to a redirected stdout triggers it.

**Reproduction (Windows, Python 3.14, no `PYTHONIOENCODING`).**

```text
$ python -c "import sys; print(sys.stdout.encoding)" | cat
cp1252
$ python scripts/build.py --target-dir "$(mktemp -d)/t" > out.txt 2>&1; echo $?
1
$ grep UnicodeEncodeError out.txt
UnicodeEncodeError: 'charmap' codec can't encode character '✓' in position 2: character maps to <undefined>
```

With `PYTHONIOENCODING=utf-8` set, the same command exits 0. That is how this session bootstrapped a fresh worktree.

**Mechanism.** On an interactive console Python writes UTF-16 through the console API, so `✓` prints fine, and a person running the build by hand never sees the crash. When stdout is a pipe or file, Python uses the ANSI code page (cp1252), which has no `✓`. The first status line raises, and the build aborts after doing part of its work. Tests that run `build.py` through `subprocess.run(capture_output=True)`, such as the GE-120c-1 deployed-check harness, always capture, so they always hit it.

**Fix direction.** At the top of `build.py`'s `main()`, call `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` and the same for `sys.stderr`, guarded for streams that lack `reconfigure`. Or replace the glyphs with ASCII. Add a test that runs `build.py --help`, or a dry build, as a subprocess with `PYTHONIOENCODING` explicitly removed from the environment and asserts exit 0. Also re-run `unit_tests/portability` on Windows once fixed, and attribute any remaining failures separately.

**Related.** `KI-BP-20260910-1240` is the other Windows-only build defect found in the same epic: text-mode I/O that behaves differently on Windows than on Linux CI, where CI can never catch it.

**Pattern:** output that only fails when it is captured, so the people who run the tool by hand never see what every automated caller hits.
