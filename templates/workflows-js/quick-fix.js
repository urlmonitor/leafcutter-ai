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
    { title: 'Knowledge Routing', detail: 'route emitted learnings to their surfaces before commit (INF-700a-1-i, fail-open)' },
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

// Every *_SCHEMA below shares a "status" enum and trailing "message"; each call
// site supplies only its own extra properties and which of them are required.
function schema(properties, required = []) {
  return {
    type: 'object',
    properties: {
      status: { type: 'string', enum: ['ok', 'blocked'] },
      ...properties,
      message: { type: 'string' },
    },
    required: ['status', ...required],
  }
}

const ISOLATION_CHECK_SCHEMA = schema({
  is_repo: { type: 'boolean' },
  session_cwd: { type: 'string' },
  initial_branch: { type: 'string' },
  needs_isolation: { type: 'boolean' },
}, ['is_repo', 'session_cwd', 'needs_isolation'])

const SELF_ISOLATE_SCHEMA = schema({
  worktree_root: { type: 'string' },
  branch: { type: 'string' },
  created: { type: 'boolean' },
  script_path: { type: 'string' },
}, ['worktree_root', 'branch'])

const GUARD_SCHEMA = schema({
  target_file_dirty: { type: 'boolean' },
  dirty_files: { type: 'array', items: { type: 'string' } },
})

const AC_CREATION_SCHEMA = schema({
  ac_id: { type: 'string' },
  ac_path: { type: 'string' },
  parent_ac_path: { type: 'string' },
  component_id: { type: 'string' },
  ac_title: { type: 'string' },
}, ['ac_id', 'ac_path', 'parent_ac_path'])

const TEST_WRITER_SCHEMA = schema({
  test_file: { type: 'string' },
}, ['test_file'])

// `outcome` exists because a boolean cannot carry the distinction BP-600c-2-i
// requires. A collection error — bad import, syntax error, missing fixture —
// is "not passed", and with only a boolean the red phase reads that as a
// healthy red and goes on to apply a fix to a test that never ran. Three
// states, not two: the run failed an assertion, or it never got that far.
const TEST_RUNNER_SCHEMA = schema({
  passed: { type: 'boolean' },
  outcome: { type: 'string', enum: ['passed', 'failed', 'error'] },
  strict_command_run: { type: 'string' },
  output_summary: { type: 'string' },
  failure_message: { type: 'string' },
}, ['passed', 'outcome', 'strict_command_run'])

const MUTATION_SCHEMA = schema({
  red_without_fix: { type: 'boolean' },
  green_with_fix_restored: { type: 'boolean' },
  fix_restored: { type: 'boolean' },
  output_summary: { type: 'string' },
}, ['red_without_fix', 'green_with_fix_restored', 'fix_restored'])

const FIX_SCHEMA = schema({
  modified_files: { type: 'array', items: { type: 'string' } },
  scope_expanded: { type: 'boolean' },
  extra_files: { type: 'array', items: { type: 'string' } },
}, ['modified_files'])

/* BP-600e-1-i: paths already dirty before the coder is dispatched — from an
   earlier phase's own output, from pre-commit/doc-enforcer auto-formatting,
   or from ordinary worktree drift — so the Fix-phase scope guard can treat
   them as pre-existing rather than as the coder's own intentional change. */
const BASELINE_SCHEMA = schema({ dirty_paths: { type: 'array', items: { type: 'string' } } })
const COMMIT_SCHEMA = schema({
  commit_sha: { type: 'string' },
})

const CHANGELOG_SCHEMA = schema({
  entry_path: { type: 'string' },
  commit_sha: { type: 'string' },
}, ['entry_path'])

const PUSH_SCHEMA = schema({
  branch: { type: 'string' },
  pr_url: { type: 'string' },
  pr_opened: { type: 'boolean' },
  compare_url: { type: 'string' },
  pr_command: { type: 'string' },
})

// Every blocked return in this file shares this envelope: status, phase, message,
// plus whatever a call site needs beyond that (halt_reason, ac_id, detail, ...).
function blocked(phase, message, extra = {}) {
  return { status: 'blocked', phase, message, ...extra }
}

