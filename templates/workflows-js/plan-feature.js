/**
 * plan-feature.js — Claude Code Workflow script
 *
 * Implements the /plan-feature command: triages the user's request via the
 * ac-triage agent (Haiku-tier, fast), routes to the correct AC authoring
 * agents (product-owner, business-analyst, it-po, test-designer) in sequence
 * with user confirmation gates after the PO and BA stages (the IT PO stage is
 * auto-gated by a rule check), and writes all output exclusively
 * to the AC store (docs/acceptance-criteria/). No ticket files are produced.
 *
 * Routing table (matches ac-triage classification; every route ends with the
 * IT PO stage, then test design, then the final gate):
 *   strategic  → PO → gate → BA → gate → IT PO (auto) → test design → final gate
 *   behavioral → BA → gate → IT PO (auto) → test design → final gate
 *   technical  → IT PO (auto) → test design → final gate
 *   (a product-truth flow produced for a technical request adds the BA stage)
 *   covered    → show matching ACs → prompt cancel / amend / force
 *
 * Architecture:
 *   Stage 0: ac-triage agent (Haiku-pinned, reads AC store, classifies route)
 *   Stage 1–N: authoring agents dispatched in sequence per route
 *   Gates: user confirm/edit/cancel after PO and BA; IT PO passes on its rule check
 *   Test design: design pre-pass (design_prepass.py), then the test-designer
 *     agent; its output is committed as plan-feature(TEST-DESIGN-HANDBACK)
 *   Hand-back: up to 2 rounds returning undecided file findings to it-po; each
 *     round runs runRuleCheck("itpo-handback") and fails closed
 *   Final gate: user sets priority; approveBatch runs approve_acs.py --ids
 *     (approval-holds, then approval-apply): it approves the records that
 *     pass and reports the held ones and the failed ones
 *
 * E2 canonical form: top-level body, agent(prompt, opts), args global.
 * No export async function run() — E2 executes the top-level body directly.
 *
 * Source ticket: EPIC-ACDrivenDevelopment/08_create_ac_workflow.md
 * ACs: ACD-300, ACD-300a, ACD-300a-1..3, ACD-300b..d, TKT-100g
 * Renamed from create-ac.js per AC ACD-1100c-1 (v2.0 migration).
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 */

export const meta = {
  name: "plan-feature",
  description:
    "Triage, orchestrate, and gate AC authoring for a new feature request. Dispatches ac-triage (Haiku) to classify the request as strategic / behavioral / technical / covered, then routes through the correct authoring agents (PO v3, BA v3, IT PO v3) with user gates between stages. All output goes exclusively to the AC store — no ticket files are produced.",
  phases: [
    "stage-0: ac-triage (Haiku) — duplicate check + route classification",
    "stage-1: authoring agents per route (PO v3 / BA v3 / IT PO v3)",
    "gates: user confirm/edit/cancel between each stage",
    "final-gate: priority setting + readiness: approved",
  ],
};

/** Maximum retry count for a single authoring agent on edit-path. */
const MAX_EDIT_RETRIES = 1;

// BO-3900-PATH-HELPERS-START
/**
 * Cross-platform path handling (BO-3900). Every rule below is decided from
 * the path STRING's own form only — never from process.platform or any
 * other host signal (BO-3900a). This block is a deliberate, self-contained
 * COPY of the same rules in build-feature.js and build-epic.js: the E2
 * engine injects no module loader (ADR-030; KI-BO-028), so a workflow
 * script cannot require/import Node's `path`, `os`, or `fs` modules, or
 * reach for a shared helper file outside itself.
 */

/**
 * Classify a path STRING's form: "absolute", "relative", or "unrecognised".
 * See build-feature.js's own copy of this function for the full contract.
 *
 * @param {*} input
 * @returns {"absolute"|"relative"|"unrecognised"}
 */
function classifyPathForm(input) {
  if (typeof input !== "string" || input.trim() === "") return "unrecognised";
  if ((input.match(/[A-Za-z]:[\\/]/g) || []).length >= 2) return "unrecognised";
  if (/^(\\\\[^\\/]|[A-Za-z]:[\\/]|\/)/.test(input)) return "absolute";
  if (/^([A-Za-z]:|\\(?!\\))/.test(input)) return "unrecognised";
  return "relative";
}

/**
 * Normalise separator spelling to "/" and apply "." and ".." segments,
 * anchored on the path's own root so a ".." can never climb above it.
 *
 * @param {string} input
 * @returns {string}
 */
function normalizePathForm(input) {
  const slashed = String(input).replace(/\\/g, "/");
  const rootMatch = /^([A-Za-z]:\/|\/\/[^/]+\/[^/]+(\/|$)|\/)/.exec(slashed);
  const root = rootMatch ? rootMatch[0].replace(/\/?$/, "/") : "";
  const stack = [];
  for (const seg of slashed.slice(root.length).split("/")) {
    if (seg === "" || seg === ".") continue;
    if (seg !== "..") stack.push(seg);
    else if (stack.length > 0) stack.pop();
    else if (root === "") stack.push("..");
  }
  return root + stack.join("/");
}

/**
 * Resolve `input` onto `root`. An absolute input is normalised and returned
 * unchanged in content — never joined onto anything. A relative input is
 * joined onto the normalised root exactly once. An unrecognised input is
 * refused: its exact value comes back verbatim, still unjoined.
 *
 * @param {string} root
 * @param {*} input
 * @returns {{ok: true, form: string, path: string}|{ok: false, form: "unrecognised", value: *}}
 */
function resolvePathOntoRoot(root, input) {
  const form = classifyPathForm(input);
  if (form === "unrecognised") return { ok: false, form, value: input };
  const path = normalizePathForm(input);
  if (form === "absolute") return { ok: true, form, path };
  return { ok: true, form, path: normalizePathForm(root).replace(/\/$/, "") + "/" + path };
}
// BO-3900-PATH-HELPERS-END

// Prose-tolerant reply reader (BP-300e)

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
    let depth = 0, inString = false, j = i;
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
            try { return JSON.parse(raw.slice(i, j + 1)); } catch (_) { i = j; break; }
          }
        }
      }
      j++;
    }
    if (depth > 0) { break; }
  }
  throw new Error(
    "[" + stage + "] " + agent +
    " returned a reply with no parseable JSON — " +
    "all reply-reading sites must route through parseAgentJson"
  );
}

/**
 * Priority values accepted at the final gate.
 * Must match the ac_store_schema.json enum.
 *
 * @type {string[]}
 */
const VALID_PRIORITIES = ["critical", "high", "medium", "low"];

/**
 * Extract the pull request number from a GitHub PR URL.
 *
 * GitHub PR URLs follow the pattern:
 *   https://github.com/<owner>/<repo>/pull/<number>
 *
 * Returns the number as a string (e.g. "42"), or null when the URL is absent,
 * malformed, or does not contain a numeric pull-request segment.
 *
 * This is a pure function with no I/O — no try/except is warranted per the
 * project Error Handling Policy (Rule 4).
 *
 * @param {string|null} prUrl - The PR URL returned by `gh pr create`.
 * @returns {string|null} The PR number string, or null if not extractable.
 */
function extractPrNumber(prUrl) {
  if (!prUrl || typeof prUrl !== "string") {
    return null;
  }
  const trimmed = prUrl.trim().replace(/\/$/, "");
  const lastSegment = trimmed.split("/").pop();
  return /^\d+$/.test(lastSegment) ? lastSegment : null;
}

/**
 * Parse $ARGUMENTS into workflow inputs.
 *
 * Expected format (all optional):
 *   <request text> [--component <name>] [--force]
 *
 * @param {string} raw - Raw $ARGUMENTS string.
 * @returns {{ request: string, component: string|null, force: boolean }}
 */
function parseArgs(raw) {
  const parts = raw.trim().split(/\s+/);
  const force = parts.includes("--force");
  const compIdx = parts.indexOf("--component");
  const component = compIdx !== -1 && compIdx + 1 < parts.length
    ? parts[compIdx + 1]
    : null;

  // Everything before --component or --force is the request text.
  const flagPositions = new Set();
  if (compIdx !== -1) {
    flagPositions.add(compIdx);
    flagPositions.add(compIdx + 1);
  }
  if (force) {
    const forceIdx = parts.indexOf("--force");
    flagPositions.add(forceIdx);
  }
  const requestParts = parts.filter((_, i) => !flagPositions.has(i));
  const request = requestParts.join(" ").trim();

  return { request, component, force };
}

/**
 * Map an internal pipeline stage key to a display-name used in commit messages.
 *
 * Canonical display names per AC ACD-300g-3:
 *   po       → PO
 *   ba       → BA
 *   itpo     → IT-PO
 *   mockdata → MOCK-DATA   (product-truth phase)
 *   mockup   → MOCKUP      (product-truth phase)
 *   flow     → FLOW        (product-truth phase)
 *   (any other key is returned uppercase as a fallback)
 *
 * @param {string} stageKey - Internal stage key (e.g. "po", "ba", "mockdata").
 * @returns {string} Display name (e.g. "PO", "BA", "MOCK-DATA").
 */
function stageDisplayName(stageKey) {
  const map = {
    po: "PO",
    ba: "BA",
    itpo: "IT-PO",
    mockdata: "MOCK-DATA",
    mockup: "MOCKUP",
    flow: "FLOW",
  };
  return map[stageKey] || stageKey.toUpperCase();
}

/**
 * Commit AC YAML files produced by a completed pipeline stage.
 *
 * Stages ONLY the files that correspond to AC IDs in the `written` array,
 * using `git add <explicit-path>` for each file individually.
 *
 * NO-MAIN-COMMIT DEFENSIVE GUARD (fail-CLOSED):
 * Before staging or committing anything, verifies that the authoring worktree is
 * NOT on the main branch. Fail-CLOSED: when authoringWorktreePath is set, the
 * branch MUST be positively confirmed as a non-main authoring branch before any
 * commit proceeds. ALL failure paths return a structured error and abort the
 * commit — we cannot risk committing to an unknown branch.
 *
 * @param {string[]} written      - Array of AC IDs written by the stage.
 * @param {string}   stageName    - Internal stage key (e.g. "po", "ba", "itpo").
 * @param {string}   component    - Target component name.
 * @param {boolean}  isFinal      - True when this is the final commit of the pipeline run.
 * @param {string}   runId        - Short run identifier.
 * @param {string}        acStorePath           - Absolute path to the AC store directory.
 * @param {string|null}   authoringWorktreePath  - Absolute path to the dedicated authoring worktree.
 * @param {string[]}      [extraPaths]           - Repo-relative record paths to stage too (the rule check's records_to_commit: repaired parents).
 * @returns {Promise<{ status: "ok"|"error", message: string, hook_name?: string|null, failing_files?: string[], is_conflict?: boolean }>}
 */
async function commitStageOutput(written, stageName, component, isFinal, runId, acStorePath, authoringWorktreePath, extraPaths) {
  acStorePath = acStorePath || "docs/acceptance-criteria";
  const stageLabel = stageDisplayName(stageName);

  // Why the no-main-commit guard: docs/reference/plan-feature-workflow-rationale-helpers.md
  {
    let branchConfirmed = false;
    let branchCheckError = "unknown error during branch check";

    const branchCheckCmd = authoringWorktreePath ? `git -C ${makerQuote(authoringWorktreePath)} branch --show-current` : null;

    try {
      if (!branchCheckCmd) throw new Error("no authoring workspace path to anchor the branch check");
      const branchCheckResult = await agent(
        `Run the following command and return its raw stdout output:\n` +
        `${branchCheckCmd}\n` +
        `Return JSON: { "output": "<raw stdout line>", "exit_code": <number> }`,
        { agentType: "status-checker", label: "branch-check" }
      );
      let branchParsed;
      try {
        branchParsed = parseAgentJson(branchCheckResult, { stage: "branch-check", agent: "status-checker" });
      } catch (_parseErr) {
        branchCheckError = "branch check response was not valid JSON";
        branchParsed = null;
      }

      if (branchParsed && branchParsed.exit_code === 0) {
        const currentBranch = (branchParsed.output || "").trim();
        if (currentBranch.toLowerCase() === "main") {
          return {
            status: "error",
            message:
              "safety: refusing to commit AC files to main — authoring branch invariant violated (AC BO-1500c-3)",
            hook_name: null,
            failing_files: [],
            is_conflict: false,
          };
        }
        if (currentBranch.length > 0) {
          // Positively confirmed: non-empty, non-main branch name.
          branchConfirmed = true;
        } else {
          branchCheckError = "git branch --show-current returned an empty branch name";
        }
      } else if (branchParsed) {
        branchCheckError =
          "git branch --show-current exited non-zero (exit_code=" +
          branchParsed.exit_code + ")";
      } else {
        branchCheckError = "branch check returned null or unparseable result";
      }
    } catch (branchCheckErr) {
      branchCheckError = "agent dispatch failed: " + branchCheckErr.message;
    }

    if (!branchConfirmed) {
      // Cannot positively confirm the branch — fail-closed: abort the commit.
      return {
        status: "error",
        message:
          "safety: cannot confirm authoring branch is not main — commit aborted to prevent " +
          "committing to an unknown branch (AC BO-1500c-3). Cause: " + branchCheckError,
        hook_name: null,
        failing_files: [],
        is_conflict: false,
      };
    }
  }
  // ---------------------------------------------------------------------------

  const displayStage = isFinal ? `${stageLabel}, final` : stageLabel;
  const componentLabel = component || "unknown-component";
  const acIdList = written.length > 0 ? written.join(", ") : "(none)";
  const commitKind = isFinal ? "final commit of run" : "mid-pipeline commit";
  const commitMessage =
    `plan-feature(${displayStage}): ${componentLabel}\n\nAC IDs: ${acIdList}\nrun-id: ${runId}\n${commitKind}`;

  // BO-4500a-5-ii: the exact paths (the rule check's records_to_commit, repaired parents included) go to the
  // shared commit step. records_to_commit is untrusted: keep only .yaml paths under the store, never `..`;
  // a path the scan reported absolute is made relative to the worktree first.
  const _wt = (authoringWorktreePath || "").split("\\").join("/"), _st = acStorePath.split("\\").join("/");
  const _storeRel = (_wt && _st.startsWith(_wt + "/")) ? _st.slice(_wt.length + 1) : _st;
  // With no rule-check list, name the flat <store>/<id>.yaml of each written id (legacy); a record that is
  // not there makes the step refuse loudly rather than skip silently.
  const keepPaths = (extraPaths && extraPaths.length ? extraPaths : written.map((id) => `${_storeRel}/${id}.yaml`))
    .map((p) => (typeof p === "string" && _wt && p.split("\\").join("/").startsWith(_wt + "/")) ? p.split("\\").join("/").slice(_wt.length + 1) : p)
    .filter((p) => typeof p === "string" && p.endsWith(".yaml") && p.startsWith(_storeRel + "/") && !p.split("/").includes(".."));
  if (keepPaths.length === 0) {
    return { status: "ok", message: "no new AC files to commit — skipped" };
  }

  let commitResult;
  try {
    commitResult = await agent(
      `Commit the AC records produced by the ${stageName} stage through the shared commit step, once, in supervised mode. Use no other way of committing.\n` +
      "1. Write the message between the BEGIN-MESSAGE and END-MESSAGE lines (the markers excluded) to a new temporary message file.\n" +
      "BEGIN-MESSAGE\n" + commitMessage + "\nEND-MESSAGE\n" +
      `2. With the working directory set to ${makerQuote(authoringWorktreePath || ".")}, run: python3 {{config.output_root}}/scripts/commit_changes.py --message-file <that file> --supervised --run ${runId} ${keepPaths.join(" ")}\n` +
      "3. Return { \"status\": \"<the answer's status>\", \"commit_answer\": <the step's JSON answer exactly as printed> }",
      { agentType: "commit", label: "commit-stage-output" }
    );
  } catch (err) {
    return {
      status: "error",
      message: `commitStageOutput: agent dispatch failed: ${err.message}`,
      hook_name: null,
      failing_files: [],
      is_conflict: false,
    };
  }

  // Only a committed answer is a commit; anything else (or an unreadable reply) fails closed.
  let answer = null;
  try {
    answer = (parseAgentJson(commitResult, { stage: "commit-stage-output", agent: "commit" }) || {}).commit_answer || null;
  } catch (_parseErr) {
    answer = null;
  }
  if (answer && answer.status === "committed") return { status: "ok", message: "committed successfully" };
  return {
    status: "error",
    message: answer
      ? `the commit step answered status ${answer.status}, reason_code ${answer.reason_code}: ${answer.reason}`
      : "commit answer unreadable — cannot confirm success",
    hook_name: (answer && answer.hook_name) || null,
    failing_files: (answer && Array.isArray(answer.failing_files)) ? answer.failing_files : [],
    // A refused answer that reports a conflict is an index conflict, never a hook rejection (never retried or forced).
    is_conflict: !!(answer && answer.status === "refused" && /conflict/i.test(String(answer.reason || ""))),
  };
}

/**
 * Format a structured commit failure from commitStageOutput() into an
 * actionable user-facing error message.
 *
 * @param {string}      agentLabel   - Human-readable label for the stage agent.
 * @param {string}      stageName    - Stage label used in the commit message.
 * @param {{
 *   message: string,
 *   hook_name?: string|null,
 *   failing_files?: string[],
 *   is_conflict?: boolean
 * }} commitOutcome  - The error result returned by commitStageOutput().
 * @param {string[]}    allAcsWritten - All AC IDs written so far in the pipeline run.
 * @returns {string}   Actionable error message for the user.
 */
function formatCommitError(agentLabel, stageName, commitOutcome, allAcsWritten) {
  const failingFiles = Array.isArray(commitOutcome.failing_files) ? commitOutcome.failing_files : [];
  const fileList = failingFiles.length > 0
    ? "\n  Conflicting/failing files:\n" + failingFiles.map(f => `    - ${f}`).join("\n")
    : "";

  if (commitOutcome.is_conflict) {
    return (
      `Commit of ${agentLabel} AC output failed due to an index conflict.` +
      fileList + "\n" +
      "The conflict was caused by concurrent modifications to the same files. " +
      "Resolve the conflict manually (do NOT force-overwrite) then re-run /plan-feature. " +
      "All AC files from this stage remain on disk as uncommitted changes."
    );
  }

  const hookLabel = commitOutcome.hook_name
    ? `Hook "${commitOutcome.hook_name}"`
    : "A pre-commit hook";

  return (
    `Commit of ${agentLabel} AC output failed. ` +
    `${hookLabel} rejected the staged files.` +
    (commitOutcome.message && !/rejected (the )?staged files/i.test(commitOutcome.message) ? "\n  " + commitOutcome.message : "") + // the hook's own error; a message that only repeats the rejection adds nothing
    fileList + "\n" +
    "Fix the validation errors listed above, then re-run /plan-feature. " +
    "All AC files from this stage remain on disk as uncommitted changes so you can inspect and correct them."
  );
}

/**
 * Build a human-readable cancel/abort exit message that distinguishes between
 * ACs already committed in prior stages and the current stage's uncommitted drafts.
 *
 * @param {string[]} committedAcs          - AC IDs that have already been committed to git.
 * @param {string[]} draftAcs             - AC IDs written by the cancelled stage; still uncommitted.
 * @param {string}   cancelledAt          - Human label for where the cancel occurred.
 * @param {string}   acStorePath          - Absolute path to the AC store directory.
 * @param {string|null} authoringWorktreePath - Absolute path to the dedicated authoring worktree.
 * @param {string[]} [recordPaths]        - Repo-relative record paths (the rule check's records_to_commit); a draft id is matched to the path whose filename stem equals it exactly. Without any path the flat <store>/<id>.yaml is shown (legacy).
 * @returns {string} Formatted exit message for the user.
 */
