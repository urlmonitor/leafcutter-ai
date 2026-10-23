---
title: "Reference: Source File Length Measurement"
description: "Lookup for how the file-size standard measures a source file's length: the published rule, what counts and what does not, Python, JavaScript, shell and used-string raw-versus-measured examples, the INDETERMINATE outcome, and the backstop for an over-limit file."
type: reference
status: active
created: 2026-10-21
last_updated: 2026-10-23
components:
  - commit_guardian
  - documentation_system
related_docs:
  - docs/reference/document-length-standard.md
  - docs/architecture/components/commit-guardian.md
  - docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127d-3.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-134-history-never-costs-size/GE-134a.yaml
  - templates/skills/doc-enforcer/SKILL.md
  - templates/scripts/commit_guardian/_file_size_measure/rule_statement.py
  - templates/scripts/commit_guardian/_file_size_ratchet.py
  - templates/scripts/commit_guardian/README.md
---

# Source File Length Measurement

Lets an author who is about to change a `.py`, `.sql`, `.js`, `.mjs`, `.ts`, `.tsx` or `.sh` file work out, by hand, the length the `check-file-size` gate will quote for it. Markdown documents under `docs/` are judged by a different gate; see [document-length-standard.md](document-length-standard.md).

## The rule

A line counts only if it holds a code token. The size standard publishes its measurement rule on the `Measures:` line of every refusal, and `describe_measurement_rule()` in `_file_size_ratchet.py` generates that sentence (through `_file_size_measure/rule_statement.py`) from what the measure actually does with probe content. Verbatim:

> does not count comments of every style (line and block comments in every language measured), standalone strings (Python strings standing alone as statements: docstrings, bare strings and trailing blocks) and blank lines; counts every line of a used string (a Python string that is assigned, passed, returned or part of a larger expression), every line of an f-string and every other line of code.

If the function's output and this quotation ever differ, the function is right: it is the rule in force. The same sentence follows `MEASUREMENT RULE:` in the `check_file_size.py` row of the [commit_guardian README](../../templates/scripts/commit_guardian/README.md).

This rule replaced the GE-134a rule, under which a line-comment DECISION HISTORY block was uncounted while ordinary comments and blank lines counted. The requirement now in force is [GE-127d-3](../acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127d-3.yaml) and its children.

## What is left out, and what is counted

Measurement is per language, by a tokenizer (`templates/scripts/commit_guardian/_file_size_measure/`), not by a delimiter pattern. The language is chosen from the file's extension.

| Content | Counted | Notes |
|---|---|---|
| Comment, any style (`#`, `//`, `--`, `/* ... */`) | No | A line holding only comment text is dropped. Code before a trailing comment still counts the line. JSDoc is a block comment. |
| Python string standing alone as a statement | No | Docstrings, bare strings, and a trailing DECISION HISTORY string block. |
| Python string that is used | Yes | Assigned, passed, returned or part of an expression; every line of it counts. |
| Standalone f-string | Yes | Every line counts. |
| Blank line | No | Anywhere, including inside a used string. |
| Comment marker inside a string, glob, regex literal or here-document | Yes | It is code, not a comment. |
| Any other code line | Yes | |

A DECISION HISTORY block is not special: in a line-comment form it is comments, and in a Python string form it is a standalone string, so it is uncounted either way. A file whose whole content is uncounted measures `0`.

The block's heading, underline and entry form are defined by the decision-history convention in the [doc-enforcer skill](../../templates/skills/doc-enforcer/SKILL.md) and are not repeated here. The requirement that first made history free is [GE-134a](../acceptance-criteria/guardrail-engine/GE-134-history-never-costs-size/GE-134a.yaml); its mechanism was superseded by GE-127d-3, which leaves history free as a consequence of leaving all comments and standalone strings out.

### INDETERMINATE

A file the tokenizer cannot read as its language (for example an unterminated string or block comment), or whose extension has no tokenizer, is INDETERMINATE. The gate reports that it could not measure the file; it never falls back to a raw line count and never reports `0`.

