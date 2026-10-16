// SINGLE TRACKED SOURCE of the WORKSPACE-ANSWER block (BO-4300c-3).
// Never edited inside a workflow. Each consuming template carries only an empty
// start/end marker pair (the two WORKSPACE-ANSWER comment lines; this file must
// never spell either marker out, or the deployed block would carry a second
// pair); the workflow build phase (scripts/build_phases_workflows.py) fills that
// pair with this whole file, and refuses a pair that already holds text. Workflow bodies run in
// the E2 engine with no require (ADR-030), so this is inlined at build time only.
// Do not use config-token placeholders here: the deployed text must stay
// byte-identical to this file in every workflow. Callers pass the script path in.
//
// Rule: ONE acceptance predicate. An answer is accepted only when it is a single
// JSON object whose status is "ok" and whose workspace_path is a non-empty
// string. Anything else stops the run, quoting (at most 2 KB of) what arrived.
// No function here falls back to any location when an answer is not accepted.
const WORKSPACE_ANSWER_MAX_RECEIVED = 2048;
const WORKSPACE_ANSWER_SCHEMA = {
  type: "object",
  properties: {
    status: { type: "string" },
    workspace_path: { type: "string" },
    worktree_path: { type: "string" },
    branch: { type: "string" },
    code: { type: "string" },
    message: { type: "string" },
  },
  additionalProperties: true,
};

function workspaceReceivedText(raw) {
  let text;
  if (typeof raw === "string") {
    text = raw;
  } else {
    try {
      text = JSON.stringify(raw);
    } catch (_e) {
      text = String(raw);
    }
    if (text === undefined) text = String(raw);
  }
  return text.length > WORKSPACE_ANSWER_MAX_RECEIVED ? text.slice(0, WORKSPACE_ANSWER_MAX_RECEIVED) : text;
}

// Acceptance predicate. Takes the raw answer (object or string); returns
// {accepted: true, answer, workspace_path} or {accepted: false, reason, received}.
function acceptWorkspaceAnswer(raw) {
  const received = workspaceReceivedText(raw);
  if (raw === undefined || raw === null || (typeof raw === "string" && raw.trim() === "")) {
    return { accepted: false, reason: "No answer: the workspace maker returned nothing.", received };
  }
  let answer = raw;
  if (typeof raw === "string") {
    try {
      answer = JSON.parse(raw.trim());
    } catch (_e) {
      return { accepted: false, reason: "The answer is not a single JSON object.", received };
    }
  }
  if (answer === null || typeof answer !== "object" || Array.isArray(answer)) {
    return { accepted: false, reason: "The answer is not a single JSON object.", received };
  }
  if (answer.status !== "ok") {
    return { accepted: false, reason: "The answer status is " + JSON.stringify(answer.status === undefined ? null : answer.status) + ', not "ok".', received };
  }
  if (typeof answer.workspace_path !== "string" || answer.workspace_path.trim() === "") {
    return { accepted: false, reason: "The answer names no workspace_path.", received };
  }
  return { accepted: true, answer, workspace_path: answer.workspace_path };
}

// Dispatch helper. Exactly ONE agent() dispatch, to an agent whose registry entry
// permits shell commands, carrying the maker's answer schema. Returns the raw reply.
async function requestWorkspace(command, opts) {
  const o = opts || {};
  return await agent(
    "Run exactly this one command, unchanged, from any directory. Run nothing else.\n" +
      command +
      "\nReply with the command's standard output, word for word, as the answer object. Never edit, summarise or add to it. If the command fails, reply with what it printed.",
    {
      agentType: "worktree-agent",
      schema: WORKSPACE_ANSWER_SCHEMA,
      label: o.label || "workspace-ensure",
      phase: o.phase || "Workspace",
    }
  );
}

// The run's single stop payload for a rejected answer. It quotes what was received
// (once, bounded) and names no location to carry on in.
function workspaceStop(decision) {
  return {
    status: "error",
    abort_reason: "workspace-not-ready",
    workspace_ready: false,
    message:
      "Stopped before any work: " + decision.reason + " Received: " + decision.received +
      " No authoring, phase, commit or delivery step was started, and no other location is used.",
  };
}

function workspaceSlugFrom(text) {
  const parts = String(text || "").replace(/\\/g, "/").replace(/\/+$/, "").split("/");
  const last = (parts.pop() || "").replace(/\.md$/i, "");
  return last.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
}

// Which workspace a work-store path belongs to: a path inside an EPIC-* folder
// shares that epic's one workspace; any other ticket has a workspace named by its file.
function workspaceKindAndSlug(path) {
  const parts = String(path || "").replace(/\\/g, "/").split("/");
  const epic = parts.find((p) => /^EPIC-/.test(p));
  if (epic) return { kind: "epic", slug: workspaceSlugFrom(epic) };
  return { kind: "ticket", slug: workspaceSlugFrom(path) };
}

// The project root the maker is asked about: given outright, or read off an
// absolute work-store path that sits under <root>/tickets/. Null when neither.
function workspaceProjectRoot(args) {
  const a = args || {};
  for (const key of ["project_root", "repo_root"]) {
    if (typeof a[key] === "string" && a[key].trim()) return a[key].trim().replace(/[\\/]+$/, "");
  }
  for (const key of ["ticket_path", "epic_path", "target"]) {
    const v = a[key];
    if (typeof v !== "string") continue;
    const norm = v.replace(/\\/g, "/");
    const at = norm.indexOf("/tickets/");
    if (at > 0 && (norm.startsWith("/") || /^[A-Za-z]:\//.test(norm))) return v.slice(0, at);
  }
  return null;
}

// The one way a workflow obtains its workspace: the maker's answer handed in as
// args.workspace, or one maker dispatch. spec: {scriptRel, kind, slug, label, phase}.
async function obtainWorkspace(args, spec) {
  if (args && Object.prototype.hasOwnProperty.call(args, "workspace")) {
    return acceptWorkspaceAnswer(args.workspace);
  }
  const root = workspaceProjectRoot(args);
  if (!root || !spec.slug) {
    return {
      accepted: false,
      reason: "No answer: the workspace maker was not asked, because neither args.workspace nor a project root and a name for the work were given.",
      received: "(nothing)",
    };
  }
  const command =
    "python3 " + root + "/" + spec.scriptRel + " ensure --kind " + spec.kind + " --slug " + spec.slug + " --repo-root " + root;
  return acceptWorkspaceAnswer(await requestWorkspace(command, spec));
}