function buildCancelMessage(committedAcs, draftAcs, cancelledAt, acStorePath, authoringWorktreePath, recordPaths) {
  const store = acStorePath || "docs/acceptance-criteria";
  // Use the -C anchor in user-facing git instructions so cleanup targets the authoring worktree. (AC BO-1500a-2)
  const gitC = authoringWorktreePath ? `-C ${makerQuote(authoringWorktreePath)}` : "";
  const gitCheckoutCmd = `git ${gitC} checkout -- ${store}/`.trim();
  const draftFilePaths = draftAcs.map(
    (id) => !Array.isArray(recordPaths) || recordPaths.length === 0 ? `  ${store}/${id}.yaml` : "  " + (recordPaths.find((p) => p.split(/[\/]/).pop().replace(/\.yaml$/, "") === id) || id + " (no record path known)")
  );

  const parts = [`Pipeline cancelled at ${cancelledAt}.`];

  if (committedAcs.length > 0) {
    parts.push(
      `\nCommitted ACs from prior stages (in git history): ${committedAcs.join(", ")}`
    );
  }

  if (draftAcs.length > 0) {
    parts.push(
      `\nUncommitted draft AC files from the cancelled stage (${draftAcs.join(", ")}):`
    );
    parts.push(draftFilePaths.join("\n"));
    parts.push(
      `\nYou can inspect these files, manually commit them with \`git ${gitC} add\` + \`git ${gitC} commit\`, `.trim() +
      `or discard tracked files with \`${gitCheckoutCmd}\` and ` +
      `delete any untracked new files explicitly (e.g. \`rm ${store}/<AC_ID>.yaml\`). ` +
      "Note: `git checkout --` alone will NOT remove untracked files — both steps are required " +
      "if a prior session created new AC files that were never staged."
    );
  } else {
    parts.push("\nNo draft AC files were left on disk.");
  }

  return parts.join("\n");
}

/**
 * Scan the AC store directory for orphaned AC draft files from a prior session.
 *
 * Uses `git status --porcelain --untracked-files=all` scoped to the authoring
 * worktree's AC store to find all modified or untracked YAML files.
 *
 * @param {string}   acStoreDir              - Absolute path to the AC store directory.
 * @param {string|null} authoringWorktreePath - Absolute path to the dedicated authoring worktree.
 * @returns {Promise<Array<{filePath: string, acId: string}>>} Array of orphaned AC file paths.
 */
