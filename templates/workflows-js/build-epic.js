/**
 * build-epic.js — Claude Code Workflow script
 *
 * Replaces the epic-supervisor LLM agent and the inline batching prose
 * from /build-feature (ADR-006 §C). Converts the epic orchestration layer
 * from recursive agent calls to a deterministic JavaScript workflow that
 * reads an epic's dependency graph and drives dependency-ordered batches,
 * dispatching tickets within each batch via the parallel runtime call.
 *
 * Architecture:
 *   1. Planner agent (depth 1) reads Master_Plan.md + all sub-ticket
 *      frontmatter → returns dependency-ordered batches JSON
 *   2. Sequential batch loop: iterate batches in order
 *   3. Within each batch, dispatch all tickets via the parallel runtime call
 *      — each parallel slot calls workflow("build-ticket", { ticket_path })
 *   4. Batch-level failure detection: if any ticket halts, stop the outer
 *      batch loop and surface a structured error to the user
 *   5. Already-done tickets are omitted by the planner (resume mechanism)
 *
 * After build-epic.js ships, /build-feature becomes a thin wrapper:
 * it detects epic vs. single-ticket path and routes to build-epic.js or
 * build-ticket.js respectively.
 *
 * ADR: docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
 * Diagram: docs/architecture/components/build-epic-workflow-dispatch.md
 * Ticket: EPIC-FlattenSupervisorChain/03_build_epic_workflow.md
 * Depends on: build-ticket.js (ticket 02)
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support, parallel dispatch)
 * Fallback: for older installs, use the inline batching prose from
 *   build-feature.md ADR-006 §C.
 */

export const meta = {
  name: "build-epic",
  description:
    "Drive a full epic from Master_Plan.md through to all tickets completed. " +
    "Uses a planner agent to read the epic's dependency graph and return " +
    "dependency-ordered batches. Iterates batches sequentially; within each " +
    "batch, tickets run via the parallel runtime call — each slot calls the build-ticket " +
    "workflow logic. Already-done tickets are omitted by the planner, enabling " +
    "crash-resume. A halt from any ticket in a batch stops the outer loop " +
    "and surfaces a structured error. No Agent tool nesting exceeds depth 1.",
  phases: [
    "planner agent (depth 1 — reads Master_Plan.md + ticket frontmatter → batches JSON)",
    "sequential batch loop (one batch at a time)",
    "parallel ticket dispatch (build-ticket workflow per batch slot)",
    "halt detection (structured error surface on any ticket halt)",
  ],
};

/**
 * Epic planner output schema.
 *
 * The planner agent MUST return a JSON object conforming to this schema.
 * Each batch contains only tickets that are safe to run in parallel:
 * - No dependency relationship between them (depends_on transitive closure).
 * - Disjoint files_touched sets.
 *
 * batches: [
 *   {
 *     batch_number: 1,
 *     tickets: [
 *       {
 *         path: "01_foo.md",
 *         agents: { "python-coder": "needed", ... },
 *         files_touched: ["src/foo.py"],
 *         status: "todo"
 *       },
 *       ...
 *     ]
 *   },
 *   ...
 * ]
 *
 * Already-done tickets (status: "done") are OMITTED from the batches array.
 */
const PLANNER_SCHEMA = {
  type: "object",
  required: ["epic_path", "title", "batches"],
  properties: {
    epic_path: {
      type: "string",
      description: "Absolute or repo-relative path to the epic folder.",
    },
    title: {
      type: "string",
      description: "Human-readable epic title (from Master_Plan.md).",
    },
    batches: {
      type: "array",
      description:
        "Dependency-ordered list of ticket batches. Each batch is a group of " +
        "tickets that are safe to run in parallel (no overlapping files_touched, " +
        "no dependency between them). Batches are ordered so that all tickets " +
        "in batch N+1 depend only on tickets from batches 1..N. " +
        "Tickets with status 'done' are omitted from all batches.",
      items: {
        type: "object",
        required: ["batch_number", "tickets"],
        properties: {
          batch_number: {
            type: "integer",
            description: "1-indexed batch sequence number.",
          },
          tickets: {
            type: "array",
            description: "Tickets in this batch (safe for parallel execution).",
            items: {
              type: "object",
              required: ["path", "status"],
              properties: {
                path: {
                  type: "string",
                  description:
                    "Path to the ticket .md file (absolute or repo-relative).",
                },
                agents: {
                  type: "object",
                  description:
                    "agents: map from ticket frontmatter (agent → status).",
                },
                files_touched: {
                  type: "array",
                  items: { type: "string" },
                  description: "files_touched list from ticket frontmatter.",
                },
                status: {
                  type: "string",
                  enum: ["todo", "blocked"],
                  description: "Ticket status (done tickets are omitted).",
                },
              },
            },
          },
        },
      },
    },
  },
};

