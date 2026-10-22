---
title: "Ensure clones the main checkout and answers in the contract's exact shape"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300a-1
  - BO-4300d-4
  - BO-4300c-2
  l3: []
status: done
ac_coverage: 5/5
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-22'
last_updated: '2026-10-22'
depends_on:
  - 01_TICKET-20261022-maker-never-waits-for-input.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: high
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - bo4300-hardening
  - M2
  - M4
  - M9c
  - M9d
  - N1
  - N5
  - BO-400e-3-ix
files_touched:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_ticket_record.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_steps.py
  - scripts/build_phases_script_deploy_standalone.py
  - unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
  - unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
  - unit_tests/build_orchestration/test_bo_400e_3_ix_setup_record.py
  - unit_tests/build_orchestration/test_bo_4300a_1_route_shape.py
  - unit_tests/build_orchestration/test_bo_4300a_1_deployed.py
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1.yaml
# out_of_scope: changed by ticket 01 (c41ecb714), the base commit of this lane; the scope
# guard diffs the whole branch against main, so it sees them. Not edited by this ticket.
out_of_scope:
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_canaries.py
  - templates/scripts/worktree_identity.py
  - templates/scripts/worktree_log_root.py
  - unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  ac-validator: signed_off
  ac-fulfillment-gate: signed_off
  commit: signed_off
---

# 05: Ensure clones the main checkout and answers in the contract's exact shape

## Actor / Goal
A route asks for a workspace. The workspace should be a hardlinked local clone of the main checkout,
whose origin is the hub and whose remote-tracking refs name only the hub's branches. That works without
network or SSH for the clone itself. The answer should carry exactly the fields and codes that BO-4300c-2
lists, with no git text in the message.

## Context
All references are verified against the current tree, in `templates/scripts/worktree.py` unless stated
otherwise.

- **M2 ensure (HIGH; BO-4300a-1 IT3 as amended by A1; BO-4300d-4 IT0; ADR-018 Amendment 1 A1.1).**
  - `_create_workspace` (line 199) clones the HUB: `["clone", "--no-checkout", "--local", hub, ...]` at
    line 203. Against a real `git@github.com:` origin, `--local` is ignored, which gives a full network
    clone with no hardlinks that needs SSH and can prompt.
  - Fix:
    - Clone `str(repo_root)`, the resolved main checkout.
    - `_checkout_line` (line 124) already re-points origin at the hub (line 128).
    - Then fetch from the hub with pruning, so that `refs/remotes/origin/*` names only the hub's branches.
      Use `git fetch --prune origin`, or delete `refs/remotes/origin/*` before fetching. This replaces
      `fetch origin main` at line 129.
  - Why the prune matters: a clone of the main checkout copies its LOCAL branches into
    `refs/remotes/origin/*`, and `worktree_identity.hub_lines` (line 99) reads those refs. It would treat a
    local-only branch as a hub line.
  - The ready-path fetch in `_resume_workspace` (line 233) stays scoped to the hub.
  - `FETCH_FAILED` stays the code when the hub cannot be reached, unless `--allow-stale-base` is given.
  - Port source: v1 4ff8e251a `workspace_create._clone`. A `--landing-root` on another volume loses the
    hardlinks; ADR-018 Amendment 1 notes this.
- **M4 ensure and ticket record (HIGH; BO-4300c-2 criterion; A2 item 4).** Git's stderr is pasted into
  `message` at these sites:
  - `worktree.py:118` (`_start_line` checkout), `:131` (`_checkout_line` fetch), `:205` (clone) and `:235`
    (resume fetch);
  - `templates/scripts/worktree_ticket_record.py:51` (returned into the line-67 message) and `:89`.
  - Fix: name the step in the message and add a `step` field. Git's text stays on stderr only.
    `bootstrap.failure_excerpt` remains the one sanctioned excerpt. First grep the tests for assertions on
    stderr text inside `message`.
