/**
 * Behavioral harness for the BO-2000e-2 coder-dispatch guard in build-ticket.js.
 *
 * Loads the real workflow script and EXECUTES it against stubbed workflow
 * globals, so the assertions observe actual control flow rather than the
 * presence of a string in the source. A grep-only test cannot tell the fixed
 * guard from the broken one (both mention "Test Requirements" next to
 * "blocker"); this harness can, because it records which phase agents the
 * script actually dispatched.
 *
 * Usage:
 *   node harness_build_ticket_guard.mjs <path-to-build-ticket.js> '<scenario-json>'
 *
 * Scenario JSON:
 *   {
 *     "has_test_requirements": bool,     // what the planner reports
 *     "existing_test_files": [...],      // tests a prior drive left on disk
 *     "phases": ["test-writer", ...],    // agents marked needed, canonical order
 *     "test_writer_result": {...}        // what the test-writer stub returns
 *   }
 *
 * Prints a JSON object: { dispatched: [...], result: <script return value> }
 */
import { readFileSync } from "node:fs";

const [scriptPath, scenarioJson] = process.argv.slice(2);
const scenario = JSON.parse(scenarioJson);

const source = readFileSync(scriptPath, "utf8").replace(
  /^export const meta/m,
  "const meta"
);

const dispatched = [];

/**
 * Stub for the workflow `agent()` global. Routes on the label the script
 * passes, so the harness never has to parse the prompt text.
 */
async function agent(prompt, opts = {}) {
  const label = opts.label || opts.agentType || "unknown";

  if (label === "ticket-planner") {
    return {
      ticket_path: "/fake/worktree/tickets/TICKET-example.md",
      title: "Example ticket",
      files_touched: ["scripts/example.py"],
      has_test_requirements: scenario.has_test_requirements,
      existing_test_files: scenario.existing_test_files || [],
      ordered_phases: scenario.phases.map((a) => ({ agent: a, status: "needed" })),
    };
  }

  // Every other label is a phase agent dispatch — this is what we measure.
  dispatched.push(label);

  if (label === "test-writer") {
    return scenario.test_writer_result;
  }
  return { status: "ok" };
}

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

const run = new AsyncFunction(
  "agent",
  "parallel",
  "pipeline",
  "log",
  "phase",
  "args",
  "budget",
  "workflow",
  source
);

const result = await run(
  agent,
  async (thunks) => Promise.all(thunks.map((t) => t())),
  async (items) => items,
  () => {},
  () => {},
  {
    ticket_path: "/fake/worktree/tickets/TICKET-example.md",
    // Supplying worktree_path makes the script trust the caller and skip the
    // ambient git check, so the harness never shells out.
    worktree_path: "/fake/worktree",
  },
  { total: null, spent: () => 0, remaining: () => Infinity },
  async () => ({})
);

console.log(JSON.stringify({ dispatched, result }));