/**
 * Main entry point called by the Claude Code workflow runtime.
 *
 * @param {object} params
 * @param {string} params.userInput   - The epic_path passed via $ARGUMENTS.
 * @param {Function} params.agent     - Runtime-provided agent dispatch function.
 * @param {Function} params.workflow  - Runtime-provided sub-workflow call function.
 * @param {Function} params.parallel  - Runtime-provided parallel dispatch function.
 */
async function run({ userInput, agent, workflow, parallel }) {
  const epicPath = userInput.trim();

  if (!epicPath) {
    return {
      status: "error",
      message:
        "No epic_path provided. Usage: /build-feature <epic_path>\n" +
        "Examples:\n" +
        "  /build-feature EPIC-AgentSupervisor\n" +
        "  /build-feature tickets/01_todo/EPIC-Foo\n" +
        "  /build-feature ./tickets/00_inbox/epics/EPIC-Bar",
    };
  }

  // -------------------------------------------------------------------------
  // Step 0 — Worktree guard: refuse to run on the main clone
  // -------------------------------------------------------------------------
  // A git worktree's .git is a file (containing a gitdir: pointer); in the
  // main clone .git is a directory. Running implementation work on main risks
  // corrupting the shared working tree. If not in a worktree, emit a
  // structured error instructing the caller to create one first.
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
        "build-epic.js must run inside a git worktree, not the main clone. " +
        "The current working directory has .git as a " + gitInfo.git_type +
        " (branch: " + gitInfo.branch + "). " +
        "Create a worktree first:\n" +
        "  /worktree create <epic-branch-name>\n" +
        "Then re-run /build-feature from inside the worktree.",
      action_required: "create_worktree",
    };
  }

  // -------------------------------------------------------------------------
  // Step 1 — Planner: read Master_Plan.md + all ticket frontmatter → batches
  // -------------------------------------------------------------------------
  // The workflow script cannot read files directly. A planner agent reads
  // the epic's Master_Plan.md and all sub-ticket frontmatter, applies the
  // dependency-graph algorithm (building-epics §1.1), and returns the
  // dependency-ordered batches array. Already-done tickets are omitted.
  const plannerResult = await agent({
    agentType: "status-checker",
    input: {
      epic_path: epicPath,
      instructions:
        "Read Master_Plan.md at the epic_path folder. Then read the frontmatter " +
        "of every NN_*.md sub-ticket in that folder (excluding Master_Plan.md). " +
        "Compute the dependency-ordered batch list using the algorithm from " +
        "building-epics SKILL.md §1.1: " +
        "(1) Build a dependency graph using depends_on (logical edges) and " +
        "files_touched overlap (physical edges). " +
        "(2) Compute the maximal antichain of ready tickets (all depends_on met). " +
        "(3) Split the antichain into batches so no two tickets in a batch share " +
        "any files_touched entry. " +
        "(4) Tickets with status 'done' are OMITTED from all batches (resume). " +
        "Return a JSON object conforming exactly to this schema: " +
        JSON.stringify(PLANNER_SCHEMA, null, 2) +
        " Return ONLY the JSON object, no prose.",
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

  const batches = plan.batches || [];
  const epicTitle = plan.title || epicPath;

  // -------------------------------------------------------------------------
  // Step 2 — Guard: if no batches, the epic is already complete (or empty)
  // -------------------------------------------------------------------------
  if (batches.length === 0) {
    return {
      status: "ok",
      message:
        `Epic "${epicTitle}" complete (or no tickets to run). ` +
        "All tickets are done or the epic is empty.",
      epic_path: epicPath,
      batches_run: 0,
    };
  }

  // -------------------------------------------------------------------------
  // Step 3 — Sequential batch loop
  // -------------------------------------------------------------------------
  const completedBatches = [];

  for (const batch of batches) {
    const batchNumber = batch.batch_number;
    const tickets = batch.tickets || [];

    if (tickets.length === 0) {
      // Empty batch — skip (shouldn't happen if planner is correct)
      completedBatches.push({ batch_number: batchNumber, tickets_completed: 0 });
      continue;
    }

    // -----------------------------------------------------------------------
    // Step 4 — Dispatch all tickets in this batch via parallel()
    // -----------------------------------------------------------------------
    // Each parallel slot calls the build-ticket workflow with the ticket path
    // and the worktree_path so child tickets retain worktree context.
    // parallel() waits for ALL slots to complete before returning the results.
    const worktreePath = gitInfo.worktree_path || process.cwd();
    const batchResults = await parallel(
      tickets.map((ticket) => async () => {
        try {
          const result = await workflow("build-ticket", {
            ticket_path: ticket.path,
            worktree_path: worktreePath,
          });
          return {
            ticket_path: ticket.path,
            status: result && result.status ? result.status : "ok",
            result,
          };
        } catch (err) {
          return {
            ticket_path: ticket.path,
            status: "failed",
            error: err.message || String(err),
          };
        }
      })
    );

    // -----------------------------------------------------------------------
    // Step 5 — Batch-level failure detection
    // -----------------------------------------------------------------------
    // Check for any halt-class results. If any ticket in the batch halted,
    // stop the outer batch loop and surface the error. Already-completed
    // parallel slots in the same batch are not rolled back.
    const haltedTickets = batchResults.filter(
      (r) =>
        r.status === "failed" ||
        r.status === "blocked" ||
        r.status === "halt" ||
        r.status === "error"
    );

    if (haltedTickets.length > 0) {
      // Surface structured error — do NOT start any subsequent batch.
      const haltSummary = haltedTickets.map((r) => ({
        ticket_path: r.ticket_path,
        status: r.status,
        error: r.error || (r.result && r.result.message) || "unknown error",
      }));

      return {
        status: "blocked",
        message:
          `Epic "${epicTitle}" halted at batch ${batchNumber} — ` +
          `${haltedTickets.length} ticket(s) failed or blocked.`,
        epic_path: epicPath,
        halted_at_batch: batchNumber,
        halted_tickets: haltSummary,
        completed_batches: completedBatches,
        suggested_action:
          "Review the ## Comments section of each halted ticket for the " +
          "blocker details. Resolve the blocker(s) and re-run /build-feature " +
          "to resume from the halted batch (already-done tickets are skipped).",
      };
    }

    // All tickets in this batch succeeded.
    completedBatches.push({
      batch_number: batchNumber,
      tickets_completed: tickets.length,
      tickets: batchResults.map((r) => r.ticket_path),
    });
  }

  // -------------------------------------------------------------------------
  // Step 6 — Return success summary
  // -------------------------------------------------------------------------
  const totalTickets = completedBatches.reduce(
    (sum, b) => sum + (b.tickets_completed || 0),
    0
  );

  const worktreePath = gitInfo.worktree_path || process.cwd();

  // Build a flat list of all completed ticket paths for manual test hints.
  const completedTicketPaths = completedBatches.flatMap(
    (b) => b.tickets || []
  );

  // Derive manual test suggestions from the completed ticket set.
  // The planner does not surface ACs or files_touched at this stage, so we
  // produce generic smoke-test suggestions based on the ticket count and the
  // epic name. Callers can enrich this list by reading individual tickets.
  const manualTests = [
    `Verify that all ${totalTickets} ticket change(s) for "${epicTitle}" are reflected on the branch.`,
    `Run the full test suite on the worktree to confirm no regressions.`,
    `Inspect each changed file listed in the completed tickets' files_touched frontmatter.`,
    `Confirm the PR diff on GitHub matches the expected scope for "${epicTitle}".`,
    `Run /finalize-feature ${epicTitle} in a clean shell and confirm it completes without errors.`,
  ];

  const epicName = epicPath.split("/").pop() || epicPath;

  const completionMessage =
    `## Summary\n` +
    `Epic "${epicTitle}" complete. ` +
    `${completedBatches.length} batch(es) run, ${totalTickets} ticket(s) completed.\n\n` +
    `## Worktree path\n` +
    `${worktreePath}\n\n` +
    `## Things to manually test\n` +
    manualTests.map((t) => `- ${t}`).join("\n") + "\n\n" +
    `## Finalize command\n` +
    `/finalize-feature ${epicName}`;

  return {
    status: "ok",
    epic_path: epicPath,
    title: epicTitle,
    worktree_path: worktreePath,
    manual_tests: manualTests,
    batches_run: completedBatches.length,
    tickets_completed: totalTickets,
    completed_batches: completedBatches,
    message: completionMessage,
  };
}
