---
title: "Five audit methods each missed a declared-deploy site; the sixth finds all nine"
date: "2026-08-31"
time: "19:57"
type: manual
components: 
  - build_pipeline
summary: "Closed the remaining gaps in the build's missing-source safety check by converting the last four places where a deleted source file would have shipped a silently incomplete install, and recorded why five different search techniques each missed one before a more thorough method found every remaining site."
description: "2 commits finishing BP-900g-9 (n_location_rule: all), which landed on main converting five of nine declared-deploy sites onto the existing record_deploy_failure / raise_if_deploy_failures / DeployDeclarationError accumulator. This converts the remaining four: build_agent_support_scripts' AGENT_SUPPORT_SCRIPT_DIRS loop, build_ac_store_docs (a bare print(\"[WARNING] ...\") rather than _log.warning, invisible to a warning-grep audit), build_product_truth's deploy_groups loop (its glob applies only within each declared subdir, so the subdir itself is a declared entry), and build_build_orchestration_scripts' own source-directory check (found last, after review; its own record_deploy_failure call for a sibling helper reuses the enclosing function's name, so a phase-name search reads it as already covered).

Five independent audit methods each missed at least one site: a search framed on `continue`-shaped loops (missed a `return 0`), a grep keyed on `_log.warning` (missed the bare `print`), a \"glob-shaped, out of scope\" judgement (missed build_product_truth), a `git stash` comparison unable to distinguish stale build output from a real defect, and phase-name matching (missed the ninth). Reading every build_* and _deploy_* function and asking what it does when its named source is absent found a site every time it was used, and is now recorded as the required method for this file. Two independent implementations of this AC, run in separate sessions with different exception names, converged on the same first five sites and missed the same remaining three -- replication, not carelessness. The ninth site was found by review on a branch where the full suite was already 4541 passed, 0 failed; no test could have caught it.

Coupled fixture fix: _build_synthetic_full_package() copied templates/, scripts/ and config/ but never docs/, so once build_product_truth went fail-closed, 19 tests building against it aborted. Fixed by deriving the extra directories from build_phases.py instead of hardcoding the path back in, since hardcoding is what let the fixture go stale in the first place.

Two known issues recorded: KI-BP-20260831-0728 (the hook-script integrity check strips the hooks/ segment off each declared entry, so three real scripts are reported missing on every build -- warning-only, which trains reviewers to skim it) and KI-BP-20260831-1014 (seven declared sources are still skipped with no log at all; corrected mid-range because its own scope boundary -- 'does it warn' -- had itself gone unaudited for coverage before being defended on principle).

Not fixed, by design: the seven silent-skip sites remain open, and build_template_standalone_scripts is filed as a further candidate -- its docstring names setup_ticket_worktree.py as the declared deliverable but its glob would drop that file with no warning and no failure.

Verified: full suite 4542 passed, 7 skipped, 6 xfailed, 0 failed; ruff clean; build.py --target-dir <scratch> exits 0 with deployed artefacts confirmed present in the output tree; every new test verified red-then-green by stash isolation."
commits: 
  - ed7cfdd3b
  - 39f82aa85
breaking: false
---

## Entry