// Shared shape for the nine `if (!x || x.status === 'blocked') return {...}` guards
// below. The mutation-proof and changelog-authoring checks build different messages
// entirely and call `blocked()` directly instead.
function blockedOnFailure(result, phase, agentLabel, extra = {}) {
  if (!result || result.status === 'blocked') {
    return blocked(phase, result ? result.message : `${agentLabel} returned null`, { detail: result, ...extra })
  }
  return null
}

// The routing dispatch's expected reply shape (INF-700a-1-i). `case` is the
// only required field — `read`/`written`/`unwritten`/`detail` are read
// defensively by classifyKnowledgeRouting() below, never trusted as present
// just because the schema names them.
const KNOWLEDGE_ROUTING_SCHEMA = {
  type: 'object',
  properties: {
    case: { type: 'string', enum: ['completed', 'could_not_complete', 'did_not_run'] },
    read: { type: 'integer' },
    written: { type: 'integer' },
    unwritten: { type: 'integer' },
    detail: { type: ['string', 'null'] },
  },
  required: ['case'],
}

/**
 * classifyKnowledgeRouting — the SINGLE construction site for the
 * `knowledge_routing` figures consumed into this path's terminal payload
 * (INF-700a-1 / INF-700a-1-i / INF-700a-1-ii — same contract as
 * fast-lane-ship.js's own copy of this function). Fails CLOSED: only a
 * reply carrying a RECOGNISED `case` value ("completed" or
 * "could_not_complete") is trusted as having actually run. Anything else —
 * a missing case, an unparseable reply, or the harness's own unlabelled
 * default stub — is reported as the third, distinct "did_not_run" case,
 * never rendered as "completed" with zero figures.
 *
 * A knowledge step never fails, retries, or blocks the unit of work's own
 * outcome (ADR-034's fail-open branch) — this function only classifies the
 * reply; it never throws.
 *
 * Pure function: no agent(), no I/O — safe to extract and execute directly.
 *
 * @param {*} reply - The raw reply from the "knowledge-routing-step" dispatch.
 * @returns {{case: string, read: number, written: number, unwritten: number, detail: (string|null)}}
 */
function classifyKnowledgeRouting(reply) {
  const recognisedCase =
    reply && (reply.case === 'completed' || reply.case === 'could_not_complete')
      ? reply.case
      : 'did_not_run'
  const asInt = (value) => (typeof value === 'number' && Number.isFinite(value) ? value : 0)
  return {
    case: recognisedCase,
    read: recognisedCase === 'did_not_run' ? 0 : asInt(reply.read),
    written: recognisedCase === 'did_not_run' ? 0 : asInt(reply.written),
    unwritten: recognisedCase === 'did_not_run' ? 0 : asInt(reply.unwritten),
    detail:
      recognisedCase === 'could_not_complete' && typeof reply.detail === 'string'
        ? reply.detail
        : null,
  }
}

// ---------------------------------------------------------------------------
// Phase 0 — Guards and self-isolation
// ---------------------------------------------------------------------------

phase('Guards')

const diagnosis = args
if (!diagnosis || !diagnosis.target_file || !diagnosis.root_cause) {
  log('Missing required diagnosis fields (target_file, root_cause)')
  return blocked('Guards', 'Diagnosis must include: target_file, location_hint, symptom, root_cause. ' +
    'Pass them as args: { target_file, location_hint, symptom, root_cause }')
}

const { target_file, location_hint, symptom, root_cause, divergence_decision } = diagnosis

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

const isolationBlock = blockedOnFailure(isolationCheck, 'Guards (isolation-check)', 'Isolation-check agent')
if (isolationBlock) return isolationBlock

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

  const isolateBlock = blockedOnFailure(isolateResult, 'Guards (self-isolate)', 'Self-isolate agent',
    { halt_reason: 'isolation_failed' })
  if (isolateBlock) return isolateBlock

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

const guardBlock = blockedOnFailure(guardResult, 'Guards', 'Guard check agent')
if (guardBlock) return guardBlock

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

const acBlock = blockedOnFailure(acResult, 'AC Creation', 'AC creation agent')
if (acBlock) return acBlock

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

