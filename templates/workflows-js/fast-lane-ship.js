/**
 * fast-lane-ship.js — Claude Code Workflow script (full-arc fast lane)
 *
 * One command, one AC id, a PR back. Point the fast lane at ANY acceptance
 * criterion and it does the whole arc with no other input (BO-2400f):
 *
 *   1. Worktree      — setup_ticket_worktree.py create-fastlane-worktree <slug>
 *                      opens a fresh isolated worktree off the latest origin/main
 *                      (fast-lane/<slug> branch), bootstrapped (BO-2400f-3).
 *   2. Resolve       — fast_lane.py select_connected --ac <id> resolves the
 *                      connected build set (subtree ∪ unmet-deps closure, in
 *                      dependency order, readiness-agnostic — BO-2400f-1/f-2).
 *                      An empty set is a clean no-op (nothing to build).
 *   3. Lean loop     — the two-agent test-writer → python-coder loop, INLINED
 *                      and scoped to the resolved id list, gated by
 *                      verify_red_baseline and verify_green_and_coverage
 *                      (the same deterministic gates as fast-lane-build.js).
 *   4. Commit + PR   — a commit agent marks the built ACs done and commits on
 *                      the worktree branch; a pull-request agent opens the PR
 *                      against main (gh pr create + EMU REST fallback) — the
 *                      operator runs neither by hand (BO-2400f-4).
 *
 * The inner lean loop is inlined here (not a nested workflow) because E2 is
 * leaf-invariant: a workflow cannot call workflow(). Every side-effect (git,
 * gh, python gates) is performed by an agent() dispatch. No per-ticket
 * supervisor chain, no LLM planner — the phase order is fixed and code-defined
 * (BO-2400a-5).
 *
 * Gate script:   {{config.output_root}}/scripts/build_orchestration/fast_lane.py
 *                (resolved inside the freshly-created worktree, once bootstrapped)
 * Worktree tool: {{config.output_root}}/scripts/setup_ticket_worktree.py
 *                (run from the consumer repo root, BEFORE any worktree exists)
 * Done marker:   fast_lane.py's own `mark_done` subcommand (coverage-gated) —
 *                not a direct call to scripts/ac_store/mark_ac_done.py
 *
 * E2 canonical form: top-level body, agent(prompt, opts), args global.
 */

export const meta = {
  name: "fast-lane-ship",
  description: "Full-arc fast lane: point at one AC id and get a PR back. Opens a fresh worktree off origin/main, resolves the AC's connected build set (subtree + unmet deps, dependency-ordered, readiness-agnostic), runs the inlined lean two-agent loop (test-writer then coder) gated by verify_red_baseline and verify_green_and_coverage, then auto-commits and opens the PR. Empty set is a clean no-op. No per-ticket supervisor chain, no planner (BO-2400f).",
  phases: [
    { title: "Worktree", detail: "create-fastlane-worktree off origin/main" },
    { title: "Resolve", detail: "select_connected — the connected build set" },
    { title: "Test Writer", detail: "red stubs for the resolved ids + verify_red_baseline" },
    { title: "Coder", detail: "make green + verify_green_and_coverage" },
    { title: "Commit", detail: "mark ACs done + commit on the worktree branch" },
    { title: "Pull Request", detail: "open the PR against main (gh + EMU fallback)" },
  ],
};

// ---------------------------------------------------------------------------
// JSON Schemas
// ---------------------------------------------------------------------------

const WORKTREE_SCHEMA = {
  type: "object",
  required: ["worktree_path"],
  properties: {
    worktree_path: { type: "string" },
    branch: { type: "string" },
    ac_store_path: { type: "string" },
    created: { type: "boolean" },
  },
};

const RESOLVER_SCHEMA = {
  type: "object",
  required: ["ac_ids"],
  properties: {
    ac_ids: { type: "array", items: { type: "string" } },
    message: { type: "string" },
  },
};