- **M9c / N1 (BO-4300c-2 ok-answer fields).** The ensure ok answer (`_install_and_mark`, lines 142-196)
  lacks the following, which this ticket adds:
  - `base_ref` (`"origin/main"`);
  - `origin_main_commit`;
  - `base_matches_origin_main`;
  - `fetch` (`ok|failed|skipped`; `failed` only under `--allow-stale-base`);
  - `created` (bool);
  - `bootstrap.config_path`;
  - `bootstrap.env_copied`.

  `templates/scripts/worktree_git.py:91` `copy_optional_files` must return the names it copied. Merge
  `config_path` and `env_copied` into the bootstrap dict in `worktree.py`; `bootstrap` itself comes from
  `worktree_readiness.prove_ready`, which this ticket does NOT edit (ticket 07 owns `worktree_readiness.py`).
- **M9d (A2, A10).**
  - `templates/scripts/worktree_answer.py:37-52` lists `REFUSED` in `ALL_CODES` and `REFUSED_CODES`, and
    the comment at lines 33-34 claims `worktree_admin` emits it. Nothing emits it: a grep of
    `templates/scripts`, `templates/workflows-js`, `templates/skills`, `templates/agents` and
    `templates/commands` finds none (the only "REFUSED" in `finalize-feature.js:1202` is prose about
    `mark_ac_done.py`). Remove it.
  - `BUILT_FOR_OTHER_TICKET` is already in both sets (ticket 20 of the previous epic). A2 makes it a
    contract code.
  - The `REFUSED` row in `docs/reference/workspace-maker-answer.md:88` is removed by ticket 07, which owns
    that doc. `test_bo_4300_docs.py` only checks that codes are a subset of the doc, so the stale row does
    not fail in between.
- **BO-400e-3-ix (A10).** The record writer is `worktree_ticket_record.py`, and the refusal is
  `BUILT_FOR_OTHER_TICKET` with `branch`, `recorded_ticket` and `ticket_path`. The user kept scenario 2,
  reworded for existing legacy `feature/` lines that carry a built-for-ticket record. With A4,
  `feature/<slug>` is kind feature (ticket 06), so the test proves that a legacy `feature/my-fix` line
  carrying a record still derives its ticket in finalization.
  - BO-400e-3-ix lives in another AC folder
    (`docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400e-3-ix.yaml`).
    The `ac_traceability` list form resolves one folder only, so ac-fulfillment-gate will not see it.
    ac-validator checks it from this body.
- `worktree.py` is 477 lines. If the additions push it past the file-size ratchet, move the answer
  assembly into a helper inside `worktree.py`'s own family. Do not split it into a file that another
  ticket of this wave owns.

## Scope
1. Clone the main checkout, re-point origin, and run a pruning fetch from the hub (A1).
2. Step-named messages plus `step` at the six sites, with no git text (A2 item 4).
3. The ok-answer fields of M9c/N1; `copy_optional_files` returns the copied names.
4. Remove `REFUSED` from the code tables.
5. Keep the BO-400e-3-ix promises, with scenario 2 reworded.

## Acceptance Criteria
- [x] AC-1: BO-4300a-1 IT3 (A1) / BO-4300d-4 IT0. With a bare hub and a main checkout that has a local-only
  branch `feature/x` and a local `main` behind the hub, `ensure --kind feature --slug x` gives all of:
  - the workspace's origin URL equals the hub;
  - an object or pack file has a link count greater than 1;
  - `line_of_work` is `new`;
  - `base_commit` equals the hub's main tip;
  - `refs/remotes/origin/feature/x` does not exist.
- [x] AC-2: BO-4300c-2 (no tool text; `step`). An unreachable hub gives `FETCH_FAILED` with a `step` field.
  No line the maker wrote to stderr (no `fatal:`) appears in `message` or `step`.
- [x] AC-3: BO-4300c-2 (ok fields). An ensure ok answer carries:
  - `base_ref == "origin/main"`;
  - `origin_main_commit`;
  - `base_matches_origin_main`;
  - `fetch` in {ok, failed, skipped};
  - `created` (true on create, false on re-ready);
  - `bootstrap.config_path`;
  - `bootstrap.env_copied` (listing `.env` when the main checkout has one).
- [x] AC-4: BO-4300c-2 (code enum, A2). `worktree_answer.ALL_CODES` is a subset of the code list parsed from
  `BO-4300c-2.yaml`'s delivers_to contract, `REFUSED` is in neither code set, and every non-ok answer the
  family's tests produce has a code in that list.
