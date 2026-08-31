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
# MUST NOT BE DETECTED -- GE-122 precision anchors for the fix that adds a
# positional (line-start) fallback to _is_placeholder_marker, closing the
# parity gap with _is_bare_todo_marker / _is_replace_with_marker /
# _is_fixme_marker (see the "MUST-DETECT (BUG) -- GE-122" section in the
# sibling recall-floor file for the defect this pairs against). The
# inline-code exemption is the escape hatch a document uses to NAME a marker
# without leaving one behind, and it must keep working exactly as it does
# today once PLACEHOLDER gains the new positional check.
# ---------------------------------------------------------------------------


def test_fp_placeholder_backtick_bulleted_stays_exempt(tmp_path: Path) -> None:
    """GE-122 precision anchor: '- `PLACEHOLDER`' (a bulleted, backtick-
    wrapped mention) must stay exempt after the positional line-start fix
    lands. Backticks are the supported way a document NAMES a marker
    without leaving one behind -- _is_within_inline_code excludes any match
    that sits fully inside a single-backtick span, and that guard runs
    BEFORE any positional check in every validator, including the fixed
    PLACEHOLDER one. This is the paired precision case for
    test_bug_placeholder_dash_bullet_no_colon in the sibling recall file --
    a fix that makes the guard positional must not have moved the
    inline-code check to run only for the pre-existing branches.
    """
    hits = _scan_text(tmp_path, "- `PLACEHOLDER`")
    assert hits == [], f"'- `PLACEHOLDER`' must stay exempt via the inline-code guard, got: {hits}"


@pytest.mark.parametrize(
    "content",
    [
        "- `TODO`",
        "- `FIXME:`",
        "- `Replace with`",
    ],
)
def test_fp_backtick_bulleted_markers_stay_exempt_for_every_convention(tmp_path: Path, content: str) -> None:
    """GE-122 precision anchor: the backtick-wrapped, bulleted form of every
    OTHER marker convention already stays exempt today (verified
    behaviourally before this fix) and must keep doing so after the
    PLACEHOLDER fix lands -- a regression here would mean the fix
    accidentally weakened _is_within_inline_code's precedence for markers
    it did not even touch.
    """
    hits = _scan_text(tmp_path, content)
    assert hits == [], f"{content!r} must stay exempt via the inline-code guard, got: {hits}"


def test_ge122_full_false_positive_prose_corpus_stays_clean(tmp_path: Path) -> None:
    """GE-122 regression anchor: the fix adds a positional (line-start)
    fallback to _is_placeholder_marker, mirroring _is_bare_todo_marker /
    _is_replace_with_marker / _is_fixme_marker. None of the false-positive
    strings already pinned individually above (and in the sibling recall
    file) open their line with the bare marker word -- every one is either
    backtick-quoted or sits mid-sentence -- so this combines them into a
    single document and re-asserts the whole corpus stays clean in one
    scan, the way a real multi-paragraph doc would be scanned end to end.
    """
    corpus = "\n".join(
        [
            "the placeholder detection step scans for markers left unfilled.",
            "A placeholder is a token left unfilled, such as {summary}.",
            "If the default value does not fit your project, replace with a value that matches your conventions.",
            "The scanner looks for markers such as `TODO:` or `PLACEHOLDER` in generated docs.",
            "This convention (`FIXME:` for known bugs) is documented in the style guide.",
            "The <!-- QUESTION --> comment style is used to flag open questions in docs.",
            "Markers scanned for include TODO, FIXME, and PLACEHOLDER.",
            "For example, TODO is one of the literal markers this scanner looks for.",
        ]
    )
    hits = _scan_text(tmp_path, corpus)
    assert hits == [], f"the combined false-positive prose corpus must stay clean after the GE-122 fix, got: {hits}"


