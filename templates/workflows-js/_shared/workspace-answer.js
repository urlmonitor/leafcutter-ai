// SINGLE SOURCE of the workflow runtime's workspace + shell-reply rules (BO-4300c-3, BO-4300a-1-ia, ADR-070).
// scripts/build_phases_workflows.py copies this text between the WORKSPACE-ANSWER marker lines of each
// consuming workflow at build time (E2 bodies have no require, ADR-030). Never edit a copy in a workflow.
const WORKSPACE_STEP_LABEL = "workspace-ensure";
const SHELL_RUNNER_AGENT = "shell-runner";
const WORKSPACE_QUOTE_LIMIT = 2048;
const SHELL_REPLY_SCHEMA = {
  type: "object",
  properties: {
    command: { type: "string" },
    exit_status: { type: "number" },
    stdout: { type: "string" },
    stderr: { type: "string" },
    declined: { type: "boolean" },
    agent: { type: "string" },
    reason: { type: "string" },
  },
};
const DECLINE_PROSE = /declin|outside (?:of )?(?:my|its|the agent's) (?:role|scope|charter)|can(?:'|no)t (?:help|run|do)|unable to (?:help|run)|not (?:able|permitted) to/i;

// Bounded (2 KB) quotation of whatever was received, so a failure always shows the reply it is about.
function workspaceQuote(received) {
  let text;
  if (received === undefined) text = "(no answer)";
  else if (typeof received === "string") text = received;
  else {
    try { text = JSON.stringify(received); } catch (_e) { text = String(received); }
    if (text === undefined) text = String(received);
  }
  return text.length > WORKSPACE_QUOTE_LIMIT ? text.slice(0, WORKSPACE_QUOTE_LIMIT) + "...[truncated]" : text;
}

// A string that is one JSON object becomes that object; anything else stays as it was.
function workspaceParseJson(value) {
  if (typeof value !== "string") return value;
  const trimmed = value.trim();
  if (trimmed.charAt(0) !== "{") return value;
  try { return JSON.parse(trimmed); } catch (_e) { return value; }
}

// kind: "declined" | "none" | "unreadable" | "refused" | "error" | "invalid" -- why nothing was accepted.
function workspaceReject(reason, raw, kind) {
  return { accepted: false, kind: kind || "invalid", reason: reason, received: workspaceQuote(raw) };
}

function workspaceIsObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

// ONE reply check for every shell step (a decline, prose, a non-JSON reply or a reply without the
// requested result is never "the step ran"). Returns {ok:true, exit_status, stdout, stderr} or
// {ok:false, reason, received}. Both executors' reply shapes are read (exit_status/stdout, and the
// older exit_code/output).
function shellStepReply(raw, stepName) {
  const step = stepName || "shell step";
  const value = workspaceParseJson(raw);
  if (value === null || value === undefined || (typeof value === "string" && !value.trim())) {
    return { ok: false, kind: "none", reason: "no valid answer was received from " + step + " (no answer)", received: workspaceQuote(raw) };
  }
  if (typeof value === "string") {
    const declined = DECLINE_PROSE.test(value);
    return { ok: false, kind: declined ? "declined" : "unreadable", reason: declined ? "the agent declined " + step : "no valid answer was received from " + step + " (a prose reply, not a result)", received: workspaceQuote(raw) };
  }
  if (!workspaceIsObject(value)) {
    return { ok: false, kind: "unreadable", reason: "no valid answer was received from " + step, received: workspaceQuote(raw) };
  }
  if (value.declined === true) {
    return { ok: false, kind: "declined", reason: "the agent declined " + step + (value.reason ? " (" + String(value.reason) + ")" : ""), received: workspaceQuote(raw) };
  }
  const status = typeof value.exit_status === "number" ? value.exit_status : value.exit_code;
  if (typeof status !== "number") {
    return { ok: false, kind: "unreadable", reason: "no valid answer was received from " + step + " (the reply carries no exit status)", received: workspaceQuote(raw) };
  }
  const stdout = typeof value.stdout === "string" ? value.stdout : (typeof value.output === "string" ? value.output : "");
  return { ok: true, exit_status: status, stdout: stdout, stderr: typeof value.stderr === "string" ? value.stderr : "", reply: value };
}

