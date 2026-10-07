---
title: "Exception-handling hook: every block names the file, line and rule; no reason, no block"
status: todo
components:
  - commit_guardian
created: 2026-10-07
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - hooks
  - post-tool-use
  - exception-handling
  - agent-feedback
last_updated: 2026-10-07
files_touched:
  - templates/hooks/check_exception_handling_hook.py
  - unit_tests/commit_guardian/test_exception_hook.py
  - docs/known-issues/commit-guardian/open-low-ki-cg-20260914-exception-hook-blocks-silently.md
  - docs/known-issues/commit-guardian.md
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

# Exception-handling hook: every block names the file, line and rule; no reason, no block

## Actor / Goal
In order that an agent can fix what the exception-handling hook objects to, we need every block it
raises to say which file, which line and which rule. And when the hook cannot say why, it must not
block; it reports its own failure instead. Then a block always means a real violation the agent can
act on.

## Context
- **Seen 2026-10-07 by two agents.** The ticket 03 coder (worktree `build-tooling-gate-record`) and the
  ticket 08 test-writer (worktree `build-tooling-generators`). Right after a Write or Edit of a Python
  file, the PostToolUse hook `check_exception_handling_hook.py` reported a "blocking error" with an
  empty message. Neither agent could tell what it objected to. In one case the file was a new test
  file, and the write still went through.
- **Known issue.** KI-CG-20260914-exception-hook-blocks-silently
  (`docs/known-issues/commit-guardian/open-low-ki-cg-20260914-exception-hook-blocks-silently.md`,
  open) records the same symptom: "PostToolUse:Write hook blocking error from command: ...: No stderr
  output".
- **Root cause.** The hook prints every blocking message to stdout and exits 2:
  - the violation message (`templates/hooks/check_exception_handling_hook.py:260-262`);
  - the ruff-not-found message (:246-249).
  For exit code 2, Claude Code passes stderr to the model, not stdout, so the model gets an empty
  reason. The module docstring states the wrong contract (:19-24): "Exit 2 with text on stdout = block
  the next step and show the text".
- **Reproduced 2026-10-07, with ruff on PATH.** A file with a bare `except:` gives exit 2, an empty
  stderr, and the whole message on stdout. The message's em-dash also reached the pipe as a cp1252
  byte (shown as "�").
- **Second cause (from the KI).** The hook runs the bare `ruff` binary (:127-141). Where ruff is
  installed only as a module (`python -m ruff` works, but there is no console script on PATH), every
  `.py` write "blocks" with the install message, which nobody sees either.
- **Non-violations also block.** Any non-zero ruff exit takes the violation branch (:255-262). ruff
  exits 2 on its own errors, for example a bad configuration.
- **The write always goes through.** A PostToolUse hook runs after the tool. A block only feeds a
  reason back to the model.
- **Sibling convention.** `ticket_frontmatter_guard` prints `{"decision": "block", "reason": ...}` on
  stdout and exits 0 (`templates/hooks/ticket_frontmatter_guard.py:735-741`).
- **Existing tests pin the wrong stream.** `unit_tests/commit_guardian/test_exception_hook.py` asserts
  the rule code in stdout (:123), and exit 2 when ruff is missing (:196-230). They change with this
  ticket.
- **Deployed copy.** `.claude/hooks/check_exception_handling_hook.py` is gitignored build output.
  The hook is registered in `templates/settings.json:104`.

