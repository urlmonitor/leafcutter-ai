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
 *   1. Run `git status --porcelain -- docs/acceptance-criteria/` to find all
 *      modified or new (untracked) AC YAML files in the store.
 *   2. Filter the results to those whose filename stem (without .yaml) matches
 *      an AC ID in the `written` array — these are the current stage's files.
 *   3. Stage each matching file with an individual `git add <path>` call.
 *
 * Commit message format (AC ACD-300g-3):
 *   Subject: create-ac(<STAGE>): <component>
 *   Body:    AC IDs: <comma-separated list>
 *            <"mid-pipeline commit" | "final commit of run">
 *
 * On pre-commit hook failure the result includes:
 *   hook_name    {string|null} — name of the failing hook (parsed from git output)
 *   failing_files {string[]}  — file paths that failed validation
 *   is_conflict  {boolean}    — true when failure is an index conflict
 *
 * @param {Function} agent       - Runtime-provided agent dispatch function.
 * @param {string[]} written     - Array of AC IDs (e.g. ["ACD-100a-1"]) written by the stage.
 * @param {string}   stageName   - Internal stage key (e.g. "po", "ba", "itpo").
 * @param {string}   component   - Target component name (e.g. "ac-driven-dev").
 * @param {boolean}  isFinal     - True when this is the final commit of the pipeline run.
 * @returns {Promise<{
 *   status: "ok"|"error",
 *   message: string,
 *   hook_name?: string|null,
 *   failing_files?: string[],
 *   is_conflict?: boolean
 * }>}
 */
