---
title: "The cut-over clones the main checkout, uses the canonical identity, defers readiness and loses nothing silently"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300f-3
  - BO-4300a-2
  l3:
  - BO-4300f-3-iii
  - BO-4300f-3-iv
status: todo
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-22'
last_updated: '2026-10-22'
depends_on:
  - 04_TICKET-20261022-clearing-stays-inside-project.md
  - 06_TICKET-20261022-work-identity-safe-slugs-canonical-first.md
  - 07_TICKET-20261022-read-only-verbs-refuse-and-answer-contract-shape.md
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
  - M6
  - N6
  - M10
  - M17
  - N7
  - P9
files_touched:
  - templates/scripts/worktree_migrate.py
  - templates/scripts/worktree.py
  - templates/scripts/worktree_readiness.py
  - unit_tests/build_orchestration/test_bo_4300f_3.py
  - unit_tests/build_orchestration/test_bo_4300f_3_iii.py
  - unit_tests/build_orchestration/test_bo_4300f_3_iv.py
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  commit: needed
---

# 08: The cut-over clones the main checkout, uses the canonical identity, defers readiness and loses nothing silently

## Actor / Goal
A user runs the one-off cut-over of old-style (linked) workspaces. Each old workspace should end up in one
of three states:
- brought over to its canonical place under its canonical identity, but not called ready until it is
  proven ready;
- retired, with any ignored content it deletes reported;
- left exactly as it is and listed for a decision, when it cannot be carried over exactly.

## Context
All references are verified against the current tree, in `templates/scripts/worktree_migrate.py` unless
stated otherwise.

- **M2 migrate (HIGH; ADR-018 Amendment 1 A1.1; BO-4300a-1 IT3 as amended by A1).** `_git_steps`
  (line 225) clones the HUB with `--local` (line 229).
  - Fix: clone `str(ctx.repo_root)`, then re-point origin at `ctx.hub` and run a pruning fetch from the hub,
    as ticket 05 does for ensure.
  - The following `fetch <repo_root> +refs/heads/<b>:refs/heads/<b>` (line 230) is still needed after the
    prune, because a local-only legacy line has no hub ref.
- **M4 migrate (BO-4300c-2 criterion).** At line 236, `git {cmd[0]} failed: {proc.stderr.strip()}` puts
  git's text into the report's `reason`. Name the step instead; git's text stays on stderr.
- **M6 / N6 (MEDIUM-HIGH; BO-4300f-3 criteria as amended by A8, option 1, plus the new IT;
  BO-4300c-1-ii).** `_marker` (line 213) writes `state: "ready"` (line 219) with no install build and no
  canary.
  - Fix:
    - Write `state: "creating"`.
    - Add `next: "ensure --kind <k> --slug <s>"` to the `brought_over` entry. The report names, for each
      brought-over workspace not yet shown ready, the one request that makes it ready.
  - That ensure must answer `workspace_action: "completed"` and `line_of_work: "resumed"`, and keep every
    brought-over commit and every uncommitted and untracked file byte-identical. Its clean-tree check and
    canaries never refuse on, or touch, the brought-over content.
  - Today a `creating` marker that is already checked out takes `worktree.py` `_resume_workspace`'s
    `head_state` path (lines 236-243), and `line_of_work` comes from `head_state`. The marker's recorded
    `resumed` must win there. That is why this ticket owns `worktree.py` in wave 4.
  - `worktree_readiness.tree_is_clean` (line 92) only looks at tracked changes, which `work_set_aside` puts
    aside. Edit `worktree_readiness.py` only if the canaries prove otherwise; it is listed so that the
    edit is owned.