// The one acceptance predicate: the maker's answer is ONE JSON object, status "ok", with a non-empty
// workspace_path. Takes the maker's answer itself or a shell executor's reply carrying it in stdout.
// Never falls back to any location: anything else is {accepted:false, reason, received}.
function workspaceAcceptAnswer(raw) {
  let answer = workspaceParseJson(raw);
  if (workspaceIsObject(answer) && (answer.declined === true || "exit_status" in answer || "exit_code" in answer || "stdout" in answer)) {
    const reply = shellStepReply(answer, "the workspace step");
    if (!reply.ok) return workspaceReject(reply.reason, raw, reply.kind);
    answer = workspaceParseJson(reply.stdout);
    if (!workspaceIsObject(answer)) return workspaceReject("no valid answer was received from the workspace maker (its output is not one JSON object)", raw, "unreadable");
    if (reply.exit_status !== 0 && answer.status === "ok") return workspaceReject("no valid answer was received: the workspace maker exited " + reply.exit_status, raw, "error");
  }
  if (answer === null || answer === undefined || (typeof answer === "string" && !answer.trim())) {
    return workspaceReject("no valid answer was received from the workspace step (no answer)", raw, "none");
  }
  if (typeof answer === "string") {
    const declined = DECLINE_PROSE.test(answer);
    return workspaceReject(declined ? "the agent declined the workspace step" : "no valid answer was received from the workspace step (not a JSON object)", raw, declined ? "declined" : "unreadable");
  }
  if (!workspaceIsObject(answer)) return workspaceReject("no valid answer was received from the workspace step", raw, "unreadable");
  if (answer.status !== "ok") {
    const why = answer.status === "refused" ? "the workspace maker refused" : (answer.status === "error" ? "the workspace maker reported an error" : "no valid answer was received (status is neither ok nor refused)");
    return workspaceReject(why, raw, answer.status === "refused" ? "refused" : (answer.status === "error" ? "error" : "invalid"));
  }
  if (typeof answer.workspace_path !== "string" || !answer.workspace_path.trim()) {
    return workspaceReject("no valid answer was received (status ok but no workspace_path)", raw, "invalid");
  }
  return { accepted: true, answer: answer, workspace_path: answer.workspace_path.trim() };
}

// Every shell step goes to the one narrow shell executor: it runs the exact command once, unchanged, and
// relays stdout verbatim. The caller reads the raw reply with shellStepReply and stops on a bad one.
async function shellStepDispatch(command, stepLabel, phaseName) {
  const prompt =
    "Run exactly this one command, once, unchanged, and relay its stdout verbatim. " +
    "Do not run any other command, do not fix or retry anything, do not add words.\n\n" +
    command + "\n\n" +
    "Reply with { \"command\": \"<the command>\", \"exit_status\": <number>, \"stdout\": \"<stdout verbatim>\", \"stderr\": \"<stderr verbatim>\" }. " +
    "If you cannot run it as given, reply { \"declined\": true, \"agent\": \"shell-runner\", \"reason\": \"<why>\" } and do nothing else.";
  return await agent(prompt, { agentType: SHELL_RUNNER_AGENT, schema: SHELL_REPLY_SCHEMA, label: stepLabel, phase: phaseName });
}

