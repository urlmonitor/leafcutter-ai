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
    // existing_test_files: test files a PREVIOUS drive already wrote for this
    // ticket and that still exist on disk. Third satisfaction route for the
    // coder guard — without it, resuming a ticket whose test-writer is already
    // signed_off would re-block the coder forever, because test-writer is no
    // longer in the needed set and cannot re-supply its evidence.
    existing_test_files: { type: 'array', items: { type: 'string' } },
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
    // Test-evidence fields (BO-2000e-2 second satisfaction route). Populated by
    // the test-writer phase; ignored for every other phase. Both are optional so
    // that a phase agent which omits them leaves the coder guard CLOSED — absent
    // evidence must never read as satisfied evidence.
    tests_written: {
      type: 'array',
      items: { type: 'string' },
      description: 'Paths of test files this phase created or extended. Non-empty is the evidence that tests exist for the ticket.',
    },
    red_baseline_verified: {
      type: 'boolean',
      description: 'True when the phase ran the new tests and confirmed they fail (non-zero exit) before any implementation work.',
    },
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
    // The root of the worktree the check POSITIVELY identified. Optional:
    // when it is absent the isolated working copy stays undetermined and the
    // drive holds back (BO-1900a-4-i) rather than substituting the ambient
    // directory.
    worktree_path: { type: 'string' },
  },
  required: ['git_type', 'branch'],
}

/**
 * Reply shape of the post-dispatch record read-back (BO-2900f-1-i).
 *
 * `readable: false` is a first-class answer, not an error to be swallowed: an
 * unreadable record adjudicates the gate FAILED. Absent evidence must never
 * resolve to success.
 */
const RECORD_READBACK_SCHEMA = {
  type: 'object',
  properties: {
    readable: { type: 'boolean' },
    ticket_path: { type: 'string' },
    lifecycle_status: { type: 'string' },
    needed_phases: { type: 'array', items: { type: 'string' } },
    signoffs: {
      type: 'array',
      items: {
        type: 'object',
        properties: { agent: { type: 'string' }, status: { type: 'string' } },
      },
    },
    signed_off_agents: { type: 'array', items: { type: 'string' } },
    error: { type: 'string' },
  },
  required: ['readable'],
}

/** Reply shape of the ticket-completion write (BO-400a-2-ii). */
const COMPLETION_WRITE_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string' },
    ticket_path: { type: 'string' },
    error: { type: 'string' },
  },
  required: ['status'],
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
// Record adjudication — pure functions over a ticket record read back off disk
//
// TWIN: mirrors build-feature.js. Keep in sync with that file.
//
// BUG-23 (run wf_cc2b46d9-f6f): phase agents returned `status: ok` and left no
// sign-off in the ticket's record — ticket 01 lost test-runner AND pr-reviewer,
// ticket 03 lost test-runner, ticket 09 lost pr-reviewer. A gate's word for its
// own success is therefore never sufficient: the verdict the drive carries
// forward is derived from the record that was read back, never from the gate's
// own report of itself (BO-2900f-1-i).
// ---------------------------------------------------------------------------

/**
 * Sign-off statuses that count as a gate having PASSED.
 *
 * Anything else the record can carry — blocker, failed, question, handoff — is
 * evidence the gate did not pass and must never satisfy the completion trigger
 * (BO-400a-2-iii).
 *
 * @type {Array<string>}
 */
const POSITIVE_SIGNOFF_STATUSES = ["ok", "signed_off"];

/**
 * Every sign-off entry the record carries for one agent, in record order.
 *
 * @param {object|null} record
 * @param {string} agentName
 * @returns {Array<{agent: string, status: string}>}
 */
function signoffEntriesFor(record, agentName) {
  if (!record || !Array.isArray(record.signoffs)) {
    return [];
  }
  return record.signoffs.filter((s) => s && s.agent === agentName);
}

// BO-2900f-1-ii — "the latest entry is the one that counts" is implemented at
// the two places that need it (adjudicatePhaseAgainstRecord and
// completionVerdictFromRecord), each of which already holds the entries array
// to report its length. A latestSignoffFor() helper existed here and was never
// called by either; it is removed rather than left as a second, untested
// definition of the same rule.

/**
 * True when a sign-off entry represents a passing outcome.
 *
 * @param {{status: string}|null} entry
 * @returns {boolean}
 */
function isPassingSignoff(entry) {
  return (
    !!entry &&
    POSITIVE_SIGNOFF_STATUSES.indexOf(String(entry.status)) !== -1
  );
}

/**
 * Adjudicate ONE dispatched gate against the record that was read back.
 *
 * This is the single generic post-dispatch verification (BO-2900f-1-iii): it
 * belongs to the path every dispatch returns through, NOT to any named gate.
 * A per-gate call site would satisfy the gates it touches and leave the next
 * gate anyone adds unguarded — which is exactly how the observed run held on
 * one ticket and lapsed on the next.
 *
 * Fails closed: an unreadable record adjudicates the gate failed.
 *
 * @param {object|null} record — the read-back reply
 * @param {string} phaseName
 * @returns {{verified: boolean, reason: string|null, entries: number}}
 */
function adjudicatePhaseAgainstRecord(record, phaseName) {
  if (!record || record.readable !== true) {
    return {
      verified: false,
      entries: 0,
      reason:
        `the '${phaseName}' gate reported success but its outcome could not be ` +
        `confirmed: the ticket's record could not be read back` +
        (record && record.error ? ` (${record.error})` : "") +
        ". Absent evidence is adjudicated failed, never credited.",
    };
  }
  const entries = signoffEntriesFor(record, phaseName);
  if (entries.length === 0) {
    return {
      verified: false,
      entries: 0,
      reason:
        `the '${phaseName}' gate reported success while leaving no sign-off ` +
        `entry in the ticket's record`,
    };
  }
  const latest = entries[entries.length - 1];
  if (!isPassingSignoff(latest)) {
    return {
      verified: false,
      entries: entries.length,
      reason:
        `the latest sign-off entry for the '${phaseName}' gate in the ticket's ` +
        `record reads status '${latest.status}', which is not a passing outcome`,
    };
  }
  return { verified: true, entries: entries.length, reason: null };
}

