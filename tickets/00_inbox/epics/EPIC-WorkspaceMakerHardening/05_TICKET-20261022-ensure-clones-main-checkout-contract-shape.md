---
title: "Ensure clones the main checkout and answers in the contract's exact shape"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300a-1
  - BO-4300d-4
  - BO-4300c-2
  l3: []
status: todo
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
  - unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
  - unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
  - unit_tests/build_orchestration/test_bo_400e_3_ix_setup_record.py
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  commit: needed
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
- [ ] AC-1: BO-4300a-1 IT3 (A1) / BO-4300d-4 IT0. With a bare hub and a main checkout that has a local-only
  branch `feature/x` and a local `main` behind the hub, `ensure --kind feature --slug x` gives all of:
  - the workspace's origin URL equals the hub;
  - an object or pack file has a link count greater than 1;
  - `line_of_work` is `new`;
  - `base_commit` equals the hub's main tip;
  - `refs/remotes/origin/feature/x` does not exist.
- [ ] AC-2: BO-4300c-2 (no tool text; `step`). An unreachable hub gives `FETCH_FAILED` with a `step` field.
  No line the maker wrote to stderr (no `fatal:`) appears in `message` or `step`.
- [ ] AC-3: BO-4300c-2 (ok fields). An ensure ok answer carries:
  - `base_ref == "origin/main"`;
  - `origin_main_commit`;
  - `base_matches_origin_main`;
  - `fetch` in {ok, failed, skipped};
  - `created` (true on create, false on re-ready);
  - `bootstrap.config_path`;
  - `bootstrap.env_copied` (listing `.env` when the main checkout has one).
- [ ] AC-4: BO-4300c-2 (code enum, A2). `worktree_answer.ALL_CODES` is a subset of the code list parsed from
  `BO-4300c-2.yaml`'s delivers_to contract, `REFUSED` is in neither code set, and every non-ok answer the
  family's tests produce has a code in that list.
- [ ] AC-5: BO-400e-3-ix (A10). `ensure --kind ticket` records `branch.<branch>.leafcutterTicket`. A
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
