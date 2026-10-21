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

// Narration helper — AC BO-1000a-1, AC BO-1000a-1-i. narrate() runs BEFORE a step's first
// agent() dispatch so the in-flight step is identifiable from the progress stream even when
// a sub-agent errors; error branches must not emit their own 'Step X of N' line.
// The "Step X of N" label is double-quoted (BO-1000a-2) and N must equal STEP_COUNT.

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
}

// Outcome helper — AC BO-1000b-1. Fires AFTER a step's agent() dispatches and records to
// stepOutcomes[] for the end-of-run summary (BO-1000b-2). The literal 'Step X of N' label
// stays statically visible to tooling. In-flight visibility comes from the E2 engine's own
// per-agent journal (<transcriptDir>/journal.jsonl); see the removal note further down.

const stepOutcomes = [];

/**
 * Emit a post-step outcome line on the workflow's narration channel.
 *
 * Invoke after each numbered step's work completes on the success path,
 * after all agent() dispatches in the step (AC BO-1000b-1). The description
 * carries the concrete result data for the step — not a bare 'done' notice.
 *
 * Also records to stepOutcomes[] so downstream consumers (BO-1000b-2
 * end-of-run summary) can read the ordered per-step record without
 * re-parsing log output.
 *
 * @param {string} progressText - Literal position label, e.g. 'Step 0 of 9'.
 * @param {string} description  - Concrete result description for the step.
 */
function outcome(progressText, description) {
  const entry = { step: progressText, outcome: description };
  stepOutcomes.push(entry);
  const line = progressText + ': ' + description;
  log(line);
}

// Single source of truth for N in "Step X of N" — AC BO-1000a-2. When adding or removing a
// step: update meta.phases, STEP_COUNT, and the N literal in every narrate() call.

/** Total number of numbered steps in the finalize sequence (AC BO-1000a-2). */
const STEP_COUNT = 9;

// AC FIN-100h: statuses meaning "this agent DECLINED the dispatch". A refusal never ran at
// all (unlike a failure), so load-bearing steps must halt on it rather than fall through
// to a success path.
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

// INF-700a-5-i, Step 7 before the removal. Step 4's merge is not trusted, so the PR state is probed. Merged: the
// read-only `observe --all-stages` names every stage's routed write HEAD lacks; not merged: every staged write.
let unpublishedLearnings = [];
async function announceUnpublishedLearnings() {
  let merged = false;
  try {
    const probe = await agent(`Run: gh pr view ${prNumber} --json state --jq '.state'\nReturn ONLY a JSON object: { "state": "OPEN"|"MERGED"|"CLOSED" }`, { agentType: "status-checker", label: "step-7-pr-merged-probe", phase: "Step 7" });
    merged = String(parsedOr(() => parseAgentJson(probe, { stage: "step-7-pr-merged-probe", agent: "status-checker" }), {}, "treating the branch as not merged").state || "").toUpperCase() === "MERGED";
    // Read-only observation: one shell-runner dispatch of the exact command; a reply that is no usable result is
    // recorded as "did not run" (never as nothing-unpublished) and the advisory step never blocks the removal.
    const observed = shellStepReply(await shellStepDispatch(
      `python3 {{config.output_root}}/scripts/knowledge/completion_routing_cli.py observe --working-dir ${WORKTREE_ROOT} --commit-status ${merged ? "ok" : "not_run"} --all-stages`,
      "step-7-unpublished-learnings", "Step 7"), "step-7-unpublished-learnings");
    const reply = observed.ok
      ? parsedOr(() => parseAgentJson(observed.stdout, { stage: "step-7-unpublished-learnings", agent: "shell-runner" }), {}, "announcing nothing; removal proceeds")
      : { case: "did_not_run", detail: observed.reason + " -- " + observed.received };
    unpublishedLearnings = (Array.isArray(reply.unwritten_records) ? reply.unwritten_records : [])
      .filter((r) => r && typeof r === "object" && r.destination)
      .map((r) => (merged || r.reason !== "stopped_before_publication" ? r : { ...r, reason: "branch_not_merged" }));
    if (!reply.case || reply.case === "did_not_run") log(`[finalize-feature] step 7 unpublished-learning check did not run: ${reply.detail || "no usable reply"}`);
  } catch (err) {
    log(`[finalize-feature] step 7 unpublished-learning check unavailable (${err}) — removal proceeds`);
  }
  if (unpublishedLearnings.length === 0) return "";
  const note = (merged ? `${unpublishedLearnings.length} learning(s) written in this worktree are NOT in the merged tree:\n`
    : `branch not merged — every routed learning here is unpublished (${unpublishedLearnings.length}):\n`) +
    unpublishedLearnings.map((r) => `  - ${r.destination} [${r.reason}; ${r.eligible === false
      ? "NOT eligible: will not be written again" : "still eligible: a later completed unit of work writes it"}]: ${r.text}`).join("\n");
  log(`[finalize-feature] step 7: ${note}`);
  return `Before removing, tell the user verbatim (this does not block the removal):\n${note}\n\n`;
}

// AC BO-1000a-2-i: step 3.5 is counted in STEP_COUNT (3 < 3.5 < 4). Pre-flight sections make
// no narrate() call; their failures use a non-numbered { status: 'error', ... } return.

// E2 top-level body — executed directly by the E2 engine. workflow() is never called
// (in E2 it throws, which is the leaf guard).

// Pre-flight: detect branch and worktree root

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
    let depth = 0, inString = false, j = i;
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
            try { return JSON.parse(raw.slice(i, j + 1)); } catch (_) { i = j; break; }
          }
        }
      }
      j++;
    }
    if (depth > 0) { break; }
  }
  throw new Error(
    "[" + stage + "] " + agent +
    " returned a reply with no parseable JSON — " +
    "all reply-reading sites must route through parseAgentJson"
  );
}

/**
 * Run `parse` — a parseAgentJson(...) call written AT the dispatch site, so every
 * reply-reading site stays visible as one (BP-300e-6 derivation). A malformed reply
 * is logged with parseAgentJson's own "[stage] agent ..." message plus `note`, and
 * answered with `fallback` (AC-4: degrade to the stage's conservative default).
 */
function parsedOr(parse, fallback, note) {
  try {
    return parse() || fallback;
  } catch (err) {
    log(`[finalize-feature] parse malformed — ${note}: ${err && err.message}`);
    return fallback;
  }
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
      "  python {{config.output_root}}/scripts/pause_store.py read --run-id " + runId + "\n" +
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
    // record_context lets a caller bind the answer to what the question was about (BO-400e-3-vii).
    return { ...applyAnswerByType(args.resume_answer, incomingType), record_context: (recCheck.record && recCheck.record.context) || null };
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
    "  python {{config.output_root}}/scripts/pause_store.py write --run-id " + runId + " --record '" + JSON.stringify(rec) + "'\n" +
    "That writes .leafcutter/paused_runs/" + runId + ".json. Return the command's JSON stdout.";
  await agent(_persistPrompt, { agentType: "status-checker", label: "pause-persist" });
  return { status: "paused_awaiting_input", run_id: runId, gate_id: gateId };
}

