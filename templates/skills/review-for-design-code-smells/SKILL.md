---
name: review-for-design-code-smells
description: |
  Scan code for the six cross-cutting / judgment Fowler code smells — Global Data,
  Mutable Data, Feature Envy, Data Clumps, Primitive Obsession, Shotgun Surgery — and
  point each at its named refactoring. These need whole-target reasoning about data flow,
  ownership, and change locality, so an Opus-tier reviewer is the right fit. Load together
  with the review-for-code-smells core skill, which supplies the method, severity rubric,
  and finding/report format.
  Use when: running the design bucket of a code-smell review (the find-design-smells agent,
  or the design half of an orchestrated code-smell-review).
allowed-tools:
  - Read
  - Bash
---

# Design code smells (the judgment bucket)

This skill is the **catalogue** for the six cross-cutting / judgment smells. It assumes you
have also loaded **`review-for-code-smells`** for the review method, severity rubric,
writing style, and finding/report format. These smells are defined by looking **across** the
whole target — data flow, ownership, and where a change ripples — so read the touched files
in full, not just a diff. Report only smells you can anchor to concrete lines; name the
refactoring for each.

| # | Smell | One-line tell | Primary refactoring(s) |
|---|-------|---------------|------------------------|
| 1 | Global Data | Mutable state reachable from anywhere | Encapsulate Variable |
| 2 | Mutable Data | A value is reassigned/mutated far from its birth | Encapsulate Variable; Split Variable; Extract Function |
| 3 | Feature Envy | A function uses another module's data more than its own | Move Function; Extract Function |
| 4 | Data Clumps | The same 3+ fields recur together | Extract Class; Introduce Parameter Object |
| 5 | Primitive Obsession | Domain concepts modelled as strings/ints/maps | Replace Primitive with Object; Replace Type Code with Subclasses |
| 6 | Shotgun Surgery | One change forces edits scattered across many places | Move Function/Field; Combine Functions into Class/Module |

### 1. Global Data
- **Spot it:** module-level mutable variables, singletons holding mutable state, ambient
  config that any code can write.
- **Why it hurts:** action at a distance — a bug can originate anywhere that touches it.
- **Refactor:** Encapsulate Variable (route all access through functions so mutation has one
  controllable choke point).

### 2. Mutable Data
- **Spot it:** a variable reassigned for a second, unrelated purpose; a structure mutated by
  a distant function; an update whose effect is hard to trace.
- **Why it hurts:** you cannot reason locally about a value that anyone can change.
- **Refactor:** Encapsulate Variable, Split Variable (one variable = one responsibility),
  Extract Function to isolate the update; prefer returning new values.

### 3. Feature Envy
- **Spot it:** a function that reaches repeatedly into another object/module — calling its
  getters, chaining its fields — to do its work.
- **Why it hurts:** behaviour lives apart from the data it needs, so both change together.
- **Refactor:** Move Function (put it next to the data it envies), or Extract Function first
  and move the envious part.

### 4. Data Clumps
- **Spot it:** the same three-plus fields appearing together — as params, as struct fields,
  in DB rows (`x`,`y`,`width`,`height`; `start`,`end`; `street`,`city`,`zip`). Test: delete
  one — do the rest still make sense? If not, they are a clump.
- **Why it hurts:** the missing concept is duplicated everywhere the clump travels.
- **Refactor:** Extract Class (give the clump a name), then Introduce Parameter Object.

### 5. Primitive Obsession
- **Spot it:** money as `float`, a phone number as `str`, a type/status as an int or bare
  string constant, coordinates as a loose `dict`, validation logic scattered wherever the
  primitive is used.
- **Why it hurts:** the domain rule has no home, so it is re-implemented (and mis-implemented).
- **Refactor:** Replace Primitive with Object, Replace Type Code with Subclasses / enum,
  Introduce Parameter Object.

### 6. Shotgun Surgery
- **Spot it:** one conceptual change (add a field, change a format) forces small edits in
  many files/classes. The opposite of Divergent Change.
- **Why it hurts:** easy to miss an edit site; the concept is smeared across the codebase.
- **Refactor:** Move Function / Move Field to gather the scattered behaviour, Combine
  Functions into Class/Module, Inline needless indirection.

> Note: a magic-literal sentinel repeated at several return sites is the lightweight edge of
> Primitive Obsession — Replace Magic Literal with Symbolic Constant. Flag it at LOW.
