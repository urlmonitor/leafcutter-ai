/**
 * finalize-feature.js — Claude Code Workflow script
 *
 * Replaces the finalize-feature LLM agent for the post-merge feature
 * finalization sequence. Converts the 6-step orchestration from recursive
 * agent calls to a deterministic JavaScript workflow where every specialist
 * dispatch is a flat depth-1 agent() call.
 *
 * This is a LEAF WORKFLOW — it MUST NOT call workflow() internally. In E2,
 * workflow() throws (leaf-invariant guard) — this is preserved by design.
 * Calling workflow() from inside a child workflow would reintroduce nesting.
 *
 * Architecture:
 *   Pre-flight: status-checker reads current branch and worktree root
 *   Step 0: capture baseline test run on main HEAD (test-runner — graceful on failure)
 *   Step 1: probe for open PR (gh pr list); dispatch pull-request if missing
 *   Step 2: merge origin/main into worktree --no-commit --no-ff (HALT on conflict)
 *   Step 3: run post-merge tests + triage; HALT if regressions detected
 *   Step 4: merge PR to main — only if tests pass (confirmation-gated)
 *   Step 5: sync local main (git checkout main && git pull)
 *   Step 6: report untracked pre-existing/flaky failures (auto-ticketing disabled) + scope-detection
 *   Step 7: probe worktree list; dispatch worktree-agent remove if worktree exists
 *
 * Resumability: each step probes observable state before dispatching. Re-running
 * /finalize-feature after a mid-run crash resumes from the first incomplete step.
 *
 * E2 canonical form: top-level body, agent(prompt, opts), args global.
 * No export async function run() — E2 executes the top-level body directly.
 * workflow() is NOT called (leaf-invariant preserved: E2 throws, which is correct).
 *
 * ADR: docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
 * Ticket: tickets/00_inbox/TICKET-20260602-FinalizeFeatureJSWorkflow.md
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 * No fallback: the legacy LLM agent (finalize-feature.md) has been removed. Older
 * installs receive an explicit error from the slash command.
 */

export const meta = {
  name: "finalize-feature",
  description:
    "Post-merge feature finalization: capture pre-merge test baseline on main, open PR if missing, merge origin/main into worktree, run post-merge tests (with triage baseline), merge PR to main only when tests pass, sync local main, close tickets/archive epic, remove worktree. Prompt gates on all destructive steps. HALT on test regression before PR merge. Returns { status: ok } with per-step summary on full success.",
  phases: [
    "pre-flight (status-checker reads branch + worktree root)",
    "step-0: capture baseline test run on main HEAD (test-runner — graceful on failure)",
    "step-1: open PR if missing (pull-request agent)",
    "step-2: merge origin/main into worktree --no-commit --no-ff (HALT on conflict)",
    "step-3: run post-merge tests + triage (test-runner + test-failure-triage — HALT on regressions)",
    "step-3.5: pre-merge AC closure — reset test-merge, set ticket status: done + mark source ACs done, commit on feature branch",
    "step-4: merge PR to main — only if tests pass (prompt gate + pull-request agent)",
    "step-5: sync local main (status-checker shell)",
    "step-6: report untracked pre-existing/flaky failures (auto-ticketing disabled) + scope-detection (status-checker — no writes on main)",
    "step-7: remove worktree (worktree-agent — gate delegated)",
  ],
};

// ---------------------------------------------------------------------------
// JSON Schemas for agent() responses (E2: engine enforces; no JSON.parse needed)
// ---------------------------------------------------------------------------

const GATE_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    message: { type: 'string' },
  },
  required: ['status'],
}

// ---------------------------------------------------------------------------
// Narration helper — AC BO-1000a-1, AC BO-1000a-1-i
//
// Emits a start-of-step progress line on the workflow's narration channel
// (via log()) at the entry of each numbered step, BEFORE any agent() dispatch
// in that step.
//
// AC BO-1000a-1-i (error-path ordering guarantee): narrate() is always called
// BEFORE the step's first agent() dispatch, so even when a sub-agent returns
// an error or a malformed result the start-of-step line is already present in
// the progress stream. The in-flight step at the moment of failure is therefore
// identifiable from the progress output alone — the error branch need not (and
// must not) emit its own separate 'Step X of N' diagnostic line.
//
// The 'progressText' argument carries the "Step X of N" label (AC BO-1000a-2):
// N MUST equal STEP_COUNT. Use double-quoted strings so N appears as a
// detectable integer literal (required by BO-1000a-1 static text tests) while
// avoiding the single-quoted bare-literal form that BO-1000a-2 prohibits.
// When STEP_COUNT changes, update every narrate() call alongside it.
// ---------------------------------------------------------------------------

/**
 * Emit a start-of-step progress line on the workflow's narration channel.
 *
 * Invoke at the entry of each numbered step, before ANY agent() dispatch in
 * that step (AC BO-1000a-1, AC BO-1000a-1-i). This guarantees the start-of-step
 * line is already in the progress stream before any sub-agent can error or
 * return a malformed result, so the in-flight step is always identifiable from
 * the progress output alone — step identification does not depend on the error
 * branch emitting its own diagnostic line (AC BO-1000a-1-i).
 *
 * Pass progressText as a double-quoted string with N equal to STEP_COUNT
 * (AC BO-1000a-2), e.g. "Step 0 of 9". Double-quoted strings satisfy
 * BO-1000a-1 static-text detection while not triggering the single-quoted
 * literal check in BO-1000a-2.
 *
 * @param {string} progressText - Position label, e.g. "Step 0 of 9".
 *   N must always equal STEP_COUNT; update both together when the step
 *   sequence changes.
 * @param {string} description  - Human-readable description of what this step
 *   is about to do.
 */
function narrate(progressText, description) {
  const line = progressText + ': ' + description;
  log(line);
  appendJournal(line);
}

// ---------------------------------------------------------------------------
// Outcome helper — AC BO-1000b-1
//
// Emits a post-step outcome line on the workflow's narration channel
// (via log()) after each numbered step's work completes on the success path,
// AFTER the step's agent() dispatches (distinct from narrate() which fires
// BEFORE the first dispatch). Also records the outcome to stepOutcomes[] in
// insertion order so BO-1000b-2 can compose an end-of-run summary and
// BO-1000c-1a can relay it via the live journal channel.
//
// The 'progressText' argument carries the literal 'Step X of N' label so the
// text is statically visible to tooling and tests that parse the source file.
// ---------------------------------------------------------------------------

const stepOutcomes = [];

/**
 * Emit a post-step outcome line on the workflow's narration channel.
 *
 * Invoke after each numbered step's work completes on the success path,
 * after all agent() dispatches in the step (AC BO-1000b-1). The description
 * carries the concrete result data for the step — not a bare 'done' notice.
 *
 * Also records to stepOutcomes[] so downstream consumers (BO-1000b-2
 * end-of-run summary; BO-1000c-1a live journal relay) can read the ordered
 * per-step record without re-parsing log output.
 *
 * @param {string} progressText - Literal position label, e.g. 'Step 0 of 9'.
 * @param {string} description  - Concrete result description for the step.
 */
function outcome(progressText, description) {
  const entry = { step: progressText, outcome: description };
  stepOutcomes.push(entry);
  const line = progressText + ': ' + description;
  log(line);
  appendJournal(line);
}

// ---------------------------------------------------------------------------
// Single-source-of-truth step count — AC BO-1000a-2
//
// Derived from the numbered entries in meta.phases (entries whose key starts
// with "step-", excluding "pre-flight"). The value must match every N in the
// narrate() calls below. N must be identical in every start-of-step line
// across a run and must equal the declared step count.
//
// When adding or removing a step:
//   1. Update meta.phases.
//   2. Update STEP_COUNT.
//   3. Update the N literal in every affected narrate() call.
// ---------------------------------------------------------------------------

/** Total number of numbered steps in the finalize sequence (AC BO-1000a-2). */
const STEP_COUNT = 9;

// AC FIN-100h: statuses meaning "this agent DECLINED the dispatch".
//
// A refusal is categorically different from a failure: a failed step ran and
// produced a result, a refused step never ran at all. The workflow previously
// modelled only success/known-failure, so a refusal fell through whatever
// terminal `else` a step happened to have — and on step 2 that else IS the
// success path, so a refused merge was recorded as "Merged origin/main
// cleanly". Load-bearing steps must halt on a refusal, never degrade.
const REFUSAL_STATUSES = new Set(["refused", "wrong_agent", "declined", "not_permitted"]);

/**
 * True when an agent's reported status means it declined to do the work.
 *
 * Matches the exact refusal vocabulary plus the `out_of_scope*` family, which
 * agents emit as `out_of_scope_for_<agent-name>`.
 *
 * @param {string} status Lower-cased status string from the agent's JSON.
 * @returns {boolean}
 */
function isRefusalStatus(status) {
  const s = String(status || "").toLowerCase();
  return REFUSAL_STATUSES.has(s) || s.startsWith("out_of_scope");
}

// AC BO-1000a-2-i: step 3.5 is the intermediate closure step — it is
// included in STEP_COUNT so its position is monotonic (3 < 3.5 < 4) and N
// is unchanged for all other steps. Pre-flight aborts occur BEFORE the
// first numbered step: no narrate() call is made in the pre-flight sections
// (Pre-flight and Pre-flight 2); pre-flight failures use a distinct
// non-numbered return ({ status: 'error', ... }).

// ---------------------------------------------------------------------------
// E2 top-level body — executed directly by the E2 engine
//
// NOTE on leaf invariant: workflow() is NOT called anywhere in this script.
// In E2, workflow() throws — that throw IS the leaf guard. Since we never call
// workflow(), the leaf invariant is preserved without any explicit check.
// ---------------------------------------------------------------------------

// -------------------------------------------------------------------------
// Pre-flight: detect branch and worktree root
// -------------------------------------------------------------------------

phase('Pre-flight')

/**
 * Tolerant agent-reply reader (BP-300e). Extracts the first balanced JSON
 * object or array from a raw agent reply string, tolerating surrounding prose.
 *
 * Passthrough: when raw is already an object or array (not a string), it is
 * returned unchanged — no re-parse is attempted.
 *
 * Brace-matching: scan character-by-character, tracking depth and skipping
 * characters inside JSON string literals (including escaped quotes), and
 * return the first complete balanced JSON value.
 *
 * Error: when no parseable JSON value is found (including empty or
 * whitespace-only replies), throws a typed Error naming both stage and agent.
 *
 * @param {*} raw - Value returned by agent() — may be string, object, or null.
 * @param {{ stage: string, agent: string }} ctx - Context for error messages.
 * @returns {*} Parsed JSON value (object, array, etc.).
 */
function parseAgentJson(raw, ctx) {
  const stage = ctx.stage;
  const agent = ctx.agent;
  if (typeof raw !== "string") {
    return raw;
  }
  if (!raw.trim()) {
    throw new Error(
      "[" + stage + "] " + agent +
      " returned an empty or whitespace-only reply — no parseable JSON found"
    );
  }
  const closeFor = { 123: 125, 91: 93 };
  for (let i = 0; i < raw.length; i++) {
    const code = raw.charCodeAt(i);
    if (code !== 123 && code !== 91) { continue; }
    const closeCode = closeFor[code];
    let depth = 0;
    let inString = false;
    let j = i;
    while (j < raw.length) {
      const ch = raw.charCodeAt(j);
      if (inString) {
        if (ch === 92 && j + 1 < raw.length) {
          j += 2;
          continue;
        }
        if (ch === 34) { inString = false; }
      } else {
        if (ch === 34) { inString = true; }
        else if (ch === code) { depth++; }
        else if (ch === closeCode) {
          depth--;
          if (depth === 0) {
            try {
              return JSON.parse(raw.slice(i, j + 1));
            } catch (_) {
              break;
            }
          }
        }
      }
      j++;
    }
  }
  throw new Error(
    "[" + stage + "] " + agent +
    " returned a reply with no parseable JSON — " +
    "all reply-reading sites must route through parseAgentJson"
  );
}

// ---------------------------------------------------------------------------
// §R — Inline pause-resume helpers (ADR-024 BO-2300 RESUME half).
// E2 workflow bodies are self-contained and cannot import local modules, so the
// pause-resume helper is defined inline here. The same helper is inlined in
// plan-feature.js — keep them in sync.
// ---------------------------------------------------------------------------

/**
 * Validate a resume_answer's shape against its declared question type.
 * @param {object}       answer       - args.resume_answer object.
 * @param {string}       expectedType - "single_choice" | "priority_choice" | "free_text"
 * @param {string[]|null} [validOptions] - Allowed action/choice values for single_choice gates.
 * @returns {{ valid: boolean }}
 */
function validateAnswerShape(answer, expectedType, validOptions) {
  if (!answer || typeof answer !== "object") { return { valid: false }; }
  if (expectedType === "single_choice") {
    const act = typeof answer.action === "string" ? answer.action
      : (typeof answer.choice === "string" ? answer.choice : null);
    if (!act) { return { valid: false }; }
    if (Array.isArray(validOptions) && validOptions.length > 0 && !validOptions.includes(act)) {
      return { valid: false };
    }
    return { valid: true };
  }
  if (expectedType === "priority_choice") {
    return (answer.priority != null) ? { valid: true } : { valid: false };
  }
  if (expectedType === "free_text") {
    return (typeof answer.text === "string") ? { valid: true } : { valid: false };
  }
  return { valid: false };
}

/**
 * Apply a validated resume answer by its type and return the effective gate decision.
 * @param {object} answer - Validated answer from args.resume_answer.
 * @param {string} type   - "single_choice" | "priority_choice" | "free_text"
 * @returns {object} Gate decision e.g. { action: "approve" }.
 */
function applyAnswerByType(answer, type) {
  if (type === "priority_choice") { return { action: "approve", priority: answer.priority }; }
  if (type === "free_text") { return { action: "approve", text: answer.text }; }
  return { action: answer.action || answer.choice };
}

/**
 * Resume-aware interactive gate resolver (ADR-024).
 *
 * CORRECTNESS INVARIANT (ADR-024 Rule 4): checks args.resume_answer BEFORE liveGateFn.
 *
 * Return value:
 *   { action: "..." }                   — valid gate decision; caller proceeds.
 *   { status: "paused_awaiting_input" } — headless or invalid answer; caller MUST return.
 *   { status: "nothing_to_resume" }     — record absent (exists:false); caller MUST return.
 *   { status: "unresumable_stale" }     — record stale; caller MUST return.
 *
 * @param {string}   gateId      - Gate label (e.g. "step-4-merge-gate").
 * @param {Function} liveGateFn  - Zero-arg async fn; returns parsed gate decision or null (headless).
 * @param {object}   args        - Workflow args (may include resume_answer, run_id).
 * @param {object}   context     - Context snapshot for the pause record.
 * @param {object}   [descriptor] - Gate question descriptor: { type, options, prompt }.
 * @param {string}   [runId]     - Explicit run id; falls back to args.run_id || "default-run".
 * @returns {Promise<object>}
 */