## Examples

Raw count is the physical line count; measured length is what the gate quotes. Each figure below was produced by the deployed measure.

### Python: 18 raw lines, 5 measured

```python
"""Parse the config file."""                       # not counted (docstring)
import json                                        # counted
                                                   # not counted (blank)
# Load the file and return its mapping.            # not counted (comment)
DEFAULTS = {"mode": "strict"}  # fallback          # counted (code before comment)
                                                   # not counted (blank)
                                                   # not counted (blank)
def load(path):                                    # counted
    """Read path."""                               # not counted (docstring)
    with open(path) as handle:                     # counted
        return json.load(handle)                   # counted
                                                   # not counted (blank)
                                                   # not counted (blank)
# ==============                                   # not counted (comment)
# DECISION HISTORY                                 # not counted (comment)
# ==============                                   # not counted (comment)
# - 2026-10-01 [python-coder/X-1]: Created.        # not counted (comment)
# - 2026-10-05 [python-coder/X-2]: Added errors.   # not counted (comment)
```

18 raw - 13 uncounted = 5 measured.

### Python: used strings and markers inside strings, 10 raw lines, 9 measured

```python
BANNER = """                                       # counted (assigned string, every line)
usage: tool                                        # counted
  --help                                           # counted
"""                                                # counted
f"""                                               # counted (standalone f-string)
{BANNER}                                           # counted
"""                                                # counted
"""bare string"""                                  # not counted (standalone string)
print("# not a comment")                           # counted (marker inside a string)
PATTERN = "/* not a comment */"                    # counted (marker inside a string)
```

10 raw - 1 (standalone string) = 9 measured. Annotations on the right are for reading only; they are not part of the measured sample.

### JavaScript: 10 raw lines, 4 measured

```javascript
// Build the request.                    // not counted (comment)
/**                                      // not counted (block comment)
 * Fetch one record.                     // not counted
 */                                      // not counted
export async function fetchRecord(id) {  // counted
  // retry once                          // not counted (comment)
                                         // not counted (blank)
  const note = "// not a comment";       // counted (marker inside a string)
  return get(id); /* inline */           // counted (code before block comment)
}                                        // counted
```

10 raw - 6 uncounted = 4 measured.

### Shell: 6 raw lines, 4 measured

```bash
#!/bin/sh                 # not counted (comment, shebang included)
# header comment          # not counted
cat <<EOF                 # counted
# inside here-document    # counted (here-document body is not a comment)
EOF                       # counted
echo "a # b"   # trailing # counted (code before comment)
```

6 raw - 2 uncounted = 4 measured.

## Moving history out of a file frees no lines

A decision-history block costs no measured lines. Moving a file's decision history into another file or document therefore removes nothing from its measured length, and it cannot bring an over-limit file under its limit or make room to add code.

The same holds for restyling and for every other uncounted form. No comment style and no standalone string counts, so converting `//` runs to `/* */`, adding or deleting docstrings, or moving a DECISION HISTORY block elsewhere changes nothing in the measured length. Only code-token lines move it. Deleting blank lines does not either: they never count.

## Over-limit files: the backstop

For a file whose previous version already stood over its limit, a change is refused when its measured length falls while its total physical line count rises. That shape is the signature of moving content into forms the measure does not count (comments, standalone strings) instead of shortening the file. Example: a 520-line (measured) file over a 500-line limit that is edited to 510 measured while its raw count goes from 700 to 705 is refused; make the reduction and the added commenting in separate commits and each passes on its own. A file under its limit, or a change in which the raw count does not rise, is not affected. The refusal block is rendered by `_file_size_measure/backstop.py`.

## Related

- Limits per extension and the refusal behaviour: `file_size` in [commit_guardian README](../../templates/scripts/commit_guardian/README.md) and [commit-guardian.md](../architecture/components/commit-guardian.md).
- Requirement: [GE-127d-3](../acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127d-3.yaml).