const TEST_WRITER_SCHEMA = {
  type: "object",
  required: ["status"],
  properties: {
    status: { type: "string", enum: ["ok", "blocker", "failed"] },
    tests_written: { type: "array", items: { type: "string" } },
    // AMENDED 2026-08-17 (BO-2400a-3-v): the red-baseline gate no longer
    // returns all_red/offender — it returns gate_passed (True when >=1
    // newly-added covering test is red) plus a named `reason` on halt and
    // the individual green_at_baseline entries (never collapsed into a
    // count). The pre-amendment keys are REMOVED, not kept as aliases.
    gate_passed: { type: "boolean" },
    // KI-BO-004: `reason` is null on a passing gate — verify_red_baseline only
    // names a reason when it halts. Declaring it string-only made the agent
    // coerce the null, so the journal recorded the four-character string
    // "null" (observed on the TKT-600a-1 run). Harmless while the workflow
    // branches on gate_passed, but a trap for anything that later branches on
    // reason, where "null" is truthy and matches no named halt reason.
    reason: { type: ["string", "null"] },
    green_at_baseline: { type: "array" },
    message: { type: "string" },
  },
};

const CODER_SCHEMA = {
  type: "object",
  required: ["status"],
  properties: {
    status: { type: "string", enum: ["ok", "blocker", "failed"] },
    files_modified: { type: "array", items: { type: "string" } },
    green: { type: "boolean" },
    coverage_ok: { type: "boolean" },
    uncovered_ac_ids: { type: "array", items: { type: "string" } },
    message: { type: "string" },
  },
};

const COMMIT_SCHEMA = {
  type: "object",
  required: ["status"],
  properties: {
    status: { type: "string", enum: ["ok", "error"] },
    branch: { type: "string" },
    message: { type: "string" },
  },
};

const PR_SCHEMA = {
  type: "object",
  required: ["status"],
  properties: {
    status: { type: "string", enum: ["ok", "error"] },
    pr_url: { type: "string" },
    message: { type: "string" },
  },
};

// ---------------------------------------------------------------------------
// Phase 0 — Argument validation
// ---------------------------------------------------------------------------

const acId = (args && args.ac) || null;

if (!acId || typeof acId !== "string" || !acId.trim()) {
  return {
    status: "error",
    message:
      "fast-lane-ship requires a single AC id: Workflow(\"fast-lane-ship\", " +
      "{ ac: \"<AC-id>\" }). No AC id was supplied.",
  };
}

const targetAc = acId.trim();
// Slug derived from the AC id — deterministic, no Date/random (E2 constraint).
const slug = targetAc.toLowerCase().replace(/[^a-z0-9._-]/g, "-");
const acStoreRel = "docs/acceptance-criteria";

// ---------------------------------------------------------------------------
// Phase 1 — Worktree: auto-create off origin/main (BO-2400f-3)
// ---------------------------------------------------------------------------

phase("Worktree");

const worktreeResult = await agent(
  `You are the worktree phase agent for a fast-lane build. Create the isolated ` +
  `build worktree — do NOT ask for confirmation (creation is non-destructive).\n\n` +
  `Run this single Bash command from the repository root:\n` +
  `   python3 {{config.output_root}}/scripts/setup_ticket_worktree.py create-fastlane-worktree "${slug}"\n\n` +
  `It fetches origin, creates a worktree on branch fast-lane/${slug} rooted at the ` +
  `latest origin/main, bootstraps it, and prints a single JSON line with keys ` +
  `worktree_path, branch, ac_store_path, created.\n\n` +
  `Return that JSON verbatim as: ` +
  `{ "worktree_path": "<abs path>", "branch": "fast-lane/${slug}", "ac_store_path": "<abs>", "created": <bool> }.\n` +
  `If the command exits non-zero, return { "worktree_path": "", "message": "<stderr>" }.`,
  {
    agentType: "worktree-agent",
    schema: WORKTREE_SCHEMA,
    label: "fastlane-worktree",
    phase: "Worktree",
  }
);

if (!worktreeResult || !worktreeResult.worktree_path) {
  return {
    status: "error",
    message:
      "Worktree phase failed — could not create the fast-lane worktree. " +
      `Detail: ${JSON.stringify(worktreeResult)}`,
    failing_phase: "worktree",
  };
}

