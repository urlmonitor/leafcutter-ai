/**
 * finalize-feature.js — Claude Code Workflow script
 *
 * Replaces the finalize-feature LLM agent for the post-merge feature
 * finalization sequence. Converts the 6-step orchestration from recursive
 * agent calls to a deterministic JavaScript workflow where every specialist
 * dispatch is a flat depth-1 agent() call.
 *
 * This is a LEAF WORKFLOW — it MUST NOT call workflow() internally. In E2,
 * workflow() throws (leaf-invariant guard) — this is preserved by design.
 * Calling workflow() from inside a child workflow would reintroduce nesting.
 *
 * Architecture:
 *   Pre-flight: status-checker reads current branch and worktree root
 *   Step 0: capture baseline test run on main HEAD (test-runner — graceful on failure)
 *   Step 1: probe for open PR (gh pr list); dispatch pull-request if missing
 *   Step 2: merge origin/main into worktree --no-commit --no-ff (HALT on conflict)
 *   Step 3: run post-merge tests + triage; HALT if regressions detected
 *   Step 4: merge PR to main — only if tests pass (confirmation-gated)
 *   Step 5: sync local main (git checkout main && git pull)
 *   Step 6: report untracked pre-existing/flaky failures (auto-ticketing disabled) + scope-detection
 *   Step 7: probe worktree list; dispatch worktree-agent remove if worktree exists
 *
 * Resumability: each step probes observable state before dispatching. Re-running
 * /finalize-feature after a mid-run crash resumes from the first incomplete step.
 *
 * E2 canonical form: top-level body, agent(prompt, opts), args global.
 * No export async function run() — E2 executes the top-level body directly.
 * workflow() is NOT called (leaf-invariant preserved: E2 throws, which is correct).
 *
 * ADR: docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
 * Ticket: tickets/00_inbox/TICKET-20260602-FinalizeFeatureJSWorkflow.md
 *
 * Minimum Claude Code version: 2.1.154 (workflow script support)
 * No fallback: the legacy LLM agent (finalize-feature.md) has been removed. Older
 * installs receive an explicit error from the slash command.
 */

export const meta = {
  name: "finalize-feature",
  description:
    "Post-merge feature finalization: capture pre-merge test baseline on main, open PR if missing, merge origin/main into worktree, run post-merge tests (with triage baseline), merge PR to main only when tests pass, sync local main, close tickets/archive epic, remove worktree. Prompt gates on all destructive steps. HALT on test regression before PR merge. Returns { status: ok } with per-step summary on full success.",
  phases: [
    "pre-flight (status-checker reads branch + worktree root)",
    "step-0: capture baseline test run on main HEAD (test-runner — graceful on failure)",
    "step-1: open PR if missing (pull-request agent)",
    "step-2: merge origin/main into worktree --no-commit --no-ff (HALT on conflict)",
    "step-3: run post-merge tests + triage (test-runner + test-failure-triage — HALT on regressions)",
    "step-3.5: pre-merge AC closure — reset test-merge, set ticket status: done + mark source ACs done, commit on feature branch",
    "step-4: merge PR to main — only if tests pass (prompt gate + pull-request agent)",
    "step-5: sync local main (status-checker shell)",
    "step-6: report untracked pre-existing/flaky failures (auto-ticketing disabled) + scope-detection (status-checker — no writes on main)",
    "step-7: remove worktree (worktree-agent — gate delegated)",
  ],
};

// ---------------------------------------------------------------------------
// JSON Schemas for agent() responses (E2: engine enforces; no JSON.parse needed)
// ---------------------------------------------------------------------------

const GATE_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'blocked'] },
    message: { type: 'string' },
  },
  required: ['status'],
}

// ---------------------------------------------------------------------------
// E2 top-level body — executed directly by the E2 engine
//
// NOTE on leaf invariant: workflow() is NOT called anywhere in this script.
// In E2, workflow() throws — that throw IS the leaf guard. Since we never call
// workflow(), the leaf invariant is preserved without any explicit check.
// ---------------------------------------------------------------------------

// -------------------------------------------------------------------------
// Pre-flight: detect branch and worktree root
// -------------------------------------------------------------------------

phase('Pre-flight')

/**
 * AC-4: Tolerant JSON parse helper.
 *
 * Distinguishes between two failure modes:
 *   1. Agent returned a value that is already an object/array (pass-through).
 *   2. Agent returned a string — try JSON.parse; on failure, scan for a JSON
 *      object or array embedded inside freeform prose.
 *
 * Returns { value: <parsed>, malformed: false } on success.
 * Returns { value: null, malformed: true } when no parseable JSON is found.
 *
 * @param {*} raw  - Value returned by agent() — may be string, object, or null.
 * @returns {{ value: *, malformed: boolean }}
 */
function safeParseJSON(raw) {
  if (raw === null || raw === undefined) {
    return { value: null, malformed: true };
  }
  // Already a non-string (object, array, boolean, number) — use directly.
  if (typeof raw !== "string") {
    return { value: raw, malformed: false };
  }
  // Try direct parse first.
  try {
    return { value: JSON.parse(raw), malformed: false };
  } catch (_) {
    // Try to extract a JSON object or array from inside prose.
    const objMatch = raw.match(/\{[\s\S]*\}/);
    if (objMatch) {
      try {
        return { value: JSON.parse(objMatch[0]), malformed: false };
      } catch (_) {
        // fall through
      }
    }
    const arrMatch = raw.match(/\[[\s\S]*\]/);
    if (arrMatch) {
      try {
        return { value: JSON.parse(arrMatch[0]), malformed: false };
      } catch (_) {
        // fall through
      }
    }
    return { value: null, malformed: true };
  }
}

// -------------------------------------------------------------------------
// Pre-flight worktree resolution
//
// Fix (TICKET-20260707-Finalize_Preflight_Branch_Detection):
// Previously the pre-flight ran `git branch --show-current` with no -C
// anchor, reading from the session CWD — which is often the main clone on
// `main`. This caused a false "must be run from a feature branch" abort even
// when a valid epic worktree existed.
//
// The new approach:
//   1. Extract the epic/ticket name from `args` (e.g. "EPIC-FooBar").
//   2. Run `git worktree list --porcelain` (no anchor needed — lists all
//      registered worktrees for this repo regardless of CWD) to find the
//      worktree whose branch matches `EPIC-<name>` or the single-ticket branch.
//   3. Anchor the branch/toplevel detection at the resolved worktree root
//      using `git -C <worktree_root>`.
//   4. When no matching worktree is found, fail with a clear, actionable
//      message (not a silent misdetection or a false "on main" abort).
//   5. When no arg is provided, fall back to the CWD-based detection so
//      existing callers that pass no argument are unaffected.
// -------------------------------------------------------------------------

// Extract the epic/ticket argument passed to the workflow.
// For `/finalize-feature EPIC-FooBar`, args is the string "EPIC-FooBar".
// When args is not a string (or is empty), fall back to CWD-based detection.
const epicArg = (typeof args === 'string' ? args.trim() : '');

