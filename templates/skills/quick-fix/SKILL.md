---
name: quick-fix
description: |
  Fast, in-place bug-fix pipeline. Operates in the current worktree without
  creating a new branch or worktree. Accepts a structured bug diagnosis (target
  file, location hint, symptom, root cause) and drives: AC creation → test-first
  (red) → warning check → fix (python-coder) → green phase → commit → close.
  Escalates to the full /build-feature pipeline when scope expands beyond the
  single target file. Invoked by /quick-fix.
allowed-tools: Bash, Read, Write, Agent
produces: orchestration
---

# quick-fix

This skill is the **single instruction set** for the `/quick-fix` workflow. It
drives a focused, in-place bug fix on the current branch without creating a
worktree or full ticket lifecycle. Load it when the user invokes `/quick-fix`.

Contrast with `build-single-ticket`: that skill always creates a new isolated
worktree. This skill operates in place — the branch and directory are unchanged
from start to finish.

---

## Input

Accept the user's diagnosis in either format:

**Natural language:**
> "In `scripts/build_helpers.py` line 42, `_resolve_precommit_cmd()` returns a
> non-executable path because the executability probe is missing."

**Structured JSON:**
```json
{
  "target_file": "scripts/build_helpers.py",
  "location_hint": "line 42 / _resolve_precommit_cmd()",
  "symptom": "returns a non-executable path",
  "root_cause": "executability probe is missing"
}
```

Parse both into these four fields before proceeding. If any field is missing or
ambiguous, ask the user to clarify before starting Phase 0.

- `target_file` — repo-relative path to the file containing the bug.
- `location_hint` — line number or function name narrowing the location.
- `symptom` — observable wrong behaviour.
- `root_cause` — the mechanism causing the symptom.

---

## Your Available Sub-Agents

| Agent | Role | When spawned |
|-------|------|--------------|
| `test-writer` | Writes the failing test that covers the new AC | Phase 2 |
| `test-runner` | Executes the test and returns pass/fail result | Phase 2 (red), Phase 4 (green) |
| `python-coder` | Applies the targeted fix to the single target file | Phase 3 |
| `commit` | Stages AC YAML + test file + fixed source and commits | Phase 5 |

---

## Phase 0 — Guards

Run all three guards before any other action. Halt on any failure.

### Guard BP-600a-1 — Worktree invariant

Record the current branch name:

```bash
git branch --show-current
```

Store this as `INITIAL_BRANCH`. After each phase that might affect git state,
verify the branch has not changed. If it has, halt immediately:

```
Halt: branch changed from '<INITIAL_BRANCH>' to '<current>' during quick-fix.
This is a bug — quick-fix must never switch branches.
```

### Guard BP-600a-2 — No isolation

Do NOT invoke `worktree-agent`, the `feature` skill, or any `git worktree add`
command. Quick-fix is an in-place operation. If the user's request requires a
new worktree, decline and redirect them to `/build-feature`.

### Guard BP-600a-3 — Uncommitted changes guard

Check whether the target file has uncommitted changes:

```bash
git status --porcelain
```

If the output contains the `target_file` path (on any line beginning with
`M`, `A`, `D`, `R`, or `??`), halt immediately:

```
Halt: '<target_file>' has uncommitted changes.
Commit or stash your current work before running /quick-fix.

Option A — stash:
  git stash

Option B — commit in two steps:
  git add <target_file>
  git commit -m "wip: save work before quick-fix"

Then re-run /quick-fix with the same diagnosis.
```

Do not proceed past this guard if the target file is dirty.

---

## Phase 1 — AC Creation (BP-600b-1, BP-600b-2, BP-600b-3)

### Step 1.1 — Locate the component

Use the `Read` tool to read `docs/acceptance-criteria/index.yaml`.

Match the `target_file` path against the `directory_patterns` fields (if
present) or use the component whose `description` best matches the file's role.
Record the matching component `prefix` (e.g. `BP`) and `id` (e.g.
`build-pipeline`). When no pattern matches, use the `build-pipeline` component
(`prefix: BP`) as the default for script and build-system files.

### Step 1.2 — Determine the next sequential AC ID

List the existing files in the component directory:

```bash
ls docs/acceptance-criteria/<component-id>/
```

Find the highest numeric suffix used by any `<PREFIX>-NNN.yaml` file. Increment
by 1. If the directory is empty or does not exist, start at 001.
Call the new ID `<PREFIX>-<NNN>` (e.g. `BP-601`).

### Step 1.3 — Write the AC YAML

Create the file at `docs/acceptance-criteria/<component-id>/<AC-ID>.yaml`.

Required fields:

```yaml
id: <AC-ID>
status: active
component: <component-id>
title: "<one-line title describing the correct behaviour the fix enforces>"
criteria: |
  Given <context matching the diagnosed situation>
  When  <the action or input that previously triggered the bug>
  Then  <the correct outcome that the fix must produce>
  And   the bug symptom ("<symptom>") must not occur
notes: "Authored by /quick-fix. Root cause: <root_cause>."
```

This AC YAML file is permanent. It must NOT be deleted or moved after the
ticket lifecycle closes. Use the `Write` tool to create it.