async function resolveGate(gateId, liveGateFn, args, context, descriptor, runId) {
  runId = runId || (args && args.run_id) || "default-run";
  const answerType = (descriptor && descriptor.type) || "single_choice";
  const validOptions = (descriptor && Array.isArray(descriptor.options)) ? descriptor.options : null;

  // ADR-024 Rule 4: check resume_answer BEFORE liveGateFn.
  if (args && args.resume_answer && args.resume_answer.gate_id === gateId) {
    const incomingType = args.resume_answer.type || answerType;
    const validation = validateAnswerShape(args.resume_answer, incomingType, validOptions);
    if (!validation.valid) {
      // Wrong/malformed shape or action not in valid options: stay paused.
      return { status: "paused_awaiting_input", run_id: runId, gate_id: gateId };
    }
    // Shape valid: consult the durable record via agent dispatch (body has no fs access per ADR-024).
    const _readPrompt =
      "Read the durable pause record for this run. Run exactly:\n" +
      "  python scripts/pause_store.py read --run-id " + runId + "\n" +
      "Return EXACTLY its stdout JSON of the form {\"exists\":<bool>,\"stale\":<bool>,\"record\":<obj|null>}.";
    const _rawRec = await agent(_readPrompt, { agentType: "status-checker", label: "read-pause-record" });
    let recCheck;
    try {
      recCheck = (typeof _rawRec === "string")
        ? parseAgentJson(_rawRec, { stage: "read-pause-record", agent: "status-checker" })
        : _rawRec;
    } catch (_e) { recCheck = null; }
    // FAIL CLOSED: apply ONLY when exists===true AND stale is not true.
    if (!recCheck || recCheck.exists !== true) {
      return { status: "nothing_to_resume", run_id: runId, gate_id: gateId };
    }
    if (recCheck.stale === true) {
      return { status: "unresumable_stale", run_id: runId, gate_id: gateId };
    }
    return applyAnswerByType(args.resume_answer, incomingType);
  }

  // No matching resume_answer: call the live gate.
  let gateAnswer = null;
  if (typeof liveGateFn === "function") {
    try { gateAnswer = await liveGateFn(); } catch (_err) { gateAnswer = null; }
  }
  // Valid explicit decision.
  if (gateAnswer !== null && gateAnswer !== undefined && typeof gateAnswer === "object" &&
      (typeof gateAnswer.action === "string" || typeof gateAnswer.choice === "string")) {
    return gateAnswer;
  }
  // Headless or unparseable: pause and persist.
  return pauseAtGate(gateId, runId, context, descriptor);
}

/**
 * Pause the workflow at an interactive gate and persist the pending-question
 * record (ADR-024 pause-resume mechanism).
 *
 * Dispatches a "pause-persist" agent call carrying the question shape and
 * context snapshot, then returns { status: "paused_awaiting_input" } so the
 * caller can `return` it immediately, exiting without losing committed steps.
 *
 * Called by resolveGate() on the headless path. Direct callers should use
 * resolveGate() instead, which checks args.resume_answer first (ADR-024 Rule 4).
 *
 * @param {string} gateId        - Gate label (e.g. "step-4-merge-gate").
 * @param {string} runId         - Current run identifier.
 * @param {object} ctxSnapshot   - Workflow context snapshot at pause time.
 * @param {object} [descriptor]  - Gate question descriptor: { type, options, prompt }.
 * @returns {Promise<{status: "paused_awaiting_input", run_id: string, gate_id: string}>}
 */
async function pauseAtGate(gateId, runId, ctxSnapshot, descriptor) {
  const questionType = (descriptor && descriptor.type) || "single_choice";
  const questionOptions = (descriptor && Array.isArray(descriptor.options))
    ? descriptor.options : ["approve", "edit", "cancel", "defer"];
  const questionPrompt = (descriptor && descriptor.prompt) ||
    ("Interactive gate '" + gateId + "' requires a human decision. Options: " +
      questionOptions.join(", ") + ".");
  const question = {
    type: questionType,
    gate_id: gateId,
    options: questionOptions,
    prompt: questionPrompt,
  };
  const context = ctxSnapshot || { gate_id: gateId };
  const rec = {
    run_id: runId, gate_id: gateId,
    question: question, context: context,
    status: "paused_awaiting_input",
  };
  const _persistPrompt =
    "Interactive gate '" + gateId + "' has no reachable human answerer. " +
    "Persist this pending-question record so the run can be resumed later. Run exactly:\n" +
    "  python scripts/pause_store.py write --run-id " + runId + " --record '" + JSON.stringify(rec) + "'\n" +
    "That writes .leafcutter/paused_runs/" + runId + ".json. Return the command's JSON stdout.";
  await agent(_persistPrompt, { agentType: "status-checker", label: "pause-persist" });
  return { status: "paused_awaiting_input", run_id: runId, gate_id: gateId };
}

// -------------------------------------------------------------------------
// Pre-flight worktree resolution
//
// Fix (TICKET-20260707-Finalize_Preflight_Branch_Detection):
// Previously the pre-flight ran `git branch --show-current` with no -C
// anchor, reading from the session CWD — which is often the main clone on
// `main`. This caused a false "must be run from a feature branch" abort even
// when a valid epic worktree existed.
//
// The new approach:
//   1. Extract the epic/ticket name from `args` (e.g. "EPIC-FooBar").
//   2. Run `git worktree list --porcelain` (no anchor needed — lists all
//      registered worktrees for this repo regardless of CWD) to find the
//      worktree whose branch matches `EPIC-<name>` or the single-ticket branch.
//   3. Anchor the branch/toplevel detection at the resolved worktree root
//      using `git -C <worktree_root>`.
//   4. When no matching worktree is found, fail with a clear, actionable
//      message (not a silent misdetection or a false "on main" abort).
//   5. When no arg is provided, fall back to the CWD-based detection so
//      existing callers that pass no argument are unaffected.
// -------------------------------------------------------------------------

// Extract the epic/ticket argument passed to the workflow.
// For `/finalize-feature EPIC-FooBar`, args is the string "EPIC-FooBar".
// When args is an object (e.g. {target: "ge-116a-1"} from a /build-feature dispatch
// or the workflow engine), extract args.target or args.target_branch (FIN-100g-2).
// When args is empty, has no target/target_branch key, or carries an empty value,
// epicArg is '' and the pre-flight falls back to CWD-based detection (FIN-100g-2-i).
const _epicArgCandidate = (
  typeof args === 'string'
    ? args
    : (args && (args.target || args.target_branch)) || ''
);
// A non-string target value (e.g. a number or object) is treated as no target —
// it falls back to CWD detection (FIN-100g-2-i) rather than raising a .trim()
// TypeError. Only a string candidate is trimmed.
const epicArg = (typeof _epicArgCandidate === 'string' ? _epicArgCandidate : '').trim();

const preflightResult = await agent(
  "Detect the target worktree branch and root path for /finalize-feature.\n" +
  "\n" +
  (epicArg
    ? "A target argument was provided. Resolve the worktree from it.\n" +
      `Argument: "${epicArg}"\n` +
      "\n" +
      "Step 1 — list all registered worktrees:\n" +
      "  Run: git worktree list --porcelain\n" +
      "  Parse the output. Each block starts with 'worktree <path>' followed by\n" +
      "  'HEAD <sha>' and optionally 'branch refs/heads/<branch_name>'.\n" +
      "  Detached-HEAD entries have no 'branch' line — skip them.\n" +
      "\n" +
      "Step 2 — find the matching worktree:\n" +
      "  Find a worktree whose branch_name:\n" +
      `    - equals "${epicArg}" (exact match), OR\n` +
      `    - equals "feature/${epicArg}", OR\n` +
      `    - contains "${epicArg}" as a substring.\n` +
      "  Exclude any worktree whose branch_name is 'main' or 'master'.\n" +
      "  If multiple candidates match, prefer the one whose branch_name is\n" +
      "  shortest (fewest extra characters beyond the argument string).\n" +
      "\n" +
      "Step 3a — matching worktree found:\n" +
      "  Let <wt_path> = the matched worktree path.\n" +
      "  Run: git -C \"<wt_path>\" branch --show-current\n" +
      "  Run: git -C \"<wt_path>\" rev-parse --show-toplevel\n" +
      "  Return ONLY: { \"found\": true, \"branch\": \"<branch_name>\", \"worktree_root\": \"<path>\" }\n" +
      "\n" +
      "Step 3b — no matching worktree found (FIN-100g-3):\n" +
      "  A target was supplied but resolves to no registered worktree. Build a\n" +
      "  SINGLE actionable error string containing ALL THREE of:\n" +
      `    (a) the unresolved target name '${epicArg}';\n` +
      "    (b) the expected argument forms — a bare branch-name string, OR an\n" +
      "        object with a target/target_branch key;\n" +
      "    (c) the candidate worktrees that ARE currently registered and their\n" +
      "        checked-out branches — list the '<path> [<branch>]' entries you\n" +
      "        parsed from `git worktree list --porcelain` in Step 1, sorted by\n" +
      "        path for deterministic output.\n" +
      "  This message is intentionally more specific than the generic\n" +
      "  branch-named error (it adds the expected forms and the candidate list).\n" +
      `  Return ONLY: { "found": false, "branch": null, "worktree_root": null,\n` +
      `               "error": "No worktree found matching target '${epicArg}'. ` +
      `Expected a bare branch-name string OR an object with a target/target_branch key. ` +
      `Candidate worktrees (from git worktree list --porcelain): <path> [<branch>], ..." }`
    : "No target argument provided — fall back to CWD-based detection.\n" +
      "1. Run: git branch --show-current\n" +
      "2. Run: git rev-parse --show-toplevel\n" +
      "Return ONLY: { \"found\": true, \"branch\": \"<name>\", \"worktree_root\": \"<path>\" }"
  ),
  { agentType: "status-checker", label: "pre-flight", phase: "Pre-flight" }
)

let preflightInfo;
{
  try {
    preflightInfo = parseAgentJson(preflightResult, { stage: "pre-flight", agent: "status-checker" }) || { found: true, branch: "unknown", worktree_root: "unknown" };
  } catch (_parseErr) {
    log("[finalize-feature] pre-flight parse malformed — using safe defaults (branch: unknown)");
    preflightInfo = { found: true, branch: "unknown", worktree_root: "unknown" };
  }
}

// When the worktree resolution step found no matching worktree, fail with a
// clear, actionable message rather than a silent misdetection.
if (preflightInfo.found === false) {
  return {
    status: "error",
    message:
      preflightInfo.error ||
      `/finalize-feature could not find a worktree matching target "${epicArg}". ` +
      "Expected a bare branch-name string OR an object with a target/target_branch key. " +
      "Run `git worktree list` to see the candidate worktrees and their branches, " +
      "then re-run with the correct epic or ticket name.",
    action_required: "resolve_worktree_argument",
  };
}

const BRANCH = (preflightInfo.branch || "").trim();
const WORKTREE_ROOT = (preflightInfo.worktree_root || "").trim();

if (!BRANCH || BRANCH === "main" || BRANCH === "master") {
  return {
    status: "error",
    message:
      "/finalize-feature must be run from a feature branch, not main/master " +
      `(detected branch: "${BRANCH}" from worktree resolved via arg: "${epicArg}"). ` +
      "Checkout your feature branch and re-run.",
    action_required: "switch_to_feature_branch",
  };
}

// ---------------------------------------------------------------------------
// Run-progress journal — AC BO-1000c-1a
//
// Durable append-only file at a worktree-keyed path so the launcher
// (BO-1000c-1b) can read it while the run is in flight. Each narrate call
// and outcome call appends a line incrementally (append-as-you-go),
// not only at end-of-run, so an external poller sees progress live.
//
// Path: run-progress.journal.jsonl under WORKTREE_ROOT — deterministically
// locatable by the launcher without parsing log output.
// ---------------------------------------------------------------------------
const journalPath = WORKTREE_ROOT + '/run-progress.journal.jsonl';

/**
 * Append one progress line to the durable run-progress journal.
 *
 * Best-effort: a journal-write failure is logged at WARNING level and
 * never aborts the finalize run (AC BO-1000c-1a policy). The journal is
 * append-only (fs.appendFileSync) so emission order is preserved across
 * all steps (AC BO-1000c-1a AC-2).
 *
 * @param {string} line - The progress line to append (newline appended automatically).
 */
function appendJournal(line) {
  try {
    const fs = require('fs');
    fs.appendFileSync(journalPath, line + '\n');
  } catch (journalErr) {
    log('[finalize-feature] WARNING: journal write failed (best-effort) — ' + journalErr.message);
  }
}

// Track completed and skipped steps for the final summary.
const completedSteps = [];
const skippedSteps = [];
let prNumber = null;
let prUrl = null;
let mergeResult = null;
let testResult = null;
const ticketsClosed = [];
// Failures that could not be auto-ticketed (create-ticket is a workflow, not an agent).
// Populated by step 6a; never confused with actually-created tickets.
const untrackedFailures = [];
let worktreeRemoved = false;
// Triage report from step 3; null means tests passed (no triage needed).
let triageReport = null;
// Closure counts from step 3.5 (pre-merge AC closure).
let ticketsClosedPreMerge = 0;
let acsClosed = 0;
let acsSkipped = 0;

// Baseline state (populated by step 0; forwarded to step 3 triage).
// null means the baseline run did not complete — triage treats all failures
// as regressions in that case (conservative classification).
let baselineFailures = null; // string[] | null
let baselineSha = null;      // string | null
let baselineRunAt = null;    // ISO string | null

// Cleanup guard: remove temp baseline worktree on any early exit.
// The path is set by step 0 and cleared after the worktree is removed.
// args.baseline_ts replaces Date.now() (banned in E2 — non-deterministic).
const baselineTmpPath = `/tmp/leafcutter-main-baseline-${args.baseline_ts || 'baseline'}`;
let baselineWorktreePath = null;

/**
 * Attempt to remove the temporary baseline worktree if it still exists.
 * Silently swallows errors — this is a best-effort cleanup.
 */
