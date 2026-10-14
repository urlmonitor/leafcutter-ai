---
title: "KI-CG-20261014-no-gate-keeps-the-document-length-standard-in-step — nothing checks docs/reference/document-length-standard.md against the doc_length declaration in commit_guardian.json, so a set-aside location added or a report_above_lines changed leaves the published standard silently stale; the code-side rule has a parity gate, the document side has none"
description: "low — the published page lists the three set-aside locations, their grounds and their ceilings (1500 / 1500 / 2000) as prose. The enforced values live in templates/scripts/commit_guardian/commit_guardian.json doc_length.set_aside_locations. check-file-size-rule-parity (GE-127d-1) reconciles the FILE-size rule's published surfaces with its enforced rule, but its configured surfaces are README.md and commit_guardian.json only, and it never reads the doc_length section. unit_tests/docs/test_ge_127g_4_published_standard.py deliberately checks prose only and never reads the config. GE-127g-4's own test_rationale records this gap and assigns it to GE-127d. A known gap, not yet observed going stale. Verified on origin/main 95961b718."
type: reference
category: reference
status: active
created: '2026-10-14'
last_updated: '2026-10-14'
components:
  - commit_guardian
  - documentation_system
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/reference/document-length-standard.md
  - docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127g-4.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127d.yaml
---

# KI-CG-20261014-no-gate-keeps-the-document-length-standard-in-step — the document-length standard has no parity gate

> Filed 2026-10-14 from GE-127g-4. Index: [commit-guardian.md](../commit-guardian.md).
> Filed under commit-guardian because the missing piece is a commit-time gate, the twin of
> `check-file-size-rule-parity`. `components:` names `documentation_system` so it can be found from
> that side. Filename severity is the three-level index bucket (`low`).

- **Severity:** low. Nothing is wrong today: the page and the declaration agree. But the page is the
  place an author is sent to learn what is judged, and the first time the declaration changes without
  it, the page tells authors something the gate does not do, with nothing to notice.
- **Status:** open, no AC. GE-127g-4 recorded the gap and fenced it out of its own scope (see
  below).
- **Occurrences:** 0 observed drifts. This is a recorded gap, not an incident.
- **First seen:** 2026-10-14 · **Last seen:** 2026-10-14
- **Where:**
  - The published side: `docs/reference/document-length-standard.md:45-47` (the table of locations,
    grounds, sources and ceilings) and `:53` (the ceilings restated in prose: "`docs/agents/cards/` and
    `docs/roadmap.md` declare 1500, `docs/INDEX.md` declares 2000").
  - The enforced side: `templates/scripts/commit_guardian/commit_guardian.json:45-60`
    (`doc_length.set_aside_locations`, each with `path`, `ground` and `report_above_lines`).
  - The code-side twin: `templates/scripts/commit_guardian/check_file_size_rule_parity.py` (GE-127d-1).
    Its surfaces come from `file_size.published_rule_surfaces` (`commit_guardian.json:34-37`:
    `README.md`, `commit_guardian.json`), and it compares them with the file-size constants from
    `config.py`. It has no notion of `doc_length`.
  - The test: `unit_tests/docs/test_ge_127g_4_published_standard.py:9-11`. Its docstring says "It
    reads the published prose and nothing else" and "DELIBERATELY NOT A PARITY CHECK: it never reads
    commit_guardian.json".

## The record of the gap

`docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127g-4.yaml`:

- `doc_links` (`:66-77`) notes for the IT PO that "a parity check exists for the code-side rule and
  there is no equivalent for the document-side one, so parity here currently rests on review rather
  than on a gate."
- An `it_requirement` (`:198-201`) forbids adding a parity assertion in that record.
- `test_rationale` (`:237-250`): GE-127g-5 closed the declaration half (an entry with no ceiling is
  refused, and an over-ceiling document is reported). What remains is "PUBLISHED TEXT versus
  CONFIGURATION … a location added or a ceiling altered leaves the published description quietly
  stale". A "published-versus-configured parity gate, mirroring the code-side rule's existing one,
  would close it. It needs its own record under GE-127d". The record adds that GE-127 holds 7 of 7
  L1s and GE-127g 5 of 5 children, "so it needs a split or a new L0 rather than a sibling anywhere in
  this subtree."

Counts checked: `GE-127.yaml:104-111` lists 7 L1s (GE-127a to GE-127g) and `GE-127g.yaml:288-293`
lists 5 children. **Not resolved here:** `GE-127d.yaml:86-88` lists only 2 children (GE-127d-1,
GE-127d-2), so an L2 under GE-127d does not obviously hit a child cap. The record's "needs a split or
a new L0" may refer to a cap or placement rule this entry did not check. The AC author should confirm
it before choosing a home.

## Detection

Compare the two sides by hand: each `path` and `report_above_lines` in
`commit_guardian.json` `doc_length.set_aside_locations` should appear in the table and prose of
`docs/reference/document-length-standard.md`, and the page should name no location the declaration
lacks.

## Workaround

Edit both in the same commit, and make a reviewer check the pair. Nothing enforces it.

## Suggested fix

A document-side parity gate, mirroring `check-file-size-rule-parity`: on any commit that stages
`commit_guardian.json` or `docs/reference/document-length-standard.md`, read
`doc_length.set_aside_locations` through `config.py` and refuse when a declared location or its
ceiling is missing from the page, or the page names one the declaration does not. Either a
`doc_length.published_rule_surfaces` list, or a generalisation of the existing gate to more than one
rule. It needs an AC first (under GE-127d, or wherever the cap question above lands), per
`CLAUDE.md`'s "New Work Goes Through ACs".

**Pattern:** a rule stated in two places with a check on one pair and not the other. The asymmetry is
recorded in an AC, which is not a gate.