---

## Phase 2 — Test-First (BP-600c-1, BP-600c-2)

### Step 2.1 — Dispatch test-writer

Dispatch the `test-writer` agent with all four diagnosis fields plus the AC
path. Pass as the agent input:

```
Write a failing test for the bug described below.
The test MUST include the comment `# covers: <AC-ID>` near the top of the
test function or class.

AC file:        docs/acceptance-criteria/<component-id>/<AC-ID>.yaml
Target file:    <target_file>
Location hint:  <location_hint>
Symptom:        <symptom>
Root cause:     <root_cause>

The test must fail (red phase) against the current unmodified code.
```

Record the path to the test file written by `test-writer`. Call it
`TEST_FILE`.

### Step 2.2 — Red-phase verification

Dispatch the `test-runner` agent to execute the new test against the unmodified
source. Pass as the agent input:

```
Run this test file and return the result (pass or fail) with the full output.

Test file: <TEST_FILE>

Expected result: FAIL (this is the red phase — the bug has not been fixed yet).
```

**Expected: test-runner reports FAIL.** If test-runner reports PASS against
unmodified code, halt:

```
Halt: the test written by test-writer PASSES against unmodified code.
This means either the bug has already been fixed, or the test does not
actually cover the diagnosed bug.

Options:
  1. Re-diagnose: confirm the bug reproduces on the current branch.
  2. Re-write: re-invoke /quick-fix with a corrected diagnosis.
  3. Skip: if the bug is already fixed, no further action is needed.
```

Do not proceed to Phase 2.5 or Phase 3 until the red phase is confirmed.
Record the full failure output from test-runner as `RED_PHASE_OUTPUT`.

---

## Phase 2.5 — Root-Cause Divergence Warning (BP-600e-2)

Compare `RED_PHASE_OUTPUT` (the test failure message/traceback from Step 2.2) against
the diagnosed `root_cause`.

If the failure pattern diverges — e.g. the test fails with an error unrelated
to the diagnosed cause (different exception, different module, different line
than `location_hint`) — display this warning and wait for user input before
continuing:

```
Warning: the test failure suggests the root cause may differ from your diagnosis.

  Diagnosed: <root_cause>
  Observed:  <actual failure message / key traceback lines>

Options:
  - "continue" — proceed with the fix as diagnosed (you accept the risk)
  - "re-diagnose" — abort /quick-fix and start over with an updated diagnosis

What would you like to do?
```

Do NOT proceed until the user explicitly replies "continue" or "re-diagnose".
On "re-diagnose", halt cleanly and preserve the AC YAML (already written — do
not delete it).

---

## Phase 3 — Fix (BP-600d-1, BP-600d-2)

### Step 3.1 — Dispatch python-coder

Dispatch the `python-coder` agent with the full diagnosis and the AC to apply
the fix. Pass as the agent input:

```
Apply a targeted fix for the diagnosed bug.

CONSTRAINT: Modify ONLY the target file listed below. Do not touch any other
source file. If the fix logically requires changes to other files, do NOT make
those changes — instead return a note listing what additional changes would be
needed. The /quick-fix workflow will handle escalation.

AC file:        docs/acceptance-criteria/<component-id>/<AC-ID>.yaml
Target file:    <target_file>
Location hint:  <location_hint>
Symptom:        <symptom>
Root cause:     <root_cause>
```

### Step 3.2 — Capture modified files

After python-coder returns, check which files were modified:

```bash
git status --porcelain
```

Record the set of modified files as `MODIFIED_FILES`.

---

## Phase 3.5 — Scope Expansion Warning (BP-600e-1)

If `MODIFIED_FILES` contains any file other than `target_file` (ignoring the
AC YAML and the test file, which are expected additions), display this warning:

```
Warning: python-coder modified files beyond the target.

  Target file:      <target_file>
  Additional files: <list each extra modified source file>

This may indicate the bug requires a larger fix than /quick-fix supports.

Options:
  - "continue" — accept the scope expansion and proceed to the green phase
  - "escalate" — hand off to the full /build-feature pipeline

What would you like to do?
```

Wait for user input.

**On "continue":** proceed to Phase 4.

**On "escalate":** run the escalation path (see Escalation section below).

---

## Phase 4 — Green Phase (BP-600c-3)

Dispatch the `test-runner` agent to execute the test against the fixed code. Pass
as the agent input:

```
Run this test file and return the result (pass or fail) with the full output.

Test file: <TEST_FILE>

Expected result: PASS (this is the green phase — the fix should have resolved the bug).
```

**Expected: test-runner reports PASS.** If test-runner reports FAIL, halt with a
structured report:

```
Halt: the test is still failing after the fix.

  Test file:     <TEST_FILE>
  AC:            <AC-ID>
  Failure:       <failure message / key traceback lines>

The fix applied by python-coder did not resolve the bug. Options:
  1. Respawn python-coder with this failure as additional context.
  2. Escalate to /build-feature for a deeper investigation.
  3. Inspect the fix manually and re-run /quick-fix after editing.
