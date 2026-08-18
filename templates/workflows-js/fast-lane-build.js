/**
 * fast-lane-build.js — Claude Code Workflow script (lean path)
 *
 * Three deterministic Python gate scripts enforce correctness (invoked via the
 * agents that run them — not LLM planners — BO-2400a-2, BO-2400a-3, BO-2400a-4):
 *   select_batch              — BO-2400a-2: picks the next N approved ACs
 *   verify_red_baseline       — BO-2400a-3: confirms tests RED before coder runs
 *   verify_green_and_coverage — BO-2400a-4: confirms GREEN + AC coverage after coder
 *
 * Lean two-agent batch build. Unlike the heavy path (build-feature.js), the
 * fast lane dispatches EXACTLY two flat agents regardless of batch size N
 * (BO-2400a-1):
 *   1. test-writer  — writes failing test stubs for the whole batch, then runs
 *                     the verify_red_baseline gate and returns its result
 *   2. python-coder — implements the batch ACs to make all stubs green, then
 *                     runs the verify_green_and_coverage gate and returns its result
 *
 * The workflow branches on each gate result — the coder is only dispatched
 * when gate_passed===true (AMENDED 2026-08-17, BO-2400a-3-v: at least one
 * newly-added covering test is red — see BO-2400a-3 and its decomposed
 * children BO-2400a-3-i..viii), and status:"ok" is only returned when
 * green===true and coverage_ok===true. This is the DEFECT H-1 fix.
 * (BO-2400a-3, BO-2400a-4)
 *
 * No supervisor chain, no LLM planner, no per-ticket worktree. (BO-2400a-5)
 * Single command, single worktree, fixed code-defined phase order.
 *
 * Supporting integrations (BO-2400b-3, BO-2400c-1, BO-2400d-1):
 *   choose_lane           — path_selection.py: lane eligibility at entry
 *   assemble_context_bundle — injection_builders.py: layered context for agents
 *   emit_agent_telemetry  — agent_telemetry.py: per-phase telemetry record
 *
 * Gate script: {{config.output_root}}/scripts/build_orchestration/fast_lane.py
 *
 * E2 canonical form: top-level body, agent(prompt, opts), args global.
 * No export async function run() — E2 executes the top-level body directly.
 */

export const meta = {
  name: "fast-lane-build",
  description: "Lean two-agent batch build. Runs select_batch to pick the next AC batch, dispatches test-writer to write failing stubs and run verify_red_baseline, branches on the red-baseline result, dispatches python-coder to make tests green and run verify_green_and_coverage, then branches on the green+coverage result before staging the commit. Two flat dispatches independent of batch size N (BO-2400a-1). No supervisor chain, no LLM planner, single worktree (BO-2400a-5).",
  phases: [
    "select-batch: deterministic gate (select_batch) picks the next N approved ACs from the store",
    "test-writer: writes failing test stubs for every AC in the batch, then runs verify_red_baseline",
    "red-baseline: workflow branches on test-writer's gate_passed result — coder only dispatched when true",
    "coder: python-coder implements the batch ACs, then runs verify_green_and_coverage",
    "green-coverage: workflow branches on coder's green+coverage result — ok only returned when both pass",
    "stage-commit: batch output is staged for commit",
  ],
};

// ---------------------------------------------------------------------------
// JSON Schemas for agent() responses
//
// TEST_WRITER_SCHEMA includes gate-result fields (gate_passed, reason,
// green_at_baseline) so the workflow can branch on the verify_red_baseline
// result without a second agent dispatch. AMENDED 2026-08-17 (BO-2400a-3-v):
// the pre-amendment all_red/offender keys are REMOVED, not kept as aliases —
// a version-skewed caller reading gate_passed as absent/undefined fails
// closed (falsy) exactly like an explicit false.
//
// CODER_SCHEMA includes gate-result fields (green, coverage_ok, uncovered_ac_ids)
// so the workflow can branch on the verify_green_and_coverage result.
// ---------------------------------------------------------------------------