- [x] AC-5: BO-400e-3-ix (A10). `ensure --kind ticket` records `branch.<branch>.leafcutterTicket`. A
  different recorded ticket is refused `BUILT_FOR_OTHER_TICKET` (exit 2, with `branch`, `recorded_ticket`
  and `ticket_path`) before any write. A legacy `feature/my-fix` line carrying a record derives that
  ticket in finalization.

## Test Requirements

```yaml
tests:
- name: test_workspace_is_hardlinked_clone_of_main_checkout_with_origin_at_hub
  file: unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
  covers:
  - BO-4300a-1
  - BO-4300d-4
  asserts: >-
    make_project(tmp). The project gets a local-only branch feature/x, and the hub's main is advanced past
    the project's main (_bo_4300a_1_fixtures.advance_hub). run_maker ensure --kind feature --slug x. Then
    the origin URL == the hub, some file under .git/objects has st_nlink > 1, line_of_work == 'new',
    base_commit == the hub's main tip, and refs/remotes/origin/feature/x is absent.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_fetch_failure_message_carries_no_git_text
  file: unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
  covers:
  - BO-4300c-2
  asserts: >-
    make_project, then the project's origin is repointed to a missing path. ensure answers FETCH_FAILED
    with a step field, and no non-empty stderr line of the run (and no 'fatal:') appears in message or
    step.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_ensure_ok_answer_carries_every_contract_field
  file: unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
  covers:
  - BO-4300c-2
  asserts: >-
    With a project holding a .env, ensure answers with base_ref 'origin/main', origin_main_commit,
    base_matches_origin_main true, fetch 'ok', created true, bootstrap.config_path, and
    bootstrap.env_copied containing '.env'. A second ensure answers created false.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_answer_codes_are_the_contract_codes
  file: unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
  covers:
  - BO-4300c-2
  asserts: >-
    Parse the code list from docs/acceptance-criteria/.../BO-4300c-2.yaml (delivers_to python-coder
    contract). The deployed worktree_answer.ALL_CODES is a subset of it, and REFUSED is absent from
    ALL_CODES and REFUSED_CODES.
  framework: unittest
  type: behavioral
- name: test_legacy_feature_line_with_record_derives_its_ticket
  file: unit_tests/build_orchestration/test_bo_400e_3_ix_setup_record.py
  covers:
  - BO-400e-3-ix
  asserts: >-
    A legacy feature/my-fix linked checkout (link_checkout) carrying branch.feature/my-fix.leafcutterTicket
    gives built_for_ticket == the recorded path from the real finalize_closable_set.py derive. The
    existing record, refusal and other-kinds tests stay green.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_h1_main_checkout_on_pushed_branch_resumes_with_only_that_local_branch
  file: unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
  covers:
  - BO-4300a-1
  asserts: >-
    Main checkout ON feature/x also pushed to a file:// hub, with a tag localtag only in the main checkout. ensure --kind feature --slug x answers ok, line_of_work resumed; the workspace is on feature/x at the hub tip, holds no other local branch and no tag.
  framework: unittest
  type: behavioral
  angle: discrimination
- name: test_m1_unreachable_hub_with_allow_stale_base_reports_failed_fetch_and_no_origin_main
  file: unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
  covers:
  - BO-4300a-1
  asserts: >-
    Origin re-pointed at a missing file:// path after the main checkout exists. With --allow-stale-base: ok, fetch failed, origin_main_commit null, base_matches_origin_main false. Without it: FETCH_FAILED with a step and no git text.
  framework: unittest
  type: behavioral
  angle: failure
- name: test_m2_ok_answer_carries_bootstrap_failure_excerpt_as_none
  file: unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
  covers:
  - BO-4300c-2
  asserts: >-
    An ok ensure answer has bootstrap.failure_excerpt present and None.
  framework: unittest
  type: behavioral
  angle: criterion
- name: test_workspace_inherits_no_alternates_from_main_checkout
  file: unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
  covers:
  - BO-4300a-1
  asserts: >-
    Main checkout made with git clone --shared (has objects/info/alternates); the created workspace has no objects/info/alternates.
  framework: unittest
  type: behavioral
  angle: discrimination
- name: test_every_route_receives_answer_of_identical_shape_MANUAL
  file: unit_tests/build_orchestration/test_bo_4300a_1_route_shape.py
  covers:
  - BO-4300a-1
  asserts: >-
    Restored M-3: the non-canary checks (via _split_canary_checks) are equal across the five routes.
  framework: unittest
  type: behavioral
  angle: criterion
```

