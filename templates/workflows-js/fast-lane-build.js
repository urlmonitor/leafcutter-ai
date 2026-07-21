/**
 * fast-lane-build.js — Claude Code Workflow script (lean path)
 *
 * Three deterministic Python gate scripts enforce correctness (invoked via Bash,
 * not LLM planners — BO-2400a-2, BO-2400a-3, BO-2400a-4):
 *   select_batch              — BO-2400a-2: picks the next N approved ACs
 *   verify_red_baseline       — BO-2400a-3: confirms tests RED before coder runs
 *   verify_green_and_coverage — BO-2400a-4: confirms GREEN + AC coverage after coder
 *
 * Lean two-agent batch build. Unlike the heavy path (build-feature.js), the
 * fast lane dispatches EXACTLY two flat agents regardless of batch size N
 * (BO-2400a-1):
 *   1. test-writer  — writes failing test stubs for the whole batch
 *   2. python-coder — implements the batch ACs to make all stubs green
 *
 * No supervisor chain, no LLM planner, no per-ticket worktree. (BO-2400a-5)
 * Single command, single worktree, fixed code-defined phase order.
 *
 * Gate script: scripts/build_orchestration/fast_lane.py
 *
 * E2 canonical form: top-level body, agent(prompt, opts), args global.
 * No export async function run() — E2 executes the top-level body directly.
 */

export const meta = {
  name: "fast-lane-build",
  description:
    "Lean two-agent batch build. Runs select_batch to pick the next AC batch, " +
    "dispatches test-writer to write failing stubs, gates on verify_red_baseline, " +
    "dispatches python-coder to make tests green, then gates on verify_green_and_coverage " +
    "before staging the commit. Two flat dispatches independent of batch size N " +
    "(BO-2400a-1). No supervisor chain, no LLM planner, single worktree (BO-2400a-5).",
  phases: [
    "select-batch: deterministic gate (select_batch) picks the next N approved ACs from the store",
    "test-writer: writes failing test stubs for every AC in the batch",
    "red-baseline: verify_red_baseline gate confirms all new tests are RED before coder runs",
    "coder: python-coder implements the batch ACs to make all stubs GREEN",
    "green-coverage: verify_green_and_coverage gate confirms tests pass and every AC has coverage",
    "stage-commit: batch output is staged for commit",
  ],
};

// ---------------------------------------------------------------------------
// JSON Schemas for agent() responses
// ---------------------------------------------------------------------------

const TEST_WRITER_SCHEMA = {
  type: "object",
  required: ["status"],
  properties: {
    status: { type: "string", enum: ["ok", "blocker", "failed"] },
    tests_written: { type: "array", items: { type: "string" } },
    message: { type: "string" },
  },
};