def test_ge122_real_documentation_verifier_agent_still_scans_clean() -> None:
    """GE-122 regression anchor: templates/agents/documentation-verifier.md
    -- the canonical over-match canary already pinned by
    test_fp_real_documentation_verifier_agent_scans_clean above -- must
    still come back with ZERO hits after the positional fix. Verified
    directly (grep for a bullet/ordinal immediately followed by the word
    "placeholder", case-insensitive) before writing this test: the file has
    no such line, so adding a line-start fallback to _is_placeholder_marker
    has nothing to fire on here. This is a distinct, GE-122-scoped pin
    rather than a duplicate of the pre-existing canary above, so a future
    edit that narrows THAT test cannot silently drop coverage of this fix
    too.
    """
    target = _REPO_ROOT / "templates" / "agents" / "documentation-verifier.md"
    assert target.is_file(), f"expected real file at {target}"
    hits = scan_for_placeholders(_REPO_ROOT, [target])
    assert hits == [], (
        f"documentation-verifier.md must still scan clean after the GE-122 PLACEHOLDER "
        f"positional fix; got {len(hits)} hit(s), e.g. {hits[:5]!r}"
    )


# ---------------------------------------------------------------------------
# MUST NOT BE DETECTED -- GE-122 precision anchors for the fix that gives
# TODO/FIXME/"Replace with" HTML-comment-wrapped detection parity with
# PLACEHOLDER (see the "MUST-DETECT (BUG) -- GE-122, HTML-comment marker
# parity" section in the sibling recall-floor file for the defect this pairs
# against). These pin the two boundaries that fix must not move: the
# colon-less QUESTION form (deliberately exempt by design, not a gap), and the
# backtick-wrapped naming-the-convention form (exempt via the pre-existing
# inline-code guard, which must keep precedence over the newly widened rules).
# ---------------------------------------------------------------------------


def test_fp_question_html_comment_without_colon_stays_clean(tmp_path: Path) -> None:
    """PINNED BOUNDARY (GE-122): '<!-- QUESTION -->' (no colon) must stay
    CLEAN -- this is deliberate, not a recall gap to close. QUESTION's own
    pattern (`<!--\\s*QUESTION\\s*:`) requires a trailing colon specifically
    so the colon-less form can be used, as prose, to show the HTML-comment
    CONVENTION as a worked example (see
    test_fp_question_comment_convention_given_as_worked_example above, which
    pins the identical string embedded in a full sentence) -- whereas
    '<!-- QUESTION: ... -->' carries real, unresolved question text. A fix
    that gives TODO/FIXME/"Replace with" HTML-comment parity with PLACEHOLDER
    must NOT fold QUESTION into that same bare-form widening, or this
    asymmetry silently disappears.
    """
    hits = _scan_text(tmp_path, "<!-- QUESTION -->")
    assert hits == [], f"'<!-- QUESTION -->' (no colon) must stay clean, got: {hits}"


@pytest.mark.parametrize(
    "content",
    [
        "`<!-- TODO -->`",
        "`<!-- todo -->`",
        "`<!-- FIXME -->`",
        "`<!-- Replace with the real thing -->`",
    ],
)
def test_fp_backtick_wrapped_html_comment_markers_stay_exempt(tmp_path: Path, content: str) -> None:
    """PINNED BOUNDARY (GE-122): a backtick-wrapped HTML-comment marker -- the
    shape prose uses to NAME the convention without leaving a real marker
    behind, e.g. "`<!-- TODO -->` is how a template shows an unresolved
    question" -- must stay exempt once TODO/FIXME/"Replace with" gain
    HTML-comment-wrapped detection. _is_within_inline_code runs FIRST in
    every validator (including PLACEHOLDER's, which already gets this for
    free via its own HTML-comment branch -- see
    test_fp_placeholder_backtick_bulleted_stays_exempt above for the sibling
    bullet-prefix form of the same guard), so a fix that widens the OTHER
    three markers' recall must not have moved the inline-code guard to run
    only for the pre-existing branches.
    """
    hits = _scan_text(tmp_path, content)
    assert hits == [], f"{content!r} must stay exempt via the inline-code guard, got: {hits}"


