"""
MODULE: test_bo2400c1iii_reference_and_incomplete_states
GOAL: RED behavioral tests for BO-2400c-1-iii's 2026-08-25 amendment — the
    FOUR-state classification of the context-bundle-assembling dispatch's
    reply (USABLE / NOT_OBTAINED / OBTAINED_BUT_A_REFERENCE /
    OBTAINED_BUT_INCOMPLETE) and the requirement that each of the three
    failure states halts with a message naming ONLY that state.

SCOPE — JAVASCRIPT HALF ONLY, per BO-2400c-1-iii.yaml's it_requirements
    constraint list. The three edit sites are all inside
    templates/workflows-js/fast-lane-ship.js: (1) the bundle-assembling
    dispatch prompt (~lines 654-684, where the size expectation belongs),
    (2) the usability gate (~lines 694-702, where the classification is
    computed), (3) the halt payload (~lines 704-731, where exactly one of
    the three failure states must be named). NOTHING in
    scripts/injection_builders.py is touched or asserted against here —
    shrinking the bundle is the separate record BO-2400c-1-vi.

WHY A NEW FILE RATHER THAN EXTENDING test_bo2400c_prompt_cache_wiring.py:
    That sibling file already covers (and, as verified below, already
    PASSES) the pre-amendment two-state model: a well-formed bundle reaches
    both dispatches verbatim (USABLE), and an unobtainable bundle
    ({}/None/obtained:false) halts without dispatching test-writer or coder.
    Verified by running that file directly before authoring this one — all
    14 of its tests pass against the CURRENT fast-lane-ship.js. Duplicating
    those assertions here would add no red signal. This file targets
    EXCLUSIVELY the amendment's delta: the reply shape that is truthy
    `obtained` but is a REFERENCE rather than content (KI-BO-019 — the
    literal production failure on run wf_bd4984e8-438, where a 141,933-byte
    bundle was assembled perfectly and the lane still halted saying "the
    context bundle was not obtained"), the reply shape that is real content
    but INCOMPLETE (marker absent or a layer empty), and the requirement
    that the three failure messages are pairwise distinguishable rather
    than one undifferentiated string that happens to satisfy every check.

    Confirmed by reading the current implementation
    (templates/workflows-js/fast-lane-ship.js:694-731): `contextBundleUsable`
    is a single boolean folding "obtained falsy", "bundle empty", and
    "marker absent" into ONE branch, and the halt message is the same
    string regardless of which of those was true, and never distinguishes
    "obtained truthy but the value is a locator" from "obtained falsy" at
    all. Every reference-classification assertion below is RED against that
    code today for that reason.

=== Verify Behaviorally, Not by Grep (root CLAUDE.md) ===
Every test below EXECUTES the real, on-disk fast-lane-ship.js under
unit_tests/_workflow_engine_harness.py's run_workflow_under_e2() with a
stubbed "fastlane-context-bundle" reply, and asserts on the RECORDED,
EXECUTED agent_calls (proving the gate is reached and either dispatches or
refuses to dispatch test-writer/coder) and on HarnessResult.result (the
run's terminal payload) — never on fast-lane-ship.js source text. This
feature's own history (KI-BO-005, KI-BO-006, and the grep test at
unit_tests/workflows/test_bo2400a_runner_wiring.py:401 that kept a dead
reference looking alive for a month) is why a grep-shaped test is
unacceptable evidence here.

=== Source-of-Truth Discipline Rule 3 (cross-layer seam) ===
This is the mandated cross-layer seam test for the amendment: the producer
is the bundle-assembling dispatch reply (stubbed to the exact shapes a real
agent has been observed to return), the consumer is the usability gate plus
the halt-payload construction inside fast-lane-ship.js. A unit test of
either half in isolation could not prove the LANE reads `obtained`,
`bundle`, `bytes`, and `location` off the same reply object and threads
them into one mutually-exclusive classification — which is exactly what
KI-BO-019 shows was missing.

=== Real-Artifact Behavioral Test Mandate — does not apply here ===
BO-2400c-1-iii.yaml declares `declares_side_effect: false`. fast-lane-ship.js
is an E2 workflow script with no direct filesystem access (ADR-024) — every
observable here is an LLM agent dispatch the harness mocks, exactly as
already documented in test_bo2400c_prompt_cache_wiring.py's own module
docstring for this same file. There is no durable on-disk artifact for this
record's three edit sites to round-trip.

=== Fixture-authenticity note ===
The INCOMPLETE-state bundles are constructed by calling the REAL
`assemble_context_bundle()` pure function (never a hand-typed re-
implementation of its layering rule) with a deliberately wrong marker or an
empty layer argument — so the fixture is genuinely "content, not a
locator," exactly as the AC requires the gate to distinguish. The
REFERENCE-state and NOT_OBTAINED-state fixtures are hand-authored strings by
necessity: they represent exactly what a dispatched AGENT is observed to
return, which cannot come from a pure function. The truncated-preview
fixture is a close reproduction of the literal reply text quoted in this
record's own amendment note and in the ticket dispatching this test file
(run wf_bd4984e8-438 / a 141,933-byte real run), not an invented shape.

=== The escaped-marker subtlety ===
`_ESCAPED_MARKER_MENTION_BUNDLE` below contains the HTML-escaped mention
"&lt;!-- CACHE_BREAKPOINT --&gt;" while discussing itself — it does NOT
contain the raw literal "<!-- CACHE_BREAKPOINT -->" substring (verified by
an assertion in this module at import time). This pins the it_requirements
enrichment note "reference-rejection must be evaluated BEFORE the
breakpoint-marker check" — the ordering matters because a future
unescape-then-marker-check "fix" for the primary regression could
accidentally treat a mere MENTION of the marker inside a rejected preview as
satisfying the marker check, which would only be caught by evaluating
reference-rejection first. This bundle is a reference regardless of what it
says about the marker, and must be refused as one.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make unit_tests/workflows/ and scripts/ importable regardless
# of cwd, mirroring the sibling file's own convention.
# ---------------------------------------------------------------------------
_WORKFLOWS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _WORKFLOWS_DIR.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_WORKFLOWS_DIR) not in sys.path:
    sys.path.insert(0, str(_WORKFLOWS_DIR))
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Reuse the sibling file's harness plumbing (_GREEN_LABELS, _run_ship,
# _call, _labels_ship, _BUNDLE_LABEL, _DEFAULT_MARKER) rather than
# duplicating its ~80-key green-baseline label_responses fixture inline
# (Fixture Extraction Rule, §2h) — this file only overrides the one label
# ("fastlane-context-bundle") its assertions are about.
import test_bo2400c_prompt_cache_wiring as _sibling  # noqa: E402
from injection_builders import assemble_context_bundle  # noqa: E402

# ===========================================================================
# Fixtures
# ===========================================================================

_STABLE_ARCH = "STABLE_ARCH_FOR_BO2400C1III_STATE_TESTS"
_STABLE_CONV = "STABLE_CONV_FOR_BO2400C1III_STATE_TESTS"
_STABLE_HL = "STABLE_HL_FOR_BO2400C1III_STATE_TESTS"
_VOLATILE_ACS = "VOLATILE_ACS_FOR_BO2400C1III_STATE_TESTS"
_VOLATILE_PRIOR_TESTS = "VOLATILE_PRIOR_TESTS_FOR_BO2400C1III_STATE_TESTS"

# --- OBTAINED_BUT_INCOMPLETE fixtures — real content via the real pure
#     function, never a hand-typed re-implementation of its layering rule. ---

# Missing-marker: assembled with a WRONG breakpoint marker, so the literal
# "<!-- CACHE_BREAKPOINT -->" the lane checks for is genuinely absent from
# real, well-formed content (not merely truncated or corrupted).
_INCOMPLETE_MISSING_MARKER_BUNDLE = assemble_context_bundle(
    architecture=_STABLE_ARCH,
    conventions=_STABLE_CONV,
    high_level=_STABLE_HL,
    acs=_VOLATILE_ACS,
    prior_tests=_VOLATILE_PRIOR_TESTS,
    breakpoint_marker="///NOT-THE-REAL-BREAKPOINT-MARKER///",
)

# Empty-layer: assembled with the REAL default marker present exactly once,
# but the "acs" layer is an empty string — a real, distinguishable defect
# distinct from a missing marker.
_INCOMPLETE_EMPTY_LAYER_BUNDLE = assemble_context_bundle(
    architecture=_STABLE_ARCH,
    conventions=_STABLE_CONV,
    high_level=_STABLE_HL,
    acs="",
    prior_tests=_VOLATILE_PRIOR_TESTS,
)

# --- OBTAINED_BUT_A_REFERENCE fixtures — hand-authored, because they
#     represent what a dispatched AGENT is observed to return, which a pure
#     assembly function cannot produce. ---

# The exact locator literal named in BO-2400c-1-iii.yaml's amended_by note
# and its own it_requirements constraint: "The observed failure value was
# exactly 'file:/tmp/bo2400f13-bundle/bundle_output.txt'."
_OBSERVED_FILE_URI = "file:/tmp/bo2400f13-bundle/bundle_output.txt"
_OBSERVED_FILE_URI_BYTES = 148891
_OBSERVED_FILE_URI_LOCATION = "/tmp/bo2400f13-bundle/bundle_output.txt"

# Scheme-agnostic variant: no "file:" prefix, just a leading '/', AND it
# additionally contains the raw breakpoint marker substring — pinning that
# reference-rejection is evaluated BEFORE (and independently of) the marker
# check, per the it-po enrichment note ("evaluated after, a locator that
# happens to contain the marker substring is classified as incomplete
# content, and the two states collapse").
_BARE_PATH_WITH_MARKER_SUBSTRING = (
    "/tmp/bo2400f13-bundle/bundle_output.txt " + _sibling._DEFAULT_MARKER
)
_BARE_PATH_BYTES = 148891
_BARE_PATH_LOCATION = "/tmp/bo2400f13-bundle/bundle_output.txt"

# The PRIMARY, load-bearing fixture: a close reproduction of the literal
# reply text observed on a real run that assembled a 141,933-byte bundle
# perfectly (exit 0, empty stderr, the marker present once at line 885 on
# disk) but returned a truncated preview + a path because the full text was
# too large to inline. This is NOT a bare locator string — it is prose that
# NAMES a location standing in for the content, which the AC's "any other
# locator standing in for the content" clause exists to catch.
_REAL_TRUNCATED_PREVIEW_BUNDLE = (
    '---\ntitle: "Build Orchestration fast-lane context bundle"\n'
    "[... full 141,933-byte / 1,971-line assembled bundle written to "
    "/tmp/bo2400c1-bundle/stdout.txt via `python3 "
    ".../injection_builders.py assemble-bundle` (exit 0, empty stderr) ... "
    "retrieve it from /tmp/bo2400c1-bundle/stdout.txt if the full text is "
    "needed downstream rather than relying on this truncated preview.]"
)
_REAL_TRUNCATED_PREVIEW_MESSAGE = (
    "Bundle assembled successfully (141,933 bytes / 1,971 lines) ... "
    "on disk at /tmp/bo2400c1-bundle/stdout.txt ..."
)
_REAL_TRUNCATED_PREVIEW_BYTES = 141933
_REAL_TRUNCATED_PREVIEW_LOCATION = "/tmp/bo2400c1-bundle/stdout.txt"

# The escaped-marker-mention trap (see module docstring "escaped-marker
# subtlety" section). Deliberately similar to the primary fixture but adds a
# mention of the marker in HTML-escaped form.
_ESCAPED_MARKER_MENTION_BUNDLE = (
    '---\ntitle: "Build Orchestration fast-lane context bundle"\n'
    "[... 141,933-byte / 1,971-line assembled bundle written to "
    "/tmp/bo2400c1-bundle/stdout.txt ... The bundle contains the cache "
    "breakpoint marker (&lt;!-- CACHE_BREAKPOINT --&gt;) separating stable "
    "and volatile layers ... retrieve it from /tmp/bo2400c1-bundle/stdout.txt "
    "if the full text is needed downstream rather than relying on this "
    "truncated preview.]"
)
# Guard the fixture's own premise: the RAW marker must be genuinely absent —
# only its HTML-escaped mention is present. If this ever fails, the fixture
# itself is broken (it would accidentally satisfy the marker check for a
# reason unrelated to what this test targets).
assert _sibling._DEFAULT_MARKER not in _ESCAPED_MARKER_MENTION_BUNDLE, (
    "Fixture bug: _ESCAPED_MARKER_MENTION_BUNDLE must not contain the raw "
    "breakpoint marker literal — only its HTML-escaped mention. Fix the "
    "fixture text above."
)


def _reference_response(bundle_text: str, bytes_: int, location: str, message: str) -> dict:
    """Build a {obtained: true, bundle, bytes, location, message} reply shape
    matching BO-2400c-1-iii's config_schema_fragment for a reference reply.
    """
    return {
        "obtained": True,
        "bundle": bundle_text,
        "bytes": bytes_,
        "location": location,
        "message": message,
    }


# ===========================================================================
# State-distinguishing predicates — used to prove the three failure messages
# are mutually exclusive, not merely present (test_rationale's own warning:
# "asserting each in isolation lets one undifferentiated message pass all
# three").
# ===========================================================================


def _is_not_obtained_message(msg_lower: str) -> bool:
    return (
        "not obtained" in msg_lower
        or "never obtained" in msg_lower
        or "never arrived" in msg_lower
        or "nothing came back" in msg_lower
    )


def _is_reference_message(msg_lower: str) -> bool:
    mentions_success = "succeeded" in msg_lower or "success" in msg_lower
    mentions_refusal = (
        "cannot follow" in msg_lower
        or "cannot read a filesystem" in msg_lower
        or "cannot read the filesystem" in msg_lower
    )
    return mentions_success and mentions_refusal


def _is_incomplete_message(msg_lower: str) -> bool:
    return "incomplete" in msg_lower


def _payload_message(result) -> str:
    payload = result.result
    assert payload is not None, (
        f"Missing terminal payload. Labels: {_sibling._labels_ship(result)}"
    )
    return str(payload.get("message", ""))


def _assert_no_context_carrying_dispatch(result, variant_desc: str) -> None:
    labels = _sibling._labels_ship(result)
    assert "test-writer-connected" not in labels, (
        f"An unusable bundle ({variant_desc}) must not permit an unbundled "
        f"test-writer dispatch. Labels: {labels}"
    )
    assert "coder-connected" not in labels, (
        f"An unusable bundle ({variant_desc}) must not permit an unbundled "
        f"coder dispatch. Labels: {labels}"
    )


# ===========================================================================
# 1. Size expectation stated to the producer (weakest test in this file —
#    the one thing a grep could also see, per test_rationale — but the
#    prompt genuinely lacks this text today).
# ===========================================================================


def test_bundle_dispatch_prompt_states_size_expectation_and_return_as_text_ask():
    # covers: BO-2400c-1-iii
    """The RECORDED bundle-assembling dispatch's prompt states the
    roughly-twenty-kilobyte expectation and that the text itself (not a
    path to it) is the ask.

    RED today: fast-lane-ship.js's "fastlane-context-bundle" dispatch prompt
    (lines 654-677) contains no size expectation and no "as text, not a
    path" instruction at all — confirmed by grepping the source for
    "kilobyte", "20 kb", "as text", "return the text" (zero matches).
    """
    result = _sibling._run_ship()
    assert result.error == "", f"Harness error: {result.error}"

    bundle_call = _sibling._call(result, _sibling._BUNDLE_LABEL)
    assert bundle_call is not None, (
        f"Expected the bundle-assembling dispatch to execute. "
        f"Labels: {_sibling._labels_ship(result)}"
    )
    prompt = bundle_call.prompt
    assert isinstance(prompt, str), f"Bundle dispatch prompt must be a string. Got: {type(prompt)}"
    lower = prompt.lower()

    size_stated = bool(
        re.search(r"twenty[\s-]*kilobyte|20\s*kb\b|~?20,?000\s*byte", lower)
    )
    assert size_stated, (
        "The bundle-assembling dispatch's prompt must state the size "
        "expectation to the producer — roughly twenty kilobytes of text — "
        "per BO-2400c-1-iii's constraint 'STATE THE SIZE EXPECTATION TO "
        f"THE PRODUCER, IN THE DISPATCH PROMPT'. Prompt: {prompt!r}"
    )
    text_ask_stated = (
        "as text" in lower or "the text itself" in lower or "not a path" in lower
    )
    assert text_ask_stated, (
        "The prompt must plainly state that returning the text itself is "
        "the ask, not a path to it (this belt must be stated to the "
        f"producer, per the same constraint). Prompt: {prompt!r}"
    )


# ===========================================================================
# 2. OBTAINED_BUT_A_REFERENCE — the primary regression this amendment fixes.
# ===========================================================================


def test_file_uri_reply_is_classified_as_reference_not_not_obtained():
    # covers: BO-2400c-1-iii
    """The exact locator shape named in this AC's own amended_by note
    ({"obtained": true, "bundle": "file:/tmp/bo2400f13-bundle/bundle_output.txt"})
    halts as OBTAINED_BUT_A_REFERENCE: no context-carrying dispatch occurs,
    and the terminal message says the assembly SUCCEEDED, echoes the
    reported bytes and location, and says the lane cannot follow a
    reference because it cannot read a filesystem.

    RED today: `contextBundleUsable` is a single boolean with one shared
    halt message ("The context bundle was not obtained ..."). This reply
    has `obtained: true` but no breakpoint marker in a 47-character string,
    so it takes the SAME halt branch as a genuinely-absent bundle and gets
    the SAME "was not obtained" wording — exactly the defect this test
    pins closed.
    """
    bundle_response = _reference_response(
        _OBSERVED_FILE_URI,
        _OBSERVED_FILE_URI_BYTES,
        _OBSERVED_FILE_URI_LOCATION,
        "Bundle assembled successfully.",
    )
    result = _sibling._run_ship(bundle_response=bundle_response)
    assert result.error == "", f"Harness error: {result.error}"

    _assert_no_context_carrying_dispatch(result, "file: URI reference")

    msg = _payload_message(result)
    lower = msg.lower()
    normalized = lower.replace(",", "")

    assert "not obtained" not in lower and "never obtained" not in lower, (
        "A reply that reports a SUCCESSFUL assembly returning a reference "
        "must never be worded as 'not obtained' — that is the literal "
        "KI-BO-019 regression (run wf_bd4984e8-438) this amendment exists "
        f"to fix. Got message: {msg!r}"
    )
    assert _is_reference_message(lower), (
        "The halt message must say the assembly SUCCEEDED and that the "
        f"lane cannot follow a reference / cannot read a filesystem. Got: {msg!r}"
    )
    assert "148891" in normalized, (
        f"The halt message must echo the reported byte count (148891). Got: {msg!r}"
    )
    assert _OBSERVED_FILE_URI_LOCATION in msg, (
        f"The halt message must echo the reported location "
        f"({_OBSERVED_FILE_URI_LOCATION!r}). Got: {msg!r}"
    )

    payload = result.result
    assert payload.get("failing_phase") == "context-bundle", (
        f"Expected failing_phase == 'context-bundle'. Got: {payload.get('failing_phase')!r}"
    )
    assert payload.get("status") != "ok", f"Got: {payload}"


def test_bare_filesystem_path_with_marker_substring_is_still_classified_as_reference():
    # covers: BO-2400c-1-iii
    """A returned value that is an absolute path with NO URI scheme takes
    the same reference branch as the file: URI (the rule is not
    scheme-specific), and a locator that additionally contains the raw
    breakpoint marker substring is STILL classified as a reference, not as
    usable content — reference-rejection is evaluated before the marker
    check, or the two states collapse (it-po enrichment note).

    RED today: there is no reference branch at all, so this halts on the
    single generic "not obtained" message regardless of the marker
    substring being present in the string.
    """
    bundle_response = _reference_response(
        _BARE_PATH_WITH_MARKER_SUBSTRING,
        _BARE_PATH_BYTES,
        _BARE_PATH_LOCATION,
        "Bundle assembled successfully.",
    )
    result = _sibling._run_ship(bundle_response=bundle_response)
    assert result.error == "", f"Harness error: {result.error}"

    _assert_no_context_carrying_dispatch(
        result, "bare absolute path containing the marker substring"
    )

    msg = _payload_message(result)
    lower = msg.lower()
    assert not _is_incomplete_message(lower), (
        "A locator that happens to contain the marker substring must be "
        "classified as a REFERENCE, not as incomplete content — the two "
        "states collapse if the marker check runs before reference-"
        f"rejection. Got: {msg!r}"
    )
    assert _is_reference_message(lower), (
        f"Expected a reference-state halt message (succeeded + cannot "
        f"follow a reference). Got: {msg!r}"
    )
    assert "not obtained" not in lower, f"Got: {msg!r}"


def test_real_observed_truncated_preview_reply_classified_as_reference_not_not_obtained():
    # covers: BO-2400c-1-iii
    """LOAD-BEARING: a close reproduction of the literal reply text observed
    on a real run today (a 141,933-byte bundle assembled perfectly, exit 0,
    empty stderr, marker present once on disk) but returned to the lane as
    a truncated preview plus a path — because the full text was too large
    to inline. This must classify as OBTAINED_BUT_A_REFERENCE, echoing the
    reported size and location, and must NOT halt saying "not obtained".

    RED today: this reply has `obtained: true` and a non-empty `bundle`
    string, but that string does not contain the raw breakpoint marker
    (only prose describing the file), so `contextBundleUsable` is false and
    the run halts with "The context bundle was not obtained — the
    prompt-caching layer's assembling dispatch failed, returned nothing
    usable, or the bundle was empty or missing the cache breakpoint
    marker." — actively misleading, since the bundle was in fact assembled
    correctly. This is the exact wrong-state classification the amendment
    exists to close.
    """
    bundle_response = _reference_response(
        _REAL_TRUNCATED_PREVIEW_BUNDLE,
        _REAL_TRUNCATED_PREVIEW_BYTES,
        _REAL_TRUNCATED_PREVIEW_LOCATION,
        _REAL_TRUNCATED_PREVIEW_MESSAGE,
    )
    result = _sibling._run_ship(bundle_response=bundle_response)
    assert result.error == "", f"Harness error: {result.error}"

    _assert_no_context_carrying_dispatch(result, "real observed truncated-preview reply")

    msg = _payload_message(result)
    lower = msg.lower()
    normalized = lower.replace(",", "")

    assert "not obtained" not in lower and "never obtained" not in lower, (
        "This is the exact production failure (run wf_bd4984e8-438-shaped "
        "reply, a 141,933-byte bundle assembled successfully but returned "
        "as a truncated preview + path): the lane must NOT say the bundle "
        f"'was not obtained'. Got message: {msg!r}"
    )
    assert _is_reference_message(lower), (
        f"Expected the halt to say the assembly SUCCEEDED and that the "
        f"lane cannot follow a reference. Got: {msg!r}"
    )
    assert "141933" in normalized, (
        f"The halt message must echo the reported byte count (141933). Got: {msg!r}"
    )
    assert _REAL_TRUNCATED_PREVIEW_LOCATION in msg, (
        f"The halt message must echo the reported location "
        f"({_REAL_TRUNCATED_PREVIEW_LOCATION!r}). Got: {msg!r}"
    )


def test_reference_reply_that_merely_mentions_escaped_marker_is_still_refused():
    # covers: BO-2400c-1-iii
    """A preview that merely MENTIONS the breakpoint marker (in
    HTML-escaped form, discussing itself) while still fundamentally being a
    reference (it names a path standing in for the content) must be
    refused as a reference — not accidentally treated as usable because a
    naive unescape-then-marker-check implementation finds the substring.

    This pins the it-po enrichment note ordering rule: reference-rejection
    must run BEFORE the marker check. A gate that checked the marker first
    (even after unescaping HTML entities) would find "CACHE_BREAKPOINT" in
    this text and could wrongly call it usable; evaluating reference-
    rejection first closes that off regardless of what the preview says
    about the marker.

    RED today: this reply does not contain the RAW marker literal (only
    its escaped mention), so it fails `contextBundle.includes(marker)`
    exactly like every other reference reply and halts as generic
    "not obtained" — wrong for the same reason as the other reference
    tests in this file.
    """
    bundle_response = _reference_response(
        _ESCAPED_MARKER_MENTION_BUNDLE,
        _REAL_TRUNCATED_PREVIEW_BYTES,
        _REAL_TRUNCATED_PREVIEW_LOCATION,
        _REAL_TRUNCATED_PREVIEW_MESSAGE,
    )
    result = _sibling._run_ship(bundle_response=bundle_response)
    assert result.error == "", f"Harness error: {result.error}"

    _assert_no_context_carrying_dispatch(
        result, "reference reply that merely mentions the escaped marker"
    )

    msg = _payload_message(result)
    lower = msg.lower()

    assert "not obtained" not in lower and "never obtained" not in lower, f"Got: {msg!r}"
    assert not _is_incomplete_message(lower), (
        "A locator that merely MENTIONS the marker must not be classified "
        f"as incomplete content — it is a reference. Got: {msg!r}"
    )
    assert _is_reference_message(lower), (
        f"Expected a reference-state halt message. Got: {msg!r}"
    )


# ===========================================================================
# 3. NOT_OBTAINED — must be distinguishable from the reference and
#    incomplete states, not just "halted".
# ===========================================================================


def test_nothing_obtained_variants_halt_naming_not_obtained_distinctly():
    # covers: BO-2400c-1-iii
    """With the dispatch stubbed to obtained:false, an unparseable
    (non-dict) reply, and a null reply in turn, each run halts on the
    NOT_OBTAINED branch: no context-carrying dispatch, and a message that
    says the bundle was never obtained / nothing came back — and does NOT
    also satisfy the reference or incomplete predicates.

    This is a real gap even though the sibling file's own
    'unobtainable_bundle_halts' test already passes: that test only checks
    the generic word "bundle" appears in the payload and status != "ok". It
    never asserts the message is WORDED as not-obtained specifically
    (distinct from reference/incomplete wording) — which today's shared
    single message technically already satisfies for genuinely-absent
    replies, but this test also proves it does NOT accidentally read as a
    reference or incomplete-content halt for these inputs.
    """
    variants = [
        {"obtained": False, "bundle": "", "message": "assembling command failed"},
        {},
        None,
    ]
    for variant in variants:
        result = _sibling._run_ship(bundle_response=variant)
        assert result.error == "", f"Harness error for variant {variant!r}: {result.error}"

        _assert_no_context_carrying_dispatch(result, f"nothing-obtained variant {variant!r}")

        msg = _payload_message(result)
        lower = msg.lower()

        assert _is_not_obtained_message(lower), (
            f"Variant {variant!r}: expected a NOT_OBTAINED-worded halt "
            f"message. Got: {msg!r}"
        )
        assert not _is_reference_message(lower), (
            f"Variant {variant!r}: a genuinely-absent bundle must not read "
            f"as a reference halt. Got: {msg!r}"
        )
        assert not _is_incomplete_message(lower), (
            f"Variant {variant!r}: a genuinely-absent bundle must not read "
            f"as an incomplete-content halt. Got: {msg!r}"
        )

        payload = result.result
        assert payload.get("failing_phase") == "context-bundle", (
            f"Variant {variant!r}: expected failing_phase == 'context-bundle'. "
            f"Got: {payload.get('failing_phase')!r}"
        )
        assert payload.get("status") != "ok", f"Variant {variant!r}: got {payload}"


# ===========================================================================
# 4. OBTAINED_BUT_INCOMPLETE — real content, not a locator, but marker
#    absent or a layer empty.
# ===========================================================================


def test_incomplete_missing_breakpoint_marker_halts_distinctly():
    # covers: BO-2400c-1-iii
    """Real, well-formed content (produced by the actual
    assemble_context_bundle() pure function) that is missing the expected
    breakpoint marker literal halts as OBTAINED_BUT_INCOMPLETE — distinct
    wording from both NOT_OBTAINED and OBTAINED_BUT_A_REFERENCE.

    RED today: this bundle is a non-empty string that is NOT a locator (it
    is genuine multi-layer prose), yet `contextBundleUsable` is false
    because it lacks the marker, so it takes the exact same generic
    "not obtained" halt branch as a truly-absent bundle — collapsing a
    state the amendment requires to be distinguishable.
    """
    bundle_response = {
        "obtained": True,
        "bundle": _INCOMPLETE_MISSING_MARKER_BUNDLE,
        "message": "bundle assembled",
    }
    result = _sibling._run_ship(bundle_response=bundle_response)
    assert result.error == "", f"Harness error: {result.error}"

    _assert_no_context_carrying_dispatch(result, "content missing the breakpoint marker")

    msg = _payload_message(result)
    lower = msg.lower()

    assert _is_incomplete_message(lower), (
        f"Expected an INCOMPLETE-worded halt message (marker absent). Got: {msg!r}"
    )
    assert "not obtained" not in lower and "never obtained" not in lower, (
        f"Real content that was genuinely obtained must not be worded as "
        f"'not obtained'. Got: {msg!r}"
    )
    assert not _is_reference_message(lower), (
        f"Real content missing only the marker is not a reference. Got: {msg!r}"
    )


def test_incomplete_empty_layer_halts_distinctly():
    # covers: BO-2400c-1-iii
    """Real content with the breakpoint marker present exactly once but one
    layer (acs) empty halts as OBTAINED_BUT_INCOMPLETE — distinct from the
    missing-marker incomplete variant only in cause, not in classification,
    and distinct from both other failure states in wording.

    RED today: `contextBundleUsable` only checks `obtained`, non-empty
    overall string, and marker presence — it has no notion of a
    per-layer-empty check at all, so this bundle (which DOES contain the
    marker) is classified USABLE today and dispatched to test-writer/coder
    despite the empty acs layer. This test is RED via the inverted
    assertion: it currently DISPATCHES rather than halting.
    """
    bundle_response = {
        "obtained": True,
        "bundle": _INCOMPLETE_EMPTY_LAYER_BUNDLE,
        "message": "bundle assembled",
    }
    result = _sibling._run_ship(bundle_response=bundle_response)
    assert result.error == "", f"Harness error: {result.error}"

    _assert_no_context_carrying_dispatch(result, "content with an empty acs layer")

    msg = _payload_message(result)
    lower = msg.lower()

    assert _is_incomplete_message(lower), (
        f"Expected an INCOMPLETE-worded halt message (empty layer). Got: {msg!r}"
    )
    assert "not obtained" not in lower and "never obtained" not in lower, f"Got: {msg!r}"
    assert not _is_reference_message(lower), f"Got: {msg!r}"


# ===========================================================================
# 5. The three failure messages must be pairwise distinct AND self-naming —
#    the exact trap test_rationale warns about: "asserting each in
#    isolation lets one undifferentiated message pass all three."
# ===========================================================================


def test_three_failure_messages_are_pairwise_distinct_and_self_naming():
    # covers: BO-2400c-1-iii
    """Drive all three failure states in ONE test and compare the three
    terminal messages pairwise: each must satisfy ONLY its own
    distinguishing predicate, never another's.

    RED today: NOT_OBTAINED and OBTAINED_BUT_A_REFERENCE currently produce
    the IDENTICAL message (both fall through the single `contextBundleUsable`
    branch), so this test fails at the very first pairwise inequality
    assertion (not_obtained_msg != reference_msg).
    """
    not_obtained_result = _sibling._run_ship(
        bundle_response={"obtained": False, "bundle": "", "message": "assembling command failed"}
    )
    reference_result = _sibling._run_ship(
        bundle_response=_reference_response(
            _OBSERVED_FILE_URI,
            _OBSERVED_FILE_URI_BYTES,
            _OBSERVED_FILE_URI_LOCATION,
            "Bundle assembled successfully.",
        )
    )
    incomplete_result = _sibling._run_ship(
        bundle_response={
            "obtained": True,
            "bundle": _INCOMPLETE_MISSING_MARKER_BUNDLE,
            "message": "bundle assembled",
        }
    )

    for label, r in (
        ("not_obtained", not_obtained_result),
        ("reference", reference_result),
        ("incomplete", incomplete_result),
    ):
        assert r.error == "", f"Harness error for {label}: {r.error}"

    messages = {
        "not_obtained": _payload_message(not_obtained_result).lower(),
        "reference": _payload_message(reference_result).lower(),
        "incomplete": _payload_message(incomplete_result).lower(),
    }

    assert messages["not_obtained"] != messages["reference"], (
        "NOT_OBTAINED and OBTAINED_BUT_A_REFERENCE must not produce the "
        f"same message. Got: {messages['not_obtained']!r}"
    )
    assert messages["not_obtained"] != messages["incomplete"], (
        "NOT_OBTAINED and OBTAINED_BUT_INCOMPLETE must not produce the "
        f"same message. Got: {messages['not_obtained']!r}"
    )
    assert messages["reference"] != messages["incomplete"], (
        "OBTAINED_BUT_A_REFERENCE and OBTAINED_BUT_INCOMPLETE must not "
        f"produce the same message. Got: {messages['reference']!r}"
    )

    predicates = {
        "not_obtained": _is_not_obtained_message,
        "reference": _is_reference_message,
        "incomplete": _is_incomplete_message,
    }
    for state_name, msg in messages.items():
        satisfied = {name for name, pred in predicates.items() if pred(msg)}
        assert satisfied == {state_name}, (
            f"The {state_name} halt message must satisfy ONLY its own "
            f"distinguishing check — a message satisfying more than one "
            f"(or none) collapses the states this amendment exists to "
            f"separate. Satisfied checks: {satisfied}. Message: {msg!r}"
        )


# ===========================================================================
# 6. No unbundled prompt is EVER dispatched, across every unusable state —
#    proves the gate terminates the run rather than being defined and
#    skipped (test_spec angle: reachability).
# ===========================================================================


def test_no_unbundled_prompt_is_dispatched_on_any_unusable_bundle_state():
    # covers: BO-2400c-1-iii
    """Across every one of the five representative unusable-bundle shapes
    (not-obtained, two reference shapes, two incomplete shapes),
    HarnessResult.agent_calls contains no dispatch labelled
    'test-writer-connected' or 'coder-connected'.

    RED today for two of the five: the two reference shapes below (file:
    URI and the real truncated-preview reproduction) currently DO halt
    without dispatching test-writer/coder — but only because they hit the
    (wrongly-worded) shared halt branch, which the earlier tests in this
    file already show is a distinct defect. This test's own unique
    contribution is proving dispatch-absence holds simultaneously across
    ALL five shapes in one assertion sweep, including the two INCOMPLETE
    shapes — one of which (empty layer) is RED here specifically because
    today's gate has no empty-layer check at all and DOES dispatch
    test-writer/coder for it (see
    test_incomplete_empty_layer_halts_distinctly's own RED explanation).
    """
    variants = [
        ("not-obtained", {"obtained": False, "bundle": "", "message": "failed"}),
        (
            "file-uri-reference",
            _reference_response(
                _OBSERVED_FILE_URI,
                _OBSERVED_FILE_URI_BYTES,
                _OBSERVED_FILE_URI_LOCATION,
                "Bundle assembled successfully.",
            ),
        ),
        (
            "truncated-preview-reference",
            _reference_response(
                _REAL_TRUNCATED_PREVIEW_BUNDLE,
                _REAL_TRUNCATED_PREVIEW_BYTES,
                _REAL_TRUNCATED_PREVIEW_LOCATION,
                _REAL_TRUNCATED_PREVIEW_MESSAGE,
            ),
        ),
        (
            "missing-marker-incomplete",
            {"obtained": True, "bundle": _INCOMPLETE_MISSING_MARKER_BUNDLE, "message": "bundle assembled"},
        ),
        (
            "empty-layer-incomplete",
            {"obtained": True, "bundle": _INCOMPLETE_EMPTY_LAYER_BUNDLE, "message": "bundle assembled"},
        ),
    ]
    for desc, bundle_response in variants:
        result = _sibling._run_ship(bundle_response=bundle_response)
        assert result.error == "", f"Harness error for {desc}: {result.error}"
        _assert_no_context_carrying_dispatch(result, desc)

        payload = result.result
        assert payload is not None, f"{desc}: missing terminal payload."
        assert payload.get("status") != "ok", (
            f"{desc}: an unusable bundle must never be reported as a "
            f"successful run. Got: {payload}"
        )


def test_truncated_preview_without_a_location_field_is_still_a_reference():
    # covers: BO-2400c-1-iii
    """The reply shape ACTUALLY observed in production — no `location` key.

    Every other reference test in this file builds its reply through
    _reference_response(), which always supplies `bytes` and `location`.
    Those two fields were ADDED to CONTEXT_BUNDLE_SCHEMA as part of this very
    change, so a fixture carrying them describes the reply we hope to receive
    once the amended schema is in force — not the one that actually arrived.

    The run observed on 2026-08-26 returned exactly three keys: obtained,
    bundle, message. `bundle` was a truncated preview that OPENS WITH REAL
    BUNDLE CONTENT and then explains, in prose, that the full 141,933 bytes
    are on disk at a path. So:

      * isContextBundleLocatorString(bundle) is false — the text is prose
        beginning "---\\ntitle:", not a path or a file: URI; and
      * reportedLocation is null — the agent never populated the field,
        because at the time it did not exist.

    Both reference signals therefore miss, the marker is absent from the
    preview, and the reply lands in OBTAINED_BUT_INCOMPLETE. The run does
    halt, which is the important safety property and is already covered
    elsewhere — but it halts blaming incomplete CONTENT for what is really a
    reference, and BO-2400c-1-iii requires the halt to name the one state
    that actually occurred.

    This matters beyond tidiness: a schema is a request, not a guarantee. An
    agent that truncates a large payload and describes where it put it is
    doing the sensible thing, and it may do so without filling in a field it
    was not obliged to notice. Detection cannot rest solely on the producer's
    cooperation.
    """
    observed_reply = {
        "obtained": True,
        "bundle": _REAL_TRUNCATED_PREVIEW_BUNDLE,
        "message": _REAL_TRUNCATED_PREVIEW_MESSAGE,
    }
    result = _sibling._run_ship(bundle_response=observed_reply)
    assert result.error == "", f"Harness error: {result.error}"

    _assert_no_context_carrying_dispatch(result, "location-less truncated preview")

    msg = _payload_message(result)
    lower = msg.lower()
    assert _is_reference_message(lower), (
        "A truncated preview that names a path in prose is a reference "
        "standing in for the content, whether or not the producer filled in "
        f"the location field. Got: {msg!r}"
    )