- **M10 cut-over (MEDIUM; BO-4300f-3 IT2 as amended by A4; BO-4300a-2).** `identity_for` (line 117) tries
  the declared aliases BEFORE the canonical prefixes. So `feature/x` became kind `ticket` and landed in
  `<landing>/ticket/x`, and a later `ensure --kind feature --slug x` made a second workspace on the same
  line.
  - Fix: canonical prefixes first, declared aliases second, and never two identities.
  - A slug that `wi.slugify` cannot normalise (ticket 06) is unmappable. It goes to `needs_decision`, never
    a guess.
  - Ticket 06 removes the `ticket <- feature/` alias itself.
- **M17 (BO-4300e-2 IT1).** Replace `_rmtree_onerror` (line 101) and `_drop` (line 107) with the shared
  delete helper, and `_status_paths` (line 160, X-side rename only) with the shared `status -z` parser.
  Ticket 04 exposes both from `worktree_remove.py`.
- **N7 (new AC BO-4300f-3-iv, A9b, option R).** `_retire` (line 274) deletes the folder via
  `wrm._delete_tree` without reporting its git-ignored content.
  - Fix: list that content from git's own ignored listing (`status --ignored --porcelain=v1 -z`), naming a
    wholly ignored folder as that folder.
  - Report it as `ignored_removed: [path]` on the retired entry. `--preview` lists the same paths before
    anything is deleted.