const TEST_WRITER_SCHEMA = {
  type: "object",
  required: ["status"],
  properties: {
    status: { type: "string", enum: ["ok", "blocker", "failed"] },
    tests_written: { type: "array", items: { type: "string" } },
    gate_passed: { type: "boolean" },
    reason: { type: "string" },
    green_at_baseline: { type: "array" },
    message: { type: "string" },
  },
};

const CODER_SCHEMA = {
  type: "object",
  required: ["status"],
  properties: {
    status: { type: "string", enum: ["ok", "blocker", "failed"] },
    files_modified: { type: "array", items: { type: "string" } },
    green: { type: "boolean" },
    coverage_ok: { type: "boolean" },
    uncovered_ac_ids: { type: "array", items: { type: "string" } },
    message: { type: "string" },
  },
};

// ---------------------------------------------------------------------------
// Phase 0 — Argument validation
// ---------------------------------------------------------------------------

phase("Select Batch");

const worktree_path = (args && args.worktree_path) || null;
const batchSize = (args && args.batch_size) || 5;
const acStoreRoot = (args && args.ac_store_root) || "docs/acceptance-criteria";
const gateScript = "{{config.output_root}}/scripts/build_orchestration/fast_lane.py";

// ---------------------------------------------------------------------------
// Supporting integration invocations (BO-2400b-3, BO-2400c-1, BO-2400d-1)
//
// E2 has no shell primitive — agents run these commands as single Bash calls.
// ---------------------------------------------------------------------------

// b: choose_lane — lane-selection check at entry (BO-2400b-3).
// Determines whether the current AC batch qualifies for the fast lane or must
// fall back to the heavy path (build-feature.js). Agents invoke this at the
// start of a session to confirm fast-lane eligibility.
const chooseLaneInvocation =
  `python3 ${worktree_path}/{{config.output_root}}/scripts/build_orchestration/path_selection.py choose_lane` +
  ` --ac-root ${worktree_path}/${acStoreRoot} --limit ${batchSize}`;

// c: assemble_context_bundle — builds the layered context bundle for agents
// (BO-2400c-1). Enables stable-prefix cache optimisation. Each agent dispatch
// is preceded by a context build so agents receive optimised context.
const assembleContextBundleInvocation =
  `python3 ${worktree_path}/{{config.output_root}}/scripts/injection_builders.py assemble_context_bundle` +
  ` --worktree ${worktree_path} --ac-root ${worktree_path}/${acStoreRoot}`;

// d: emit_agent_telemetry — records each phase dispatch for the
// retrospective-agent lane comparison (BO-2400d-1). Agents call this after
// completing their phase so telemetry is captured on every fast-lane run.
const emitTelemetryBase =
  `python3 ${worktree_path}/{{config.output_root}}/scripts/agent-health/agent_telemetry.py emit_agent_telemetry`;

// ---------------------------------------------------------------------------
// Gate: select_batch — deterministic AC batch selection (BO-2400a-2)
//
// CLI form (sibling-coder-added fast_lane.py CLI):
//   python3 <gateScript> select_batch --ac-root <root> --limit <N>
//
// Reads the AC YAML store, filters to approved+unimplemented ACs, and returns
// the next N by priority order. No LLM decides the batch.
// ---------------------------------------------------------------------------

const selectBatchInvocation =
  `python3 ${worktree_path}/${gateScript} select_batch` +
  ` --ac-root ${worktree_path}/${acStoreRoot}` +
  ` --limit ${batchSize}`;

