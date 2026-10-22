---
title: "The workspace maker never waits for input"
ac_coverage: 3/3
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300c-2
  - BO-4300a-1
  - BO-4300e-2
  - BO-4300f-3
  l3: []
status: done
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-22'
last_updated: '2026-10-22'
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: low
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - bo4300-hardening
  - M3
  - N5
files_touched:
  - templates/scripts/worktree_git.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_canaries.py
  - templates/scripts/worktree_log_root.py
  - templates/scripts/worktree_identity.py
  - unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  ac-validator: signed_off
  ac-fulfillment-gate: signed_off
  commit: signed_off
---

# 01: The workspace maker never waits for input

## Actor / Goal
A workflow or agent runs the maker unattended. It must get exactly one JSON answer back within the timeout,
including when the hub needs credentials. The maker must never block on a terminal prompt or on stdin that
the caller happens to hold open.

## Context
- **Defect M3 (HIGH), confirmed on main 2026-10-22:** no file in `templates/scripts/worktree*.py` or
  `workspace_root.py` passes `stdin=subprocess.DEVNULL` or sets `GIT_TERMINAL_PROMPT`. Every child process
  inherits the caller's stdin, and git may prompt for credentials.
- **ACs violated:**
  - BO-4300c-2 it_requirement: "The maker never reads stdin and never prompts".
  - The same clause in BO-4300a-1 IT13, BO-4300e-2 (criteria and IT0/IT2) and BO-4300f-3 IT5.
  - ADR-018 Amendment 1 A1.2: the maker MUST NOT read stdin or prompt.
- **The five child-process sites**, verified against the current tree. The handover's file names are
  correct; the line numbers are current.
  1. `templates/scripts/worktree_git.py:74`: `run_git`, the single git boundary for nearly every maker call.
     `worktree_readiness._git`, `worktree_remove`, `worktree_migrate` and `worktree_ticket_record` all go
     through it.
  2. `templates/scripts/workspace_root.py:53`: `_git`, which project resolution uses.
  3. `templates/scripts/worktree_identity.py:246`: `_show_bytes`, which runs `git show <ref>:<path>`. This
     ticket edits ONLY this function in this file; ticket 06 owns the rest of the file in wave 2.
  4. `templates/scripts/worktree_canaries.py:93`: `install_shims`, which runs the install's
     `install_pre_commit_shims.py`.
  5. `templates/scripts/worktree_log_root.py:58`: `_run_build`, the install build. It is called from
     `worktree_readiness.run_install_build`, which passes `env={**os.environ, ...}` (`worktree_readiness.py:66-71`).
     Close stdin inside `_run_build` itself, so that `worktree_readiness.py` (ticket 07) is not touched.
- No other `subprocess` call exists in the maker files. `worktree_remove.py` reads processes through psutil
  only.
- **Port source:** v1 commit 3cbfacba0, `workspace_core.run`.

## Scope
1. Pass `stdin=subprocess.DEVNULL` at all five sites.
2. Run git (sites 1-3) with an environment of
   `{**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}`.
   - Add `GIT_SSH_COMMAND="ssh -o BatchMode=yes"` ONLY when the caller set neither `GIT_SSH_COMMAND` nor
     `GIT_SSH`. Never override a user's own SSH command.
   - Build the environment in one place: a helper in `worktree_git.py`. `workspace_root.py` must stay
     importable on its own (BO-4300b-1), so if it cannot import `worktree_git`, give it a local copy with
     the same keys and a comment naming the canonical helper.
3. Sites 4 and 5 (Python children) get `stdin=DEVNULL` and the same no-prompt git variables, because they
   run git in turn.
4. Make no change to answer shapes, codes or messages; ticket 05 does those.

## Acceptance Criteria
- [x] AC-1: BO-4300c-2 ("never reads stdin and never prompts"). The deployed maker is started with
  `stdin=PIPE` held open, and the project's origin is `https://127.0.0.1:9/x.git`, a hub that needs
  credentials or network. `ensure --kind scratch --slug np` prints exactly one JSON answer with code
  `FETCH_FAILED` and exits 2 within 60 s, without anything being written to its stdin.
- [x] AC-2: BO-4300a-1 IT13 / BO-4300e-2 / BO-4300f-3 IT5. Every child process the maker starts is started
  with stdin closed. A static test over the deployed `worktree*.py` and `workspace_root.py` finds no
  `subprocess.run`/`Popen` call without `stdin=subprocess.DEVNULL`, and finds that the git environment
  carries `GIT_TERMINAL_PROMPT=0`.