const testWriterBlock = blockedOnFailure(testWriterResult, 'Red Phase (test-writer)', 'test-writer')
if (testWriterBlock) return testWriterBlock

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

// Red and Green share these two failure shapes (strict-flag missing; outcome:"error").
// Only the explanation differs between the phases; the rest is written once.
function strictFlagMissingBlock(phase, result, explanation) {
  return blocked(phase,
    `${phase} was not verified under AC_ENFORCE_STRICT=1.\n\nCommand reported: ${result.strict_command_run || '(none)'}\n\n${explanation}`,
    { halt_reason: 'strict_flag_missing', test_file: testFile, ac_id })
}

function unrunnableTestBlock(phase, haltReason, result, notARedResult, explanation) {
  return blocked(phase,
    `The test could not run — this is an ERROR, not ${notARedResult}.\n\nTest file: ${testFile}\nCommand: ${result.strict_command_run}\nDetail: ${result.failure_message || result.output_summary || '(none)'}\n\n${explanation}`,
    { halt_reason: haltReason, test_file: testFile, ac_id })
}

const redResult = await agent(
  `Verify the red phase for /quick-fix.

Worktree root: ${worktreeRoot}
Test file:     ${testFile}

${STRICT_NOTE}

EXPECTED: the test FAILS (the bug is not fixed yet).
Return passed=true if it passes, passed=false if it fails, plus the failure message or output summary.`,
  { label: 'red-verify/strict', phase: 'Red Phase', schema: TEST_RUNNER_SCHEMA, agentType: 'test-runner' }
)

if (!redResult) return { status: 'blocked', phase: 'Red Phase', message: 'Red-phase verification returned null' }

if (!redResult.strict_command_run || !redResult.strict_command_run.includes('AC_ENFORCE_STRICT=1')) {
  return strictFlagMissingBlock('Red Phase', redResult,
    'Without that prefix pytest_ac_enforcement downgrades the failure to xfail and reports a false green, so this result cannot be trusted. Re-run /quick-fix.')
}

// BP-600c-2-i: an error is not a red result. Check this BEFORE the passed
// boolean — a collection error reports passed=false, and without this guard
// the run would read a test that never executed as a healthy red and go on
// to "fix" code against it.
if (redResult.outcome === 'error') {
  return unrunnableTestBlock('Red Phase', 'red_phase_error', redResult, 'a red result',
    'A collection error, ImportError, SyntaxError, missing fixture or empty selection means the assertion was never evaluated, so this run says nothing about the bug. Fix the test so it executes, then re-run /quick-fix. No fix has been applied.')
}

if (redResult.passed === true || redResult.outcome === 'passed') {
  return blocked('Red Phase',
    `Test PASSES against unmodified code — the bug may already be fixed or the test doesn't cover it.\n\nTest file: ${testFile}\nCommand: ${redResult.strict_command_run}\nOutput: ${redResult.output_summary || '(none)'}`,
    { halt_reason: 'red_phase_pass', test_file: testFile, ac_id })
}

log(`Red phase confirmed under AC_ENFORCE_STRICT=1: test fails as expected.`)

// Check for root-cause divergence (BP-600e-2)
//
// The previous check asked whether the FIRST WHITESPACE TOKEN of the prose
// root cause appeared anywhere in the pytest output. That fails in both
// directions and for the same reason: one word is not a topic. A root cause
// beginning "the ..." matched almost any failure text, so real divergence went
// unreported; a correct diagnosis paraphrased without its own first word was
// reported as divergent. What distinguishes the two cases is whether the two
// texts are ABOUT the same thing, so the comparison is over their content
// vocabulary rather than over any single token.
const failureMsg = redResult.failure_message || redResult.output_summary || ''

// Words that carry no diagnostic weight. Counting these is what let the old
// check "match" on the accident of ordinary English.
const DIVERGENCE_STOPWORDS = new Set([
  'and', 'are', 'because', 'been', 'being', 'but', 'did', 'does', 'for',
  'from', 'had', 'has', 'have', 'into', 'its', 'not', 'occur', 'occurs',
  'that', 'the', 'their', 'then', 'there', 'these', 'this', 'those', 'was',
  'were', 'when', 'where', 'which', 'while', 'with', 'you', 'your',
])