// -------------------------------------------------------------------------
// Pre-flight workspace: branch and root come only from the workspace maker's answer (below).
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
// A non-string target value (number, object) is treated as no target (FIN-100g-2-i), not a .trim() TypeError.
const epicArg = (typeof _epicArgCandidate === 'string' ? _epicArgCandidate : '').trim();

// BO-4300c-3 / BO-4300a-1-ia: ONE workspace -- the maker's answer (args.workspace, or exactly ONE verbatim dispatch).
// Branch and root come from that answer only; a decline / prose / result-less reply ends the run quoting it.
// WORKSPACE-ANSWER-START
// WORKSPACE-ANSWER-END

const finalizeSlug = (epicArg || "finalize-feature").toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "finalize-feature";
const finalizeWorkspace = await workspaceObtain(
  "python3 {{config.output_root}}/scripts/worktree.py ensure --kind feature --slug " + finalizeSlug, "Pre-flight");
if (!finalizeWorkspace.accepted) return workspaceFailure(finalizeWorkspace);

const BRANCH = workspaceBranch(finalizeWorkspace.answer);
const WORKTREE_ROOT = finalizeWorkspace.workspace_path;

if (!BRANCH || BRANCH === "main" || BRANCH === "master") {
  return {
    status: "error",
    message:
      "/finalize-feature must be run from a feature branch, not main/master " +
      `(the workspace maker named branch: "${BRANCH}" for target: "${epicArg}"). ` +
      "Re-run with the feature's own name.",
    action_required: "switch_to_feature_branch",
  };
}

const completedSteps = [];
const skippedSteps = [];
let prNumber = null;
let prUrl = null;
let mergeResult = null;
let testResult = null;
const ticketsClosed = [];
// Failures that could not be auto-ticketed (create-ticket is a workflow, not an agent); set by step 6a.
const untrackedFailures = [];
let worktreeRemoved = false;
let triageReport = null; // from step 3; null means tests passed
let ticketsClosedPreMerge = 0; // closure counts from step 3.5
let acsClosed = 0;
let acsSkipped = 0;
let closureReport = []; // one line per closed/refused/left-open record from step 3.5

// Baseline state from step 0, forwarded to step 3 triage. null means the baseline run did
// not complete, so triage treats every failure as a regression.
let baselineFailures = null; // string[] | null
let baselineSha = null;      // string | null
let baselineRunAt = null;    // ISO string | null

// Cleanup guard: the scratch workspace of a baseline / targeted-rerun run, removed through the
// workspace maker (never by a hand-written git or rm command) on any early exit.
// The slug embeds args.baseline_ts, which replaces Date.now() (banned in E2 -- non-deterministic).
const baselineSlug = ("finalize-baseline-" + String((args && args.baseline_ts) || "baseline"))
  .toLowerCase().replace(/[^a-z0-9._-]+/g, "-");
let baselineWorktreePath = null;
// BO-4300e-4: the outcome of clearing the scratch copy (the maker's `remove` answer) -- part of finalize's own result.
let scratchClearing = null;

/** Remove the scratch baseline workspace: one shell-runner dispatch of the maker's `remove`; best-effort, a failed reply is logged. */
async function cleanupBaselineWorktree() {
  if (!baselineWorktreePath) return;
  const path = baselineWorktreePath;
  baselineWorktreePath = null;
  try {
    const removal = shellStepReply(await shellStepDispatch(
      "python3 {{config.output_root}}/scripts/worktree.py remove --path \"" + path + "\" --force",
      "cleanup-baseline-worktree", "Cleanup"), "cleanup-baseline-worktree");
    if (!removal.ok) log("[finalize-feature][WARNING] baseline workspace " + path + " was not removed: " + removal.reason + " -- " + removal.received);
    scratchClearing = workspaceRemovalRecord(path, removal);
  } catch (err) {
    log("[finalize-feature][WARNING] baseline workspace cleanup failed: " + (err && err.message));
    scratchClearing = workspaceRemovalRecord(path, null, String(err && err.message));
  }
}

/**
 * A scratch workspace from the maker, ONE pytest run in it (whole suite, or only `testIds`), its removal; every
 * step is a shell-runner dispatch. status "declined" = an answer that was no usable result -- never "the step ran".
 */
async function mainTestRun(slug, testIds, phaseName, stepLabel) {
  const made = workspaceAcceptAnswer(await workspaceDispatch(
    "python3 {{config.output_root}}/scripts/worktree.py ensure --kind scratch --slug " + slug, phaseName, stepLabel + "-workspace"));
  if (!made.accepted) {
    const makerSaidNo = made.kind === "refused" || made.kind === "error";
    return { status: makerSaidNo ? "worktree_failed" : "declined", failures: null, sha: null, detail: made.reason + ": " + made.received };
  }
  const root = made.workspace_path;
  baselineWorktreePath = root;
  const sha = typeof made.answer.base_commit === "string" ? made.answer.base_commit : null;
  // Deploy shims first (build parity with Step 3); pytest runs only when the deploy succeeded.
  const deploy = shellStepReply(await shellStepDispatch(
    "python3 \"" + root + "/scripts/build.py\" --target-dir \"" + root + "\"", stepLabel + "-deploy", phaseName), stepLabel + "-deploy");
  const deployOk = deploy.ok && deploy.exit_status === 0;
  const targets = testIds ? testIds.map((id) => "\"" + root + "/" + id + "\"").join(" ") : "\"" + root + "\"";
  const run = deployOk
    ? shellStepReply(await shellStepDispatch(
      "python3 -m pytest --tb=no -q --rootdir \"" + root + "\" " + targets, stepLabel, phaseName), stepLabel)
    : null;
  await cleanupBaselineWorktree();
  const fin = (status, detail, failures) => ({ status, failures: failures || null, sha, detail });
  if (!deploy.ok) return fin("declined", deploy.reason + ": " + deploy.received);
  if (!deployOk) return fin("build_failed", "build.py exited " + deploy.exit_status);
  if (!run.ok) return fin("declined", run.reason + ": " + run.received);
  if (run.exit_status !== 0 && run.exit_status !== 1) return fin("run_failed", "pytest exited " + run.exit_status);
  return fin("ok", "", pytestFailedIds(run.stdout));
}

/** The failing test ids named in pytest's output (`FAILED <id> - ...` or `<id> FAILED`). */
function pytestFailedIds(stdout) {
  return String(stdout || "").split(/\r?\n/).map((l) => /^FAILED\s+(\S+)/.exec(l) || /^(\S+::\S+)\s+FAILED/.exec(l)).filter(Boolean).map((m) => m[1]);
}

/** Branch, PR and step-progress fields every halt return carries (each still states its own step_summary). */
function haltRefs() {
  return { branch: BRANCH, pr_number: prNumber, pr_url: prUrl, completed_steps: completedSteps, skipped_steps: skippedSteps, step_outcomes: stepOutcomes, scratch_clearing: scratchClearing };
}

