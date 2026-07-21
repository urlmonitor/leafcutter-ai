/**
 * plan-feature.js — Claude Code Workflow script
 *
 * Implements the /plan-feature command: triages the user's request via the
 * ac-triage agent (Haiku-tier, fast), routes to the correct AC authoring
 * agents (product-owner, business-analyst, it-po) in sequence with
 * user confirmation gates between stages, and writes all output exclusively
 * to the AC store (docs/acceptance-criteria/). No ticket files are produced.
 *
 * Routing table (matches ac-triage classification):
 *   strategic  → PO v3 → gate → BA v3 → gate → IT PO v3 → final gate
 *   behavioral → BA v3 → gate → IT PO v3 → final gate
 *   technical  → IT PO v3 → final gate
 *   covered    → show matching ACs → prompt cancel / amend / force
 *
 * Architecture:
 *   Stage 0: ac-triage agent (Haiku-pinned, reads AC store, classifies route)
 *   Stage 1–N: authoring agents dispatched in sequence per route
 *   Gates: user confirm/edit/cancel between each stage
 *   Final gate: user sets priority; workflow writes readiness: approved
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

// ---------------------------------------------------------------------------
// JSON Schemas for structured agent() responses
// ---------------------------------------------------------------------------

/** Maximum retry count for a single authoring agent on edit-path. */
const MAX_EDIT_RETRIES = 1;

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
 * @returns {Promise<{ status: "ok"|"error", message: string, hook_name?: string|null, failing_files?: string[], is_conflict?: boolean }>}
 */
