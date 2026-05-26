---
title: "Fix UnicodeDecodeError in check_documentation.py on Windows (subprocess encoding)"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on: []
priority: high
phase: "Phase 1"
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - leafcutter-ai/templates/commit-guardian/check_documentation.py
  - leafcutter-ai/templates/scripts/commit_guardian/check_documentation.py
  - scripts/commit_guardian/check_documentation.py
agents:
  architect-review: not_needed
  python-coder: needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
  status-checker: not_needed
  sql-coder: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# 05: Fix UnicodeDecodeError in check_documentation.py on Windows (subprocess encoding)

## Goal

In order to prevent the `check_documentation` pre-commit hook from crashing on
Windows when any staged file contains non-cp1252 bytes (e.g. em-dash U+2014 used
in sign-off templates), we need to add `encoding="utf-8"` to the
`subprocess.run()` call in `get_staged_files()` so that the hook reads git output
as UTF-8 on all platforms.

## Context

On Windows, `subprocess.run(..., text=True)` defaults to the system code page
(typically `cp1252`). When git emits a filename or output that contains a byte
not valid in cp1252 (byte `0x9d` = U+009D, or any byte from a UTF-8 multibyte
sequence for chars like em-dash `—` U+2014), the readerthread in Python's
subprocess module crashes with:

```
UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 5560:
character maps to <undefined>
```

The crash appeared in the pre-commit log as:
```
Exception in thread Thread-49 (_readerthread):
  File ".../subprocess.py", line 1615, in _readerthread
    buffer.append(fh.read())
  File ".../cp1252.py", line 23, in decode
    return codecs.charmap_decode(input,self.errors,decoding_table)[0]
UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 5560
```

The fix: pass `encoding="utf-8"` explicitly to `subprocess.run()` in
`get_staged_files()`. Git always outputs UTF-8 filenames (with
`-c core.quotepath=off` or by default in modern git); reading as UTF-8 is
correct cross-platform behavior.

There are **three copies** of `check_documentation.py` that all have the same
`subprocess.run()` on line 46 without an encoding argument:

1. `leafcutter-ai/templates/commit-guardian/check_documentation.py` — source template
   deployed to `.claude/commit-guardian/` in some configurations
2. `leafcutter-ai/templates/scripts/commit_guardian/check_documentation.py` — source
   template deployed to `scripts/commit_guardian/` in downstream projects
3. `scripts/commit_guardian/check_documentation.py` — deployed copy in this repo

All three must be fixed identically.

## Acceptance Criteria

```gherkin
Given a Windows downstream project where a staged file contains an em-dash (U+2014)
When the pre-commit hook check_documentation runs
Then no UnicodeDecodeError is raised and the hook completes normally

Given check_documentation.py get_staged_files() function
When inspected
Then subprocess.run() is called with encoding="utf-8"

Given a downstream project rebuilt from the updated templates via build.py
When check_documentation.py is inspected in the target project
Then subprocess.run() contains encoding="utf-8"
```

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit

## Comments

## Implementation Tasks

- [ ] In all three copies of `check_documentation.py`, update `get_staged_files()`:

  Change:
  ```python
  result = subprocess.run(
      ["git", "diff", "--cached", "--name-status"],
      capture_output=True,
      text=True,
      check=True,
  )
  ```
  To:
  ```python
  result = subprocess.run(
      ["git", "diff", "--cached", "--name-status"],
      capture_output=True,
      text=True,
      encoding="utf-8",
      check=True,
  )
  ```

  Files:
  - `leafcutter-ai/templates/commit-guardian/check_documentation.py`
  - `leafcutter-ai/templates/scripts/commit_guardian/check_documentation.py`
  - `scripts/commit_guardian/check_documentation.py`

- [ ] Add a DECISION HISTORY entry to each of the three files documenting this fix
  (with today's date, HH:MM, and `(#EPIC-TemplateDocViolations/05)` tail-tag)

## Risk & Safety

- Touches money? No.
- Touches data? No. This is a pre-commit hook script change only.
- Reversibility? Fully reversible. Adding an explicit encoding that matches the
  previously-implicit default on non-Windows (UTF-8) is a no-op on Linux/macOS
  and a fix on Windows. No behavioral change on non-Windows platforms.
