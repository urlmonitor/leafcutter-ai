"""Behavioral tests for BO-3000b — a status-less phase reply must be rejected
for the missing `status` alone, never with a misleading `handoff_target`
demand.

Covers:
  BO-3000b — "A phase reply missing `status` is rejected for the missing
              status alone, never with a handoff_target demand that points
              the retrying agent at the wrong field."

WHERE THIS CAME FROM. run wf_e1f3e873-096 on 2026-09-25: documentation-expert
wrapped its whole reply inside a single `input` string field, so the reply
carried no `status` key at all. PHASE_RESULT_SCHEMA's `if` clause is
`{ properties: { status: { const: 'handoff' } } }` — in JSON Schema,
`properties` passes vacuously when the named property is absent, so a
status-less reply satisfies `if` and the `then` branch's
`required: ['handoff_target']` fires alongside the real `required: ['status']`
failure. The retrying agent followed the (wrong) handoff_target error on
retries 3 and 5 instead of removing the `input` wrapper, exhausted the
5-retry cap, and halted the epic drive with its work already done.

THE FIX (not yet applied — these tests must be RED against the unmodified
schema). Add `required: ['status']` inside the `if` clause of both
PHASE_RESULT_SCHEMA declarations (templates/workflows-js/build-feature.js and
its declared twin templates/workflows-js/build-ticket.js), so the conditional
only fires when `status` is present AND equals `'handoff'`. A reply missing
`status` then fails ONLY the top-level `required: ['status']`.

WHAT MUST NOT REGRESS. BO-3000a's own guarantee — a `status: 'handoff'` reply
with no `handoff_target` must still be rejected for `handoff_target`, and one
naming a target must still be accepted. test_every_currently_valid_reply_stays_valid
below pins every reply shape PHASE_RESULT_SCHEMA accepts today so the narrowed
`if` cannot silently widen acceptance.

Every test evaluates the REAL JS source (via node) to extract the schema
object as it is actually declared — never a hand-typed Python literal copy of
it — and validates real replies against it with jsonschema's Draft7Validator.
Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep" and the
Fixture Authenticity Rule (a hand-copied schema would silently diverge from
the real declaration and could pass while the real file stays broken).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest

from jsonschema import Draft7Validator

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
BUILD_FEATURE_JS = os.path.join(REPO_ROOT, "templates", "workflows-js", "build-feature.js")
BUILD_TICKET_JS = os.path.join(REPO_ROOT, "templates", "workflows-js", "build-ticket.js")


def _extract_balanced(text: str, open_idx: int, open_ch: str, close_ch: str) -> str:
    """Return text[open_idx:...] up to (and including) the matching close_ch.

    Assumes no string literal inside the span contains open_ch/close_ch — true
    for PHASE_STATUS_VALUES and PHASE_RESULT_SCHEMA as declared today (their
    description strings contain no braces/brackets).
    """
    depth = 0
    i = open_idx
    while i < len(text):
        c = text[i]
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[open_idx : i + 1]
        i += 1
    raise ValueError(f"unbalanced {open_ch}{close_ch} starting at {open_idx}")


def _extract_phase_result_schema(js_path: str) -> dict:
    """Evaluate the REAL PHASE_RESULT_SCHEMA object literal from js_path via node.

    Extracts the exact `const PHASE_STATUS_VALUES = [...]` and
    `const PHASE_RESULT_SCHEMA = {...}` source spans (balanced-bracket scan,
    not regex-over-the-whole-object) and evaluates them with node so the
    schema under test is byte-identical to what the workflow driver actually
    declares — never a hand-typed copy that could silently diverge.
    """
    text = open(js_path, encoding="utf-8").read()

    values_decl = re.search(r"const PHASE_STATUS_VALUES = (\[)", text)
    if not values_decl:
        raise AssertionError(f"PHASE_STATUS_VALUES not found in {js_path}")
    values_src = _extract_balanced(text, values_decl.start(1), "[", "]")

    schema_decl = re.search(r"const PHASE_RESULT_SCHEMA = (\{)", text)
    if not schema_decl:
        raise AssertionError(f"PHASE_RESULT_SCHEMA not found in {js_path}")
    schema_src = _extract_balanced(text, schema_decl.start(1), "{", "}")

    node_src = (
        f"const PHASE_STATUS_VALUES = {values_src};\n"
        f"const PHASE_RESULT_SCHEMA = {schema_src};\n"
        "process.stdout.write(JSON.stringify(PHASE_RESULT_SCHEMA));"
    )
    result = subprocess.run(
        ["node", "-e", node_src],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"node failed to evaluate PHASE_RESULT_SCHEMA from {js_path}: "
            f"{result.stderr}"
        )
    return json.loads(result.stdout)


def _error_messages(validator: Draft7Validator, instance: dict) -> list:
    return sorted(e.message for e in validator.iter_errors(instance))


def _then_branch_errors(validator: Draft7Validator, instance: dict) -> list:
    """Errors raised from inside the schema's `then` branch, identified by the
    validator's own schema path rather than by matching message text. A
    non-empty list means the handoff conditional fired for this instance."""
    return [e.message for e in validator.iter_errors(instance) if "then" in e.schema_path]


@unittest.skipUnless(shutil.which("node"), "node is not available on PATH")
class TestStatuslessReplyRejectedForStatusAlone(unittest.TestCase):
    """PHASE_RESULT_SCHEMA (build-feature.js) — the wrapped-reply incident."""

    def setUp(self):
        self.schema = _extract_phase_result_schema(BUILD_FEATURE_JS)
        self.validator = Draft7Validator(self.schema)

    def test_ac1_statusless_reply_fails_only_on_missing_status(self):
        # covers: BO-3000b
        # angle: criterion
        """Incident replay: a reply wrapped as {'input': '<json string>'}
        carries no `status` key at all. It must be rejected for the missing
        `status` alone — no error may mention `handoff_target`.

        RED against the unmodified schema: the `if` clause's
        `properties: { status: { const: 'handoff' } }` passes vacuously when
        `status` is absent, so `then.required: ['handoff_target']` also
        fires, producing a second, misleading error.
        """
        reply = {"input": json.dumps({"status": "ok", "message": "done"})}

        errors = _error_messages(self.validator, reply)

        self.assertIn(
            "'status' is a required property",
            errors,
            f"expected the missing-status error; got {errors}",
        )
        handoff_errors = _then_branch_errors(self.validator, reply)
        self.assertEqual(
            handoff_errors,
            [],
            "a status-less reply must never be rejected for a missing "
            f"handoff_target — this is the exact misdirection that made "
            f"documentation-expert edit the wrong field on retries 3 and 5 "
            f"of run wf_e1f3e873-096. Got: {handoff_errors}",
        )
        self.assertEqual(
            len(errors),
            1,
            f"expected exactly one error (missing status); got {errors}",
        )

    def test_negative_control_a_reply_that_names_status_is_not_flagged_for_it(self):
        # covers: BO-3000b
        # angle: criterion
        """Negative control tied to the fix, not to an empty fixture: a reply
        that DOES carry `status` must never be rejected for a missing
        `status` — ties the assertion above to the presence/absence of the
        `status` key, not to some unrelated validator quirk.
        """
        reply = {"status": "ok"}

        errors = _error_messages(self.validator, reply)

        self.assertNotIn("'status' is a required property", errors)


@unittest.skipUnless(shutil.which("node"), "node is not available on PATH")
class TestHandoffTargetRequirementStillEnforced(unittest.TestCase):
    """BO-3000a must not regress: handoff replies still need handoff_target."""

    def setUp(self):
        self.schema = _extract_phase_result_schema(BUILD_FEATURE_JS)
        self.validator = Draft7Validator(self.schema)

    def test_handoff_without_target_is_still_rejected_for_handoff_target(self):
        # covers: BO-3000b
        # angle: failure
        """A `status: 'handoff'` reply with no `handoff_target` must still be
        rejected naming `handoff_target` — the BO-3000b narrowing must only
        stop the conditional from firing on a status-less reply, never
        disable it for a genuine handoff.
        """
        reply = {"status": "handoff"}

        errors = _error_messages(self.validator, reply)

        self.assertIn(
            "'handoff_target' is a required property",
            errors,
            f"a genuine handoff reply with no target must still be "
            f"rejected for it; got {errors}",
        )

    def test_handoff_with_target_is_accepted(self):
        # covers: BO-3000b
        # angle: failure
        """A `status: 'handoff'` reply naming a target is accepted (no
        errors) — the natural positive counterpart to the rejection above.
        """
        reply = {"status": "handoff", "handoff_target": "python-coder"}

        errors = _error_messages(self.validator, reply)

        self.assertEqual(errors, [])


@unittest.skipUnless(shutil.which("node"), "node is not available on PATH")
class TestEveryCurrentlyValidReplyStaysValid(unittest.TestCase):
    """Boundary sweep over every reply shape PHASE_RESULT_SCHEMA accepts today."""

    def setUp(self):
        self.schema = _extract_phase_result_schema(BUILD_FEATURE_JS)
        self.validator = Draft7Validator(self.schema)

    def test_every_currently_valid_reply_stays_valid(self):
        # covers: BO-3000b
        # angle: boundary
        """Sweeps the empty/one/many edge of currently-valid reply shapes:
        every non-handoff status with and without handoff_target, and a
        handoff reply that names its target. None of these may become
        invalid once the `if` clause is narrowed.
        """
        valid_replies = [
            {"status": "ok"},
            {"status": "ok", "message": "done"},
            {"status": "blocker", "message": "needs human review"},
            {"status": "failed"},
            {"status": "question", "message": "which branch?"},
            {"status": "undetermined"},
            {"status": "ok", "handoff_target": "python-coder"},
            {"status": "handoff", "handoff_target": "test-writer"},
            {
                "status": "ok",
                "tests_written": ["unit_tests/foo/test_bar.py"],
                "red_baseline_verified": True,
            },
        ]

        for reply in valid_replies:
            with self.subTest(reply=reply):
                errors = _error_messages(self.validator, reply)
                self.assertEqual(
                    errors,
                    [],
                    f"reply {reply!r} is valid today and must stay valid; "
                    f"got errors {errors}",
                )


@unittest.skipUnless(shutil.which("node"), "node is not available on PATH")
class TestBuildTicketTwinSchemaBehavesIdentically(unittest.TestCase):
    """build-ticket.js declares the identical conditional independently —
    the two drivers must not diverge on how a status-less reply is reported.
    """

    def setUp(self):
        self.schema = _extract_phase_result_schema(BUILD_TICKET_JS)
        self.validator = Draft7Validator(self.schema)

    def test_build_ticket_twin_schema_behaves_identically(self):
        # covers: BO-3000b
        # angle: real_artifact
        # surface_invoked: templates/workflows-js/build-ticket.js
        """Re-runs the statusless-reply, handoff-without-target, and
        handoff-with-target cases against build-ticket.js's OWN
        PHASE_RESULT_SCHEMA declaration (extracted independently, not copied
        from build-feature.js's), and asserts the same verdicts.

        RED against the unmodified schema for the same reason as
        test_ac1_statusless_reply_fails_only_on_missing_status: build-ticket.js's
        `if` clause carries the identical vacuous-pass defect.
        """
        statusless = {"input": json.dumps({"status": "ok"})}
        statusless_errors = _error_messages(self.validator, statusless)
        self.assertIn("'status' is a required property", statusless_errors)
        handoff_errors_on_statusless = _then_branch_errors(self.validator, statusless)
        self.assertEqual(
            handoff_errors_on_statusless,
            [],
            "build-ticket.js's twin schema must not demand handoff_target "
            f"for a status-less reply either; got {handoff_errors_on_statusless}",
        )

        handoff_no_target = {"status": "handoff"}
        self.assertIn(
            "'handoff_target' is a required property",
            _error_messages(self.validator, handoff_no_target),
        )

        handoff_with_target = {"status": "handoff", "handoff_target": "test-writer"}
        self.assertEqual(
            _error_messages(self.validator, handoff_with_target), []
        )


if __name__ == "__main__":
    unittest.main()
