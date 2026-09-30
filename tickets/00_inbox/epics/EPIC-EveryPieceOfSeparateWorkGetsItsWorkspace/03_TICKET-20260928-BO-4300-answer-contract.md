---
title: 'The maker''s answer: one JSON object, one code table, paths usable from every shell'
status: todo
components:
- worktree_manager
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: contract_boundary
complexity: high
requires_adr: false
requires_diagram: false
source_ac: BO-4300c-2
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300c-2
  - BO-4300b-5
  l3:
  - BO-4300b-5-i
ac_coverage: 0/3
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- templates/scripts/worktree.py
- templates/scripts/worktree_git.py
- templates/scripts/worktree_admin.py
- templates/scripts/worktree_answer.py
- templates/scripts/worktree_paths.py
- scripts/build_phases_script_deploy_standalone.py
- scripts/build_deploy_manifest_helpers.py
- unit_tests/build_orchestration/test_bo_4300c_2.py
- unit_tests/build_orchestration/test_bo_4300b_5.py
- unit_tests/build_orchestration/test_bo_4300b_5_i.py
agents:
  ac-fulfillment-gate: needed
  ac-validator: needed
  architect-review: needed
  commit: needed
  documentation-expert: not_needed
  documentation-verifier: not_needed
  frontend-coder: not_needed
  pr-reviewer: needed
  pull-request: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
  user-surface-smoker: not_needed
---

# 03: The maker's answer: one JSON object, one code table, paths usable from every shell

## Actor / Goal

In order that every caller can parse the maker without guessing, we need the BO-4300c-2 result contract implemented in one place, so that stdout is exactly one JSON object with a status/code/exit mapping callers can rely on, and every path in it works from PowerShell, Git Bash and WSL.

## Context

BO-4300c-2 is the contract nearly every other BO-4300 AC expects from (a-2, a-5, b-5, c-3, c-4, and every maker answer). Ticket 01 fixed exit codes, the three-way status and part of the code enum inside `worktree_git.py` (`status_for_code`, `exit_code_for_answer`, `finalize_answer`); the rest is here.

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 3 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300c-2 | L2 | The maker's answer is one readable answer and nothing else | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |
| AC-2 | BO-4300b-5-i | L3 | A project under a folder whose name contains spaces gets a usable workspace | BO-4300b-5 | this ticket |
| AC-3 | BO-4300b-5 | L2 | The location handed back works from every shell on the machine | BO-4300c-2 | this ticket |