/** A step_refused halt: the shell-runner's answer was no usable result, so whether the step ran is unknown. */
async function refusedHalt(step, what, remedy) {
  await cleanupBaselineWorktree();
  outcome(`Step ${step} of ${STEP_COUNT}`, `halted: ${what}`);
  return { status: "halted", halted_at_step: step, reason: "step_refused", message: remedy, ...haltRefs(),
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n') };
}

// Pre-flight 2 — gh account verification (EMU-aware, config-driven)
//
// Reads `gh_target_account` and `gh_repo` from the worktree's settings.json
// (or config/settings.json). If the key is absent the pre-flight is a no-op
// so installs with no EMU constraint are unaffected (AC-4).

phase('Pre-flight 2')

const ghConfigResult = await agent(
  "Read the gh account config from the worktree settings file.\n" +
  `Run: cat "${WORKTREE_ROOT}/settings.json" 2>/dev/null || cat "${WORKTREE_ROOT}/config/settings.json" 2>/dev/null || echo 'null'\n` +
  "Parse the JSON output (if any). Look for a top-level key 'gh_target_account' and 'gh_repo'.\n" +
  "Return ONLY a JSON object: { \"gh_target_account\": \"<value or null>\", \"gh_repo\": \"<owner/repo or null>\" }\n" +
  "If the file does not exist or the keys are absent, return: { \"gh_target_account\": null, \"gh_repo\": null }",
  { agentType: "status-checker", label: "gh-config", phase: "Pre-flight 2" }
)

const ghConfig = parsedOr(() => parseAgentJson(ghConfigResult, { stage: "gh-config", agent: "status-checker" }), { gh_target_account: null, gh_repo: null }, "proceeding with no account constraint");

const GH_TARGET_ACCOUNT = (ghConfig.gh_target_account || "").trim() || null;
const GH_REPO = (ghConfig.gh_repo || "").trim() || null;

if (GH_TARGET_ACCOUNT) {
  const ghStatusResult = await agent(
    "Run: gh auth status 2>&1\n" +
    "Parse the output to find which account is currently logged in and active.\n" +
    "The active account appears on the line containing 'Logged in to' or '✓ Logged in to'.\n" +
    "The active account username follows 'as ' (e.g. 'Logged in to github.com as urlmonitor').\n" +
    "Return ONLY a JSON object: { \"active_account\": \"<username or null>\" }",
    { agentType: "status-checker", label: "gh-auth-status", phase: "Pre-flight 2" }
  )

  const ghStatus = parsedOr(() => parseAgentJson(ghStatusResult, { stage: "gh-auth-status", agent: "status-checker" }), { active_account: null }, "assuming active_account is null");

  const activeAccount = (ghStatus.active_account || "").trim() || null;

  if (activeAccount !== GH_TARGET_ACCOUNT) {
    // BO-4300a-1-ia: switch and re-verification are two shell-runner dispatches; no usable result ends the run quoting it.
    const ghHalt = (r) => ({ status: "error", message: `gh account pre-flight failed: ${r.reason}. Received: ${r.received}`, action_required: "gh_login_required" });
    const ghSwitch = shellStepReply(await shellStepDispatch(
      `gh auth switch --user "${GH_TARGET_ACCOUNT}"`, "gh-auth-switch", "Pre-flight 2"), "gh-auth-switch");
    if (!ghSwitch.ok) return ghHalt(ghSwitch);
    const ghVerify = shellStepReply(await shellStepDispatch(
      "gh auth status", "gh-auth-verify", "Pre-flight 2"), "gh-auth-verify");
    if (!ghVerify.ok) return ghHalt(ghVerify);
    // The active account is the one named just before an "Active account: true" line (gh prints one block per account).
    let verifiedAccount = null;
    for (const line of (ghVerify.stdout + "\n" + ghVerify.stderr).split(/\r?\n/)) {
      const named = /Logged in to \S+ (?:account|as) (\S+)/.exec(line);
      if (named) verifiedAccount = named[1];
      if (/Active account:\s*true/i.test(line) && verifiedAccount) break;
    }
    const switchFailed = ghSwitch.exit_status !== 0 || verifiedAccount !== GH_TARGET_ACCOUNT;

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
}

// Step 0 — Capture pre-merge test baseline on current main HEAD
//
// Makes a scratch workspace at origin/main, runs the suite in it, and stores the failing test IDs as the
// baseline passed to triage in step 3. Graceful degradation: if the workspace or the run fails, set
// baselineFailures = null -- the workflow does NOT halt; triage classifies all failures as regressions.
// -------------------------------------------------------------------------

phase('Step 0')

narrate("Step 0 of 9", 'Capturing pre-merge test baseline on current main HEAD...')

// BO-4300a-1-ia: a scratch workspace from the maker (no hand-written workspace steps or rm) and one pytest run in it
// (after the build.py deploy, so deploy-dependent tests are not RED in the baseline), each a shell-runner dispatch.
const baselineRun = await mainTestRun(baselineSlug, null, "Step 0", "step-0-baseline");
const baselineInfo = {
  status: baselineRun.status,
  baseline_sha: baselineRun.sha,
  baseline_failures: baselineRun.failures,
  baseline_run_at: null, // no clock in an E2 body
  detail: baselineRun.detail,
};

const baselineStatus = (baselineInfo.status || "unknown").toLowerCase();

// AC FIN-100h: a REFUSAL is not a run failure (run_failed / parse_failed degrade conservatively below). A
// refusal means the step never ran -- no evidence either way, and the whole regression comparison rests on
// the baseline -- so halt instead of degrading.
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
      "Received: " + baselineInfo.detail,
    ...haltRefs(),
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
  };
}

if (baselineStatus === "ok") {
  baselineFailures = Array.isArray(baselineInfo.baseline_failures)
    ? baselineInfo.baseline_failures
    : [];
  baselineSha = baselineInfo.baseline_sha || null;
  baselineRunAt = baselineInfo.baseline_run_at || null;
  completedSteps.push(0);
} else {
  // worktree_failed | run_failed | parse_failed | unknown — degrade gracefully.
  // baselineFailures stays null — triage will classify all failures as regressions.
  baselineSha = baselineInfo.baseline_sha || null;
  baselineRunAt = baselineInfo.baseline_run_at || null;
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

// Step 1 — Open PR if missing (non-destructive, no confirmation gate)

phase('Step 1')

narrate("Step 1 of 9", 'Checking for an open pull request; opening one if missing...')

const prProbeResult = await agent(
  `Run: gh pr list --head "${BRANCH}" --json number,url --jq '.[0]'\n` +
  "Return ONLY a JSON object:\n" +
  "- If a PR is found: { \"found\": true, \"number\": <N>, \"url\": \"<url>\" }\n" +
  "- If no PR exists: { \"found\": false }",
  { agentType: "status-checker", label: "step-1-pr-probe", phase: "Step 1" }
)

// AC-4: a malformed probe means "not found" — a duplicate PR is rejected by GH; a skipped one is silent.
const prProbe = parsedOr(() => parseAgentJson(prProbeResult, { stage: "step-1-pr-probe", agent: "status-checker" }), { found: false }, "assuming no PR exists");

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

  const openPr = parsedOr(() => parseAgentJson(openPrResult, { stage: "step-1-open-pr", agent: "pull-request" }), {}, "pr_number and url will be null");

  prNumber = openPr.number || openPr.pr_number || null;
  prUrl = openPr.url || openPr.pr_url || null;
  completedSteps.push(1);
  outcome('Step 1 of 9', prNumber !== null
    ? `PR open: #${prNumber} at ${prUrl || 'url unknown'}`
    : 'Pull request status could not be determined');
}

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

