---
title: "Commit Guardian — Pre-Commit Hook System"
description: "Pre-commit hook orchestration system that enforces code quality, ADR coverage, component integrity, and structural rules before every commit lands."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-08-31
components:
  - commit_guardian
  - git_vcs_operations
related_docs:
  - docs/architecture/adrs/ADR-038-commit-guardian-shared-change-set-derivation.md
  - docs/architecture/adrs/ADR-037-whole-collection-uniqueness-pass.md
  - docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/diagrams/c3-006-whole-collection-uniqueness-pass.md
  - docs/how-to/managing-pre-commit-hooks.md
related_code:
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py
  - templates/scripts/commit_guardian/check_adr_collision.py
  - templates/scripts/commit_guardian/_authored_change.py
  - templates/scripts/commit_guardian/check_contract_shrinking.py
  - templates/scripts/commit_guardian/check_doc_frontmatter.py
---

# Commit Guardian

## Overview

The Commit Guardian is the pre-commit enforcement layer for the leafcutter-ai package. It orchestrates a suite of independent hook scripts that run during `git commit`, blocking commits that violate structural, documentation, or code quality rules.

## Responsibilities

- Enforce component registry integrity (`check_components_integrity.py`)
- Verify ADR coverage for structural changes (`check_adr_coverage.py`)
- Validate documentation frontmatter on staged `docs/**/*.md` and ticket
  frontmatter on staged `tickets/**/*.md` (`check_doc_frontmatter.py`)
- Guard against contract shrinking in test suites (`check_contract_shrinking.py`)
- Enforce exception handling boundaries in Python code
- Check ticket sign-off parity between frontmatter and Sign-offs sections

## Entry Points

- `scripts/commit_guardian/run_hook.py` — dispatcher invoked by pre-commit
- `.pre-commit-config.yaml` — hook registration file
- `scripts/commit_guardian/commit_guardian.json` — configuration

## Design Principles

Each hook is an independent script that exits 0 (pass) or 1 (block). Hooks are fail-fast by default (`fail_fast: true` in `.pre-commit-config.yaml`). Advisory hooks always exit 0 regardless of findings.

## Merge-Aware Checks (Authorship, Not Operation, Is the Discriminator)

`check_contract_shrinking.py` and `check_doc_frontmatter.py` both narrow their
staged-file set during a merge (`MERGE_HEAD` present) so a check judges only
the merge author's own content, never work carried in verbatim from the
other line of development. A merge stages the entire incoming branch, so an
unscoped `git diff --cached` also names every file the *other* side ever
touched, which the merge author neither wrote nor can fix; naming that
carried-in work in an objection is the false-positive class this scoping
removes — the observed trigger was a 479-file mainline merge whose own change
set touched none of the files a check objected to. Both checks still run
their full inspection during a merge — a merge changes which content is
attributed to the author, never whether the author's content is inspected.
See AC `GE-120e-3-ii` (both checks' merge-scoping arms, plus the
no-skip-during-merge guarantee) under
`docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/`.

### Single Shared Source: `_authored_change.py` (`GE-120e-1`)

Before `GE-120e-1`, each check hand-implemented the same merge-scoping idiom
privately — `check_contract_shrinking.py`'s `_merge_scoped_paths()` and
`frontmatter_validators.py`'s `merge_scoped_md_paths()` — and each
independently fell back to the **unscoped** (whole-staged-tree) diff whenever
its own `git` call failed, silently re-widening the scope on exactly the
commits where `git` is under stress. Two independently-maintained
implementations of the same idiom can also drift apart, letting a merge
leave one check objecting to carried-in content while its sibling, computing
the same narrowing slightly differently, does not — a split verdict on the
same commit.

`templates/scripts/commit_guardian/_authored_change.py` closes both gaps
as one shared module both named checks now consume in place of their private
`git diff --cached` calls, per
[ADR-038](../adrs/ADR-038-commit-guardian-shared-change-set-derivation.md).
The module was renamed from `_resolve_change_set.py`/`get_change_set()`/
`ChangeSet` to its current name to honour a contract
`unit_tests/portability/test_ge_120e_4_i.py` (ticket 36, `GE-120e-4-i`) had
already established for it:

- `get_authored_change(cwd=None) -> AuthoredChange` derives, once per
  resolved `cwd` per process (memoised — the pre-commit latency budget
  forbids one `git` invocation per consuming check), the paths differing
  from `MERGE_HEAD` during a merge (or every staged path otherwise),
  together with the `states` provenance — the commit-ish(es) the derivation
  was computed against.
- `AuthoredChange.diff_text` and `AuthoredChange.name_status` serve the two
  diff shapes the family's two named consumers need (a full text diff for
  `check_contract_shrinking.py`, a name-status list for
  `check_doc_frontmatter.py`) from that one derivation, diffing against the
  SAME ref `.paths` was derived from (the last entry in `states`) — diffing
  against the default `HEAD` instead would silently drop content the author
  already committed to their own branch before the merge began, even though
  `.paths` correctly includes it. Both are plain data attributes, computed
  eagerly inside `get_authored_change()` rather than lazily on first access,
  per the contract this module's rename adopted.
- A `git` failure or timeout inside the derivation sets
  `AuthoredChange.could_not_check = True` (with `error` describing what
  failed) rather than degrading to an unscoped diff; each consumer's
  `_get_shared_authored_change()` wrapper also catches an unexpected
  exception from the shared module itself and degrades to the same
  could-not-check outcome, so a broken dependency cannot crash the check
  outright. `could_not_check=True` is an `OUTCOME_COULD_NOT_CHECK` outcome
  (see the vocabulary table below), never license to widen the scope.