const worktreePath = worktreeResult.worktree_path;
const branch = worktreeResult.branch || `fast-lane/${slug}`;
// Derive the AC store root deterministically from the worktree path — do NOT
// trust worktreeResult.ac_store_path. The store lives at a fixed convention
// (<worktree>/docs/acceptance-criteria) inside every worktree cut from
// origin/main, but the worktree phase is an LLM agent that has been observed to
// echo a fabricated path (e.g. <worktree>/tickets/00_inbox) instead of the
// create-fastlane-worktree command's real JSON output, which then sent the
// resolver looking in the wrong directory (observed 2026-08-11 on BO-2400f).
// Deriving it removes the LLM from the trust path for this deterministic value.
const acStoreRoot = `${worktreePath}/${acStoreRel}`;
const gateScript = `${worktreePath}/{{config.output_root}}/scripts/build_orchestration/fast_lane.py`;

// ---------------------------------------------------------------------------
// Phase 2 — Resolve the connected build set (BO-2400f-1/f-2)
// ---------------------------------------------------------------------------

phase("Resolve");

const selectConnectedInvocation =
  `python3 ${gateScript} select_connected --ac ${targetAc} --ac-root ${acStoreRoot}`;

const resolverResult = await agent(
  `You are the resolver phase agent for a fast-lane build.\n\n` +
  `Run this single Bash command and parse its JSON stdout (a list of AC ids):\n` +
  `   ${selectConnectedInvocation}\n\n` +
  `This is the connected build set for ${targetAc}: its subtree plus any unmet ` +
  `dependency prerequisites, in dependency order, restricted to not-done leaves.\n\n` +
  `If the command exits non-zero (e.g. the AC id does not exist), return ` +
  `{ "ac_ids": [], "message": "<stderr>" }.\n` +
  `Otherwise return { "ac_ids": [<the parsed list>], "message": "<n> to build" }.`,
  {
    agentType: "status-checker",
    schema: RESOLVER_SCHEMA,
    label: "resolve-connected",
    phase: "Resolve",
  }
);

const acIds = (resolverResult && resolverResult.ac_ids) || [];

// Distinguish a RESOLUTION ERROR from a genuinely-empty connected set.
// A bad --ac-root (e.g. an un-deployed create-fastlane-worktree returning the
// wrong ac_store_path), a missing store, or a typo'd id all make the resolver
// exit non-zero with a diagnostic message while still yielding an empty ac_ids
// list. Treating that as a clean "nothing to build" no-op hides a real failure
// (observed 2026-08-10: ac_store_path resolved to <worktree>/tickets, so every
// id was "not found"). Fail loudly instead so the operator sees the cause.
const resolverMsg = (resolverResult && resolverResult.message) || "";
if (acIds.length === 0 && /not found|no build set|no such|does not exist|no module|traceback|error/i.test(resolverMsg)) {
  return {
    status: "error",
    message:
      `Resolver could not resolve the connected build set for ${targetAc} — ` +
      `this is a failure, not an empty set. Check that the AC store path is ` +
      `correct (a stale/un-deployed create-fastlane-worktree can return the ` +
      `wrong ac_store_path) and that ${targetAc} exists on origin/main. ` +
      `Resolver said: ${resolverMsg}`,
    failing_phase: "resolve",
    worktree_path: worktreePath,
    branch,
    ac_store_root: acStoreRoot,
    classification: "halt",
  };
}

// Empty set — clean no-op (nothing to build). No worktree churn beyond the
// created worktree, no empty PR (BO-2400f-2).
if (acIds.length === 0) {
  return {
    status: "ok",
    message:
      `Nothing to build: the connected set for ${targetAc} is empty ` +
      `(already done, or the id resolved to no not-done leaves). ` +
      `${resolverResult ? resolverResult.message || "" : ""}`,
    worktree_path: worktreePath,
    branch,
    ac_ids: [],
    nothing_to_build: true,
  };
}

const batchIds = acIds.join(" ");
const batchIdsCsv = acIds.join(",");

