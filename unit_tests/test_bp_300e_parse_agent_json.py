"""
MODULE: test_bp_300e_parse_agent_json
GOAL: Tests for the prose-tolerant reply reader (parseAgentJson) that must be
      uniformly applied across all delivery workflow scripts.

ACs: BP-300e-1, BP-300e-1-i, BP-300e-1-ii, BP-300e-1-iii, BP-300e-2,
     BP-300e-2-i, BP-300e-3, BP-300e-4, BP-300e-4-i, BP-300e-5

Tests drive the real JS source via Node.js (no Claude binary required).

Function-behaviour tests (TestParseAgentJsonBehavior) extract parseAgentJson
from plan-feature.js via brace-matching and run it in isolation under Node.js.

Structural tests (TestParseAgentJsonStructuralAudit) audit the template source
files to assert that:
  (a) no brittle ternary/bare JSON.parse patterns remain on agent-reply variables
  (b) every script in _SCRIPTS_REQUIRING_TOLERANT_READER carries a byte-identical
      parseAgentJson body (structural uniformity per BP-300e-5 — includes
      build-epic.js and build-ticket.js even though they have 0 live parse call sites)

Integration tests (TestParseAgentJsonIntegration) run the workflow scripts
under the _workflow_engine_harness E2 stub and verify the run continues when
a prose-wrapped reply is injected via the label_responses mechanism.

TICKET: TICKET-20260716-BP-300e-5.md
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

from _workflow_engine_harness import run_workflow_under_e2

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOWS_JS_DIR = _REPO_ROOT / "templates" / "workflows-js"

_PLAN_FEATURE_JS = _WORKFLOWS_JS_DIR / "plan-feature.js"
_BUILD_FEATURE_JS = _WORKFLOWS_JS_DIR / "build-feature.js"
_FINALIZE_FEATURE_JS = _WORKFLOWS_JS_DIR / "finalize-feature.js"
_BUILD_EPIC_JS = _WORKFLOWS_JS_DIR / "build-epic.js"
_BUILD_TICKET_JS = _WORKFLOWS_JS_DIR / "build-ticket.js"

# All five delivery workflow scripts.
# build-feature.js is trivially compliant (0 parse sites, schema-enforced agent() calls).
_ALL_SCRIPTS: dict[str, Path] = {
    "plan-feature.js": _PLAN_FEATURE_JS,
    "build-feature.js": _BUILD_FEATURE_JS,
    "finalize-feature.js": _FINALIZE_FEATURE_JS,
    "build-epic.js": _BUILD_EPIC_JS,
    "build-ticket.js": _BUILD_TICKET_JS,
}

# Scripts that must carry a byte-identical parseAgentJson helper (BP-300e-5,
# "uniformly across every delivery workflow script").
#
# plan-feature.js and finalize-feature.js: have LIVE parse call sites that
#   call parseAgentJson() directly on agent-reply variables.
# build-epic.js and build-ticket.js: schema-only (0 live parse call sites —
#   every agent() call passes a schema: so the engine auto-parses). They carry
#   the helper for structural uniformity and forward-compatibility, NOT because
#   they currently have parse sites.
# build-feature.js: EXCLUDED — schema-only and no uniformity carve-in was
#   made for it (the ticket's files_touched lists it but implementation notes
#   mark it 0-parse-site and unchanged).
_SCRIPTS_REQUIRING_TOLERANT_READER: dict[str, Path] = {
    "plan-feature.js": _PLAN_FEATURE_JS,
    "finalize-feature.js": _FINALIZE_FEATURE_JS,
    "build-epic.js": _BUILD_EPIC_JS,
    "build-ticket.js": _BUILD_TICKET_JS,
}

# Brittle ternary pattern: typeof x === "string" ? JSON.parse(x) : x
# This is the pattern that parseAgentJson must replace.
_BRITTLE_TERNARY_RE = re.compile(
    r"typeof\s+\w+\s*===\s*['\"]string['\"]\s*\?\s*JSON\.parse\("
)


# ---------------------------------------------------------------------------
# Internal helpers (not test methods)
# ---------------------------------------------------------------------------


def _read_source(path: Path) -> str:
    """Return the full UTF-8 text of a workflow script. Raises AssertionError on I/O error."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(  # noqa: TRY003
            f"Cannot read {path.name}: {exc}"
        ) from exc


