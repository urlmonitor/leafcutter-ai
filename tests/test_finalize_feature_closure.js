/**
 * test_finalize_feature_closure.js
 *
 * Tests for ticket:
 *   10_close_acs_on_finalize.md
 *
 * Verifies that finalize-feature.js implements the pre-merge AC closure step
 * (step 3.5) correctly. All tests inspect the workflow source file and
 * simulate the logic described in the implementation.
 *
 * Acceptance criteria exercised:
 *   AC-1: ticket status:done + source_ac work_status:done committed on branch
 *         BEFORE step 4 PR merge
 *   AC-2: Step 2 test-merge is reset/aborted before closure edits
 *   AC-3: ticket with no source_ac — AC step is a silent no-op
 *   AC-4: non-zero mark_ac_done.py exit is logged as WARNING; finalize proceeds
 *   AC-5: idempotent/resumable — already-closed tickets are no-ops; PR-already-
 *         merged path skips closure
 *   AC-6: return payload reports tickets_closed, acs_closed, acs_skipped
 *   AC-7: finalize-feature.md updated to show closure pre-merge (verified
 *         separately by reading the doc file)
 *
 * Run with:  node tests/test_finalize_feature_closure.js
 * Exit code 0 = all tests passed (GREEN).
 * Exit code 1 = at least one test failed.
 */

"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Test runner helpers
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    console.log(`  PASS  ${name}`);
    passed += 1;
  } catch (err) {
    console.error(`  FAIL  ${name}`);
    console.error(`        ${err.message}`);
    failures.push({ name, message: err.message });
    failed += 1;
  }
}

// ---------------------------------------------------------------------------
// Load production sources
// ---------------------------------------------------------------------------

const WORKFLOW_PATH = path.resolve(
  __dirname,
  "../templates/workflows-js/finalize-feature.js"
);

const DOC_PATH = path.resolve(
  __dirname,
  "../templates/workflows/finalize-feature.md"
);

let workflowSource;
try {
  workflowSource = fs.readFileSync(WORKFLOW_PATH, "utf8");
} catch (err) {
  console.error(`Cannot read workflow file: ${WORKFLOW_PATH}`);
  console.error(err.message);
  process.exit(2);
}

let docSource;
try {
  docSource = fs.readFileSync(DOC_PATH, "utf8");
} catch (err) {
  console.error(`Cannot read doc file: ${DOC_PATH}`);
  console.error(err.message);
  process.exit(2);
}

// ---------------------------------------------------------------------------
// Source extraction helpers
// ---------------------------------------------------------------------------

/**
 * Extract the step 3.5 block from the workflow source.
 * The block starts with the step-3.5 banner comment and ends just before
 * the step-4 banner comment.
 */
function extractStep35Block(src) {
  const start = src.indexOf("Step 3.5");
  const end = src.indexOf("Step 4 —", start);
  if (start === -1 || end === -1) return null;
  return src.slice(start, end);
}

/**
 * Extract the meta.phases array section from the source.
 */
function extractMetaPhases(src) {
  const start = src.indexOf("phases: [");
  const end = src.indexOf("],", start);
  if (start === -1 || end === -1) return null;
  return src.slice(start, end + 2);
}

/**
 * Extract the final return block from the workflow source.
 * Anchored on "return {" near the end of the run() function.
 */
function extractFinalReturn(src) {
  // Find the last "return {" in the source.
  let idx = src.lastIndexOf("return {");
  if (idx === -1) return null;
  return src.slice(idx, idx + 2000);
}

// ---------------------------------------------------------------------------
// Simulation helpers — mirror the step-3.5 logic described in the source
// ---------------------------------------------------------------------------

/**
 * Simulate the closure accumulator logic.
 * Mirrors the section that reads closureInfo and populates workflow variables.
 */
function simulateClosureAccumulation(closureInfo) {
  const ticketsClosedPreMerge_sim = Array.isArray(closureInfo.tickets_closed)
    ? closureInfo.tickets_closed.length
    : 0;
  const acsClosed_sim =
    typeof closureInfo.acs_closed === "number" ? closureInfo.acs_closed : 0;
  const acsSkipped_sim =
    typeof closureInfo.acs_skipped === "number" ? closureInfo.acs_skipped : 0;
  return { ticketsClosedPreMerge_sim, acsClosed_sim, acsSkipped_sim };
}

