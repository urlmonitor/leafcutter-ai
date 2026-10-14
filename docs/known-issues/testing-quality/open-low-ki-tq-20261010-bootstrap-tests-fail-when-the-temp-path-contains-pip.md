---
title: "KI-TQ-20261010-bootstrap-tests-fail-when-the-temp-path-contains-pip — six setup_ticket_worktree tests route subprocess calls by substring, so a random temp directory whose name contains 'pip' sends the build.py call down the install branch and the test fails"
description: "low — a rare CI flake with a deterministic cause. The fake subprocess.run in six tests of tests/test_setup_ticket_worktree.py checks '\"pip\" in cmd_str' before it checks for build.py. The build command carries the temp path, so when tempfile picks a name like tmpipohl1rp the build is answered as a pip install, no .pre-commit-config.yaml is written, and _bootstrap raises BootstrapError. Seen once on PR #1138 (shard 2/8), green on rerun. Reproduced every time with a temp root whose path contains 'pip'."
type: reference
category: reference
status: active
created: '2026-10-10'
last_updated: '2026-10-10'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20260914-tempdir-cleanup-race-fails-a-green-test-run.md
---

# KI-TQ-20261010-bootstrap-tests-fail-when-the-temp-path-contains-pip — a substring router in a test fake reads the temp path

> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. It costs a rerun of the failed jobs, and it shows up on whatever PR is running,
  here a docs-only one. Rare: about 1 in 1,200 runs per affected test, so roughly 1 in 200 CI runs
  across the six tests (estimate below).
- **Status:** open, no AC. Cause verified: the CI log matches the mechanism line for line, and the
  failure reproduces every time locally.
- **Occurrences:** 1 in CI. PR #1138 (docs-only), CI run `38053212873`, job `114216373815`,
  "Test suite shard 2/8", 2026-10-10 13:01 UTC. Green on a rerun of the failed jobs (attempt 2).
  main's CI was green at the same base.
- **First seen:** 2026-10-10 · **Last seen:** 2026-10-10
- **Where:** `tests/test_setup_ticket_worktree.py` on `origin/main` `d03830e7c`. In
  `TestBootstrapAC1HappyPath::test_ac1_no_bootstrap_error_when_config_present` the fake is
  `fake_run` (:1000-1012). The `"poetry" in cmd_str or "pip" in cmd_str` branch (:1004) comes before
  the `"build.py" ... "--target-dir"` branch that writes the config (:1006-1011). The production
  side is `scripts/setup_ticket_worktree.py`: the build call (:1483) and the AC-5 safety net that
  raises (:1511).

## Symptom

```text
FAILED tests/test_setup_ticket_worktree.py::TestBootstrapAC1HappyPath::test_ac1_no_bootstrap_error_when_config_present
  BootstrapError: AC-5: .pre-commit-config.yaml is missing at /tmp/tmpipohl1rp/worktree/.pre-commit-config.yaml.
  scripts/setup_ticket_worktree.py:1511
----------------------------- Captured stderr call -----------------------------
WARNING: no pyproject.toml or requirements-dev.txt found in /tmp/tmpipohl1rp/worktree; skipping dependency install.
WARNING: neither /tmp/tmpipohl1rp/main/.leafcutter nor /tmp/tmpipohl1rp/main/.pre-commit-config.yaml found in the main repo. ...
1 failed, 1607 passed, 1 skipped, 8895 deselected, 5 xfailed
```

**build.py did not fail.** "WARNING: build.py run failed in new worktree" does appear in the log,
but only as source lines in the traceback's listing of `_bootstrap` (`setup_ticket_worktree.py:1488`).
The captured stderr has no such warning, and no "build.py not found" warning either. So the build
call returned normally and wrote nothing.

## Mechanism

1. The temp directory was `/tmp/tmpipohl1rp`. Its name contains `pip` (`tm[p][ip]ohl1rp`).
2. `_bootstrap` runs `[sys.executable, "<tmp>/worktree/scripts/build.py", "--target-dir",
   "<tmp>/worktree"]`. `fake_run` joins it into `cmd_str` and tests `"pip" in cmd_str` first. That
   matches on the path, so it returns `MagicMock(returncode=0)` without writing
   `.pre-commit-config.yaml`.
3. No `CalledProcessError`, so no warning. `_establish_pre_commit_config` finds neither source in
   the empty main repo and prints its step-4 warning. The AC-5 safety net raises, and the test
   fails at :1023.

**Reproduced (verified).** I ran the file with `TEMP`/`TMP`/`TMPDIR` pointed at a directory whose
path contains `pip`. Result: 8 failed, 23 passed, with the same `BootstrapError` and the same two
warnings. Under a plain temp root: 2 failed, 29 passed. The 2 that fail in both runs are
`TestEstablishPreCommitConfigSymlinkPath`, a local Windows symlink limitation unrelated to this.
So **six tests** share the defect:

- `TestBootstrapPoetryRepo::test_bootstrap_uses_poetry_when_pyproject_toml_present`
- `TestBootstrapAC5RaisesWhenConfigAbsent::test_ac5_raises_with_build_exc_when_called_process_error`
- `TestBootstrapAC1HappyPath::test_ac1_config_resolvable_at_worktree_root_after_bootstrap`
- `TestBootstrapAC1HappyPath::test_ac1_no_bootstrap_error_when_config_present`
- `TestBootstrapAC3Idempotency::test_ac3_main_repo_tree_unchanged_after_bootstrap`
- `TestBootstrapAC2ProbeGuarantee::test_ac2_probe_precondition_config_present_implies_hooks_activatable`

**Rate (estimate).** `tempfile` names are `tmp` plus 8 characters from a 37-character alphabet.
`pip` appears when the first two are `ip` (1 in 1,369) or anywhere in the eight (about 1 in
8,400). That is about 1 in 1,180 per test, independently per test, so about 1 in 200 runs of the
file. The fixed `/tmp/` prefix contains no `pip`. The runner's interpreter path cannot contain it
either, or every run would fail.

## Workaround

Rerun the failed jobs. Nothing in the change under test is implicated.

## Fix direction

- Match on the command's structure, not a substring of the joined string. For example, route on
  `Path(cmd[1]).name == "build.py"` before anything else, and treat an install only when `cmd`
  holds `install` with `pip`/`poetry` as a whole argument (`"pip" in cmd`, not `in cmd_str`).
  Several fakes in the same file use the substring form (:861, :926, :1004, :1052, :1103, :1157,
  :1227, :1327), and the assertions at :528, :577, :626, :662 and :764 filter commands the same way.
- Add a regression test that runs one of these tests with a temp root containing `pip`, or fix the
  temp name (`tempfile.TemporaryDirectory(prefix="wt-")` still leaves eight random characters, so
  the routing fix is the real one).

**Flaky-test register.** This repo has no file-based flaky or known-failing register: the
`known_failing_tests` baseline was retired on 2026-08-18
(`changelogs/2026-08-18-1420-retire-the-known-failing-tests-baseline-a-gate-that-never-ran.md`).
Pass-on-retry is tracked by CI itself in one `post-merge-flaky` issue (`scripts/ci/_flaky_notice.py`,
TQ-600a-13-xiii). That covers only the post-merge correctness lane on main and is written by CI,
not by hand. This failure was in a PR run, so this entry is its only record. No `post-merge-flaky`
issue exists as of 2026-10-10.

**Related.** `KI-TQ-20260914-tempdir-cleanup-race-fails-a-green-test-run`: another CI-only failure
that comes from the temp directory rather than the change under test.

**Pattern:** a test fake that routes on a substring of a string that includes a random path.
