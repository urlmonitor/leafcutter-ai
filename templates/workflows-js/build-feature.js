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
    // Tickets the planner OMITTED from every batch because their own
    // frontmatter already reads `status: done` — work finished before this
    // run began, typically by an earlier session.
    //
    // The planner already computes this set (that is what "omitted from all
    // batches (resume)" means); it simply never reported it, so the run had
    // no way to tell "finished earlier" apart from "not in this run at all".
    // BO-100e-1-i's eligibility gate needs exactly that distinction, and
    // asking for a field the planner already derived costs no extra dispatch.
    already_done: {
      type: "array",
      items: { type: "string" },
    },
    // EVERY sub-ticket the folder contained at this look, whatever its status
    // and whether or not it is eligible yet.
    //
    // This is what fixes the run set. A ticket that is a later LAYER of the
    // work this run started with is present here at look 1 even though it is
    // not eligible until its prerequisite finishes; a ticket ADDED to the
    // folder mid-drive is not. That distinction cannot be drawn from the
    // batches alone — both are absent from look 1's batches — and it is the
    // only thing separating work the run should carry from work BO-300a-5
    // requires it to leave outstanding.
    enumerated: {
      type: "array",
      items: { type: "string" },
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
 * Completion-time re-read of the epic's set of work (BO-300a-5).
 *
 * `readable: false` is a first-class answer: a re-read that FAILED must never
 * be treated as a re-read that found nothing new. Those two states produce
 * opposite completion outputs.
 *
 * `required: ["readable"]` is the half that makes that true. Without it a reply
 * may simply OMIT the flag — legal under the schema, and indistinguishable from
 * a successful read to any consumer that tests `readable === false`. A partial
 * enumeration answered that way yields `additions: []`, `withhold: false` and an
 * "Epic complete" statement: BUG-19's exact failure mode, inside the guard built
 * to prevent it. The flag is mandatory here for the same reason it is mandatory
 * on RECORD_READBACK_SCHEMA below, and compareEpicTicketSets tests it with the
 * same polarity (`!== true`).
 */
const EPIC_RECHECK_SCHEMA = {
  type: "object",
  properties: {
    readable: { type: "boolean" },
    epic_path: { type: "string" },
    tickets: {
      type: "array",
      items: {
        type: "object",
        properties: { path: { type: "string" }, status: { type: "string" } },
      },
    },
    ticket_paths: { type: "array", items: { type: "string" } },
    error: { type: "string" },
  },
  required: ["readable"],
};

/**
 * Reply shape of the post-dispatch record read-back (BO-2900f-1-i).
 *
 * TWIN: mirrors build-ticket.js RECORD_READBACK_SCHEMA. Keep in sync.
 *
 * `readable: false` is a first-class answer, not an error to be swallowed: an
 * unreadable record adjudicates the gate FAILED. Absent evidence must never
 * resolve to success.
 */
const RECORD_READBACK_SCHEMA = {
  type: "object",
  properties: {
    readable: { type: "boolean" },
    ticket_path: { type: "string" },
    lifecycle_status: { type: "string" },
    needed_phases: { type: "array", items: { type: "string" } },
    signoffs: {
      type: "array",
      items: {
        type: "object",
        properties: { agent: { type: "string" }, status: { type: "string" } },
      },
    },
    signed_off_agents: { type: "array", items: { type: "string" } },
    // depends_on (BO-100e-1-i): the ticket's own depends_on: frontmatter list,
    // as an array of ticket paths, or [] when absent. Optional — a reader that
    // predates this field simply never populates it, and every existing
    // caller of readTicketRecordBack already tolerates an absent key.
    depends_on: { type: "array", items: { type: "string" } },
    error: { type: "string" },
  },
  required: ["readable"],
};

/**
 * Reply shape of the ticket-completion write (BO-400a-2-ii).
 * TWIN: mirrors build-ticket.js COMPLETION_WRITE_SCHEMA. Keep in sync.
 */
const COMPLETION_WRITE_SCHEMA = {
  type: "object",
  properties: {
    status: { type: "string" },
    ticket_path: { type: "string" },
    error: { type: "string" },
  },
  required: ["status"],
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
    // existing_test_files: test files a PREVIOUS drive already wrote for this
    // ticket and that still exist on disk. Third satisfaction route for the
    // coder guard — without it, resuming a ticket whose test-writer is already
    // signed_off would re-block the coder forever, because test-writer is no
    // longer in the needed set and cannot re-supply its evidence.
    existing_test_files: { type: "array", items: { type: "string" } },
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
/**
 * Every status a phase result may legally carry.
 *
 * 'undetermined' is the boundary-failure value: it means "I could not perform
 * my task", as distinct from "I performed it and the answer is no". Without it
 * an agent that cannot do its job has no truthful value to return, so its
 * failure gets forced onto a status meaning something else — the shape behind
 * KI-SS-001. Any status outside this list is treated as unrecognised and
 * therefore NOT a success.
 *
 * TWIN: mirrors build-ticket.js PHASE_STATUS_VALUES. Keep in sync.
 */
const PHASE_STATUS_VALUES = [
  "ok",
  "blocker",
  "failed",
  "question",
  "handoff",
  "undetermined",
];

const PHASE_RESULT_SCHEMA = {
  type: "object",
  properties: {
    status: {
      type: "string",
      enum: PHASE_STATUS_VALUES,
    },
    result_status: { type: "string" },
    message: { type: "string" },
    // Test-evidence fields (BO-2000e-2 second satisfaction route). Populated by
    // the test-writer phase; ignored for every other phase. Both are optional so
    // that a phase agent which omits them leaves the coder guard CLOSED — absent
    // evidence must never read as satisfied evidence.
    tests_written: {
      type: "array",
      items: { type: "string" },
      description:
        "Paths of test files this phase created or extended. Non-empty is the " +
        "evidence that tests exist for the ticket.",
    },
    red_baseline_verified: {
      type: "boolean",
      description:
        "True when the phase ran the new tests and confirmed they fail (non-zero exit) " +
        "before any implementation work.",
    },
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
        `[build-feature.js] PHASE-ORDER GAP: agent "${agentName}" is not a member of ` +
        `the phaseOrder array in templates/workflows-js/build-feature.js. It will be ` +
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
// Record adjudication — pure functions over a ticket record read back off disk
//
// TWIN: mirrors build-ticket.js. Keep in sync with that file.
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
 * TWIN: mirrors build-ticket.js. Keep in sync with that file.
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
 * TWIN: mirrors build-ticket.js. Keep in sync with that file.
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
// TWIN: mirrors build-ticket.js. Keep in sync with that file.
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
// Record I/O — the drive's only channel to the ticket's own record
//
// TWIN: mirrors build-ticket.js. Keep in sync with that file.
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
    `"depends_on" (the frontmatter depends_on: list, as an array of ticket paths verbatim, or [] if the key is absent — do not resolve or interpret the paths), ` +
    `and "signoffs": one entry per sign-off heading in the ## Comments section, in the order they appear, as {"agent": "<name>", "status": "<status>"} ` +
    `(heading form: "### YYYY-MM-DD HH:MM — <agent> (status: <status>)"). List EVERY matching heading, including repeats — do not de-duplicate them. ` +
    `If the record cannot be opened for any reason, return {"readable": false, "error": "<what went wrong>"} — an unreadable record is a real answer and will be treated as a failure, so never guess its contents. ` +
    `Otherwise return {"readable": true, "ticket_path": "${recordPath}", "lifecycle_status": "...", "needed_phases": [...], "depends_on": [...], "signoffs": [...], "signed_off_agents": [...]}. ` +
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
  // retry cap, design/halt, the epic halt) emits blocked or error, and the epic
  // loop's halted filter branches on exactly that vocabulary. Leaving "ok" here
  // while the same payload carries `ticket_completed: false`, `not_completed`
  // and an outstanding-phase list inverts the signal for every caller that
  // reads the field first — and the single-ticket branch returns this payload
  // verbatim, with no compensating re-derivation of its own.
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
 * Take the completion decision for one ticket and record it.
 *
 * THE SINGLE EXIT for a ticket that reaches the end of its drive — whether it
 * ran twelve phases or none. Read-back → adjudicate against the record → write
 * done only if the record proves it → emit the outcome payload.
 *
 * It exists because the empty-needed-phase case used to bypass all of that with
 * a bare `{status: "ok"}` carrying no `ticket_completed` key. The epic loop
 * filters on exactly that key, so a ticket whose phases were all already
 * signed_off landed in the incomplete set and blocked the epic while naming
 * nothing to fix — and the block was unrecoverable, because a re-run is
 * byte-identical and there is no sign-off left to add. Worse, it is reached by
 * following this driver's own remediation advice ("add the sign-off it owes",
 * which flips the last agent to signed_off and empties the needed set), by a
 * transient completion-write failure, and by an epic member whose only
 * remaining needed phase is the deferred pull-request. Keeping both exits on
 * one path is what stops the next one being added off it.
 *
 * TWIN: mirrors build-ticket.js. Keep in sync with that file.
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

/**
 * The resolved target this drive emits for its consumers.
 *
 * BO-1900a-4 (BUG-01, run wf_09a91c7e-d5f): the resolver returned an epic
 * target whose isolated-working-copy value was a verbatim copy of the epic's
 * work-store folder. A work-store folder is not a working copy. Nothing broke
 * only because the very next step overwrote the value — that is luck, not
 * design: any consumer reading the target BEFORE that step would run phase
 * agents against the shared clone, and commit there.
 *
 * There is no correct working-copy value to emit at resolution time, because
 * none has been created yet. `worktree_path: null` is the honest answer and
 * the unambiguous marker: absent is not a location, so no consumer can join,
 * open, or run a command in it, and none has to compare it against the epic's
 * folder to discover the two are the same. resolveResult.worktree_path is
 * DELIBERATELY not copied here.
 *
 * TWIN: mirrors build-ticket.js. Keep in sync with that file.
 */
const resolvedTarget = {
  target_type,
  epic_path: epic_path || null,
  ticket_path: ticket_path || null,
  worktree_path: null,
};

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
    worktree_undetermined: true,
    resolved_target: resolvedTarget,
    message:
      `The isolated working copy for "${worktreeTarget}" is UNDETERMINED: ` +
      `worktree-agent failed to create or reuse one. ` +
      `Error: ${(worktreeResult && worktreeResult.error) || "worktree-agent returned null or failed"}. ` +
      `No phase agent has been spawned. Safety abort: /build-feature will NOT ` +
      `fall back to the epic's work-store folder, to the directory the process ` +
      `happens to be running in, or to any other existing location — an agent ` +
      `sent to the wrong working copy commits in the wrong repository, and that ` +
      `is discovered only after the fact. Fix the worktree issue and re-run.`,
    abort_reason: "worktree-undetermined",
    action_required: "establish_worktree",
  };
}

const realWorktreePath = worktreeResult.worktree_path;
if (!realWorktreePath) {
  return {
    status: "error",
    worktree_undetermined: true,
    resolved_target: resolvedTarget,
    message:
      "The isolated working copy for this drive is UNDETERMINED: worktree-agent " +
      "returned no worktree_path. No phase agent has been spawned, and no " +
      "substitute location is used in its place.",
    abort_reason: "worktree-undetermined",
    action_required: "establish_worktree",
  };
}

// The later step has now established the isolated working copy, so the
// resolved target carries it and no longer reads as undetermined.
resolvedTarget.worktree_path = realWorktreePath;

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
    `Also report "existing_test_files": test files a previous drive already wrote for this ticket. Find them by reading any test-writer sign-off in the ticket's ## Comments section and collecting the test file paths it names, then verifying with the shell that each path actually EXISTS on disk. List only paths you confirmed exist; return [] if there is no test-writer sign-off, it names no files, or the named files are gone. Do not guess a path from the ticket title or a naming convention. ` +
    `Return a JSON object with exactly these keys: { "ticket_path": "<path>", "title": "<ticket title>", "files_touched": [...], "has_test_requirements": true|false, "existing_test_files": [...], "ordered_phases": [{"agent": "<name>", "status": "<status>"}, ...] }. ` +
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

  // BO-1900a-4-ii — an unusable plan reply holds the ticket back. It is never
  // reduced to a blank record and then to a blank list, which is what turned a
  // dead planner into a `status: done` write.
  const planReason = unusablePlanReason(ticketPlan);
  if (planReason) {
    return buildPlanHoldback(worktreeTicketPath, planReason, resolvedTarget);
  }

  const plan = ticketPlan;
  const orderedPhases = plan.ordered_phases;
  const filesTouched = plan.files_touched || [];
  const title = plan.title || worktreeTicketPath;

  // Test-coverage precondition for coder phases (BO-2000e-2). Three satisfaction
  // routes, any of which proves tests exist before a coder runs:
  //   1. the ticket ships a populated ## Test Requirements section, OR
  //   2. the test-writer phase runs earlier in this same drive and returns
  //      evidence of test files it wrote (see the test-writer branch below), OR
  //   3. a previous drive already wrote test files that still exist on disk.
  //
  // Route 2 exists because test-writer has a mandatory AC-derivation fallback:
  // when ## Test Requirements is absent it resolves the ticket's source_ac and
  // derives the tests from the AC store instead. Reading the planner's pre-drive
  // snapshot as an immutable fact ignored that fallback entirely and deadlocked
  // every AC-generated ticket (no surface has emitted ## Test Requirements since
  // v2.0.0), so this must stay a `let` that route 2 can flip.
  //
  // Route 3 covers RESUME. Once test-writer is signed_off it drops out of the
  // needed set, so on a re-run it can never re-supply route 2's evidence — the
  // ticket would deadlock permanently on the second drive. The planner verifies
  // these paths exist on disk, so this is evidence, not a status flag.
  const existingTestFiles = Array.isArray(plan.existing_test_files)
    ? plan.existing_test_files.filter((p) => typeof p === "string" && p.trim())
    : [];
  let hasTestRequirements =
    plan.has_test_requirements === true || existingTestFiles.length > 0;

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

  // Agents that produce production code — must NOT run without Test Requirements.
  const CODER_PHASES = new Set(["python-coder", "sql-coder", "frontend-coder"]);

  // BO-1900a-4-i — the pre-dispatch working-copy check. Unreachable in the
  // normal flow (the resolve step above already held the drive back), and
  // deliberately kept anyway: the refusal belongs at the point where a phase
  // agent would be spawned, so a future edit that reorders the guard cannot
  // silently start dispatching against an undetermined working copy.
  if (!resolvedTarget.worktree_path) {
    return {
      status: "error",
      worktree_undetermined: true,
      abort_reason: "worktree-undetermined",
      resolved_target: resolvedTarget,
      ticket_path: worktreeTicketPath,
      message:
        "Held back before spawning any phase agent: the isolated working copy " +
        "for this drive is UNDETERMINED. No substitute location is used.",
      action_required: "establish_worktree",
    };
  }

  // deferredPhases: for an epic member the pull-request phase is opened once
  // per epic by finalize-feature, so a record that still names it as needed
  // must not hold the ticket open forever. Declared here rather than at the
  // completion step because the no-phases-to-run exit below needs it too — that
  // exit is reached precisely BY the deferral (selectDispatchPhases drops
  // pull-request before the length check).
  const deferredPhases = isEpicMember ? ["pull-request"] : [];

  // No phase left to run. NOT a reason to skip the completion decision: the
  // ticket's record already holds whatever evidence exists, and it is the only
  // thing that can say whether this ticket is done. Bypassing the read-back
  // here is what made an already-finished ticket unrecoverably block its epic
  // (see concludeTicket's header for the full failure).
  //
  // The required set is what the ticket CLAIMS is complete, not what the drive
  // ran — the drive ran nothing, and an empty required set would say yes to
  // every ticket, including one whose frontmatter reads signed_off while its
  // record carries no sign-off entry at all.
  if (neededPhases.length === 0) {
    return await concludeTicket({
      recordPath: worktreeTicketPath,
      title,
      record: await readTicketRecordBack(worktreeTicketPath),
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

  // -------------------------------------------------------------------------
  // Step 3 — Sequential phase loop with failure adjudication
  // -------------------------------------------------------------------------
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

    // Test Requirements guard (BO-2000e-2): refuse to dispatch a coder phase
    // unless tests are known to exist — either declared in the ticket's
    // ## Test Requirements section, or written by test-writer earlier in this
    // drive. Fail-closed: if neither route produced evidence, block.
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
        ticket_path: worktreeTicketPath,
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

      // Dispatch each needed phase as a flat depth-1 agent() call.
      // agentType: phaseName ensures the phase agent's template is loaded.
      //
      // The trailing pointer block is load-bearing, not decoration
      // (BO-1900d-1). templates/agents/_signoff_block.md — carried by 30 agent
      // templates, including every phase agent — opens with
      // "## Sign-off (when ticket_path is provided)" and closes with
      // "Skip this entire section if no `ticket_path` was provided". A gate
      // handed the path only as narrative ("for ticket: <path>") has to decide
      // for itself whether its own conditional is satisfied, which is a very
      // plausible mechanism for BUG-23 having been INCONSISTENT rather than
      // uniformly absent: on run wf_cc2b46d9-f6f ticket 09 recorded test-runner
      // and lost pr-reviewer while ticket 03 did the reverse.
      //
      // Prose is the ONLY channel. agent(prompt, opts) accepts exactly
      // {agentType, schema, label, phase, model, effort, isolation} — an extra
      // `ticket_path` key placed in opts is dropped before the agent ever sees
      // it, so putting it there would look like a fix and pass nothing. The
      // literal `key: value` token below is the in-repo convention for this
      // channel (build-epic.js:357 hands worktree_path the same way).
      phaseResult = await agent(
        `You are the ${phaseName} phase agent for ticket: ${worktreeTicketPath}. ` +
        `Read the ticket before starting. Execute your phase. ` +
        `Files touched: ${JSON.stringify(filesTouched)}. ` +
        `Return a JSON result with at minimum { "status": "ok" | "blocker" | "failed" }.` +
        (phaseName === "test-writer"
          ? ` You MUST also return "tests_written": a list of the test file paths you created or ` +
            `extended, and "red_baseline_verified": true only if you ran those tests and confirmed ` +
            `they fail. Return "tests_written": [] if you wrote no tests (for example if you ` +
            `self-skipped) — an empty list is the correct, honest answer and will stop the coder ` +
            `phase rather than let it run untested. Do not list a file you did not actually write.`
          : "") +
        `\n\nYou WERE invoked with the arguments below. Your sign-off protocol is ` +
        `therefore in force: record your outcome in this ticket's own record before ` +
        `you return.\n` +
        `ticket_path: ${worktreeTicketPath}\n` +
        `worktree_path: ${resolvedTarget.worktree_path}`,
        {
          agentType: phaseName,
          schema: PHASE_RESULT_SCHEMA,
          label: phaseName,
          phase: "Phase Dispatch",
        }
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

      const phaseRecord = await readTicketRecordBack(worktreeTicketPath);
      if (phaseRecord && phaseRecord.readable === true) {
        lastRecord = phaseRecord;
      } else {
        lastRecord = null;
      }
      const verdict = adjudicatePhaseAgainstRecord(phaseRecord, phaseName);

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
      //
      // Recognition, not truthiness: the comment above promises "or unrecognized
      // status", but a truthiness test cannot deliver it. A hallucinated status
      // ("complete", "done") is truthy, so it passed this guard and then matched
      // neither the blocker/failed nor the handoff branch below — landing back in
      // the silent-success hole the guard exists to close. Checking membership in
      // PHASE_STATUS_VALUES closes it, and also catches an explicit
      // 'undetermined' (the agent saying it could not perform its task).
      //
      // TWIN: mirrors build-ticket.js. Keep in sync with that file.
      if (!phaseResult || !PHASE_STATUS_VALUES.includes(resultStatus) ||
          resultStatus === "undetermined") {
        return {
          status: "blocked",
          message:
            `Phase '${phaseName}' returned no usable result (agent died, was ` +
            `skipped, or returned an empty, unrecognised, or undetermined ` +
            `status: ${JSON.stringify(resultStatus)}). Halting to avoid ` +
            `proceeding on incomplete work — treat the phase as NOT run and ` +
            `verify the repository, not this payload.`,
          ticket_path: worktreeTicketPath,
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
              `then re-run /build-feature.`,
            ticket_path: worktreeTicketPath,
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
          `${worktreeTicketPath}. You are being RE-DISPATCHED because phase ` +
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
            phase: "Phase Dispatch",
          }
        );

        return {
          status: "blocked",
          message:
            `Phase '${phaseName}' returned 'status: handoff' naming ` +
            `'${normalizedTarget}'. '${normalizedTarget}' was re-dispatched ` +
            `to resolve the handoff; re-run /build-feature to continue this ` +
            `ticket's remaining phases once the handoff is resolved.`,
          ticket_path: worktreeTicketPath,
          failing_phase: phaseName,
          handoff_target: normalizedTarget,
          handoff_result: handoffResult,
          classification: "cross_agent",
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

      // Satisfaction route 2 for the coder guard (BO-2000e-2): test-writer
      // succeeded AND named at least one test file it wrote. Evidence must be
      // explicit — a bare `status: ok` is NOT enough, because test-writer signs
      // off ok when it self-skips too. Only a non-empty tests_written list opens
      // the gate for the coder phases that follow (test-writer is priority 5,
      // every coder is 6+, so this always lands before the guard is consulted).
      if (phaseName === "test-writer") {
        const testsWritten = Array.isArray(phaseResult.tests_written)
          ? phaseResult.tests_written.filter((p) => typeof p === "string" && p.trim())
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
          `VERIFICATION FAILED for '${phaseName}' on ${worktreeTicketPath}: ${verdict.reason}. ` +
          `The gate is adjudicated failed and is NOT counted as completed.`
        );
      } else {
        if (verdict.entries > 1) {
          log(
            `'${phaseName}' carries ${verdict.entries} sign-off entries in ${worktreeTicketPath}; ` +
            `the latest entry is the one that counts (BO-2900f-1-ii).`
          );
        }
        completedPhases.push({ agent: phaseName, result: phaseResult });
      }
    }
  }

  // -------------------------------------------------------------------------
  // Step 4 — Completion decision, taken FROM THE RECORD (BO-400a-2-ii/-iii)
  // -------------------------------------------------------------------------
  // BUG-22: the observed run's payload named four completed batches while every
  // ticket in the store still read `status: todo`. The work was real and
  // committed; the record claimed nothing happened, which blocks the epic
  // archive check. The missing half is this write — and its boundary: the write
  // happens only when the ticket's OWN record proves every needed phase passed.
  return await concludeTicket({
    recordPath: worktreeTicketPath,
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
}

// ---------------------------------------------------------------------------
// Completion-time re-read of the epic's set of work (BO-300a-5 / BO-300a-5-i)
//
// BUG-19, run wf_cc2b46d9-f6f: the batch plan was computed once and enumerated
// ten pieces of work. Three more were committed to the epic branch 26 minutes
// later. They were never built — defensible — AND never appeared in the final
// output's halted or skipped lists, so the drive would have reported the epic
// complete having never seen them. The additions were invisible in both
// directions at once.
//
// The contract is DETECT AND REPORT, not build: work added during a drive can
// itself add more, so absorbing it would leave the drive with no termination
// condition. The operator who added the work is the one who knows whether it
// belongs in this drive.
//
// NO TWIN COUNTERPART BY DESIGN: build-ticket.js drives a single piece of work
// and has no epic set to re-read. Mirroring this into the twin would be wrong,
// not symmetric (n_location_rule: 1).
// ---------------------------------------------------------------------------

/**
 * Re-read the epic's set of work at the moment the completion output is made.
 *
 * @param {string} epicFolder
 * @returns {Promise<object>} the enumeration reply (readable:false when it failed)
 */
async function recheckEpicTicketSet(epicFolder) {
  return await agent(
    `Re-read the epic folder "${epicFolder}" RIGHT NOW and report the set of work it contains AT THIS MOMENT. ` +
    `This is a completion-time re-check: the plan for this drive was computed earlier, and work may have been added to or removed from the epic since. ` +
    `List every NN_*.md sub-ticket currently present in the folder, each with its frontmatter status. Do not use any earlier listing, and do not omit tickets whose status is done. ` +
    `If the folder cannot be listed for any reason, return {"readable": false, "error": "<what went wrong>"} — a failed re-read is a real answer and will withhold the epic-complete claim, so never return an empty list to represent a failure. ` +
    `Otherwise return {"readable": true, "epic_path": "${epicFolder}", "tickets": [{"path": "<absolute path>", "status": "<status>"}, ...], "ticket_paths": [...]}. ` +
    `Return ONLY the JSON object, no prose.`,
    {
      agentType: "status-checker",
      schema: EPIC_RECHECK_SCHEMA,
      label: "epic-recheck",
      phase: "Build",
    }
  );
}

/**
 * Compare the plan's set of work with the set the epic carries now.
 *
 * Pure. Compares BY IDENTITY, never by count: a drive in which one piece of
 * work was added and another removed has an unchanged count.
 *
 * Fails closed — an unreadable re-read is its own state, never an empty set.
 * Conflating the two restores the original defect exactly at the moment the
 * store is least readable, while appearing to have fixed it.
 *
 * The polarity below is `readable !== true`, not `readable === false`, and that
 * is the whole of "fails closed". A reply that OMITS the flag makes no claim
 * about whether the folder could be listed; read as a claim of success it
 * yields `additions: []`, `withhold: false` and an "Epic complete" statement off
 * an enumeration that may have seen nothing. Only an explicit `readable: true`
 * is a verified read. EPIC_RECHECK_SCHEMA declares the flag required so a
 * conforming reply always makes the claim one way or the other; this check is
 * what holds when a reply does not conform.
 *
 * Work that is already `done` in the re-read is NOT an addition: it was
 * complete before the drive started and the planner omitted it deliberately.
 * Naming it would make the section noise, and an ignored section is the same
 * outcome as no section at all.
 *
 * @param {Array<string>} plannedPaths
 * @param {object|null} reply
 * @param {string} worktreePath
 * @returns {{verified: boolean, error: string|null,
 *            additions: Array<string>, removals: Array<string>}}
 */
function compareEpicTicketSets(plannedPaths, reply, worktreePath) {
  if (!reply || reply.readable !== true || reply.status === "error") {
    return {
      verified: false,
      error:
        (reply && reply.error) ||
        (reply && reply.readable === undefined
          ? "the completion-time re-read of the epic folder returned no " +
            "`readable` verdict, so it never claimed the folder could be " +
            "listed; the set of work it reported cannot be relied on"
          : "the epic's set of work could not be enumerated"),
      additions: [],
      removals: [],
    };
  }

  const entries = Array.isArray(reply.tickets)
    ? reply.tickets
    : (reply.ticket_paths || []).map((p) => ({ path: p, status: "todo" }));

  const currentAll = [];
  const currentOpen = [];
  for (const entry of entries) {
    if (!entry || !entry.path) continue;
    const normalized = toWorktreePath(entry.path, worktreePath);
    if (currentAll.indexOf(normalized) === -1) currentAll.push(normalized);
    if (entry.status !== "done" && currentOpen.indexOf(normalized) === -1) {
      currentOpen.push(normalized);
    }
  }

  return {
    verified: true,
    error: null,
    additions: currentOpen.filter((p) => plannedPaths.indexOf(p) === -1),
    removals: plannedPaths.filter((p) => currentAll.indexOf(p) === -1),
  };
}

/**
 * The work THIS DRIVE'S OWN RECORD names as completed, as worktree paths.
 *
 * Pure. BO-300a-5-iii: this is the proof `epicRecheckReport` partitions the
 * missing set against. It reads the same `completedBatches` accumulator every
 * epic return reports under `completed_batches`, so what the partition judges
 * against is exactly what the payload shows the operator — the two cannot drift.
 *
 * Normalized through toWorktreePath because `plannedTicketPaths` (and therefore
 * `cmp.removals`) are normalized, while `batchResults[].ticket_path` carries the
 * planner's spelling. Comparing the two un-normalized would silently classify
 * every completed removal as uncompleted and withhold on every tidy-up.
 *
 * Batches recorded with no tickets (an empty batch) contribute nothing rather
 * than throwing.
 *
 * @param {Array<object>} completedBatches
 * @param {string} worktreePath
 * @returns {Array<string>}
 */
function completedWorkPaths(completedBatches, worktreePath) {
  const out = [];
  for (const batch of completedBatches || []) {
    for (const ticketPath of (batch && batch.tickets) || []) {
      const normalized = toWorktreePath(ticketPath, worktreePath);
      if (normalized && out.indexOf(normalized) === -1) out.push(normalized);
    }
  }
  return out;
}

/**
 * Turn a set comparison into completion-output fields and sentences.
 *
 * Pure. `withhold` is the load-bearing half: naming the additions while still
 * emitting an epic-complete statement leaves the operator with two
 * contradictory sentences and an archive attempt that fails later.
 *
 * A removal is reported as its own event — it is not an addition, and leaving
 * it out of both lists is the same class of omission BUG-19 is.
 *
 * BO-300a-5-iii — A REMOVAL AND A COMPLETION ARE INDEPENDENT FACTS, and this
 * drive already knows both. Every removal used to be described as work that
 * "was not built", which is false for the ordinary case: the commonest cause of
 * a removal is the lifecycle move the drive itself makes when it FINISHES a
 * ticket. That produced a payload naming one ticket both as work the drive
 * completed and as work that was not built, certified by a success outcome
 * value and an affirmative verdict. So the missing set is partitioned against
 * `completedPaths` — the drive's own record of what it completed — BEFORE
 * anything is said about it:
 *
 *   * removed AND completed → named as no longer present and NOTHING MORE. Not
 *     described as unbuilt, and it does not withhold the claim. The drive's own
 *     completed record is the proof the work was done before the piece left.
 *   * removed AND NOT completed → nothing anywhere can assert it was done, so
 *     it withholds exactly as an addition does, and carries its own operator
 *     action rather than only generic halt advice.
 *
 * The decision is PER PIECE. One flag over the whole missing set necessarily
 * mis-describes one of them whenever a drive has both kinds, and softening the
 * wording alone would leave the completion claim turning on the wrong fact.
 * Every removal is still NAMED in `no_longer_present` in both cases —
 * suppressing the list would satisfy the no-contradiction invariant by
 * destroying the information BO-300a-5-i was authored to add.
 *
 * `completedPaths` defaults to empty, which is the fail-safe direction: an
 * unpassed completed set classifies every removal as uncompleted and withholds,
 * rather than certifying work no record proves was done.
 *
 * @param {{verified: boolean, error: string|null,
 *          additions: Array<string>, removals: Array<string>}} cmp
 * @param {Array<string>} [completedPaths] — work this drive's own record names
 *        as completed, normalized to worktree paths (see completedWorkPaths).
 * @returns {{fields: object, withhold: boolean, headline: string|null, suffix: string}}
 */
function epicRecheckReport(cmp, completedPaths) {
  const completed = Array.isArray(completedPaths) ? completedPaths : [];
  if (!cmp.verified) {
    return {
      fields: {
        epic_set_verified: false,
        epic_complete: false,
        epic_set_recheck_error: cmp.error,
      },
      withhold: true,
      headline:
        `the epic's work set could not be read back at completion time — ` +
        `the re-read failed: ${cmp.error}`,
      suffix:
        " Nothing about what the epic now contains can be asserted from this " +
        "drive; re-run once the epic folder can be listed.",
    };
  }

  // BO-300a-5-ii — the success path STATES its verdict. Emitting
  // `epic_set_verified: true` and simply leaving `epic_complete` absent means a
  // machine cannot tell "complete" from "a path that forgot to say", and those
  // are the two cases it most needs to tell apart. Agreement by silence is the
  // same thing that let the contradiction ship: the field a caller reads was
  // never the field being maintained. Set to false below if additions are found.
  const fields = { epic_set_verified: true, epic_complete: true };
  let headline = null;
  let suffix = "";

  if (cmp.additions.length > 0) {
    fields.epic_complete = false;
    fields.discovered_after_planning = cmp.additions;
    fields.discovered_work_action =
      "This work was added to the epic after the plan for this drive was fixed, " +
      "so it was never built. Decide whether it belongs in this epic: re-run " +
      "/build-feature to plan and build it, or move it out. The epic is not " +
      "archivable until it is resolved.";
    headline =
      `${cmp.additions.length} piece(s) of work were discovered after planning ` +
      `and were not built: ${cmp.additions.join(", ")}`;
  }

  // BO-300a-5-iii — partition BEFORE describing. Both lists are still reported
  // under `no_longer_present`; what differs is whether a piece is described as
  // unbuilt and whether it withholds the completion claim.
  const removedAndCompleted = cmp.removals.filter((p) => completed.indexOf(p) !== -1);
  const removedAndNotCompleted = cmp.removals.filter((p) => completed.indexOf(p) === -1);

  if (cmp.removals.length > 0) {
    fields.no_longer_present = cmp.removals;
  }

  if (removedAndCompleted.length > 0) {
    fields.no_longer_present_completed = removedAndCompleted;
    // Deliberately carries no not-built / not-done wording: this drive's own
    // completed record names every one of these, so the only true statement
    // left to make is that they left the epic.
    suffix +=
      ` ${removedAndCompleted.length} planned piece(s) of work are no longer ` +
      `present in the epic; this drive completed them, so they were built ` +
      `before they left: ${removedAndCompleted.join(", ")}.`;
  }

  if (removedAndNotCompleted.length > 0) {
    fields.epic_complete = false;
    fields.no_longer_present_not_completed = removedAndNotCompleted;
    fields.missing_work_action =
      "This work was planned for this drive, was never recorded complete by it, " +
      "and is no longer in the epic, so nothing can assert it was ever built. " +
      "Find where it went: if it was moved or archived, confirm it was finished " +
      "and restore its record; if it was deleted in error, restore it and re-run " +
      "/build-feature. The epic is not archivable until it is resolved: " +
      `${removedAndNotCompleted.join(", ")}.`;
    // HEADLINE ONLY, never headline AND suffix — exactly as the additions
    // branch above does it. Every return that renders a withheld claim renders
    // the headline (the two completion returns as "is NOT complete — …", the
    // halted and incomplete-member returns as "Also: …"), and this branch
    // always withholds, so the sentence is never lost. Appending it to the
    // suffix as well printed it TWICE in one message — caught by driving the
    // real epic and reading the prose, not by any assertion in the suite.
    const missingHeadline =
      `${removedAndNotCompleted.length} planned piece(s) of work neither ` +
      `completed in this drive nor remain in the epic and were not built: ` +
      `${removedAndNotCompleted.join(", ")}`;
    headline = headline ? `${headline}; ${missingHeadline}` : missingHeadline;
  }

  return {
    fields,
    withhold: cmp.additions.length > 0 || removedAndNotCompleted.length > 0,
    headline,
    suffix,
  };
}

/**
 * The single overall outcome value an epic completion return must lead with.
 *
 * Pure. BO-300a-5-ii: both epic completion returns used to hardcode "ok" and
 * then Object.assign the re-check's fields in beside it, so a payload could
 * report success while the same payload carried `epic_complete: false`,
 * `epic_set_verified: false` and a message reading `Epic "X" is NOT complete`.
 * One payload asserting three things, two of which contradicted the first.
 *
 * Derived from the verdict rather than asserted next to it, so the value, the
 * verdict and the sentence cannot drift apart — including for a withhold
 * condition nobody has written yet. Two conditions reach it today: a work set
 * that could not be re-read (`epic_set_verified: false`) and work added after
 * planning that was never built (`withhold`); both are covered by reading the
 * verdict itself rather than by enumerating them.
 *
 * "blocked" is the vocabulary the rest of these drivers already use for a run
 * that did not succeed (the halt exits, the incomplete-member exit and
 * buildTicketOutcome's not-completed path all emit it), and the epic loop's own
 * halted filter branches on it.
 *
 * NO TWIN COUNTERPART BY DESIGN: build-ticket.js drives a single piece of work
 * and has no epic completion return (n_location_rule: 1).
 *
 * @param {{fields: object, withhold: boolean}} report — from epicRecheckReport
 * @returns {string}
 */
function epicOutcomeStatus(report) {
  const fields = (report && report.fields) || {};
  if (report && report.withhold) return "blocked";
  if (fields.epic_complete === false) return "blocked";
  if (fields.epic_set_verified !== true) return "blocked";
  return "ok";
}

/**
 * Classify a prerequisite's own drive outcome for BO-100e-1-i's
 * `prerequisite_states` record.
 *
 * Pure. Reads the SAME `ticket_completed` verdict the halted filter and
 * buildTicketOutcome already produce (~line 2338) — never a second,
 * independently-invented notion of "finished". `true` is the only affirmative
 * value; a missing outcome (the prerequisite never reached a completion
 * decision — e.g. a classified halt) and an explicit `false` (a phase ran but
 * left no confirmable sign-off) are both real, distinct, non-affirmative
 * states, and neither is ever read as success.
 *
 * @param {{ticket_path: string, status: string, result: object|null}|undefined} outcome
 * @returns {string} one of the PREREQUISITE_STATE_VALUES below
 */
function prerequisiteStateFromOutcome(outcome) {
  if (!outcome) return "not_in_run_set";
  if (outcome.status === "withheld") return "unrecognised_outcome";
  if (!outcome.result) return "no_outcome_recorded";
  if (outcome.result.ticket_completed === true) return "succeeded";
  if (outcome.result.ticket_completed === false) return "failed";
  return "no_outcome_recorded";
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
  //
  // BO-100e-1 — REPEATED-LOOK WIDENING (KI-BO-025). The epic-planner used to
  // be asked exactly once, before anything in the epic had been built, so
  // only prerequisite-free work could ever appear in that one reply — a
  // four-deep chain A<-B<-C<-D built only A, however long the run was left to
  // keep going. The planner call now sits INSIDE the while loop below: one
  // "look" per iteration, each asked against what THIS DRIVE has actually
  // recorded complete by that moment (never against what had finished when
  // the run began), until a look releases no new work. The planner's own
  // eligibility rule is unchanged — it already computes "all depends_on met"
  // correctly for whatever moment it is asked; the fix is asking again.
  //
  // A flat, no-prerequisite set is unaffected in substance: it is still
  // built in one work-releasing look. It still pays for exactly one more
  // "epic-planner" dispatch — the terminating look that finds nothing left —
  // which is the fixed, one-time cost of ever being able to find a later
  // layer at all (BO-100e-1's own cost-control constraint: never one look
  // per ticket).
  // -----------------------------------------------------------------------
  const worktreeEpicPath = toWorktreePath(epic_path || target, realWorktreePath);

  const BATCH_SIZE = 12;
  const completedBatches = [];

  // This run's OWN record of each ticket's verdict, keyed by worktree path.
  // `true` only for an affirmative `ticket_completed` (BO-100e-1-i reuses
  // this exact verdict, never a second one); every other outcome — failure,
  // no outcome recorded, an unrecognised value, or never having reached a
  // completion decision at all — is simply absent here, and absence is never
  // read as success anywhere this map is consulted.
  const completedTicketOutcomes = {};

  // Work whose OWN frontmatter already read `status: done` when a look ran —
  // finished before this drive began, usually by an earlier session.
  //
  // This exists because the eligibility gate below and the planner must not
  // disagree about what "prerequisite met" means. The planner already treats
  // a done-on-disk prerequisite as satisfied AND omits it from every batch
  // (that is what resume is), so such a prerequisite can never appear in
  // completedTicketOutcomes — this run never drove it. Without this set the
  // gate reads it as `not_in_run_set` and withholds the dependant, turning a
  // correctly resumed drive into a spurious `blocked`, which is the exact
  // inverse of the error BO-100e-1-i exists to prevent.
  //
  // Kept separate from completedTicketOutcomes rather than folded into it:
  // that map is this run's own first-hand verdict, and the withheld report
  // should be able to say which kind of evidence a prerequisite had.
  const priorCompletedPaths = new Set();

  // The set of work THIS RUN has ADMITTED — the run_set BO-100e's
  // config_schema_fragment names. Union across looks, not just the first
  // look's batches, so a later layer a chain releases (once its own
  // prerequisite finishes) is still part of what the completion-time re-read
  // below is compared against.
  //
  // BO-100e-1's own scope boundary against BO-300a-5 (done), restated because
  // it is easy to blur with the paragraph above: a path is folded in here
  // ONLY after passing the FIRST-LOOK RUN-SET LOCK below, which is what makes
  // this an admitted set rather than simply "everything any look ever said".
  // Look 1's own offer is admitted unconditionally — it defines the set this
  // run started with. A later look's offer is admitted only when it links
  // back into what THIS variable already holds (see the lock's own comment).
  // A path the lock rejects is never folded in here, which is exactly what
  // keeps it visible to `discovered_after_planning` at the completion-time
  // re-read below instead of being silently absorbed.
  const plannedTicketPaths = [];

  // The epic's full contents as look 1 found them — the run set, frozen.
  //
  // Every later layer of the work this drive started with is already in here
  // at look 1, sitting behind a prerequisite; work added to the folder after
  // the drive began is not. That is the whole discriminator, and it is why
  // this is taken from the ENUMERATION rather than from look 1's batches: a
  // next layer is absent from look 1's batches too, so a batch-derived set
  // cannot tell the two apart and would reject the chains this loop exists to
  // carry.
  //
  // Empty means look 1 reported no enumeration. That is a planner that did not
  // answer the question, not an empty epic, so it must NOT be read as "nothing
  // belongs to this run" — see the lock below for what happens instead.
  const runSetPaths = new Set();
  let runSetFrozen = false;

  // Looks that ran while the run set was still unknown, i.e. under the unsound
  // fallback. Reported on the payload so a degraded drive says so instead of
  // looking identical to a sound one — absence of evidence must not read as
  // success, and that applies to the guard's own confidence too.
  const runSetUnknownLooks = [];

  const lookRecords = [];
  let epicTitle = worktreeEpicPath;
  let lookNumber = 0;

  while (true) {
    lookNumber += 1;

    // What THIS look re-decides against: not what had finished when the run
    // began, but what has finished by now (BO-100e-1's own distinguishing
    // requirement — a re-decision, not a resend of the look-1 prompt).
    const completedBeforeThisLook = plannedTicketPaths.filter(
      (p) => completedTicketOutcomes[p] === true
    );

    const plannerResult = await agent(
      `Read Master_Plan.md at the epic folder: "${worktreeEpicPath}". Then read the frontmatter of every NN_*.md sub-ticket, RIGHT NOW — a fresh read for THIS look, not an earlier snapshot. ` +
      `This drive has, as of this moment, recorded the following ticket path(s) successfully complete: ${JSON.stringify(completedBeforeThisLook)}. ` +
      `Compute dependency-ordered batches: (1) Build a dependency graph using depends_on (logical) and files_touched overlap (physical). ` +
      `(2) Compute the maximal antichain of ready tickets: a ticket is ready when every depends_on entry names a ticket in the completed set above, or a ticket whose own frontmatter already reads status: done. ` +
      `(3) Split the antichain into batches so no two tickets share any files_touched entry. ` +
      `(4) Tickets with status 'done', or already recorded complete above, are OMITTED from all batches (resume). ` +
      `(5) If nothing further is eligible right now, return an empty batches list — that is a valid, expected answer, and it ends this drive's search for more work. ` +
      `(6) Also return already_done: the absolute paths of every sub-ticket you OMITTED at step (4) because its own frontmatter already reads status: done. This is the set you just computed in order to omit it — report it rather than discarding it. Return [] if none. ` +
      `(7) Also return enumerated: the absolute path of EVERY NN_*.md sub-ticket the folder contains right now, whatever its status and whether or not it is eligible yet — including the ones you omitted at step (4) and the ones not yet ready at step (2). This is the folder's full contents, not a selection. ` +
      `Return a JSON object with: epic_path, title, batches, already_done, enumerated. Return ONLY the JSON object.`,
      {
        agentType: "status-checker",
        schema: PLANNER_SCHEMA,
        label: "epic-planner",
        phase: "Build",
      }
    );

    const plan = plannerResult || {};
    let batches = plan.batches || [];
    if (plan.title) {
      epicTitle = plan.title;
    }

    // Work that was already finished before this run began. Kept SEPARATE
    // from completedTicketOutcomes on purpose: that map is this run's own
    // first-hand verdict, and folding a frontmatter reading into it would
    // erase the difference between "this drive watched it succeed" and "the
    // record says it succeeded". The eligibility gate below needs both to
    // count as satisfied, and the withheld report needs to be able to say
    // which kind of evidence it had.
    for (const donePath of plan.already_done || []) {
      const normalized = toWorktreePath(donePath, realWorktreePath);
      if (normalized) {
        priorCompletedPaths.add(normalized);
      }
    }

    // Freeze the run set from the FIRST look only. Later looks re-enumerate a
    // folder that may have grown; taking their word for it would defeat the
    // point of fixing the set at all.
    if (!runSetFrozen) {
      for (const seenPath of plan.enumerated || []) {
        const normalized = toWorktreePath(seenPath, realWorktreePath);
        if (normalized) {
          runSetPaths.add(normalized);
        }
      }
      // Freeze only once something was actually enumerated. `enumerated` is
      // not in PLANNER_SCHEMA's `required` list, so a minimally-compliant
      // reply can omit it — and latching on that would drop the REST of the
      // drive into the fallback this file's own comment calls unsound, even
      // if look 2 would have answered correctly. Staying unfrozen lets a
      // later look supply it. The window is still degraded, and
      // `run_set_unknown_looks` below is what stops that being invisible.
      if (runSetPaths.size > 0) {
        runSetFrozen = true;
      } else {
        runSetUnknownLooks.push(lookNumber);
      }
    }

    // FAIL-OPEN DUPLICATE-OFFER GUARD, now also the FIRST-LOOK RUN-SET LOCK.
    // This look's own prompt above instructs the planner to OMIT every
    // ticket path in `completedBeforeThisLook`, but nothing here verified it
    // obeyed — a degraded or truncated reply that re-offers an
    // already-completed ticket was driven a SECOND time, inflating
    // `tickets_completed` and duplicating `completed_batches` entries
    // (observed live: two identical looks, `tickets_completed: 4` for a
    // two-ticket epic). Mirrors the BO-100e-1-i eligibility gate's own
    // principle one level up: re-check rather than trust the planner got it
    // right.
    //
    // FIRST-LOOK RUN-SET LOCK (the second condition below) is the fix for the
    // separate regression this ticket exists to close: a later look's own
    // enumeration re-reads the epic folder fresh, so it may legitimately
    // contain a path no EARLIER look ever offered, for either of two reasons
    // that are NOT distinguishable by path alone:
    //
    //   * a genuine next LAYER of the set this run started with — a chain
    //     member whose own depends_on names something this run has already
    //     admitted (`plannedTicketPaths`) or that was already done before
    //     this run began (`priorCompletedPaths`), unlocked now that its
    //     prerequisite finished. This is the ENTIRE reason the loop keeps
    //     looking (BO-100e-1's own criterion) and must still be driven.
    //   * work ADDED to the epic folder after this run began — no such link.
    //     Absorbing this is BO-300a-5's (done) job to prevent: that work must
    //     be reported via `discovered_after_planning` at the completion-time
    //     re-read, never silently driven by a later look.
    //
    // `readTicketRecordBack` is the SAME helper the (unchanged) eligibility
    // gate below already dispatches per driven ticket to read depends_on —
    // reused here, before this ticket ever reaches that gate, so a path that
    // fails the link check is dropped BEFORE it is ever driven, not merely
    // withheld after being dispatched.
    //
    // `lookNumber > 1` guards it because look 1's own offer is unconditional:
    // it IS the set this run started with, by definition, with nothing yet
    // in `plannedTicketPaths` to link back into.
    //
    // Deliberately checked against `plannedTicketPaths`, not against a value
    // reset or widened by anything THIS look contributes — the lookup below
    // reads it before this look's own survivors are folded in further down,
    // so it only ever reflects what EARLIER looks admitted. Constraining
    // against a set that included this look's own offer would make the check
    // trivially satisfiable by a ticket linking to a SIBLING in the same
    // batch, which is not what "admitted by an earlier look" means; reusing
    // `plannedTicketPaths` any other way (e.g. testing raw membership of the
    // offered path itself, rather than its depends_on) would reject every
    // legitimate next layer outright, since a next layer is by definition
    // something no earlier look named yet — that is the no-op-in-the-other-
    // direction this comment's sibling warns about.
    //
    // Filter every batch's own ticket list — using the SAME toWorktreePath
    // normalisation the surrounding code uses — before it is folded into
    // `releasedThisLook`/`plannedTicketPaths` or driven below.
    let anyRawTicketOffered = false;
    let anyTicketRemainsAfterDedup = false;
    for (const plannedBatch of batches) {
      const rawTickets = plannedBatch.tickets || [];
      if (rawTickets.length > 0) {
        anyRawTicketOffered = true;
      }
      const dedupedTickets = [];
      for (const t of rawTickets) {
        const normalized = toWorktreePath(t.path, realWorktreePath);
        if (normalized && completedTicketOutcomes[normalized] === true) {
          continue;
        }
        if (lookNumber > 1 && normalized && plannedTicketPaths.indexOf(normalized) === -1) {
          if (runSetPaths.size > 0) {
            // The run set is known. Membership in it settles the question
            // outright: present at look 1 means this is a later layer of the
            // work the drive started with; absent means it arrived after, and
            // BO-300a-5 requires it be left outstanding and reported at the
            // completion re-read rather than driven here.
            if (!runSetPaths.has(normalized)) {
              continue;
            }
          } else {
            // DEGRADED. Look 1 reported no enumeration, so there is no run set
            // to test against. Fall back to the weaker check: admit only a
            // path whose own depends_on links into work this run has already
            // admitted or that was done before it began.
            //
            // This is weaker on purpose and it is not sound — a ticket ADDED
            // mid-drive that happens to declare such a dependency passes it.
            // It is kept only because the alternative when the run set is
            // unknown is worse in both directions: reject everything and the
            // chains this loop exists to carry stop dead; accept everything
            // and the drive absorbs new work silently. A partial guard beats
            // both. When the planner answers question (7) this branch is dead.
            const dependencyRecord = await readTicketRecordBack(normalized);
            const dependsOn = Array.isArray(dependencyRecord && dependencyRecord.depends_on)
              ? dependencyRecord.depends_on.map((p) => toWorktreePath(p, realWorktreePath))
              : [];
            const linksIntoRunSet = dependsOn.some(
              (p) => p && (plannedTicketPaths.indexOf(p) !== -1 || priorCompletedPaths.has(p))
            );
            if (!linksIntoRunSet) {
              continue;
            }
          }
        }
        dedupedTickets.push(t);
      }
      // Marks a batch that was NOT already empty from the planner but was
      // emptied entirely by this filter — it must not be driven and must
      // not add a spurious zero-count `completed_batches` entry below,
      // unlike a batch the planner itself returned with no tickets (which
      // keeps its existing zero-count record).
      plannedBatch._dedupEmptiedByFilter = rawTickets.length > 0 && dedupedTickets.length === 0;
      plannedBatch.tickets = dedupedTickets;
      if (dedupedTickets.length > 0) {
        anyTicketRemainsAfterDedup = true;
      }
    }
    if (anyRawTicketOffered && !anyTicketRemainsAfterDedup) {
      // Every ticket this look offered was already recorded complete by
      // this run — nothing new was actually released, even though the
      // planner did not itself return an empty `batches` list. Treat this
      // exactly like an empty planner reply so the existing termination
      // logic below ends the run instead of spinning on stale offers.
      batches = [];
    }

    const releasedThisLook = [];
    for (const plannedBatch of batches) {
      for (const plannedTicket of plannedBatch.tickets || []) {
        const normalized = toWorktreePath(plannedTicket.path, realWorktreePath);
        if (!normalized) continue;
        if (plannedTicketPaths.indexOf(normalized) === -1) {
          plannedTicketPaths.push(normalized);
        }
        if (releasedThisLook.indexOf(normalized) === -1) {
          releasedThisLook.push(normalized);
        }
      }
    }

    lookRecords.push({
      look_number: lookNumber,
      released: releasedThisLook,
      released_count: releasedThisLook.length,
    });

    // TERMINATE ON WHAT WAS RELEASED, NOT ON THE SHAPE OF THE CONTAINER.
    //
    // This was `batches.length === 0`, which asks whether the planner sent any
    // batch OBJECTS — not whether any of them offered work. A reply of
    // `batches: [{batch_number: 1, tickets: []}]` is valid under
    // PLANNER_SCHEMA (`tickets` has no minItems) and is a plausible compliance
    // slip against step (5), which asks for an empty LIST. It offers nothing,
    // so `anyRawTicketOffered` stays false and the reset above never fires;
    // it has length 1, so the old test never fired either. The look released
    // nothing, changed nothing, and went back to the top to ask an unchanged
    // question — an unbounded spin with no cap and no operator-visible error.
    // Harmless before this loop existed, because the planner ran exactly once.
    //
    // `releasedThisLook` is the direct answer and is already computed above.
    // It is empty in every case the old test caught (no batches at all; every
    // batch emptied by the dedup or run-set filter) and also in the case it
    // missed, so this subsumes the old condition rather than sitting beside it.
    // A look that released nothing cannot be made to release something by
    // asking again with the same inputs — that is the loop's own premise.
    if (releasedThisLook.length === 0) {
      if (lookNumber === 1) {
        // The EXISTING empty-plan return, unchanged in substance: nothing was
        // ever eligible, or the epic is genuinely empty / already done.
        // BO-300a-5-iii — the completed set is passed at ALL FOUR call sites, not
        // only the two that can exhibit the bug today. This return ran no batches,
        // so its record of completed work is empty BY CONSTRUCTION and it reports no
        // `completed_batches` at all. Passing the literal empty set (rather than
        // reaching for a `completedBatches` that is not yet in scope here) states
        // that emptiness explicitly and keeps the partition's one input the same
        // shape at every site.
        const emptyRecheck = epicRecheckReport(
          compareEpicTicketSets(
            plannedTicketPaths,
            await recheckEpicTicketSet(worktreeEpicPath),
            realWorktreePath
          ),
          []
        );
        return Object.assign(
          {
            // BO-300a-5-ii — derived, never hardcoded. This is the return a
            // degraded run is most likely to reach, and the one a fix applied only
            // to the final return leaves behind.
            status: epicOutcomeStatus(emptyRecheck),
            message:
              (emptyRecheck.withhold
                ? `Epic "${epicTitle}" is NOT complete — ${emptyRecheck.headline}.`
                : `Epic "${epicTitle}" complete (or no tickets to run). All tickets are done or the epic is empty.`) +
              emptyRecheck.suffix,
            epic_path: worktreeEpicPath,
            title: epicTitle,
            worktree_path: realWorktreePath,
            resolved_target: resolvedTarget,
            batches_run: 0,
            looks: lookNumber,
            look_records: lookRecords,
            run_set: plannedTicketPaths.slice(),
            ended_because: "no_further_work_eligible",
            unbuilt: [],
          },
          emptyRecheck.fields
        );
      }
      // TERMINATING LOOK (BO-100e-1): this look released nothing new — the
      // search for further work ends here. Fall through to the same
      // completion-time re-read and final return every successful drive
      // already reaches.
      break;
    }

    // --- run THIS LOOK's batches -------------------------------------------
    for (const batch of batches) {
      const batchNumber = batch.batch_number;
      const tickets = batch.tickets || [];

      if (tickets.length === 0) {
        // A batch the duplicate-offer guard above emptied entirely was
        // never actually released this look — it must not add a
        // zero-count `completed_batches` entry, unlike a batch the
        // planner itself returned empty (still recorded, unchanged).
        if (!batch._dedupEmptiedByFilter) {
          completedBatches.push({ batch_number: batchNumber, tickets_completed: 0 });
        }
        continue;
      }

      const batchResults = [];

      for (let i = 0; i < tickets.length; i += BATCH_SIZE) {
        const chunk = tickets.slice(i, i + BATCH_SIZE);

        // BO-100e-1-i — FAIL-CLOSED ELIGIBILITY GATE, keyed on EACH TICKET'S
        // OWN DECLARED depends_on — never on its position in the batch. A
        // batch is meant to name only mutually-independent, ready tickets
        // (that is the planner's own job), but this drive does not simply
        // trust that a batch got it right: a ticket is dispatched only once
        // EVERY prerequisite ITS OWN RECORD NAMES has itself recorded an
        // AFFIRMATIVE `ticket_completed === true` — the SAME machine-readable
        // verdict buildTicketOutcome already produces and the halted filter
        // below already reads. A prerequisite that merely ATTEMPTED, that
        // left no outcome at all, or that recorded some other non-affirmative
        // value, never satisfies this: absence of evidence is never read as
        // success. A ticket that names NO depends_on (the ordinary case —
        // most batch members are genuinely independent) is never WITHHELD:
        // every chunk still starts every one of its thunks via parallel()
        // together, and an independent ticket proceeds straight to its
        // phases. A dependant's own thunk is what awaits its named
        // prerequisite's settled outcome — whether that prerequisite is
        // another member of THIS SAME chunk, an earlier CHUNK of this same
        // batch, an earlier batch or look of this drive, or work that was
        // already done before this drive began — before doing any real work.
        //
        // WHAT THIS GATE COSTS, stated plainly because an earlier draft of
        // this comment claimed it was free and that was false: every ticket
        // pays ONE readTicketRecordBack dispatch, independent ones included,
        // because depends_on cannot be consulted without first reading the
        // record that names it. Only the WITHHOLDING is conditional, not the
        // read. That is a real per-ticket cost on the common case and it is
        // the honest price of not trusting the planner blindly; if it needs
        // to come down, the fix is to carry depends_on in the enumeration the
        // run already performs, not to pretend the dispatch is not happening.
        const chunkOutcomesByPath = {};
        const chunkThunks = chunk.map((ticket) => {
          const worktreeTicketPath = toWorktreePath(ticket.path, realWorktreePath);

          const outcomePromise = (async () => {
            const dependencyRecord = await readTicketRecordBack(worktreeTicketPath);
            const dependsOn = Array.isArray(dependencyRecord && dependencyRecord.depends_on)
              ? dependencyRecord.depends_on
                  .map((p) => toWorktreePath(p, realWorktreePath))
                  .filter((p) => p && p !== worktreeTicketPath)
              : [];

            const withheldBy = [];
            const prerequisiteStates = {};
            for (const depPath of dependsOn) {
              let depOutcome;
              let depState;
              if (Object.prototype.hasOwnProperty.call(chunkOutcomesByPath, depPath)) {
                depOutcome = await chunkOutcomesByPath[depPath];
                depState = prerequisiteStateFromOutcome(depOutcome);
              } else if (completedTicketOutcomes[depPath] === true) {
                depState = "succeeded";
              } else if (Object.prototype.hasOwnProperty.call(completedTicketOutcomes, depPath)) {
                depState = "failed";
              } else {
                // THIS RUN HOLDS NO VERDICT FOR THIS PREREQUISITE.
                //
                // Either it finished before the drive began — the planner
                // omits done work from every batch, so this run never drove it
                // and never will — or it genuinely is not part of this run.
                // Demanding a verdict this run cannot hold would make every
                // resumed drive with a cross-session dependency unbuildable;
                // assuming success would release a dependant onto work that
                // may not exist. So go and look.
                //
                // READ THE PREREQUISITE'S OWN RECORD, rather than consulting
                // the planner's `already_done` list. That list is the
                // planner's claim, and this gate exists precisely because the
                // planner's claims are not evidence — accepting it here would
                // have left one unverified input in a guard whose whole point
                // is that there are none. It is also the more robust of the
                // two: believing the list requires it to be COMPLETE as well
                // as correct, and a planner that merely omits an entry would
                // silently withhold a dependant that was ready.
                //
                // One dispatch, and only for a prerequisite this run did not
                // itself drive.
                const priorRecord = await readTicketRecordBack(depPath);
                if (priorRecord && priorRecord.lifecycle_status === "done") {
                  // Reported under its own name, not as `succeeded`, so the
                  // difference between watched-to-succeed and read-as-done
                  // stays visible in prerequisite_states.
                  depState = "succeeded_before_this_run";
                } else {
                  depState = "not_in_run_set";
                }
              }
              prerequisiteStates[depPath] = depState;
              if (depState !== "succeeded" && depState !== "succeeded_before_this_run") {
                withheldBy.push(depPath);
              }
            }

            if (withheldBy.length > 0) {
              // WITHHELD. Never reaches driveTicketPhases — no phase agent
              // for this ticket is ever dispatched.
              return {
                ticket_path: ticket.path,
                status: "withheld",
                withheld_by: withheldBy,
                prerequisite_states: prerequisiteStates,
                result: null,
              };
            }

            // Drive each ticket through its needed phases using the flattened
            // per-phase driver (driveTicketPhases) so each phase runs under its
            // own agent template. No ticket-supervisor is dispatched here.
            // isEpicMember=true → the per-ticket pull-request phase is deferred;
            // finalize-feature opens the single epic-level PR.
            const result = await driveTicketPhases(worktreeTicketPath, true);
            return {
              ticket_path: ticket.path,
              // Fail CLOSED. This previously defaulted to "ok", which converted a
              // ticket drive that returned nothing usable into a completed
              // ticket — the halt filter below then had nothing to catch and the
              // epic reported tickets_completed with no work done.
              status: result && result.status ? result.status : "undetermined",
              result,
            };
          })();

          chunkOutcomesByPath[worktreeTicketPath] = outcomePromise;
          return () => outcomePromise;
        });

        const chunkResults = await parallel(chunkThunks);

        for (let idx = 0; idx < chunkResults.length; idx += 1) {
          const r = chunkResults[idx];
          if (r) {
            batchResults.push(r);
          } else {
            // parallel() resolves a thunk that threw to null. Silently dropping it
            // would remove the ticket from the batch record altogether — the run
            // would report a smaller batch rather than a failure. Record it as
            // undetermined so the halt filter below sees it.
            batchResults.push({
              ticket_path: chunk[idx] && chunk[idx].path,
              status: "undetermined",
              result: null,
            });
          }
        }

        // Fold THIS chunk's verdicts in before the next chunk starts.
        //
        // chunkOutcomesByPath is rebuilt per chunk, so it can only answer for
        // members of the chunk being built. A batch larger than BATCH_SIZE is
        // split across several chunks, and a dependant in chunk 2 whose
        // prerequisite sat in chunk 1 would find it in neither map if this
        // update waited until every chunk had finished — the prerequisite
        // would read `not_in_run_set` and the dependant would be withheld
        // even though it had just succeeded. Recording per chunk closes that
        // window; the batch-level pass below is what the NEXT look reads.
        for (const r of chunkResults) {
          if (!r) continue;
          const settled = toWorktreePath(r.ticket_path, realWorktreePath);
          if (settled) {
            completedTicketOutcomes[settled] = !!(
              r.result && r.result.ticket_completed === true
            );
          }
        }
      }

      // Record THIS look's own verdict for every ticket it touched — the
      // input the NEXT look's prompt above reads back as
      // `completedBeforeThisLook`.
      for (const r of batchResults) {
        const normalized = toWorktreePath(r.ticket_path, realWorktreePath);
        if (normalized) {
          completedTicketOutcomes[normalized] = !!(
            r.result && r.result.ticket_completed === true
          );
        }
      }

      // BO-100e-1-i — tickets the eligibility gate withheld before they ever
      // reached driveTicketPhases. Distinct from haltedTickets below: a
      // withheld ticket never attempted anything of its own.
      const withheldResults = batchResults.filter((r) => r.status === "withheld");

      const haltedTickets = batchResults.filter(
        (r) =>
          r.status === "failed" ||
          r.status === "blocked" ||
          r.status === "halt" ||
          r.status === "error" ||
          // A ticket whose drive returned nothing usable has NOT completed.
          r.status === "undetermined"
      );

      if (haltedTickets.length > 0 || withheldResults.length > 0) {
        // outstanding_phases / unverified_phases are carried through, not just the
        // prose message. A ticket the drive ran but could not confirm now reports
        // a failure status (see buildTicketOutcome), so it arrives here rather
        // than in the incomplete-member branch below — and BO-400a-2-iii's
        // requirement is that the operator be told WHICH phase to fix, which the
        // message alone leaves them to parse out of a sentence.
        const haltSummary = haltedTickets.map((r) => ({
          ticket_path: r.ticket_path,
          status: r.status,
          error: r.error || (r.result && r.result.message) || "unknown error",
          outstanding_phases: (r.result && r.result.outstanding_phases) || [],
          unverified_phases: (r.result && r.result.unverified_phases) || [],
        }));

        // BO-100e-1-i — every withheld piece, named with the prerequisite
        // that withheld it. This is the `unbuilt` field BO-100e's
        // config_schema_fragment defines for the whole family.
        const unbuiltSummary = withheldResults.map((r) => ({
          ticket_path: r.ticket_path,
          eligible: false,
          withheld_by: r.withheld_by || [],
          prerequisite_states: r.prerequisite_states || {},
        }));

        // BO-300a-5-iii — THIS is the return that can actually exhibit both kinds
        // of removal at once. At the two epic COMPLETION returns the planned and
        // completed sets are necessarily equal (or both empty), so an uncompleted
        // removal is unreachable there; here, earlier batches are already in
        // `completedBatches` while this batch's members are not. It carries the
        // same `no_longer_present` field and used to carry the same "were not
        // built" sentence, so a partition applied only to the completion returns
        // would leave the defect live at the one site that can show it.
        const haltRecheck = epicRecheckReport(
          compareEpicTicketSets(
            plannedTicketPaths,
            await recheckEpicTicketSet(worktreeEpicPath),
            realWorktreePath
          ),
          completedWorkPaths(completedBatches, realWorktreePath)
        );

        return Object.assign(
          {
            status: "blocked",
            message:
              `Epic "${epicTitle}" halted at batch ${batchNumber} — ` +
              `${haltedTickets.length} ticket(s) failed or blocked` +
              (withheldResults.length > 0
                ? `, ${withheldResults.length} withheld pending an unsatisfied prerequisite`
                : "") +
              `.` +
              (haltRecheck.headline ? ` Also: ${haltRecheck.headline}.` : "") +
              haltRecheck.suffix,
            epic_path: worktreeEpicPath,
            title: epicTitle,
            worktree_path: realWorktreePath,
            resolved_target: resolvedTarget,
            halted_at_batch: batchNumber,
            halted_tickets: haltSummary,
            unbuilt: unbuiltSummary,
            completed_batches: completedBatches,
            looks: lookNumber,
            look_records: lookRecords,
            run_set: plannedTicketPaths.slice(),
            ended_because: "halted",
            suggested_action:
              "Review the ## Comments section of each halted ticket for the blocker details. " +
              "Resolve the blocker(s) and re-run /build-feature to resume.",
          },
          haltRecheck.fields,
          { epic_complete: false }
        );
      }

      // A ticket that ran every phase but could NOT be confirmed complete against
      // its own record (BO-400a-2-iii) is not completed work, even though its
      // phase loop did not halt. It must not be counted into completed_batches —
      // that count is what the operator and the archive check read.
      //
      // BACKSTOP, deliberately kept. Every per-ticket exit now reports a failure
      // status when it could not confirm the ticket, so an unconfirmed member is
      // normally caught by the halted filter above and this branch is not
      // reached. It stays because `ticket_completed === true` is the actual
      // machine-readable verdict, and the failure this guards against is exactly
      // a future exit that returns `ok` without ever setting it — which is the
      // defect the no-phases-to-run path shipped with.
      const incompleteTickets = batchResults.filter(
        (r) => !(r.result && r.result.ticket_completed === true)
      );

      if (incompleteTickets.length > 0) {
        const incompleteSummary = incompleteTickets.map((r) => ({
          ticket_path: r.ticket_path,
          outstanding_phases: (r.result && r.result.outstanding_phases) || [],
          unverified_phases: (r.result && r.result.unverified_phases) || [],
          detail: (r.result && r.result.message) || "no detail reported",
        }));

        // BO-300a-5-iii — the fourth consumer of the same report. It is a
        // backstop that is not normally reached (see the note above), which is
        // exactly why it must be passed the completed set too: a site that is
        // inert today is the site a future change makes load-bearing, and this
        // whole record exists because the last three defects were each an inert
        // path a remedy activated without extending the guard to it.
        const incompleteRecheck = epicRecheckReport(
          compareEpicTicketSets(
            plannedTicketPaths,
            await recheckEpicTicketSet(worktreeEpicPath),
            realWorktreePath
          ),
          completedWorkPaths(completedBatches, realWorktreePath)
        );

        return Object.assign(
          {
            status: "blocked",
            message:
              `Epic "${epicTitle}" is NOT complete — ${incompleteTickets.length} ` +
              `ticket(s) in batch ${batchNumber} ran their phases without being ` +
              `recorded complete in their own records.` +
              (incompleteRecheck.headline ? ` Also: ${incompleteRecheck.headline}.` : "") +
              incompleteRecheck.suffix,
            epic_path: worktreeEpicPath,
            title: epicTitle,
            worktree_path: realWorktreePath,
            resolved_target: resolvedTarget,
            halted_at_batch: batchNumber,
            incomplete_tickets: incompleteSummary,
            unbuilt: [],
            completed_batches: completedBatches,
            looks: lookNumber,
            look_records: lookRecords,
            run_set: plannedTicketPaths.slice(),
            ended_because: "halted",
            suggested_action:
              "For each ticket above, a needed phase is outstanding in the ticket's " +
              "own record — most often a gate that ran, returned success and left no " +
              "sign-off. Re-run that phase (or add the sign-off it owes) and re-run " +
              "/build-feature; the ticket stays out of the completed set until its " +
              "record can prove every needed phase passed.",
          },
          incompleteRecheck.fields,
          { epic_complete: false }
        );
      }

      completedBatches.push({
        batch_number: batchNumber,
        tickets_completed: batchResults.length,
        tickets: batchResults.map((r) => r.ticket_path),
      });
    }
  }

  // Reached only when a look — never the first — released nothing new: the
  // search for further work has genuinely ended.
  const totalTickets = completedBatches.reduce(
    (sum, b) => sum + (b.tickets_completed || 0),
    0
  );

  // BO-300a-5 — the epic's set of work is read AGAIN here, at the moment the
  // completion output is produced, and compared with the set the plan was
  // built from. This is the latest moment the re-read may happen: it is what
  // makes the claim in the output true at the moment it is made.
  //
  // BO-300a-5-iii — the reviewer's captured payload came from HERE: two tickets
  // reported completed by name, one of them then reported as planned work that
  // was not built, all certified with `status: "ok"` and `epic_complete: true`.
  // The completed set below is the same accumulator this return reports under
  // `completed_batches`, so the payload is now judged against its own record.
  const finalRecheck = epicRecheckReport(
    compareEpicTicketSets(
      plannedTicketPaths,
      await recheckEpicTicketSet(worktreeEpicPath),
      realWorktreePath
    ),
    completedWorkPaths(completedBatches, realWorktreePath)
  );

  return Object.assign(
    {
      // BO-300a-5-ii — derived from finalRecheck's own verdict rather than
      // hardcoded and then contradicted by the fields merged in below.
      status: epicOutcomeStatus(finalRecheck),
      epic_path: worktreeEpicPath,
      title: epicTitle,
      worktree_path: realWorktreePath,
      resolved_target: resolvedTarget,
      batches_run: completedBatches.length,
      tickets_completed: totalTickets,
      completed_batches: completedBatches,
      looks: lookNumber,
      look_records: lookRecords,
      run_set: plannedTicketPaths.slice(),
      ended_because: "no_further_work_eligible",
      unbuilt: [],
      message:
        (finalRecheck.withhold
          ? `Epic "${epicTitle}" is NOT complete — ${finalRecheck.headline}. ` +
            `${completedBatches.length} batch(es) run, ${totalTickets} ticket(s) driven.`
          : `Epic "${epicTitle}" complete. ` +
            `${completedBatches.length} batch(es) run, ${totalTickets} ticket(s) completed.`) +
        finalRecheck.suffix,
    },
    finalRecheck.fields
  );
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

  if (!ticketResult) {
    return {
      status: "error",
      resolved_target: resolvedTarget,
      message: `driveTicketPhases returned null for ticket: ${worktreeTicketPath}`,
    };
  }

  return ticketResult;
}