```

Do not commit if the green phase fails.

---

## Phase 5 — Commit (BP-600d-3)

Dispatch the `commit` agent. Provide exact staging instructions:

```
Stage and commit exactly these three files:

  1. <AC YAML path>  — new acceptance criterion
  2. <TEST_FILE>     — new test covering the bug
  3. <target_file>   — bug fix

Commit message format:
  fix(<component-id>): <one-line description of the fix> (<AC-ID>)

  Covers <AC-ID>: <AC title>
  Root cause: <root_cause>

Do not stage any other files.
```

The `commit` agent handles pre-commit hook failures and the autofix retry loop
per its own protocol. If the commit fails after the retry loop is exhausted,
halt and surface the commit agent's failure message verbatim to the user.

---

## Phase 6 — Close (BP-600d-4)

After the commit agent returns success, run the three close-phase operations
in order. Each operation is a separate Bash call (no chaining).

**Step 6.1 — Push:**

```bash
git push origin HEAD
```

If this fails, halt immediately:

```
Halt: push to origin failed.

  Error: <push error output>

The fix is committed locally but NOT visible on the remote. The ticket will
NOT be marked done until the push succeeds.

Recovery:
  1. Check your network connection and remote permissions.
  2. Re-run: git push origin HEAD
  3. Then re-run /quick-fix close (or manually mark done after push).
```

Do not proceed to Step 6.2 until the push succeeds.

**Step 6.2 — PR check:**

```bash
git branch --show-current
```

Use the branch name from the output:

```bash
gh pr list --head <branch-name>
```

If a PR exists, log its URL. If no PR exists, print:

```
No open PR for branch '<branch-name>'.
To open one: https://github.com/<org>/<repo>/compare/main...<branch-name>
```

**Step 6.3 — Confirm close:**

The quick-fix lifecycle is complete. Print the completion summary:

```
/quick-fix complete.

  AC:        <AC-ID> — <AC title>
  Test:      <TEST_FILE>  [green]
  Fix:       <target_file>
  Commit:    <short SHA from git log -1>
  Branch:    <INITIAL_BRANCH>
  PR:        <PR URL or "none — see link above">
```

---

## Escalation Path (BP-600e-3)

Escalation is triggered by:
- User choosing "escalate" in Phase 3.5 (scope expansion), OR
- Any other condition where the fix cannot be contained to `target_file`.

**Escalation steps:**

1. Do NOT delete or revert any artefacts already created (AC YAML, test file).
   Leave them in the working tree. If they are already committed, they remain.

2. Print the escalation summary:

```
/quick-fix is escalating to the full build pipeline.

Preserved artefacts:
  AC:           <AC-ID>  [docs/acceptance-criteria/<component-id>/<AC-ID>.yaml]
  Test file:    <TEST_FILE>
  Target file:  <target_file>
  Root cause:   <root_cause>

Next steps:
  1. Stage and commit the AC YAML and test file if not already committed:
       git add <AC YAML path> <TEST_FILE>
       git commit -m "chore: stage quick-fix artefacts for escalated fix (<AC-ID>)"

  2. Create a ticket referencing the AC:
       /create-ticket
       > Fix the multi-file bug diagnosed by /quick-fix. AC ID: <AC-ID>.
       > Test file already written: <TEST_FILE>
       > Target file: <target_file>
       > Root cause: <root_cause>

  3. Drive the ticket through the full pipeline:
       /build-feature <ticket-path>
```

3. Halt. Do not run Phase 4, 5, or 6.

---

## Stop-and-Ask Rule

The `/quick-fix` skill MUST stop and ask the user (do not proceed automatically) when:

- Any Guard in Phase 0 fires (uncommitted changes, branch ambiguity).
- Phase 2.2 red-phase verification finds the test already passes.
- Phase 2.5 divergence warning fires.
- Phase 3.5 scope expansion warning fires.
- Phase 4 green phase fails.
- Phase 5 commit fails after the retry loop is exhausted.
- Phase 6 push fails.
- The diagnosis input is missing any of the four required fields.
- The target file does not exist in the repository.

Never attempt to auto-resolve any of the above. Surface the exact condition to
the user with the available options and wait for explicit direction.

---

## Constraints

- **Single-command bash rule** — every Bash call is a single, simple command.
  No `&&`, `;`, `||`, pipes, or multi-line scripts.
- **One file only** — python-coder is instructed to modify ONLY `target_file`.
  This constraint is non-negotiable; scope expansion triggers escalation (Phase 3.5).
- **AC file is permanent** — do NOT delete or move the AC YAML after creation,
  even if the workflow aborts mid-run.
- **No worktree creation** — do NOT call `worktree-agent`, `git worktree add`,
  or the `feature` skill under any circumstances.
- **No new branches** — the branch at Phase 0 is the branch at Phase 6.
  Verify with `git branch --show-current` before and after.
- **No registry or build pipeline edits** — do not edit
  `config/agent_registry.json`, `scripts/build.py`, or any commit-guardian manifest.
- **Scope boundary** — this skill operates only within the current working tree.
  It does not create tickets, does not open PRs autonomously, and does not invoke
  `/build-feature` — it can only recommend escalation and halt.
