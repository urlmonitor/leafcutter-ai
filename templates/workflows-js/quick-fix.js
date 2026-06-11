/**
 * quick-fix.js — Claude Code Workflow script
 *
 * Deterministic fast-path bug-fix pipeline. Enforces the exact phase sequence:
 *   Guards → AC creation → test-writer → red-phase → python-coder → green-phase → commit → push
 *
 * Each phase is a flat depth-1 agent() call with a structured schema for the result.
 * The workflow halts with status:"blocked" when user input is required (divergence
 * warnings, scope expansion, test failures).
 *
 * Implements all 16 ACs from BP-600a through BP-600e.
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 */

export const meta = {
  name: 'quick-fix',
  description: 'Fast in-place bug-fix: guards, AC creation, red/green TDD, fix, commit, push',
  phases: [
    { title: 'Guards', detail: 'Branch check, uncommitted-changes check, no-worktree invariant' },
    { title: 'AC Creation', detail: 'Write AC YAML with correct component prefix and sequential ID' },
    { title: 'Red Phase', detail: 'test-writer creates failing test, test-runner confirms red' },
    { title: 'Fix', detail: 'python-coder applies targeted fix to single file' },
    { title: 'Green Phase', detail: 'test-runner confirms fix resolves the bug' },
    { title: 'Commit & Close', detail: 'commit agent stages 3 files, push to origin' },
  ],
}

const GUARD_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    initial_branch: { type: 'string' },
    target_file_dirty: { type: 'boolean' },
    dirty_files: { type: 'array', items: { type: 'string' } },
    message: { type: 'string' },
  },
  required: ['status', 'initial_branch'],
}

const AC_CREATION_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    ac_id: { type: 'string' },
    ac_path: { type: 'string' },
    component_id: { type: 'string' },
    ac_title: { type: 'string' },
    message: { type: 'string' },
  },
  required: ['status', 'ac_id', 'ac_path'],
}

const TEST_WRITER_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    test_file: { type: 'string' },
    message: { type: 'string' },
  },
  required: ['status', 'test_file'],
}

const TEST_RUNNER_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    passed: { type: 'boolean' },
    output_summary: { type: 'string' },
    failure_message: { type: 'string' },
    message: { type: 'string' },
  },
  required: ['status', 'passed'],
}

const FIX_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    modified_files: { type: 'array', items: { type: 'string' } },
    scope_expanded: { type: 'boolean' },
    extra_files: { type: 'array', items: { type: 'string' } },
    message: { type: 'string' },
  },
  required: ['status', 'modified_files'],
}

const COMMIT_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    commit_sha: { type: 'string' },
    message: { type: 'string' },
  },
  required: ['status'],
}

const PUSH_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    branch: { type: 'string' },
    pr_url: { type: 'string' },
    message: { type: 'string' },
  },
  required: ['status'],
}

// ---------------------------------------------------------------------------
// Phase 0 — Guards
// ---------------------------------------------------------------------------

phase('Guards')

const diagnosis = args
if (!diagnosis || !diagnosis.target_file || !diagnosis.root_cause) {
  log('Missing required diagnosis fields (target_file, root_cause)')
  return {
    status: 'blocked',
    phase: 'Guards',
    message: 'Diagnosis must include: target_file, location_hint, symptom, root_cause. ' +
      'Pass them as args: { target_file, location_hint, symptom, root_cause }',
  }
}

const { target_file, location_hint, symptom, root_cause } = diagnosis

const guardResult = await agent(
  `You are the guard-check phase of /quick-fix. Run these checks in order and return structured JSON:

1. Run: git branch --show-current
   Record the output as initial_branch.

2. Run: git status --porcelain
   Check if "${target_file}" appears in the output.
   If yes: set target_file_dirty=true and list all dirty files in dirty_files[].
   If no: set target_file_dirty=false and dirty_files=[].

3. Check if initial_branch is "main" or "master". If yes, set is_default_branch=true.

Return status:"ok" if target_file is clean (regardless of branch name).
Return status:"blocked" with a message only if target_file is dirty.

IMPORTANT: Do NOT invoke worktree-agent, feature skill, or git worktree add.`,
  { label: 'guard-checks', phase: 'Guards', schema: GUARD_SCHEMA }
)