// ---------------------------------------------------------------------------
// Lifecycle: claim the connected set (flip todo → in_progress)
// ---------------------------------------------------------------------------
const claimResult = await agent(
  `You are the claim-phase agent for a fast-lane build.\n\n` +
  `Run this single Bash command and parse its JSON stdout:\n` +
  `   python3 ${gateScript} claim --ac-ids ${batchIdsCsv} --ac-root ${acStoreRoot}\n\n` +
  `Returns {"claimed":[...],"excluded_claimed":[...],"target_refused":<bool>}.\n` +
  `If the command exits non-zero or target_refused is true, the connected set is\n` +
  `already in_progress (owned by a concurrent run) — return the JSON plus "message".\n` +
  `Otherwise return the parsed JSON with message "claimed <N> ACs".`,
  {
    agentType: "status-checker",
    schema: {
      type: "object",
      required: ["claimed", "target_refused"],
      properties: {
        claimed: { type: "array", items: { type: "string" } },
        excluded_claimed: { type: "array", items: { type: "string" } },
        target_refused: { type: "boolean" },
        message: { type: "string" },
      },
    },
    label: "claim-connected",
    phase: "Resolve",
  }
);

if (!claimResult || claimResult.target_refused) {
  return {
    status: "halt",
    classification: "halt",
    message:
      "connected set already claimed / in progress — a concurrent fast-lane run " +
      "owns these ACs. Wait for that run to complete or release stuck claims. " +
      `Detail: ${JSON.stringify(claimResult)}`,
    worktree_path: worktreePath,
    branch,
    ac_ids: acIds,
  };
}

// Only the ACs THIS run actually flipped to in_progress may be released on a
// later failure. Releasing the full resolved set would reset a concurrent run's
// claims (its ACs land in excluded_claimed here, NOT in claimResult.claimed).
const claimedIdsCsv = (claimResult.claimed || []).join(",");
const releaseInvocation =
  `python3 ${gateScript} release --ac-ids ${claimedIdsCsv} --ac-root ${acStoreRoot}`;

// ---------------------------------------------------------------------------
// Gate invocations (inlined lean loop — scoped to the resolved ids)
// ---------------------------------------------------------------------------

const redBaselineInvocation =
  `python3 ${gateScript} verify_red_baseline --ac-ids ${batchIds} --test-root ${worktreePath}`;

const greenCoverageInvocation =
  `python3 ${gateScript} verify_green_and_coverage` +
  ` --ac-ids ${batchIds} --test-root ${worktreePath} --ac-root ${acStoreRoot}`;

// ---------------------------------------------------------------------------
// Phase 3 — test-writer: red stubs for the resolved ids + red-baseline gate
// ---------------------------------------------------------------------------

phase("Test Writer");

const testWriterResult = await agent(
  `You are the test-writer phase agent for a fast-lane AC-scoped build.\n\n` +
  `Worktree: ${worktreePath}\n` +
  `AC store: ${acStoreRoot}\n` +
  `Connected build set (dependency order): ${batchIds}\n\n` +
  `Step 1 — Write failing stubs:\n` +
  `For each AC id above, read its YAML from ${acStoreRoot} and write a minimal ` +
  `failing test that asserts the AC behavior. Tag each test with a '# covers: <AC-id>' ` +
  `comment. All stubs MUST be RED — do NOT write production code.\n\n` +
  `Step 2 — Run the red-baseline gate (single Bash command):\n` +
  `   ${redBaselineInvocation}\n` +
  `Parse the JSON: { "gate_passed": <bool>, "reason": <string|null>, "red": [...], ` +
  `"green_at_baseline": [...], "inconclusive": [...], "preexisting": [...] }.\n\n` +
  `Return JSON: { "status": "ok", "tests_written": ["<path>", ...], "gate_passed": <bool>, ` +
  `"reason": <string|null>, "green_at_baseline": [...], "message": "<summary>" }\n\n` +
  `CRITICAL: gate_passed and reason MUST reflect the real gate output — do NOT fabricate ` +
  `them. Fail closed: if the gate's JSON cannot be parsed or "gate_passed" is absent, ` +
  `report gate_passed: false.`,
  {
    agentType: "test-writer",
    schema: TEST_WRITER_SCHEMA,
    label: "test-writer-connected",
    phase: "Test Writer",
  }
);