async function cleanupBaselineWorktree() {
  if (!baselineWorktreePath) return;
  // Use WORKTREE_ROOT for the -C anchor when it is already resolved; fall
  // back to the baseline path itself (which is a valid git repo checkout) so
  // the worktree remove still works even if WORKTREE_ROOT is "unknown".
  const gitAnchor = (WORKTREE_ROOT && WORKTREE_ROOT !== "unknown")
    ? WORKTREE_ROOT
    : baselineWorktreePath;
  try {
    await agent(
      `Remove the temporary baseline worktree if it still exists:\n` +
      `Run: git -C "${gitAnchor}" worktree remove "${baselineWorktreePath}" --force 2>/dev/null || true\n` +
      `Run: rm -rf "${baselineWorktreePath}" 2>/dev/null || true\n` +
      `Return: { "removed": true }`,
      { agentType: "status-checker", label: "cleanup-baseline-worktree" }
    );
  } catch (_err) {
    // Swallow — cleanup is best-effort.
  }
  baselineWorktreePath = null;
}

// -------------------------------------------------------------------------
// Pre-flight 2 — gh account verification (EMU-aware, config-driven)
//
// Reads `gh_target_account` and `gh_repo` from the worktree's settings.json
// (or config/settings.json). If the key is absent the pre-flight is a no-op
// so installs with no EMU constraint are unaffected (AC-4).
// -------------------------------------------------------------------------

phase('Pre-flight 2')

const ghConfigResult = await agent(
  "Read the gh account config from the worktree settings file.\n" +
  `Run: cat "${WORKTREE_ROOT}/settings.json" 2>/dev/null || cat "${WORKTREE_ROOT}/config/settings.json" 2>/dev/null || echo 'null'\n` +
  "Parse the JSON output (if any). Look for a top-level key 'gh_target_account' and 'gh_repo'.\n" +
  "Return ONLY a JSON object: { \"gh_target_account\": \"<value or null>\", \"gh_repo\": \"<owner/repo or null>\" }\n" +
  "If the file does not exist or the keys are absent, return: { \"gh_target_account\": null, \"gh_repo\": null }",
  { agentType: "status-checker", label: "gh-config", phase: "Pre-flight 2" }
)

let ghConfig;
{
  try {
    ghConfig = parseAgentJson(ghConfigResult, { stage: "gh-config", agent: "status-checker" }) || { gh_target_account: null, gh_repo: null };
  } catch (_parseErr) {
    log("[finalize-feature] gh config parse malformed — proceeding with no account constraint");
    ghConfig = { gh_target_account: null, gh_repo: null };
  }
}

const GH_TARGET_ACCOUNT = (ghConfig.gh_target_account || "").trim() || null;
const GH_REPO = (ghConfig.gh_repo || "").trim() || null;

if (GH_TARGET_ACCOUNT) {
  // Probe current active account.
  const ghStatusResult = await agent(
    "Run: gh auth status 2>&1\n" +
    "Parse the output to find which account is currently logged in and active.\n" +
    "The active account appears on the line containing 'Logged in to' or '✓ Logged in to'.\n" +
    "The active account username follows 'as ' (e.g. 'Logged in to github.com as urlmonitor').\n" +
    "Return ONLY a JSON object: { \"active_account\": \"<username or null>\" }",
    { agentType: "status-checker", label: "gh-auth-status", phase: "Pre-flight 2" }
  )

  let ghStatus;
  {
    try {
      ghStatus = parseAgentJson(ghStatusResult, { stage: "gh-auth-status", agent: "status-checker" }) || { active_account: null };
    } catch (_parseErr) {
      log("[finalize-feature] gh auth status parse malformed — assuming active_account is null");
      ghStatus = { active_account: null };
    }
  }

  const activeAccount = (ghStatus.active_account || "").trim() || null;

  if (activeAccount !== GH_TARGET_ACCOUNT) {
    // Switch to the configured account.
    const ghSwitchResult = await agent(
      `Run: gh auth switch --user "${GH_TARGET_ACCOUNT}" 2>&1\n` +
      "Capture exit code and output.\n" +
      "Then re-verify: run `gh auth status 2>&1` and extract the active account (see prior step).\n" +
      "Return ONLY a JSON object: { \"switch_exit_code\": <integer>, \"verified_account\": \"<username or null>\" }",
      { agentType: "status-checker", label: "gh-auth-switch", phase: "Pre-flight 2" }
    )

    let ghSwitch;
    {
      try {
        ghSwitch = parseAgentJson(ghSwitchResult, { stage: "gh-auth-switch", agent: "status-checker" }) || { switch_exit_code: 1, verified_account: null };
      } catch (_parseErr) {
        log("[finalize-feature] gh switch parse malformed — assuming switch failed");
        ghSwitch = { switch_exit_code: 1, verified_account: null };
      }
    }

    const verifiedAccount = (ghSwitch.verified_account || "").trim() || null;
    const switchFailed =
      ghSwitch.switch_exit_code !== 0 || verifiedAccount !== GH_TARGET_ACCOUNT;

    if (switchFailed) {
      return {
        status: "error",
        message:
          `gh account pre-flight failed: could not activate '${GH_TARGET_ACCOUNT}'. ` +
          `Run: gh auth login --hostname github.com --user ${GH_TARGET_ACCOUNT}`,
        action_required: "gh_login_required",
      };
    }
  }
  // Active account is now confirmed to be GH_TARGET_ACCOUNT — proceed.
}

// -------------------------------------------------------------------------
// Step 0 — Capture pre-merge test baseline on current main HEAD
//
// Creates a temporary worktree at origin/main, runs test-runner against it,
// and stores the list of failing test IDs as the baseline. This baseline is
// passed to the triage agent in step 3 so regressions can be distinguished
// from pre-existing failures.
//
// Graceful degradation: if the worktree creation or test run fails for any
// reason, log a warning and set baselineFailures = null. The workflow DOES
// NOT halt — triage will classify all failures conservatively as regressions.
//
// Resumability: before creating the temp worktree, the agent probes for any
// stale /tmp/leafcutter-main-baseline-* directory from a prior interrupted run
// and removes it. This prevents git worktree add from failing because the
// target path already exists.
// -------------------------------------------------------------------------

phase('Step 0')

narrate("Step 0 of 9", 'Capturing pre-merge test baseline on current main HEAD...')

// Set the cleanup guard path so cleanupBaselineWorktree() can remove it on
// any early exit after this point. Step 0 clears it on success (step D).
// baselineTmpPath uses args.baseline_ts (replaces Date.now(), banned in E2).
baselineWorktreePath = baselineTmpPath;

const baselineResult = await agent(
  "Capture a pre-merge test baseline on the current main HEAD.\n" +
  `Use git -C "${WORKTREE_ROOT}" for all git commands to avoid CWD ambiguity.\n` +
  "\n" +
  "Step A0 — Reclaim any stale baseline worktrees from prior interrupted runs:\n" +
  "  Run: ls /tmp/leafcutter-main-baseline-* 2>/dev/null || true\n" +
  "  For each path returned (if any):\n" +
  `    Run: git -C "${WORKTREE_ROOT}" worktree remove \"<path>\" --force 2>/dev/null || true\n` +
  "    Run: rm -rf \"<path>\" 2>/dev/null || true\n" +
  "  Log each removed path as: 'Reclaimed stale baseline worktree: <path>'\n" +
  "  If no paths found: log 'No stale baseline worktrees found.'\n" +
  "\n" +
  "Step A — Create a temporary detached worktree at origin/main:\n" +
  `  Run: git -C "${WORKTREE_ROOT}" worktree add --detach "${baselineTmpPath}" origin/main\n` +
  "  Capture the exit code.\n" +
  "  If exit code is non-zero:\n" +
  "    Log: 'Baseline worktree creation failed — triage will treat all failures as regressions.'\n" +
  "    Return: { \"status\": \"worktree_failed\", \"baseline_sha\": null,\n" +
  "              \"baseline_failures\": null, \"baseline_run_at\": null }\n" +
  "\n" +
  "Step B — Capture the SHA of main HEAD inside the temp worktree:\n" +
  `  Run: git -C "${baselineTmpPath}" rev-parse HEAD\n` +
  "  Store as <baseline_sha>.\n" +
  "\n" +
  "Step C — Deploy shims then run the test suite inside the temp worktree (FIN-100a-4):\n" +
  `  Run: python3 "${baselineTmpPath}/scripts/build.py" --target-dir "${baselineTmpPath}"\n` +
  "  (Deploys commit_guardian, feedback scripts, and .pre-commit-config.yaml — same build state as production.)\n" +
  "  If build.py exits non-zero: log a warning but continue (shim deploy failure is non-fatal for baseline).\n" +
  `  Then run inside "${baselineTmpPath}": pytest --tb=no -q 2>&1\n` +
  "  Collect each line that matches the pattern '<file>::<test_name> FAILED'.\n" +
  "  Build a list of failing test IDs (strings like 'test_foo.py::test_bar').\n" +
  "  Note: a zero-length list means the baseline is clean (all tests pass).\n" +
  "\n" +
  "Step D — Remove the temp worktree:\n" +
  `  Run: git -C "${WORKTREE_ROOT}" worktree remove "${baselineTmpPath}" --force\n` +
  `  Run: rm -rf "${baselineTmpPath}" 2>/dev/null || true\n` +
  "\n" +
  "Step E — Return the baseline result:\n" +
  "  If the test run completed (even with failures): return:\n" +
  "    { \"status\": \"ok\",\n" +
  "      \"baseline_sha\": \"<sha>\",\n" +
  "      \"baseline_failures\": [<list of failing test IDs or empty>],\n" +
  "      \"baseline_run_at\": \"<ISO 8601 timestamp>\" }\n" +
  "  If the test run itself failed to execute (pytest not found, import error, etc.):\n" +
  "    Log: 'Baseline run failed — triage will treat all failures as regressions.'\n" +
  "    Return: { \"status\": \"run_failed\", \"baseline_sha\": \"<sha>\",\n" +
  "              \"baseline_failures\": null, \"baseline_run_at\": \"<ISO 8601 timestamp>\" }",
  // AC FIN-100h: NOT status-checker. This step provisions a git worktree, runs
  // build.py and runs pytest — none of which is in that agent's contract, and
  // it refuses the dispatch outright ("this task should be routed to whichever
  // agent owns pre-merge CI baseline capture").
  { agentType: "general-purpose", label: "step-0-baseline", phase: "Step 0" }
)

let baselineInfo;
{
  try {
    baselineInfo = parseAgentJson(baselineResult, { stage: "step-0-baseline", agent: "status-checker" }) || { status: "parse_failed", baseline_sha: null, baseline_failures: null, baseline_run_at: null };
  } catch (_parseErr) {
    // AC-4: Malformed reply is not the same as "baseline failed" —
    // degrade gracefully (same as run_failed path) without spuriously halting.
    log("[finalize-feature] step 0 baseline parse malformed — treating as run_failed (triage will use conservative classification)");
    baselineInfo = { status: "parse_failed", baseline_sha: null, baseline_failures: null, baseline_run_at: null };
  }
}

const baselineStatus = (baselineInfo.status || "unknown").toLowerCase();

// AC FIN-100h: a REFUSAL is not a run failure. run_failed / parse_failed mean
// the baseline was attempted and produced nothing usable, which the degrade
// path below handles conservatively. A refusal means the step never ran, so
// there is no evidence either way — and the baseline is what the whole
// regression comparison is measured against. Halt instead of degrading.
if (isRefusalStatus(baselineStatus)) {
  await cleanupBaselineWorktree();
  outcome(`Step 0 of ${STEP_COUNT}`, `halted: baseline agent refused the dispatch (${baselineStatus})`);
  return {
    status: "halted",
    halted_at_step: 0,
    reason: "step_refused",
    message:
      `Step 0 (pre-merge test baseline) reported status '${baselineStatus}' — the agent ` +
      "DECLINED the dispatch, so no baseline was captured and no test run happened. " +
      "Without a baseline the post-merge regression check has nothing to compare against, " +
      "so continuing would either halt on every pre-existing failure or merge unchecked. " +
      "Re-dispatch step 0 to an agent whose contract covers git worktree provisioning, " +
      "build.py and pytest.",
    branch: BRANCH,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
    step_outcomes: stepOutcomes,
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
  };
}

if (baselineStatus === "ok") {
  baselineFailures = Array.isArray(baselineInfo.baseline_failures)
    ? baselineInfo.baseline_failures
    : [];
  baselineSha = baselineInfo.baseline_sha || null;
  baselineRunAt = baselineInfo.baseline_run_at || null;
  // Step D ran successfully — temp worktree already removed by the agent.
  baselineWorktreePath = null;
  completedSteps.push(0);
} else {
  // worktree_failed | run_failed | parse_failed | unknown — degrade gracefully.
  // baselineFailures stays null — triage will classify all failures as regressions.
  baselineSha = baselineInfo.baseline_sha || null;
  baselineRunAt = baselineInfo.baseline_run_at || null;
  // The agent may have left the temp worktree behind if it failed part-way;
  // keep baselineWorktreePath set so cleanup fires on any subsequent halt path.
  skippedSteps.push({
    step: 0,
    reason:
      `Baseline capture failed (${baselineStatus}) — ` +
      "triage will treat all post-merge failures as regressions",
  });
}

outcome('Step 0 of 9', baselineFailures !== null
  ? `Baseline captured: ${baselineFailures.length} pre-existing failure(s) at SHA ${baselineSha}`
  : `Baseline capture degraded (${baselineStatus}) — triage will use conservative classification`);

// -------------------------------------------------------------------------
// Step 1 — Open PR if missing (non-destructive, no confirmation gate)
// -------------------------------------------------------------------------

phase('Step 1')

narrate("Step 1 of 9", 'Checking for an open pull request; opening one if missing...')

const prProbeResult = await agent(
  `Run: gh pr list --head "${BRANCH}" --json number,url --jq '.[0]'\n` +
  "Return ONLY a JSON object:\n" +
  "- If a PR is found: { \"found\": true, \"number\": <N>, \"url\": \"<url>\" }\n" +
  "- If no PR exists: { \"found\": false }",
  { agentType: "status-checker", label: "step-1-pr-probe", phase: "Step 1" }
)

