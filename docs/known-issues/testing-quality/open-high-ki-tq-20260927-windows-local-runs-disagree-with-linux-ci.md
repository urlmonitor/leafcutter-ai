---
title: "KI-TQ-20260927-windows-local-runs-disagree-with-linux-ci — a fixed set of tests fails on an unmodified Windows checkout and pass on Linux CI, so a local red run cannot tell a regression from the baseline"
description: "high — six separate Windows causes (cmd.exe running POSIX sh, NTFS ignoring chmod, a POSIX-only import, cp1252 subprocess stdin, MSYS vs Windows temp paths, plus a Windows path-repr mismatch) make a fixed set of tests fail locally. On 2026-09-25 a real regression hid inside that set until CI. Each cause reproduced on 2026-09-27 at main 93bd801c."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/build-pipeline/open-low-ki-bp-20260914-build-crashes-on-a-cp1252-stdout.md
  - docs/known-issues/build-pipeline/open-high-ki-bp-20260910-1240.md
---

# KI-TQ-20260927-windows-local-runs-disagree-with-linux-ci — a fixed set of tests fails on an unmodified Windows checkout and pass on Linux CI, so a local red run cannot tell a regression from the baseline

- **Severity:** high. Silent wrong behaviour in the verification loop. On 2026-09-25, 20 failures in `unit_tests/workflows/test_acd_2100a_4.py`, `test_acd_2100c_2.py`, `test_acd_2100c_3.py` and `test_acd_2100c_3_i.py` were read as "pre-existing", because they also fail on unmodified main locally. A real regression among them surfaced only on CI. That account is from the session and not re-verified. The local failure set is reproduced below.
- **Status:** open. No AC.
- **Occurrences:** 1 incident (2026-09-25). The failure set is deterministic on this machine.
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-27
- **Where:** listed per cause below. CI runs only `ubuntu-latest` (`.github/workflows/ci.yml:94` and every other job), so nothing exercises Windows.

## Causes (each reproduced 2026-09-27, Windows 11, Python 3.14, Git Bash)

**(a) Node `execSync` runs through cmd.exe, but the commands are POSIX sh.** The test shims call `execSync(cmd, { cwd, encoding, timeout })` with no `shell` option (`unit_tests/workflows/test_acd_2100a_4.py:274`, `:304`; the same shim is in `test_acd_2100c_2.py:209/233` and `test_acd_2100c_3.py:184/208`). On win32, Node runs that through `%ComSpec%`, which is cmd.exe. The command is built by `_buildRepoRootResolutionSnippet()` (`templates/workflows-js/plan-feature.js:2091-2124`) via `buildPauseStoreCommand()` (`:2207`), and it is POSIX sh (`$(...)`, `for d in */`, `[ -z ... ]`). So the pause-store call fails. Result under default ComSpec: `test_acd_2100a_4.py` 4 failed, `c_2` 4, `c_3` 7, `c_3_i` 5 (the 20 above; `c_*` show `pause_persist_failed`), plus `test_acd_2100a_1.py` 3 and `test_acd_2100a_5.py` 3.

**(b) `chmod` cannot deny access on NTFS.** Tests that simulate "permission refused" with `chmod(0o555)` / `chmod(0o000)` still find the path writable or readable, so the refusal branch never runs:
`test_acd_2100a_4.py::test_reported_write_failure_matches_what_is_on_disk` (`:666`); `unit_tests/ac_driven_dev/test_acd_2100b_1.py` × 2 (`:147`); `unit_tests/workflows/test_acd_2100b_1.py::TestUnreadableRegistryReport::test_permission_refused_and_absent_verdicts_render_different_reports` (`:275`).

**(c) POSIX-only import at module level.** `unit_tests/build_orchestration/test_bo2400e_3_durable_write.py:58` has `import resource`, which gives `ModuleNotFoundError: No module named 'resource'`. That is a collection error for the whole file.