// AC-4: a malformed reply is not "conflict detected" — a real merge problem surfaces at step 3 instead.
const mergeMainInfo = parsedOr(() => parseAgentJson(mergeMainResult, { stage: "step-2-merge-main", agent: "status-checker" }),
  { status: "already_up_to_date", merge_strategy: "already_up_to_date" }, "treating as already_up_to_date (non-halting safe default)");

const mergeStatus = (mergeMainInfo.status || "already_up_to_date").toLowerCase();

if (mergeStatus === "conflict") {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: 2,
    reason: "merge_conflict",
    message:
      "Feature branch has conflicts with main. Resolve conflicts and re-run.",
    ...haltRefs(),
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
    ...haltRefs(),
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

// AC-4: a malformed test reply is ambiguous — treated as failed (conservative), logged as a parse
// failure rather than an agent-reported one; triage then classifies (with its own safe default).
testResult = parsedOr(() => parseAgentJson(testResult, { stage: "step-3-test-run", agent: "test-runner" }),
  { passed: false, output: "(parse malformed)", failing_tests: [] }, "treating as failed (conservative; triage will classify)");
let testPassed = testResult.passed === true;
let postMergeFailures = Array.isArray(testResult.failing_tests) ? testResult.failing_tests : [];

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
  // BO-4300a-1-ia: the deploy is ONE shell-runner dispatch of the exact build command; the re-run of the failing
  // tests is a second. The classification is computed here from what the re-run reported, never taken from prose.
  const deployReply = shellStepReply(await shellStepDispatch(
    `python3 "${WORKTREE_ROOT}/scripts/build.py" --target-dir "${WORKTREE_ROOT}"`, "step-3-deploy-parity", "Step 3"), "step-3-deploy-parity");
  if (!deployReply.ok) {
    return await refusedHalt(3, `deploy-parity step produced no usable answer (${deployReply.reason})`,
      `Step 3 (deploy parity) received no usable answer, so whether the deploy ran is unknown: ${deployReply.reason}. Received: ${deployReply.received}`);
  }
  let buildStateOnly = [];
  let stillFailing = null;
  if (deployReply.exit_status === 0) {
    const rerun = shellStepReply(await shellStepDispatch(
      "python3 -m pytest --tb=no -q --rootdir \"" + WORKTREE_ROOT + "\" " +
      postMergeFailures.map((id) => "\"" + WORKTREE_ROOT + "/" + id + "\"").join(" "), "step-3-deploy-parity-rerun", "Step 3"), "step-3-deploy-parity-rerun");
    if (rerun.ok && (rerun.exit_status === 0 || rerun.exit_status === 1)) {
      stillFailing = pytestFailedIds(rerun.stdout);
      buildStateOnly = postMergeFailures.filter((t) => !stillFailing.includes(t));
    } else {
      log(`[finalize-feature] step 3 deploy-parity re-run gave no usable result (${rerun.ok ? "pytest exited " + rerun.exit_status : rerun.reason}); proceeding with the original post-merge failures (conservative).`);
    }
  } else {
    log(`[finalize-feature] step 3 deploy-parity: build.py exited ${deployReply.exit_status}; proceeding with the original post-merge failures (conservative).`);
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
  // Step 3 (triage sub-step) — Dispatch test-failure-triage when failures exist
  //
  // Passes post_merge_failures, baseline_failures, baseline_sha,
  // feature_branch, and changed_files (derived here via git diff) so the
  // triage agent can classify each failure as regression or pre-existing.

  // Derive changed_files: files touched by the feature branch relative to
  // origin/main. Captured at this point (after the --no-commit merge) so
  // the diff reflects the full feature delta including the merged state.
  const changedFilesResult = await agent(
    `Run: git -C "${WORKTREE_ROOT}" diff --name-only origin/main HEAD\n` +
    "Return ONLY a JSON object: { \"changed_files\": [\"<file1>\", \"<file2>\", ...] }\n" +
    "If the command fails or returns no output, return: { \"changed_files\": [] }",
    { agentType: "status-checker", label: "step-3-changed-files", phase: "Step 3" }
  )

  const parsedCf = parsedOr(() => parseAgentJson(changedFilesResult, { stage: "step-3-changed-files", agent: "status-checker" }), {}, "triage will use empty changed_files list");
  const changedFiles = Array.isArray(parsedCf.changed_files) ? parsedCf.changed_files : [];

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
  let recoveredBaselineFailures = null;

  if (baselineFailures === null && postMergeFailures.length > 0) {
    log(
      `[finalize-feature] step 3: baseline unavailable — attempting targeted rerun of ` +
      `${postMergeFailures.length} failing test ID(s) against origin/main HEAD (FIN-100c-4).`
    );

    // Deploy shims before rerun (build parity with Step 0): the helper runs build.py in the scratch workspace first.
    // BO-4300a-1-ia: the same helper as Step 0 -- a scratch workspace from the maker, one pytest run of ONLY the
    // failing ids in it, its removal. A reply that is no usable result ends the run; it is never "the rerun ran".
    const recoveryRun = await mainTestRun(baselineSlug + "-recovery", postMergeFailures, "Step 3", "step-3-targeted-rerun");
    if (recoveryRun.status === "declined") {
      return await refusedHalt(3, `targeted rerun step produced no usable answer (${recoveryRun.detail})`,
        "Step 3 (targeted rerun on origin/main) received no usable answer, so whether it ran is unknown: " + recoveryRun.detail);
    }
    const recoveryInfo = { status: recoveryRun.status, recovered_failures: recoveryRun.failures };

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

  // AC-4: an empty or malformed triage reply is ambiguous — conservative blocks_finalization=true, logged
  // as a parse failure so "tests have regressions" stays distinguishable from "triage reply was garbled".
  triageReport = parsedOr(() => parseAgentJson(triageRaw, { stage: "step-3-triage", agent: "test-failure-triage" }), {
    blocks_finalization: true, regressions: postMergeFailures, pre_existing: [],
    summary: "Triage reply was empty or malformed (could not parse JSON) — treating all failures as regressions conservatively. If you believe this is a parse error rather than a real regression, re-run /finalize-feature.",
  }, "treating as blocks_finalization=true (conservative; see note in summary)");

  // Log the triage report to the user for visibility.
  log("[finalize-feature] step 3 triage report: " + JSON.stringify(triageReport, null, 2));

  // Step 3 (halt gate) — Halt-or-continue based on triage_report.blocks_finalization
  //
  // If blocks_finalization is true: HARD EARLY RETURN. Step 4 (PR merge) is
  // structurally unreachable from this point — no escape hatch.
  // If false: pass triage_report forward and continue to step 4.
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
      ...haltRefs(),
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

// Step 3.5 — Pre-merge AC closure (runs on the feature branch, before Step 4)
//
// This step MUST run before the PR merge (step 4) so that ticket status and
// source AC work_status are committed on the feature branch. The PR then
// carries that closure commit to origin/main atomically. Writing closure on
// local main is not possible because main is PR-only (branch protection).

phase('Step 3.5')

narrate("Step 3.5 of 9", 'Closing in-scope tickets and source ACs on the feature branch before merge...')

// Probe: check whether a closure commit already exists on the branch. Scoped to the branch's OWN
// commits (origin/main..HEAD, the same base ref the derive step measures from): an unscoped search
// finds main's earlier closure commits and would skip this step for every branch.
const closureProbeResult = await agent(
  `Run: git -C "${WORKTREE_ROOT}" log --oneline --grep 'chore(tickets): close tickets and source ACs' -1 origin/main..HEAD\n` +
  "Only the command's standard output counts; if the command itself fails, treat the output as empty.\n" +
  "If the output is non-empty (a closure commit already exists on this branch):\n" +
  "  Return: { \"already_committed\": true }\n" +
  "Otherwise:\n" +
  "  Return: { \"already_committed\": false }",
  { agentType: "status-checker", label: "step-3.5-closure-probe", phase: "Step 3.5" }
)

const closureAlreadyCommitted = parsedOr(() => parseAgentJson(closureProbeResult, { stage: "step-3.5-closure-probe", agent: "status-checker" }),
  {}, "assuming not already committed (will re-attempt closure)").already_committed === true;

let step35Outcome = null; // set only on the two executed paths; the skip paths record their own outcome
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
    prAlreadyMergedAtClosure = String(parsedOr(() => parseAgentJson(prClosureStateResult, { stage: "step-3.5-pr-state", agent: "status-checker" }),
      {}, "assuming PR is OPEN").state || "").toUpperCase() === "MERGED";
  }

  if (prAlreadyMergedAtClosure) {
    log("Step 3.5 of 9: [skipped] PR is already merged — pre-merge closure step omitted");
    outcome(`Step 3.5 of ${STEP_COUNT}`, 'skipped: PR already merged — pre-merge closure step omitted');
    skippedSteps.push({
      step: "3.5",
      reason: "PR already merged — pre-merge closure step skipped (AC-5 idempotency)",
    });
  } else {
    const halt35 = async (reason, message, extra) => {
      await cleanupBaselineWorktree();
      outcome(`Step 3.5 of ${STEP_COUNT}`, `halted: ${reason}`);
      return { status: "halted", halted_at_step: "3.5", reason: reason, message: `${message} The PR has NOT been merged.`, ...extra, ...haltRefs(), step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n') };
    };

    // Sub-step A: abort a Step 2 test-merge still in progress (never touches uncommitted edits).
    // The abort is re-checked: a merge that survives it would make the derivation read a half-merged tree.
    const resetReply = await agent(
      "If a merge is in progress in the worktree, abort it; otherwise change nothing.\n" +
      `  Run: git -C "${WORKTREE_ROOT}" rev-parse --verify MERGE_HEAD\n` +
      `  If (and only if) that succeeds, run: git -C "${WORKTREE_ROOT}" merge --abort\n` +
      `  Then check again, run: git -C "${WORKTREE_ROOT}" rev-parse --verify MERGE_HEAD\n` +
      "Return: { \"status\": \"aborted\"|\"no_merge\"|\"still_merging\" } — still_merging when that second check still succeeds.",
      { agentType: "status-checker", label: "step-3.5-reset-merge", phase: "Step 3.5" }
    )
    const resetStatus = parsedOr(() => parseAgentJson(resetReply, { stage: "step-3.5-reset-merge", agent: "status-checker" }), {}, "reset-merge reply unreadable").status;
    if (resetStatus !== "aborted" && resetStatus !== "no_merge") {
      const stillMerging = resetStatus === "still_merging";
      return await halt35(stillMerging ? "merge_still_in_progress" : "merge_state_unknown", stillMerging
        ? "A merge is still in progress in the worktree after the abort, so the closable set cannot be worked out from a clean branch state. Nothing was closed. Resolve or abort the merge by hand and re-run /finalize-feature."
        : "Could not confirm that no merge is in progress in the worktree (the reset reply was unreadable or unrecognised). Nothing was closed. Check `git status`, then re-run /finalize-feature.", {});
    }

    // BO-400e-3-ii..-viii: the closable set is COMPUTED by finalize_closable_set.py, never selected
    // by prose handed to an agent. This step dispatches the script and reads its reply. The script
    // closes a ticket only through set_ticket_status.py --status done (the one writer of the finished
    // state, ADR-047) and its source AC only through mark_ac_done.py; a non-zero exit is REFUSED, the
    // ticket is not closed and its AC is left open.
    const CLOSER_CLI = `python3 ${WORKTREE_ROOT}/{{config.output_root}}/scripts/build_orchestration/finalize_closable_set.py`;
    const runCloser = async (label, subcommand) => {
      const raw = await agent(
        JSON.stringify({ step: label, command: `${CLOSER_CLI} ${subcommand}`, target: { workspace: WORKTREE_ROOT, branch: BRANCH, ac_id: "none" } }),
        { agentType: "command-step-runner", label, phase: "Step 3.5" }
      );
      const ctx = { stage: label, agent: "command-step-runner" };
      const reply = parsedOr(() => parseAgentJson(raw, ctx), null, `${label} reply unreadable`);
      // Only a runner reply that exited 0 with a string stdout is read; never the raw reply object
      // itself (a failed or shapeless run must not be parsed as the closer's answer).
      if (!reply || typeof reply !== "object" || reply.exit_status !== 0 || typeof reply.stdout !== "string") return null;
      const body = parsedOr(() => parseAgentJson(reply.stdout, ctx), null, `${label} output unreadable`);
      return body && typeof body === "object" ? body : null;
    };

    const derived = await runCloser("step-3.5-derive-set", `derive --worktree ${WORKTREE_ROOT} --branch ${BRANCH} --base-ref origin/main`);
    if (!derived || !["closable", "nothing_to_close", "undeterminable"].includes(derived.outcome)) {
      return await halt35("closable_set_unreadable", "Could not work out which tickets and acceptance criteria this branch may close (the derivation reply was unreadable). Nothing was closed. Re-run /finalize-feature.", {});
    }
    if (derived.outcome === "undeterminable") {
      const undeterminableMessages = {
        built_for_unknown: `Finalization could not establish which ticket branch ${BRANCH} was built for, so nothing was closed. Record it with: git config branch.${BRANCH}.leafcutterTicket <ticket path>, then re-run /finalize-feature.`,
        uncommitted_record_changes: `Finalization found uncommitted edits to records it would close (${derived.detail || "no detail"}), most likely left by an earlier halted run, so it cannot tell what is still open. Commit or discard those record edits, then re-run /finalize-feature.`,
        ambiguous_ticket_record: `Branch ${BRANCH} carries more than one built-for-ticket record (${derived.detail || "no detail"}), so nothing was closed. Leave exactly one with: git config --replace-all branch.${BRANCH}.leafcutterTicket <ticket path>, then re-run /finalize-feature.`,
        diff_failed: `Finalization could not list what ${BRANCH} changed because a git call failed (${derived.detail || "no detail"}), so nothing was closed. Fix the repository state and re-run /finalize-feature.`,
      };
      return await halt35(derived.reason_code || "undeterminable", undeterminableMessages[derived.reason_code]
        || `Finalization could not establish where ${BRANCH} left ${derived.base_ref} (no merge base), so nothing was closed. Fix the base ref and re-run /finalize-feature.`, { closure_report: [] });
    }
    if (derived.outcome === "nothing_to_close") {
      completedSteps.push("3.5");
      step35Outcome = (`Nothing to close (${derived.reason_code}): compared against merge base ${derived.merge_base}, no ticket or acceptance criterion of this branch was left open`);
    } else {
      // Person-only gate: only a resume answer from channel "person" is a yes; a live agent reply is never read.
      const gate = await resolveGate("step-3.5-closure-gate", async () => null, args, { branch: BRANCH, set_digest: derived.set_digest },
        { type: "single_choice", options: ["confirm", "decline"], prompt: `Close exactly these records on ${BRANCH} and commit them? (confirm / decline)\n${derived.listing_text}` },
        (args && typeof args === "object" && args.run_id) || `finalize-${BRANCH.replace(/\//g, "-")}`);
      if (gate && gate.status === "paused_awaiting_input") { await cleanupBaselineWorktree(); return gate; }
      // The answer belongs to the set that was shown when the question was asked: a resumed answer is
      // applied only when the re-derived set has the digest stored in the pause record.
      if (gate && gate.action && "record_context" in gate && (gate.record_context || {}).set_digest !== derived.set_digest) {
        return await halt35("closure_set_changed", "The set of records to close changed since the question was asked, so the answer was treated as unanswered and nothing was closed or committed. Re-run /finalize-feature to see the current list.",
          { closure_report: derived.records.map(r => `${r.kind === "ac" ? r.id : r.path} left open`) });
      }
      const byPerson = !!(args && args.resume_answer && args.resume_answer.channel === "person");
      if (!gate || gate.action !== "confirm" || !byPerson) {
        const declined = !!gate && gate.action === "decline" && byPerson;
        return await halt35(declined ? "closure_declined" : "closure_unanswered", declined
          ? "Closure declined by the person: nothing was closed or committed. Re-running /finalize-feature shows the list again."
          : "The closure confirmation was unanswered by a person, so nothing was closed or committed. Re-run /finalize-feature to see the list again.",
          { closure_report: derived.records.map(r => `${r.kind === "ac" ? r.id : r.path} left open`) });
      }
      const closed = await runCloser("step-3.5-close-set", `close --worktree ${WORKTREE_ROOT} --set-file ${derived.set_file}`);
      if (!closed || !Array.isArray(closed.results) || closed.set_digest !== derived.set_digest) {
        return await halt35("closure_not_confirmed", "The closure did not complete: the closer's reply was unreadable or answered for a different set. Nothing was committed, but if the closer ran, some closed records may have been left modified and uncommitted in the worktree: check `git status`, and commit or discard them before re-running /finalize-feature.", {});
      }
      const changes = Array.isArray(closed.outside_set_changes) ? closed.outside_set_changes : [];
      const stray = (Array.isArray(closed.out_of_set_paths) ? closed.out_of_set_paths : []).filter(p => !changes.some(c => c.path === p));
      closureReport = closed.results.map(r => `${r.kind === "ac" ? r.id : r.path} ${r.result}${r.reason ? ` — ${r.reason}` : ""}`);
      if (changes.length > 0 || stray.length > 0) {
        return await halt35("closed_outside_set", "A record outside the shown list was changed during the closure; nothing was committed. The closed records were left modified and uncommitted in the worktree: commit or discard them before re-running /finalize-feature.", {
          closure_report: [...closureReport, ...changes.map(c => `${c.path} closed outside its set, outside the shown list: ${c.before} -> ${c.after}`), ...stray.map(p => `${p} changed outside its set, outside the shown list`)],
        });
      }
      const closedTickets = closed.results.filter(r => r.kind === "ticket" && r.result === "closed").map(r => r.path);
      ticketsClosed.push(...closedTickets);
      ticketsClosedPreMerge = closedTickets.length;
      acsClosed = closed.results.filter(r => r.kind === "ac" && r.result === "closed").length;
      acsSkipped = closed.results.filter(r => r.kind === "ac" && r.result !== "closed").length;
      const commitPaths = Array.isArray(closed.commit_paths) ? closed.commit_paths : [];
      let answer = null;
      for (let attempt = 0; commitPaths.length > 0 && attempt < 3; attempt++) {
        const commitReply = await agent(
          "Commit the closed records through the shared commit step, once, in supervised mode. Use no other way of committing.\n" +
          "1. Write this single line to a new temporary message file: chore(tickets): close tickets and source ACs\n" +
          `2. With the working directory set to ${WORKTREE_ROOT}, run: python3 ${WORKTREE_ROOT}/{{config.output_root}}/scripts/commit_changes.py --message-file <that file> --supervised --run ${(args && typeof args === "object" && args.run_id) || BRANCH} ${commitPaths.join(" ")}\n` +
          "3. Return { \"status\": \"<the answer's status>\", \"commit_answer\": <the step's JSON answer exactly as printed> }",
          { agentType: "commit", label: "step-3.5-closure-commit", phase: "Step 3.5" }
        );
        answer = (parsedOr(() => parseAgentJson(commitReply, { stage: "step-3.5-closure-commit", agent: "commit" }), {}, "commit answer unreadable") || {}).commit_answer || null;
        if (!answer || answer.status === "committed" || !String(answer.reason_code || "").startsWith("step_")) break;
      }
      if (commitPaths.length > 0 && (!answer || answer.status !== "committed")) {
        return await halt35("closure_commit_not_committed", `The closing commit was not made (status ${answer ? answer.status : "unreadable"}, reason_code ${answer ? answer.reason_code : "none"}: ${answer ? answer.reason : "no commit answer"}). The closed records were left modified and uncommitted in the worktree: commit or discard them before re-running /finalize-feature.`, { closure_report: closureReport, commit_answer: answer });
      }
      completedSteps.push("3.5");
      step35Outcome = `Closed ${ticketsClosedPreMerge} ticket(s) and ${acsClosed} source AC(s) on the feature branch; ${acsSkipped} AC(s) left open`;
    }

  }
}

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

const SYNC_INDETERMINATE_MESSAGE =
  "Could not confirm the local branch HEAD is on origin, so refusing to merge a possibly-stale head. " +
  `Push the branch manually (git push origin ${BRANCH}) and re-run /finalize-feature. ` +
  "The PR has NOT been merged — no work is lost.";

let syncCheckInfo;
{
  let syncCheckValue;
  try {
    syncCheckValue = parseAgentJson(syncCheckResult, { stage: "pre-step-4-sync-check", agent: "status-checker" });
  } catch (_parseErr) {
    syncCheckValue = null;
  }
  // H-1: Fail closed — an unverified head is never merged.
  if (syncCheckValue === null || syncCheckValue === undefined) {
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: "pre-4",
      reason: "sync_check_indeterminate",
      message: SYNC_INDETERMINATE_MESSAGE,
      ...haltRefs(),
      step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
      action_required: "verify_and_push",
    };
  }
  syncCheckInfo = syncCheckValue;
}

// H-1: any status outside this set is indeterminate → HALT; an unknown status never falls through to Step 4.
const KNOWN_SYNC_STATUSES = new Set(["fetch_failed", "push_failed", "diverged", "pushed", "up_to_date"]);
const syncStatus = (typeof syncCheckInfo.status === "string" ? syncCheckInfo.status : "").toLowerCase();

if (!KNOWN_SYNC_STATUSES.has(syncStatus)) {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: "pre-4",
    reason: "sync_check_indeterminate",
    message: SYNC_INDETERMINATE_MESSAGE,
    ...haltRefs(),
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
    ...haltRefs(),
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
    ...haltRefs(),
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
    ...haltRefs(),
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
    action_required: "resolve_divergence",
  };
}

