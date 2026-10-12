---
ac_traceability:
  id: BO-4300c-6
  path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-6.yaml
ac_coverage: 11/11
advances_current_outcome: true
agents:
  ac-fulfillment-gate: signed_off
  ac-validator: signed_off
  architect-review: signed_off
  commit: signed_off
  documentation-expert: not_needed
  documentation-verifier: not_needed
  frontend-coder: not_needed
  pr-reviewer: signed_off
  pull-request: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  test-writer: signed_off
  user-surface-smoker: not_needed
change_target: code
complexity: medium
components:
- worktree_manager
- build_orchestration
- precommit_hooks
created: '2026-10-10'
depends_on:
- 05_TICKET-20260928-BO-4300-readiness.md
documentation_required: false
files_touched:
- templates/scripts/commit_guardian/precommit_canary.py
- unit_tests/build_orchestration/test_bo_4300c_6.py
- unit_tests/build_orchestration/test_bo_4300c_6_real_install.py
- unit_tests/build_orchestration/_bo_4300c_6_fixtures.py
- unit_tests/build_orchestration/test_bo_4300c_1_real_install.py
- docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-6.yaml
out_of_scope:
- scripts/build_deploy_manifest_helpers.py
- scripts/build_helpers.py
- scripts/build_phases_script_deploy.py
- scripts/build_phases_script_deploy_standalone.py
- scripts/build_shim_env.py
- templates/scripts/workspace_root.py
- templates/scripts/worktree.py
- templates/scripts/worktree_admin.py
- templates/scripts/worktree_answer.py
- templates/scripts/worktree_canaries.py
- templates/scripts/worktree_ensure_state.py
- templates/scripts/worktree_git.py
- templates/scripts/worktree_identity.py
- templates/scripts/worktree_layout.py
- templates/scripts/worktree_paths.py
- templates/scripts/worktree_readiness.py
- unit_tests/build_orchestration/_bo2400f13_fixtures.py
- unit_tests/build_orchestration/_bo_4300a_1_fixtures.py
- unit_tests/build_orchestration/_bo_4300a_1_ii_fixtures.py
- unit_tests/build_orchestration/_developer_repo_guard.py
- unit_tests/build_orchestration/_workspace_maker_build_helpers.py
- unit_tests/build_orchestration/_workspace_maker_builders.py
- unit_tests/build_orchestration/_workspace_maker_fixtures.py
- unit_tests/build_orchestration/conftest.py
- unit_tests/build_orchestration/test_bo2400f_13i_own_leftover_report.py
- unit_tests/build_orchestration/test_bo_4300a_1.py
- unit_tests/build_orchestration/test_bo_4300a_1_deployed.py
- unit_tests/build_orchestration/test_bo_4300a_1_ib.py
- unit_tests/build_orchestration/test_bo_4300a_1_ii.py
- unit_tests/build_orchestration/test_bo_4300a_2.py
- unit_tests/build_orchestration/test_bo_4300b_1.py
- unit_tests/build_orchestration/test_bo_4300b_1_i.py
- unit_tests/build_orchestration/test_bo_4300b_2.py
- unit_tests/build_orchestration/test_bo_4300b_2_i.py
- unit_tests/build_orchestration/test_bo_4300b_2_ii.py
- unit_tests/build_orchestration/test_bo_4300b_3.py
- unit_tests/build_orchestration/test_bo_4300b_3_i.py
- unit_tests/build_orchestration/test_bo_4300b_4.py
- unit_tests/build_orchestration/test_bo_4300b_5.py
- unit_tests/build_orchestration/test_bo_4300b_5_i.py
- unit_tests/build_orchestration/test_bo_4300c_1.py
- unit_tests/build_orchestration/test_bo_4300c_1_canary_git_failure.py
- unit_tests/build_orchestration/test_bo_4300c_1_canary_order.py
- unit_tests/build_orchestration/test_bo_4300c_1_i.py
- unit_tests/build_orchestration/test_bo_4300c_1_ii.py
- unit_tests/build_orchestration/test_bo_4300c_1_iii.py
- unit_tests/build_orchestration/test_bo_4300c_1_marker_and_guardian.py
- unit_tests/build_orchestration/test_bo_4300c_1_path_keyed_canaries.py
- unit_tests/build_orchestration/test_bo_4300c_1_review_fixes.py
- unit_tests/build_orchestration/test_bo_4300c_2.py
- unit_tests/build_orchestration/test_bo_4300d_1.py
- unit_tests/build_orchestration/test_bo_4300d_1_i.py
- unit_tests/build_orchestration/test_bo_4300d_1_ii.py
- unit_tests/build_orchestration/test_bo_4300d_2.py
- unit_tests/build_orchestration/test_bo_4300d_2_i.py
- unit_tests/build_orchestration/test_bo_4300d_2_ii.py
- unit_tests/build_orchestration/test_bo_4300d_2_iii.py
- unit_tests/build_orchestration/test_bo_4300d_3.py
- unit_tests/build_orchestration/test_bo_4300d_3_i.py
- unit_tests/build_orchestration/test_bo_4300d_4.py
- unit_tests/build_orchestration/test_bo_4300f_4.py
- unit_tests/build_orchestration/test_bo_4300f_4_i.py
priority: critical
requires_adr: false
requires_diagram: false
risk_surface: safety
roadmap_phase: phase_1
source_ac: BO-4300c-6
status: done
title: A protection canary never mistakes a git failure for a pass, and never blocks
  ordinary work
