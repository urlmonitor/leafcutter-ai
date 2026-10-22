---
title: "The workspace maker never waits for input"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300c-2
  - BO-4300a-1
  - BO-4300e-2
  - BO-4300f-3
  l3: []
status: todo
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
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  commit: needed
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
- [ ] AC-1: BO-4300c-2 ("never reads stdin and never prompts"). The deployed maker is started with
  `stdin=PIPE` held open, and the project's origin is `https://127.0.0.1:9/x.git`, a hub that needs
  credentials or network. `ensure --kind scratch --slug np` prints exactly one JSON answer with code
  `FETCH_FAILED` and exits 2 within 60 s, without anything being written to its stdin.
- [ ] AC-2: BO-4300a-1 IT13 / BO-4300e-2 / BO-4300f-3 IT5. Every child process the maker starts is started
  with stdin closed. A static test over the deployed `worktree*.py` and `workspace_root.py` finds no
  `subprocess.run`/`Popen` call without `stdin=subprocess.DEVNULL`, and finds that the git environment
  carries `GIT_TERMINAL_PROMPT=0`.
- [ ] AC-3: ADR-018 A1.2 / BO-4300c-2. A caller's own `GIT_SSH_COMMAND` reaches git unchanged, and
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
```

## Sign-offs
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