if (!testWriterResult || testWriterResult.status !== "ok") {
  await agent(
    `You are the release-phase agent. The test-writer phase failed after claiming.\n\n` +
    `Release all claimed ACs back to todo by running this single Bash command:\n` +
    `   ${releaseInvocation}\n\n` +
    `Return {"released":[...]} from stdout. Ignore non-zero exit (best-effort release).`,
    { agentType: "status-checker", label: "release-on-test-writer-fail", phase: "Test Writer" }
  );
  return {
    status: "blocked",
    message:
      "test-writer phase did not return ok. " +
      `Detail: ${JSON.stringify(testWriterResult)}`,
    failing_phase: "test-writer",
    worktree_path: worktreePath,
    classification: "halt",
  };
}

// gate_passed is read as a plain JS falsy check so a missing key (version
// skew between this workflow and an older/newer fast_lane.py) fails closed
// exactly like an explicit gate_passed: false — never treated as passing.
if (!testWriterResult.gate_passed) {
  await agent(
    `You are the release-phase agent. The red-baseline gate failed after claiming.\n\n` +
    `Release all claimed ACs back to todo by running this single Bash command:\n` +
    `   ${releaseInvocation}\n\n` +
    `Return {"released":[...]} from stdout. Ignore non-zero exit (best-effort release).`,
    { agentType: "status-checker", label: "release-on-red-baseline-fail", phase: "Test Writer" }
  );
  return {
    status: "blocked",
    message:
      "verify_red_baseline gate failed: test-writer reported gate_passed=false. " +
      `Reason: ${testWriterResult.reason || "unknown"}. ` +
      `Green-at-baseline: ${JSON.stringify(testWriterResult.green_at_baseline || [])}. ` +
      "At least one newly-added scoped test must be red before the coder is dispatched.",
    failing_phase: "test-writer",
    gate: "verify_red_baseline",
    worktree_path: worktreePath,
    classification: "halt",
  };
}

// ---------------------------------------------------------------------------
// Phase 4 — python-coder: make green + green+coverage gate
// ---------------------------------------------------------------------------

phase("Coder");

const coderResult = await agent(
  `You are the python-coder phase agent for a fast-lane AC-scoped build.\n\n` +
  `Worktree: ${worktreePath}\n` +
  `AC store: ${acStoreRoot}\n` +
  `Connected build set (dependency order): ${batchIds}\n\n` +
  `Step 1 — Implement:\n` +
  `The test-writer has written failing stubs. Run the suite to see the failures, ` +
  `then implement the minimum production code to make every scoped test PASS. ` +
  `Build the ACs in the order listed (prerequisites first).\n\n` +
  `Step 2 — Run the green+coverage gate (single Bash command):\n` +
  `   ${greenCoverageInvocation}\n` +
  `Parse the JSON: { "green": <bool>, "coverage_ok": <bool>, "uncovered_ac_ids": [...] }.\n\n` +
  `Return JSON: { "status": "ok", "files_modified": ["<path>", ...], "green": <bool>, "coverage_ok": <bool>, "uncovered_ac_ids": [...], "message": "<summary>" }\n\n` +
  `CONSTRAINT: implement only what the failing tests require — no gold-plating.\n` +
  `CRITICAL: green and coverage_ok MUST reflect the real gate output — do NOT fabricate them.`,
  {
    agentType: "python-coder",
    schema: CODER_SCHEMA,
    label: "coder-connected",
    phase: "Coder",
  }
);

if (!coderResult || coderResult.status !== "ok") {
  await agent(
    `You are the release-phase agent. The coder phase failed after claiming.\n\n` +
    `Release all claimed ACs back to todo by running this single Bash command:\n` +
    `   ${releaseInvocation}\n\n` +
    `Return {"released":[...]} from stdout. Ignore non-zero exit (best-effort release).`,
    { agentType: "status-checker", label: "release-on-coder-fail", phase: "Coder" }
  );
  return {
    status: "blocked",
    message:
      "python-coder phase did not return ok. " +
      `Detail: ${JSON.stringify(coderResult)}`,
    failing_phase: "python-coder",
    worktree_path: worktreePath,
    classification: "halt",
  };
}