last_updated: '2026-10-10'
tags:
- BO-4300
- canary-fix-2026-10-10
---

# A protection canary never mistakes a git failure for a pass, and never blocks ordinary work

## Actor / Goal

As the leafcutter-ai system, I want to implement AC `BO-4300c-6` — A protection canary never mistakes a git failure for a pass, and never blocks ordinary work — so that the acceptance criterion is satisfied.

## Context

This ticket was generated from AC store entry `BO-4300c-6`. Component: `build-orchestration`. Assigned agent: `python-coder`. Estimated complexity: `M`. Complexity: `medium`.

## Acceptance Criteria

```gherkin
Given a project in which git fails when the commit-time canary asks which
  files are staged -- for example because the staging index is corrupt, or
  because the setting that tells git where its repository is points at a
  folder that is not one -- once with the canary's reserved file staged and
  once with only an ordinary file staged,
When the commit-time canary runs,
Then in both cases it fails, which stops the commit, and its report names the
  git command that failed, the status git ended with, and git's own error
  message,
And it does not give the rejection signal that the workspace maker counts as
  "this protection fired", so a git failure is never counted as a firing,
And a git failure is never reported as "the reserved file is not staged".

Given a working project in which nothing has been merged yet, so git holds no
  record of where the line of work stood before a merge -- for example a
  fresh copy in which the after-merge canary is run by hand,
When the after-merge canary runs,
Then it passes with nothing to check and gives no rejection signal.

Given a project in which git fails when the after-merge canary asks what a
  merge brought in, for any reason other than that missing record -- for
  example because the setting that tells git where its repository is points
  at a folder that is not one,
When the after-merge canary runs,
Then it reports the merge as failing, naming the git command that failed,
  the status git ended with, and git's own error message,
And it gives no rejection signal, and never reports the failure as "nothing
  was merged".

Given an ordinary commit whose message is not UTF-8 text -- for example the
  word "Größe" in the Windows Western European encoding (cp1252) -- and an
  ordinary commit whose message is empty in a project that allows empty
  messages,
When the commit-message canary checks each message,
Then each commit goes through, and the canary neither stops with a crash
  report nor gives the rejection signal,
And a commit whose first message line is exactly the reserved line the
  install declares is still rejected with the rejection signal, whether the
  message's lines end in a line feed alone or in a carriage return and line
  feed.

Given the canaries exactly as an install delivers them, each run as its own
  program in the way the hook runner runs it, inside a real temporary project
  under version control with nothing standing in for git,
When an ordinary file is staged for a commit, and a branch that adds an
  ordinary file is merged with a merge commit rather than a fast-forward,
Then the commit-time canary and the after-merge canary both pass and give no
  rejection signal,
And in that same project, staging the reserved commit-time file makes the
  commit-time canary reject it with the rejection signal, and merging a
  branch that adds the reserved after-merge file makes the after-merge canary
  report the merge as failing with the rejection signal,
And a canary altered to reject every staged file, or every file a merge
  brings in, fails this proof.
```

- [x] AC-1: in both cases it fails, which stops the commit, and its report names the
- [x] AC-2: it does not give the rejection signal that the workspace maker counts as
- [x] AC-3: a git failure is never reported as "the reserved file is not staged".
- [x] AC-4: it passes with nothing to check and gives no rejection signal.
- [x] AC-5: it reports the merge as failing, naming the git command that failed
- [x] AC-6: it gives no rejection signal, and never reports the failure as "nothing
- [x] AC-7: each commit goes through, and the canary neither stops with a crash
- [x] AC-8: a commit whose first message line is exactly the reserved line the
- [x] AC-9: the commit-time canary and the after-merge canary both pass and give no
- [x] AC-10: in that same project, staging the reserved commit-time file makes the
- [x] AC-11: a canary altered to reject every staged file, or every file a merge

## Test Requirements