async function scanOrphanedAcDrafts(acStoreDir, authoringWorktreePath) {
  // Build the git status command, conditionally inserting -C.
  const gitStatusCmd = authoringWorktreePath
    ? `git -C ${makerQuote(authoringWorktreePath)} status --porcelain --untracked-files=all -- ${acStoreDir}`
    : `git status --porcelain --untracked-files=all -- ${acStoreDir}`;
  // Run git status to discover modified/untracked YAML files in the AC store.
  let statusOutput;
  try {
    const statusResult = await agent(
      `Run the following command and return ONLY the raw stdout output, with no additional text:\n` +
      `${gitStatusCmd}\n` +
      `Return a JSON object: { "output": "<raw stdout>", "exit_code": <number> }`,
      { agentType: "status-checker", label: "scan-orphans-git-status" }
    );
    let parsed;
    try {
      parsed = parseAgentJson(statusResult, { stage: "scan-orphans-git-status", agent: "status-checker" });
    } catch (_parseErr) {
      return [];
    }
    if (!parsed || parsed.exit_code !== 0) {
      // git status failed — warn and proceed without blocking.
      return [];
    }
    statusOutput = parsed.output || "";
  } catch (_err) {
    // Cannot check for orphans — proceed without blocking.
    return [];
  }
  // Parse git status --porcelain output lines.
  const orphans = [];
  const lines = statusOutput.split("\n").filter((l) => l.trim().length > 0);
  for (const line of lines) {
    if (line.length < 4) { continue; }
    const xyStatus = line.slice(0, 2);
    const filePath = line.slice(3).trim();
    // Only consider YAML files.
    if (!filePath.endsWith(".yaml") && !filePath.endsWith(".yml")) { continue; }
    // Relevant status codes: M (modified), A (added), ? (untracked).
    const indexStatus = xyStatus[0];
    const worktreeStatus = xyStatus[1];
    const isRelevant =
      indexStatus === "M" || indexStatus === "A" ||
      worktreeStatus === "M" || worktreeStatus === "A" ||
      xyStatus === "??";
    if (!isRelevant) { continue; }
    // Resolve the file path against the authoring worktree root (BO-3900).
    /*
     * filePath is a relative path git status reported; classify it from its
     * own form rather than assuming it is always relative, so a value that
     * already looks absolute is never joined onto anything, and a mixed
     * separator pairing (a Windows-backslash authoringWorktreePath with a
     * forward-slash filePath) never survives past this one join site. A
     * refused (unrecognised) filePath is used verbatim, exactly as given.
     */
    const resolved = authoringWorktreePath ? resolvePathOntoRoot(authoringWorktreePath, filePath) : null;
    const resolvedFilePath = resolved && resolved.ok ? resolved.path : filePath;
    // Read the YAML file content to qualify it as an orphan.
    let fileContent;
    try {
      const readResult = await agent(
        `Read the file at path "${resolvedFilePath}" and return its raw text content.\n` +
        `Return a JSON object: { "content": "<raw file text>" }\n` +
        `If the file cannot be read, return: { "content": null }`,
        { agentType: "status-checker", label: "scan-orphans-read-file" }
      );
      let readParsed;
      try {
        readParsed = parseAgentJson(readResult, { stage: "scan-orphans-read-file", agent: "status-checker" });
      } catch (_parseErr) {
        readParsed = null;
      }
      fileContent = readParsed ? readParsed.content : null;
    } catch (_readErr) {
      // Cannot read file — skip it.
      continue;
    }
    if (!fileContent) { continue; }
    // Extract origin_agent and readiness fields from raw YAML text.
    const originAgentMatch = fileContent.match(/^origin_agent\s*:\s*(.+)$/m);
    const readinessMatch = fileContent.match(/^readiness\s*:\s*(.+)$/m);
    const idMatch = fileContent.match(/^id\s*:\s*(.+)$/m);
    const originAgent = originAgentMatch ? originAgentMatch[1].trim().replace(/^['"]|['"]$/g, "") : null;
    const readiness = readinessMatch ? readinessMatch[1].trim().replace(/^['"]|['"]$/g, "") : null;
    // Qualify as orphan: origin_agent must be an AC authoring agent AND readiness must be "draft".
    const AUTHORING_AGENTS = new Set(["product-owner", "business-analyst", "it-po"]);
    if (!AUTHORING_AGENTS.has((originAgent || "").replace(/-v\d+$/, ""))) { continue; } // stored v3 authors map to canonical names
    if (readiness !== "draft") { continue; }
    // Extract AC ID: prefer the id field, fall back to filename stem.
    let acId;
    if (idMatch) {
      acId = idMatch[1].trim().replace(/^['"]|['"]$/g, "");
    } else {
      // Derive from filename: last path component without extension.
      const parts = filePath.replace(/\\/g, "/").split("/");
      const filename = parts[parts.length - 1];
      acId = filename.replace(/\.ya?ml$/, "");
    }
    // Store the resolved (absolute) path so downstream operations target the correct
    // worktree location (H-4 fix).
    orphans.push({ filePath: resolvedFilePath, acId });
  }
  return orphans;
}

/**
 * Push the authoring branch to origin and open a pull request targeting main.
 *
 * @param {string}      authoringBranch       - Full branch name.
 * @param {string|null} authoringWorktreePath - Absolute path to the dedicated authoring worktree.
 * @param {string[]}    allAcsApproved        - AC IDs approved in this session.
 * @param {string}      component             - Component label.
 * @param {string}      priority              - Priority set at the final gate.
 * @returns {Promise<{ status: "ok"|"error", message: string, pr_url?: string }>}
 */
async function deliverAuthoringBranch(authoringBranch, authoringWorktreePath, allAcsApproved, component, priority) {
  const gitC = authoringWorktreePath ? `git -C ${makerQuote(authoringWorktreePath)}` : "git";
  const acList = allAcsApproved.length > 0 ? allAcsApproved.join(", ") : "(none)";
  const componentLabel = component || "ac-store";
  const prTitle = `chore(ac): ${componentLabel} — AC authoring session approved (${allAcsApproved.length} AC${allAcsApproved.length !== 1 ? "s" : ""})`;
  const prBody =
    `## Summary\n\n` +
    `AC authoring session approved via /plan-feature.\n\n` +
    `- **Component:** ${componentLabel}\n` +
    `- **Priority:** ${priority}\n` +
    `- **ACs approved:** ${acList}\n\n` +
    `## Test plan\n\n` +
    `- [ ] Verify all AC YAML files listed above appear under docs/acceptance-criteria/ on this branch.\n` +
    `- [ ] Confirm readiness field is "approved" and priority is "${priority}" in each file.\n` +
    `- [ ] Confirm no ticket files were modified (AC authoring is AC-store-only).`;

  // Step 1 — push the authoring branch to origin.
  let pushResult;
  try {
    pushResult = await agent(
      `You are delivering an AC authoring session. The user has already given final approval — ` +
      `do NOT ask for another confirmation.\n\n` +
      `TASK: Push the authoring branch to origin and open a pull request.\n\n` +
      `Branch: ${authoringBranch}\n` +
      `Worktree: ${authoringWorktreePath || "(current checkout)"}\n` +
      `Base branch: main\n` +
      `Head branch: ${authoringBranch}\n\n` +
      `Step 1 — Push the branch:\n` +
      `  Run: ${gitC} push --set-upstream origin ${authoringBranch}\n` +
      `  If the push exits non-zero, return:\n` +
      `    { "status": "error", "message": "push failed: <stderr>", "pr_url": null }\n\n` +
      `Step 2 — Switch to the authorized GitHub account (EMU-tolerant, e-3 fix):\n` +
      `  Run: gh auth switch --user urlmonitor\n` +
      `  If this exits non-zero, continue anyway (the account may already be active).\n\n` +
      `Step 3 — Open the pull request (with REST API fallback for EMU accounts):\n` +
      `  Attempt A — gh pr create (preferred path):\n` +
      `    Run: gh pr create \\\n` +
      `      --base main \\\n` +
      `      --head "${authoringBranch}" \\\n` +
      `      --title "${prTitle.replace(/"/g, '\\"')}" \\\n` +
      `      --body "$(cat <<'PREOF'\n${prBody}\nPREOF\n)"\n` +
      `    Capture the PR URL from stdout.\n` +
      `    If gh pr create succeeds (exit 0): proceed to Step 4.\n` +
      `    If gh pr create fails with an error containing "Enterprise Managed User",\n` +
      `    "createPullRequest", or "GraphQL" in the stderr, fall through to Attempt B.\n` +
      `    If gh pr create fails for any other reason, return:\n` +
      `      { "status": "error", "message": "gh pr create failed: <stderr>", "pr_url": null }\n\n` +
      `  Attempt B — REST API fallback (for EMU-blocked GraphQL accounts):\n` +
      `    Determine the GitHub org/repo from the git remote URL:\n` +
      `      Run: ${gitC} remote get-url origin\n` +
      `      Parse the org and repo name from the URL (e.g. git@github.com:org/repo.git → org/repo).\n` +
      `    Make the REST API call (the gh CLI's api subcommand, POST to repos/<org>/<repo>/pulls) with these fields:\n` +
      `      title="${prTitle.replace(/"/g, '\\"')}"\n` +
      `      head="${authoringBranch}"\n` +
      `      base="main"\n` +
      `      body="${prBody.replace(/"/g, '\\"').replace(/\n/g, "\\n")}"\n` +
      `    Parse the JSON response to extract .html_url as the PR URL.\n` +
      `    If gh api exits non-zero, return:\n` +
      `      { "status": "error", "message": "gh api REST fallback failed: <stderr>", "pr_url": null }\n\n` +
      `Step 4 — Return success with the PR URL from whichever path succeeded:\n` +
      `  { "status": "ok", "message": "PR opened", "pr_url": "<url>" }\n` +
      `  The pr_url must be the full HTTPS URL to the pull request.\n\n` +
      `IMPORTANT: Do NOT add a sign-off to any ticket file — there is no ticket in this flow. ` +
      `Return ONLY the JSON payload described above.`,
      { agentType: "pull-request", label: "deliver-authoring-branch" }
    );
  } catch (dispatchErr) {
    return {
      status: "error",
      message: `deliverAuthoringBranch: agent dispatch failed: ${dispatchErr.message}`,
    };
  }

  let result;
  try {
    result = parseAgentJson(pushResult, { stage: "deliver-authoring-branch", agent: "pull-request" });
  } catch (_parseErr) {
    // Non-JSON response — treat as best-effort success if we cannot tell otherwise.
    return {
      status: "ok",
      message: "Branch delivery completed (response unparseable — verify PR manually).",
    };
  }

  return result || { status: "error", message: "no result returned by delivery agent" };
}

/**
 * Detect which pipeline stage keys have already been committed to the authoring
 * branch by inspecting `git log` commit messages.
 *
 * @param {string|null} authoringWorktreePath - Absolute path to the dedicated authoring worktree.
 * @returns {Promise<Set<string>>} Set of internal stage keys that already have commits.
 */
async function scanCommittedStages(authoringWorktreePath) {
  const gitLogCmd = authoringWorktreePath
    ? `git -C ${makerQuote(authoringWorktreePath)} log --oneline origin/main..HEAD`
    : "git log --oneline origin/main..HEAD";

  let logOutput;
  try {
    const logResult = await agent(
      `Run the following command and return ONLY the raw stdout:\n` +
      `${gitLogCmd}\n` +
      `Return JSON: { "output": "<raw stdout>", "exit_code": <number> }`,
      { agentType: "status-checker", label: "scan-committed-stages" }
    );
    let parsed;
    try {
      parsed = parseAgentJson(logResult, { stage: "scan-committed-stages", agent: "status-checker" });
    } catch (_parseErr) {
      return new Set();
    }
    if (!parsed || parsed.exit_code !== 0) {
      // git log failed (e.g. no origin/main yet) — treat as no committed stages.
      return new Set();
    }
    logOutput = parsed.output || "";
  } catch (_err) {
    // Cannot inspect git log — proceed without stage-skip optimisation.
    return new Set();
  }

  // Why the display-name mapping: docs/reference/plan-feature-workflow-rationale-helpers.md
  const displayToKey = {
    "po": "po",
    "ba": "ba",
    "it-po": "itpo",
    "test-design": "test-design",
    "test-design-handback": "test-design-handback",
    "mock-data": "mockdata",
    "mockup": "mockup",
    "flow": "flow",
  };

  const committedStageKeys = new Set();
  const lines = logOutput.split("\n").filter((l) => l.trim().length > 0);

  for (const line of lines) {
    // Subject format: "<hash> plan-feature(<STAGE>[, final]): <component>"
    const match = line.match(/^[0-9a-f]+\s+plan-feature\(([^,)]+)/i);
    if (!match) { continue; }
    const displayName = match[1].trim().toLowerCase();

    // Resolve the display name to an internal key using the mapping table.
    if (Object.prototype.hasOwnProperty.call(displayToKey, displayName)) {
      committedStageKeys.add(displayToKey[displayName]);
    }
  }

  return committedStageKeys;
}

/**
 * Resolve orphaned AC draft files discovered by scanOrphanedAcDrafts().
 *
 * ACD-2100c-1: the yes/no/discard choice itself is now obtained by the
 * caller through resolveGate()/pauseAtGate() (the same ADR-024 mechanism
 * every other decision point in this file routes through) BEFORE this
 * function is invoked — never by this function dispatching an agent() call
 * of its own to ask. This function only APPLIES an already-obtained
 * `userChoice`.
 *
 * @param {Array<{filePath: string, acId: string}>} orphans - Orphan list from scanOrphanedAcDrafts().
 * @param {string}      acStoreDir          - AC store directory path.
 * @param {string}      runId               - Current run id (for commit message).
 * @param {string|null} authoringWorktreePath - Absolute path to the dedicated authoring worktree.
 * @param {string}      userChoice          - "yes" | "no" | "discard" (or shorthand y/n/d),
 *                                            already obtained via resolveGate() by the caller.
 * @returns {Promise<{action: "continue"|"abort"}>} "continue" to proceed to Stage 0; "abort" to exit.
 */
async function resolveOrphanedDrafts(orphans, acStoreDir, runId, authoringWorktreePath, userChoice) {
  // Build a git command prefix helper.
  const gitCmd = authoringWorktreePath
    ? (sub) => `git -C ${makerQuote(authoringWorktreePath)} ${sub}`
    : (sub) => `git ${sub}`;

  userChoice = (typeof userChoice === "string") ? userChoice.toLowerCase().trim() : "no";

  // Normalize shorthand aliases.
  if (userChoice === "y") { userChoice = "yes"; }
  if (userChoice === "n") { userChoice = "no"; }
  if (userChoice === "d") { userChoice = "discard"; }

  if (userChoice === "yes") {
    // Commit orphaned files using the hook-safe commit path (commitStageOutput via commit agent).
    const acIdsForCommit = orphans.map((o) => o.acId);
    const commitOutcome = await commitStageOutput(
      acIdsForCommit,
      "recovery",
      "orphaned-ac-recovery",
      false,
      runId,
      acStoreDir,
      authoringWorktreePath,
      orphans.map((o) => o.filePath) // exactly the orphans' own records
    );

    if (commitOutcome.status === "error") {
      // Commit failed — abort the workflow so the user can fix the git state.
      return {
        action: "abort",
        message:
          `Could not commit orphaned AC files: ${commitOutcome.message}\n` +
          `Resolve the git error manually before re-running /plan-feature.`,
      };
    }

    return { action: "continue" };
  }

  if (userChoice === "discard") {
    // Discard orphaned files. Must handle BOTH tracked and untracked files.
    for (const orphan of orphans) {
      const { filePath } = orphan;

      // Determine if the file is untracked (status ??) or tracked (modified/added).
      let fileStatusResult;
      try {
        fileStatusResult = await agent(
          `Run this command and return the raw stdout:\n` +
          `${gitCmd(`status --porcelain --untracked-files=all -- "${filePath}"`)}\n` +
          `Return JSON: { "output": "<raw stdout>", "exit_code": <number> }`,
          { agentType: "status-checker", label: "discard-orphan-status" }
        );
      } catch (_statusErr) {
        continue;
      }

      let statusParsed;
      try {
        statusParsed = parseAgentJson(fileStatusResult, { stage: "discard-orphan-status", agent: "status-checker" });
      } catch (_parseErr) {
        statusParsed = null;
      }
      const fileStatusLine = (statusParsed && statusParsed.output) ? statusParsed.output.trim() : "";
      const isUntracked = fileStatusLine.startsWith("??");

      if (isUntracked) {
        // Untracked file: delete it explicitly (git restore cannot remove untracked files).
        try {
          await agent(
            `Delete the file at path "${filePath}" using fs.unlinkSync or equivalent.\n` +
            `Run: rm -f "${filePath}"\n` +
            `Return JSON: { "exit_code": <number>, "error": "<error or null>" }`,
            { agentType: "status-checker", label: "discard-orphan-delete" }
          );
        } catch (_rmErr) {
          // Continue — warning logged implicitly.
        }
      } else {
        // Tracked modified file: use git restore to discard working-tree changes.
        const indexStatus = fileStatusLine.length >= 1 ? fileStatusLine[0] : " ";
        if (indexStatus === "A" || indexStatus === "M") {
          try {
            await agent(
              `Run this command:\n` +
              `${gitCmd(`restore --staged "${filePath}"`)}\n` +
              `Return JSON: { "exit_code": <number> }`,
              { agentType: "status-checker", label: "discard-orphan-unstage" }
            );
          } catch (_unstageErr) {
            // Continue — warning logged implicitly.
          }
        }
        // Restore working tree. Uses git -C anchor to target the authoring worktree. (AC BO-1500a-2)
        try {
          await agent(
            `Run this command:\n` +
            `${gitCmd(`restore "${filePath}"`)}\n` +
            `Return JSON: { "exit_code": <number> }`,
            { agentType: "status-checker", label: "discard-orphan-restore" }
          );
        } catch (_restoreErr) {
          // Continue — warning logged implicitly.
        }
      }
    }

    return { action: "continue" };
  }

  // "no" or unrecognized choice: abort.
  return {
    action: "abort",
    message:
      "Uncommitted AC files must be resolved first. " +
      "Re-run /plan-feature after committing or discarding them.",
  };
}

// Why the PT phase helpers: docs/reference/plan-feature-workflow-rationale-helpers.md

/**
 * Canonical outcome → {mockdata, mockup, flow} run-set mapping.
 *
 * This is the row-for-row inverse of the validator's OUTCOME_BY_COMBO table
 * (docs/product-truth/scripts/validate_product_truth.py) keyed on
 * (needs_flow, needs_mock_data, needs_mockup):
 *
 *   OUTCOME_BY_COMBO = {
 *     (True,  True,  True):  "full-set",
 *     (False, True,  True):  "mockup+data",
 *     (False, False, True):  "mockup-only",
 *     (False, True,  False): "mock-data-only",
 *     (False, False, False): "none",
 *   }
 *
 * so full-set ⇒ all three; mockup+data ⇒ mockdata+mockup; mockup-only ⇒ mockup;
 * mock-data-only ⇒ mockdata; none ⇒ nothing. (mockdata==needs_mock_data,
 * mockup==needs_mockup, flow==needs_flow.)
 *
 * @type {Object<string,{mockdata:boolean,mockup:boolean,flow:boolean}>}
 */
const OUTCOME_TO_STAGES = {
  "full-set":       { mockdata: true,  mockup: true,  flow: true  },
  "mockup+data":    { mockdata: true,  mockup: true,  flow: false },
  "mockup-only":    { mockdata: false, mockup: true,  flow: false },
  "mock-data-only": { mockdata: true,  mockup: false, flow: false },
  "none":           { mockdata: false, mockup: false, flow: false },
};

/**
 * FIXED authoring order for the PT phase. The classifier's `dispatch` array
 * order is NEVER trusted for sequencing — the run-set is filtered from this
 * canonical order so mock data is always drafted before the mockups that
 * populate from it, and the flow that wires them is always drafted last.
 *
 * @type {Array<{agent:string, stage:string}>}
 */
const PT_ORDER = [
  { agent: "mock-data-author", stage: "mockdata" },
  { agent: "mockup-author",    stage: "mockup" },
  { agent: "flow-author",      stage: "flow" },
];

/**
 * Derive the PT run-set from a classifier decision.
 *
 * Pure function (no I/O). Trusts `classifier.outcome` exclusively — the
 * `dispatch` array is only cross-checked for advisory disagreement. Unparseable,
 * non-object, or unknown-outcome input returns `{ skip: true }` so the caller
 * falls straight through to the AC pipeline (graceful degradation). An outcome
 * of "none" returns `{ skip: false, order: [] }` — the PT phase runs but drafts
 * nothing and continues to the AC pipeline.
 *
 * @param {*} classifier - Parsed classifier JSON (any shape).
 * @returns {{skip:boolean, reason:string, outcome:string|null, order:Array<{agent:string,stage:string}>, dispatchDisagrees:boolean}}
 */
function derivePtRunSet(classifier) {
  if (!classifier || typeof classifier !== "object" || Array.isArray(classifier)) {
    return { skip: true, reason: "classifier output was not a JSON object", outcome: null, order: [], dispatchDisagrees: false };
  }
  const outcome = classifier.outcome;
  if (typeof outcome !== "string" || !Object.prototype.hasOwnProperty.call(OUTCOME_TO_STAGES, outcome)) {
    return {
      skip: true,
      reason: "classifier outcome missing or not a known enum: " + JSON.stringify(outcome),
      outcome: null,
      order: [],
      dispatchDisagrees: false,
    };
  }
  const bools = OUTCOME_TO_STAGES[outcome];
  const order = PT_ORDER.filter((step) => bools[step.stage]);

  // Advisory consistency check only — we ALWAYS trust `outcome` for the run-set.
  let dispatchDisagrees = false;
  if (Array.isArray(classifier.dispatch)) {
    const derivedAgents = order.map((step) => step.agent).sort();
    const claimed = classifier.dispatch.filter((entry) => typeof entry === "string").slice().sort();
    dispatchDisagrees = JSON.stringify(derivedAgents) !== JSON.stringify(claimed);
  }

  return { skip: false, reason: "", outcome, order, dispatchDisagrees };
}

/**
 * Verify the product-truth store + its scripts exist in the authoring worktree.
 *
 * The workflow cannot run raw fs — this is an agent dispatch (status-checker
 * runs a bash existence check). Returns true only when the store dir AND both
 * required scripts are present; any failure/unparseable result returns false so
 * the caller self-skips (non-silent) rather than dispatching authors into a
 * store that isn't there.
 *
 * @param {string}      ptStorePath           - Store path (e.g. "docs/product-truth").
 * @param {string|null} authoringWorktreePath - Absolute path to the authoring worktree.
 * @returns {Promise<boolean>}
 */
async function checkProductTruthStorePresent(ptStorePath, authoringWorktreePath) {
  const _r = authoringWorktreePath ? resolvePathOntoRoot(authoringWorktreePath, ptStorePath) : null; // KI-ACD-007 (see ptStoreDir): avoid double-anchoring an already-anchored path
  const storeDir = (_r && _r.ok) ? _r.path : ptStorePath;
  const genScript = storeDir + "/scripts/generate_product_truth.py";
  const reconcileScript = storeDir + "/scripts/apply_flow_backlinks.py";
  const checkCmd =
    `test -d "${storeDir}" && test -f "${genScript}" && test -f "${reconcileScript}" ` +
    `&& echo present || echo absent`;

  try {
    const result = await agent(
      `Run the following command and return ONLY the raw stdout:\n` +
      `${checkCmd}\n` +
      `Return JSON: { "output": "<raw stdout line>", "exit_code": <number> }`,
      { agentType: "status-checker", label: "pt-store-check" }
    );
    let parsed;
    try {
      parsed = parseAgentJson(result, { stage: "pt-store-check", agent: "status-checker" });
    } catch (_parseErr) {
      return false;
    }
    if (!parsed || typeof parsed.output !== "string") {
      return false;
    }
    return parsed.output.trim() === "present";
  } catch (_err) {
    // Cannot confirm the store — self-skip (fail-closed to "absent").
    return false;
  }
}

/**
 * Emit an OBSERVABLE, non-silent PT telemetry line via an agent dispatch.
 *
 * The workflow cannot append to a log file directly (everything is an agent
 * dispatch), so store-absent / skip events are recorded by dispatching a
 * status-checker to append one JSON line to the DECLARED operational telemetry
 * stream. The stream is never composed here (AC INF-500d-4-iv): the dispatched
 * command asks the deployed `sink_resolution.py --print-location telemetry`
 * (INF-500d-4-iii) for it, repository-anchored through
 * _buildRepoRootResolutionSnippet(), so the line lands in the enduring log
 * root and not in the authoring worktree that is deleted afterwards. On a
 * fresh install the log directory does not exist yet, so the command creates
 * it (mkdir -p) -- but only when the enduring root holding it is live (the
 * directory above the log root, or the project above `debugging`; the same
 * rule as sink_resolution.enduring_root_exists), so a vanished project is
 * never conjured back and the first event is not lost.
 * Best-effort: never throws, never blocks the pipeline. This is the "never
 * silent" guarantee for the store-absent self-skip.
 *
 * @param {string}      event                 - Short event key (e.g. "pt_phase_skipped_store_absent").
 * @param {object}      detail                - JSON-serialisable detail payload.
 * @param {string|null} authoringWorktreePath - Unused: the stream is declared, never derived from the worktree.
 * @returns {Promise<void>}
 */
async function emitPtTelemetry(event, detail, authoringWorktreePath) {
  log(`[plan-feature][PT] ${event}: ${JSON.stringify(detail)}`);
  const line = JSON.stringify({ source: "plan-feature", phase: "product-truth", event, detail });
  const target = ".leafcutter/scripts/knowledge/sink_resolution.py";
  const cmd = _buildRepoRootResolutionSnippet(target) + "SCRIPT=\"$REPO_ROOT/" + target + "\"; " +
    "STREAM=$(python \"$SCRIPT\" --print-location telemetry) || exit 1; LOG_DIR=$(dirname \"$STREAM\"); HOLDER=$(dirname \"$LOG_DIR\"); " +
    "[ \"$(basename \"$HOLDER\")\" != debugging ] || HOLDER=$(dirname \"$HOLDER\"); [ -d \"$HOLDER\" ] && mkdir -p \"$LOG_DIR\" || exit 1; " +
    "printf '%s\\n' " + JSON.stringify(line) + " >> \"$STREAM\"";
  try {
    await agent(
      `Append exactly one line to the declared operational telemetry stream. Its path comes from the ` +
      `location query sink_resolution.py --print-location telemetry; never compose a path yourself.\nRun: ${cmd}\n` +
      `This is an observability signal for the /plan-feature product-truth phase — event: ${event}.\n` +
      `Return JSON: { "exit_code": <number> }`,
      { agentType: "status-checker", label: "pt-telemetry" }
    );
  } catch (_err) {
    // Telemetry is best-effort — the log() call above already recorded the event.
  }
}

/**
 * Commit one product-truth stage's output — the surgical sibling of
 * commitStageOutput() for the AC store.
 *
 * SURGICAL STAGING (critical): stages ONLY the explicit artifact paths the PT
 * agent reported (the artifact + its regenerated derived files) PLUS
 * `<ptStorePath>/index.json`. It NEVER runs `git add docs/product-truth` (or
 * `git add .`) wholesale — that would sweep unrelated derived churn — and it
 * NEVER stages docs/acceptance-criteria/ (the AC store is a separate commit
 * surface). This mirrors the deliberately-surgical AC commit in the other
 * direction.
 *
 * NO-MAIN-COMMIT DEFENSIVE GUARD (fail-CLOSED): duplicates commitStageOutput()'s
 * guard — the branch MUST be positively confirmed non-main before any commit;
 * all failure paths abort.
 *
 * Commit subject: `plan-feature(MOCK-DATA|MOCKUP|FLOW): <component>`.
 *
 * @param {string[]}    reportedPaths         - Worktree-relative artifact + derived paths the PT agent wrote.
 * @param {string}      stageName             - Internal PT stage key ("mockdata"|"mockup"|"flow").
 * @param {string}      component             - Target component id.
 * @param {string}      runId                 - Short run identifier.
 * @param {string}      ptStorePath           - Product-truth store path (default "docs/product-truth").
 * @param {string|null} authoringWorktreePath - Absolute path to the authoring worktree.
 * @returns {Promise<{ status:"ok"|"error", message:string, hook_name?:string|null, failing_files?:string[], is_conflict?:boolean }>}
 */
async function commitStageOutputProductTruth(reportedPaths, stageName, component, runId, ptStorePath, authoringWorktreePath) {
  ptStorePath = ptStorePath || "docs/product-truth";
  const stageLabel = stageDisplayName(stageName);

  // Why the PT commit guard: docs/reference/plan-feature-workflow-rationale-helpers.md
  {
    let branchConfirmed = false;
    let branchCheckError = "unknown error during branch check";
    const branchCheckCmd = authoringWorktreePath ? `git -C ${makerQuote(authoringWorktreePath)} branch --show-current` : null;

    try {
      if (!branchCheckCmd) throw new Error("no authoring workspace path to anchor the branch check");
      const branchCheckResult = await agent(
        `Run the following command and return its raw stdout output:\n` +
        `${branchCheckCmd}\n` +
        `Return JSON: { "output": "<raw stdout line>", "exit_code": <number> }`,
        { agentType: "status-checker", label: "branch-check" }
      );
      let branchParsed;
      try {
        branchParsed = parseAgentJson(branchCheckResult, { stage: "branch-check-pt", agent: "status-checker" });
      } catch (_parseErr) {
        branchCheckError = "branch check response was not valid JSON";
        branchParsed = null;
      }

      if (branchParsed && branchParsed.exit_code === 0) {
        const currentBranch = (branchParsed.output || "").trim();
        if (currentBranch.toLowerCase() === "main") {
          return {
            status: "error",
            message:
              "safety: refusing to commit product-truth files to main — authoring branch invariant violated (AC BO-1500c-3)",
            hook_name: null,
            failing_files: [],
            is_conflict: false,
          };
        }
        if (currentBranch.length > 0) {
          branchConfirmed = true;
        } else {
          branchCheckError = "git branch --show-current returned an empty branch name";
        }
      } else if (branchParsed) {
        branchCheckError =
          "git branch --show-current exited non-zero (exit_code=" + branchParsed.exit_code + ")";
      } else {
        branchCheckError = "branch check returned null or unparseable result";
      }
    } catch (branchCheckErr) {
      branchCheckError = "agent dispatch failed: " + branchCheckErr.message;
    }

    if (!branchConfirmed) {
      return {
        status: "error",
        message:
          "safety: cannot confirm authoring branch is not main — product-truth commit aborted to " +
          "prevent committing to an unknown branch (AC BO-1500c-3). Cause: " + branchCheckError,
        hook_name: null,
        failing_files: [],
        is_conflict: false,
      };
    }
  }
  // -------------------------------------------------------------------------

  const componentLabel = component || "unknown-component";
  const commitMessage =
    `plan-feature(${stageLabel}): ${componentLabel}\n\nrun-id: ${runId}\nproduct-truth stage commit`;

  // Surgical staging set: the reported artifact/derived paths + index.json only.
  const indexPath = `${ptStorePath}/index.json`;
  const pathsToStage = Array.isArray(reportedPaths) ? reportedPaths.filter((p) => typeof p === "string" && p) : [];
  if (!pathsToStage.includes(indexPath)) {
    pathsToStage.push(indexPath);
  }
  // The product-truth commit never carries the AC store: that is a separate commit surface.
  const ptPaths = pathsToStage.filter((p) => !p.startsWith("docs/acceptance-criteria/"));

  let commitResult;
  try {
    commitResult = await agent(
      `Commit the product-truth artifacts produced by the ${stageName} stage through the shared commit step, once, in supervised mode. Use no other way of committing.\n` +
      "1. Write the message between the BEGIN-MESSAGE and END-MESSAGE lines (the markers excluded) to a new temporary message file.\n" +
      "BEGIN-MESSAGE\n" + commitMessage + "\nEND-MESSAGE\n" +
      `2. With the working directory set to ${makerQuote(authoringWorktreePath || ".")}, run: python3 {{config.output_root}}/scripts/commit_changes.py --message-file <that file> --supervised --run ${runId} ${ptPaths.join(" ")}\n` +
      "3. Return { \"status\": \"<the answer's status>\", \"commit_answer\": <the step's JSON answer exactly as printed> }",
      { agentType: "commit", label: "commit-stage-output-product-truth" }
    );
  } catch (err) {
    return {
      status: "error",
      message: `commitStageOutputProductTruth: agent dispatch failed: ${err.message}`,
      hook_name: null,
      failing_files: [],
      is_conflict: false,
    };
  }

  // Only a committed answer is a commit; anything else (or an unreadable reply) fails closed.
  let answer = null;
  try {
    answer = (parseAgentJson(commitResult, { stage: "commit-stage-output-product-truth", agent: "commit" }) || {}).commit_answer || null;
  } catch (_parseErr) {
    answer = null;
  }
  if (answer && answer.status === "committed") return { status: "ok", message: "committed successfully" };
  return {
    status: "error",
    message: answer
      ? `the commit step answered status ${answer.status}, reason_code ${answer.reason_code}: ${answer.reason}`
      : "product-truth commit answer unreadable — cannot confirm success",
    hook_name: (answer && answer.hook_name) || null,
    failing_files: (answer && Array.isArray(answer.failing_files)) ? answer.failing_files : [],
    is_conflict: !!(answer && answer.status === "refused" && /conflict/i.test(String(answer.reason || ""))),
  };
}

/**
 * Recover the committed flow's store-relative path (flowRef) from the FLOW-stage
 * commit on the authoring branch — net-new crash-resume support (today's resume
 * only recovers AC IDs). Inspects the committed diff of the plan-feature(FLOW)
 * commit for the `*.flow.json` path it added/modified.
 *
 * @param {string|null} authoringWorktreePath - Absolute path to the authoring worktree.
 * @returns {Promise<string|null>} The `.flow.json` path, or null when not recoverable.
 */
async function recoverFlowRefFromCommit(authoringWorktreePath) {
  const gitLogCmd = authoringWorktreePath
    ? `git -C ${makerQuote(authoringWorktreePath)} log --name-only --format=%H%x00%s origin/main..HEAD`
    : "git log --name-only --format=%H%x00%s origin/main..HEAD";

  try {
    const logResult = await agent(
      `Run the following command and return ONLY the raw stdout:\n` +
      `${gitLogCmd}\n` +
      `Return JSON: { "output": "<raw stdout>", "exit_code": <number> }`,
      { agentType: "status-checker", label: "resume-flow-ref" }
    );
    let parsed;
    try {
      parsed = parseAgentJson(logResult, { stage: "resume-flow-ref", agent: "status-checker" });
    } catch (_parseErr) {
      return null;
    }
    if (!parsed || parsed.exit_code !== 0) {
      return null;
    }
    const out = parsed.output || "";
    // Why how the git log is parsed per commit: docs/reference/plan-feature-workflow-rationale.md
    const lines = out.split("\n");
    let currentSubjectIsFlow = false;
    for (const rawLine of lines) {
      const nulIdx = rawLine.indexOf("\x00");
      if (nulIdx !== -1) {
        const subject = rawLine.slice(nulIdx + 1).trim();
        currentSubjectIsFlow = /^plan-feature\(FLOW\):/i.test(subject);
        continue;
      }
      const candidate = rawLine.trim();
      if (candidate.length === 0) { continue; }
      if (currentSubjectIsFlow && candidate.endsWith(".flow.json")) {
        return candidate;
      }
    }
    return null;
  } catch (_err) {
    return null;
  }
}

/**
 * Reconciliation (Track 1.3): write the business-analyst's reported
 * `flow_backlinks` into the flow's `step.implements[]` and regenerate derived
 * data, then commit the flow + index + the rewritten ACs as a DEDICATED
 * reconciliation commit (it re-mutates already-committed files, so it cannot be
 * folded into a stage commit).
 *
 * Runs `docs/product-truth/scripts/apply_flow_backlinks.py` via a status-checker
 * dispatch, then commits through the shared commit step (commit_changes.py): the
 * flow, the index, and exactly the AC records the script's `rewritten_acs` JSON
 * report names (the ACs whose product_truth back-ref changed) -- no store glob.
 *
 * @param {string}      flowRef               - Store-relative path to the approved flow's `.flow.json`.
 * @param {object}      flowBacklinks         - Map step_id -> [AC ids] reported by the BA.
 * @param {string}      component             - Target component id.
 * @param {string}      runId                 - Short run identifier.
 * @param {string}      ptStorePath           - Product-truth store path.
 * @param {string|null} authoringWorktreePath - Absolute path to the authoring worktree.
 * @returns {Promise<{status:"ok"|"error"|"skipped", message:string}>}
 */
async function runFlowReconciliation(flowRef, flowBacklinks, component, runId, ptStorePath, authoringWorktreePath) {
  if (!flowRef || !flowBacklinks || typeof flowBacklinks !== "object" || Object.keys(flowBacklinks).length === 0) {
    return { status: "skipped", message: "no flow_backlinks reported by the business-analyst — reconciliation skipped" };
  }

  const _r = authoringWorktreePath ? resolvePathOntoRoot(authoringWorktreePath, ptStorePath) : null; // BO-3900 / KI-ACD-007 (see ptStoreDir): avoid double-anchoring
  const resolvedPtStorePath = (_r && _r.ok) ? _r.path : ptStorePath;
  const scriptPath = resolvedPtStorePath + "/scripts/apply_flow_backlinks.py";
  // flowRef is store-relative (e.g. flows/foo/bar.flow.json); resolve it for the CLI.
  // NOT-A-PATH: idempotent de-duplication of an already-prefixed product-truth store identifier (forward-slash by convention, UXP-700c-3-i) — not a Windows/POSIX absoluteness decision.
  const flowArg = resolvedPtStorePath + "/" + flowRef.replace(/^\/+/, "").replace(new RegExp("^" + ptStorePath + "/"), "");
  const backlinksJson = JSON.stringify(JSON.stringify(flowBacklinks));

  // Step 1 — run the reconciliation script (writes step.implements + regenerates derived data).
  let runResult;
  try {
    runResult = await agent(
      `Run the flow-backlink reconciliation script and return its result.\n` +
      `Run: python "${scriptPath}" --flow "${flowArg}" --backlinks-json ${backlinksJson}\n` +
      `Return JSON: { "output": "<raw stdout>", "exit_code": <number>, "stderr": "<stderr or empty>" }`,
      { agentType: "status-checker", label: "pt-reconcile-run" }
    );
  } catch (err) {
    return { status: "error", message: "reconciliation dispatch failed: " + err.message };
  }
  // Why the reconcile-run parse guard: docs/reference/plan-feature-workflow-rationale-helpers.md
  let runParsed;
  try {
    runParsed = parseAgentJson(runResult, { stage: "pt-reconcile-run", agent: "status-checker" });
  } catch (_runParseErr) {
    return { status: "error", message: "reconcile result unparseable" };
  }
  if (!runParsed || (runParsed.exit_code != null && runParsed.exit_code !== 0)) {
    return {
      status: "error",
      message: "apply_flow_backlinks.py failed: " + ((runParsed && runParsed.stderr) || "(no stderr)"),
    };
  }

  // The script reports, as one JSON line on stdout, exactly the AC records it rewrote (its derived product_truth
  // back-refs). Those, and only those, join the commit; a missing or unreadable report names none (never a glob).
  const rewrittenAcs = [];
  for (const line of String(runParsed.output || "").split("\n")) {
    let rep = null;
    try { rep = JSON.parse(line.trim()); } catch (_e) { rep = null; }
    if (rep && Array.isArray(rep.rewritten_acs)) {
      for (const p of rep.rewritten_acs) {
        if (typeof p === "string" && p.endsWith(".yaml") && p.startsWith("docs/acceptance-criteria/") && !p.split("/").includes("..") && !rewrittenAcs.includes(p)) {
          rewrittenAcs.push(p);
        }
      }
    }
  }

  // Step 2 — commit the reconciliation as its own commit (flow + index + exactly the rewritten ACs).
  const commitMessage =
    `plan-feature(RECONCILE): ${component || "unknown-component"}\n\nrun-id: ${runId}\nflow step.implements back-links + regenerated derived data`;
  const indexPath = ptStorePath + "/index.json";
  // NOT-A-PATH: same idempotent store-identifier de-duplication as flowArg above — not a Windows/POSIX absoluteness decision.
  const flowStorePath = ptStorePath + "/" + flowRef.replace(/^\/+/, "").replace(new RegExp("^" + ptStorePath + "/"), "");

  try {
    const commitOut = await agent(
      `Commit the flow-backlink reconciliation as a DEDICATED commit through the shared commit step, once, in supervised mode. Use no other way of committing.\n` +
      "The reconciliation script already wrote step.implements into the flow and regenerated derived data.\n" +
      "1. Write the message between the BEGIN-MESSAGE and END-MESSAGE lines (the markers excluded) to a new temporary message file.\n" +
      "BEGIN-MESSAGE\n" + commitMessage + "\nEND-MESSAGE\n" +
      `2. With the working directory set to ${makerQuote(authoringWorktreePath || ".")}, run: python3 {{config.output_root}}/scripts/commit_changes.py --message-file <that file> --supervised --run ${runId} ${[flowStorePath, indexPath, ...rewrittenAcs].join(" ")}\n` +
      "3. Return { \"status\": \"<the answer's status>\", \"commit_answer\": <the step's JSON answer exactly as printed> }",
      { agentType: "commit", label: "commit-flow-reconciliation" }
    );
    // Only a committed answer is a commit; anything else (or an unreadable reply) fails closed.
    let answer = null;
    try {
      answer = (parseAgentJson(commitOut, { stage: "commit-flow-reconciliation", agent: "commit" }) || {}).commit_answer || null;
    } catch (_parseErr) {
      answer = null;
    }
    if (answer && answer.status === "committed") return { status: "ok", message: "reconciliation committed" };
    return {
      status: "error",
      message: answer
        ? `the commit step answered status ${answer.status}, reason_code ${answer.reason_code}: ${answer.reason}`
        : "no commit answer from the reconciliation commit",
      hook_name: (answer && answer.hook_name) || null,
      failing_files: (answer && Array.isArray(answer.failing_files)) ? answer.failing_files : [],
    };
  } catch (err) {
    return { status: "error", message: "reconciliation commit dispatch failed: " + err.message };
  }
}

// Why the inline resume helpers: docs/reference/plan-feature-workflow-rationale-helpers.md

/**
 * Validate a resume_answer's shape against its declared question type.
 * @param {object}       answer       - args.resume_answer object.
 * @param {string}       expectedType - "single_choice" | "priority_choice" | "free_text"
 * @param {string[]|null} [validOptions] - Allowed action/choice values for single_choice gates.
 * @returns {{ valid: boolean }}
 */
function validateAnswerShape(answer, expectedType, validOptions) {
  if (!answer || typeof answer !== "object") { return { valid: false }; }
  if (expectedType === "single_choice") {
    const act = typeof answer.action === "string" ? answer.action
      : (typeof answer.choice === "string" ? answer.choice : null);
    if (!act) { return { valid: false }; }
    if (Array.isArray(validOptions) && validOptions.length > 0 && !validOptions.includes(act)) {
      return { valid: false };
    }
    return { valid: true };
  }
  if (expectedType === "priority_choice") { // BO-2300d-1-iii: the answer's own action is honoured; only approve needs a priority
    const act = typeof answer.action === "string" ? answer.action : "approve";
    return ((Array.isArray(validOptions) && validOptions.length > 0 && !validOptions.includes(act)) || (act === "approve" && answer.priority == null)) ? { valid: false } : { valid: true };
  }
  if (expectedType === "free_text") {
    return (typeof answer.text === "string") ? { valid: true } : { valid: false };
  }
  return { valid: false };
}

/**
 * Apply a validated resume answer by its type and return the effective gate decision.
 * @param {object} answer - Validated answer from args.resume_answer.
 * @param {string} type   - "single_choice" | "priority_choice" | "free_text"
 * @returns {object} Gate decision e.g. { action: "approve" }.
 */
function applyAnswerByType(answer, type) {
  if (type === "priority_choice") { return { action: typeof answer.action === "string" ? answer.action : "approve", priority: answer.priority, feedback: answer.feedback }; } // BO-2300d-1-iii: never coerce edit/defer/cancel to approve
  if (type === "free_text") { return { action: "approve", text: answer.text }; }
  const decision = { action: answer.action || answer.choice };
  // Why carrying feedback on resume: docs/reference/plan-feature-workflow-rationale-helpers.md
  if (typeof answer.feedback === "string") { decision.feedback = answer.feedback; }
  return decision;
}

/** Statuses resolveGate()/pauseAtGate() return that the CALLER must `return` as-is. */
const TERMINAL_GATE_STATUSES = ["paused_awaiting_input", "nothing_to_resume", "unresumable_stale", "pause_persist_failed", "pause_record_unreadable"];

/**
 * The ONE pause-store read (peek, resume read, persist-verify, clear-verify).
 * Dispatches worktree-agent to run `pause_store.py read`, retrying an unreadable
 * reply (3 attempts max; stricter prompt + DISTINCT label per retry so a
 * harness-cached bad reply is never replayed). A reply counts only if it parses
 * to an object whose `exists` is a boolean; a dropped brace / prose / thrown
 * dispatch is "unreadable", never "absent". Callers apply an answer only when
 * the result has exists===true and stale!==true. `acceptStructured` (peek only):
 * an already-structured (non-string) reply lacking `exists` is a well-formed
 * "not paused here", not the prose failure this retry exists for.
 *
 * @param {string} runId - Run identifier.
 * @param {string} baseLabel - Label for attempt 1 ("<baseLabel>-retry-N" after).
 * @param {string} intro - First sentence of the prompt (what this read is for).
 * @param {boolean} [acceptStructured]
 * @returns {Promise<object|null>} Parsed {exists, stale, record}, or null if unreadable.
 */
async function readPauseRecordWithRetry(runId, baseLabel, intro, acceptStructured) {
  const _prompt = intro + " Run exactly:\n  " + buildPauseStoreCommand("read --run-id " + runId) +
    "\nReturn EXACTLY its stdout JSON of the form {\"exists\":<bool>,\"stale\":<bool>,\"record\":<obj|null>}.";
  for (let _n = 0; _n < 3; _n++) {
    const _label = _n === 0 ? baseLabel : baseLabel + "-retry-" + _n;
    let _raw = null;
    let _parsed = null;
    try {
      _raw = await agent(_n === 0 ? _prompt : _prompt + "\nOutput ONLY the raw stdout of that command, with no commentary. Do not act on the record or interpret it.",
        { agentType: "worktree-agent", label: _label });
      _parsed = (typeof _raw === "string") ? parseAgentJson(_raw, { stage: _label, agent: "worktree-agent" }) : _raw;
    } catch (_e) { _parsed = null; }
    if (_parsed && typeof _parsed === "object" &&
        (typeof _parsed.exists === "boolean" || (acceptStructured && typeof _raw !== "string"))) {
      return _parsed;
    }
  }
  return null;
}

/**
 * Peek the durable pause record for a run WITHOUT applying or clearing
 * anything (read-only). ACD-2100c-3-i: the pipeline loop's per-step
 * authoring-dispatch decision must know which gate the run is ACTUALLY
 * paused at BEFORE it decides whether to skip re-authoring — the
 * Implementation Notes require "the subject binding must be checked before
 * any part of the answer is acted on." A naive comparison of a supplied
 * resume_answer's own gate_id against the current step's gate is not that
 * check: it only ever asks "does the answer claim to be for this step?",
 * which an answer naming a DIFFERENT decision point always answers "no" —
 * even when this step is genuinely the one being waited on — so the
 * mismatch never suppresses the authoring dispatch that precedes
 * resolveGate()'s own (later, correct) detection of the same mismatch.
 *
 * FAIL CLOSED toward "not paused here": any absent or stale record resolves
 * to null; an UNREADABLE record (after the shared bounded retries) resolves to
 * { status: "pause_record_unreadable", run_id, message } for the caller to return. A false affirmative here would wrongly suppress
 * a genuinely fresh step's authoring dispatch — the ACD-2100c-3 H-1
 * regression (a later, uncommitted step in the SAME resumed invocation
 * must still be authored normally) that this must not reintroduce.
 *
 * @param {string} runId - Current run identifier.
 * @returns {Promise<string|null>} The gate_id the run is genuinely paused
 *   at right now, or null when there is nothing (valid) to resume.
 */
async function peekPausedGateId(runId) {
  const _peekParsed = await readPauseRecordWithRetry(runId, "peek-pause-record",
    "Read the durable pause record for this run (READ-ONLY — do not act on it or clear it).", true);
  // Unreadable is NOT "not paused here": surface a terminal status so the caller
  // does not re-dispatch the author over approved drafts.
  if (_peekParsed === null) {
    return { status: "pause_record_unreadable", run_id: runId, message: "The saved pause record could not be read, so your answer was not applied and nothing was re-authored. Re-send the same answer to retry." };
  }
  if (_peekParsed.exists !== true || _peekParsed.stale === true) { return null; }
  const _peekedRecord = _peekParsed.record;
  return (_peekedRecord && typeof _peekedRecord.gate_id === "string") ? _peekedRecord.gate_id : null;
}

/**
 * Resume-aware interactive gate resolver (ADR-024).
 *
 * CORRECTNESS INVARIANT (ADR-024 Rule 4):
 *   Checks args.resume_answer BEFORE calling liveGateFn so that on resume the
 *   harness-replayed cached headless answer is never applied.
 *
 * Return value:
 *   { action: "..." }                   — valid gate decision; caller proceeds.
 *   { status: "paused_awaiting_input" } — headless or invalid answer; caller MUST return.
 *   { status: "nothing_to_resume" }     — record absent (exists:false); caller MUST return.
 *   { status: "unresumable_stale" }     — record stale; caller MUST return.
 *
 * @param {string}   gateId      - Gate label (e.g. "final-gate").
 * @param {Function} liveGateFn  - Zero-arg async fn; returns parsed gate decision or null (headless).
 * @param {object}   args        - Workflow args (may include resume_answer, run_id).
 * @param {object}   context     - Context snapshot for the pause record.
 * @param {object}   [descriptor] - Gate question descriptor: { type, options, prompt }.
 * @param {string}   [runId]     - Explicit run id; falls back to args.run_id || "default-run".
 * @returns {Promise<object>}
 */
async function resolveGate(gateId, liveGateFn, args, context, descriptor, runId) {
  runId = runId || (args && args.run_id) || "default-run";
  const answerType = (descriptor && descriptor.type) || "single_choice";
  const validOptions = (descriptor && Array.isArray(descriptor.options)) ? descriptor.options : null;
  // BO-2300a-1-ii: LOCAL constant -- see peekPausedGateId()'s comment above.
  const _shellPermittedAgentId = "worktree-agent";

  // ADR-024 Rule 4: check resume_answer BEFORE liveGateFn.
  if (args && args.resume_answer && !args.resume_answer._appliedThisRun && args.resume_answer.gate_id === gateId) { // BO-2300d-1-iii: applied at most once per run
    const incomingType = args.resume_answer.type || answerType;
    const validation = validateAnswerShape(args.resume_answer, incomingType, validOptions);
    if (!validation.valid) {
      // Wrong/malformed shape or action not in valid options: stay paused.
      return { status: "paused_awaiting_input", run_id: runId, gate_id: gateId };
    }
    // Why shape-valid is not person-authored (ACD-2100c-4): docs/reference/plan-feature-workflow-rationale.md
    if (args.resume_answer.channel !== "person") {
      return {
        status: "paused_awaiting_input",
        run_id: runId,
        gate_id: gateId,
        reason:
          "This answer did not come from the person running the route, " +
          "so it was not treated as their decision and the choice it " +
          "named was not carried out.",
      };
    }
    // Shape valid and person-attributed: consult the durable record via agent dispatch (body has no fs access per ADR-024).
    const recCheck = await readPauseRecordWithRetry(runId, "read-pause-record",
      "Read the durable pause record for this run.");
    // An unreadable reply is NOT an absent record: never apply, never claim absence.
    if (recCheck === null) {
      return { status: "pause_record_unreadable", run_id: runId, gate_id: gateId, message: "The saved pause record could not be read after 3 attempts, so your answer was not applied. It is not known to be absent; re-send the same answer to retry." };
    }
    // FAIL CLOSED: apply ONLY when exists===true AND stale is not true.
    if (recCheck.exists !== true) {
      return { status: "nothing_to_resume", run_id: runId, gate_id: gateId };
    }
    if (recCheck.stale === true) {
      return { status: "unresumable_stale", run_id: runId, gate_id: gateId };
    }
    const decision = applyAnswerByType(args.resume_answer, incomingType); args.resume_answer._appliedThisRun = true;
    // Why the pause record context hand-back (ACD-2100c-3): docs/reference/plan-feature-workflow-rationale.md
    const _pausedRecord = (recCheck && recCheck.record) || null;
    if (_pausedRecord && _pausedRecord.context && typeof _pausedRecord.context === "object") {
      decision._resumedContext = _pausedRecord.context;
    }
    // Why the pause record is cleared once the run moves past the gate (ACD-2100c-3 AC-4): docs/reference/plan-feature-workflow-rationale.md
    if (decision.action !== "edit") {
      const _clearPrompt =
        "This paused run has been resumed and is moving past the decision point " +
        "it was waiting on. Clear its durable pause record so it no longer shows " +
        "as waiting. Run exactly:\n" +
        "  " + buildPauseStoreCommand("clear --run-id " + runId) + "\n" +
        "Return EXACTLY the command's JSON stdout.";
      const _clearRaw = await agent(_clearPrompt, { agentType: _shellPermittedAgentId, label: "clear-pause-record" });
      let _clearParsed = null;
      try {
        _clearParsed = (typeof _clearRaw === "string")
          ? parseAgentJson(_clearRaw, { stage: "clear-pause-record", agent: _shellPermittedAgentId })
          : _clearRaw;
      } catch (_clearParseErr) {
        _clearParsed = null;
      }
      let _clearVerified = !!(_clearParsed && _clearParsed.ok === true);
      if (_clearVerified) {
        const _clearVerifyParsed = await readPauseRecordWithRetry(runId, "clear-pause-record-verify",
          "Confirm the pause record was cleared.");
        _clearVerified = !!(_clearVerifyParsed && _clearVerifyParsed.exists === false);
      }

      if (!_clearVerified) {
        // Why a failed pause-record clear is reported: docs/reference/plan-feature-workflow-rationale.md
        log(
          "[plan-feature][WARNING] Could not verify the durable pause record for run '" +
          runId + "' (gate '" + gateId + "') was cleared after resume. A stale record " +
          "may remain on disk. clear-pause-record result: " + JSON.stringify(_clearParsed)
        );
        decision._clearVerifyFailed = true;
      }
    }
    return decision;
  }
  // Why an unanswered gate pauses (ACD-2100c-1 / KI-ACD-005): docs/reference/plan-feature-workflow-rationale.md
  void liveGateFn;
  return pauseAtGate(gateId, runId, context, descriptor);
}

/**
 * Pause the workflow at an interactive gate and persist the pending-question
 * record (ADR-024 pause-resume mechanism).
 *
 * Dispatches a "pause-persist" agent call carrying the question shape and
 * context snapshot, then returns { status: "paused_awaiting_input" } so the
 * caller can `return` it immediately, exiting the workflow without losing
 * committed stages.
 *
 * Called by resolveGate() on the headless path. Direct callers should use
 * resolveGate() instead, which checks args.resume_answer first (ADR-024 Rule 4).
 *
 * @param {string} gateId        - Gate label (e.g. "final-gate", "covered-route-gate").
 * @param {string} runId         - Current run identifier.
 * @param {object} ctxSnapshot   - Workflow context snapshot at pause time.
 * @param {object} [descriptor]  - Gate question descriptor: { type, options, prompt }.
 * @returns {Promise<{status: "paused_awaiting_input", run_id: string, gate_id: string}>}
 */
let _runRouteCtx = null; // ACD-2100c-3-iv: the run's effective route, persisted in every pause context
async function pauseAtGate(gateId, runId, ctxSnapshot, descriptor) {
  // BO-2300a-1-ii: LOCAL constant -- see peekPausedGateId()'s comment above.
  const _shellPermittedAgentId = "worktree-agent";
  const questionType = (descriptor && descriptor.type) || "single_choice";
  const questionOptions = (descriptor && Array.isArray(descriptor.options))
    ? descriptor.options : ["approve", "edit", "cancel", "defer"];
  const questionPrompt = (descriptor && descriptor.prompt) ||
    ("Interactive gate '" + gateId + "' requires a human decision. Options: " +
      questionOptions.join(", ") + ".");
  const question = {
    type: questionType,
    gate_id: gateId,
    options: questionOptions,
    prompt: questionPrompt,
  };
  const context = { ...(ctxSnapshot || { gate_id: gateId }), ...((typeof _runRouteCtx !== "undefined" && _runRouteCtx) || {}) };
  const rec = {
    run_id: runId, gate_id: gateId,
    question: question, context: context,
    status: "paused_awaiting_input",
  };
  // Repository-anchored (ACD-2100a-4): see buildPauseStoreCommand().
  const _persistPrompt =
    "Interactive gate '" + gateId + "' has no reachable human answerer. " +
    "Persist this pending-question record so the run can be resumed later. Run exactly:\n" +
    "  " + buildPauseStoreCommand("write --run-id " + runId + " --record '" + JSON.stringify(rec) + "'") + "\n" +
    "That writes to the repository's own paused_runs store. Return the command's JSON stdout.";
  await agent(_persistPrompt, { agentType: _shellPermittedAgentId, label: "pause-persist" });
  // Why verifying the persist: docs/reference/plan-feature-workflow-rationale-helpers.md
  const _verified = await readPauseRecordWithRetry(runId, "pause-persist-verify",
    "Confirm a pause record was persisted.");
  const _persistVerified = !!(_verified && _verified.exists === true);
  if (!_persistVerified) {
    // Fail loudly rather than advertising a resumable pause that does not exist.
    return {
      status: "pause_persist_failed",
      run_id: runId,
      gate_id: gateId,
      message:
        "Gate '" + gateId + "' needed a human answer, but the pause record for run '" +
        runId + "' could not be verified as written, so this run CANNOT be resumed.\n" +
        "Work already committed by earlier stages is safe on the authoring branch; " +
        "uncommitted drafts remain in the authoring worktree.\n" +
        "Re-run /plan-feature interactively, or drive the remaining authoring agents directly.",
    };
  }
  // Why the pause payload carries the question (ACD-2100c-1): docs/reference/plan-feature-workflow-rationale.md
  return { status: "paused_awaiting_input", run_id: runId, gate_id: gateId, question: question };
}

/**
 * Phrases that mark a dispatched agent's REFUSAL of the gate role it was handed
 * (KI-ACD-005), as opposed to a decision a human actually made.
 *
 * A refusal is well-formed JSON carrying a valid `action`/`choice` — that is
 * exactly why it used to sail through resolveGate's shape check — so it can only
 * be told apart by what its free-text field SAYS. These markers are deliberately
 * multi-word: single words like "scope" or "route" appear in ordinary user
 * feedback ("cancel, this is out of the release scope") and must not pause a run
 * the user really did decide.
 *
 * @type {string[]}
 */
const AGENT_REFUSAL_MARKERS = [
  "defined scope",
  "out of scope",
  "outside the scope",
  "outside its scope",
  "outside my scope",
  "outside your scope",
  "no defined process",
  "has no process for",
  "recommend routing",
  "routing this approval",
  "not responsible for",
  "not the right agent",
  "not the agent responsible",
  "cannot approve",
  "can not approve",
  "unable to approve",
  "cannot make this decision",
  "not authorized to",
  "no authority to",
  "beyond my remit",
  "i decline",
  "declines to",
  "refuses to",
  "was provided for this dispatch",
];

/**
 * Detect a dispatched-agent REFUSAL masquerading as a gate decision (AC BO-2300a-1).
 *
 * The gate agent (status-checker) is a proxy for a human answerer. When it replies
 * that the question is outside its charter, no human answered — the correct reading
 * is "no reachable human answerer", which per BO-2300a-1 must PAUSE the run, not
 * cancel it and discard the work. Prior to this check any object with a string
 * `action` was accepted verbatim, so a refusal reading `{"action":"cancel", ...}`
 * was indistinguishable from a user typing "cancel".
 *
 * Detection is deliberately conservative: an explicit refusal flag, or refusal
 * language in a free-text field. A bare `{"action":"cancel"}` (a real user's own
 * choice, which carries no explanation) is NOT a refusal and still cancels.
 *
 * @param {object} answer - A gate reply that already passed the shape check.
 * @returns {boolean} True when the reply is the gate agent refusing the role.
 */
function isAgentRefusal(answer) {
  if (!answer || typeof answer !== "object") { return false; }
  if (answer.refusal === true || answer.refused === true) { return true; }
  if (typeof answer.status === "string" && answer.status.toLowerCase() === "refused") { return true; }
  const textFields = ["feedback", "rationale", "reason", "message", "text", "explanation", "note"];
  for (let i = 0; i < textFields.length; i++) {
    const value = answer[textFields[i]];
    if (typeof value !== "string" || !value.trim()) { continue; }
    const haystack = value.toLowerCase();
    for (let m = 0; m < AGENT_REFUSAL_MARKERS.length; m++) {
      if (haystack.indexOf(AGENT_REFUSAL_MARKERS[m]) !== -1) { return true; }
    }
  }
  return false;
}

// Rationale (why `--git-common-dir`, why resolve inside a dispatched command): docs/reference/plan-feature-workflow-rationale.md

/**
 * Build the POSIX-sh fragment that resolves `$REPO_ROOT` to the repository
 * this process is actually operating on, worktree-aware, or prints a
 * diagnostic to stderr and exits non-zero if none resolves. Shared by every
 * repository-anchored resolution/read command below — never duplicated —
 * so a future fix to the resolution order only has to land here once.
 *
 * Resolution order:
 *   1. `git rev-parse --git-common-dir`'s parent directory. This is the same
 *      answer whether the current directory is the main checkout or a linked
 *      worktree of it, because all worktrees of a repository share one
 *      `.git` directory (KI-ACD-009 cause 1) — unlike `--show-toplevel`,
 *      which reports whichever worktree happens to be current.
 *   2. Otherwise (the ADR-001 self-hosting layout: cwd is the untracked
 *      workspace parent, and the repository lives one level down as one of
 *      its immediate child directories), probe immediate non-dot children
 *      the same way.
 *   3. Otherwise (cwd is itself a directory with no filesystem relationship
 *      to the repository at all — ACD-2100a-5: a scratch/notes/unrelated
 *      directory that merely happens to share the SAME workspace parent as
 *      the repository, e.g. a sibling of the ADR-001 workspace parent's
 *      child directories), probe the immediate children of cwd's OWN parent
 *      directory (i.e. cwd's siblings) the same way. This is the identical
 *      child-probe mechanism as step 2, anchored one directory higher, so it
 *      is still a single bounded `ls`-equivalent — never an unbounded
 *      filesystem search — keeping the startup path inside its 2-second
 *      budget (ACD-2100a-5 it_requirement).
 *   4. If none of the above resolves, print a diagnostic naming what could
 *      not be found to stderr and exit non-zero — NEVER fall back to a
 *      cwd-relative guess that could silently select the wrong physical copy.
 *
 * Kept to single-line statements (no embedded newlines) so any command built
 * from it survives this file's existing
 * "Run the following command...:\n<cmd>\n" single-line convention.
 *
 * @param {string} targetDescription - Human-readable name of what could not
 *                                      be found, used only in the failure
 *                                      diagnostic printed to stderr.
 * @returns {string} A POSIX-sh fragment (semicolon-terminated statements,
 *                    leaves `$REPO_ROOT` populated on success).
 */
function _buildRepoRootResolutionSnippet(targetDescription) {
  return (
    "REPO_ROOT=$(GC=$(git rev-parse --git-common-dir 2>/dev/null); " +
    "if [ -n \"$GC\" ]; then (cd \"$(dirname \"$GC\")\" 2>/dev/null && pwd); fi); " +
    "if [ -z \"$REPO_ROOT\" ]; then " +
    "REPO_ROOT=$(for d in */; do " +
    "gc=$(git -C \"$d\" rev-parse --git-common-dir 2>/dev/null); " +
    "if [ -n \"$gc\" ]; then (cd \"$d\" && cd \"$(dirname \"$gc\")\" 2>/dev/null && pwd); fi; " +
    "done | sort -u | head -n1); " +
    "fi; " +
    "if [ -z \"$REPO_ROOT\" ]; then " +
    "REPO_ROOT=$(for d in ../*/; do " +
    "gc=$(git -C \"$d\" rev-parse --git-common-dir 2>/dev/null); " +
    "if [ -n \"$gc\" ]; then (cd \"$d\" && cd \"$(dirname \"$gc\")\" 2>/dev/null && pwd); fi; " +
    "done | sort -u | head -n1); " +
    "fi; " +
    "if [ -z \"$REPO_ROOT\" ]; then " +
    // Why the structured ENOREPO marker is an errno-style code (ACD-2100b-1, ACD-2100b-2): docs/reference/plan-feature-workflow-rationale-helpers.md
    "echo \"REGISTRYREADFAIL reason=ENOREPO location=" + targetDescription + "\" >&2; " +
    "exit 1; " +
    "fi; "
  );
}

/**
 * Build the single-line POSIX-sh command that resolves BOTH the
 * `pause_store.py` script's repository-anchored location AND the
 * repository-anchored `paused_runs` store directory it must read/write, then
 * invokes `python "$SCRIPT" <subcommandArgs> --store-dir "$STORE_DIR"` --
 * all within the SAME shell invocation the dispatched agent runs, so a
 * single `agent()` call both resolves and executes and the resolution can
 * never silently drift from the invocation it protects (ACD-2100a-4,
 * extending ACD-2100a-1 / ACD-2100a-3's shared
 * _buildRepoRootResolutionSnippet() to the pause-store's three sites: the
 * resume-check read in resolveGate(), the write in pauseAtGate(), and the
 * read-back verification in pauseAtGate()).
 *
 * Passing an explicit `--store-dir` (rather than relying on pause_store.py's
 * own `git rev-parse --show-toplevel`-derived default) matters even once the
 * script itself is found: `--show-toplevel` reports the WORKTREE's own
 * directory when run from inside a linked git worktree, not the repository
 * root every worktree shares (see _buildRepoRootResolutionSnippet's own
 * rationale for `--git-common-dir` vs `--show-toplevel`, KI-ACD-009 cause 1)
 * -- so a writer started in a worktree and a reader started at the project
 * root must both be handed the SAME repository-anchored store directory
 * rather than each deriving their own from their own cwd.
 *
 * @param {string} subcommandArgs - The pause_store.py subcommand and its own
 *                                   arguments, e.g. "read --run-id foo" or
 *                                   "write --run-id foo --record '...'".
 * @returns {string} A single-line POSIX shell command.
 */
function buildPauseStoreCommand(subcommandArgs) {
  const target = ".leafcutter/scripts/pause_store.py";
  return (
    (typeof authoringWorktreePath === "string" && authoringWorktreePath ? "cd \"" + authoringWorktreePath + "\" || exit 1; " : "") +
    _buildRepoRootResolutionSnippet(target) +
    "SCRIPT=\"$REPO_ROOT/" + target + "\"; " +
    "if [ ! -f \"$SCRIPT\" ]; then " +
    "echo \"Could not resolve a repository-anchored " + target + " (looked for: $SCRIPT)\" >&2; " +
    "exit 1; " +
    "fi; " +
    "STORE_DIR=\"$REPO_ROOT/.leafcutter/paused_runs\"; " +
    // Why the --store-dir placement: docs/reference/plan-feature-workflow-rationale-helpers.md
    "python \"$SCRIPT\" --store-dir \"$STORE_DIR\" " + subcommandArgs
  );
}

/**
 * ACD-2500a-1: run requirement_rule_check.py for one authoring stage. Dispatches
 * label `rule-check-<stage>` to `agentType` (a shell-permitted agent). The agent
 * relay carries stdout and exit code only; the verdict is read fail-closed from
 * those, never from prose: passed iff exit_code === 0, report.verdict === "passed"
 * and report.records_checked > 0. Every other outcome (dispatch error, unreadable
 * reply, exit/verdict disagreement) is `passed: false`.
 * @returns {Promise<{passed: boolean, toCommit: string[], report: object, summary: string}>} toCommit = report.records_to_commit (every record file changed against HEAD, repaired parents included)
 */
async function runRuleCheck(stage, acStoreDir, worktreePath, agentType) {
  const target = ".leafcutter/scripts/ac_store/requirement_rule_check.py";
  const label = "rule-check-" + stage;
  const failed = (why, report) => ({ passed: false, toCommit: [], report: report || { verdict: "failed", reason: why }, summary: "Rule check failed: " + why });
  const cmd = _buildRepoRootResolutionSnippet(target) +
    "python \"$REPO_ROOT/" + target + "\" --stage " + stage + " --changed-since HEAD" +
    " --store-root \"" + acStoreDir + "\" --repo-root \"" + worktreePath + "\" --before-ref HEAD";
  try {
    const raw = await agent(
      "Run the following command and return ONLY the raw stdout output:\n" + cmd + "\n" +
      "Return JSON: { \"output\": \"<raw stdout>\", \"exit_code\": <number>, \"stderr\": \"<stderr or empty>\" }",
      { agentType: agentType, label: label }
    );
    const reply = parseAgentJson(raw, { stage: label, agent: agentType });
    const report = JSON.parse(reply.output);
    const findings = Array.isArray(report.findings) ? report.findings : [];
    if (reply.exit_code === 0 && report.verdict === "passed" && report.records_checked > 0) {
      return { passed: true, toCommit: Array.isArray(report.records_to_commit) ? report.records_to_commit : [], report: report, summary: "Rule check passed." + findings.filter((f) => f.disposition === "fixed").map((f) => "\nFixed by the check: " + f.message).join("") };
    }
    return failed("verdict " + report.verdict + ", exit " + reply.exit_code + "\n" + findings.map((f) => f.file + ": [" + f.rule_family + "] " + f.message).join("\n"), report);
  } catch (err) {
    return failed("the check produced no readable report (" + (err && err.message ? err.message : String(err)) + ")");
  }
}

// ACD-2500c-2: one deterministic ac_store CLI via the shell agent; ok only on exit 0 with JSON stdout (fail closed, like runRuleCheck).
async function runStageScript(label, script, ids, acStoreDir, worktreePath, agentType, tail) {
  const target = ".leafcutter/scripts/ac_store/" + script;
  const bad = ids.filter((id) => !/^[A-Za-z0-9._-]+$/.test(id));
  if (bad.length > 0) { return { ok: false, why: label + " refused unsafe ids " + bad.join(",") }; }
  const cmd = _buildRepoRootResolutionSnippet(target) + "python \"$REPO_ROOT/" + target + "\" --ids " + ids.join(",") +
    (tail || " --store-root \"" + acStoreDir + "\" --repo-root \"" + worktreePath + "\"");
  try {
    const raw = await agent(
      "Run the following command and return ONLY the raw stdout output:\n" + cmd + "\n" +
      "Return JSON: { \"output\": \"<raw stdout>\", \"exit_code\": <number>, \"stderr\": \"<stderr or empty>\" }",
      { agentType: agentType, label: label }
    );
    const reply = parseAgentJson(raw, { stage: label, agent: agentType });
    if (reply.exit_code !== 0) { let partial = null; try { partial = JSON.parse(reply.output); } catch (_) { partial = null; } return { ok: false, report: partial, why: label + " exited " + reply.exit_code + " " + (reply.stderr || "") }; }
    return { ok: true, report: JSON.parse(reply.output) };
  } catch (err) {
    return { ok: false, why: label + " produced no readable report (" + (err && err.message ? err.message : String(err)) + ")" };
  }
}

// ACD-2500c-2: the test-design step. No pre-pass report, no designer dispatch. Returns {ruleCheck} to stand in for the stage check, or {ruleCheck: null} to run it.
async function dispatchTestDesign(agentType, ids, feedback, acStoreDir, worktreePath, shellAgent, fromHandback) {
  const stop = (passed, why) => ({ ruleCheck: { passed: passed, toCommit: [], report: { verdict: passed ? "passed" : "failed", reason: why }, summary: "Test-design step: " + why } });
  if (fromHandback) { log("[plan-feature] resumed from the hand-back design commit (TEST-DESIGN-HANDBACK); continuing with the hand-back round and the final gate."); return stop(true, "resumed from the hand-back design commit (its test-design check passed before it was made)."); }
  const pre = await runStageScript("design-prepass", "design_prepass.py", ids, acStoreDir, worktreePath, shellAgent);
  if (!pre.ok) { return stop(false, "the pre-pass produced no report: " + pre.why); }
  if (!Array.isArray(pre.report.records) || pre.report.records.length === 0) { return stop(true, "nothing to design (no record needs a design)."); }
  try {
    const raw = await agent(
      "You are the test-designer of the /plan-feature pipeline. Design the tests of these requirement records: " + ids.join(", ") + ".\n" +
      (feedback ? "The previous attempt was rejected, address this feedback: " + feedback + "\n" : "") +
      "Pre-pass report (file facts, verbatim): " + JSON.stringify(pre.report) + "\n" +
      "First write the test design (test_spec, test_design_authorship, test_design_opened_files), then the file findings (file_findings, file_findings_opened_files, and it_requirements.reference_file_path for a record carrying the `reference file pending` marker). Edit AC YAML files ONLY under " + acStoreDir + " and touch nothing else.\n" +
      "ac_store_path: " + JSON.stringify(acStoreDir) + "\n" +
      "Return JSON: { \"status\": \"ok\" | \"blocked\", \"records\": [...], \"anomalies\": [...] }",
      { agentType: agentType, label: "stage-test-design-author" }
    );
    const result = parseAgentJson(raw, { stage: "stage-test-design-author", agent: agentType });
    if (!result || result.status !== "ok") { return stop(false, "the designer reported " + (result && result.status)); }
  } catch (err) {
    return stop(false, "the designer returned no usable result (" + (err && err.message ? err.message : String(err)) + ")");
  }
  return { ruleCheck: null };
}

// ACD-2500c-2: the records the approval-hold report holds back; an unreadable report holds every id (fail closed).
async function approvalHolds(ids, acStoreDir, worktreePath, shellAgent) {
  const out = await runStageScript("approval-holds", "approval_hold_report.py", ids, acStoreDir, worktreePath, shellAgent);
  return out.ok && Array.isArray(out.report.held) && Array.isArray(out.report.approved) ? [...out.report.held, ...ids.filter((id) => !out.report.approved.includes(id) && !out.report.held.some((h) => h.id === id)).map((id) => ({ id: id, reason: "not in the hold report" }))] : ids.map((id) => ({ id: id, reason: "unreadable" }));
}

// ACD-300c-4: approve through the store's one approval step (approve_acs.py, deployed copy; why: docs/reference/plan-feature-workflow-rationale-gates.md): its --dry-run reports the holds, the apply gets only the released ids; ok:false on any failure (fail closed).
async function approveBatch(ids, priority, acStoreDir, worktreePath, shellAgent) {
  const json = " --json --ac-root \"" + acStoreDir + "\"";
  const dry = await runStageScript("approval-holds", "approve_acs.py", ids, acStoreDir, worktreePath, shellAgent, " --dry-run" + json);
  if (!dry.ok) { return dry; }
  const released = [...(dry.report.approved || []), ...(dry.report.already_approved || [])];
  const done = released.length === 0 ? { ok: true, report: {} } : await runStageScript("approval-apply", "approve_acs.py", released, acStoreDir, worktreePath, shellAgent, " --priority " + priority + json);
  const part = done.report || {}, got = [...(part.approved || []), ...(part.already_approved || [])], failed = part.failed || [];
  const held = [...(dry.report.held || []), ...(part.held || []).filter((h) => !(dry.report.held || []).some((d) => d.id === h.id))];
  return done.ok ? { ok: true, held: held, approved: got, already: part.already_approved || [] } : { ...done, held: held, approved: got, failed: failed, untouched: released.filter((id) => !got.includes(id) && !failed.includes(id)) };
}

/** ACD-2500a-2-ix-a: add the AC ids of the hand-back design commit (exact subject label TEST-DESIGN-HANDBACK, never TEST-DESIGN) to `acs`, read from its `AC IDs:` body line. Returns true only when ids were recovered; otherwise logs why and returns false so the caller runs the stage normally (fail closed). */
async function recoverHandbackIds(acs, worktreePath) {
  const cmd = worktreePath ? `git -C "${worktreePath}" log --format=%B origin/main..HEAD` : "git log --format=%B origin/main..HEAD";
  try {
    const reply = parseAgentJson(await agent("Run the following command and return ONLY the raw stdout:\n" + cmd + "\nReturn JSON: { \"output\": \"<raw stdout>\", \"exit_code\": <number> }", { agentType: "status-checker", label: "resume-log" }), { stage: "resume-log", agent: "status-checker" });
    const commit = String(reply && reply.exit_code === 0 ? reply.output : "").split(/\n(?=plan-feature\()/).find((c) => /^plan-feature\(TEST-DESIGN-HANDBACK\):/i.test(c));
    const found = commit && commit.match(/^AC IDs:\s*(.+)$/m);
    const ids = (found ? found[1].split(",").map((x) => x.trim()) : []).filter((id) => id && id !== "(none)");
    for (const id of ids) { if (!acs.includes(id)) { acs.push(id); } }
    if (ids.length === 0) { log("[plan-feature] no AC ids recovered from the hand-back commit (git log exit " + (reply && reply.exit_code) + "); running the test-design stage normally."); }
    return ids.length > 0;
  } catch (err) {
    log("[plan-feature] could not read the hand-back commit's AC ids: " + (err && err.message ? err.message : String(err)));
    return false;
  }
}

// ACD-2500d-3-i / ACD-2500a-2-ix: hand undecided file findings back to it-po (max 2 rounds, docs/reference/code-aware-step.md); what stays undecided is shown held. Round 1 first commits the test-design output as test-design-handback (the check's before-state; why that label: docs/reference/plan-feature-workflow-rationale-gates.md); each round is checked as itpo-handback and a failure is `stopped`.
async function handBackFindings(held, ruleCheck, allAcs, acStoreDir, worktreePath, shellAgent, commitDesign, resumed) {
  const undecided = (list) => list.filter((h) => h.reason === "file finding undecided").map((h) => h.id);
  let stopped = null, checked = false;
  for (let round = 1; round <= 2 && ruleCheck.passed && undecided(held).length > 0; round++) {
    if (round === 1 && !resumed) { const done = await commitDesign(ruleCheck); if (done.status === "error") { stopped = formatCommitError("test-design", "test-design", done, allAcs); break; } }
    try {
      const raw = await agent(
        "You are the technical planner (it-po). These requirements carry file findings with no recorded decision: " + undecided(held).join(", ") + ".\n" +
        "Record a decision per undecided finding (reassign, split or assignment stands, a one-sentence reason, by: it-po); for reassign or split make that change; touch nothing else.\n" +
        "ac_store_path: " + JSON.stringify(acStoreDir) + "\nReturn JSON: { \"status\": \"ok\", \"acs_written\": [...] }",
        { agentType: "it-po", label: "it-po-findings-round-" + round }
      );
      for (const id of parseAgentJson(raw, { stage: "it-po-findings-round-" + round, agent: "it-po" }).acs_written || []) { if (!allAcs.includes(id)) { allAcs.push(id); } }
    } catch (err) {
      log("[plan-feature] findings hand-back round " + round + " failed: " + (err && err.message ? err.message : String(err)));
      break;
    }
    ruleCheck = await runRuleCheck("itpo-handback", acStoreDir, worktreePath, shellAgent);
    checked = true;
    if (!ruleCheck.passed) { stopped = "The hand-back stage (itpo-handback) is not complete, so the run stops before the final gate.\n" + ruleCheck.summary; }
    held = await approvalHolds(allAcs, acStoreDir, worktreePath, shellAgent);
  }
  if (resumed && !checked && ruleCheck.passed) { ruleCheck = await runRuleCheck("itpo-handback", acStoreDir, worktreePath, shellAgent); if (!ruleCheck.passed) { stopped = "The hand-back stage (itpo-handback) is not complete, so the run stops before the final gate.\n" + ruleCheck.summary; } }
  return { held: held, ruleCheck: ruleCheck, stopped: stopped };
}

/** ACD-300a-3: read the title of each covering AC through ONE shell dispatch (label read-covering-ac-titles; the body has no file access). Returns {id: title}; a failed read returns {} so the ids are still listed. */
async function readCoveringTitles(ids, acStoreDir) {
  if (ids.length === 0 || ids.some((id) => !/^[A-Za-z0-9._-]+$/.test(id))) { log("[plan-feature] covering AC titles not read (an id is unsafe or none given); listing ids only."); return {}; }
  const py = "import sys,json,glob,yaml; d={}; [d.__setitem__(i,yaml.safe_load(open(p,encoding=\"utf-8\")).get(\"title\")) for i in sys.argv[2:] for p in glob.glob(sys.argv[1]+\"/**/\"+i+\".yaml\",recursive=True)]; print(json.dumps(d))";
  try {
    const reply = parseAgentJson(await agent("Run the following command and return ONLY the raw stdout:\npython -c '" + py + "' \"" + acStoreDir + "\" " + ids.join(" ") + "\nReturn JSON: { \"output\": \"<raw stdout>\", \"exit_code\": <number> }", { agentType: scriptStepAgentId, label: "read-covering-ac-titles" }), { stage: "read-covering-ac-titles", agent: scriptStepAgentId });
    if (reply.exit_code !== 0) { log("[plan-feature] covering AC titles not read (command exit " + reply.exit_code + "); listing ids only."); }
    const titles = reply.exit_code === 0 ? JSON.parse(reply.output) : {};
    return titles && typeof titles === "object" && !Array.isArray(titles) ? titles : {};
  } catch (err) {
    log("[plan-feature] could not read the covering AC titles: " + (err && err.message ? err.message : String(err)));
    return {};
  }
}

// E2 top-level body — executed directly by the E2 engine

phase('Stage 0')

// Generate a short run id to identify this invocation in commit messages (ACD-300g-3).
// args.run_id replaces Math.random() which is banned in E2 (non-deterministic).
const runId = args.run_id || 'default-run';

const { request, component, force } = parseArgs(args.userInput || '');

if (!request) {
  return {
    status: "error",
    message:
      "No request text provided.\n" +
      "Usage: /plan-feature <description> [--component <name>] [--force]\n" +
      "Example: /plan-feature \"Allow users to export reports as PDF\" --component reports",
  };
}

// Pre-Stage-0 — Authoring Worktree Bootstrap (AC BO-1500a-1, BO-1500e-1).

// BO-4300c-3 / BO-4300a-1-ia: this workflow works in ONE authoring workspace -- the workspace maker's answer,
// handed in as args.workspace or obtained by exactly ONE verbatim dispatch of the maker command (further down).
// A decline / prose / result-less reply to any shell step ends the run quoting it; there is no mode in which
// the run carries on in the current checkout.

// WORKSPACE-ANSWER-START
// WORKSPACE-ANSWER-END

// Detect whether the user's current checkout is on main. One shell-runner dispatch of one exact command; a
// reply that is not a result (a decline, prose, no exit status) ends the run quoting it -- it is never taken
// as the step having run.
// Runs once the permission gate below has passed, in the project the maker was resolved in (ACD-2100a-1); null = go on.
async function detectCurrentBranch(projectRoot) {
  let r;
  try { r = shellStepReply(await shellStepDispatch(`git -C ${makerQuote(projectRoot)} branch --show-current`, "detect-current-branch", "Stage 0"), "detect-current-branch"); }
  catch (e) { r = { ok: false, reason: "no reply was received (" + e.message + ")", received: "(no answer)" }; }
  if (!r.ok) return { status: "error", message: "Could not detect the current branch: " + r.reason + ". Received: " + r.received + ". Nothing was dispatched after it." };
  if (r.exit_status !== 0 || r.stdout.trim().toLowerCase() !== "main") return null;
  log("[plan-feature] Detected: current checkout is on protected main branch.\n[plan-feature] The AC-authoring workspace is made by the workspace maker from origin/main on its own branch -- your main branch will not be modified.");
  return null;
}

const sessionSlug = component
  ? component.toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 20)
  : null;

// Why the registry read is out of this body (ACD-2100b-5): docs/reference/plan-feature-workflow-rationale.md
// The workspace-setup step runs repository-mutating commands and goes only to an agent whose charter permits shell; the verdict
// arrives as `args.workspace_setup_permission` (the pre-flight check runs outside this body) and a missing verdict fails closed.
const workspaceSetupAgentId = (args && args.workspace_setup_agent) || "shell-runner";
// Stage-end script steps (rule-check, test design, approval holds and apply, hand-back findings) send compound commands the
// one-command shell-runner declines, so they stay on worktree-agent until the follow-up ticket
// tickets/00_inbox/TICKET-20261021-PlanFeatureScriptStepsToShellRunner.md rewrites them for shell-runner (ADR-070).
const scriptStepAgentId = "worktree-agent";
const workspaceSetupPermission = args && args.workspace_setup_permission;

// Why a missing pre-flight verdict fails closed: docs/reference/plan-feature-workflow-rationale.md
if (!workspaceSetupPermission || typeof workspaceSetupPermission !== "object") {
  const missingPreflightMessage =
    "No workspace-setup permission pre-flight verdict was supplied in args " +
    "(args.workspace_setup_permission). This workflow no longer resolves the " +
    "workspace-setup permission itself: the plan-feature skill's pre-flight " +
    "(scripts/worktree/check_workspace_setup_permission.py) must run BEFORE " +
    "this workflow is invoked and pass its verdict through args. This is a " +
    "MISSING pre-flight, not a permission denial — halting before any " +
    "authoring agent is dispatched.";
  log("[plan-feature][WARNING] " + missingPreflightMessage);
  return { status: "error", message: missingPreflightMessage };
}

if (workspaceSetupPermission.permits !== true) {
  // Why how the pre-flight outcome field is read (ACD-2100b): docs/reference/plan-feature-workflow-rationale-gates.md
  const outcome = typeof workspaceSetupPermission.outcome === "string"
    ? workspaceSetupPermission.outcome
    : "unknown";
  const outcomeMessages = {
    // Why absent versus permission-refused registry reports (ACD-2100b-1): docs/reference/plan-feature-workflow-rationale-gates.md
    read_failure:
      "The workspace-setup permission pre-flight could not read the agent registry" +
      (typeof workspaceSetupPermission.location === "string"
        ? " at '" + workspaceSetupPermission.location + "'"
        : " (config/agent_registry.json)") +
      ". " +
      (typeof workspaceSetupPermission.reason === "string"
        ? workspaceSetupPermission.reason + " "
        : "") +
      "Halting before any authoring agent is dispatched.",
    parse_failure:
      "The workspace-setup permission pre-flight read the agent registry successfully " +
      "but its contents could not be interpreted as valid JSON. Halting before any " +
      "authoring agent is dispatched.",
    agent_not_found:
      "The isolated-workspace setup step 'worktree-setup' was configured to dispatch to agent '" +
      workspaceSetupAgentId + "', but that agent was not found in the registry " +
      "(config/agent_registry.json). Halting before any authoring agent is dispatched. " +
      "Report this mis-assignment to the operator: step='worktree-setup', agent='" +
      workspaceSetupAgentId + "'.",
    no_entries_collection:
      "The agent registry (config/agent_registry.json) could not be used: its 'agents' field is " +
      "not a list of agent entries. Halting before any authoring agent is dispatched. Fix " +
      "config/agent_registry.json so that 'agents' is a list of agent entries.",
    // Why the denied report names permits_shell (ACD-2100b-3): docs/reference/plan-feature-workflow-rationale-gates.md
    permission_denied:
      "The isolated-workspace setup step 'worktree-setup' was configured to dispatch to agent '" +
      workspaceSetupAgentId + "', which is listed in the agent registry (config/agent_registry.json) " +
      "but is not permitted to run repository-mutating shell commands. Halting before any authoring " +
      "agent is dispatched. Fix config/agent_registry.json's permits_shell field for agent '" +
      workspaceSetupAgentId + "' to true, or report this mis-assignment to the operator: " +
      "step='worktree-setup', agent='" + workspaceSetupAgentId + "'.",
  };
  const deniedMessage = outcomeMessages[outcome] || (
    "The workspace-setup permission pre-flight denied permission for agent '" +
    workspaceSetupAgentId + "' (outcome='" + outcome + "'). Halting before any authoring " +
    "agent is dispatched."
  );
  log("[plan-feature][WARNING] " + deniedMessage);
  return { status: "error", message: deniedMessage };
}

const makerPath = await resolveRepoAnchoredMakerPath("Stage 0", "{{config.output_root}}");
if (!makerPath.ok) return workspaceFailure(makerPath);
const branchFailure = await detectCurrentBranch(makerPath.root);
if (branchFailure) return branchFailure;

// The authoring workspace: the maker's answer (args.workspace) or exactly one verbatim dispatch of the maker
// command. Anything but an accepted answer ends the run here, quoting what was received (BO-4300c-3).
// ACD-2100a-1: that dispatch names the maker copy inside the repository by its absolute path, never a cwd-relative one.
const authoringWorkspace = await workspaceObtain(
  makerCommand(makerPath.path, "ensure", { kind: "ac", slug: sessionSlug || "ac-authoring" }), "Stage 0");
if (!authoringWorkspace.accepted) return workspaceFailure(authoringWorkspace);

const authoringWorktreePath = authoringWorkspace.workspace_path;
const workingLocationNote = `Working location (the maker's workspace): ${authoringWorktreePath}\n` +
  "Do all work and write every file inside that folder only.\n";
const acStoreDir = (typeof authoringWorkspace.answer.ac_store_path === "string" && authoringWorkspace.answer.ac_store_path) || "docs/acceptance-criteria";

// Pre-Stage-0 — Partial-Run Recovery: detect and resolve orphaned AC drafts
// ACD-2100c-3-iii: on resume with candidates, the run's own drafts (pause record context.acs) are not orphans.
let orphans = await scanOrphanedAcDrafts(acStoreDir, authoringWorktreePath);
if (orphans.length > 0 && args.resume_answer && args.resume_answer.gate_id !== "resolve-orphans-choice") {
  const _ownRec = await readPauseRecordWithRetry(args.run_id || "default-run", "orphan-scan-pause-record", "Read the durable pause record for this run (READ-ONLY — do not act on it or clear it).");
  if (_ownRec === null) {
    return { status: "pause_record_unreadable", run_id: args.run_id || "default-run", message: "The saved pause record could not be read, so your answer was not applied. Re-send the same answer to retry." };
  }
  const _ownAcs = (_ownRec.exists === true && _ownRec.stale !== true && _ownRec.record && _ownRec.record.context && _ownRec.record.context.acs) || [];
  const _ownAcIds = (Array.isArray(_ownAcs) ? _ownAcs : []).map((a) => (a && typeof a === "object") ? (a.id || a.ac_id) : a);
  orphans = orphans.filter((o) => !_ownAcIds.includes(o.acId));
}
if (orphans.length > 0) {
  const orphanAcIds = orphans.map((o) => o.acId).sort();
  const orphanN = orphans.length;
  const orphanAcIdList = orphanAcIds.join(", ");
  // Why the orphan gate closure: docs/reference/plan-feature-workflow-rationale-helpers.md
  const _orphanGateResult = await resolveGate(
    "resolve-orphans-choice",
    async () => {
      const raw = await agent(
        `Found ${orphanN} uncommitted AC file${orphanN !== 1 ? "s" : ""} from a prior session: [${orphanAcIdList}]. ` +
        `(yes/no/discard)\n\n` +
        `Present this message EXACTLY to the user and ask them to choose:\n` +
        `  yes     — commit the orphaned files before starting new work.\n` +
        `  no      — abort the workflow (files remain on disk, must be resolved manually).\n` +
        `  discard — delete the orphaned files and start with a clean working tree.\n\n` +
        `Return ONLY a JSON object: { "choice": "yes" | "no" | "discard" }`,
        { agentType: "status-checker", label: "resolve-orphans-choice" }
      );
      let parsed;
      try {
        parsed = parseAgentJson(raw, { stage: "resolve-orphans-choice", agent: "status-checker" });
      } catch (_orphanParseErr) {
        parsed = null;
      }
      return (parsed && typeof parsed.choice === "string") ? parsed : null;
    },
    args,
    { orphans: orphanAcIds },
    {
      type: "single_choice",
      options: ["yes", "no", "discard"],
      prompt:
        `Found ${orphanN} uncommitted AC file${orphanN !== 1 ? "s" : ""} from a prior session: ` +
        `[${orphanAcIdList}]. Choose: yes (commit them before starting new work), ` +
        `no (abort; resolve manually), or discard (delete them and start clean).`,
    },
    args.run_id || "default-run"
  );
  if (_orphanGateResult && TERMINAL_GATE_STATUSES.includes(_orphanGateResult.status)) {
    return _orphanGateResult;
  }
  // Why the orphan decision fail-closed: docs/reference/plan-feature-workflow-rationale-helpers.md
  const orphanChoice = (_orphanGateResult && (_orphanGateResult.action || _orphanGateResult.choice)) || "no";
  const recoveryOutcome = await resolveOrphanedDrafts(orphans, acStoreDir, runId, authoringWorktreePath, orphanChoice);
  if (recoveryOutcome.action === "abort") {
    return {
      status: "error",
      message: recoveryOutcome.message ||
        "Uncommitted AC files must be resolved first. Re-run /plan-feature after resolving them.",
    };
  }
}

// Pre-Stage-0 — Committed-Stage Detection
const committedStageKeys = await scanCommittedStages(authoringWorktreePath);

// ACD-2100c-3-iv: resuming any gate but covered-route-gate keeps the paused run's route; it is never re-triaged.
const _pr = args.resume_answer ? await readPauseRecordWithRetry(runId, "peek-pause-record", "Read the durable pause record for this run (READ-ONLY — do not act on it or clear it).", true) : null;
const _resumedCtx = (_pr && _pr.exists === true && _pr.stale !== true && _pr.record && _pr.record.gate_id !== "covered-route-gate" && _pr.record.context && typeof _pr.record.context.route === "string") ? _pr.record.context : null;
// Stage 0 — ac-triage: duplicate check + route classification
const triageResult = _resumedCtx ? null : await agent(
  workingLocationNote +
  "Triage the user's request against the AC store. " +
  "Return a JSON object with keys: route, existing_acs, parent_l1_id, rationale. " +
  "route must be one of: strategic | behavioral | technical | covered. " +
  "existing_acs is an array of AC IDs that are semantically relevant. " +
  "parent_l1_id is the ID of the matching L1 AC (for behavioral route), or null. " +
  "rationale is a one-sentence explanation of the classification.\n" +
  `user_request: ${JSON.stringify(request)}\n` +
  `component: ${JSON.stringify(component)}`,
  { agentType: "ac-triage", label: "stage-0-triage" }
);

let triage;
try {
  triage = _resumedCtx ? { route: _resumedCtx.route, existing_acs: _resumedCtx.existing_acs || [], parent_l1_id: _resumedCtx.parent_l1_id || null, rationale: "route restored from the pause record" } : parseAgentJson(triageResult, { stage: "stage-0-triage", agent: "ac-triage" });
} catch (err) {
  return {
    status: "error",
    message: `ac-triage returned unparseable output: ${err.message}. Raw: ${JSON.stringify(triageResult)}`,
  };
}

const { route, existing_acs = [], parent_l1_id = null, rationale = "" } = triage;

// Handle "covered" route: show existing ACs + prompt user
let _amendIds = []; // ACD-300a-3: the covering ids an "amend" answer hands to the it-po stage
if (route === "covered" && !force && !_resumedCtx) {
  const _covTitles = args.resume_answer ? {} : await readCoveringTitles(existing_acs, acStoreDir);
  const _covQuestion = "These existing ACs already cover your request. Would you like to proceed anyway (force new), amend an existing AC, or cancel?" + existing_acs.map((id) => "\n  " + id + (typeof _covTitles[id] === "string" && _covTitles[id] ? ": " + _covTitles[id] : "")).join("");
  // ADR-024: resolveGate checks args.resume_answer before the live agent call.
  const _covGateResult = await resolveGate(
    "covered-route-gate",
    async () => {
      const raw = await agent(
        "Present the following to the user and ask them to choose one option:\n\n" + _covQuestion + "\n\n" +
        "Options:\n" +
        "  1. cancel  — the existing ACs are sufficient; exit without creating new ACs.\n" +
        "  2. amend   — add constraints/details to the existing ACs (routes as 'technical').\n" +
        "  3. force   — create new ACs anyway (routes as 'strategic').\n\n" +
        "Return ONLY a JSON object: { \"choice\": \"cancel\" | \"amend\" | \"force\", \"rationale\": \"...\" }",
        { agentType: "status-checker", label: "covered-route-gate" }
      );
      let parsed;
      try {
        parsed = parseAgentJson(raw, { stage: "covered-route-gate", agent: "status-checker" });
      } catch (_) {
        parsed = null;
      }
      return (parsed && typeof parsed.choice === "string") ? parsed : null;
    },
    args,
    { route: "covered", existing_acs },
    { type: "single_choice", options: ["cancel", "amend", "force"], prompt: _covQuestion },
    args.run_id || "default-run"
  );
  if (_covGateResult && TERMINAL_GATE_STATUSES.includes(_covGateResult.status)) {
    return _covGateResult;
  }
  // Why a missing covered-gate answer fails closed (KI-ACD-005): docs/reference/plan-feature-workflow-rationale-gates.md
  if (!_covGateResult) {
    return {
      status: "undetermined",
      message:
        "The covered-route confirmation gate returned no usable answer, so no " +
        "decision was recorded and nothing was changed. This is a gate failure, " +
        "NOT a user cancellation — re-run /plan-feature and answer the gate.",
      stage: "covered-route-gate",
      covered_by: existing_acs,
    };
  }
  const userChoice = _covGateResult;
  const choice = (userChoice.choice || userChoice.action || "cancel").toLowerCase();

  if (choice === "cancel") {
    return {
      status: "ok",
      message: `Request is already covered by: ${existing_acs.join(", ")}. No new ACs created.`,
      covered_by: existing_acs,
    };
  }

  if (choice === "amend") {
    triage.route = "technical"; _amendIds = existing_acs;
  } else {
    // force → strategic
    triage.route = "strategic";
  }
}

if (route === "covered" && force) { triage.route = "strategic"; } // ACD-300a-3: --force on a covered request is the force answer
_runRouteCtx = { route: triage.route, existing_acs, parent_l1_id };
// Why the always-on Product-Truth phase: docs/reference/plan-feature-workflow-rationale-gates.md
phase('Product-Truth Phase')

// KI-ACD-007 / BO-1500a-5-i: authoringWorktreePath is guaranteed non-null past the worktree-setup gate above (ACD-2400.yaml amended_by); always anchor via resolvePathOntoRoot(), mirroring acStoreDir's own unconditional treatment above.
const ptStoreDir = resolvePathOntoRoot(authoringWorktreePath, "docs/product-truth").path;

// State the PT phase hands forward to the AC pipeline.
let ptFlowProduced = false;
let ptFlowRef = null;          // store-relative path to the approved .flow.json
let ptComponent = component;   // classifier may refine the target component

const classifierResult = await agent(
  workingLocationNote +
  "Classify which product-truth artifacts this request needs. " +
  "Decide needs_mock_data, needs_mockup, needs_flow; derive the `outcome` per OUTCOME_BY_COMBO " +
  "(full-set / mockup+data / mockup-only / mock-data-only / none); name the target component and entities. " +
  "Return the structured JSON decision — it MUST include an `outcome` field.\n" +
  `user_request: ${JSON.stringify(request)}\n` +
  `component: ${JSON.stringify(component)}\n` +
  "Return ONLY the JSON classification object.",
  { agentType: "pt-classifier", label: "pt-classify" }
);

let classifier;
try {
  classifier = parseAgentJson(classifierResult, { stage: "pt-classify", agent: "pt-classifier" });
} catch (_ptParseErr) {
  classifier = null;
}

const ptRunSet = derivePtRunSet(classifier);

if (ptRunSet.skip) {
  log(`[plan-feature][PT] classifier unparseable/inconsistent — skipping PT phase, continuing to AC pipeline. reason: ${ptRunSet.reason}`);
} else if (ptRunSet.order.length === 0) {
  log("[plan-feature][PT] outcome=none — no product-truth artifacts needed; continuing to AC pipeline.");
} else {
  if (classifier && typeof classifier.component === "string" && classifier.component) {
    ptComponent = classifier.component;
  }
  if (ptRunSet.dispatchDisagrees) {
    log("[plan-feature][PT] classifier.dispatch disagreed with outcome — trusting the outcome-derived run-set.");
  }

  const storePresent = await checkProductTruthStorePresent(ptStoreDir, authoringWorktreePath);
  if (!storePresent) {
    // Store-absent self-skip — NON-SILENT (observable telemetry + log).
    await emitPtTelemetry(
      "pt_phase_skipped_store_absent",
      { outcome: ptRunSet.outcome, component: ptComponent, run_id: runId },
      authoringWorktreePath
    );
    log("[plan-feature][PT] product-truth store/scripts absent — self-skipping PT phase; AC pipeline will proceed.");
  } else {
    // PT authoring loop — mirrors the AC pipeline loop.
    for (const ptStep of ptRunSet.order) {
      // Crash-resume: skip PT stages already committed on the authoring branch.
      if (committedStageKeys.has(ptStep.stage)) {
        if (ptStep.stage === "flow") {
          ptFlowProduced = true;
          const recovered = await recoverFlowRefFromCommit(authoringWorktreePath);
          if (recovered) { ptFlowRef = recovered; }
        }
        continue;
      }

      let ptResult;
      let ptEditRetries = 0;
      let ptApproved = false;
      let ptFeedback = "";

      while (!ptApproved) {
        ptResult = await agent(
          workingLocationNote +
          `You are running as part of the /plan-feature product-truth phase (outcome: ${ptRunSet.outcome}). ` +
          `Draft or extend the ${ptStep.stage} artifact for this request. Write it ONLY to ${ptStoreDir} — ` +
          "do NOT write to docs/product-truth/ relative to the current checkout. " +
          (ptFeedback
            ? `The user reviewed your previous attempt and requested changes — address this feedback: ${ptFeedback}. `
            : "") +
          "Do NOT write any acceptance-criteria files. " +
          "After writing, return a JSON object: " +
          "{ \"status\": \"ok\", \"artifact_paths\": [\"docs/product-truth/...\"], \"flow_ref\": \"<path or null>\" } " +
          "where artifact_paths lists EVERY file you created or modified (the artifact PLUS any regenerated derived files).\n" +
          `user_request: ${JSON.stringify(request)}\n` +
          `component: ${JSON.stringify(ptComponent)}\n` +
          `outcome: ${JSON.stringify(ptRunSet.outcome)}\n` +
          `pt_store_path: ${JSON.stringify(ptStoreDir)}`,
          { agentType: ptStep.agent, label: `pt-${ptStep.stage}-author` }
        );

        // Tolerant parse: the PT author may return a JSON STRING; read fields off
        // the parsed object so artifact_paths/flow_ref aren't silently dropped.
        let ptResultObj;
        try {
          ptResultObj = parseAgentJson(ptResult, { stage: `pt-${ptStep.stage}-author`, agent: ptStep.agent });
        } catch (_ptResultParseErr) {
          ptResultObj = {};
        }
        const reportedPaths = (ptResultObj && Array.isArray(ptResultObj.artifact_paths)) ? ptResultObj.artifact_paths : [];

        // Gate: approve / edit / cancel. ADR-024: resolveGate checks args.resume_answer first.
        const _ptGateResult = await resolveGate(
          `pt-gate-${ptStep.stage}`,
          async () => {
            const raw = await agent(
              `${ptStep.agent} drafted the following product-truth artifact(s): ${reportedPaths.join(", ") || "(none)"}.\n` +
              "Present these to the user and ask them to choose:\n" +
              "  1. approve — commit this stage and proceed.\n" +
              "  2. edit    — re-invoke this agent with feedback.\n" +
              "  3. cancel  — abort the pipeline (no PR; prior committed stages preserved; this draft left uncommitted).\n" +
              "Return ONLY a JSON object: { \"action\": \"approve\" | \"edit\" | \"cancel\", \"feedback\": \"...\" }",
              { agentType: "status-checker", label: `pt-gate-${ptStep.stage}` }
            );
            let parsed;
            try {
              parsed = parseAgentJson(raw, { stage: `pt-gate-${ptStep.stage}`, agent: "status-checker" });
            } catch (_ptGateErr) {
              parsed = null;
            }
            return (parsed && typeof parsed.action === "string") ? parsed : null;
          },
          args,
          { stage: ptStep.stage },
          { type: "single_choice", options: ["approve", "edit", "cancel"] },
          args.run_id || "default-run"
        );
        if (_ptGateResult && TERMINAL_GATE_STATUSES.includes(_ptGateResult.status)) {
          return _ptGateResult;
        }
        if (!_ptGateResult) {
          return {
            status: "undetermined",
            message:
              `The product-truth gate (${ptStep.agent}, stage ${ptStep.stage}) ` +
              `returned no usable answer, so no decision was recorded. This is a ` +
              `gate failure, NOT a user cancellation. Prior committed ` +
              `product-truth stages are preserved and the current ${ptStep.stage} ` +
              `draft is left uncommitted on disk — re-run /plan-feature and ` +
              `answer the gate.`,
            stage: `pt-gate-${ptStep.stage}`,
          };
        }
        const ptGate = _ptGateResult;
        const ptAction = ptGate.action.toLowerCase();

        if (ptAction === "cancel") {
          // Why the PT cancel status (BO-2300a-2, ACD-2100c-5): docs/reference/plan-feature-workflow-rationale-gates.md
          return {
            status: "cancelled",
            message:
              `Pipeline cancelled at the product-truth gate (${ptStep.agent}). No PR was opened. ` +
              `Prior committed product-truth stages are preserved; the current ${ptStep.stage} draft is left uncommitted on disk.`,
            cancelled_at: `pt-gate-${ptStep.stage}`,
            cancelled_by: "person",
          };
        } else if (ptAction === "edit" && ptEditRetries < MAX_EDIT_RETRIES) {
          ptEditRetries++;
          // Thread the user's edit feedback into the next re-dispatch (m4).
          ptFeedback = (ptGate && typeof ptGate.feedback === "string") ? ptGate.feedback.trim() : "";
          continue;
        } else if (ptAction === "edit" && ptEditRetries >= MAX_EDIT_RETRIES) {
          return {
            status: "error",
            message:
              `${ptStep.agent} failed to produce a satisfactory ${ptStep.stage} artifact after ${MAX_EDIT_RETRIES + 1} attempts. ` +
              "Pipeline aborted (no PR).",
          };
        } else {
          // approve — COMMIT-BEFORE-NEXT-PT-STAGE INVARIANT: a failed commit aborts
          // BEFORE the next PT agent is dispatched (mirrors the AC pipeline).
          const ptCommit = await commitStageOutputProductTruth(
            reportedPaths, ptStep.stage, ptComponent, runId, ptStoreDir, authoringWorktreePath
          );
          if (ptCommit.status === "error") {
            return {
              status: "error",
              message:
                `Commit of the ${ptStep.stage} product-truth artifact failed: ${ptCommit.message}\n` +
                "The pipeline aborted BEFORE dispatching the next product-truth agent. " +
                "The drafted artifact remains on disk as uncommitted changes.",
              failed_stage: ptStep.stage,
            };
          }
          ptApproved = true;
          if (ptStep.stage === "flow") {
            ptFlowProduced = true;
            const fr = (ptResultObj && typeof ptResultObj.flow_ref === "string" && ptResultObj.flow_ref) ? ptResultObj.flow_ref : null;
            ptFlowRef = fr || (reportedPaths.find((p) => typeof p === "string" && p.endsWith(".flow.json")) || null);
          }
        }
      }
    }
  }
}

// Build the agent dispatch sequence based on effective route
const effectiveRoute = triage.route;

// flow_backlinks reported by the business-analyst (for the reconciliation step).
let baFlowBacklinks = null;

/** @type {Array<{agent: string, stage: string, gate: string}>} */
let pipeline;

if (effectiveRoute === "strategic") {
  pipeline = [
    { agent: "product-owner",    stage: "po",   gate: "after_po" },
    { agent: "business-analyst", stage: "ba",   gate: "after_ba" },
    { agent: "it-po",           stage: "itpo",  gate: "final" },
  ];
} else if (effectiveRoute === "behavioral") {
  pipeline = [
    { agent: "business-analyst", stage: "ba",  gate: "after_ba" },
    { agent: "it-po",           stage: "itpo", gate: "final" },
  ];
} else if (ptFlowProduced) {
  // Why forcing the BA stage: docs/reference/plan-feature-workflow-rationale-helpers.md
  pipeline = [
    { agent: "business-analyst", stage: "ba",   gate: "after_ba" },
    { agent: "it-po",           stage: "itpo", gate: "final" },
  ];
} else {
  // technical (or amend → technical, or covered → force handled above)
  pipeline = [
    { agent: "it-po", stage: "itpo", gate: "final" },
  ];
}
pipeline[pipeline.length - 1].gate = "auto";
pipeline.push({ agent: "test-designer", stage: "test-design", gate: "final" });

// Stage 1–N — sequential authoring pipeline with gates

phase('Authoring Pipeline')

/** All AC ids written during this run (accumulated across all agents). */
const allAcsWritten = [];
/**
 * AC ids that have been successfully committed to git in prior stages.
 */
const committedAcs = [];
const stageResults = [];

for (const step of pipeline) {
  // Why the crash-resume skip: docs/reference/plan-feature-workflow-rationale-helpers.md
  if (committedStageKeys.has(step.stage)) {
    // Why the crash-resume id recovery: docs/reference/plan-feature-workflow-rationale-helpers.md
    const stageDisplayLabel = stageDisplayName(step.stage);
    const resumeLogCmd = authoringWorktreePath
      ? `git -C ${makerQuote(authoringWorktreePath)} log --format=%B origin/main..HEAD`
      : "git log --format=%B origin/main..HEAD";

    let resumedAcIds = [];
    try {
      const resumeLogResult = await agent(
        `Run the following command and return ONLY the raw stdout:\n` +
        `${resumeLogCmd}\n` +
        `Return JSON: { "output": "<raw stdout>", "exit_code": <number> }`,
        { agentType: "status-checker", label: "resume-log" }
      );
      let resumeLogParsed;
      try {
        resumeLogParsed = parseAgentJson(resumeLogResult, { stage: "resume-log", agent: "status-checker" });
      } catch (_parseErr) {
        resumeLogParsed = null;
      }
      if (resumeLogParsed && resumeLogParsed.exit_code === 0) {
        const logBody = resumeLogParsed.output || "";
        // Why how AC ids are recovered from commit bodies: docs/reference/plan-feature-workflow-rationale-gates.md
        const stageSubjectRe = new RegExp(
          `^plan-feature\\(${stageDisplayLabel}(?:,[^)]*)?\\):`,
          "i"
        );
        const anyStageSubjectRe = /^plan-feature\([^)]*\):/i;
        let inTargetStage = false;
        for (const rawLine of logBody.split("\n")) {
          const line = rawLine.trim();
          if (anyStageSubjectRe.test(line)) {
            inTargetStage = stageSubjectRe.test(line);
            continue;
          }
          if (!inTargetStage) { continue; }
          const acIdsMatch = line.match(/^AC IDs:\s*(.+)$/);
          if (acIdsMatch) {
            resumedAcIds = acIdsMatch[1]
              .split(",")
              .map((s) => s.trim())
              .filter((s) => s.length > 0 && s !== "(none)");
            break;
          }
        }
      }
    } catch (_resumeErr) {
      // Cannot read git log — proceed without recovering AC IDs.
    }

    // Add recovered AC IDs to allAcsWritten so they appear in the final
    // approval set and PR body (H-1 fix).
    allAcsWritten.push(...resumedAcIds);
    // Also add to committedAcs so cancel messages distinguish prior commits.
    committedAcs.push(...resumedAcIds);

    // Why a skipped reconciliation is signalled (m6): docs/reference/plan-feature-workflow-rationale-gates.md
    if (step.stage === "ba" && ptFlowProduced) {
      await emitPtTelemetry(
        "pt_reconciliation_skipped_on_resume",
        {
          component: ptComponent,
          flow_ref: ptFlowRef,
          run_id: runId,
          note:
            "BA stage was crash-resumed (already committed); flow step.implements " +
            "reconciliation was NOT run — run docs/product-truth/scripts/apply_flow_backlinks.py manually.",
        },
        authoringWorktreePath
      );
    }

    stageResults.push({ stage: step.stage, agent: step.agent, acs: resumedAcIds, skipped: true });
    continue;
  }

  let stepResult;
  let editRetries = 0;
  let approved = false;
  let acFeedback = "";
  let designOutcome = null;

  // Why the step gate id and resume detection (ACD-2100c-3): docs/reference/plan-feature-workflow-rationale-gates.md
  const stepGateId = step.gate === "final" ? "final-gate" : `gate-${step.stage}`;
  const _resumeAnswerForThisStep =
    (args && args.resume_answer && args.resume_answer.gate_id === stepGateId) ? args.resume_answer : null;
  // Why the edit resume answer: docs/reference/plan-feature-workflow-rationale-helpers.md
  const _resumeAction = _resumeAnswerForThisStep
    ? (_resumeAnswerForThisStep.action || _resumeAnswerForThisStep.choice || null)
    : null;
  // Why the resume answer subject binding (ACD-2100c-3-i): docs/reference/plan-feature-workflow-rationale-gates.md
  let isPausedAtThisStep = false;
  if (args && args.resume_answer) {
    const _actualPausedGateId = await peekPausedGateId(args.run_id || "default-run");
    if (_actualPausedGateId && typeof _actualPausedGateId === "object") { return _actualPausedGateId; }
    isPausedAtThisStep = _actualPausedGateId === stepGateId;
  }
  let skipAuthorOnResume = isPausedAtThisStep; // BO-2300d-1-iii: an edit resume also skips the pre-gate author run; the edit re-authors once
  let resumedHandback = false; // ACD-2500a-2-ix-a: the test-design step resumes from the hand-back design commit
  let reapprove = false; // approval was consumed, then the check forced a re-author: a rewrite that passes needs a NEW pause (never the old answer); one that still fails skips the gate and retries

  while (!approved) {
    // Why the author is not re-dispatched on resume (ACD-2100c-3): docs/reference/plan-feature-workflow-rationale-gates.md
    let written;
    if (skipAuthorOnResume) {
      written = [];
    } else if (step.stage === "test-design") {
      resumedHandback = committedStageKeys.has("test-design-handback") && editRetries === 0;
      if (resumedHandback) { resumedHandback = await recoverHandbackIds(allAcsWritten, authoringWorktreePath); }
      written = [...allAcsWritten];
      designOutcome = await dispatchTestDesign(step.agent, allAcsWritten, acFeedback, acStoreDir, authoringWorktreePath, scriptStepAgentId, resumedHandback);
    } else {
      // Dispatch the authoring agent, directing AC writes to the dedicated
      // authoring worktree's AC store path (AC BO-1500a-1).
      stepResult = await agent(
        workingLocationNote +
        `You are running as part of the /plan-feature pipeline (route: ${effectiveRoute}). ` +
        (acFeedback
          ? `The user reviewed your previous attempt and requested changes — address this feedback: ${acFeedback}. `
          : "") +
        `Write AC YAML files ONLY to ${acStoreDir}. ` +
        "Do NOT write AC files to docs/acceptance-criteria/ relative to the current checkout — " +
        `use the absolute path ${acStoreDir} instead. ` +
        "Do NOT create or modify any files in tickets/. " +
        "After writing, return a JSON object: { \"status\": \"ok\", \"acs_written\": [\"ACD-...\", ...] }\n" +
        // Why the flow to BA handoff: docs/reference/plan-feature-workflow-rationale-helpers.md
        (step.stage === "ba" && ptFlowProduced
          ? "A product-truth flow was approved for this request" +
            (ptFlowRef ? ` (${ptFlowRef})` : "") +
            ". Derive the L2/L3 ACs FROM THE FLOW'S STEPS. The flow is self-discoverable via " +
            "docs/product-truth/index.json — rely on that discovery, not a passed flow_ref. " +
            "ALSO return a flow_backlinks map in your JSON response: " +
            "{ \"<flow step id>\": [\"<AC id>\", ...] } linking each flow step to the AC ids you derived from it. " +
            // Why the flow-derived parenting rule: docs/reference/plan-feature-workflow-rationale-helpers.md
            (parent_l1_id
              ? `Parent every flow-derived L2/L3 under the run's L1 ${JSON.stringify(parent_l1_id)} so none is orphaned. `
              : `Anchor the derived L2s under the L1 for component ${JSON.stringify(ptComponent)} so they are not orphaned — ` +
                `this run has no triage L1 (parent_l1_id is null), so on the strategic route use the L1 the ` +
                `product-owner authored earlier in this run, otherwise use the flow's covering L1 (via index.json by_component). ` +
                `Do NOT leave any flow-derived AC without an L1 parent; if no component L1 exists, report the missing L1 rather than orphaning the ACs. `) +
            "\n"
          : "") +
        `user_request: ${JSON.stringify(request)}\n` +
        `component: ${JSON.stringify(component)}\n` +
        `parent_l1_id: ${JSON.stringify(parent_l1_id)}\n` +
        `route: ${JSON.stringify(effectiveRoute)}\n` +
        (step.stage === "itpo" && _amendIds.length > 0 ? `amend_acs: ${JSON.stringify(_amendIds)}\nThese existing records already cover the request: amend them (edit those records) rather than authoring new ones.\n` : "") +
        `ac_store_path: ${JSON.stringify(acStoreDir)}`,
        { agentType: step.agent, label: `stage-${step.stage}-author` }
      );

      // Tolerant parse: the authoring agent may return a JSON STRING; read fields
      // off the parsed object so acs_written/flow_backlinks aren't silently dropped.
      let stepResultObj;
      try {
        stepResultObj = parseAgentJson(stepResult, { stage: `stage-${step.stage}-author`, agent: step.agent });
      } catch (_stepResultParseErr) {
        stepResultObj = {};
      }
      written = (stepResultObj && stepResultObj.acs_written) ? stepResultObj.acs_written : [];
      allAcsWritten.push(...written);

      // Capture the BA's reported flow_backlinks for the post-BA reconciliation step.
      if (step.stage === "ba" && stepResultObj && stepResultObj.flow_backlinks && typeof stepResultObj.flow_backlinks === "object") {
        baFlowBacklinks = stepResultObj.flow_backlinks;
      }
    }

    // ACD-2500a-1: rule check at stage end (resume path: run after the gate).
    let ruleCheck = skipAuthorOnResume ? null : ((designOutcome && designOutcome.ruleCheck) || await runRuleCheck(step.stage, acStoreDir, authoringWorktreePath, scriptStepAgentId));
    // Present gate to the user. ADR-024: resolveGate checks args.resume_answer first.
    if (step.gate !== "final") {
      const _midGateResult = (step.gate === "auto" || (reapprove && !ruleCheck.passed)) ? { action: "approve" } : await resolveGate(
        `gate-${step.stage}`,
        async () => {
          const raw = await agent(
            `${step.agent} has written the following ACs: ${written.join(", ") || "(none)"}.\n` + (ruleCheck ? ruleCheck.summary + "\n" : "") +
            "Present these to the user and ask them to choose:\n" +
            "  1. approve — proceed to the next stage.\n" +
            "  2. edit    — re-invoke this agent with feedback.\n" +
            "  3. cancel  — abort the pipeline (ACs remain as drafts).\n" +
            "Return ONLY a JSON object: { \"action\": \"approve\" | \"edit\" | \"cancel\", \"feedback\": \"...\" }",
            { agentType: "status-checker", label: `gate-${step.stage}` }
          );
          let parsed;
          try {
            parsed = parseAgentJson(raw, { stage: `gate-${step.stage}`, agent: "status-checker" });
          } catch (_) {
            parsed = null;
          }
          return (parsed && typeof parsed.action === "string") ? parsed : null;
        },
        reapprove ? { ...args, resume_answer: null } : args,
        { stage: step.stage, acs: written, rule_check: ruleCheck && ruleCheck.summary },
        { type: "single_choice", options: ["approve", "edit", "cancel"] },
        args.run_id || "default-run"
      );
      if (_midGateResult && TERMINAL_GATE_STATUSES.includes(_midGateResult.status)) {
        return _midGateResult;
      }
      if (!_midGateResult) {
        return {
          status: "undetermined",
          message:
            `The confirmation gate after ${step.agent} returned no usable ` +
            `answer, so no decision was recorded. This is a gate failure, NOT a ` +
            `user cancellation. Committed ACs are preserved and drafted ACs are ` +
            `left on disk — re-run /plan-feature and answer the gate.`,
          stage: `gate-${step.stage}`,
          committed_acs: committedAcs,
          acs_as_drafts: written,
        };
      }
      const gateDecision = _midGateResult;
      // Why recovering AC ids at the mid gate (ACD-2100c-3): docs/reference/plan-feature-workflow-rationale-gates.md
      if (skipAuthorOnResume && gateDecision._resumedContext && Array.isArray(gateDecision._resumedContext.acs)) {
        written = gateDecision._resumedContext.acs;
        allAcsWritten.push(...written);
      }

      ruleCheck = ruleCheck || await runRuleCheck(step.stage, acStoreDir, authoringWorktreePath, scriptStepAgentId);
      let action = gateDecision.action.toLowerCase();
      if (!ruleCheck.passed && action !== "cancel") { gateDecision.feedback = (action === "edit" && gateDecision.feedback ? gateDecision.feedback + "\n" : "") + ruleCheck.summary; if (action !== "edit") reapprove = true; action = "edit"; skipAuthorOnResume = false; }

      if (action === "cancel") {
        // AC BO-1500c-1-i — NO-PR GUARANTEE (mid-pipeline cancel).
        const cancelLabel = `gate after ${step.agent}`;
        // Why a cancel is distinct from success (BO-2300a-2, ACD-2100c-5): docs/reference/plan-feature-workflow-rationale-gates.md
        return {
          status: "cancelled",
          cancelled_at: `gate-${step.stage}`,
          cancelled_by: "person",
          message: buildCancelMessage(committedAcs, written, cancelLabel, acStoreDir, authoringWorktreePath, ruleCheck && ruleCheck.report && ruleCheck.report.records_to_commit),
          committed_acs: committedAcs,
          acs_as_drafts: written,
        };
      } else if (action === "edit" && editRetries < MAX_EDIT_RETRIES) {
        editRetries++;
        // Thread the user's edit feedback into the re-dispatched author prompt (m4).
        acFeedback = (gateDecision && typeof gateDecision.feedback === "string") ? gateDecision.feedback.trim() : ""; skipAuthorOnResume = false;
        continue;
      } else if (action === "edit" && editRetries >= MAX_EDIT_RETRIES) {
        // Max retries exhausted — abort without committing the draft.
        return {
          status: "error",
          message:
            `${step.agent} failed to produce satisfactory ACs after ${MAX_EDIT_RETRIES + 1} attempts. Pipeline aborted.\n` +
            buildCancelMessage(committedAcs, written, `max-retries abort for ${step.agent}`, acStoreDir, authoringWorktreePath, ruleCheck.report.records_to_commit),
          failed_check: ruleCheck.passed ? null : ruleCheck.report,
          committed_acs: committedAcs,
          acs_as_drafts: written,
        };
      } else {
        // Why commit before the next stage: docs/reference/plan-feature-workflow-rationale-helpers.md
        const commitOutcome = await commitStageOutput(written, step.stage, component, false, runId, acStoreDir, authoringWorktreePath, ruleCheck.toCommit);
        if (commitOutcome.status === "error") {
          return {
            status: "error",
            message: formatCommitError(step.agent, step.stage, commitOutcome, allAcsWritten),
            acs_as_drafts: allAcsWritten,
          };
        }
        // Commit succeeded — record committed ACs.
        committedAcs.push(...written);
        approved = true;

        // Why the BA reconciliation commit: docs/reference/plan-feature-workflow-rationale-helpers.md
        if (step.stage === "ba" && ptFlowProduced) {
          const reconcileOutcome = await runFlowReconciliation(
            ptFlowRef, baFlowBacklinks, ptComponent, runId, ptStoreDir, authoringWorktreePath
          );
          if (reconcileOutcome.status === "error") {
            // Non-fatal: the ACs are already committed and the flow can be
            // reconciled by re-running the script. Log observably and continue.
            log(`[plan-feature][PT] flow reconciliation did not complete: ${reconcileOutcome.message}`);
          } else if (reconcileOutcome.status === "ok") {
            log("[plan-feature][PT] flow step.implements reconciled and committed.");
          }
        }
      }
    } else {
      // Final gate: IT PO v3 has enriched ACs and set readiness: reviewed.
      // ADR-024: resolveGate checks args.resume_answer before the live agent call.
      let heldPre = skipAuthorOnResume ? [] : await approvalHolds(allAcsWritten, acStoreDir, authoringWorktreePath, scriptStepAgentId);
      if (!skipAuthorOnResume) { let stopped; ({ held: heldPre, ruleCheck, stopped } = await handBackFindings(heldPre, ruleCheck, allAcsWritten, acStoreDir, authoringWorktreePath, scriptStepAgentId, (rc) => commitStageOutput(allAcsWritten, "test-design-handback", component, false, runId, acStoreDir, authoringWorktreePath, rc.toCommit), resumedHandback)); written = [...new Set(allAcsWritten)]; if (stopped) { return { status: "error", message: stopped, stage: "itpo-handback", committed_acs: committedAcs, acs_as_drafts: written }; } }
      const approvablePre = allAcsWritten.filter((id) => !heldPre.some((h) => h.id === id));
      const _finalGateResult = (reapprove && !ruleCheck.passed) ? { action: "approve" } : await resolveGate(
        "final-gate",
        async () => {
          const raw = await agent(
            `The test design is ready for these ACs: ${written.join(", ") || allAcsWritten.join(", ")}.\n` + (ruleCheck ? ruleCheck.summary + "\n" : "") +
            `Offer for approval ONLY: ${approvablePre.join(", ") || "(none)"}. Show each one with its criteria next to its test_spec (name, proves_clause, code_file).\n` +
            `HELD, listed separately with the reason and NO approve option: ${heldPre.map((h) => h.id + " (" + h.reason + ")").join(", ") || "(none)"}.\n` +
            "Ask the user to:\n" +
            "  1. Set a priority: critical / high / medium / low\n" +
            "  2. Choose an action: approve (set readiness: approved + priority) | edit | defer (leave as reviewed) | cancel (abort; leave this stage's ACs as uncommitted drafts)\n" +
            "Return ONLY a JSON object: { \"action\": \"approve\" | \"edit\" | \"defer\" | \"cancel\", \"priority\": \"high\" | \"medium\" | \"low\" | \"critical\" }",
            { agentType: "status-checker", label: "final-gate" }
          );
          let parsed;
          try {
            parsed = parseAgentJson(raw, { stage: "final-gate", agent: "status-checker" });
          } catch (_) {
            parsed = null;
          }
          return (parsed && typeof parsed.action === "string") ? parsed : null;
        },
        reapprove ? { ...args, resume_answer: null } : args,
        { stage: "final", acs: written, all_acs: allAcsWritten, rule_check: ruleCheck && ruleCheck.summary, held: heldPre, approvable: approvablePre },
        { type: "priority_choice", options: ["approve", "edit", "defer", "cancel"], prompt: "Final gate (test design). Show each approvable requirement: its criteria next to its test_spec, with its assigned_agent, estimated_complexity, delivers_to and expects_from; list held requirements separately with no approve option. Ask for one batch priority (critical / high / medium / low), then approve | edit | defer | cancel.\nApprovable: " + (approvablePre.join(", ") || "(none)") + heldPre.map((h) => "\nHeld, no approve option: " + h.id + " (" + h.reason + ")").join("") },
        args.run_id || "default-run"
      );
      // Non-proceed outcomes: exit immediately.
      if (_finalGateResult && TERMINAL_GATE_STATUSES.includes(_finalGateResult.status)) {
        return _finalGateResult;
      }
      // Why a falsy gate result fails CLOSED (ACD-2100c-2/-5): docs/reference/plan-feature-workflow-rationale.md
      if (!_finalGateResult) {
        return {
          status: "undetermined",
          message:
            "The final gate (test-design stage) returned no usable answer, so " +
            "no decision was recorded. This is a gate failure, NOT a user " +
            "cancellation. Committed ACs are preserved and drafted ACs are " +
            "left on disk -- re-run /plan-feature and answer the gate.",
          stage: "final-gate",
          committed_acs: committedAcs,
          acs_as_drafts: written,
        };
      }
      const finalDecision = _finalGateResult;
      // Why recovering AC ids at the final gate (ACD-2100c-3): docs/reference/plan-feature-workflow-rationale-gates.md
      if (skipAuthorOnResume && finalDecision._resumedContext) {
        if (Array.isArray(finalDecision._resumedContext.acs)) {
          written = finalDecision._resumedContext.acs;
        }
        // Why all_acs is merged with de-duplication (H-2): docs/reference/plan-feature-workflow-rationale-gates.md
        if (Array.isArray(finalDecision._resumedContext.all_acs)) {
          for (const _resumedAcId of finalDecision._resumedContext.all_acs) {
            if (!allAcsWritten.includes(_resumedAcId)) {
              allAcsWritten.push(_resumedAcId);
            }
          }
        }
      }

      ruleCheck = ruleCheck || await runRuleCheck(step.stage, acStoreDir, authoringWorktreePath, scriptStepAgentId);
      let finalAction = finalDecision.action.toLowerCase();
      if (!ruleCheck.passed && finalAction !== "cancel") { acFeedback = ruleCheck.summary; if (finalAction !== "edit") reapprove = true; finalAction = "edit"; skipAuthorOnResume = false; }
      const priority = VALID_PRIORITIES.includes(finalDecision.priority)
        ? finalDecision.priority
        : "medium";

      if (finalAction === "cancel") {
        // Why the final-gate cancel attribution: docs/reference/plan-feature-workflow-rationale-helpers.md
        return {
          status: "cancelled",
          cancelled_at: "final-gate",
          cancelled_by: "person",
          message: buildCancelMessage(committedAcs, written, "final gate (test design)", acStoreDir, authoringWorktreePath, ruleCheck.report.records_to_commit),
          committed_acs: committedAcs,
          acs_as_drafts: written,
        };
      } else if (finalAction === "edit" && editRetries < MAX_EDIT_RETRIES) {
        editRetries++;
        acFeedback = [typeof finalDecision.feedback === "string" ? finalDecision.feedback.trim() : "", ruleCheck.passed ? "" : acFeedback].filter((s) => s).join("\n"); skipAuthorOnResume = false; // BO-2300d-1-iii: the person's feedback first
        continue;
      } else if (finalAction === "edit" && editRetries >= MAX_EDIT_RETRIES) {
        return {
          status: "error",
          message:
            `test-design failed to produce satisfactory ACs after ${MAX_EDIT_RETRIES + 1} attempts. Pipeline aborted.\n` +
            buildCancelMessage(committedAcs, written, "max-retries abort for test-design (final gate)", acStoreDir, authoringWorktreePath, ruleCheck.report.records_to_commit),
          failed_check: ruleCheck.passed ? null : ruleCheck.report,
          committed_acs: committedAcs,
          acs_as_drafts: written,
        };
      } else if (finalAction === "defer") {
        return {
          status: "ok",
          message: "ACs left as reviewed (deferred). Re-run /plan-feature to approve.",
          acs_as_reviewed: allAcsWritten,
        };
      } else if (finalAction === "approve") {
        // Why a failed step stops before the commit (ACD-300c-4-ii): docs/reference/plan-feature-workflow-rationale-gates.md
        const approval = await approveBatch(allAcsWritten, priority, acStoreDir, authoringWorktreePath, scriptStepAgentId);
        if (!approval.ok) {
          const gotIds = approval.approved || [], failedIds = approval.failed || [], untouchedIds = approval.untouched || allAcsWritten;
          return {
            status: "error", route: effectiveRoute, acs_approved: gotIds, acs_failed: failedIds, acs_untouched: untouchedIds,
            acs_as_reviewed: allAcsWritten.filter((id) => !gotIds.includes(id)),
            message: "Approval failed and nothing was committed.\nApproved before the failure (still approved on disk): " + (gotIds.join(", ") || "none") +
              "\nFailed: " + (failedIds.join(", ") || "none") + "\nUntouched: " + (untouchedIds.join(", ") || "none") + "\n" + approval.why,
          };
        }

        // Commit the final IT PO enriched AC output before reporting success.
        const finalCommitOutcome = await commitStageOutput(written, step.stage, component, true, runId, acStoreDir, authoringWorktreePath, ruleCheck.toCommit);
        if (finalCommitOutcome.status === "error") {
          return {
            status: "error",
            message: formatCommitError("test-design", step.stage, finalCommitOutcome, allAcsWritten),
            acs_updated: allAcsWritten,
            priority,
            route: effectiveRoute,
          };
        }

        approved = true;
        stageResults.push({ stage: step.stage, agent: step.agent, acs: written });

        // Why the delivery step: docs/reference/plan-feature-workflow-rationale-helpers.md
        const authoringBranch = typeof authoringWorkspace.answer.branch === "string" ? authoringWorkspace.answer.branch : null;
        let deliveryOutcome = { status: "skipped", message: "No authoring branch available — push manually." };

        if (authoringBranch && authoringWorktreePath) {
          deliveryOutcome = await deliverAuthoringBranch(
            authoringBranch,
            authoringWorktreePath,
            allAcsWritten,
            component,
            priority
          );
        }

        const deliveryOk = deliveryOutcome.status === "ok";
        const prUrl = deliveryOutcome.pr_url || null;

        // AC BO-1500d-1: Extract the PR number from the URL.
        const prNumber = extractPrNumber(prUrl);
        const prSummary = deliveryOk
          ? (prNumber && prUrl
              ? `Pull request opened: PR #${prNumber}\n${prUrl}`
              : `Authoring branch pushed and PR opened: ${prUrl || authoringBranch}`)
          : `Delivery warning: ${deliveryOutcome.message} — Push '${authoringBranch}' and open a PR to main manually.`;

        return {
          status: "ok",
          message:
            `/plan-feature complete. ${approval.approved.length} approved, ${approval.held.length} held (priority: ${priority})` +
            (approval.already.length ? `; ${approval.already.length} already approved` : "") + approval.held.map((h) => `\nHeld ${h.id}: ${h.reason}`).join("") + "\n" + prSummary,
          acs_approved: approval.approved, held: approval.held,
          priority,
          route: effectiveRoute,
          authoring_branch: authoringBranch,
          pr_url: prUrl,
          pr_number: prNumber,
          delivery_status: deliveryOutcome.status,
        };
      } else {
        // Terminal else: unrecognized finalAction — abort immediately without committing.
        return {
          status: "error",
          message:
            `Final gate returned unrecognized action: ${JSON.stringify(finalAction)}. Pipeline aborted without committing.\n` +
            buildCancelMessage(committedAcs, written, "final gate (unrecognized action)", acStoreDir, authoringWorktreePath, ruleCheck.report.records_to_commit),
          committed_acs: committedAcs,
          acs_as_drafts: written,
        };
      }
    }
  }

  stageResults.push({ stage: step.stage, agent: step.agent, acs: stepResult?.acs_written || [] });
}

// Should not reach here (final gate returns inline)
return {
  status: "ok",
  message: "Pipeline complete.",
  acs_written: allAcsWritten,
  route: effectiveRoute,
};

// DECISION HISTORY: moved to docs/reference/plan-feature-workflow-rationale.md