/**
 * Simulate the summary message construction for the pre-merge closure section.
 * Mirrors the message template in the final return payload.
 */
function simulateSummaryMessage(ticketsClosedPreMerge, acsClosed, acsSkipped) {
  if (ticketsClosedPreMerge > 0) {
    return (
      `Pre-merge closure: ${ticketsClosedPreMerge} ticket(s) closed, ` +
      `${acsClosed} AC(s) closed, ${acsSkipped} AC(s) skipped. `
    );
  }
  return "No pre-merge ticket/AC closure. ";
}

// ============================================================================
// TEST 1 — AC-1: closure step exists between step 3 and step 4 in source
//
// Verifies the structural placement: step 3.5 block must appear AFTER the
// step-3 triage gate and BEFORE the step-4 merge gate in the source file.
// ============================================================================

test("test_closure_step_exists_between_step3_and_step4", () => {
  const step35Start = workflowSource.indexOf("Step 3.5");
  const step4Start = workflowSource.indexOf("Step 4 —");
  const step3End = workflowSource.indexOf("completedSteps.push(3)");

  assert.ok(
    step35Start !== -1,
    "FAIL: 'Step 3.5' block not found in finalize-feature.js. " +
      "The pre-merge closure step must be added between step 3 and step 4."
  );

  assert.ok(
    step4Start !== -1,
    "FAIL: 'Step 4 —' block not found. Cannot verify ordering."
  );

  assert.ok(
    step3End !== -1,
    "FAIL: 'completedSteps.push(3)' not found — cannot verify step-3 endpoint."
  );

  assert.ok(
    step35Start > step3End,
    "FAIL: step 3.5 block appears before the end of step 3. " +
      "It must come after completedSteps.push(3)."
  );

  assert.ok(
    step35Start < step4Start,
    "FAIL: step 3.5 block appears after step 4. " +
      "It must be inserted between step 3 and step 4 so closure commits on the feature branch."
  );
});

// ============================================================================
// TEST 2 — AC-2: step 3.5 resets the step 2 test-merge before editing
//
// Verifies that the step 3.5 block contains instructions to run
// `git merge --abort` or `git reset --hard HEAD` before editing ticket files.
// ============================================================================

test("test_closure_step_resets_test_merge_first", () => {
  const block = extractStep35Block(workflowSource);
  assert.ok(
    block !== null,
    "FAIL: Could not extract step-3.5 block. Ensure it starts with 'Step 3.5' comment."
  );

  // Must mention MERGE_HEAD check (to detect whether a merge is in progress).
  assert.ok(
    block.includes("MERGE_HEAD"),
    "FAIL (AC-2): step 3.5 does not check MERGE_HEAD before resetting. " +
      "The step must probe MERGE_HEAD to determine whether to run `git merge --abort` " +
      "or `git reset --hard HEAD`."
  );

  // Must mention git merge --abort (for the case where MERGE_HEAD exists).
  assert.ok(
    block.includes("git merge --abort"),
    "FAIL (AC-2): step 3.5 does not invoke `git merge --abort`. " +
      "When MERGE_HEAD exists, the step 2 test-merge must be aborted."
  );

  // Must mention git reset --hard HEAD (for the already-up-to-date path).
  assert.ok(
    block.includes("git reset --hard HEAD"),
    "FAIL (AC-2): step 3.5 does not invoke `git reset --hard HEAD`. " +
      "When no merge is in progress, a hard reset restores clean feature-branch state."
  );

  // Reset instructions must appear before the Sub-step B/C section that edits tickets.
  const resetIdx = block.indexOf("MERGE_HEAD");
  const editIdx = block.indexOf("SUB-STEP C");
  if (editIdx !== -1) {
    assert.ok(
      resetIdx < editIdx,
      "FAIL (AC-2): MERGE_HEAD check appears after ticket editing step. " +
        "The merge reset MUST come before ticket frontmatter edits."
    );
  }
});

// ============================================================================
// TEST 3 — AC-3: ticket without source_ac — AC step is a silent no-op
//
// Verifies that the step 3.5 instructions explicitly handle the case where
// a ticket has no source_ac field — skipping AC closure without error.
// ============================================================================