def test_ge122_html_comment_documentation_verifier_agent_still_scans_clean() -> None:
    """GE-122 regression anchor (HTML-comment marker parity):
    templates/agents/documentation-verifier.md -- the canonical over-match
    canary already pinned by test_fp_real_documentation_verifier_agent_scans_clean
    and test_ge122_real_documentation_verifier_agent_still_scans_clean above --
    must still come back with ZERO hits once TODO/FIXME/"Replace with" gain
    HTML-comment-wrapped, colon-less detection parity with PLACEHOLDER.
    Verified directly (`grep -rniE "<!--\\s*(TODO|FIXME|Replace with)"` across
    docs/, templates/, and tickets/) before writing this test: the only
    matches anywhere in the repository are in templates/CLAUDE.md.template and
    templates/ANTIGRAVITY.md.template, and both are already colon-anchored
    ('<!-- TODO: fill in ... -->'), already caught today via the pre-existing
    colon rule, and neither is this file -- so widening the bare, colon-less
    form has nothing new to fire on here.
    """
    target = _REPO_ROOT / "templates" / "agents" / "documentation-verifier.md"
    assert target.is_file(), f"expected real file at {target}"
    hits = scan_for_placeholders(_REPO_ROOT, [target])
    assert hits == [], (
        f"documentation-verifier.md must still scan clean after the HTML-comment "
        f"marker-parity fix; got {len(hits)} hit(s), e.g. {hits[:5]!r}"
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
def test_ge122_html_comment_known_issues_docs_scan_clean(known_issue_filename: str) -> None:
    """GE-122 regression anchor (HTML-comment marker parity): the real
    docs/known-issues/*.md files must still come back clean once
    TODO/FIXME/"Replace with" gain HTML-comment-wrapped detection parity with
    PLACEHOLDER. Verified via the same repo-wide grep as the test above --
    none of these files contain the bare HTML-comment shape this fix newly
    recognises.
    """
    target = _REPO_ROOT / "docs" / "known-issues" / known_issue_filename
    assert target.is_file(), f"expected real file at {target}"
    hits = scan_for_placeholders(_REPO_ROOT, [target])
    assert hits == [], (
        f"the real {known_issue_filename} must scan clean after the HTML-comment "
        f"marker-parity fix; got {len(hits)} false-positive hit(s): {hits[:5]!r}"
    )


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


# ---------------------------------------------------------------------------
# GE-122b PRECISION REGRESSION -- the OPTIONAL-bullet widening of
# _is_placeholder_marker (2026-08-25) was itself a bug, caught by a repo-wide
# before/after diff, NOT by the grep that justified shipping it.
#
# THE LESSON THIS SECTION PINS: `_LEADING_MARKER_PREFIX` is
# `r"^\s*(?:[-*+]|\d+[.)])?\s*"` -- the bullet/ordinal alternation group is
# OPTIONAL. `_is_marker_at_line_start` therefore accepts BARE INDENTATION
# (whitespace with no bullet or ordinal at all) as a qualifying prefix, not
# only a real list-item marker. Every sibling validator that reuses this same
# helper (_is_bare_todo_marker, _is_fixme_marker, _is_replace_with_marker)
# inherits the identical looseness, but PLACEHOLDER is the marker whose bare
# form collides with an ordinary English noun, so it is the one where this
# looseness turns into a false-positive explosion: ANY wrapped-paragraph line
# that happens to be indented and starts with the word "placeholder" now
# qualifies, because line-wrapped markdown/YAML prose is indented far more
# often than it is bulleted.
#
# THE GREP THAT MISSED IT: the widening was justified by grepping the repo for
# "one instance in a closed ticket" of the bulleted false-positive shape
# ('1. Placeholder not substituted ...', already accepted as a documented
# cost -- see test_fp_placeholder_named_in_a_list_is_now_an_accepted_cost in
# the sibling recall-floor file). That grep only searched for the BULLETED
# shape, because that was the shape the recall fix was written against. It
# never searched for the WIDER shape the fix actually implements (bare
# indentation, no bullet required at all), so it could not have found the 23
# false positives below even in principle -- they are not bulleted lines.
#
# THE MEASUREMENT THAT DID CATCH IT: a real repo-wide scan (committed HEAD vs
# the working tree, 4815 files) found BEFORE 72 hits / AFTER 94 hits / 24 NEW
# hits / 2 REMOVED. 23 of the 24 new hits are false positives spanning real
# doc surfaces (12 AC YAML files, 4 agent templates, 1 generated agent card, 4
# ticket files, 2 skill/doc files) -- all wrapped prose that merely happens to
# start a line with the word "placeholder" after markdown/YAML indentation.
# Only the 24th (a real ordinal, "1. Placeholder not substituted ...") is an
# accepted cost, because it carries an actual ordinal marker.
#
# THE FIX THIS SECTION DRIVES: PLACEHOLDER's positional path must require an
# ACTUAL bullet or ordinal -- not bare indentation -- while TODO, FIXME, and
# "Replace with" keep the existing optional-bullet form (they have used it
# since before this regression and are out of scope; narrowing them risks
# losing genuine detections with no repo-wide evidence they need it, unlike
# PLACEHOLDER's now-measured 23-false-positive cost). The verified arithmetic:
# OPTIONAL (today) detects 9/9 genuine bulleted/ordinal markers but also
# false-positives on 10/10 representative wrapped-prose samples; REQUIRING a
# real bullet/ordinal keeps the same 9/9 detection rate while dropping false
# positives to 0/10. There is no recall cost to this fix on any case anyone
# has found -- only precision gain.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source_ref", "content"),
    [
        (
            "ACS-500f-2.yaml:55",
            "  placeholder in criteria. So a pattern AC that declares its slots only via {word}",
        ),
        (
            "BO-2000c-1.yaml:18",
            "    placeholder heading.",
        ),
        (
            "INF-1100c-1.yaml:14",
            "    placeholder for the configured test root,",
        ),
        (
            "mockup-author.md:238",
            "  Placeholder / lorem text is a defect (UXP-541).",
        ),
        (
            "user-surface-smoker.md:4",
            "  placeholder-dispatch defects (EPIC-GlossaryAutomation postmortem). Only dispatched",
        ),
        (
            "architecture-diagram-author.md:267",
            "   placeholder with a real one-sentence purpose statement.",
        ),
        (
            "write-c4-diagram/SKILL.md:226",
            "   placeholder and flesh out the mermaid skeleton.",
        ),
    ],
)
def test_ge122b_indented_wrapped_prose_stays_clean(tmp_path: Path, source_ref: str, content: str) -> None:
    # covers: UNKNOWN
    """GE-122b: each of these is a REAL line copied verbatim (with its real
    leading indentation) from an on-disk file this repository already ships,
    named by `source_ref` above. None of them is a marker -- every one is a
    wrapped-paragraph continuation line that happens to open with the word
    "placeholder" purely because of markdown/YAML line-wrapping, after
    whitespace-only indentation with no bullet or ordinal anywhere in front
    of it. All seven are CURRENTLY flagged by the OPTIONAL-bullet widening
    (verified by running this exact string through scan_for_placeholders()
    before writing this test) -- this is the red state the fix must turn
    green by requiring an actual bullet/ordinal, not bare indentation, in
    PLACEHOLDER's positional check.
    """
    hits = _scan_text(tmp_path, content)
    assert hits == [], (
        f"wrapped prose from {source_ref} must not be flagged as a PLACEHOLDER marker "
        f"just because it is indented with no bullet/ordinal in front of it; got: {hits}"
    )


