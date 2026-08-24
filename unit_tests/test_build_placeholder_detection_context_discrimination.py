"""
MODULE: test_build_placeholder_detection_context_discrimination
GOAL: Pin the discrimination behaviour scan_for_placeholders() must have between a
    genuine, unresolved scaffolding marker and the same literal word/phrase used in
    ordinary English prose that DISCUSSES the detection mechanism itself.
BUSINESS CONTEXT: scan_for_placeholders() (scripts/build_placeholder_detection.py)
    backs documentation-verifier's Step 6a placeholder scan -- a gate that BLOCKS
    documentation from being accepted when it reports a hit. Its current patterns
    for PLACEHOLDER and "Replace with" are bare-word/phrase matches with
    re.IGNORECASE and no surrounding-context check, so a document that DISCUSSES
    placeholder detection (using the ordinary English words "placeholder" or
    "replace with" in running prose) is reported as CONTAINING placeholder content.
    Verified live: scan_for_placeholders() returns 59 hits against
    templates/agents/documentation-verifier.md -- the very agent that calls this
    helper, a correct and fully-authored document -- entirely because it discusses
    the mechanism using the ordinary word "placeholder". The TODO:/FIXME: patterns
    share a narrower version of the same defect: they require a trailing colon,
    which prevents a bare mention ("the word TODO") from matching, but does NOT
    prevent prose that quotes the marker AS WRITTEN with its colon (e.g. "the
    scanner looks for `TODO:`-style markers") -- a phrasing a doc that legitimately
    explains this exact gate is likely to use. The QUESTION pattern is anchored to
    a literal `<!--` comment opener, but even that anchor false-positives when
    prose gives the HTML-comment convention as a worked example
    (`<!-- QUESTION -->`) rather than leaving one unresolved.

    This gate exists to catch documentation that was announced but never written
    (scaffolding left behind), so narrowing it too far produces the opposite,
    STRICTLY WORSE failure: an unwritten doc sailing through as if it were done
    (the phantom-done failure mode this whole package exists to prevent). This
    file therefore pins BOTH directions: the load-bearing "must still catch a real
    marker" tests below are NOT decoration -- they are the tripwire that fails
    loudly if a narrowing fix goes too far.

SCOPE NOTE -- what this module does and does not implement (verified by reading
    scripts/build_placeholder_detection.py's _MARKER_PATTERNS list directly, not
    assumed): its only patterns are TODO:, PLACEHOLDER, "Replace with", the
    <!-- QUESTION comment opener, and FIXME:. It has NO pattern for a bare TBD
    marker, NO unfilled-{token}-style detection (e.g. `{summary}`), and NO
    heading-only/empty-stub detection. Those three checks are separate mechanisms
    that live directly in templates/agents/documentation-verifier.md's own
    instructions (sub-checks 6b, 6c, 6d respectively -- a standalone `grep`/`Read`
    step the agent runs itself, not a call into this Python helper). This test
    file therefore does NOT assert {summary}-token or heading-only-stub behaviour
    against scan_for_placeholders(): doing so would lock in an unscoped expansion
    of this module's contract (adding brand-new detection capability) rather than
    pinning the fix to the actual defect (case/context-insensitive bare-word
    matching on markers the module ALREADY claims to detect). If a future ticket
    moves 6c/6d's logic into this module, the tests for that behaviour belong in
    a file targeting that new surface, not here.

ARCHITECTURE: scan_for_placeholders() has no canonical templates/ counterpart --
    confirmed by directory search -- scripts/build_placeholder_detection.py is the
    one and only copy, imported directly by scripts/build.py at deploy time and
    invoked via a `python3 -c` one-liner from documentation-verifier.md's Step 6a
    at documentation-review time. All fixtures here are either real files written
    to a fresh tempdir (synthetic true/false-positive cases) or the actual on-disk
    templates/agents/documentation-verifier.md and docs/known-issues/*.md files
    (the false-positive regression cases), never a hand-typed stand-in for either.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from build_placeholder_detection import scan_for_placeholders  # noqa: E402 — after sys.path setup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scan_text(tmp_path: Path, content: str, filename: str = "doc.md") -> list[dict]:
    """Write `content` to a real file under tmp_path and scan it for real.

    Never calls scan_for_placeholders() against an in-memory string -- the
    function's contract is file-based (it opens and reads the path itself), so
    the fixture must be a real file on disk to exercise the real code path.
    """
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return scan_for_placeholders(tmp_path, [path])


# ---------------------------------------------------------------------------
# MUST STILL BE DETECTED -- load-bearing: a fix that breaks any of these has
# made the gate strictly worse (an unwritten doc sailing through as done).
# ---------------------------------------------------------------------------


def test_ac_detects_todo_scaffolding_marker(tmp_path: Path) -> None:
    """A literal, real scaffolding marker on its own line must still be caught."""
    hits = _scan_text(tmp_path, "TODO: write this section")
    assert hits, "a genuine 'TODO: write this section' scaffolding marker must be detected"
    assert hits[0]["line"] == 1
    assert "path" in hits[0] and "marker" in hits[0] and "context" in hits[0]


def test_ac_detects_placeholder_standalone_line(tmp_path: Path) -> None:
    """A bare PLACEHOLDER marker used as an actual marker must still be caught."""
    hits = _scan_text(tmp_path, "PLACEHOLDER")
    assert hits, "a line that is just 'PLACEHOLDER' (a real unfilled marker) must be detected"


def test_ac_detects_placeholder_in_html_comment(tmp_path: Path) -> None:
    """An HTML-comment-wrapped PLACEHOLDER marker must still be caught."""
    hits = _scan_text(tmp_path, "<!-- PLACEHOLDER -->")
    assert hits, "'<!-- PLACEHOLDER -->' as a real unfilled marker must be detected"


def test_ac_detects_todo_replace_with_combined_marker(tmp_path: Path) -> None:
    """A real scaffolding line combining TODO and 'Replace with' must still be caught."""
    hits = _scan_text(tmp_path, "TODO: Replace with the real component description")
    assert hits, "'TODO: Replace with the real component description' must be detected"


def test_ac_detects_bare_fixme_scaffolding_marker(tmp_path: Path) -> None:
    """A real FIXME: scaffolding marker (sibling of TODO:) must still be caught."""
    hits = _scan_text(tmp_path, "FIXME: this section needs real content")
    assert hits, "'FIXME: this section needs real content' must be detected"


def test_ac_detects_question_html_comment_marker(tmp_path: Path) -> None:
    """A real unresolved <!-- QUESTION ... --> marker must still be caught."""
    hits = _scan_text(tmp_path, "<!-- QUESTION: should this section cover retries too? -->")
    assert hits, "an actual unresolved '<!-- QUESTION' marker must be detected"


# ---------------------------------------------------------------------------
# MUST NOT BE DETECTED -- the false positives this file exists to pin down.
# Each of these is CURRENTLY detected (a bug) unless noted otherwise; report
# the observed RED/GREEN status honestly per the dispatch instructions rather
# than assuming which way each one currently goes.
# ---------------------------------------------------------------------------


def test_fp_placeholder_word_in_ordinary_prose(tmp_path: Path) -> None:
    """Prose naturally using the word "placeholder" must not be flagged."""
    hits = _scan_text(tmp_path, "the placeholder detection step scans for markers left unfilled.")
    assert hits == [], f"ordinary prose using the word 'placeholder' must not be flagged, got: {hits}"


def test_fp_placeholder_is_a_token_left_unfilled_sentence(tmp_path: Path) -> None:
    """The exact defining sentence "a placeholder is a token left unfilled" must not be flagged."""
    hits = _scan_text(tmp_path, "A placeholder is a token left unfilled, such as {summary}.")
    assert hits == [], f"a defining sentence about what a placeholder is must not be flagged, got: {hits}"


def test_fp_replace_with_phrase_mid_sentence(tmp_path: Path) -> None:
    """'replace with' occurring mid-sentence in ordinary explanation must not be flagged."""
    hits = _scan_text(
        tmp_path,
        "If the default value does not fit your project, replace with a value that matches your conventions.",
    )
    assert hits == [], f"'replace with' used mid-sentence in ordinary prose must not be flagged, got: {hits}"


def test_fp_todo_colon_quoted_as_a_worked_example(tmp_path: Path) -> None:
    """Prose that quotes the TODO: marker AS WRITTEN, to explain the convention, must not be flagged.

    This is the narrower sibling of the PLACEHOLDER/"Replace with" defect: TODO's
    pattern requires a trailing colon, which blocks a bare "the word TODO"
    mention, but does not block a doc quoting the marker exactly as it appears
    when real (colon included) purely as an illustrative example.
    """
    hits = _scan_text(
        tmp_path,
        "The scanner looks for markers such as `TODO:` or `PLACEHOLDER` in generated docs.",
    )
    assert hits == [], f"quoting 'TODO:' as a worked example of the convention must not be flagged, got: {hits}"


def test_fp_fixme_colon_quoted_as_a_worked_example(tmp_path: Path) -> None:
    """Prose that quotes the FIXME: marker AS WRITTEN, to explain the convention, must not be flagged."""
    hits = _scan_text(
        tmp_path,
        "This convention (`FIXME:` for known bugs) is documented in the style guide.",
    )
    assert hits == [], f"quoting 'FIXME:' as a worked example of the convention must not be flagged, got: {hits}"


def test_fp_question_comment_convention_given_as_worked_example(tmp_path: Path) -> None:
    """Prose that shows the <!-- QUESTION --> HTML-comment convention as an example must not be flagged."""
    hits = _scan_text(
        tmp_path,
        "The <!-- QUESTION --> comment style is used to flag open questions in docs.",
    )
    assert hits == [], f"showing the QUESTION comment convention as a worked example must not be flagged, got: {hits}"


def test_fp_marker_named_in_a_list_of_scanned_markers(tmp_path: Path) -> None:
    """Prose that lists PLACEHOLDER among the markers scanned for, as an example, must not be flagged."""
    hits = _scan_text(tmp_path, "Markers scanned for include TODO, FIXME, and PLACEHOLDER.")
    assert hits == [], f"naming PLACEHOLDER as one of the markers this scanner looks for must not be flagged, got: {hits}"


def test_fp_bare_marker_name_without_colon_is_not_flagged(tmp_path: Path) -> None:
    """A bare mention of the word TODO (no colon) already passes today -- lock it in.

    This is a currently-passing case (TODO's pattern requires a trailing colon),
    included so a future change to the TODO pattern cannot silently regress it.
    """
    hits = _scan_text(tmp_path, "For example, TODO is one of the literal markers this scanner looks for.")
    assert hits == [], f"a bare, colon-less mention of the word TODO must not be flagged, got: {hits}"


# ---------------------------------------------------------------------------
# MUST NOT BE DETECTED -- real, on-disk artifacts (never a hand-typed stand-in)
# ---------------------------------------------------------------------------


def test_fp_real_documentation_verifier_agent_scans_clean() -> None:
    """The real documentation-verifier.md -- a correct, fully-authored document
    that discusses this exact detection mechanism at length -- must come back
    clean. This is the headline defect case: as of this test's authoring,
    scan_for_placeholders() returns 59 hits against this file, all of them the
    descriptive English word "placeholder" or a quoted marker example, none an
    actual unfilled marker.
    """
    target = _REPO_ROOT / "templates" / "agents" / "documentation-verifier.md"
    assert target.is_file(), f"expected real file at {target}"
    hits = scan_for_placeholders(_REPO_ROOT, [target])
    assert hits == [], (
        f"the real, fully-authored documentation-verifier.md must scan clean; "
        f"got {len(hits)} false-positive hit(s), e.g. {hits[:5]!r}"
    )


@pytest.mark.parametrize(
    "known_issue_filename",
    [
        "supervisor-system.md",
        "commit-guardian.md",
        "feedback-collector.md",
        "README.md",
        "testing-quality.md",
        "build-orchestration.md",
    ],
)
def test_fp_real_known_issues_docs_scan_clean(known_issue_filename: str) -> None:
    """The real docs/known-issues/*.md files, which describe this and sibling
    gates, must come back clean.
    """
    target = _REPO_ROOT / "docs" / "known-issues" / known_issue_filename
    assert target.is_file(), f"expected real file at {target}"
    hits = scan_for_placeholders(_REPO_ROOT, [target])
    assert hits == [], (
        f"the real {known_issue_filename} must scan clean; got {len(hits)} false-positive hit(s): {hits[:5]!r}"
    )