// Gate is the arbiter: no commit, no PR unless green AND coverage hold (BO-2400f-4).
if (!coderResult.green || !coderResult.coverage_ok) {
  await agent(
    `You are the release-phase agent. The green+coverage gate failed after claiming.\n\n` +
    `Release all claimed ACs back to todo by running this single Bash command:\n` +
    `   ${releaseInvocation}\n\n` +
    `Return {"released":[...]} from stdout. Ignore non-zero exit (best-effort release).`,
    { agentType: "status-checker", label: "release-on-coverage-fail", phase: "Coder" }
  );
  return {
    status: "blocked",
    message:
      "verify_green_and_coverage gate failed: " +
      `green=${coderResult.green}, coverage_ok=${coderResult.coverage_ok}. ` +
      `Uncovered ACs: ${JSON.stringify(coderResult.uncovered_ac_ids || [])}. ` +
      "No PR is opened — fix failing tests and/or add AC coverage.",
    failing_phase: "python-coder",
    gate: "verify_green_and_coverage",
    uncovered_ac_ids: coderResult.uncovered_ac_ids || [],
    worktree_path: worktreePath,
    classification: "halt",
  };
}

// ---------------------------------------------------------------------------
// Phase 5 — Commit: mark ACs done + commit on the worktree branch (BO-2400f-4)
// ---------------------------------------------------------------------------

phase("Commit");

const markDoneInvocation =
  `python3 ${gateScript} mark_done --ac-ids ${batchIdsCsv}` +
  ` --ac-root ${acStoreRoot} --test-root ${worktreePath}`;

const commitResult = await agent(
  `You are the commit phase agent for a fast-lane build. The gates have passed ` +
  `and the user pre-authorized this build by pointing at the AC — do NOT ask for ` +
  `another confirmation. Commit directly.\n\n` +
  `Worktree: ${worktreePath}\n` +
  `Branch: ${branch}\n` +
  `Built ACs (dependency order): ${batchIds}\n\n` +
  `Step 1 — Mark all built ACs done (coverage-gated; single Bash call):\n` +
  `   ${markDoneInvocation}\n` +
  `Parse the JSON: { "marked_done": [...], "all_done": <bool>, "stale": [...] }.\n` +
  `If it exits non-zero or all_done is false, STOP and return ` +
  `{ "status": "error", "message": "mark_done stale: <stale ids>" }.\n\n` +
  `Step 2 — Stage everything on the worktree:\n` +
  `   git -C "${worktreePath}" add -A\n\n` +
  `Step 3 — Commit (set the COMMIT_AGENT_MODE token so the guardian allows it):\n` +
  `   COMMIT_AGENT_MODE=1 git -C "${worktreePath}" commit -m "feat: fast-lane build of ${targetAc} connected set (${acIds.length} ACs)" -m "Built via /fast-lane-build: ${batchIds}. Gates: verify_red_baseline + verify_green_and_coverage green."\n` +
  `   Every claim in the commit message must be verifiable in the staged diff.\n` +
  `   If a pre-commit hook fails, fix the reported issue and retry once.\n\n` +
  `Return JSON: { "status": "ok", "branch": "${branch}", "message": "<summary>" } ` +
  `or { "status": "error", "message": "<what failed>" }.`,
  {
    agentType: "commit",
    schema: COMMIT_SCHEMA,
    label: "fastlane-commit",
    phase: "Commit",
  }
);

if (!commitResult || commitResult.status !== "ok") {
  // The commit phase can fail AFTER mark_done flipped some/all claimed ACs to
  // done on disk (e.g. a stale-todo mark_done, or a pre-commit hook rejecting
  // the commit). Nothing was committed, so roll the whole run's claims back to
  // todo — releasing done_ids=[] resets even already-done claims (BO-2400f-10).
  await agent(
    `You are the release-phase agent. The commit phase failed after claiming and ` +
    `marking done, but nothing was committed.\n\n` +
    `Roll all claimed ACs back to todo by running this single Bash command:\n` +
    `   ${releaseInvocation}\n\n` +
    `Return {"released":[...]} from stdout. Ignore non-zero exit (best-effort release).`,
    { agentType: "status-checker", label: "release-on-commit-fail", phase: "Commit" }
  );
  return {
    status: "blocked",
    message:
      "Commit phase did not succeed — no PR opened. " +
      `Detail: ${JSON.stringify(commitResult)}`,
    failing_phase: "commit",
    worktree_path: worktreePath,
    classification: "halt",
  };
}

