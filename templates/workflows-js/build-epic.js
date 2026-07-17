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
 *      — each parallel slot calls agent(prompt, {agentType: "ticket-supervisor"})
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
 *
 * E2 canonical form: top-level body, agent(prompt, opts), args global.
 * No export async function run() — E2 executes the top-level body directly.
 * workflow() calls replaced by agent(prompt, {agentType: "ticket-supervisor"}).
 */

export const meta = {
  name: "build-epic",
  description:
    "Drive a full epic from Master_Plan.md through to all tickets completed. Uses a planner agent to read the epic's dependency graph and return dependency-ordered batches. Iterates batches sequentially; within each batch, tickets run via the parallel runtime call — each slot dispatches ticket-supervisor. Already-done tickets are omitted by the planner, enabling crash-resume. A halt from any ticket in a batch stops the outer loop and surfaces a structured error. No Agent tool nesting exceeds depth 1.",
  phases: [
    "planner agent (depth 1 — reads Master_Plan.md + ticket frontmatter → batches JSON)",
    "sequential batch loop (one batch at a time)",
    "parallel ticket dispatch (ticket-supervisor per batch slot)",
    "halt detection (structured error surface on any ticket halt)",
  ],
};

// ---------------------------------------------------------------------------
// JSON Schemas for agent() responses
// The E2 engine enforces these and returns already-parsed objects.
// Do NOT call JSON.parse() on agent() results when schema is provided.
// ---------------------------------------------------------------------------

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

const TICKET_RESULT_SCHEMA = {
  type: "object",
  properties: {
    status: {
      type: "string",
      enum: ["ok", "blocked", "failed", "error", "halt"],
    },
    message: { type: "string" },
    ticket_path: { type: "string" },
  },
  required: ["status"],
};

const WORKTREE_SCHEMA = {
  type: "object",
  properties: {
    git_type: { type: "string" },
    branch: { type: "string" },
    worktree_path: { type: "string" },
  },
  required: ["git_type", "branch"],
};

// ---------------------------------------------------------------------------
// Prose-tolerant reply reader (BP-300e)
// ---------------------------------------------------------------------------

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
// Phase 0 — Worktree guard
// ---------------------------------------------------------------------------
// Read the worktree path from args if provided. If args.worktree_path is set,
// the caller already resolved the worktree context — skip the ambient CWD check.
// This fixes the false-halt that occurred when build-epic was invoked from
// the session root (where CWD is the main clone, not the worktree).

phase('Worktree Guard')

const epicPath = (args && (args.epic_path || args.userInput || '').trim()) || '';

if (!epicPath) {
  return {
    status: "error",
    message:
      "No epic_path provided. Pass args: { epic_path: '<path>' }\n" +
      "Examples:\n" +
      "  { epic_path: 'EPIC-AgentSupervisor' }\n" +
      "  { epic_path: 'tickets/01_todo/EPIC-Foo' }\n" +
      "  { epic_path: './tickets/00_inbox/epics/EPIC-Bar' }",
  };
}

// If the caller already provided worktree_path in args, trust it — no ambient check.
const callerWorktreePath = args && args.worktree_path;

let worktreeGitInfo = null;

if (!callerWorktreePath) {
  // Fall back to the git info check when no worktree_path is provided in args.
  // Use the explicit epic path context rather than session CWD.
  const worktreeCheck = await agent(
    `Check the git context for the epic at path "${epicPath}". ` +
    "Run these two shell commands and report the results as JSON:\n" +
    "1. `test -f .git && echo file || echo directory` — determines if .git is a file (worktree) or directory (main clone)\n" +
    "2. `git branch --show-current` — reports the current branch name\n" +
    "Return ONLY a JSON object: { \"git_type\": \"file\"|\"directory\", \"branch\": \"<name>\", \"worktree_path\": \"<cwd>\" }",
    { agentType: "status-checker", schema: WORKTREE_SCHEMA, label: 'worktree-check', phase: 'Worktree Guard' }
  );

  worktreeGitInfo = worktreeCheck;

  if (
    worktreeGitInfo &&
    (worktreeGitInfo.git_type === "directory" ||
      worktreeGitInfo.branch === "main" ||
      worktreeGitInfo.branch === "master")
  ) {
    return {
      status: "error",
      worktree_required: true,
      message:
        "build-epic.js must run inside a git worktree, not the main clone. " +
        "The current working directory has .git as a " + (worktreeGitInfo.git_type || 'unknown') +
        " (branch: " + (worktreeGitInfo.branch || 'unknown') + "). " +
        "Create a worktree first:\n" +
        "  /worktree create <epic-branch-name>\n" +
        "Then re-run /build-feature from inside the worktree.",
      action_required: "create_worktree",
    };
  }
}

