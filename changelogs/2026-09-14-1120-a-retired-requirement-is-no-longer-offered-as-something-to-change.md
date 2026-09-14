---
title: "A retired requirement is no longer offered as something to change"
date: "2026-09-14"
time: "11:20"
type: manual
components:
  - ac_store
  - guardrail_engine
  - build_pipeline
summary: "The cross-reference audit's candidate selection read only work_status and implemented_by, never status, so a record retired to deprecated stayed an eligible backfill candidate — retirement changes neither field it read. Fixing it required splitting the 557-line module to satisfy check-file-size, which in turn exposed that a per-file ratchet freezes any central registry once it crosses its limit. Also adds the two fresh requirement trees the tool and the check-test-ac-tags gate had never had."
description: "scripts/ac_store/cross_reference_audit.py selected backfill candidates by asking whether a record was unfinished and unlinked to code, and never whether the requirement was still in force. Retirement changes neither field, so a record set to status: deprecated kept work_status: todo and implemented_by: [] and remained a live candidate for the --apply backfill. This was not hypothetical: PR #768 retires the ACD-800 tree to eleven deprecated records, every one of which keeps both fields eligible, so on the day it lands all eleven would become candidates for the very tool ACD-800 specified. The fix requires a new _RETIRED_AC_STATUSES membership to be absent, treating an absent status as active exactly as the existing code already treats an absent work_status as todo; it narrows the candidate set and cannot widen it. The test makes the negative arm load-bearing — two records identical in every field the selector reads, differing only by status, asserting the retired one absent AND the active one present, because absence alone would pass against a function that returns nothing. It was mutation-proven twice, the second time unintentionally when a parallel session's stash pop removed the fix from the worktree and the test went red again unprompted. Landing the fix required a refactor: check-file-size refused it because the module stood at 557 content lines against a 400 limit, so the module was split along five cohesive seams (cross_reference_audit.py 557 to 177, plus _xref_ac_store, _xref_tickets, _xref_matching, _xref_report and _xref_apply, all under 400), with every function moved verbatim and the public import surface preserved because ACS-900e names this module's traceability resolution as a contract other tooling must reuse. All five new modules are registered in build_phases.py's deploy map and the deployed copies were verified to run from a scratch build target, since a module imported but not deployed raises ModuleNotFoundError in consumer installs while passing every local test. Registering them cost six lines in build_phases.py, which is itself 2681 content lines against the same 400 limit, so the ratchet refused those six lines too — complying with the rule on one file forced violating it on another. That was resolved with a single sanctioned SKIP, reasoned in the commit, and the underlying problem filed as KI-CG-20260914-ratchet-freezes-central-registries. Two fresh requirement trees are also included: ACS-1600 governs the cross-reference audit tool, which had no live requirement at all because its entire governing tree is being retired while the code ships into every consumer project, and takes the position that the --apply path should lose its work_status write entirely rather than narrow it; GE-128 governs the check-test-ac-tags gate, which has never run and sits one absent config key away from blocking 5,566 untagged test functions."
breaking: false
---

## Entry

### The defect

Candidate selection asked two questions — is this unfinished, is it unlinked to code — and never asked whether the requirement was still **in force**. Retirement changes neither field it read, so a retired record stayed eligible.

| field | after retirement | selector reads it? |
|---|---|---|
| `status` | `active` → `deprecated` | **no** |
| `work_status` | unchanged (`todo`) | yes |
| `implemented_by` | unchanged (`[]`) | yes |

PR #768 retires the `ACD-800` tree to **eleven** deprecated records. All eleven would have become candidates for the very tool `ACD-800` specified.

### The test, and why the negative arm carries it

Two records identical in every field the selector reads, differing **only** by `status`. Asserts the retired one absent **and** the active one present. Absence alone would pass against a selector that returns nothing, or one dropping the record for an unrelated reason.

Mutation-proven twice — once deliberately, once when a parallel session's stash pop removed the fix and the test went red unprompted.

### The split, because the gate asked for it

`check-file-size` refused the fix: the module was 557 content lines against a 400 limit. It was split rather than skipped.

| file | content lines |
|---|---|
| `cross_reference_audit.py` | 557 → **177** |
| `_xref_ac_store.py` | 52 |
| `_xref_tickets.py` | 100 |
| `_xref_matching.py` | 137 |
| `_xref_report.py` | 66 |
| `_xref_apply.py` | 79 |

Every function moved verbatim. The public import surface is preserved — `ACS-900e` names this module's traceability resolution as a contract other tooling must reuse, so it is an interface, not private detail. All five modules are registered in the deploy map and verified running from a scratch build target.

### What the split exposed

Registering five modules costs six lines in `build_phases.py` — itself **2681 lines against the same 400 limit**. The ratchet refused those too. Complying with the rule on one file forced violating it on another, and not registering would have passed the gate while breaking every consumer install.

Resolved with one sanctioned `SKIP`, reasoned in the commit. The general problem — a per-file ratchet freezes exactly the registry files everything else must edit to register itself — is filed as `KI-CG-20260914-ratchet-freezes-central-registries`.

### Two requirements that did not exist

- **`ACS-1600`** — governs the audit tool, which had **no live requirement**: its whole governing tree is being retired while the code ships to every consumer. Takes a position: the `--apply` path should lose its `work_status` write entirely, not narrow it to a higher confidence band.
- **`GE-128`** — governs `check-test-ac-tags`, which has never run and is one absent config key away from blocking **5,566** untagged test functions.
