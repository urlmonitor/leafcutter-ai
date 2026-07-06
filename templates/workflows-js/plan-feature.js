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
 *   po   → PO
 *   ba   → BA
 *   itpo → IT-PO
 *   (any other key is returned uppercase as a fallback)
 *
 * @param {string} stageKey - Internal stage key (e.g. "po", "ba", "itpo").
 * @returns {string} Display name (e.g. "PO", "BA", "IT-PO").
 */
function stageDisplayName(stageKey) {
  const map = { po: "PO", ba: "BA", itpo: "IT-PO" };
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
        branchParsed =
          typeof branchCheckResult === "string"
            ? JSON.parse(branchCheckResult)
            : branchCheckResult;
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
    result =
      typeof commitResult === "string" ? JSON.parse(commitResult) : commitResult;
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
    const parsed = typeof statusResult === "string" ? JSON.parse(statusResult) : statusResult;
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
      const readParsed = typeof readResult === "string" ? JSON.parse(readResult) : readResult;
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
    result = typeof pushResult === "string" ? JSON.parse(pushResult) : pushResult;
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
    const parsed = typeof logResult === "string" ? JSON.parse(logResult) : logResult;
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
  const displayToKey = { "po": "po", "ba": "ba", "it-po": "itpo" };

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
    const parsed = typeof choiceResult === "string" ? JSON.parse(choiceResult) : choiceResult;
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

      const statusParsed = typeof fileStatusResult === "string"
        ? JSON.parse(fileStatusResult)
        : fileStatusResult;
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
  const cbParsed =
    typeof currentBranchResult === "string"
      ? JSON.parse(currentBranchResult)
      : currentBranchResult;
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

const wtParsed =
  typeof worktreeSetupResult === "string"
    ? JSON.parse(worktreeSetupResult)
    : worktreeSetupResult;

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
  triage = typeof triageResult === "string" ? JSON.parse(triageResult) : triageResult;
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
  const coverageResult = await agent(
    "Present the following to the user and ask them to choose one option:\n\n" +
    `The request appears to already be covered by these existing ACs:\n${existing_acs.join(", ")}\n\n` +
    "Options:\n" +
    "  1. cancel  — the existing ACs are sufficient; exit without creating new ACs.\n" +
    "  2. amend   — add constraints/details to the existing ACs (routes as 'technical').\n" +
    "  3. force   — create new ACs anyway (routes as 'strategic').\n\n" +
    "Return ONLY a JSON object: { \"choice\": \"cancel\" | \"amend\" | \"force\", \"rationale\": \"...\" }",
    { agentType: "status-checker", label: "covered-route-gate" }
  );

  let userChoice;
  try {
    userChoice = typeof coverageResult === "string" ? JSON.parse(coverageResult) : coverageResult;
  } catch (_) {
    userChoice = { choice: "cancel" };
  }

  const choice = (userChoice.choice || "cancel").toLowerCase();

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
// Build the agent dispatch sequence based on effective route
// -------------------------------------------------------------------------
const effectiveRoute = triage.route;

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
      const resumeLogParsed =
        typeof resumeLogResult === "string"
          ? JSON.parse(resumeLogResult)
          : resumeLogResult;
      if (resumeLogParsed && resumeLogParsed.exit_code === 0) {
        const logBody = resumeLogParsed.output || "";
        // Split into individual commit messages.
        const commitBlocks = logBody.split(/\n{2,}/);
        for (const block of commitBlocks) {
          // Match commits whose subject line is for this stage.
          const subjectMatch = block.match(
            new RegExp(
              `^plan-feature\\(${stageDisplayLabel}(?:[^)]*)?\\):`,
              "im"
            )
          );
          if (subjectMatch) {
            // Extract the "AC IDs: ..." line from this commit's body.
            const acIdsMatch = block.match(/^AC IDs:\s*(.+)$/m);
            if (acIdsMatch) {
              const ids = acIdsMatch[1]
                .split(",")
                .map((s) => s.trim())
                .filter((s) => s.length > 0 && s !== "(none)");
              resumedAcIds = ids;
            }
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

    stageResults.push({ stage: step.stage, agent: step.agent, acs: resumedAcIds, skipped: true });
    continue;
  }

  let stepResult;
  let editRetries = 0;
  let approved = false;

  while (!approved) {
    // Dispatch the authoring agent, directing AC writes to the dedicated
    // authoring worktree's AC store path (AC BO-1500a-1).
    stepResult = await agent(
      `You are running as part of the /plan-feature pipeline (route: ${effectiveRoute}). ` +
      `Write AC YAML files ONLY to ${acStoreDir}. ` +
      "Do NOT write AC files to docs/acceptance-criteria/ relative to the current checkout — " +
      `use the absolute path ${acStoreDir} instead. ` +
      "Do NOT create or modify any files in tickets/. " +
      "After writing, return a JSON object: { \"status\": \"ok\", \"acs_written\": [\"ACD-...\", ...] }\n" +
      `user_request: ${JSON.stringify(request)}\n` +
      `component: ${JSON.stringify(component)}\n` +
      `parent_l1_id: ${JSON.stringify(parent_l1_id)}\n` +
      `route: ${JSON.stringify(effectiveRoute)}\n` +
      `ac_store_path: ${JSON.stringify(acStoreDir)}`,
      { agentType: step.agent, label: `stage-${step.stage}-author` }
    );

    const written = (stepResult && stepResult.acs_written) ? stepResult.acs_written : [];
    allAcsWritten.push(...written);

    // Present gate to the user.
    if (step.gate !== "final") {
      const gateResult = await agent(
        `${step.agent} has written the following ACs: ${written.join(", ") || "(none)"}.\n` +
        "Present these to the user and ask them to choose:\n" +
        "  1. approve — proceed to the next stage.\n" +
        "  2. edit    — re-invoke this agent with feedback.\n" +
        "  3. cancel  — abort the pipeline (ACs remain as drafts).\n" +
        "Return ONLY a JSON object: { \"action\": \"approve\" | \"edit\" | \"cancel\", \"feedback\": \"...\" }",
        { agentType: "status-checker", label: `gate-${step.stage}` }
      );

      let gateDecision;
      try {
        gateDecision = typeof gateResult === "string" ? JSON.parse(gateResult) : gateResult;
      } catch (_) {
        gateDecision = { action: "cancel" };
      }

      const action = (gateDecision.action || "cancel").toLowerCase();

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
        // Re-dispatch same agent with feedback (loop continues)
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
      }
    } else {
      // Final gate: IT PO v3 has enriched ACs and set readiness: reviewed.
      const finalGateResult = await agent(
        `IT PO v3 has enriched the following ACs: ${written.join(", ") || allAcsWritten.join(", ")}.\n` +
        "Present these to the user with their enriched fields (assigned_agent, complexity, contracts).\n" +
        "Ask the user to:\n" +
        "  1. Set a priority: critical / high / medium / low\n" +
        "  2. Choose an action: approve (set readiness: approved + priority) | edit | defer (leave as reviewed) | cancel (abort; leave this stage's ACs as uncommitted drafts)\n" +
        "Return ONLY a JSON object: { \"action\": \"approve\" | \"edit\" | \"defer\" | \"cancel\", \"priority\": \"high\" | \"medium\" | \"low\" | \"critical\" }",
        { agentType: "status-checker", label: "final-gate" }
      );

      let finalDecision;
      try {
        finalDecision = typeof finalGateResult === "string" ? JSON.parse(finalGateResult) : finalGateResult;
      } catch (_) {
        finalDecision = { action: "defer" };
      }

      const finalAction = (finalDecision.action || "defer").toLowerCase();
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
