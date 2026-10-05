---
title: "Product truth: the generator writes LF on Windows instead of CRLF"
status: todo
components:
  - ux_prototyping
created: 2026-10-03
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - product-truth
  - windows
last_updated: 2026-10-03
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Product truth: the generator writes LF on Windows instead of CRLF

## Actor / Goal
In order that product-truth authoring on Windows produces no line-ending noise, we need
`generate_product_truth.py` to write LF, so that the files match `.gitattributes` (eol=lf) without
manual conversion.

## Context
- **Live reproduction (2026-10-02 and 2026-10-03):** three authoring agents on two branches
  (mock-data-author, flow-author ×2) found that running
  `docs/product-truth/scripts/generate_product_truth.py` on Windows rewrote `index.json` and the
  touched flow files with CRLF line endings. Each converted them back to LF by hand.
- **Cause:** `_write_text` (`generate_product_truth.py:339-341`) calls
  `path.write_text(text, encoding="utf-8")` without `newline="\n"`. On Windows that translates
  every `\n` to `\r\n`.
- `--check` compares content, so the drift is invisible until git normalises it, and it shows up
  as noise in working-tree diffs.

## Scope (no acceptance criteria by user decision)
- Write with `newline="\n"`, or open in binary.
- Check the store's other writers (validate/apply_flow_backlinks scripts) for the same pattern.
- Test: the written bytes contain no `\r`, whatever the platform.

## Out of Scope
- Other repository generators.

## Comments

## Implementation Tasks
### test-writer
- [ ] Byte-level LF test for the generator's writes.
### python-coder
- [ ] `newline="\n"` on every product-truth script write.

## Risk & Safety
- Touches money? No.
- Touches data? No; formatting of generated files only.
- Reversibility? Fully reversible.
