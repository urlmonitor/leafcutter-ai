---
title: "ADR-038: Commit Guardian Shared Change-Set Derivation"
description: "Self-deriving commit-guardian checks MUST consume one shared module for the authored change set instead of each computing its own private git diff, so a mainline merge cannot make one check block on content its author never wrote while another passes."
type: "adr"
status: "active"
created: "2026-08-31"
last_updated: "2026-08-31"
deciders:
  - python-coder
  - architect-review
components:
  - commit_guardian
  - git_vcs_operations
related_docs:
  - docs/architecture/components/commit-guardian.md
  - docs/architecture/adrs/ADR-037-whole-collection-uniqueness-pass.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
related_code:
  - templates/scripts/commit_guardian/_authored_change.py
  - templates/scripts/commit_guardian/check_contract_shrinking.py
  - templates/scripts/commit_guardian/check_doc_frontmatter.py
  - templates/scripts/commit_guardian/_resolve_root.py
---

# ADR-038: Commit Guardian Shared Change-Set Derivation

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-08-31 |
| Author | python-coder (GE-120e-1), architect-review |
| Supersedes | — |

**Amendment (2026-08-31, same day, pr-reviewer remediation):** the shared
module this ADR describes was renamed from `_resolve_change_set.py` /
`get_change_set()` / `ChangeSet` to `_authored_change.py` /
`get_authored_change()` / `AuthoredChange`, to honour the contract
`unit_tests/portability/test_ge_120e_4_i.py` (ticket 36, `GE-120e-4-i`) had
already established for this exact module before this ADR's implementation
landed. The shape also changed: `base_ref`/`head_ref` became a single
`states: list[str]` provenance field, `.text_diff()`/`.name_status()` became
plain data attributes `diff_text`/`name_status` (computed eagerly, not
lazily, since the contract requires attribute access rather than method
calls), and a `None` could-not-check sentinel became in-band
`could_not_check: bool` / `error: str | None` fields. The Decision and
Consequences sections below are updated in place to describe the current
(post-rename) names and shape; no decision recorded here was reversed by
the rename.

**Amendment 2 (2026-09-01, `GE-120e-2`) — the manifest declares which checks
derive their own change set.** This ADR establishes *one shared derivation*;
`GE-120e-2` establishes *who is required to use it*, and records that as data
rather than as a list of names in code.

A new key, `change_set_source`, is **required on every entry** of
`hooks_manifest.hooks[]` in
`templates/scripts/commit_guardian/commit_guardian.json`. Its vocabulary is
closed:

| Value | Meaning |
|---|---|
| `handed_by_commit_path` | The commit path hands this check its file list; it derives nothing. |
| `self_derived` | This check works out its own change set, and must obtain it from `_authored_change.get_authored_change()`. |

Three properties make this a contract rather than a comment:

- **Absent is not a default.** An entry with no `change_set_source` makes the
  determination report a *failure* naming that entry, so the next hook added
  without one is blocked rather than silently assumed harmless.
- **Membership is decided from the declared value only** — never from
  `pass_filenames` (57 of 59 entries carry `pass_filenames: false` while only
  two derive a diff, so it is not the discriminator), and never from a
  hand-written list of the two checks that were caught misattributing.
- **A declared `self_derived` check that obtains its change set by any other
  means is named and fails the determination**, so the declaration cannot
  drift away from the behaviour it claims.

`templates/scripts/commit_guardian/change_set_source.py` implements the
determination (`determine_change_set_sources(manifest_path)`), reading the
manifest at call time. As of this amendment: 59 entries, all carrying the
field, of which exactly two — `check-doc-frontmatter` and
`check-contract-shrinking` — are `self_derived`, and both verifiably consume
`get_authored_change()`.

This amendment records a field contract that was previously pinned only by a
test file's docstring (`GE-120e-2-i`, committed before the implementation) —
the same undocumented-decision drift this ADR was opened to close for the
`_authored_change.py` contract itself.

## Context

`check_contract_shrinking.py` (line ~180) and `check_doc_frontmatter.py` (line ~287,
via `frontmatter_validators.py`) each work out for themselves which staged content to
judge, because the commit path hands a pre-commit hook no file list. Before this
decision, each check independently hand-implemented the same "diff differs from the
merge parents" idiom — `_merge_scoped_paths()` in one, `merge_scoped_md_paths()` in the
other — by calling `git diff --cached` directly.

