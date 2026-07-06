/**
 * build-feature.js — Claude Code Workflow script
 *
 * Entry-point dispatcher for /build-feature. Resolves the target argument
 * as an epic folder or a single-ticket file, creates/reuses the worktree,
 * then routes to the appropriate build flow:
 *
 *   - Epic target → inline planner + parallel batch dispatch (ticket-supervisor per ticket)
 *   - Single-ticket target → dispatch ticket-supervisor directly
 *
 * This gives build-ticket.js and build-epic.js their caller: build-feature.js
 * routes to ticket-supervisor (single) or the planner + ticket-supervisor
 * batch loop (epic). workflow() is NOT called — E2 leaf-invariant preserved.
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 *
 * E2 canonical form: top-level body, agent(prompt, opts), args global.
 * No export async function run() — E2 executes the top-level body directly.
 *
 * ADR: docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
 * Ticket: tickets/00_inbox/epics/EPIC-DualEngineWorkflowSupport/10_e2_command_wiring_correctness.md
 */

export const meta = {
  name: "build-feature",
  description:
    "Resolve a build target (epic folder or single ticket file) and drive it to completion. " +
    "Dispatches a status-checker to determine epic-vs-single-ticket and set up the worktree. " +
    "For epics: runs the planner then dispatches ticket-supervisor per batch via parallel(). " +
    "For single tickets: dispatches ticket-supervisor directly.",
  phases: [
    "resolve-target: status-checker determines epic vs single-ticket + worktree path",
    "build: planner + parallel ticket-supervisor batch loop (epic) or direct ticket-supervisor (single)",
  ],
};

// ---------------------------------------------------------------------------
// JSON Schemas for agent() responses
// ---------------------------------------------------------------------------

const RESOLVE_SCHEMA = {
  type: "object",
  properties: {
    target_type: { type: "string", enum: ["epic", "ticket"] },
    epic_path: { type: "string" },
    ticket_path: { type: "string" },
    worktree_path: { type: "string" },
  },
  required: ["target_type", "worktree_path"],
};

const PLANNER_SCHEMA = {
  type: "object",
  required: ["epic_path", "title", "batches"],
  properties: {
    epic_path: { type: "string" },
    title: { type: "string" },
    batches: {
      type: "array",
      items: {
        type: "object",
        required: ["batch_number", "tickets"],
        properties: {
          batch_number: { type: "integer" },
          tickets: {
            type: "array",
            items: {
              type: "object",
              required: ["path", "status"],
              properties: {
                path: { type: "string" },
                status: { type: "string", enum: ["todo", "blocked"] },
              },
            },
          },
        },
      },
    },
  },
};

const TICKET_RESULT_SCHEMA = {
  type: "object",
  properties: {
    status: { type: "string", enum: ["ok", "blocked", "failed", "error", "halt"] },
    message: { type: "string" },
    ticket_path: { type: "string" },
  },
  required: ["status"],
};

// ---------------------------------------------------------------------------
// Phase 0 — Resolve target and worktree
// ---------------------------------------------------------------------------

phase("Resolve Target");

const target = (args && (args.target || args.userInput || "").trim()) || "";

if (!target) {
  return {
    status: "error",
    message:
      "No target provided. Pass args: { target: '<epic-name or ticket-path>' }\n" +
      "Examples:\n" +
      "  { target: 'EPIC-AgentSupervisor' }\n" +
      "  { target: 'tickets/01_todo/10_my_ticket.md' }",
  };
}

const resolveResult = await agent(
  `Resolve the /build-feature target and set up the worktree.\n\n` +
  `Target: "${target}"\n\n` +
  `1. Determine whether the target is an epic or a single ticket:\n` +
  `   - If it ends in ".md" or is a path to a file: target_type = "ticket"\n` +
  `   - If it looks like an epic folder (e.g. EPIC-*, contains Master_Plan.md): target_type = "epic"\n\n` +
  `2. Resolve the absolute path:\n` +
  `   - For ticket: resolve to the absolute path of the ticket .md file\n` +
  `   - For epic: resolve to the absolute path of the epic folder\n\n` +
  `3. Determine the worktree path:\n` +
  `   - Run: test -f .git && echo file || echo directory\n` +
  `   - If .git is a file, we are inside a worktree; report the current directory as worktree_path\n` +
  `   - If .git is a directory, the caller is in the main clone; report the epic folder path as worktree_path\n\n` +
  `Return JSON: { "target_type": "epic"|"ticket", "epic_path": "<abs>"|null, "ticket_path": "<abs>"|null, "worktree_path": "<abs>" }`,
  {
    agentType: "status-checker",
    schema: RESOLVE_SCHEMA,
    label: "resolve-target",
    phase: "Resolve Target",
  }
);