if (!guardResult || guardResult.status === 'blocked') {
  return {
    status: 'blocked',
    phase: 'Guards',
    message: guardResult ? guardResult.message : 'Guard check agent returned null',
    detail: guardResult,
  }
}

const initialBranch = guardResult.initial_branch
const isDefaultBranch = initialBranch === 'main' || initialBranch === 'master'

if (isDefaultBranch) {
  const confirmResult = await agent(
    `WARNING: You are on the "${initialBranch}" branch. /quick-fix will commit directly to ${initialBranch} — there is no PR review gate.

Ask the user to confirm: "You are on ${initialBranch}. /quick-fix will commit the AC, test, and fix directly to this branch. Continue? (yes/no)"

If the user says yes/confirm/continue, return status:"ok".
If the user says no/cancel/abort, return status:"blocked" with message "User declined main-branch quick-fix."`,
    { label: 'main-branch-confirm', phase: 'Guards', schema: GUARD_SCHEMA }
  )

  if (!confirmResult || confirmResult.status === 'blocked') {
    return {
      status: 'blocked',
      phase: 'Guards',
      message: confirmResult ? confirmResult.message : 'User declined main-branch quick-fix.',
      halt_reason: 'user_declined_main',
    }
  }
}

log(`Guards passed. Branch: ${initialBranch}${isDefaultBranch ? ' (confirmed by user)' : ''}, target file clean.`)

// ---------------------------------------------------------------------------
// Phase 1 — AC Creation
// ---------------------------------------------------------------------------

phase('AC Creation')

const acResult = await agent(
  `You are the AC-creation phase of /quick-fix. Create an acceptance criterion YAML file.

Steps:
1. Read docs/acceptance-criteria/index.yaml to find the component matching "${target_file}".
   Use directory_patterns if available; otherwise match by description. Default: build-pipeline (prefix: BP).

2. List existing files in the component's AC directory to find the highest sequential ID.
   Increment by 1 for the new AC ID.

3. Write the AC YAML file with these fields:
   - id: <new AC ID>
   - status: active
   - component: <component-id>
   - title: "<one-line description of the correct behaviour>"
   - criteria: Given/When/Then covering the bug
   - notes: "Authored by /quick-fix. Root cause: ${root_cause}."

   The criteria must describe:
   - Given: ${target_file} at ${location_hint || 'the relevant location'}
   - When: the condition that triggers the symptom "${symptom}"
   - Then: the correct behaviour (opposite of the symptom)

Return the ac_id, ac_path (repo-relative), component_id, and ac_title.`,
  { label: 'ac-creation', phase: 'AC Creation', schema: AC_CREATION_SCHEMA }
)

if (!acResult || acResult.status === 'blocked') {
  return {
    status: 'blocked',
    phase: 'AC Creation',
    message: acResult ? acResult.message : 'AC creation agent returned null',
    detail: acResult,
  }
}

const { ac_id, ac_path, component_id, ac_title } = acResult
log(`AC created: ${ac_id} at ${ac_path}`)

// ---------------------------------------------------------------------------
// Phase 2 — Red Phase (test-writer + test-runner)
// ---------------------------------------------------------------------------

phase('Red Phase')

const testWriterResult = await agent(
  `Write a failing test for this bug. The test MUST include the comment "# covers: ${ac_id}" near the top of the test function.

AC file:        ${ac_path}
Target file:    ${target_file}
Location hint:  ${location_hint || 'see root cause'}
Symptom:        ${symptom}
Root cause:     ${root_cause}

The test must FAIL (red phase) against the current unmodified code. It should exercise the exact code path that triggers the symptom and assert the correct behaviour.

Return the path to the test file you created as test_file.`,
  { label: 'test-writer', phase: 'Red Phase', schema: TEST_WRITER_SCHEMA, agentType: 'test-writer' }
)

