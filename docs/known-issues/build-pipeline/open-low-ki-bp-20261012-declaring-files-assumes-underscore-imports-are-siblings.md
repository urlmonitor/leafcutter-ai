---
title: "KI-BP-20261012-declaring-files-assumes-underscore-imports-are-siblings — the declaring-files inspection resolves every bare underscore-prefixed import to the importing file's own directory and never scans non-underscore imports, so a hook importing from its parent directory is reported MISSING while real gaps go unseen"
description: "medium — a hook in commit_guardian/hooks/ that put its parent directory on sys.path and imported _resolve_root was reported MISSING as hooks/_resolve_root.py. That failed CI's Consumer install simulation and seven test_bp_900h_4 tests on PR #944 (INF-600k-1, 2026-09-30). It was worked around with a sibling re-export module, and the inspection is unchanged. Non-underscore helper imports are not scanned at all, so a missing one would not be reported."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
  - docs/known-issues/build-pipeline/open-low-ki-bp-20260909-declaring-files-helper-wrapped-import.md
  - docs/known-issues/build-pipeline/open-low-ki-bp-20260909-declaring-files-tempdir-path.md
---

# KI-BP-20261012-declaring-files-assumes-underscore-imports-are-siblings — every bare underscore import is read as a same-directory file

> Filed 2026-10-12 from the INF-600k-1 build (PR #944). Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium (indexed low). The observed failure fails closed: a spurious MISSING that
  blocks CI, naming a file that must not exist. The untested half is the opposite: non-underscore
  helper imports are never checked, so a missing one would pass silently. That half has not been
  observed.
- **Status:** open, no AC. Worked around at the call site, as described below. The inspection is
  unchanged.
- **Occurrences:** 1 (PR #944, INF-600k-1, 2026-09-30; merged 2026-10-02 as `24c49546f`).
- **First seen:** 2026-09-30 · **Last seen:** 2026-09-30
- **Where:** `scripts/ci/_declaring_files_scan.py` on origin/main `e93eda09a`:
  - `_sibling_relative_path` (:234-239) places the module in `Path(read_by_rel).parent`.
  - `_helper_module_declaring_files` (:242-277) applies it to every bare import.
  - `_UNDERSCORE_MODULE_RE` (:64) is the underscore-only filter, applied at :254 and :264.

  The scan feeds `scripts/ci/_declaring_files_derivation.py:142`. That feeds
  `scripts/ci/check_declaring_files.py` (MISSING line at :93-94), which runs in CI's "Consumer install
  simulation (BP-900h-1)" job (`.github/workflows/ci.yml:905`, invoked at :942 and :953). It also
  feeds `unit_tests/portability/test_bp_900h_4.py` and `test_bp_900h_4_i.py`.

## Symptom

For a bare `from _x import ...` or `import _x`, the inspection derives
`expected_at = <importing file's dir>/_x.py`. It does not look at how the importing script finds
its modules.

`templates/scripts/commit_guardian/hooks/check_agent_spawn_consistency.py` lives one level below
`commit_guardian/`. It inserts its parent directory on `sys.path` (today at :59) and then imported
`from _resolve_root import ...`. At runtime that resolves to the real
`commit_guardian/_resolve_root.py`. The inspection reported it MISSING as `hooks/_resolve_root.py`.
That failed CI's Consumer install simulation and seven `test_bp_900h_4` tests.

Only underscore-prefixed names are scanned. The same hook today imports three non-underscore
modules from its parent directory (:60-62): `agent_spawn_external_callers`, `card_mermaid_parser`
and `package_root_lookup`. None of them is checked. If the build stopped deploying one, this
inspection would not report it. The hook would fail with `ImportError` in a consumer install.

## Workaround, as taken

A sibling re-export module, `templates/scripts/commit_guardian/package_root_lookup.py`, re-exports
`find_project_root` and `resolve_package_root` from `_resolve_root`. It also holds the hook's
warn-and-fall-back root policy, `resolve_package_root_or_project_root`. The hook imports through it,
so the only scanned underscore import, `_resolve_root` inside `package_root_lookup.py`, is a real
sibling. The module's docstring and DECISION HISTORY record this.

The same rule is shaping module names elsewhere. `scripts/ac_store/pytest_outcome_reader.py`'s
docstring (:13-17) says it has no leading underscore because it is imported from another directory,
and "an underscore reads to the declaring-files inspector as a same-directory sibling".

## Detection

A `MISSING: ... expected_at=<root>/<dir>/_x.py` line where `_x.py` exists one or more directories
up, and the reading file adds that directory to `sys.path` relative to `__file__`.

## Suggested fix

- Resolve imports the way the importing script resolves them. Honour a `sys.path.insert(0, ...)`
  whose argument is anchored on `__file__` (for example `Path(__file__).resolve().parent.parent`),
  and look up the module in each such directory in insert order before the script's own directory.
  The module already recognises `__file__` anchoring (`_is_file_anchored_ancestor_walk`, :99).
- Or support an explicit declaration a script can make, such as a module-level tuple naming the
  helper modules it needs and where they live. It is cheaper than inference and reviewable.
- Scan non-underscore helper imports too. An import is a helper import when it resolves to a file
  inside the deployed tree; standard-library and installed packages do not.
- Whatever is chosen, name the resolution rule in the MISSING message, so the next author can tell
  "the file is absent" from "the inspection looked in the wrong directory".

**Related.** `KI-BP-20260909-declaring-files-helper-wrapped-import` and
`KI-BP-20260909-declaring-files-tempdir-path` are the same function inferring from syntax what only
the runtime decides: which imports are optional, and which joins load a sibling.

**Pattern:** a static check that models "where does this import resolve" with a fixed rule, and
whose blind spot is set by naming convention rather than by what the code does.
