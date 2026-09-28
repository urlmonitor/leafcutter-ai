---
title: "KI-ACS-20260923-doc-links-status-not-reconciled — an AC's `doc_links[].status` field is never reconciled against whether its target document actually exists or shipped"
description: "medium — no validator in scripts/ac_store/ reads doc_links[].status, so an entry can sit at status: planned for weeks after its target document actually shipped; drift on this field is invisible by construction."
type: reference
category: reference
status: active
created: '2026-09-23'
last_updated: '2026-09-23'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20260923-doc-links-status-not-reconciled — an AC's `doc_links[].status` field is never reconciled against whether its target document actually exists or shipped

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 35 `doc_links` entries across 26 AC records, one epic
- **First seen:** ~2026-08-31 (the earliest of the 35 entries went stale roughly two
  weeks before it was noticed) · **Last seen:** 2026-09-14
- **Where:** the AC YAML schema's `doc_links` list — the `status` field on each entry
  (`planned` / presumably `delivered` or similar); no validator in `scripts/ac_store/`
  reads this field.

**Symptom.** 35 `doc_links` entries across 26 AC records under
`EPIC-StartingNewWorkTheProperWayAlways` sat at `status: planned` for up to two weeks
after their target documents actually shipped. Nothing validates a markdown-to-markdown
cross-link or reconciles a `doc_links` entry's `status` against whether the target file
exists — this class of drift is invisible by construction, the same shape as the
AC-store hygiene gaps already filed in this register, but on a field none of those
checks read.

**Distinct from.** The existing `files_touched`-has-N-paths-derived-from-`doc_links`
checks already in this register, which verify presence in `files_touched`. Those checks
say nothing about whether the `status` field on a `doc_links` entry is itself truthful —
a link can be correctly present in `files_touched` while its `status` still reads
`planned` long after the document shipped.

**Why it matters.** A field nothing reconciles degrades quietly to decoration: readers
who trust `status: planned` to mean "not yet written" will miss documentation that has
in fact already landed, and nothing in this store's tooling will ever correct the record
for them.

**Fix direction.** Add a validator (standalone script and/or commit-guardian hook) that,
for each `doc_links` entry, checks the target document's existence and — where
feasible — a shipped signal (e.g. presence in a recent commit, or a doc-index entry),
and flags a `status: planned` entry whose target already exists as stale.

**Related.** The store's other invisible-by-construction gaps in this register, and
`docs/reference/false-green-mechanisms.md`'s general pattern of a documented check that
covers less than it appears to.

(Source: EPIC-StartingNewWorkTheProperWayAlways retrospective KI-4, 2026-09-14 — the
`check-doc-length` block against the then-monolithic register that deferred filing this
is gone; the register is now split into per-issue files and the index itself is small.)
