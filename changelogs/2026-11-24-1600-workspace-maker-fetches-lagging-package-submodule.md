---
title: "The workspace maker fetches the package submodule even when the main checkout's copy is out of date"
date: "2026-11-24"
time: "16:00"
type: manual
components:
  - worktree_manager
  - build_orchestration
summary: "The maker only fetched the leafcutter submodule into a new workspace when the main checkout's copy of that submodule carried the full package signature (scripts/build.py and templates/scripts/worktree.py). A main checkout whose submodule lags its recorded pin can sit at a commit without templates/scripts/worktree.py. DIAGraph's did, at dcd93781 against pin 67a7b443. In that case the fetch was skipped, and every workspace was refused BOOTSTRAP_FAILED 'scripts/build.py is absent' again. The gate now asks only that the main copy holds scripts/build.py. The fetched copy in the workspace is still checked against the full signature."
description: "BO-4300b-2-iii (amended it_requirement + new boundary test). templates/scripts/worktree_install.py init_package_submodule. New test test_submodule_is_fetched_when_the_main_checkouts_copy_predates_the_package_signature in unit_tests/build_orchestration/test_bo_4300b_2_iii.py."
commits:
breaking: false
---

## Entry

In projects that keep leafcutter as a submodule, asking for a new workspace could still fail
with "scripts/build.py is absent" when the project's own copy of leafcutter was out of date.
The workspace maker now fetches leafcutter into the new workspace in that case too.
