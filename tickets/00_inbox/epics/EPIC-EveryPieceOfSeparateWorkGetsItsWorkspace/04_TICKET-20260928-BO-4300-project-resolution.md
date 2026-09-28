---
title: 'Project resolution: the same workspace from any folder, installed or not, or a clear refusal'
status: todo
components:
- worktree_manager
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on:
- 03_TICKET-20260928-BO-4300-answer-contract.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: contract_boundary
complexity: high
requires_adr: true
requires_diagram: false
source_ac: BO-4300b-1
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300b-1
  - BO-4300b-2
  - BO-4300b-3
  l3:
  - BO-4300b-1-i
  - BO-4300b-2-i
  - BO-4300b-2-ii
  - BO-4300b-3-i
ac_coverage: 0/7
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- templates/scripts/worktree.py
- templates/scripts/worktree_git.py
- templates/scripts/worktree_admin.py
- templates/scripts/workspace_root.py
- templates/scripts/worktree_layout.py
- scripts/build_phases_script_deploy_standalone.py
- scripts/build_deploy_manifest_helpers.py
- docs/architecture/adrs/worktree-maker-amendment-1-2026-09-27.md
- unit_tests/build_orchestration/test_bo_4300b_1.py
- unit_tests/build_orchestration/test_bo_4300b_1_i.py
- unit_tests/build_orchestration/test_bo_4300b_2.py
- unit_tests/build_orchestration/test_bo_4300b_2_i.py
- unit_tests/build_orchestration/test_bo_4300b_2_ii.py
- unit_tests/build_orchestration/test_bo_4300b_3.py
- unit_tests/build_orchestration/test_bo_4300b_3_i.py
agents:
  ac-fulfillment-gate: needed
  ac-validator: needed
  adr-author: needed
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

# 04: Project resolution: the same workspace from any folder, installed or not, or a clear refusal

## Actor / Goal

In order that the same request gives the same workspace wherever it starts, we need the resolver module's full resolution order, the landing-place rule and the refusals for no project / several projects, so that a request from a nested workspace, an installed project or an empty folder never lands in the wrong place.

## Context

Ticket 01 built `workspace_root.py` with the resolution ORDER explicitly deferred to BO-4300b-1 (README Critical Context). b-2, b-2-ii, b-3 and b-3-i all expect from b-1, so the whole b-1..b-3 family is one deliverable owned by one module.

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 7 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300b-1-i | L3 | Starting inside another workspace never nests the new one there or roots it on that work | BO-4300b-1 | this ticket |
| AC-2 | BO-4300b-1 | L2 | The same request from any folder in or around the project gives the same workspace | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |
| AC-3 | BO-4300b-2-i | L3 | Two projects in the same folder never share or collide on a workspace | BO-4300b-2 | this ticket |
| AC-4 | BO-4300b-2-ii | L3 | An out-of-date installed copy inside the project does not change which project is found | BO-4300b-1 | this ticket |
| AC-5 | BO-4300b-2 | L2 | A project that installed the tools gets its workspaces the same way | BO-4300b-1 | this ticket |
| AC-6 | BO-4300b-3-i | L3 | Started where no project can be found, the request is refused and says where it looked | BO-4300b-1 | this ticket |
| AC-7 | BO-4300b-3 | L2 | When more than one project could be meant, the request is refused and names them | BO-4300b-1 | this ticket |