let prProbe;
{
  try {
    prProbe = parseAgentJson(prProbeResult, { stage: "step-1-pr-probe", agent: "status-checker" }) || { found: false };
  } catch (_parseErr) {
    // AC-4: Malformed PR probe defaults to "not found" — safer to open a duplicate
    // PR (which will be rejected by GH) than to silently skip creating one.
    log("[finalize-feature] step 1 PR probe parse malformed — assuming no PR exists");
    prProbe = { found: false };
  }
}

if (prProbe.found) {
  prNumber = prProbe.number;
  prUrl = prProbe.url;
  log("Step 1 of 9: [skipped] PR #" + prNumber + " is already open");
  outcome(`Step 1 of ${STEP_COUNT}`, 'skipped: PR #' + prNumber + ' already open');
  skippedSteps.push({ step: 1, reason: `PR already open (#${prNumber}) — skipping step 1` });
} else {
  // Dispatch pull-request agent to open the PR.
  // AC-3 EMU REST fallback: if `gh pr create` fails with the EMU error string
  // ("createPullRequest" or "Enterprise Managed User"), fall back to the REST API:
  //   gh api -X POST repos/<org>/<repo>/pulls -f title="..." -f head="..." -f base="main" -f body="..."
  // GH_REPO (from config) is used for the REST path; omit fallback if GH_REPO is absent.
  const emuFallbackNote = GH_REPO
    ? `EMU REST fallback: if gh pr create fails with "createPullRequest" or "Enterprise Managed User" error, ` +
      `use: gh api -X POST repos/${GH_REPO}/pulls -f title="<title>" -f head="${BRANCH}" -f base="main" -f body="<body>". `
    : "";
  const openPrResult = await agent(
    "Open a pull request for the current feature branch. " +
    "First try: gh pr create --base main --head \"" + BRANCH + "\" (standard path). " +
    emuFallbackNote +
    "Return ONLY a JSON object: { \"number\": <N>, \"url\": \"<url>\" }",
    { agentType: "pull-request", label: "step-1-open-pr", phase: "Step 1" }
  )

  let openPr;
  {
    try {
      openPr = parseAgentJson(openPrResult, { stage: "step-1-open-pr", agent: "pull-request" }) || {};
    } catch (_parseErr) {
      log("[finalize-feature] step 1 PR open parse malformed — pr_number and url will be null");
      openPr = {};
    }
  }

  prNumber = openPr.number || openPr.pr_number || null;
  prUrl = openPr.url || openPr.pr_url || null;
  completedSteps.push(1);
  outcome('Step 1 of 9', prNumber !== null
    ? `PR open: #${prNumber} at ${prUrl || 'url unknown'}`
    : 'Pull request status could not be determined');
}

// -------------------------------------------------------------------------
// Step 2 — Merge origin/main into the feature worktree (no commit)
//
// Inserts the merged state into the worktree so that tests in step 3 run
// against the post-merge tree. Uses --no-commit --no-ff so no merge commit
// is written to the feature branch. On conflict, git merge --abort cleans up
// and the workflow halts with category merge_conflict.
//
// Running this BEFORE the PR merge gate (step 4) ensures the test safety
// gate (step 3) can catch regressions before the feature lands on main.
//
// Resumability: probe git merge-base --is-ancestor to detect already-merged.
// -------------------------------------------------------------------------

phase('Step 2')

narrate("Step 2 of 9", 'Merging origin/main into the feature worktree before running tests...')

const mergeMainResult = await agent(
  "Run these commands inside the feature worktree to merge origin/main before tests.\n" +
  `All git commands must use the explicit worktree root: git -C "${WORKTREE_ROOT}"\n` +
  "\n" +
  "1. Check if the branch is already up-to-date with origin/main:\n" +
  `   Run: git -C "${WORKTREE_ROOT}" merge-base --is-ancestor origin/main HEAD\n` +
  "   Exit code 0 means HEAD already contains all commits from origin/main.\n" +
  "   If exit code 0: log 'Already up-to-date with origin/main.' and return\n" +
  "   { \"status\": \"already_up_to_date\", \"merge_strategy\": \"already_up_to_date\" }\n" +
  "\n" +
  "2. If not up-to-date, fetch origin/main to ensure it is current:\n" +
  `   Run: git -C "${WORKTREE_ROOT}" fetch origin main\n` +
  "\n" +
  "3. Attempt the merge (no commit, no fast-forward):\n" +
  `   Run: git -C "${WORKTREE_ROOT}" merge origin/main --no-commit --no-ff\n` +
  "   Capture the exit code.\n" +
  "\n" +
  "4. If exit code is 0 (clean merge):\n" +
  "   Log: 'Merge clean — worktree reflects post-merge state.'\n" +
  "   Return: { \"status\": \"merged\", \"merge_strategy\": \"merged_main\" }\n" +
  "\n" +
  "5. If exit code is non-zero (conflict detected):\n" +
  `   Run: git -C "${WORKTREE_ROOT}" merge --abort\n` +
  "   Return: { \"status\": \"conflict\", \"merge_strategy\": null }",
  // AC FIN-100h: NOT status-checker. This step runs git fetch / git merge /
  // git merge --abort against the feature worktree; that agent's contract
  // restricts it to ticket frontmatter and it refuses repo mutation.
  { agentType: "general-purpose", label: "step-2-merge-main", phase: "Step 2" }
)

let mergeMainInfo;
{
  try {
    mergeMainInfo = parseAgentJson(mergeMainResult, { stage: "step-2-merge-main", agent: "status-checker" }) || { status: "already_up_to_date", merge_strategy: "already_up_to_date" };
  } catch (_parseErr) {
    // AC-4: A malformed reply is not the same as "conflict detected".
    // Default to "already_up_to_date" (non-halting, safe) and log a warning.
    // If the merge actually had a problem, it will become apparent at the
    // test-runner phase (step 3) rather than spuriously halting here.
    log("[finalize-feature] step 2 merge-main parse malformed — treating as already_up_to_date (non-halting safe default)");
    mergeMainInfo = { status: "already_up_to_date", merge_strategy: "already_up_to_date" };
  }
}

const mergeStatus = (mergeMainInfo.status || "already_up_to_date").toLowerCase();

if (mergeStatus === "conflict") {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: 2,
    reason: "merge_conflict",
    message:
      "Feature branch has conflicts with main. Resolve conflicts and re-run.",
    branch: BRANCH,
    pr_number: prNumber,
    pr_url: prUrl,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
    step_outcomes: stepOutcomes,
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
  };
}

// AC FIN-100h: a refused or unrecognised status must NEVER reach the success
// path below. Integrating origin/main is load-bearing for the merge decision —
// if it did not happen, everything downstream (tests, PR merge) is judging an
// unintegrated branch. Halt rather than guess.
if (isRefusalStatus(mergeStatus) || !["merged", "already_up_to_date"].includes(mergeStatus)) {
  await cleanupBaselineWorktree();
  const refused = isRefusalStatus(mergeStatus);
  outcome(`Step 2 of ${STEP_COUNT}`, `halted: merge step ${refused ? "refused" : "returned unrecognised status"} (${mergeStatus})`);
  return {
    status: "halted",
    halted_at_step: 2,
    reason: refused ? "step_refused" : "unrecognised_step_status",
    message:
      `Step 2 (merge origin/main) reported status '${mergeStatus}' — ` +
      (refused
        ? "the agent DECLINED the dispatch, so no merge was performed. "
        : "this status is not part of the step's contract, so whether a merge happened is unknown. ") +
      "Refusing to treat this as a successful merge. Re-dispatch step 2 to an agent whose " +
      "contract covers git merge operations, or perform the merge by hand and re-run.",
    branch: BRANCH,
    pr_number: prNumber,
    pr_url: prUrl,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
    step_outcomes: stepOutcomes,
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
  };
}

if (mergeStatus === "already_up_to_date") {
  log("Step 2 of 9: [skipped] origin/main already integrated into branch — no merge step needed");
  outcome(`Step 2 of ${STEP_COUNT}`, 'skipped: already up-to-date with origin/main');
  skippedSteps.push({
    step: 2,
    reason: "Already up-to-date with origin/main",
  });
} else if (mergeStatus === "merged") {
  // Success is now reached ONLY on an explicitly-matched status.
  completedSteps.push(2);
  outcome('Step 2 of 9', 'Merged origin/main cleanly into feature worktree (--no-commit --no-ff)');
}

const mergeStrategy = mergeMainInfo.merge_strategy || "already_up_to_date";

// -------------------------------------------------------------------------
// Step 3 — Run post-merge tests + triage (always runs)
//
// The baseline captured in step 0 is forwarded here so the triage agent
// can compute:
//   regressions = post_merge_failures − baseline_failures
// If baseline_failures is null, all failures are treated as regressions
// (conservative classification).
//
// If tests pass: skip triage sub-steps and continue to step 4 (PR merge).
// If tests fail: triage classifies failures; HALT here if any are regressions.
// Only when blocks_finalization === false does the workflow proceed to step 4.
// -------------------------------------------------------------------------

phase('Step 3')

narrate("Step 3 of 9", 'Running post-merge tests and triaging any failures...')

// FIN-100a-4: deploy shims before running the suite, same as Step 0 baseline.
// Without this, ~13 deploy-dependent tests fail RED in Step 3 while passing
// in Step 0, causing the triage set-difference to misclassify them as regressions.
testResult = await agent(
  `First run: python3 "${WORKTREE_ROOT}/scripts/build.py" --target-dir "${WORKTREE_ROOT}" ` +
  "to deploy shims (same build.py step as the Step 0 baseline — ensures identical build state " +
  "for commit_guardian, feedback scripts, and .pre-commit-config.yaml). " +
  "If build.py exits non-zero: log a warning but continue. " +
  "Then run the full test suite on the post-merge worktree. " +
  "Return a JSON object: { \"passed\": true|false, \"output\": \"<verbatim test output>\", " +
  "\"failing_tests\": [\"<file>::<test_name>\", ...] }\n" +
  `Baseline context: baseline_sha=${JSON.stringify(baselineSha)}, ` +
  `baseline_failures=${JSON.stringify(baselineFailures)}, ` +
  `baseline_run_at=${JSON.stringify(baselineRunAt)}`,
  { agentType: "test-runner", label: "step-3-test-run", phase: "Step 3" }
)

let testPassed;
let postMergeFailures;
{
  try {
    const parsed = parseAgentJson(testResult, { stage: "step-3-test-run", agent: "test-runner" }) || {};
    testPassed = parsed.passed === true;
    testResult = parsed;
    postMergeFailures = Array.isArray(parsed.failing_tests) ? parsed.failing_tests : [];
  } catch (_parseErr) {
    // AC-4: A malformed test reply is ambiguous — we cannot determine pass/fail.
    // Default to testPassed=false (conservative) but log clearly that this is a
    // parse failure, not an agent-reported failure. The triage step will then
    // attempt to classify failures, and if the triage reply is also malformed,
    // that triage step's own safe default applies.
    log("[finalize-feature] step 3 test-runner parse malformed — treating as failed (conservative; triage will classify)");
    testPassed = false;
    postMergeFailures = [];
    testResult = { passed: false, output: "(parse malformed)", failing_tests: [] };
  }
}

// -------------------------------------------------------------------------
// Step 3 (deploy-parity self-check — FIN-100g-4 / FIN-100g-4-i)
//
// Before triaging any failures, verify the post-merge worktree's DEPLOYED
// layer is consistent: every runtime artifact the tests import must be present
// at its expected deployed location under WORKTREE_ROOT, INCLUDING gitignored,
// non-git-tracked deployed copies (e.g. scripts/commit_guardian/*.py deployed
// by install_shims). A missing deployed artifact is an environment/build-state
// condition, NEVER a test regression. On a miss, re-run the deterministic
// deploy against the worktree root (build parity with FIN-100a-4 / FIN-100c-4)
// and re-verify + re-run the previously-failing tests, so build-state failures
// clear before triage. Triage (FIN-100c) runs ONLY once the deployed layer is
// verified consistent. The exclusion is data-driven (tests that pass after a
// verified re-deploy), never keyed on a hard-coded test/helper name — a genuine
// failure that persists after a verified-consistent deploy still reaches triage
// and can HALT.
// -------------------------------------------------------------------------
// Only meaningful when there are CONCRETE post-merge failures to reclassify.
// A malformed Step-3 test-runner reply is treated conservatively above as
// testPassed=false with an EMPTY postMergeFailures; the deploy-parity self-check
// must NOT run (and must never flip testPassed→true) in that case — there is
// nothing to attribute to deploy skew, and rescuing an ambiguous/empty result to
// "passed" would skip triage and merge on a malformed test run (H-1).
if (!testPassed && postMergeFailures.length > 0) {
  const deployParityResult = await agent(
    `Verify the deployed layer of the post-merge worktree "${WORKTREE_ROOT}" is consistent BEFORE triage (FIN-100g-4).\n` +
    "1. For every runtime artifact the failing tests import, check it is present at its\n" +
    "   expected DEPLOYED location under the worktree root — INCLUDING gitignored,\n" +
    "   non-git-tracked deployed copies (e.g. scripts/commit_guardian/*.py, scripts/feedback/*.py\n" +
    "   deployed by install_shims), not just git-tracked files.\n" +
    "2. If ANY expected deployed artifact is missing, re-run the deterministic deploy:\n" +
    `     python3 "${WORKTREE_ROOT}/scripts/build.py" --target-dir "${WORKTREE_ROOT}"\n` +
    "   (same build.py deploy as the Step 0 baseline and the Step 3 pre-test build), then\n" +
    "   re-verify and re-run the previously-failing tests so build-state failures clear.\n" +
    "3. A test that FAILED before the re-deploy but PASSES after it is an environment/\n" +
    "   build-state condition — report it in build_state_only_failures. This classification\n" +
    "   is data-driven (passes-after-verified-redeploy), NEVER keyed on a hard-coded name.\n" +
    "   A build/deploy inconsistency is NEVER a test regression.\n" +
    "Return ONLY: { \"deploy_consistent\": true|false, \"redeployed\": true|false, " +
    "\"build_state_only_failures\": [\"<file>::<test>\", ...], \"still_failing\": [\"<file>::<test>\", ...] }",
    { agentType: "test-runner", label: "step-3-deploy-parity", phase: "Step 3" }
  )

  let buildStateOnly = [];
  let stillFailing = null;
  {
    try {
      const parsedDp = parseAgentJson(deployParityResult, { stage: "step-3-deploy-parity", agent: "test-runner" }) || {};
      buildStateOnly = Array.isArray(parsedDp.build_state_only_failures)
        ? parsedDp.build_state_only_failures
        : [];
      // still_failing is the agent's post-redeploy remaining-failure set; null
      // when the agent did not report it (older/ambiguous replies).
      stillFailing = Array.isArray(parsedDp.still_failing) ? parsedDp.still_failing : null;
    } catch (_parseErr) {
      log("[finalize-feature] step 3 deploy-parity parse malformed — proceeding with the original post-merge failures (conservative).");
    }
  }

  // Contradiction guard (M-2): never exclude a test the agent itself still reports
  // failing after the re-deploy. Only tests classified build-state AND absent from
  // still_failing are treated as deploy-skew. This bounds the trust placed in the
  // agent's classification — a test the agent both "cleared" and lists as still
  // failing is kept and sent to triage, the sole authority that can HALT.
  const stillFailingSet = new Set(stillFailing || []);
  const excludable = buildStateOnly.filter((t) => !stillFailingSet.has(t));

  // Build-state (deploy-skew) failures are environment conditions, never regressions:
  // drop them from the set handed to triage so they cannot be classified as regressions.
  if (excludable.length > 0) {
    log(
      `[finalize-feature] step 3: ${excludable.length} failure(s) cleared by a ` +
      "deterministic re-deploy (FIN-100g-4) — build-state, not regressions; excluded from triage."
    );
    const buildStateSet = new Set(excludable);
    postMergeFailures = postMergeFailures.filter((t) => !buildStateSet.has(t));
    // Flip to passed ONLY when the run started with genuine failures (guaranteed
    // by the postMergeFailures.length>0 guard on this block) and EVERY one was
    // verified build-state deploy-skew. Any genuine failure remaining stays in
    // postMergeFailures → triage → can HALT (FIN-100g-4-i).
    if (postMergeFailures.length === 0) {
      testPassed = true;
    }
  }
}

