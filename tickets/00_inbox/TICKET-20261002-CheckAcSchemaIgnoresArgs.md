---
title: "check_ac_schema.py ignores file arguments, so the documented manual check is a false green"
status: todo
components:
  - ac_store
created: 2026-10-02
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - ac-store
  - false-green
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# check_ac_schema.py ignores file arguments, so the documented manual check is a false green

## Actor / Goal
In order for the documented manual AC check to mean something, we need `check_ac_schema.py <file>` to validate the named files, or the how-to to give a command that does.

## Context
- **What the how-to says:** `docs/how-to/ac-traceability-store.md` (Step 4) says `check_ac_schema.py <file>` validates the file and prints "check_ac_schema: 1 file checked, 0 errors".
- **What actually happens:** the script ignores its arguments, checks only git-staged files, and exits 0 silently. Anyone following the how-to gets a false green (found 2026-10-02 while authoring DK-300).
- **Other hooks with the same gap:** `check_ac_limits`, `check_ac_parent_covered_by`, `check_ac_circular_deps`, `check_ac_pattern_refs` and `check_ac_governance` also ignore the `HOOK_TEST_STAGED_FILES` seam.

## Scope
- File arguments are validated, or rejected loudly. A run that checked nothing says so.
- The how-to matches the real behaviour.
- A test proves a named bad file fails.

## Out of Scope
- Changing what the schema allows.

## Comments
