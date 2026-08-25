/**
 * quick-fix.js — Claude Code Workflow script
 *
 * Deterministic fast-path bug-fix pipeline. Enforces the exact phase sequence:
 *   Guards + self-isolation → AC creation → test-writer → red-phase →
 *   python-coder → green-phase + mutation proof → commit → changelog → close
 *
 * Each phase is a flat depth-1 agent() call with a structured schema for the result.
 * The workflow halts with status:"blocked" when user input is required (divergence
 * warnings, scope expansion, test failures, mutation-proof failure, PR confirmation).
 *
 * Isolation is CONDITIONAL, not absent. When the session cwd is already inside a git
 * worktree on a non-default branch, the workflow operates in place exactly as before.
 * Otherwise — cwd is not a repo at all (common when it is an untracked workspace
 * parent), HEAD is detached, or the branch is main/master (PR-only under the
 * require-ci-lint ruleset, so a direct commit cannot be pushed) — the workflow
 * self-isolates via scripts/setup_ticket_worktree.py create-only before doing any
 * work. Every phase after Guards is anchored to the resulting worktree root.
 *
 * Implements BP-600a through BP-600e. NOTE: BP-600a-1, BP-600a-2, BP-600b-1 and
 * BP-600d-3 in docs/acceptance-criteria/build_pipeline/BP-600-quick-fix-workflow/
 * still assert the superseded no-worktree / three-file-commit behaviour and need
 * amending; see the "Known AC-store gap" note in the quick-fix SKILL.md.
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 */

export const meta = {
  name: 'quick-fix',
  description: 'Fast bug-fix: self-isolation, AC creation, strict red/green TDD with mutation proof, fix, commit, changelog, PR',
  phases: [
    { title: 'Guards', detail: 'Locate a usable worktree or create one, then check the target file is clean' },
    { title: 'AC Creation', detail: 'Write AC YAML into the hierarchical store and back-link its parent' },
    { title: 'Red Phase', detail: 'test-writer creates failing test, verified red under AC_ENFORCE_STRICT=1' },
    { title: 'Fix', detail: 'python-coder applies targeted fix to single file' },
    { title: 'Green Phase', detail: 'Verified green under AC_ENFORCE_STRICT=1, then mutation-proved' },
    { title: 'Commit', detail: 'commit agent stages AC, parent back-link, test and fix' },
    { title: 'Changelog', detail: 'changelog-agent authors the entry a required CI check demands' },
    { title: 'Close', detail: 'Push, then open a PR behind a confirmation gate' },
  ],
}

// The isolation decision is split across two agent() calls on purpose. The check
// only observes and reports; this script decides. Keeping the branch in JS control
// flow — rather than inside one agent's head — is what makes the decision testable:
// a harness can stub the check's answer and assert whether self-isolation actually
// fired, which a single combined call would hide.
const ISOLATION_CHECK_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    is_repo: { type: 'boolean' },
    session_cwd: { type: 'string' },
    initial_branch: { type: 'string' },
    needs_isolation: { type: 'boolean' },
    message: { type: 'string' },
  },
  required: ['status', 'is_repo', 'session_cwd', 'needs_isolation'],
}

const SELF_ISOLATE_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    worktree_root: { type: 'string' },
    branch: { type: 'string' },
    created: { type: 'boolean' },
    script_path: { type: 'string' },
    message: { type: 'string' },
  },
  required: ['status', 'worktree_root', 'branch'],
}

const GUARD_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    target_file_dirty: { type: 'boolean' },
    dirty_files: { type: 'array', items: { type: 'string' } },
    message: { type: 'string' },
  },
  required: ['status'],
}

const AC_CREATION_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    ac_id: { type: 'string' },
    ac_path: { type: 'string' },
    parent_ac_path: { type: 'string' },
    component_id: { type: 'string' },
    ac_title: { type: 'string' },
    message: { type: 'string' },
  },
  required: ['status', 'ac_id', 'ac_path', 'parent_ac_path'],
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

// `outcome` exists because a boolean cannot carry the distinction BP-600c-2-i
// requires. A collection error — bad import, syntax error, missing fixture —
// is "not passed", and with only a boolean the red phase reads that as a
// healthy red and goes on to apply a fix to a test that never ran. Three
// states, not two: the run failed an assertion, or it never got that far.
const TEST_RUNNER_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    passed: { type: 'boolean' },
    outcome: { type: 'string', enum: ['passed', 'failed', 'error'] },
    strict_command_run: { type: 'string' },
    output_summary: { type: 'string' },
    failure_message: { type: 'string' },
    message: { type: 'string' },
  },
  required: ['status', 'passed', 'outcome', 'strict_command_run'],
}