/**
 * Reduce free text to its comparable content words: lowercase, split on
 * non-alphanumerics, drop stopwords and 1-2 character fragments, and strip
 * common inflectional endings so "exhausted"/"exhausts" and
 * "header"/"headers" compare as the same word.
 */
function divergenceContentWords(text) {
  const words = new Set()
  for (const token of String(text).toLowerCase().split(/[^a-z0-9]+/)) {
    if (token.length < 3 || DIVERGENCE_STOPWORDS.has(token)) continue
    let word = token
    if (word.length > 4) {
      if (word.endsWith('ing')) word = word.slice(0, -3)
      else if (word.endsWith('ed') || word.endsWith('es')) word = word.slice(0, -2)
      else if (word.endsWith('s')) word = word.slice(0, -1)
    }
    words.add(word)
  }
  return words
}

const diagnosisWords = divergenceContentWords(root_cause)
const failureWords = divergenceContentWords(failureMsg)

let sharedWords = 0
for (const word of diagnosisWords) {
  if (failureWords.has(word)) sharedWords += 1
}

// With no failure text, or a diagnosis carrying no content words at all, there
// is nothing to compare. Say so rather than inventing a verdict in either
// direction — an unanalysable diagnosis is not evidence of divergence.
const comparable = failureMsg.length > 0 && diagnosisWords.size > 0

// The test is TOTAL DISJOINTNESS: warn only when the two texts share no
// substantive vocabulary whatsoever.
//
// A proportional threshold was tried first and rejected on evidence. Requiring
// some fraction of the diagnosis's vocabulary to reappear means picking a
// number, and any number is wrong somewhere: at 0.3 a real diagnosis paired
// with a terse one-line assertion ("stub root cause for harness execution" vs
// "stub AssertionError: bug not fixed", overlap 0.2) is flagged as divergent
// and a correct run halts. Halting correct work is the more expensive error
// here, because this gate sits in front of every fix the workflow makes, and a
// missed warning still faces human review of the fix itself.
//
// Being explicit about the limitation: one incidental shared word suppresses
// the warning. That is the honest ceiling of a lexical comparison and the
// reason BP-600e-2's it_requirements ask for a semantic one. What this rule
// does guarantee is that it never fires on a pair that genuinely shares a
// topic — which is what makes it safe to run unattended.
const divergenceCheck = comparable && sharedWords === 0

if (!comparable && failureMsg.length > 0) {
  log('Divergence check skipped: the diagnosed root cause carries no content words to compare.')
}

// An explicit decision from the operator resolves the pause. This is what
// makes the step a PAUSE rather than a permanent halt: the criterion says the
// workflow "waits for user confirmation before proceeding to the fix phase",
// and a halt that can only be answered by re-running into the same halt is not
// waiting for anything.
if (divergenceCheck && divergence_decision === 'continue') {
  log('Divergence acknowledged by an explicit continue decision — proceeding to the Fix phase.')
} else if (divergenceCheck) {
  log(`Warning: test failure may diverge from diagnosed root cause.`)
  return blocked('Red Phase (divergence warning)',
    `The test failure suggests the root cause may differ from your diagnosis.\n\n  Diagnosed: ${root_cause}\n  Observed:  ${failureMsg}\n\nContinue or re-diagnose?\n\nTo continue with the diagnosis as written, re-run /quick-fix with the same args plus divergence_decision: 'continue'.\nTo re-diagnose, re-run with an updated root_cause field.`,
    {
      halt_reason: 'divergence_warning',
      test_file: testFile,
      ac_id,
      observed_failure: failureMsg,
      shared_content_words: sharedWords,
      diagnosis_content_words: diagnosisWords.size,
    })
}

// ---------------------------------------------------------------------------
// Phase 3 — Fix
// ---------------------------------------------------------------------------

phase('Fix')

/* BP-600e-1-i: snapshot dirty paths BEFORE dispatching the coder. Unavailable
   (agent failure, no dirty_paths) degrades to an empty baseline — today's
   three-artifact exclusion below, never a halt on everything. */