if (testPassed) {
  // Zero failures: skip triage sub-steps entirely, proceed to step 4 (PR merge).
  completedSteps.push(3);
  // triageReport remains null — forwarded to step 6 as-is.
} else {
  // -----------------------------------------------------------------------
  // Step 3 (triage sub-step) — Dispatch test-failure-triage when failures exist
  //
  // Passes post_merge_failures, baseline_failures, baseline_sha,
  // feature_branch, and changed_files (derived here via git diff) so the
  // triage agent can classify each failure as regression or pre-existing.
  // -----------------------------------------------------------------------

  // Derive changed_files: files touched by the feature branch relative to
  // origin/main. Captured at this point (after the --no-commit merge) so
  // the diff reflects the full feature delta including the merged state.
  const changedFilesResult = await agent(
    `Run: git -C "${WORKTREE_ROOT}" diff --name-only origin/main HEAD\n` +
    "Return ONLY a JSON object: { \"changed_files\": [\"<file1>\", \"<file2>\", ...] }\n" +
    "If the command fails or returns no output, return: { \"changed_files\": [] }",
    { agentType: "status-checker", label: "step-3-changed-files", phase: "Step 3" }
  )

  let changedFiles = [];
  {
    try {
      const parsedCf = parseAgentJson(changedFilesResult, { stage: "step-3-changed-files", agent: "status-checker" }) || {};
      changedFiles = Array.isArray(parsedCf.changed_files) ? parsedCf.changed_files : [];
    } catch (_parseErr) {
      log("[finalize-feature] step 3 changed_files parse malformed — triage will use empty changed_files list");
      changedFiles = [];
    }
  }

  // -----------------------------------------------------------------------
  // Step 3 (null-baseline targeted-rerun recovery — FIN-100c-4/5/6/9)
  //
  // When baselineFailures is null (Step 0 baseline unavailable) and there
  // are post-merge failures, attempt a targeted rerun of ONLY the failing
  // test IDs against a fresh origin/main checkout. This recovers a baseline
  // without running the full suite (bounded runtime, FIN-100c-5).
  //
  // Success path: builds recoveredBaselineFailures, sets baselineFailures to
  //   the recovered list so triage receives a non-null baseline (FIN-100c-6).
  //   Tests in the recovered baseline → pre_existing; absent → regression.
  // Failure path: logs "targeted rerun unavailable" and falls back to the
  //   conservative null-baseline path (all failures = regressions, FIN-100c-9).
  // -----------------------------------------------------------------------
  let recoveredBaselineFailures = null;

  if (baselineFailures === null && postMergeFailures.length > 0) {
    log(
      `[finalize-feature] step 3: baseline unavailable — attempting targeted rerun of ` +
      `${postMergeFailures.length} failing test ID(s) against origin/main HEAD (FIN-100c-4).`
    );

    const recoveryWorktreePath = `${baselineTmpPath}-recovery`;
    // Register with the workflow-level cleanup guard so cleanupBaselineWorktree()
    // fires on any early exit (crash/non-compliant agent/malformed output) that
    // occurs while the recovery worktree exists (mirrors the Step 0 pattern at
    // line 413 where baselineWorktreePath = baselineTmpPath is set before dispatch).
    baselineWorktreePath = recoveryWorktreePath;

    const recoveryResult = await agent(
      "Perform a targeted rerun of specific failing test IDs against a fresh origin/main checkout.\n" +
      "Rerun ONLY the specified failing test IDs — NOT the full suite (bounded runtime, FIN-100c-5).\n" +
      "\n" +
      "Step A — Create a temporary detached worktree at origin/main HEAD:\n" +
      `  Run: git -C "${WORKTREE_ROOT}" worktree add --detach "${recoveryWorktreePath}" origin/main\n` +
      "  Capture exit code.\n" +
      "  If non-zero:\n" +
      "    Log: 'targeted rerun unavailable — worktree checkout failed.'\n" +
      "    Return: { \"status\": \"checkout_failed\", \"recovered_failures\": null }\n" +
      "\n" +
      "Step B — Deploy shims before rerun (build parity with Step 0 and Step 3, FIN-100c-4):\n" +
      `  Run: python3 "${recoveryWorktreePath}/scripts/build.py" --target-dir "${recoveryWorktreePath}"\n` +
      "  Capture exit code.\n" +
      "  If non-zero:\n" +
      "    Log: 'targeted rerun unavailable — build/deploy step failed.'\n" +
      `    Run: git -C "${WORKTREE_ROOT}" worktree remove "${recoveryWorktreePath}" --force 2>/dev/null || true\n` +
      `    Run: rm -rf "${recoveryWorktreePath}" 2>/dev/null || true\n` +
      "    Return: { \"status\": \"build_failed\", \"recovered_failures\": null }\n" +
      "\n" +
      "Step C — Targeted rerun of ONLY the failing test IDs (not full suite):\n" +
      `  Run in "${recoveryWorktreePath}": pytest --tb=no -q <each_failing_test_id_as_separate_arg>\n` +
      "  Where the failing test IDs are listed in Context below.\n" +
      "  Collect each output line matching '<file>::<test_name> FAILED'.\n" +
      "  Build recovered_failures = list of test IDs that ALSO fail on origin/main HEAD.\n" +
      "\n" +
      "Step D — Remove the temp recovery worktree:\n" +
      `  Run: git -C "${WORKTREE_ROOT}" worktree remove "${recoveryWorktreePath}" --force 2>/dev/null || true\n` +
      `  Run: rm -rf "${recoveryWorktreePath}" 2>/dev/null || true\n` +
      "\n" +
      "Step E — Return result:\n" +
      "  Return: { \"status\": \"ok\", \"recovered_failures\": [<list of test IDs that failed on origin/main>] }\n" +
      "  An empty list means no post-merge failure also fails on main (all are regressions).\n" +
      `Context: failing_test_ids=${JSON.stringify(postMergeFailures)}`,
      { agentType: "status-checker", label: "step-3-targeted-rerun", phase: "Step 3" }
    )

    let recoveryInfo;
    {
      try {
        recoveryInfo = parseAgentJson(recoveryResult, { stage: "step-3-targeted-rerun", agent: "status-checker" }) || { status: "parse_failed", recovered_failures: null };
      } catch (_parseErr) {
        log("[finalize-feature] step 3 targeted-rerun parse malformed — targeted rerun unavailable, using conservative fallback.");
        recoveryInfo = { status: "parse_failed", recovered_failures: null };
      }
    }

    const recoveryStatus = (recoveryInfo.status || "").toLowerCase();
    if (recoveryStatus === "ok" && Array.isArray(recoveryInfo.recovered_failures)) {
      // Success: forward recovered baseline to triage (FIN-100c-6).
      // recoveredBaselineFailures = intersection of post-merge failures and those
      // that ALSO fail on origin/main HEAD. Tests absent from it → regression.
      recoveredBaselineFailures = recoveryInfo.recovered_failures;
      baselineFailures = recoveredBaselineFailures; // [] means clean baseline, never null
      log(
        `[finalize-feature] step 3 targeted rerun complete: ` +
        `${recoveredBaselineFailures.length} pre-existing failure(s) recovered ` +
        `from ${postMergeFailures.length} post-merge failure(s). ` +
        "Forwarding recovered baseline to triage in place of null (FIN-100c-6)."
      );
    } else {
      // Checkout failed, build failed, or parse error — targeted rerun unavailable (FIN-100c-9).
      // Fall back to conservative null-baseline path: all failures = regressions.
      log(
        `[finalize-feature] step 3 targeted rerun unavailable (${recoveryStatus}) — ` +
        "falling back to conservative null-baseline path. " +
        "All post-merge failures will be classified as regressions.\n" +
        "Failing tests with modified_by_branch status:\n" +
        postMergeFailures.map(id => {
          const testFile = id.split("::")[0];
          const modifiedByBranch = changedFiles.includes(testFile);
          return `  - ${id} [modified_by_branch: ${modifiedByBranch}]`;
        }).join("\n")
      );
      // baselineFailures remains null — triage Step 1 classifies all as regressions.
    }
    // Workflow-level cleanup: remove the recovery worktree unconditionally
    // (belt-and-suspenders; the agent prompt handles cleanup in steps B/D, but
    // this ensures the path is removed even on malformed/crash/non-compliant exit).
    // cleanupBaselineWorktree() also resets baselineWorktreePath = null so later
    // halt paths do not double-target the recovery path.
    await cleanupBaselineWorktree();
  }

  const triageRaw = await agent(
    "Classify each failing test into one of four categories: " +
    "'regression' (caused by this branch), 'stale_test' (covers a deprecated/superseded AC), " +
    "'pre_existing' (already failing on main before merge), or 'flaky' (intermittently failing). " +
    "Return a JSON object matching this schema exactly: " +
    "{ \"triage_report\": [ { \"test_id\": \"<fully-qualified test name>\", " +
    "\"test_file\": \"<relative path>\", \"covers_tag\": \"<tag or null>\", " +
    "\"category\": \"regression|stale_test|pre_existing|flaky\", " +
    "\"ac_status\": \"<active|deprecated|superseded_by|not_found|null>\", " +
    "\"rationale\": \"<reason>\", \"action\": \"fix_on_branch|update_test|create_tracking_ticket\", " +
    "\"modified_by_branch\": true|false } ], " +
    "\"blocks_finalization\": true|false }\n" +
    `Context: post_merge_failures=${JSON.stringify(postMergeFailures)}, ` +
    `baseline_failures=${JSON.stringify(baselineFailures)}, ` +
    `baseline_sha=${JSON.stringify(baselineSha)}, ` +
    `feature_branch=${JSON.stringify(BRANCH)}, ` +
    `changed_files=${JSON.stringify(changedFiles)}`,
    { agentType: "test-failure-triage", label: "step-3-triage", phase: "Step 3" }
  )

  {
    try {
      triageReport = parseAgentJson(triageRaw, { stage: "step-3-triage", agent: "test-failure-triage" }) || {
        blocks_finalization: true,
        regressions: postMergeFailures,
        pre_existing: [],
        summary: "Triage report empty — treating all failures as regressions.",
      };
    } catch (_parseErr) {
      // AC-4: A malformed triage reply is genuinely ambiguous — we cannot determine
      // whether failures are regressions or pre-existing. Use conservative
      // blocks_finalization=true, but log clearly that this is a parse failure
      // (not an agent-reported regression), so the operator can distinguish
      // "tests have regressions" from "triage reply was garbled".
      log("[finalize-feature] step 3 triage parse malformed — treating as blocks_finalization=true (conservative; see note in summary)");
      triageReport = {
        blocks_finalization: true,
        regressions: postMergeFailures,
        pre_existing: [],
        summary: "Triage reply was malformed (could not parse JSON) — treating all failures as regressions conservatively. If you believe this is a parse error rather than a real regression, re-run /finalize-feature.",
      };
    }
  }

  // Log the triage report to the user for visibility.
  log("[finalize-feature] step 3 triage report: " + JSON.stringify(triageReport, null, 2));

  // -----------------------------------------------------------------------
  // Step 3 (halt gate) — Halt-or-continue based on triage_report.blocks_finalization
  //
  // If blocks_finalization is true: HARD EARLY RETURN. Step 4 (PR merge) is
  // structurally unreachable from this point — no escape hatch.
  // If false: pass triage_report forward and continue to step 4.
  // -----------------------------------------------------------------------
  if (triageReport.blocks_finalization) {
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: 3,
      reason: "test_regression",
      triage_report: triageReport,
      message:
        "Fix regressions before re-running /finalize-feature. " +
        "The PR has NOT been merged to main.",
      test_output:
        (testResult && testResult.output) ||
        JSON.stringify(testResult),
      branch: BRANCH,
      pr_number: prNumber,
      pr_url: prUrl,
      completed_steps: completedSteps,
      skipped_steps: skippedSteps,
      step_outcomes: stepOutcomes,
      step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
    };
  }
  // blocks_finalization is false: all failures are pre-existing.
  // Store triage_report in workflow state and continue to step 4.
  completedSteps.push(3);
}

outcome('Step 3 of 9', testPassed
  ? `Tests passed: no new failures (${baselineFailures !== null ? baselineFailures.length : 'N/A'} pre-existing on main)`
  : `Tests completed: ${postMergeFailures.length} pre-existing failure(s) — no regressions, proceeding`);

// -------------------------------------------------------------------------
// Step 3.5 — Pre-merge AC closure (runs on the feature branch, before Step 4)
//
// This step MUST run before the PR merge (step 4) so that ticket status and
// source AC work_status are committed on the feature branch. The PR then
// carries that closure commit to origin/main atomically. Writing closure on
// local main is not possible because main is PR-only (branch protection).
// -------------------------------------------------------------------------

phase('Step 3.5')

