/**
 * build-feature.js — Claude Code Workflow script
 *
 * Entry-point dispatcher for /build-feature. Resolves the target argument
 * as an epic folder or a single-ticket file, creates/reuses the worktree,
 * then routes to the appropriate build flow:
 *
 *   - Epic target → inline planner + parallel batch dispatch (flattened per-phase driver per ticket)
 *   - Single-ticket target → flattened per-phase driver directly
 *
 * Phase dispatch: each needed phase agent is dispatched as a flat depth-1
 * agent() call (agentType: phaseName), inlining the build-ticket.js driver
 * semantics. workflow() is NOT called — E2 leaf-invariant preserved.
 *
 * NOTE: The per-ticket phase loop (driveTicketPhases) is intentionally
 * inlined here rather than calling workflow('build-ticket') because the
 * E2 engine's leaf-invariant prohibits workflow() inside a running workflow
 * (a workflow() call from inside a running workflow throws). Inlining keeps
 * every phase agent at depth 1 so its template applies.
 *
 * TWIN: The phaseOrder array and per-ticket phase loop below are the canonical
 * twin of build-ticket.js Phase 1–3. Keep them in sync manually — any change
 * to build-ticket.js phaseOrder or the retry/adjudication logic must be
 * mirrored here.
 *
 * ADR: docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
 * Ticket: tickets/00_inbox/epics/EPIC-PromptAssemblyHardening/06_buildfeature_flatten_wiring.md
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 *
 * E2 canonical form: top-level body, agent(prompt, opts), args global.
 * No export async function run() — E2 executes the top-level body directly.
 */