if (!resolveResult) {
  return {
    status: "error",
    message:
      "resolve-target agent returned null. Cannot determine build target.",
  };
}

const { target_type, epic_path, ticket_path, worktree_path } = resolveResult;

// ---------------------------------------------------------------------------
// Phase 1 — Build: route to epic or single-ticket flow
// ---------------------------------------------------------------------------

phase("Build");

if (target_type === "epic") {
  // -----------------------------------------------------------------------
  // Epic path: planner + parallel batch dispatch
  // Mirrors build-epic.js Phase 1 + Phase 2 inline (no workflow() call).
  // -----------------------------------------------------------------------
  const epicPath = epic_path || target;

  const plannerResult = await agent(
    `Read Master_Plan.md at the epic folder: "${epicPath}". Then read the frontmatter of every NN_*.md sub-ticket. ` +
    `Compute dependency-ordered batches: (1) Build a dependency graph using depends_on (logical) and files_touched overlap (physical). ` +
    `(2) Compute the maximal antichain of ready tickets (all depends_on met). ` +
    `(3) Split the antichain into batches so no two tickets share any files_touched entry. ` +
    `(4) Tickets with status 'done' are OMITTED from all batches (resume). ` +
    `Return a JSON object with: epic_path, title, batches. Return ONLY the JSON object.`,
    {
      agentType: "status-checker",
      schema: PLANNER_SCHEMA,
      label: "epic-planner",
      phase: "Build",
    }
  );

  const plan = plannerResult || {};
  const batches = plan.batches || [];
  const epicTitle = plan.title || epicPath;

  if (batches.length === 0) {
    return {
      status: "ok",
      message: `Epic "${epicTitle}" complete (or no tickets to run). All tickets are done or the epic is empty.`,
      epic_path: epicPath,
      batches_run: 0,
    };
  }

  const BATCH_SIZE = 12;
  const completedBatches = [];

  for (const batch of batches) {
    const batchNumber = batch.batch_number;
    const tickets = batch.tickets || [];

    if (tickets.length === 0) {
      completedBatches.push({ batch_number: batchNumber, tickets_completed: 0 });
      continue;
    }

    const batchResults = [];

    for (let i = 0; i < tickets.length; i += BATCH_SIZE) {
      const chunk = tickets.slice(i, i + BATCH_SIZE);

      const chunkResults = await parallel(
        chunk.map((ticket) => async () => {
          const result = await agent(
            `Drive ticket to completion: ${ticket.path}. Worktree: ${worktree_path}. Execute all needed phase agents in order. worktree_path: ${worktree_path}`,
            {
              agentType: "ticket-supervisor",
              schema: TICKET_RESULT_SCHEMA,
              label: `ticket:${ticket.path}`,
              phase: "Build",
            }
          );
          return {
            ticket_path: ticket.path,
            status: result && result.status ? result.status : "ok",
            result,
          };
        })
      );

      for (const r of chunkResults) {
        if (r) {
          batchResults.push(r);
        }
      }
    }

    const haltedTickets = batchResults.filter(
      (r) =>
        r.status === "failed" ||
        r.status === "blocked" ||
        r.status === "halt" ||
        r.status === "error"
    );

    if (haltedTickets.length > 0) {
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
          "Review the ## Comments section of each halted ticket for the blocker details. " +
          "Resolve the blocker(s) and re-run /build-feature to resume.",
      };
    }

    completedBatches.push({
      batch_number: batchNumber,
      tickets_completed: tickets.length,
      tickets: batchResults.map((r) => r.ticket_path),
    });
  }

  const totalTickets = completedBatches.reduce(
    (sum, b) => sum + (b.tickets_completed || 0),
    0
  );

  return {
    status: "ok",
    epic_path: epicPath,
    title: epicTitle,
    worktree_path,
    batches_run: completedBatches.length,
    tickets_completed: totalTickets,
    completed_batches: completedBatches,
    message:
      `Epic "${epicTitle}" complete. ` +
      `${completedBatches.length} batch(es) run, ${totalTickets} ticket(s) completed.`,
  };
} else {
  // -----------------------------------------------------------------------
  // Single-ticket path: dispatch ticket-supervisor directly
  // -----------------------------------------------------------------------
  const singleTicketPath = ticket_path || target;

  const ticketResult = await agent(
    `Drive ticket to completion: "${singleTicketPath}". Worktree: ${worktree_path}. ` +
    `Execute all needed phase agents in order. worktree_path: ${worktree_path}`,
    {
      agentType: "ticket-supervisor",
      schema: TICKET_RESULT_SCHEMA,
      label: "build-ticket",
      phase: "Build",
    }
  );

  return ticketResult || {
    status: "error",
    message: `ticket-supervisor returned null for ticket: ${singleTicketPath}`,
  };
}
