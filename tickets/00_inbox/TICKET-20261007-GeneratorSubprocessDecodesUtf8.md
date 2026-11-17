---
title: "Epic generator reads its child's output in the encoding the child writes; AC and ticket files must be UTF-8 at commit"
status: todo
components:
  - ac_driven_dev
  - commit_guardian
created: 2026-10-07
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - encoding
  - windows
  - epic-generation
  - pre-commit
last_updated: 2026-10-07
files_touched:
  - scripts/ac_store/epic_tickets.py
  - scripts/ac_store/_gtfa_paths.py
  - templates/scripts/commit_guardian/check_ac_schema.py
  - unit_tests/ac_store/test_generator_subprocess_encoding.py  # new
  - unit_tests/commit_guardian/test_ac_and_ticket_files_must_be_utf8.py  # new
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  llm-expert: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# Epic generator reads its child's output in the encoding the child writes; AC and ticket files must be UTF-8 at commit

## Actor / Goal
In order that a generator warning is never lost to a decoding error, we need the epic generator and
its child process to agree on one text encoding, UTF-8. And so that a stray cp1252 byte cannot reach
the store, every AC and ticket file that is not valid UTF-8 is refused at commit.

## Context
- **Symptom.** The `goal_to_epic` child generator prints a UnicodeDecodeError (byte 0x97) from a
  subprocess reader thread, and the run does not fail.
- **Cause, reproduced 2026-10-07.** `epic_tickets._call_generate_ticket_from_ac`
  (`scripts/ac_store/epic_tickets.py:116-170`) runs `generate_ticket_from_ac.py` with
  `capture_output=True, text=True, encoding="utf-8"` (:162-164).
  - The child is a plain `sys.executable` Python. On Windows its piped stdout and stderr use the ANSI
    code page (cp1252) unless UTF-8 mode is on.
  - When the child logs a message that contains an em-dash, the dash is byte 0x97. One such message is
    the warning at `scripts/ac_store/_gtfa_paths.py:199-203`: "git rev-parse --show-toplevel failed —
    falling back ...".
  - The parent's UTF-8 decoder raises inside the stderr reader thread. Python prints the traceback,
    sets `stderr` to `None` and returns the child's exit code, 0. The child's warning text is lost.
  - Repro, without `PYTHONUTF8`:
    `subprocess.run([sys.executable, "-c", "import logging; logging.warning('a — b'); print('Written: x')"], capture_output=True, text=True, encoding="utf-8")`
    prints `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97` from `_readerthread`, and returns
    returncode 0, stdout `'Written: x\n'`, stderr `None`.
- **The coder's guess and the reviewer's objection are both partly right.** The coder pointed at
  `_gtfa_paths.py:190-195` (git rev-parse, `text=True`, no encoding). The reviewer judged it unlikely,
  because 0x97 is valid cp1252. The decode error is in fact at `epic_tickets.py:162-164`, and the 0x97
  byte is the em-dash in the warning just below the guessed call (:199-203). The git call's own output
  is a path. Decoding it with the locale codec only matters for a repository path with non-ASCII
  characters.
- **`text=True` calls on the generator path.** An import trace from `goal_to_epic`, `epic_pipeline`,
  `epic_tickets` and `generate_ticket_from_ac` at ed2190fd3 finds two: `epic_tickets.py:163` and
  `_gtfa_paths.py:193`. Modules imported lazily are not in that trace; check them by hand.
- **The second defect.** A phase agent once wrote a raw cp1252 0x97 byte into a UTF-8 ticket file
  through a shell heredoc.
- **What exists at commit (checked 2026-10-07).**
  - Ticket files: check-doc-frontmatter calls `validate_ticket_file`, which reads with UTF-8 and returns
    a blocking "Could not read file: ..." error (`templates/scripts/commit_guardian/frontmatter_validators.py:588-591`).
    That covers active ticket paths. Archived paths are exempt from frontmatter validation
    (`is_terminal_or_done_subfolder`, `check_doc_frontmatter.py:268`).
  - New AC files: check-ac-schema Phase 1 (`_validate_file`, `check_ac_schema.py:574-580`) reports
    "YAML parse error: 'utf-8' codec can't decode ..." and blocks.
  - Modified AC files: Phase 2 (`_check_implements_pattern_preserved`, `check_ac_schema.py:491-498`)
    catches only `OSError`. The UnicodeDecodeError escapes to the fail-open handler (:725-733), which
    exits 0 and discards Phase 1's error. So a modified AC file with a cp1252 byte passes
    check-ac-schema. This was verified by calling both functions on a file that contains 0x97: Phase 1
    returns the parse error and Phase 2 raises. Whether another hook would still stop the commit was
    not checked.
- **Sizes (measured by check-file-size, 2026-10-07).** `check_ac_schema.py` measures 551 against the
  400-line limit (733 raw), so it is over and every changed line must be paid back.
  `epic_tickets.py` measures 178 and `_gtfa_paths.py` 101.