// ACD-2100a-1 / BO-4300a-1-ia (M13): every maker command runs as ONE command with the maker script's ABSOLUTE path,
// resolved here the repo-anchored way, and every interpolated path or slug double-quoted. The repository is found
// as the parent of git-common-dir run here, else a child folder holding .git, one plain shell-runner command per
// probe. Sibling folders are not probed: that glob would also match a working folder holding an empty .git (the
// dev layout's untracked parent), i.e. the very copy this must never run. A decline or prose reply, no
// repository found, or several child repositories (the maker's AMBIGUOUS_REPO; never a pick) is returned for the
// caller to halt on, quoting what was received or the candidates.
const MAKER_PROBES = ["git rev-parse --path-format=absolute --git-common-dir", "realpath -- */.git"];
// The script sits under the consumer's output root (each consumer passes its own rendered one), joined to the
// resolved ABSOLUTE project root. Handed-in workspace: the project is the one its marker names
// (<workspace>/<output root>/workspace.json, field project_root), read by ONE probe step -- never the workspace's own
// clone (a branch that edits the maker would verify itself) and never the cwd. A missing or unreadable marker, or
// one without project_root, is returned for the caller to halt on, quoting the reply.
const MAKER_MARKER_LABEL = "read-workspace-marker";
let makerPathFound = null;
function workspaceAnchor() {
  if (args && args.workspace !== undefined && args.workspace !== null) {
    const given = workspaceAcceptAnswer(args.workspace);
    return given.accepted ? given.workspace_path : "";
  }
  return workspaceHandedIn();
}
function makerLocation(root, outputRoot) {
  return { ok: true, root: root, path: (/^(\/|[A-Za-z]:)/.test(outputRoot) ? outputRoot : root + "/" + outputRoot) + "/scripts/worktree.py" };
}
// The marker stores project_root relative to the workspace ("./" or "../" prefix, as the maker's from_portable reads it);
// resolve it against the workspace's absolute path. Any other value (already absolute, or not a path) is returned as is.
function makerPortableToAbsolute(stored, base) {
  if (!/^\.{1,2}[\\/]/.test(stored)) return stored;
  const b = String(base).replace(/\\/g, "/");
  const drive = /^[A-Za-z]:/.test(b) ? b.slice(0, 2) : "";
  const parts = b.slice(drive.length).split("/").filter(Boolean);
  for (const seg of stored.replace(/\\/g, "/").split("/")) {
    if (seg === "..") parts.pop();
    else if (seg && seg !== ".") parts.push(seg);
  }
  return drive + "/" + parts.join("/");
}
async function resolveMakerFromMarker(anchor, outputRoot, phaseName) {
  const marker = (/^(\/|[A-Za-z]:)/.test(outputRoot) ? outputRoot : anchor.replace(/[\\/]+$/, "") + "/" + outputRoot) + "/workspace.json";
  const reply = shellStepReply(await shellStepDispatch("cat " + makerQuote(marker), MAKER_MARKER_LABEL, phaseName), MAKER_MARKER_LABEL);
  if (!reply.ok) return reply;
  const body = reply.exit_status === 0 ? workspaceParseJson(reply.stdout) : null;
  const stored = workspaceIsObject(body) && typeof body.project_root === "string" ? body.project_root.trim() : "";
  const named = makerPortableToAbsolute(stored, anchor).replace(/[\\/]+$/, "");
  if (!named || !/^(\/|[A-Za-z]:)/.test(named)) return { ok: false, reason: "the workspace marker could not be read or names no project_root, so the workspace maker's location is unknown (no fallback to the workspace's own copy)", received: workspaceQuote(reply.reply) };
  return makerLocation(named, outputRoot);
}
async function resolveRepoAnchoredMakerPath(phaseName, outputRoot) {
  if (makerPathFound) return makerPathFound;
  const replies = [];
  const anchor = workspaceAnchor();
  const root0 = typeof outputRoot === "string" ? outputRoot : "";
  if (!root0) return { ok: false, reason: "no output root was given to locate the workspace maker script", received: workspaceQuote(outputRoot) };
  if (anchor) {
    const fromMarker = await resolveMakerFromMarker(anchor, root0, phaseName);
    if (fromMarker.ok) makerPathFound = fromMarker;
    return fromMarker;
  }
  for (const probe of MAKER_PROBES) {
    const reply = shellStepReply(await shellStepDispatch(probe, "resolve-maker-path", phaseName), "resolve-maker-path");
    if (!reply.ok) return reply;
    const gitDirs = [...new Set(reply.stdout.split(/\r?\n/).map((s) => s.trim()).filter((s) => /^(\/|[A-Za-z]:).*[\\/]\.git$/.test(s)))];
    if (gitDirs.length > 1) return { ok: false, reason: "more than one child repository was found, so which one the workspace maker belongs to is ambiguous (AMBIGUOUS_REPO)", received: workspaceQuote(gitDirs) };
    if (gitDirs.length) {
      makerPathFound = makerLocation(gitDirs[0].replace(/[\\/]\.git$/, ""), root0);
      return makerPathFound;
    }
    replies.push(reply.reply);
  }
  return { ok: false, reason: "the workspace maker's in-repository location could not be resolved (no repository here or in a child folder)", received: workspaceQuote(replies) };
}