// H-2: pushed / up_to_date — verify SHAs in JS; the agent's self-reported status word is not trusted alone.
const localSha = (typeof syncCheckInfo.local_sha === "string" ? syncCheckInfo.local_sha : "").trim();
const originSha = (typeof syncCheckInfo.origin_sha === "string" ? syncCheckInfo.origin_sha : "").trim();
const shasMismatch = !localSha || !originSha || localSha !== originSha;
if (syncStatus === "pushed") {
  if (shasMismatch) {
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
      ...haltRefs(),
      step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
      action_required: "verify_and_push",
    };
  }
  log(`[finalize-feature] pre-step-4 sync-check: pushed and SHA-verified (sha=${localSha.slice(0, 8)}). PR head is now current.`);
  completedSteps.push("pre-4-push");
} else if (syncStatus === "up_to_date") {
  if (shasMismatch) {
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: "pre-4",
      reason: "sync_check_indeterminate",
      message: SYNC_INDETERMINATE_MESSAGE,
      ...haltRefs(),
      step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
      action_required: "verify_and_push",
    };
  }
  log(`[finalize-feature] pre-step-4 sync-check: up-to-date and SHA-verified (sha=${localSha.slice(0, 8)}). No push needed.`);
}

// Record the executed-path outcome once, after the step's last dispatch; the skip branches
// and halt35 record their own, so step35Outcome is only set when neither fired (BO-1000b-1-i AC-2).
if (step35Outcome !== null) {
  outcome('Step 3.5 of 9', step35Outcome);
}