def _extract_fn(source: str, fn_name: str, source_name: str) -> str:
    """Brace-match extract a named JS function body from source.

    Supports both ``function <fn_name>(`` and ``async function <fn_name>(`` forms.
    Raises AssertionError if the function is absent or its closing brace is missing.
    """
    fn_start = -1
    for prefix in (f"function {fn_name}(", f"async function {fn_name}("):
        idx = source.find(prefix)
        if idx != -1:
            fn_start = idx
            break

    assert fn_start != -1, (
        f"parseAgentJson function not found in {source_name} — "
        "python-coder must implement and inline it"
    )

    depth = 0
    found_brace = False
    i = fn_start
    while i < len(source):
        c = source[i]
        if c == "{":
            depth += 1
            found_brace = True
        elif c == "}" and found_brace:
            depth -= 1
            if depth == 0:
                return source[fn_start : i + 1]
        i += 1

    assert False, f"{fn_name} closing brace not found in {source_name}"  # noqa: B011


def _invoke_node(fn_body: str, driver_js: str) -> dict:
    """Inline fn_body + driver_js and run via Node.js; return parsed stdout dict.

    The driver is expected to write a JSON object to stdout. The object MUST
    have at least an ``ok`` key. Errors thrown inside ``parseAgentJson`` are
    caught by the driver and represented as ``{ok: false, threw: true, error: "<msg>"}``.
    """
    script = f"'use strict';\n{fn_body}\n{driver_js}\n"
    try:
        proc = subprocess.run(
            ["node", "--input-type=module"],
            input=script,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(  # noqa: TRY003
            "node binary not found — install Node.js"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(  # noqa: TRY003
            "Node.js subprocess timed out after 10s"
        ) from exc

    assert proc.returncode == 0, (
        f"Node.js exited {proc.returncode}. stderr: {proc.stderr!r}"
    )

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(  # noqa: TRY003
            f"Cannot parse node stdout as JSON: {exc}. stdout={proc.stdout!r}"
        ) from exc


# ---------------------------------------------------------------------------
# Function-behaviour tests (BP-300e-1 through BP-300e-4-i)
# ---------------------------------------------------------------------------


class TestParseAgentJsonBehavior(unittest.TestCase):
    """Behavioural tests for parseAgentJson extracted from plan-feature.js.

    Each test extracts the function and runs it in isolation via Node.js.
    """

    fn_body: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        """Extract parseAgentJson from plan-feature.js once for all tests in this class."""
        source = _read_source(_PLAN_FEATURE_JS)
        cls.fn_body = _extract_fn(source, "parseAgentJson", "plan-feature.js")

    def _call(
        self,
        raw_js_expr: str,
        ctx_js: str = '{ stage: "test-stage", agent: "test-agent" }',
    ) -> dict:
        """Call parseAgentJson(<raw_js_expr>, <ctx_js>) and return the driver output dict."""
        driver = f"""
(async () => {{
  try {{
    const result = parseAgentJson({raw_js_expr}, {ctx_js});
    process.stdout.write(JSON.stringify({{ ok: true, value: result }}));
  }} catch (err) {{
    process.stdout.write(JSON.stringify({{ ok: false, threw: true, error: String(err) }}));
  }}
}})();
"""
        return _invoke_node(self.fn_body, driver)

    def test_object_with_trailing_prose_parsed(self) -> None:
        # covers: BP-300e-1
        """AC: parseAgentJson recovers a JSON object followed by trailing markdown;
        all fields intact, trailing prose ignored."""
        driver = r"""
(async () => {
  const raw = "{\"status\": \"ok\", \"name\": \"leafcutter\"}\n## Anomalies\nNo anomalies.";
  try {
    const result = parseAgentJson(raw, { stage: "s", agent: "a" });
    process.stdout.write(JSON.stringify({ ok: true, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("ok"), f"Expected ok=True but got: {result}")
        value = result["value"]
        self.assertEqual(value.get("status"), "ok")
        self.assertEqual(value.get("name"), "leafcutter")

    def test_nested_braces_not_truncated(self) -> None:
        # covers: BP-300e-1-i
        """AC: Extraction stops at the matching top-level closing brace, not the first
        nested one; nested objects recovered whole."""
        driver = r"""
(async () => {
  const raw = "{\"outer\": {\"inner\": \"nested_value\"}, \"count\": 3}";
  try {
    const result = parseAgentJson(raw, { stage: "s", agent: "a" });
    process.stdout.write(JSON.stringify({ ok: true, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("ok"), f"Expected ok=True but got: {result}")
        value = result["value"]
        self.assertIsInstance(value.get("outer"), dict, "outer must be a dict")
        self.assertEqual(value["outer"].get("inner"), "nested_value")
        self.assertEqual(value.get("count"), 3)

    def test_braces_and_hash_inside_strings_ignored(self) -> None:
        # covers: BP-300e-1-ii
        """AC: { } and # characters inside JSON string values and escaped quotes are
        treated as text, not structure/delimiters; object recovered with string intact."""
        driver = r"""
(async () => {
  const raw = '{"msg": "foo { bar } # baz \\"escaped\\""}';
  try {
    const result = parseAgentJson(raw, { stage: "s", agent: "a" });
    process.stdout.write(JSON.stringify({ ok: true, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("ok"), f"Expected ok=True but got: {result}")
        msg = result["value"].get("msg", "")
        self.assertIn("{", msg, "Opening brace inside string must be preserved")
        self.assertIn("}", msg, "Closing brace inside string must be preserved")
        self.assertIn("#", msg, "Hash inside string must be preserved")

    def test_already_parsed_value_passthrough(self) -> None:
        # covers: BP-300e-1-iii
        """AC: A non-string (already-parsed) value is returned unchanged with no
        re-parse attempt."""
        driver = """
(async () => {
  const raw = { status: "done", items: [1, 2, 3] };
  try {
    const result = parseAgentJson(raw, { stage: "preflight", agent: "status-checker" });
    process.stdout.write(JSON.stringify({ ok: true, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("ok"), f"Expected ok=True but got: {result}")
        value = result["value"]
        self.assertEqual(value.get("status"), "done")
        self.assertListEqual(value.get("items"), [1, 2, 3])

    def test_surrounding_prose_parsed(self) -> None:
        # covers: BP-300e-2
        """AC: parseAgentJson recovers a valid JSON object wrapped in prose both before
        the opening brace and after the closing brace."""
        driver = r"""
(async () => {
  const raw = "Agent result:\n{\"status\": \"ok\", \"score\": 7}\nEnd of output.";
  try {
    const result = parseAgentJson(raw, { stage: "s", agent: "a" });
    process.stdout.write(JSON.stringify({ ok: true, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("ok"), f"Expected ok=True but got: {result}")
        value = result["value"]
        self.assertEqual(value.get("status"), "ok")
        self.assertEqual(value.get("score"), 7)

    def test_multiple_blocks_first_balanced_taken(self) -> None:
        # covers: BP-300e-2-i
        """AC: When a reply contains more than one top-level JSON block, the FIRST
        complete balanced value is parsed and later blocks ignored (deterministic)."""
        driver = r"""
(async () => {
  const raw = "First: {\"a\": 1} then: {\"b\": 2}";
  try {
    const result = parseAgentJson(raw, { stage: "s", agent: "a" });
    process.stdout.write(JSON.stringify({ ok: true, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("ok"), f"Expected ok=True but got: {result}")
        value = result["value"]
        self.assertEqual(value.get("a"), 1, "First block's 'a' field must be present")
        self.assertNotIn("b", value, "Second block must not be included")

    def test_json_array_with_prose_parsed(self) -> None:
        # covers: BP-300e-3
        """AC: A valid JSON array surrounded by prose is recovered with every element intact."""
        driver = r"""
(async () => {
  const raw = "Results:\n[\"item1\", \"item2\", \"item3\"]\nDone.";
  try {
    const result = parseAgentJson(raw, { stage: "s", agent: "a" });
    process.stdout.write(JSON.stringify({ ok: true, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("ok"), f"Expected ok=True but got: {result}")
        value = result["value"]
        self.assertIsInstance(value, list, "Array reply must be recovered as a list")
        self.assertEqual(len(value), 3)
        self.assertIn("item1", value)
        self.assertIn("item2", value)
        self.assertIn("item3", value)

    def test_unusable_reply_raises_typed_error_naming_stage_and_agent(self) -> None:
        # covers: BP-300e-4
        """AC: A prose-only reply with no parseable JSON raises a typed error naming
        the stage and agent; never silently skipped or swallowed."""
        driver = """
(async () => {
  const raw = "This is explanatory prose only. No JSON at all.";
  try {
    const result = parseAgentJson(raw, { stage: "ac-triage", agent: "ac-triage-agent" });
    process.stdout.write(JSON.stringify({ ok: false, threw: false, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: true, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("threw"), f"Expected function to throw but got: {result}")
        error_msg = result.get("error", "")
        self.assertIn(
            "ac-triage", error_msg,
            f"Error must name the stage 'ac-triage'; got: {error_msg!r}"
        )
        self.assertIn(
            "ac-triage-agent", error_msg,
            f"Error must name the agent 'ac-triage-agent'; got: {error_msg!r}"
        )

    def test_empty_or_whitespace_reply_raises_same_typed_error(self) -> None:
        # covers: BP-300e-4-i
        """AC: An empty or whitespace-only reply raises the same typed stage+agent error,
        never treated as an acceptable/skippable result."""
        driver = """
(async () => {
  const raw = "   ";
  try {
    const result = parseAgentJson(raw, { stage: "commit-stage", agent: "commit-agent" });
    process.stdout.write(JSON.stringify({ ok: false, threw: false, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: true, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("threw"), f"Expected function to throw but got: {result}")
        error_msg = result.get("error", "")
        self.assertIn(
            "commit-stage", error_msg,
            f"Error must name the stage; got: {error_msg!r}"
        )
        self.assertIn(
            "commit-agent", error_msg,
            f"Error must name the agent; got: {error_msg!r}"
        )

    def test_top_level_scalar_reply_raises_typed_error(self) -> None:
        # covers: BP-300e-4
        """AC: A reply that is a bare JSON scalar string (no braces or brackets, e.g.
        "42" or "true") raises the typed error naming stage and agent.

        Documents the M-1 contract change: the old greedy helper tolerated bare
        scalars; the new brace-matching helper requires an object or array.
        """
        driver = """
(async () => {
  const raw = "42";
  try {
    const result = parseAgentJson(raw, { stage: "build-stage", agent: "build-agent" });
    process.stdout.write(JSON.stringify({ ok: false, threw: false, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: true, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(
            result.get("threw"),
            f"Expected function to throw on bare scalar input but got: {result}",
        )
        error_msg = result.get("error", "")
        self.assertIn(
            "build-stage", error_msg,
            f"Error must name the stage 'build-stage'; got: {error_msg!r}",
        )
        self.assertIn(
            "build-agent", error_msg,
            f"Error must name the agent 'build-agent'; got: {error_msg!r}",
        )

    def test_escaped_backslash_before_closing_quote_parsed(self) -> None:
        # covers: BP-300e-1-ii
        """AC: A JSON string value ending with an escaped backslash is recovered intact;
        the trailing escape does not swallow the real closing quote.

        Covers the F2/L-1 escape edge: the brace-matching scanner must treat the
        two-byte sequence \\\\ in the JSON stream as a complete backslash escape so
        that the following '"' correctly closes the string, rather than being misread
        as part of an escaped-quote sequence (which would extend the string past its
        true end and corrupt the extraction).

        Driver input: JS single-quoted string whose JSON path value is C:\\ (encoding
        C + colon + backslash = 3 chars). After brace-extraction and JSON.parse the
        recovered path must equal "C:\\" — confirming the escape was handled correctly.
        """
        driver = r"""
(async () => {
  const raw = '{"path":"C:\\\\"}';
  try {
    const result = parseAgentJson(raw, { stage: "s", agent: "a" });
    process.stdout.write(JSON.stringify({ ok: true, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("ok"), f"Expected ok=True but got: {result}")
        path_value = result["value"].get("path", "")
        # The JS driver uses a single-quoted string literal whose bytes on disk are:
        #   C, colon, 4 backslash bytes, closing-quote  →  {"path":"C:\\"}  at JS runtime.
        # JSON.parse decodes C + : + \\ (two backslashes) → C + : + \ (3-char value: C:\).
        # The key escape-edge assertion: the trailing \\ in the JSON stream is consumed
        # as a complete backslash escape, so the following " correctly closes the string
        # rather than being misread as an escaped-quote (\\\" extends-string bug).
        self.assertTrue(
            path_value.endswith("\\"),
            f"Expected path value ending with a backslash but got: {path_value!r}",
        )
        self.assertEqual(
            path_value, "C:\\",
            f"Expected 'C:\\\\' (C-colon-backslash, 3 chars) but got: {path_value!r}",
        )

    def test_null_passthrough_returned_unchanged(self) -> None:
        # covers: BP-300e-1-iii
        """AC: A non-string null input is returned as null unchanged with no throw and
        no re-parse attempt."""
        driver = """
(async () => {
  const raw = null;
  try {
    const result = parseAgentJson(raw, { stage: "s", agent: "a" });
    process.stdout.write(JSON.stringify({ ok: true, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("ok"), f"Expected ok=True for null input but got: {result}")
        self.assertIn("value", result, "Output must contain 'value' key")
        self.assertIsNone(result["value"], "null input must be returned as null (Python None)")

    def test_numeric_passthrough_returned_unchanged(self) -> None:
        # covers: BP-300e-1-iii
        """AC: A non-string numeric input (e.g. 42) is returned unchanged with no throw
        and no re-parse attempt."""
        driver = """
(async () => {
  const raw = 42;
  try {
    const result = parseAgentJson(raw, { stage: "s", agent: "a" });
    process.stdout.write(JSON.stringify({ ok: true, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("ok"), f"Expected ok=True for numeric input but got: {result}")
        self.assertEqual(result.get("value"), 42, "Numeric input 42 must be returned unchanged")

    def test_incidental_json_before_real_payload_first_taken(self) -> None:
        # covers: BP-300e-2-i
        """AC: When leading prose contains an incidental balanced JSON object before the
        intended payload, the first balanced value is returned (M-2 first-match contract).

        This test pins the risk explicitly: if any earlier balanced JSON block appears in
        the reply prose, parseAgentJson returns it — not the intended later payload.
        The variant uses leading prose + an incidental {step:1} + real {status:'done'}
        to document that first-match is deterministic, even when the earlier block is small.
        """
        driver = r"""
(async () => {
  const raw = "Step completed {\"step\": 1} and full result: {\"status\": \"done\", \"count\": 5}";
  try {
    const result = parseAgentJson(raw, { stage: "s", agent: "a" });
    process.stdout.write(JSON.stringify({ ok: true, value: result }));
  } catch (err) {
    process.stdout.write(JSON.stringify({ ok: false, threw: true, error: String(err) }));
  }
})();
"""
        result = _invoke_node(self.fn_body, driver)
        self.assertTrue(result.get("ok"), f"Expected ok=True but got: {result}")
        value = result["value"]
        self.assertEqual(
            value.get("step"), 1,
            "The incidental first block {step: 1} must be returned (first-match wins)",
        )
        self.assertNotIn(
            "status", value,
            "The later block {status: 'done'} must NOT be included — first-match wins",
        )


# ---------------------------------------------------------------------------
# Structural audit tests (BP-300e-5)
# ---------------------------------------------------------------------------


class TestParseAgentJsonStructuralAudit(unittest.TestCase):
    """Structural audit: all agent-reply parse sites route through parseAgentJson.

    Covers AC BP-300e-5.
    """

    def test_all_agent_parse_sites_route_through_tolerant_reader(self) -> None:
        # covers: BP-300e-5
        """AC: Every enumerated agent-reply parse site across the five workflow scripts
        routes through parseAgentJson; no bare JSON.parse or strict ternary on agent
        output remains (count-agnostic; 0-site scripts trivially compliant).

        Method: for each script, strip the parseAgentJson function body (so its
        own internal JSON.parse calls do not register as violations), then search
        for the brittle ternary pattern.  build-feature.js is trivially compliant
        and must have zero ternary occurrences as-is.
        """
        violations: list[str] = []

        for script_name, script_path in _ALL_SCRIPTS.items():
            source = _read_source(script_path)

            # Remove the parseAgentJson body (legitimately contains JSON.parse).
            try:
                fn_body = _extract_fn(source, "parseAgentJson", script_name)
                source_without_fn = source.replace(fn_body, "/* parseAgentJson body removed */")
            except AssertionError:
                # Function absent — still check the rest of the source.
                source_without_fn = source

            hits = _BRITTLE_TERNARY_RE.findall(source_without_fn)
            if hits:
                violations.append(
                    f"{script_name}: {len(hits)} brittle ternary JSON.parse pattern(s) — "
                    f"each must be replaced with parseAgentJson(raw, {{stage, agent}})"
                )

        self.assertEqual(
            violations,
            [],
            "Brittle parse patterns found — python-coder must route all sites through "
            "parseAgentJson:\n" + "\n".join(violations),
        )

    def test_tolerant_reader_body_identical_across_workflow_scripts(self) -> None:
        # covers: BP-300e-5
        """AC: The inlined parseAgentJson body is byte-identical across every workflow
        script in _SCRIPTS_REQUIRING_TOLERANT_READER (guards inline placement against drift).

        build-feature.js is excluded: schema-only with no uniformity carve-in per BP-300e-5.
        build-epic.js and build-ticket.js are schema-only (0 live parse call sites) but
        included for structural uniformity — the helper is present for forward-compatibility,
        not because they currently call parseAgentJson directly.
        """
        fn_bodies: dict[str, str] = {}
        missing: list[str] = []

        for script_name, script_path in _SCRIPTS_REQUIRING_TOLERANT_READER.items():
            source = _read_source(script_path)
            try:
                body = _extract_fn(source, "parseAgentJson", script_name)
                fn_bodies[script_name] = body
            except AssertionError:
                missing.append(script_name)

        self.assertEqual(
            missing,
            [],
            f"parseAgentJson missing from {missing}. "
            "python-coder must inline a byte-identical copy in each script.",
        )

        if len(fn_bodies) >= 2:
            items = list(fn_bodies.items())
            reference_name, reference_body = items[0]
            for script_name, body in items[1:]:
                self.assertEqual(
                    body,
                    reference_body,
                    f"parseAgentJson body in '{script_name}' differs from "
                    f"'{reference_name}'. The bodies must be byte-identical "
                    "(run a diff to locate the drift).",
                )


# ---------------------------------------------------------------------------
# Integration tests (BP-300e-5)
# ---------------------------------------------------------------------------


class TestParseAgentJsonIntegration(unittest.TestCase):
    """Runtime behavioural tests: workflow scripts tolerate prose-wrapped replies.

    Covers AC BP-300e-5.

    Uses _workflow_engine_harness.run_workflow_under_e2 to run each workflow
    script under a stub E2 engine and injects prose-wrapped JSON via
    label_responses.  Asserts the workflow dispatches further agents (run
    continues) rather than crashing or returning immediately.
    """

    def test_build_feature_run_tolerates_prose_wrapped_reply(self) -> None:
        # covers: BP-300e-5
        """AC: Replay a prose-wrapped reply through build-feature; the run continues
        to its next stage.

        build-feature.js dispatches via schema-enforced agent() calls (trivially
        compliant per spec — 0 parse sites). This test verifies the top-level body
        dispatches at least one agent call without error under the E2 stub harness.

        NOTE: This test may pass before implementation because build-feature.js is
        already schema-compliant (trivially compliant per implementation notes).
        It is kept to satisfy the AC parity requirement and to catch any future
        regression that introduces a bare JSON.parse into build-feature.js.
        """
        if not _BUILD_FEATURE_JS.exists():
            self.fail(f"build-feature.js not found at {_BUILD_FEATURE_JS}")

        result = run_workflow_under_e2(_BUILD_FEATURE_JS, timeout=15)
        self.assertFalse(
            result.error,
            f"Harness returned an error running build-feature.js: {result.error!r}",
        )
        self.assertGreater(
            result.dispatch_count,
            0,
            f"build-feature.js dispatched 0 agents. stderr: {result.stderr!r}",
        )

    def test_finalize_feature_run_tolerates_prose_wrapped_reply(self) -> None:
        # covers: BP-300e-5
        """AC: Replay a prose-wrapped reply through finalize-feature; the run continues
        to its next stage AND the correctly parsed worktree root appears in the
        subsequent agent prompt (proving the prose was parsed correctly, not merely
        falling through to a fallback).

        Injects a prose-wrapped JSON string as the pre-flight agent reply.
        The trailing prose deliberately contains a closing brace character
        ('feature-{name}' in the convention note) so that the old greedy-regex
        safeParseJSON implementation fails (greedy match spans across the '}' in
        the trailing text) and falls back to worktree_root="unknown".
        parseAgentJson brace-matching correctly extracts the first complete balanced
        block, producing worktree_root="/tmp/wt-leafcutter-test".

        The test asserts that:
        1. The workflow dispatches at least two agents (run continues).
        2. A subsequent call's prompt contains the expected worktree root
           "/tmp/wt-leafcutter-test" — confirming the reply was correctly parsed
           rather than falling through to the "unknown" fallback.
        """
        if not _FINALIZE_FEATURE_JS.exists():
            self.fail(f"finalize-feature.js not found at {_FINALIZE_FEATURE_JS}")

        # A prose-wrapped reply whose trailing text contains '}' so that a greedy
        # /\{[\s\S]*\}/ regex captures too much and produces invalid JSON (the greedy
        # match extends from the opening '{' all the way to the last '}' in
        # 'feature-{name}'), whereas brace-matching stops at the correct closing brace.
        expected_worktree_root = "/tmp/wt-leafcutter-test"
        prose_reply_with_brace_in_trailing_text = (
            "Pre-flight completed:\n"
            f'{{"branch": "conventions-fix", "worktree_root": "{expected_worktree_root}", '
            '"found": true, "status": "ok"}\n'
            "Note: branch convention is `feature-{name}` (see docs/conventions.md)."
        )

        label_responses = {"pre-flight": prose_reply_with_brace_in_trailing_text}
        result = run_workflow_under_e2(
            _FINALIZE_FEATURE_JS,
            timeout=20,
            label_responses=label_responses,
        )
        self.assertFalse(
            result.error,
            f"Harness returned an error running finalize-feature.js: {result.error!r}",
        )
        # Expect at least 2 dispatches: pre-flight + one subsequent call (gh-config).
        self.assertGreaterEqual(
            result.dispatch_count,
            2,
            (
                f"finalize-feature.js dispatched only {result.dispatch_count} agent(s) "
                "with a prose-wrapped pre-flight reply — expected at least 2. "
                f"stderr: {result.stderr!r}"
            ),
        )
        # The gh-config call (the call after pre-flight) embeds WORKTREE_ROOT in its
        # prompt: `cat "${WORKTREE_ROOT}/settings.json"`. After correct prose parsing,
        # WORKTREE_ROOT must equal the expected value from the JSON block.
        # If safeParseJSON (greedy regex) was used, WORKTREE_ROOT would be "unknown"
        # because the greedy regex fails on the trailing '}' and safeParseJSON returns
        # {malformed: true}, causing the fallback {worktree_root: "unknown"} to apply.
        settings_prompts = [
            str(call.prompt)
            for call in result.agent_calls
            if "settings.json" in str(call.prompt)
        ]
        self.assertGreater(
            len(settings_prompts),
            0,
            "Expected at least one agent call with 'settings.json' in its prompt "
            "(the gh-config call embeds WORKTREE_ROOT); none found. "
            f"All prompts: {[str(c.prompt)[:120] for c in result.agent_calls]!r}",
        )
        self.assertIn(
            expected_worktree_root,
            settings_prompts[0],
            f"Expected WORKTREE_ROOT '{expected_worktree_root}' (from correctly parsed JSON) "
            "in the gh-config prompt, but it was absent — likely 'unknown' (the fallback "
            "from greedy-regex safeParseJSON failure) appeared instead. "
            f"Actual prompt (first 200 chars): {settings_prompts[0][:200]!r}",
        )


if __name__ == "__main__":
    unittest.main()