const preflightResult = await agent(
  "Detect the target worktree branch and root path for /finalize-feature.\n" +
  "\n" +
  (epicArg
    ? "A target argument was provided. Resolve the worktree from it.\n" +
      `Argument: "${epicArg}"\n` +
      "\n" +
      "Step 1 — list all registered worktrees:\n" +
      "  Run: git worktree list --porcelain\n" +
      "  Parse the output. Each block starts with 'worktree <path>' followed by\n" +
      "  'HEAD <sha>' and optionally 'branch refs/heads/<branch_name>'.\n" +
      "  Detached-HEAD entries have no 'branch' line — skip them.\n" +
      "\n" +
      "Step 2 — find the matching worktree:\n" +
      "  Find a worktree whose branch_name:\n" +
      `    - equals "${epicArg}" (exact match), OR\n` +
      `    - equals "feature/${epicArg}", OR\n` +
      `    - contains "${epicArg}" as a substring.\n` +
      "  Exclude any worktree whose branch_name is 'main' or 'master'.\n" +
      "  If multiple candidates match, prefer the one whose branch_name is\n" +
      "  shortest (fewest extra characters beyond the argument string).\n" +
      "\n" +
      "Step 3a — matching worktree found:\n" +
      "  Let <wt_path> = the matched worktree path.\n" +
      "  Run: git -C \"<wt_path>\" branch --show-current\n" +
      "  Run: git -C \"<wt_path>\" rev-parse --show-toplevel\n" +
      "  Return ONLY: { \"found\": true, \"branch\": \"<branch_name>\", \"worktree_root\": \"<path>\" }\n" +
      "\n" +
      "Step 3b — no matching worktree found:\n" +
      `  Return ONLY: { "found": false, "branch": null, "worktree_root": null,\n` +
      `               "error": "No worktree found matching '${epicArg}'. ` +
      `Run \\"git worktree list\\" to see all registered worktrees." }`
    : "No target argument provided — fall back to CWD-based detection.\n" +
      "1. Run: git branch --show-current\n" +
      "2. Run: git rev-parse --show-toplevel\n" +
      "Return ONLY: { \"found\": true, \"branch\": \"<name>\", \"worktree_root\": \"<path>\" }"
  ),
  { agentType: "status-checker", label: "pre-flight", phase: "Pre-flight" }
)

let preflightInfo;
{
  const { value, malformed } = safeParseJSON(preflightResult);
  if (malformed) {
    log("[finalize-feature] pre-flight parse malformed — using safe defaults (branch: unknown)");
    preflightInfo = { found: true, branch: "unknown", worktree_root: "unknown" };
  } else {
    preflightInfo = value || { found: true, branch: "unknown", worktree_root: "unknown" };
  }
}

// When the worktree resolution step found no matching worktree, fail with a
// clear, actionable message rather than a silent misdetection.
if (preflightInfo.found === false) {
  return {
    status: "error",
    message:
      preflightInfo.error ||
      `/finalize-feature could not find a worktree matching "${epicArg}". ` +
      "Run `git worktree list` to see all registered worktrees, " +
      "then re-run with the correct epic or ticket name.",
    action_required: "resolve_worktree_argument",
  };
}

const BRANCH = (preflightInfo.branch || "").trim();
const WORKTREE_ROOT = (preflightInfo.worktree_root || "").trim();