- The merge-scoping predicate here is deliberately **broader** than the
  pre-existing per-check helpers' "differs from both `HEAD` and `MERGE_HEAD`"
  intersection: scoping to `MERGE_HEAD` alone is required so a check's
  verdict on the author's own content — committed to their branch before the
  merge began, and therefore matching `HEAD` exactly — is unaffected by the
  merge. This is a different, narrower predicate than
  `check_contract_shrinking.py`'s private `_merge_scoped_paths()` still uses
  for the unrelated `ACS-100c-1` family (excluding content taken verbatim
  from the merge's own side); that helper is intentionally NOT unified into
  the shared module. See ADR-038's Decision §4 and §8.

`_authored_change.py` follows this family's existing shared-facility
pattern set by `_resolve_root.py` (one small leaf module in the package,
imported by name), but solves a different problem: `_resolve_root.py`
resolves a *prerequisite* (the project root); `_authored_change.py`
derives the *change set* itself.

## Machine-Readable Outcome Vocabulary

Because the merge-scoped set above can legitimately come back empty — a clean
auto-merge where the author changed nothing of their own — both checks must be able
to report that outcome explicitly, without silently widening back to the whole staged
tree and without confusing it with a check that never ran at all. `check_outcome.py`
declares this vocabulary once, for every check in this directory to share:

| Constant | Meaning |
|---|---|
| `OUTCOME_OK` | The check ran its inspection and found nothing wrong. |
| `OUTCOME_COULD_NOT_CHECK` | The check could not perform its inspection at all (e.g. a required helper module was absent) — distinct from a genuine clean pass. |
| `OUTCOME_NOTHING_TO_INSPECT` | The check derived its own (merge-scoped/authored) change set per the section above and that set was empty — there was nothing of the author's to inspect. This is a pass, not a skip: exit status is 0 and the commit proceeds. It must never be produced by falling back to the whole staged tree when the derived set is empty; an empty derived set is an explicit value, not an absence, and is never widened. |

Each value is emitted on stdout as a fixed-shape `RESULT: <outcome>` line via
`check_outcome.emit_result()`, so a caller can detect it with
`line.startswith("RESULT: ")` independent of exit code and without parsing prose.
`check_contract_shrinking.py` and `check_doc_frontmatter.py` both call a
`_report_if_nothing_to_inspect()` helper from their own empty-derived-set pass branch
in `main()` to emit `OUTCOME_NOTHING_TO_INSPECT`. See AC `GE-120e-1-i` under
`docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/` for the
no-widening-on-empty guarantee this vocabulary entry pins down, and AC `GE-120a-1`
for the `OUTCOME_OK` / `OUTCOME_COULD_NOT_CHECK` vocabulary it extends.

### `check_ac_parent_covered_by.py` — Cannot-Reach-Prerequisite Reports `OUTCOME_COULD_NOT_CHECK`

`check_ac_parent_covered_by.py` depends on `derive_parent_id()` (imported from
`scripts/ac_store/ac_parent_id.py`) to identify each staged child AC's immediate
parent before it can evaluate the `covered_by` back-link. When the working copy
it runs from does not expose the deployed layout — `ac_parent_id.py` is absent,
or present as a directory rather than a file — that prerequisite is unreachable
and the check cannot perform its inspection at all.

Previously this cannot-run condition fell open silently: a single stderr line
("cannot import derive_parent_id ...; skipping check (fail-open)") followed by
an ordinary success. That shape is indistinguishable from a genuine clean pass
to any caller that does not read prose, so a broken deploy and a clean commit
looked identical. `GE-120a-1` closes this: `main()` now catches
`(ImportError, OSError)` around prerequisite discovery — the `OSError` arm
covers the directory-shaped-file case, which previously fell through uncaught
to the bottom-of-file catch-all — and both arms call `_emit_could_not_check()`.

`_emit_could_not_check()` does two things on every cannot-run path:

1. Prints a reader-actionable `WARNING` to stderr naming both the unreachable
   prerequisite (`derive_parent_id`) and the unverified scope, e.g. `parent
   covered_by links were not evaluated for 6 staged files`.
2. Emits `RESULT: could_not_check` via the shared `check_outcome.emit_result()`
   (`OUTCOME_COULD_NOT_CHECK`) — independent of exit code, since the check
   still returns 0 here. Naming the outcome does not by itself decide
   block-vs-announce; that disposition is `GE-120a-2`'s concern.

The reachable-prerequisite path is unchanged: with `derive_parent_id` importable,
the same staged set still blocks on the same violations it always did (the
`GE-118a-1` backward-compatibility precedent). See AC `GE-120a-1` under
`docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/` for the
full Gherkin spec and its coverage note (execution-based test required; a
grep-only test on the warning string does not satisfy it).

## Whole-Collection Uniqueness Pass (goal `GE-122`)

Most hooks above are **per-file**: they read the staged diff and judge each record in
isolation, so they cannot see that a sibling file — never itself staged — already claims
the same number. `check_identifier_uniqueness.py` (`run_uniqueness_pass`) is a different
unit of inspection: a single importable module that walks the **whole on-disk collection**
(never diff-scoped) across four numbered namespaces — acceptance-criterion identifiers,
decision-record integers, architecture-diagram level-and-sequence ids, and work-item
identifiers — and returns one fixed `UniquenessVerdict` object: one finding per contested
number (never one per claimant file), every claimant path, and a mandatory per-namespace
`inspected_count` that distinguishes a real pass from a pass over nothing. Six sibling
ACs under goal `GE-122` consume that verdict object directly rather than a CLI's printed
text. See the [data-flow diagram](../diagrams/c3-006-whole-collection-uniqueness-pass.md)
and the governing [ADR-037](../adrs/ADR-037-whole-collection-uniqueness-pass.md).

The decision-record namespace of that pass adopts `check_adr_collision.py`'s existing
staged-vs-`origin/main`-vs-in-flight-branch comparison rather than reimplementing it. That
script is now registered as the `check-decision-number-uniqueness` hook in
`hooks_manifest.hooks` — as of 2026-08-18 it is the first time it has ever executed; see
[ADR-029 Amendment 1](../adrs/ADR-029-adr-number-collision-prevention.md#amendment-1--2026-08-18--fail-open-is-narrowed-to-the-guards-own-defects)
for the fail-open narrowing this registration depended on. `check_identifier_uniqueness.py`
itself is not yet registered in any hook manifest — wiring it into the three
commit-lifecycle stages is `GE-122d-1`'s scope, not this pass's.