narrate("Step 3.5 of 9", 'Closing in-scope tickets and source ACs on the feature branch before merge...')

// Probe: check whether a closure commit already exists on the branch.
const closureProbeResult = await agent(
  `Run: git -C "${WORKTREE_ROOT}" log --oneline --grep 'chore(tickets): close tickets and source ACs' -1\n` +
  "If the output is non-empty (a closure commit already exists on this branch):\n" +
  "  Return: { \"already_committed\": true }\n" +
  "Otherwise:\n" +
  "  Return: { \"already_committed\": false }",
  { agentType: "status-checker", label: "step-3.5-closure-probe", phase: "Step 3.5" }
)

let closureAlreadyCommitted = false;
{
  try {
    closureAlreadyCommitted = (parseAgentJson(closureProbeResult, { stage: "step-3.5-closure-probe", agent: "status-checker" }) || {}).already_committed === true;
  } catch (_parseErr) {
    log("[finalize-feature] step 3.5 closure probe parse malformed — assuming not already committed (will re-attempt closure)");
    closureAlreadyCommitted = false;
  }
}

if (closureAlreadyCommitted) {
  log("Step 3.5 of 9: [skipped] Closure commit already present on this branch — skipping pre-merge closure");
  outcome(`Step 3.5 of ${STEP_COUNT}`, 'skipped: pre-merge closure commit already present on branch');
  skippedSteps.push({
    step: "3.5",
    reason: "Pre-merge closure commit already present — skipping step 3.5",
  });
} else {
  // Also check: if the PR is already merged, the pre-merge closure step is moot.
  let prAlreadyMergedAtClosure = false;
  if (prNumber !== null) {
    const prClosureStateResult = await agent(
      `Run: gh pr view ${prNumber} --json state --jq '.state'\n` +
      "Return ONLY a JSON object: { \"state\": \"OPEN\"|\"MERGED\"|\"CLOSED\" }",
      { agentType: "status-checker", label: "step-3.5-pr-state", phase: "Step 3.5" }
    )
    {
      try {
        prAlreadyMergedAtClosure = ((parseAgentJson(prClosureStateResult, { stage: "step-3.5-pr-state", agent: "status-checker" }) || {}).state || "").toUpperCase() === "MERGED";
      } catch (_parseErr) {
        log("[finalize-feature] step 3.5 PR state parse malformed — assuming PR is OPEN");
        prAlreadyMergedAtClosure = false;
      }
    }
  }

  if (prAlreadyMergedAtClosure) {
    log("Step 3.5 of 9: [skipped] PR is already merged — pre-merge closure step omitted");
    outcome(`Step 3.5 of ${STEP_COUNT}`, 'skipped: PR already merged — pre-merge closure step omitted');
    skippedSteps.push({
      step: "3.5",
      reason: "PR already merged — pre-merge closure step skipped (AC-5 idempotency)",
    });
  } else {
    // -----------------------------------------------------------------------
    // Sub-step A: Reset the Step 2 test-merge.
    // -----------------------------------------------------------------------
    const resetMergeResult = await agent(
      "Reset any staged test-merge left by step 2 before editing ticket files.\n" +
      `All git commands use the explicit worktree root: git -C "${WORKTREE_ROOT}"\n` +
      "\n" +
      "1. Check if a merge is in progress:\n" +
      `   Run: git -C "${WORKTREE_ROOT}" rev-parse --verify MERGE_HEAD 2>/dev/null\n` +
      "   Capture the exit code.\n" +
      "\n" +
      "2. If exit code is 0 (MERGE_HEAD exists — merge in progress):\n" +
      `   Run: git -C "${WORKTREE_ROOT}" merge --abort\n` +
      "   Log: 'Step 2 test-merge aborted — clean feature-branch state restored.'\n" +
      "   Return: { \"status\": \"aborted\" }\n" +
      "\n" +
      "3. If exit code is non-zero (no merge in progress):\n" +
      `   Run: git -C "${WORKTREE_ROOT}" reset --hard HEAD\n` +
      "   Log: 'No merge in progress — reset to feature-branch HEAD.'\n" +
      "   Return: { \"status\": \"reset\" }",
      { agentType: "status-checker", label: "step-3.5-reset-merge", phase: "Step 3.5" }
    )

    // Derive the epic scope prefix from the branch name.
    // For EPIC-* branches the closure is restricted to that epic's own ticket folder.
    // For single-ticket branches (no EPIC- prefix) SCOPE_PREFIX is empty — git diff
    // already limits discovery to files the branch changed, so no folder filter is needed.
    const SCOPE_PREFIX = BRANCH.startsWith("EPIC-")
      ? `tickets/00_inbox/epics/${BRANCH}/`
      : "";

    // Sub-step B + C + D + E: find in-scope tickets, close them, close ACs, commit.
    const closureResult = await agent(
      "Close in-scope tickets and their source ACs on the feature branch.\n" +
      "\n" +
      "=== CONTEXT ===\n" +
      `Feature branch: ${BRANCH}\n` +
      `Worktree root: ${WORKTREE_ROOT}\n` +
      `SCOPE_PREFIX: '${SCOPE_PREFIX}'\n` +
      "(SCOPE_PREFIX is non-empty for EPIC-* branches — only paths under it are eligible.)\n" +
      "\n" +
      "=== SUB-STEP B: FIND IN-SCOPE TICKETS ===\n" +
      "CRITICAL: Only close tickets that this branch explicitly changed via git.\n" +
      "DO NOT walk the whole ticket store — that causes cross-epic contamination.\n" +
      "\n" +
      "B1. List ticket files changed by this branch (git-only — no worktree walk):\n" +
      `  Run: git -C ${WORKTREE_ROOT} diff --name-only origin/main HEAD -- 'tickets/**/*.md'\n` +
      `  Run: git -C ${WORKTREE_ROOT} log --oneline origin/main..${BRANCH} --name-only --diff-filter=A -- 'tickets/**/*.md'\n` +
      "  Combine both lists; deduplicate. Exclude Master_Plan.md.\n" +
      `  If SCOPE_PREFIX ('${SCOPE_PREFIX}') is non-empty: discard every path that does NOT start with SCOPE_PREFIX.\n` +
      "  Log: 'SCOPE_PREFIX=<value>; in-scope ticket candidates from git diff: <count>'\n" +
      "\n" +
      "B2. For each remaining file, read its frontmatter `status:` field.\n" +
      "  Collect only files where status != 'done' (skip already-done tickets — idempotency).\n" +
      "  Call this list OPEN_TICKETS.\n" +
      "  If OPEN_TICKETS is empty: log 'No open tickets to close.' and skip to REPORTING.\n" +
      "\n" +
      "=== SUB-STEP C: SET status: done ===\n" +
      "For each ticket in OPEN_TICKETS:\n" +
      "  Read the file content.\n" +
      "  Replace the `status: <value>` line in the YAML frontmatter with `status: done`.\n" +
      "  Write the updated content back to the file.\n" +
      "  Log: 'Set status: done on <ticket_path>'\n" +
      "\n" +
      "=== SUB-STEP D: CLOSE SOURCE ACs ===\n" +
      "For each ticket in OPEN_TICKETS:\n" +
      "  Read the ticket frontmatter and look for a `source_ac:` field.\n" +
      "  If `source_ac` is absent or empty: log 'No source_ac on <ticket_path> — skipping AC closure.' and skip (AC-3 no-op).\n" +
      "  If `source_ac` is present:\n" +
      `    Run: python3 ${WORKTREE_ROOT}/scripts/ac_store/mark_ac_done.py --ticket <ticket_path> --ac-root ${WORKTREE_ROOT}/docs/acceptance-criteria/\n` +
      "    Capture the exit code.\n" +
      "    If exit code is 0: increment acs_closed counter.\n" +
      "    If exit code is non-zero: log 'WARNING: mark_ac_done.py exited <code> for <ticket_path> — skipping AC closure (non-fatal).' and increment acs_skipped counter. DO NOT fail finalize. (AC-4 non-fatal)\n" +
      "\n" +
      "=== SUB-STEP E: COMMIT ON FEATURE BRANCH ===\n" +
      "If OPEN_TICKETS was non-empty (any edits were made):\n" +
      `  Run: git -C ${WORKTREE_ROOT} add tickets/\n` +
      `  Run: git -C ${WORKTREE_ROOT} add docs/acceptance-criteria/ 2>/dev/null || true\n` +
      `  Run: git -C ${WORKTREE_ROOT} diff --cached --name-only\n` +
      "  Capture the list as STAGED_PATHS.\n" +
      "\n" +
      "  SCOPE GUARD — verify every staged path is within the epic scope:\n" +
      "  A path is allowed when ANY of these hold:\n" +
      "    - It starts with 'docs/acceptance-criteria/' (AC closure files).\n" +
      `    - SCOPE_PREFIX ('${SCOPE_PREFIX}') is non-empty AND the path starts with SCOPE_PREFIX.\n` +
      "    - SCOPE_PREFIX is empty AND the path is in the OPEN_TICKETS list.\n" +
      "  Any path that does not satisfy one of these conditions is a SCOPE VIOLATION.\n" +
      "\n" +
      "  If any SCOPE VIOLATION is found:\n" +
      `    Run: git -C ${WORKTREE_ROOT} reset HEAD\n` +
      "    Log: 'ABORT: closure commit aborted — staged paths fall outside epic scope.'\n" +
      "    For each violating path log: 'OUT-OF-SCOPE: <path>'\n" +
      "    Return:\n" +
      "    {\n" +
      '      "tickets_closed": [],\n' +
      '      "acs_closed": 0,\n' +
      '      "acs_skipped": 0,\n' +
      '      "commit_made": false,\n' +
      '      "scope_violation": true,\n' +
      '      "out_of_scope_paths": ["<violating path 1>", ...]\n' +
      "    }\n" +
      "\n" +
      "  If all staged paths pass the scope guard:\n" +
      "    If staged files exist:\n" +
      `      Run: git -C ${WORKTREE_ROOT} commit -m 'chore(tickets): close tickets and source ACs'\n` +
      "      Log: 'Closure commit created on feature branch.'\n" +
      "    Else:\n" +
      "      Log: 'Nothing staged after edits — all tickets were already done.'\n" +
      "\n" +
      "=== REPORTING ===\n" +
      "Return a JSON object:\n" +
      "{\n" +
      '  "tickets_closed": ["<path1>", ...],\n' +
      '  "acs_closed": <integer>,\n' +
      '  "acs_skipped": <integer>,\n' +
      '  "commit_made": true|false,\n' +
      '  "scope_violation": false,\n' +
      '  "out_of_scope_paths": []\n' +
      "}",
      { agentType: "status-checker", label: "step-3.5-closure", phase: "Step 3.5" }
    )

    let closureInfo;
    {
      try {
        closureInfo = parseAgentJson(closureResult, { stage: "step-3.5-closure", agent: "status-checker" }) || { tickets_closed: [], acs_closed: 0, acs_skipped: 0, commit_made: false, scope_violation: false, out_of_scope_paths: [] };
      } catch (_parseErr) {
        log("[finalize-feature] step 3.5 closure parse malformed — assuming zero tickets/ACs closed");
        closureInfo = { tickets_closed: [], acs_closed: 0, acs_skipped: 0, commit_made: false, scope_violation: false, out_of_scope_paths: [] };
      }
    }

    // Surface any scope violation clearly so the operator can investigate.
    // A scope violation means the agent staged paths outside the epic's own folder
    // and the guard correctly aborted the commit (no closure commit was made).
    if (closureInfo.scope_violation) {
      const offendingPaths = Array.isArray(closureInfo.out_of_scope_paths)
        ? closureInfo.out_of_scope_paths
        : [];
      log(
        "[finalize-feature] step 3.5 SCOPE VIOLATION: closure commit aborted — " +
        "staged paths fall outside epic scope (" + (SCOPE_PREFIX || "branch-diff-derived") + ").\n" +
        "Offending paths:\n" +
        offendingPaths.map(p => `  - ${p}`).join("\n")
      );
    }

    // Accumulate counts into workflow-level variables.
    if (Array.isArray(closureInfo.tickets_closed)) {
      ticketsClosedPreMerge = closureInfo.tickets_closed.length;
      // Merge into the broader ticketsClosed list for the final summary.
      ticketsClosed.push(...closureInfo.tickets_closed);
    }
    acsClosed = typeof closureInfo.acs_closed === "number" ? closureInfo.acs_closed : 0;
    acsSkipped = typeof closureInfo.acs_skipped === "number" ? closureInfo.acs_skipped : 0;

    completedSteps.push("3.5");

    log(
      `[finalize-feature] step 3.5 closure: tickets_closed=${ticketsClosedPreMerge} ` +
        `acs_closed=${acsClosed} acs_skipped=${acsSkipped} ` +
        `commit_made=${closureInfo.commit_made}`
    );
  }
}

// -------------------------------------------------------------------------
// Pre-Step-4 Sync Check — ensure local branch HEAD is on origin before merge
//
// AC-1 (TICKET-20260708-Finalize_Push_Before_Merge):
// gh pr merge merges the ORIGIN PR head, not the local HEAD. Any commit made
// on the branch after the last ticket's pull-request phase — e.g. a code-review
// fix, an origin/main-into-branch merge, or a manual edit at finalize time — is
// local-only. If finalize runs without this check, gh pr merge merges the older
// origin head and those local commits are silently excluded from main.
//
// This check compares local HEAD to origin/<branch>. When local is ahead, it
// pushes the branch to origin so the PR head is always current. When the push
// fails or the branch has diverged, it halts with an actionable message.
// -------------------------------------------------------------------------