**(d) cp1252 subprocess stdin in the E2 runner.** `unit_tests/_plan_feature_e2_runner.py:175-183` runs `subprocess.run(["node", "--input-type=module"], input=script_text, text=True)` with no `encoding`, so Python encodes stdin as cp1252. The script embeds `templates/workflows-js/plan-feature.js`, which contains `→` (U+2192) and `⇒` (U+21D2). The registry JSON is ASCII-escaped by `json.dumps`, so it is not the culprit. The stdin writer thread raises `UnicodeEncodeError: ... '\u2192' in position 87323`. Node never gets EOF, and the test fails as `TimeoutExpired ... timed out after 25 seconds`. Reproduced: `unit_tests/test_partial_run_recovery.py` fails after 25.7 s by default and gives 19 passed in 3 s with the recipe below. Every test using this runner is affected (e.g. `test_commit_stage_output_*.py`, `test_final_gate_and_commit_message.py`). **Same class as `KI-BP-20260914-build-crashes-on-a-cp1252-stdout`, different site:** that entry is `build.py`'s own stdout, and this is a test helper's stdin. Neither fix covers the other.

**(e) MSYS vs Windows temp paths under the bash workaround.** With `COMSPEC` pointed at Git Bash, the snippet's `pwd` returns MSYS paths (`/tmp/acd2100a5_.../project/...`), while the tests compare against `C:\Users\...\Temp\...`. Remaining failures: `test_acd_2100a_1.py::test_worktree_step_invocation_is_reached_from_the_workflow_entry_point`, `::test_wrong_copy_execution_is_observable_and_blocks`, and `test_acd_2100a_5.py::test_every_resolved_support_file_path_observed_before_the_first_question_is_inside_the_project`.

**(f) Windows path repr in a diagnostic (not chmod).** `unit_tests/ac_driven_dev/test_acd_2100a_2_i.py::TestRefusalNamesEveryCandidateItFound::test_refusal_names_every_candidate_it_found` looks for `str(candidate)` (backslashes). The script prints the candidate list as `[WindowsPath('C:/Users/...')]` (forward slashes), so the substring never matches.

## Detection

Run the affected files on Windows with no special environment. They fail on an unmodified checkout of main. Compare with the Linux CI run for the same SHA. A local red that CI does not show is this entry, not your change, until you check.

## Workaround (exact recipe, Git Bash)

```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 \
COMSPEC='C:\Program Files\Git\bin\bash.exe' \
python -m pytest unit_tests/workflows/test_acd_2100a_4.py unit_tests/workflows/test_acd_2100c_2.py \
  unit_tests/workflows/test_acd_2100c_3.py unit_tests/workflows/test_acd_2100c_3_i.py
```

Under this recipe, `a_1`, `a_4`, `a_5`, `c_2`, `c_3` and `c_3_i` go from 26 failed to 4 failed, 22 passed. The remaining 4 are cause (b) × 1 and cause (e) × 3. Causes (b), (c) and (f) have no environment workaround. Treat those tests as unverifiable locally and read CI for them.

## Suggested fix

- (a) In the test shims, pass `shell: <bash>` to `execSync` on win32, or skip with a stated reason when no POSIX shell is found. The product has the same exposure wherever an agent runs the snippet in cmd.exe or PowerShell. That is not re-verified here.
- (b) Deny access portably (e.g. `icacls` on Windows) or `skipif(os.name == "nt")` with a reason.
- (c) `pytest.importorskip("resource")`, or import it inside the test that needs it.
- (d) `encoding="utf-8"` on the runner's `subprocess.run`.
- (e) Normalise paths on both sides (`cygpath -w` or `Path.resolve()`) before comparing.
- (f) Print `str(p)` in the diagnostic, or compare with `as_posix()`.
- Add a Windows job to CI, even a small allow-listed one, so this class stops depending on someone noticing locally.

**Someone may be starting on this:** worktree `feature/windows-portable-tests` (`C:/Users/Hendrik/Code/leafcutter/worktrees/windows-portable-tests`) was created 2026-09-27 at main tip. As of filing it carries one commit, `efa35b4b` ("test: three test files pass on Windows (BP-1500d-1, check-doc-length, KM-300a-1)"). That commit touches other test files, none of those named above. Check that branch before starting.

**Pattern:** a baseline that is red for environmental reasons trains people to stop reading red.