async function commitStageOutput(written, stageName, component, isFinal, runId, acStorePath, authoringWorktreePath) {
  acStorePath = acStorePath || "docs/acceptance-criteria";
  // Build the git -C anchor for all git operations in this function. (AC BO-1500a-2)
  const gitC = authoringWorktreePath ? `-C "${authoringWorktreePath}"` : "";
  const stageLabel = stageDisplayName(stageName);

  // ---------------------------------------------------------------------------
  // AC BO-1500c-3 — NO-MAIN-COMMIT DEFENSIVE GUARD (fail-CLOSED)
  //
  // Always run the branch check, regardless of whether authoringWorktreePath
  // is set. When null, use `git branch --show-current` without -C.
  // ALL failure paths abort the commit — cannot risk committing to main or
  // an unconfirmable branch.
  // ---------------------------------------------------------------------------
  {
    let branchConfirmed = false;
    let branchCheckError = "unknown error during branch check";

    // Build git command: with -C if worktree path is known; bare otherwise.
    const branchCheckCmd = authoringWorktreePath
      ? `git -C "${authoringWorktreePath}" branch --show-current`
      : `git branch --show-current`;

    try {
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

  // Build a JSON-safe representation of the AC IDs so the agent can filter on them.
  const writtenJson = JSON.stringify(written);

  let commitResult;
  try {
    commitResult = await agent(
      `Stage and commit the AC YAML files produced by the ${stageName} stage.\n` +
      "\n" +
      `The AC IDs written by this stage are: ${writtenJson}\n` +
      `The commit message to use is: ${commitMessage}\n` +
      "\n" +
      (authoringWorktreePath
        ? `ISOLATION RULE (AC BO-1500a-2): ALL git commands in this task MUST use the\n` +
          `'-C "${authoringWorktreePath}"' flag so they operate inside the dedicated authoring\n` +
          `worktree and NEVER in the original checkout or any other worktree.\n\n`
        : "") +
      `IMPORTANT STAGING RULE: You MUST stage ONLY the files that correspond to the\n` +
      `AC IDs listed above. Never run 'git ${gitC} add ${acStorePath}' or\n` +
      `'git ${gitC} add .' — those commands would include files from previous stages or\n` +
      `unrelated working-tree changes, which is a correctness violation.\n` +
      `\n` +
      `Step 1 — Discover which AC files from this stage exist on disk:\n` +
      `  Run: git ${gitC} status --porcelain --untracked-files=all -- ${acStorePath}/\n` +
      "  (The --untracked-files=all flag is required so that files inside a\n" +
      "  previously-untracked subfolder are emitted individually rather than\n" +
      "  collapsed to a single directory-level '?? <dir>/' line. Without it,\n" +
      "  a fresh AC store is silently skipped.)\n" +
      "  Parse the output. Each line has the format: XY <path>\n" +
      "  where XY is a two-character status code. For rename lines the format is:\n" +
      "  R  old-path -> new-path — extract the NEW path (the part after '-> ').\n" +
      "  Collect ALL lines where the path ends in '.yaml' and the status is not\n" +
      "  '  ' (i.e. it is modified or untracked — status codes: M, A, R, ??, etc.).\n" +
      "  From those paths, keep only the ones whose filename stem (the portion\n" +
      "  after the last '/' and before '.yaml') is exactly equal to one of the\n" +
      "  AC IDs above. The stem must match exactly — not merely share a prefix.\n" +
      "  For example, ACD-300g.yaml must NOT match ACD-300 (stems must be\n" +
      "  identical, not merely prefix-equal; ACD-300g !== ACD-300).\n" +
      "  These are the stage-specific files to stage.\n" +
      "\n" +
      "Step 2 — If no matching files are found:\n" +
      "  Return: { \"status\": \"ok\", \"message\": \"no new AC files to commit — skipped\" }\n" +
      "\n" +
      "Step 3 — Stage each matching file individually:\n" +
      "  For each file path found in Step 1, run:\n" +
      `    git ${gitC} add <path>\n` +
      `  Run one 'git ${gitC} add' command per file. Do NOT use 'git ${gitC} add .' or\n` +
      `  'git ${gitC} add ${acStorePath}/' — only individual explicit paths.\n` +
      `  If any 'git ${gitC} add <path>' exits non-zero:\n` +
      "    Return: { \"status\": \"error\", \"message\": \"git add failed for <path>\", \"hook_name\": null, \"failing_files\": [\"<path>\"], \"is_conflict\": false }\n" +
      "\n" +
      "Step 4 — Verify only the expected files are staged:\n" +
      `  Run: git ${gitC} diff --cached --name-only\n` +
      "  If the output is empty (nothing staged despite Step 3 succeeding):\n" +
      "    Return: { \"status\": \"ok\", \"message\": \"no new AC files to commit — skipped\" }\n" +
      "\n" +
      "Step 5 — Commit the staged files using the commit agent's standard flow.\n" +
      "  The commit message has already been provided above. Use it exactly.\n" +
      "  After committing, capture the exit code and output.\n" +
      "  If exit code is 0:\n" +
      "    Return: { \"status\": \"ok\", \"message\": \"committed successfully\" }\n" +
      "  If exit code is non-zero:\n" +
      "    Analyse the combined output to build a structured error:\n" +
      "\n" +
      "    a) Conflict detection:\n" +
      "       If the output contains the word 'conflict' (case-insensitive),\n" +
      "       extract any file paths mentioned (lines matching docs/ or .yaml/.yml\n" +
      "       patterns, or lines after 'CONFLICT (' markers).\n" +
      "       Return: {\n" +
      "         \"status\": \"error\",\n" +
      "         \"message\": \"index conflict detected\",\n" +
      "         \"hook_name\": null,\n" +
      "         \"failing_files\": [<extracted conflict file paths>],\n" +
      "         \"is_conflict\": true\n" +
      "       }\n" +
      "\n" +
      "    b) Pre-commit hook failure:\n" +
      "       Look for lines containing 'hook' (e.g. 'hook: ...' or '- hook-name').\n" +
      "       Extract the first hook name you can identify, or null if none found.\n" +
      "       Collect file paths from the output: any token matching\n" +
      "         docs/acceptance-criteria/**.yaml or similar path patterns.\n" +
      "       Return: {\n" +
      "         \"status\": \"error\",\n" +
      "         \"message\": \"pre-commit hook rejected staged files\",\n" +
      "         \"hook_name\": \"<hook name or null>\",\n" +
      "         \"failing_files\": [<file paths from error output>],\n" +
      "         \"is_conflict\": false\n" +
      "       }\n" +
      "\n" +
      "    c) Generic failure (no hook or conflict pattern found):\n" +
      "       Return: {\n" +
      "         \"status\": \"error\",\n" +
      "         \"message\": \"git commit failed\",\n" +
      "         \"hook_name\": null,\n" +
      "         \"failing_files\": [],\n" +
      "         \"is_conflict\": false\n" +
      "       }\n" +
      "\n" +
      "  IMPORTANT: Do NOT retry the commit. Do NOT run git commit --no-verify.\n" +
      "  Do NOT run git add again. Leave all AC files as uncommitted changes on disk.",
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

  let result;
  try {
    result = parseAgentJson(commitResult, { stage: "commit-stage-output", agent: "commit" });
  } catch (_parseErr) {
    // If the agent returned non-JSON, treat as failure — an unparseable result
    // means we cannot confirm the commit succeeded (fail-closed per ACD-300g-1-i).
    result = { status: "error", message: "commit result unparseable — cannot confirm success", hook_name: null, failing_files: [], is_conflict: false };
  }

  return result || { status: "error", message: "no result returned by agent", hook_name: null, failing_files: [], is_conflict: false };
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
 * @returns {string} Formatted exit message for the user.
 */
function buildCancelMessage(committedAcs, draftAcs, cancelledAt, acStorePath, authoringWorktreePath) {
  const store = acStorePath || "docs/acceptance-criteria";
  // Use the -C anchor in user-facing git instructions so cleanup targets the authoring worktree. (AC BO-1500a-2)
  const gitC = authoringWorktreePath ? `-C "${authoringWorktreePath}"` : "";
  const gitCheckoutCmd = `git ${gitC} checkout -- ${store}/`.trim();
  const draftFilePaths = draftAcs.map(
    (id) => `  ${store}/${id}.yaml`
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
    ? `git -C "${authoringWorktreePath}" status --porcelain --untracked-files=all -- ${acStoreDir}`
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

    // Resolve the file path against the authoring worktree root.
    const resolvedFilePath = authoringWorktreePath
      ? authoringWorktreePath.replace(/\/$/, "") + "/" + filePath.replace(/^\//, "")
      : filePath;

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
    if (!AUTHORING_AGENTS.has(originAgent)) { continue; }
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
  const gitC = authoringWorktreePath ? `git -C "${authoringWorktreePath}"` : "git";
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
      `    Run the REST API call:\n` +
      `      gh api -X POST repos/<org>/<repo>/pulls \\\n` +
      `        -f title="${prTitle.replace(/"/g, '\\"')}" \\\n` +
      `        -f head="${authoringBranch}" \\\n` +
      `        -f base="main" \\\n` +
      `        -f body="${prBody.replace(/"/g, '\\"').replace(/\n/g, "\\n")}"\n` +
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
    ? `git -C "${authoringWorktreePath}" log --oneline origin/main..HEAD`
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

  // Display name → internal stage key mapping (inverse of stageDisplayName()).
  // Keyed on the LOWERCASED display name (the subject scan lowercases below), so
  // "MOCK-DATA" → "mock-data" → "mockdata", "MOCKUP" → "mockup", "FLOW" → "flow".
  const displayToKey = {
    "po": "po",
    "ba": "ba",
    "it-po": "itpo",
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
 * Presents the user with a yes/no/discard choice.
 *
 * @param {Array<{filePath: string, acId: string}>} orphans - Orphan list from scanOrphanedAcDrafts().
 * @param {string}      acStoreDir          - AC store directory path.
 * @param {string}      runId               - Current run id (for commit message).
 * @param {string|null} authoringWorktreePath - Absolute path to the dedicated authoring worktree.
 * @returns {Promise<{action: "continue"|"abort"}>} "continue" to proceed to Stage 0; "abort" to exit.
 */
async function resolveOrphanedDrafts(orphans, acStoreDir, runId, authoringWorktreePath) {
  // Build a git command prefix helper.
  const gitCmd = authoringWorktreePath
    ? (sub) => `git -C "${authoringWorktreePath}" ${sub}`
    : (sub) => `git ${sub}`;
  const acIds = orphans.map((o) => o.acId).sort();
  const N = orphans.length;
  const acIdList = acIds.join(", ");

  // Present the user with the three-way choice.
  let userChoice;
  try {
    const choiceResult = await agent(
      `Found ${N} uncommitted AC file${N !== 1 ? "s" : ""} from a prior session: [${acIdList}]. ` +
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
      parsed = parseAgentJson(choiceResult, { stage: "resolve-orphans-choice", agent: "status-checker" });
    } catch (_parseErr) {
      parsed = null;
    }
    userChoice = (parsed && parsed.choice) ? parsed.choice.toLowerCase().trim() : "no";
  } catch (_choiceErr) {
    // Cannot parse choice — default to "no" (safe-abort).
    userChoice = "no";
  }

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
      authoringWorktreePath
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

// ===========================================================================
// PRODUCT-TRUTH (PT) PHASE HELPERS
//
// The PT phase runs on every invocation (always-on) between ac-triage and the
// AC authoring pipeline. It dispatches pt-classifier, derives the run-set from
// the classifier OUTCOME (never the dispatch array), then drafts the required
// product-truth artifacts (mock data → mockups → flow) each behind a user gate,
// committing each approved stage surgically. See ADR (always-on PT phase).
// ===========================================================================

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
  const root = authoringWorktreePath ? authoringWorktreePath.replace(/\/$/, "") + "/" : "";
  const storeDir = root + ptStorePath;
  const genScript = root + ptStorePath + "/scripts/generate_product_truth.py";
  const reconcileScript = root + ptStorePath + "/scripts/apply_flow_backlinks.py";
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
 * status-checker to append one JSON line to debugging/logs/agent_telemetry.jsonl.
 * Best-effort: never throws, never blocks the pipeline. This is the "never
 * silent" guarantee for the store-absent self-skip.
 *
 * @param {string}      event                 - Short event key (e.g. "pt_phase_skipped_store_absent").
 * @param {object}      detail                - JSON-serialisable detail payload.
 * @param {string|null} authoringWorktreePath - Absolute path to the authoring worktree.
 * @returns {Promise<void>}
 */
async function emitPtTelemetry(event, detail, authoringWorktreePath) {
  log(`[plan-feature][PT] ${event}: ${JSON.stringify(detail)}`);
  const root = authoringWorktreePath ? authoringWorktreePath.replace(/\/$/, "") + "/" : "";
  const logPath = root + "debugging/logs/agent_telemetry.jsonl";
  const line = JSON.stringify({ source: "plan-feature", phase: "product-truth", event, detail });
  try {
    await agent(
      `Append exactly one line to a telemetry log (create the directory if needed).\n` +
      `Run: mkdir -p "${root}debugging/logs" && printf '%s\\n' ${JSON.stringify(line)} >> "${logPath}"\n` +
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
  const gitC = authoringWorktreePath ? `-C "${authoringWorktreePath}"` : "";
  const stageLabel = stageDisplayName(stageName);

  // -------------------------------------------------------------------------
  // NO-MAIN-COMMIT DEFENSIVE GUARD (fail-CLOSED) — mirrors commitStageOutput.
  // -------------------------------------------------------------------------
  {
    let branchConfirmed = false;
    let branchCheckError = "unknown error during branch check";
    const branchCheckCmd = authoringWorktreePath
      ? `git -C "${authoringWorktreePath}" branch --show-current`
      : `git branch --show-current`;

    try {
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
  const pathsJson = JSON.stringify(pathsToStage);

  let commitResult;
  try {
    commitResult = await agent(
      `Stage and commit the product-truth artifacts produced by the ${stageName} stage.\n` +
      "\n" +
      `The EXACT paths to stage (artifact + its regenerated derived files + the store index) are:\n` +
      `  ${pathsJson}\n` +
      `The commit message to use is: ${commitMessage}\n` +
      "\n" +
      (authoringWorktreePath
        ? `ISOLATION RULE: ALL git commands in this task MUST use the '-C "${authoringWorktreePath}"'\n` +
          `flag so they operate inside the dedicated authoring worktree and NEVER in another checkout.\n\n`
        : "") +
      `SURGICAL STAGING RULE (correctness-critical): stage ONLY the explicit paths listed above.\n` +
      `  - NEVER run 'git ${gitC} add ${ptStorePath}' or 'git ${gitC} add ${ptStorePath}/' or 'git ${gitC} add .'\n` +
      `    — a wholesale add would sweep unrelated derived churn into this commit.\n` +
      `  - NEVER stage anything under docs/acceptance-criteria/ — the AC store is a SEPARATE commit surface.\n` +
      "\n" +
      "Step 1 — Stage each listed path individually (skip any that do not exist on disk):\n" +
      `  For each path P in the list above, run: git ${gitC} add "P"\n` +
      `  If a 'git ${gitC} add' for a path that DOES exist exits non-zero:\n` +
      "    Return: { \"status\": \"error\", \"message\": \"git add failed for <path>\", \"hook_name\": null, \"failing_files\": [\"<path>\"], \"is_conflict\": false }\n" +
      "\n" +
      "Step 2 — Verify staging is surgical:\n" +
      `  Run: git ${gitC} diff --cached --name-only\n` +
      "  Confirm every staged path is one of the listed paths and NONE is under docs/acceptance-criteria/.\n" +
      "  If nothing is staged: Return { \"status\": \"ok\", \"message\": \"no product-truth files to commit — skipped\" }\n" +
      "\n" +
      "Step 3 — Commit the staged files using the commit agent's standard flow with the message above.\n" +
      "  If exit code is 0: Return { \"status\": \"ok\", \"message\": \"committed successfully\" }\n" +
      "  If non-zero, analyse the output:\n" +
      "    a) 'conflict' (case-insensitive) → { \"status\": \"error\", \"message\": \"index conflict detected\", \"hook_name\": null, \"failing_files\": [<paths>], \"is_conflict\": true }\n" +
      "    b) hook failure → { \"status\": \"error\", \"message\": \"pre-commit hook rejected staged files\", \"hook_name\": \"<hook or null>\", \"failing_files\": [<paths>], \"is_conflict\": false }\n" +
      "    c) generic → { \"status\": \"error\", \"message\": \"git commit failed\", \"hook_name\": null, \"failing_files\": [], \"is_conflict\": false }\n" +
      "\n" +
      "  IMPORTANT: Do NOT retry. Do NOT run git commit --no-verify. Leave files as uncommitted changes on disk.",
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

  let result;
  try {
    result = parseAgentJson(commitResult, { stage: "commit-stage-output-product-truth", agent: "commit" });
  } catch (_parseErr) {
    result = { status: "error", message: "product-truth commit result unparseable — cannot confirm success", hook_name: null, failing_files: [], is_conflict: false };
  }

  return result || { status: "error", message: "no result returned by agent", hook_name: null, failing_files: [], is_conflict: false };
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
    ? `git -C "${authoringWorktreePath}" log --name-only --format=%H%x00%s origin/main..HEAD`
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
    // Parse per-commit by scanning lines. Real `git log --name-only
    // --format=%H%x00%s` output is: a header line `<hash>\x00<subject>`, a BLANK
    // line, then the commit's file list — with NO blank line between one commit's
    // last file and the next commit's header. A blank-line split therefore
    // misaligns headers and files. Instead, treat any line containing \x00 as a
    // new commit header (recording its subject) and collect the subsequent
    // non-empty lines as that commit's files until the next header. Return the
    // first *.flow.json belonging to a commit whose subject matches the FLOW stage.
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
 * data, then commit the flow + index + affected ACs as a DEDICATED
 * reconciliation commit (it re-mutates already-committed files, so it cannot be
 * folded into a stage commit).
 *
 * Runs `docs/product-truth/scripts/apply_flow_backlinks.py` via a status-checker
 * dispatch, then commits via the commit agent (surgical: flow + index +
 * docs/acceptance-criteria — the ACs whose product_truth back-ref changed).
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

  const root = authoringWorktreePath ? authoringWorktreePath.replace(/\/$/, "") + "/" : "";
  const scriptPath = root + ptStorePath + "/scripts/apply_flow_backlinks.py";
  // flowRef is store-relative (e.g. flows/foo/bar.flow.json); resolve it for the CLI.
  const flowArg = root + ptStorePath + "/" + flowRef.replace(/^\/+/, "").replace(new RegExp("^" + ptStorePath + "/"), "");
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
  // Guard the parse: a non-JSON reconcile-run response must NOT throw out of the
  // top-level body (the ACs are already committed by this point). Reconciliation
  // is intentionally non-fatal — the caller only logs on status:error.
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

  // Step 2 — commit the reconciliation as its own commit (flow + index + affected ACs).
  const gitC = authoringWorktreePath ? `-C "${authoringWorktreePath}"` : "";
  const commitMessage =
    `plan-feature(RECONCILE): ${component || "unknown-component"}\n\nrun-id: ${runId}\nflow step.implements back-links + regenerated derived data`;
  const indexPath = ptStorePath + "/index.json";
  const flowStorePath = ptStorePath + "/" + flowRef.replace(/^\/+/, "").replace(new RegExp("^" + ptStorePath + "/"), "");

  try {
    const commitOut = await agent(
      `Commit the flow-backlink reconciliation as a DEDICATED commit.\n` +
      `The reconciliation script already wrote step.implements into the flow and regenerated derived data.\n` +
      `Commit message to use: ${commitMessage}\n\n` +
      (authoringWorktreePath
        ? `ISOLATION RULE: ALL git commands MUST use '-C "${authoringWorktreePath}"'.\n\n`
        : "") +
      `Step 1 — Stage the reconciled files:\n` +
      `  Run: git ${gitC} add "${flowStorePath}"\n` +
      `  Run: git ${gitC} add "${indexPath}"\n` +
      `  Then stage ONLY the changed AC files under docs/acceptance-criteria/ whose product_truth back-ref\n` +
      `  was regenerated by this reconciliation:\n` +
      `    Run: git ${gitC} status --porcelain --untracked-files=all -- docs/acceptance-criteria/\n` +
      `    For each modified '.yaml' line, run: git ${gitC} add "<path>"\n` +
      `  Do NOT run 'git ${gitC} add .' or 'git ${gitC} add ${ptStorePath}' wholesale.\n\n` +
      `Step 2 — Commit with the message above.\n` +
      `  If exit 0: Return { "status": "ok", "message": "reconciliation committed" }\n` +
      `  If non-zero: Return { "status": "error", "message": "<summary>" }`,
      { agentType: "commit", label: "commit-flow-reconciliation" }
    );
    let commitParsed;
    try {
      commitParsed = parseAgentJson(commitOut, { stage: "commit-flow-reconciliation", agent: "commit" });
    } catch (_parseErr) {
      commitParsed = null;
    }
    return commitParsed || { status: "error", message: "no result from reconciliation commit agent" };
  } catch (err) {
    return { status: "error", message: "reconciliation commit dispatch failed: " + err.message };
  }
}

// ---------------------------------------------------------------------------
// §R — Inline pause-resume helpers (ADR-024 BO-2300 RESUME half).
// E2 workflow bodies are self-contained and cannot import local modules
// (ES-module import is a SyntaxError inside the test-harness IIFE, and the
// runtime has no module access), so the pause-resume helper is defined inline
// here. The same helper is inlined in finalize-feature.js — keep them in sync.
// ---------------------------------------------------------------------------

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
  if (expectedType === "priority_choice") {
    return (answer.priority != null) ? { valid: true } : { valid: false };
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
  if (type === "priority_choice") { return { action: "approve", priority: answer.priority }; }
  if (type === "free_text") { return { action: "approve", text: answer.text }; }
  return { action: answer.action || answer.choice };
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

  // ADR-024 Rule 4: check resume_answer BEFORE liveGateFn.
  if (args && args.resume_answer && args.resume_answer.gate_id === gateId) {
    const incomingType = args.resume_answer.type || answerType;
    const validation = validateAnswerShape(args.resume_answer, incomingType, validOptions);
    if (!validation.valid) {
      // Wrong/malformed shape or action not in valid options: stay paused.
      return { status: "paused_awaiting_input", run_id: runId, gate_id: gateId };
    }
    // Shape valid: consult the durable record via agent dispatch (body has no fs access per ADR-024).
    const _readPrompt =
      "Read the durable pause record for this run. Run exactly:\n" +
      "  python scripts/pause_store.py read --run-id " + runId + "\n" +
      "Return EXACTLY its stdout JSON of the form {\"exists\":<bool>,\"stale\":<bool>,\"record\":<obj|null>}.";
    const _rawRec = await agent(_readPrompt, { agentType: "status-checker", label: "read-pause-record" });
    let recCheck;
    try {
      recCheck = (typeof _rawRec === "string")
        ? parseAgentJson(_rawRec, { stage: "read-pause-record", agent: "status-checker" })
        : _rawRec;
    } catch (_e) { recCheck = null; }
    // FAIL CLOSED: apply ONLY when exists===true AND stale is not true.
    if (!recCheck || recCheck.exists !== true) {
      return { status: "nothing_to_resume", run_id: runId, gate_id: gateId };
    }
    if (recCheck.stale === true) {
      return { status: "unresumable_stale", run_id: runId, gate_id: gateId };
    }
    return applyAnswerByType(args.resume_answer, incomingType);
  }

  // No matching resume_answer: call the live gate.
  let gateAnswer = null;
  if (typeof liveGateFn === "function") {
    try { gateAnswer = await liveGateFn(); } catch (_err) { gateAnswer = null; }
  }
  // Valid explicit decision.
  if (gateAnswer !== null && gateAnswer !== undefined && typeof gateAnswer === "object" &&
      (typeof gateAnswer.action === "string" || typeof gateAnswer.choice === "string")) {
    return gateAnswer;
  }
  // Headless or unparseable: pause and persist.
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
async function pauseAtGate(gateId, runId, ctxSnapshot, descriptor) {
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
  const context = ctxSnapshot || { gate_id: gateId };
  const rec = {
    run_id: runId, gate_id: gateId,
    question: question, context: context,
    status: "paused_awaiting_input",
  };
  const _persistPrompt =
    "Interactive gate '" + gateId + "' has no reachable human answerer. " +
    "Persist this pending-question record so the run can be resumed later. Run exactly:\n" +
    "  python scripts/pause_store.py write --run-id " + runId + " --record '" + JSON.stringify(rec) + "'\n" +
    "That writes .leafcutter/paused_runs/" + runId + ".json. Return the command's JSON stdout.";
  await agent(_persistPrompt, { agentType: "status-checker", label: "pause-persist" });
  return { status: "paused_awaiting_input", run_id: runId, gate_id: gateId };
}

// ---------------------------------------------------------------------------
// E2 top-level body — executed directly by the E2 engine
// ---------------------------------------------------------------------------

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

// -------------------------------------------------------------------------
// Pre-Stage-0 — Authoring Worktree Bootstrap (AC BO-1500a-1, BO-1500e-1).
// -------------------------------------------------------------------------

// Detect whether the user's current checkout is on main (best-effort).
let userIsOnMain = false;
try {
  const currentBranchResult = await agent(
    "Run the following command and return ONLY the raw stdout:\n" +
    "git branch --show-current\n" +
    "Return JSON: { \"output\": \"<raw stdout line>\", \"exit_code\": <number> }",
    { agentType: "status-checker", label: "detect-current-branch" }
  );
  let cbParsed;
  try {
    cbParsed = parseAgentJson(currentBranchResult, { stage: "detect-current-branch", agent: "status-checker" });
  } catch (_parseErr) {
    cbParsed = null;
  }
  if (cbParsed && cbParsed.exit_code === 0) {
    const currentBranch = (cbParsed.output || "").trim();
    if (currentBranch.toLowerCase() === "main") {
      userIsOnMain = true;
      log(
        "[plan-feature] Detected: current checkout is on protected main branch.\n" +
        "[plan-feature] The AC-authoring worktree will be created from origin/main " +
        "on a dedicated ac-authoring/ branch — your main branch will not be modified.\n" +
        "[plan-feature] No branch switch is required. Proceeding with worktree setup."
      );
    }
  }
} catch (_branchDetectErr) {
  // Cannot determine current branch — proceed normally.
}

const sessionSlug = component
  ? component.toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 20)
  : null;

let authoringWorktreePath = null;
let acStoreDir = "docs/acceptance-criteria"; // default: overridden below

let worktreeSetupResult;
try {
  worktreeSetupResult = await agent(
    "Run the following command and return ONLY the raw stdout output:\n" +
    "python scripts/setup_ticket_worktree.py create-ac-worktree" +
    (sessionSlug ? ` "${sessionSlug}"` : "") + "\n" +
    "Return JSON: { \"output\": \"<raw stdout line>\", \"exit_code\": <number>, \"stderr\": \"<stderr or empty>\" }",
    { agentType: "status-checker", label: "worktree-setup" }
  );
} catch (wtErr) {
  return {
    status: "error",
    message:
      "Failed to dispatch worktree setup: " + wtErr.message + "\n" +
      "Cannot create the dedicated AC-authoring worktree. " +
      "Resolve the issue and re-run /plan-feature.",
  };
}

let wtParsed;
try {
  wtParsed = parseAgentJson(worktreeSetupResult, { stage: "worktree-setup", agent: "status-checker" });
} catch (_parseErr) {
  wtParsed = null;
}

// Only fail-hard when exit_code is explicitly non-zero.
if (wtParsed && wtParsed.exit_code != null && wtParsed.exit_code !== 0) {
  const wtStderr = wtParsed.stderr ? wtParsed.stderr : "(no stderr captured)";
  return {
    status: "error",
    message:
      "Authoring worktree creation failed (exit code " +
      wtParsed.exit_code + ").\n" +
      wtStderr + "\n" +
      "Resolve the git error and re-run /plan-feature.",
  };
}

let wtPayload = null;
try {
  if (wtParsed && typeof wtParsed.output === "string" && wtParsed.output.trim()) {
    wtPayload = JSON.parse(wtParsed.output.trim());
  }
} catch (_parseErr) {
  // Unparseable payload — fall back to default acStoreDir.
  wtPayload = null;
}

if (wtPayload) {
  authoringWorktreePath = wtPayload.worktree_path || null;
  acStoreDir = wtPayload.ac_store_path || acStoreDir;
}

// -------------------------------------------------------------------------
// Pre-Stage-0 — Partial-Run Recovery: detect and resolve orphaned AC drafts
// -------------------------------------------------------------------------
const orphans = await scanOrphanedAcDrafts(acStoreDir, authoringWorktreePath);
if (orphans.length > 0) {
  const recoveryOutcome = await resolveOrphanedDrafts(orphans, acStoreDir, runId, authoringWorktreePath);
  if (recoveryOutcome.action === "abort") {
    return {
      status: "error",
      message: recoveryOutcome.message ||
        "Uncommitted AC files must be resolved first. Re-run /plan-feature after resolving them.",
    };
  }
}

// -------------------------------------------------------------------------
// Pre-Stage-0 — Committed-Stage Detection
// -------------------------------------------------------------------------
const committedStageKeys = await scanCommittedStages(authoringWorktreePath);

// -------------------------------------------------------------------------
// Stage 0 — ac-triage: duplicate check + route classification
// -------------------------------------------------------------------------
const triageResult = await agent(
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
  triage = parseAgentJson(triageResult, { stage: "stage-0-triage", agent: "ac-triage" });
} catch (err) {
  return {
    status: "error",
    message: `ac-triage returned unparseable output: ${err.message}. Raw: ${JSON.stringify(triageResult)}`,
  };
}

const { route, existing_acs = [], parent_l1_id = null, rationale = "" } = triage;

// -------------------------------------------------------------------------
// Handle "covered" route: show existing ACs + prompt user
// -------------------------------------------------------------------------
if (route === "covered" && !force) {
  // ADR-024: resolveGate checks args.resume_answer before the live agent call.
  const _covGateResult = await resolveGate(
    "covered-route-gate",
    async () => {
      const raw = await agent(
        "Present the following to the user and ask them to choose one option:\n\n" +
        `The request appears to already be covered by these existing ACs:\n${existing_acs.join(", ")}\n\n` +
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
    { type: "single_choice", options: ["cancel", "amend", "force"] },
    args.run_id || "default-run"
  );
  if (_covGateResult && _covGateResult.status &&
      ["paused_awaiting_input", "nothing_to_resume", "unresumable_stale"].includes(_covGateResult.status)) {
    return _covGateResult;
  }
  const userChoice = _covGateResult || { choice: "cancel" };
  const choice = (userChoice.choice || userChoice.action || "cancel").toLowerCase();

  if (choice === "cancel") {
    return {
      status: "ok",
      message: `Request is already covered by: ${existing_acs.join(", ")}. No new ACs created.`,
      covered_by: existing_acs,
    };
  }

  if (choice === "amend") {
    triage.route = "technical";
  } else {
    // force → strategic
    triage.route = "strategic";
  }
}

// -------------------------------------------------------------------------
// Product-Truth (PT) Phase — ALWAYS-ON; runs between triage and the AC pipeline.
//
// Dispatches pt-classifier, derives the run-set from the OUTCOME (never the
// `dispatch` array), self-skips (non-silent) when the store is absent, then
// drafts mock-data → mockup → flow (filtered) each behind a user gate, committing
// each approved stage surgically. `outcome:"none"` and unparseable classifier
// output fall straight through to the AC pipeline.
// -------------------------------------------------------------------------
phase('Product-Truth Phase')

const ptStoreDir = "docs/product-truth";

// State the PT phase hands forward to the AC pipeline.
let ptFlowProduced = false;
let ptFlowRef = null;          // store-relative path to the approved .flow.json
let ptComponent = component;   // classifier may refine the target component

const classifierResult = await agent(
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
          `You are running as part of the /plan-feature product-truth phase (outcome: ${ptRunSet.outcome}). ` +
          `Draft or extend the ${ptStep.stage} artifact for this request in the product-truth store at ${ptStoreDir}. ` +
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
        if (_ptGateResult && _ptGateResult.status &&
            ["paused_awaiting_input", "nothing_to_resume", "unresumable_stale"].includes(_ptGateResult.status)) {
          return _ptGateResult;
        }
        const ptGate = _ptGateResult || { action: "cancel" };
        const ptAction = ptGate.action.toLowerCase();

        if (ptAction === "cancel") {
          // NO-PR GUARANTEE (PT cancel): prior committed PT stages preserved, current draft uncommitted.
          return {
            status: "ok",
            message:
              `Pipeline cancelled at the product-truth gate (${ptStep.agent}). No PR was opened. ` +
              `Prior committed product-truth stages are preserved; the current ${ptStep.stage} draft is left uncommitted on disk.`,
            cancelled_at: `pt-gate-${ptStep.stage}`,
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

// -------------------------------------------------------------------------
// Build the agent dispatch sequence based on effective route
// -------------------------------------------------------------------------
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
  // technical route BUT a flow was produced — FORCE the BA stage in so the flow's
  // steps derive L2s (else the flow steps would be orphaned). The BA dispatch
  // below supplies an L1 anchor for the component when parent_l1_id is absent.
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

// -------------------------------------------------------------------------
// Stage 1–N — sequential authoring pipeline with gates
// -------------------------------------------------------------------------

phase('Authoring Pipeline')

/** All AC ids written during this run (accumulated across all agents). */
const allAcsWritten = [];
/**
 * AC ids that have been successfully committed to git in prior stages.
 */
const committedAcs = [];
const stageResults = [];

for (const step of pipeline) {
  // -----------------------------------------------------------------------
  // Crash-resume: skip stages that already committed in a prior session
  // (AC BO-1500b-2).
  // -----------------------------------------------------------------------
  if (committedStageKeys.has(step.stage)) {
    // Crash-resume: this stage's output is already in git history.
    // Recover the AC IDs from the commit body so they are included in
    // allAcsWritten (and thus in the final approval set and PR body).
    const stageDisplayLabel = stageDisplayName(step.stage);
    const resumeLogCmd = authoringWorktreePath
      ? `git -C "${authoringWorktreePath}" log --format=%B origin/main..HEAD`
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
        // Scan line-by-line. Real `git log --format=%B` concatenates commit
        // bodies with a BLANK line between each subject and the rest of its body
        // (and between commits), so a blank-line split shatters the subject away
        // from the `AC IDs:` line and resumedAcIds is always []. Instead, track
        // whether we are inside a commit whose subject is for THIS stage — any
        // plan-feature(...) subject line resets the state — and read the
        // `AC IDs:` line from within that commit.
        const stageSubjectRe = new RegExp(
          `^plan-feature\\(${stageDisplayLabel}(?:[^)]*)?\\):`,
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

    // m6 — the flow reconciliation lives in the BA approve branch below; a
    // crash-resumed (already-committed) BA stage `continue`s past it, so
    // baFlowBacklinks is lost and step.implements would never be reconciled.
    // Emit an OBSERVABLE, non-silent signal that reconciliation must be run
    // manually rather than silently dropping it. (A full re-derivation on
    // resume is out of scope; the observable signal is the required minimum.)
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

  while (!approved) {
    // Dispatch the authoring agent, directing AC writes to the dedicated
    // authoring worktree's AC store path (AC BO-1500a-1).
    stepResult = await agent(
      `You are running as part of the /plan-feature pipeline (route: ${effectiveRoute}). ` +
      (acFeedback
        ? `The user reviewed your previous attempt and requested changes — address this feedback: ${acFeedback}. `
        : "") +
      `Write AC YAML files ONLY to ${acStoreDir}. ` +
      "Do NOT write AC files to docs/acceptance-criteria/ relative to the current checkout — " +
      `use the absolute path ${acStoreDir} instead. ` +
      "Do NOT create or modify any files in tickets/. " +
      "After writing, return a JSON object: { \"status\": \"ok\", \"acs_written\": [\"ACD-...\", ...] }\n" +
      // Flow → BA handoff: when a product-truth flow was approved this run, the BA
      // derives L2/L3 from the flow's steps (self-discovered via index.json — a
      // structured flow_ref input is inert) and reports a flow_backlinks map the
      // reconciliation step writes back into step.implements.
      (step.stage === "ba" && ptFlowProduced
        ? "A product-truth flow was approved for this request" +
          (ptFlowRef ? ` (${ptFlowRef})` : "") +
          ". Derive the L2/L3 ACs FROM THE FLOW'S STEPS. The flow is self-discoverable via " +
          "docs/product-truth/index.json — rely on that discovery, not a passed flow_ref. " +
          "ALSO return a flow_backlinks map in your JSON response: " +
          "{ \"<flow step id>\": [\"<AC id>\", ...] } linking each flow step to the AC ids you derived from it. " +
          // FLOW-DERIVED-AC PARENTING RULE (orphan-prevention): every L2/L3 you derive
          // from a flow step MUST have an L1 parent, or scan_ac_orphans.py /
          // check_ac_parent_covered_by (pre-commit hooks) will flag it. Give an
          // explicit anchor in BOTH branches — never leave a flow-derived AC parentless.
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
    const written = (stepResultObj && stepResultObj.acs_written) ? stepResultObj.acs_written : [];
    allAcsWritten.push(...written);

    // Capture the BA's reported flow_backlinks for the post-BA reconciliation step.
    if (step.stage === "ba" && stepResultObj && stepResultObj.flow_backlinks && typeof stepResultObj.flow_backlinks === "object") {
      baFlowBacklinks = stepResultObj.flow_backlinks;
    }

    // Present gate to the user. ADR-024: resolveGate checks args.resume_answer first.
    if (step.gate !== "final") {
      const _midGateResult = await resolveGate(
        `gate-${step.stage}`,
        async () => {
          const raw = await agent(
            `${step.agent} has written the following ACs: ${written.join(", ") || "(none)"}.\n` +
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
        args,
        { stage: step.stage, acs: written },
        { type: "single_choice", options: ["approve", "edit", "cancel"] },
        args.run_id || "default-run"
      );
      if (_midGateResult && _midGateResult.status &&
          ["paused_awaiting_input", "nothing_to_resume", "unresumable_stale"].includes(_midGateResult.status)) {
        return _midGateResult;
      }
      const gateDecision = _midGateResult || { action: "cancel" };

      const action = gateDecision.action.toLowerCase();

      if (action === "cancel") {
        // AC BO-1500c-1-i — NO-PR GUARANTEE (mid-pipeline cancel).
        const cancelLabel = `gate after ${step.agent}`;
        return {
          status: "ok",
          message: buildCancelMessage(committedAcs, written, cancelLabel, acStoreDir, authoringWorktreePath),
          committed_acs: committedAcs,
          acs_as_drafts: written,
        };
      } else if (action === "edit" && editRetries < MAX_EDIT_RETRIES) {
        editRetries++;
        // Thread the user's edit feedback into the re-dispatched author prompt (m4).
        acFeedback = (gateDecision && typeof gateDecision.feedback === "string") ? gateDecision.feedback.trim() : "";
        continue;
      } else if (action === "edit" && editRetries >= MAX_EDIT_RETRIES) {
        // Max retries exhausted — abort without committing the draft.
        return {
          status: "error",
          message:
            `${step.agent} failed to produce satisfactory ACs after ${MAX_EDIT_RETRIES + 1} attempts. Pipeline aborted.\n` +
            buildCancelMessage(committedAcs, written, `max-retries abort for ${step.agent}`, acStoreDir, authoringWorktreePath),
          committed_acs: committedAcs,
          acs_as_drafts: written,
        };
      } else {
        // approve — commit stage output before dispatching the next agent.
        //
        // COMMIT-BEFORE-NEXT-STAGE INVARIANT (AC BO-1500b-1):
        // The commit MUST succeed before the while-loop exits and the outer
        // for-loop advances to the next pipeline step.
        const commitOutcome = await commitStageOutput(written, step.stage, component, false, runId, acStoreDir, authoringWorktreePath);
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

        // -----------------------------------------------------------------
        // Reconciliation (Track 1.3): AFTER the BA stage is committed, write
        // the BA's reported flow_backlinks into the flow's step.implements and
        // regenerate derived data as a DEDICATED reconciliation commit (it
        // re-mutates the already-committed flow + index + ACs).
        // -----------------------------------------------------------------
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
      const _finalGateResult = await resolveGate(
        "final-gate",
        async () => {
          const raw = await agent(
            `IT PO v3 has enriched the following ACs: ${written.join(", ") || allAcsWritten.join(", ")}.\n` +
            "Present these to the user with their enriched fields (assigned_agent, complexity, contracts).\n" +
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
        args,
        { stage: "final", acs: written, all_acs: allAcsWritten },
        { type: "priority_choice", options: ["approve", "edit", "defer", "cancel"] },
        args.run_id || "default-run"
      );
      // Non-proceed outcomes: exit immediately.
      if (_finalGateResult && _finalGateResult.status &&
          ["paused_awaiting_input", "nothing_to_resume", "unresumable_stale"].includes(_finalGateResult.status)) {
        return _finalGateResult;
      }
      const finalDecision = _finalGateResult || { action: "defer" };

      const finalAction = finalDecision.action.toLowerCase();
      const priority = VALID_PRIORITIES.includes(finalDecision.priority)
        ? finalDecision.priority
        : "medium";

      if (finalAction === "cancel") {
        // AC BO-1500c-1-i — NO-PR GUARANTEE (final-gate cancel).
        return {
          status: "ok",
          message: buildCancelMessage(committedAcs, written, "final gate (IT-PO)", acStoreDir, authoringWorktreePath),
          committed_acs: committedAcs,
          acs_as_drafts: written,
        };
      } else if (finalAction === "edit" && editRetries < MAX_EDIT_RETRIES) {
        editRetries++;
        continue;
      } else if (finalAction === "edit" && editRetries >= MAX_EDIT_RETRIES) {
        return {
          status: "error",
          message:
            `it-po failed to produce satisfactory ACs after ${MAX_EDIT_RETRIES + 1} attempts. Pipeline aborted.\n` +
            buildCancelMessage(committedAcs, written, "max-retries abort for it-po (final gate)", acStoreDir, authoringWorktreePath),
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
        // Write readiness: approved + priority to all ACs in batch.
        const approvalResult = await agent(
          `For each of the following ACs: ${allAcsWritten.join(", ")}, ` +
          `update their YAML files to set readiness: approved and priority: ${priority}. ` +
          "Use Edit tool on each file. Confirm by returning { \"status\": \"ok\", \"updated\": [<ac_ids>] }.",
          { agentType: "status-checker", label: "apply-approval" }
        );

        // Commit the final IT PO enriched AC output before reporting success.
        const finalCommitOutcome = await commitStageOutput(written, step.stage, component, true, runId, acStoreDir, authoringWorktreePath);
        if (finalCommitOutcome.status === "error") {
          return {
            status: "error",
            message: formatCommitError("it-po", step.stage, finalCommitOutcome, allAcsWritten),
            acs_updated: allAcsWritten,
            priority,
            route: effectiveRoute,
          };
        }

        approved = true;
        stageResults.push({ stage: step.stage, agent: step.agent, acs: written });

        // -----------------------------------------------------------------------
        // §D — Delivery: push authoring branch to origin and open a PR to main.
        // (AC BO-1500c-1)
        // -----------------------------------------------------------------------
        const authoringBranch = wtPayload ? wtPayload.branch : null;
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
            `/plan-feature complete. ${allAcsWritten.length} AC(s) approved with priority: ${priority}.\n` +
            prSummary,
          acs_approved: allAcsWritten,
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
            buildCancelMessage(committedAcs, written, "final gate (unrecognized action)", acStoreDir, authoringWorktreePath),
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