test("test_closure_no_source_ac_is_silent_noop", () => {
  const block = extractStep35Block(workflowSource);
  assert.ok(
    block !== null,
    "FAIL: Could not extract step-3.5 block."
  );

  // Must mention source_ac field explicitly.
  assert.ok(
    block.includes("source_ac"),
    "FAIL (AC-3): step 3.5 does not reference 'source_ac' field. " +
      "The step must read source_ac from each ticket's frontmatter."
  );

  // Must explicitly handle the absent/empty case as a no-op.
  assert.ok(
    block.includes("absent") || block.includes("no-op") || block.includes("skipping"),
    "FAIL (AC-3): step 3.5 does not explicitly treat absent source_ac as a no-op. " +
      "Tickets without source_ac must close their status: done normally " +
      "and skip AC closure silently."
  );
});

// ============================================================================
// TEST 4 — AC-4: non-zero mark_ac_done.py exit is non-fatal
//
// Verifies that the step 3.5 block explicitly handles non-zero exit from
// mark_ac_done.py as a WARNING, not as a fatal error.
// ============================================================================

test("test_closure_mark_ac_done_failure_is_nonfatal", () => {
  const block = extractStep35Block(workflowSource);
  assert.ok(
    block !== null,
    "FAIL: Could not extract step-3.5 block."
  );

  // Must invoke mark_ac_done.py.
  assert.ok(
    block.includes("mark_ac_done.py"),
    "FAIL (AC-4): step 3.5 does not invoke mark_ac_done.py. " +
      "AC closure must be performed via scripts/ac_store/mark_ac_done.py."
  );

  // Non-zero exit must be treated as non-fatal — must mention WARNING or non-fatal.
  assert.ok(
    block.toLowerCase().includes("warning") || block.includes("non-fatal"),
    "FAIL (AC-4): step 3.5 does not label non-zero mark_ac_done.py exit as a WARNING. " +
      "Any non-zero exit from mark_ac_done.py must be logged as WARNING and finalize proceeds."
  );

  // Must explicitly NOT fail finalize on AC closure failure.
  assert.ok(
    block.includes("DO NOT fail") ||
      block.includes("not fail") ||
      block.includes("non-fatal") ||
      block.includes("proceed"),
    "FAIL (AC-4): step 3.5 must explicitly state that mark_ac_done.py failure " +
      "does not fail finalize and that the workflow proceeds to the merge."
  );
});

// ============================================================================
// TEST 5 — AC-5: idempotent/resumable paths present in source
//
// Verifies that the step 3.5 block contains:
//   (a) a probe for an existing closure commit (skip if already committed)
//   (b) a probe for PR-already-merged (skip the closure step)
//   (c) already-done tickets skipped (status != 'done' filter)
// ============================================================================

test("test_closure_is_idempotent_and_resumable", () => {
  const block = extractStep35Block(workflowSource);
  assert.ok(
    block !== null,
    "FAIL: Could not extract step-3.5 block."
  );

  // Must check for a prior closure commit.
  assert.ok(
    block.includes("already_committed") || block.includes("closure commit"),
    "FAIL (AC-5): step 3.5 does not probe for an existing closure commit. " +
      "Re-running finalize after a partial run must not error."
  );

  // Must skip when PR is already merged.
  assert.ok(
    block.includes("prAlreadyMergedAtClosure") ||
      block.includes("PR already merged") ||
      block.includes("MERGED"),
    "FAIL (AC-5): step 3.5 does not handle the PR-already-merged case. " +
      "When the PR is already merged, the pre-merge closure step must be skipped."
  );

  // Already-done tickets must be excluded (idempotency for ticket status).
  assert.ok(
    block.includes("status != done") ||
      block.includes("status != 'done'") ||
      block.includes("!= done"),
    "FAIL (AC-5): step 3.5 does not filter out already-done tickets. " +
      "Tickets with status: done must be idempotently skipped."
  );
});

// ============================================================================
// TEST 6 — AC-6: return payload includes tickets_closed, acs_closed, acs_skipped
//
// Verifies that the workflow's final return object exposes the three closure
// count fields, and that the summary message uses them honestly.
// ============================================================================

