---
title: "Reference: Code Smell Finding Anatomy and Named Catalogue"
description: "All twelve Modern-12 Fowler code smells with their bucket grouping, primary refactorings, and the exact finding format produced by the review-for-code-smells skill family."
type: reference
status: active
created: 2026-08-11
last_updated: 2026-08-11
components:
  - review_system
related_docs:
  - templates/skills/review-for-code-smells/SKILL.md
  - templates/skills/review-for-structural-code-smells/SKILL.md
  - templates/skills/review-for-design-code-smells/SKILL.md
---

# Code Smell Finding Anatomy and Named Catalogue

The `review-for-code-smells` skill family reviews code against Martin Fowler's
*Refactoring* (2nd ed) "Bad Smells in Code". This document names every smell in the
Modern-12 catalogue, groups them by bucket, records the primary Fowler refactoring for
each, and specifies the exact finding format that every reviewer in the family emits.

---

## Smell Catalogue Overview

The twelve smells are divided into two buckets: **Structural** (local, mechanical
smells handled by the `find-structural-smells` agent) and **Design** (cross-cutting,
judgment smells handled by the `find-design-smells` agent).

| # | Bucket | Smell | One-line tell | Primary refactoring(s) |
|---|--------|-------|---------------|------------------------|
| 1 | Structural | Mysterious Name | You must read the body to know what it does | Rename Variable / Rename Function / Rename Field |
| 2 | Structural | Duplicated Code | The same shape appears in 2+ places | Extract Function; Pull Up Method; Slide Statements |
| 3 | Structural | Long Function | One function does many things or many lines | Extract Function; Replace Temp with Query |
| 4 | Structural | Long Parameter List | 4+ params, or params that always travel together | Introduce Parameter Object; Preserve Whole Object |
| 5 | Structural | Loops | A raw loop hides its intent (map/filter/reduce) | Replace Loop with Pipeline |
| 6 | Structural | Repeated Switches | The same switch/if-chain on a type recurs | Replace Conditional with Polymorphism; Replace Type Code with Subclasses |
| 7 | Design | Global Data | Mutable state reachable from anywhere | Encapsulate Variable |
| 8 | Design | Mutable Data | A value is reassigned/mutated far from its birth | Encapsulate Variable; Split Variable; Extract Function |
| 9 | Design | Feature Envy | A function uses another module's data more than its own | Move Function; Extract Function |
| 10 | Design | Data Clumps | The same 3+ fields recur together across call sites | Extract Class; Introduce Parameter Object |
| 11 | Design | Primitive Obsession | Domain concepts modelled as bare strings/ints/maps | Replace Primitive with Object; Replace Type Code with Subclasses |
| 12 | Design | Shotgun Surgery | One change forces edits scattered across many files | Move Function / Move Field; Combine Functions into Class/Module |

---

## Structural Bucket

Structural smells are local, mostly within-a-function smells. They surface from
reading a single file or function body and are assigned to the `find-structural-smells`
agent (Sonnet tier).

| Smell | Spot it by | Primary refactoring(s) | Secondary refactoring(s) |
|-------|-----------|------------------------|--------------------------|
| **Mysterious Name** | A name that needs a comment or body-read to understand; abbreviations (`d`, `tmp`, `mgr`); names that lie about what the thing does | Rename Variable | Rename Function; Rename Field |
| **Duplicated Code** | Identical or near-identical expressions/blocks; the same calculation in two branches; copy-pasted functions with one value changed | Extract Function | Pull Up Method; Slide Statements |
| **Long Function** | More than ~15–20 lines, or mixed levels of abstraction; comments that announce sections (`// now validate`, `// then save`); deep nesting | Extract Function | Replace Temp with Query; Decompose Conditional; Replace Loop with Pipeline |
| **Long Parameter List** | 4+ parameters; booleans that flip behaviour; several params that always arrive together; a param derived from another param | Introduce Parameter Object | Preserve Whole Object; Replace Parameter with Query; Remove Flag Argument |
| **Loops** | A raw `for`/`while` that is really a map, filter, or reduce; a loop that both transforms, accumulates, and filters at once | Replace Loop with Pipeline | Split loop into named stages |
| **Repeated Switches** | The same `switch`/`if-elif` on the same type code appearing in more than one place; adding a case means hunting down every copy | Replace Conditional with Polymorphism | Replace Type Code with Subclasses; dispatch table / strategy map |

