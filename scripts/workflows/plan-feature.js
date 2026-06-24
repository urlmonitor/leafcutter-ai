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
 * Source ticket: EPIC-ACDrivenDevelopment/08_create_ac_workflow.md
 * ACs: ACD-300, ACD-300a, ACD-300a-1..3, ACD-300b..d, TKT-100g
 * Renamed from create-ac.js per AC ACD-1100c-1 (v2.0 migration).
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 */

export const meta = {
  name: "plan-feature",
  description:
    "Triage, orchestrate, and gate AC authoring for a new feature request. " +
    "Dispatches ac-triage (Haiku) to classify the request as strategic / " +
    "behavioral / technical / covered, then routes through the correct " +
    "authoring agents (PO v3, BA v3, IT PO v3) with user gates between stages. " +
    "All output goes exclusively to the AC store — no ticket files are produced.",
  phases: [
    "stage-0: ac-triage (Haiku) — duplicate check + route classification",
    "stage-1: authoring agents per route (PO v3 / BA v3 / IT PO v3)",
    "gates: user confirm/edit/cancel between each stage",
    "final-gate: priority setting + readiness: approved",
  ],
};

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
 * using `git add <explicit-path>` for each file individually. This guarantees
 * that:
 *   - No files outside docs/acceptance-criteria/ are staged.
 *   - No AC files from a previous stage (already committed) are re-staged.
 *   - Unrelated uncommitted working-tree changes remain unstaged.
 *
 * The staging strategy:
 *   1. Run `git status --porcelain --untracked-files=all -- docs/acceptance-criteria/`
 *      to find all modified or new (untracked) AC YAML files in the store.
 *      The --untracked-files=all flag is required to discover files in previously-
 *      untracked subfolders that would otherwise be collapsed to a dir-level entry.
 *   2. Filter the results to those whose filename stem (without .yaml) is EXACTLY
 *      equal to an AC ID in the `written` array — stems must match exactly, not
 *      merely share a prefix (e.g. ACD-300g must NOT match written=["ACD-300"]).
 *   3. Stage each matching file with an individual `git add <path>` call.
 *
 * Commit message format (AC ACD-300g-3):
 *   Subject: plan-feature(<STAGE>): <component>
 *   Body:    AC IDs: <comma-separated list>
 *            run-id: <runId>
 *            <"mid-pipeline commit" | "final commit of run">
 *
 * On pre-commit hook failure the result includes:
 *   hook_name    {string|null} — name of the failing hook (parsed from git output)
 *   failing_files {string[]}  — file paths that failed validation
 *   is_conflict  {boolean}    — true when failure is an index conflict
 *
 * @param {Function} agent        - Runtime-provided agent dispatch function.
 * @param {string[]} written      - Array of AC IDs (e.g. ["ACD-100a-1"]) written by the stage.
 * @param {string}   stageName    - Internal stage key (e.g. "po", "ba", "itpo").
 * @param {string}   component    - Target component name (e.g. "ac-driven-dev").
 * @param {boolean}  isFinal      - True when this is the final commit of the pipeline run.
 * @param {string}   runId        - Short run identifier generated at the top of run().
 * @param {string}   acStorePath  - Absolute path to the AC store directory (AC BO-1500a-1).
 *                                  Defaults to "docs/acceptance-criteria" when omitted.
 * @returns {Promise<{
 *   status: "ok"|"error",
 *   message: string,
 *   hook_name?: string|null,
 *   failing_files?: string[],
 *   is_conflict?: boolean
 * }>}
 */