const baselineResult = await agent(`Snapshot dirty paths BEFORE any fix, in ${worktreeRoot}: run git -C "${worktreeRoot}" status --porcelain and list every shown path (staged/unstaged/untracked) as dirty_paths[]. Never block — return status="ok", dirty_paths=[] if clean or the command fails.`, { label: 'baseline-dirty-snapshot', phase: 'Fix', schema: BASELINE_SCHEMA })
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
Report all modified files in modified_files[], excluding pre-existing build-output drift you did not cause.

EXPECTED ADDITIONS — do not report these in extra_files, and do not set scope_expanded
because of them. They are artifacts the /quick-fix workflow itself already wrote in
earlier phases, so they always show up dirty in git status by the time you run it:
  - ${ac_path}         (AC YAML written in the AC Creation phase)
  - ${parent_ac_path}  (parent AC, back-linked to the one above)
  - ${testFile}         (test written by test-writer in the Red Phase)
extra_files[] is for genuinely unexpected files beyond ${target_file} and the three
paths above — name only those.`,
  { label: 'python-coder/fix', phase: 'Fix', schema: FIX_SCHEMA, agentType: 'python-coder' }
)

const fixBlock = blockedOnFailure(fixResult, 'Fix', 'python-coder')
if (fixBlock) return fixBlock

// Scope expansion check (BP-600e-1, narrowed by BP-600e-1-ii)
//
// By the time this phase runs, ac_path, parent_ac_path and testFile are ALWAYS
// already dirty — the workflow itself wrote them in earlier phases. A fix agent
// that reports everything from `git status --porcelain` (as instructed above)
// will therefore always see these three paths, even when it touched nothing but
// target_file. Without this filter every run halts on the workflow's own output.
//
// The exclusion set is built from the run's own known-good variables, never from
// a hardcoded glob — a glob would also silence a genuine unrelated AC or test
// edit, which is exactly the third-party change this guard exists to catch.
//
// Paths are normalised before matching (separator, leading "./", and
// worktree-absolute vs repo-relative) because the agent reports paths as
// `git status --porcelain` prints them, not as this script constructed them.
function normalizeArtifactPath(rawPath, root) {
  if (!rawPath) return ''
  let normalized = String(rawPath).replace(/\\/g, '/')
  const rootNormalized = String(root || '').replace(/\\/g, '/').replace(/\/+$/, '')
  if (rootNormalized && normalized.startsWith(`${rootNormalized}/`)) {
    normalized = normalized.slice(rootNormalized.length + 1)
  }
  normalized = normalized.split('/').filter((seg) => seg && seg !== '.').join('/')
  return normalized
}

/* BP-600e-1-i: the baseline snapshot above is folded in as extra entries, reusing normalizeArtifactPath and this same Set — a path already dirty before the coder ran is not a scope-exceeding change. Unavailable baseline (no dirty_paths) contributes nothing, so behaviour degrades to the three-artifact exclusion alone. */
const expectedArtifacts = new Set(
  [ac_path, parent_ac_path, testFile, ...((baselineResult && Array.isArray(baselineResult.dirty_paths)) ? baselineResult.dirty_paths : [])].map((p) => normalizeArtifactPath(p, worktreeRoot))
)

const genuineExtraFiles = (fixResult.extra_files || []).filter(
  (f) => !expectedArtifacts.has(normalizeArtifactPath(f, worktreeRoot))
)

// modified_files gets the same treatment, plus target_file itself. scope_expanded
// is NOT the trigger on its own — the agent can set it true while naming nothing in
// extra_files, which would otherwise either always-halt or be a no-op. What still
// must halt is an expansion never named in extra_files but visible in modified_files.
const expectedModifiedPaths = new Set([...expectedArtifacts, normalizeArtifactPath(target_file, worktreeRoot)])
const genuineExtraModifiedFiles = (fixResult.modified_files || [])
  .filter((f) => !expectedModifiedPaths.has(normalizeArtifactPath(f, worktreeRoot)))
const allGenuineExtraFiles = Array.from(new Set([...genuineExtraFiles, ...genuineExtraModifiedFiles]))

if (allGenuineExtraFiles.length > 0) {
  log(`Scope expansion detected: ${allGenuineExtraFiles.join(', ')}`)
  return blocked('Fix (scope expansion)',
    `python-coder reports the fix requires changes beyond ${target_file}.\n\nAdditional files needed: ${allGenuineExtraFiles.join(', ')}\n\nOptions:\n  - Re-run /quick-fix to proceed anyway (if python-coder only modified target_file)\n  - Escalate to /build-feature for a multi-file fix`,
    { halt_reason: 'scope_expansion', test_file: testFile, ac_id, extra_files: allGenuineExtraFiles })
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

if (!greenResult) return { status: 'blocked', phase: 'Green Phase', message: 'Green-phase verification returned null' }

if (!greenResult.strict_command_run || !greenResult.strict_command_run.includes('AC_ENFORCE_STRICT=1')) {
  return strictFlagMissingBlock('Green Phase', greenResult,
    'A default pytest run cannot distinguish a real pass from an xfail-masked failure on a not-done AC. Re-run /quick-fix.')
}

// BP-600c-2-i, green side: an error is not a failure to diagnose as "the fix
// did not work" — it is a run that never happened. Say which it was.
if (greenResult.outcome === 'error') {
  return unrunnableTestBlock('Green Phase', 'green_phase_error', greenResult, 'a failing test',
    `The assertion was never evaluated, so this says nothing about whether the fix worked. The fix IS still applied to ${target_file}. Repair whatever stopped the test executing, then re-run /quick-fix.`)
}

if (greenResult.passed === false || greenResult.outcome === 'failed') {
  return blocked('Green Phase',
    `Test still FAILS after fix.\n\nTest file: ${testFile}\nCommand: ${greenResult.strict_command_run}\nFailure: ${greenResult.failure_message || greenResult.output_summary || '(no details)'}\n\nThe fix did not resolve the bug. Options:\n  1. Re-run /quick-fix to retry with additional context\n  2. Escalate to /build-feature\n  3. Inspect and fix manually`,
    { halt_reason: 'green_phase_fail', test_file: testFile, ac_id, failure: greenResult.failure_message })
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
  return blocked('Green Phase (related tests)',
    `The fix makes its own test pass but breaks existing tests.\n\nFixed file: ${target_file}\nCommand: ${relatedResult.strict_command_run || '(not reported)'}\nBroken: ${relatedResult.failure_message || relatedResult.output_summary || '(see output)'}\n\nThe fix is still applied. Either narrow it so the neighbours survive, or escalate to /build-feature — a change that needs those tests updated is bigger than one file, which is past what /quick-fix covers.`,
    { halt_reason: 'related_tests_broken', test_file: testFile, ac_id })
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

DO NOT USE git stash. The stash stack is shared with every other session in this
repository and an unqualified pop takes the top entry, which may not be yours — that
recipe has already destroyed a concurrent session's uncommitted work. Revert through two
files in /tmp instead.

Run these as single, simple commands, in order:

1. cp "${worktreeRoot}/${target_file}" "/tmp/quickfix-${ac_id}-fixed.bak"
2. git -C "${worktreeRoot}" show "HEAD:${target_file}" > "/tmp/quickfix-${ac_id}-head.orig"
   This must exit 0 and leave a non-empty file. If it does not, STOP here and report
   red_without_fix=false with the reason — nothing has been overwritten yet, and the fix is
   still in place. Never redirect git show straight over "${target_file}": the shell
   truncates the target before git runs, so a failed lookup would destroy the fix.
3. cp "/tmp/quickfix-${ac_id}-head.orig" "${worktreeRoot}/${target_file}"
4. AC_ENFORCE_STRICT=1 python -m pytest "${testFile}" -v
   EXPECTED: FAIL. Record the result as red_without_fix (true when it fails).
5. cp "/tmp/quickfix-${ac_id}-fixed.bak" "${worktreeRoot}/${target_file}"
6. AC_ENFORCE_STRICT=1 python -m pytest "${testFile}" -v
   EXPECTED: PASS. Record the result as green_with_fix_restored.

Then run: diff -q "/tmp/quickfix-${ac_id}-fixed.bak" "${worktreeRoot}/${target_file}"
and set fix_restored=true only when it exits 0 with no output. Do not infer the restore
from git status — a path showing as modified only proves it differs from HEAD, which a
partial or corrupted restore does too.

RESTORING THE FIX IS MANDATORY, on the failing path as much as the passing one: run step 5
even when step 4 came out green. If the restore fails for any reason, say so explicitly and
set fix_restored=false rather than continuing — the run must not proceed to commit with the
fix reverted. Name /tmp/quickfix-${ac_id}-fixed.bak as the file that holds it.

Set status="ok" only when red_without_fix=true AND green_with_fix_restored=true AND
fix_restored=true.`,
  { label: 'mutation-proof', phase: 'Green Phase', schema: MUTATION_SCHEMA }
)

