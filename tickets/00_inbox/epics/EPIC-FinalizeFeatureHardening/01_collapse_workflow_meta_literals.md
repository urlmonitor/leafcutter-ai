---
title: "Collapse non-literal meta to pure literals in all workflow scripts"
status: todo
components:
  - build_pipeline
created: 2026-06-24
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/create-ticket.js
  - templates/workflows-js/plan-feature.js
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 01: Collapse non-literal meta to pure literals in all workflow scripts

## Actor / Goal

In order for `/finalize-feature` (and the other workflow-backed slash commands)
to run at all, we need every `export const meta = {...}` block in
`templates/workflows-js/` to be a **pure literal**, so the `Workflow` tool stops
rejecting the scripts at parse time.

## Context

The `Workflow` tool parses `meta` at the AST level and rejects any non-literal
node (variables, calls, spreads, template interpolation, and the `+` operator).
`finalize-feature.js` builds `meta.description` and several `meta.phases` entries
with string concatenation, producing `BinaryExpression` nodes, so it fails with:

```
Invalid workflow script: meta must be a pure literal: non-literal node type in meta: BinaryExpression
```

Analysis confirmed 5 of 6 scripts violate the contract:

| Script | Violating field(s) |
|--------|--------------------|
| `finalize-feature.js` | `description` (6-way `+`), multiple `phases[]` entries |
| `build-epic.js` | `description` |
| `build-ticket.js` | `description` |
| `create-ticket.js` | `description` |
| `plan-feature.js` | `description` |

`quick-fix.js` is already clean and is the template to copy.

This is a `python-coder`-assigned ticket only because it is the repo's standards
coder; the edits are to `.js` files (collapse concatenated string segments into
single string literals). No `.js` runtime test framework change is required —
ticket 02 adds the validation gate; the verification here is that each script's
`meta` contains no `BinaryExpression`.

## Acceptance Criteria

- [ ] AC-1: `meta.description` in each of the 5 scripts is a single string literal
  (no `+`), with rendered text byte-identical to the previous concatenated value
  (trailing spaces at former join points preserved; no double spaces introduced).
- [ ] AC-2: Every entry in `finalize-feature.js`'s `meta.phases` array is a single
  string literal (no `+`).
- [ ] AC-3: After the change, invoking each of the 5 workflows via the `Workflow`
  tool no longer raises the `meta must be a pure literal` error (it proceeds past
  the parse stage). For `finalize-feature.js` this is the unblock that lets the
  rest of the epic be verified.
- [ ] AC-4: No change to any `run()` body or workflow behavior — only `meta` is edited.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

## Implementation Tasks
- [ ] For each of the 5 scripts, replace the `+`-concatenated `meta.description`
  with one string literal (mechanically join segments, preserve trailing spaces).
- [ ] In `finalize-feature.js`, replace each `+`-built `phases[]` entry with a
  single literal.
- [ ] Diff the rendered strings before/after to confirm byte-identical text.

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? High — single-field edits, trivially revertible.