async function commitStageOutput(agent, written, stageName, component, isFinal) {
  const displayStage = isFinal ? "final" : stageDisplayName(stageName);
  const componentLabel = component || "unknown-component";
  const acIdList = written.length > 0 ? written.join(", ") : "(none)";
  const commitKind = isFinal ? "final commit of run" : "mid-pipeline commit";
  const commitMessage =
    `create-ac(${displayStage}): ${componentLabel}\n\nAC IDs: ${acIdList}\n${commitKind}`;

  // Build a JSON-safe representation of the AC IDs so the agent can filter on them.
  const writtenJson = JSON.stringify(written);

  let commitResult;
  try {
    commitResult = await agent({
      agentType: "status-checker",
      input: {
        instructions:
          `Commit the AC YAML files produced by the ${stageName} stage.\n` +
          "\n" +
          `The AC IDs written by this stage are: ${writtenJson}\n` +
          "\n" +
          "IMPORTANT STAGING RULE: You MUST stage ONLY the files that correspond to the\n" +
          "AC IDs listed above. Never run 'git add docs/acceptance-criteria/' or\n" +
          "'git add .' — those commands would include files from previous stages or\n" +
          "unrelated working-tree changes, which is a correctness violation.\n" +
          "\n" +
          "Step 1 — Discover which AC files from this stage exist on disk:\n" +
          "  Run: git status --porcelain -- docs/acceptance-criteria/\n" +
          "  Parse the output. Each line has the format: XY <path>\n" +
          "  where XY is a two-character status code. Collect ALL lines where the\n" +
          "  path ends in '.yaml' and the status is not '  ' (i.e. it is modified or\n" +
          "  untracked — status codes: M, A, ??, etc.).\n" +
          "  From those paths, keep only the ones whose filename stem (the portion\n" +
          "  after the last '/' and before '.yaml') matches one of the AC IDs above.\n" +
          "  These are the stage-specific files to stage.\n" +
          "\n" +
          "Step 2 — If no matching files are found:\n" +
          "  Return: { \"status\": \"ok\", \"message\": \"no new AC files to commit — skipped\" }\n" +
          "\n" +
          "Step 3 — Stage each matching file individually:\n" +
          "  For each file path found in Step 1, run:\n" +
          "    git add <path>\n" +
          "  Run one 'git add' command per file. Do NOT use 'git add .' or\n" +
          "  'git add docs/acceptance-criteria/' — only individual explicit paths.\n" +
          "  If any 'git add <path>' exits non-zero:\n" +
          "    Return: { \"status\": \"error\", \"message\": \"git add failed for <path>\", \"hook_name\": null, \"failing_files\": [\"<path>\"], \"is_conflict\": false }\n" +
          "\n" +
          "Step 4 — Verify only the expected files are staged:\n" +
          "  Run: git diff --cached --name-only\n" +
          "  If the output is empty (nothing staged despite Step 3 succeeding):\n" +
          "    Return: { \"status\": \"ok\", \"message\": \"no new AC files to commit — skipped\" }\n" +
          "\n" +
          `Step 5 — Commit the staged files:\n` +
          `  Run: git commit -m "${commitMessage}" 2>&1\n` +
          "  Capture ALL output (stdout + stderr combined) and the exit code.\n" +
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
    // If the agent returned non-JSON, treat as success — the agent would have
    // thrown or returned an error object if the git commands failed.
    result = { status: "ok", message: "commit result unparseable — assuming success" };
  }

  return result || { status: "ok", message: "no result returned by agent" };
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
 * Main entry point called by the Claude Code workflow runtime.
 *
 * @param {object} params
 * @param {string} params.userInput   - Raw $ARGUMENTS (request + optional flags).
 * @param {Function} params.agent     - Runtime-provided agent dispatch function.
 * @param {Function} params.workflow  - Runtime-provided workflow dispatch (not used — leaf).
 */
async function run({ userInput, agent }) {
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
  const stageResults = [];

  for (const step of pipeline) {
    let stepResult;
    let editRetries = 0;
    let approved = false;

    while (!approved) {
      // Dispatch the authoring agent.
      stepResult = await agent({
        agentType: step.agent,
        input: {
          user_request: request,
          component: component,
          parent_l1_id: parent_l1_id,
          route: effectiveRoute,
          instructions:
            `You are running as part of the /plan-feature pipeline (route: ${effectiveRoute}). ` +
            "Write AC YAML files ONLY to docs/acceptance-criteria/. " +
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
          return {
            status: "ok",
            message: `Pipeline cancelled at gate after ${step.agent}. ACs remain as drafts.`,
            acs_as_drafts: allAcsWritten,
          };
        } else if (action === "edit" && editRetries < MAX_EDIT_RETRIES) {
          editRetries++;
          // Re-dispatch same agent with feedback (loop continues)
          continue;
        } else if (action === "edit" && editRetries >= MAX_EDIT_RETRIES) {
          return {
            status: "error",
            message: `${step.agent} failed to produce satisfactory ACs after ${MAX_EDIT_RETRIES + 1} attempts. Pipeline aborted.`,
            acs_as_drafts: allAcsWritten,
          };
        } else {
          // approve — commit stage output before dispatching the next agent.
          const commitOutcome = await commitStageOutput(agent, written, step.stage, component, false);
          if (commitOutcome.status === "error") {
            return {
              status: "error",
              message: formatCommitError(step.agent, step.stage, commitOutcome, allAcsWritten),
              acs_as_drafts: allAcsWritten,
            };
          }
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
          return {
            status: "ok",
            message: "Pipeline cancelled at final gate. ACs remain as reviewed.",
            acs_as_reviewed: allAcsWritten,
          };
        } else if (finalAction === "edit" && editRetries < MAX_EDIT_RETRIES) {
          editRetries++;
          continue;
        } else if (finalAction === "defer") {
          return {
            status: "ok",
            message: "ACs left as reviewed (deferred). Re-run /plan-feature to approve.",
            acs_as_reviewed: allAcsWritten,
          };
        } else if (finalAction === "approve" || finalAction === "edit") {
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
          const finalCommitOutcome = await commitStageOutput(agent, written, step.stage, component, true);
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
