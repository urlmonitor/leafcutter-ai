/**
 * build-ticket.js — Claude Code Workflow script
 *
 * Replaces the ticket-supervisor LLM agent for the ticket-driving loop.
 * Converts the recursive agent chain (ticket-supervisor → phase agents)
 * into a deterministic JavaScript workflow where every phase agent is
 * dispatched as a flat depth-1 agent() call.
 *
 * Architecture:
 *   1. Planner agent (depth 1) reads ticket frontmatter → ordered_phases JSON
 *   2. Sequential loop: iterate ordered_phases, skip non-needed, dispatch each
 *   3. Failure detection: blocker result → failure-classifier agent (depth 1)
 *   4. failure-classifier returns: mechanical | cross_agent | design | halt
 *   5. Retry up to MAX_RETRIES for mechanical; skip for cross_agent;
 *      halt + structured error for design / halt
 *
 * ADR: docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
 * Diagram: docs/architecture/components/build-ticket-workflow-dispatch.md
 * Ticket: EPIC-FlattenSupervisorChain/02_build_ticket_workflow.md
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 * Fallback: for older installs, ticket-supervisor.md is used instead.
 */

export const meta = {
  name: "build-ticket",
  description:
    "Drive a single ticket's phase agents from needed to fully signed-off. " +
    "Uses a planner agent to read ticket frontmatter and return the ordered " +
    "phase list, then dispatches each needed phase as a flat depth-1 agent() " +
    "call. Handles failure adjudication via failure-classifier: mechanical " +
    "failures are retried; cross-agent blockers are skipped; design/halt " +
    "blockers surface a structured error to the user.",
  phases: [
    "status-checker (reads ticket frontmatter → ordered_phases)",
    "phase agents (sequential, depth 1)",
    "brainstorm-lead (conditional, on blocker result)",
  ],
};

/**
 * Maximum number of retry attempts for a single phase agent on a mechanical
 * failure. Must be > 0 (at least one retry allowed) and <= 3 (prevents
 * runaway loops). Ticket spec: MAX_RETRIES = 2.
 */
const MAX_RETRIES = 2;

/**
 * Canonical phase ordering for build-ticket dispatch.
 * Agents must appear in this priority order (lower index = runs first).
 * Source: building-epics SKILL.md canonical phase ordering table.
 *
 * Agents not listed here run after all listed agents at their YAML
 * declaration position (fallback: alphabetical).
 */
const phaseOrder = [
  "status-checker",              // priority 1
  "adr-author",                  // priority 2
  "architecture-diagram-author", // priority 3
  "architect-review",            // priority 4
  "test-writer",                 // priority 5
  "python-coder",                // priority 6
  "sql-coder",                   // priority 7
  "sql-query",                   // priority 7
  "frontend-coder",              // priority 8
  "test-runner",                 // priority 9
  "change-scope-reviewer",       // priority 10
  "documentation-expert",        // priority 10
  "explanation-author",          // priority 10
  "how-to-author",               // priority 10
  "reference-author",            // priority 10
  "pr-reviewer",                 // priority 11
  "user-surface-smoker",         // priority 11.5
  "commit",                      // priority 12
  "pull-request",                // priority 13
];

/**
 * Return the canonical priority index for an agent name.
 * Agents not in phaseOrder get a high index (run last, preserve YAML order).
 *
 * @param {string} agentName
 * @returns {number}
 */
function getPriority(agentName) {
  const idx = phaseOrder.indexOf(agentName);
  return idx === -1 ? phaseOrder.length : idx;
}

/**
 * Sort an array of phase objects by canonical priority, preserving
 * relative YAML declaration order for ties (stable sort).
 *
 * @param {Array<{agent: string, status: string}>} phases
 * @returns {Array<{agent: string, status: string}>}
 */
function sortByCanonicalPriority(phases) {
  return [...phases].sort(
    (a, b) => getPriority(a.agent) - getPriority(b.agent)
  );
}

/**
 * Main entry point called by the Claude Code workflow runtime.
 *
 * @param {object} params
 * @param {string} params.userInput  - The ticket_path passed via $ARGUMENTS.
 * @param {Function} params.agent    - Runtime-provided agent dispatch function.
 */
