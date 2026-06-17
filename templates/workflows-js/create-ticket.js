/**
 * create-ticket.js — Claude Code Workflow script
 *
 * Replaces the BA → architect-review agent chain (which violated the
 * depth-1 nesting limit) with a flat sequential/parallel dispatch pattern
 * where every agent call is at depth 1.
 *
 * CONSOLIDATION NOTE (EPIC-AcPipelineConsolidation v2.0.0):
 * test-planner, refinement, and ticket-wiring agents were removed and their
 * responsibilities merged into business-analyst. create-epic was removed as
 * an agent — users must run /create-epic directly for epic-scoped requests.
 *
 * ADR: docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
 * Ticket: EPIC-FlattenSupervisorChain/04_create_ticket_workflow.md
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 * Fallback: for older installs, create-ticket.md prompts the user to use
 * the business-analyst agent directly.
 */

export const meta = {
  name: "create-ticket",
  description:
    "Create a well-formed ticket by sequentially running business-analyst, " +
    "optionally surfacing open questions, then running architect-review — " +
    "all at depth 1.",
  phases: [
    "business-analyst",
    "user-prompt (conditional)",
    "architect-review (conditional)",
  ],
};

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
async function run({ userInput, currentDepth = 1, agent, prompt }) {
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
    // create-epic is no longer a registered agent (removed in
    // EPIC-AcPipelineConsolidation v2.0.0). Users must invoke /create-epic
    // directly. Return an instructional error regardless of depth.
    return {
      status: "error",
      message:
        "This request requires epic-level planning. " +
        "The create-epic agent was removed in v2.0.0. " +
        "Please run /create-epic directly with your request.",
    };
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
  // Step 3 — Spawn architect-review at depth 1 (conditional on BA output)
  //
  // NOTE: test-planner, refinement, and ticket-wiring agents were removed in
  // EPIC-AcPipelineConsolidation v2.0.0. The business-analyst now produces
  // the full ticket draft including test requirements. architect-review runs
  // when the BA output signals architectural impact.
  // -------------------------------------------------------------------------
  const requiresArchReview =
    baResult.requires_architect_review !== false &&
    baResult.routing_decision !== "trivial";

  let architectResult = null;
  if (requiresArchReview) {
    architectResult = await agent({
      agentType: "architect-review",
      input: {
        ba_output: baResult,
        clarifications,
      },
    });
  }

  return {
    status: "ok",
    ticket_path: baResult.ticket_path,
    result: {
      ba_output: baResult,
      architect_output: architectResult,
    },
  };
}