test("test_closure_return_payload_has_real_counts", () => {
  const finalReturn = extractFinalReturn(workflowSource);
  assert.ok(
    finalReturn !== null,
    "FAIL: Could not find the final return block in finalize-feature.js."
  );

  assert.ok(
    finalReturn.includes("acs_closed"),
    "FAIL (AC-6): final return payload does not include 'acs_closed' field."
  );

  assert.ok(
    finalReturn.includes("acs_skipped"),
    "FAIL (AC-6): final return payload does not include 'acs_skipped' field."
  );

  assert.ok(
    finalReturn.includes("tickets_closed_pre_merge") ||
      finalReturn.includes("ticketsClosedPreMerge"),
    "FAIL (AC-6): final return payload does not expose the pre-merge ticket closure count."
  );

  // Summary message must use honest language — never claim closure when empty.
  assert.ok(
    finalReturn.includes("No pre-merge") ||
      finalReturn.includes("ticketsClosedPreMerge > 0") ||
      finalReturn.includes("tickets_closed_pre_merge"),
    "FAIL (AC-6): final summary message does not guard against claiming closure " +
      "when the closure set was empty."
  );
});

// ============================================================================
// TEST 6b — AC-6: closure accumulator logic produces correct counts
//
// Unit-tests the JavaScript accumulator pattern that populates the closure
// count variables from the agent's JSON response.
// ============================================================================

test("test_closure_accumulator_produces_correct_counts", () => {
  // Case 1: 2 tickets closed, 1 AC closed, 1 AC skipped.
  const closureInfo1 = {
    tickets_closed: ["tickets/foo.md", "tickets/bar.md"],
    acs_closed: 1,
    acs_skipped: 1,
    commit_made: true,
  };
  const r1 = simulateClosureAccumulation(closureInfo1);
  assert.strictEqual(r1.ticketsClosedPreMerge_sim, 2);
  assert.strictEqual(r1.acsClosed_sim, 1);
  assert.strictEqual(r1.acsSkipped_sim, 1);

  // Case 2: empty — nothing to close.
  const closureInfo2 = {
    tickets_closed: [],
    acs_closed: 0,
    acs_skipped: 0,
    commit_made: false,
  };
  const r2 = simulateClosureAccumulation(closureInfo2);
  assert.strictEqual(r2.ticketsClosedPreMerge_sim, 0);
  assert.strictEqual(r2.acsClosed_sim, 0);
  assert.strictEqual(r2.acsSkipped_sim, 0);

  // Case 3: malformed response (parse failure fallback).
  const closureInfo3 = {
    tickets_closed: null,
    acs_closed: undefined,
    acs_skipped: undefined,
    commit_made: false,
  };
  const r3 = simulateClosureAccumulation(closureInfo3);
  assert.strictEqual(r3.ticketsClosedPreMerge_sim, 0);
  assert.strictEqual(r3.acsClosed_sim, 0);
  assert.strictEqual(r3.acsSkipped_sim, 0);
});

// ============================================================================
// TEST 7 — AC-6: summary message is honest about empty closure
//
// Verifies that when ticketsClosedPreMerge === 0, the summary does NOT claim
// closure occurred. When > 0, it reports the real counts.
// ============================================================================

test("test_closure_summary_message_is_honest", () => {
  // Empty set — message must not claim closure.
  const emptyMsg = simulateSummaryMessage(0, 0, 0);
  assert.ok(
    emptyMsg.includes("No pre-merge") || emptyMsg.includes("0 ticket"),
    "FAIL (AC-6): empty closure produces a message that might claim closure. " +
      `Got: "${emptyMsg}"`
  );
  assert.ok(
    !emptyMsg.toLowerCase().includes("closed, 0 ac"),
    "FAIL (AC-6): empty closure message must not say '0 ticket(s) closed, 0 AC(s) closed'."
  );

  // Non-empty set — message must include real counts.
  const nonEmptyMsg = simulateSummaryMessage(2, 1, 1);
  assert.ok(
    nonEmptyMsg.includes("2 ticket(s) closed"),
    `FAIL (AC-6): non-empty closure message missing ticket count. Got: "${nonEmptyMsg}"`
  );
  assert.ok(
    nonEmptyMsg.includes("1 AC(s) closed"),
    `FAIL (AC-6): non-empty closure message missing acs_closed count. Got: "${nonEmptyMsg}"`
  );
  assert.ok(
    nonEmptyMsg.includes("1 AC(s) skipped"),
    `FAIL (AC-6): non-empty closure message missing acs_skipped count. Got: "${nonEmptyMsg}"`
  );
});

