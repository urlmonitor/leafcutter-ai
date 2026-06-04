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
    "Post-merge feature finalization: capture pre-merge test baseline on main, " +
    "open PR if missing, merge to main, sync local main, run post-merge tests " +
    "(with triage baseline), close tickets/archive epic, remove worktree. " +
    "Prompt gates on all destructive steps. HALT on test failure before ticket " +
    "closing. Returns { status: ok } with per-step summary on full success.",
  phases: [
    "pre-flight (status-checker reads branch + worktree root)",
    "step-0: capture baseline test run on main HEAD (test-runner — graceful on failure)",
    "step-1: open PR if missing (pull-request agent)",
    "step-2: merge PR to main (prompt gate + pull-request agent)",
    "step-3: sync local main (status-checker shell)",
    "step-3.5: merge origin/main into worktree --no-commit --no-ff (HALT on conflict)",
    "step-4a: run post-merge tests (test-runner — HALT on failure)",
    "step-4b: triage_failures — dispatch test-failure-triage when failures exist",
    "step-4c: halt-or-continue gate based on triage_report.blocks_finalization",
    "step-5: create_pre_existing_tickets — dispatch create-ticket for each pre_existing/flaky triage entry",
    "step-5b: close tickets / archive epic (status-checker)",
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
  const createdTrackingTickets = [];
  let worktreeRemoved = false;
  // Triage report from step 4b; null means tests passed (no triage needed).
  let triageReport = null;

  // Baseline state (populated by step 0; forwarded to step 4 triage).
  // null means the baseline run did not complete — triage treats all failures
  // as regressions in that case (conservative classification).
  let baselineFailures = null; // string[] | null
  let baselineSha = null;      // string | null
  let baselineRunAt = null;    // ISO string | null

  // Cleanup guard: remove temp baseline worktree on any early exit.
  // The path is set by step 0 and cleared after the worktree is removed.
  let baselineWorktreePath = null;

  /**
   * Attempt to remove the temporary baseline worktree if it still exists.
   * Silently swallows errors — this is a best-effort cleanup.
   */
  async function cleanupBaselineWorktree() {
    if (!baselineWorktreePath) return;
    try {
      await agent({
        agentType: "status-checker",
        input: {
          instructions:
            `Remove the temporary baseline worktree if it still exists:\n` +
            `Run: git worktree remove "${baselineWorktreePath}" --force 2>/dev/null || true\n` +
            `Run: rm -rf "${baselineWorktreePath}" 2>/dev/null || true\n` +
            `Return: { "removed": true }`,
        },
      });
    } catch (_err) {
      // Swallow — cleanup is best-effort.
    }
    baselineWorktreePath = null;
  }

  // -------------------------------------------------------------------------
  // Step 0 — Capture pre-merge test baseline on current main HEAD
  //
  // Creates a temporary worktree at origin/main, runs test-runner against it,
  // and stores the list of failing test IDs as the baseline. This baseline is
  // passed to the triage agent in step 4 so regressions can be distinguished
  // from pre-existing failures.
  //
  // Graceful degradation: if the worktree creation or test run fails for any
  // reason, log a warning and set baselineFailures = null. The workflow DOES
  // NOT halt — triage will classify all failures conservatively as regressions.
  //
  // Resumability: if a baseline worktree path from a previous run exists, the
  // agent will attempt to remove it first before creating a new one.
  // -------------------------------------------------------------------------
  const baselineTs = Date.now();
  const baselineTmpPath = `/tmp/leafcutter-main-baseline-${baselineTs}`;

  // Set the cleanup guard path so cleanupBaselineWorktree() can remove it on
  // any early exit after this point. Step 0 clears it on success (step D).
  baselineWorktreePath = baselineTmpPath;

  const baselineResult = await agent({
    agentType: "status-checker",
    input: {
      instructions:
        "Capture a pre-merge test baseline on the current main HEAD.\n" +
        "\n" +
        "Step A — Create a temporary detached worktree at origin/main:\n" +
        `  Run: git worktree add --detach "${baselineTmpPath}" origin/main\n` +
        "  Capture the exit code.\n" +
        "  If exit code is non-zero:\n" +
        "    Log: 'Baseline worktree creation failed — triage will treat all failures as regressions.'\n" +
        "    Return: { \"status\": \"worktree_failed\", \"baseline_sha\": null,\n" +
        "              \"baseline_failures\": null, \"baseline_run_at\": null }\n" +
        "\n" +
        "Step B — Capture the SHA of main HEAD inside the temp worktree:\n" +
        `  Run: git -C "${baselineTmpPath}" rev-parse HEAD\n` +
        "  Store as <baseline_sha>.\n" +
        "\n" +
        "Step C — Run the test suite inside the temp worktree:\n" +
        `  Run inside "${baselineTmpPath}": pytest --tb=no -q 2>&1\n` +
        "  Collect each line that matches the pattern '<file>::<test_name> FAILED'.\n" +
        "  Build a list of failing test IDs (strings like 'test_foo.py::test_bar').\n" +
        "  Note: a zero-length list means the baseline is clean (all tests pass).\n" +
        "\n" +
        "Step D — Remove the temp worktree:\n" +
        `  Run: git worktree remove "${baselineTmpPath}" --force\n` +
        `  Run: rm -rf "${baselineTmpPath}" 2>/dev/null || true\n` +
        "\n" +
        "Step E — Return the baseline result:\n" +
        "  If the test run completed (even with failures): return:\n" +
        "    { \"status\": \"ok\",\n" +
        "      \"baseline_sha\": \"<sha>\",\n" +
        "      \"baseline_failures\": [<list of failing test IDs or empty>],\n" +
        "      \"baseline_run_at\": \"<ISO 8601 timestamp>\" }\n" +
        "  If the test run itself failed to execute (pytest not found, import error, etc.):\n" +
        "    Log: 'Baseline run failed — triage will treat all failures as regressions.'\n" +
        "    Return: { \"status\": \"run_failed\", \"baseline_sha\": \"<sha>\",\n" +
        "              \"baseline_failures\": null, \"baseline_run_at\": \"<ISO 8601 timestamp>\" }",
    },
  });

  let baselineInfo;
  try {
    baselineInfo =
      typeof baselineResult === "string"
        ? JSON.parse(baselineResult)
        : baselineResult;
  } catch (_err) {
    baselineInfo = { status: "parse_failed", baseline_sha: null, baseline_failures: null, baseline_run_at: null };
  }

  const baselineStatus = (baselineInfo.status || "unknown").toLowerCase();

  if (baselineStatus === "ok") {
    baselineFailures = Array.isArray(baselineInfo.baseline_failures)
      ? baselineInfo.baseline_failures
      : [];
    baselineSha = baselineInfo.baseline_sha || null;
    baselineRunAt = baselineInfo.baseline_run_at || null;
    // Step D ran successfully — temp worktree already removed by the agent.
    baselineWorktreePath = null;
    completedSteps.push(0);
  } else {
    // worktree_failed | run_failed | parse_failed | unknown — degrade gracefully.
    // baselineFailures stays null — triage will classify all failures as regressions.
    baselineSha = baselineInfo.baseline_sha || null;
    baselineRunAt = baselineInfo.baseline_run_at || null;
    // The agent may have left the temp worktree behind if it failed part-way;
    // keep baselineWorktreePath set so cleanup fires on any subsequent halt path.
    skippedSteps.push({
      step: 0,
      reason:
        `Baseline capture failed (${baselineStatus}) — ` +
        "triage will treat all post-merge failures as regressions",
    });
  }

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
      await cleanupBaselineWorktree();
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
  // Step 3.5 — Merge origin/main into the feature worktree (no commit)
  //
  // Inserts the merged state into the worktree so that tests in step 4 run
  // against the post-merge tree. Uses --no-commit --no-ff so no merge commit
  // is written to the feature branch. On conflict, git merge --abort cleans up
  // and the workflow halts with category merge_conflict.
  //
  // Resumability: probe git merge-base --is-ancestor to detect already-merged.
  // -------------------------------------------------------------------------
  const mergeMainResult = await agent({
    agentType: "status-checker",
    input: {
      instructions:
        "Run these commands inside the feature worktree to merge origin/main before tests:\n" +
        "\n" +
        "1. Check if the branch is already up-to-date with origin/main:\n" +
        `   Run: git merge-base --is-ancestor origin/main HEAD\n` +
        "   Exit code 0 means HEAD already contains all commits from origin/main.\n" +
        "   If exit code 0: log 'Already up-to-date with origin/main.' and return\n" +
        "   { \"status\": \"already_up_to_date\", \"merge_strategy\": \"already_up_to_date\" }\n" +
        "\n" +
        "2. If not up-to-date, fetch origin/main to ensure it is current:\n" +
        "   Run: git fetch origin main\n" +
        "\n" +
        "3. Attempt the merge (no commit, no fast-forward):\n" +
        "   Run: git merge origin/main --no-commit --no-ff\n" +
        "   Capture the exit code.\n" +
        "\n" +
        "4. If exit code is 0 (clean merge):\n" +
        "   Log: 'Merge clean — worktree reflects post-merge state.'\n" +
        "   Return: { \"status\": \"merged\", \"merge_strategy\": \"merged_main\" }\n" +
        "\n" +
        "5. If exit code is non-zero (conflict detected):\n" +
        "   Run: git merge --abort\n" +
        "   Return: { \"status\": \"conflict\", \"merge_strategy\": null }",
    },
  });

  let mergeMainInfo;
  try {
    mergeMainInfo =
      typeof mergeMainResult === "string"
        ? JSON.parse(mergeMainResult)
        : mergeMainResult;
  } catch (_err) {
    mergeMainInfo = { status: "conflict", merge_strategy: null };
  }

  const mergeStatus = (mergeMainInfo.status || "conflict").toLowerCase();

  if (mergeStatus === "conflict") {
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: "3.5",
      reason: "merge_conflict",
      message:
        "Feature branch has conflicts with main. Resolve conflicts and re-run.",
      branch: BRANCH,
      pr_number: prNumber,
      pr_url: prUrl,
      completed_steps: completedSteps,
      skipped_steps: skippedSteps,
    };
  }

  if (mergeStatus === "already_up_to_date") {
    skippedSteps.push({
      step: "3.5",
      reason: "Already up-to-date with origin/main",
    });
  } else {
    // merged_main path
    completedSteps.push("3.5");
  }

  const mergeStrategy = mergeMainInfo.merge_strategy || "already_up_to_date";

  // -------------------------------------------------------------------------
  // Step 4a — Run post-merge tests (always runs)
  //
  // The baseline captured in step 0 is forwarded here so the triage agent
  // in step 4b can compute:
  //   regressions = post_merge_failures − baseline_failures
  // If baseline_failures is null, all failures are treated as regressions
  // (conservative classification).
  // -------------------------------------------------------------------------
  testResult = await agent({
    agentType: "test-runner",
    input: {
      instructions:
        "Run the full test suite on the post-merge worktree. " +
        "Return a JSON object: { \"passed\": true|false, \"output\": \"<verbatim test output>\", " +
        "\"failing_tests\": [\"<file>::<test_name>\", ...] }",
      // Baseline context: forwarded so triage can classify failures.
      baseline_sha: baselineSha,
      baseline_failures: baselineFailures,
      baseline_run_at: baselineRunAt,
    },
  });

  let testPassed;
  let postMergeFailures;
  try {
    const parsed =
      typeof testResult === "string" ? JSON.parse(testResult) : testResult;
    testPassed = parsed && parsed.passed === true;
    testResult = parsed;
    postMergeFailures = (testResult && Array.isArray(testResult.failing_tests))
      ? testResult.failing_tests
      : [];
  } catch (_err) {
    // If parsing fails, assume failure to be safe.
    testPassed = false;
    postMergeFailures = [];
  }

  if (testPassed) {
    // Zero failures: skip 4b and 4c entirely, proceed to step 5.
    completedSteps.push("4a");
    // triageReport remains null — forwarded to step 5 as-is.
  } else {
    // -----------------------------------------------------------------------
    // Step 4b — Dispatch test-failure-triage when failures exist
    //
    // Passes post_merge_failures, baseline_failures, baseline_sha,
    // feature_branch, and changed_files (derived here via git diff) so the
    // triage agent can classify each failure as regression or pre-existing.
    // -----------------------------------------------------------------------

    // Derive changed_files: files touched by the feature branch relative to
    // origin/main. Captured at this point (after the --no-commit merge) so
    // the diff reflects the full feature delta including the merged state.
    const changedFilesResult = await agent({
      agentType: "status-checker",
      input: {
        instructions:
          "Run: git diff --name-only origin/main HEAD\n" +
          "Return ONLY a JSON object: { \"changed_files\": [\"<file1>\", \"<file2>\", ...] }\n" +
          "If the command fails or returns no output, return: { \"changed_files\": [] }",
      },
    });

    let changedFiles = [];
    try {
      const parsedCf =
        typeof changedFilesResult === "string"
          ? JSON.parse(changedFilesResult)
          : changedFilesResult;
      changedFiles = Array.isArray(parsedCf.changed_files) ? parsedCf.changed_files : [];
    } catch (_err) {
      // Default to empty list on parse failure — triage uses it as a hint only.
      changedFiles = [];
    }

    const triageRaw = await agent({
      agentType: "test-failure-triage",
      input: {
        post_merge_failures: postMergeFailures,
        baseline_failures: baselineFailures,
        baseline_sha: baselineSha,
        feature_branch: BRANCH,
        changed_files: changedFiles,
        instructions:
          "Classify each failing test as 'regression' (caused by this branch) or " +
          "'pre_existing' (already failing on main). " +
          "Return a JSON object with at minimum: { \"blocks_finalization\": true|false, " +
          "\"regressions\": [\"<test_id>\", ...], \"pre_existing\": [\"<test_id>\", ...], " +
          "\"summary\": \"<one sentence>\" }",
      },
    });

    try {
      triageReport =
        typeof triageRaw === "string" ? JSON.parse(triageRaw) : triageRaw;
    } catch (_err) {
      // Parse failure: treat as blocking — cannot determine safety.
      triageReport = {
        blocks_finalization: true,
        regressions: postMergeFailures,
        pre_existing: [],
        summary: "Triage report parse failed — treating all failures as regressions.",
      };
    }

    // Log the triage report to the user for visibility.
    console.log("[finalize-feature] step 4b triage report:", JSON.stringify(triageReport, null, 2));

    // -----------------------------------------------------------------------
    // Step 4c — Halt-or-continue gate based on triage_report.blocks_finalization
    //
    // If blocks_finalization is true: HARD EARLY RETURN. Steps 5 and 6 are
    // structurally unreachable from this point — no escape hatch.
    // If false: pass triage_report forward and continue to step 5.
    // -----------------------------------------------------------------------
    if (triageReport.blocks_finalization) {
      await cleanupBaselineWorktree();
      return {
        status: "halted",
        halted_at_step: "4c",
        reason: "regressions_or_stale_tests",
        triage_report: triageReport,
        message:
          "Fix regressions and stale tests before re-running /finalize-feature.",
        test_output:
          (testResult && testResult.output) ||
          JSON.stringify(testResult),
        branch: BRANCH,
        pr_number: prNumber,
        pr_url: prUrl,
        completed_steps: completedSteps,
        skipped_steps: skippedSteps,
      };
    }
    // blocks_finalization is false: all failures are pre-existing.
    // Store triage_report in workflow state and continue to step 5.
    completedSteps.push("4a");
    completedSteps.push("4b");
    completedSteps.push("4c");
  }

  // -------------------------------------------------------------------------
  // Step 5 — Create tracking tickets for pre-existing / flaky failures
  //
  // Before closing tickets and archiving the epic, dispatch create-ticket for
  // each entry in the triage report where category is "pre_existing" or "flaky".
  // This ensures every known breakage on main has a corresponding inbox ticket
  // before the feature branch is considered finalized.
  //
  // Failure policy: ticket creation failure is non-fatal. Log a warning and
  // continue. Finalization must not be blocked by a failed create-ticket call.
  //
  // Only runs when triageReport is non-null (tests had failures in step 4b).
  // When triageReport is null (all tests passed), this sub-step is a no-op.
  // -------------------------------------------------------------------------
  if (triageReport !== null) {
    const triageEntries = Array.isArray(triageReport.triage_report)
      ? triageReport.triage_report
      : [];

    const preExistingEntries = triageEntries.filter(
      (entry) =>
        entry.category === "pre_existing" || entry.category === "flaky"
    );

    for (const entry of preExistingEntries) {
      const testId = entry.test_id || "<unknown test>";
      const category = entry.category || "pre_existing";

      let requestText =
        `Tracked pre-existing test failure: ${testId}. ` +
        `Failing on main at SHA ${baselineSha || "unknown"}. ` +
        `Triage category: ${category}. ` +
        `See finalize-feature triage report from ${baselineRunAt || new Date().toISOString()}.`;

      if (category === "flaky") {
        requestText +=
          " Intermittent failure detected. Failing in some runs but not others." +
          " Needs investigation to determine root cause before adding a known-flaky marker.";
      }

      try {
        const createTicketResult = await agent({
          agentType: "create-ticket",
          input: {
            request: requestText,
          },
        });

        let ticketInfo;
        try {
          ticketInfo =
            typeof createTicketResult === "string"
              ? JSON.parse(createTicketResult)
              : createTicketResult;
        } catch (_parseErr) {
          ticketInfo = { ticket_path: null };
        }

        const ticketPath =
          ticketInfo &&
          (ticketInfo.ticket_path || ticketInfo.path || ticketInfo.filename);

        if (ticketPath) {
          createdTrackingTickets.push(ticketPath);
          console.log(
            `[finalize-feature] step 5: created tracking ticket for ${testId}: ${ticketPath}`
          );
        } else {
          // create-ticket succeeded but did not return a path — push null as sentinel.
          createdTrackingTickets.push(null);
          console.warn(
            `[finalize-feature] step 5: create-ticket for ${testId} returned no ticket_path`
          );
        }
      } catch (createErr) {
        // Non-fatal: log warning and continue.
        console.warn(
          `[finalize-feature] step 5: create-ticket dispatch failed for ${testId}: ${createErr && createErr.message}`
        );
        createdTrackingTickets.push(null);
      }
    }

    if (preExistingEntries.length === 0) {
      console.log(
        "[finalize-feature] step 5: no pre_existing or flaky entries in triage report — skipping create-ticket sub-step"
      );
    }
  }

  // -------------------------------------------------------------------------
  // Step 5b — Close tickets / archive epic (resumable)
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
        "5. For epic-scoped branches: before moving the epic folder, run the\n" +
        "   finalize-feature-archive-check skill:\n" +
        "   a. Find all *.md files under <epic_folder>/done/ (excluding Master_Plan.md).\n" +
        "   b. For each file, parse the YAML frontmatter and read the `status:` field.\n" +
        "   c. Build two lists: ok_tickets (status: done) and missing_tickets (any other value).\n" +
        "   d. If missing_tickets is non-empty, surface the list to the user and ask:\n" +
        "      'Auto-fix: set status: done in frontmatter for all listed tickets and commit? (yes / no)'\n" +
        "   e. On 'yes': edit each missing ticket's frontmatter, git add, commit with message\n" +
        "      'chore(tickets): fix frontmatter status on archived sub-tickets', then re-scan.\n" +
        "   f. On 'no': HALT — return { status: 'halted', scope: 'epic',\n" +
        "      reason: 'user declined archive status fix — epic folder move blocked',\n" +
        "      missing_tickets: [...] }. Do NOT proceed to git mv.\n" +
        "   g. Only when all sub-tickets have status: done: run the epic archival gate\n" +
        "      (verify all sub-tickets are signed_off or not_needed), then\n" +
        "      git mv the epic folder to tickets/99_done/EPIC-<Name>/.\n" +
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
    merge_strategy: mergeStrategy,
    // Baseline context included in the summary for auditability.
    baseline_sha: baselineSha,
    baseline_failures: baselineFailures,
    baseline_run_at: baselineRunAt,
    test_result: testResult,
    // Triage report from step 4b; null means tests passed (no triage needed).
    triage_report: triageReport,
    tickets_closed: ticketsClosed,
    // Tracking tickets created in step 5 for pre_existing and flaky triage entries.
    // Each entry is the ticket_path returned by create-ticket, or null on failure.
    created_tracking_tickets: createdTrackingTickets,
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
      (baselineFailures !== null
        ? `Baseline captured at ${baselineSha} (${baselineFailures.length} pre-existing failure(s)). `
        : "Baseline capture failed — regression triage used conservative classification. ") +
      (ticketsClosed.length > 0
        ? `Tickets closed: ${ticketsClosed.length}. `
        : "") +
      (createdTrackingTickets.length > 0
        ? `Tracking tickets created for pre-existing failures: ${createdTrackingTickets.filter(Boolean).length}. `
        : "") +
      (ticketsReconciled.length > 0
        ? `Tickets folder-reconciled: ${ticketsReconciled.length}.`
        : ""),
  };
}