// The two mutation-proof failures below differ only in halt_reason and message.
function mutationProofBlock(haltReason, message) {
  return blocked('Green Phase (mutation proof)', message,
    { halt_reason: haltReason, test_file: testFile, ac_id, detail: mutationResult })
}

if (!mutationResult || mutationResult.status === 'blocked' ||
    mutationResult.fix_restored !== true) {
  return mutationProofBlock('mutation_proof_incomplete', mutationResult
    ? `Mutation proof did not complete cleanly.\n\n  red without fix:      ${mutationResult.red_without_fix}\n  green with fix back:  ${mutationResult.green_with_fix_restored}\n  fix restored:         ${mutationResult.fix_restored}\n\n${mutationResult.message || ''}\n\nIf fix_restored is false the fix is NOT in the working tree — recover it with "cp /tmp/quickfix-${ac_id}-fixed.bak ${worktreeRoot}/${target_file}" before doing anything else.`
    : `Mutation-proof agent returned null — the fix may have been left reverted. Compare "${worktreeRoot}/${target_file}" against "/tmp/quickfix-${ac_id}-fixed.bak" and copy it back if they differ, before continuing.`)
}

if (mutationResult.red_without_fix !== true || mutationResult.green_with_fix_restored !== true) {
  return mutationProofBlock('mutation_proof_failed',
    `The test is NOT coupled to the fix.\n\n  Reverting the fix left the test ${mutationResult.red_without_fix ? 'red (expected)' : 'GREEN — it passes without the fix'}.\n  Restoring the fix left the test ${mutationResult.green_with_fix_restored ? 'green (expected)' : 'RED — it fails with the fix'}.\n\nA test that passes without the fix proves nothing about the fix. Rewrite the test to assert the behaviour the fix actually changes, then re-run /quick-fix.`)
}