```yaml
tests:
- name: test_commit_time_canary_fails_closed_on_corrupt_index_with_git_report
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  asserts: 'test_bo_4300c_6.py. Two arms in a real temp repo, one with the declared
    reserved pre-commit path staged and one with only an ordinary file staged; .git/index
    is then truncated. The deployed canary, run with cwd = the project, exits non-zero.
    PRECOMMIT_CANARY_REJECTED is absent from stdout and stderr. stderr carries one
    `precommit_canary: git <args> exited <rc>:` line whose non-zero rc is reproduced
    by re-running `git <args>` in the same cwd and env, and git''s own "index file
    smaller than expected" text.'
  framework: unittest
  type: behavioral
  angle: failure
  must_catch:
  - git's non-zero exit read as an empty staged-file list, so the canary exits 0 --
    the shipped defect, "the reserved file is not staged"
  - the git failure reported with PRECOMMIT_CANARY_REJECTED, so readiness counts it
    as the stage firing
  - git's stderr discarded, so the report names neither the exit status nor git's
    message
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
- name: test_commit_time_canary_fails_closed_when_git_dir_is_not_a_repository
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  asserts: test_bo_4300c_6.py. Same two arms (reserved path staged / only an ordinary
    file staged) with GIT_DIR set to an empty folder under the temp dir and GIT_CEILING_DIRECTORIES
    set to the temp dir's parent. The canary exits non-zero with no marker. Its stderr
    report names a git command and a non-zero status that re-running the command reproduces,
    and includes the first line of git's own stderr from that re-run.
  framework: unittest
  type: behavioral
  angle: failure
  must_catch:
  - git's non-zero exit (129 under a non-repository GIT_DIR) read as an empty staged-file
    list (exit 0)
  - the git failure reported with PRECOMMIT_CANARY_REJECTED
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
- name: test_after_merge_canary_passes_when_nothing_was_merged
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  asserts: 'test_bo_4300c_6.py. Two arms: a fresh `git clone` of a temp source repo,
    and a fresh repo with one commit. Precondition: `git rev-parse -q --verify ORIG_HEAD`
    exits 1 in each. The deployed post-merge canary, run by hand with cwd = the project,
    exits 0 with no marker and no `precommit_canary: git ... exited` report on stderr.'
  framework: unittest
  type: behavioral
  angle: boundary
  must_catch:
  - a missing ORIG_HEAD treated as a git failure, so a hand run in a fresh clone exits
    1
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
- name: test_after_merge_canary_fails_closed_when_git_dir_is_not_a_repository
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  asserts: test_bo_4300c_6.py. After a real --no-ff merge (so ORIG_HEAD exists), the
    canary runs with GIT_DIR pointing at an empty non-repository folder and GIT_CEILING_DIRECTORIES
    at the temp dir's parent. It exits non-zero with no marker, and never exits 0.
    The stderr report names the failing git command, a non-zero status that re-running
    the command reproduces, and git's own "not a git repository" text.
  framework: unittest
  type: behavioral
  angle: failure
  must_catch:
  - every failure of the ORIG_HEAD probe or of the merge listing treated as "nothing
    was merged" (exit 0)
  - the git failure reported with PRECOMMIT_CANARY_REJECTED
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
- name: test_after_merge_canary_fails_closed_on_dangling_orig_head
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  asserts: test_bo_4300c_6.py. After a real --no-ff merge, .git/ORIG_HEAD is overwritten
    with a well-formed object id that names no object, so the record is present but
    broken. The canary exits non-zero with no marker, and its stderr report names
    the failing git command, its non-zero status and git's own "bad object" text.
  framework: unittest
  type: behavioral
  angle: discrimination
  must_catch:
  - an absence probe that peels the record (ORIG_HEAD^{commit}), which exits 1 for
    a dangling record as well as for a missing one, so a broken repository is reported
    as nothing merged
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
- name: test_commit_msg_canary_lets_non_utf8_and_empty_messages_through
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  asserts: 'test_bo_4300c_6.py. A real repo whose .git/hooks/commit-msg shim runs
    the deployed canary as registered (`--stage commit-msg "$1"`). Two arms: `git
    commit -F <file>` with the bytes b"Gr\xf6\xdfe\n" (cp1252), and an empty message
    with --allow-empty-message, each run with cwd = the project. Each commit exits
    0 and advances HEAD. stdout and stderr contain neither the marker nor "Traceback".
    `git cat-file commit HEAD` of the first arm still contains b"Gr\xf6\xdfe".'
  framework: unittest
  type: behavioral
  angle: boundary
  must_catch:
  - the message file decoded as UTF-8, so a cp1252 message raises UnicodeDecodeError,
    exits 1 with a traceback and blocks an ordinary commit -- the shipped defect
  - the first line taken without guarding an empty message (IndexError crash)
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
- name: test_commit_msg_canary_rejects_reserved_first_line_with_lf_or_crlf
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  asserts: 'test_bo_4300c_6.py. The deployed canary, run as the hook runner runs it
    with the message file path as the last argument, reads message files whose bytes
    the test fixes. Three files are rejected with exit 1 and the marker: reserved
    + b"\n"; reserved + b"\r\n" + b"body\r\n"; and reserved + b"\n\n" + b"Gr\xf6\xdfe\n"
    (non-UTF-8 body). Two near misses exit 0 with no marker: reserved + b" x\r\n",
    and b"subject\r\n" + reserved + b"\r\n". A real `git commit -F` of the LF reserved
    message is rejected and HEAD is unchanged.'
  framework: unittest
  type: behavioral
  angle: discrimination
  must_catch:
  - the first line compared without dropping a trailing carriage return, so a CRLF
    reserved line passes
  - the whole message decoded before comparing, so a reserved first line with a non-UTF-8
    body crashes instead of being rejected with the marker
  - a byte comparison that matches a prefix or any line instead of exactly the first
    line
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
- name: test_ordinary_non_ascii_and_non_utf8_paths_never_crash_the_canary
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  asserts: test_bo_4300c_6.py (IT PO addition under "never blocks ordinary work").
    Index entries for b"\xc5\x81\xc3\xb3d\xc5\xba.txt" (Lodz with its Polish letters
    in UTF-8; contains byte 0x81) and b"Gr\xf6\xdfe.txt" (not UTF-8) are staged through
    `git update-index --index-info` with bytes on stdin, which works on every platform.
    The deployed pre-commit canary exits 0 with no marker and no "Traceback". With
    the reserved path also staged, it exits 1 with the marker. A --no-ff merge of
    a branch adding that UTF-8 Lodz file leaves the post-merge canary at exit 0 with
    no marker.
  framework: unittest
  type: behavioral
  angle: boundary
  must_catch:
  - git's name list read as locale text, which raises UnicodeDecodeError on byte 0x81
    under cp1252 or on a non-UTF-8 path under a UTF-8 locale, so an ordinary commit
    is blocked
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
- name: test_registered_canaries_are_inert_for_ordinary_commit_and_merge_in_a_real_repo
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  asserts: 'test_bo_4300c_6_real_install.py. Replaces test_registered_canary_hooks_are_inert_for_ordinary_input.
    Each registered entry is read from the deployed layout''s generated .pre-commit-config.yaml
    and run as [sys.executable, <deployed canary absolute path>, *its arguments after
    the script], with cwd = a real temp repo. Preconditions: `git diff --cached --name-only`
    lists the staged ordinary file; after `git merge --no-ff` of a branch adding an
    ordinary file, `git rev-parse -q --verify ORIG_HEAD` exits 0 and the ORIG_HEAD..HEAD
    added-file list holds that file. Both canaries exit 0 with no marker and no git-failure
    report.'
  framework: unittest
  type: behavioral
  angle: deployed
  must_catch:
  - the inert check run outside any git repository, where git falls into --no-index
    mode and lists nothing, so a canary that rejects everything still passes -- the
    replaced test
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
- name: test_registered_canaries_reject_reserved_inputs_in_the_same_repo
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  asserts: test_bo_4300c_6_real_install.py. In the same repo and through the same
    registered entries, staging the declared reserved pre-commit path makes the pre-commit
    canary exit 1 with the marker. After a --no-ff merge of a branch adding the declared
    reserved post-merge path, the post-merge canary exits 1 with the marker.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
- name: test_reject_everything_canary_fails_the_inert_proof
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  asserts: test_bo_4300c_6_real_install.py. A temp-dir copy of the deployed canary,
    with the deployed commit_guardian.json beside it, is altered so every listed path
    counts as reserved. The test first checks that the mutant exits 1 with the marker
    on the ordinary staged file and on the ordinary merge, so the mutation applied.
    It then checks that the inert proof shared with test_registered_canaries_are_inert_for_ordinary_commit_and_merge_in_a_real_repo
    raises AssertionError for the mutant, at both the pre-commit and the post-merge
    stage.
  framework: unittest
  type: behavioral
  angle: discrimination
  must_catch:
  - a canary that rejects every staged file
  - a canary that rejects every file a merge brings in
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
- name: test_bo_4300c_6_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300c_6.py
  covers:
  - BO-4300c-6
  angle: reachability
  asserts: 'REQUIRED — invoke the production entry point (CLI, hook, slash command,
    workflow dispatch, or main()) as a subprocess/dispatch and assert the new behaviour
    actually occurs. Do NOT satisfy this by importing the function directly. The AC
    authored no test_spec, so the entry point is not declared: resolve it before writing
    this test, and do not delete this entry.'
  implementation_files:
  - .leafcutter/scripts/commit_guardian/precommit_canary.py
  - scripts/build.py
  - templates/scripts/commit_guardian/precommit_canary.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
```