// Resolve the worktree path: caller-provided wins, then git info, then epic path context.
const worktreePath = callerWorktreePath ||
  (worktreeGitInfo && worktreeGitInfo.worktree_path) ||
  epicPath;

// -------------------------------------------------------------------------
// Phase 1 — Planner: read Master_Plan.md + all ticket frontmatter → batches
// -------------------------------------------------------------------------

phase('Planner')

const plannerResult = await agent(
  `Read Master_Plan.md at the epic folder: "${epicPath}". Then read the frontmatter of every NN_*.md sub-ticket in that folder (excluding Master_Plan.md). Compute the dependency-ordered batch list: (1) Build a dependency graph using depends_on (logical edges) and files_touched overlap (physical edges). (2) Compute the maximal antichain of ready tickets (all depends_on met). (3) Split the antichain into batches so no two tickets in a batch share any files_touched entry. (4) Tickets with status 'done' are OMITTED from all batches (resume). Return a JSON object with these top-level keys: epic_path, title, batches. Return ONLY the JSON object, no prose.`,
  { agentType: "status-checker", schema: PLANNER_SCHEMA, label: 'epic-planner', phase: 'Planner' }
)

const plan = plannerResult || {};
const batches = plan.batches || [];
const epicTitle = plan.title || epicPath;

// -------------------------------------------------------------------------
// Phase 2 — Guard: if no batches, the epic is already complete (or empty)
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
// Phase 3 — Sequential batch loop
// -------------------------------------------------------------------------

phase('Batch Dispatch')

const completedBatches = [];

// Chunk size: keep parallel fan-out well below the ~16 concurrent cap.
const BATCH_SIZE = 12;

for (const batch of batches) {
  const batchNumber = batch.batch_number;
  const tickets = batch.tickets || [];

  if (tickets.length === 0) {
    completedBatches.push({ batch_number: batchNumber, tickets_completed: 0 });
    continue;
  }

  // -----------------------------------------------------------------------
  // Dispatch all tickets in this batch via parallel()
  // Chunk the tickets to stay within the ~16 concurrent cap.
  // Each slot dispatches ticket-supervisor (replaces workflow("build-ticket")).
  // worktree_path is passed in the prompt so child tickets retain worktree context.
  // -----------------------------------------------------------------------

  const batchResults = [];

  for (let i = 0; i < tickets.length; i += BATCH_SIZE) {
    const chunk = tickets.slice(i, i + BATCH_SIZE);

    const chunkResults = await parallel(
      chunk.map((ticket) => async () => {
        const result = await agent(
          `Drive ticket to completion: ${ticket.path}. Worktree: ${worktreePath}. Execute all needed phase agents in order. worktree_path: ${worktreePath}`,
          { agentType: "ticket-supervisor", schema: TICKET_RESULT_SCHEMA, label: `ticket:${ticket.path}`, phase: 'Batch Dispatch' }
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

  // -----------------------------------------------------------------------
  // Batch-level failure detection
  // -----------------------------------------------------------------------
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
        "Review the ## Comments section of each halted ticket for the " +
        "blocker details. Resolve the blocker(s) and re-run /build-feature " +
        "to resume from the halted batch (already-done tickets are skipped).",
    };
  }

  completedBatches.push({
    batch_number: batchNumber,
    tickets_completed: tickets.length,
    tickets: batchResults.map((r) => r.ticket_path),
  });
}

// -------------------------------------------------------------------------
// Phase 4 — Return success summary
// -------------------------------------------------------------------------

const totalTickets = completedBatches.reduce(
  (sum, b) => sum + (b.tickets_completed || 0),
  0
);

const completedTicketPaths = completedBatches.flatMap(
  (b) => b.tickets || []
);

const manualTests = [
  `Verify that all ${totalTickets} ticket change(s) for "${epicTitle}" are reflected on the branch.`,
  `Run the full test suite on the worktree to confirm no regressions.`,
  `Inspect each changed file listed in the completed tickets' files_touched frontmatter.`,
  `Confirm the PR diff on GitHub matches the expected scope for "${epicTitle}".`,
  `Run /finalize-feature in a clean shell and confirm it completes without errors.`,
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