### Notes on Repeated Switches boundary

Repeated Switches shades into the Design bucket when the same type-code switch is
spread across many modules — that is Shotgun Surgery. When that cross-module breadth is
detected, the finding belongs in the design reviewer pass.

---

## Design Bucket

Design smells require whole-target reasoning about data flow, ownership, and where a
change ripples. They are assigned to the `find-design-smells` agent (Opus tier).

| Smell | Spot it by | Primary refactoring(s) | Secondary refactoring(s) |
|-------|-----------|------------------------|--------------------------|
| **Global Data** | Module-level mutable variables; singletons holding mutable state; ambient config that any code can write | Encapsulate Variable | — |
| **Mutable Data** | A variable reassigned for a second unrelated purpose; a structure mutated by a distant function; an update whose effect is hard to trace | Encapsulate Variable | Split Variable; Extract Function |
| **Feature Envy** | A function that reaches repeatedly into another object/module — calling its getters, chaining its fields — to do its work | Move Function | Extract Function (extract the envious part, then move) |
| **Data Clumps** | The same three-plus fields appearing together — as params, as struct fields, in DB rows (`x`,`y`,`width`,`height`; `street`,`city`,`zip`). Test: delete one; if the rest no longer make sense, it is a clump | Extract Class | Introduce Parameter Object |
| **Primitive Obsession** | Money as `float`; a phone number as `str`; a type/status as a bare int or string constant; validation logic scattered wherever the primitive is used | Replace Primitive with Object | Replace Type Code with Subclasses; Introduce Parameter Object |
| **Shotgun Surgery** | One conceptual change (add a field, change a format) forces small edits in many files/classes. The opposite of Divergent Change | Move Function / Move Field | Combine Functions into Class/Module; Inline needless indirection |

### Note on Primitive Obsession edge case

A magic-literal sentinel repeated at several return sites is the lightweight edge of
Primitive Obsession. The refactoring is Replace Magic Literal with Symbolic Constant.
Flag it at LOW severity.

---

## Severity Rubric

Each finding is assigned exactly one severity based on impact, not smell identity.

| Severity | Criteria | Typical smells at this tier |
|----------|----------|----------------------------|
| **HIGH** | Actively multiplies risk of bugs or missed edits now — duplication across edit sites, Shotgun Surgery, Global/Mutable Data driving real bugs, Repeated Switches whose cases already diverge | Duplicated Code, Shotgun Surgery, Global Data, Repeated Switches |
| **MEDIUM** | Clear maintainability drag that will bite on the next change | Long Function, Long Parameter List, Feature Envy, Data Clumps, Primitive Obsession |
| **LOW** | Readability/polish; safe to defer | Mysterious Name, a single intent-hiding Loop, minor local smells |

Severity is assigned per finding, not per smell class. A Mysterious Name on a
widely-used public API can be MEDIUM. A duplicated one-liner in a test file can be LOW.

---

## Finding Format

Every finding produced by the skill family uses this structure in this exact order.

