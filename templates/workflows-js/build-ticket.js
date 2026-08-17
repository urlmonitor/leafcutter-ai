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
 *
 * E2 canonical form: top-level body, agent(prompt, opts), args global.
 * No export async function run() — E2 executes the top-level body directly.
 */

export const meta = {
  name: "build-ticket",
  description:
    "Drive a single ticket's phase agents from needed to fully signed-off. Uses a planner agent to read ticket frontmatter and return the ordered phase list, then dispatches each needed phase as a flat depth-1 agent() call. Handles failure adjudication via failure-classifier: mechanical failures are retried; cross-agent blockers are skipped; design/halt blockers surface a structured error to the user.",
  phases: [
    "status-checker (reads ticket frontmatter → ordered_phases)",
    "phase agents (sequential, depth 1)",
    "brainstorm-lead (conditional, on blocker result)",
  ],
};

// ---------------------------------------------------------------------------
// JSON Schemas for agent() responses
// The E2 engine enforces these and returns already-parsed objects.
// Do NOT call JSON.parse() on agent() results when schema is provided.
// ---------------------------------------------------------------------------

const PLANNER_SCHEMA = {
  type: 'object',
  required: ['ticket_path', 'ordered_phases'],
  properties: {
    ticket_path: { type: 'string' },
    title: { type: 'string' },
    files_touched: { type: 'array', items: { type: 'string' } },
    // has_test_requirements: true when the ticket's ## Test Requirements
    // block contains at least one "- name:" entry in the tests: array.
    // Used by the Test Requirements guard (BO-2000e-2) to block coder
    // dispatch for code tickets that lack populated Test Requirements.
    has_test_requirements: { type: 'boolean' },
    ordered_phases: {
      type: 'array',
      items: {
        type: 'object',
        required: ['agent', 'status'],
        properties: {
          agent: { type: 'string' },
          status: { type: 'string', enum: ['needed', 'signed_off', 'not_needed', 'failed'] },
        },
      },
    },
  },
}

const PHASE_RESULT_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocker', 'failed', 'question', 'handoff'] },
    result_status: { type: 'string' },
    message: { type: 'string' },
  },
  required: ['status'],
}

const CLASSIFY_SCHEMA = {
  type: 'object',
  properties: {
    classification: { type: 'string', enum: ['mechanical', 'cross_agent', 'design', 'halt'] },
    reason: { type: 'string' },
  },
  required: ['classification'],
}

const WORKTREE_SCHEMA = {
  type: 'object',
  properties: {
    git_type: { type: 'string' },
    branch: { type: 'string' },
  },
  required: ['git_type', 'branch'],
}

// ---------------------------------------------------------------------------
// Constants and helper functions (pure — no I/O)
// ---------------------------------------------------------------------------

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
  "llm-expert",                  // priority 8 — implements agent-template / skill / slash-command prompt work
  "test-runner",                 // priority 9
  "change-scope-reviewer",       // priority 10
  "documentation-expert",        // priority 10
  "explanation-author",          // priority 10
  "how-to-author",               // priority 10
  "reference-author",            // priority 10
  "pr-reviewer",                 // priority 11
  "ac-validator",                // priority 11.5 — AC coverage gate, MUST precede commit
  "user-surface-smoker",         // priority 11.5
  "ac-fulfillment-gate",         // priority 11.7 — AC store fulfillment gate, MUST precede commit
  "live-surface-tester",         // priority 11.8 — live-app proof, MUST precede commit
  "documentation-verifier",      // priority 11.9
  "commit",                      // priority 12
  "pull-request",                // priority 13
];

/**
 * Agent names already reported as absent from phaseOrder. Prevents the
 * O(n log n) comparator from emitting the same diagnostic repeatedly.
 * @type {Set<string>}
 */
const unknownPhaseAgentsReported = new Set();

