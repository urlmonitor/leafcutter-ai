---
title: "Reference: Code-Smell Report Format"
description: "Severity rubric (HIGH / MEDIUM / LOW), finding structure, report sections, and consolidated-merge rules for the code-smell review pipeline."
type: reference
status: active
created: 2026-08-11
last_updated: 2026-08-11
components:
  - review_system
related_docs:
  - templates/skills/review-for-code-smells/SKILL.md
  - templates/skills/code-smell-review/SKILL.md
---

# Code-Smell Report Format

Lookup reference for the severity rubric, finding structure, report section layout, and
consolidated-merge rules that govern every code-smell review produced by the
`find-structural-smells`, `find-design-smells`, and `code-smell-review` agents.

---

## Severity Rubric

Every finding receives exactly one severity level. Severity is determined by **impact on
the codebase**, not by smell identity: the same smell can warrant different levels depending
on how critical its location is.

| Severity | Criteria | Typical smells (not exhaustive) |
|---|---|---|
| **HIGH** | Actively multiplies risk of bugs or missed edits now — duplication across edit sites, Repeated Switches whose cases already diverge, Global or Mutable Data driving real bugs, Shotgun Surgery. | Duplicated Code (multi-site), Repeated Switches (diverged), Global Data, Mutable Data, Shotgun Surgery |
| **MEDIUM** | Clear maintainability drag that will bite on the next change but does not cause bugs today. | Long Function, Long Parameter List, Feature Envy, Data Clumps, Primitive Obsession |
| **LOW** | Readability or polish — safe to defer without immediate production risk. | Mysterious Name, a single intent-hiding Loop, minor local smells |

**Impact-overrides-identity rule.** A Mysterious Name on a widely-used public API can be
MEDIUM; a duplicated one-liner in a test file can be LOW. The assigned level reflects
consequence, not category membership.

---

## Finding Format

Every finding in a report uses this structure, in this exact order.

| Field | Content |
|---|---|
| **Title** | `[<SMELL NAME>] <short description>` — e.g. `[LONG FUNCTION] save() does five jobs` |
| **What's wrong** | 3–5 plain-English sentences: what the code does, why it is a smell, stop. Active voice. No jargon without a plain gloss. |
| **Refactoring** | The named Fowler refactoring(s) to apply (one line). Every finding cites at least one *Refactoring* (2nd ed) move by name. |
| **File** | Exact path and line range — e.g. `src/order.py:42–91`. |
| **Before** | Fenced code block. Verbatim from source; never altered. 3–15 lines. First line is a comment with filename and lines. |
| **After** | Fenced code block showing the shape of the fix, not a finished implementation. 5–15 lines. First line is `// direction only – not a full rewrite` (target-language comment syntax). |

### Finding ID convention

IDs follow the pattern `H-N`, `M-N`, `L-N` where the letter matches the severity level and
`N` is a sequence number within that level. In a consolidated (merged) report, IDs are
continuous across both reviewers' contributions (see [Consolidated Report](#consolidated-report)).

---

## Report Sections

A complete report contains the following six sections, in order.

### 1. Inferred Context

A table with two rows: Language/Stack (with confidence: High / Medium / Low) and Inferred
Intent (what the code is trying to do, reconstructed from names and data flow). Stated
briefly so the reader can correct misidentification before acting on findings.

| Field | Example value |
|---|---|
| Language / Stack | `Python 3.11 — Django REST Framework (High confidence)` |
| Inferred Intent | `Validates incoming webhook payloads and persists them to an order queue.` |

### 2. Summary

A table counting findings per smell and per severity level.

Columns: Smell name | HIGH count | MEDIUM count | LOW count | Total.

A totals row appears at the bottom showing the aggregate count per severity column.

### 3. HIGH Section

All HIGH-severity findings, each in [Finding Format](#finding-format), ordered by finding
ID (`H-1`, `H-2`, …).

### 4. MEDIUM Section

All MEDIUM-severity findings, ordered by finding ID (`M-1`, `M-2`, …).

### 5. LOW Section

All LOW-severity findings, ordered by finding ID (`L-1`, `L-2`, …).

### 6. Scorecard

A table with one row per smell category that had at least one finding. Columns:

| Column | Content |
|---|---|
| Smell | Name of the smell category |
| Score | 0–10 rating for that category (10 = no instances, 0 = severe) |
| Verdict | One sentence stating the key concern or confirming the category is clean |

A final row shows the **overall mean**, rounded to one decimal place, across all scored
categories.

---

## Consolidated Report

When the `code-smell-review` orchestration skill fans out to both `find-structural-smells`
and `find-design-smells` in parallel, their separate finding sets are merged into a single
report before delivery.

### Merge rules

| Rule | Specification |
|---|---|
| **One Inferred Context table** | Reconcile the two stacks/intents returned by each reviewer; they should agree. Surface any disagreement in the table. |
| **One Summary table** | Spans all twelve smells and both reviewers' counts. |
| **Re-numbered IDs** | Finding IDs are re-numbered continuously across the merged set: `H-1`, `H-2`, … across all HIGH findings regardless of which reviewer raised them. |
| **Severity ordering** | Findings are ordered by severity within each section (HIGH first, then MEDIUM, then LOW). |
| **De-duplicate overlaps** | A finding raised by both reviewers (e.g. a Repeated Switch that is also Shotgun Surgery) becomes one finding. Keep the stronger framing; list all affected sites. |
| **One Scorecard** | Combined across all smell categories from both reviewers. |

### Degradation

When one reviewer returns nothing usable (error or skip), the report is written from the
other reviewer's findings alone. The report states plainly which bucket did not run; it does
not silently narrow coverage.

### File output

The merged report is written to `code-smells-{target-id}.md` at the workspace root. A
single confirmation sentence in chat names the file path and the total finding count by
severity (e.g. "Written to `code-smells-order-service.md`: 2 HIGH, 3 MEDIUM, 1 LOW.").

---

## Smell Catalogue Coverage

The twelve Modern-12 smells covered by the two bucket skills are split by review difficulty.

| Bucket | Model | Smells |
|---|---|---|
| Structural (local / mechanical) | Sonnet | Mysterious Name, Duplicated Code, Long Function, Long Parameter List, Loops, Repeated Switches |
| Design (cross-cutting / judgment) | Opus | Global Data, Mutable Data, Feature Envy, Data Clumps, Primitive Obsession, Shotgun Surgery |

All twelve smells appear in the Summary table of a consolidated report regardless of which
bucket raised findings.

---

## See Also

- `templates/skills/review-for-code-smells/SKILL.md` — core method skill: severity rubric,
  writing style rules, and finding/report format authoritative source.
- `templates/skills/code-smell-review/SKILL.md` — parallel fan-out orchestration skill:
  consolidated-merge rules, degradation behavior, and file-output specification.
- `templates/skills/review-for-structural-code-smells/SKILL.md` — structural bucket skill:
  definitions for the six local/mechanical smells.
- `templates/skills/review-for-design-code-smells/SKILL.md` — design bucket skill:
  definitions for the six cross-cutting/judgment smells.