## Sign-offs
- [x] test-writer — 2026-10-22 11:52
- [x] python-coder — 2026-10-22 13:30
- [x] pr-reviewer — 2026-10-22 16:05
- [x] ac-validator — 2026-10-22 16:40
- [x] ac-fulfillment-gate — 2026-10-22 17:10
- [x] commit — 2026-10-22 17:30

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-10-22 11:52 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_written: true
  tests_red_for_right_reason: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "worktree.py ensure (deployed maker, real subprocess) answering for a file:// hub and a main checkout with a local-only branch"
    consuming_side: "git itself (hardlinked objects, refs/remotes/origin/*) and worktree_answer.ALL_CODES read against the BO-4300c-2.yaml contract"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python <deployed>/scripts/worktree.py ensure ... (CLI via subprocess, run_maker/maker helper)"
red_baseline:
  - test_name: test_workspace_is_hardlinked_clone_of_main_checkout_with_origin_at_hub
    file: unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
    kind: assertion
    error: "AssertionError: False is not true : no object file has st_nlink > 1: not a hardlinked local clone"
  - test_name: test_fetch_failure_message_carries_no_git_text
    file: unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
    kind: assertion
    error: "AssertionError: False is not true : no step field: {'status': 'refused', 'code': 'FETCH_FAILED', 'message': \"git clone --no-checkout --local failed: fatal: repository ... does not exist\"}"
  - test_name: test_resume_fetch_failure_carries_a_step_and_no_git_text
    file: unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
    kind: assertion
    error: "AssertionError: False is not true : no step field: {... 'message': \"git fetch origin main failed: fatal: ... does not appear to be a git repository\"}"
  - test_name: test_ensure_ok_answer_carries_every_contract_field
    file: unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
    kind: assertion
    error: "AssertionError: None != 'origin/main' (base_ref missing from the ok answer)"
  - test_name: test_answer_codes_are_the_contract_codes
    file: unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
    kind: assertion
    error: "AssertionError: Lists differ: ['REFUSED'] != [] : codes outside the contract list"
Verified red on Linux (Docker, AC_ENFORCE_STRICT=1), each file alone. Not red by design: test_non_ok_answers_use_contract_codes
and test_legacy_feature_line_with_record_derives_its_ticket already pass (regression pins; the derive reader already honours the record).
The clone-source test uses a file:// hub, because git ignores --local for a URL and a plain-path hub hides the bug.

### 2026-10-22 13:30 — python-coder (status: handoff)
feedback-id: (submit-failed)
handoff_target: test-writer
red_baseline_results:
  - test_workspace_is_hardlinked_clone_of_main_checkout_with_origin_at_hub: green
  - test_fetch_failure_message_carries_no_git_text: green
  - test_resume_fetch_failure_carries_a_step_and_no_git_text: green
  - test_ensure_ok_answer_carries_every_contract_field: green
  - test_answer_codes_are_the_contract_codes: green
files: worktree.py (ensure path), NEW worktree_ensure_steps.py (named deploy entry in scripts/build_phases_script_deploy_standalone.py), worktree_answer.py (REFUSED removed), worktree_ticket_record.py (step, no git text), worktree_git.py (copy_optional_files returns names).
REFUSED grep (templates/workflows-js, agents, skills, scripts, commands): no code use; only prose in finalize-feature.js:1202, commit_guardian OUTCOME_REFUSED/"REFUSED:" hook text, and submit_feedback.py prose.
Linux (Docker, bo_4300 or bo_400e): one failure, outside the red baseline: test_bo_4300a_1_deployed.py::test_every_route_receives_answer_of_identical_shape_MANUAL. It compares every non-identity key across the five routes, and the new bootstrap.config_path is workspace-specific (<workspace>/.claude/skills_config.json), so it differs by design. Needs a test-writer fix: treat bootstrap.config_path as identity-derived (compare bootstrap with config_path removed). Production is correct (classification: test_drift).