log(`Mutation proof passed: reverting the fix returns the test to red; restoring it returns green.`)

// ---------------------------------------------------------------------------
// Knowledge Routing — dispatched once the phases that perform the work have
// returned, and BEFORE the phase that publishes this unit of work's own
// output ("commit"), so its writes can ride the commit this path already
// makes (INF-700a-1's ordering clause, applied here per INF-700a-1-i's
// per-path coverage requirement). Fail-open: there is deliberately no halt
// branch below — whatever this dispatch reports, the run's own outcome and
// exit status proceed unaffected.
// ---------------------------------------------------------------------------

phase('Knowledge Routing')

const knowledgeRoutingReply = await agent(
  `Route any knowledge records the phases that just ran emitted to the ` +
  `surface each one names — nobody runs this by hand.\n\n` +
  `Run this single Bash command from the repository root and read its JSON ` +
  `summary and exit code:\n` +
  `   python3 {{config.output_root}}/scripts/knowledge/harvest_learnings.py\n\n` +
  `Classify the outcome as exactly one of three cases:\n` +
  `  - "completed": the harvester ran to completion (exit 0 or 3 — some ` +
  `records left unroutable is still a completed run).\n` +
  `  - "could_not_complete": the declared sink could not be read, or a ` +
  `destination file could not be written (exit 1, 2, or 4).\n` +
  `  - "did_not_run": the command itself could not be run at all.\n\n` +
  `Return JSON: { "case": "completed"|"could_not_complete"|"did_not_run", ` +
  `"read": <records read>, "written": <records written to a surface>, ` +
  `"unwritten": <records left unwritten>, "detail": "<what could not be ` +
  `done, or null>" }.\n\n` +
  `This step must never block, retry, or fail the build — always return a ` +
  `best-effort classification, even on an unreadable sink or a failed write.`,
  { label: 'knowledge-routing-step', phase: 'Knowledge Routing', schema: KNOWLEDGE_ROUTING_SCHEMA, agentType: 'python-coder' }
)

