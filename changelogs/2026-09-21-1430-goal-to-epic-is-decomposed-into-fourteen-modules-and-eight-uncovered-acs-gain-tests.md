---
title: "goal_to_epic.py is decomposed into fourteen modules, and eight uncovered ACs gain their first tests"
date: "2026-09-21"
time: "14:30"
type: manual
components:
  - ac_driven_dev
  - ac_store
  - build_pipeline
  - commit_guardian
  - build_orchestration
  - ticket_creation_pipeline
summary: "scripts/goal_to_epic.py goes from 2809 lines to 492, with its logic moved into fourteen sibling modules under scripts/ac_store/ that are each under the 400-line limit and each registered in AC_STORE_DEPLOY_MAP. Behaviour is preserved and proven so: a full run against copies of the real 4040-file AC store produces byte-identical ticket files, Master_Plan.md, and all 4040 AC YAMLs after target_epic stamping. The refactor also surfaced and fixed a live test defect — nineteen patch(\"goal_to_epic.X\") sites that a module split silently breaks, ten of which were passing while executing real subprocesses and a real Anthropic client. Alongside: eight previously-uncovered ACs gain their first tests (deliberately red), BP-900a's criteria are amended from an enumerated filename list to a derived import-closure property, and one new high-severity known issue is filed."
description: "Driven by hand at the user's direction across several sessions, on branch feature/goal-to-epic-decompose, rebased twice onto a fast-moving main. THE REFACTOR. scripts/goal_to_epic.py (the goal-AC to EPIC-folder batch orchestrator) was 2809 physical lines against check-file-size's 400-line .py limit; it is now 492 physical / 186 by the hook's own counting rule, which excludes docstrings and block comments. Its logic lives in fourteen new siblings under scripts/ac_store/: epic_ac_phases, epic_ac_store, epic_assembly, epic_cli, epic_dependencies, epic_errors, epic_master_plan, epic_naming, epic_phases, epic_pipeline, epic_readiness, epic_readiness_gate, epic_runtime, epic_tickets — largest 393 lines, all under the limit. THE DEPLOY CONSTRAINT, which shaped the design: build_ac_store deploys goal_to_epic.py FLATTENED into <output_root>/scripts/ac_store/, so the siblings were placed at scripts/ac_store/epic_*.py precisely so source and deployed names match 1:1 and the file's existing _sibling_dir dual-layout guard resolves them unchanged. A scripts/goal_to_epic/ package directory — the obvious-looking option — would not have survived the flattening. All fourteen are registered in AC_STORE_DEPLOY_MAP (which main moved from build_phases.py to build_phases_ac_store.py mid-flight, in PR #806). That registration is load-bearing and was proven so rather than assumed: deleting one deployed module makes the deployed entry point die with ModuleNotFoundError: No module named 'epic_naming', and rebuilding restores exactly that file from the manifest. BEHAVIOUR PRESERVATION. Verified three ways. (1) Test delta against a baseline built at the branch point: zero. (2) A --dry-run of the real CLI: byte-identical stdout and stderr, for both the source and the deployed copy. (3) A FULL run (not just dry-run) against copies of the real 4040-file AC store: 8 ticket files plus Master_Plan.md byte-identical, and all 4040 AC YAMLs byte-identical after target_epic stamping and implemented_by rewriting. ruff clean; check_complexity clean at max 12 against a threshold of 15. THE DEFECT THE REFACTOR EXPOSED. patch(\"goal_to_epic.X\") does not survive a module split: X is now defined AND called inside its own sibling and resolved through that module's globals, so the facade re-export is a different binding. Nineteen such sites existed; nine failed outright once the split landed, and TEN had been passing while silently running the real code — test_bo_2600a_5.py spawning real generate_ticket_from_ac.py subprocesses, test_concise_epic_name.py reaching for a real Anthropic client. All nineteen retargeted at the owning modules; no assertion deleted, weakened or skipped; all # covers: tags intact. Those four files went from 9 failed / 37 passed in 121.85s to 46 passed in 0.69s. TESTS FOR EIGHT UNCOVERED ACs. Staging AC records for the doc_links rewiring below surfaced a latent check-ac-schema violation: thirteen ACs were change_target: code with a coder assigned_agent and no test_spec — pre-existing, and structurally unreachable until now because that hook validates only files present in the commit's index. Rather than widen a hook skip, test contracts were authored for all thirteen (five describing tests that already existed, eight forward specifications), and tests were then written for eight of them: TKT-500f-5, -5-i, -6, -6-i, -6-ii, -6-iii-a, ACD-1200a-10-i, ACD-1200f-2-i. These tests are DELIBERATELY RED — 19 failed / 9 passed for the TKT set and 2 failed / 5 passed for the ACD set under AC_ENFORCE_STRICT=1. Non-strict they read 9 passed / 19 xfailed, exit 0, because pytest_ac_enforcement masks failures for ACs that are not done; the strict run is the only honest reading and is the one recorded here. None of the new tests use patch() anywhere — they build real AC stores with yaml.dump and invoke real entry points, specifically so they cannot go stale the way the nineteen above did. A three-module shared harness (_tkt_500f_fixtures / _tkt_500f_generators / _tkt_500f_support, 686 lines total) was split three ways because a single file breached the same 400-line limit, which exempts no test files. AC-STORE AND DOC WIRING. 29 AC records had doc_links retargeted at the owning sibling modules (append-only, keeping the goal_to_epic.py facade entry with a relevance note), three scalar reference_file_path values rewritten, two implemented_by lists appended to, and stale line citations retargeted. BP-900a's criteria were amended by the business-analyst from an enumerated filename list to a derived transitive-import-closure property: the old form would have certified a broken install, since it presence-checked goal_to_epic.py alone and that file now imports fourteen siblings at module scope. Every clause of the new criteria maps to a function that already exists (extract_script_path_refs, compute_intra_package_closure, find_uncovered_closure_dependencies, build.py's _check_intra_package_closure_guard). Stale line citations in docs/known-issues/ac-driven-dev/ (five per-issue files) and docs/known-issues/build-orchestration/open-high-ki-bo-014.md were retargeted at the modules that now own the behaviour; docs/how-to/goal-to-epic.md's prerequisite list, which had become incomplete in a way that would let a reader deploy an unrunnable install, now points at AC_STORE_DEPLOY_MAP as the authoritative set; and docs/architecture/components/template-compiler.md's claim that goal_to_epic.py and build_ac_mode_detection.py deploy from templates/scripts/ was corrected — neither has ever lived there. KI-BO-014 was verified in code and marked RESOLVED with two residuals recorded: its root cause (two entry paths with divergent inline depends_on wiring) is closed by this change, which routes both through one epic_phases helper, but _apply_epic_backrefs still takes warn_unrelativisable=True for run() and False for build_epic_from_ids(), so both routes write a non-portable back-reference in the same condition while only one warns; and test_bo_2600a_5.py still exercises only one entry path. Notably TKT-016 and TKT-017 had each fixed a SYMPTOM earlier while adding a second inline copy, so the root cause survived both fixes. NEW KNOWN ISSUE. KI-CG-20260914-ac-hooks-resolve-root-from-cwd (high): all six AC commit-guardian gates derive BOTH their project root AND their staged file set from the current working directory, so run from outside the worktree they validate zero files and exit 0 — a pass-shaped result from a run that checked nothing. Verified by negative control. It bit three separate agents in one session, because this workspace's default cwd is the untracked build-output parent, which is not a git repository, so the broken invocation is the DEFAULT one. The fix already exists in the package: _resolve_root.find_project_root() prefers git rev-parse --show-toplevel and is already imported by 31 hooks; the six AC gates import none of it. HOOK SKIPS, both user-authorized and both recorded on the commits that use them: check-file-size, because build_phases.py was already 6.7x its limit when the fourteen mandatory manifest entries had to be added and the ratchet refuses any net growth on an already-over file (main has since split that file, which may make this skip unnecessary); and check-doc-length, because two known-issues registers grow and the gate flipped from warn to a blocking growth ratchet on 2026-09-14. NOT VERIFIED, stated plainly: the full pytest unit_tests tests suite was never run end-to-end on either side of the comparison — roughly six hours serially, and long runs were repeatedly killed under concurrent load. An explicit blast-radius set was used instead (719 passed, 3 skipped, 21 xfailed, 0 failed after the final rebase); unit_tests/agents, knowledge and workflows were run on neither side. No third-party consumer install was simulated beyond this worktree's own .leafcutter/. While fixing the commit-guardian index's counts for the new entry, main's own header was found stale — it claimed 67 open and 6 resolved against 66 and 7 actual — and is corrected here to the branch's true 67 open / 7 resolved."
commits:
breaking: false
---