// Step 4 — Merge PR to main (destructive — confirmation gate required)
//
// This step runs AFTER the worktree merge (step 2) and test + triage (step 3).
// The gate only shows the confirmation prompt when blocks_finalization === false
// (ensured by the halt in step 3). A defensive guard is included to catch any
// edge case where blocks_finalization is truthy at this point.

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
    ...haltRefs(),
    step_summary: stepOutcomes.map(e => `${e.step}: ${e.outcome}`).join('\n'),
  };
}

// TQ-600a-13-xx: the correctness lane's hold check, recognised by EXACT name only
// (no case-folding, trimming or prefix match) and a failing state.
const POST_MERGE_HOLD_NAME = "Post-merge suite status";
const FAILING_CHECK_STATES = new Set(["FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"]);

/** Pure: split a `gh pr checks` array into the external hold and the branch's own failures. */
function classifyPrChecks(checks) {
  const failing = (Array.isArray(checks) ? checks : []).filter((c) => c && typeof c === "object" &&
    (c.bucket === "fail" || FAILING_CHECK_STATES.has(String(c.state || ""))));
  return {
    hold: failing.find((c) => c.name === POST_MERGE_HOLD_NAME) || null,
    ownFailures: failing.filter((c) => c.name !== POST_MERGE_HOLD_NAME),
  };
}