async function run({ userInput, agent }) {
  const ticketPath = userInput.trim();

  if (!ticketPath) {
    return {
      status: "error",
      message:
        "No ticket_path provided. Usage: /build-feature <ticket_path>",
    };
  }

  // -------------------------------------------------------------------------
  // Step 0 — Worktree guard: refuse to run on the main clone
  // -------------------------------------------------------------------------
  // A git worktree's .git is a file (containing a gitdir: pointer); in the
  // main clone .git is a directory. Running implementation work on main risks
  // corrupting the shared working tree.
  const worktreeCheck = await agent({
    agentType: "status-checker",
    input: {
      instructions:
        "Run these two shell commands and report the results as JSON:\n" +
        "1. `test -f .git && echo file || echo directory` — determines if .git is a file (worktree) or directory (main clone)\n" +
        "2. `git branch --show-current` — reports the current branch name\n" +
        "Return ONLY a JSON object: { \"git_type\": \"file\"|\"directory\", \"branch\": \"<name>\" }",
    },
  });

  let gitInfo;
  try {
    gitInfo =
      typeof worktreeCheck === "string"
        ? JSON.parse(worktreeCheck)
        : worktreeCheck;
  } catch (err) {
    gitInfo = { git_type: "unknown", branch: "unknown" };
  }

  if (gitInfo.git_type === "directory" || gitInfo.branch === "main" || gitInfo.branch === "master") {
    return {
      status: "error",
      worktree_required: true,
      message:
        "build-ticket.js must run inside a git worktree, not the main clone. " +
        "The current working directory has .git as a " + gitInfo.git_type +
        " (branch: " + gitInfo.branch + "). " +
        "Create a worktree first:\n" +
        "  /worktree create <branch-name>\n" +
        "Then re-run /build-feature from inside the worktree.",
      action_required: "create_worktree",
    };
  }

  // -------------------------------------------------------------------------
  // Step 1 — Planner: read ticket frontmatter → ordered_phases JSON
  // -------------------------------------------------------------------------
  // The workflow script cannot read files directly. The status-checker agent
  // reads the ticket frontmatter and returns a structured JSON plan.
  const plannerResult = await agent({
    agentType: "status-checker",
    input: {
      ticket_path: ticketPath,
      instructions:
        "Read the ticket at ticket_path. Extract the agents: map from the " +
        "frontmatter and the files_touched list. Return a JSON object with " +
        "exactly these keys: " +
        '{ "ticket_path": "<path>", "title": "<ticket title>", ' +
        '"files_touched": ["..."], ' +
        '"ordered_phases": [{"agent": "<name>", "status": "<status>"}, ...] } ' +
        "The ordered_phases array must list ALL agents from the agents: map, " +
        "in canonical phase priority order (status-checker first, pull-request last). " +
        "Each entry must include the agent name and its current status from the file " +
        "(needed | signed_off | not_needed | failed). " +
        "Return ONLY the JSON object, no prose.",
    },
  });

  // Parse the planner output.
  let plan;
  try {
    plan =
      typeof plannerResult === "string"
        ? JSON.parse(plannerResult)
        : plannerResult;
  } catch (err) {
    return {
      status: "error",
      message:
        `Planner agent returned unparseable output: ${err.message}. ` +
        `Raw output: ${JSON.stringify(plannerResult)}`,
    };
  }

  const orderedPhases = plan.ordered_phases || [];
  const filesTouched = plan.files_touched || [];
  const title = plan.title || ticketPath;

  // -------------------------------------------------------------------------
  // Step 2 — Guard: if no phases are needed, exit cleanly
  // -------------------------------------------------------------------------
  const neededPhases = sortByCanonicalPriority(
    orderedPhases.filter((p) => p.status === "needed")
  );

  if (neededPhases.length === 0) {
    return {
      status: "ok",
      message: `No phases to run for ticket "${title}". All agents are already signed_off or not_needed.`,
      ticket_path: ticketPath,
    };
  }

  // -------------------------------------------------------------------------
  // Step 3 — Sequential phase loop
  // -------------------------------------------------------------------------
  // Track retry counts per phase to enforce MAX_RETRIES cap.
  const retryCounts = {};

  // We iterate neededPhases but the planner may return stale state if a
  // previous run partially completed. Phases already signed_off are skipped
  // by the status filter above, so crash-resume is automatic.

  const completedPhases = [];
  const skippedPhases = [];

  for (const phase of neededPhases) {
    const phaseName = phase.agent;
    retryCounts[phaseName] = retryCounts[phaseName] || 0;

    let phaseResult;
    let retryLoop = true;

    while (retryLoop) {
      retryLoop = false; // default: don't loop unless mechanical retry fires

      // Dispatch the phase agent at depth 1 (dynamic: agentType is phaseName variable).
      phaseResult = await agent({
        agentType: phaseName,
        input: {
          ticket_path: ticketPath,
          files_touched: filesTouched,
        },
      });

      // ------------------------------------------------------------------
      // Step 4 — Failure detection
      // ------------------------------------------------------------------
      const resultStatus =
        phaseResult && (phaseResult.status || phaseResult.result_status);

      if (resultStatus === "blocker" || resultStatus === "failed") {
        // Invoke brainstorm-lead to classify the blocker type.
        const classifyResult = await agent({
          agentType: "brainstorm-lead",
          input: {
            ticket_path: ticketPath,
            failing_phase: phaseName,
            blocker_detail: phaseResult,
            retry_count: retryCounts[phaseName],
            max_retries: MAX_RETRIES,
          },
        });

        const classification =
          classifyResult && classifyResult.classification;

        // ----------------------------------------------------------------
        // Step 5 — Branch on classification
        // ----------------------------------------------------------------
        if (classification === "mechanical") {
          // Retry the phase agent up to MAX_RETRIES times.
          if (retryCounts[phaseName] < MAX_RETRIES) {
            retryCounts[phaseName] += 1;
            retryLoop = true; // re-enter while loop
            continue;
          } else {
            // Retry cap exhausted — surface error and halt.
            return {
              status: "blocked",
              message:
                `Phase '${phaseName}' failed with a mechanical blocker and ` +
                `exhausted retry cap (MAX_RETRIES=${MAX_RETRIES}). ` +
                `Manual intervention required.`,
              ticket_path: ticketPath,
              failing_phase: phaseName,
              blocker_detail: phaseResult,
              classification: "mechanical",
            };
          }
        } else if (classification === "cross_agent") {
          // Log the blocker, skip the agent, and continue to the next phase.
          skippedPhases.push({
            agent: phaseName,
            reason: "cross_agent blocker — phase skipped per protocol",
            blocker_detail: phaseResult,
          });
          // Break out of the while loop to advance to next phase.
          break;
        } else if (classification === "design" || classification === "halt") {
          // Terminal: emit structured error and stop the workflow.
          return {
            status: "blocked",
            message:
              `Phase '${phaseName}' returned a '${classification}' blocker that ` +
              `requires user intervention. The workflow has stopped.`,
            ticket_path: ticketPath,
            failing_phase: phaseName,
            blocker_detail: phaseResult,
            classification,
            suggested_action:
              classification === "design"
                ? "Review the design question in the ticket's ## Comments section and provide guidance before re-running /build-feature."
                : "Inspect the ticket's ## Comments section for the blocker details. Manual resolution is required before re-running.",
          };
        } else {
          // Unknown classification — treat as halt.
          return {
            status: "blocked",
            message:
              `Phase '${phaseName}' failed and failure-classifier returned ` +
              `unknown classification '${classification}'. Treating as halt.`,
            ticket_path: ticketPath,
            failing_phase: phaseName,
            blocker_detail: phaseResult,
            classification: classification || "unknown",
          };
        }
      }

      // Phase completed successfully (or was not a blocker).
      completedPhases.push({ agent: phaseName, result: phaseResult });
    }
  }

  // -------------------------------------------------------------------------
  // Step 6 — Return success summary
  // -------------------------------------------------------------------------
  return {
    status: "ok",
    ticket_path: ticketPath,
    title,
    completed_phases: completedPhases.map((p) => p.agent),
    skipped_phases: skippedPhases.map((p) => ({
      agent: p.agent,
      reason: p.reason,
    })),
    message:
      `Ticket "${title}" driven to completion. ` +
      `${completedPhases.length} phase(s) completed` +
      (skippedPhases.length > 0
        ? `, ${skippedPhases.length} skipped (cross_agent blockers).`
        : "."),
  };
}
