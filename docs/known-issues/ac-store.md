---
title: "Known issues — ac-store"
description: "Open, observed defects in the ac-store component: the acceptance-criteria YAML store, its truth fields, its schema validator, the done-proof oracle, and the scripts that read it and transition a criterion to done. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: '2026-09-25'
components:
  - ac_store
related_docs:
  - docs/how-to/prove-ac-done.md
  - docs/known-issues/build-orchestration.md
  - docs/reference/ac-schema.md
---


# Known issues — ac-store

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-ACS-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

## How this register is stored

This file is an **index**. Each known issue is its own file under [`ac-store/`](ac-store/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/ac-store/open-blocker-*   # anything critical open?
ls docs/known-issues/ac-store/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`ac-store/resolved/`](ac-store/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 24** (1 blocker, 14 high, 9 low) · **Resolved: 3**

## Open

| Severity | Issue | File |
|---|---|---|
| `blocker` | KI-ACS-007 — `components` is required and hand-authored while the package ships its deriver | [open-blocker-ki-acs-007.md](ac-store/open-blocker-ki-acs-007.md) |
| `high` | KI-ACS-002 — `--verify` passes `files_touched` on a path count, not on correctness | [open-high-ki-acs-002.md](ac-store/open-high-ki-acs-002.md) |
| `high` | KI-ACS-003 — The store validator does not check id uniqueness, so duplicate AC ids merge clean through a required gate | [open-high-ki-acs-003.md](ac-store/open-high-ki-acs-003.md) |
| `high` | KI-ACS-004 — An AC is marked `done` with no link to the code implementing it | [open-high-ki-acs-004.md](ac-store/open-high-ki-acs-004.md) |
| `high` | KI-ACS-006 — Three defects in the done-proof oracle that misreport AC coverage | [open-high-ki-acs-006.md](ac-store/open-high-ki-acs-006.md) |
| `high` | KI-ACS-008 — The oracle's tag-to-test layer cannot see an async test or a parametrised one | [open-high-ki-acs-008.md](ac-store/open-high-ki-acs-008.md) |
| `high` | KI-ACS-012 — 193 approved code-AC leaves have no test contract, and each one blocks the next person to touch it | [open-high-ki-acs-012.md](ac-store/open-high-ki-acs-012.md) |
| `high` | KI-ACS-013 — `delivers_to` and `expects_from` are the two ends of one edge keyed on different things, so the forward half is not traversable and nothing validates either | [open-high-ki-acs-013.md](ac-store/open-high-ki-acs-013.md) |
| `high` | KI-ACS-014 — `reference_file_path` can name a symlinked build output that git does not track, and nothing checks it resolves to a source file | [open-high-ki-acs-014.md](ac-store/open-high-ki-acs-014.md) |
| `high` | KI-ACS-20260901-1520 — The ticket generator hard-codes `.py` on every test filename, so a browser test is declared as a Python file and the done-proof oracle routes on that extension | [open-high-ki-acs-20260901-1520.md](ac-store/open-high-ki-acs-20260901-1520.md) |
| `high` | KI-ACS-20260901-1730 — The done-proof oracle gives pytest 60 seconds and reports the timeout as "linked test not run", so a slow-but-passing test makes an AC nondeterministically ineligible for done | [resolved-high-ki-acs-20260901-1730.md](ac-store/resolved/resolved-high-ki-acs-20260901-1730.md) |
| `high` | KI-ACS-20260907-0920 — Nothing compares an AC's fields against each other, so a record can carry two clauses that contradict — and in one case the contradicted clause predicted verbatim the defect that shipped | [open-high-ki-acs-20260907-0920.md](ac-store/open-high-ki-acs-20260907-0920.md) |
| `high` | KI-ACS-20260907-the-validator-everyone-runs-is-weaker-than-the-gate-that-blocks — KI-ACS-20260907-the-validator-everyone-runs-is-weaker-than-the-gate-that-blocks | [open-high-ki-acs-20260907-the-validator-everyone-runs-is-weaker-than-the-gate-that-blocks.md](ac-store/open-high-ki-acs-20260907-the-validator-everyone-runs-is-weaker-than-the-gate-that-blocks.md) |
| `high` | KI-ACS-20260914-composite-proof-drops-path-leaves — the CI done-proof gate expands a leaf that lists its test file in `covered_by` as if it were a composite, finds no children, and refuses every parent goal above such leaves | [open-high-ki-acs-20260914-composite-proof-drops-path-leaves.md](ac-store/open-high-ki-acs-20260914-composite-proof-drops-path-leaves.md) |
| `high` | KI-ACS-20260914-mark-ac-done-refuses-every-test-required-false-leaf — the sanctioned tool for marking an AC done cannot pass a single docs-only leaf, ever | [resolved-high-ki-acs-20260914-mark-ac-done-refuses-every-test-required-false-leaf.md](ac-store/resolved/resolved-high-ki-acs-20260914-mark-ac-done-refuses-every-test-required-false-leaf.md) |
| `low` | KI-ACS-009 — The documented AC-store pre-flight runs a weaker validator than the required CI gate, so a clean local check does not predict CI | [open-low-ki-acs-009.md](ac-store/open-low-ki-acs-009.md) |
| `low` | KI-ACS-011 — `documentation_triggers: []` is refused on an L2 while `null` is accepted, so declaring "no documentation needed" is uncommittable | [open-low-ki-acs-011.md](ac-store/open-low-ki-acs-011.md) |
| `low` | KI-ACS-015 — A `test_spec` descriptor has no link to the criterion it was promised for, so "which behaviour is this proof for" is unrepresentable | [open-low-ki-acs-015.md](ac-store/open-low-ki-acs-015.md) |
| `low` | KI-ACS-016 — There is no retired `work_status`, so a superseded child stays in its parent's `covered_by` and the parent can never be proved done | [open-low-ki-acs-016.md](ac-store/open-low-ki-acs-016.md) |
| `low` | KI-ACS-20260901-1810 — Generating a ticket into a throwaway `--tickets-root` permanently stamps the SOURCE AC with a path that will never exist, and mangles it into one that looks repo-relative | [open-low-ki-acs-20260901-1810.md](ac-store/open-low-ki-acs-20260901-1810.md) |
| `low` | KI-ACS-20260907-approved-code-acs-with-no-test-contract-sit-on-main-until-something-stages-them — KI-ACS-20260907-approved-code-acs-with-no-test-contract-sit-on-main-until-something-stages-them | [open-low-ki-acs-20260907-approved-code-acs-with-no-test-contract-sit-on-main-until-something-stages-them.md](ac-store/open-low-ki-acs-20260907-approved-code-acs-with-no-test-contract-sit-on-main-until-something-stages-them.md) |
| `low` | KI-ACS-20260907-reachability-boilerplate-denies-the-test_spec-printed-above-it — the generated ticket tells the test author the AC declared nothing, six paragraphs below the six things it declared | [open-low-ki-acs-20260907-reachability-boilerplate-denies-the-test_spec-printed-above-it.md](ac-store/open-low-ki-acs-20260907-reachability-boilerplate-denies-the-test_spec-printed-above-it.md) |
| `low` | KI-ACS-20260909-standalone-validator-does-not-derive-declares-side-effect — `validate_ac_schema.py` passes records the commit hook then rejects, so a clean bulk run is not evidence on every field | [open-low-ki-acs-20260909-standalone-validator-does-not-derive-declares-side-effect.md](ac-store/open-low-ki-acs-20260909-standalone-validator-does-not-derive-declares-side-effect.md) |
| `low` | KI-ACS-20260923-doc-links-status-not-reconciled — an AC's `doc_links[].status` field is never reconciled against whether its target document actually exists or shipped | [open-low-ki-acs-20260923-doc-links-status-not-reconciled.md](ac-store/open-low-ki-acs-20260923-doc-links-status-not-reconciled.md) |

## Resolved

| Severity | Issue | File |
|---|---|---|
| `high` | KI-ACS-010 — The store's test vocabulary is Python-only, so 29 web-app ACs are unvalidatable landmines | [resolved-high-ki-acs-010.md](ac-store/resolved/resolved-high-ki-acs-010.md) |
| `blocker` | KI-ACS-017 — `approve_acs.py` corrupts any record whose `amended_by` holds a multi-line entry, and returns success for the files it broke | [resolved-blocker-ki-acs-017.md](ac-store/resolved/resolved-blocker-ki-acs-017.md) |
| `low` | KI-ACS-018 — withdrawn as a duplicate; see `ac-driven-dev.md` | [resolved-low-ki-acs-018.md](ac-store/resolved/resolved-low-ki-acs-018.md) |