### 2026-10-22 14:10 — test-writer (status: ok)
feedback-id: (submit-failed)
(classification: test_drift) test_every_route_receives_answer_of_identical_shape_MANUAL compared every non-identity top-level key across routes, but BO-4300c-2's bootstrap.config_path is <workspace>/.claude/skills_config.json, so it is per-workspace by contract; production is correct. The test now removes config_path from the strict `bootstrap` comparison (all other bootstrap fields still compared exactly) and asserts config_path sits inside each route's workspace_path. The test lives in test_bo_4300a_1_route_shape.py (see the file-size comment below).
Linux variant runner (bo_4300 or bo_400e): 355 passed, 2 skipped, 0 failed.

### 2026-10-22 14:40 — test-writer (status: ok)
feedback-id: (submit-failed)
check-file-size ratchet: moved test_every_route_receives_answer_of_identical_shape_MANUAL (name and `# covers:`/`# angle:` tags kept, with the setUpClass and the three fixture helpers it needs) into the new unit_tests/build_orchestration/test_bo_4300a_1_route_shape.py; removed only that region from test_bo_4300a_1_deployed.py (back to base content minus the test, plus the now-unused `import json` dropped). BO-4300a-1.yaml covered_by now lists the new file; files_touched updated. `pre-commit run check-file-size` passes on both files. MERGE NOTE: ci.yml is ticket 03's lane and was not edited; test_bo_4300a_1_route_shape.py must join the dedicated CI job's file list at merge.

### 2026-10-22 15:20 — pr-reviewer (status: blocker)
feedback-id: (submit-failed)
completion_manifest:
  clone_source_reviewed: true
  step_and_messages_reviewed: true
  c2_ok_fields_reviewed: true
  refused_removal_reviewed: true
  deploy_manifest_reviewed: true
  clone_source_regression:
    result: false
    reason: "H-1: git clone of the main checkout creates a local refs/heads/<HEAD branch> (verified with git). When the main checkout sits on a branch that is also a pushed hub line for the requested identity, _start_line runs `checkout -b <branch> --track origin/<branch>` and git answers 'a branch named ... already exists'; ensure returns GIT_FAILED(step checkout) and discards the clone. Cloning the hub never had this."
    remediation: "Respawn python-coder: after the clone, detach or delete the cloned local branch (e.g. checkout -B in the resume path, or remove refs/heads/* the clone made) and add a test with the main checkout ON a pushed feature/x. Also address M-1..M-4 in the report."
Blocking findings: H-1 above. Medium: M-1 --allow-stale-base after a failed first fetch keeps origin/main = the main checkout's local main, so base_matches_origin_main is trivially true and origin_main_commit is not the hub's (and with no local main ensure refuses at resolve-base); M-2 bootstrap on an ok answer lacks failure_excerpt (c-2 says str|null); M-3 test_bo_4300a_1_route_shape.py silently dropped the non-canary `checks` equality assertion of the original test (and the deployed file keeps a now-dead _split_canary_checks); M-4 main-checkout tags survive in the workspace (fetch --prune does not prune tags), and the set-url / set-head / update-ref results are unchecked. REFUSED removal, BUILT_FOR_OTHER_TICKET fields, step names with no git text, and the worktree_ensure_steps.py deploy entry (manifest helpers derive from NAMED_STANDALONE_SCRIPTS) are sound. No code was modified by the reviewer.