if (!BRANCH || BRANCH === "main" || BRANCH === "master") {
  return {
    status: "error",
    message:
      "/finalize-feature must be run from a feature branch, not main/master " +
      `(detected branch: "${BRANCH}" from worktree resolved via arg: "${epicArg}"). ` +
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
// Failures that could not be auto-ticketed (create-ticket is a workflow, not an agent).
// Populated by step 6a; never confused with actually-created tickets.
const untrackedFailures = [];
let worktreeRemoved = false;
// Triage report from step 3; null means tests passed (no triage needed).
let triageReport = null;
// Closure counts from step 3.5 (pre-merge AC closure).
let ticketsClosedPreMerge = 0;
let acsClosed = 0;
let acsSkipped = 0;

// Baseline state (populated by step 0; forwarded to step 3 triage).
// null means the baseline run did not complete — triage treats all failures
// as regressions in that case (conservative classification).
let baselineFailures = null; // string[] | null
let baselineSha = null;      // string | null
let baselineRunAt = null;    // ISO string | null

// Cleanup guard: remove temp baseline worktree on any early exit.
// The path is set by step 0 and cleared after the worktree is removed.
// args.baseline_ts replaces Date.now() (banned in E2 — non-deterministic).
const baselineTmpPath = `/tmp/leafcutter-main-baseline-${args.baseline_ts || 'baseline'}`;
let baselineWorktreePath = null;

/**
 * Attempt to remove the temporary baseline worktree if it still exists.
 * Silently swallows errors — this is a best-effort cleanup.
 */
async function cleanupBaselineWorktree() {
  if (!baselineWorktreePath) return;
  // Use WORKTREE_ROOT for the -C anchor when it is already resolved; fall
  // back to the baseline path itself (which is a valid git repo checkout) so
  // the worktree remove still works even if WORKTREE_ROOT is "unknown".
  const gitAnchor = (WORKTREE_ROOT && WORKTREE_ROOT !== "unknown")
    ? WORKTREE_ROOT
    : baselineWorktreePath;
  try {
    await agent(
      `Remove the temporary baseline worktree if it still exists:\n` +
      `Run: git -C "${gitAnchor}" worktree remove "${baselineWorktreePath}" --force 2>/dev/null || true\n` +
      `Run: rm -rf "${baselineWorktreePath}" 2>/dev/null || true\n` +
      `Return: { "removed": true }`,
      { agentType: "status-checker", label: "cleanup-baseline-worktree" }
    );
  } catch (_err) {
    // Swallow — cleanup is best-effort.
  }
  baselineWorktreePath = null;
}

// -------------------------------------------------------------------------
// Pre-flight 2 — gh account verification (EMU-aware, config-driven)
//
// Reads `gh_target_account` and `gh_repo` from the worktree's settings.json
// (or config/settings.json). If the key is absent the pre-flight is a no-op
// so installs with no EMU constraint are unaffected (AC-4).
// -------------------------------------------------------------------------

phase('Pre-flight 2')

const ghConfigResult = await agent(
  "Read the gh account config from the worktree settings file.\n" +
  `Run: cat "${WORKTREE_ROOT}/settings.json" 2>/dev/null || cat "${WORKTREE_ROOT}/config/settings.json" 2>/dev/null || echo 'null'\n` +
  "Parse the JSON output (if any). Look for a top-level key 'gh_target_account' and 'gh_repo'.\n" +
  "Return ONLY a JSON object: { \"gh_target_account\": \"<value or null>\", \"gh_repo\": \"<owner/repo or null>\" }\n" +
  "If the file does not exist or the keys are absent, return: { \"gh_target_account\": null, \"gh_repo\": null }",
  { agentType: "status-checker", label: "gh-config", phase: "Pre-flight 2" }
)

let ghConfig;
{
  const { value, malformed } = safeParseJSON(ghConfigResult);
  if (malformed) {
    log("[finalize-feature] gh config parse malformed — proceeding with no account constraint");
    ghConfig = { gh_target_account: null, gh_repo: null };
  } else {
    ghConfig = value || { gh_target_account: null, gh_repo: null };
  }
}

const GH_TARGET_ACCOUNT = (ghConfig.gh_target_account || "").trim() || null;
const GH_REPO = (ghConfig.gh_repo || "").trim() || null;

if (GH_TARGET_ACCOUNT) {
  // Probe current active account.
  const ghStatusResult = await agent(
    "Run: gh auth status 2>&1\n" +
    "Parse the output to find which account is currently logged in and active.\n" +
    "The active account appears on the line containing 'Logged in to' or '✓ Logged in to'.\n" +
    "The active account username follows 'as ' (e.g. 'Logged in to github.com as urlmonitor').\n" +
    "Return ONLY a JSON object: { \"active_account\": \"<username or null>\" }",
    { agentType: "status-checker", label: "gh-auth-status", phase: "Pre-flight 2" }
  )

  let ghStatus;
  {
    const { value, malformed } = safeParseJSON(ghStatusResult);
    if (malformed) {
      log("[finalize-feature] gh auth status parse malformed — assuming active_account is null");
      ghStatus = { active_account: null };
    } else {
      ghStatus = value || { active_account: null };
    }
  }

  const activeAccount = (ghStatus.active_account || "").trim() || null;

  if (activeAccount !== GH_TARGET_ACCOUNT) {
    // Switch to the configured account.
    const ghSwitchResult = await agent(
      `Run: gh auth switch --user "${GH_TARGET_ACCOUNT}" 2>&1\n` +
      "Capture exit code and output.\n" +
      "Then re-verify: run `gh auth status 2>&1` and extract the active account (see prior step).\n" +
      "Return ONLY a JSON object: { \"switch_exit_code\": <integer>, \"verified_account\": \"<username or null>\" }",
      { agentType: "status-checker", label: "gh-auth-switch", phase: "Pre-flight 2" }
    )

    let ghSwitch;
    {
      const { value, malformed } = safeParseJSON(ghSwitchResult);
      if (malformed) {
        log("[finalize-feature] gh switch parse malformed — assuming switch failed");
        ghSwitch = { switch_exit_code: 1, verified_account: null };
      } else {
        ghSwitch = value || { switch_exit_code: 1, verified_account: null };
      }
    }

    const verifiedAccount = (ghSwitch.verified_account || "").trim() || null;
    const switchFailed =
      ghSwitch.switch_exit_code !== 0 || verifiedAccount !== GH_TARGET_ACCOUNT;

    if (switchFailed) {
      return {
        status: "error",
        message:
          `gh account pre-flight failed: could not activate '${GH_TARGET_ACCOUNT}'. ` +
          `Run: gh auth login --hostname github.com --user ${GH_TARGET_ACCOUNT}`,
        action_required: "gh_login_required",
      };
    }
  }
  // Active account is now confirmed to be GH_TARGET_ACCOUNT — proceed.
}

// -------------------------------------------------------------------------
// Step 0 — Capture pre-merge test baseline on current main HEAD
//
// Creates a temporary worktree at origin/main, runs test-runner against it,
// and stores the list of failing test IDs as the baseline. This baseline is
// passed to the triage agent in step 3 so regressions can be distinguished
// from pre-existing failures.
//
// Graceful degradation: if the worktree creation or test run fails for any
// reason, log a warning and set baselineFailures = null. The workflow DOES
// NOT halt — triage will classify all failures conservatively as regressions.
//
// Resumability: before creating the temp worktree, the agent probes for any
// stale /tmp/leafcutter-main-baseline-* directory from a prior interrupted run
// and removes it. This prevents git worktree add from failing because the
// target path already exists.
// -------------------------------------------------------------------------

phase('Step 0')

// Set the cleanup guard path so cleanupBaselineWorktree() can remove it on
// any early exit after this point. Step 0 clears it on success (step D).
// baselineTmpPath uses args.baseline_ts (replaces Date.now(), banned in E2).
baselineWorktreePath = baselineTmpPath;

const baselineResult = await agent(
  "Capture a pre-merge test baseline on the current main HEAD.\n" +
  `Use git -C "${WORKTREE_ROOT}" for all git commands to avoid CWD ambiguity.\n` +
  "\n" +
  "Step A0 — Reclaim any stale baseline worktrees from prior interrupted runs:\n" +
  "  Run: ls /tmp/leafcutter-main-baseline-* 2>/dev/null || true\n" +
  "  For each path returned (if any):\n" +
  `    Run: git -C "${WORKTREE_ROOT}" worktree remove \"<path>\" --force 2>/dev/null || true\n` +
  "    Run: rm -rf \"<path>\" 2>/dev/null || true\n" +
  "  Log each removed path as: 'Reclaimed stale baseline worktree: <path>'\n" +
  "  If no paths found: log 'No stale baseline worktrees found.'\n" +
  "\n" +
  "Step A — Create a temporary detached worktree at origin/main:\n" +
  `  Run: git -C "${WORKTREE_ROOT}" worktree add --detach "${baselineTmpPath}" origin/main\n` +
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
  "Step C — Deploy shims then run the test suite inside the temp worktree (FIN-100a-4):\n" +
  `  Run: python3 "${baselineTmpPath}/scripts/build.py" --target-dir "${baselineTmpPath}"\n` +
  "  (Deploys commit_guardian, feedback scripts, and .pre-commit-config.yaml — same build state as production.)\n" +
  "  If build.py exits non-zero: log a warning but continue (shim deploy failure is non-fatal for baseline).\n" +
  `  Then run inside "${baselineTmpPath}": pytest --tb=no -q 2>&1\n` +
  "  Collect each line that matches the pattern '<file>::<test_name> FAILED'.\n" +
  "  Build a list of failing test IDs (strings like 'test_foo.py::test_bar').\n" +
  "  Note: a zero-length list means the baseline is clean (all tests pass).\n" +
  "\n" +
  "Step D — Remove the temp worktree:\n" +
  `  Run: git -C "${WORKTREE_ROOT}" worktree remove "${baselineTmpPath}" --force\n` +
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
  { agentType: "status-checker", label: "step-0-baseline", phase: "Step 0" }
)

let baselineInfo;
{
  const { value, malformed } = safeParseJSON(baselineResult);
  if (malformed) {
    // AC-4: Malformed reply is not the same as "baseline failed" —
    // degrade gracefully (same as run_failed path) without spuriously halting.
    log("[finalize-feature] step 0 baseline parse malformed — treating as run_failed (triage will use conservative classification)");
    baselineInfo = { status: "parse_failed", baseline_sha: null, baseline_failures: null, baseline_run_at: null };
  } else {
    baselineInfo = value || { status: "parse_failed", baseline_sha: null, baseline_failures: null, baseline_run_at: null };
  }
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

phase('Step 1')

const prProbeResult = await agent(
  `Run: gh pr list --head "${BRANCH}" --json number,url --jq '.[0]'\n` +
  "Return ONLY a JSON object:\n" +
  "- If a PR is found: { \"found\": true, \"number\": <N>, \"url\": \"<url>\" }\n" +
  "- If no PR exists: { \"found\": false }",
  { agentType: "status-checker", label: "step-1-pr-probe", phase: "Step 1" }
)

let prProbe;
{
  const { value, malformed } = safeParseJSON(prProbeResult);
  if (malformed) {
    // AC-4: Malformed PR probe defaults to "not found" — safer to open a duplicate
    // PR (which will be rejected by GH) than to silently skip creating one.
    log("[finalize-feature] step 1 PR probe parse malformed — assuming no PR exists");
    prProbe = { found: false };
  } else {
    prProbe = value || { found: false };
  }
}

if (prProbe.found) {
  prNumber = prProbe.number;
  prUrl = prProbe.url;
  skippedSteps.push({ step: 1, reason: `PR already open (#${prNumber}) — skipping step 1` });
} else {
  // Dispatch pull-request agent to open the PR.
  // AC-3 EMU REST fallback: if `gh pr create` fails with the EMU error string
  // ("createPullRequest" or "Enterprise Managed User"), fall back to the REST API:
  //   gh api -X POST repos/<org>/<repo>/pulls -f title="..." -f head="..." -f base="main" -f body="..."
  // GH_REPO (from config) is used for the REST path; omit fallback if GH_REPO is absent.
  const emuFallbackNote = GH_REPO
    ? `EMU REST fallback: if gh pr create fails with "createPullRequest" or "Enterprise Managed User" error, ` +
      `use: gh api -X POST repos/${GH_REPO}/pulls -f title="<title>" -f head="${BRANCH}" -f base="main" -f body="<body>". `
    : "";
  const openPrResult = await agent(
    "Open a pull request for the current feature branch. " +
    "First try: gh pr create --base main --head \"" + BRANCH + "\" (standard path). " +
    emuFallbackNote +
    "Return ONLY a JSON object: { \"number\": <N>, \"url\": \"<url>\" }",
    { agentType: "pull-request", label: "step-1-open-pr", phase: "Step 1" }
  )

  let openPr;
  {
    const { value, malformed } = safeParseJSON(openPrResult);
    if (malformed) {
      log("[finalize-feature] step 1 PR open parse malformed — pr_number and url will be null");
      openPr = {};
    } else {
      openPr = value || {};
    }
  }

  prNumber = openPr.number || openPr.pr_number || null;
  prUrl = openPr.url || openPr.pr_url || null;
  completedSteps.push(1);
}

// -------------------------------------------------------------------------
// Step 2 — Merge origin/main into the feature worktree (no commit)
//
// Inserts the merged state into the worktree so that tests in step 3 run
// against the post-merge tree. Uses --no-commit --no-ff so no merge commit
// is written to the feature branch. On conflict, git merge --abort cleans up
// and the workflow halts with category merge_conflict.
//
// Running this BEFORE the PR merge gate (step 4) ensures the test safety
// gate (step 3) can catch regressions before the feature lands on main.
//
// Resumability: probe git merge-base --is-ancestor to detect already-merged.
// -------------------------------------------------------------------------

phase('Step 2')

const mergeMainResult = await agent(
  "Run these commands inside the feature worktree to merge origin/main before tests.\n" +
  `All git commands must use the explicit worktree root: git -C "${WORKTREE_ROOT}"\n` +
  "\n" +
  "1. Check if the branch is already up-to-date with origin/main:\n" +
  `   Run: git -C "${WORKTREE_ROOT}" merge-base --is-ancestor origin/main HEAD\n` +
  "   Exit code 0 means HEAD already contains all commits from origin/main.\n" +
  "   If exit code 0: log 'Already up-to-date with origin/main.' and return\n" +
  "   { \"status\": \"already_up_to_date\", \"merge_strategy\": \"already_up_to_date\" }\n" +
  "\n" +
  "2. If not up-to-date, fetch origin/main to ensure it is current:\n" +
  `   Run: git -C "${WORKTREE_ROOT}" fetch origin main\n` +
  "\n" +
  "3. Attempt the merge (no commit, no fast-forward):\n" +
  `   Run: git -C "${WORKTREE_ROOT}" merge origin/main --no-commit --no-ff\n` +
  "   Capture the exit code.\n" +
  "\n" +
  "4. If exit code is 0 (clean merge):\n" +
  "   Log: 'Merge clean — worktree reflects post-merge state.'\n" +
  "   Return: { \"status\": \"merged\", \"merge_strategy\": \"merged_main\" }\n" +
  "\n" +
  "5. If exit code is non-zero (conflict detected):\n" +
  `   Run: git -C "${WORKTREE_ROOT}" merge --abort\n` +
  "   Return: { \"status\": \"conflict\", \"merge_strategy\": null }",
  { agentType: "status-checker", label: "step-2-merge-main", phase: "Step 2" }
)

let mergeMainInfo;
{
  const { value, malformed } = safeParseJSON(mergeMainResult);
  if (malformed) {
    // AC-4: A malformed reply is not the same as "conflict detected".
    // Default to "already_up_to_date" (non-halting, safe) and log a warning.
    // If the merge actually had a problem, it will become apparent at the
    // test-runner phase (step 3) rather than spuriously halting here.
    log("[finalize-feature] step 2 merge-main parse malformed — treating as already_up_to_date (non-halting safe default)");
    mergeMainInfo = { status: "already_up_to_date", merge_strategy: "already_up_to_date" };
  } else {
    mergeMainInfo = value || { status: "already_up_to_date", merge_strategy: "already_up_to_date" };
  }
}

const mergeStatus = (mergeMainInfo.status || "already_up_to_date").toLowerCase();

if (mergeStatus === "conflict") {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: 2,
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
    step: 2,
    reason: "Already up-to-date with origin/main",
  });
} else {
  // merged_main path
  completedSteps.push(2);
}

const mergeStrategy = mergeMainInfo.merge_strategy || "already_up_to_date";

// -------------------------------------------------------------------------
// Step 3 — Run post-merge tests + triage (always runs)
//
// The baseline captured in step 0 is forwarded here so the triage agent
// can compute:
//   regressions = post_merge_failures − baseline_failures
// If baseline_failures is null, all failures are treated as regressions
// (conservative classification).
//
// If tests pass: skip triage sub-steps and continue to step 4 (PR merge).
// If tests fail: triage classifies failures; HALT here if any are regressions.
// Only when blocks_finalization === false does the workflow proceed to step 4.
// -------------------------------------------------------------------------

phase('Step 3')

// FIN-100a-4: deploy shims before running the suite, same as Step 0 baseline.
// Without this, ~13 deploy-dependent tests fail RED in Step 3 while passing
// in Step 0, causing the triage set-difference to misclassify them as regressions.
testResult = await agent(
  `First run: python3 "${WORKTREE_ROOT}/scripts/build.py" --target-dir "${WORKTREE_ROOT}" ` +
  "to deploy shims (same build.py step as the Step 0 baseline — ensures identical build state " +
  "for commit_guardian, feedback scripts, and .pre-commit-config.yaml). " +
  "If build.py exits non-zero: log a warning but continue. " +
  "Then run the full test suite on the post-merge worktree. " +
  "Return a JSON object: { \"passed\": true|false, \"output\": \"<verbatim test output>\", " +
  "\"failing_tests\": [\"<file>::<test_name>\", ...] }\n" +
  `Baseline context: baseline_sha=${JSON.stringify(baselineSha)}, ` +
  `baseline_failures=${JSON.stringify(baselineFailures)}, ` +
  `baseline_run_at=${JSON.stringify(baselineRunAt)}`,
  { agentType: "test-runner", label: "step-3-test-run", phase: "Step 3" }
)

let testPassed;
let postMergeFailures;
{
  const { value, malformed } = safeParseJSON(testResult);
  if (malformed) {
    // AC-4: A malformed test reply is ambiguous — we cannot determine pass/fail.
    // Default to testPassed=false (conservative) but log clearly that this is a
    // parse failure, not an agent-reported failure. The triage step will then
    // attempt to classify failures, and if the triage reply is also malformed,
    // that triage step's own safe default applies.
    log("[finalize-feature] step 3 test-runner parse malformed — treating as failed (conservative; triage will classify)");
    testPassed = false;
    postMergeFailures = [];
    testResult = { passed: false, output: "(parse malformed)", failing_tests: [] };
  } else {
    const parsed = value || {};
    testPassed = parsed.passed === true;
    testResult = parsed;
    postMergeFailures = Array.isArray(parsed.failing_tests) ? parsed.failing_tests : [];
  }
}

if (testPassed) {
  // Zero failures: skip triage sub-steps entirely, proceed to step 4 (PR merge).
  completedSteps.push(3);
  // triageReport remains null — forwarded to step 6 as-is.
} else {
  // -----------------------------------------------------------------------
  // Step 3 (triage sub-step) — Dispatch test-failure-triage when failures exist
  //
  // Passes post_merge_failures, baseline_failures, baseline_sha,
  // feature_branch, and changed_files (derived here via git diff) so the
  // triage agent can classify each failure as regression or pre-existing.
  // -----------------------------------------------------------------------

  // Derive changed_files: files touched by the feature branch relative to
  // origin/main. Captured at this point (after the --no-commit merge) so
  // the diff reflects the full feature delta including the merged state.
  const changedFilesResult = await agent(
    `Run: git -C "${WORKTREE_ROOT}" diff --name-only origin/main HEAD\n` +
    "Return ONLY a JSON object: { \"changed_files\": [\"<file1>\", \"<file2>\", ...] }\n" +
    "If the command fails or returns no output, return: { \"changed_files\": [] }",
    { agentType: "status-checker", label: "step-3-changed-files", phase: "Step 3" }
  )

  let changedFiles = [];
  {
    const { value, malformed } = safeParseJSON(changedFilesResult);
    if (malformed) {
      log("[finalize-feature] step 3 changed_files parse malformed — triage will use empty changed_files list");
      changedFiles = [];
    } else {
      const parsedCf = value || {};
      changedFiles = Array.isArray(parsedCf.changed_files) ? parsedCf.changed_files : [];
    }
  }

  const triageRaw = await agent(
    "Classify each failing test into one of four categories: " +
    "'regression' (caused by this branch), 'stale_test' (covers a deprecated/superseded AC), " +
    "'pre_existing' (already failing on main before merge), or 'flaky' (intermittently failing). " +
    "Return a JSON object matching this schema exactly: " +
    "{ \"triage_report\": [ { \"test_id\": \"<fully-qualified test name>\", " +
    "\"test_file\": \"<relative path>\", \"covers_tag\": \"<tag or null>\", " +
    "\"category\": \"regression|stale_test|pre_existing|flaky\", " +
    "\"ac_status\": \"<active|deprecated|superseded_by|not_found|null>\", " +
    "\"rationale\": \"<reason>\", \"action\": \"fix_on_branch|update_test|create_tracking_ticket\", " +
    "\"modified_by_branch\": true|false } ], " +
    "\"blocks_finalization\": true|false }\n" +
    `Context: post_merge_failures=${JSON.stringify(postMergeFailures)}, ` +
    `baseline_failures=${JSON.stringify(baselineFailures)}, ` +
    `baseline_sha=${JSON.stringify(baselineSha)}, ` +
    `feature_branch=${JSON.stringify(BRANCH)}, ` +
    `changed_files=${JSON.stringify(changedFiles)}`,
    { agentType: "test-failure-triage", label: "step-3-triage", phase: "Step 3" }
  )

  {
    const { value, malformed } = safeParseJSON(triageRaw);
    if (malformed) {
      // AC-4: A malformed triage reply is genuinely ambiguous — we cannot determine
      // whether failures are regressions or pre-existing. Use conservative
      // blocks_finalization=true, but log clearly that this is a parse failure
      // (not an agent-reported regression), so the operator can distinguish
      // "tests have regressions" from "triage reply was garbled".
      log("[finalize-feature] step 3 triage parse malformed — treating as blocks_finalization=true (conservative; see note in summary)");
      triageReport = {
        blocks_finalization: true,
        regressions: postMergeFailures,
        pre_existing: [],
        summary: "Triage reply was malformed (could not parse JSON) — treating all failures as regressions conservatively. If you believe this is a parse error rather than a real regression, re-run /finalize-feature.",
      };
    } else {
      triageReport = value || {
        blocks_finalization: true,
        regressions: postMergeFailures,
        pre_existing: [],
        summary: "Triage report empty — treating all failures as regressions.",
      };
    }
  }

  // Log the triage report to the user for visibility.
  log("[finalize-feature] step 3 triage report: " + JSON.stringify(triageReport, null, 2));

  // -----------------------------------------------------------------------
  // Step 3 (halt gate) — Halt-or-continue based on triage_report.blocks_finalization
  //
  // If blocks_finalization is true: HARD EARLY RETURN. Step 4 (PR merge) is
  // structurally unreachable from this point — no escape hatch.
  // If false: pass triage_report forward and continue to step 4.
  // -----------------------------------------------------------------------
  if (triageReport.blocks_finalization) {
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: 3,
      reason: "test_regression",
      triage_report: triageReport,
      message:
        "Fix regressions before re-running /finalize-feature. " +
        "The PR has NOT been merged to main.",
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
  // Store triage_report in workflow state and continue to step 4.
  completedSteps.push(3);
}

// -------------------------------------------------------------------------
// Step 3.5 — Pre-merge AC closure (runs on the feature branch, before Step 4)
//
// This step MUST run before the PR merge (step 4) so that ticket status and
// source AC work_status are committed on the feature branch. The PR then
// carries that closure commit to origin/main atomically. Writing closure on
// local main is not possible because main is PR-only (branch protection).
// -------------------------------------------------------------------------

phase('Step 3.5')

// Probe: check whether a closure commit already exists on the branch.
const closureProbeResult = await agent(
  `Run: git -C "${WORKTREE_ROOT}" log --oneline --grep 'chore(tickets): close tickets and source ACs' -1\n` +
  "If the output is non-empty (a closure commit already exists on this branch):\n" +
  "  Return: { \"already_committed\": true }\n" +
  "Otherwise:\n" +
  "  Return: { \"already_committed\": false }",
  { agentType: "status-checker", label: "step-3.5-closure-probe", phase: "Step 3.5" }
)

let closureAlreadyCommitted = false;
{
  const { value, malformed } = safeParseJSON(closureProbeResult);
  if (malformed) {
    log("[finalize-feature] step 3.5 closure probe parse malformed — assuming not already committed (will re-attempt closure)");
    closureAlreadyCommitted = false;
  } else {
    closureAlreadyCommitted = (value || {}).already_committed === true;
  }
}

if (closureAlreadyCommitted) {
  skippedSteps.push({
    step: "3.5",
    reason: "Pre-merge closure commit already present — skipping step 3.5",
  });
} else {
  // Also check: if the PR is already merged, the pre-merge closure step is moot.
  let prAlreadyMergedAtClosure = false;
  if (prNumber !== null) {
    const prClosureStateResult = await agent(
      `Run: gh pr view ${prNumber} --json state --jq '.state'\n` +
      "Return ONLY a JSON object: { \"state\": \"OPEN\"|\"MERGED\"|\"CLOSED\" }",
      { agentType: "status-checker", label: "step-3.5-pr-state", phase: "Step 3.5" }
    )
    {
      const { value, malformed } = safeParseJSON(prClosureStateResult);
      if (malformed) {
        log("[finalize-feature] step 3.5 PR state parse malformed — assuming PR is OPEN");
        prAlreadyMergedAtClosure = false;
      } else {
        prAlreadyMergedAtClosure = ((value || {}).state || "").toUpperCase() === "MERGED";
      }
    }
  }

  if (prAlreadyMergedAtClosure) {
    skippedSteps.push({
      step: "3.5",
      reason: "PR already merged — pre-merge closure step skipped (AC-5 idempotency)",
    });
  } else {
    // -----------------------------------------------------------------------
    // Sub-step A: Reset the Step 2 test-merge.
    // -----------------------------------------------------------------------
    const resetMergeResult = await agent(
      "Reset any staged test-merge left by step 2 before editing ticket files.\n" +
      `All git commands use the explicit worktree root: git -C "${WORKTREE_ROOT}"\n` +
      "\n" +
      "1. Check if a merge is in progress:\n" +
      `   Run: git -C "${WORKTREE_ROOT}" rev-parse --verify MERGE_HEAD 2>/dev/null\n` +
      "   Capture the exit code.\n" +
      "\n" +
      "2. If exit code is 0 (MERGE_HEAD exists — merge in progress):\n" +
      `   Run: git -C "${WORKTREE_ROOT}" merge --abort\n` +
      "   Log: 'Step 2 test-merge aborted — clean feature-branch state restored.'\n" +
      "   Return: { \"status\": \"aborted\" }\n" +
      "\n" +
      "3. If exit code is non-zero (no merge in progress):\n" +
      `   Run: git -C "${WORKTREE_ROOT}" reset --hard HEAD\n` +
      "   Log: 'No merge in progress — reset to feature-branch HEAD.'\n" +
      "   Return: { \"status\": \"reset\" }",
      { agentType: "status-checker", label: "step-3.5-reset-merge", phase: "Step 3.5" }
    )

    // Sub-step B + C + D + E: find in-scope tickets, close them, close ACs, commit.
    const closureResult = await agent(
      "Close in-scope tickets and their source ACs on the feature branch.\n" +
      "\n" +
      "=== CONTEXT ===\n" +
      `Feature branch: ${BRANCH}\n` +
      `Worktree root: ${WORKTREE_ROOT}\n` +
      "\n" +
      "=== SUB-STEP B: FIND IN-SCOPE TICKETS ===\n" +
      "Find all ticket .md files that this branch introduced or modified:\n" +
      `  Run: git -C ${WORKTREE_ROOT} diff --name-only origin/main HEAD -- 'tickets/**/*.md'\n` +
      "  Also include any ticket file in the worktree that has status != done:\n" +
      `  Run: git -C ${WORKTREE_ROOT} log --oneline origin/main..${BRANCH} --name-only --diff-filter=A -- 'tickets/**/*.md'\n` +
      "  Combine both lists; deduplicate. Exclude Master_Plan.md.\n" +
      "  For each file, read its frontmatter `status:` field.\n" +
      "  Collect only files where status != 'done' (skip already-done tickets — AC-5 idempotency).\n" +
      "  Call this list OPEN_TICKETS.\n" +
      "  If OPEN_TICKETS is empty: log 'No open tickets to close.' and skip to REPORTING.\n" +
      "\n" +
      "=== SUB-STEP C: SET status: done ===\n" +
      "For each ticket in OPEN_TICKETS:\n" +
      "  Read the file content.\n" +
      "  Replace the `status: <value>` line in the YAML frontmatter with `status: done`.\n" +
      "  Write the updated content back to the file.\n" +
      "  Log: 'Set status: done on <ticket_path>'\n" +
      "\n" +
      "=== SUB-STEP D: CLOSE SOURCE ACs ===\n" +
      "For each ticket in OPEN_TICKETS:\n" +
      "  Read the ticket frontmatter and look for a `source_ac:` field.\n" +
      "  If `source_ac` is absent or empty: log 'No source_ac on <ticket_path> — skipping AC closure.' and skip (AC-3 no-op).\n" +
      "  If `source_ac` is present:\n" +
      `    Run: python3 ${WORKTREE_ROOT}/scripts/ac_store/mark_ac_done.py --ticket <ticket_path> --ac-root ${WORKTREE_ROOT}/docs/acceptance-criteria/\n` +
      "    Capture the exit code.\n" +
      "    If exit code is 0: increment acs_closed counter.\n" +
      "    If exit code is non-zero: log 'WARNING: mark_ac_done.py exited <code> for <ticket_path> — skipping AC closure (non-fatal).' and increment acs_skipped counter. DO NOT fail finalize. (AC-4 non-fatal)\n" +
      "\n" +
      "=== SUB-STEP E: COMMIT ON FEATURE BRANCH ===\n" +
      "If OPEN_TICKETS was non-empty (any edits were made):\n" +
      `  Run: git -C ${WORKTREE_ROOT} add tickets/\n` +
      `  Run: git -C ${WORKTREE_ROOT} add docs/acceptance-criteria/ 2>/dev/null || true\n` +
      `  Run: git -C ${WORKTREE_ROOT} diff --cached --name-only\n` +
      "  If staged files exist:\n" +
      `    Run: git -C ${WORKTREE_ROOT} commit -m 'chore(tickets): close tickets and source ACs'\n` +
      "    Log: 'Closure commit created on feature branch.'\n" +
      "  Else:\n" +
      "    Log: 'Nothing staged after edits — all tickets were already done.'\n" +
      "\n" +
      "=== REPORTING ===\n" +
      "Return a JSON object:\n" +
      "{\n" +
      '  "tickets_closed": ["<path1>", ...],\n' +
      '  "acs_closed": <integer>,\n' +
      '  "acs_skipped": <integer>,\n' +
      '  "commit_made": true|false\n' +
      "}",
      { agentType: "status-checker", label: "step-3.5-closure", phase: "Step 3.5" }
    )

    let closureInfo;
    {
      const { value, malformed } = safeParseJSON(closureResult);
      if (malformed) {
        log("[finalize-feature] step 3.5 closure parse malformed — assuming zero tickets/ACs closed");
        closureInfo = { tickets_closed: [], acs_closed: 0, acs_skipped: 0, commit_made: false };
      } else {
        closureInfo = value || { tickets_closed: [], acs_closed: 0, acs_skipped: 0, commit_made: false };
      }
    }

    // Accumulate counts into workflow-level variables.
    if (Array.isArray(closureInfo.tickets_closed)) {
      ticketsClosedPreMerge = closureInfo.tickets_closed.length;
      // Merge into the broader ticketsClosed list for the final summary.
      ticketsClosed.push(...closureInfo.tickets_closed);
    }
    acsClosed = typeof closureInfo.acs_closed === "number" ? closureInfo.acs_closed : 0;
    acsSkipped = typeof closureInfo.acs_skipped === "number" ? closureInfo.acs_skipped : 0;

    completedSteps.push("3.5");

    log(
      `[finalize-feature] step 3.5 closure: tickets_closed=${ticketsClosedPreMerge} ` +
        `acs_closed=${acsClosed} acs_skipped=${acsSkipped} ` +
        `commit_made=${closureInfo.commit_made}`
    );
  }
}

// -------------------------------------------------------------------------
// Pre-Step-4 Sync Check — ensure local branch HEAD is on origin before merge
//
// AC-1 (TICKET-20260708-Finalize_Push_Before_Merge):
// gh pr merge merges the ORIGIN PR head, not the local HEAD. Any commit made
// on the branch after the last ticket's pull-request phase — e.g. a code-review
// fix, an origin/main-into-branch merge, or a manual edit at finalize time — is
// local-only. If finalize runs without this check, gh pr merge merges the older
// origin head and those local commits are silently excluded from main.
//
// This check compares local HEAD to origin/<branch>. When local is ahead, it
// pushes the branch to origin so the PR head is always current. When the push
// fails or the branch has diverged, it halts with an actionable message.
// -------------------------------------------------------------------------

const syncCheckResult = await agent(
  "Check whether the local feature branch HEAD is ahead of origin and push if needed.\n" +
  `All git commands use the explicit worktree root: git -C "${WORKTREE_ROOT}"\n` +
  "\n" +
  "Step 1 — Fetch origin to ensure tracking refs are current:\n" +
  `  Run: git -C "${WORKTREE_ROOT}" fetch origin "${BRANCH}" 2>/dev/null || true\n` +
  "\n" +
  "Step 2 — Compare local HEAD to origin branch head:\n" +
  `  Run: git -C "${WORKTREE_ROOT}" rev-parse HEAD\n` +
  `  Run: git -C "${WORKTREE_ROOT}" rev-parse "origin/${BRANCH}" 2>/dev/null || echo "no-remote-ref"\n` +
  "  If origin ref does not exist (new branch, never pushed): treat as local-ahead.\n" +
  "  If both SHAs are equal: branch is up-to-date.\n" +
  "\n" +
  "Step 3 — When SHAs differ, determine direction:\n" +
  `  Run: git -C "${WORKTREE_ROOT}" rev-list --count "origin/${BRANCH}..HEAD" 2>/dev/null || echo "0"\n` +
  "  ahead_count = integer from the output (0 if origin ref missing, in which case treat as ahead).\n" +
  "  If ahead_count == 0 and SHAs differ: branch is diverged (origin has commits local lacks).\n" +
  "\n" +
  "Step 4 — Push when local is ahead:\n" +
  `  Run: git -C "${WORKTREE_ROOT}" push origin "${BRANCH}"\n` +
  "  Capture exit code.\n" +
  "  If exit code 0:\n" +
  `    Run: git -C "${WORKTREE_ROOT}" rev-parse "origin/${BRANCH}"\n` +
  "    Return: { \"status\": \"pushed\", \"local_sha\": \"<sha>\", \"origin_sha\": \"<sha-after-push>\" }\n" +
  "  If non-zero:\n" +
  "    Return: { \"status\": \"push_failed\", \"local_sha\": \"<sha>\", \"origin_sha\": \"<sha>\", \"error\": \"<captured stderr>\" }\n" +
  "\n" +
  "Step 5 — Return status:\n" +
  "  up_to_date: { \"status\": \"up_to_date\", \"local_sha\": \"<sha>\", \"origin_sha\": \"<sha>\" }\n" +
  "  diverged:   { \"status\": \"diverged\",   \"local_sha\": \"<sha>\", \"origin_sha\": \"<sha>\" }",
  { agentType: "status-checker", label: "pre-step-4-sync-check", phase: "Step 4" }
)

let syncCheckInfo;
{
  const { value, malformed } = safeParseJSON(syncCheckResult);
  if (malformed) {
    log("[finalize-feature] pre-step-4 sync-check parse malformed — proceeding (cannot determine push state; fail-open for robustness)");
    syncCheckInfo = { status: "unknown" };
  } else {
    syncCheckInfo = value || { status: "unknown" };
  }
}

const syncStatus = (syncCheckInfo.status || "unknown").toLowerCase();

if (syncStatus === "push_failed") {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: "pre-4",
    reason: "push_failed",
    message:
      "Local branch HEAD is ahead of origin but push failed. " +
      `Push the branch manually (git push origin ${BRANCH}) and re-run /finalize-feature. ` +
      "The PR has NOT been merged — no work is lost.",
    branch: BRANCH,
    pr_number: prNumber,
    pr_url: prUrl,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
    action_required: "push_local_commits",
  };
}

if (syncStatus === "diverged") {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: "pre-4",
    reason: "branch_diverged",
    message:
      `Local branch and origin/${BRANCH} have diverged. ` +
      "Resolve the divergence (rebase or force-push with caution) before merging, " +
      "then re-run /finalize-feature.",
    branch: BRANCH,
    pr_number: prNumber,
    pr_url: prUrl,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
    action_required: "resolve_divergence",
  };
}

