---
title: "KI-ACD-20260925-contract-target-is-parent-link — generated tickets name the parent AC as the documentation-expert's target document"
description: "medium — the ticket generator takes the first doc_links entry containing a slash as the documentation target, ignoring relationship; the BA writes the parent link first, so every generated child ticket's documentation contract targets an approved AC YAML with genre '(unspecified genre)', and documentation-verifier then blocks or the doc lands in the wrong place."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-10-14'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-002.md
---

# KI-ACD-20260925-contract-target-is-parent-link — generated tickets name the parent AC as the documentation target

- **Severity:** medium. `documentation-verifier` catches it (fail-closed), but every affected ticket
  needs a hand correction first.
- **Status:** open — no AC.
- **Occurrences:** 3 observed on 2026-09-25: GE-120f-1, GE-120f-1-i and GE-120f-1-ii. On
  GE-120f-1 it produced a `documentation-verifier` blocker. Structural: reachable for every AC whose
  first doc_link is its parent. A fourth on 2026-10-12 (`INF-500d-4-i`), where the first link was
  a source file; see Occurrence 2.
- **Where:** `scripts/ac_store/_gtfa_doc_genre.py:_extract_doc_path` (target selection) and
  `scripts/ac_store/_gtfa_contracts.py` (renders `- [ ] AC-N: <genre> | <doc_path> | ...`).

## Symptom

A generated ticket's `### documentation-expert` block reads, for example:

```
- [ ] AC-1: (unspecified genre) | docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f-1.yaml | ...
```

The target is the parent acceptance criterion. That is an approved record in the store, not a
document the phase is meant to write.

## Mechanism

`_extract_doc_path` returns the first `doc_links` entry whose `path` is a local string containing a
`/`. It never reads `relationship`. BA-authored child ACs list `relationship: parent` first, so
the parent YAML always wins. The genre falls back to the `(unspecified genre)` marker, because
nothing in the record states one.

## Consequence

The documentation-expert is pointed at a file it must not edit. If it complies, it rewrites an
approved AC. If it doesn't, `documentation-verifier` finds no diff on the named target and blocks.
Either way the ticket needs a hand correction before the phase can pass.

## Fix direction

Exclude `relationship: parent`, and any path under `docs/acceptance-criteria/`, from target
selection. When no qualifying link remains, use the existing computed default under
`docs/<genre>/`. Add a regression test with a parent-first `doc_links` list.

Widened by Occurrence 2: select only a link that is a documentation file. Exclude
`relationship: implements` / `modifies` (those name the code the AC changes), and any path
that is not a doc (for example, not `.md`). Prefer `relationship: describes`. Add a second
regression test with a source-file-first `doc_links` list.

---

## Occurrence 2 — 2026-10-12: a source file, not the parent, wins target selection

- **Occurrences:** now 4 (3 on 2026-09-25, 1 on 2026-10-12). **Last seen:** 2026-10-12.
- **Severity:** unchanged at medium. The verifier still catches it, but the blocker now names
  the wrong cause (see KI-DS-20261014-token-scan-flags-f-string-fields-in-source-targets).
- **Re-checked on `origin/main` `435c11395`:**
  - `scripts/ac_store/_gtfa_doc_genre.py:226-237`. `_extract_doc_path` still returns the first
    `doc_links` entry whose `path` holds a `/` and does not start with `http`. It reads neither
    `relationship` nor the file extension.
  - `scripts/ac_store/_gtfa_contracts.py:164-181`. `_doc_expert_subsection_lines` passes that
    path straight into `- [ ] AC-N: <genre> | <doc_path> | <constraint>`.

**What happened.** Ticket 02 of `EPIC-OneDurableLogRootForEveryWorkspace` (`INF-500d-4-i`) was
generated with:

```text
- [ ] AC-1: (unspecified genre) | templates/scripts/feedback/submit_feedback.py | ...
```

The AC's first `doc_links` entry is `templates/scripts/feedback/submit_feedback.py` with
`relationship: implements`
(`docs/acceptance-criteria/infrastructure/INF-500-operational-observability/INF-500d-4-i.yaml:47-50`).
It is the Python source the AC changes. It is not a doc. The parent-link exclusion in the fix
direction above would not have helped, because the source link came first.

**Effect.** documentation-verifier blocked, reading the f-string fields in the source as
unfilled placeholders (KI-DS-20261014-token-scan-flags-f-string-fields-in-source-targets). The
contract was corrected by hand to `docs/architecture/feedback-lifecycle.md` (`ddae96e40`).

**How far it reaches.** A read-only scan on `435c11395` ran `_extract_doc_path` over every AC
with a non-empty `doc_links`. For ACs that are not yet `done`:

| Target `_extract_doc_path` picks | ACs |
|---|---:|
| a documentation file (`.md` / `.mdx` outside `docs/acceptance-criteria/`) | 1929 |
| a non-doc file (`.py`, `.yaml`, `.json`, `.js`, ...) | 604 |
| an AC record under `docs/acceptance-criteria/` (this entry's original shape) | 570 |

So about two in five not-done ACs with doc links would get a wrong documentation-expert target
if a ticket were generated from them today. In the same family, `INF-500d`, `INF-500d-4`,
`INF-500d-4-ii` and `INF-500d-5` all list `submit_feedback.py` first.

**Related.** KI-BP-20260831-generator-emits-unparseable-doc-contract, point 2, recorded source
files as doc targets on 2026-08-31 and named the risk that a coder's own edit satisfies the
diff check. This occurrence is the other outcome: the verifier read the source and blocked.