**Closure order.** Children are listed before their parents. Composite(s) `BO-4300b-5` close only after every child listed in their `covered_by` is done (`check-done-proof`); all of those children are in this ticket, so no parent here waits on another ticket. `source_ac` (`BO-4300c-2`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300c-2 (L2) -- The maker's answer is one readable answer and nothing else

```gherkin
Given each of these outcomes -- ready; refused because the location is
  occupied; refused because the shared project cannot be reached; refused
  because the install failed -- and underlying tools that print their own
  progress messages during the request, such as "HEAD is now at bc5d638 init",
When the channel that carries the workspace maker's answer is read,
Then it holds exactly one answer and nothing else, in every one of the four
  outcomes,
And the answer always states whether the result is ready or refused,
And the underlying tools' own messages are available separately and never
  appear in the answer,
And the way the maker's run ends signals the same outcome that the answer
  states.
```

### AC-2: BO-4300b-5-i (L3) -- A project under a folder whose name contains spaces gets a usable workspace

```gherkin
Given a project located under a folder named "My Projects",
When a workspace for "alpha" is requested,
Then it is answered ready,
And the location in the answer reproduces "My Projects" exactly,
And a version-control command run at that exact location succeeds.
```

### AC-3: BO-4300b-5 (L2) -- The location handed back works from every shell on the machine

```gherkin
Given a Windows machine with a Linux shell running on it that can reach the
  same project,
When a workspace for "alpha" is requested from a Windows shell,
Then the ready answer gives the workspace's location in a form usable from the
  Windows shell and in a form usable from the Linux shell, both naming the same
  folder,
And a request for "alpha" started from the Linux shell is answered with that
  same workspace, not a second one,
And version-control commands run inside the workspace succeed from both shells.
```

- [ ] AC-1: BO-4300c-2 -- The maker's answer is one readable answer and nothing else
- [ ] AC-2: BO-4300b-5-i -- A project under a folder whose name contains spaces gets a usable workspace
- [ ] AC-3: BO-4300b-5 -- The location handed back works from every shell on the machine

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_stdout_holds_exactly_one_json_object_in_each_outcome
  file: unit_tests/build_orchestration/test_bo_4300c_2.py
  covers:
  - BO-4300c-2
  asserts: For ok, OCCUPIED, FETCH_FAILED (unreachable hub) and BOOTSTRAP_FAILED, stdout parses as exactly
    one JSON object with nothing before or after.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_every_answer_states_its_status
  file: unit_tests/build_orchestration/test_bo_4300c_2.py
  covers:
  - BO-4300c-2
  asserts: Each of the four answers has status in {ok, refused, error} and a code.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_git_progress_messages_appear_on_stderr_not_stdout
  file: unit_tests/build_orchestration/test_bo_4300c_2.py
  covers:
  - BO-4300c-2
  asserts: Git's own lines (e.g. 'HEAD is now at ...', 'set up to track') appear on stderr and never in
    stdout.
  framework: unittest
  type: behavioral
  angle: seam
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_exit_code_matches_stated_status
  file: unit_tests/build_orchestration/test_bo_4300c_2.py
  covers:
  - BO-4300c-2
  asserts: Exit code is 0/2/1 for ok/refused/error respectively in each outcome.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_usage_error_still_emits_one_json_object
  file: unit_tests/build_orchestration/test_bo_4300c_2.py
  covers:
  - BO-4300c-2
  asserts: An unknown verb exits 64 with one JSON object (status error, code USAGE).
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_project_under_folder_with_spaces_is_answered_ok
  file: unit_tests/build_orchestration/test_bo_4300b_5_i.py
  covers:
  - BO-4300b-5-i
  asserts: A project under 'My Projects' gets an ok answer.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_answer_reproduces_the_spaced_folder_name_exactly
  file: unit_tests/build_orchestration/test_bo_4300b_5_i.py
  covers:
  - BO-4300b-5-i
  asserts: workspace_path contains 'My Projects' verbatim.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_git_command_at_the_exact_answered_location_succeeds
  file: unit_tests/build_orchestration/test_bo_4300b_5_i.py
  covers:
  - BO-4300b-5-i
  asserts: git -C <workspace_path> rev-parse succeeds.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_ready_answer_gives_native_and_posix_forms_of_the_same_folder
  file: unit_tests/build_orchestration/test_bo_4300b_5.py
  covers:
  - BO-4300b-5
  asserts: The two path fields name the same folder (each resolves to the same inode/volume path).
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_request_from_the_other_shell_returns_the_same_workspace
  file: unit_tests/build_orchestration/test_bo_4300b_5.py
  covers:
  - BO-4300b-5
  asserts: A second request for alpha using the other shell's spelling of --repo-root (and, where WSL
    exists, from a WSL process) is answered ok with the same workspace, and the landing place still holds
    one workspace.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_git_commands_succeed_inside_the_workspace_from_both_spellings
  file: unit_tests/build_orchestration/test_bo_4300b_5.py
  covers:
  - BO-4300b-5
  asserts: git -C with each spelling of the workspace path succeeds.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_ticket_03_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300c_2.py
  covers:
  - BO-4300c-2
  angle: reachability
  surface_invoked: python <install-root>/.leafcutter/scripts/worktree.py ensure|locate|verify|where ...
    (CLI via subprocess)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_paths.py
  - scripts/build_phases_script_deploy_standalone.py
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- OWN THE TABLE: move `status_for_code`, `exit_code_for_answer`, `finalize_answer` and the refused-code set out of `worktree_git.py` into `templates/scripts/worktree_answer.py`, and declare the COMPLETE code enum from BO-4300c-2's delivers_to contract (including NOT_FOUND, INCOMPLETE, OCCUPIED_LEGACY_WORKTREE, IN_PROGRESS, AMBIGUOUS_REPO, WORK_AT_RISK, HOOKS_INACTIVE, VERIFY_FAILED, UNSENT_WORK, ON_PROTECTED_BRANCH, TICKET_NOT_ON_BASE, and AMBIGUOUS_LINE added by the user's Q4 decision of 2026-09-28) so that tickets 04-08 and 12 never edit the table. In the failed run tickets 14, 43 and 04 each added a code to `_REFUSED_CODES` in parallel (collision).
- USER DECISIONS (2026-09-28) THAT CHANGE THE CONTRACT: Q4 adds the refusal code `AMBIGUOUS_LINE` (status refused, exit 2) with field `lines [branch]` -- more than one spelling of the same work identity already holds a line of work on the hub (behaviour delivered by ticket 06, BO-4300a-2). Q8 adds `discard_token` (string) on remove's `UNSENT_WORK` answer only -- never on ensure's `WORK_AT_RISK`, never on stderr, in the marker or in any file (behaviour delivered by ticket 08, BO-4300e-3). Both are compatible additions under the schema_version policy; this ticket declares them in the table and the field set so tickets 06 and 08 do not edit it.
- STDOUT DISCIPLINE: every child process (git, installers, the build) runs with stdout and stderr captured and forwarded to the maker's stderr; a usage error and an internal exception still print one JSON object (INTERNAL_ERROR, never a traceback on stdout); the maker never reads stdin and never prompts.
- FIELDS: `schema_version`, `workspace_path` canonical with `worktree_path` alias, `repo_root`/`repo_root_posix`, `workspace_path_posix`; the full `checks` dict names are BO-4300c-1's and land in ticket 05 (01 python-coder's disclosed scope boundary).
- PATHS (b-5, b-5-i): new `templates/scripts/worktree_paths.py`: native + POSIX alias for every emitted path (on Windows the WSL `/mnt/<drive>/...` form), `--repo-root`/`--path` accept Git Bash, PowerShell and WSL spellings; the marker stores no single-platform absolute path; a project under a folder with spaces works. The real two-shell arm runs where wsl.exe exists and is reported as not run otherwise.
- STARTING POINT: ticket 01's commit b7c48169 (current answer code). The failed run's `git show refs/wip/bo4300-attempt1 -- templates/scripts/worktree_git.py` has later `_REFUSED_CODES` edits; re-verify, do not trust.
- FILE-SIZE RATCHET: `templates/scripts/worktree.py` is at ~393 of 400 counted lines and `templates/scripts/worktree_git.py` near its limit (01 python-coder sign-off). Every addition therefore goes into the NEW module this ticket owns (see files_touched); the two core files are touched only to move code out and to wire the new module in. A new module needs its own NAMED deploy entry in `scripts/build_phases_script_deploy_standalone.py` and `scripts/build_deploy_manifest_helpers.py` (KI-TQ-004: no second tracked copy; the maker is deployed to `<install-root>/.leafcutter/scripts/<name>`, not `<install-root>/scripts/`, per 01 test-writer/python-coder).
- ANSWER TABLE: the status/code/exit table is owned by ticket 03 (BO-4300c-2 declares the full code enum). Do not add codes locally; if a code is missing from BO-4300c-2 it is a contract change, not a local edit.
- PROOF: tests run the DEPLOYED maker through ticket 02's locator (`unit_tests/build_orchestration/_workspace_maker_fixtures.py`), as a subprocess, against real temp repos with a real bare hub; no mock of git, no import of the maker module, never spawn `scripts/build.py`. Pin `newline="\n"` on fixture writes and isolate GIT_CONFIG_GLOBAL/GIT_CONFIG_NOSYSTEM (the CRLF drift found on 04 in the failed run). Use `AC_ENFORCE_STRICT=1` to see a genuine red baseline (the AC-enforcement plugin otherwise downgrades not-done-AC failures to xfail).
- HOOK HYGIENE (lessons from ticket 01): DECISION HISTORY entries need `HH:MM` and the `(#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/NN)` tail-tag on the entry's FIRST line; run `check_documentation.py` with NO `--file` flag (staged mode) before commit; run `check_doc_length.py` on every doc touched (300-line ratchet); stage every file in files_touched (01 shipped an ADR edit unstaged). Commits never spelled `git -C <path> commit`.
- SCOPE: the epic worktree is shared by every ticket. Edit only files_touched. If the fix needs another file, stop and get this ticket updated (CLAUDE.md TICKET MANDATE); the failed run stalled on exactly this (tickets 04, 14, 46, 59).

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300c-2**