if (!testWriterResult || testWriterResult.status === 'blocked') {
  return {
    status: 'blocked',
    phase: 'Red Phase (test-writer)',
    message: testWriterResult ? testWriterResult.message : 'test-writer returned null',
    detail: testWriterResult,
  }
}

const testFile = testWriterResult.test_file
log(`Test written: ${testFile}`)

// Red-phase verification
const redResult = await agent(
  `Run this specific test file and report whether it passes or fails:

Test file: ${testFile}

EXPECTED: The test should FAIL (this is the red phase — the bug has not been fixed yet).
Return passed=true if the test passes, passed=false if it fails.
Include the failure message or output summary.`,
  { label: 'test-runner/red', phase: 'Red Phase', schema: TEST_RUNNER_SCHEMA, agentType: 'test-runner' }
)

if (!redResult) {
  return { status: 'blocked', phase: 'Red Phase', message: 'test-runner returned null' }
}

if (redResult.passed === true) {
  return {
    status: 'blocked',
    phase: 'Red Phase',
    message: `Test PASSES against unmodified code — the bug may already be fixed or the test doesn't cover it.\n\nTest file: ${testFile}\nOutput: ${redResult.output_summary || '(none)'}`,
    halt_reason: 'red_phase_pass',
    test_file: testFile,
    ac_id,
  }
}

log(`Red phase confirmed: test fails as expected.`)

// Check for root-cause divergence (BP-600e-2)
const failureMsg = redResult.failure_message || redResult.output_summary || ''
const divergenceCheck = failureMsg.length > 0 &&
  !failureMsg.toLowerCase().includes(root_cause.toLowerCase().split(' ')[0])

if (divergenceCheck) {
  log(`Warning: test failure may diverge from diagnosed root cause.`)
  return {
    status: 'blocked',
    phase: 'Red Phase (divergence warning)',
    message: `The test failure suggests the root cause may differ from your diagnosis.\n\n  Diagnosed: ${root_cause}\n  Observed:  ${failureMsg}\n\nTo continue, re-run /quick-fix with the same args. To re-diagnose, update the root_cause field.`,
    halt_reason: 'divergence_warning',
    test_file: testFile,
    ac_id,
    observed_failure: failureMsg,
  }
}

// ---------------------------------------------------------------------------
// Phase 3 — Fix
// ---------------------------------------------------------------------------

phase('Fix')

const fixResult = await agent(
  `Apply a targeted fix for this bug. MODIFY ONLY THE TARGET FILE.

AC:             ${ac_id} (${ac_path})
Target file:    ${target_file}
Location hint:  ${location_hint || 'see root cause'}
Symptom:        ${symptom}
Root cause:     ${root_cause}

CONSTRAINT: Only modify ${target_file}. If the fix requires changes to other files,
do NOT make those changes. Instead, set scope_expanded=true and list the additional
files in extra_files[].

After applying the fix, run: git status --porcelain
Report all modified files in modified_files[].`,
  { label: 'python-coder/fix', phase: 'Fix', schema: FIX_SCHEMA, agentType: 'python-coder' }
)

if (!fixResult || fixResult.status === 'blocked') {
  return {
    status: 'blocked',
    phase: 'Fix',
    message: fixResult ? fixResult.message : 'python-coder returned null',
    detail: fixResult,
  }
}

// Scope expansion check (BP-600e-1)
if (fixResult.scope_expanded || (fixResult.extra_files && fixResult.extra_files.length > 0)) {
  log(`Scope expansion detected: ${(fixResult.extra_files || []).join(', ')}`)
  return {
    status: 'blocked',
    phase: 'Fix (scope expansion)',
    message: `python-coder reports the fix requires changes beyond ${target_file}.\n\nAdditional files needed: ${(fixResult.extra_files || []).join(', ')}\n\nOptions:\n  - Re-run /quick-fix to proceed anyway (if python-coder only modified target_file)\n  - Escalate to /build-feature for a multi-file fix`,
    halt_reason: 'scope_expansion',
    test_file: testFile,
    ac_id,
    extra_files: fixResult.extra_files,
  }
}