def test_ge122b_bare_indentation_alone_does_not_qualify_but_a_real_bullet_does(tmp_path: Path) -> None:
    # covers: UNKNOWN
    """GE-122b structural anchor: indentation ALONE must never be sufficient
    for PLACEHOLDER's positional check -- only a real bullet or ordinal
    qualifies. This pairs the two lines that differ ONLY in whether a bullet
    is present, so the distinction the fix must draw is unambiguous evidence
    in a single test rather than two tests a reader has to cross-reference:

    - "    placeholder for the configured test root," (four spaces, no
      bullet -- the real line from INF-1100c-1.yaml:14) must stay CLEAN.
    - "    - PLACEHOLDER" (identical indentation, PLUS a real dash bullet)
      must still be CAUGHT -- this is the genuine unfilled-checklist-entry
      shape _is_marker_at_line_start exists to catch, and the fix must not
      collapse it into "any indentation is clean" as an overcorrection.
    """
    indented_prose_hits = _scan_text(
        tmp_path,
        "    placeholder for the configured test root,",
        filename="prose.md",
    )
    indented_bulleted_hits = _scan_text(
        tmp_path,
        "    - PLACEHOLDER",
        filename="bulleted.md",
    )
    assert indented_prose_hits == [], (
        f"bare indentation with no bullet must not qualify as a marker position, got: {indented_prose_hits}"
    )
    assert indented_bulleted_hits, (
        "the identical indentation WITH a real dash bullet must still be caught as a genuine "
        f"unfilled checklist entry, got: {indented_bulleted_hits}"
    )


