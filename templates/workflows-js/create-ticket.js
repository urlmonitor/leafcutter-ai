/**
 * create-ticket.js — Claude Code Workflow script
 *
 * Replaces the BA → test-planner → refinement → architect-review agent chain
 * (which violated the depth-1 nesting limit) with a flat sequential/parallel
 * dispatch pattern where every agent call is at depth 1.
 *
 * ADR: docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
 * Ticket: EPIC-FlattenSupervisorChain/04_create_ticket_workflow.md
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 * Fallback: for older installs, create-ticket.md invokes the agent directly.
 */

export const meta = {
  name: "create-ticket",
  description:
    "Create a well-formed ticket by sequentially running business-analyst, " +
    "optionally surfacing open questions, then running refinement and " +
    "architect-review in parallel — all at depth 1.",
  phases: [
    "business-analyst",
    "user-prompt (conditional)",
    "test-planner",
    "refinement + architect-review (parallel)",
    "ticket-write",
  ],
};

/**
 * Maximum dispatch depth before we refuse to spawn create-epic
 * to avoid re-entering a nesting violation.
 */
const DEPTH_CAP = 3;

/**
 * Main entry point called by the Claude Code workflow runtime.
 *
 * DESIGN NOTE: This workflow intentionally runs on the main branch (no
 * worktree guard). create-ticket is a planning tool — it creates ticket
 * files but does not modify implementation code. Running on main is safe
 * and correct: the ticket file should land directly in tickets/00_inbox/.
 *
 * @param {object} params
 * @param {string} params.userInput  - The raw user request string ($ARGUMENTS).
 * @param {number} [params.currentDepth=1] - Caller's current dispatch depth.
 * @param {Function} params.agent    - Runtime-provided agent dispatch function.
 * @param {Function} params.parallel - Runtime-provided parallel dispatch helper.
 * @param {Function} params.prompt   - Runtime-provided user-prompt helper.
 */
async function run({ userInput, currentDepth = 1, agent, parallel, prompt }) {
  // -------------------------------------------------------------------------
  // Step 1 — Spawn business-analyst at depth 1
  // -------------------------------------------------------------------------
  const baResult = await agent({
    agentType: "business-analyst",
    input: { request: userInput },
  });

  const routingDecision = baResult.routing_decision;

  // -------------------------------------------------------------------------
  // Step 2 — Route on routing_decision
  // -------------------------------------------------------------------------
  if (routingDecision === "epic") {
    // Depth-cap guard: refuse to spawn create-epic if we are already deep.
    if (currentDepth >= DEPTH_CAP) {
      return {
        status: "error",
        message:
          `Depth-cap reached (currentDepth=${currentDepth} >= ${DEPTH_CAP}). ` +
          "Cannot spawn create-epic. Surface this request to the user and ask " +
          "them to run /create-epic directly.",
      };
    }

    // Spawn create-epic at depth 1 with the BA output.
    const epicResult = await agent({
      agentType: "create-epic",
      input: {
        request: userInput,
        ba_output: baResult,
        current_depth: currentDepth + 1,
      },
    });

    return { status: "ok", result: epicResult };
  }

  // routing_decision == "standard_ticket" (default path)
  // -------------------------------------------------------------------------
  // Step 2b — Surface open questions to the user (if any)
  // -------------------------------------------------------------------------
  let clarifications = {};
  if (
    baResult.open_questions &&
    Array.isArray(baResult.open_questions) &&
    baResult.open_questions.length > 0
  ) {
    const questionsText = baResult.open_questions
      .map((q, i) => `${i + 1}. ${q}`)
      .join("\n");

    const userAnswers = await prompt(
      `Before creating the ticket, the business-analyst has the following questions:\n\n` +
        questionsText +
        `\n\nPlease provide your answers (one per question, or type 'skip' to proceed without answers):`
    );

    clarifications = { user_answers: userAnswers };
  }

  // -------------------------------------------------------------------------
  // Step 3 — Spawn test-planner at depth 1 with BA output
  // -------------------------------------------------------------------------
  const tpResult = await agent({
    agentType: "test-planner",
    input: {
      ba_output: baResult,
      clarifications,
    },
  });

  // -------------------------------------------------------------------------
  // Step 4 — Spawn refinement and architect-review in parallel at depth 1
  // -------------------------------------------------------------------------
  const [refinementResult, architectResult] = await parallel([
    agent({
      agentType: "refinement",
      input: {
        ba_output: baResult,
        tp_output: tpResult,
        clarifications,
      },
    }),
    agent({
      agentType: "architect-review",
      input: {
        ba_output: baResult,
        tp_output: tpResult,
        clarifications,
      },
    }),
  ]);

  // -------------------------------------------------------------------------
  // Step 5 — Assemble and write the ticket file via ticket-wiring agent
  // -------------------------------------------------------------------------
  const ticketResult = await agent({
    agentType: "ticket-wiring",
    input: {
      ba_output: baResult,
      tp_output: tpResult,
      refinement_output: refinementResult,
      architect_output: architectResult,
      original_request: userInput,
    },
  });

  return {
    status: "ok",
    ticket_path: ticketResult.ticket_path,
    result: ticketResult,
  };
}