log(`Fix applied to ${target_file}`)

// ---------------------------------------------------------------------------
// Phase 4 — Green Phase
// ---------------------------------------------------------------------------

phase('Green Phase')

const greenResult = await agent(
  `Run this specific test file and report whether it passes or fails:

Test file: ${testFile}

EXPECTED: The test should PASS (this is the green phase — the bug has been fixed).
Return passed=true if the test passes, passed=false if it fails.
Include the failure message or output summary if it fails.`,
  { label: 'test-runner/green', phase: 'Green Phase', schema: TEST_RUNNER_SCHEMA, agentType: 'test-runner' }
)

if (!greenResult) {
  return { status: 'blocked', phase: 'Green Phase', message: 'test-runner returned null' }
}

if (greenResult.passed === false) {
  return {
    status: 'blocked',
    phase: 'Green Phase',
    message: `Test still FAILS after fix.\n\nTest file: ${testFile}\nFailure: ${greenResult.failure_message || greenResult.output_summary || '(no details)'}\n\nThe fix did not resolve the bug. Options:\n  1. Re-run /quick-fix to retry with additional context\n  2. Escalate to /build-feature\n  3. Inspect and fix manually`,
    halt_reason: 'green_phase_fail',
    test_file: testFile,
    ac_id,
    failure: greenResult.failure_message,
  }
}

log(`Green phase confirmed: test passes.`)

// ---------------------------------------------------------------------------
// Phase 5+6 — Commit & Close
// ---------------------------------------------------------------------------

phase('Commit & Close')

const commitResult = await agent(
  `Stage and commit exactly these files:
  1. ${ac_path}  — new acceptance criterion
  2. ${testFile}  — new test covering the bug
  3. ${target_file}  — bug fix

Commit message:
  fix(${component_id}): ${ac_title} (${ac_id})

  Covers ${ac_id}: ${ac_title}
  Root cause: ${root_cause}

Do not stage any other files.`,
  { label: 'commit', phase: 'Commit & Close', schema: COMMIT_SCHEMA, agentType: 'commit' }
)

if (!commitResult || commitResult.status === 'blocked') {
  return {
    status: 'blocked',
    phase: 'Commit',
    message: commitResult ? commitResult.message : 'commit agent returned null',
    detail: commitResult,
  }
}

log(`Committed: ${commitResult.commit_sha || '(sha pending)'}`)

// Push
const pushResult = await agent(
  `Push the current branch to origin and check for an existing PR.

Steps:
1. Run: git push origin HEAD
2. Run: git branch --show-current
3. Run: gh pr list --head <branch-name>

Return:
- branch: the current branch name
- pr_url: the PR URL if one exists, or empty string if none
- status: "ok" if push succeeded, "blocked" if it failed`,
  { label: 'push-and-close', phase: 'Commit & Close', schema: PUSH_SCHEMA }
)

if (!pushResult || pushResult.status === 'blocked') {
  return {
    status: 'blocked',
    phase: 'Push',
    message: pushResult ? pushResult.message : 'Push agent returned null',
    detail: pushResult,
  }
}

// ---------------------------------------------------------------------------
// Done
// ---------------------------------------------------------------------------

return {
  status: 'ok',
  message: `/quick-fix complete.\n\n  AC:        ${ac_id} — ${ac_title}\n  Test:      ${testFile}  [green]\n  Fix:       ${target_file}\n  Commit:    ${commitResult.commit_sha || '(see git log -1)'}\n  Branch:    ${initialBranch}\n  PR:        ${pushResult.pr_url || 'none'}`,
  ac_id,
  ac_path,
  test_file: testFile,
  target_file,
  commit_sha: commitResult.commit_sha,
  branch: initialBranch,
}
