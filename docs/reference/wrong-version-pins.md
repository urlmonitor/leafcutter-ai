---
title: "Reference: Wrong-Version Pins"
description: "Lookup for the wrong-version pin store: when a name goes back to the preparer, the checks every pin passes before it is used, what each verdict row names, the kept manifests, and how an operator clears a pin."
type: reference
status: active
created: 2026-10-29
last_updated: 2026-10-29
components:
  - testing_quality
  - build_orchestration
related_docs:
  - docs/reference/wrong-version-runs.md
  - docs/architecture/adrs/ADR-079-wrong-version-pins-replay-replacements-per-work.md
  - docs/analysis/2026-10-23-the-wrong-version-gate-tests-a-different-guess-each-run.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261023-test-breaker-no-op-alterations.md
---

# Wrong-Version Pins

A pin is the replacement (`{path, old, new}`) a named wrong version was prepared with for one
piece of work. Later runs of that work apply the same replacement to the code as it then stands
instead of asking the preparer again (ADR-079). This page lists the checks a pin must pass before
it is used, and how a pin is cleared. Where pins live and why is in ADR-079; the result words of a
run are in [wrong-version-runs.md](wrong-version-runs.md). The problem pins solve is measured in
the [analysis page](../analysis/2026-10-23-the-wrong-version-gate-tests-a-different-guess-each-run.md).

## When a name goes back to the preparer (TQ-500g-1-xii)

`list --work-key` sends a name to the preparer only when one of three things is true; every other
owed name is rebuilt from its pin and its decision reads `pinned`:

| Trigger | Decision on the row |
|---|---|
| The work holds no pin for the name (a new name) | `prepared: not pinned` |
| The pinned old text no longer occurs exactly once in the current file | `re-prepared: target changed` (or another failed check below) |
| The name's wording changed beyond trim and case | treated as a new name: `prepared: not pinned` |

- **Lookup is by trim and case-fold only** (`_wvr_scope.norm_name`). A change of case or of
  surrounding spaces keeps the pin; a change of inner wording or punctuation does not. A name is
  never matched to a pin by entry position or similarity.
- **The row and the manifest carry the name as the requirement now spells it**, not as the pin
  stored it.
- **A pin no run owes any more is left in the store untouched.** Nothing but the operator's reset
  removes a pin.
- **A pin with several replacements** is judged in order, each against the result of the one
  before.

## Checks before a pin is used (TQ-500g-1-xiii)

Every pinned candidate is checked against the code as now written, in the plan step
(`scripts/build_orchestration/_wvp_plan.py`, checks in `_wvp_checks.py`), before the preparer is
dispatched and before any wrong version runs. The first failure wins, in this order:

| Order | Check | Reason on the row |
|---|---|---|
| 1 | Paths: the file is still in scope for that name, and passes the writer's path rules | `not in scope`, or the writer's own refusal wording |
| 2 | Old text occurs exactly once, each replacement against the result of the one before | `old text found N times`, or `target changed` when not found |
| 3 | The applied result differs from the file as written | `changes nothing` |
| 4 | The altered `.py` file executes as a module in a child interpreter | `did not load` |
| 5 | A test whose own entry names the candidate runs a changed line (one traced pytest run, at most) | `changes no line the tests naming it run` |

- **A pin that fails is neither applied nor dropped.** Its decision reads `re-prepared: <reason>`,
  the name goes to the preparer, and the earlier pin stays byte for byte as it was until a
  re-preparation passes every check and replaces it.
- **A re-preparation that cannot be made or also fails** reports the name unfinished with the
  failed check named first in its reason, never as caught or survived.
- **Check 4 never uses `git stash`.** It applies and puts back through the runner's journalled
  apply-and-put-back, so the file is byte for byte as written afterwards.
- **A pin that only fails in the run** (`did_not_load`, `not_applied`, `not_executed`) records
  `failed_check: {check, files_sha256}`. The next plan treats it as failing that check until the
  bytes of its files change.
- **A fresh preparation** (a name with no pin) is held to the same checks and becomes its pin only
  when it passes all of them. This is what refuses a pinned no-op, the round-III naive-chain
  survivor in the analysis page: checks 3 and 5.

## What each verdict row names, and the kept manifests (TQ-500g-1-xv)

Every verdict row carries three keys beside `test`, `wrong_version`, `result`, `blocking` and
`detail`, copied by the runner from that wrong version's own manifest entry (never derived):

| Key | Value |
|---|---|
| `alteration_id` | `sha256:` and 16 hex digits over the replacements alone, so a change elsewhere in the file keeps it and a different `new` text changes it; for "the fix undone", a hash over the base content it puts back |
| `source` | `prepared: not pinned`, `pinned`, `re-prepared: <check>`, or `fix undone` |
| `replacements` | the applied `{path, old, new}` list (null for "the fix undone") |

Rows of two runs of the same work compare directly: the same `alteration_id` means the same
alteration was judged.

**Earlier manifests are kept.** The write step's first action moves the manifest and copies an
earlier run left into `<git-dir>/leafcutter/work/<work-key>/history/<NNNN>/` (one more than the
highest number there), manifest first. A move that fails stops the step with no new manifest, and
never leaves the earlier manifest at the current path. The runner reads only the current path; it
never falls back to `history/`.