// A value as one double-quoted shell word (the characters a double-quoted word still expands are escaped).
function makerQuote(value) {
  return '"' + String(value).replace(/(["\\$`])/g, "\\$1") + '"';
}

// One exact maker command: python3 "<absolute script>" <verb> [--kind k] [--slug "s"] [--ticket "t"] [--path "p"] [--force].
function makerCommand(makerPath, verb, flags) {
  const f = flags || {};
  return "python3 " + makerQuote(makerPath) + " " + verb +
    (f.kind ? " --kind " + f.kind : "") + (f.slug ? " --slug " + makerQuote(f.slug) : "") +
    (f.ticket ? " --ticket " + makerQuote(f.ticket) : "") + (f.path ? " --path " + makerQuote(f.path) : "") +
    (f.force ? " --force" : "");
}

// The maker path of a run, or {ok:true, path:""} when the answer is handed in (args.workspace: no command is sent).
async function workspaceMakerPath(phaseName, outputRoot) {
  if (args && args.workspace !== undefined && args.workspace !== null) return { ok: true, path: "", root: "" };
  return await resolveRepoAnchoredMakerPath(phaseName, outputRoot);
}

// A maker location that could not be resolved, as a rejected acceptance result (callers stop on `!accepted`).
function workspaceUnresolved(maker) {
  return workspaceReject(maker.reason, maker.received, maker.kind || "invalid");
}

// Obtain the workspace with ONE absolute, quoted ensure command (see workspaceObtain); an unresolved maker location is a rejection.
async function workspaceEnsure(phaseName, flags, confirmed) {
  const maker = await workspaceMakerPath(phaseName, flags.outputRoot);
  return maker.ok ? await workspaceObtain(makerCommand(maker.path, "ensure", flags), phaseName, confirmed) : workspaceUnresolved(maker);
}

// A handed-in location confirmed with the maker by its absolute path (see workspaceConfirmHandedIn).
async function workspaceConfirmHandedInAt(location, phaseName, outputRoot) {
  const maker = await resolveRepoAnchoredMakerPath(phaseName, outputRoot);
  return maker.ok ? await workspaceConfirmHandedIn(location, makerCommand(maker.path, "ensure"), phaseName) : workspaceUnresolved(maker);
}

// A workspace made by a direct maker dispatch (no handed-in answer: a scratch copy), accepted or rejected like any other.
async function workspaceMade(phaseName, flags, stepLabel) {
  const maker = await resolveRepoAnchoredMakerPath(phaseName, flags.outputRoot);
  return maker.ok ? workspaceAcceptAnswer(await workspaceDispatch(makerCommand(maker.path, "ensure", flags), phaseName, stepLabel)) : workspaceUnresolved(maker);
}

// The maker's `remove` command for a workspace; throws when the maker's location is unknown (the caller logs it).
async function workspaceRemoveCommand(path) {
  if (!makerPathFound) throw new Error("the workspace maker's location was never resolved in this run");
  return makerCommand(makerPathFound.path, "remove", { path: path, force: true });
}

// The ONLY way a workflow asks for a workspace: one shell-executor dispatch of the maker command.
// Returns the raw reply; the caller hands it to workspaceAcceptAnswer and stops on anything but an
// accepted answer.
async function workspaceDispatch(command, phaseName, stepLabel) {
  return await shellStepDispatch(command, stepLabel || WORKSPACE_STEP_LABEL, phaseName || "Workspace");
}

// BO-4300c-4-i: a location handed in by whoever started the run (args.worktree_path / args.workspace_path).
const WORKSPACE_VERIFY_LABEL = "workspace-verify";
function workspaceHandedIn() {
  const given = args ? (args.worktree_path || args.workspace_path) : undefined;
  return typeof given === "string" && given.trim() ? given.trim() : "";
}

// Both spellings of one location are the same location: separators, repeated and trailing slashes, and the
// case of a drive-lettered path do not tell two locations apart.
function workspaceSamePath(a, b) {
  const form = function (p) {
    const t = String(p).replace(/[\\]+/g, "/").replace(/\/{2,}/g, "/").replace(/\/+$/, "");
    return /^[a-z]:/i.test(t) ? t.toLowerCase() : t;
  };
  return form(a) === form(b);
}

// The verify request for a handed-in location, derived from the run's own ensure command (same script).
// null when the ensure command names no maker script: there is no bare-name fallback to guess at.
function workspaceVerifyCommand(ensureCommand, location) {
  const m = /^(.*?worktree\.py(?:"|')?)\s+ensure\b/.exec(String(ensureCommand));
  return m ? m[1] + " verify --path " + makerQuote(location) : null;
}

// Confirm the handed-in location with the maker (ONE verbatim verify request) before any step runs. Only an
// ok answer whose workspace_path is that same location lets the run go on; the failure names the location.
// A non-ok verify answer (refused / VERIFY_FAILED / error / prose) ends the run, quoting the answer.
async function workspaceConfirmHandedIn(location, ensureCommand, phaseName) {
  const verifyCommand = workspaceVerifyCommand(ensureCommand, location);
  if (!verifyCommand) return workspaceReject("the location given (" + location + ") cannot be confirmed: no workspace maker script is named", ensureCommand, "invalid");
  const raw = await shellStepDispatch(verifyCommand, WORKSPACE_VERIFY_LABEL, phaseName || "Workspace");
  const result = workspaceAcceptAnswer(raw);
  const given = "the location given (" + location + ")";
  if (!result.accepted) return workspaceReject(given + " is not a ready workspace: " + result.reason, raw, result.kind);
  if (!workspaceSamePath(result.workspace_path, location)) {
    return workspaceReject(given + " was not confirmed: the maker answered for a different location (" + result.workspace_path + ")", raw, "invalid");
  }
  return result;
}

// Obtain the workspace: take the answer handed in as args.workspace, confirm a handed-in location with the
// maker, or issue the one ensure dispatch. Returns the acceptance result; there is no other source of a location.
// A run that must confirm the location before its own first step passes the confirmation it already got.
async function workspaceObtain(command, phaseName, confirmed) {
  if (args && args.workspace !== undefined && args.workspace !== null) return workspaceAcceptAnswer(args.workspace);
  if (confirmed) return confirmed;
  const handedIn = workspaceHandedIn();
  if (handedIn) return await workspaceConfirmHandedIn(handedIn, command, phaseName);
  return workspaceAcceptAnswer(await workspaceDispatch(command, phaseName));
}

// The branch an accepted answer names: the top-level `branch` first, else the marker's (an older verify answer
// carries it only there); "" when it names none.
function workspaceBranch(answer) {
  const named = answer.branch || (answer.marker && answer.marker.branch);
  return typeof named === "string" ? named.trim() : "";
}

// finalize's record of clearing a scratch copy: the maker's `remove` answer, or why none was usable.
function workspaceRemovalRecord(path, removal, failure) {
  const answer = removal && removal.ok ? workspaceParseJson(removal.stdout) : null;
  const said = workspaceIsObject(answer) ? answer : {};
  return {
    path: path,
    status: removal && removal.ok ? (said.status || "unknown") : "not_removed",
    removed_path: typeof said.removed_path === "string" ? said.removed_path : null,
    detail: removal && removal.ok ? (said.message || "") : (failure || removal.reason + " -- " + removal.received),
  };
}

function workspaceFailure(result) {
  return { status: "error", message: "Workspace step failed: " + result.reason + ". Received: " + result.received + ". Nothing was dispatched after it and no other location was used." };
}