- **P9 (new AC BO-4300f-3-iii, A9).** Not detected today:
  - An operation in progress: merge, rebase (both backends), cherry-pick, revert or bisect, read from the
    registration's own admin dir (`registrations`, line 84).
  - Stash entries. These are repository-wide, so a stash counts for the workspace whose branch it was made
    on.
  - Staged changes. `_carry` (line ~187) copies bytes only, so the index is lost. Either carry the index or
    send the entry to `needs_decision`.
  - A user lock, i.e. a `locked` reason other than WSL's `initializing` (line 96 handles only the stuck
    `initializing` case). v1 sends it to `needs_decision`.
  - Each of these sends the entry to `needs_decision` with its reason. No folder, register entry, stash
    entry or branch changes, and the preview reports the same reasons.
  - Port source: v1-UNCOMMITTED `workspace_migrate.py` (`_OPERATIONS`, `_operation`, stash detection, the
    `_blocker` cases, locked -> needs_decision). It exists only in the WSL worktree
    `/home/henzeh/projects/leafcutter/worktrees/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, which was
    not verifiable from this checkout.
- **Fixtures.** Use `legacy_worktree(project, name, unsent=...)` (the one exempt creator of old-style
  workspaces) and `start_merge` from `_workspace_maker_fixtures`. Write the user lock as the registration's
  `locked` file directly. Test files must not spell the raw linked-checkout add/remove command (BO-4300f-2
  census).

## Scope
1. Clone the main checkout in `_git_steps` (A1), with step-named reasons.
2. Deferred readiness (A8): a `creating` marker, the `next` hint, and ensure's completion as
   `completed`/`resumed` with the content byte-identical.
3. Canonical-first identity resolution.
4. Use the shared delete helper and status parser.
5. `ignored_removed` on retired entries, and in the preview (A9b).
6. The P9 blockers, sent to `needs_decision` with their reasons, in both the run and the preview (A9).

## Acceptance Criteria
- [ ] AC-1: BO-4300f-3 (A8). After the cut-over brings over a legacy `feature/a` with an unpushed commit, an
  uncommitted edit and an untracked file:
  - its marker state is `creating`, and `verify` answers `INCOMPLETE`;
  - its report entry carries `next == "ensure --kind feature --slug a"`;
  - running that ensure answers ok, `workspace_action == "completed"`, `line_of_work == "resumed"`;
  - the commit, the edit and the untracked file are byte-identical afterwards.
- [ ] AC-2: BO-4300f-3 IT2 / BO-4300a-2 (A4). After the cut-over of a legacy `feature/x`,
  `ensure --kind feature --slug x` answers the same `workspace_path` the cut-over reported, with
  `workspace_action` in {completed, re-readied}. The hub and the workspace hold exactly one line for x.
- [ ] AC-3: BO-4300f-3-iii (A9). Legacy workspaces "m" (merge with an unresolved conflict), "s" (a stash
  made on its branch), "i" (a staged, uncommitted change) and "l" (locked, reason "on USB drive") are
  handled as follows:
  - "m", "s" and "l" are listed in `needs_decision`, each with its reason;
  - "i" is either brought over with the change still staged and its content identical, or listed;
  - no folder, registration, stash entry or branch of the four changes;
  - the preview reports the same reasons.
- [ ] AC-4: BO-4300f-3-iv (A9b). Retiring a legacy workspace holding nothing unsent but holding ignored
  `.env.local` and `build/` removes its folder. Its retired entry lists `ignored_removed` containing
  `.env.local` and `build/`, and `--preview` run first lists the same paths and deletes nothing.
- [ ] AC-5: BO-4300a-1 IT3 (A1) / BO-4300c-2 (M2, M4 migrate). A brought-over clone's origin is the hub,
  some object file under its `.git/objects` has a link count greater than 1, and no `needs_decision` reason
  contains a line of git's stderr (no `fatal:`).

## Test Requirements

```yaml
tests:
- name: test_brought_over_workspace_is_not_ready_until_proven
  file: unit_tests/build_orchestration/test_bo_4300f_3.py
  covers:
  - BO-4300f-3
  asserts: >-
    make_project, then legacy_worktree(project, 'feature/a', unsent=True), plus an uncommitted edit and an
    untracked file. run_maker migrate-legacy, then:
    the marker state is 'creating';
    verify answers INCOMPLETE;
    the brought_over entry next == 'ensure --kind feature --slug a';
    run_maker that ensure answers ok with workspace_action 'completed' and line_of_work 'resumed';
    the commit sha, the edit bytes and the untracked bytes are unchanged.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_legacy_feature_line_is_one_workspace_whichever_kind_finds_it
  file: unit_tests/build_orchestration/test_bo_4300f_3.py
  covers:
  - BO-4300f-3
  - BO-4300a-2
  asserts: >-
    Cut over a legacy feature/x holding unsent work, then run_maker ensure --kind feature --slug x. The
    workspace_path equals the cut-over's reported path (under <landing>/feature/x, never ticket/x), the
    landing place holds one folder for x, and the hub and workspace hold one branch for x.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_work_that_cannot_be_carried_exactly_keeps_the_old_workspace
  file: unit_tests/build_orchestration/test_bo_4300f_3_iii.py
  covers:
  - BO-4300f-3-iii
  asserts: >-
    Four legacy_worktree fixtures: m (start_merge with an unresolved conflict), s (git stash on its
    branch), i (a staged change) and l (the registration's locked file reads 'on USB drive'). The preview
    and then the run list m, s and l in needs_decision with distinct reasons, and list i either there or
    as brought over with `git diff --cached` identical. The folder digests, registration files,
    `git stash list` and branch tips of all four are unchanged.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_retiring_reports_the_ignored_files_it_deletes
  file: unit_tests/build_orchestration/test_bo_4300f_3_iv.py
  covers:
  - BO-4300f-3-iv
  asserts: >-
    A legacy_worktree with nothing unsent, a .gitignore listing .env.local and build/, and both present.
    --preview lists ignored_removed ['.env.local', 'build/'] and the folder still exists. The real run
    removes the folder, and its retired entry has the same ignored_removed.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_brought_over_clone_is_hardlinked_from_main_checkout_and_reasons_carry_no_git_text
  file: unit_tests/build_orchestration/test_bo_4300f_3.py
  covers:
  - BO-4300f-3
  asserts: >-
    After bringing over feature/a, the brought-over clone's remote.origin.url equals the hub and some file
    under .git/objects has st_nlink > 1. With a legacy line whose checkout is forced to fail, the
    needs_decision reason names the step and contains no 'fatal:'.
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