## Entry

`scripts/goal_to_epic.py` — the goal-AC → EPIC-folder batch orchestrator — was
**2809 lines** against a 400-line limit. It is now **492** (186 by the
`check-file-size` hook's own rule, which excludes docstrings and comments),
with its logic in **fourteen sibling modules** under `scripts/ac_store/`.

### The constraint that shaped the design

`build_ac_store` deploys `goal_to_epic.py` **flattened** into
`<output_root>/scripts/ac_store/`. So the siblings were placed at
`scripts/ac_store/epic_*.py` precisely so source and deployed names match 1:1
and the file's existing `_sibling_dir` dual-layout guard resolves them
unchanged. A `scripts/goal_to_epic/` package directory — the obvious-looking
option — would not have survived the flattening.

All fourteen are registered in `AC_STORE_DEPLOY_MAP`. That registration is
load-bearing, and was proven rather than assumed: deleting one deployed module
makes the deployed entry point die with
`ModuleNotFoundError: No module named 'epic_naming'`, and rebuilding restores
exactly that file.

### Behaviour preservation

A **full** run — not just `--dry-run` — against copies of the real 4040-file AC
store produced byte-identical ticket files, `Master_Plan.md`, and all 4040 AC
YAMLs after `target_epic` stamping. Test delta against a branch-point baseline:
zero. `ruff` clean.

### The defect the refactor exposed

`patch("goal_to_epic.X")` does not survive a module split — the name is now
defined *and called* inside its own sibling, resolved through that module's
globals, so the facade re-export is a different binding.

Nineteen such sites existed. Nine failed outright once the split landed. **Ten
had been passing while silently executing the real code** — real
`generate_ticket_from_ac.py` subprocesses, a real Anthropic client. All
nineteen retargeted at the owning modules; no assertion deleted or weakened.
Those four files went from 9 failed / 37 passed in 121.85s to **46 passed in
0.69s**.

### Eight uncovered ACs gain their first tests

Staging AC records surfaced thirteen ACs that were `change_target: code` with a
coder `assigned_agent` and no `test_spec` — pre-existing, and structurally
unreachable until now, because `check-ac-schema` validates only what is in the
commit's index. Test contracts were authored for all thirteen rather than
widening a hook skip, and tests written for eight.

**These tests are deliberately red**: 19 failed / 9 passed (TKT) and 2 failed /
5 passed (ACD) under `AC_ENFORCE_STRICT=1`. Non-strict they read
`9 passed, 19 xfailed, exit 0` — `pytest_ac_enforcement` masks them completely,
so the strict run is the only honest reading.

### Also in this change

- **`BP-900a`'s criteria** amended from an enumerated filename list to a derived
  import-closure property. The old form would have certified a broken install.
- **`KI-BO-014`** verified in code and marked **RESOLVED**, with two residuals
  recorded. Its root cause survived two earlier symptom fixes, each of which
  added a second inline copy.
- **`KI-CG-20260914-ac-hooks-resolve-root-from-cwd`** filed (high): all six AC
  gates take their root *and* their file set from the cwd, so from the wrong
  directory they validate zero files and exit 0.

### Not verified

The full `pytest unit_tests tests` suite was never run end-to-end on either
side — roughly six hours serially, and long runs were repeatedly killed under
load. An explicit blast-radius set was used instead (719 passed, 0 failed after
the final rebase). `unit_tests/agents`, `knowledge` and `workflows` were run on
neither side. No third-party consumer install was simulated.