/**
 * Return the canonical priority index for an agent name.
 *
 * An agent that is NOT a member of phaseOrder still receives a
 * sorts-last sentinel (phaseOrder.length) — throwing here would abort the
 * whole drive from inside a sort comparator for a merely-unregistered
 * project-local agent. But the omission is reported loudly on stderr,
 * naming both the agent and this file, because a *registered* phase agent
 * missing from this array silently sorts AFTER commit (12) and
 * pull-request (13) — which is how ac-validator, ac-fulfillment-gate and
 * live-surface-tester ran after their own commit for months.
 *
 * @param {string} agentName
 * @returns {number}
 */
function getPriority(agentName) {
  const idx = phaseOrder.indexOf(agentName);
  if (idx === -1) {
    if (!unknownPhaseAgentsReported.has(agentName)) {
      unknownPhaseAgentsReported.add(agentName);
      console.error(
        `[build-ticket.js] PHASE-ORDER GAP: agent "${agentName}" is not a member of ` +
        `the phaseOrder array in templates/workflows-js/build-ticket.js. It will be ` +
        `sorted LAST (index ${phaseOrder.length}) — i.e. AFTER commit and pull-request. ` +
        `If "${agentName}" is a registered ticket phase (is_ticket_phase: true in ` +
        `config/agent_registry.json), this is a BUG: add it to phaseOrder at its ` +
        `registry-declared priority.`
      );
    }
    return phaseOrder.length;
  }
  return idx;
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
// This fixes the false-halt that occurred when build-ticket was invoked from
// the session root (where CWD is the main clone, not the worktree).

phase('Worktree Guard')

const ticketPath = (args && (args.ticket_path || args.userInput || '').trim()) || '';

if (!ticketPath) {
  return {
    status: "error",
    message:
      "No ticket_path provided. Pass args: { ticket_path: '<path>' }",
  };
}

// If the caller already provided worktree_path in args, trust it — no ambient check.
const callerWorktreePath = args && args.worktree_path;

let gitInfo = null;

if (!callerWorktreePath) {
  // Fall back to the git info check when no worktree_path is provided in args.
  const worktreeCheck = await agent(
    "Run these two shell commands and report the results as JSON:\n" +
    "1. `test -f .git && echo file || echo directory` — determines if .git is a file (worktree) or directory (main clone)\n" +
    "2. `git branch --show-current` — reports the current branch name\n" +
    "Return ONLY a JSON object: { \"git_type\": \"file\"|\"directory\", \"branch\": \"<name>\" }",
    { agentType: "status-checker", schema: WORKTREE_SCHEMA, label: 'worktree-check', phase: 'Worktree Guard' }
  );

  gitInfo = worktreeCheck;

  if (gitInfo && (gitInfo.git_type === "directory" || gitInfo.branch === "main" || gitInfo.branch === "master")) {
    return {
      status: "error",
      worktree_required: true,
      message:
        "build-ticket.js must run inside a git worktree, not the main clone. " +
        "The current working directory has .git as a " + (gitInfo.git_type || 'unknown') +
        " (branch: " + (gitInfo.branch || 'unknown') + "). " +
        "Create a worktree first:\n" +
        "  /worktree create <branch-name>\n" +
        "Then re-run /build-feature from inside the worktree.",
      action_required: "create_worktree",
    };
  }
}

// -------------------------------------------------------------------------
// Phase 1 — Planner: read ticket frontmatter → ordered_phases JSON
// -------------------------------------------------------------------------

phase('Planner')

const plannerResult = await agent(
  `Read the ticket at "${ticketPath}". Extract the agents: map from the frontmatter and the files_touched list. Also check whether the ticket's ## Test Requirements section is populated: it is populated when there is a fenced code block after "## Test Requirements" that contains at least one "- name:" entry in the tests: array. Return a JSON object with exactly these keys: { "ticket_path": "<path>", "title": "<ticket title>", "files_touched": [...], "has_test_requirements": true|false, "ordered_phases": [{"agent": "<name>", "status": "<status>"}, ...] }. The ordered_phases array must list ALL agents from the agents: map in canonical phase priority order. Each entry must include the agent name and its current status (needed | signed_off | not_needed | failed). Return ONLY the JSON object, no prose.`,
  { agentType: "status-checker", schema: PLANNER_SCHEMA, label: 'ticket-planner', phase: 'Planner' }
)

const plan = plannerResult || {};
const orderedPhases = plan.ordered_phases || [];
const filesTouched = plan.files_touched || [];
const title = plan.title || ticketPath;

// -------------------------------------------------------------------------
// Test Requirements Guard — extracted from planner data (BO-2000e-2)
// -------------------------------------------------------------------------
// has_test_requirements is true only when the ticket's ## Test Requirements
// section contains at least one "- name:" entry in the tests: YAML array.
// When absent or false, coder phases are refused with a structured blocker.
const hasTestRequirements = plan.has_test_requirements === true;

// Agents that produce production code — must NOT run without Test Requirements.
const CODER_PHASES = new Set(["python-coder", "sql-coder", "frontend-coder"]);

// -------------------------------------------------------------------------
// Phase 2 — Guard: if no phases are needed, exit cleanly
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
// Phase 3 — Sequential phase loop
// -------------------------------------------------------------------------

phase('Phase Dispatch')

const retryCounts = {};
const completedPhases = [];
const skippedPhases = [];

for (const currentPhase of neededPhases) {
  const phaseName = currentPhase.agent;
  retryCounts[phaseName] = retryCounts[phaseName] || 0;

  let phaseResult;
  let retryLoop = true;

  // -----------------------------------------------------------------------
  // Test Requirements guard (BO-2000e-2): refuse to dispatch a coder phase
  // when the ticket's ## Test Requirements section is empty or absent.
  // Surfacing a structured blocker here prevents the phantom-test failure
  // mode where test-writer self-skips and the coder writes its own tests.
  // -----------------------------------------------------------------------
  if (CODER_PHASES.has(phaseName) && !hasTestRequirements) {
    return {
      status: "blocked",
      message:
        `Structured blocker: the coder phase '${phaseName}' cannot be ` +
        `dispatched because the ticket's ## Test Requirements section is ` +
        `empty or absent (BO-2000e-2). ` +
        `Add at least one test to the tests: array before re-running.`,
      ticket_path: ticketPath,
      failing_phase: phaseName,
      classification: "halt",
      suggested_action:
        "Populate ## Test Requirements in the ticket with at least one " +
        "'- name: ...' entry, then re-run /build-feature.",
    };
  }

  while (retryLoop) {
    retryLoop = false;

    phaseResult = await agent(
      `You are the ${phaseName} phase agent for ticket: ${ticketPath}. Read the ticket before starting. Execute your phase. Files touched: ${JSON.stringify(filesTouched)}. Return a JSON result with at minimum { "status": "ok" | "blocker" | "failed" }.`,
      { agentType: phaseName, schema: PHASE_RESULT_SCHEMA, label: phaseName, phase: 'Phase Dispatch' }
    )

    // ------------------------------------------------------------------
    // Failure detection
    // ------------------------------------------------------------------
    const resultStatus =
      phaseResult && (phaseResult.status || phaseResult.result_status);

    if (resultStatus === "blocker" || resultStatus === "failed") {
      const classifyResult = await agent(
        `Classify this blocker for ticket ${ticketPath}, failing phase ${phaseName}. Retry count: ${retryCounts[phaseName]}/${MAX_RETRIES}. Blocker detail: ${JSON.stringify(phaseResult)}. Return classification as one of: mechanical | cross_agent | design | halt.`,
        { agentType: "brainstorm-lead", schema: CLASSIFY_SCHEMA, label: 'failure-classifier', phase: 'Phase Dispatch' }
      )

      const classification =
        classifyResult && classifyResult.classification;

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
            ticket_path: ticketPath,
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

    completedPhases.push({ agent: phaseName, result: phaseResult });
  }
}

// -------------------------------------------------------------------------
// Phase 4 — Return success summary
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