if (syncStatus === "pushed") {
  log("[finalize-feature] pre-step-4 sync-check: local branch was ahead of origin — pushed successfully. PR head is now current.");
  completedSteps.push("pre-4-push");
} else if (syncStatus === "up_to_date") {
  log("[finalize-feature] pre-step-4 sync-check: local branch is up-to-date with origin. No push needed.");
} else {
  // unknown or other — log and proceed (fail-open for robustness)
  log(`[finalize-feature] pre-step-4 sync-check: status=${syncStatus} — proceeding (conservative pass).`);
}

// -------------------------------------------------------------------------
// Step 4 — Merge PR to main (destructive — confirmation gate required)
//
// This step runs AFTER the worktree merge (step 2) and test + triage (step 3).
// The gate only shows the confirmation prompt when blocks_finalization === false
// (ensured by the halt in step 3). A defensive guard is included to catch any
// edge case where blocks_finalization is truthy at this point.
// -------------------------------------------------------------------------

phase('Step 4')

// Defensive guard: blocks_finalization should never be true here (step 3 halts),
// but guard against edge cases.
if (triageReport !== null && triageReport.blocks_finalization) {
  await cleanupBaselineWorktree();
  return {
    status: "halted",
    halted_at_step: 4,
    reason: "test_regression",
    triage_report: triageReport,
    message:
      "Defensive guard triggered: blocks_finalization is true at step 4. " +
      "The PR has NOT been merged. Fix regressions and re-run /finalize-feature.",
    branch: BRANCH,
    pr_number: prNumber,
    pr_url: prUrl,
    completed_steps: completedSteps,
    skipped_steps: skippedSteps,
  };
}