- stdout is reserved for the one answer: every child process (git, submodule, package installers, the build) runs with its stdout and stderr captured and forwarded to the maker's stderr; the answer is a single JSON object (UTF-8, no BOM, one trailing newline allowed).
- Exit code always matches status (0 ok, 2 refused, 1 error, 64 usage); a usage error and an internal exception still produce one JSON object.
- The contract is versioned by schema_version; adding a field is compatible, renaming or removing one bumps it. workspace_path is the canonical key; worktree_path is kept as an alias for existing callers. The per-stage hook checks, hooks_stages_declared, inactive_stages and the two ticket fields are additions (compatible); hooks_canary_rejected keeps its name and now means "every declared stage fired". The AMBIGUOUS_LINE code with its lines field (Q4) and the discard_token field on remove's UNSENT_WORK answer (Q8) are additions too (compatible; user decisions 2026-09-28).
- discard_token is emitted ONLY on a remove answer with code UNSENT_WORK, never on ensure's WORK_AT_RISK or any other answer, and never written to stderr, the marker, a log or any file; the token alone is not an authorisation -- it is valid only on the remove request for the same workspace while its unsent set is unchanged (BO-4300e-3, BO-4300e-3-i).
- The ticket fields follow the same presence rule as workspace_path: present only on an ok answer, and only when the request named a ticket; their value is never the path the caller passed in (BO-4300a-1-ii).
- This record is the single authoritative statement of the result contract. Other records that need it (BO-4300a-5, callers' expects_from) point to it rather than restating it, so a field added here cannot be missed in a copy.

**BO-4300b-5-i**

- Paths are never split on whitespace or passed through a shell string; the answer reproduces the folder name exactly.

**BO-4300b-5**

- Every emitted path appears in native form and in a POSIX alias (workspace_path / workspace_path_posix, repo_root / repo_root_posix); on a Windows host the alias is the form a WSL shell can use (/mnt/<drive>/...), and --repo-root/--path accept Git Bash, PowerShell and WSL spellings of the same folder.
- The marker and every stored value hold no absolute path in only one platform's spelling, so a request from either shell recognises the same workspace (decision 1: clones embed no absolute path).
- The real two-shell arm runs where wsl.exe is available and is reported as not run otherwise; the spelling-equivalence arm (the same --repo-root given in each of the three spellings) runs everywhere.

## Agent Contracts

### python-coder

- [ ] AC-1: BO-4300c-2 -- The maker's answer is one readable answer and nothing else
- [ ] AC-2: BO-4300b-5-i -- A project under a folder whose name contains spaces gets a usable workspace
- [ ] AC-3: BO-4300b-5 -- The location handed back works from every shell on the machine

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300c-2 per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300b-5-i per `## Test Requirements`
- [ ] AC-3: red tests for BO-4300b-5 per `## Test Requirements`

**Delivers to:** python-coder (red baseline).

### Expects From

- **BO-4300c-2 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): The maker's verbs (CLI) whose answers this contract governs.
- **BO-4300b-5-i <- BO-4300b-5** (this ticket): Path fields in the answer.
- **BO-4300b-5 <- BO-4300c-2** (this ticket): workspace_path and workspace_path_posix fields.

