/**
 * finalize-feature.js — Claude Code Workflow script
 *
 * Replaces the finalize-feature LLM agent for the post-merge feature
 * finalization sequence. Converts the 6-step orchestration from recursive
 * agent calls to a deterministic JavaScript workflow where every specialist
 * dispatch is a flat depth-1 agent() call.
 *
 * This is a LEAF WORKFLOW — it MUST NOT call workflow() internally. It is
 * callable by debug.js or build-epic.js via workflow("finalize-feature", {...}).
 * Calling workflow() from inside a child workflow would reintroduce nesting.
 *
 * Architecture:
 *   Pre-flight: status-checker reads current branch and worktree root
 *   Step 1: probe for open PR (gh pr list); dispatch pull-request if missing
 *   Step 2: probe PR state (gh pr view); prompt() merge gate if not merged
 *   Step 3: dispatch status-checker to sync main (git checkout main && git pull)
 *   Step 4: dispatch test-runner; HALT if tests fail (do not proceed to 5/6)
 *   Step 5: dispatch status-checker to detect scope and close tickets/archive epic
 *   Step 6: probe worktree list; dispatch worktree-agent remove if worktree exists
 *
 * Resumability: each step probes observable state before dispatching. Re-running
 * /finalize-feature after a mid-run crash resumes from the first incomplete step.
 *
 * ADR: docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
 * Ticket: tickets/00_inbox/TICKET-20260602-FinalizeFeatureJSWorkflow.md
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 * Fallback: for older installs, templates/agents/finalize-feature.md is used instead.
 */

const meta = {
  name: "finalize-feature",
  description:
    "Post-merge feature finalization: open PR if missing, merge to main, sync " +
    "local main, run tests, close tickets/archive epic, remove worktree. " +
    "Prompt gates on all destructive steps. HALT on test failure before ticket " +
    "closing. Returns { status: ok } with per-step summary on full success.",
  phases: [
    "pre-flight (status-checker reads branch + worktree root)",
    "step-1: open PR if missing (pull-request agent)",
    "step-2: merge PR to main (prompt gate + pull-request agent)",
    "step-3: sync local main (status-checker shell)",
    "step-4: run post-merge tests (test-runner — HALT on failure)",
    "step-5: close tickets / archive epic (status-checker)",
    "step-6: remove worktree (worktree-agent — gate delegated)",
  ],
};

/**
 * Main entry point called by the Claude Code workflow runtime.
 *
 * NOTE: `workflow` is intentionally absent from the destructure — this is a
 * leaf workflow. Calling workflow() from inside finalize-feature.js would
 * reintroduce the nesting violation this script is designed to prevent.
 * Any accidental call to `workflow` will throw a TypeError at runtime.
 *
 * @param {object} params
 * @param {string} params.userInput  - Optional extra arguments (unused; context read from git).
 * @param {Function} params.agent    - Runtime-provided agent dispatch function (depth 1).
 * @param {Function} params.parallel - Runtime-provided parallel dispatch (unused in this leaf).
 * @param {Function} params.prompt   - Runtime-provided user-prompt function for gate steps.
 */