/** Halt payload for a PR the hold check blocks; records Step 4's one outcome for this path. */
function holdHaltPayload(hold, ownFailures) {
  const held = ownFailures.length === 0;
  const named = (c) => `${c.name} (${c.link || "no link"})`;
  const holdText = `External hold "${hold.name}": ${hold.description || "(no description)"} Link: ${hold.link || "(none)"}`;
  const message = held
    ? `Merge held externally, not by this branch. ${holdText}\n` +
      "The cause is the correctness lane on main, not this branch. The PR has NOT been merged; the worktree and branch are kept. " +
      "Re-run /finalize-feature once the hold lifts. If the hold check itself is broken, only the owner's break-glass procedure (TQ-600a-13-xvii) applies; this workflow never performs it."
    : `Required checks failing on this branch: ${ownFailures.map(named).join("; ")}.\n` +
      `Listed separately, not counted as the branch's own: ${holdText}\nThe PR has NOT been merged.`;
  outcome(`Step 4 of ${STEP_COUNT}`, held ? `halted: PR #${prNumber} held externally by ${hold.name}`
    : `halted: PR #${prNumber} has failing required checks: ${ownFailures.map((c) => c.name).join(", ")}`);
  return {
    status: "halted",
    halted_at_step: 4,
    reason: held ? "held_externally" : "required_checks_failing",
    external_hold: { name: hold.name, state: hold.state, link: hold.link, description: hold.description },
    own_failures: ownFailures,
    message: message,
    ...haltRefs(),
    step_summary: stepOutcomes.map((e) => `${e.step}: ${e.outcome}`).join("\n"),
  };
}

// First probe current PR state to support crash-resume.
const prStateResult = await agent(
  `Run: gh pr view ${prNumber} --json state --jq '.state'\n` +
  "Return ONLY a JSON object: { \"state\": \"OPEN\"|\"MERGED\"|\"CLOSED\" }",
  { agentType: "status-checker", label: "step-4-pr-state", phase: "Step 4" }
)

const prState = parsedOr(() => parseAgentJson(prStateResult, { stage: "step-4-pr-state", agent: "status-checker" }), { state: "OPEN" }, "assuming PR is OPEN");

