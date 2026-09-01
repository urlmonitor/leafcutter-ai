/**
 * Behavioral harness for the build-ticket.js / build-feature.js drivers.
 *
 * Loads a real workflow script and EXECUTES it against stubbed workflow
 * globals, so the assertions observe actual control flow rather than the
 * presence of a string in the source. A grep-only test cannot tell a fixed
 * guard from a broken one (both mention the same identifiers); this harness
 * can, because it records what the script actually dispatched and what it
 * actually wrote.
 *
 * Usage:
 *   node harness_build_ticket_guard.mjs <path-to-driver.js> '<scenario-json>'
 *   node harness_build_ticket_guard.mjs <path-to-driver.js> @<scenario-json-file>
 *
 * ---------------------------------------------------------------------------
 * MODE 1 — legacy coder-guard scenarios (BO-2000e-2). Unchanged.
 * ---------------------------------------------------------------------------
 *   {
 *     "has_test_requirements": bool,     // what the planner reports
 *     "existing_test_files": [...],      // tests a prior drive left on disk
 *     "phases": ["test-writer", ...],    // agents marked needed, canonical order
 *     "test_writer_result": {...}        // what the test-writer stub returns
 *   }
 *
 * ---------------------------------------------------------------------------
 * MODE 2 — record-aware scenarios (BO-400a-2-ii/iii, BO-2900f-1-i/ii/iii,
 *          BO-300a-5, BO-300a-5-i, BO-1900a-4, BO-1900a-4-i).
 *
 * Active whenever "tickets" is present. Ticket records are REAL .md files on
 * disk, written by the caller before the run. Phase-agent stubs append REAL
 * sign-off headings to those files, exactly as a phase agent would; the caller
 * reads the files back after the run. That round-trip — not the value the
 * script returned — is the evidence.
 *
 *   {
 *     "record_dir": "/tmp/...",          // the worktree root for this run
 *     "args": { ... },                   // overrides the args global wholesale
 *     "resolve": {...} | null,           // resolve-target stub reply
 *     "worktree_agent": {...} | null,    // worktree-setup stub reply
 *     "worktree_check": {...} | null,    // build-ticket.js ambient git check reply
 *     "epic": {
 *        "path": "<abs epic folder>",
 *        "title": "...",
 *        "reads": [                      // consumed in order, one per epic
 *          { "present": [{"path": "...", "status": "todo"}] },   // enumeration
 *          { "error": "ENOENT ..." },    // an enumeration that cannot be read
 *          { "present": [...], "omit_readable": true },  // reply with NO
 *                                        // `readable` key at all — see below
 *          { "present": [...],           // BO-300a-5-iii: an EXPLICIT batch
 *            "batches": [                // plan, served verbatim. Optional;
 *              {"batch_number": 1,       // without it every buildable piece
 *               "tickets": [{"path": "...", "status": "todo"}]}  // lands in
 *            ] }                         // ONE batch and a drive can never
 *                                        // reach a completion-time re-check
 *                                        // with one batch already pushed to
 *                                        // completedBatches and another piece
 *                                        // planned but not completed.
 *        ]
 *     },
 *     "tickets": {
 *        "<abs ticket path>": {
 *          "title": "...",
 *          "files_touched": [...],
 *          "has_test_requirements": bool,
 *          "existing_test_files": [...],
 *          "phases": ["test-writer", "python-coder", ...],   // status: needed
 *          "ordered_phases": [{"agent": "commit", "status": "signed_off"}],
 *                                        // verbatim planner reply; overrides
 *                                        // "phases" so a scenario can present
 *                                        // phases that are NOT needed
 *          "results": {
 *            "<phase>": { "status": "ok"|"blocker"|"failed",
 *                         "record": true|false,       // append a sign-off?
 *                         "tests_written": [...] }
 *            // or an ARRAY of the above, one entry per dispatch attempt
 *          },
 *          "delete_record_after_phase": "<phase>",   // makes the record unreadable
 *          "delete_record_before_run": bool,
 *          "plan_reply": { "mode": "...", "value": ... }   // OPT-IN, see below
 *        }
 *     },
 *     "classify": { "<phase>": "mechanical"|"cross_agent"|"design"|"halt" }
 *   }
 *
 * ---------------------------------------------------------------------------
 * UNUSABLE PLAN REPLIES — "plan_reply" (BO-1900a-4-ii). OPT-IN, DEFAULT OFF.
 *
 * Without this key the ticket-planner stub answers exactly as it always has,
 * so every pre-existing scenario keeps its current meaning byte for byte. The
 * key exists because the harness otherwise SYNTHESISES the planner reply from
 * the fixture's own frontmatter and can therefore never present the drive with
 * a reply it cannot use — the precise condition BO-1900a-4-ii is about.
 *
 *   { "mode": "null" }                — the planning step returns nothing at all
 *   { "mode": "not_an_object",
 *     "value": <any non-object> }     — the reply is not a usable record
 *                                       (defaults to a truncated-agent string)
 *   { "mode": "omit_ordered_phases" } — a valid record that states NO ordered
 *                                       list of phases either way. Legal under
 *                                       TICKET_PLANNER_SCHEMA's optional list,
 *                                       and the shape a truncated or degraded
 *                                       planner actually produces.
 *
 * Every reply the stub serves — controlled or not — is recorded in the
 * `plan_replies` output array, so a test can SHOW the reply really did omit
 * its list rather than assume it. That array is observation only: it adds no
 * write path and changes no reply.
 *
 * A TICKET THAT NAMES NO PHASE (BO-400a-2-iv) needs no new mode: pass
 * "ordered_phases": [] for the empty list, an all-`not_needed` array for the
 * third shape, and { "mode": "omit_ordered_phases" } for a ticket that names
 * no list at all.
 *
 * ---------------------------------------------------------------------------
 * DISPATCH LABELS THE HARNESS UNDERSTANDS
 *
 * The drivers have no filesystem access — every read and every write is an
 * agent() dispatch. The harness therefore answers, and records, three families
 * of dispatch in addition to the phase agents. Canonical labels:
 *
 *   record read-back      label: "signoff-readback"
 *                         (also matched: *read-back*, *signoff-verify*,
 *                          *verify-signoff*, *record-check*, *record-verify*)
 *                         reply: { readable, ticket_path, lifecycle_status,
 *                                  needed_phases, signoffs, signed_off_agents }
 *                         or   : { readable: false, error }
 *
 *   completion write      label: "ticket-completion-write"
 *                         (also matched: *completion*, *status-write*,
 *                          *mark-done*, *ticket-done*, *lifecycle-write*)
 *                         effect: flips the record's frontmatter status to done
 *                         reply: { status: "ok" } | { status: "error", error }
 *
 *   epic enumeration      label: "epic-planner" (first) and any subsequent
 *                         "epic-recheck" / "epic-readback" / "epic-reread" /
 *                         "epic-set" / "epic-scan". Each consumes the next
 *                         entry of scenario.epic.reads.
 *
 * OMITTED `readable` FLAG. A read entry carrying "omit_readable": true replies
 * with the ordinary success shape MINUS the `readable` key. EPIC_RECHECK_SCHEMA
 * declares no `required`, so a real status-checker may legitimately answer this
 * way — and a consumer that tests `reply.readable === false` (rather than
 * `!== true`) then takes the VERIFIED branch on a reply that verified nothing.
 * Without this mode the flag is always present and always agrees with the
 * outcome, so a fail-open re-check and a fail-closed one are indistinguishable.
 *
 * Any other label is treated as a phase-agent dispatch — that is what the
 * `dispatched` array measures.
 * ---------------------------------------------------------------------------
 *
 * Prints a JSON object:
 *   {
 *     dispatched:   [label, ...],          // phase-agent dispatches, in order
 *     dispatches:   [{label, agent_type, phase, ticket_path, attempt,
 *                     prompt, opts_keys, opts_ticket_path}, ...],
 *                   // `prompt` is the FULL dispatch string, verbatim. Prose is
 *                   // the only channel a workflow driver has to a phase agent
 *                   // (agent(prompt, opts) accepts only agentType / schema /
 *                   // label / phase / model / effort / isolation — any other
 *                   // opts key is dropped), so what the agent can key on is
 *                   // exactly what this string contains. `opts_ticket_path`
 *                   // and `opts_keys` are recorded so a test can SHOW that the
 *                   // opts channel carried nothing, rather than assume it.
 *     readbacks:    [{label, ticket_path, readable, signed_off_agents,
 *                     needed_phases}, ...],
 *                   // `needed_phases` is what the DRIVER was told the record
 *                   // still names as needed — observation only.
 *     writes:       [{label, ticket_path, applied, error, prompt_excerpt}, ...],
 *     enumerations: [{label, index, failed}, ...],
 *     plan_replies: [{ticket_path, mode, reply_type, has_ordered_phases,
 *                     ordered_phases}, ...],
 *                   // one entry per per-ticket planner dispatch, in order.
 *                   // `has_ordered_phases` is an OWN-PROPERTY check, so a
 *                   // reply that omits the list is distinguishable from one
 *                   // that states an empty list.
 *     logs:         [string, ...],
 *     records:      {"<ticket path>": {exists, lifecycle_status, signoffs,
 *                     signed_off_agents, agents, needed_phases}},
 *                   // `agents` / `needed_phases` are the map AS THIS HARNESS
 *                   // PARSES IT, which is not always what the .md says: an
 *                   // agents: block that is the LAST frontmatter key does not
 *                   // parse (parseRecord's `\Z` is a literal "Z" in JS). Put a
 *                   // key after the map in the fixture when the driver needs
 *                   // to see it — see write_ticket_record(extra_frontmatter).
 *     result:       <script return value>,
 *     error:        <string, if the script threw>
 *   }
 */