// ---------------------------------------------------------------------------
// Phase 6 — Pull Request: open against main (gh + EMU fallback) (BO-2400f-4)
// ---------------------------------------------------------------------------

phase("Pull Request");

const prTitle = `feat: fast-lane build of ${targetAc} connected set`;
const prBody =
  `## Summary\n\n` +
  `One-command fast-lane build of ${targetAc} and its connected set.\n\n` +
  `- **Built ACs (dependency order):** ${batchIds}\n` +
  `- **Gates:** verify_red_baseline + verify_green_and_coverage (both green)\n\n` +
  `## Test plan\n\n` +
  `- [ ] Required CI checks pass (Lint, vocab, pytest, done-proof).\n` +
  `- [ ] Every built AC has a passing '# covers:' test.`;

const prResult = await agent(
  `You are the pull-request phase agent for a fast-lane build. The user ` +
  `pre-authorized delivery by pointing at the AC — do NOT ask for another ` +
  `confirmation.\n\n` +
  `Branch: ${branch}\n` +
  `Worktree: ${worktreePath}\n` +
  `Base: main\n\n` +
  `Step 1 — Push the branch:\n` +
  `   git -C "${worktreePath}" push --set-upstream origin ${branch}\n` +
  `   If push exits non-zero, return { "status": "error", "message": "push failed: <stderr>" }.\n\n` +
  `Step 2 — Switch to the authorized account (EMU-tolerant):\n` +
  `   gh auth switch --user urlmonitor\n` +
  `   If this exits non-zero, continue anyway (it may already be active).\n\n` +
  `Step 3 — Open the PR (with REST fallback for EMU accounts):\n` +
  `   Attempt A — gh pr create:\n` +
  `     gh pr create --base main --head "${branch}" ` +
  `--title "${prTitle.replace(/"/g, '\\"')}" ` +
  `--body "$(cat <<'PREOF'\n${prBody}\nPREOF\n)"\n` +
  `     Capture the PR URL from stdout. On success, go to Step 4.\n` +
  `     If it fails with "Enterprise Managed User", "createPullRequest", or "GraphQL", ` +
  `fall through to Attempt B. Any other failure: return ` +
  `{ "status": "error", "message": "gh pr create failed: <stderr>" }.\n\n` +
  `   Attempt B — REST fallback:\n` +
  `     Get org/repo: git -C "${worktreePath}" remote get-url origin (parse org/repo).\n` +
  `     gh api -X POST repos/<org>/<repo>/pulls -f title="${prTitle.replace(/"/g, '\\"')}" ` +
  `-f head="${branch}" -f base="main" -f body="<body>"\n` +
  `     Parse .html_url from the JSON response. If gh api exits non-zero, return ` +
  `{ "status": "error", "message": "gh api REST fallback failed: <stderr>" }.\n\n` +
  `Step 4 — Return: { "status": "ok", "pr_url": "<full https url>", "message": "PR opened" }.`,
  {
    agentType: "pull-request",
    schema: PR_SCHEMA,
    label: "fastlane-pr",
    phase: "Pull Request",
  }
);

if (!prResult || prResult.status !== "ok") {
  return {
    status: "error",
    message:
      "Build committed on the worktree branch, but opening the PR failed. " +
      `Branch ${branch} is ready — open the PR manually. ` +
      `Detail: ${JSON.stringify(prResult)}`,
    failing_phase: "pull-request",
    worktree_path: worktreePath,
    branch,
    ac_ids: acIds,
  };
}

// ---------------------------------------------------------------------------
// Done
// ---------------------------------------------------------------------------

return {
  status: "ok",
  message:
    `Fast-lane build of ${targetAc} complete. Built ${acIds.length} AC(s) in ` +
    `dependency order, gates green, committed on ${branch}, PR opened.`,
  target_ac: targetAc,
  worktree_path: worktreePath,
  branch,
  ac_ids: acIds,
  tests_written: (testWriterResult && testWriterResult.tests_written) || [],
  files_modified: (coderResult && coderResult.files_modified) || [],
  pr_url: prResult.pr_url || null,
};