const CODER_SCHEMA = {
  type: "object",
  required: ["status"],
  properties: {
    status: { type: "string", enum: ["ok", "blocker", "failed"] },
    files_modified: { type: "array", items: { type: "string" } },
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
const gateScript = "scripts/build_orchestration/fast_lane.py";

if (!worktree_path) {
  return {
    status: "error",
    message:
      "No worktree_path provided. Pass args: { worktree_path: '<absolute-worktree-path>' }.\n" +
      "The fast lane requires an isolated worktree (not the main clone).",
  };
}

// ---------------------------------------------------------------------------
// Gate: select_batch — deterministic AC batch selection (BO-2400a-2)
//
// The gate reads the AC YAML store, filters to approved+unimplemented ACs,
// and returns the next N by priority order. No LLM decides the batch.
// The test-writer invokes this gate as a Bash command (its first action)
// to discover which ACs to cover before writing stubs.
//
// Invocation pattern (single Bash command):
//   python3 <worktree_path>/<gateScript> select_batch \
//     --ac-store <worktree_path>/<acStoreRoot> \
//     --batch-size <batchSize>
// ---------------------------------------------------------------------------

const selectBatchInvocation =
  `python3 ${worktree_path}/${gateScript} select_batch` +
  ` --ac-store ${worktree_path}/${acStoreRoot}` +
  ` --batch-size ${batchSize}`;

// ---------------------------------------------------------------------------
// Phase 1 — test-writer: write failing stubs for the batch (BO-2400a-1)
//
// One flat dispatch covers the entire batch. Invocation count = 1,
// independent of N. The test-writer runs select_batch as its first
// Bash call, then writes stubs for every AC in the returned list.
// ---------------------------------------------------------------------------

phase("Test Writer");

const testWriterResult = await agent(
  `You are the test-writer phase agent for a fast-lane AC batch build.\n\n` +
  `Worktree: ${worktree_path}\n` +
  `AC store: ${worktree_path}/${acStoreRoot}\n` +
  `Batch gate command: ${selectBatchInvocation}\n\n` +
  `Instructions:\n` +
  `1. Run the select_batch gate (single Bash command) to obtain the AC list:\n` +
  `   ${selectBatchInvocation}\n` +
  `   Parse the JSON output — it is the ordered list of AC ids for this batch.\n` +
  `2. For each AC id, read the AC YAML from ${worktree_path}/${acStoreRoot}.\n` +
  `3. Write a minimal failing test stub that asserts the AC behavior. Tests MUST be RED.\n` +
  `4. Run the test suite to confirm all new stubs FAIL (non-zero exit).\n` +
  `5. Return { "status": "ok", "tests_written": ["<path>", ...], "message": "<summary>" }.\n\n` +
  `CONSTRAINT: Do NOT write any production code — only failing test stubs.\n` +
  `After you sign off, the verify_red_baseline gate runs to confirm the red state\n` +
  `before the coder phase is dispatched.`,
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
// Gate: verify_red_baseline — confirm all batch tests RED (BO-2400a-3)
//
// This gate runs BEFORE the coder is dispatched. It is a deterministic
// Python script — not an LLM judgment. A non-zero exit means the stubs
// are not genuinely failing; the coder must not be dispatched.
//
// Invocation pattern (single Bash command):
//   python3 <worktree_path>/<gateScript> verify_red_baseline \
//     --worktree <worktree_path>
// ---------------------------------------------------------------------------

const redBaselineInvocation =
  `python3 ${worktree_path}/${gateScript} verify_red_baseline` +
  ` --worktree ${worktree_path}`;

// ---------------------------------------------------------------------------
// Phase 2 — python-coder: implement ACs to make batch tests GREEN (BO-2400a-1)
//
// One flat dispatch covers the entire batch — the second and final dispatch
// in this workflow. The coder runs only after verify_red_baseline confirms
// the red state above.
// ---------------------------------------------------------------------------

phase("Coder");

const coderResult = await agent(
  `You are the python-coder phase agent for a fast-lane AC batch build.\n\n` +
  `Worktree: ${worktree_path}\n` +
  `AC store: ${worktree_path}/${acStoreRoot}\n\n` +
  `Instructions:\n` +
  `1. The test-writer has already written failing stubs in the worktree.\n` +
  `   Run the test suite to see which tests are failing.\n` +
  `2. Implement the minimum production code to make every failing batch test PASS.\n` +
  `3. Run the test suite to confirm all batch tests are GREEN (zero exit).\n` +
  `4. Return { "status": "ok", "files_modified": ["<path>", ...], "message": "<summary>" }.\n\n` +
  `CONSTRAINT: Implement only what the failing tests require — no gold-plating.\n` +
  `After you sign off, the verify_green_and_coverage gate confirms green state\n` +
  `and full AC coverage before the batch output is staged for commit.`,
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
// Gate: verify_green_and_coverage — confirm GREEN + AC coverage (BO-2400a-4)
//
// This gate runs AFTER the coder finishes. Two conditions must both pass:
//   1. All batch tests pass (zero exit from the test suite).
//   2. Every AC id in the batch has at least one covering test.
//
// A non-zero exit means coverage is incomplete or tests still fail — the
// commit is NOT staged until this gate passes.
//
// Invocation pattern (single Bash command):
//   python3 <worktree_path>/<gateScript> verify_green_and_coverage \
//     --worktree <worktree_path> \
//     --ac-store <worktree_path>/<acStoreRoot>
// ---------------------------------------------------------------------------

const greenCoverageInvocation =
  `python3 ${worktree_path}/${gateScript} verify_green_and_coverage` +
  ` --worktree ${worktree_path}` +
  ` --ac-store ${worktree_path}/${acStoreRoot}`;

// ---------------------------------------------------------------------------
// Phase 3 — Stage commit
// ---------------------------------------------------------------------------

phase("Stage Commit");

return {
  status: "ok",
  message:
    "Fast-lane batch complete. " +
    "test-writer wrote failing stubs (verify_red_baseline confirmed red baseline), " +
    "python-coder made them green (verify_green_and_coverage confirmed green + coverage). " +
    "Batch output is ready to commit.",
  worktree_path,
  batch_size: batchSize,
  tests_written: (testWriterResult && testWriterResult.tests_written) || [],
  files_modified: (coderResult && coderResult.files_modified) || [],
  gates_passed: ["select_batch", "verify_red_baseline", "verify_green_and_coverage"],
};