## Implementation Notes

```yaml
- 'SCOPE: the code change is confined to templates/scripts/commit_guardian/precommit_canary.py,
  the only tracked source (scripts/commit_guardian/ and .leafcutter/ are gitignored
  build outputs), plus the test modules named in test_spec. worktree_canaries.py,
  worktree_readiness.py and commit_guardian.json need no change: in the maker''s own
  canary flow every git call already exits 0, so healthy repositories see no behaviour
  change. No registry entry is added (package_surface false); refreshing the existing
  `_comment` text of the three precommit-canary-<stage> members to mention failing
  closed is allowed and adds no key or member.'
- 'GIT RAN AND FAILED == GIT COULD NOT START (BO-1700b-1, KI-CG-20260901): when a
  git call the canary relies on exits with a status that does not mean "nothing to
  report", the canary fails closed exactly like the existing "git could not start"
  path -- non-zero exit, no PRECOMMIT_CANARY_REJECTED marker anywhere in its output
  -- and the failure is never read as an empty change set. Settled approach (2026-10-09
  investigation): the failing git call prints one line `precommit_canary: git <args>
  exited <rc>: <git stderr>` to stderr and raises subprocess.CalledProcessError, which
  run_stage''s existing OSError/SubprocessError handler already maps to exit 1 with
  no marker.'
- 'REPORT SHAPE: the stderr report names the git command as run (its arguments), git''s
  exit status and git''s own stderr text, trimmed of surrounding whitespace and never
  discarded or paraphrased. Re-running the named command in the same directory and
  environment reproduces the reported status. The marker never appears in the report.'
- 'POST-MERGE, ONLY A MISSING RECORD IS "NOTHING MERGED": before listing what a merge
  added, the canary probes for ORIG_HEAD. Only the absence of the ORIG_HEAD record
  (git''s quiet-verify exit 1) means nothing was merged, which gives exit 0 with no
  report. Every other outcome of the probe (for example 128 when GIT_DIR names a folder
  that is not a repository) and every non-zero exit of the listing call is a git failure
  under the rule above. Evidence (git 2.52.0.windows.1, checked 2026-10-10): `git
  rev-parse -q --verify ORIG_HEAD^{commit}` ALSO exits 1 when ORIG_HEAD is present
  but names an object that does not exist, while the unpeeled `git rev-parse -q --verify
  ORIG_HEAD` exits 0 there and the listing call then fails with 128 ("bad object").
  So the absence probe must not peel, or a dangling record is reported as "nothing
  merged" (test_after_merge_canary_fails_closed_on_dangling_orig_head). This refines
  the coordinator''s suggested `ORIG_HEAD^{commit}` probe.'
- 'COMMIT-MSG COMPARES BYTES, NEVER DECODES: the message file is read as raw bytes.
  Its first line (bytes.splitlines()[0] with any trailing b"\r" removed) is compared
  for exact equality with the declared reserved line encoded as UTF-8. A message with
  no lines (an empty file) is "not reserved". Nothing decodes the message, so a cp1252
  or other non-UTF-8 message can neither crash the canary nor block an ordinary commit,
  and a reserved first line followed by a non-UTF-8 body is still rejected with the
  marker. A message file that cannot be read stays inside the existing fail-closed
  handling (exit 1, no marker).'
- 'NAME LISTS COMPARE BYTES TOO (IT PO addition: same defect class as the commit-msg
  crash, reproduced on the current deployed canary on 2026-10-10): git''s NUL-separated
  name list (pre-commit and post-merge) is read as raw bytes and split on NUL. The
  membership test uses the declared reserved path encoded as UTF-8. Reading git''s
  output as locale text crashes the canary (exit 1 with a traceback). It does so on
  an ordinary staged path whose UTF-8 bytes include 0x81 (for example the city name
  Lodz spelled with its Polish letters, U+0141 first) under a cp1252 locale, where
  byte 0x81 is undefined, and on any non-UTF-8 staged path under a UTF-8 locale, so
  ordinary work is blocked. git''s stderr is captured as bytes and decoded only for
  the report, with undecodable bytes replaced. The decode never raises.'
- 'UNCHANGED CONTRACTS: the no-argument PRECOMMIT_CANARY_OK path is byte-for-byte
  unchanged (unit_tests/commit_guardian/test_precommit_canary.py). The "git could
  not start" path keeps exit 1 and its `precommit_canary: git failed for <stage>`
  stderr line, so unit_tests/build_orchestration/test_bo_4300c_1_canary_git_failure.py
  stays green unmodified. The reserved inputs still come only from the stage_canaries
  entry of the commit_guardian.json beside the running canary (BO-4300c-1-ii), never
  hard-coded. Exit 1 with the marker stays the only "fired" signal (worktree_canaries._hook_rejected).'
- 'The canary stays stdlib-only, well under the 400-line .py limit (100 lines today)
  and within the commit-guardian complexity limits. check-exception-handling IO-001
  stays satisfied: every git call and every file read sits inside the fail-closed
  handling.'
- 'PROOF RULES (BO-4300c-1-iii, BO-4300f-4): every test runs the DEPLOYED canary,
  `ensure_deployed_layout() / ".leafcutter/scripts/commit_guardian/precommit_canary.py"`
  with the deployed commit_guardian.json beside it, resolved through the shared locator
  unit_tests/build_orchestration/_workspace_maker_fixtures.py. It runs as a separate
  process (sys.executable plus the absolute path), never as an import of the module,
  and never from the templates/ or scripts/ copy. No mock of git and no grep of source
  (CLAUDE.md "Gate / Workflow ACs -- Verify Behaviorally, Not by Grep").'
- 'Tests must not spawn the package''s own scripts/build.py (CLAUDE.md "Tests must
  not spawn their own build.py"): the deployed copy comes from ensure_deployed_layout()''s
  one session-cached build.'
- 'ISOLATION: all temporary projects live under the test''s temp directory. Every
  fixture git call and every canary run uses an isolated global and system git config
  (reuse _workspace_maker_builders._isolated_git_env: HOME/USERPROFILE, GIT_CONFIG_GLOBAL,
  GIT_CONFIG_NOSYSTEM). Each starts from an environment with the inherited repository-locating
  variables removed (GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE, GIT_COMMON_DIR, GIT_OBJECT_DIRECTORY,
  GIT_ALTERNATE_OBJECT_DIRECTORIES, GIT_PREFIX), so a suite run from inside a git
  hook can neither read nor write the developer''s repository. A test that needs a
  non-repository sets GIT_DIR to an empty folder under the temp dir and GIT_CEILING_DIRECTORIES
  to the temp dir''s parent. Afterwards the developer''s own repository''s branches,
  registered worktrees and local git config are unchanged (BO-4300f-4-i, F14, KI-TQ-012).'
- 'Git spelling (KI-CG-20260925-commit-delegation-hook-misses-git-dash-c): every commit,
  merge and canary run in the tests sets git''s working directory through cwd=, never
  `git -C <path> commit` or `git -C <path> merge`.'
- 'REPLACED TEST: unit_tests/build_orchestration/test_bo_4300c_1_real_install.py::test_registered_canary_hooks_are_inert_for_ordinary_input
  is removed. It runs outside any repository, where git falls into --no-index mode
  and lists nothing, so it cannot fail. Its replacement is test_registered_canaries_are_inert_for_ordinary_commit_and_merge_in_a_real_repo.
  The removal lands in a test-only change (the red-baseline commit) and is never staged
  together with the precommit_canary.py change, because check-contract-shrinking refuses
  a test deletion staged with production code.'
- 'MUTANT ARMS CHECK THEMSELVES: the reject-everything mutant is a temp-dir copy of
  the deployed canary, with the deployed commit_guardian.json beside it, changed only
  so every listed path counts as reserved. It never edits templates/, scripts/ or
  the shared deployed layout. The test first asserts that the mutant rejects the ordinary
  input with the marker, so a mutation that did not apply, or a mutant that cannot
  start, fails loudly. Only then does it assert that the inert proof fails for the
  mutant.'
- 'FILE SIZE: each new test module stays under the 400-line .py limit, which check-file-size
  applies to unit_tests/. Scenarios 1-4 go in test_bo_4300c_6.py; scenario 5 and its
  mutant arm go in test_bo_4300c_6_real_install.py. Shared repo-building helpers,
  if any, go in a leading-underscore helper module (for example _bo_4300c_6_fixtures.py)
  instead of growing test_bo_4300c_1_real_install.py (188 lines) or _workspace_maker_fixtures.py
  (340 lines).'
```