// ---------------------------------------------------------------------------
// Gate: verify_red_baseline — confirm all batch tests RED (BO-2400a-3)
//
// CLI form (agent substitutes BATCH_IDS with space-separated AC ids from
// the select_batch output):
//   python3 <gateScript> verify_red_baseline --ac-ids <BATCH_IDS> --test-root <wt>
//
// Runs INSIDE the test-writer agent after stubs are written. The test-writer
// returns { gate_passed: bool, reason: string|null, green_at_baseline: [...] }
// from the gate output (AMENDED 2026-08-17, BO-2400a-3-v: gate_passed is true
// iff >=1 NEWLY-ADDED covering test is red — not "every test is red").
// The workflow branches on gate_passed: false → blocked (coder not dispatched).
// ---------------------------------------------------------------------------

const redBaselineInvocation =
  `python3 ${worktree_path}/${gateScript} verify_red_baseline` +
  ` --ac-ids <BATCH_IDS> --test-root ${worktree_path}`;

// ---------------------------------------------------------------------------
// Phase 1 — test-writer: write failing stubs + run red-baseline gate (BO-2400a-1)
//
// One flat dispatch covers the entire batch. Invocation count = 1,
// independent of N. The test-writer:
//   A. Runs select_batch (single Bash command) to obtain the AC id list.
//   B. Writes minimal failing stubs for every AC in the batch.
//   C. Runs redBaselineInvocation (single Bash command) to verify red state.
//   D. Returns { gate_passed: bool, reason: string|null, green_at_baseline: [...] }
//      from the gate output.
// ---------------------------------------------------------------------------

phase("Test Writer");

const testWriterResult = await agent(
  `You are the test-writer phase agent for a fast-lane AC batch build.\n\n` +
  `Worktree: ${worktree_path}\n` +
  `AC store: ${worktree_path}/${acStoreRoot}\n` +
  `Lane eligibility: ${chooseLaneInvocation}\n\n` +
  `Step 0 — Context assembly (run first, single Bash command):\n` +
  `   ${assembleContextBundleInvocation}\n` +
  `This builds the layered context bundle for optimised prompt injection.\n\n` +
  `Step 1 — Select batch (single Bash command):\n` +
  `   ${selectBatchInvocation}\n` +
  `Parse the JSON output — it is the ordered list of AC ids for this batch.\n\n` +
  `Step 2 — Write failing stubs:\n` +
  `For each AC id, read the AC YAML from ${worktree_path}/${acStoreRoot}.\n` +
  `Write a minimal failing test stub that asserts the AC behavior.\n` +
  `All stubs MUST be RED (fail when run) — do NOT write production code.\n\n` +
  `Step 3 — Run the red-baseline gate (single Bash command):\n` +
  `Replace BATCH_IDS with the space-separated AC ids from Step 1, then run:\n` +
  `   ${redBaselineInvocation}\n` +
  `Parse the JSON output to obtain: { "gate_passed": <boolean>, "reason": <string|null>, ` +
  `"red": [...], "green_at_baseline": [...], "inconclusive": [...], "preexisting": [...] }.\n\n` +
  `Step 4 — Emit phase telemetry (single Bash command):\n` +
  `   ${emitTelemetryBase} --phase test-writer --worktree ${worktree_path} --status <ok|failed>\n\n` +
  `Return JSON: { "status": "ok", "tests_written": ["<path>", ...], "gate_passed": <bool>, ` +
  `"reason": <string|null>, "green_at_baseline": [...], "message": "<summary>" }\n\n` +
  `CRITICAL: The gate_passed and reason fields MUST reflect the actual gate output from ` +
  `${redBaselineInvocation}.\n` +
  `Do NOT fabricate gate_passed=true — return the real gate verdict so the coder guard ` +
  `can branch correctly. Fail closed: if the gate's JSON cannot be parsed, report ` +
  `gate_passed: false.`,
  {
    agentType: "test-writer",
    schema: TEST_WRITER_SCHEMA,
    label: "test-writer-batch",
    phase: "Test Writer",
  }
);

