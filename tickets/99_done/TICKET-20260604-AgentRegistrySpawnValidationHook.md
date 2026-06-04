---
title: "Add pre-commit hook for bidirectional spawn validation on agent_registry.json"
status: done
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/commit_guardian/hooks/check_agent_spawn_consistency.py
  - scripts/commit_guardian/commit_guardian.json
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Add pre-commit hook for bidirectional spawn validation on agent_registry.json

## Actor / Goal

In order to catch bidirectional spawn mismatches in `config/agent_registry.json`
at commit time rather than build time, we need a targeted pre-commit hook that
runs the bidirectional spawn consistency check whenever `config/agent_registry.json`
is staged, so that engineers receive an immediate, named-pair error message inside
the worktree before the bad registry state reaches `main`.

## Context

During the EPIC-ContractDrivenACs drive, two bidirectional spawn mismatches were
silently introduced and only caught at build time after the PR was already merged:

- `create-ticket` listed `brainstorm-lead` in `spawn_allowlist`, but `brainstorm-lead`
  did not list `create-ticket` in its `spawned_by`.
- `it-po` listed `create-ticket-v2` in `spawned_by`, but `create-ticket-v2` did not
  list `it-po` in its `spawn_allowlist`.

The existing `check_agent_registry.py` pre-commit hook already validates spawn
bidirectionality, but it fires on a broad trigger set (`leafcutter/config/`,
`leafcutter/templates/agents/`, `leafcutter/scripts/`). That hook delegates to
`registry_validator.validate_agent_registry()` which loads the registry from the
`leafcutter/` package subdirectory — appropriate for the consumer-project install
path but not the narrower case of editing `config/agent_registry.json` directly
inside the `leafcutter-ai` repo.

This ticket adds a lightweight companion hook scoped precisely to
`config/agent_registry.json` being staged. It reads the file from the index (the
staged version), runs the same bidirectional spawn check, and emits a structured
error naming every mismatched pair so the engineer can fix before committing.

The hook lives in `scripts/commit_guardian/hooks/`, consistent with the `check-ac-limits`
hook already registered in `commit_guardian.json` that follows the same pattern.

### Relationship to existing `check-agent-registry` hook

The existing `check-agent-registry` hook targets the **consumer-project** registry
path (`leafcutter/config/agent_registry.json` after build) and requires the
`leafcutter` package subtree to exist. This new hook targets the **source registry**
(`config/agent_registry.json` directly in the `leafcutter-ai` repo) and reads it
directly without going through `registry_validator`. The two hooks are complementary;
both should remain registered.

## Acceptance Criteria

- [ ] AC-1: When `config/agent_registry.json` is NOT in the staged file list,
  the hook exits 0 immediately without loading or parsing the registry.
