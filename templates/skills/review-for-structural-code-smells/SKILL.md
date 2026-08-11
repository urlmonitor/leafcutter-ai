---
name: review-for-structural-code-smells
description: |
  Scan code for the six local / mechanical Fowler code smells — Mysterious Name,
  Duplicated Code, Long Function, Long Parameter List, Loops, Repeated Switches — and
  point each at its named refactoring. These are the near-lint, mostly-within-a-function
  smells; a Sonnet-tier reviewer handles them well. Load together with the
  review-for-code-smells core skill, which supplies the method, severity rubric, and
  finding/report format.
  Use when: running the structural bucket of a code-smell review (the find-structural-smells
  agent, or the structural half of an orchestrated code-smell-review).
allowed-tools:
  - Read
  - Bash
---

# Structural code smells (the straightforward bucket)

This skill is the **catalogue** for the six local / mechanical smells. It assumes you have
also loaded **`review-for-code-smells`** for the review method, severity rubric, writing
style, and finding/report format. Scan the target for each smell below; report only smells
you can anchor to concrete lines; name the refactoring for each.

| # | Smell | One-line tell | Primary refactoring(s) |
|---|-------|---------------|------------------------|
| 1 | Mysterious Name | You must read the body to know what it does | Rename Variable / Function / Field |
| 2 | Duplicated Code | The same shape appears in 2+ places | Extract Function; Pull Up; Slide Statements |
| 3 | Long Function | One function does many things / many lines | Extract Function; Replace Temp with Query |
| 4 | Long Parameter List | 4+ params, or params that travel together | Introduce Parameter Object; Preserve Whole Object |
| 5 | Loops | A raw loop hides its intent (map/filter/reduce) | Replace Loop with Pipeline |
| 6 | Repeated Switches | The same switch/if-chain on a type recurs | Replace Conditional with Polymorphism; Replace Type Code with Subclasses |

### 1. Mysterious Name
- **Spot it:** a name that needs a comment or a body-read to understand; abbreviations
  (`d`, `tmp`, `mgr`); names that lie about what the thing does.
- **Why it hurts:** naming is the cheapest documentation there is; a wrong name misleads
  every future reader and hides duplication.
- **Refactor:** Rename Variable / Rename Function / Rename Field. If you cannot find a good
  name, the design is unclear — that is itself the finding.

### 2. Duplicated Code
- **Spot it:** identical or near-identical expressions/blocks; the same calculation in two
  branches; copy-pasted functions with one value changed. Grep across the target.
- **Why it hurts:** every copy is a place the next change can be forgotten.
- **Refactor:** Extract Function (same class), Pull Up Method (siblings), Slide Statements
  then Extract (near-duplicates).

### 3. Long Function
- **Spot it:** more than ~15–20 lines *or* mixed levels of abstraction in one body; comments
  that announce sections ("// now validate", "// then save"); deep nesting.
- **Why it hurts:** you must hold the whole thing in your head to change any part.
- **Refactor:** Extract Function (name the intent, not the mechanics), Replace Temp with
  Query, Decompose Conditional, Replace Loop with Pipeline.

### 4. Long Parameter List
- **Spot it:** 4+ parameters; booleans that flip behaviour; several params that always
  arrive together; a param derived from another param.
- **Why it hurts:** hard to call correctly, easy to transpose arguments, signals a function
  doing too much.
- **Refactor:** Introduce Parameter Object, Preserve Whole Object, Replace Parameter with
  Query, Remove Flag Argument.

### 5. Loops
- **Spot it:** a raw `for`/`while` that is really a map, filter, or reduce; a loop that both
  transforms and accumulates and filters at once.
- **Why it hurts:** the loop's *intent* is buried in mechanics; readers must simulate it.
- **Refactor:** Replace Loop with Pipeline (`map`/`filter`/`reduce`/comprehension); split a
  multi-purpose loop into named stages.

### 6. Repeated Switches
- **Spot it:** the same `switch`/`if-elif` on the same type code appearing in more than one
  place; adding a case means hunting down every copy.
- **Why it hurts:** the compiler cannot tell you which copy you forgot.
- **Refactor:** Replace Conditional with Polymorphism, Replace Type Code with Subclasses;
  in a stateless language, a dispatch table / strategy map.

> Note: Repeated Switches shades into the design bucket when the *same* type-code switch is
> smeared across many modules (that is Shotgun Surgery). If you see that breadth, flag it and
> let the design reviewer (`review-for-design-code-smells`) own the cross-module call.