// First probe current PR state to support crash-resume.
const prStateResult = await agent(
  `Run: gh pr view ${prNumber} --json state --jq '.state'\n` +
  "Return ONLY a JSON object: { \"state\": \"OPEN\"|\"MERGED\"|\"CLOSED\" }",
  { agentType: "status-checker", label: "step-4-pr-state", phase: "Step 4" }
)

let prState;
{
  const { value, malformed } = safeParseJSON(prStateResult);
  if (malformed) {
    log("[finalize-feature] step 4 PR state parse malformed — assuming PR is OPEN");
    prState = { state: "OPEN" };
  } else {
    prState = value || { state: "OPEN" };
  }
}

if ((prState.state || "").toUpperCase() === "MERGED") {
  // PR already merged — skip the merge gate and proceed.
  skippedSteps.push({ step: 4, reason: "PR already merged — skipping step 4" });
} else {
  // E2 has no prompt() global — implement the merge confirmation gate as an
  // explicit agent turn. The agent presents the question to the user, waits
  // for a response, and returns status: 'ok' (yes) or status: 'blocked' (no).
  // This matches the E2 user-gate convention from the workflow-authoring-contract.
  const mergeConfirmResult = await agent(
    `WARNING: This will merge PR #${prNumber} (\`${BRANCH}\` → main). This is a destructive operation.\n\n` +
    `Ask the user: "Merge PR #${prNumber} (\`${BRANCH}\` → main)? (yes / no)"\n\n` +
    `Return status:"ok" if the user says yes/confirm/y.\n` +
    `Return status:"blocked" with message "User declined merge." if the user says no/cancel/n.`,
    { agentType: "status-checker", label: "step-4-merge-gate", phase: "Step 4", schema: GATE_SCHEMA }
  )

  if (!mergeConfirmResult || mergeConfirmResult.status !== "ok") {
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: 4,
      reason: "user_declined_merge",
      message: "Finalization halted at merge step. No changes made to main.",
      branch: BRANCH,
      pr_number: prNumber,
      pr_url: prUrl,
      completed_steps: completedSteps,
      skipped_steps: skippedSteps,
    };
  }

  // Dispatch pull-request agent for the merge operation.
  // AC-3 EMU REST fallback: if `gh pr merge` fails with the EMU error string,
  // fall back to the REST API.
  const emuMergeFallbackNote = GH_REPO
    ? `EMU REST fallback: if gh pr merge fails with "createPullRequest" or "Enterprise Managed User" error, ` +
      `use: gh api -X PUT repos/${GH_REPO}/pulls/${prNumber}/merge -f merge_method="merge". `
    : "";
  mergeResult = await agent(
    `Merge PR #${prNumber} to main using: gh pr merge ${prNumber} --merge --auto\n` +
    emuMergeFallbackNote +
    "Wait for the merge to complete, then return a JSON object: " +
    "{ \"merged\": true, \"sha\": \"<merge-commit-sha>\" }",
    { agentType: "pull-request", label: "step-4-merge-pr", phase: "Step 4" }
  )

  completedSteps.push(4);
}