const MUTATION_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    red_without_fix: { type: 'boolean' },
    green_with_fix_restored: { type: 'boolean' },
    fix_restored: { type: 'boolean' },
    output_summary: { type: 'string' },
    message: { type: 'string' },
  },
  required: ['status', 'red_without_fix', 'green_with_fix_restored', 'fix_restored'],
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

const CHANGELOG_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    entry_path: { type: 'string' },
    commit_sha: { type: 'string' },
    message: { type: 'string' },
  },
  required: ['status', 'entry_path'],
}

const PUSH_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    branch: { type: 'string' },
    pr_url: { type: 'string' },
    pr_opened: { type: 'boolean' },
    message: { type: 'string' },
  },
  required: ['status'],
}

// ---------------------------------------------------------------------------
// Phase 0 — Guards and self-isolation
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

// Step 0a — OBSERVE. This call only reports what the current location is; it
// creates nothing and decides nothing. The decision is made in JS below.
const isolationCheck = await agent(
  `You are the isolation-decision phase of /quick-fix. Report what the current location is.
Create nothing.

Every command below is a SINGLE simple command. Never chain with &&, ;, || or pipes, and never use cd — use absolute paths or "git -C <path>".

1. Run: pwd
   Record the output as session_cwd. This is defined even outside a git repository.

2. Run: git rev-parse --is-inside-work-tree
   If it exits non-zero ("fatal: not a git repository"), set is_repo=false and leave
   initial_branch as an empty string.
   If it exits 0 and prints "true", set is_repo=true and run:
     git branch --show-current
   recording the output as initial_branch. An empty result means detached HEAD.

3. Set needs_isolation = true when is_repo is false, OR initial_branch is "", "main",
   or "master". Otherwise set it false.

Return status="ok" — this step never blocks, it only reports. Do NOT run
git worktree add, do NOT run setup_ticket_worktree.py, and do NOT dispatch
worktree-agent or the feature skill. Creating the worktree is a later step, and only
if this script decides it is needed.`,
  { label: 'isolation-check', phase: 'Guards', schema: ISOLATION_CHECK_SCHEMA }
)

if (!isolationCheck || isolationCheck.status === 'blocked') {
  return {
    status: 'blocked',
    phase: 'Guards (isolation-check)',
    message: isolationCheck ? isolationCheck.message : 'Isolation-check agent returned null',
    detail: isolationCheck,
  }
}

// Step 0b — DECIDE, here, in control flow. This replaces the former "no isolation,
// ever" guard, which had no answer for a non-repo cwd and offered a dead end on main
// (PR-only: the commit cannot be pushed, so confirming "yes" produced unlandable work).
let worktreeRoot
let activeBranch
let selfIsolated = false

if (isolationCheck.needs_isolation) {
  const isolateResult = await agent(
    `You are the self-isolation phase of /quick-fix. The current location cannot be used in
place — it is not a git repository, or HEAD is detached, or the branch is main/master,
which is PR-only here so a direct commit could not be pushed.

Create an isolated worktree using the repository's canonical script. Never use
worktree-agent, never use the feature skill, and never hand-roll a bare "git worktree add":
a hand-made worktree gets none of the bootstrap and silently skips every package pre-commit
hook for the whole run. The script below calls git worktree add for you and bootstraps the
result — that is exactly why it is the required tool.

Session cwd: ${isolationCheck.session_cwd}

Use single, simple commands only.

1. Locate the script by testing these absolute paths in order:
     ls "${isolationCheck.session_cwd}/scripts/setup_ticket_worktree.py"
     ls "${isolationCheck.session_cwd}/leafcutter-ai/scripts/setup_ticket_worktree.py"
   The first that exists is script_path — the first is the deployed/consumer layout, the
   second the dev workspace-parent layout where leafcutter-ai/ is a subdirectory. If
   neither exists, return status="blocked" naming both paths tried.
   script_repo_root is script_path with the trailing /scripts/setup_ticket_worktree.py removed.

2. MANDATORY staleness gate, before creating anything. The create-only subcommand roots the
   new branch at LOCAL main, not origin/main — it is the one subcommand in that script that
   does (create-ac-worktree and create-fastlane-worktree both root at origin/main). A stale
   local main silently yields a stale branch.
     Run: git -C "<script_repo_root>" fetch origin
     Run: git -C "<script_repo_root>" rev-list --left-right --count main...origin/main
   The output is "<L>\\t<R>". If R is non-zero, return status="blocked": local main is R
   commits behind. Tell the user to run
     git -C "<script_repo_root>" checkout main
     git -C "<script_repo_root>" merge --ff-only origin/main
   and re-run /quick-fix. Do NOT create the worktree.

3. Derive a short kebab-case slug from the diagnosed bug:
     target file: ${target_file}
     root cause:  ${root_cause}
   For example, "fast-lane-structural-parent".

4. Run: python "<script_path>" create-only "<slug>"
   Idempotent: an existing worktree for that slug is reused and reported with created=false
   rather than failing.
   Parse the single-line JSON payload it prints to stdout:
     {"worktree_path": "...", "branch": "feature/<slug>", "created": true|false}
   Return worktree_root and branch from that payload verbatim — do not construct the path
   any other way. The branch is ALWAYS feature/<slug>: the script does not honour fix/,
   bugfix/, hotfix/ or chore/ prefixes on creation.`,
    { label: 'self-isolate', phase: 'Guards', schema: SELF_ISOLATE_SCHEMA }
  )

  if (!isolateResult || isolateResult.status === 'blocked') {
    return {
      status: 'blocked',
      phase: 'Guards (self-isolate)',
      message: isolateResult ? isolateResult.message : 'Self-isolate agent returned null',
      halt_reason: 'isolation_failed',
      detail: isolateResult,
    }
  }

  worktreeRoot = isolateResult.worktree_root
  activeBranch = isolateResult.branch
  selfIsolated = true
  log(`Self-isolated into ${worktreeRoot} on ${activeBranch} (created: ${isolateResult.created !== false}).`)
} else {
  worktreeRoot = isolationCheck.session_cwd
  activeBranch = isolationCheck.initial_branch
  log(`Operating in place: ${worktreeRoot} on ${activeBranch}.`)
}