if ((prState.state || "").toUpperCase() === "MERGED") {
  // PR already merged — skip the merge gate and proceed.
  log("Step 4 of 9: [skipped] PR #" + prNumber + " is already merged — skipping merge gate");
  outcome(`Step 4 of ${STEP_COUNT}`, 'skipped: PR #' + prNumber + ' already merged');
  skippedSteps.push({ step: 4, reason: "PR already merged — skipping step 4" });
} else {
  // TQ-600a-13-xx: one read of the PR's checks, before the user is asked to merge.
  const checksReply = await agent(
    `Run: gh pr checks ${prNumber} --json name,state,bucket,link,description\n` +
    "That command exits non-zero when a check fails or is pending; still return its output. " +
    "Return ONLY the JSON array it printed, verbatim. Do not re-run, wait on, or change anything.",
    { agentType: "status-checker", label: "step-4-pr-checks", phase: "Step 4" }
  );
  const checksParsed = parsedOr(() => parseAgentJson(checksReply, { stage: "step-4-pr-checks", agent: "status-checker" }), [], "treating checks as unreadable (no hold)");
  if (!Array.isArray(checksParsed)) { log("[finalize-feature] step-4-pr-checks reply was not an array — treating as no hold"); }
  const checkVerdict = classifyPrChecks(checksParsed);
  if (checkVerdict.hold) {
    await cleanupBaselineWorktree();
    return holdHaltPayload(checkVerdict.hold, checkVerdict.ownFailures);
  }

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
      // FIX 3: parse raw before reading .status — raw may be an unparsed string (an object passes through).
      const s = parsedOr(() => parseAgentJson(raw, { stage: "step-4-merge-gate", agent: "status-checker" }), {}, "no gate decision").status;
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
  // Only an explicit approval merges; blocked, cancel or anything else halts.
  const _fzAction = _fzGateResult && _fzGateResult.action;
  if (_fzAction !== "ok" && _fzAction !== "approve") {
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: 4,
      reason: "user_declined_merge",
      message: "Finalization halted at merge step. No changes made to main.",
      ...haltRefs(),
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

// Step 5 — Sync local main (resumable). Makes no commits on main: only checkout + pull.

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

const syncInfo = parsedOr(() => parseAgentJson(syncResult, { stage: "step-5-sync-main", agent: "status-checker" }), {}, "HEAD SHA and message will be unknown");
const headSha = (typeof syncInfo.head_sha === "string" ? syncInfo.head_sha.trim() : null) || null;
const headMessage = (typeof syncInfo.head_message === "string" ? syncInfo.head_message.trim() : null) || null;

completedSteps.push(5);

outcome('Step 5 of 9', `Local main synced: HEAD ${headSha || 'unknown'} — ${headMessage || 'message unknown'}`);

// Step 6 — Report untracked pre-existing/flaky failures, then detect scope

phase('Step 6')

narrate("Step 6 of 9", 'Reporting untracked pre-existing and flaky failures, then detecting branch scope...')

// Sub-step 6a: report pre-existing / flaky failures that require manual tracking.
if (triageReport !== null) {
  const triageEntries = Array.isArray(triageReport.triage_report) ? triageReport.triage_report : [];
  // Collect untracked failures so the final summary is accurate.
  for (const entry of triageEntries.filter((e) => e.category === "pre_existing" || e.category === "flaky")) {
    untrackedFailures.push({ testId: entry.test_id || "<unknown test>", category: entry.category || "pre_existing" });
  }
  // Emit one structured report listing all untracked failures.
  log(untrackedFailures.length === 0
    ? "[finalize-feature] step 6a: no pre_existing or flaky entries in triage report — no tracking tickets needed"
    : `[finalize-feature] step 6a: ${untrackedFailures.length} pre-existing/flaky failure(s) detected.\n` +
      `Auto-ticketing is disabled (create-ticket is a workflow, not an agent).\n` +
      `No tracking tickets were created. To track these failures, run /create-ticket for each:\n` +
      untrackedFailures.map(({ testId, category }) => `  - [${category}] ${testId} (failing on main at SHA ${baselineSha || "unknown"})`).join("\n"));
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

const closeInfo = parsedOr(() => parseAgentJson(closeResult, { stage: "step-6-scope-detect", agent: "status-checker" }),
  { tickets_in_scope: [], tickets_done: [], tickets_not_done: [], skipped: false }, "no tickets reported in summary");

// Step 6b is informational only: it never adds to the closed list (BO-400e-3-vi).

if (closeInfo.skipped) {
  outcome(`Step 6 of ${STEP_COUNT}`, 'skipped: scope detection — no in-scope tickets found');
  skippedSteps.push({ step: 6, reason: "Scope detection skipped — no in-scope tickets found" });
} else {
  completedSteps.push(6);
  outcome('Step 6 of 9',
    `Reported ${untrackedFailures.length} untracked pre-existing/flaky failure(s); ` +
    `${Array.isArray(closeInfo.tickets_done) ? closeInfo.tickets_done.length : 0} ticket(s) confirmed done in scope`);
}

// Step 7 — Remove worktree (resumable; confirmation gate delegated to agent)

phase('Step 7')

narrate("Step 7 of 9", 'Removing the feature worktree after finalization is complete...')

const worktreeProbeResult = await agent(
  `Run: git -C "${WORKTREE_ROOT}" worktree list --porcelain\n` +
  `Check if a worktree for WORKTREE_ROOT="${WORKTREE_ROOT}" is listed.\n` +
  "Return ONLY a JSON object: { \"exists\": true|false }",
  { agentType: "status-checker", label: "step-7-worktree-probe", phase: "Step 7" }
)

// AC-4: a malformed probe means exists=true — safer to attempt removal than leave it dangling.
const worktreeProbe = parsedOr(() => parseAgentJson(worktreeProbeResult, { stage: "step-7-worktree-probe", agent: "status-checker" }), { exists: true }, "assuming exists=true (conservative)");

if (!worktreeProbe.exists) {
  log("Step 7 of 9: [skipped] Worktree already absent — skipping removal");
  outcome(`Step 7 of ${STEP_COUNT}`, 'skipped: worktree already absent — skipping step 7');
  skippedSteps.push({ step: 7, reason: "Worktree already absent — skipping step 7" });
} else {
  // Dispatch worktree-agent (it owns its own confirmation gate), carrying the INF-700a-5-i announcement.
  const worktreeResult = await agent(
    (await announceUnpublishedLearnings()) +
    `Remove the worktree at ${WORKTREE_ROOT}. ` +
    "If conflict_pids are reported, surface them verbatim and stop. " +
    "Return a JSON object: { \"removed\": true|false, \"conflict_pids\": [] }",
    { agentType: "worktree-agent", label: "step-7-remove-worktree", phase: "Step 7" }
  )
  const wResult = parsedOr(() => parseAgentJson(worktreeResult, { stage: "step-7-remove-worktree", agent: "worktree-agent" }), { removed: false, conflict_pids: [] }, "assuming removed=false, conflict_pids=[]");

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
      ...haltRefs(),
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

// Final — success summary. The cleanup is a no-op unless step 0 degraded and left its worktree.
await cleanupBaselineWorktree();

return {
  status: "ok",
  branch: BRANCH,
  pr_number: prNumber,
  pr_url: prUrl,
  merge_result: mergeResult,
  merge_strategy: mergeStrategy,
  baseline_sha: baselineSha,
  baseline_failures: baselineFailures,
  baseline_run_at: baselineRunAt,
  test_result: testResult,
  triage_report: triageReport,
  tickets_closed: ticketsClosed,
  tickets_closed_pre_merge: ticketsClosedPreMerge,
  acs_closed: acsClosed,
  acs_skipped: acsSkipped,
  closure_report: closureReport,
  // Pre-existing/flaky failures with no tracking ticket (auto-ticketing is disabled).
  untracked_failures: untrackedFailures,
  unpublished_learnings: unpublishedLearnings, // INF-700a-5-i: announced before the removal
  worktree_removed: worktreeRemoved,
  scratch_clearing: scratchClearing,
  completed_steps: completedSteps,
  skipped_steps: skippedSteps,
  step_outcomes: stepOutcomes,
  // Built from stepOutcomes[] so it cannot diverge from what was narrated live (BO-1000b-2).
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