// -------------------------------------------------------------------------
// Step 5 — Sync local main (resumable)
//
// AC-2 note: this step does NOT make commits on main. It only runs
// `git checkout main && git pull` (read operations).
// -------------------------------------------------------------------------

phase('Step 5')

const syncResult = await agent(
  "Run these commands in sequence using the explicit repo root to avoid CWD ambiguity:\n" +
  `1. git -C "${WORKTREE_ROOT}" checkout main\n` +
  `2. git -C "${WORKTREE_ROOT}" pull\n` +
  `3. git -C "${WORKTREE_ROOT}" log -1 --oneline\n` +
  "Report the final HEAD SHA and commit message. " +
  "Return a JSON object: { \"head_sha\": \"<sha>\", \"head_message\": \"<message>\" }",
  { agentType: "status-checker", label: "step-5-sync-main", phase: "Step 5" }
)

completedSteps.push(5);

// -------------------------------------------------------------------------
// Step 6 — Report untracked pre-existing/flaky failures, then detect scope
// -------------------------------------------------------------------------

phase('Step 6')

// Sub-step 6a: report pre-existing / flaky failures that require manual tracking.
if (triageReport !== null) {
  const triageEntries = Array.isArray(triageReport.triage_report)
    ? triageReport.triage_report
    : [];

  const preExistingEntries = triageEntries.filter(
    (entry) =>
      entry.category === "pre_existing" || entry.category === "flaky"
  );

  if (preExistingEntries.length === 0) {
    log(
      "[finalize-feature] step 6a: no pre_existing or flaky entries in triage report — no tracking tickets needed"
    );
  } else {
    // Collect untracked failures so the final summary is accurate.
    for (const entry of preExistingEntries) {
      const testId = entry.test_id || "<unknown test>";
      const category = entry.category || "pre_existing";
      untrackedFailures.push({ testId, category });
    }

    // Emit one structured report listing all untracked failures.
    const failureLines = untrackedFailures
      .map(
        ({ testId, category }) =>
          `  - [${category}] ${testId} (failing on main at SHA ${baselineSha || "unknown"})`
      )
      .join("\n");

    log(
      `[finalize-feature] step 6a: ${untrackedFailures.length} pre-existing/flaky failure(s) detected.\n` +
      `Auto-ticketing is disabled (create-ticket is a workflow, not an agent).\n` +
      `No tracking tickets were created. To track these failures, run /create-ticket for each:\n` +
      failureLines
    );
  }
}

