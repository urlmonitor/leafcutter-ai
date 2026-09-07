---
title: "The reachability census counts hooks on disk, not just the ones the registry names, and holds back six that turned out to be broken rather than switching them on"
date: "2026-09-07"
time: "18:48"
type: manual
components: 
  - commit_guardian
  - build_pipeline
summary: "Fixed a blind spot in the commit-safety checks so the gate that hunts for unregistered checks can no longer miss one itself, and correctly refused to switch on six checks that looked unregistered but turn out to be unfixably broken."
description: "One commit (fd02d53d9) rewires check-hook-trigger-reachability to compare against a new disk-side census (_hook_trigger_census.py) instead of only the registry's own list, closing a blind spot where a gate script nothing registered was invisible to the very check meant to find it. Of 19 previously-unwired scripts the census surfaced, 13 were verified as real, working gates and registered; 6 were found to error out under real pre-commit invocation and were deliberately left off, recorded as broken-and-tracked rather than switched on to make the count reach zero."
commits: 
  - fd02d53d9
---

## Entry

`check-hook-trigger-reachability` exists to catch a gate script that nothing invokes. Until this change, it walked only the hooks the registry named — so a script that nothing had ever registered was structurally invisible to the one check built to find exactly that. A guard whose input is the registry cannot see what the registry omits.

A new module, `_hook_trigger_census.py`, supplies the missing disk side: a recursive listing of every `check_*.py` under the gate directory, with identity tracked by position rather than bare filename (so `hooks/check_ac_limits.py` and `check_ac_limits.py` are never conflated as the same script). The check now compares that census against the entries the generated, commit-time configuration actually executes. Anything on disk that no entry invokes is named and fails the run.

### The first attempt at fixing the registry was wrong, and catching that is the point

The AC required the real registry to come out clean in the same change. The first pass did that by registering all 19 previously-unwired scripts it found as live gates — taking the registered count from 61 to 80, unreferenced down to 0, every test green.

Then each of those 19 was probed the way pre-commit actually invokes it — positional staged filenames, since all were wired `files: null` with no `always_run`. Six of them cannot be invoked at all: `check-ac-coverage`, `check-debug-scripts`, `check-docstrings`, `check-documentation`, and `check-v2-ac-store-alignment` reject positional arguments outright (exit 2), and `check-doc-coverage` raises a `NameError` before it even reaches argument parsing (exit 1). Any one of these, switched on, blocks every commit in this repository and in every consumer install.

So the census was right that nothing invokes these six scripts. The inference that they should therefore be switched on was wrong — for these six, the reason nothing invokes them is that they cannot be invoked. Turning them on to make the "unreferenced" count hit zero would have shipped a self-inflicted outage, not a fix.

The final state keeps the two facts separate instead of blurring them: 13 of the 19 are registered as real gates (61 to 74 total), each verified exit 0 under real invocation. The other six are recorded in the declared-non-gate register as broken and tracked — not treated as legitimate non-gates — with each entry naming its actual failure and stating plainly that it is meant to become a gate once fixed. ACs are being authored for that follow-up work. A register that quietly absorbs broken scripts just to make a count read zero would be worse than the problem it's supposed to solve.

### Also worth noting

- **The newly-registered `check-file-size` caught this very commit, twice**, on the first attempt to commit it: a test module that had grown while already over its line limit, and a production module sitting at 424 lines against a 400 cap. Both were fixed by splitting the file, not by trimming comments or skipping the check — the gate proving itself on the commit that switched it on is the outcome this change was aiming for.
- **Two pre-existing, unrelated hooks were skipped for this commit only**: `check-product-truth-validate` and `check-product-truth-generate`. Both fail identically against a clean checkout of `main` with zero product-truth files touched by this change, so they are already failing repo-wide, independent of anything here.
