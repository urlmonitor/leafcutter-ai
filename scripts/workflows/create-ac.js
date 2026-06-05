/**
 * create-ac.js — Claude Code Workflow script
 *
 * Implements the /create-ac command: triages the user's request via the
 * ac-triage agent (Haiku-tier, fast), routes to the correct AC authoring
 * agents (product-owner-v3, business-analyst-v3, it-po-v3) in sequence with
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
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 */

export const meta = {
  name: "create-ac",
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
        "Usage: /create-ac <description> [--component <name>] [--force]\n" +
        "Example: /create-ac \"Allow users to export reports as PDF\" --component reports",
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
      { agent: "product-owner-v3", stage: "po",    gate: "after_po" },
      { agent: "business-analyst-v3", stage: "ba", gate: "after_ba" },
      { agent: "it-po-v3",          stage: "itpo", gate: "final" },
    ];
  } else if (effectiveRoute === "behavioral") {
    pipeline = [
      { agent: "business-analyst-v3", stage: "ba", gate: "after_ba" },
      { agent: "it-po-v3",          stage: "itpo", gate: "final" },
    ];
  } else {
    // technical (or amend → technical, or covered → force handled above)
    pipeline = [
      { agent: "it-po-v3", stage: "itpo", gate: "final" },
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
            `You are running as part of the /create-ac pipeline (route: ${effectiveRoute}). ` +
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
          // approve
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
            message: "ACs left as reviewed (deferred). Re-run /create-ac to approve.",
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

          approved = true;
          stageResults.push({ stage: step.stage, agent: step.agent, acs: written });

          return {
            status: "ok",
            message:
              `/create-ac complete. ${allAcsWritten.length} AC(s) approved with priority: ${priority}.`,
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