## Agent Contracts

### documentation-expert

Existing docs to update / cross-link:

- docs/analysis/2026-09-25-worktree-failure-modes.md (relationship: describes | status: exists)
- docs/architecture/components/worktree-manager.md (relationship: describes | status: exists | relevance: Component page for the one maker, including the ensure-time canary that proves each declared stage fires.)
- docs/architecture/adrs/ADR-031-worktree-quality-gate-guard.md (relationship: constrains | status: exists | relevance: Canary-execution probe model (section 1) -- a protection counts only when a real operation is rejected.)
- docs/acceptance-criteria/build-orchestration/BO-1700-worktree-quality-gate-guard/BO-1700b-1.yaml (relationship: constrains | status: exists | relevance: Fail closed on any non-positive check outcome and surface the raw error text -- the rule the git-failure scenarios apply to the canary itself.)
- docs/known-issues/commit-guardian/open-low-ki-cg-20260901-precommit-probe-reports-false-where-it-means-could-not-look.md (relationship: related | status: exists | relevance: Same defect class -- "could not look" reported as a definite negative.)
- docs/testing/test-angles.md (relationship: describes | status: exists | relevance: Angle taxonomy for this record's test_spec.)
- docs/architecture/components/worktree-quality-gate-guard.md (relationship: describes | status: exists | relevance: Key invariants 1 (fail closed, never fail open) and 2 (execution proof via the canary) -- the two rules this record applies to the stage canary itself.)
- docs/architecture/components/commit-guardian.md (relationship: describes | status: exists | relevance: Parent pre-commit layer; precommit_canary.py ships from templates/scripts/commit_guardian/.)
- docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-1-ii.yaml (relationship: constrains | status: exists | relevance: Owns the stage_canaries declaration and the precommit-canary-<stage> registrations this canary reads, and the BO-4300 proof rules its tests reuse.)
- docs/known-issues/commit-guardian/open-high-ki-cg-20260925-commit-delegation-hook-misses-git-dash-c.md (relationship: constrains | status: exists | relevance: Why every commit and merge in these tests sets git's working directory, never `git -C`.)
- docs/how-to/writing-a-tdd-ticket.md (relationship: describes | status: exists | relevance: check-contract-shrinking refuses a test deletion staged with production code; the replaced inert test is removed in a test-only change.)

- [ ] AC-1: sequence-diagram | docs/analysis/2026-09-25-worktree-failure-modes.md | in both cases it fails, which stops the commit, and its report names the

### Delivers To

- **Agent:** python-coder
- **Contract:** The stage canary's verdict, as read by the workspace maker's readiness canaries (templates/scripts/worktree_canaries.py, BO-4300c-1-ii), per run of `precommit_canary.py --stage <stage>`: exit 1 with `PRECOMMIT_CANARY_REJECTED (<stage>)` on stdout = the stage fired; exit 0 with no marker = input not reserved, or nothing merged (ORIG_HEAD absent); exit 1 with no marker and one stderr line `precommit_canary: git <args> exited <rc>: <git stderr>` = git ran and failed, which the maker counts as not fired (HOOKS_INACTIVE). The maker needs no change: its own canary flow sees git exit 0 throughout. Carrying the git report into the HOOKS_INACTIVE answer is out of scope (see notes).

### Expects From

- **AC:** BO-4300c-1-ii
- **Contract:** stage_canaries in the commit_guardian.json beside the running canary: pre-commit.path and post-merge.path (repo-relative POSIX path strings), commit-msg.message (one line, no newline). The generated .pre-commit-config.yaml registers `python <output_root>/scripts/commit_guardian/precommit_canary.py --stage <stage>` for each stage, pass_filenames false for pre-commit and post-merge, true for commit-msg (the message file path is the last argument).
- **AC:** BO-4300f-4
- **Contract:** unit_tests/build_orchestration/_workspace_maker_fixtures.py: ensure_deployed_layout() -> Path of the session-cached deployed layout (deployed canary at .leafcutter/scripts/commit_guardian/precommit_canary.py, commit_guardian.json beside it, generated .pre-commit-config.yaml at the layout root); _workspace_maker_builders._isolated_git_env() -> env dict with isolated HOME/USERPROFILE, GIT_CONFIG_GLOBAL and GIT_CONFIG_NOSYSTEM.

## Sign-offs

- [x] architect-review — 2026-10-10 12:00
- [x] test-writer — 2026-10-10 14:00
- [x] python-coder — 2026-10-12 10:00
- [x] test-runner — 2026-10-12 11:00
- [x] pr-reviewer — 2026-10-12 12:00
- [x] ac-validator — 2026-10-12 13:00
- [x] ac-fulfillment-gate — 2026-10-12 09:45
- [x] commit — 2026-10-12 14:00

## Comments

### 2026-10-10 12:00 — architect-review (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  impact_classified: true
  research_agent_blast_radius:
    result: false
    reason: "Agent tool not available in this dispatch; classification made from the ticket's own scope notes."
    remediation: "None required; scope is explicit and confined to one production file."
Small: no always-large trigger (no migration, hypertable, API or ADR contract change). One production file (templates/scripts/commit_guardian/precommit_canary.py) in one component (commit_guardian/precommit_hooks); the other 5 touched files are tests and the AC yaml, so the >5 file count is test volume, not blast radius. Design concern: canary must fail closed with no marker on git failure, absence probe must not peel ORIG_HEAD, compare bytes not text. requires_adr stays false. No acceptance adjustments, no diagrams.

### 2026-10-10 14:00 — test-writer (status: ok)
feedback-id: fb_2026-10-10_3d7b0aca
completion_manifest:
  tests_written: true
  red_verified: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "deployed .pre-commit-config.yaml registered canary entries + real git (staged list, ORIG_HEAD, merge)"
    consuming_side: "deployed precommit_canary.py run as its own process in a real repo (test_bo_4300c_6_real_install.py)"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python <deployed>/.leafcutter/scripts/commit_guardian/precommit_canary.py --stage <pre-commit|commit-msg|post-merge> (CLI via subprocess, plus the real .git/hooks/commit-msg shim)"
red_baseline:
  - test_name: test_commit_time_canary_fails_closed_on_corrupt_index_with_git_report
    file: unit_tests/build_orchestration/test_bo_4300c_6.py
    kind: assertion
    error: "AssertionError: 0 == 0 (canary exits 0 on git failure)"
  - test_name: test_commit_time_canary_fails_closed_when_git_dir_is_not_a_repository
    file: unit_tests/build_orchestration/test_bo_4300c_6.py
    kind: assertion
    error: "AssertionError: 0 == 0"
  - test_name: test_after_merge_canary_fails_closed_when_git_dir_is_not_a_repository
    file: unit_tests/build_orchestration/test_bo_4300c_6.py
    kind: assertion
    error: "AssertionError: 0 == 0"
  - test_name: test_after_merge_canary_fails_closed_on_dangling_orig_head
    file: unit_tests/build_orchestration/test_bo_4300c_6.py
    kind: assertion
    error: "AssertionError: 0 == 0"
  - test_name: test_commit_msg_canary_lets_non_utf8_and_empty_messages_through
    file: unit_tests/build_orchestration/test_bo_4300c_6.py
    kind: assertion
    error: "AssertionError: 1 != 0 : UnicodeDecodeError: 'utf-8' codec can't decode byte 0xf6"
  - test_name: test_commit_msg_canary_rejects_reserved_first_line_with_lf_or_crlf
    file: unit_tests/build_orchestration/test_bo_4300c_6.py
    kind: assertion
    error: "AssertionError: False != True : UnicodeDecodeError (non_utf8_body case)"
  - test_name: test_ordinary_non_ascii_and_non_utf8_paths_never_crash_the_canary
    file: unit_tests/build_orchestration/test_bo_4300c_6.py
    kind: assertion
    error: "AssertionError: 1 != 0 : UnicodeDecodeError: 'charmap' codec can't decode byte 0x81"
  - test_name: test_bo_4300c_6_reachable_from_entry_point
    file: unit_tests/build_orchestration/test_bo_4300c_6.py
    kind: assertion
    error: "AssertionError: 0 != 1"
Eight tests are red against the current canary. test_after_merge_canary_passes_when_nothing_was_merged and the three real_install tests pass today by design (regression guards: inert proof, reserved inputs, reject-everything mutant); the mutant arm is self-checking. The replaced test test_registered_canary_hooks_are_inert_for_ordinary_input was removed from test_bo_4300c_1_real_install.py in this test-only change; commit it apart from precommit_canary.py (check-contract-shrinking). Run with unittest: this repo's pytest config reports expected failures as xfailed.

## Escalation

Branch: none
Reason: one production file in one component; no always-large trigger fired.

### 2026-10-10 16:00 — python-coder (status: handoff)

feedback-id: (submit-failed)

handoff_target: test-writer
Implemented templates/scripts/commit_guardian/precommit_canary.py (fail-closed git report, git-dir preflight, ORIG_HEAD absence probe unpeeled, byte comparison for names and messages). 11 of 12 tests in test_bo_4300c_6.py / test_bo_4300c_6_real_install.py are green; test_bo_4300c_1_real_install and the canary git-failure tests green.
Remaining red: test_commit_msg_canary_lets_non_utf8_and_empty_messages_through, final assertion `b'Größe' in git cat-file commit HEAD`. The commit succeeds through the canary (all prior assertions pass), but git itself re-encodes the message to UTF-8 (stored bytes GrÃ¶Ãe), so the assertion is a test defect independent of the canary (classification: test_drift). test-writer: assert the stored message is either encoding, or set i18n.commitEncoding=cp1252 for that repo.
Pre-existing unrelated failure: unit_tests/commit_guardian/test_precommit_canary.py::test_hook_manifest_stages (registry stages) fails on the unmodified registry.
red_baseline_results: 7 of 8 red tests now green; the commit-msg test above still red.

### 2026-10-12 10:00 — python-coder (status: ok)

feedback-id: (submit-failed)
Re-verified after test-writer fix: all 17 tests in test_bo_4300c_6, test_bo_4300c_6_real_install, test_bo_4300c_1_real_install, test_bo_4300c_1_canary_git_failure pass (unittest, 56s). precommit_canary.py is 137 lines.
red_baseline_results:
  - all 8 red_baseline tests: green

### 2026-10-12 11:00 — test-runner (status: ok)

feedback-id: (submit-failed)
Suite: build-orchestration (pytest, AC_ENFORCE_STRICT=1). test_bo_4300c_6, test_bo_4300c_6_real_install, test_bo_4300c_1_real_install: 16 passed on first run plus 1 teardown error in test_bo_4300c_1_real_install (DeveloperRepoChangedError: refs/scratch/e1-merge-resolution-1 appeared in the shared repo, a concurrent-session artifact, not this change). Rerun of test_bo_4300c_1_real_install alone: 3 passed, 7 subtests passed. No failures attributable to the ticket.

completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true

### 2026-10-12 12:00 — pr-reviewer (status: ok)

feedback-id: (submit-failed)
Reviewed working diff (precommit_canary.py, test_bo_4300c_1_real_install.py, new BO-4300c-6 tests). No high-confidence findings; contract mismatches none. Medium: none. Suppressed: 0 low, 0 dropped. Removed test_registered_canary_hooks_are_inert_for_ordinary_input is superseded by test_bo_4300c_6_real_install inert proof; BO-4300c-1-ii remains covered elsewhere. 3 of 4 modules green on rerun; the one teardown error was env-induced (untracked-source guard / shared-repo artifact), not the change.

## Escalation

Branch: none
Reason: not escalated: medium count was 0 (threshold > 3)

### 2026-10-12 13:00 — ac-validator (status: ok)

feedback-id: fb_2026-10-12_a2e1d6a3
completion_manifest:
  all_acs_covered: true
  store_alignment_clean: true
All 11 ACs covered (store alignment script rc=0; no delivers_to/expects_from gap). Evidence:
AC-1/2/3 covered: impl templates/scripts/commit_guardian/precommit_canary.py (_git wrapper, fail-closed one-line report); test test_commit_time_canary_fails_closed_on_corrupt_index_with_git_report and test_commit_time_canary_fails_closed_when_git_dir_is_not_a_repository (unit_tests/build_orchestration/test_bo_4300c_6.py:48,59).
AC-4 covered: impl precommit_canary.py post-merge ORIG_HEAD absence probe; test test_after_merge_canary_passes_when_nothing_was_merged (test_bo_4300c_6.py:71).
AC-5/6 covered: impl same file, post-merge git failure path; test test_after_merge_canary_fails_closed_when_git_dir_is_not_a_repository and ..._on_dangling_orig_head (test_bo_4300c_6.py:86,96).
AC-7 covered: impl byte comparison of messages/names; test test_commit_msg_canary_lets_non_utf8_and_empty_messages_through (test_bo_4300c_6.py:113).
AC-8 covered: test test_commit_msg_canary_rejects_reserved_first_line_with_lf_or_crlf (test_bo_4300c_6.py:136).
AC-9 covered: test test_registered_canaries_are_inert_for_ordinary_commit_and_merge_in_a_real_repo (test_bo_4300c_6_real_install.py:68).
AC-10 covered: test test_registered_canaries_reject_reserved_inputs_in_the_same_repo (test_bo_4300c_6_real_install.py:75).
AC-11 covered: test test_reject_everything_canary_fails_the_inert_proof (test_bo_4300c_6_real_install.py:93).
Note: the ticket has no ## AC Coverage table, so none was filled; the new test files and fixtures are untracked and must be git-added before commit.

### 2026-10-12 09:45 — ac-fulfillment-gate (status: ok)

feedback-id: fb_2026-10-12_8a835577
All 1 L2 AC verified (BO-4300c-6). 3 auto-fixes applied to docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-6.yaml:
- implemented_by: appended templates/scripts/commit_guardian/precommit_canary.py (in files_touched and in the diff).
- covered_by: appended unit_tests/build_orchestration/test_bo_4300c_6.py and test_bo_4300c_6_real_install.py (both carry # covers: BO-4300c-6 tags).
- work_status: mark_ac_done.py output: 'marked BO-4300c-6 work_status=done' (exit 0).
check_ac_schema.py exit 0 after the edit. Commit phase may proceed; the new test files and fixtures are untracked and must be git-added.

### 2026-10-12 14:00 — commit (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Two commits: fc95a763f (tests, incl. removal of the vacuous inert test, test-only per check-contract-shrinking) and 29a7bf203 (precommit_canary.py + BO-4300c-6.yaml). Notes: check-build-drift needed build.py re-run per template state; check-contract-shrinking crashes on cp1252 without PYTHONUTF8=1 (set it, no hook bypass). Pre-existing staged BO-4300d files and ticket 07 were left staged and uncommitted (not part of this ticket).