async function run({ userInput, agent, parallel, prompt }) {
  // -------------------------------------------------------------------------
  // Pre-flight: detect branch and worktree root
  // -------------------------------------------------------------------------
  const preflightResult = await agent({
    agentType: "status-checker",
    input: {
      instructions:
        "Run these shell commands and return the results as a JSON object:\n" +
        "1. `git branch --show-current` — current branch name\n" +
        "2. `git rev-parse --show-toplevel` — absolute path to the worktree root\n" +
        "Return ONLY: { \"branch\": \"<name>\", \"worktree_root\": \"<path>\" }",
    },
  });

  let preflightInfo;
  try {
    preflightInfo =
      typeof preflightResult === "string"
        ? JSON.parse(preflightResult)
        : preflightResult;
  } catch (_err) {
    preflightInfo = { branch: "unknown", worktree_root: "unknown" };
  }

  const BRANCH = (preflightInfo.branch || "").trim();
  const WORKTREE_ROOT = (preflightInfo.worktree_root || "").trim();

  if (!BRANCH || BRANCH === "main" || BRANCH === "master") {
    return {
      status: "error",
      message:
        "/finalize-feature must be run from a feature branch, not main/master " +
        `(detected branch: "${BRANCH}"). ` +
        "Checkout your feature branch and re-run.",
      action_required: "switch_to_feature_branch",
    };
  }

  // Track completed and skipped steps for the final summary.
  const completedSteps = [];
  const skippedSteps = [];
  let prNumber = null;
  let prUrl = null;
  let mergeResult = null;
  let testResult = null;
  const ticketsClosed = [];
  let worktreeRemoved = false;

  // -------------------------------------------------------------------------
  // Step 1 — Open PR if missing (non-destructive, no confirmation gate)
  // -------------------------------------------------------------------------
  const prProbeResult = await agent({
    agentType: "status-checker",
    input: {
      instructions:
        `Run: gh pr list --head "${BRANCH}" --json number,url --jq '.[0]'\n` +
        "Return ONLY a JSON object:\n" +
        "- If a PR is found: { \"found\": true, \"number\": <N>, \"url\": \"<url>\" }\n" +
        "- If no PR exists: { \"found\": false }",
    },
  });

  let prProbe;
  try {
    prProbe =
      typeof prProbeResult === "string"
        ? JSON.parse(prProbeResult)
        : prProbeResult;
  } catch (_err) {
    prProbe = { found: false };
  }

  if (prProbe.found) {
    prNumber = prProbe.number;
    prUrl = prProbe.url;
    skippedSteps.push({ step: 1, reason: `PR already open (#${prNumber}) — skipping step 1` });
  } else {
    // Dispatch pull-request agent to open the PR.
    const openPrResult = await agent({
      agentType: "pull-request",
      input: {
        branch: BRANCH,
        action: "open",
        instructions:
          "Open a pull request for the current feature branch. " +
          "Return ONLY a JSON object: { \"number\": <N>, \"url\": \"<url>\" }",
      },
    });

    let openPr;
    try {
      openPr =
        typeof openPrResult === "string" ? JSON.parse(openPrResult) : openPrResult;
    } catch (_err) {
      openPr = {};
    }

    prNumber = openPr.number || openPr.pr_number || null;
    prUrl = openPr.url || openPr.pr_url || null;
    completedSteps.push(1);
  }

  // -------------------------------------------------------------------------
  // Step 2 — Merge PR to main (destructive — prompt gate required)
  // -------------------------------------------------------------------------
  // First probe current PR state to support crash-resume.
  const prStateResult = await agent({
    agentType: "status-checker",
    input: {
      instructions:
        `Run: gh pr view ${prNumber} --json state --jq '.state'\n` +
        "Return ONLY a JSON object: { \"state\": \"OPEN\"|\"MERGED\"|\"CLOSED\" }",
    },
  });

  let prState;
  try {
    prState =
      typeof prStateResult === "string"
        ? JSON.parse(prStateResult)
        : prStateResult;
  } catch (_err) {
    prState = { state: "OPEN" };
  }

  if ((prState.state || "").toUpperCase() === "MERGED") {
    // PR already merged — skip the merge gate and proceed.
    skippedSteps.push({ step: 2, reason: "PR already merged — skipping step 2" });
  } else {
    // Present merge summary and ask for confirmation.
    const mergeConfirm = await prompt(
      `Merge PR #${prNumber} (\`${BRANCH}\` → main)? (yes / no)`
    );

    if (!mergeConfirm || mergeConfirm.trim().toLowerCase() !== "yes") {
      return {
        status: "halted",
        halted_at_step: 2,
        reason: "user_declined_merge",
        message: "Finalization halted at merge step. No changes made.",
        branch: BRANCH,
        pr_number: prNumber,
        pr_url: prUrl,
        completed_steps: completedSteps,
        skipped_steps: skippedSteps,
      };
    }

    // Dispatch pull-request agent for the merge operation.
    mergeResult = await agent({
      agentType: "pull-request",
      input: {
        branch: BRANCH,
        pr_number: prNumber,
        action: "merge",
        instructions:
          `Merge PR #${prNumber} to main using: gh pr merge ${prNumber} --merge --auto\n` +
          "Wait for the merge to complete, then return a JSON object: " +
          "{ \"merged\": true, \"sha\": \"<merge-commit-sha>\" }",
      },
    });

    completedSteps.push(2);
  }

  // -------------------------------------------------------------------------
  // Step 3 — Sync local main (resumable)
  // -------------------------------------------------------------------------
  const syncResult = await agent({
    agentType: "status-checker",
    input: {
      instructions:
        "Run these commands in sequence:\n" +
        "1. `git checkout main`\n" +
        "2. `git pull`\n" +
        "3. `git log -1 --oneline`\n" +
        "Report the final HEAD SHA and commit message. " +
        "Return a JSON object: { \"head_sha\": \"<sha>\", \"head_message\": \"<message>\" }",
    },
  });

  completedSteps.push(3);

  // -------------------------------------------------------------------------
  // Step 4 — Run post-merge tests (always runs; HALT on failure)
  // -------------------------------------------------------------------------
  testResult = await agent({
    agentType: "test-runner",
    input: {
      instructions:
        "Run the full test suite on the current main branch. " +
        "Return a JSON object: { \"passed\": true|false, \"output\": \"<verbatim test output>\" }",
    },
  });

  let testPassed;
  try {
    const parsed =
      typeof testResult === "string" ? JSON.parse(testResult) : testResult;
    testPassed = parsed && parsed.passed === true;
    testResult = parsed;
  } catch (_err) {
    // If parsing fails, assume failure to be safe.
    testPassed = false;
  }

  if (!testPassed) {
    return {
      status: "halted",
      halted_at_step: 4,
      reason: "post_merge_test_failure",
      message:
        "Post-merge tests failed on main. Tickets have NOT been closed. " +
        "Worktree has NOT been removed.",
      test_output:
        (testResult && testResult.output) ||
        JSON.stringify(testResult),
      action_required:
        "Fix the regression on a new branch, then re-run /finalize-feature.",
      branch: BRANCH,
      pr_number: prNumber,
      pr_url: prUrl,
      completed_steps: completedSteps,
      skipped_steps: skippedSteps,
    };
  }

  completedSteps.push(4);

  // -------------------------------------------------------------------------
  // Step 5 — Close tickets / archive epic (resumable)
  //
  // Sub-step 5a: detect scope and close tickets (flip status: done in frontmatter
  //   + git mv to target folder).
  // Sub-step 5b: reconcile folder positions for any ticket file whose physical
  //   folder does not match its frontmatter `status:` after merge.
  //   This is necessary because worktree branches no longer perform git mv —
  //   the move-on-main-only pattern defers all moves to this post-merge step.
  //
  // Resumability: each sub-step probes state before acting.
  //   - Sub-step 5a: if ticket is already `done` and in the correct folder, it is skipped.
  //   - Sub-step 5b: if the reconciliation commit already exists (checked via
  //     `git log --oneline --grep "reconcile folder positions"`), the entire sub-step
  //     is skipped. If a ticket file is already in its target folder, git mv is skipped
  //     for that file (idempotent per-file).
  // -------------------------------------------------------------------------

  // Sub-step 5a: ticket closing / epic archival
  const closeResult = await agent({
    agentType: "status-checker",
    input: {
      branch: BRANCH,
      instructions:
        "Detect branch scope and close completed tickets:\n" +
        `1. Run: git log --oneline main..${BRANCH} 2>/dev/null || git log --oneline -20\n` +
        "2. Search tickets/ tree for ticket files referencing this branch or with status != done.\n" +
        "3. Determine if any ticket path is inside an EPIC-*/ folder — if so, this is epic-scoped.\n" +
        "4. For single-ticket branches: check if ticket status is already 'done'; if not, " +
        "   move the ticket file to tickets/99_done/ and flip status: todo → status: done.\n" +
        "5. For epic-scoped branches: run the epic archival gate (verify all sub-tickets are done), " +
        "   then git mv the epic folder to tickets/99_done/EPIC-<Name>/.\n" +
        "6. Return a JSON object: " +
        '{ "scope": "single-ticket"|"epic"|"unknown", ' +
        '"tickets_closed": ["<path>", ...], ' +
        '"already_done": ["<path>", ...], ' +
        '"skipped": false|true }',
    },
  });

  let closeInfo;
  try {
    closeInfo =
      typeof closeResult === "string" ? JSON.parse(closeResult) : closeResult;
  } catch (_err) {
    closeInfo = { tickets_closed: [], already_done: [], skipped: false };
  }

  if (closeInfo.tickets_closed) {
    ticketsClosed.push(...closeInfo.tickets_closed);
  }

  if (closeInfo.skipped) {
    skippedSteps.push({ step: 5, reason: "All tickets already done — skipping step 5" });
  } else {
    completedSteps.push(5);
  }

  // Sub-step 5b: folder reconciliation (EPIC-MoveOnMainOnly/03)
  //
  // After tickets 01 and 02 land, worktree branches no longer perform git mv.
  // Ticket files arrive on main in whatever folder the branch had them in
  // (typically 00_inbox/ for new tickets). This sub-step reconciles each
  // ticket file's physical folder position against its frontmatter `status:`.
  //
  // Status → target folder mapping (from ticket_lifecycle.json):
  //   done, deferred  → tickets/99_done/
  //   todo, in_progress, blocked → tickets/01_todo/
  //   (epic sub-tickets with status: done → tickets/01_todo/EPIC-*/done/)
  //
  // Single-writer guarantee: this git mv runs on main inside finalize-feature.js,
  // which is only invoked after the feature branch has been merged. No concurrent
  // worktrees are active on the same ticket at this point.
  const reconcileResult = await agent({
    agentType: "status-checker",
    input: {
      instructions:
        // Resumability probe: skip entire sub-step if reconciliation commit exists.
        "1. Run: git log --oneline --grep 'reconcile folder positions' | head -1\n" +
        "   If output is non-empty, the reconciliation commit already exists.\n" +
        "   Log: 'Reconciliation commit already present — skipping.'\n" +
        "   Return: { \"tickets_reconciled\": [], \"skipped\": true }\n" +
        "\n" +
        "2. Otherwise, read ticket_lifecycle.json from the repo root.\n" +
        "   Build the status→folder map:\n" +
        "   - done, deferred → tickets/99_done/\n" +
        "   - todo, in_progress, blocked → tickets/01_todo/\n" +
        "\n" +
        "3. Find all ticket files in the repo (find tickets/ -name '*.md' -not -name 'Master_Plan.md').\n" +
        "   For each ticket file:\n" +
        "   a. Parse the frontmatter `status:` value (read lines between first and second '---' markers).\n" +
        "   b. Determine the current folder (dirname of the file path).\n" +
        "   c. Compute the target folder from the status→folder map.\n" +
        "      - For epic sub-tickets (path contains /EPIC-*/): status: done → tickets/01_todo/EPIC-*/done/\n" +
        "   d. If current folder == target folder: skip (already in correct position).\n" +
        "   e. GUARD: if a file already exists at <target_folder>/<basename>, skip and log a warning:\n" +
        "      'WARNING: target path <target_path> already exists — skipping to avoid collision.\n" +
        "       Run the duplicate cleanup tool (EPIC-MoveOnMainOnly/06) to resolve.'\n" +
        "   f. If current folder != target folder AND no collision: run git mv <current_path> <target_folder>/<basename>.\n" +
        "      Accumulate the moved path in reconciled_paths.\n" +
        "\n" +
        "4. If any files were moved (reconciled_paths is non-empty):\n" +
        "   Run: git add tickets/\n" +
        "   Run: git commit -m 'chore(tickets): reconcile folder positions after merge'\n" +
        "   Verify the commit contains only R (rename) entries — no A/D pairs.\n" +
        "   Log: 'Folder reconciliation complete — <N> file(s) moved.'\n" +
        "\n" +
        "5. If no files needed moving:\n" +
        "   Log: 'Folder positions already correct — skipping reconciliation commit.'\n" +
        "\n" +
        "6. Return a JSON object:\n" +
        '{ "tickets_reconciled": ["<path1>", ...], "skipped": false|true, "warnings": ["<w1>", ...] }',
    },
  });

  let reconcileInfo;
  const ticketsReconciled = [];
  try {
    reconcileInfo =
      typeof reconcileResult === "string"
        ? JSON.parse(reconcileResult)
        : reconcileResult;
  } catch (_err) {
    reconcileInfo = { tickets_reconciled: [], skipped: false, warnings: [] };
  }

  if (reconcileInfo.tickets_reconciled) {
    ticketsReconciled.push(...reconcileInfo.tickets_reconciled);
  }

  // -------------------------------------------------------------------------
  // Step 6 — Remove worktree (resumable; confirmation gate delegated to agent)
  // -------------------------------------------------------------------------
  const worktreeProbeResult = await agent({
    agentType: "status-checker",
    input: {
      instructions:
        `Run: git worktree list --porcelain\n` +
        `Check if a worktree for WORKTREE_ROOT="${WORKTREE_ROOT}" is listed.\n` +
        "Return ONLY a JSON object: { \"exists\": true|false }",
    },
  });

  let worktreeProbe;
  try {
    worktreeProbe =
      typeof worktreeProbeResult === "string"
        ? JSON.parse(worktreeProbeResult)
        : worktreeProbeResult;
  } catch (_err) {
    worktreeProbe = { exists: true }; // default-conservative: assume it exists
  }

  if (!worktreeProbe.exists) {
    worktreeRemoved = false;
    skippedSteps.push({ step: 6, reason: "Worktree already absent — skipping step 6" });
  } else {
    // Dispatch worktree-agent (it owns its own confirmation gate).
    const worktreeResult = await agent({
      agentType: "worktree-agent",
      input: {
        action: "remove",
        worktree_path: WORKTREE_ROOT,
        instructions:
          `Remove the worktree at ${WORKTREE_ROOT}. ` +
          "If conflict_pids are reported, surface them verbatim and stop. " +
          "Return a JSON object: { \"removed\": true|false, \"conflict_pids\": [] }",
      },
    });

    let wResult;
    try {
      wResult =
        typeof worktreeResult === "string"
          ? JSON.parse(worktreeResult)
          : worktreeResult;
    } catch (_err) {
      wResult = { removed: false, conflict_pids: [] };
    }

    if (wResult.conflict_pids && wResult.conflict_pids.length > 0) {
      // Surface conflict PIDs verbatim and stop — user must resolve manually.
      return {
        status: "halted",
        halted_at_step: 6,
        reason: "worktree_conflict_pids",
        message:
          "Worktree removal blocked by conflicting processes. " +
          "Resolve the conflict PIDs below, then re-run /finalize-feature.",
        conflict_pids: wResult.conflict_pids,
        branch: BRANCH,
        pr_number: prNumber,
        pr_url: prUrl,
        completed_steps: completedSteps,
        skipped_steps: skippedSteps,
        tickets_closed: ticketsClosed,
      };
    }

    worktreeRemoved = wResult.removed === true;
    completedSteps.push(6);
  }

  // -------------------------------------------------------------------------
  // Step 7 — Return success summary
  // -------------------------------------------------------------------------
  return {
    status: "ok",
    branch: BRANCH,
    pr_number: prNumber,
    pr_url: prUrl,
    merge_result: mergeResult,
    test_result: testResult,
    tickets_closed: ticketsClosed,
    tickets_reconciled: ticketsReconciled,
    worktree_removed: worktreeRemoved,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
    message:
      `Feature "${BRANCH}" finalized. ` +
      `Steps completed: [${completedSteps.join(", ")}]. ` +
      (skippedSteps.length > 0
        ? `Steps skipped (already done): [${skippedSteps.map((s) => s.step).join(", ")}]. `
        : "") +
      (ticketsClosed.length > 0
        ? `Tickets closed: ${ticketsClosed.length}. `
        : "") +
      (ticketsReconciled.length > 0
        ? `Tickets folder-reconciled: ${ticketsReconciled.length}.`
        : ""),
  };
}