// Step 0b — uncommitted-changes guard, anchored to the established worktree.
const guardResult = await agent(
  `You are the guard-check phase of /quick-fix, operating in the worktree established by the
isolation phase. Use single, simple commands only.

Worktree root: ${worktreeRoot}
Branch:        ${activeBranch}

1. Run: git -C "${worktreeRoot}" branch --show-current
   Confirm it equals "${activeBranch}". If it does not, return status="blocked" with a
   message saying the branch changed — that is a bug, quick-fix must never switch branches.

2. Run: git -C "${worktreeRoot}" status --porcelain
   Check whether "${target_file}" appears in the output.
   If yes: set target_file_dirty=true, list all dirty files in dirty_files[], and return
   status="blocked" instructing the user to stash or commit that work first.
   If no: set target_file_dirty=false, dirty_files=[], and return status="ok".

Note: an isolated worktree may legitimately carry unrelated build-output drift. Only the
target file being dirty is a blocker.`,
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

log(`Guards passed. Target file clean.`)

// ---------------------------------------------------------------------------
// Phase 1 — AC creation (hierarchical store)
// ---------------------------------------------------------------------------

phase('AC Creation')

const acResult = await agent(
  `You are the AC-creation phase of /quick-fix. Create an acceptance criterion in the
HIERARCHICAL AC store. A flat six-field record is rejected by check_ac_schema.py.

Work entirely inside: ${worktreeRoot}

1. LOCATE THE COMPONENT. Read ${worktreeRoot}/docs/acceptance-criteria/index.yaml and match
   "${target_file}" against directory_patterns, or the component whose description best fits.
   Record the kebab id (e.g. build-orchestration) and prefix (e.g. BO).
   If nothing matches, do NOT default to a component. Return status="blocked" and ask which
   registered component applies, listing the candidates you considered.
   There is no safe default here: build-pipeline is a real component that would silently
   absorb criteria belonging to another, the AC file is permanent by design (BP-600b-3
   guarantees no phase ever deletes or moves it), and the same phase already blocks and asks
   in three adjacent situations — no matching L1, a parent at its child cap, and an
   underscore id absent from components.json. Guessing the component while asking about the
   others is the odd one out, and it is the more consequential of the two vocabulary axes.

   TWO-AXIS VOCABULARY — do not conflate. The scalar "component:" field takes the kebab id
   from index.yaml. The "components:" LIST takes the UNDERSCORE id from docs/components.json
   (build-orchestration -> build_orchestration). The hyphen-to-underscore swap is a
   convention, not a guarantee: confirm with
     grep -n "<underscore-id>" "${worktreeRoot}/docs/components.json"
   and if it is absent, do not invent one — return status="blocked" and ask which registered
   component id applies.

2. LOCATE THE PARENT. The store is docs/acceptance-criteria/<component>/<L0-slug>/<ID>.yaml
   with L0 -> L1 -> L2 -> L3. List the L0 directories, read the candidate L1/L2 files, and
   find the node whose criteria actually cover the behaviour being fixed.
   If no existing L1 plausibly covers it, return status="blocked": authoring new L0/L1 nodes
   is /plan-feature territory, not a bug-fix decision.

3. RESPECT THE CHILD CAPS. check_ac_limits.py enforces _MAX_L1_PER_L0 = 7 and
   _MAX_L2_PER_L1 = 5 (superseded children do not count; an explicit child_limit_override on
   the parent raises its own cap).
   - Under the cap: add a new L2 sibling <PARENT_L1>-<next unused integer>.
   - At the cap: do NOT add child_limit_override yourself — that is an audited waiver. If the
     bug is a technical CONSTRAINT on an already-specified L2 behaviour (edge case, extra
     invariant, boundary condition), add a Roman-suffix L3 child on the most relevant L2:
     <L2-id>-i, then -ii, -iii. If it genuinely needs a new L2 behaviour and the parent is
     full, return status="blocked" and ask the user.

4. WRITE THE AC. Ground the field set by reading
   ${worktreeRoot}/config/ac_store_schema.json and
   ${worktreeRoot}/scripts/commit_guardian/check_ac_schema.py rather than from memory.
   Include at least: id, title, component (kebab), components (list, underscore), status,
   criteria, level, req_status, work_status: todo, readiness, priority, roadmap_phase,
   depends_on, doc_links, assigned_agent, estimated_complexity, origin_agent, created,
   amended_by, superseded_by, covered_by, implemented_by, change_target, risk_surface, notes.

   criteria must read:
     Given <context matching the diagnosed situation>
     When  <the action or input that previously triggered the bug>
     Then  <the correct outcome the fix must produce>
     And   the bug symptom ("${symptom}") must not occur

   notes must record: "Authored by /quick-fix. Root cause: ${root_cause}."
   origin_agent is REQUIRED by check_ac_governance — set it to the committing user's identity.

   If you set readiness: approved, validate_test_contract then REQUIRES a non-empty test_spec
   on a not-done, code-targeting leaf assigned to a coder. Author a real test_spec (and
   test_rationale) or leave readiness lower — do not write an approved AC with an empty
   contract.

5. BACK-LINK THE PARENT. Append the new id to the parent's covered_by list. The AC guardian
   hooks read the git INDEX, not the store, so the parent file MUST be staged in the same
   commit or the back-link is never checked and silently rots. Return the parent's path as
   parent_ac_path so the commit phase stages it.

6. VALIDATE before returning:
     python "${worktreeRoot}/scripts/ac_store/validate_ac_schema.py" "<new AC path>" "<parent AC path>"
   Pass FILE PATHS, never a bare directory — given a directory the script prints
   "No YAML files to validate." and exits 0, a success-shaped result from a run that checked
   nothing. Fix anything it reports before returning status="ok".

Return ac_id, ac_path, parent_ac_path, component_id, ac_title.`,
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

const { ac_id, ac_path, parent_ac_path, component_id, ac_title } = acResult
log(`AC created: ${ac_id} at ${ac_path} (parent back-linked: ${parent_ac_path})`)

// ---------------------------------------------------------------------------
// Phase 2 — Red phase (test-writer, then strict verification)
// ---------------------------------------------------------------------------

phase('Red Phase')

const testWriterResult = await agent(
  `Write a failing test for this bug. The test MUST include the comment "# covers: ${ac_id}" near the top of the test function.

Worktree root:  ${worktreeRoot}
AC file:        ${ac_path}
Target file:    ${target_file}
Location hint:  ${location_hint || 'see root cause'}
Symptom:        ${symptom}
Root cause:     ${root_cause}

The test must FAIL (red phase) against the current unmodified code. It should exercise the exact code path that triggers the symptom and assert the correct behaviour.

Assert on OBSERVABLE BEHAVIOUR — the value returned, the state changed, the exit code. Do not write a test that greps the source for a string: such a test passes against dead code and cannot tell a wired fix from an inert one. Where the behaviour has a natural inverse, add a negative control so the assertion is tied to the fix rather than to an empty fixture or a load failure.

Return the absolute path to the test file you created as test_file.`,
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

const STRICT_NOTE =
  `You MUST run the suite with the AC_ENFORCE_STRICT=1 environment prefix:

  AC_ENFORCE_STRICT=1 python -m pytest "<test file>" -v

That prefix is one single command and is permitted. Do NOT run plain "python -m pytest".
scripts/ac_store/pytest_ac_enforcement.py DOWNGRADES failures to xfail for any AC that is not
yet work_status: done — and a brand-new AC never is. Without the strict flag a genuinely
failing test reports as a pass, which is precisely the false green this phase exists to catch.
Report the exact command you ran as strict_command_run.

Also report an "outcome", and be precise about it — the distinction matters more than the
boolean:
  "passed" — the test ran and its assertions held.
  "failed" — the test ran and an assertion did not hold. This is a real result.
  "error"  — the test never actually ran its assertions: a collection error, an ImportError,
             a SyntaxError, a missing fixture, a misspelled path, an empty selection
             ("no tests ran"). Report "error" whenever pytest could not get as far as
             evaluating the behaviour under test.
An error is NOT a red result. A run that never reached the assertion proves nothing about
the bug, and treating it as a healthy red would send a fix at a test that never executed.`

const redResult = await agent(
  `Verify the red phase for /quick-fix.

Worktree root: ${worktreeRoot}
Test file:     ${testFile}

${STRICT_NOTE}

EXPECTED: the test FAILS (the bug is not fixed yet).
Return passed=true if it passes, passed=false if it fails, plus the failure message or output summary.`,
  { label: 'red-verify/strict', phase: 'Red Phase', schema: TEST_RUNNER_SCHEMA, agentType: 'test-runner' }
)

if (!redResult) {
  return { status: 'blocked', phase: 'Red Phase', message: 'Red-phase verification returned null' }
}

if (!redResult.strict_command_run || !redResult.strict_command_run.includes('AC_ENFORCE_STRICT=1')) {
  return {
    status: 'blocked',
    phase: 'Red Phase',
    message: `Red phase was not verified under AC_ENFORCE_STRICT=1.\n\nCommand reported: ${redResult.strict_command_run || '(none)'}\n\nWithout that prefix pytest_ac_enforcement downgrades the failure to xfail and reports a false green, so this result cannot be trusted. Re-run /quick-fix.`,
    halt_reason: 'strict_flag_missing',
    test_file: testFile,
    ac_id,
  }
}

// BP-600c-2-i: an error is not a red result. Check this BEFORE the passed
// boolean — a collection error reports passed=false, and without this guard
// the run would read a test that never executed as a healthy red and go on
// to "fix" code against it.
if (redResult.outcome === 'error') {
  return {
    status: 'blocked',
    phase: 'Red Phase',
    message: `The test could not run — this is an ERROR, not a red result.\n\nTest file: ${testFile}\nCommand: ${redResult.strict_command_run}\nDetail: ${redResult.failure_message || redResult.output_summary || '(none)'}\n\nA collection error, ImportError, SyntaxError, missing fixture or empty selection means the assertion was never evaluated, so this run says nothing about the bug. Fix the test so it executes, then re-run /quick-fix. No fix has been applied.`,
    halt_reason: 'red_phase_error',
    test_file: testFile,
    ac_id,
  }
}

if (redResult.passed === true || redResult.outcome === 'passed') {
  return {
    status: 'blocked',
    phase: 'Red Phase',
    message: `Test PASSES against unmodified code — the bug may already be fixed or the test doesn't cover it.\n\nTest file: ${testFile}\nCommand: ${redResult.strict_command_run}\nOutput: ${redResult.output_summary || '(none)'}`,
    halt_reason: 'red_phase_pass',
    test_file: testFile,
    ac_id,
  }
}

log(`Red phase confirmed under AC_ENFORCE_STRICT=1: test fails as expected.`)

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

Worktree root:  ${worktreeRoot}
AC:             ${ac_id} (${ac_path})
Target file:    ${target_file}
Location hint:  ${location_hint || 'see root cause'}
Symptom:        ${symptom}
Root cause:     ${root_cause}

CONSTRAINT: Only modify ${target_file}. If the fix requires changes to other files,
do NOT make those changes. Instead, set scope_expanded=true and list the additional
files in extra_files[].

After applying the fix, run: git -C "${worktreeRoot}" status --porcelain
Report all modified files in modified_files[], excluding pre-existing build-output drift you did not cause.`,
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
// Phase 4 — Green phase, then mutation proof
// ---------------------------------------------------------------------------

phase('Green Phase')

const greenResult = await agent(
  `Verify the green phase for /quick-fix.

Worktree root: ${worktreeRoot}
Test file:     ${testFile}

${STRICT_NOTE}

EXPECTED: the test PASSES (the bug has been fixed).
Return passed=true if it passes, passed=false if it fails, plus the failure message or output summary.`,
  { label: 'green-verify/strict', phase: 'Green Phase', schema: TEST_RUNNER_SCHEMA, agentType: 'test-runner' }
)

if (!greenResult) {
  return { status: 'blocked', phase: 'Green Phase', message: 'Green-phase verification returned null' }
}

if (!greenResult.strict_command_run || !greenResult.strict_command_run.includes('AC_ENFORCE_STRICT=1')) {
  return {
    status: 'blocked',
    phase: 'Green Phase',
    message: `Green phase was not verified under AC_ENFORCE_STRICT=1.\n\nCommand reported: ${greenResult.strict_command_run || '(none)'}\n\nA default pytest run cannot distinguish a real pass from an xfail-masked failure on a not-done AC. Re-run /quick-fix.`,
    halt_reason: 'strict_flag_missing',
    test_file: testFile,
    ac_id,
  }
}

// BP-600c-2-i, green side: an error is not a failure to diagnose as "the fix
// did not work" — it is a run that never happened. Say which it was.
if (greenResult.outcome === 'error') {
  return {
    status: 'blocked',
    phase: 'Green Phase',
    message: `The test could not run — this is an ERROR, not a failing test.\n\nTest file: ${testFile}\nCommand: ${greenResult.strict_command_run}\nDetail: ${greenResult.failure_message || greenResult.output_summary || '(none)'}\n\nThe assertion was never evaluated, so this says nothing about whether the fix worked. The fix IS still applied to ${target_file}. Repair whatever stopped the test executing, then re-run /quick-fix.`,
    halt_reason: 'green_phase_error',
    test_file: testFile,
    ac_id,
  }
}

if (greenResult.passed === false || greenResult.outcome === 'failed') {
  return {
    status: 'blocked',
    phase: 'Green Phase',
    message: `Test still FAILS after fix.\n\nTest file: ${testFile}\nCommand: ${greenResult.strict_command_run}\nFailure: ${greenResult.failure_message || greenResult.output_summary || '(no details)'}\n\nThe fix did not resolve the bug. Options:\n  1. Re-run /quick-fix to retry with additional context\n  2. Escalate to /build-feature\n  3. Inspect and fix manually`,
    halt_reason: 'green_phase_fail',
    test_file: testFile,
    ac_id,
    failure: greenResult.failure_message,
  }
}

log(`Green phase confirmed under AC_ENFORCE_STRICT=1: test passes.`)

// BP-600c-3-i: the new test passing says nothing about the neighbours. A fix
// that repairs its own test while breaking an existing one would otherwise
// reach commit unchallenged — the mutation proof below does not cover this,
// because coupling-to-the-fix and collateral-damage are different questions.
const relatedResult = await agent(
  `Check the fix for collateral damage. The new test is green; that says nothing about the
tests that already existed.

Worktree root: ${worktreeRoot}
Fixed file:    ${target_file}
New test:      ${testFile}

1. Find the existing tests that exercise the fixed file, by import or reference: those that
   import the module it defines, or name it by path. Use single, simple commands (grep is
   fine). Exclude ${testFile}; it was just verified.
   Do NOT select tests because they sit in a directory that mirrors the fixed file's package
   (BP-600c-3-i). Co-location is not evidence of coverage — it pulls in neighbours that never
   touch the changed code, and it misses the callers in other packages that do. Those callers
   are where a regression from a one-file fix actually shows up.

2. Run them in one strict invocation:
     AC_ENFORCE_STRICT=1 python -m pytest <the files you found> -v
   If you found none, say so plainly: report outcome="passed" with an output_summary saying
   no related tests were found. That is an honest empty result, not a pass to hide behind.

3. Report outcome as "passed", "failed", or "error" on the same terms as before, and name
   every test that failed.

Judge only against what these tests did BEFORE the fix. A test already broken on this branch
for unrelated reasons is not collateral damage — if you cannot tell, say which ones you were
unsure about rather than guessing.`,
  { label: 'related-tests/strict', phase: 'Green Phase', schema: TEST_RUNNER_SCHEMA, agentType: 'test-runner' }
)

if (relatedResult && relatedResult.outcome === 'failed') {
  return {
    status: 'blocked',
    phase: 'Green Phase (related tests)',
    message: `The fix makes its own test pass but breaks existing tests.\n\nFixed file: ${target_file}\nCommand: ${relatedResult.strict_command_run || '(not reported)'}\nBroken: ${relatedResult.failure_message || relatedResult.output_summary || '(see output)'}\n\nThe fix is still applied. Either narrow it so the neighbours survive, or escalate to /build-feature — a change that needs those tests updated is bigger than one file, which is past what /quick-fix covers.`,
    halt_reason: 'related_tests_broken',
    test_file: testFile,
    ac_id,
  }
}

if (!relatedResult || relatedResult.outcome === 'error') {
  log(`Related-test check did not produce a usable result — treating as unverified, not as a pass.`)
} else {
  log(`Related tests still green: ${relatedResult.output_summary || 'no regressions found'}`)
}

// Mutation proof — green-after-red alone does not prove the test is coupled to
// the fix. Revert the fix, confirm red, restore, confirm green.
const mutationResult = await agent(
  `Prove the new test is actually coupled to the fix, not green for an unrelated reason.

Worktree root: ${worktreeRoot}
Target file:   ${target_file}
Test file:     ${testFile}

Run these as single, simple commands, in order:

1. git -C "${worktreeRoot}" stash push -- "${target_file}"
2. AC_ENFORCE_STRICT=1 python -m pytest "${testFile}" -v
   EXPECTED: FAIL. Record the result as red_without_fix (true when it fails).
3. git -C "${worktreeRoot}" stash pop
4. AC_ENFORCE_STRICT=1 python -m pytest "${testFile}" -v
   EXPECTED: PASS. Record the result as green_with_fix_restored.

Then run: git -C "${worktreeRoot}" status --porcelain
and confirm "${target_file}" is modified again — the fix must be back in the working tree.
Set fix_restored accordingly.

RESTORING THE FIX IS MANDATORY. If step 3 fails for any reason, say so explicitly and set
fix_restored=false rather than continuing — the run must not proceed to commit with the fix
still stashed. Report which stash entry holds it.

Set status="ok" only when red_without_fix=true AND green_with_fix_restored=true AND
fix_restored=true.`,
  { label: 'mutation-proof', phase: 'Green Phase', schema: MUTATION_SCHEMA }
)

if (!mutationResult || mutationResult.status === 'blocked' ||
    mutationResult.fix_restored !== true) {
  return {
    status: 'blocked',
    phase: 'Green Phase (mutation proof)',
    message: mutationResult
      ? `Mutation proof did not complete cleanly.\n\n  red without fix:      ${mutationResult.red_without_fix}\n  green with fix back:  ${mutationResult.green_with_fix_restored}\n  fix restored:         ${mutationResult.fix_restored}\n\n${mutationResult.message || ''}\n\nIf fix_restored is false the fix is still stashed — recover it with "git -C ${worktreeRoot} stash list" and "git -C ${worktreeRoot} stash pop" before doing anything else.`
      : 'Mutation-proof agent returned null — check "git -C ' + worktreeRoot + ' stash list" before continuing; the fix may still be stashed.',
    halt_reason: 'mutation_proof_incomplete',
    test_file: testFile,
    ac_id,
    detail: mutationResult,
  }
}

if (mutationResult.red_without_fix !== true || mutationResult.green_with_fix_restored !== true) {
  return {
    status: 'blocked',
    phase: 'Green Phase (mutation proof)',
    message: `The test is NOT coupled to the fix.\n\n  Reverting the fix left the test ${mutationResult.red_without_fix ? 'red (expected)' : 'GREEN — it passes without the fix'}.\n  Restoring the fix left the test ${mutationResult.green_with_fix_restored ? 'green (expected)' : 'RED — it fails with the fix'}.\n\nA test that passes without the fix proves nothing about the fix. Rewrite the test to assert the behaviour the fix actually changes, then re-run /quick-fix.`,
    halt_reason: 'mutation_proof_failed',
    test_file: testFile,
    ac_id,
    detail: mutationResult,
  }
}

log(`Mutation proof passed: reverting the fix returns the test to red; restoring it returns green.`)

// ---------------------------------------------------------------------------
// Phase 5 — Commit
// ---------------------------------------------------------------------------

phase('Commit')

const commitResult = await agent(
  `Stage and commit exactly these files, from the worktree ${worktreeRoot}:

  1. ${ac_path}         — new acceptance criterion
  2. ${parent_ac_path}  — parent, for the covered_by back-link (MUST be in the same commit:
                          the AC guardian hooks read the git index, not the store, so an
                          unstaged parent is never checked and the back-link silently rots)
  3. ${testFile}        — new test covering the bug
  4. ${target_file}     — bug fix

Before staging, flip work_status on ${ac_path} from todo to done and add ${testFile} to its
covered_by list — the test is green and mutation-proved, so the record should say so.

Commit message:
  fix(${component_id}): ${ac_title} (${ac_id})

  Covers ${ac_id}: ${ac_title}
  Root cause: ${root_cause}

  Verified: the test fails without the fix and passes with it (mutation-proved),
  both under AC_ENFORCE_STRICT=1.

Every claim in the message must be verifiable in git diff --staged. Do not stage any other
files — an isolated worktree may carry unrelated build-output drift, which stays out.`,
  { label: 'commit', phase: 'Commit', schema: COMMIT_SCHEMA, agentType: 'commit' }
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

// ---------------------------------------------------------------------------
// Phase 6 — Changelog
// ---------------------------------------------------------------------------
// "Changelog entry present" is a REQUIRED status check on main. Without this
// phase every quick-fix PR is born failing a required check.

phase('Changelog')

const changelogResult = await agent(
  `Author the changelog entry this change requires.

Worktree root: ${worktreeRoot}
Fix commit:    ${commitResult.commit_sha || '(read it from git -C "' + worktreeRoot + '" log -1 --format=%H)'}
AC:            ${ac_id} — ${ac_title}
Component:     ${component_id}
Root cause:    ${root_cause}

"Changelog entry present" is one of the required status checks on main, so a pull request
without an entry cannot merge. Read
${worktreeRoot}/scripts/release/check_changelog_presence.py and an existing file under
${worktreeRoot}/changelogs/ to get the filename convention and the required frontmatter
exactly right rather than assuming them.

Follow the changelog-agent template's steps for composing and writing the entry, but STOP
BEFORE its own commit step — this repository's enforce_commit_delegation hook only trusts the
commit agent, and the entry is committed separately below.

Return the path to the entry you wrote as entry_path.`,
  { label: 'changelog-author', phase: 'Changelog', schema: CHANGELOG_SCHEMA, agentType: 'changelog-agent' }
)

if (!changelogResult || changelogResult.status === 'blocked' || !changelogResult.entry_path) {
  return {
    status: 'blocked',
    phase: 'Changelog',
    message: changelogResult
      ? `Changelog entry was not authored: ${changelogResult.message || '(no detail)'}\n\nThe fix is committed (${commitResult.commit_sha || 'see git log -1'}) but the PR will fail the required "Changelog entry present" check without an entry.`
      : 'changelog-agent returned null. The fix is committed but the required changelog entry is missing.',
    halt_reason: 'changelog_missing',
    ac_id,
    commit_sha: commitResult.commit_sha,
    detail: changelogResult,
  }
}

const changelogCommit = await agent(
  `Stage and commit exactly one file, from the worktree ${worktreeRoot}:

  ${changelogResult.entry_path}  — changelog entry for ${ac_id}

Commit message:
  docs(changelog): entry for ${ac_id}

  ${ac_title}

Do not stage any other file.`,
  { label: 'commit/changelog', phase: 'Changelog', schema: COMMIT_SCHEMA, agentType: 'commit' }
)

if (!changelogCommit || changelogCommit.status === 'blocked') {
  return {
    status: 'blocked',
    phase: 'Changelog (commit)',
    message: changelogCommit ? changelogCommit.message : 'commit agent returned null for the changelog entry',
    halt_reason: 'changelog_commit_failed',
    ac_id,
    detail: changelogCommit,
  }
}

log(`Changelog entry committed: ${changelogResult.entry_path}`)

// ---------------------------------------------------------------------------
// Phase 7 — Close: push, then open a PR behind a confirmation gate
// ---------------------------------------------------------------------------

phase('Close')

const pushResult = await agent(
  `Push the branch and, on the user's confirmation, open a pull request.

Worktree root: ${worktreeRoot}
Branch:        ${activeBranch}
AC:            ${ac_id} — ${ac_title}

Run single, simple commands only.

1. git -C "${worktreeRoot}" push -u origin HEAD
   If this fails, return status="blocked" with the error. Do not continue.

2. gh auth switch --user urlmonitor
   This MUST run before any gh pr command — the default account is EMU-blocked for PR
   creation and gh pr create will fail with an authorization error.

3. gh pr list --head "${activeBranch}"
   If a PR already exists, return its URL as pr_url with pr_opened=false and status="ok".

4. If no PR exists, ASK THE USER whether to open one, showing the title and a summary.
   Opening a PR is outward-facing, so it stays behind an explicit confirmation.
   If the user declines, return status="ok" with pr_opened=false, pr_url="" and a message
   giving the compare URL so they can open it themselves later.

5. On confirmation, write the PR body to a FILE with the Write tool (for example
   /tmp/quick-fix-pr-body-${ac_id}.md) and pass it with --body-file:
     gh pr create --base main --head "${activeBranch}" --title "<title>" --body-file "<path>"
   NEVER pass the body inline with --body. The shell interpolates backticks inside it: a body
   containing a backticked identifier has been published as "<identifier>: command not found".
   Writing to a file and using --body-file avoids that entirely.
   Return the new PR URL as pr_url with pr_opened=true.

Do not merge the PR. That is the user's decision.`,
  { label: 'push-and-pr', phase: 'Close', schema: PUSH_SCHEMA }
)

if (!pushResult || pushResult.status === 'blocked') {
  return {
    status: 'blocked',
    phase: 'Close',
    message: pushResult ? pushResult.message : 'Close-phase agent returned null',
    halt_reason: 'push_failed',
    ac_id,
    commit_sha: commitResult.commit_sha,
    detail: pushResult,
  }
}

// ---------------------------------------------------------------------------
// Done
// ---------------------------------------------------------------------------

return {
  status: 'ok',
  message: `/quick-fix complete.\n\n  AC:        ${ac_id} — ${ac_title}\n  Test:      ${testFile}  [green, mutation-proved]\n  Fix:       ${target_file}\n  Changelog: ${changelogResult.entry_path}\n  Commit:    ${commitResult.commit_sha || '(see git log -1)'}\n  Worktree:  ${worktreeRoot}${selfIsolated ? ' (self-isolated)' : ' (in place)'}\n  Branch:    ${activeBranch}\n  PR:        ${pushResult.pr_url || 'none — not opened'}`,
  ac_id,
  ac_path,
  parent_ac_path,
  test_file: testFile,
  target_file,
  changelog_path: changelogResult.entry_path,
  commit_sha: commitResult.commit_sha,
  worktree_root: worktreeRoot,
  isolated: selfIsolated,
  branch: activeBranch,
  pr_url: pushResult.pr_url || '',
}