const syncCheckResult = await agent(
  "Check whether the local feature branch HEAD is ahead of origin and push if needed.\n" +
  `All git commands use the explicit worktree root: git -C "${WORKTREE_ROOT}"\n` +
  "\n" +
  "Step 1 — Fetch origin to ensure tracking refs are current:\n" +
  `  Run: git -C "${WORKTREE_ROOT}" fetch origin "${BRANCH}"\n` +
  "  Capture the exit code. If non-zero, also capture stderr.\n" +
  "  If the fetch exits non-zero: return immediately with NO further steps:\n" +
  "    { \"status\": \"fetch_failed\", \"error\": \"<captured stderr>\" }\n" +
  "  ONLY proceed to Step 2 when fetch exit code is 0.\n" +
  "\n" +
  "Step 2 — Compare local HEAD to origin branch head:\n" +
  `  Run: git -C "${WORKTREE_ROOT}" rev-parse HEAD\n` +
  `  Run: git -C "${WORKTREE_ROOT}" rev-parse "origin/${BRANCH}" 2>/dev/null || echo "no-remote-ref"\n` +
  "  local_sha = the HEAD sha.\n" +
  "  origin_sha = the origin ref sha (or \"no-remote-ref\" if branch has never been pushed).\n" +
  "  If origin ref does not exist: treat as local-ahead (ahead_count > 0, behind_count = 0) and go to Step 4.\n" +
  "  If both SHAs are equal: return up_to_date immediately (go to Step 5).\n" +
  "\n" +
  "Step 3 — When SHAs differ and origin ref exists, determine direction:\n" +
  `  Run: git -C "${WORKTREE_ROOT}" rev-list --count "origin/${BRANCH}..HEAD"\n` +
  "  ahead_count = integer from the output.\n" +
  `  Run: git -C "${WORKTREE_ROOT}" rev-list --count "HEAD..origin/${BRANCH}"\n` +
  "  behind_count = integer from the output.\n" +
  "  Classification rules (MUST follow exactly — no exceptions):\n" +
  "    - ahead_count > 0 AND behind_count == 0 => push path (proceed to Step 4)\n" +
  "    - ahead_count > 0 AND behind_count > 0  => return { \"status\": \"diverged\", ... }\n" +
  "    - ahead_count == 0 AND behind_count > 0 => return { \"status\": \"diverged\", ... }\n" +
  "    - ahead_count == 0 AND behind_count == 0 => impossible here (SHAs would be equal, handled in Step 2)\n" +
  "\n" +
  "Step 4 — Push when local is ahead (ahead_count > 0, behind_count == 0):\n" +
  `  Run: git -C "${WORKTREE_ROOT}" push origin "${BRANCH}"\n` +
  "  Capture exit code.\n" +
  "  If exit code 0:\n" +
  `    Run: git -C "${WORKTREE_ROOT}" rev-parse "origin/${BRANCH}"\n` +
  "    (Re-reads origin_sha after push to get the updated remote ref.)\n" +
  "    Return: { \"status\": \"pushed\", \"ahead_count\": <N>, \"behind_count\": 0, \"local_sha\": \"<local-sha>\", \"origin_sha\": \"<sha-after-push>\" }\n" +
  "  If non-zero:\n" +
  "    Return: { \"status\": \"push_failed\", \"ahead_count\": <N>, \"behind_count\": 0, \"local_sha\": \"<local-sha>\", \"origin_sha\": \"<origin-sha-before-push>\", \"error\": \"<captured stderr>\" }\n" +
  "\n" +
  "Step 5 — Return status for non-push outcomes:\n" +
  "  up_to_date: { \"status\": \"up_to_date\", \"ahead_count\": 0, \"behind_count\": 0, \"local_sha\": \"<sha>\", \"origin_sha\": \"<sha>\" }\n" +
  "  diverged:   { \"status\": \"diverged\",   \"ahead_count\": <N>, \"behind_count\": <N>, \"local_sha\": \"<sha>\", \"origin_sha\": \"<sha>\" }\n" +
  "IMPORTANT: Return ONLY valid JSON with no prose. The 'status' field must be exactly one of:\n" +
  "  fetch_failed, push_failed, diverged, pushed, up_to_date",
  { agentType: "status-checker", label: "pre-step-4-sync-check", phase: "Step 4" }
)

let syncCheckInfo;
{
  let syncCheckValue;
  try {
    syncCheckValue = parseAgentJson(syncCheckResult, { stage: "pre-step-4-sync-check", agent: "status-checker" });
  } catch (_parseErr) {
    syncCheckValue = null;
  }
  // H-1: Fail closed — malformed parse or null/missing value cannot be trusted.
  // Refusing to merge an unverified head is safer than proceeding on unknown state.
  if (syncCheckValue === null || syncCheckValue === undefined) {
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: "pre-4",
      reason: "sync_check_indeterminate",
      message:
        "Could not confirm the local branch HEAD is on origin, so refusing to merge a possibly-stale head. " +
        `Push the branch manually (git push origin ${BRANCH}) and re-run /finalize-feature. ` +
        "The PR has NOT been merged — no work is lost.",
      branch: BRANCH,
      pr_number: prNumber,
      pr_url: prUrl,
      completed_steps: completedSteps,
      skipped_steps: skippedSteps,
      step_outcomes: stepOutcomes,
      step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
      action_required: "verify_and_push",
    };
  }
  syncCheckInfo = syncCheckValue;
}

// H-1: Explicit known-status gate — any status outside this set is indeterminate → HALT.
// There must be NO code path where an unknown/unrecognised status falls through to Step 4.
const KNOWN_SYNC_STATUSES = new Set(["fetch_failed", "push_failed", "diverged", "pushed", "up_to_date"]);
const syncStatus = (typeof syncCheckInfo.status === "string" ? syncCheckInfo.status : "").toLowerCase();

if (!KNOWN_SYNC_STATUSES.has(syncStatus)) {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: "pre-4",
    reason: "sync_check_indeterminate",
    message:
      "Could not confirm the local branch HEAD is on origin, so refusing to merge a possibly-stale head. " +
      `Push the branch manually (git push origin ${BRANCH}) and re-run /finalize-feature. ` +
      "The PR has NOT been merged — no work is lost.",
    branch: BRANCH,
    pr_number: prNumber,
    pr_url: prUrl,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
    step_outcomes: stepOutcomes,
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
    action_required: "verify_and_push",
  };
}

// M-2: fetch_failed → HALT; tracking refs could not be updated so sync state is unknown.
if (syncStatus === "fetch_failed") {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: "pre-4",
    reason: "fetch_failed",
    message:
      `Could not update tracking refs for origin/${BRANCH} (fetch failed). ` +
      "Sync state is unknown — refusing to merge a head that may be stale. " +
      "Verify network / remote access and re-run /finalize-feature. " +
      "The PR has NOT been merged — no work is lost.",
    branch: BRANCH,
    pr_number: prNumber,
    pr_url: prUrl,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
    step_outcomes: stepOutcomes,
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
    action_required: "retry_after_fetch",
  };
}

if (syncStatus === "push_failed") {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: "pre-4",
    reason: "push_failed",
    message:
      "Local branch HEAD is ahead of origin but push failed. " +
      `Push the branch manually (git push origin ${BRANCH}) and re-run /finalize-feature. ` +
      "The PR has NOT been merged — no work is lost.",
    branch: BRANCH,
    pr_number: prNumber,
    pr_url: prUrl,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
    step_outcomes: stepOutcomes,
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
    action_required: "push_local_commits",
  };
}

// M-1: diverged — covers genuine divergence (ahead+behind) AND origin-strictly-ahead case.
// User must integrate origin (rebase/pull) before merging — a plain push would be rejected.
if (syncStatus === "diverged") {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: "pre-4",
    reason: "branch_diverged",
    message:
      `Local branch and origin/${BRANCH} have diverged ` +
      `(local ahead: ${syncCheckInfo.ahead_count ?? 0}, origin ahead: ${syncCheckInfo.behind_count ?? 0} commit(s)). ` +
      "Integrate origin changes before merging: " +
      `git -C "${WORKTREE_ROOT}" pull --rebase origin ${BRANCH}. ` +
      "Resolve any conflicts, verify tests pass, then re-run /finalize-feature. " +
      "Do NOT use plain 'git push' — that would be rejected or would silently drop origin commits. " +
      "The PR has NOT been merged — no work is lost.",
    branch: BRANCH,
    pr_number: prNumber,
    pr_url: prUrl,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
    step_outcomes: stepOutcomes,
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
    action_required: "resolve_divergence",
  };
}

// H-2: pushed — verify SHAs in JS; agent's self-reported status word is not trusted alone.
if (syncStatus === "pushed") {
  const localSha = (typeof syncCheckInfo.local_sha === "string" ? syncCheckInfo.local_sha : "").trim();
  const originSha = (typeof syncCheckInfo.origin_sha === "string" ? syncCheckInfo.origin_sha : "").trim();
  if (!localSha || !originSha || localSha !== originSha) {
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: "pre-4",
      reason: "push_not_confirmed",
      message:
        "Push was reported as successful but SHA verification failed: " +
        "local and origin SHAs do not match or are missing. " +
        `Verify with: git -C "${WORKTREE_ROOT}" rev-parse HEAD "origin/${BRANCH}", ` +
        `then push manually (git push origin ${BRANCH}) and re-run /finalize-feature. ` +
        "The PR has NOT been merged — no work is lost.",
      branch: BRANCH,
      pr_number: prNumber,
      pr_url: prUrl,
      completed_steps: completedSteps,
      skipped_steps: skippedSteps,
      step_outcomes: stepOutcomes,
      step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
      action_required: "verify_and_push",
    };
  }
  log(`[finalize-feature] pre-step-4 sync-check: pushed and SHA-verified (sha=${localSha.slice(0, 8)}). PR head is now current.`);
  completedSteps.push("pre-4-push");
} else if (syncStatus === "up_to_date") {
  // H-2: up_to_date — verify SHAs in JS; agent's status word alone is not trusted.
  const localSha = (typeof syncCheckInfo.local_sha === "string" ? syncCheckInfo.local_sha : "").trim();
  const originSha = (typeof syncCheckInfo.origin_sha === "string" ? syncCheckInfo.origin_sha : "").trim();
  if (!localSha || !originSha || localSha !== originSha) {
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: "pre-4",
      reason: "sync_check_indeterminate",
      message:
        "Could not confirm the local branch HEAD is on origin, so refusing to merge a possibly-stale head. " +
        `Push the branch manually (git push origin ${BRANCH}) and re-run /finalize-feature. ` +
        "The PR has NOT been merged — no work is lost.",
      branch: BRANCH,
      pr_number: prNumber,
      pr_url: prUrl,
      completed_steps: completedSteps,
      skipped_steps: skippedSteps,
      step_outcomes: stepOutcomes,
      step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
      action_required: "verify_and_push",
    };
  }
  log(`[finalize-feature] pre-step-4 sync-check: up-to-date and SHA-verified (sha=${localSha.slice(0, 8)}). No push needed.`);
}
// At this point syncStatus is either "pushed" (SHA-verified, pre-4-push recorded) or
// "up_to_date" (SHA-verified). Both are safe to proceed to Step 4.

// Only record the executed-path outcome when step 3.5 was NOT skipped; the two
// skip branches above already recorded their own 'skipped' outcome, so guarding
// here prevents a duplicate stepOutcomes[] entry for the same step (BO-1000b-1-i AC-2).
if (!skippedSteps.some(s => String(s.step) === "3.5")) {
  outcome('Step 3.5 of 9', ticketsClosedPreMerge > 0
    ? `Closed ${ticketsClosedPreMerge} ticket(s) and ${acsClosed} source AC(s) on the feature branch`
    : 'Pre-merge AC closure completed (no open in-scope tickets on this branch)');
}

// -------------------------------------------------------------------------
// Step 4 — Merge PR to main (destructive — confirmation gate required)
//
// This step runs AFTER the worktree merge (step 2) and test + triage (step 3).
// The gate only shows the confirmation prompt when blocks_finalization === false
// (ensured by the halt in step 3). A defensive guard is included to catch any
// edge case where blocks_finalization is truthy at this point.
// -------------------------------------------------------------------------

phase('Step 4')

narrate("Step 4 of 9", 'Merging the pull request to main after tests pass...')

// Defensive guard: blocks_finalization should never be true here (step 3 halts),
// but guard against edge cases.
if (triageReport !== null && triageReport.blocks_finalization) {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: 4,
    reason: "test_regression",
    triage_report: triageReport,
    message:
      "Defensive guard triggered: blocks_finalization is true at step 4. " +
      "The PR has NOT been merged. Fix regressions and re-run /finalize-feature.",
    branch: BRANCH,
    pr_number: prNumber,
    pr_url: prUrl,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
    step_outcomes: stepOutcomes,
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
  };
}

// First probe current PR state to support crash-resume.
const prStateResult = await agent(
  `Run: gh pr view ${prNumber} --json state --jq '.state'\n` +
  "Return ONLY a JSON object: { \"state\": \"OPEN\"|\"MERGED\"|\"CLOSED\" }",
  { agentType: "status-checker", label: "step-4-pr-state", phase: "Step 4" }
)

let prState;
{
  try {
    prState = parseAgentJson(prStateResult, { stage: "step-4-pr-state", agent: "status-checker" }) || { state: "OPEN" };
  } catch (_parseErr) {
    log("[finalize-feature] step 4 PR state parse malformed — assuming PR is OPEN");
    prState = { state: "OPEN" };
  }
}