**Closure order.** Children are listed before their parents. Composite(s) `BO-4300b-1`, `BO-4300b-2`, `BO-4300b-3` close only after every child listed in their `covered_by` is done (`check-done-proof`); all of those children are in this ticket, so no parent here waits on another ticket. `source_ac` (`BO-4300b-1`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300b-1-i (L3) -- Starting inside another workspace never nests the new one there or roots it on that work

```gherkin
Given the request for "beta" is started from inside workspace W1, whose line of
  work carries one commit not on the shared main line, and which has one
  uncommitted change,
When the request is answered ready,
Then the "beta" workspace sits beside W1 in the landing place, not inside W1,
And "beta"'s line of work starts at the shared main line tip, and W1's commit
  is not reachable from it,
And W1's files, its uncommitted change and its line of work are identical
  before and after the request.
```

### AC-2: BO-4300b-1 (L2) -- The same request from any folder in or around the project gives the same workspace

```gherkin
Given a project "proj" whose parent folder is not itself a project, and a ready
  workspace W1 for the work "alpha",
When a workspace for the work "beta" is requested, one request at a time, from
  each of: proj's top folder; a folder three levels down inside proj; the parent
  folder above proj; a sibling folder beside proj; inside W1; and inside the
  "beta" workspace itself once it exists,
Then every request is answered ready with the same location for "beta",
And every request found the same project, proj,
And in every case the "beta" workspace is in proj's landing place for
  workspaces, never inside the folder the request was started from.
```

### AC-3: BO-4300b-2-i (L3) -- Two projects in the same folder never share or collide on a workspace

```gherkin
Given two projects, "shop" and "blog", that each installed these tools, sit side
  by side in the same parent folder,
When a workspace for work named "alpha" is requested in shop, and then a
  workspace for work named "alpha" is requested in blog,
Then two distinct workspaces exist, each a copy of its own project,
And shop's "alpha" workspace is identical before and after blog's request,
And asking shop where its "alpha" workspace is returns shop's, and asking blog
  returns blog's, never the other project's.
```

### AC-4: BO-4300b-2-ii (L3) -- An out-of-date installed copy inside the project does not change which project is found

```gherkin
Given the tools' own package project contains an out-of-date installed copy of
  the tools inside it, and the current installed copy sits in the folder above
  it, as in the package's development layout,
When a workspace for "alpha" is requested from the folder above, from the
  package project's top folder, and from inside an existing workspace,
Then all three requests find the same project and are answered with the same
  location,
And the tools installed inside the workspace are built from the workspace's own
  contents, not taken from the out-of-date copy.
```

### AC-5: BO-4300b-2 (L2) -- A project that installed the tools gets its workspaces the same way

```gherkin
Given a project "shop" that installed these tools, whose installed copy of the
  workspace maker lives in a folder outside shop's version history,
When a workspace for the work "alpha" is requested from shop's top folder, and
  again from the folder above shop,
Then both requests are answered ready with the same location,
And the workspace is a copy of shop, started from shop's shared main line tip,
  with shop's own tools installed inside it,
And that location is the same on every request for "alpha" in shop, and lies
  in the one place set aside for shop's workspaces: a folder beside shop, in
  shop's parent folder and named after shop, never inside shop itself.
```

### AC-6: BO-4300b-3-i (L3) -- Started where no project can be found, the request is refused and says where it looked

```gherkin
Given an empty folder with no project in it, beneath it or beside it,
When a workspace is requested from that folder,
Then the request is refused,
And the refusal states that no project was found and names the folder the
  request was started from,
And the folder and its neighbours contain exactly what they contained before.
```

### AC-7: BO-4300b-3 (L2) -- When more than one project could be meant, the request is refused and names them

```gherkin
Given a folder that is not a project and contains two projects, "shop" and
  "blog",
When a workspace is requested from that folder without saying which project,
Then the request is refused,
And the refusal names both "shop" and "blog" as the candidates it could not
  choose between,
And no workspace and no line of work is created in either project,
And given the same request names "shop" as its project, it is answered ready
  with a workspace that is a copy of shop.
```

- [ ] AC-1: BO-4300b-1-i -- Starting inside another workspace never nests the new one there or roots it on that work
- [ ] AC-2: BO-4300b-1 -- The same request from any folder in or around the project gives the same workspace
- [ ] AC-3: BO-4300b-2-i -- Two projects in the same folder never share or collide on a workspace
- [ ] AC-4: BO-4300b-2-ii -- An out-of-date installed copy inside the project does not change which project is found
- [ ] AC-5: BO-4300b-2 -- A project that installed the tools gets its workspaces the same way
- [ ] AC-6: BO-4300b-3-i -- Started where no project can be found, the request is refused and says where it looked
- [ ] AC-7: BO-4300b-3 -- When more than one project could be meant, the request is refused and names them

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_request_from_inside_w1_places_beta_beside_w1
  file: unit_tests/build_orchestration/test_bo_4300b_1_i.py
  covers:
  - BO-4300b-1-i
  asserts: beta's workspace_path is a sibling of W1 in the landing place, not a descendant of W1.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_beta_starts_at_hub_main_and_w1_commit_is_unreachable
  file: unit_tests/build_orchestration/test_bo_4300b_1_i.py
  covers:
  - BO-4300b-1-i
  asserts: beta's base_commit equals the hub's main tip and W1's extra commit is not an ancestor of beta's
    HEAD.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_w1_is_byte_identical_after_the_request
  file: unit_tests/build_orchestration/test_bo_4300b_1_i.py
  covers:
  - BO-4300b-1-i
  asserts: W1's tracked files, its uncommitted change and its branch ref are identical before and after.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_beta_is_answered_ok_with_same_location_from_every_starting_point
  file: unit_tests/build_orchestration/test_bo_4300b_1.py
  covers:
  - BO-4300b-1
  asserts: From proj's top folder, three levels down, the parent folder, a sibling folder, inside W1 and
    inside the 'beta' workspace, every request for beta is answered ok with the same workspace_path.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_every_starting_point_resolves_the_same_project
  file: unit_tests/build_orchestration/test_bo_4300b_1.py
  covers:
  - BO-4300b-1
  asserts: Every answer's repo_root is proj.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_beta_never_lands_inside_the_starting_folder
  file: unit_tests/build_orchestration/test_bo_4300b_1.py
  covers:
  - BO-4300b-1
  asserts: In every case beta's workspace_path is in proj's landing place and is not inside the folder
    the request started from.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_workspace_parent_with_empty_git_and_claude_md_is_never_resolved_as_the_project
  file: unit_tests/build_orchestration/test_bo_4300b_1.py
  covers:
  - BO-4300b-1
  asserts: The dev layout's workspace parent is built with an empty .git/ folder and a CLAUDE.md (git
    discovery bounded to the temp root via GIT_CEILING_DIRECTORIES). Run from it, the deployed maker answers
    ok with repo_root == proj; with a second child repository added it answers AMBIGUOUS_REPO listing
    both; with proj removed it answers NO_REPO. In no case is repo_root the parent. The same three cases
    are repeated through the deployed resolver module in a separate process.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_resolution_never_anchors_on_the_makers_own_location
  file: unit_tests/build_orchestration/test_bo_4300b_1.py
  covers:
  - BO-4300b-1
  asserts: With the deployed maker living inside project A's install, a request started from a temp folder
    that is not in or beside any repository answers NO_REPO naming that folder as searched_from, never
    project A.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_inside_a_workspace_the_project_comes_from_its_marker_only
  file: unit_tests/build_orchestration/test_bo_4300b_1.py
  covers:
  - BO-4300b-1
  asserts: From three levels inside W1 the answer's repo_root is the project_root W1's marker records;
    with the marker's project_root pointed at a missing folder the answer is NO_REPO naming the marker,
    and never W1 itself nor a folder derived from W1's position under the landing place.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_resolver_recomputes_on_every_call
  file: unit_tests/build_orchestration/test_bo_4300b_1.py
  covers:
  - BO-4300b-1
  asserts: In one separate process, the deployed resolver module called from proj and then from an unrelated
    second project returns each project in turn -- no answer is carried over between calls.
  framework: unittest
  type: behavioral
  angle: seam
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_same_slug_in_two_projects_gives_two_distinct_workspaces
  file: unit_tests/build_orchestration/test_bo_4300b_2_i.py
  covers:
  - BO-4300b-2-i
  asserts: alpha in shop and alpha in blog yield two different workspace_path values, each a clone of
    its own project.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_shops_workspace_is_unchanged_by_blogs_request
  file: unit_tests/build_orchestration/test_bo_4300b_2_i.py
  covers:
  - BO-4300b-2-i
  asserts: shop's alpha workspace (files and HEAD) is identical before and after blog's request.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_locate_returns_each_projects_own_workspace
  file: unit_tests/build_orchestration/test_bo_4300b_2_i.py
  covers:
  - BO-4300b-2-i
  asserts: locate alpha run in shop returns shop's path and in blog returns blog's.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_two_projects_land_in_their_own_sibling_folders
  file: unit_tests/build_orchestration/test_bo_4300b_2_i.py
  covers:
  - BO-4300b-2-i
  asserts: shop's alpha is under <parent>/shop-worktrees/ and blog's under <parent>/blog-worktrees/.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_shared_landing_root_override_refuses_rather_than_collides
  file: unit_tests/build_orchestration/test_bo_4300b_2_i.py
  covers:
  - BO-4300b-2-i
  asserts: With both requests given the same valid --landing-root, blog's alpha is refused OCCUPIED with
    occupant kind other-project, and shop's alpha workspace is byte-identical before and after.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_stale_inner_install_does_not_change_the_project_found
  file: unit_tests/build_orchestration/test_bo_4300b_2_ii.py
  covers:
  - BO-4300b-2-ii
  asserts: In a dev-layout fixture with an out-of-date inner install and a current outer one, requests
    from the parent, the package's top folder and inside a workspace return the same repo_root and workspace_path.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_workspace_install_is_built_from_its_own_contents
  file: unit_tests/build_orchestration/test_bo_4300b_2_ii.py
  covers:
  - BO-4300b-2-ii
  asserts: Files in the workspace's install match the workspace's own build output (a marker value planted
    only in the stale copy is absent).
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_adopter_request_from_top_and_parent_folder_gives_same_location
  file: unit_tests/build_orchestration/test_bo_4300b_2.py
  covers:
  - BO-4300b-2
  asserts: An installed maker outside shop's history, run from shop's top folder and from its parent,
    answers ok with the same workspace_path both times.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_adopter_workspace_is_clone_of_shop_at_hub_main_with_own_install
  file: unit_tests/build_orchestration/test_bo_4300b_2.py
  covers:
  - BO-4300b-2
  asserts: The workspace is a clone of shop (origin = shop's hub), base_commit = shop's hub main tip,
    and shop's install files are regular files built inside it.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_adopter_location_is_stable_and_in_shops_landing_place
  file: unit_tests/build_orchestration/test_bo_4300b_2.py
  covers:
  - BO-4300b-2
  asserts: Repeated requests for alpha in shop return the same workspace_path, located in the one place
    set aside for shop's workspaces.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_workspace_lands_in_the_sibling_folder_named_after_the_project
  file: unit_tests/build_orchestration/test_bo_4300b_2.py
  covers:
  - BO-4300b-2
  asserts: The ok workspace_path is <shop's parent>/shop-worktrees/<kind>/alpha, and shop's working tree
    (git status --porcelain --ignored) is identical before and after -- no folder, file or ignore entry
    appears inside shop.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_dev_layout_lands_beside_the_package_repository
  file: unit_tests/build_orchestration/test_bo_4300b_2.py
  covers:
  - BO-4300b-2
  asserts: In a dev-layout fixture (package repository pkg as a child of a non-repo workspace folder holding
    the current install), the ok workspace_path is <workspace folder>/pkg-worktrees/<kind>/alpha, not
    <workspace folder>/worktrees/alpha and not inside pkg.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_valid_landing_root_override_is_used_and_needed_to_find_it_again
  file: unit_tests/build_orchestration/test_bo_4300b_2.py
  covers:
  - BO-4300b-2
  asserts: With --landing-root naming a valid empty folder outside shop, the workspace lands at <override>/<kind>/alpha;
    locate with the same override finds it, and locate without it answers NOT_FOUND.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_invalid_landing_root_override_is_refused_as_usage_writing_nothing
  file: unit_tests/build_orchestration/test_bo_4300b_2.py
  covers:
  - BO-4300b-2
  asserts: --landing-root inside shop's working tree, and --landing-root inside an existing workspace,
    each exit 64 with status error, code USAGE and a message naming the broken rule; no folder, lock,
    branch or marker is created anywhere.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_landing_place_is_not_taken_from_the_environment
  file: unit_tests/build_orchestration/test_bo_4300b_2.py
  covers:
  - BO-4300b-2
  asserts: With environment variables named like a landing-root setting pointing elsewhere, the workspace
    still lands at <shop's parent>/shop-worktrees/<kind>/alpha.
  framework: unittest
  type: behavioral
  angle: seam
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_request_from_empty_folder_is_refused_no_repo_naming_the_folder
  file: unit_tests/build_orchestration/test_bo_4300b_3_i.py
  covers:
  - BO-4300b-3-i
  asserts: The answer is refused, code NO_REPO, searched_from equals the start folder, exit 2.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_no_repo_refusal_leaves_folder_and_neighbours_unchanged
  file: unit_tests/build_orchestration/test_bo_4300b_3_i.py
  covers:
  - BO-4300b-3-i
  asserts: A recursive listing of the folder and its parent is identical before and after.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_two_candidate_projects_are_refused_as_ambiguous
  file: unit_tests/build_orchestration/test_bo_4300b_3.py
  covers:
  - BO-4300b-3
  asserts: From a folder containing shop and blog the answer is refused, code AMBIGUOUS_REPO, candidates
    naming both, exit 2.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_ambiguous_refusal_creates_nothing_in_either_project
  file: unit_tests/build_orchestration/test_bo_4300b_3.py
  covers:
  - BO-4300b-3
  asserts: Neither project gains a branch, a landing-place entry or a lock file.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_naming_the_project_resolves_ambiguity
  file: unit_tests/build_orchestration/test_bo_4300b_3.py
  covers:
  - BO-4300b-3
  asserts: The same request with --repo-root shop is answered ok with a clone of shop.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
- name: test_ticket_04_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300b_1_i.py
  covers:
  - BO-4300b-1
  angle: reachability
  surface_invoked: python <install-root>/.leafcutter/scripts/worktree.py ensure --kind scratch --slug
    <s> run from each BO-4300b-1 starting folder (CLI via subprocess)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- ORDER (b-1 it_requirements): --repo-root; else parent of `git rev-parse --path-format=absolute --git-common-dir` from cwd; ... A workspace identifies its project ONLY through the maker's marker; landing-place position is never a resolution step. Forbidden: anchoring on `__file__`, reusing `templates/scripts/commit_guardian/_resolve_root.py` (KI-CG-20260925). Per 01 architect-review, add a test that the new resolver and `_resolve_root.py` agree on ordinary (non-forbidden) cases.
- MOVE `resolve_repo_root`, `landing_place`, `layout_for`, `derive_config_path`, `_read_top_level_packages` out of `worktree_git.py` into `templates/scripts/worktree_layout.py`.
- CARRIED FINDING (01 pr-reviewer 02:15 H-2, left as a KNOWN LIMITATION docstring): `derive_config_path()`'s `top_level_packages` prefix stripping can never fire for real input (it only ever tests `.claude`/`.gemini`/... against package names) and it never searches above `repo_root`, so in the self-hosted layout (leafcutter-ai nested inside a consumer) it cannot find the consumer's `.claude/skills_config.json`. BO-4300b-2 requires 'shop's install inside the workspace is built with shop's own derived config': fix the derivation for the consumer/self-hosted layout, delete the KNOWN LIMITATION note, and amend ADR-018 Amendment 1 A1.3 (`docs/architecture/adrs/worktree-maker-amendment-1-2026-09-27.md`) to state the rule that actually ships (hence requires_adr: true, adr-author needed).
- REFUSALS: NO_REPO names `searched_from` (the failed run changed `resolve_repo_root()` to return `(Path|None, searched_from)` and updated three call sites -- 14 python-coder); AMBIGUOUS_REPO lists every candidate, never first-match (the `check_workspace_setup_permission.py` behaviour is not reproduced; its own search is removed in ticket 14); a refusal during resolution writes nothing.
- LANDING PLACE -- Q5 DECIDED (user, 2026-09-28): workspaces live in a SIBLING folder per project, `<parent-of-project>/<project-dir-name>-worktrees/`, each at `<kind>/<slug>` for its canonical identity (Q4, ticket 06). This replaces today's `<workspace>/worktrees/<slug>` (dev) and `<consumer>.parent/worktrees/<slug>` (consumer) rules: implement the ONE rule in `templates/scripts/worktree_layout.py` (the `landing_place` this ticket moves out of `worktree_git.py`), derived only from the resolved main checkout. It applies to the package's own dev layout too (leafcutter-ai -> `<parent>/leafcutter-ai-worktrees/`). Nothing is written inside the project and no ignore entry is added.
- LANDING-ROOT OVERRIDE (Q5): `--landing-root P` on ensure, locate, list, verify and remove (parsed in `worktree.py`, applied through `worktree_layout.py`; remove/list in `worktree_admin.py`). Validated BEFORE anything is written: absolute folder outside the project's working tree, not inside an existing workspace or another git repository, creatable/writable -- otherwise USAGE (exit 64) naming the broken rule. Never read from an environment variable or config, never remembered. Ticket 01's `test_every_route_workspace_lands_in_the_one_landing_place` stays green (it asserts a shared parent only); the exact location is asserted by the new BO-4300b-2 / b-2-i tests below. Check that ticket 02's fixtures in `_workspace_maker_fixtures.py` do not hard-code `<parent>/worktrees/` -- if they do, that is a ticket 02 change, not a local edit.
- ADR: the adr-author amendment to ADR-018 Amendment 1 (`docs/architecture/adrs/worktree-maker-amendment-1-2026-09-27.md`) also records the Q5 landing root and override, superseding the `worktrees/<slug>` folder name of fixed decision 1.
- Q6 DECIDED (user, 2026-09-28): `leafcutter-ai/.leafcutter/` must not exist; its deletion and build.py's refusal are ticket 14's (BO-4300f-2). BO-4300b-2-ii here still plants a stale inner copy in its fixture -- the resolver must never read any install copy, whether or not the real one is gone.
- STARTING POINT (re-verify): `git show refs/wip/bo4300-attempt1:unit_tests/build_orchestration/test_bo_4300b_3_i.py` and the `resolve_repo_root` hunk of `git show refs/wip/bo4300-attempt1 -- templates/scripts/worktree_git.py`.
- FILE-SIZE RATCHET: `templates/scripts/worktree.py` is at ~393 of 400 counted lines and `templates/scripts/worktree_git.py` near its limit (01 python-coder sign-off). Every addition therefore goes into the NEW module this ticket owns (see files_touched); the two core files are touched only to move code out and to wire the new module in. A new module needs its own NAMED deploy entry in `scripts/build_phases_script_deploy_standalone.py` and `scripts/build_deploy_manifest_helpers.py` (KI-TQ-004: no second tracked copy; the maker is deployed to `<install-root>/.leafcutter/scripts/<name>`, not `<install-root>/scripts/`, per 01 test-writer/python-coder).
- ANSWER TABLE: the status/code/exit table is owned by ticket 03 (BO-4300c-2 declares the full code enum). Do not add codes locally; if a code is missing from BO-4300c-2 it is a contract change, not a local edit.
- PROOF: tests run the DEPLOYED maker through ticket 02's locator (`unit_tests/build_orchestration/_workspace_maker_fixtures.py`), as a subprocess, against real temp repos with a real bare hub; no mock of git, no import of the maker module, never spawn `scripts/build.py`. Pin `newline="\n"` on fixture writes and isolate GIT_CONFIG_GLOBAL/GIT_CONFIG_NOSYSTEM (the CRLF drift found on 04 in the failed run). Use `AC_ENFORCE_STRICT=1` to see a genuine red baseline (the AC-enforcement plugin otherwise downgrades not-done-AC failures to xfail).
- HOOK HYGIENE (lessons from ticket 01): DECISION HISTORY entries need `HH:MM` and the `(#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/NN)` tail-tag on the entry's FIRST line; run `check_documentation.py` with NO `--file` flag (staged mode) before commit; run `check_doc_length.py` on every doc touched (300-line ratchet); stage every file in files_touched (01 shipped an ADR edit unstaged). Commits never spelled `git -C <path> commit`.
- SCOPE: the epic worktree is shared by every ticket. Edit only files_touched. If the fix needs another file, stop and get this ticket updated (CLAUDE.md TICKET MANDATE); the failed run stalled on exactly this (tickets 04, 14, 46, 59).

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300b-1-i**

- Starting inside a workspace resolves to the project it was made from (see BO-4300b-1); the new workspace's base is the hub's main tip, never the current workspace's HEAD or branch.

**BO-4300b-1**

- Project resolution is performed by the separate resolver module delivered by BO-4300a-1 (duplication audit C4; KI-CG-20260925-shared-root-resolver-accepts-non-repo-workspace-parent), in exactly this order: (1) --repo-root when given; (2) otherwise the parent of `git rev-parse --path-format=absolute --git-common-dir` run from cwd -- and when that folder holds the maker's own marker record, the project is the marker's recorded project_root, never the workspace clone itself; (3) otherwise a bounded search of cwd's immediate children, then of cwd's siblings, where a candidate counts only when git itself confirms it is a repository (an empty .git folder is not one), a maker-made workspace counts as its recorded project, and candidates are de-duplicated by resolved project before exactly one match is required (AMBIGUOUS_REPO with candidates on more than one); (4) otherwise NO_REPO naming searched_from.
- A workspace identifies its project ONLY through the maker's own marker record. The landing-place convention (inferring the project from a folder's position under worktrees/ or any other landing place) is NOT a resolution step. When a marker's recorded project_root is missing or is not a repository, the answer is NO_REPO naming the marker -- never the clone itself, never a folder guessed from the path.
- Forbidden in resolution: any anchor on the file location of the maker or resolver (__file__ or equivalent; the deployed copy lives outside every repository in the dev layout and inside the consumer project in the consumer layout, so either would give a cwd-independent wrong answer); any upward walk that accepts a folder because ".git exists" or "CLAUDE.md exists" (the dev-layout workspace parent has both and is not a project); any caching of an answer (module global, file, environment) -- every call recomputes from its own inputs; and any reuse, import, wrapping or copy of templates/scripts/commit_guardian/_resolve_root.py, which does all three.
- The landing place is derived from the resolved project only, never from cwd (F3). git is run with its working directory set to the target, or with -C <path> for verbs other than commit only; a commit is never spelled `git -C <path> commit` (KI-CG-20260925-commit-delegation-hook-misses-git-dash-c).