| Position | Field | Format | Constraints |
|----------|-------|--------|-------------|
| 1 | **Title** | `[<SMELL NAME>] <short description>` | E.g. `[LONG FUNCTION] save() does five jobs`. Smell name in capitals. |
| 2 | **What's wrong** | Plain-English prose | 3–5 sentences. State what the code does, why it is a smell, stop. Active voice. No jargon without a plain gloss. |
| 3 | **Refactoring** | Named Fowler refactoring(s), one line | At least one Fowler move named. E.g. `Refactoring: Extract Function`. |
| 4 | **File** | Exact path + line range | E.g. `src/order.py:42–91`. |
| 5 | **Before** (code block) | Verbatim from source | Fenced code block. First line is a comment naming the file and lines. 3–15 lines. Never altered. |
| 6 | **After** (code block) | Direction-only sketch | Fenced code block. First line: `// direction only – not a full rewrite` (using the target language's comment syntax). 5–15 lines. Shows the shape of the fix, not a finished implementation. |

### Title examples by smell

| Smell | Example title |
|-------|--------------|
| Mysterious Name | `[MYSTERIOUS NAME] process() tells you nothing` |
| Duplicated Code | `[DUPLICATED CODE] amount calculation copied to three branches` |
| Long Function | `[LONG FUNCTION] render() does layout, fetch, and error handling` |
| Long Parameter List | `[LONG PARAMETER LIST] send_email() takes 7 separate arguments` |
| Loops | `[LOOPS] for-loop hides a filter+map` |
| Repeated Switches | `[REPEATED SWITCHES] shape dispatch copied in draw() and export()` |
| Global Data | `[GLOBAL DATA] CONFIG mutated by every request handler` |
| Mutable Data | `[MUTABLE DATA] result re-used for two unrelated accumulations` |
| Feature Envy | `[FEATURE ENVY] format_invoice() chains through Order's internals` |
| Data Clumps | `[DATA CLUMPS] street, city, zip travel together in four functions` |
| Primitive Obsession | `[PRIMITIVE OBSESSION] money stored as float throughout billing` |
| Shotgun Surgery | `[SHOTGUN SURGERY] adding a status field touches 9 files` |

### Concrete finding example

```
[LONG FUNCTION] load_report() does five jobs                     ← Title

load_report() reads the file, parses headers, applies filters,   ← What's wrong
formats rows, and writes the output. That is five separate jobs
in one body. The filtering logic is buried behind 40 lines of
parsing. If the filter rules change, the whole function is in
scope.

Refactoring: Extract Function (one function per job).            ← Refactoring

File: src/reports/loader.py:12–58                                ← File

```python
# src/reports/loader.py:12–58
def load_report(path, filters, fmt, out, encoding):
    with open(path, encoding=encoding) as f:
        raw = f.read()
    headers = raw.split('\n')[0].split(',')
    rows = [r.split(',') for r in raw.split('\n')[1:]]
    filtered = [r for r in rows if all(f(r) for f in filters)]
    formatted = fmt(headers, filtered)
    out.write(formatted)
```                                                               ← Before block

```python
# direction only – not a full rewrite
def load_report(path, filters, fmt, out, encoding):
    raw = read_file(path, encoding)
    headers, rows = parse_rows(raw)
    filtered = apply_filters(rows, filters)
    out.write(fmt(headers, filtered))
```                                                               ← After sketch
```

---

## Output Report Structure

When a reviewer emits a full standalone report (not a sub-agent pass), the sections
appear in this order.

| # | Section | Content |
|---|---------|---------|
| 1 | **Inferred Context** | Table: Language/Stack (with High/Medium/Low confidence), Inferred Intent. |
| 2 | **Summary** | Table counting findings per smell and per severity (HIGH/MEDIUM/LOW totals). |
| 3 | **HIGH** | All high-severity findings, each in the six-field finding format. |
| 4 | **MEDIUM** | All medium-severity findings. |
| 5 | **LOW** | All low-severity findings. |
| 6 | **Scorecard** | 0–10 rating per smell category that had signal, one-sentence verdict each, and an overall mean rounded to one decimal. |

Finding IDs follow the pattern `H-N`, `M-N`, `L-N` (e.g. `H-1`, `M-3`, `L-2`).

When invoked as part of an orchestrated review (a parent `code-smell-review` agent
fanned out one bucket), the reviewer omits the Inferred-Context prose and returns only
its bucket's findings sections, Summary rows, and Scorecard rows for the parent to merge.

---

## See Also

- `templates/skills/review-for-code-smells/SKILL.md` — core method, severity rubric, writing style, and finding/report format.
- `templates/skills/review-for-structural-code-smells/SKILL.md` — structural bucket catalogue (smells 1–6).
- `templates/skills/review-for-design-code-smells/SKILL.md` — design bucket catalogue (smells 7–12).
- `.claude/agents/find-structural-smells.md` — agent template for the structural reviewer (Sonnet tier).
- `.claude/agents/find-design-smells.md` — agent template for the design reviewer (Opus tier).