if ((prState.state || "").toUpperCase() === "MERGED") {
  // PR already merged — skip the merge gate and proceed.
  log("Step 4 of 9: [skipped] PR #" + prNumber + " is already merged — skipping merge gate");
  outcome(`Step 4 of ${STEP_COUNT}`, 'skipped: PR #' + prNumber + ' already merged');
  skippedSteps.push({ step: 4, reason: "PR already merged — skipping step 4" });
} else {
  // E2 has no prompt() global — implement the merge confirmation gate as an
  // explicit agent turn. The agent presents the question to the user, waits
  // for a response, and returns status: 'ok' (yes) or status: 'blocked' (no).
  // This matches the E2 user-gate convention from the workflow-authoring-contract.
  // ADR-024: resolveGate checks args.resume_answer before the live agent call.
  const fzRunId = (args && typeof args === "object" && args.run_id)
    ? args.run_id
    : (BRANCH || "default-finalize-run");
  const _fzGateResult = await resolveGate(
    "step-4-merge-gate",
    async () => {
      const raw = await agent(
        `WARNING: This will merge PR #${prNumber} (\`${BRANCH}\` → main). This is a destructive operation.\n\n` +
        `Ask the user: "Merge PR #${prNumber} (\`${BRANCH}\` → main)? (yes / no)"\n\n` +
        `Return status:"ok" if the user says yes/confirm/y.\n` +
        `Return status:"blocked" with message "User declined merge." if the user says no/cancel/n.`,
        { agentType: "status-checker", label: "step-4-merge-gate", phase: "Step 4" }
      );
      // FIX 3: parse raw before reading .status — raw may be an unparsed string.
      let parsed;
      try {
        parsed = (typeof raw === "string")
          ? parseAgentJson(raw, { stage: "step-4-merge-gate", agent: "status-checker" })
          : raw;
      } catch (_parseErr) { parsed = null; }
      const s = parsed && parsed.status;
      if (s === "ok") return { action: "ok" };
      if (s === "blocked") return { action: "blocked" };
      return null;
    },
    args,
    { pr_number: prNumber, branch: BRANCH },
    { type: "single_choice", options: ["ok", "blocked"] },
    fzRunId
  );
  if (_fzGateResult && _fzGateResult.status &&
      ["paused_awaiting_input", "nothing_to_resume", "unresumable_stale"].includes(_fzGateResult.status)) {
    await cleanupBaselineWorktree();
    return _fzGateResult;
  }
  // Normalise to the shape downstream code expects: { status: "ok" | "blocked" }
  const _fzAction = _fzGateResult && _fzGateResult.action;
  const mergeConfirmResult = (_fzAction === "ok" || _fzAction === "approve")
    ? { status: "ok" }
    : (_fzAction === "blocked" || _fzAction === "cancel")
      ? { status: "blocked" }
      : null;

  if (!mergeConfirmResult || mergeConfirmResult.status !== "ok") {
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: 4,
      reason: "user_declined_merge",
      message: "Finalization halted at merge step. No changes made to main.",
      branch: BRANCH,
      pr_number: prNumber,
      pr_url: prUrl,
      completed_steps: completedSteps,
      skipped_steps: skippedSteps,
      step_outcomes: stepOutcomes,
      step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
    };
  }

  // Dispatch pull-request agent for the merge operation.
  // AC-3 EMU REST fallback: if `gh pr merge` fails with the EMU error string,
  // fall back to the REST API.
  const emuMergeFallbackNote = GH_REPO
    ? `EMU REST fallback: if gh pr merge fails with "createPullRequest" or "Enterprise Managed User" error, ` +
      `use: gh api -X PUT repos/${GH_REPO}/pulls/${prNumber}/merge -f merge_method="merge". `
    : "";
  mergeResult = await agent(
    `Merge PR #${prNumber} to main using: gh pr merge ${prNumber} --merge --auto\n` +
    emuMergeFallbackNote +
    "Wait for the merge to complete, then return a JSON object: " +
    "{ \"merged\": true, \"sha\": \"<merge-commit-sha>\" }",
    { agentType: "pull-request", label: "step-4-merge-pr", phase: "Step 4" }
  )

  completedSteps.push(4);
  outcome('Step 4 of 9', `PR #${prNumber} merged to main`);
}

// -------------------------------------------------------------------------
// Step 5 — Sync local main (resumable)
//
// AC-2 note: this step does NOT make commits on main. It only runs
// `git checkout main && git pull` (read operations).
// -------------------------------------------------------------------------

phase('Step 5')

narrate("Step 5 of 9", 'Syncing local main with origin after the pull request merge...')

const syncResult = await agent(
  "Run these commands in sequence using the explicit repo root to avoid CWD ambiguity:\n" +
  `1. git -C "${WORKTREE_ROOT}" checkout main\n` +
  `2. git -C "${WORKTREE_ROOT}" pull\n` +
  `3. git -C "${WORKTREE_ROOT}" log -1 --oneline\n` +
  "Report the final HEAD SHA and commit message. " +
  "Return a JSON object: { \"head_sha\": \"<sha>\", \"head_message\": \"<message>\" }",
  { agentType: "status-checker", label: "step-5-sync-main", phase: "Step 5" }
)

let headSha = null;
let headMessage = null;
{
  try {
    const syncInfo = parseAgentJson(syncResult, { stage: "step-5-sync-main", agent: "status-checker" }) || {};
    headSha = (typeof syncInfo.head_sha === "string" ? syncInfo.head_sha.trim() : null) || null;
    headMessage = (typeof syncInfo.head_message === "string" ? syncInfo.head_message.trim() : null) || null;
  } catch (_parseErr) {
    log("[finalize-feature] step 5 sync-main parse malformed — HEAD SHA and message will be unknown");
  }
}

completedSteps.push(5);

outcome('Step 5 of 9', `Local main synced: HEAD ${headSha || 'unknown'} — ${headMessage || 'message unknown'}`);

// -------------------------------------------------------------------------
// Step 6 — Report untracked pre-existing/flaky failures, then detect scope
// -------------------------------------------------------------------------

phase('Step 6')

narrate("Step 6 of 9", 'Reporting untracked pre-existing and flaky failures, then detecting branch scope...')

// Sub-step 6a: report pre-existing / flaky failures that require manual tracking.
if (triageReport !== null) {
  const triageEntries = Array.isArray(triageReport.triage_report)
    ? triageReport.triage_report
    : [];

  const preExistingEntries = triageEntries.filter(
    (entry) =>
      entry.category === "pre_existing" || entry.category === "flaky"
  );

  if (preExistingEntries.length === 0) {
    log(
      "[finalize-feature] step 6a: no pre_existing or flaky entries in triage report — no tracking tickets needed"
    );
  } else {
    // Collect untracked failures so the final summary is accurate.
    for (const entry of preExistingEntries) {
      const testId = entry.test_id || "<unknown test>";
      const category = entry.category || "pre_existing";
      untrackedFailures.push({ testId, category });
    }

    // Emit one structured report listing all untracked failures.
    const failureLines = untrackedFailures
      .map(
        ({ testId, category }) =>
          `  - [${category}] ${testId} (failing on main at SHA ${baselineSha || "unknown"})`
      )
      .join("\n");

    log(
      `[finalize-feature] step 6a: ${untrackedFailures.length} pre-existing/flaky failure(s) detected.\n` +
      `Auto-ticketing is disabled (create-ticket is a workflow, not an agent).\n` +
      `No tracking tickets were created. To track these failures, run /create-ticket for each:\n` +
      failureLines
    );
  }
}

// Sub-step 6b: scope-detection only (no git writes on main)
const closeResult = await agent(
  "Detect branch scope and report what tickets were touched (informational only — no writes):\n" +
  `1. Run: git -C "${WORKTREE_ROOT}" log --oneline main..${BRANCH} 2>/dev/null || git -C "${WORKTREE_ROOT}" log --oneline -20\n` +
  "2. Search tickets/ tree for ticket files referencing this branch.\n" +
  "3. Determine if any ticket path is inside an EPIC-*/ folder — if so, this is epic-scoped.\n" +
  "4. For each in-scope ticket: read its frontmatter `status:` field.\n" +
  "   NOTE: Do NOT flip status or move files. Ticket closure already happened in\n" +
  "   step 3.5 (pre-merge closure commit on the feature branch). status: frontmatter\n" +
  "   is the sole source of truth (BO-400a-3/4/5, BO-400c-1/2).\n" +
  "5. Return a JSON object: " +
  '{ "scope": "single-ticket"|"epic"|"unknown", ' +
  '"tickets_in_scope": ["<path>", ...], ' +
  '"tickets_done": ["<path — status: done>", ...], ' +
  '"tickets_not_done": ["<path — status: other>", ...], ' +
  '"skipped": false|true }',
  { agentType: "status-checker", label: "step-6-scope-detect", phase: "Step 6" }
)

let closeInfo;
{
  try {
    closeInfo = parseAgentJson(closeResult, { stage: "step-6-scope-detect", agent: "status-checker" }) || { tickets_in_scope: [], tickets_done: [], tickets_not_done: [], skipped: false };
  } catch (_parseErr) {
    log("[finalize-feature] step 6 scope-detect parse malformed — no tickets reported in summary");
    closeInfo = { tickets_in_scope: [], tickets_done: [], tickets_not_done: [], skipped: false };
  }
}

// Step 6b is informational only — no ticket files were moved or written.
if (closeInfo.tickets_done && Array.isArray(closeInfo.tickets_done)) {
  ticketsClosed.push(...closeInfo.tickets_done);
}

if (closeInfo.skipped) {
  outcome(`Step 6 of ${STEP_COUNT}`, 'skipped: scope detection — no in-scope tickets found');
  skippedSteps.push({ step: 6, reason: "Scope detection skipped — no in-scope tickets found" });
} else {
  completedSteps.push(6);
  outcome('Step 6 of 9',
    `Reported ${untrackedFailures.length} untracked pre-existing/flaky failure(s); ` +
    `${Array.isArray(closeInfo.tickets_done) ? closeInfo.tickets_done.length : 0} ticket(s) confirmed done in scope`);
}

// -------------------------------------------------------------------------
// Step 7 — Remove worktree (resumable; confirmation gate delegated to agent)
// -------------------------------------------------------------------------

phase('Step 7')

narrate("Step 7 of 9", 'Removing the feature worktree after finalization is complete...')

const worktreeProbeResult = await agent(
  `Run: git -C "${WORKTREE_ROOT}" worktree list --porcelain\n` +
  `Check if a worktree for WORKTREE_ROOT="${WORKTREE_ROOT}" is listed.\n` +
  "Return ONLY a JSON object: { \"exists\": true|false }",
  { agentType: "status-checker", label: "step-7-worktree-probe", phase: "Step 7" }
)

let worktreeProbe;
{
  try {
    worktreeProbe = parseAgentJson(worktreeProbeResult, { stage: "step-7-worktree-probe", agent: "status-checker" }) || { exists: true };
  } catch (_parseErr) {
    // AC-4: Malformed probe — conservative default is exists=true (safer to
    // attempt removal than to skip and leave the worktree dangling).
    log("[finalize-feature] step 7 worktree probe parse malformed — assuming exists=true (conservative)");
    worktreeProbe = { exists: true };
  }
}

if (!worktreeProbe.exists) {
  worktreeRemoved = false;
  log("Step 7 of 9: [skipped] Worktree already absent — skipping removal");
  outcome(`Step 7 of ${STEP_COUNT}`, 'skipped: worktree already absent — skipping step 7');
  skippedSteps.push({ step: 7, reason: "Worktree already absent — skipping step 7" });
} else {
  // Dispatch worktree-agent (it owns its own confirmation gate).
  const worktreeResult = await agent(
    `Remove the worktree at ${WORKTREE_ROOT}. ` +
    "If conflict_pids are reported, surface them verbatim and stop. " +
    "Return a JSON object: { \"removed\": true|false, \"conflict_pids\": [] }",
    { agentType: "worktree-agent", label: "step-7-remove-worktree", phase: "Step 7" }
  )

  let wResult;
  {
    try {
      wResult = parseAgentJson(worktreeResult, { stage: "step-7-remove-worktree", agent: "worktree-agent" }) || { removed: false, conflict_pids: [] };
    } catch (_parseErr) {
      log("[finalize-feature] step 7 worktree-agent parse malformed — assuming removed=false, conflict_pids=[]");
      wResult = { removed: false, conflict_pids: [] };
    }
  }

  if (wResult.conflict_pids && wResult.conflict_pids.length > 0) {
    // Surface conflict PIDs verbatim and stop — user must resolve manually.
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: 7,
      reason: "worktree_conflict_pids",
      message:
        "Worktree removal blocked by conflicting processes. " +
        "Resolve the conflict PIDs below, then re-run /finalize-feature.",
      conflict_pids: wResult.conflict_pids,
      branch: BRANCH,
      pr_number: prNumber,
      pr_url: prUrl,
      completed_steps: completedSteps,
      skipped_steps: skippedSteps,
      step_outcomes: stepOutcomes,
      step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
      tickets_closed: ticketsClosed,
    };
  }

  worktreeRemoved = wResult.removed === true;
  completedSteps.push(7);
  outcome('Step 7 of 9', worktreeRemoved
    ? `Worktree removed: ${WORKTREE_ROOT}`
    : 'Worktree removal failed — no removal made');
}

// -------------------------------------------------------------------------
// Final — Return success summary
//
// AC-1: ensure the baseline temp worktree is cleaned up on the success path.
// baselineWorktreePath is already null when step 0 completed successfully
// (the agent ran step D to remove it), so this is a no-op in the happy path.
// It fires only when step 0 degraded but the workflow continued to completion.
// -------------------------------------------------------------------------
await cleanupBaselineWorktree();

return {
  status: "ok",
  branch: BRANCH,
  pr_number: prNumber,
  pr_url: prUrl,
  merge_result: mergeResult,
  merge_strategy: mergeStrategy,
  // Baseline context included in the summary for auditability.
  baseline_sha: baselineSha,
  baseline_failures: baselineFailures,
  baseline_run_at: baselineRunAt,
  test_result: testResult,
  // Triage report from step 3; null means tests passed (no triage needed).
  triage_report: triageReport,
  tickets_closed: ticketsClosed,
  // Pre-merge closure counts from step 3.5.
  tickets_closed_pre_merge: ticketsClosedPreMerge,
  acs_closed: acsClosed,
  acs_skipped: acsSkipped,
  // Untracked failures from step 6a: pre_existing/flaky triage entries for which
  // no tracking ticket was created (auto-ticketing is disabled — create-ticket is a
  // workflow, not an agent). Operators should run /create-ticket manually for each.
  untracked_failures: untrackedFailures,
  worktree_removed: worktreeRemoved,
  completed_steps: completedSteps,
  skipped_steps: skippedSteps,
  // In-order per-step outcome record (AC BO-1000b-1).
  // Consumed by BO-1000b-2 (end-of-run summary) and BO-1000c-1a (live relay).
  step_outcomes: stepOutcomes,
  // End-of-run summary composed from the recorded per-step outcomes (AC BO-1000b-2).
  // Each step is listed alongside the specific outcome text it recorded — not a bare
  // overall status. Sourced directly from stepOutcomes[] so the summary cannot
  // diverge from what was narrated live.
  step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
  message:
    `Feature "${BRANCH}" finalized. ` +
    `Steps completed: [${completedSteps.join(", ")}]. ` +
    (skippedSteps.length > 0
      ? `Steps skipped (already done): [${skippedSteps.map((s) => s.step).join(", ")}]. `
      : "") +
    (baselineFailures !== null
      ? `Baseline captured at ${baselineSha} (${baselineFailures.length} pre-existing failure(s)). `
      : "Baseline capture failed — regression triage used conservative classification. ") +
    (ticketsClosedPreMerge > 0
      ? `Pre-merge closure: ${ticketsClosedPreMerge} ticket(s) closed, ${acsClosed} AC(s) closed, ${acsSkipped} AC(s) skipped. `
      : "No pre-merge ticket/AC closure. ") +
    (ticketsClosed.length > 0
      ? `Tickets closed total: ${ticketsClosed.length}. `
      : "") +
    (untrackedFailures.length > 0
      ? `${untrackedFailures.length} pre-existing/flaky failure(s) not auto-ticketed (auto-ticketing disabled) — run /create-ticket manually to track them. `
      : ""),
};
