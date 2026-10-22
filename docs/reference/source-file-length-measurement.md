---
title: "Reference: Source File Length Measurement"
description: "Lookup for how the file-size standard measures a source file's length: the published rule, what it leaves out, Python and JavaScript raw-versus-measured examples, and why moving decision history frees no lines."
type: reference
status: active
created: 2026-10-21
last_updated: 2026-10-21
components:
  - commit_guardian
  - documentation_system
related_docs:
  - docs/reference/document-length-standard.md
  - docs/architecture/components/commit-guardian.md
  - docs/acceptance-criteria/guardrail-engine/GE-134-history-never-costs-size/GE-134a.yaml
  - templates/skills/doc-enforcer/SKILL.md
  - templates/scripts/commit_guardian/_file_size_ratchet.py
  - templates/scripts/commit_guardian/README.md
---

# Source File Length Measurement

Lets an author who is about to change a `.py`, `.sql`, `.js`, `.mjs`, `.ts`, `.tsx` or `.sh` file work out, by hand, the length the `check-file-size` gate will quote for it. Markdown documents under `docs/` are judged by a different gate; see [document-length-standard.md](document-length-standard.md).

## The rule

The size standard publishes its measurement rule on the `Measures:` line of every refusal, and `describe_measurement_rule()` in `_file_size_ratchet.py` generates that sentence from the counting function in force. Verbatim:

> discards content inside triple-quoted strings and block comments; a decision-history block is not counted: it starts at a comment (prefix '#', '//' and '--') whose whole text is DECISION HISTORY, takes a '=' rule line directly above it if there is one, and ends at the first line that is not a comment line of that prefix; counts every remaining line, including blank lines and ordinary '#' comments.

If the function's output and this quotation ever differ, the function is right: it is the rule in force.

## What is left out, and what is counted

| Content | Measured | Notes |
|---|---|---|
| Triple-quoted strings (`"""` or `'''`) | No | Docstrings included. The region and its closing newline contribute zero lines. |
| Block comments (`/* ... */`) | No | JSDoc included. Same zero-line rule. |
| Decision-history block | No | Line-comment form only; see below. Added by GE-134a-1. |
| Blank lines | Yes | |
| Ordinary comment lines (`#`, `//`, `--`) | Yes | A comment that merely mentions the words `DECISION HISTORY` is an ordinary comment. |
| Code | Yes | |

The same rule applies to every covered extension; it does not look at the file's language.

### The decision-history block

- It starts at a line comment whose whole text is `DECISION HISTORY`. `# DECISION HISTORY notes are below` starts none.
- A rule line of `=` characters directly above the heading, with the same prefix, belongs to the block. One separated from the heading by any other line is counted.
- It ends at the first line that is not a comment line with the heading's own prefix. The code line directly after it is counted.
- A block inside text the rule already leaves out (a module docstring or a block comment) is not subtracted a second time.
- A file whose whole content is one block measures `0` and is not refused as empty or unreadable.

The block's heading, underline and entry form are defined by the decision-history convention in the [doc-enforcer skill](../../templates/skills/doc-enforcer/SKILL.md) and are not repeated here. The requirement behind the exclusion is [GE-134a](../acceptance-criteria/guardrail-engine/GE-134-history-never-costs-size/GE-134a.yaml).

## Examples

Raw count is the physical line count; measured length is what the gate quotes.

### Python: 15 raw lines, 8 measured

```python
"""Parse the config file."""                       # not counted (docstring)
import json                                        # counted
                                                   # counted (blank)
# Load the file and return its mapping.            # counted (ordinary comment)
def load(path):                                    # counted
    with open(path) as handle:                     # counted
        return json.load(handle)                   # counted
                                                   # counted (blank)
                                                   # counted (blank)
# ==============                                   # not counted (rule line above heading)
# DECISION HISTORY                                 # not counted
# ==============                                   # not counted
# - 2026-10-01 [python-coder/X-1]: Created.        # not counted
# - 2026-10-05 [python-coder/X-2]: Added errors.   # not counted
# - 2026-10-09 [python-coder/X-3]: Empty file -> {}.  # not counted
```

15 raw - 1 (docstring) - 6 (block) = 8 measured.

### JavaScript: 12 raw lines, 5 measured

```javascript
// DECISION HISTORY                  // not counted (no rule lines in this form)
// - 2026-10-01 [coder/X-1]: Created.   // not counted
// - 2026-10-05 [coder/X-2]: Retries once.   // not counted
                                     // counted (blank; the block ended at it)
/* Build the request. */             // not counted (block comment)
/**                                  // not counted
 * Fetch one record.                 // not counted
 */                                  // not counted
export async function fetchRecord(id) {  // counted
  // retry once                      // counted (ordinary comment)
  return get(id);                    // counted
}                                    // counted
```

12 raw - 3 (block) - 4 (block comment and JSDoc) = 5 measured.

## Moving history out of a file frees no lines

A decision-history block costs no measured lines. Moving a file's decision history into another file or document therefore removes nothing from its measured length, and it cannot bring an over-limit file under its limit or make room to add code. Only measured lines count: deleting blank lines or ordinary comments reduces the length; deleting a docstring, a block comment or a decision-history block does not.

The same holds for growth. The ratchet judges the measured lines a change puts into a file, so a change that only appends entries to a decision-history block adds none and is not refused for size.

## Related

- Limits per extension and the refusal behaviour: `file_size` in [commit_guardian README](../../templates/scripts/commit_guardian/README.md) and [commit-guardian.md](../architecture/components/commit-guardian.md).
- Known gap: a `/*` inside a string literal is read as a block-comment start, see [the open known issue](../known-issues/commit-guardian/open-high-ki-cg-20261009-file-size-measure-strips-from-slash-star-inside-strings.md).