### Delivers To

- **BO-4300c-2 -> python-coder**: Result contract. stdout carries exactly one JSON object for every verb and outcome; all child-process output (git, package installers, the build) goes to stderr. Exit 0 = status ok, 2 = refused, 1 = error, 64 = usage error (still one JSON object: status error, code USAGE). Common fields: schema_version (int), status ('ok'|'refused'|'error'), code (OK | NOT_FOUND | INCOMPLETE | OCCUPIED | OCCUPIED_LEGACY_WORKTREE | IN_PROGRESS | NO_REPO | AMBIGUOUS_REPO | NO_HUB | FETCH_FAILED | GIT_FAILED | NO_CONFIG | BOOTSTRAP_FAILED | BOOTSTRAP_DIRTIED_TRACKED | WORK_AT_RISK | HOOKS_INACTIVE | VERIFY_FAILED | UNSENT_WORK | PROCESS_HOLDS_FILES | ON_PROTECTED_BRANCH | TICKET_NOT_ON_BASE | AMBIGUOUS_LINE | USAGE | INTERNAL_ERROR), message (one sentence naming the cause), verb, repo_root and repo_root_posix, layout ('dev'|'consumer'), mechanism ('clone'), hub (the main checkout's origin URL). ensure/locate/verify ok answers add: kind, slug, branch (null for scratch), workspace_path (absolute, native spelling), workspace_path_posix, worktree_path (alias, always equal to workspace_path), base_ref ('origin/main'), base_commit (sha read back from the workspace), origin_main_commit (sha of origin/main at the fetch), base_matches_origin_main (bool), fetch ('ok'|'failed'|'skipped'), workspace_action ('created'|'re-readied'|'completed'|'located'), line_of_work ('new'|'resumed'|'existing'), created (bool), bootstrap {build_ok: bool, config_path: str, restored_tracked: [repo-relative path], env_copied: [name], failure_excerpt: str|null}, hooks_stages_declared [stage], checks {is_independent_repo, not_main_checkout, same_project, branch_matches, not_protected_branch, base_is_fresh, build_ok, tree_clean, precommit_config_present, hooks_pre_commit_fired, hooks_commit_msg_fired, hooks_post_merge_fired, hooks_canary_rejected (the conjunction of the three stage checks)}, each true|false|'n/a'. 'n/a' rule for the stage checks: kind scratch -> all three and the conjunction are 'n/a'; any other kind -> hooks_pre_commit_fired is never 'n/a', and the commit-msg / post-merge checks are 'n/a' only when the project does not declare that stage. An ensure/locate/verify ok answer to a request that named a ticket (--ticket) adds ticket_path_in_worktree (absolute, native spelling, inside workspace_path, verified to exist when the answer is emitted) and ticket_path_in_worktree_posix; both are ABSENT on every other answer. ticket_path_final and ticket_path_new are never emitted. On EVERY non-ok answer workspace_path, workspace_path_posix and worktree_path are ABSENT (not blank, not null); diagnostic paths travel under different names: inactive_stages [stage] (HOOKS_INACTIVE), ticket_path (the path as requested) and reason 'absent'|'differs' (TICKET_NOT_ON_BASE, status refused, exit 2), candidates [path] (AMBIGUOUS_REPO), searched_from (NO_REPO), occupant {path, kind: 'other-line'|'other-project'|'plain-folder'|'legacy-worktree', branch|null} (OCCUPIED*), remnant_path (INCOMPLETE), unsent {commits: [sha], files: [path]} (UNSENT_WORK, WORK_AT_RISK), holders [{pid, name}] (PROCESS_HOLDS_FILES), lines [branch] (AMBIGUOUS_LINE, status refused, exit 2: more than one spelling of the same identity holds a line of work on the hub, Q4 decided 2026-09-28, BO-4300a-2). A remove answer UNSENT_WORK also carries discard_token (string): the one-time token bound to that workspace and exactly the unsent set listed in the same answer (Q8 decided 2026-09-28, BO-4300e-3); the only way to discard it is `remove --path <same> --discard-token <that token>`. remove ok adds removed_path and discarded {commits: [sha], files: [path]}. list ok adds workspaces [{kind, slug, branch, workspace_path, workspace_path_posix, state: 'ready'|'incomplete'}]. Callers treat refused and error identically: halt.
- **BO-4300c-2 -> llm-expert**: Skills relay the maker's stdout verbatim and stop on a non-zero exit; they never summarise or re-derive fields.
- **BO-4300c-2 -> documentation-expert**: Field and code list for docs/reference/workspace-maker-answer.md (BO-4300a-5).
- consumed by **BO-4300a-1** in 01_TICKET-20260927-BO-4300a-1.md
- consumed by **BO-4300a-5** in 13_TICKET-20260928-BO-4300-docs-and-diagrams.md
- consumed by **BO-4300c-3** in 10_TICKET-20260928-BO-4300-workflow-runtime-and-shell-runner.md
- consumed by **BO-4300c-4** in 11_TICKET-20260928-BO-4300-workflow-routes.md

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No production data; developer repositories are protected by the ticket 02 session guard.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