/**
 * Decide FROM THE RECORD whether the ticket may be recorded done.
 *
 * BO-400a-2-ii: the trigger is the sign-offs actually present in the ticket's
 * own record — never the drive's in-memory tally of phases it thinks it ran
 * (the report and the record would then agree because they share one
 * unverified source), and never the delivery phase alone (a successful commit
 * proves code landed, not that the review and test gates ran).
 *
 * BO-400a-2-iii: held back, blocked, unrecorded and UNREADABLE all read as not
 * done. An unreadable record is handled as its own case rather than folded
 * into the empty-list path, because "no outstanding phases found" and "could
 * not look" must never produce the same answer. THE UNREADABLE CHECK RUNS
 * FIRST, ahead of the empty-required-set refusal below: a record that could not
 * be opened cannot support any claim about what the ticket names, and the two
 * conditions co-occur (a deleted record read back for a ticket whose phases are
 * all not_needed). Ordering, not presence, is what this clause turns on — both
 * refusals are correct in isolation.
 *
 * BO-400a-2-iv: AN EMPTY REQUIRED SET IS NOT A SATISFIED ONE, and this function
 * is the only place that can say so for every caller. The loop below collects
 * the phases that failed to prove themselves and reads an empty collection as
 * success; over an empty required set that collection is empty for the exactly
 * opposite reason — nothing was looked at. The two are separated HERE, before
 * the verdict is formed, rather than computed as `completed: true` and
 * overridden afterwards (an override is one refactor away from the defect
 * returning). And HERE rather than at whichever branch happens to reach this
 * function today: the vacuous decision is reachable from every route into it —
 * BO-1900a-4-ii is a second, independent one — so a guard placed on one route
 * leaves the rest live.
 *
 * TWIN: mirrors build-feature.js. Keep in sync with that file.
 *
 * @param {object|null} record — the last record read back during the drive
 * @param {{requiredPhases: Array<string>, unverifiedReasons: object,
 *          skippedAgents: Array<string>, dispatchedAgents: Array<string>}} ctx
 * @returns {{completed: boolean, unreadable: boolean, noPhaseRequired: boolean,
 *            outstanding: Array<{agent: string, reason: string}>,
 *            duplicates: Array<{agent: string, entries: number}>}}
 */
function completionVerdictFromRecord(record, ctx) {
  const required = ctx.requiredPhases || [];

  // BO-400a-2-iii — UNREADABLE ANSWERS FIRST, and the order is the whole guard.
  // `noPhaseRequired` is a claim about what the ticket's frontmatter SAYS; this
  // branch is the admission that the frontmatter was never read. When both
  // conditions hold, letting the empty-set refusal answer first reports
  // `unreadable: false` about a record nobody could open, discards
  // `record.error`, and sends the operator to edit the agents: map of a file
  // that is not there — a statement about the contents of a file the drive could
  // not open. "No outstanding phases found" and "could not look" must never
  // produce the same answer, least of all when the second is the true one.
  //
  // Nothing is lost by deciding it here: over an empty required set the map
  // below yields `outstanding: []`, so this branch returns the same not-done
  // verdict the empty-set refusal would have, and keeps the diagnosis with it.
  if (!record || record.readable !== true) {
    return {
      completed: false,
      unreadable: true,
      noPhaseRequired: false,
      duplicates: [],
      outstanding: required.map((agentName) => ({
        agent: agentName,
        reason:
          "the ticket's record could not be read back, so no sign-off could be " +
          "confirmed" +
          (record && record.error ? ` (${record.error})` : ""),
      })),
    };
  }

  // BO-400a-2-iv — the ticket names no phase for this drive to verify, so no
  // evidence was inspected and none could have been. Its own verdict, not a
  // satisfied one: there is nothing here to be outstanding, which is why the
  // per-phase loop below cannot detect this state and why the answer has to be
  // decided before that loop is ever reached.
  //
  // Reached only once the record has been READ, which is what makes the claim
  // it makes true: by here `record.readable === true`, so "this ticket names no
  // phase" is a fact established from the file rather than assumed about one
  // that could not be opened.
  if (required.length === 0) {
    return {
      completed: false,
      unreadable: false,
      noPhaseRequired: true,
      outstanding: [],
      duplicates: [],
    };
  }

  const outstanding = [];
  const duplicates = [];

  for (const agentName of required) {
    const entries = signoffEntriesFor(record, agentName);
    if (entries.length > 1) {
      duplicates.push({ agent: agentName, entries: entries.length });
    }
    if (entries.length === 0) {
      let reason;
      if (ctx.unverifiedReasons && ctx.unverifiedReasons[agentName]) {
        reason = ctx.unverifiedReasons[agentName];
      } else if ((ctx.skippedAgents || []).indexOf(agentName) !== -1) {
        reason =
          `'${agentName}' was skipped after a cross_agent blocker and left no ` +
          `sign-off entry in the record`;
      } else if ((ctx.dispatchedAgents || []).indexOf(agentName) === -1) {
        reason =
          `'${agentName}' is still needed and was never dispatched, so the ` +
          `record carries no sign-off entry for it`;
      } else {
        reason = `'${agentName}' left no sign-off entry in the record`;
      }
      outstanding.push({ agent: agentName, reason });
      continue;
    }
    const latest = entries[entries.length - 1];
    if (!isPassingSignoff(latest)) {
      outstanding.push({
        agent: agentName,
        reason:
          `the latest sign-off entry for '${agentName}' in the record reads ` +
          `status '${latest.status}', not a passing outcome`,
      });
    }
  }

  return {
    completed: outstanding.length === 0,
    unreadable: false,
    noPhaseRequired: false,
    outstanding,
    duplicates,
  };
}

/**
 * The phases whose sign-offs the completion decision requires.
 *
 * Union of what the drive was asked to run and what the RECORD still names as
 * needed (the record is the source of truth), minus phases the driver
 * deliberately deferred — an epic member's pull-request phase is opened once
 * per epic by finalize-feature, so it must not block the ticket forever.
 *
 * @param {Array<string>} drivenPhases
 * @param {Array<string>} recordNeededPhases
 * @param {Array<string>} deferredPhases
 * @returns {Array<string>}
 */
function requiredPhasesForCompletion(drivenPhases, recordNeededPhases, deferredPhases) {
  const deferred = deferredPhases || [];
  const out = [];
  for (const name of (drivenPhases || []).concat(recordNeededPhases || [])) {
    if (!name) continue;
    if (deferred.indexOf(name) !== -1) continue;
    if (out.indexOf(name) === -1) out.push(name);
  }
  return out;
}

/**
 * The phases a ticket CLAIMS are already complete.
 *
 * Used only when the drive has nothing to dispatch. "What the drive was asked
 * to run" is then empty, and a completion decision taken from an empty required
 * set is vacuous: it says yes to every ticket, including one whose frontmatter
 * reads signed_off while its record carries no sign-off entry at all — the
 * BUG-23 signature, inverted into a phantom-done write. The honest basis is
 * what the ticket itself claims: every agent in its map except the ones it
 * declares not_needed. Each of those must still be backed by a passing entry in
 * the record before the ticket may be recorded done.
 *
 * TWIN: mirrors build-feature.js. Keep in sync with that file.
 *
 * @param {Array<{agent: string, status: string}>} orderedPhases
 * @returns {Array<string>}
 */