## Acceptance Criteria
- [ ] AC-1: When ruff reports violations, the hook blocks, and the reason the model receives names the file and, for each violation, its line and rule code: ruff's concise lines, `<path>:<line>:<col>: <CODE> <message>`. The reason goes where Claude Code reads it: stderr with exit 2, or a JSON `decision: block` with its `reason` on stdout with exit 0, as `ticket_frontmatter_guard` does. It is never empty.
- [ ] AC-2: When the hook cannot produce such a reason, it does not block. That covers ruff unavailable both as `python -m ruff` and on PATH, a ruff exit other than 0 or 1, and exit 1 with no parseable violation line. Instead it reports its own failure explicitly in one line that names the file and the cause, without blocking.
- [ ] AC-3: ruff runs as `[sys.executable, "-m", "ruff", ...]` first, and falls back to `ruff` on PATH (the KI's fix direction).
- [ ] AC-4: Everything the hook writes is valid UTF-8 on Windows.
- [ ] AC-5: A clean file and a non-`.py` file still pass silently: exit 0, no output. The module docstring states the real contract.
- [ ] AC-6: KI-CG-20260914-exception-hook-blocks-silently is marked resolved, citing this ticket, in its file and in the index `docs/known-issues/commit-guardian.md`, following the known-issues convention (`docs/known-issues/README.md`).

## Test Requirements

```yaml
tests:
  - name: test_violation_block_reason_names_file_line_and_rule
    location: unit_tests/commit_guardian/test_exception_hook.py
    type: integration
    covers: [AC-1]
    description: |
      Run the hook as a subprocess with a Write payload for a file whose bare except is on a known
      line. Read the reason from the channel Claude Code uses (stderr for exit 2, or the parsed
      JSON reason for exit 0). It contains the file path, "<line>:" for that line, and E722. Do not
      take the reason from plain stdout. Red today: exit 2 with an empty stderr.
  - name: test_ruff_own_error_does_not_block_and_says_so
    location: unit_tests/commit_guardian/test_exception_hook.py
    type: integration
    covers: [AC-2]
    description: |
      Put an invalid ruff configuration next to the checked file, so ruff exits 2. The hook does
      not block, and its report names the file and that ruff failed. Red today: it blocks with an
      empty reason.
  - name: test_ruff_unavailable_does_not_block_and_says_so
    location: unit_tests/commit_guardian/test_exception_hook.py
    type: integration
    covers: [AC-2, AC-3]
    description: |
      Simulate ruff being unavailable both as a module and on PATH. The hook does not block, and
      its report names the file and the missing tool. Replaces the old exit-2 expectation at
      :196-230.
  - name: test_hook_output_is_valid_utf8
    location: unit_tests/commit_guardian/test_exception_hook.py
    type: integration
    covers: [AC-4]
    description: |
      Run the violation case, capturing bytes. Both streams decode as UTF-8. Red on Windows today
      (cp1252 em-dash).
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_violation_block_reason_names_file_line_and_rule | | |
| AC-2 | test_ruff_own_error_does_not_block_and_says_so; test_ruff_unavailable_does_not_block_and_says_so | | |
| AC-3 | test_ruff_unavailable_does_not_block_and_says_so | | |
| AC-4 | test_hook_output_is_valid_utf8 | | |
| AC-5 | (existing clean-file and non-.py tests) | | |
| AC-6 | (review) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Update `unit_tests/commit_guardian/test_exception_hook.py`: move the stdout assertions to the
  channel Claude Code reads, replace the ruff-missing exit-2 expectation, and add the tests above.

### python-coder
- [ ] `check_exception_handling_hook.py`: emit the block reason where Claude Code reads it, built from
  ruff's concise lines; run ruff as a module first; do not block on ruff errors or a missing ruff,
  and report that instead; write UTF-8; fix the docstring contract (19-24).
- [ ] Run `python scripts/build.py` so `.claude/hooks/` gets the new copy.
- [ ] Mark KI-CG-20260914-exception-hook-blocks-silently resolved (AC-6).

### test-runner / pr-reviewer / commit
- [ ] Run `unit_tests/commit_guardian/test_exception_hook.py` and
  `unit_tests/commit_guardian/test_ge_122d_1_authoring_reachability.py`.

## Risk & Safety
- Touches money? No.
- Touches data? No; an authoring-time hook.
- When ruff is unavailable, exception-handling violations are no longer flagged at authoring time.
  The pre-commit ruff hook still catches them at commit time, as the install message already says.
- Reversibility: revert the commit.

## Out of Scope
- The pre-commit rule set `templates/scripts/commit_guardian/check_exception_handling.py`.
- Other PostToolUse hooks that may share the stdout pattern; list any found.