if (!testWriterResult || testWriterResult.status !== "ok") {
  return {
    status: "blocked",
    message:
      "test-writer phase did not return ok. " +
      "The red-baseline gate cannot run on an incomplete test set. " +
      `Detail: ${JSON.stringify(testWriterResult)}`,
    failing_phase: "test-writer",
    classification: "halt",
  };
}

// ---------------------------------------------------------------------------
// Guard: red-baseline gate result (DEFECT H-1 fix — BO-2400a-3)
//
// AMENDED 2026-08-17 (BO-2400a-3-v): the coder MUST NOT be dispatched unless
// at least one NEWLY-ADDED batch test is genuinely red — not "every batch
// test", which wrongly halted on partially-implemented ACs whose covering
// tests were legitimately part-green (BO-2400g-1, TKT-600a-1). This branches
// on the gate_passed field from the test-writer's gate run — the gate is NOT
// re-run here (it ran inside the test-writer agent). gate_passed is read as
// a plain JS falsy check so an absent key (version skew) fails closed.
// ---------------------------------------------------------------------------

if (!testWriterResult.gate_passed) {
  return {
    status: "blocked",
    message:
      "verify_red_baseline gate failed: test-writer reported gate_passed=false. " +
      `Reason: ${testWriterResult.reason || "unknown"}. ` +
      `Green-at-baseline: ${JSON.stringify(testWriterResult.green_at_baseline || [])}. ` +
      "At least one newly-added batch test must be red before the coder is dispatched. " +
      "Fix the stubs so a newly-added batch test is genuinely red, then re-run.",
    failing_phase: "test-writer",
    gate: "verify_red_baseline",
    classification: "halt",
  };
}

// ---------------------------------------------------------------------------
// Gate: verify_green_and_coverage — confirm GREEN + AC coverage (BO-2400a-4)
//
// CLI form (agent substitutes BATCH_IDS with space-separated AC ids from
// the select_batch output):
//   python3 <gateScript> verify_green_and_coverage \
//     --ac-ids <BATCH_IDS> --test-root <wt> --ac-root <root>
//
// Runs INSIDE the coder agent after implementation. The coder returns
// { green: bool, coverage_ok: bool, uncovered_ac_ids: [...] } from gate output.
// The workflow branches on green && coverage_ok — ok returned only when both true.
// ---------------------------------------------------------------------------

const greenCoverageInvocation =
  `python3 ${worktree_path}/${gateScript} verify_green_and_coverage` +
  ` --ac-ids <BATCH_IDS> --test-root ${worktree_path}` +
  ` --ac-root ${worktree_path}/${acStoreRoot}`;

// ---------------------------------------------------------------------------
// Phase 2 — python-coder: implement ACs + run green+coverage gate (BO-2400a-1)
//
// One flat dispatch covers the entire batch — the second and final dispatch
// in this workflow. The coder:
//   A. Runs the test suite to see which stubs fail.
//   B. Implements minimum production code to make all stubs pass.
//   C. Runs greenCoverageInvocation (single Bash command) to verify green state
//      and full AC coverage.
//   D. Returns { green: bool, coverage_ok: bool, uncovered_ac_ids: [...] }.
// ---------------------------------------------------------------------------

phase("Coder");