import { readFileSync, writeFileSync, existsSync, rmSync } from "node:fs";

const [scriptPath, scenarioArg] = process.argv.slice(2);

function loadScenario(arg) {
  if (!arg) return {};
  if (arg.startsWith("@")) return JSON.parse(readFileSync(arg.slice(1), "utf8"));
  return JSON.parse(arg);
}

const scenario = loadScenario(scenarioArg);
const recordMode = !!scenario.tickets;
const ticketConfigs = scenario.tickets || {};
const ticketPaths = Object.keys(ticketConfigs);

const source = readFileSync(scriptPath, "utf8").replace(
  /^export const meta/m,
  "const meta"
);

// ---------------------------------------------------------------------------
// Recorded observations
// ---------------------------------------------------------------------------
const dispatched = [];
const dispatches = [];
const readbacks = [];
const writes = [];
const enumerations = [];
const planReplies = [];
const logs = [];
const attemptCounts = {}; // "<ticket>::<phase>" -> n

// ---------------------------------------------------------------------------
// Real ticket-record I/O — the artifacts the run is judged on
// ---------------------------------------------------------------------------

const SIGNOFF_RE =
  /^###\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+—\s+([A-Za-z0-9_-]+)\s+\(status:\s*([A-Za-z_]+)\s*\)\s*$/;