// Sub-step 6b: scope-detection only (no git writes on main)
const closeResult = await agent(
  "Detect branch scope and report what tickets were touched (informational only — no writes):\n" +
  `1. Run: git -C "${WORKTREE_ROOT}" log --oneline main..${BRANCH} 2>/dev/null || git -C "${WORKTREE_ROOT}" log --oneline -20\n` +
  "2. Search tickets/ tree for ticket files referencing this branch.\n" +
  "3. Determine if any ticket path is inside an EPIC-*/ folder — if so, this is epic-scoped.\n" +
  "4. For each in-scope ticket: read its frontmatter `status:` field.\n" +
  "   NOTE: Do NOT flip status or move files. Ticket closure already happened in\n" +
  "   step 3.5 (pre-merge closure commit on the feature branch). status: frontmatter\n" +
  "   is the sole source of truth (BO-400a-3/4/5, BO-400c-1/2).\n" +
  "5. Return a JSON object: " +
  '{ "scope": "single-ticket"|"epic"|"unknown", ' +
  '"tickets_in_scope": ["<path>", ...], ' +
  '"tickets_done": ["<path — status: done>", ...], ' +
  '"tickets_not_done": ["<path — status: other>", ...], ' +
  '"skipped": false|true }',
  { agentType: "status-checker", label: "step-6-scope-detect", phase: "Step 6" }
)