- [ ] AC-2: When `config/agent_registry.json` IS staged and all spawn relationships
  are bidirectionally consistent (every agent A that lists B in `spawn_allowlist`
  also appears in B's `spawned_by`, and vice versa), the hook exits 0.
- [ ] AC-3: When `config/agent_registry.json` IS staged and one or more
  bidirectional mismatches exist, the hook exits 1 and prints to stderr a message
  of the form:
  ```
  [check-agent-spawn-consistency] Bidirectional spawn mismatch(es) found:
    - 'create-ticket' lists 'brainstorm-lead' in spawn_allowlist, but 'brainstorm-lead'
      does not list 'create-ticket' in its spawned_by.
    - 'it-po' lists 'create-ticket-v2' in spawned_by, but 'create-ticket-v2' does not
      list 'it-po' in its spawn_allowlist.

  Fix the above mismatches in config/agent_registry.json before committing.
  ```
- [ ] AC-4: The special token `__ticket_phase_agents__` in `spawn_allowlist` is
  silently skipped (not treated as an unknown agent ID).
- [ ] AC-5: The external caller value `"user"` in `spawned_by` is silently skipped
  (not treated as an unknown agent ID).
- [ ] AC-6: When `config/agent_registry.json` is staged but is not valid JSON or
  the file cannot be read, the hook prints a clear error to stderr and exits 1.
- [ ] AC-7: The hook is registered in `scripts/commit_guardian/commit_guardian.json`
  under `hooks_manifest.hooks` with `files: "^config/agent_registry\\.json$"` and
  `pass_filenames: false`.
- [ ] AC-8: The hook script has a module docstring with MODULE, GOAL, BUSINESS
  CONTEXT, and ARCHITECTURE fields (matching the project's Python documentation
  convention) and a DECISION HISTORY block at the bottom.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |
| AC-8 | | | |

## Sign-offs

- [x] test-writer — 2026-06-04 12:07
- [x] python-coder — 2026-06-04 12:11
- [x] test-runner — 2026-06-04 12:19
- [x] pr-reviewer — 2026-06-04 12:26
- [x] commit — 2026-06-04 12:30
- [x] pull-request — 2026-06-04 12:35

## Comments

### 2026-06-04 12:07 — test-writer (status: ok)
feedback-id: fb_2026-06-04_bed58288
completion_manifest:
  test_stubs_created: true
  all_tests_red: true
  red_baseline_captured: true
red_baseline:
  - test_name: test_exits_0_when_registry_not_staged
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
  - test_name: test_exits_0_when_registry_consistent
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
  - test_name: test_exits_1_on_allowlist_mismatch
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
  - test_name: test_exits_1_on_spawned_by_mismatch
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
  - test_name: test_error_message_format
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
  - test_name: test_skips_special_token
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
  - test_name: test_skips_user_in_spawned_by
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
  - test_name: test_exits_1_on_invalid_json
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
  - test_name: test_exits_1_on_os_error
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
  - test_name: test_hook_registered_in_commit_guardian_json
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
  - test_name: test_hook_has_module_docstring
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
  - test_name: test_hook_has_decision_history_block
    file: unit_tests/commit_guardian/test_check_agent_spawn_consistency.py
    error: "ImportError: Hook script not found at .../scripts/commit_guardian/hooks/check_agent_spawn_consistency.py. Implement it (python-coder phase)."
Wrote 12 failing test stubs to unit_tests/commit_guardian/test_check_agent_spawn_consistency.py covering all 8 ACs. All 12 tests red on ImportError (hook not yet implemented). python-coder must create scripts/commit_guardian/hooks/check_agent_spawn_consistency.py and register it in commit_guardian.json.

### 2026-06-04 12:11 — python-coder (status: ok)
feedback-id: fb_2026-06-04_47c3bd9a
completion_manifest:
  hook_script_created: true
  hook_registered_in_commit_guardian: true
  all_tests_green: true
Created scripts/commit_guardian/hooks/check_agent_spawn_consistency.py with two-pass bidirectional check, __ticket_phase_agents__ skip (AC-4), "user" skip (AC-5), JSON error handling (AC-6), and module docstring + DECISION HISTORY (AC-8). Registered in commit_guardian.json after check-agent-registry with files pattern "^config/agent_registry\\.json$" and pass_filenames: false (AC-7). All 12 tests now pass.

### 2026-06-04 12:19 — test-runner (status: ok)
feedback-id: fb_2026-06-04_5017df54
completion_manifest:
  unit_tests_all_pass: true
  smoke_test_mismatch_detection: true
Command: python3 -m pytest unit_tests/commit_guardian/test_check_agent_spawn_consistency.py -v
Result: 12 passed in 0.18s (exit 0). Smoke test: introduced synthetic mismatch (_test_agent_A / _test_agent_B), confirmed hook exits 1 with both agent IDs in stderr output.

### 2026-06-04 12:26 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_b59b500a
completion_manifest:
  all_acs_verified: true
  implementation_matches_spec: true
  no_regressions: true
Reviewed all 8 ACs against implementation. AC-1 through AC-8 all satisfied. Hook is a standalone script (no leafcutter package imports), two-pass bidirectional check is correct, __ticket_phase_agents__ token handled in both directions (AC-4 edge case verified), "user" skipped in spawned_by (AC-5), JSON/OSError handled with clear stderr messages (AC-6), registration in commit_guardian.json is correct with files and pass_filenames fields (AC-7), module docstring and DECISION HISTORY present (AC-8). 12/12 tests green. No blockers.

### 2026-06-04 12:30 — commit (status: ok)
feedback-id: fb_2026-06-04_8371c269
completion_manifest:
  staged_files_correct: true
  commit_succeeded: true
  lock_released: true
Staged 5 files explicitly (no git add .): hooks/__init__.py, check_agent_spawn_consistency.py, test_check_agent_spawn_consistency.py, commit_guardian.json, ticket. Committed on branch feature/agentregistryspawnvalidationhook, SHA 5f102e3. Note: scripts/commit_guardian/ is .gitignored so new files required git add -f. Commit-phase lock acquired and released cleanly.

### 2026-06-04 12:35 — pull-request (status: ok)
feedback-id: fb_2026-06-04_272c9f45
completion_manifest:
  branch_pushed: true
  pr_opened: true
PR #48 opened at https://github.com/urlmonitor/leafcutter-ai/pull/48 on branch feature/agentregistryspawnvalidationhook targeting main.

## Implementation Tasks

### test-writer

Write `unit_tests/test_check_agent_spawn_consistency.py` with the following
test cases (write tests before the hook exists — hook must pass them):

- `test_exits_0_when_registry_not_staged` — mock `_get_staged_files()` to return
  a list that does not include `config/agent_registry.json`; assert `main()` returns 0.
- `test_exits_0_when_registry_consistent` — mock staged files to include the registry
  path; provide a registry JSON with two agents each correctly referencing the other;
  assert `main()` returns 0.
- `test_exits_1_on_allowlist_mismatch` — registry where agent A lists B in
  `spawn_allowlist` but B's `spawned_by` does not include A; assert `main()` returns 1
  and stderr contains both agent IDs.
- `test_exits_1_on_spawned_by_mismatch` — registry where agent B lists A in
  `spawned_by` but A's `spawn_allowlist` does not include B; assert `main()` returns 1.
- `test_skips_special_token` — `__ticket_phase_agents__` in allowlist; assert no
  error emitted and `main()` returns 0.
- `test_skips_user_in_spawned_by` — `"user"` in `spawned_by`; assert no error and
  `main()` returns 0.
- `test_exits_1_on_invalid_json` — staged registry content is `{invalid`; assert
  `main()` returns 1.

### python-coder

Create `scripts/commit_guardian/hooks/check_agent_spawn_consistency.py`.

**Algorithm:**

1. Call `git diff --cached --name-only --diff-filter=ACRM` to list staged files.
2. If `config/agent_registry.json` is not in the output, exit 0.
3. Read `config/agent_registry.json` from disk (the working-tree version, which
   matches the staged version for newly-staged files). Parse as JSON.
   - On `json.JSONDecodeError` or `OSError`: print error to stderr, exit 1.
4. Extract `agents` list. Build:
   - `spawn_map`: `{agent["id"]: agent.get("spawn_allowlist", [])}`
   - `spawned_by_map`: `{agent["id"]: agent.get("spawned_by", [])}`
   - `registry_ids`: set of all `agent["id"]` values
5. Run bidirectional check (two passes):
   - For each `(A, B)` where `B` in `spawn_map[A]`: skip if `B == "__ticket_phase_agents__"`;
     if `A not in spawned_by_map.get(B, [])`, record error.
   - For each `(B, A)` where `A` in `spawned_by_map[B]`: skip if `A == "user"`;
     if `B not in spawn_map.get(A, [])` and `"__ticket_phase_agents__" not in spawn_map.get(A, [])`,
     record error.
6. If any errors: print header + bulleted list to stderr, then fix guidance line, exit 1.
7. Exit 0.

**Error format (stderr):**
```
[check-agent-spawn-consistency] Bidirectional spawn mismatch(es) found:
  - '<A>' lists '<B>' in spawn_allowlist, but '<B>' does not list '<A>' in its spawned_by.
  - '<B>' lists '<A>' in spawned_by, but '<A>' does not list '<B>' in its spawn_allowlist.

Fix the above mismatches in config/agent_registry.json before committing.
```

**File location:** `scripts/commit_guardian/hooks/check_agent_spawn_consistency.py`

The `hooks/` subdirectory must be created if it does not exist. Add an empty
`__init__.py` to make it a package (consistent with the rest of the commit guardian
package).

**Docstring requirement:** Include a module-level docstring with MODULE, GOAL,
BUSINESS CONTEXT, and ARCHITECTURE sections, and a `# DECISION HISTORY` block at
the bottom.

Register the hook in `scripts/commit_guardian/commit_guardian.json` under
`hooks_manifest.hooks` (insert after the existing `check-agent-registry` entry):

```json
{
    "id": "check-agent-spawn-consistency",
    "name": "Check Agent Spawn Bidirectionality (registry edit guard)",
    "entry": "python scripts/commit_guardian/run_hook.py scripts/commit_guardian/hooks/check_agent_spawn_consistency.py",
    "language": "system",
    "files": "^config/agent_registry\\.json$",
    "stages": ["pre-commit"],
    "pass_filenames": false,
    "_comment": "TICKET-20260604-AgentRegistrySpawnValidationHook: fires only when config/agent_registry.json is staged. Runs the bidirectional spawn consistency check inline (no registry_validator import) and exits 1 with named mismatched pairs if any are found. Companion to check-agent-registry, which targets the consumer-project install path."
}
```

### test-runner

After `python-coder` completes, run the test file and confirm all tests pass:

```
python3 -m pytest unit_tests/test_check_agent_spawn_consistency.py -v
```

Also perform a smoke test by staging a mutated copy of `config/agent_registry.json`
(introduce a deliberate mismatch) and confirming the hook exits 1 with the expected
message, then restoring the original.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The new script and JSON entry can be reverted trivially. The hook
  is narrowly scoped to `config/agent_registry.json` staging events — it cannot
  fire on any other commit.
- Interaction with existing `check-agent-registry` hook: both hooks will fire when
  `config/agent_registry.json` is staged (the existing hook's trigger pattern
  `leafcutter/config/` also matches this path when it resolves from the package
  root). Both checks are complementary and idempotent — running both is safe and
  provides defence-in-depth.
- The hook reads the working-tree file, not the git object (avoids needing
  `git show :config/agent_registry.json`). This is safe: `git add` copies the
  current working-tree content into the index, so reading from disk is equivalent
  for normal staging workflows. Stash-and-unstash edge cases are out of scope for
  this ticket.