def test_ge122b_acceptance_criteria_tree_placeholder_hits_are_zero() -> None:
    # covers: UNKNOWN
    """GE-122b repo-scale canary -- THE tripwire that would have caught this
    regression, because it measures the fix's effect on real, already-shipped
    documents instead of estimating it from a hand-picked grep shape.

    Scans every AC YAML file under docs/acceptance-criteria/ (3092 files,
    ~1.3s wall-clock measured directly with the real scan_for_placeholders()
    entry point -- well inside the 5s per-test budget, so no _MANUAL suffix
    is warranted) and asserts that PLACEHOLDER-marker hits specifically are
    ZERO.

    Deliberately filtered to the PLACEHOLDER marker only (case-insensitive
    match on hit["marker"]): this tree also contains genuine, pre-existing,
    IN-SCOPE bare-TODO hits (e.g. "- todo -> in_progress" bulleted checklist
    lines in BO-400b-2.yaml, TKT-500c-6.yaml, BO-2400e-3.yaml) that
    _is_bare_todo_marker already and correctly catches today via the exact
    same optional-bullet positional check this fix deliberately does NOT
    touch for TODO/FIXME/"Replace with" (see module docstring's scope
    discipline). Asserting a literal zero-hits-of-any-marker canary would
    make this test red for a reason unrelated to the PLACEHOLDER regression
    and would break the moment anyone fixes or leaves alone that unrelated
    TODO usage -- exactly the kind of over-broad assertion this whole
    regression teaches us to avoid.

    Before this fix: 12 of these files produce a PLACEHOLDER hit (verified
    directly by running scan_for_placeholders() over this exact tree before
    writing this test) -- all wrapped prose, none a real marker. After the
    fix requires an actual bullet/ordinal for PLACEHOLDER, none of them open
    their line with a bullet or ordinal, so all 12 must clear to zero.
    """
    yaml_paths = sorted((_REPO_ROOT / "docs" / "acceptance-criteria").rglob("*.yaml"))
    assert len(yaml_paths) > 100, (
        f"expected the real AC store to contain hundreds of YAML files, found {len(yaml_paths)} -- "
        "the store may have moved or this canary is scanning the wrong tree"
    )
    hits = scan_for_placeholders(_REPO_ROOT, yaml_paths)
    placeholder_hits = [h for h in hits if h["marker"].lower() == "placeholder"]
    assert placeholder_hits == [], (
        f"the whole docs/acceptance-criteria/ tree must produce ZERO PLACEHOLDER-marker hits; "
        f"got {len(placeholder_hits)} false-positive hit(s), e.g. {placeholder_hits[:5]!r} -- this is "
        "the repo-scale canary that a shape-limited grep cannot substitute for"
    )
