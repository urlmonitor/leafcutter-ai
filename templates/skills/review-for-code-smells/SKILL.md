---
name: review-for-code-smells
description: |
  Shared core method for the code-smell reviewers: how to gather code, infer the stack,
  classify severity, write findings, and format the report — mapping every finding to
  Martin Fowler's named refactoring (Refactoring, 2nd ed). The Modern-12 smell catalogue
  itself lives in two bucket skills that build on this one. Load this together with a
  bucket skill; on its own it defines the process, not the smells.
  Use when: an agent runs a code-smell / refactoring review and needs the review method,
  severity rubric, writing style, and finding/report format.
allowed-tools:
  - Read
  - Bash
---

# Review For Code Smells — core method

This is the **shared method** for reviewing code against Martin Fowler's *Refactoring*
(2nd ed) "Bad Smells in Code". It defines the process and the output; the **smell
definitions** live in two bucket skills that each build on this one:

- **`review-for-structural-code-smells`** — local / mechanical smells: Mysterious Name,
  Duplicated Code, Long Function, Long Parameter List, Loops, Repeated Switches.
- **`review-for-design-code-smells`** — cross-cutting / judgment smells: Global Data,
  Mutable Data, Feature Envy, Data Clumps, Primitive Obsession, Shotgun Surgery.

Load this skill **together with one (or both) bucket skills**. This skill gives you the
method, severity rubric, writing style, and finding/report format; the bucket skill gives
you the smells to scan for. Every finding names the **smell** and the **refactoring** that
removes it. You diagnose and give direction — you do **not** hand back a full rewrite.

## Review method

Run these steps in order. Do not skip any.

### 1. Gather
Find the code to review, in this priority order:
1. Files/folders the user attached, linked, or referenced — read them fully, follow imports.
2. Code pasted inline in the message.
3. Neither — ask the user to paste, attach, or name the code. Ask for nothing else.

Use `Bash` (`grep`, `git diff`, `wc -l`) to locate recurrence, count parameters, and find
repeated field groups across files — several smells only show up when you look across the
whole target, not one function.

### 2. Infer
Silently derive, then state briefly so the user can correct you:
- **Language / stack** (with High / Medium / Low confidence).
- **What the code is trying to do** — reconstruct intent from names and data flow.

### 3. Scan
Walk the code against **each smell in your loaded bucket skill(s)**. A smell is only a
finding when you can point at concrete lines — never report a smell you cannot anchor.

### 4. Classify severity
Assign every finding exactly one severity (rubric below).

### 5. Report
Emit the output in the format below. Direction only — never a full rewrite.

## Severity classification

| Severity | Criteria |
|----------|----------|
| **HIGH** | Actively multiplies risk of bugs or missed edits now — duplication across edit sites, Shotgun Surgery, Global/Mutable Data driving real bugs, Repeated Switches whose cases already diverge. |
| **MEDIUM** | Clear maintainability drag that will bite on the next change — Long Function, Long Parameter List, Feature Envy, Data Clumps, Primitive Obsession. |
| **LOW** | Readability / polish — Mysterious Name, a single intent-hiding Loop, minor local smells safe to defer. |

Severity is about *impact*, not smell identity — a Mysterious Name on a widely-used public
API can be MEDIUM; a duplicated one-liner in a test can be LOW.

## Writing style

Write as if talking to a teammate at a whiteboard. Short sentences. Everyday words.

**Do NOT write like this:**
> "The routine conflates orthogonal responsibilities, thereby degrading cohesion and
> elevating the maintenance surface."

**Write like this instead:**
> "This function validates the input and also saves it. That is two jobs. Split them so
> each can change on its own."

Rules:
- **3–5 sentences per "What's wrong" block.** Say what the code does, why it is a smell, stop.
- **One idea per sentence.** If you joined two thoughts with a comma or semicolon, split them.
- **Active voice.** "The function reaches into `order`", not "`order` is reached into."
- **No jargon without a plain gloss.** Write "Feature Envy (the function leans on another
  object's data more than its own)", not just "Feature Envy".
- **No filler.** Cut "it is worth noting", "as previously stated".

## Finding format

Every finding uses this structure, in this exact order:

1. **Title** — `[<SMELL NAME>] <short description>` (e.g. `[LONG FUNCTION] save() does five jobs`).
2. **What's wrong** — 3–5 plain-English sentences.
3. **Refactoring** — the named Fowler refactoring(s) to apply, one line.
4. **File** — exact path and line range (e.g. `src/order.py:42–91`).
5. **Before** (code block) — verbatim from the source, filename+lines as a first-line
   comment. 3–15 lines. Never alter it.
6. **After** (code block) — a minimal sketch. Start the block with
   `// direction only – not a full rewrite` (use the target language's comment syntax).
   5–15 lines, showing the shape of the fix, not a finished implementation.

## Output format

Produce, in order:

1. **Inferred Context** — a small table: Language/Stack (+confidence), Inferred Intent.
2. **Summary** — a table counting findings per smell and per severity (HIGH/MEDIUM/LOW totals).
3. **HIGH** section — all high-severity findings.
4. **MEDIUM** section — same structure.
5. **LOW** section — same structure.
6. **Scorecard** — a 0–10 rating per smell category that had signal, a one-sentence verdict
   each, and an overall mean rounded to one decimal.

Finding IDs follow `H-N`, `M-N`, `L-N`.

**When invoked as part of an orchestrated review** (a parent `code-smell-review` fanned you
out for one bucket): skip the Inferred-Context prose and **return your bucket's findings
sections + Summary rows + Scorecard rows** so the parent can merge them into one report.
**When invoked standalone**: emit the full report above.

## Constraints

- **Direction, not rewrite.** The After block shows the move; it is not production code.
- **Anchor everything.** No finding without a concrete file + line range.
- **No noise.** Report real smells only. Do not pad with theoretical edge cases, and group
  repeated occurrences of one smell into a single finding with a list of sites.
- **Name the refactoring.** Every finding cites at least one Fowler refactoring move.
- **Before is verbatim.** Never edit the source shown in a Before block.