function claimedPhasesForCompletion(orderedPhases) {
  const out = [];
  for (const entry of orderedPhases || []) {
    if (!entry || !entry.agent) continue;
    if (entry.status === "not_needed") continue;
    if (out.indexOf(entry.agent) === -1) out.push(entry.agent);
  }
  return out;
}

// ---------------------------------------------------------------------------
// The plan reply the drive cannot use (BO-1900a-4-ii)
//
// TWIN: mirrors build-feature.js. Keep in sync with that file.
//
// The reduction these two functions replace was `ticketPlan || {}` followed by
// `plan.ordered_phases || []`. Each substitution looks like defensive
// programming; in sequence they convert a dead planner into a completion claim.
// A missing reply becomes a blank record, a missing list becomes a blank list,
// the drive concludes the ticket needs no phase, takes its no-phases exit, and
// arrives at a completion decision with an empty required set. Nothing throws,
// because every step did exactly what it was written to do.
// ---------------------------------------------------------------------------

/**
 * Why the drive cannot use this plan reply — or null when it can.
 *
 * Pure. The polarity is deliberate and is the whole of the fix: the reply must
 * AFFIRMATIVELY carry an ordered list of phases, and everything else is
 * unusable. A check written the other way round — look for a reply that
 * DECLARES failure, treat the rest as usable — takes the usable branch on a
 * reply that simply omits the list, and an omitted list is precisely what a
 * truncated, timed-out or degraded planner produces.
 * This is the same correction already made to the epic-level re-check in
 * compareEpicTicketSets (`readable !== true`, not `readable === false`).
 *
 * DEFENCE IN DEPTH, stated accurately. `ordered_phases` is in the `required`
 * list of the planner schema this driver hands to agent() (TICKET_PLANNER_SCHEMA
 * in build-feature.js, PLANNER_SCHEMA in build-ticket.js), and the E2 engine
 * validates against that schema before the object ever reaches this function, so
 * a SCHEMA-CONFORMING reply that omits the list cannot arrive here. What CAN
 * arrive here — and what no schema can rule out — is the engine returning
 * nothing at all, or something that is not a record: the two branches above,
 * both genuinely reachable. The third branch is kept as the backstop for a reply
 * that bypasses or outlives that validation, and it costs nothing.
 *
 * An earlier version of this comment justified the function by calling the
 * omission "legal under TICKET_PLANNER_SCHEMA's optional list". That was false —
 * the guard is right and the reason given for it was not. Corrected rather than
 * deleted, because a false rationale left in a comment is how the next round
 * talks itself into the next defect.
 *
 * A stated EMPTY list is usable: it is an answer. Only "no reply / not a
 * record / states no list either way" is not.
 *
 * @param {*} reply — the ticket-planner reply, verbatim
 * @returns {string|null}
 */
function unusablePlanReason(reply) {
  if (reply === null || reply === undefined) {
    return "the planning step returned no reply at all";
  }
  if (typeof reply !== "object" || Array.isArray(reply)) {
    return (
      `the planning step returned a ${Array.isArray(reply) ? "list" : typeof reply}, ` +
      `which is not a usable plan record`
    );
  }
  if (!Array.isArray(reply.ordered_phases)) {
    return (
      "the planning step returned a record that states no ordered list of " +
      "phases either way"
    );
  }
  return null;
}

/**
 * The hold-back payload for a ticket whose plan reply could not be used.
 *
 * Pure. Sibling of the worktree-undetermined hold-back above and deliberately
 * shaped like it: an unanswered question stops the drive rather than being
 * filled in with a plausible substitute. Holding back means WRITING NOTHING —
 * the caller returns this before any read-back, any completion decision and any
 * phase dispatch, so the ticket's recorded state is left exactly as found.
 *
 * The reported reason names the PLANNING failure. It deliberately does not
 * describe the ticket as having no work left (it is not known whether it has
 * work — the reply that would have said so never arrived) and does not send the
 * operator looking for a phase that failed or a sign-off that is owed, because
 * no phase was ever identified, let alone dispatched.
 *
 * @param {string} recordPath
 * @param {string} reason — from unusablePlanReason()
 * @param {object} resolved — the drive's resolved target
 * @returns {object}
 */