- [x] AC-3: ADR-018 A1.2 / BO-4300c-2. A caller's own `GIT_SSH_COMMAND` reaches git unchanged, and
  `BatchMode=yes` is added only when no SSH command is set (asserted through the env-builder helper).

## Test Requirements

```yaml
tests:
- name: test_maker_with_open_stdin_and_credential_hub_answers_once_without_prompting
  file: unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
  covers:
  - BO-4300c-2
  - BO-4300a-1
  asserts: >-
    make_project(tmp) and then `git remote set-url origin https://127.0.0.1:9/x.git` in the project. Start
    the DEPLOYED maker (deployed_maker_path()) with subprocess.Popen(stdin=PIPE) held open and the
    _isolated_git_env() environment, running ensure --kind scratch --slug np. Within 60 s stdout is one
    JSON object, code FETCH_FAILED, exit 2. The test spawns the maker itself (not run_maker, which ticket
    03 changes to stdin=DEVNULL) and never spawns scripts/build.py.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_every_maker_child_process_closes_stdin
  file: unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
  covers:
  - BO-4300c-2
  - BO-4300e-2
  - BO-4300f-3
  asserts: >-
    An AST walk of the deployed worktree*.py and workspace_root.py (resolved beside deployed_maker_path())
    finds every subprocess.run/Popen call passes stdin=subprocess.DEVNULL.
  framework: unittest
  type: behavioral
- name: test_git_env_disables_prompts_and_keeps_user_ssh_command
  file: unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
  covers:
  - BO-4300c-2
  asserts: >-
    The worktree_git env helper returns GIT_TERMINAL_PROMPT=0 and GCM_INTERACTIVE=never. It adds
    BatchMode=yes only when neither GIT_SSH_COMMAND nor GIT_SSH is set, and passes a caller's
    GIT_SSH_COMMAND through byte-identical.
  framework: unittest
  type: behavioral
- name: test_core_ssh_command_in_git_config_suppresses_batchmode_in_both_builders
  file: unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
  covers:
  - BO-4300c-2
  asserts: >-
    Guard test. With core.sshCommand set in an isolated GIT_CONFIG_GLOBAL (GIT_CONFIG_NOSYSTEM=1,
    GIT_SSH and GIT_SSH_COMMAND unset), both worktree_git.git_env() and workspace_root._git_env() leave
    GIT_SSH_COMMAND unset; with an empty global config both add `ssh -o BatchMode=yes`.
    ssh_command_configured.cache_clear() is called before each builder.
  framework: unittest
  type: behavioral
  angle: failure
- name: test_the_two_git_env_copies_agree_on_prompt_and_ssh_keys
  file: unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
  covers:
  - BO-4300c-2
  asserts: >-
    Guard test (drift guard). Under the same environment workspace_root._git_env() and
    worktree_git.git_env() return identical GIT_TERMINAL_PROMPT, GCM_INTERACTIVE and GIT_SSH_COMMAND,
    for both an empty and a core.sshCommand-bearing global config.
  framework: unittest
  type: behavioral
  angle: seam