### 2026-10-22 14:30 — python-coder (status: ok)
feedback-id: (submit-failed)
Rework for pr-reviewer (templates/scripts/worktree_ensure_steps.py, worktree.py):
- H-1: after the clone HEAD is detached (update-ref --no-deref), then every refs/heads/* and refs/tags/* is deleted (chunked branch -D / tag -d).
- M-4: set-url, set-head and every ref deletion are checked; a failure is GIT_FAILED with a step (set-origin, set-head, strip-local-refs, strip-remote-refs, detach-head) and no git text, and the new clone is discarded. An objects/info/alternates file is repacked away (step alternates).
- M-1: a failed hub fetch under --allow-stale-base answers fetch 'failed', origin_main_commit null, base_matches_origin_main false, plus a message saying the base is stale. No origin/main at all stays FETCH_FAILED at step resolve-base.
- M-2: bootstrap.failure_excerpt is always present (None on ok).
Linux family run (ci_docker_add.sh, bo_4300 or bo_400e): green, with test_bo_4300a_1_clone_source.py ignored because it was mid-write by the test-writer (SyntaxError at line 108, unterminated string).

### 2026-10-22 16:10 — test-writer (status: ok)
feedback-id: (submit-failed)
(classification: production_drift for H-1/M-1/M-2/alternates; test_drift for M-3) Responds to the pr-reviewer blocker. Added to test_bo_4300a_1_clone_source.py: H-1 resume with main checkout ON a pushed feature/x plus a main-checkout-only tag; M-1 unreachable hub (+/- --allow-stale-base); M-2 failure_excerpt present and None; alternates dropped (main checkout made with clone --shared). M-3 restored in test_bo_4300a_1_route_shape.py (non-canary checks equal across routes). _split_canary_checks stays in test_bo_4300a_1_deployed.py because the parity test there still uses it (line 298), so it was not removed.
Linux (ci_docker_add.sh, strict, each file alone) against the working tree with the coder's strip-refs/alternates changes landed: clone_source 5 passed, route_shape 1 passed.
Red proof: against a scratch worktree of HEAD + the same production files with clone_main_checkout's strip/alternates step neutralised: H-1 FAILED (GIT_FAILED step checkout) and the alternates test FAILED (alternates leaked). M-1 and M-2 were not run against a pre-fix tree (the fix had already landed); M-3 is an assertion restoration, green on the current tree.
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: "deployed worktree.py ensure (real subprocess) cloning a real main checkout"
    consuming_side: "git refs/tags/alternates state of the created workspace and the answer JSON fields"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python <deployed>/scripts/worktree.py ensure (CLI via subprocess, maker helper)"
red_baseline:
  - test_name: test_h1_main_checkout_on_pushed_branch_resumes_with_only_that_local_branch
    file: unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
    kind: assertion
    error: "AssertionError: Tuples differ: ('error', 1) != ('ok', 0) : GIT_FAILED step checkout (clone strip step neutralised)"
  - test_name: test_workspace_inherits_no_alternates_from_main_checkout
    file: unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
    kind: assertion
    error: "AssertionError: True is not false : alternates leaked into workspace (clone strip step neutralised)"

### 2026-10-22 16:05 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  h1_resolved: true
  m1_m2_m3_m4_resolved: true
  new_high_findings: false
  ok_answer_message_matches_contract:
    result: false
    reason: "Medium M-5: under --allow-stale-base with a failed fetch, ok_fields adds `message` to an ENSURE ok answer. BO-4300c-2 lists message as a common field 'naming the cause' and its ok-field list has none; the maker emits no message on any other ensure ok answer. It is a compatible addition under the schema_version rule, so not blocking."
    remediation: "Prefer dropping it: fetch 'failed', origin_main_commit null and base_matches_origin_main false already state the staleness, and the sentence can go to stderr. If a human-visible note is wanted, amend BO-4300c-2 (message present on an ok answer when fetch is 'failed') first."
Re-review of the reworked staged diff: H-1 is fixed (HEAD detached, refs/heads/* and tags stripped, verified by the new resume test on a pushed branch); M-1..M-4 are addressed and covered by tests that ran green (10 passed in clone_source, contract_codes and route_shape). No low leftovers worth a rework (_split_canary_checks is still used in test_bo_4300a_1_deployed.py).

### 2026-10-22 15:10 — python-coder (status: ok)
feedback-id: (submit-failed)
M-5 rework: ok_fields no longer adds `message` on the failed-fetch path; the stale-base sentence goes to the logger (stderr). To keep worktree.py inside the file-size ratchet (it measured 406 > 400), build_marker/now_iso moved to worktree_ensure_steps.py. Linux: test_bo_4300a_1_clone_source.py alone green (5 passed); full family (bo_4300 or bo_400e) green.

### 2026-10-22 16:40 — ac-validator (status: ok)
feedback-id: (submit-failed)
All 5 ACs covered. Store alignment (check_v2_ac_store_alignment.py): exit 0. No delivers_to/expects_from fields on the ACs; cross-file seams checked in the body (BO-400e-3-ix below). Test evidence is the caller's Linux Docker run (bo_4300 or bo_400e green incl. manual); not re-run here.
AC-1 covered:
  implementation: templates/scripts/worktree_ensure_steps.py clone_main_checkout (clones str(repo_root)), sync_with_hub (set-url hub, fetch --prune origin), _strip_local_refs; worktree.py _create_workspace
  test: test_workspace_is_hardlinked_clone_of_main_checkout_with_origin_at_hub (unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py); also test_h1_..., test_workspace_inherits_no_alternates_...
AC-2 covered:
  implementation: worktree_ensure_steps.py _fetch / step_error("FETCH_FAILED", "fetch-hub", ...); worktree.py _checkout_line, _resume_workspace; worktree_ticket_record.py (step read-ticket-record, record-ticket)
  test: test_fetch_failure_message_carries_no_git_text, test_resume_fetch_failure_carries_a_step_and_no_git_text (test_bo_4300c_2_contract_codes.py)
AC-3 covered:
  implementation: worktree_ensure_steps.py ok_fields (base_ref, origin_main_commit, base_matches_origin_main, fetch, created), bootstrap_fields (config_path, env_copied, failure_excerpt); worktree_git.py copy_optional_files returns names; worktree.py _install_and_mark
  test: test_ensure_ok_answer_carries_every_contract_field (test_bo_4300c_2_contract_codes.py), test_m2_ok_answer_carries_bootstrap_failure_excerpt_as_none, test_m1_unreachable_hub_with_allow_stale_base_... (clone_source), test_every_route_receives_answer_of_identical_shape_MANUAL (test_bo_4300a_1_route_shape.py)
AC-4 covered:
  implementation: templates/scripts/worktree_answer.py ALL_CODES and REFUSED_CODES (REFUSED removed; BUILT_FOR_OTHER_TICKET retained); BO-4300c-2.yaml lists BUILT_FOR_OTHER_TICKET, states REFUSED is not a code, defines step
  test: test_answer_codes_are_the_contract_codes (asserts subset, REFUSED absent, BUILT_FOR_OTHER_TICKET in refused set), test_non_ok_answers_use_contract_codes (test_bo_4300c_2_contract_codes.py)
AC-5 (BO-400e-3-ix, checked from the ticket body) covered:
  IT0 records: worktree_ticket_record.py finish/_record writes branch.<b>.leafcutterTicket via git config --replace-all in the workspace clone; test_ticket_workspace_records_its_ticket_against_its_branch (reads the workspace config), test_record_round_trips_into_the_derivation_...
  IT1 refusal: conflict_refusal returns BUILT_FOR_OTHER_TICKET with branch, recorded_ticket, ticket_path, called in worktree.py:195 before any write; test_same_slug_different_ticket_is_refused_by_name_before_any_write (exit 2, config and snapshot byte-identical, no workspace_path)
  IT2 other kinds: RECORDING_KIND == "ticket" guard; test_ticketless_kinds_record_nothing (with a control row)
  IT3 writer/legacy: writer is worktree_ticket_record.py (staged diff: step/no-git-text changes only); test_legacy_feature_line_with_record_derives_its_ticket (test_bo_400e_3_ix_setup_record.py:232, real derive)
Notes: ticket has no `## AC Coverage` table, so only checkboxes and frontmatter ac_coverage: 5/5 were updated. BO-4300a-1.yaml covered_by now lists test_bo_4300a_1_route_shape.py (ci.yml job list is ticket 03's merge note).

### 2026-10-22 17:10 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
All 3 L2 ACs resolved (BO-4300a-1, BO-4300d-4, BO-4300c-2) plus BO-400e-3-ix verified. 4 append-only auto-fixes to implemented_by/covered_by (schema check clean, files staged). work_status untouched: BO-4300a-1 and BO-4300c-2 stay in_progress (tickets 07/08 pending), BO-400e-3-ix stays in_progress, BO-4300d-4 already done.
Composite BO-4300a-1 in_progress -- unfinished children: BO-4300a-1-ia, BO-4300a-1-ib, BO-4300a-1-ii. Commit phase may proceed.

### 2026-10-22 17:30 — commit (status: ok)
feedback-id: (submit-failed)
Auto-authorized commit gate: 16 staged files (4 AC YAMLs, deploy script, 5 worktree scripts, ticket, 5 tests); pre-commit hook probe passed.