function buildPlanHoldback(recordPath, reason, resolved) {
  return {
    status: "error",
    plan_undetermined: true,
    abort_reason: "ticket-plan-unusable",
    action_required: "obtain_ticket_plan",
    resolved_target: resolved,
    ticket_path: recordPath,
    ticket_completed: false,
    not_completed: true,
    held_back: true,
    plan_failure_reason: reason,
    message:
      `Held back before spawning any phase agent: the plan of phases for ` +
      `"${recordPath}" is UNDETERMINED because ${reason}. The drive therefore ` +
      `never learned which phases this ticket has, and an unusable plan reply ` +
      `is an unanswered question — it is NOT an answer that the ticket needs ` +
      `nothing. The ticket's recorded lifecycle state is left exactly as it ` +
      `was found, no completion decision was taken for it, and no phase agent ` +
      `was spawned.`,
    suggested_action:
      "Re-run the ticket-planner for this ticket and confirm its reply carries " +
      "an ordered_phases list. Nothing in the ticket's own record needs " +
      "correcting: the planning step failed before the record was consulted.",
  };
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
// Record I/O — the drive's only channel to the ticket's own record
//
// TWIN: mirrors build-feature.js. Keep in sync with that file.
// ---------------------------------------------------------------------------

/**
 * Read the ticket's record back off disk after a gate has run.
 *
 * The reply — not the gate's own report — is the deciding input for that
 * gate's verdict (BO-2900f-1-i). Reading and merely logging a warning while
 * still trusting the agent leaves the observed defect fully intact.
 *
 * @param {string} recordPath — absolute path to the ticket .md
 * @returns {Promise<object>} the read-back reply (readable:false when it failed)
 */
async function readTicketRecordBack(recordPath) {
  return await agent(
    `Read the ticket record at "${recordPath}" back off disk RIGHT NOW and report what it actually contains. ` +
    `Do not infer, do not remember, do not trust any earlier report about this ticket — open the file. ` +
    `Report: "lifecycle_status" (the frontmatter status: value), "needed_phases" (every agent in the frontmatter agents: map whose value is "needed"), ` +
    `and "signoffs": one entry per sign-off heading in the ## Comments section, in the order they appear, as {"agent": "<name>", "status": "<status>"} ` +
    `(heading form: "### YYYY-MM-DD HH:MM — <agent> (status: <status>)"). List EVERY matching heading, including repeats — do not de-duplicate them. ` +
    `If the record cannot be opened for any reason, return {"readable": false, "error": "<what went wrong>"} — an unreadable record is a real answer and will be treated as a failure, so never guess its contents. ` +
    `Otherwise return {"readable": true, "ticket_path": "${recordPath}", "lifecycle_status": "...", "needed_phases": [...], "signoffs": [...], "signed_off_agents": [...]}. ` +
    `Return ONLY the JSON object, no prose.`,
    {
      agentType: "status-checker",
      schema: RECORD_READBACK_SCHEMA,
      label: "signoff-readback",
      phase: "Phase Dispatch",
    }
  );
}

/**
 * Write the done lifecycle state into the ticket's OWN record.
 *
 * BUG-22: the observed run reported four completed batches while every ticket
 * in the store still read `status: todo`, which blocks finalize-feature's
 * archive check. A report is not a record.
 *
 * Only ever called once per ticket, and only after
 * completionVerdictFromRecord() confirmed every required phase carries a
 * passing sign-off in the record itself.
 *
 * @param {string} recordPath
 * @param {Array<string>} confirmedPhases
 * @returns {Promise<object>} the write reply
 */
async function writeTicketCompletion(recordPath, confirmedPhases) {
  return await agent(
    `Record the ticket at "${recordPath}" as complete in its own record. ` +
    `Every phase that ticket names as needed now carries a passing sign-off in the record itself, verified by reading it back: ${JSON.stringify(confirmedPhases)}. ` +
    `Edit the ticket's frontmatter so that "status:" reads done. Change nothing else — do not touch the agents: map, the ## Sign-offs checklist, or the ## Comments section. ` +
    `If the record cannot be written, return {"status": "error", "error": "<what went wrong>"} rather than reporting success. ` +
    `Return ONLY the JSON object: {"status": "ok"|"error", "ticket_path": "${recordPath}"}.`,
    {
      agentType: "status-checker",
      schema: COMPLETION_WRITE_SCHEMA,
      label: "ticket-completion-write",
      phase: "Phase Dispatch",
    }
  );
}

/**
 * Build the driver's per-ticket outcome payload.
 *
 * Pure. `ticket_completed` is the machine-readable verdict; `not_completed`
 * and `outstanding_phases` make the same fact readable to an operator, so a
 * ticket that ran every phase but could not be confirmed is never presented
 * as completed work (BO-400a-2-iii).
 *
 * @returns {object}
 */
function buildTicketOutcome(spec) {
  const completedAgents = spec.completedPhases.map((p) => p.agent);
  const skippedOut = spec.skippedPhases.map((p) => ({
    agent: p.agent,
    reason: p.reason,
  }));
  const base = {
    // Provisional. The not-completed branch below overwrites it — see the
    // comment there for why this field cannot stay "ok" on that path.
    status: "ok",
    ticket_path: spec.recordPath,
    title: spec.title,
    resolved_target: spec.resolvedTarget,
    completed_phases: completedAgents,
    skipped_phases: skippedOut,
  };

  // BO-2900f-1-ii — surface the duplicate, do not swallow it. Set BEFORE the
  // completed/not-completed branch, because the completed path is precisely
  // where a duplicate is otherwise invisible: the adjudication resolved it
  // cleanly from the latest entry, and with no outstanding-phase list for the
  // operator to inspect, an unreported duplicate leaves the write-side defect
  // (BO-2900f-2-ii) masked for as long as this read-side rule keeps
  // compensating for it. Omitted entirely when there are no duplicates — a
  // report naming every gate is indistinguishable from no report at all.
  if (spec.verdict.duplicates && spec.verdict.duplicates.length > 0) {
    base.duplicate_signoff_entries = spec.verdict.duplicates;
  }

  if (spec.verdict.completed && spec.writeApplied) {
    base.ticket_completed = true;
    base.recorded_status = "done";
    base.message = spec.noPhasesToRun
      ? `Ticket "${spec.title}" had no phase left to run, and its own record ` +
        `carries a passing sign-off for every phase it names. Recorded done ` +
        `without dispatching any phase agent.`
      : `Ticket "${spec.title}" driven to completion and recorded done in its own record. ` +
        `${completedAgents.length} phase(s) completed` +
        (skippedOut.length > 0
          ? `, ${skippedOut.length} skipped (cross_agent blockers).`
          : ".");
    if (spec.noPhasesToRun) {
      base.no_phases_dispatched = true;
    }
    return base;
  }

  // BO-400a-2-iii — `status` is the machine-readable signal in these drivers:
  // every other failure exit (the coder guard, the null-result guard, the
  // retry cap, design/halt) emits blocked or error, and build-feature.js's epic
  // loop branches on exactly that vocabulary. Leaving "ok" here while the same
  // payload carries `ticket_completed: false`, `not_completed` and an
  // outstanding-phase list inverts the signal for every caller that reads the
  // field first — and this payload is returned verbatim as the whole script
  // result, with no compensating re-derivation anywhere.
  base.status = "blocked";
  base.ticket_completed = false;
  base.not_completed = true;
  base.outstanding_phases = spec.verdict.outstanding;
  if (spec.unverifiedPhases.length > 0) {
    base.unverified_phases = spec.unverifiedPhases.map((u) => u.agent);
  }
  if (spec.writeError) {
    base.completion_write_error = spec.writeError;
  }
  if (spec.noPhasesToRun) {
    base.no_phases_dispatched = true;
  }

  // BO-400a-2-iv — the refusal taken over an EMPTY required set needs its own
  // wording, and this is why. The standard message below counts outstanding
  // phases and the standard advice tells the operator to re-run the phase that
  // failed or supply the sign-off it owes. With no phase required of the ticket
  // at all there is no count to state, nothing to re-run and nothing that owes
  // a sign-off, so that advice names nothing the operator can act on and sends
  // them looking for a phase failure that never happened. What IS actionable is
  // the ticket's own list of phases: it is the thing that is wrong.
  if (spec.verdict.noPhaseRequired) {
    base.no_phase_required = true;
    base.message =
      `Ticket "${spec.title}" was NOT recorded complete: it names no phase for ` +
      `this drive to verify. Its own list of phases — the agents: map in its ` +
      `frontmatter — is absent, empty, or marks every phase it names as ` +
      `not_needed, so the required set was empty and NOTHING about this ticket ` +
      `was verified. An empty set of outstanding phases means nothing was ` +
      `looked at, never that everything passed.`;
    base.suggested_action =
      "Correct the ticket's own list of phases: edit the agents: map in its " +
      "frontmatter so it names the phases this ticket actually requires, then " +
      "re-run the drive. Do not look for a failed phase or a missing sign-off — " +
      "this ticket asked for neither, which is the problem.";
    return base;
  }

  const detail = spec.verdict.outstanding
    .map((o) => `${o.agent} (${o.reason})`)
    .join("; ");
  base.message =
    `Ticket "${spec.title}" was NOT recorded complete. ` +
    (spec.verdict.unreadable
      ? `Its record could not be read back, so the lifecycle state was left untouched. `
      : `${spec.verdict.outstanding.length} needed phase(s) are outstanding in the ticket's own record: ${detail}. `) +
    (spec.writeError ? `The completion write failed: ${spec.writeError}. ` : "") +
    `${completedAgents.length} phase(s) confirmed` +
    (skippedOut.length > 0 ? `, ${skippedOut.length} skipped.` : ".");
  base.suggested_action =
    "Inspect the ticket's ## Comments section. A phase named above ran and " +
    "returned success without leaving its sign-off: re-run that phase (or add " +
    "the sign-off it owes) and re-run the drive. The ticket stays out of the " +
    "completed set until its own record can prove every needed phase passed.";
  return base;
}

/**
 * Take the completion decision for this ticket and record it.
 *
 * THE SINGLE EXIT for a ticket that reaches the end of its drive — whether it
 * ran twelve phases or none. Read-back → adjudicate against the record → write
 * done only if the record proves it → emit the outcome payload.
 *
 * It exists because the empty-needed-phase case used to bypass all of that with
 * a bare `{status: "ok"}` carrying no `ticket_completed` key. build-feature.js's
 * epic loop filters on exactly that key, so a ticket whose phases were all
 * already signed_off landed in the incomplete set and blocked the epic while
 * naming nothing to fix — and the block was unrecoverable, because a re-run is
 * byte-identical and there is no sign-off left to add. Worse, it is reached by
 * following this driver's own remediation advice ("add the sign-off it owes",
 * which flips the last agent to signed_off and empties the needed set) and by a
 * transient completion-write failure. Keeping both exits on one path is what
 * stops the next one being added off it.
 *
 * TWIN: mirrors build-feature.js. Keep in sync with that file.
 *
 * @param {{recordPath: string, title: string, record: object|null,
 *          basePhases: Array<string>, deferredPhases: Array<string>,
 *          completedPhases: Array<object>, skippedPhases: Array<object>,
 *          unverifiedPhases: Array<object>, unverifiedReasons: object,
 *          dispatchedAgents: Array<string>, noPhasesToRun: boolean}} spec
 * @returns {Promise<object>} the per-ticket outcome payload
 */
async function concludeTicket(spec) {
  const record = spec.record;

  const requiredPhases = requiredPhasesForCompletion(
    spec.basePhases,
    (record && record.needed_phases) || [],
    spec.deferredPhases
  );

  const verdict = completionVerdictFromRecord(record, {
    requiredPhases,
    unverifiedReasons: spec.unverifiedReasons || {},
    skippedAgents: (spec.skippedPhases || []).map((p) => p.agent),
    dispatchedAgents: spec.dispatchedAgents || [],
  });

  let writeApplied = false;
  let writeError = null;

  if (verdict.completed) {
    const writeResult = await writeTicketCompletion(spec.recordPath, requiredPhases);
    if (writeResult && writeResult.status === "ok") {
      writeApplied = true;
    } else {
      writeError =
        (writeResult && writeResult.error) ||
        "the completion write returned no usable result";
    }
  }

  return buildTicketOutcome({
    recordPath: spec.recordPath,
    title: spec.title,
    resolvedTarget,
    completedPhases: spec.completedPhases || [],
    skippedPhases: spec.skippedPhases || [],
    unverifiedPhases: spec.unverifiedPhases || [],
    verdict,
    writeApplied,
    writeError,
    noPhasesToRun: spec.noPhasesToRun === true,
  });
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
const callerWorktreePath = (args && args.worktree_path) || null;

/**
 * The resolved target this drive emits for its consumers.
 *
 * BO-1900a-4: `worktree_path: null` is the unambiguous not-yet-determined
 * marker. It is deliberately NOT a path-shaped stand-in — absent is not a
 * location, and a consumer must be able to tell "not determined" from a real
 * location using the target alone, without comparing it against the ticket's
 * or epic's work-store folder to discover the two are the same.
 *
 * TWIN: mirrors build-feature.js. Keep in sync with that file.
 */
const resolvedTarget = {
  target_type: "ticket",
  epic_path: null,
  ticket_path: ticketPath,
  worktree_path: null,
};

let gitInfo = null;

if (callerWorktreePath) {
  resolvedTarget.worktree_path = callerWorktreePath;
} else {
  // No caller-supplied working copy. The ambient git check may POSITIVELY
  // identify one — .git as a file on a non-protected branch is a real,
  // verified worktree, and its root is reported explicitly. What the check
  // must never do is answer the question by reaching for whatever is nearest:
  // if it cannot identify a worktree, the working copy stays undetermined and
  // the drive holds back (BO-1900a-4-i).
  const worktreeCheck = await agent(
    "Run these shell commands and report the results as JSON:\n" +
    "1. `test -f .git && echo file || echo directory` — determines if .git is a file (worktree) or directory (main clone)\n" +
    "2. `git branch --show-current` — reports the current branch name\n" +
    "3. `git rev-parse --show-toplevel` — reports the absolute root of the working copy you are in\n" +
    "Report worktree_path ONLY from command 3, and ONLY when command 1 said \"file\". " +
    "If any command fails, or .git is a directory, omit worktree_path entirely — do NOT substitute the current directory, the ticket's folder, or any other location you can find.\n" +
    "Return ONLY a JSON object: { \"git_type\": \"file\"|\"directory\", \"branch\": \"<name>\", \"worktree_path\": \"<absolute path, omit if unknown>\" }",
    { agentType: "status-checker", schema: WORKTREE_SCHEMA, label: 'worktree-check', phase: 'Worktree Guard' }
  );

  gitInfo = worktreeCheck;

  if (gitInfo && (gitInfo.git_type === "directory" || gitInfo.branch === "main" || gitInfo.branch === "master")) {
    return {
      status: "error",
      worktree_required: true,
      resolved_target: resolvedTarget,
      message:
        "build-ticket.js must run inside a git worktree, not the main clone. " +
        "The current working directory has .git as a " + (gitInfo.git_type || 'unknown') +
        " (branch: " + (gitInfo.branch || 'unknown') + "), so there is no isolated " +
        "working copy for this drive and no phase agent will be spawned. " +
        "Create a worktree first:\n" +
        "  /worktree create <branch-name>\n" +
        "Then re-run /build-feature from inside the worktree.",
      action_required: "create_worktree",
    };
  }

  if (gitInfo && gitInfo.git_type === "file") {
    resolvedTarget.worktree_path = gitInfo.worktree_path || null;
  }
}

// BO-1900a-4-i — the refusal that makes the marker load-bearing. An unanswered
// question about where the work belongs stops the drive instead of being
// answered by whatever is nearest: no fallback to the process's current
// directory, to the ticket's folder in the work store, or to any other
// location the driver could reach for.
if (!resolvedTarget.worktree_path) {
  return {
    status: "error",
    worktree_undetermined: true,
    abort_reason: "worktree-undetermined",
    resolved_target: resolvedTarget,
    message:
      "The isolated working copy for this drive is UNDETERMINED — no worktree " +
      "was supplied by the caller and the ambient git check could not identify " +
      "one. No phase agent has been spawned. build-ticket.js will NOT fall back " +
      "to the directory the process happens to be running in, to the ticket's " +
      "folder in the work store, or to any other existing location: an agent " +
      "sent to the wrong working copy commits in the wrong repository, and that " +
      "is discovered only after the fact.",
    action_required: "establish_worktree",
    suggested_action:
      "Establish the isolated working copy first — run /worktree create <branch-name> " +
      "— then re-run with args: { ticket_path: '<path>', worktree_path: '<absolute worktree root>' }.",
  };
}

// -------------------------------------------------------------------------
// Phase 1 — Planner: read ticket frontmatter → ordered_phases JSON
// -------------------------------------------------------------------------

phase('Planner')

const plannerResult = await agent(
  `Read the ticket at "${ticketPath}". Extract the agents: map from the frontmatter and the files_touched list. Also check whether the ticket's ## Test Requirements section is populated: it is populated when there is a fenced code block after "## Test Requirements" that contains at least one "- name:" entry in the tests: array. Also report "existing_test_files": test files a previous drive already wrote for this ticket. Find them by reading any test-writer sign-off in the ticket's ## Comments section and collecting the test file paths it names, then verifying with the shell that each path actually EXISTS on disk. List only paths you confirmed exist; return [] if there is no test-writer sign-off, it names no files, or the named files are gone. Do not guess a path from the ticket title or a naming convention. Return a JSON object with exactly these keys: { "ticket_path": "<path>", "title": "<ticket title>", "files_touched": [...], "has_test_requirements": true|false, "existing_test_files": [...], "ordered_phases": [{"agent": "<name>", "status": "<status>"}, ...] }. The ordered_phases array must list ALL agents from the agents: map in canonical phase priority order. Each entry must include the agent name and its current status (needed | signed_off | not_needed | failed). Return ONLY the JSON object, no prose.`,
  { agentType: "status-checker", schema: PLANNER_SCHEMA, label: 'ticket-planner', phase: 'Planner' }
)

// BO-1900a-4-ii — an unusable plan reply holds the ticket back. It is never
// reduced to a blank record and then to a blank list, which is what turned a
// dead planner into a `status: done` write.
const planReason = unusablePlanReason(plannerResult);
if (planReason) {
  return buildPlanHoldback(ticketPath, planReason, resolvedTarget);
}

const plan = plannerResult;
const orderedPhases = plan.ordered_phases;
const filesTouched = plan.files_touched || [];
const title = plan.title || ticketPath;

// -------------------------------------------------------------------------
// Test Requirements Guard — extracted from planner data (BO-2000e-2)
// -------------------------------------------------------------------------
// Three satisfaction routes, any of which proves tests exist before a coder runs:
//   1. the ticket ships a populated ## Test Requirements section (at least one
//      "- name:" entry in the tests: YAML array), OR
//   2. the test-writer phase runs earlier in this same drive and returns evidence
//      of test files it wrote (see the test-writer branch in the phase loop), OR
//   3. a previous drive already wrote test files that still exist on disk.
//
// Route 3 covers RESUME. Once test-writer is signed_off it drops out of the needed
// set, so on a re-run it can never re-supply route 2's evidence — the ticket would
// deadlock permanently on the second drive. The planner verifies these paths exist
// on disk, so this is evidence, not a status flag.
//
// Route 2 exists because test-writer has a mandatory AC-derivation fallback: when
// ## Test Requirements is absent it resolves the ticket's source_ac and derives the
// tests from the AC store instead. Reading the planner's pre-drive snapshot as an
// immutable fact ignored that fallback entirely and deadlocked every AC-generated
// ticket (no surface has emitted ## Test Requirements since v2.0.0), so this must
// stay a `let` that route 2 can flip. When neither route produces evidence, coder
// phases are refused with a structured blocker.
const existingTestFiles = Array.isArray(plan.existing_test_files)
  ? plan.existing_test_files.filter((p) => typeof p === 'string' && p.trim())
  : []
let hasTestRequirements =
  plan.has_test_requirements === true || existingTestFiles.length > 0;

// Agents that produce production code — must NOT run without Test Requirements.
const CODER_PHASES = new Set(["python-coder", "sql-coder", "frontend-coder"]);

// -------------------------------------------------------------------------
// Phase 2 — Guard: compute the phases this drive will dispatch
// -------------------------------------------------------------------------

const neededPhases = sortByCanonicalPriority(
  orderedPhases.filter((p) => p.status === "needed")
);

// -------------------------------------------------------------------------
// Phase 3 — Sequential phase loop
// -------------------------------------------------------------------------

phase('Phase Dispatch')

// BO-1900a-4-i — the pre-dispatch working-copy check. Unreachable in the
// normal flow (the worktree guard above already held the drive back), and
// deliberately kept anyway: the refusal belongs at the point where a phase
// agent would be spawned, so a future edit that reorders the guard cannot
// silently start dispatching against an undetermined working copy.
if (!resolvedTarget.worktree_path) {
  return {
    status: "error",
    worktree_undetermined: true,
    abort_reason: "worktree-undetermined",
    resolved_target: resolvedTarget,
    ticket_path: ticketPath,
    message:
      "Held back before spawning any phase agent: the isolated working copy " +
      "for this drive is UNDETERMINED. No substitute location is used.",
    action_required: "establish_worktree",
  };
}

// deferredPhases: build-ticket.js drives one standalone ticket, so nothing is
// deferred to an epic-level step. Kept as an explicit empty list rather than a
// bare [] at the call site so the twin's epic-member case (which defers
// pull-request) lines up line-for-line with this one.
const deferredPhases = [];

// No phase left to run. NOT a reason to skip the completion decision: the
// ticket's record already holds whatever evidence exists, and it is the only
// thing that can say whether this ticket is done. Bypassing the read-back here
// is what made an already-finished ticket unrecoverably block its epic when
// this driver's twin drove it (see concludeTicket's header for the full
// failure).
//
// The required set is what the ticket CLAIMS is complete, not what the drive
// ran — the drive ran nothing, and an empty required set would say yes to every
// ticket, including one whose frontmatter reads signed_off while its record
// carries no sign-off entry at all.
if (neededPhases.length === 0) {
  return await concludeTicket({
    recordPath: ticketPath,
    title,
    record: await readTicketRecordBack(ticketPath),
    basePhases: claimedPhasesForCompletion(orderedPhases),
    deferredPhases,
    completedPhases: [],
    skippedPhases: [],
    unverifiedPhases: [],
    unverifiedReasons: {},
    dispatchedAgents: [],
    noPhasesToRun: true,
  });
}

const retryCounts = {};
const completedPhases = [];
const skippedPhases = [];

// Post-dispatch verification state (BO-2900f-1-i/-iii).
//   unverifiedPhases — gates that reported success and could not be confirmed
//                      against the record. Their verdict is FAILED.
//   lastRecord       — the most recent readable read-back. The completion
//                      decision is taken from this and nothing else, so it is
//                      never taken from the drive's own tally (BO-400a-2-ii).
const unverifiedPhases = [];
const unverifiedReasons = {};
const dispatchedAgents = [];
let lastRecord = null;

for (const currentPhase of neededPhases) {
  const phaseName = currentPhase.agent;
  retryCounts[phaseName] = retryCounts[phaseName] || 0;

  // -----------------------------------------------------------------------
  // Test Requirements guard (BO-2000e-2): refuse to dispatch a coder phase
  // unless tests are known to exist — either declared in the ticket's
  // ## Test Requirements section, or written by test-writer earlier in this
  // drive. Fail-closed: if neither route produced evidence, block. This still
  // catches the phantom-test failure mode where test-writer self-skips and the
  // coder would otherwise write its own tests.
  // -----------------------------------------------------------------------
  if (CODER_PHASES.has(phaseName) && !hasTestRequirements) {
    const testWriterRan = neededPhases.some((p) => p.agent === "test-writer");
    return {
      status: "blocked",
      message:
        `Structured blocker: the coder phase '${phaseName}' cannot be ` +
        `dispatched because no tests exist for this ticket (BO-2000e-2). ` +
        `The ticket's ## Test Requirements section is empty or absent` +
        (testWriterRan
          ? `, and the test-writer phase did not report any test files it wrote.`
          : `, and no test-writer phase is scheduled for this ticket.`),
      ticket_path: ticketPath,
      resolved_target: resolvedTarget,
      not_completed: true,
      ticket_completed: false,
      outstanding_phases: [
        {
          agent: phaseName,
          reason:
            `'${phaseName}' is needed and was held back before dispatch: no ` +
            `tests exist for this ticket (BO-2000e-2)`,
        },
      ],
      failing_phase: phaseName,
      classification: "halt",
      suggested_action: testWriterRan
        ? "test-writer ran but returned no 'tests_written' evidence. Inspect its " +
          "sign-off in the ticket's ## Comments: if it genuinely wrote tests, the " +
          "evidence field is missing from its result; if it self-skipped, populate " +
          "## Test Requirements or fix the ticket's source_ac so the AC-derivation " +
          "fallback can resolve."
        : "Populate ## Test Requirements in the ticket with at least one " +
          "'- name: ...' entry, or mark test-writer as needed so it can derive " +
          "tests from the ticket's source_ac, then re-run /build-feature.",
    };
  }

  let phaseResult;
  let retryLoop = true;

  while (retryLoop) {
    retryLoop = false;

    // The trailing pointer block is load-bearing, not decoration (BO-1900d-1).
    // templates/agents/_signoff_block.md — carried by 30 agent templates,
    // including every phase agent — opens with
    // "## Sign-off (when ticket_path is provided)" and closes with
    // "Skip this entire section if no `ticket_path` was provided". A gate handed
    // the path only as narrative ("for ticket: <path>") has to decide for itself
    // whether its own conditional is satisfied, which is a very plausible
    // mechanism for BUG-23 having been INCONSISTENT rather than uniformly
    // absent: on run wf_cc2b46d9-f6f ticket 09 recorded test-runner and lost
    // pr-reviewer while ticket 03 did the reverse.
    //
    // Prose is the ONLY channel. agent(prompt, opts) accepts exactly
    // {agentType, schema, label, phase, model, effort, isolation} — an extra
    // `ticket_path` key placed in opts is dropped before the agent ever sees it,
    // so putting it there would look like a fix and pass nothing. The literal
    // `key: value` token below is the in-repo convention for this channel
    // (build-epic.js:357 hands worktree_path the same way).
    //
    // TWIN: mirrors build-feature.js. Keep in sync with that file.
    phaseResult = await agent(
      `You are the ${phaseName} phase agent for ticket: ${ticketPath}. Read the ticket before starting. Execute your phase. Files touched: ${JSON.stringify(filesTouched)}. Return a JSON result with at minimum { "status": "ok" | "blocker" | "failed" }.` +
      (phaseName === 'test-writer'
        ? ` You MUST also return "tests_written": a list of the test file paths you created or extended, and "red_baseline_verified": true only if you ran those tests and confirmed they fail. Return "tests_written": [] if you wrote no tests (for example if you self-skipped) — an empty list is the correct, honest answer and will stop the coder phase rather than let it run untested. Do not list a file you did not actually write.`
        : '') +
      `\n\nYou WERE invoked with the arguments below. Your sign-off protocol is ` +
      `therefore in force: record your outcome in this ticket's own record before ` +
      `you return.\n` +
      `ticket_path: ${ticketPath}\n` +
      `worktree_path: ${resolvedTarget.worktree_path}`,
      { agentType: phaseName, schema: PHASE_RESULT_SCHEMA, label: phaseName, phase: 'Phase Dispatch' }
    );

    // ------------------------------------------------------------------
    // THE VERIFICATION POINT (BO-2900f-1-i / -iii)
    //
    // One generic point, reached exactly once per dispatch, for EVERY gate —
    // not one added at each gate's call site. The observed defect was not a
    // broken gate, it was an inconsistently applied check: ticket 09 recorded
    // test-runner correctly while ticket 01 did not, and ticket 03 recorded
    // pr-reviewer correctly while ticket 01 did not. Anchoring the check to
    // the dispatch path is what makes the guarantee a property of the drive
    // rather than of a lucky work item.
    // ------------------------------------------------------------------
    dispatchedAgents.push(phaseName);

    const phaseRecord = await readTicketRecordBack(ticketPath);
    if (phaseRecord && phaseRecord.readable === true) {
      lastRecord = phaseRecord;
    } else {
      lastRecord = null;
    }
    const verdict = adjudicatePhaseAgainstRecord(phaseRecord, phaseName);

    // ------------------------------------------------------------------
    // Failure detection
    // ------------------------------------------------------------------
    const resultStatus =
      phaseResult && (phaseResult.status || phaseResult.result_status);

    // Null / empty-status guard: agent() returns null when a phase agent dies
    // on a terminal error or is skipped mid-run. Without this guard a null
    // result falls through the blocker/failed check below and the phase is
    // silently recorded as completed — letting the driver proceed to commit /
    // pull-request on incomplete work. It is also the difference between a
    // structured blocker and a stack trace: the test-writer branch further down
    // dereferences phaseResult.tests_written, which throws on null and aborts
    // the whole drive. Treat an absent result or unrecognized status as a halt
    // so the ticket stops rather than shipping half-done.
    //
    // TWIN: mirrors build-feature.js. Keep in sync with that file.
    if (!phaseResult || !resultStatus) {
      return {
        status: "blocked",
        message:
          `Phase '${phaseName}' returned no usable result (agent died, was ` +
          `skipped, or returned an empty status). Halting to avoid proceeding ` +
          `on incomplete work.`,
        ticket_path: ticketPath,
        failing_phase: phaseName,
        classification: "halt",
      };
    }

    // ------------------------------------------------------------------
    // Handoff routing (BO-3000)
    // ------------------------------------------------------------------
    // `handoff` is a valid PHASE_RESULT_SCHEMA status meaning "another
    // agent must act before I can proceed" — it is NOT a success and must
    // never fall through to the completed-phase path below. Without this
    // branch a handoff result was indistinguishable from `status: "ok"`:
    // the loop advanced to the next phase in phaseOrder and the named
    // agent was never re-dispatched (see BO-3000 for the live incident).
    // Kept deliberately identical to the build-feature.js handler.
    if (resultStatus === "handoff") {
      const handoffTarget = phaseResult.handoff_target;
      const normalizedTarget =
        typeof handoffTarget === "string" ? handoffTarget.trim() : "";
      const isKnownAgent =
        normalizedTarget !== "" && phaseOrder.includes(normalizedTarget);

      if (!isKnownAgent) {
        return {
          status: "blocked",
          message:
            `Phase '${phaseName}' returned 'status: handoff' but named no ` +
            `recognizable handoff_target ('${handoffTarget}'). Refusing to ` +
            `guess a re-dispatch target and refusing to advance to the ` +
            `next phase in phaseOrder. Inspect '${phaseName}'’s message ` +
            `and the ticket's ## Comments for the intended target agent, ` +
            `then re-run /build-ticket.`,
          ticket_path: ticketPath,
          failing_phase: phaseName,
          blocker_detail: phaseResult,
          classification: "halt",
        };
      }

      log(
        `Phase '${phaseName}' returned 'status: handoff' naming ` +
        `'${normalizedTarget}'. Re-dispatching '${normalizedTarget}' ` +
        `before advancing to any later phase in phaseOrder.`
      );

      const handoffResult = await agent(
        `You are the ${normalizedTarget} phase agent for ticket: ` +
        `${ticketPath}. You are being RE-DISPATCHED because phase ` +
        `'${phaseName}' returned 'status: handoff' naming you as the agent ` +
        `that must act before it can proceed. Handoff message: ` +
        `${JSON.stringify(phaseResult.message || "")}. Read the ticket ` +
        `before starting. Execute your phase. Files touched: ` +
        `${JSON.stringify(filesTouched)}. Return a JSON result with at ` +
        `minimum { "status": "ok" | "blocker" | "failed" }.`,
        {
          agentType: normalizedTarget,
          schema: PHASE_RESULT_SCHEMA,
          label: normalizedTarget,
          phase: 'Phase Dispatch',
        }
      );

      return {
        status: "blocked",
        message:
          `Phase '${phaseName}' returned 'status: handoff' naming ` +
          `'${normalizedTarget}'. '${normalizedTarget}' was re-dispatched ` +
          `to resolve the handoff; re-run /build-ticket to continue this ` +
          `ticket's remaining phases once the handoff is resolved.`,
        ticket_path: ticketPath,
        failing_phase: phaseName,
        handoff_target: normalizedTarget,
        handoff_result: handoffResult,
        classification: "cross_agent",
      };
    }

    if (resultStatus === "blocker" || resultStatus === "failed") {
      const classifyResult = await agent(
        `Classify this blocker for ticket ${ticketPath}, failing phase ${phaseName}. Retry count: ${retryCounts[phaseName]}/${MAX_RETRIES}. Blocker detail: ${JSON.stringify(phaseResult)}. Return classification as one of: mechanical | cross_agent | design | halt.`,
        { agentType: "brainstorm-lead", schema: CLASSIFY_SCHEMA, label: 'failure-classifier', phase: 'Phase Dispatch' }
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

    // Satisfaction route 2 for the coder guard (BO-2000e-2): test-writer
    // succeeded AND named at least one test file it wrote. Evidence must be
    // explicit — a bare `status: ok` is NOT enough, because test-writer signs
    // off ok when it self-skips too. Only a non-empty tests_written list opens
    // the gate for the coder phases that follow (test-writer is priority 5,
    // every coder is 6+, so this always lands before the guard is consulted).
    if (phaseName === 'test-writer') {
      const testsWritten = Array.isArray(phaseResult.tests_written)
        ? phaseResult.tests_written.filter((p) => typeof p === 'string' && p.trim())
        : [];
      if (testsWritten.length > 0) {
        hasTestRequirements = true;
        log(
          `test-writer wrote ${testsWritten.length} test file(s) for "${title}" ` +
          `(red baseline ${phaseResult.red_baseline_verified === true ? "verified" : "NOT verified"}) ` +
          `— coder phases unblocked.`
        );
      } else {
        log(
          `test-writer returned no tests_written evidence for "${title}" — ` +
          `coder phases remain blocked.`
        );
      }
    }

    // The verdict the drive carries forward is the one derived from the
    // record — never the gate's own report. A gate that reported success and
    // left no entry (or whose record could not be read) is FAILED here, and
    // is not carried forward as a completed phase. The drive continues so the
    // remaining gates still run and are reported, but the ticket can no
    // longer be recorded complete.
    if (!verdict.verified) {
      unverifiedPhases.push({ agent: phaseName, reason: verdict.reason });
      unverifiedReasons[phaseName] = verdict.reason;
      log(
        `VERIFICATION FAILED for '${phaseName}' on ${ticketPath}: ${verdict.reason}. ` +
        `The gate is adjudicated failed and is NOT counted as completed.`
      );
    } else {
      if (verdict.entries > 1) {
        log(
          `'${phaseName}' carries ${verdict.entries} sign-off entries in ${ticketPath}; ` +
          `the latest entry is the one that counts (BO-2900f-1-ii).`
        );
      }
      completedPhases.push({ agent: phaseName, result: phaseResult });
    }
  }
}

// -------------------------------------------------------------------------
// Phase 4 — Completion decision, taken FROM THE RECORD (BO-400a-2-ii/-iii)
// -------------------------------------------------------------------------
// BUG-22: the observed run's payload named four completed batches while every
// ticket in the store still read `status: todo`. The work was real and
// committed; the record claimed nothing happened, which blocks the epic
// archive check. The missing half is this write — and its boundary: the write
// happens only when the ticket's OWN record proves every needed phase passed.

return await concludeTicket({
  recordPath: ticketPath,
  title,
  record: lastRecord,
  basePhases: neededPhases.map((p) => p.agent),
  deferredPhases,
  completedPhases,
  skippedPhases,
  unverifiedPhases,
  unverifiedReasons,
  dispatchedAgents,
  noPhasesToRun: false,
});