A large mainline merge exposes the cost of that duplication concretely: staging a
479-file merge stages the *entire* incoming branch, not just the merging author's own
conflict resolutions. An unscoped `git diff --cached` names every file the other side
ever touched, so a check reading that raw diff can object to test deletions or
frontmatter faults the branch's own change set never introduced — the observed case
that forced this decision. Because each check computed this narrowing privately, the
two independent implementations could silently drift, so a merge could leave one check
naming carried-in work as an objection while its sibling, computing the same narrowing
slightly differently, did not — the split-verdict failure mode `GE-120e-1`'s Gherkin
forbids.

Both private implementations also fell back to the **unscoped** (whole-staged-tree)
diff whenever the git call needed to compute the narrowing failed — for example, a git
subprocess timing out under repository stress. That fallback silently restores the
original defect on exactly the commits where git is least reliable, converting a
could-not-check condition into a false widening rather than an explicit
`OUTCOME_COULD_NOT_CHECK` (`GE-120a-1`'s vocabulary, documented in
[docs/architecture/components/commit-guardian.md](../components/commit-guardian.md)).

`_resolve_root.py` is this family's existing precedent for one shared facility with
many importers (27 at time of writing) — but it resolves a *prerequisite* (the project
root), not the *change set* itself, so it does not cover this gap.

## Decision

1. `templates/scripts/commit_guardian/_authored_change.py` MUST be the single
   shared source every self-deriving commit-guardian check consumes for "what did the
   author change." A check MUST NOT compute its own private `git diff --cached` call
   for this purpose.
2. The module MUST expose `get_authored_change(cwd: Path | None = None) ->
   AuthoredChange`. `AuthoredChange` MUST carry the derived `paths`, the `states`
   provenance (the commit-ish(es) the derivation was computed against) as plain data
   attributes, plus `diff_text` and `name_status` — both diff shapes the family's
   consumers need, served from the one underlying `git` invocation shape rather than
   from two independently-shaped return values.
3. `check_contract_shrinking.py` and `check_doc_frontmatter.py` MUST both be migrated
   to consume `get_authored_change()` in the same change that introduces the shared
   module. A change that migrates one named consumer and leaves the other on its
   private diff call MUST be rejected at review — it reproduces the exact
   split-verdict defect this ADR exists to close.
4. During a merge (`MERGE_HEAD` present), the derivation MUST scope `paths` to
   content differing from `MERGE_HEAD` (the incoming branch) alone. It MUST NOT
   require the stricter "differs from both `HEAD` and `MERGE_HEAD`" intersection the
   pre-existing per-check helpers used, because that stricter form also excludes
   content the author already committed to their own branch before the merge began —
   such content matches `HEAD` exactly and would never be flagged, contradicting the
   AC's requirement that the verdict on the author's own content is unchanged by a
   merge. `AuthoredChange.diff_text` and `.name_status` MUST diff against the same
   ref `paths` was derived from (the last entry in `states`), not the default `HEAD`
   comparison, so the text and the path list never disagree.
5. On an ordinary (non-merge) commit, the derivation MUST equal `git diff --cached`'s
   full output byte for byte. This is the regression budget for every other
   manifest check and for every ordinary commit in the repository.
6. A `git` subprocess failure or timeout in the derivation MUST resolve to an
   `AuthoredChange` with `could_not_check=True` (and an `error` describing what
   failed) rather than a partial or widened result. Consumers MUST treat
   `could_not_check=True` as an `OUTCOME_COULD_NOT_CHECK` outcome and MUST NOT fall
   back to inspecting the whole staged tree.
7. The derivation MUST be memoised per resolved `cwd` for the lifetime of the process,
   and MUST resolve the git directory via `git` plumbing (e.g. `git rev-parse
   --git-dir` inside the underlying calls) rather than assuming `<root>/.git` exists as
   a directory, so the module remains correct inside a linked git worktree.