/** Parse a ticket .md into the shape a record read-back reports. */
function parseRecord(path) {
  if (!existsSync(path)) {
    return { readable: false, error: `ENOENT: no such ticket record: ${path}` };
  }
  let text;
  try {
    text = readFileSync(path, "utf8");
  } catch (err) {
    return { readable: false, error: `EIO reading ${path}: ${err.message}` };
  }

  const fmMatch = text.match(/^---\n([\s\S]*?)\n---/);
  const frontmatter = fmMatch ? fmMatch[1] : "";

  const statusMatch = frontmatter.match(/^status:\s*(\S+)\s*$/m);
  const lifecycleStatus = statusMatch ? statusMatch[1] : null;

  // agents: map — collect "  <name>: <status>" lines under "agents:"
  const agents = {};
  const agentsBlock = frontmatter.match(/^agents:\n([\s\S]*?)(?=^\S|\Z)/m);
  if (agentsBlock) {
    for (const line of agentsBlock[1].split("\n")) {
      const m = line.match(/^\s+([A-Za-z0-9_-]+):\s*(\S+)\s*$/);
      if (m) agents[m[1]] = m[2];
    }
  }

  // depends_on: list (BO-100e-1-i) — a PyYAML block list under a top-level
  // key serializes with its dash bullets at COLUMN 0, not indented (the same
  // real-artifact shape documented for files_touched elsewhere in this repo).
  // The agentsBlock lookahead above (`(?=^\S|\Z)`) relies on its own list
  // items being INDENTED so a column-0 line only ever means "the next key" —
  // that assumption is false here, so a dedicated pattern is used instead:
  // capture only the run of column-0 "-" bullet lines immediately following
  // "depends_on:", however many there are, however this key is ordered
  // relative to any other frontmatter key.
  const dependsOn = [];
  const dependsOnBlock = frontmatter.match(/^depends_on:\n((?:^-[^\n]*\n?)*)/m);
  if (dependsOnBlock) {
    for (const line of dependsOnBlock[1].split("\n")) {
      const m = line.match(/^-\s*(.+?)\s*$/);
      if (!m) continue;
      let value = m[1];
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      dependsOn.push(value);
    }
  }

  const signoffs = [];
  for (const line of text.split("\n")) {
    const m = line.match(SIGNOFF_RE);
    if (m) signoffs.push({ agent: m[1], status: m[2] });
  }

  // implementation_task_agents (BO-3000a) — the `### <agent>` subsection
  // headings under `## Implementation Tasks`, and ONLY under that section.
  //
  // Scoping is the whole point. A real ticket also carries `## Agent Contracts`
  // with its own `### <agent>` subsections (`### documentation-expert` is
  // routine), and those declare documentation obligations rather than work
  // handed off to another phase. A scan over every `### <agent>` heading in the
  // file therefore resolves the WRONG agent on an ordinary ticket — verified
  // against the real on-disk record for GE-122d-1, which carries exactly one
  // `### test-writer` under Implementation Tasks and one
  // `### documentation-expert` under Agent Contracts.
  // Sliced explicitly rather than matched with a `(?=^## |\Z)` lookahead.
  // JavaScript has NO `\Z` escape — it is a literal "Z" — which is the same
  // trap already documented for the agents: block above. With the section last
  // in the file (the shape appendImplementationTask produces, and the shape a
  // coder appending to a real ticket produces) there is no following `## `
  // heading, so a `\Z`-terminated lookahead fails to match ANYTHING and the
  // handoff target silently resolves to nothing. Written the first time with
  // exactly that bug; the reachability test is what caught it.
  const implementationTaskAgents = [];
  const tasksHeading = text.match(/^##[ \t]+Implementation Tasks[ \t]*$/m);
  if (tasksHeading) {
    const rest = text.slice(tasksHeading.index + tasksHeading[0].length);
    const nextSection = rest.match(/^##[ \t]+/m);
    const section = nextSection ? rest.slice(0, nextSection.index) : rest;
    for (const line of section.split("\n")) {
      const m = line.match(/^###[ \t]+([A-Za-z0-9_-]+)[ \t]*$/);
      if (m && !implementationTaskAgents.includes(m[1])) {
        implementationTaskAgents.push(m[1]);
      }
    }
  }

  return {
    readable: true,
    ticket_path: path,
    lifecycle_status: lifecycleStatus,
    agents,
    needed_phases: Object.keys(agents).filter((a) => agents[a] === "needed"),
    depends_on: dependsOn,
    implementation_task_agents: implementationTaskAgents,
    signoffs,
    signed_off_agents: signoffs.map((s) => s.agent),
  };
}

/** Append a real sign-off heading, exactly as a phase agent would. */
function appendSignoff(path, agentName, status) {
  if (!existsSync(path)) return false;
  const stamp = "2026-08-18 12:00";
  const block =
    `\n### ${stamp} — ${agentName} (status: ${status})\n` +
    `harness-simulated phase agent sign-off\n`;
  writeFileSync(path, readFileSync(path, "utf8") + block, "utf8");
  return true;
}

/**
 * Promote an agent to `needed` in the record's frontmatter agents map — what
 * architect-review really does when it concludes an ADR or diagram is required
 * (BO-3700). Adds the key when absent, flips it when present.
 */
function promoteAgentToNeeded(path, agentName) {
  if (!existsSync(path)) return false;
  const text = readFileSync(path, "utf8");
  const fmMatch = text.match(/^---\n([\s\S]*?)\n---/);
  if (!fmMatch) return false;
  let fm = fmMatch[1];
  const existing = new RegExp(`^(\\s+)${agentName}:\\s*\\S+\\s*$`, "m");
  if (existing.test(fm)) {
    fm = fm.replace(existing, `$1${agentName}: needed`);
  } else if (/^agents:\n/m.test(fm)) {
    fm = fm.replace(/^agents:\n/m, `agents:\n  ${agentName}: needed\n`);
  } else {
    return false;
  }
  writeFileSync(path, text.replace(fmMatch[0], `---\n${fm}\n---`), "utf8");
  return true;
}

/**
 * Append an `## Implementation Tasks` / `### <agent>` block — the channel
 * templates/agents/python-coder.md §"Test Delegation" tells a coder to use when
 * handing work to another phase (BO-3000a). Reuses the section when it already
 * exists so two calls do not produce two `## Implementation Tasks` headings.
 */
function appendImplementationTask(path, agentName) {
  if (!existsSync(path)) return false;
  const text = readFileSync(path, "utf8");
  const entry = `### ${agentName}\n\n- [ ] harness-simulated handoff task\n`;
  if (/^##[ \t]+Implementation Tasks[ \t]*$/m.test(text)) {
    writeFileSync(path, `${text}\n${entry}`, "utf8");
  } else {
    writeFileSync(path, `${text}\n## Implementation Tasks\n\n${entry}`, "utf8");
  }
  return true;
}

/** Flip the record's frontmatter lifecycle status. */
function setLifecycleStatus(path, newStatus) {
  if (!existsSync(path)) {
    return { applied: false, error: `ENOENT: no such ticket record: ${path}` };
  }
  const text = readFileSync(path, "utf8");
  const fmMatch = text.match(/^---\n([\s\S]*?)\n---/);
  if (!fmMatch) {
    return { applied: false, error: `no frontmatter block in ${path}` };
  }
  const updatedFm = fmMatch[1].replace(/^status:\s*\S+\s*$/m, `status: ${newStatus}`);
  const updated = text.replace(fmMatch[0], `---\n${updatedFm}\n---`);
  writeFileSync(path, updated, "utf8");
  return { applied: true };
}

function deleteRecord(path) {
  if (existsSync(path)) rmSync(path);
}

/** Longest ticket path that appears in the prompt (handles parallel epics). */
function ticketFromPrompt(prompt) {
  let best = null;
  for (const p of ticketPaths) {
    if (typeof prompt === "string" && prompt.includes(p)) {
      if (best === null || p.length > best.length) best = p;
    }
  }
  return best;
}

// ---------------------------------------------------------------------------
// Label routing
// ---------------------------------------------------------------------------
const RE_EPIC_ENUM =
  /^epic[-_]?(planner|plan|recheck|re-check|readback|read-back|reread|re-read|set|scan|survey|enumerate)/i;
const RE_COMPLETION_WRITE =
  /(completion|complete[-_]?write|status[-_]?write|mark[-_]?done|mark[-_]?ticket[-_]?done|ticket[-_]?done|lifecycle[-_]?write|record[-_]?done)/i;
const RE_READBACK =
  /(read[-_]?back|sign[-_]?off[-_]?(verify|verifier|check|audit)|verify[-_]?sign[-_]?off|record[-_]?(check|verify|audit|read)|phase[-_]?record)/i;

// ---------------------------------------------------------------------------
// Epic enumeration replies
// ---------------------------------------------------------------------------
let epicReadIndex = 0;

function epicEnumerationReply(label) {
  const epic = scenario.epic || {};
  const reads = epic.reads || [];
  const index = epicReadIndex;
  epicReadIndex += 1;

  const read = reads[index];
  if (!read) {
    enumerations.push({ label, index, failed: true, reason: "no read configured" });
    return {
      status: "error",
      readable: false,
      error: `harness: scenario.epic.reads has no entry ${index}`,
    };
  }

  if (read.error) {
    enumerations.push({ label, index, failed: true, reason: read.error });
    return {
      status: "error",
      readable: false,
      error: read.error,
      epic_path: epic.path,
      title: epic.title || epic.path,
    };
  }

  const present = read.present || [];
  const buildable = present.filter((t) => t.status !== "done");
  // An explicit `batches` array is served VERBATIM (BO-300a-5-iii). Without it
  // the derivation below puts every buildable piece into ONE batch, and a
  // single batch cannot produce the state the mixed-removal case needs: a
  // payload whose completed record names one piece (a batch that finished and
  // was pushed to completedBatches) while another planned piece never reached
  // it. OPT-IN and guarded by Array.isArray, so every pre-existing scenario
  // gets byte-identical replies.
  const batches = Array.isArray(read.batches)
    ? read.batches
    : buildable.length === 0
      ? []
      : [{ batch_number: 1, tickets: buildable.map((t) => ({ path: t.path, status: "todo" })) }];

  // What the real planner OMITS from every batch because the ticket's own
  // frontmatter already reads `status: done` — the resume set. DERIVED from
  // `present` by default rather than opt-in, because that is exactly what the
  // real planner does with the same input, and a fixture that marks a ticket
  // done should not also have to remember to restate it here. An explicit
  // `already_done` array overrides, for scenarios that need to model a planner
  // reply which omits or misreports the set.
  const alreadyDone = Array.isArray(read.already_done)
    ? read.already_done
    : present.filter((t) => t.status === "done").map((t) => t.path);

  const omitReadable = read.omit_readable === true;

  enumerations.push({
    label,
    index,
    failed: false,
    omitted_readable: omitReadable,
    present: present.map((t) => t.path),
  });

  // Reply carries BOTH shapes: the batch plan the first read needs, and a flat
  // ticket list a completion-time re-read is likely to ask for.
  //
  // When omit_readable is set the `readable` key is left OFF entirely. This is
  // a legal reply under EPIC_RECHECK_SCHEMA (no `required` list), and it is the
  // only shape that can tell a `readable === false` check apart from a
  // `readable !== true` one.
  const reply = {
    epic_path: epic.path,
    title: epic.title || epic.path,
    batches,
    already_done: alreadyDone,
    // The folder's FULL contents at this look — every sub-ticket, whatever its
    // status and whether or not it is eligible yet. Derived from `present`
    // because that is exactly what a real planner reports for question (7),
    // and an explicit `enumerated` overrides for scenarios that need to model
    // a planner reply which omits or misstates it.
    enumerated: Array.isArray(read.enumerated)
      ? read.enumerated
      : present.map((t) => t.path),
    tickets: present,
    ticket_paths: present.map((t) => t.path),
  };
  if (!omitReadable) {
    reply.readable = true;
  }
  return reply;
}

// ---------------------------------------------------------------------------
// The agent() stub
// ---------------------------------------------------------------------------
async function agent(prompt, opts = {}) {
  const label = opts.label || opts.agentType || "unknown";

  // --- infrastructure stubs -------------------------------------------------
  if (label === "worktree-check") {
    return scenario.worktree_check === undefined
      ? { git_type: "file", branch: "feat/harness" }
      : scenario.worktree_check;
  }

  if (label === "resolve-target") {
    if (scenario.resolve !== undefined) return scenario.resolve;
    return {
      target_type: recordMode && scenario.epic ? "epic" : "ticket",
      epic_path: scenario.epic ? scenario.epic.path : null,
      ticket_path: ticketPaths[0] || null,
      worktree_path: scenario.record_dir || "/fake/worktree",
    };
  }

  if (label === "worktree-setup") {
    if (scenario.worktree_agent !== undefined) return scenario.worktree_agent;
    return { worktree_path: scenario.record_dir || "/fake/worktree", status: "reused" };
  }

  if (RE_EPIC_ENUM.test(label)) {
    return epicEnumerationReply(label);
  }

  // --- record write ---------------------------------------------------------
  if (RE_COMPLETION_WRITE.test(label)) {
    const ticketPath = ticketFromPrompt(prompt) || opts.ticket_path || null;
    if (!ticketPath) {
      writes.push({
        label,
        ticket_path: null,
        applied: false,
        error: "harness: completion write named no known ticket record",
        prompt_excerpt: String(prompt).slice(0, 300),
      });
      return { status: "error", error: "no ticket path in completion-write prompt" };
    }
    const outcome = setLifecycleStatus(ticketPath, "done");
    writes.push({
      label,
      ticket_path: ticketPath,
      applied: outcome.applied,
      error: outcome.error || null,
      prompt_excerpt: String(prompt).slice(0, 300),
    });
    return outcome.applied
      ? { status: "ok", ticket_path: ticketPath }
      : { status: "error", ticket_path: ticketPath, error: outcome.error };
  }

  // --- record read-back -----------------------------------------------------
  if (RE_READBACK.test(label)) {
    const ticketPath = ticketFromPrompt(prompt) || opts.ticket_path || null;
    const record = ticketPath
      ? parseRecord(ticketPath)
      : { readable: false, error: "harness: read-back named no known ticket record" };
    readbacks.push({
      label,
      ticket_path: ticketPath,
      readable: record.readable === true,
      signed_off_agents: record.signed_off_agents || [],
      // Observation only (BO-1900a-4-ii): what the DRIVER was told the record
      // still names as needed. Recorded so a test can show the required set it
      // is reasoning about was really non-empty, rather than assume it.
      needed_phases: record.needed_phases || [],
      // Observation only (BO-3000a): the `### <agent>` subsections the record
      // carries under `## Implementation Tasks`. Recorded so a test can show
      // the driver was HANDED a resolvable target before asserting it used one.
      implementation_task_agents: record.implementation_task_agents || [],
      prompt_excerpt: String(prompt).slice(0, 300),
    });
    return record;
  }

  // --- per-ticket planner ---------------------------------------------------
  if (label === "ticket-planner") {
    if (!recordMode) {
      // Legacy mode — unchanged.
      return {
        ticket_path: "/fake/worktree/tickets/TICKET-example.md",
        title: "Example ticket",
        files_touched: ["scripts/example.py"],
        has_test_requirements: scenario.has_test_requirements,
        existing_test_files: scenario.existing_test_files || [],
        ordered_phases: (scenario.phases || []).map((a) => ({ agent: a, status: "needed" })),
      };
    }
    const ticketPath = ticketFromPrompt(prompt);
    const cfg = (ticketPath && ticketConfigs[ticketPath]) || {};
    const usable = {
      ticket_path: ticketPath,
      title: cfg.title || ticketPath,
      files_touched: cfg.files_touched || ["scripts/example.py"],
      has_test_requirements: cfg.has_test_requirements === true,
      existing_test_files: cfg.existing_test_files || [],
      // ordered_phases, when given, is the planner reply VERBATIM — the only
      // way a scenario can present a ticket whose phases are already
      // signed_off (and so whose needed set is empty).
      ordered_phases: Array.isArray(cfg.ordered_phases)
        ? cfg.ordered_phases
        : (cfg.phases || []).map((a) => ({ agent: a, status: "needed" })),
    };

    // OPT-IN unusable-reply control (BO-1900a-4-ii). With no `plan_reply` key
    // `reply` stays `usable`, which is byte-identical to what this branch
    // returned before the key existed — no pre-existing scenario changes.
    const planMode = (cfg.plan_reply && cfg.plan_reply.mode) || null;
    let reply = usable;
    if (planMode === "null") {
      reply = null;
    } else if (planMode === "not_an_object") {
      reply =
        cfg.plan_reply.value !== undefined
          ? cfg.plan_reply.value
          : "ticket-planner failed: the reply was truncated before any JSON was emitted";
    } else if (planMode === "omit_ordered_phases") {
      reply = Object.assign({}, usable);
      delete reply.ordered_phases;
    } else if (planMode) {
      reply = { harness_error: `unknown plan_reply mode: ${planMode}` };
    }

    planReplies.push({
      ticket_path: ticketPath,
      mode: planMode,
      reply_type:
        reply === null ? "null" : Array.isArray(reply) ? "array" : typeof reply,
      has_ordered_phases:
        !!reply &&
        typeof reply === "object" &&
        Object.prototype.hasOwnProperty.call(reply, "ordered_phases"),
      ordered_phases:
        reply && typeof reply === "object" && Array.isArray(reply.ordered_phases)
          ? reply.ordered_phases
          : null,
    });

    return reply;
  }

  // --- failure classifier ---------------------------------------------------
  if (label === "failure-classifier") {
    const table = scenario.classify || {};
    const ticketPath = ticketFromPrompt(prompt);
    const cfg = (ticketPath && ticketConfigs[ticketPath]) || {};
    const perTicket = cfg.classify || {};
    let classification = "halt";
    for (const phaseName of Object.keys(perTicket)) {
      if (typeof prompt === "string" && prompt.includes(`failing phase ${phaseName}`)) {
        classification = perTicket[phaseName];
      }
    }
    for (const phaseName of Object.keys(table)) {
      if (typeof prompt === "string" && prompt.includes(`failing phase ${phaseName}`)) {
        classification = table[phaseName];
      }
    }
    return { classification, reason: "harness classification" };
  }

  // --- everything else is a phase-agent dispatch ----------------------------
  dispatched.push(label);

  const ticketPath = recordMode ? ticketFromPrompt(prompt) : null;
  const key = `${ticketPath}::${label}`;
  attemptCounts[key] = (attemptCounts[key] || 0) + 1;
  const attempt = attemptCounts[key];

  dispatches.push({
    label,
    agent_type: opts.agentType || null,
    phase: opts.phase || null,
    ticket_path: ticketPath,
    attempt,
    // The FULL dispatch string. Prose is the only channel to a phase agent, so
    // whatever the agent template can key on has to be in here.
    prompt: typeof prompt === "string" ? prompt : String(prompt),
    opts_keys: Object.keys(opts || {}),
    opts_ticket_path:
      opts && typeof opts.ticket_path === "string" ? opts.ticket_path : null,
  });

  if (!recordMode) {
    if (label === "test-writer") return scenario.test_writer_result;
    return { status: "ok" };
  }

  const cfg = (ticketPath && ticketConfigs[ticketPath]) || {};
  const results = cfg.results || {};
  let spec = results[label];
  if (Array.isArray(spec)) {
    spec = spec[Math.min(attempt - 1, spec.length - 1)];
  }
  spec = spec || { status: "ok", record: true };

  const status = spec.status || "ok";

  // A phase that records leaves a real sign-off in the real record. A phase
  // with record:false reports success and leaves nothing — BUG-23.
  if (spec.record !== false && ticketPath) {
    appendSignoff(ticketPath, label, status);
  }

  // BO-3700: a running phase promoting another agent to `needed` in the real
  // on-disk record — what architect-review does when it decides an ADR is
  // required. Written to the record, not just reported, so the driver can only
  // learn about it the way it learns about everything else: by reading back.
  if (Array.isArray(spec.promotes) && ticketPath) {
    for (const promoted of spec.promotes) promoteAgentToNeeded(ticketPath, promoted);
  }

  // BO-3000a: the coder's prescribed handoff channel — a `### <agent>` block
  // under `## Implementation Tasks` in the record itself.
  if (typeof spec.adds_implementation_task === "string" && ticketPath) {
    appendImplementationTask(ticketPath, spec.adds_implementation_task);
  }

  if (cfg.delete_record_after_phase === label && ticketPath) {
    deleteRecord(ticketPath);
  }

  const reply = { status };
  if (spec.tests_written !== undefined) reply.tests_written = spec.tests_written;
  if (spec.red_baseline_verified !== undefined) {
    reply.red_baseline_verified = spec.red_baseline_verified;
  }
  if (spec.message !== undefined) reply.message = spec.message;
  // Passed through only when the scenario sets it, so a handoff spec that omits
  // it reproduces the real defect shape: `status: handoff` with no target field.
  if (spec.handoff_target !== undefined) reply.handoff_target = spec.handoff_target;
  return reply;
}

// ---------------------------------------------------------------------------
// Run
// ---------------------------------------------------------------------------

for (const p of ticketPaths) {
  if (ticketConfigs[p].delete_record_before_run) deleteRecord(p);
}

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

const run = new AsyncFunction(
  "agent",
  "parallel",
  "pipeline",
  "log",
  "phase",
  "args",
  "budget",
  "workflow",
  source
);

const defaultArgs = {
  ticket_path: "/fake/worktree/tickets/TICKET-example.md",
  // Supplying worktree_path makes the script trust the caller and skip the
  // ambient git check, so the harness never shells out.
  worktree_path: "/fake/worktree",
};

let result = null;
let errorMessage = null;

try {
  result = await run(
    agent,
    async (thunks) => Promise.all(thunks.map((t) => t())),
    async (items) => items,
    (msg) => {
      logs.push(String(msg));
    },
    () => {},
    scenario.args !== undefined ? scenario.args : defaultArgs,
    { total: null, spent: () => 0, remaining: () => Infinity },
    async () => ({})
  );
} catch (err) {
  errorMessage = err && err.stack ? err.stack : String(err);
}

const records = {};
for (const p of ticketPaths) {
  const parsed = parseRecord(p);
  records[p] = parsed.readable
    ? {
        exists: true,
        lifecycle_status: parsed.lifecycle_status,
        signoffs: parsed.signoffs,
        signed_off_agents: parsed.signed_off_agents,
        // Observation only (BO-1900a-4-ii): the agents map AS THE HARNESS
        // PARSES IT. A record whose agents: block is the last frontmatter key
        // does not parse here at all (parseRecord's lookahead uses `\Z`, which
        // JavaScript treats as a literal "Z"), so a fixture can silently
        // present the driver with an empty needed set while the .md on disk
        // plainly names needed phases. Surfacing it lets a test assert the
        // fixture really is the shape it claims, instead of inheriting that
        // blind spot.
        agents: parsed.agents,
        needed_phases: parsed.needed_phases,
      }
    : { exists: false, error: parsed.error };
}

console.log(
  JSON.stringify({
    dispatched,
    dispatches,
    readbacks,
    writes,
    enumerations,
    plan_replies: planReplies,
    logs,
    records,
    result,
    error: errorMessage,
  })
);