export const meta = {
  name: "build-feature",
  description:
    "Resolve a build target (epic folder or single ticket file) and drive it to completion. Dispatches a status-checker to determine epic-vs-single-ticket and set up the worktree. For epics: runs the planner then dispatches each ticket's phases individually through the flattened per-phase driver via parallel(). For single tickets: dispatches each needed phase as a flat depth-1 agent() call. No workflow() call — E2 leaf-invariant preserved.",
  phases: [
    "resolve-target: status-checker determines epic vs single-ticket + worktree path",
    "build: planner + parallel batch dispatch (epic) or direct dispatch (single), both using the flattened per-phase driver (agentType: phaseName per phase)",
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
  required: ["target_type"],
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

const WORKTREE_SCHEMA = {
  type: "object",
  required: ["worktree_path", "status"],
  properties: {
    worktree_path: { type: "string" },
    status: { type: "string", enum: ["created", "reused"] },
    error: { type: "string" },
  },
};

/**
 * Per-ticket planner schema — mirrors build-ticket.js PLANNER_SCHEMA.
 * Used by driveTicketPhases() to read a single ticket's agents map
 * and derive ordered_phases.
 */
const TICKET_PLANNER_SCHEMA = {
  type: "object",
  required: ["ticket_path", "ordered_phases"],
  properties: {
    ticket_path: { type: "string" },
    title: { type: "string" },
    files_touched: { type: "array", items: { type: "string" } },
    // has_test_requirements: true when ## Test Requirements has at least one "- name:" entry.
    // Used by the Test Requirements guard (BO-2000e-2) to block coder dispatch.
    has_test_requirements: { type: "boolean" },
    ordered_phases: {
      type: "array",
      items: {
        type: "object",
        required: ["agent", "status"],
        properties: {
          agent: { type: "string" },
          status: {
            type: "string",
            enum: ["needed", "signed_off", "not_needed", "failed"],
          },
        },
      },
    },
  },
};

/**
 * Per-phase result schema — mirrors build-ticket.js PHASE_RESULT_SCHEMA.
 * Used by driveTicketPhases() for each phase agent dispatch.
 */
const PHASE_RESULT_SCHEMA = {
  type: "object",
  properties: {
    status: {
      type: "string",
      enum: ["ok", "blocker", "failed", "question", "handoff"],
    },
    result_status: { type: "string" },
    message: { type: "string" },
  },
  required: ["status"],
};

/**
 * Failure classifier schema — mirrors build-ticket.js CLASSIFY_SCHEMA.
 * Used by driveTicketPhases() failure adjudication.
 */
const CLASSIFY_SCHEMA = {
  type: "object",
  properties: {
    classification: {
      type: "string",
      enum: ["mechanical", "cross_agent", "design", "halt"],
    },
    reason: { type: "string" },
  },
  required: ["classification"],
};

// ---------------------------------------------------------------------------
// Constants and helper functions (pure — no I/O)
//
// TWIN: mirrors build-ticket.js. Keep in sync with that file.
// ---------------------------------------------------------------------------

/**
 * Maximum retry attempts for a single phase on a mechanical failure.
 * Must be > 0 and <= 3 to prevent runaway loops.
 */
const MAX_RETRIES = 2;

/**
 * Canonical phase ordering for per-ticket dispatch.
 * Agents run in priority order (lower index = runs first).
 * Source: building-epics SKILL.md canonical phase ordering table.
 *
 * TWIN: mirrors build-ticket.js phaseOrder. Keep in sync.
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
  "llm-expert",                  // priority 8 — implements agent-template / skill / slash-command prompt work
  "test-runner",                 // priority 9
  "change-scope-reviewer",       // priority 10
  "documentation-expert",        // priority 10
  "explanation-author",          // priority 10
  "how-to-author",               // priority 10
  "reference-author",            // priority 10
  "pr-reviewer",                 // priority 11
  "user-surface-smoker",         // priority 11.5
  "documentation-verifier",      // priority 11.9
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
 * From a ticket's candidate phases, return those to actually dispatch.
 *
 * Pure function (no module state) so it is unit-testable in isolation — this is
 * the load-bearing decision behind BO-2700 ("one PR per epic"): for an
 * epic-member ticket the pull-request phase is dropped (the single epic-level PR
 * is opened later by finalize-feature, NOT per ticket), while the commit phase
 * and every other phase are retained (commit's pre-commit hooks must fire per
 * ticket). For a standalone ticket (isEpicMember=false) the list is returned
 * unchanged, so single-ticket behavior is unaffected.
 *
 * @param {Array<{agent: string, status: string}>} orderedPhases
 * @param {boolean} isEpicMember
 * @returns {Array<{agent: string, status: string}>}
 */
function selectDispatchPhases(orderedPhases, isEpicMember) {
  const phases = orderedPhases || [];
  if (!isEpicMember) {
    return phases;
  }
  return phases.filter((p) => p.agent !== "pull-request");
}

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

const { target_type, epic_path, ticket_path } = resolveResult;

// Establish the isolated worktree (create or reuse) before any build work.
const worktreeTarget = target_type === "epic"
  ? (epic_path || target)
  : (ticket_path || target);

const worktreeResult = await agent(
  `Create or reuse the isolated git worktree for the build target.\n\n` +
  `Target: "${worktreeTarget}"\n` +
  `Target type: "${target_type}"\n\n` +
  `Instructions:\n` +
  `1. Run 'git worktree list --porcelain' to check if a worktree for this target already exists.\n` +
  `2. If it exists: REUSE it — report the existing absolute path as worktree_path, status "reused".\n` +
  `3. If it does not exist: CREATE it from origin/main.\n` +
  `   For epics: 'git worktree add <path> -b <branch-name> origin/main'\n` +
  `   Report the new absolute path as worktree_path, status "created".\n` +
  `4. On any error: report status "failed" with an error message.\n\n` +
  `IMPORTANT: After creating, bootstrap the worktree: copy/symlink .leafcutter from the main clone so hooks are present.\n\n` +
  `Return JSON: { "worktree_path": "<absolute path>", "status": "created"|"reused", "error": "<if failed, else omit>" }`,
  {
    agentType: "worktree-agent",
    schema: WORKTREE_SCHEMA,
    label: "worktree-setup",
    phase: "Resolve Target",
  }
);

if (!worktreeResult || worktreeResult.status === "failed" || worktreeResult.error) {
  return {
    status: "error",
    message:
      `worktree-agent failed to create/reuse isolated worktree for "${worktreeTarget}". ` +
      `Error: ${(worktreeResult && worktreeResult.error) || "worktree-agent returned null or failed"}. ` +
      `Safety abort: /build-feature will NOT fall back to driving phase agents ` +
      `against the main clone. Fix the worktree issue and re-run.`,
    abort_reason: "worktree-setup-failed",
  };
}

const realWorktreePath = worktreeResult.worktree_path;
if (!realWorktreePath) {
  return {
    status: "error",
    message:
      "worktree-agent returned no worktree_path. Cannot drive phase agents without " +
      "a confirmed isolated worktree path.",
    abort_reason: "worktree-path-missing",
  };
}

// ---------------------------------------------------------------------------
// Derive worktree-resident paths from resolve output
//
// resolve may return epic_path / ticket_path as an absolute main-clone path
// (e.g. /home/user/leafcutter-ai/tickets/…) or as a repo-relative path
// (e.g. tickets/00_inbox/epics/EPIC-X).  Either way we must land inside
// realWorktreePath before passing paths to the planner or phase agents.
//
// Algorithm:
//   1. If the path is already inside realWorktreePath → use as-is.
//   2. If absolute → strip to the repo-relative portion via known directory
//      anchors (tickets/, templates/, docs/, unit_tests/), then join under
//      realWorktreePath.
//   3. If repo-relative (no leading slash) → join directly under realWorktreePath.
// ---------------------------------------------------------------------------

function toWorktreePath(resolvedPath, worktreePath) {
  if (!resolvedPath) return null;

  // Case 1: already inside the worktree
  if (
    resolvedPath === worktreePath ||
    resolvedPath.startsWith(worktreePath + "/")
  ) {
    return resolvedPath;
  }

  // Case 2: absolute path — strip to repo-relative using known anchors
  if (resolvedPath.startsWith("/")) {
    const anchors = ["tickets/", "templates/", "docs/", "unit_tests/"];
    for (const anchor of anchors) {
      const idx = resolvedPath.indexOf("/" + anchor);
      if (idx !== -1) {
        return worktreePath + "/" + resolvedPath.slice(idx + 1);
      }
    }
    // Fallback: try anchor without requiring a leading slash
    for (const anchor of anchors) {
      const idx = resolvedPath.indexOf(anchor);
      if (idx !== -1) {
        return worktreePath + "/" + resolvedPath.slice(idx);
      }
    }
  }

  // Case 3: repo-relative (no leading slash) — join directly
  return worktreePath + "/" + resolvedPath;
}

// ---------------------------------------------------------------------------
// driveTicketPhases — flattened per-ticket phase driver
//
// Drives a single ticket through its needed phases as sequential flat depth-1
// agent() calls. This inlines build-ticket.js Phase 1–3 semantics so that
// every phase agent runs under its own template (agentType: phaseName).
//
// TWIN: mirrors build-ticket.js Phase 1 (Planner) + Phase 2 (Guard) +
// Phase 3 (Phase Dispatch). Keep in sync with build-ticket.js.
//
// @param {string} worktreeTicketPath — absolute path to ticket inside the worktree
// @returns {object} — { status, ticket_path, title, completed_phases, skipped_phases, message }
// ---------------------------------------------------------------------------

async function driveTicketPhases(worktreeTicketPath, isEpicMember = false) {
  // -------------------------------------------------------------------------
  // Step 1 — Planner: read ticket frontmatter → ordered_phases JSON
  // -------------------------------------------------------------------------
  const ticketPlan = await agent(
    `Read the ticket at "${worktreeTicketPath}". Extract the agents: map from the frontmatter and the files_touched list. ` +
    `Also check whether the ticket's ## Test Requirements section is populated: it is populated when there is a fenced code block after "## Test Requirements" that contains at least one "- name:" entry in the tests: array. ` +
    `Return a JSON object with exactly these keys: { "ticket_path": "<path>", "title": "<ticket title>", "files_touched": [...], "has_test_requirements": true|false, "ordered_phases": [{"agent": "<name>", "status": "<status>"}, ...] }. ` +
    `The ordered_phases array must list ALL agents from the agents: map in canonical phase priority order. ` +
    `Each entry must include the agent name and its current status (needed | signed_off | not_needed | failed). ` +
    `Return ONLY the JSON object, no prose.`,
    {
      agentType: "status-checker",
      schema: TICKET_PLANNER_SCHEMA,
      label: "ticket-planner",
      phase: "Phase Dispatch",
    }
  );

  const plan = ticketPlan || {};
  const orderedPhases = plan.ordered_phases || [];
  const filesTouched = plan.files_touched || [];
  const title = plan.title || worktreeTicketPath;
  const hasTestRequirements = plan.has_test_requirements === true;

  // -------------------------------------------------------------------------
  // Step 2 — Filter and sort needed phases
  // -------------------------------------------------------------------------
  // selectDispatchPhases applies the "one PR per epic" rule (BO-2700): for an
  // epic-member ticket it drops the pull-request phase (the single epic PR is
  // opened by finalize-feature, not per ticket); commit and all other phases are
  // retained. Standalone tickets (isEpicMember=false) are unaffected.
  const neededPhases = sortByCanonicalPriority(
    selectDispatchPhases(
      orderedPhases.filter((p) => p.status === "needed"),
      isEpicMember
    )
  );

  if (neededPhases.length === 0) {
    return {
      status: "ok",
      message:
        `No phases to run for ticket "${title}". All agents are already signed_off or not_needed.`,
      ticket_path: worktreeTicketPath,
    };
  }

  // Agents that produce production code — must NOT run without Test Requirements.
  const CODER_PHASES = new Set(["python-coder", "sql-coder", "frontend-coder"]);

  // -------------------------------------------------------------------------
  // Step 3 — Sequential phase loop with failure adjudication
  // -------------------------------------------------------------------------
  const retryCounts = {};
  const completedPhases = [];
  const skippedPhases = [];

  for (const currentPhase of neededPhases) {
    const phaseName = currentPhase.agent;
    retryCounts[phaseName] = retryCounts[phaseName] || 0;

    // Test Requirements guard (BO-2000e-2): refuse to dispatch a coder phase
    // when the ticket's ## Test Requirements section is empty or absent.
    if (CODER_PHASES.has(phaseName) && !hasTestRequirements) {
      return {
        status: "blocked",
        message:
          `Structured blocker: the coder phase '${phaseName}' cannot be ` +
          `dispatched because the ticket's ## Test Requirements section is ` +
          `empty or absent (BO-2000e-2). ` +
          `Add at least one test to the tests: array before re-running.`,
        ticket_path: worktreeTicketPath,
        failing_phase: phaseName,
        classification: "halt",
        suggested_action:
          "Populate ## Test Requirements in the ticket with at least one " +
          "'- name: ...' entry, then re-run /build-feature.",
      };
    }

    let phaseResult;
    let retryLoop = true;

    while (retryLoop) {
      retryLoop = false;

      // Dispatch each needed phase as a flat depth-1 agent() call.
      // agentType: phaseName ensures the phase agent's template is loaded.
      phaseResult = await agent(
        `You are the ${phaseName} phase agent for ticket: ${worktreeTicketPath}. ` +
        `Read the ticket before starting. Execute your phase. ` +
        `Files touched: ${JSON.stringify(filesTouched)}. ` +
        `Return a JSON result with at minimum { "status": "ok" | "blocker" | "failed" }.`,
        {
          agentType: phaseName,
          schema: PHASE_RESULT_SCHEMA,
          label: phaseName,
          phase: "Phase Dispatch",
        }
      );

      // ------------------------------------------------------------------
      // Failure detection and adjudication
      // ------------------------------------------------------------------
      const resultStatus =
        phaseResult && (phaseResult.status || phaseResult.result_status);

      // Null / empty-status guard: agent() returns null when a phase agent dies
      // on a terminal error or is skipped mid-run. Without this guard a null
      // result falls through the blocker/failed check below and the phase is
      // silently recorded as completed — letting the driver proceed to commit /
      // pull-request on incomplete work. Treat an absent result or unrecognized
      // status as a halt so the ticket stops rather than shipping half-done.
      if (!phaseResult || !resultStatus) {
        return {
          status: "blocked",
          message:
            `Phase '${phaseName}' returned no usable result (agent died, was ` +
            `skipped, or returned an empty status). Halting to avoid proceeding ` +
            `on incomplete work.`,
          ticket_path: worktreeTicketPath,
          failing_phase: phaseName,
          classification: "halt",
        };
      }

      if (resultStatus === "blocker" || resultStatus === "failed") {
        const classifyResult = await agent(
          `Classify this blocker for ticket ${worktreeTicketPath}, failing phase ${phaseName}. ` +
          `Retry count: ${retryCounts[phaseName]}/${MAX_RETRIES}. ` +
          `Blocker detail: ${JSON.stringify(phaseResult)}. ` +
          `Return classification as one of: mechanical | cross_agent | design | halt.`,
          {
            agentType: "brainstorm-lead",
            schema: CLASSIFY_SCHEMA,
            label: "failure-classifier",
            phase: "Phase Dispatch",
          }
        );

        const classification = classifyResult && classifyResult.classification;

        if (classification === "mechanical") {
          if (retryCounts[phaseName] < MAX_RETRIES) {
            retryCounts[phaseName] += 1;
            retryLoop = true;
            continue;
          } else {
            return {
              status: "blocked",
              message:
                `Phase '${phaseName}' failed with a mechanical blocker and ` +
                `exhausted retry cap (MAX_RETRIES=${MAX_RETRIES}). ` +
                `Manual intervention required.`,
              ticket_path: worktreeTicketPath,
              failing_phase: phaseName,
              blocker_detail: phaseResult,
              classification: "mechanical",
            };
          }
        } else if (classification === "cross_agent") {
          skippedPhases.push({
            agent: phaseName,
            reason: "cross_agent blocker — phase skipped per protocol",
            blocker_detail: phaseResult,
          });
          break;
        } else if (classification === "design" || classification === "halt") {
          return {
            status: "blocked",
            message:
              `Phase '${phaseName}' returned a '${classification}' blocker that ` +
              `requires user intervention. The workflow has stopped.`,
            ticket_path: worktreeTicketPath,
            failing_phase: phaseName,
            blocker_detail: phaseResult,
            classification,
            suggested_action:
              classification === "design"
                ? "Review the design question in the ticket's ## Comments section and provide guidance before re-running /build-feature."
                : "Inspect the ticket's ## Comments section for the blocker details. Manual resolution is required before re-running.",
          };
        } else {
          return {
            status: "blocked",
            message:
              `Phase '${phaseName}' failed and failure-classifier returned ` +
              `unknown classification '${classification}'. Treating as halt.`,
            ticket_path: worktreeTicketPath,
            failing_phase: phaseName,
            blocker_detail: phaseResult,
            classification: classification || "unknown",
          };
        }
      }

      completedPhases.push({ agent: phaseName, result: phaseResult });
    }
  }

  return {
    status: "ok",
    ticket_path: worktreeTicketPath,
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

// ---------------------------------------------------------------------------
// Phase 1 — Build: route to epic or single-ticket flow
// ---------------------------------------------------------------------------

phase("Build");

if (target_type === "epic") {
  // -----------------------------------------------------------------------
  // Epic path: planner + parallel batch dispatch (flattened per-phase driver)
  // Mirrors build-epic.js Phase 1 + Phase 2 inline (no workflow() call).
  // worktreeEpicPath is the epic folder INSIDE the real worktree — the
  // planner reads accurate (post-drive) ticket statuses from there so that
  // resume correctly omits already-done tickets.
  //
  // Per-ticket phases are dispatched via driveTicketPhases() which inlines
  // the build-ticket.js sequential phase loop (agentType: phaseName per phase).
  // -----------------------------------------------------------------------
  const worktreeEpicPath = toWorktreePath(epic_path || target, realWorktreePath);

  const plannerResult = await agent(
    `Read Master_Plan.md at the epic folder: "${worktreeEpicPath}". Then read the frontmatter of every NN_*.md sub-ticket. ` +
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
  const epicTitle = plan.title || worktreeEpicPath;

  if (batches.length === 0) {
    return {
      status: "ok",
      message: `Epic "${epicTitle}" complete (or no tickets to run). All tickets are done or the epic is empty.`,
      epic_path: worktreeEpicPath,
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
          const worktreeTicketPath = toWorktreePath(ticket.path, realWorktreePath);
          // Drive each ticket through its needed phases using the flattened
          // per-phase driver (driveTicketPhases) so each phase runs under its
          // own agent template. No ticket-supervisor is dispatched here.
          // isEpicMember=true → the per-ticket pull-request phase is deferred;
          // finalize-feature opens the single epic-level PR.
          const result = await driveTicketPhases(worktreeTicketPath, true);
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
        epic_path: worktreeEpicPath,
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
    epic_path: worktreeEpicPath,
    title: epicTitle,
    worktree_path: realWorktreePath,
    batches_run: completedBatches.length,
    tickets_completed: totalTickets,
    completed_batches: completedBatches,
    message:
      `Epic "${epicTitle}" complete. ` +
      `${completedBatches.length} batch(es) run, ${totalTickets} ticket(s) completed.`,
  };
} else {
  // -----------------------------------------------------------------------
  // Single-ticket path: drive the ticket through its needed phases using the
  // flattened per-phase driver (driveTicketPhases). No ticket-supervisor is
  // dispatched — each needed phase is a separate flat depth-1 agent() call.
  // worktreeTicketPath is the ticket file INSIDE the real worktree so that
  // the planner reads accurate (post-drive) frontmatter statuses.
  // -----------------------------------------------------------------------
  const singleTicketPath = ticket_path || target;
  const worktreeTicketPath = toWorktreePath(singleTicketPath, realWorktreePath);

  const ticketResult = await driveTicketPhases(worktreeTicketPath);

  return ticketResult || {
    status: "error",
    message: `driveTicketPhases returned null for ticket: ${worktreeTicketPath}`,
  };
}