let closeInfo;
{
  const { value, malformed } = safeParseJSON(closeResult);
  if (malformed) {
    log("[finalize-feature] step 6 scope-detect parse malformed — no tickets reported in summary");
    closeInfo = { tickets_in_scope: [], tickets_done: [], tickets_not_done: [], skipped: false };
  } else {
    closeInfo = value || { tickets_in_scope: [], tickets_done: [], tickets_not_done: [], skipped: false };
  }
}

// Step 6b is informational only — no ticket files were moved or written.
if (closeInfo.tickets_done && Array.isArray(closeInfo.tickets_done)) {
  ticketsClosed.push(...closeInfo.tickets_done);
}

if (closeInfo.skipped) {
  skippedSteps.push({ step: 6, reason: "Scope detection skipped — no in-scope tickets found" });
} else {
  completedSteps.push(6);
}

// -------------------------------------------------------------------------
// Step 7 — Remove worktree (resumable; confirmation gate delegated to agent)
// -------------------------------------------------------------------------

phase('Step 7')

const worktreeProbeResult = await agent(
  `Run: git -C "${WORKTREE_ROOT}" worktree list --porcelain\n` +
  `Check if a worktree for WORKTREE_ROOT="${WORKTREE_ROOT}" is listed.\n` +
  "Return ONLY a JSON object: { \"exists\": true|false }",
  { agentType: "status-checker", label: "step-7-worktree-probe", phase: "Step 7" }
)

let worktreeProbe;
{
  const { value, malformed } = safeParseJSON(worktreeProbeResult);
  if (malformed) {
    // AC-4: Malformed probe — conservative default is exists=true (safer to
    // attempt removal than to skip and leave the worktree dangling).
    log("[finalize-feature] step 7 worktree probe parse malformed — assuming exists=true (conservative)");
    worktreeProbe = { exists: true };
  } else {
    worktreeProbe = value || { exists: true };
  }
}

if (!worktreeProbe.exists) {
  worktreeRemoved = false;
  skippedSteps.push({ step: 7, reason: "Worktree already absent — skipping step 7" });
} else {
  // Dispatch worktree-agent (it owns its own confirmation gate).
  const worktreeResult = await agent(
    `Remove the worktree at ${WORKTREE_ROOT}. ` +
    "If conflict_pids are reported, surface them verbatim and stop. " +
    "Return a JSON object: { \"removed\": true|false, \"conflict_pids\": [] }",
    { agentType: "worktree-agent", label: "step-7-remove-worktree", phase: "Step 7" }
  )

  let wResult;
  {
    const { value, malformed } = safeParseJSON(worktreeResult);
    if (malformed) {
      log("[finalize-feature] step 7 worktree-agent parse malformed — assuming removed=false, conflict_pids=[]");
      wResult = { removed: false, conflict_pids: [] };
    } else {
      wResult = value || { removed: false, conflict_pids: [] };
    }
  }

  if (wResult.conflict_pids && wResult.conflict_pids.length > 0) {
    // Surface conflict PIDs verbatim and stop — user must resolve manually.
    await cleanupBaselineWorktree();
    return {
      status: "halted",
      halted_at_step: 7,
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
  completedSteps.push(7);
}

// -------------------------------------------------------------------------
// Final — Return success summary
//
// AC-1: ensure the baseline temp worktree is cleaned up on the success path.
// baselineWorktreePath is already null when step 0 completed successfully
// (the agent ran step D to remove it), so this is a no-op in the happy path.
// It fires only when step 0 degraded but the workflow continued to completion.
// -------------------------------------------------------------------------
await cleanupBaselineWorktree();

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
  // Triage report from step 3; null means tests passed (no triage needed).
  triage_report: triageReport,
  tickets_closed: ticketsClosed,
  // Pre-merge closure counts from step 3.5.
  tickets_closed_pre_merge: ticketsClosedPreMerge,
  acs_closed: acsClosed,
  acs_skipped: acsSkipped,
  // Untracked failures from step 6a: pre_existing/flaky triage entries for which
  // no tracking ticket was created (auto-ticketing is disabled — create-ticket is a
  // workflow, not an agent). Operators should run /create-ticket manually for each.
  untracked_failures: untrackedFailures,
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
    (ticketsClosedPreMerge > 0
      ? `Pre-merge closure: ${ticketsClosedPreMerge} ticket(s) closed, ${acsClosed} AC(s) closed, ${acsSkipped} AC(s) skipped. `
      : "No pre-merge ticket/AC closure. ") +
    (ticketsClosed.length > 0
      ? `Tickets closed total: ${ticketsClosed.length}. `
      : "") +
    (untrackedFailures.length > 0
      ? `${untrackedFailures.length} pre-existing/flaky failure(s) not auto-ticketed (auto-ticketing disabled) — run /create-ticket manually to track them. `
      : ""),
};