8. This decision does not extend to `check_contract_shrinking.py`'s narrower, private
   `_merge_scoped_paths()` helper used by a *different* AC family
   (`ACS-100c-1`, verified by `unit_tests/commit_guardian/test_ac_limits_merge_scope.py`),
   which requires the stricter both-parents intersection for a different purpose
   (excluding content taken verbatim from the merge's own side). That helper MUST
   remain self-contained rather than being unified into the shared module.

## Consequences

### Positive

- A merge that touches none of a check's files can no longer trip that check on
  content its author never wrote, because every consumer answers "what did the author
  change" from the same derivation.
- Adding a third self-deriving check (e.g. `GE-120e-2`'s future consumers) requires
  only importing `get_authored_change()`, not re-implementing the merge-scoping idiom a
  third time.
- The could-not-check outcome is now explicit and shared: a git failure during
  derivation is indistinguishable in outcome vocabulary from any other
  `OUTCOME_COULD_NOT_CHECK` condition already documented in
  [docs/architecture/components/commit-guardian.md](../components/commit-guardian.md).

### Negative

- The merge-scoping predicate is now intentionally *broader* than the pre-existing
  per-check helpers' both-parents intersection (Decision §4). Any future consumer that
  actually needs the stricter, narrower predicate (as `ACS-100c-1` does) must not be
  routed to this shared module without re-deriving whether the broader predicate is
  safe for its use case.
- `AuthoredChange.diff_text` and `.name_status` are computed eagerly inside
  `get_authored_change()` (a data-attribute shape, not a lazy accessor, per the
  contract this ADR was amended to honour — see the Amendment note above), so every
  call issues both `git diff --cached` invocations regardless of whether the caller
  reads one shape or both. Memoisation per resolved `cwd` (Decision §7) still bounds
  this to one derivation per process per working tree.

### Operational

- The derivation runs inside every `pre-commit` invocation, so it inherits the
  family's latency budget: on the ~500-file staged tree observed in the triggering
  merge, the shared module must add materially less than the commit's overall time
  budget. Memoisation per process (Decision §7) keeps this to one `git rev-parse
  --verify MERGE_HEAD` probe, one name-only listing, and the two diff invocations
  needed to populate `diff_text`/`name_status` — per resolved `cwd`, regardless of how
  many consuming checks call `get_authored_change()`.
- `templates/scripts/commit_guardian/_authored_change.py` is deployed by
  `build_commit_guardian()`'s whole-directory `rglob` copy in `scripts/build_phases.py`
  — no `deploy_map` edit was required to ship this module, per ADR-001's
  template/deployed parity convention. Any future move of this module out of
  `templates/scripts/commit_guardian/` would require an explicit `deploy_map` entry or
  the deployed hooks fail with `ModuleNotFoundError` at commit time.

## Alternatives

- **Leave each check's private `git diff --cached` call as-is and fix only the
  fallback-on-failure defect in each, independently.** Rejected. This does not close
  the split-verdict risk: two independently-maintained implementations of the same
  merge-scoping idiom can still drift apart (as the pre-existing `_merge_scoped_paths`
  vs. `merge_scoped_md_paths` pair already had), producing exactly the "one check
  blocks, its sibling passes, on the same commit" outcome this ADR forbids.
- **Two separately-shaped return values from two entry points (one for the text diff,
  one for name-status) instead of one `AuthoredChange` object.** Rejected. Two entry points
  computed independently can derive against different states if one caller passes a
  different `cwd` or the merge-probe result changes between calls; a single object
  carrying both accessors, memoised together, guarantees they always describe the same
  derivation.
- **Intersect with both `HEAD` and `MERGE_HEAD` (the pre-existing per-check helpers'
  predicate) in the shared module too, for consistency with prior behaviour.**
  Rejected. This predicate excludes the author's own content committed to their branch
  before the merge began (it matches `HEAD` byte-for-byte), so a check driven by it can
  never flag that content during a merge — directly contradicting `GE-120e-1`'s
  requirement that the verdict on the author's own content is unchanged by a merge.
- **Degrade to the whole staged tree when the derivation cannot be computed, logging a
  warning.** Rejected. This is the exact anti-pattern the triggering incident exists to
  remove: a git failure under repository stress would silently re-widen the scope back
  to carrying-in-work-included, on precisely the commits least able to tolerate a false
  objection.
- **Fold the change-set derivation into `_resolve_root.py`.** Rejected. `_resolve_root.py`
  solves prerequisite resolution (locating the project root); the change set is a
  different kind of derivation (comparing git states) with a different failure mode
  (could-not-check vs. an unresolvable root). Conflating the two would make a
  root-resolution failure and a diff-derivation failure indistinguishable to callers
  that only check for `None`.

## References

- Ticket: `tickets/00_inbox/epics/EPIC-TrustThatAGreenCheckActuallyChecked/28_TICKET-20260825-GE-120e-1.md`
- AC: `docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120e-1.yaml`
- [docs/architecture/components/commit-guardian.md](../components/commit-guardian.md) — the
  component doc this ADR is back-linked from, including the Machine-Readable Outcome
  Vocabulary section this decision's could-not-check outcome extends.
- [ADR-037 — Whole-Collection Uniqueness Pass](ADR-037-whole-collection-uniqueness-pass.md) —
  sibling precedent for a shared derivation consumed by multiple commit-guardian checks.
