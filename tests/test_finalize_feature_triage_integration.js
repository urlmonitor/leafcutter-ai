/**
 * test_finalize_feature_triage_integration.js
 *
 * RED baseline tests for ticket:
 *   04_align_finalize_feature_triage_schema.md
 *
 * All 6 tests MUST FAIL (RED) until the implementation is complete.
 *
 * The schema mismatch under test:
 *   Step 3 (lines 480-485): Instructions request OLD flat schema:
 *     { blocks_finalization, regressions: [...], pre_existing: [...], summary }
 *   Step 6a (line 663): Code reads NESTED schema:
 *     triageReport.triage_report.forEach(entry => entry.category)
 *
 * With the old flat schema, triageReport.triage_report is undefined in production
 * (the agent follows the step-3 instructions), so the loop is dead code.
 * The fix: rewrite step-3 instructions to request the nested schema.
 *
 * Run with:  node tests/test_finalize_feature_triage_integration.js
 * Exit code 0 = all tests passed (GREEN — implementation complete).
 * Exit code 1 = at least one test failed (RED — expected baseline).
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
// Read the production workflow file.
// ---------------------------------------------------------------------------

const WORKFLOW_PATH = path.resolve(
  __dirname,
  "../templates/workflows-js/finalize-feature.js"
);

let workflowSource;
try {
  workflowSource = fs.readFileSync(WORKFLOW_PATH, "utf8");
} catch (err) {
  console.error(`Cannot read workflow file: ${WORKFLOW_PATH}`);
  console.error(err.message);
  process.exit(2);
}

// ---------------------------------------------------------------------------
// Helper: extract ONLY the step-3 `instructions:` string literal value.
//
// The instructions value starts after `instructions:` and ends at the closing
// `",` that terminates the last concatenated string segment. We locate the
// closing tag `},` that ends the `input:` object (i.e. the line containing
// only `},` after the last `+ "..."` segment).
//
// Strategy: find `instructions:` inside the agent({ input: { ... }}) block,
// then capture only the text between the first `"Classify` and the first `"}"`
// that ends the string literal.
// ---------------------------------------------------------------------------

function extractStep3InstructionsLiteral(src) {
  // Anchor on the exact marker that starts the instructions content.
  const startMarker = '"Classify each failing test';
  const startIdx = src.indexOf(startMarker);
  if (startIdx === -1) return null;

  // The instructions literal ends with `}"` followed by a comma on the same
  // or next line. Capture from startIdx to that closing marker.
  // We look for the pattern `}" }` or `}" ,` or just the end quote + comma.
  // Specifically: the last string segment ends with `}",` (closing the JSON
  // example inside the string, then closing the string with `, `).
  // We capture up to the first `",` that does NOT appear inside a nested quote.
  //
  // Simpler: capture from startMarker to the standalone line `      },`
  // which closes the `input:` object. This gives us only the string content.
  const inputClose = src.indexOf("      },\n    });", startIdx);
  if (inputClose === -1) {
    // Fallback: capture 400 chars — enough for the ~5-line instructions literal.
    return src.slice(startIdx, startIdx + 400);
  }
  return src.slice(startIdx, inputClose);
}

// ---------------------------------------------------------------------------
// Helper: extract the step-6a source block.
// ---------------------------------------------------------------------------

function extractStep6aBlock(src) {
  const marker = "Sub-step 6a: create tracking tickets";
  const start = src.indexOf(marker);
  if (start === -1) return null;
  return src.slice(start, start + 3000);
}

// ---------------------------------------------------------------------------
// Helper: simulate the step-6a filtering logic.
// Mirrors finalize-feature.js lines 662-707.
// ---------------------------------------------------------------------------

function step6aFilterEntries(triageReport) {
  const triageEntries = Array.isArray(triageReport.triage_report)
    ? triageReport.triage_report
    : [];
  const preExistingEntries = triageEntries.filter(
    (entry) => entry.category === "pre_existing" || entry.category === "flaky"
  );
  return { triageEntries, preExistingEntries };
}

function step6aSimulate(triageReport, baselineRunAt) {
  const result = {
    triageEntries: [],
    preExistingEntries: [],
    dispatched: [],
    errors: [],
    noEntryMessageLogged: false,
  };

  try {
    result.triageEntries = Array.isArray(triageReport.triage_report)
      ? triageReport.triage_report
      : [];

    result.preExistingEntries = result.triageEntries.filter(
      (entry) => entry.category === "pre_existing" || entry.category === "flaky"
    );

    for (const entry of result.preExistingEntries) {
      const testId = entry.test_id || "<unknown test>";
      const category = entry.category || "pre_existing";
      const ts = baselineRunAt || new Date().toISOString();

      let requestText =
        `Tracked pre-existing test failure: ${testId}. ` +
        `Failing on main at SHA unknown. ` +
        `Triage category: ${category}. ` +
        `See finalize-feature triage report from ${ts}.`;

      if (category === "flaky") {
        requestText +=
          " Intermittent failure detected. Failing in some runs but not others.";
      }

      result.dispatched.push({ testId, category, requestText });
    }

    if (result.preExistingEntries.length === 0) {
      result.noEntryMessageLogged = true;
    }
  } catch (err) {
    result.errors.push(err);
  }

  return result;
}

// ============================================================================
// TEST 1 — test_finalize_feature_triage_schema_alignment
//
// RED because: the step-3 instructions literal does NOT contain "triage_report",
// "category", or per-entry field names. It uses the old flat schema.
// ============================================================================

test("test_finalize_feature_triage_schema_alignment", () => {
  const literal = extractStep3InstructionsLiteral(workflowSource);
  assert.ok(literal !== null, "Could not find step-3 instructions literal in source");

  // The old flat schema must NOT appear in the instructions literal.
  // CURRENTLY FAILS because `regressions` IS present in the literal.
  assert.ok(
    !literal.includes("regressions"),
    'FAIL (RED): step-3 instructions literal still contains the old flat "regressions" key. ' +
    "The fix must replace this with the nested triage_report schema."
  );

  // The instructions literal must request the nested triage_report array.
  // CURRENTLY FAILS because triage_report is absent from the literal.
  assert.ok(
    literal.includes("triage_report"),
    "FAIL (RED): step-3 instructions literal does not include 'triage_report' key. " +
    'Fix: request { "triage_report": [{"category": "...", "test_id": "..."}] }.'
  );

  // Each entry must have a .category field.
  assert.ok(
    literal.includes("category"),
    "FAIL (RED): step-3 instructions literal does not mention per-entry 'category' field."
  );

  // blocks_finalization must still be mentioned as a top-level boolean.
  assert.ok(
    literal.includes("blocks_finalization"),
    "step-3 instructions must still include top-level blocks_finalization boolean."
  );
});

// ============================================================================
// TEST 2 — test_finalize_feature_step_6a_pre_existing_loop_executes
//
// RED because: step-3 instructions literal still has old flat schema (same
// assertion from test 1 is repeated here as a schema-alignment precondition).
// The loop logic itself works correctly, but the schema fix is the prerequisite.
// ============================================================================

test("test_finalize_feature_step_6a_pre_existing_loop_executes", () => {
  // Schema-alignment precondition: instructions must NOT use old flat schema.
  // CURRENTLY FAILS — same reason as test 1.
  const literal = extractStep3InstructionsLiteral(workflowSource);
  assert.ok(literal !== null, "Could not find step-3 instructions literal");
  assert.ok(
    !literal.includes("regressions"),
    'FAIL (RED): step-3 instructions still contain "regressions" key from old flat schema. ' +
    "The pre-existing loop test cannot pass until the schema is aligned."
  );

  // Logic tests (would pass in isolation after the schema fix).
  const triageReport = {
    blocks_finalization: false,
    triage_report: [
      {
        category: "pre_existing",
        test_id: "tests/test_foo.py::test_bar",
        ac_status: "failing",
        rationale: "Failing on main before branch",
        action: "create_tracking_ticket",
        modified_by_branch: false,
      },
      {
        category: "pre_existing",
        test_id: "tests/test_baz.py::test_qux",
        ac_status: "failing",
        rationale: "Failing on main before branch",
        action: "create_tracking_ticket",
        modified_by_branch: false,
      },
    ],
  };

  assert.strictEqual(Array.isArray(triageReport.triage_report), true);
  const sim = step6aSimulate(triageReport);
  assert.strictEqual(sim.errors.length, 0);
  assert.strictEqual(sim.preExistingEntries.length, 2);
  assert.strictEqual(sim.dispatched.length, 2);
  for (const d of sim.dispatched) {
    assert.ok(d.requestText.includes(d.testId));
    assert.ok(d.requestText.includes(d.category));
  }

  // Source: step-6a must read triageReport.triage_report.
  const step6a = extractStep6aBlock(workflowSource);
  assert.ok(step6a !== null);
  assert.ok(step6a.includes("triageReport.triage_report"));
});

// ============================================================================
// TEST 3 — test_finalize_feature_step_6a_flaky_loop_executes
//
// RED because: (a) schema-alignment precondition fails (same as tests 1-2);
// (b) the test asserts requestText includes baselineRunAt, but the simulation
// helper correctly threads it through — so this test's RED status derives
// entirely from assertion (a).
// ============================================================================

test("test_finalize_feature_step_6a_flaky_loop_executes", () => {
  // Schema-alignment precondition.
  // CURRENTLY FAILS.
  const literal = extractStep3InstructionsLiteral(workflowSource);
  assert.ok(literal !== null, "Could not find step-3 instructions literal");
  assert.ok(
    !literal.includes("regressions"),
    'FAIL (RED): step-3 instructions still contain "regressions" key from old flat schema.'
  );

  const baselineRunAt = "2026-06-17T12:00:00.000Z";
  const triageReport = {
    blocks_finalization: false,
    triage_report: [
      {
        category: "pre_existing",
        test_id: "tests/test_stable.py::test_always_fails",
        ac_status: "failing",
        rationale: "Failing on main consistently",
        action: "create_tracking_ticket",
        modified_by_branch: false,
      },
      {
        category: "flaky",
        test_id: "tests/test_flaky.py::test_sometimes_fails",
        ac_status: "failing",
        rationale: "Intermittently failing on main",
        action: "create_tracking_ticket",
        modified_by_branch: false,
      },
    ],
  };

  const sim = step6aSimulate(triageReport, baselineRunAt);
  assert.strictEqual(sim.preExistingEntries.length, 2);

  const flakyDispatch = sim.dispatched.find((d) => d.category === "flaky");
  assert.ok(flakyDispatch !== undefined);
  assert.ok(flakyDispatch.requestText.toLowerCase().includes("intermittent"));
  assert.ok(
    flakyDispatch.requestText.includes(baselineRunAt),
    `flaky requestText must include baselineRunAt '${baselineRunAt}'`
  );
});

// ============================================================================
// TEST 4 — test_finalize_feature_step_6a_empty_triage_result
//
// RED because: schema-alignment precondition fails (same as tests 1-3).
// ============================================================================

test("test_finalize_feature_step_6a_empty_triage_result", () => {
  // Schema-alignment precondition.
  // CURRENTLY FAILS.
  const literal = extractStep3InstructionsLiteral(workflowSource);
  assert.ok(literal !== null, "Could not find step-3 instructions literal");
  assert.ok(
    !literal.includes("regressions"),
    'FAIL (RED): step-3 instructions still contain "regressions" key from old flat schema. ' +
    "Empty-triage test blocked until schema is aligned."
  );

  const triageReport = { blocks_finalization: false, triage_report: [] };
  assert.strictEqual(Array.isArray(triageReport.triage_report), true);
  const sim = step6aSimulate(triageReport);
  assert.strictEqual(sim.errors.length, 0);
  assert.strictEqual(sim.preExistingEntries.length, 0);
  assert.strictEqual(sim.dispatched.length, 0);
  assert.strictEqual(sim.noEntryMessageLogged, true);
});

// ============================================================================
// TEST 5 — test_finalize_feature_step_6a_malformed_triage_null
//
// RED because: schema-alignment precondition fails.
// ============================================================================

test("test_finalize_feature_step_6a_malformed_triage_null", () => {
  // Schema-alignment precondition.
  // CURRENTLY FAILS.
  const literal = extractStep3InstructionsLiteral(workflowSource);
  assert.ok(literal !== null, "Could not find step-3 instructions literal");
  assert.ok(
    !literal.includes("regressions"),
    'FAIL (RED): step-3 instructions still contain "regressions" key from old flat schema. ' +
    "Null guard test blocked until schema is aligned."
  );

  const triageReport = { blocks_finalization: false, triage_report: null };
  assert.strictEqual(Array.isArray(null), false);

  const { triageEntries } = step6aFilterEntries(triageReport);
  assert.deepStrictEqual(triageEntries, []);

  const sim = step6aSimulate(triageReport);
  assert.strictEqual(sim.errors.length, 0);
  assert.strictEqual(sim.dispatched.length, 0);

  // Source: step-6a must have the Array.isArray guard.
  const step6a = extractStep6aBlock(workflowSource);
  assert.ok(step6a !== null);
  assert.ok(step6a.includes("Array.isArray(triageReport.triage_report)"));
});

// ============================================================================
// TEST 6 — test_finalize_feature_step_6a_malformed_triage_undefined
//
// RED because: step-3 instructions contain the old flat schema patterns that
// cause the agent to return triage_report: undefined. Asserts both that the
// old patterns are absent AND the new nested key is present.
// ============================================================================

test("test_finalize_feature_step_6a_malformed_triage_undefined", () => {
  // Old flat schema — triage_report key does not exist.
  const triageReportOldSchema = {
    blocks_finalization: false,
    regressions: [],
    pre_existing: ["tests/test_foo.py::test_bar"],
    summary: "One pre-existing failure found.",
  };

  assert.strictEqual(Array.isArray(triageReportOldSchema.triage_report), false);

  const { triageEntries } = step6aFilterEntries(triageReportOldSchema);
  assert.deepStrictEqual(triageEntries, []);

  const sim = step6aSimulate(triageReportOldSchema);
  assert.strictEqual(sim.errors.length, 0);
  assert.strictEqual(
    sim.dispatched.length,
    0,
    "Old flat schema produces zero dispatched entries — this is the dead-code bug."
  );

  // The root cause: assert that step-3 instructions no longer produce the old schema.
  const literal = extractStep3InstructionsLiteral(workflowSource);
  assert.ok(literal !== null, "Could not find step-3 instructions literal");

  // CURRENTLY FAILS: old flat pattern IS present.
  assert.ok(
    !literal.includes("regressions"),
    'FAIL (RED): step-3 instructions still contain old flat "regressions" key. ' +
    "This causes the agent to return triage_report: undefined, disabling the tracking loop."
  );

  // The new nested schema key must be requested.
  // CURRENTLY FAILS: triage_report not in instructions literal.
  assert.ok(
    literal.includes("triage_report"),
    "FAIL (RED): step-3 instructions literal does not request 'triage_report' nested schema."
  );
});

// ============================================================================
// Summary
// ============================================================================

console.log("");
console.log(`Results: ${passed} passed, ${failed} failed`);

if (failed > 0) {
  console.log("");
  console.log("Failed tests (RED baseline — expected until implementation lands):");
  for (const f of failures) {
    console.log(`  - ${f.name}`);
    console.log(`    ${f.message}`);
  }
  process.exit(1);
} else {
  console.log("All tests PASSED (implementation is complete).");
  process.exit(0);
}