**BO-4300b-2-i**

- Q5 (DECIDED user 2026-09-28): each project's landing root is its own sibling folder, <parent>/<project-dir-name>-worktrees/, so shop's and blog's alpha land in different folders by construction. The marker still carries project_root and locate/list filter by it, so a shared explicit --landing-root override cannot mix them either: a request whose location already holds another project's workspace is refused OCCUPIED (occupant kind other-project, BO-4300d-3) and that workspace is left untouched.

**BO-4300b-2-ii**

- Resolution never consults any installed copy's location or contents, including a stale gitignored install inside the package repository. Q6 (DECIDED user 2026-09-28): leafcutter-ai/.leafcutter/ must not exist -- it is deleted and build.py refuses to build into the package repository unless an explicit --target-dir is given (BO-4300f-2, ticket 14). This record does not rely on that deletion: its tests still plant a stale inner copy in the fixture, because any adopter project can carry one and the outcome must not depend on it.
- The install inside the workspace comes from the workspace's own build, never copied or linked from any existing install tree.

**BO-4300b-2**

- Consumer layout (the maker deployed in a folder outside shop's version history) resolves shop by the BO-4300b-1 order, never from the maker's own location (F11, KI-ACD-004).
- LANDING ROOT (Q5, DECIDED user 2026-09-28): the landing place is ONE rule owned by the maker (templates/scripts/worktree_layout.py): landing root = <parent-of-project>/<project-dir-name>-worktrees/, where the project is the resolved main checkout (BO-4300b-1) -- never cwd, never the maker's or any install's location. Each workspace lands at <landing-root>/<kind>/<slug> for its canonical identity (Q4, BO-4300a-2). The same rule holds in the consumer layout and in the package's own dev layout (leafcutter-ai -> <parent>/leafcutter-ai-worktrees/); layout is still reported as 'dev'|'consumer'. Nothing is created inside the project's working tree and no ignore entry is written, so tools and tests that scan the project never see a clone.
- LANDING-ROOT OVERRIDE (Q5): only an explicit --landing-root P argument overrides the rule -- never an environment variable, a config setting or a remembered value. The maker validates it before writing anything: it must resolve to an absolute folder outside the project's working tree, not inside any existing workspace, not inside any other git repository, and creatable and writable; an invalid override is a usage error (status error, code USAGE, exit 64) naming the rule it breaks, and nothing is written. locate, list, verify and remove apply the same rule and accept the same override; a workspace made under an override is found only when the same override is given.
- The landing rule is stable across requests and keeps projects apart (BO-4300b-2-i).
- shop's install inside the workspace is built from the workspace's own contents with shop's own derived config.

**BO-4300b-3-i**

- NO_REPO refusal names searched_from; the maker creates no folder, lock or file anywhere before resolution succeeds.

**BO-4300b-3**

- More than one candidate project -> refused AMBIGUOUS_REPO whose candidates list every one found; never the first match (check_workspace_setup_permission.py's first-match behaviour is not reproduced).
- A refusal made during resolution writes nothing: no landing place, lock, branch or marker in any candidate.
- Naming the project (--repo-root) resolves the ambiguity.

## Agent Contracts

### python-coder

- [ ] AC-1: BO-4300b-1-i -- Starting inside another workspace never nests the new one there or roots it on that work
- [ ] AC-2: BO-4300b-1 -- The same request from any folder in or around the project gives the same workspace
- [ ] AC-3: BO-4300b-2-i -- Two projects in the same folder never share or collide on a workspace
- [ ] AC-4: BO-4300b-2-ii -- An out-of-date installed copy inside the project does not change which project is found
- [ ] AC-5: BO-4300b-2 -- A project that installed the tools gets its workspaces the same way
- [ ] AC-6: BO-4300b-3-i -- Started where no project can be found, the request is refused and says where it looked
- [ ] AC-7: BO-4300b-3 -- When more than one project could be meant, the request is refused and names them

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300b-1-i per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300b-1 per `## Test Requirements`
- [ ] AC-3: red tests for BO-4300b-2-i per `## Test Requirements`
- [ ] AC-4: red tests for BO-4300b-2-ii per `## Test Requirements`
- [ ] AC-5: red tests for BO-4300b-2 per `## Test Requirements`
- [ ] AC-6: red tests for BO-4300b-3-i per `## Test Requirements`
- [ ] AC-7: red tests for BO-4300b-3 per `## Test Requirements`

**Delivers to:** python-coder (red baseline).

### Expects From

- **BO-4300b-1-i <- BO-4300b-1** (this ticket): Resolution from inside a workspace reaches the main project.
- **BO-4300b-1 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): ensure CLI; resolution is internal to the maker.
- **BO-4300b-2-i <- BO-4300b-2** (this ticket): Per-project landing-place rule.
- **BO-4300b-2-ii <- BO-4300b-1** (this ticket): Project resolution order independent of any install copy.
- **BO-4300b-2 <- BO-4300b-1** (this ticket): Project resolution order independent of the maker's location.
- **BO-4300b-3-i <- BO-4300b-1** (this ticket): Resolution ending in NO_REPO.
- **BO-4300b-3 <- BO-4300b-1** (this ticket): Resolution search requiring exactly one candidate.

### Delivers To

- none

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No production data; developer repositories are protected by the ticket 02 session guard.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