const coderResult = await agent(
  `You are the python-coder phase agent for a fast-lane AC batch build.\n\n` +
  `Worktree: ${worktree_path}\n` +
  `AC store: ${worktree_path}/${acStoreRoot}\n\n` +
  `Step 0 — Context assembly (run first, single Bash command):\n` +
  `   ${assembleContextBundleInvocation}\n` +
  `This builds the layered context bundle for optimised prompt injection.\n\n` +
  `Step 1 — Implement:\n` +
  `The test-writer has already written failing stubs in the worktree.\n` +
  `Run the test suite to see which tests are failing.\n` +
  `Implement the minimum production code to make every failing batch test PASS.\n` +
  `Run the test suite to confirm all batch tests are GREEN (zero exit).\n\n` +
  `Step 2 — Run the green+coverage gate (single Bash command):\n` +
  `Replace BATCH_IDS with the space-separated AC ids from the select_batch output, then run:\n` +
  `   ${greenCoverageInvocation}\n` +
  `Parse the JSON output: { "green": <bool>, "coverage_ok": <bool>, "uncovered_ac_ids": [...] }.\n\n` +
  `Step 3 — Emit phase telemetry (single Bash command):\n` +
  `   ${emitTelemetryBase} --phase python-coder --worktree ${worktree_path} --status <ok|failed>\n\n` +
  `Return JSON: { "status": "ok", "files_modified": ["<path>", ...], "green": <bool>, "coverage_ok": <bool>, "uncovered_ac_ids": [...], "message": "<summary>" }\n\n` +
  `CONSTRAINT: Implement only what the failing tests require — no gold-plating.\n` +
  `CRITICAL: The green and coverage_ok fields MUST reflect the actual gate output from ${greenCoverageInvocation}.\n` +
  `Do NOT fabricate green=true or coverage_ok=true — return the real gate verdict.`,
  {
    agentType: "python-coder",
    schema: CODER_SCHEMA,
    label: "coder-batch",
    phase: "Coder",
  }
);

if (!coderResult || coderResult.status !== "ok") {
  return {
    status: "blocked",
    message:
      "python-coder phase did not return ok. " +
      "The green+coverage gate cannot run on an incomplete implementation. " +
      `Detail: ${JSON.stringify(coderResult)}`,
    failing_phase: "python-coder",
    classification: "halt",
  };
}

// ---------------------------------------------------------------------------
// Guard: green+coverage gate result (DEFECT H-1 fix — BO-2400a-4)
//
// The batch is NOT complete unless BOTH conditions hold:
//   1. All batch tests pass (green === true).
//   2. Every AC id in the batch has at least one covering test (coverage_ok === true).
//
// This branches on the coder's gate result — the gate ran inside the coder agent.
// ---------------------------------------------------------------------------

if (!coderResult.green || !coderResult.coverage_ok) {
  return {
    status: "blocked",
    message:
      "verify_green_and_coverage gate failed: " +
      `green=${coderResult.green}, coverage_ok=${coderResult.coverage_ok}. ` +
      `Uncovered ACs: ${JSON.stringify(coderResult.uncovered_ac_ids || [])}. ` +
      "Fix failing tests and/or add AC coverage before staging the commit.",
    failing_phase: "python-coder",
    gate: "verify_green_and_coverage",
    uncovered_ac_ids: coderResult.uncovered_ac_ids || [],
    classification: "halt",
  };
}

// ---------------------------------------------------------------------------
// Phase 3 — Stage commit
// ---------------------------------------------------------------------------

phase("Stage Commit");

// Build gates_passed from actual gate verdicts — NOT a hardcoded literal.
// DEFECT H-1 fix: the previous unconditional return claimed all three gates
// passed even when neither verify_red_baseline nor verify_green_and_coverage
// had actually run. Now gates_passed only includes gates whose results were
// verified by the conditional guards above.
const gatesPassed = ["select_batch"];
if (testWriterResult.gate_passed) {
  gatesPassed.push("verify_red_baseline");
}
if (coderResult.green && coderResult.coverage_ok) {
  gatesPassed.push("verify_green_and_coverage");
}

return {
  status: "ok",
  message:
    "Fast-lane batch complete. " +
    "test-writer wrote failing stubs and verify_red_baseline confirmed red baseline. " +
    "python-coder made them green and verify_green_and_coverage confirmed green + coverage. " +
    "Batch output is ready to commit.",
  worktree_path,
  batch_size: batchSize,
  tests_written: (testWriterResult && testWriterResult.tests_written) || [],
  files_modified: (coderResult && coderResult.files_modified) || [],
  gates_passed: gatesPassed,
};