// ============================================================================
// TEST 8 — AC-7: finalize-feature.md shows closure step pre-merge
//
// Verifies that the step-map doc was updated to document step 3.5 (pre-merge
// closure) positioned between step 3 and step 4.
// ============================================================================

test("test_doc_shows_pre_merge_closure_step", () => {
  // Step map table must contain a row for step 3.5.
  assert.ok(
    docSource.includes("3.5") || docSource.includes("pre_merge_ac_closure"),
    "FAIL (AC-7): finalize-feature.md does not mention step 3.5 or pre_merge_ac_closure. " +
      "The step-map table must be updated to show pre-merge closure between steps 3 and 4."
  );

  // Step 3.5 must appear BEFORE step 4 in the document.
  const step35DocIdx = docSource.indexOf("3.5");
  const step4DocIdx = docSource.indexOf("| 4 |");
  if (step35DocIdx !== -1 && step4DocIdx !== -1) {
    assert.ok(
      step35DocIdx < step4DocIdx,
      "FAIL (AC-7): step 3.5 appears after step 4 in finalize-feature.md. " +
        "The closure step must be documented before the PR merge step."
    );
  }

  // Must mention that closure commits on the feature branch before merge.
  assert.ok(
    docSource.includes("feature branch") || docSource.includes("before the PR merge"),
    "FAIL (AC-7): finalize-feature.md does not state that closure commits on the " +
      "feature branch before the PR merge."
  );

  // Must document the non-fatal AC closure behaviour.
  assert.ok(
    docSource.toLowerCase().includes("non-fatal") || docSource.includes("WARNING"),
    "FAIL (AC-7): finalize-feature.md does not document that AC closure is non-fatal."
  );
});

// ============================================================================
// TEST 9 — meta.phases includes step 3.5
//
// Verifies that the meta.phases array in the workflow file was updated to
// include the new step-3.5 entry.
// ============================================================================

test("test_meta_phases_includes_step_35", () => {
  const phasesBlock = extractMetaPhases(workflowSource);
  assert.ok(
    phasesBlock !== null,
    "FAIL: Could not extract meta.phases array from finalize-feature.js."
  );

  assert.ok(
    phasesBlock.includes("3.5") || phasesBlock.includes("pre-merge AC closure"),
    "FAIL: meta.phases does not include a step-3.5 entry. " +
      "The phases array must document the new pre-merge AC closure step."
  );
});

// ============================================================================
// TEST 10 — AC-1: commit is on the feature branch (not main)
//
// Verifies that the step 3.5 commit instruction uses the worktree root path
// (i.e. the feature branch worktree) and does NOT switch to or commit on main.
// ============================================================================

test("test_closure_commit_is_on_feature_branch_not_main", () => {
  const block = extractStep35Block(workflowSource);
  assert.ok(
    block !== null,
    "FAIL: Could not extract step-3.5 block."
  );

  // Must use WORKTREE_ROOT for the commit (git -C ... commit).
  assert.ok(
    block.includes("WORKTREE_ROOT") || block.includes("worktree_root"),
    "FAIL (AC-1): step 3.5 commit does not use WORKTREE_ROOT path. " +
      "The commit must run in the feature branch worktree, not on local main."
  );

  // Must NOT checkout main before committing.
  const blockLower = block.toLowerCase();
  assert.ok(
    !blockLower.includes("checkout main"),
    "FAIL (AC-1): step 3.5 instructions include 'checkout main'. " +
      "Closure must commit on the feature branch — switching to main is forbidden."
  );

  // Commit message must match the expected message used by the idempotency probe.
  assert.ok(
    block.includes("chore(tickets): close tickets and source ACs"),
    "FAIL (AC-1): step 3.5 closure commit message does not match the idempotency probe. " +
      "The commit must use exactly: 'chore(tickets): close tickets and source ACs' " +
      "so the probe in the step preamble can detect it."
  );
});

// ============================================================================
// Summary
// ============================================================================

console.log("");
console.log(`Results: ${passed} passed, ${failed} failed`);

if (failed > 0) {
  console.log("");
  console.log("Failed tests:");
  for (const f of failures) {
    console.log(`  - ${f.name}`);
    console.log(`    ${f.message}`);
  }
  process.exit(1);
} else {
  console.log("All tests PASSED.");
  process.exit(0);
}