const knowledgeRouting = classifyKnowledgeRouting(knowledgeRoutingReply)

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

const commitBlock = blockedOnFailure(commitResult, 'Commit', 'commit agent')
if (commitBlock) return commitBlock

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
  return blocked('Changelog', changelogResult
    ? `Changelog entry was not authored: ${changelogResult.message || '(no detail)'}\n\nThe fix is committed (${commitResult.commit_sha || 'see git log -1'}) but the PR will fail the required "Changelog entry present" check without an entry.`
    : 'changelog-agent returned null. The fix is committed but the required changelog entry is missing.',
    { halt_reason: 'changelog_missing', ac_id, commit_sha: commitResult.commit_sha, detail: changelogResult })
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

const changelogCommitBlock = blockedOnFailure(changelogCommit, 'Changelog (commit)', 'commit agent (changelog entry)',
  { halt_reason: 'changelog_commit_failed', ac_id })
if (changelogCommitBlock) return changelogCommitBlock

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
   If the user declines (or there is no interactive user to ask), return status="ok" with
   pr_opened=false, pr_url="", AND ALSO return:
     - compare_url: the compare URL for this branch, e.g.
       https://github.com/<org>/<repo>/compare/main...${activeBranch}?expand=1
       Derive <org>/<repo> from git -C "${worktreeRoot}" remote get-url origin.
     - pr_command: the exact command that would open the PR, e.g.
       gh pr create --base main --head "${activeBranch}" --title "<title>" --body-file <path>
   These two fields are how the caller opens the PR themselves later without re-deriving
   anything — do not omit them just because the message text also mentions the compare URL.

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

const pushBlock = blockedOnFailure(pushResult, 'Close', 'Close-phase agent',
  { halt_reason: 'push_failed', ac_id, commit_sha: commitResult.commit_sha })
if (pushBlock) return pushBlock

// ---------------------------------------------------------------------------
// Done
// ---------------------------------------------------------------------------

// pr_opened=false covers two different endings: a PR already existed (pr_url is
// populated, nothing left to do) and no PR exists at all (pr_url is empty — the
// confirmation gate in step 4 above was declined or unanswered). Only the second
// shape is an outstanding action owned by the caller; the first is done.
const prNotOpened = !pushResult.pr_opened && !pushResult.pr_url
const prOpenCommand = pushResult.pr_command ||
  `gh pr create --base main --head "${activeBranch}" --title "<title>" --body-file <path>`
const outstandingAction = prNotOpened
  ? {
      type: 'pr_not_opened',
      owner: 'caller',
      reason: 'Opening a pull request is outward-facing and stays behind an explicit ' +
        'confirmation gate. No confirmation was given during this run, so quick-fix ' +
        'intentionally stopped short of opening one — the caller must open it.',
      branch: activeBranch,
      compare_url: pushResult.compare_url || '',
      command: prOpenCommand,
    }
  : null

return {
  status: 'ok',
  action_required: prNotOpened,
  outstanding_action: outstandingAction,
  message: `/quick-fix complete.\n\n  AC:        ${ac_id} — ${ac_title}\n  Test:      ${testFile}  [green, mutation-proved]\n  Fix:       ${target_file}\n  Changelog: ${changelogResult.entry_path}\n  Commit:    ${commitResult.commit_sha || '(see git log -1)'}\n  Worktree:  ${worktreeRoot}${selfIsolated ? ' (self-isolated)' : ' (in place)'}\n  Branch:    ${activeBranch}\n  PR:        ${pushResult.pr_url || 'none — not opened'}` +
    (prNotOpened
      ? `\n\n  *** ACTION REQUIRED ***\n  No pull request was opened. Opening it is now YOUR responsibility.\n  Compare: ${outstandingAction.compare_url || '(derive from branch above)'}\n  Command: ${outstandingAction.command}`
      : ''),
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
  knowledge_routing: knowledgeRouting,
}