```

## Sign-offs
- [x] test-writer — 2026-10-22 12:00
- [x] python-coder — 2026-10-22 13:00
- [x] pr-reviewer — 2026-10-22 14:00
- [x] ac-validator — 2026-10-22 16:00
- [x] ac-fulfillment-gate — 2026-10-22 17:00
- [x] commit — 2026-10-22 18:00

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-10-22 12:00 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_written: true
  tests_red_for_right_reason: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "deployed worktree_git.git_env() and the five subprocess call sites"
    consuming_side: "git child processes started by the deployed maker (stdin closed, no-prompt env), proven end-to-end by the held-open-stdin maker run"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python <deployed>/worktree.py ensure --kind scratch --slug np (CLI via subprocess.Popen, stdin=PIPE)"
red_baseline:
  - test_name: test_every_maker_child_process_closes_stdin
    file: unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
    kind: assertion
    error: "AssertionError: subprocess calls without stdin=subprocess.DEVNULL: ['worktree_canaries.py:93 in install_shims', 'worktree_git.py:74 in run_git', 'worktree_identity.py:246 in _show_bytes', 'worktree_log_root.py:58 in _run_build', 'workspace_root.py:53 in _git']"
  - test_name: test_git_sites_carry_the_no_prompt_environment
    file: unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
    kind: assertion
    error: "AssertionError: Lists differ: ['worktree_canaries.py: no GIT_TERMINAL_PROMPT / git_env', 'worktree_canaries.py:93 in install_shims: no env=', ... 10 entries]"
  - test_name: test_git_env_disables_prompts_and_adds_batchmode_when_no_ssh_command
    file: unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
    kind: absence
    error: "AttributeError: module 'worktree_git' has no attribute 'git_env'"
  - test_name: test_git_env_keeps_user_ssh_command_byte_identical
    file: unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
    kind: absence
    error: "AttributeError: module 'worktree_git' has no attribute 'git_env'"
  - test_name: test_git_env_adds_no_batchmode_when_git_ssh_is_set
    file: unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
    kind: absence
    error: "AttributeError: module 'worktree_git' has no attribute 'git_env'"
Wrote unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py (6 tests; 5 red under AC_ENFORCE_STRICT=1). The helper name `worktree_git.git_env()` (no args) is fixed by these tests. test_maker_with_open_stdin_and_credential_hub_answers_once_without_prompting PASSES today (connection refused on 127.0.0.1:9 fails before any prompt) so it is a regression guard, not a red; it cannot discriminate prompting without a real credential-challenging server. Three Questions: Q1 a fix adding stdin=DEVNULL but no env= still fails test_git_sites_carry_the_no_prompt_environment and the git_env tests (reasoned); Q2 the AST tests fail on the current tree (observed); Q3 n/a, no control row beyond the GIT_SSH and GIT_SSH_COMMAND cases.

### 2026-10-22 13:00 — python-coder (status: ok)
feedback-id: (not-submitted)
Added worktree_git.no_prompt_env(base=None) and git_env() (no args); every child-process site now passes stdin=subprocess.DEVNULL and an env built from them: worktree_git.run_git, worktree_canaries.install_shims, worktree_identity._show_bytes, worktree_log_root._run_build (strips caller stdin/env kwargs, keeps caller env values, forces prompt vars), workspace_root._git (local _git_env mirror: workspace_root is the leaf resolver loaded by worktree_layout and stays free of worktree_git; the test also demands the GIT_TERMINAL_PROMPT literal in that file). check-file-size and check-complexity pass. Ran with AC_ENFORCE_STRICT=1: this test file plus test_bo_4300c_2, c_1_canary_git_failure, c_3, c_6, a_2 -> 21 passed.
red_baseline_results:
  - test_name: test_every_maker_child_process_closes_stdin
    result: green
  - test_name: test_git_sites_carry_the_no_prompt_environment
    result: green
  - test_name: test_git_env_disables_prompts_and_adds_batchmode_when_no_ssh_command
    result: green
  - test_name: test_git_env_keeps_user_ssh_command_byte_identical
    result: green
  - test_name: test_git_env_adds_no_batchmode_when_git_ssh_is_set
    result: green

### 2026-10-22 14:00 — pr-reviewer (status: ok)
feedback-id: (not-submitted)
No high-confidence findings. All five child-process sites close stdin and carry the no-prompt env. _run_build keeps the caller env (worktree_readiness passes {**os.environ, LEAFCUTTER_SHIM_STRATEGY}), so PATH/venv are preserved. The _git_env duplicate in workspace_root.py is justified (leaf resolver) and documented; no test pins the two copies together (medium). BatchMode is added only when no GIT_SSH_COMMAND/GIT_SSH; ssh-agent and passphrase-less keys are unaffected, but a passphrase-protected key without an agent now fails fast instead of prompting (intended). No os.system, shell=True, input() or sys.stdin in the maker files. Medium: core.sshCommand in git config is overridden by GIT_SSH_COMMAND env (git precedence), so a user relying on core.sshCommand loses it; Low: `from collections.abc import Mapping` is out of import order in worktree_git.py.

### 2026-10-22 14:00 — python-coder (status: handoff)
feedback-id: (submit-failed)
Rework for pr-reviewer M-2 and Low. M-2: new `workspace_root.ssh_command_configured()` (cached `git config --get core.sshCommand`, stdin=DEVNULL, exit 1 = unset, launch failure logged and treated as unset); both `workspace_root._git_env` and `worktree_git.no_prompt_env` add BatchMode only when GIT_SSH_COMMAND, GIT_SSH and core.sshCommand are all absent (`worktree_git` imports `workspace_root`; no cycle). Low: `collections.abc` import order fixed. Manually verified: global config with sshCommand -> no GIT_SSH_COMMAND from either builder; empty config -> BatchMode added. check-file-size and ruff I/F pass.
Not done (python-coder may not write tests; handoff_target: test-writer): (a) M-2 test: core.sshCommand set in the isolated global config (GIT_CONFIG_GLOBAL) -> `git_env()` adds no GIT_SSH_COMMAND; (b) M-1 test: `workspace_root._git_env()` and `worktree_git.git_env()` return identical prompt keys/values under the same environment. Externalise any table >3 rows to tests/fixtures.

### 2026-10-22 15:00 — test-writer (status: ok)
feedback-id: (not-submitted)
Added two guard tests to unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py (both listed in Test Requirements). Both run the DEPLOYED worktree_git/workspace_root in a fresh subprocess with an isolated GIT_CONFIG_GLOBAL, GIT_CONFIG_NOSYSTEM=1 and GIT_SSH/GIT_SSH_COMMAND unset; the child calls ssh_command_configured.cache_clear() before each builder, so cases cannot leak (a tearDown clear would be moot in a fresh process).
- guard: test_core_ssh_command_in_git_config_suppresses_batchmode_in_both_builders (angle: failure) - core.sshCommand set -> neither builder sets GIT_SSH_COMMAND; empty config -> both add `ssh -o BatchMode=yes`.
- guard: test_the_two_git_env_copies_agree_on_prompt_and_ssh_keys (angle: seam) - identical GIT_TERMINAL_PROMPT / GCM_INTERACTIVE / GIT_SSH_COMMAND from both copies, empty and configured cases.
Run (AC_ENFORCE_STRICT=1, pytest, file only): both green (8 passed, 1 error). The one error is the session-teardown DeveloperRepoChangedError from the shared repo's branch hardening/h09 moving during the 7-minute run (another session), not a test failure; the second guard's own call phase passed.
Wrong version check (observed): copy of templates/scripts with the `not ssh_command_configured()` clause removed from both builders, same env -> both return `ssh -o BatchMode=yes` with core.sshCommand set, so guard 1 (assertNotIn) goes red. A copy that drops the clause from only one builder makes the two copies differ in the configured case, so guard 2 goes red (reasoned).
Vacuity: exact-value assertions, control case (empty config) present in both tests, new input (core.sshCommand) distinct from the old; collaborator call count not applicable (pure env builders).
These are guard tests over already-written code, so there is no red_baseline entry (no new red).
File is git-added and ast.parse-clean; no commit made.

### 2026-10-22 16:00 — ac-validator (status: ok)
feedback-id: (submit-failed)
All 3 ACs covered. Store alignment script exit 0. No delivers_to/expects_from links.
AC-1 covered:
  implementation: templates/scripts/worktree_git.py run_git (stdin=subprocess.DEVNULL, env=git_env()); workspace_root.py _git; worktree_identity.py _show_bytes; worktree_canaries.py install_shims; worktree_log_root.py _run_build
  test: test_maker_with_open_stdin_and_credential_hub_answers_once_without_prompting (unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py:113)
AC-2 covered:
  implementation: same five sites pass stdin=subprocess.DEVNULL; worktree_git.no_prompt_env sets GIT_TERMINAL_PROMPT=0, GCM_INTERACTIVE=never
  test: test_every_maker_child_process_closes_stdin (:144), test_git_sites_carry_the_no_prompt_environment (:161)
AC-3 covered:
  implementation: worktree_git.no_prompt_env / git_env, workspace_root._git_env, workspace_root.ssh_command_configured (BatchMode only when GIT_SSH_COMMAND, GIT_SSH, core.sshCommand all absent)
  test: test_git_env_disables_prompts_and_adds_batchmode_when_no_ssh_command (:197), test_git_env_keeps_user_ssh_command_byte_identical (:206), test_git_env_adds_no_batchmode_when_git_ssh_is_set (:215), test_core_ssh_command_in_git_config_suppresses_batchmode_in_both_builders (:257), test_the_two_git_env_copies_agree_on_prompt_and_ssh_keys (:268)
Test runs were reported by the caller (local strict: 8 passed; Docker earlier run passed with 2 skips); not re-run by this agent.

### 2026-10-22 17:00 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
Resolved 4 L2 ACs via the shared resolver (list form l2/ac_path): BO-4300c-2, BO-4300a-1, BO-4300e-2, BO-4300f-3. All four are work_status in_progress ON PURPOSE (amendments owned by later tickets in this epic); mark_ac_done.py was NOT run and nothing was marked done.
Auto-fix (append-only): implemented_by gained the changed templates/scripts files (workspace_root, worktree_canaries, worktree_git, worktree_identity, worktree_log_root; only those not already listed) and covered_by gained unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py (carries `# covers:` tags for all four ACs). check_ac_schema.py exit 0 on all four files. AC YAML files staged with git add; no commit made.
Composite handling: none of the four is composite; no mark_ac_done run needed.

### 2026-10-22 18:00 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate: subject "fix(worktree): the workspace maker never waits for input"; 11 staged files.