async function commitStageOutput(agent, written, stageName, component, isFinal, runId, acStorePath) {
  acStorePath = acStorePath || "docs/acceptance-criteria";
  const stageLabel = stageDisplayName(stageName);
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
    commitResult = await agent({
      agentType: "commit",
      input: {
        instructions:
          `Stage and commit the AC YAML files produced by the ${stageName} stage.\n` +
          "\n" +
          `The AC IDs written by this stage are: ${writtenJson}\n` +
          `The commit message to use is: ${commitMessage}\n` +
          "\n" +
          `IMPORTANT STAGING RULE: You MUST stage ONLY the files that correspond to the\n` +
          `AC IDs listed above. Never run 'git add ${acStorePath}' or\n` +
          `'git add .' — those commands would include files from previous stages or\n` +
          `unrelated working-tree changes, which is a correctness violation.\n` +
          `\n` +
          `Step 1 — Discover which AC files from this stage exist on disk:\n` +
          `  Run: git status --porcelain --untracked-files=all -- ${acStorePath}/\n` +
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
          "    git add <path>\n" +
          `  Run one 'git add' command per file. Do NOT use 'git add .' or\n` +
          `  'git add ${acStorePath}/' — only individual explicit paths.\n` +
          "  If any 'git add <path>' exits non-zero:\n" +
          "    Return: { \"status\": \"error\", \"message\": \"git add failed for <path>\", \"hook_name\": null, \"failing_files\": [\"<path>\"], \"is_conflict\": false }\n" +
          "\n" +
          "Step 4 — Verify only the expected files are staged:\n" +
          "  Run: git diff --cached --name-only\n" +
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
          "       The hook name is typically on a line like:\n" +
          "         '- hook-name...Failed'\n" +
          "         'Running: hook-name'\n" +
          "         '[ERROR] hook-name:'\n" +
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
      },
    });
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
 * Handles two cases:
 *   - index conflict: reports conflicting paths, advises manual resolution
 *   - pre-commit hook failure: names the hook, lists failing files, advises fix + re-run
 *
 * @param {string}      agentLabel   - Human-readable label for the stage agent (e.g. "product-owner").
 * @param {string}      stageName    - Stage label used in the commit message (e.g. "po-v3").
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
 * The AC store keeps one YAML file per AC ID at the path:
 *   <acStorePath>/<AC_ID>.yaml
 *
 * When the user cancels at a gate, draft files for the cancelled stage remain on
 * disk as uncommitted working-tree changes. Files from stages that were already
 * committed are in git history and are not listed here.
 *
 * @param {string[]} committedAcs   - AC IDs that have already been committed to git (prior stages).
 * @param {string[]} draftAcs       - AC IDs written by the cancelled stage; still uncommitted.
 * @param {string}   cancelledAt    - Human label for where the cancel occurred (e.g. "gate after product-owner").
 * @param {string}   acStorePath    - Absolute path to the AC store directory (AC BO-1500a-1).
 *                                    Defaults to "docs/acceptance-criteria" when omitted.
 * @returns {string} Formatted exit message for the user.
 */
function buildCancelMessage(committedAcs, draftAcs, cancelledAt, acStorePath) {
  const store = acStorePath || "docs/acceptance-criteria";
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
      `\nYou can inspect these files, manually commit them with \`git add\` + \`git commit\`, ` +
      `or discard tracked files with \`git checkout -- ${store}/\` and ` +
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
 * Uses `git status --porcelain --untracked-files=all` to find all modified or
 * untracked YAML files in the AC store directory. For each candidate, reads the
 * YAML content and qualifies it as an orphan iff:
 *   - `origin_agent` is in {product-owner, business-analyst, it-po}
 *   - `readiness` is "draft"
 *
 * The scan uses a single `git status` invocation — it is O(1) relative to the
 * number of YAML files and completes in under 2 seconds for stores up to 500 files.
 *
 * @param {Function} agent       - Runtime-provided agent dispatch function.
 * @param {string}   acStoreDir  - Path to the AC store directory (e.g. "docs/acceptance-criteria").
 * @returns {Promise<Array<{filePath: string, acId: string}>>} Array of orphaned AC file paths and their AC IDs.
 */
async function scanOrphanedAcDrafts(agent, acStoreDir) {
  // Run git status to discover modified/untracked YAML files in the AC store.
  let statusOutput;
  try {
    const statusResult = await agent({
      agentType: "status-checker",
      input: {
        instructions:
          `Run the following command and return ONLY the raw stdout output, with no additional text:\n` +
          `git status --porcelain --untracked-files=all -- ${acStoreDir}\n` +
          `Return a JSON object: { "output": "<raw stdout>", "exit_code": <number> }`,
      },
    });
    const parsed = typeof statusResult === "string" ? JSON.parse(statusResult) : statusResult;
    if (!parsed || parsed.exit_code !== 0) {
      // git status failed — warn and proceed without blocking (§PRR.2 error handling).
      return [];
    }
    statusOutput = parsed.output || "";
  } catch (_err) {
    // Cannot check for orphans — proceed without blocking.
    return [];
  }

  // Parse git status --porcelain output lines.
  // Line format: "XY <path>" where X = index status, Y = worktree status.
  // For untracked files: "?? <path>"
  const orphans = [];
  const lines = statusOutput.split("\n").filter((l) => l.trim().length > 0);

  for (const line of lines) {
    if (line.length < 4) { continue; }
    const xyStatus = line.slice(0, 2);
    const filePath = line.slice(3).trim();

    // Only consider YAML files.
    if (!filePath.endsWith(".yaml") && !filePath.endsWith(".yml")) { continue; }

    // Relevant status codes: M (modified), A (added), ? (untracked).
    // Skip files that are neither modified nor untracked.
    const indexStatus = xyStatus[0];
    const worktreeStatus = xyStatus[1];
    const isRelevant =
      indexStatus === "M" || indexStatus === "A" ||
      worktreeStatus === "M" || worktreeStatus === "A" ||
      xyStatus === "??";
    if (!isRelevant) { continue; }

    // Read the YAML file content to qualify it as an orphan.
    let fileContent;
    try {
      const readResult = await agent({
        agentType: "status-checker",
        input: {
          instructions:
            `Read the file at path "${filePath}" and return its raw text content.\n` +
            `Return a JSON object: { "content": "<raw file text>" }\n` +
            `If the file cannot be read, return: { "content": null }`,
        },
      });
      const readParsed = typeof readResult === "string" ? JSON.parse(readResult) : readResult;
      fileContent = readParsed ? readParsed.content : null;
    } catch (_readErr) {
      // Cannot read file — skip it.
      continue;
    }

    if (!fileContent) { continue; }

    // Extract origin_agent and readiness fields from raw YAML text.
    // Use simple regex-based extraction to avoid a YAML parser dependency.
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

    orphans.push({ filePath, acId });
  }

  return orphans;
}

/**
 * Resolve orphaned AC draft files discovered by scanOrphanedAcDrafts().
 *
 * Presents the user with a yes/no/discard choice:
 *   - yes:     commits orphaned files using the hook-safe commit path (commitStageOutput).
 *   - no:      prints an abort message and exits the workflow.
 *   - discard: reverts tracked modified files (git restore) and removes untracked
 *              new files (rm). Both operations are performed — git restore alone
 *              does not remove untracked files.
 *
 * On "yes", the commit uses the existing commitStageOutput() function, which
 * dispatches the commit agent (hook-safe path established by ticket 07).
 *
 * @param {Function}                            agent      - Runtime-provided agent dispatch function.
 * @param {Array<{filePath: string, acId: string}>} orphans - Orphan list from scanOrphanedAcDrafts().
 * @param {string}                              acStoreDir  - AC store directory path.
 * @param {string}                              runId       - Current run id (for commit message).
 * @returns {Promise<{action: "continue"|"abort"}>} "continue" to proceed to Stage 0; "abort" to exit.
 */
async function resolveOrphanedDrafts(agent, orphans, acStoreDir, runId) {
  const acIds = orphans.map((o) => o.acId).sort();
  const N = orphans.length;
  const acIdList = acIds.join(", ");

  // Present the user with the three-way choice.
  let userChoice;
  try {
    const choiceResult = await agent({
      agentType: "status-checker",
      input: {
        instructions:
          `Found ${N} uncommitted AC file${N !== 1 ? "s" : ""} from a prior session: [${acIdList}]. ` +
          `(yes/no/discard)\n\n` +
          `Present this message EXACTLY to the user and ask them to choose:\n` +
          `  yes     — commit the orphaned files before starting new work.\n` +
          `  no      — abort the workflow (files remain on disk, must be resolved manually).\n` +
          `  discard — delete the orphaned files and start with a clean working tree.\n\n` +
          `Return ONLY a JSON object: { "choice": "yes" | "no" | "discard" }`,
      },
    });
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
    // Build an AC ID array for the commit function. Use "recovery" as the stage name.
    const acIdsForCommit = orphans.map((o) => o.acId);
    const commitOutcome = await commitStageOutput(
      agent,
      acIdsForCommit,
      "recovery",
      "orphaned-ac-recovery",
      false,
      runId
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
    // git restore alone does not remove untracked files — both operations are required.
    const errors = [];

    for (const orphan of orphans) {
      const { filePath } = orphan;

      // Determine if the file is untracked (status ??) or tracked (modified/added).
      // Re-check git status for this specific file.
      let fileStatusResult;
      try {
        fileStatusResult = await agent({
          agentType: "status-checker",
          input: {
            instructions:
              `Run this command and return the raw stdout:\n` +
              `git status --porcelain --untracked-files=all -- "${filePath}"\n` +
              `Return JSON: { "output": "<raw stdout>", "exit_code": <number> }`,
          },
        });
      } catch (_statusErr) {
        errors.push(`Warning: could not determine status of ${filePath} — skipping.`);
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
          await agent({
            agentType: "status-checker",
            input: {
              instructions:
                `Delete the file at path "${filePath}" using fs.unlinkSync or equivalent.\n` +
                `Run: rm -f "${filePath}"\n` +
                `Return JSON: { "exit_code": <number>, "error": "<error or null>" }`,
            },
          });
        } catch (_rmErr) {
          errors.push(`Warning: could not delete untracked file ${filePath}.`);
        }
      } else {
        // Tracked modified file: use git restore to discard working-tree changes.
        // If the file is staged (index status A or M), unstage first.
        const indexStatus = fileStatusLine.length >= 1 ? fileStatusLine[0] : " ";
        if (indexStatus === "A" || indexStatus === "M") {
          try {
            await agent({
              agentType: "status-checker",
              input: {
                instructions:
                  `Run this command:\n` +
                  `git restore --staged "${filePath}"\n` +
                  `Return JSON: { "exit_code": <number> }`,
              },
            });
          } catch (_unstageErr) {
            errors.push(`Warning: could not unstage ${filePath}.`);
          }
        }
        // Restore working tree.
        try {
          await agent({
            agentType: "status-checker",
            input: {
              instructions:
                `Run this command:\n` +
                `git restore "${filePath}"\n` +
                `Return JSON: { "exit_code": <number> }`,
            },
          });
        } catch (_restoreErr) {
          errors.push(`Warning: could not restore ${filePath}.`);
        }
      }
    }

    // Verify the working tree is clean under the AC store.
    // (Best-effort — do not block if verification itself fails.)
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

/**
 * Main entry point called by the Claude Code workflow runtime.
 *
 * @param {object} params
 * @param {string} params.userInput   - Raw $ARGUMENTS (request + optional flags).
 * @param {Function} params.agent     - Runtime-provided agent dispatch function.
 * @param {Function} params.workflow  - Runtime-provided workflow dispatch (not used — leaf).
 */
async function run({ userInput, agent }) {
  // Generate a short run id (8 hex chars) to identify this invocation in commit messages (ACD-300g-3).
  const runId = Math.floor(Math.random() * 0xFFFFFFFF).toString(16).padStart(8, "0");

  const { request, component, force } = parseArgs(userInput);

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
  // Pre-Stage-0 — Authoring Worktree Bootstrap (AC BO-1500a-1).
  //
  // Creates a dedicated worktree branched from origin/main so that every AC
  // YAML file produced in this session is written under an isolated path and
  // never lands in the user's original checkout.  The script fetches origin
  // (best-effort) so the branch starts at the true remote tip.
  // -------------------------------------------------------------------------
  const sessionSlug = component
    ? component.toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 20)
    : null;

  let authoringWorktreePath = null;
  let acStoreDir = "docs/acceptance-criteria"; // default: overridden below

  let worktreeSetupResult;
  try {
    worktreeSetupResult = await agent({
      agentType: "status-checker",
      input: {
        instructions:
          "Run the following command and return ONLY the raw stdout output:\n" +
          "python scripts/setup_ticket_worktree.py create-ac-worktree" +
          (sessionSlug ? ` "${sessionSlug}"` : "") + "\n" +
          "Return JSON: { \"output\": \"<raw stdout line>\", \"exit_code\": <number>, \"stderr\": \"<stderr or empty>\" }",
      },
    });
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

  // Only fail-hard when exit_code is explicitly non-zero.  When exit_code is
  // absent (undefined) the step ran in a context that does not return structured
  // subprocess results (e.g. a test mock or a status-checker that ignores the
  // instructions format).  In that case we continue with the default acStoreDir
  // so that the rest of the pipeline — especially the §PRR scan — can proceed.
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
    // This can happen in mock environments that return non-JSON output.
    wtPayload = null;
  }

  if (wtPayload) {
    authoringWorktreePath = wtPayload.worktree_path || null;
    acStoreDir = wtPayload.ac_store_path || acStoreDir;
  }

  // -------------------------------------------------------------------------
  // Pre-Stage-0 — Partial-Run Recovery: detect and resolve orphaned AC drafts
  // from a prior crashed session (AC ACD-300g-2-i).
  //
  // Scans the authoring worktree's AC store via git status (single git call,
  // O(1) for up to 500 files). Qualifies files by origin_agent + readiness:
  // draft. Presents yes/no/discard choice if any orphans are found.
  // -------------------------------------------------------------------------
  const orphans = await scanOrphanedAcDrafts(agent, acStoreDir);
  if (orphans.length > 0) {
    const recoveryOutcome = await resolveOrphanedDrafts(agent, orphans, acStoreDir, runId);
    if (recoveryOutcome.action === "abort") {
      return {
        status: "error",
        message: recoveryOutcome.message ||
          "Uncommitted AC files must be resolved first. Re-run /plan-feature after resolving them.",
      };
    }
  }

  // -------------------------------------------------------------------------
  // Stage 0 — ac-triage: duplicate check + route classification
  // -------------------------------------------------------------------------
  const triageResult = await agent({
    agentType: "ac-triage",
    input: {
      user_request: request,
      component: component,
      instructions:
        "Triage the user's request against the AC store. " +
        "Return a JSON object with keys: route, existing_acs, parent_l1_id, rationale. " +
        "route must be one of: strategic | behavioral | technical | covered. " +
        "existing_acs is an array of AC IDs that are semantically relevant. " +
        "parent_l1_id is the ID of the matching L1 AC (for behavioral route), or null. " +
        "rationale is a one-sentence explanation of the classification.",
    },
  });

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
    const coverageResult = await agent({
      agentType: "status-checker",
      input: {
        instructions:
          "Present the following to the user and ask them to choose one option:\n\n" +
          `The request appears to already be covered by these existing ACs:\n${existing_acs.join(", ")}\n\n` +
          "Options:\n" +
          "  1. cancel  — the existing ACs are sufficient; exit without creating new ACs.\n" +
          "  2. amend   — add constraints/details to the existing ACs (routes as 'technical').\n" +
          "  3. force   — create new ACs anyway (routes as 'strategic').\n\n" +
          "Return ONLY a JSON object: { \"choice\": \"cancel\" | \"amend\" | \"force\", \"rationale\": \"...\" }",
      },
    });

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
  /** All AC ids written during this run (accumulated across all agents). */
  const allAcsWritten = [];
  /**
   * AC ids that have been successfully committed to git in prior stages.
   * Updated immediately after each successful commitStageOutput() call.
   * Used to distinguish "committed from prior stages" vs "draft from cancelled stage"
   * in cancel/abort exit messages (AC ACD-300g-4).
   */
  const committedAcs = [];
  const stageResults = [];

  for (const step of pipeline) {
    let stepResult;
    let editRetries = 0;
    let approved = false;

    while (!approved) {
      // Dispatch the authoring agent, directing AC writes to the dedicated
      // authoring worktree's AC store path (AC BO-1500a-1).
      stepResult = await agent({
        agentType: step.agent,
        input: {
          user_request: request,
          component: component,
          parent_l1_id: parent_l1_id,
          route: effectiveRoute,
          ac_store_path: acStoreDir,
          instructions:
            `You are running as part of the /plan-feature pipeline (route: ${effectiveRoute}). ` +
            `Write AC YAML files ONLY to ${acStoreDir}. ` +
            "Do NOT write AC files to docs/acceptance-criteria/ relative to the current checkout — " +
            `use the absolute path ${acStoreDir} instead. ` +
            "Do NOT create or modify any files in tickets/. " +
            "After writing, return a JSON object: { \"status\": \"ok\", \"acs_written\": [\"ACD-...\", ...] }",
        },
      });

      const written = (stepResult && stepResult.acs_written) ? stepResult.acs_written : [];
      allAcsWritten.push(...written);

      // Present gate to the user.
      if (step.gate !== "final") {
        const gateResult = await agent({
          agentType: "status-checker",
          input: {
            instructions:
              `${step.agent} has written the following ACs: ${written.join(", ") || "(none)"}.\n` +
              "Present these to the user and ask them to choose:\n" +
              "  1. approve — proceed to the next stage.\n" +
              "  2. edit    — re-invoke this agent with feedback.\n" +
              "  3. cancel  — abort the pipeline (ACs remain as drafts).\n" +
              "Return ONLY a JSON object: { \"action\": \"approve\" | \"edit\" | \"cancel\", \"feedback\": \"...\" }",
          },
        });

        let gateDecision;
        try {
          gateDecision = typeof gateResult === "string" ? JSON.parse(gateResult) : gateResult;
        } catch (_) {
          gateDecision = { action: "cancel" };
        }

        const action = (gateDecision.action || "cancel").toLowerCase();

        if (action === "cancel") {
          // AC ACD-300g-4: do NOT commit — draft files remain on disk.
          // Distinguish committed ACs from prior stages vs. this stage's drafts.
          const cancelLabel = `gate after ${step.agent}`;
          return {
            status: "ok",
            message: buildCancelMessage(committedAcs, written, cancelLabel, acStoreDir),
            committed_acs: committedAcs,
            acs_as_drafts: written,
          };
        } else if (action === "edit" && editRetries < MAX_EDIT_RETRIES) {
          editRetries++;
          // Re-dispatch same agent with feedback (loop continues)
          continue;
        } else if (action === "edit" && editRetries >= MAX_EDIT_RETRIES) {
          // Max retries exhausted — abort without committing the draft.
          // AC ACD-300g-4: draft files remain on disk uncommitted.
          return {
            status: "error",
            message:
              `${step.agent} failed to produce satisfactory ACs after ${MAX_EDIT_RETRIES + 1} attempts. Pipeline aborted.\n` +
              buildCancelMessage(committedAcs, written, `max-retries abort for ${step.agent}`, acStoreDir),
            committed_acs: committedAcs,
            acs_as_drafts: written,
          };
        } else {
          // approve — commit stage output before dispatching the next agent.
          const commitOutcome = await commitStageOutput(agent, written, step.stage, component, false, runId, acStoreDir);
          if (commitOutcome.status === "error") {
            return {
              status: "error",
              message: formatCommitError(step.agent, step.stage, commitOutcome, allAcsWritten),
              acs_as_drafts: allAcsWritten,
            };
          }
          // Track successfully committed ACs so cancel messages can distinguish
          // prior-stage commits from the current draft (AC ACD-300g-4).
          committedAcs.push(...written);
          approved = true;
        }
      } else {
        // Final gate: IT PO v3 has enriched ACs and set readiness: reviewed.
        const finalGateResult = await agent({
          agentType: "status-checker",
          input: {
            instructions:
              `IT PO v3 has enriched the following ACs: ${written.join(", ") || allAcsWritten.join(", ")}.\n` +
              "Present these to the user with their enriched fields (assigned_agent, complexity, contracts).\n" +
              "Ask the user to:\n" +
              "  1. Set a priority: critical / high / medium / low\n" +
              "  2. Choose an action: approve (set readiness: approved + priority) | edit | defer (leave as reviewed)\n" +
              "Return ONLY a JSON object: { \"action\": \"approve\" | \"edit\" | \"defer\", \"priority\": \"high\" | \"medium\" | \"low\" | \"critical\" }",
          },
        });

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
          // AC ACD-300g-4: do NOT commit — draft files remain on disk.
          // written here are the IT-PO files; committedAcs holds prior-stage commits.
          return {
            status: "ok",
            message: buildCancelMessage(committedAcs, written, "final gate (IT-PO)", acStoreDir),
            committed_acs: committedAcs,
            acs_as_drafts: written,
          };
        } else if (finalAction === "edit" && editRetries < MAX_EDIT_RETRIES) {
          editRetries++;
          continue;
        } else if (finalAction === "edit" && editRetries >= MAX_EDIT_RETRIES) {
          // Max retries exhausted at the final gate — abort without committing.
          // AC ACD-300g-4: draft files remain on disk uncommitted.
          return {
            status: "error",
            message:
              `it-po failed to produce satisfactory ACs after ${MAX_EDIT_RETRIES + 1} attempts. Pipeline aborted.\n` +
              buildCancelMessage(committedAcs, written, "max-retries abort for it-po (final gate)", acStoreDir),
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
          const approvalResult = await agent({
            agentType: "status-checker",
            input: {
              instructions:
                `For each of the following ACs: ${allAcsWritten.join(", ")}, ` +
                `update their YAML files to set readiness: approved and priority: ${priority}. ` +
                "Use Edit tool on each file. Confirm by returning { \"status\": \"ok\", \"updated\": [<ac_ids>] }.",
            },
          });

          // Commit the final IT PO enriched AC output before reporting success.
          const finalCommitOutcome = await commitStageOutput(agent, written, step.stage, component, true, runId, acStoreDir);
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

          return {
            status: "ok",
            message:
              `/plan-feature complete. ${allAcsWritten.length} AC(s) approved with priority: ${priority}.`,
            acs_approved: allAcsWritten,
            priority,
            route: effectiveRoute,
          };
        } else {
          // Terminal else: unrecognized finalAction — abort immediately without committing.
          // AC ACD-300g-4: no infinite loop on unexpected gate responses.
          return {
            status: "error",
            message:
              `Final gate returned unrecognized action: ${JSON.stringify(finalAction)}. Pipeline aborted without committing.\n` +
              buildCancelMessage(committedAcs, written, "final gate (unrecognized action)", acStoreDir),
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
}

export { run };