## Acceptance Criteria
- [ ] AC-1: `_call_generate_ticket_from_ac` starts the child so that it writes UTF-8 (for example `PYTHONIOENCODING=utf-8` or `-X utf8` in the child's environment), and decodes UTF-8. On Windows without `PYTHONUTF8`, a child warning that contains an em-dash reaches the parent's captured stderr as "—", with no reader-thread traceback.
- [ ] AC-2: The git rev-parse call in `_gtfa_paths._derive_repo_root_from_git` (:190-195) decodes git's output as UTF-8. For a repository whose path contains a non-ASCII character, it returns that path unchanged.
- [ ] AC-3: Every other `text=True` subprocess call on the generator path, lazy imports included, names its encoding. The PR lists each call it found.
- [ ] AC-4: A staged, modified AC YAML file that is not valid UTF-8 is refused by check-ac-schema with exit 1. The message names the file and the byte offset. The error never reaches the fail-open handler.
- [ ] AC-5: A staged ticket file under `tickets/` that is not valid UTF-8 is refused at commit, naming the file. Active ticket paths already are (regression guard).
- [ ] AC-6: The existing tests stay green: `unit_tests/test_generate_ticket_from_ac.py`, `unit_tests/ac_store/test_ki_acd_20260921_depends_on_expects_from.py` and the check-ac-schema tests.

## Test Requirements

```yaml
tests:
  - name: test_child_warning_with_em_dash_reaches_parent_intact
    location: unit_tests/ac_store/test_generator_subprocess_encoding.py
    type: integration
    covers: [AC-1]
    description: |
      Run the real _call_generate_ticket_from_ac against a temporary store laid out so the child
      logs the em-dash warning (git rev-parse fails outside a repository), with PYTHONUTF8 removed
      from the environment. The captured stderr contains "—" and no "UnicodeDecodeError" is printed.
      Red on Windows today.
  - name: test_git_toplevel_with_non_ascii_path_round_trips
    location: unit_tests/ac_store/test_generator_subprocess_encoding.py
    type: integration
    covers: [AC-2]
    description: |
      Create a temporary git repository in a folder named with a non-ASCII character (e.g. "prüfung")
      and call _gtfa_paths._derive_repo_root_from_git (:162) from inside it. The returned path
      equals the folder. Red on Windows today if git's UTF-8 output is decoded as cp1252.
  - name: test_modified_ac_file_with_cp1252_byte_is_refused
    location: unit_tests/commit_guardian/test_ac_and_ticket_files_must_be_utf8.py
    type: integration
    covers: [AC-4]
    description: |
      In a temporary git repository with a committed AC file, stage a modified copy that contains a
      raw 0x97 byte. Run the real check-ac-schema entry point. Exit 1, and the output names the file
      and the byte offset. Red today: exit 0 through the fail-open handler.
  - name: test_ticket_file_with_cp1252_byte_is_refused
    location: unit_tests/commit_guardian/test_ac_and_ticket_files_must_be_utf8.py
    type: integration
    covers: [AC-5]
    description: |
      Stage a ticket under tickets/00_inbox/ that contains a raw 0x97 byte and run the real
      check-doc-frontmatter entry point. It is refused, naming the file. Green today (regression
      guard).
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_child_warning_with_em_dash_reaches_parent_intact | | |
| AC-2 | test_git_toplevel_with_non_ascii_path_round_trips | | |
| AC-3 | (PR list of calls) | | |
| AC-4 | test_modified_ac_file_with_cp1252_byte_is_refused | | |
| AC-5 | test_ticket_file_with_cp1252_byte_is_refused | | |
| AC-6 | (existing tests) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Write the two new test files.

### python-coder
- [ ] `epic_tickets.py:142-165`: give the child a UTF-8 output encoding through its environment, and
  keep decoding UTF-8.
- [ ] `_gtfa_paths.py:190-195`: `encoding="utf-8"` on the git call.
- [ ] Check the lazily imported modules on the generator path for `text=True` calls (AC-3).
- [ ] `check_ac_schema.py:491-498`: handle `UnicodeDecodeError` as a validation failure that names the
  file and the offset, not as a crash. Pay back every changed line under the ratchet. Then run
  `python scripts/build.py`, so the deployed copy that pre-commit runs (untracked build output)
  matches, and stage every tracked output it changes.

### test-runner / pr-reviewer / commit
- [ ] Run the new files and the AC-6 tests, on Windows without `PYTHONUTF8`.

## Risk & Safety
- Touches money? No.
- Touches data? No. A commit that today slips a non-UTF-8 AC file through will be refused.
- Reversibility: revert the commit.

## Out of Scope
- Archived ticket paths (`tickets/99_done/`, `done/` subfolders), which are exempt from frontmatter
  validation by design.
- Other subprocess readers outside the generator path.
