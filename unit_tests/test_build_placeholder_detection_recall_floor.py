"""
MODULE: test_build_placeholder_detection_recall_floor
GOAL: Pin the RECALL floor scan_for_placeholders() must meet -- the direction the
    sibling file test_build_placeholder_detection_context_discrimination.py does
    NOT cover. That file's "must still detect" tests are a mirror image of its own
    false-positive corpus (every case is UPPERCASE, drawn from the same mental
    template as the marker patterns themselves), so a fix could satisfy every test
    in that file while still missing most genuine, real-world scaffolding.

BUSINESS CONTEXT: pr-reviewer findings [H-1] and [H-2] (2026-08-25) reproduced six
    forms of genuine, unwritten-doc scaffolding that scan_for_placeholders() misses
    entirely:

        'placeholder: fill this in'              -- lowercase, PLACEHOLDER has no
                                                     re.IGNORECASE
        'fixme: this needs attention'            -- lowercase, FIXME has no
                                                     re.IGNORECASE
        'replace with the real description'      -- lowercase, "Replace with" is
                                                     deliberately case-sensitive
        'TODO fix this before shipping'          -- bare TODO, no colon
        'TODO'                                   -- bare TODO, alone, no colon
        'TODO(alice): fix this before shipping'  -- GitHub owner-tag form; the
                                                     parenthesis breaks the \\s*
                                                     bridge between TODO and :

    docs/known-issues/build-orchestration.md KI-BO-3 claims the earlier fix (which
    THIS same repo's own postmortem-writing agent produced) was "verified
    behaviourally in both directions" -- that claim was false. All six of that
    round's must-detect regression cases were UPPERCASE mirrors of the
    false-positive corpus; they could only ever confirm the patterns already
    worked on the shape they were written against. This file exists so that
    claim can never be made truthfully again without evidence.

THE TENSION THIS FILE HOLDS: every test below that demands wider recall is paired
    with a named precision case (an existing test in the sibling file, or a new one
    added here) that the same fix must NOT break. Widening a pattern indiscriminately
    (e.g. bolting re.IGNORECASE onto "Replace with" without also tightening its
    structural requirement) reproduces the exact defect KI-BO-3 fixed, just in
    lowercase. See inline "PRECISION RISK" notes on each MUST-DETECT test.

WHY A SIBLING FILE, NOT AN EXTENSION OF THE EXISTING ONE: the existing file's own
    docstring explicitly frames its must-detect tests as a "floor this logic must
    not fall below" for the false-positive-elimination fix -- its unit of concern is
    precision. This file's unit of concern is recall, and mixing the two would bury
    the "which regression is this a floor for" framing that made KI-BO-3's own gap
    invisible for as long as it was. Keeping them separate also means this file can
    be added without touching a single line of the 21 tests that must stay green
    throughout -- zero risk of an editing mistake weakening the precision tripwire
    while raising the recall floor.

SCOPE -- BUG vs PROPOSED (do not conflate): every test in the "MUST-DETECT (BUG)"
    section below targets a case this module ALREADY CLAIMS to detect (its own
    docstring lists TODO:, PLACEHOLDER, "Replace with", <!-- QUESTION, and FIXME:
    as covered marker conventions) but currently misses due to a case-sensitivity
    or colon-anchoring defect. Cases that would require recognizing a marker
    vocabulary this module has NEVER claimed to support (`@todo`, `XXX`, `HACK`) are
    feature requests, not bugs -- they are deliberately NOT asserted here (see the
    "CONSIDERED, NOT ASSERTED" section at the bottom for the reasoning captured
    against each).

ARCHITECTURE: identical fixture methodology to the sibling file -- every case is
    written to a real file under tmp_path and scanned via the real
    scan_for_placeholders() entry point, never an in-memory string or a mock. The
    six primary BUG fixtures below are byte-for-byte the strings from the
    pr-reviewer reproduction dump (single line, no trailing newline) -- not a
    paraphrase -- because that dump is itself the reproduction of a real defect
    report, and paraphrasing it risks fixing a slightly different, easier string.
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


def _scan_text(tmp_path: Path, content: str, filename: str = "doc.md") -> list[dict]:
    """Write `content` to a real file under tmp_path and scan it for real.

    Mirrors the sibling file's helper exactly (duplicated rather than imported so
    this file has no coupling to the other module's private helpers). Content is
    written with NO forced trailing newline unless the caller includes one --
    several tests below rely on that to cover the "marker on the last line with no
    trailing newline" case honestly rather than by accident.
    """
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return scan_for_placeholders(tmp_path, [path])


# ---------------------------------------------------------------------------
# MUST-DETECT (BUG) -- the six forms from the pr-reviewer reproduction, verbatim.
# Every one of these is RED on arrival: the underlying regex does not even match,
# confirmed independently against the compiled patterns before writing this file.
# ---------------------------------------------------------------------------


def test_bug_lowercase_placeholder_with_colon(tmp_path: Path) -> None:
    """BUG: 'placeholder: fill this in' -- PLACEHOLDER's regex has no re.IGNORECASE.

    PRECISION RISK: naively adding re.IGNORECASE to \\bPLACEHOLDER\\b without also
    keeping the existing structural guard (alone-on-line / HTML-comment / colon)
    would re-flag test_fp_placeholder_word_in_ordinary_prose and
    test_fp_placeholder_is_a_token_left_unfilled_sentence in the sibling file --
    both use the bare lowercase word "placeholder" in running prose with no
    colon. The fix must keep the colon/alone-line/comment requirement AND make it
    case-insensitive, not drop the requirement to gain the case-insensitivity.
    """
    hits = _scan_text(tmp_path, "placeholder: fill this in")
    assert hits, "'placeholder: fill this in' (lowercase, real scaffolding) must be detected"


def test_bug_lowercase_fixme_with_colon(tmp_path: Path) -> None:
    """BUG: 'fixme: this needs attention' -- FIXME's regex has no re.IGNORECASE.

    PRECISION RISK: a doc discussing the convention in lowercase prose, e.g.
    "this convention (fixme: for known bugs) is sometimes written in lowercase in
    commit messages" -- see test_fp_lowercase_fixme_convention_discussion_note
    below, which this file adds specifically because the sibling file's only
    FIXME false-positive anchor (test_fp_fixme_colon_quoted_as_a_worked_example)
    is backtick-quoted and would stay excluded by the inline-code guard either way,
    so it does not actually exercise this new risk.
    """
    hits = _scan_text(tmp_path, "fixme: this needs attention")
    assert hits, "'fixme: this needs attention' (lowercase, real scaffolding) must be detected"


def test_bug_lowercase_replace_with_no_prefix(tmp_path: Path) -> None:
    """BUG: 'replace with the real description' -- "Replace with" is deliberately
    case-sensitive today (see the module's own comment: dropping IGNORECASE was
    the fix for a different false-positive), so the lowercase form used when a
    template's own "TODO: " prefix has already been stripped is invisible.

    PRECISION RISK -- the sharpest one in this file: the existing
    test_fp_replace_with_phrase_mid_sentence pins "...replace with a value that
    matches your conventions." (lowercase, no slash-adjacency) as NOT flagged.
    That string and this BUG's string are the same phrase in the same case,
    differing only in SENTENCE POSITION -- this one starts the line, the FP one is
    embedded mid-sentence after other words. Simply adding re.IGNORECASE to
    \\bReplace with\\b, as the module's own line-by-line marker rules currently
    read the phrase, would flag BOTH or NEITHER -- it cannot discriminate them
    without a positional/structural check the current validator does not have.
    This is the one case in this file where "just add IGNORECASE" provably breaks
    an existing green test; the fix needs a structural discriminator (e.g.
    alone-on-line, or line-start) on top of case-insensitivity, mirroring how
    PLACEHOLDER already combines a bare regex with a positional validator.
    """
    hits = _scan_text(tmp_path, "replace with the real description")
    assert hits, "'replace with the real description' (lowercase, real scaffolding) must be detected"


def test_bug_bare_todo_no_colon_with_trailing_words(tmp_path: Path) -> None:
    """BUG: 'TODO fix this before shipping' -- TODO's regex requires a literal
    colon (\\bTODO\\s*:); a bare TODO followed by instructional text with no colon
    at all never matches, regardless of case.

    PRECISION RISK: the sibling file's test_fp_bare_marker_name_without_colon_is_not_flagged
    pins "For example, TODO is one of the literal markers this scanner looks
    for." as NOT flagged -- also a colon-less TODO followed by more words. The
    discriminator available here is sentence/line position: the BUG string has
    TODO as the FIRST token on the line; the FP string has TODO preceded by "For
    example, " -- it is not the first token. A fix that detects "bare TODO
    anywhere in the line" (rather than "bare TODO at the start of the line")
    would re-flag the FP case.
    """
    hits = _scan_text(tmp_path, "TODO fix this before shipping")
    assert hits, "'TODO fix this before shipping' (bare TODO, no colon) must be detected"


def test_bug_bare_todo_alone_on_line(tmp_path: Path) -> None:
    """BUG: 'TODO' alone on its own line (the classic unfilled-scaffolding shape
    already handled for PLACEHOLDER via _is_marker_line) is invisible for TODO
    because TODO's regex requires a colon that is not present at all.

    PRECISION RISK: none additional beyond test_bug_bare_todo_no_colon_with_trailing_words
    above -- this is the strict subset of that case (alone-on-line implies
    line-start), included separately because it is the literal reproduction
    string from the pr-reviewer dump and because it is also, incidentally, "a
    marker as the entire file body" from the broader case list this file was
    asked to consider.
    """
    hits = _scan_text(tmp_path, "TODO")
    assert hits, "a bare 'TODO' alone on a line (the entire file body) must be detected"


def test_bug_todo_owner_tag_paren_form(tmp_path: Path) -> None:
    """BUG: 'TODO(alice): fix this before shipping' -- the GitHub-style owner-tag
    convention. \\bTODO\\s*: requires the colon to follow TODO after only
    whitespace; "(alice)" breaks that bridge, so the colon-anchored regex never
    fires even though a colon is present later in the line.

    PRECISION RISK: a doc that explains the convention by name without backticks,
    e.g. "Contributors write comments like TODO(owner): to tag the assignee." --
    see test_fp_todo_owner_tag_convention_named_in_prose below, added here
    because the sibling file has no coverage for the parenthesized-owner form at
    all (it predates this convention being in scope).
    """
    hits = _scan_text(tmp_path, "TODO(alice): fix this before shipping")
    assert hits, "'TODO(alice): fix this before shipping' (owner-tagged TODO) must be detected"


# ---------------------------------------------------------------------------
# MUST-DETECT (BUG) -- casing permutations of the same six defects.
# The pr-reviewer's own postmortem (KI-BO-3) names the root failure mode: every
# must-detect regression case from the PRIOR fix was drawn from the same
# mental template as the patterns (all-uppercase), so it never exercised the
# actual boundary. These tests deliberately use Title-case and MiXeD-case, not
# just the one lowercase example each defect was reported with, so a fix that
# special-cases "exactly all-lowercase" cannot pass silently.
# ---------------------------------------------------------------------------


def test_bug_titlecase_placeholder_with_colon(tmp_path: Path) -> None:
    """BUG: Title-case 'Placeholder:' -- same case-sensitivity defect as the
    all-lowercase form, at a different point on the casing spectrum.

    PRECISION RISK: a sentence that legitimately starts with the word
    "Placeholder" (Title case purely because it opens a sentence), e.g.
    "Placeholder text appears when a field is empty." -- see
    test_fp_titlecase_placeholder_starts_a_sentence below.
    """
    hits = _scan_text(tmp_path, "Placeholder: fill this in")
    assert hits, "'Placeholder: fill this in' (Title-case) must be detected"


def test_bug_mixedcase_fixme_with_colon(tmp_path: Path) -> None:
    """BUG: MiXeD-case 'FixMe:' -- same case-sensitivity defect, mixed-case form.

    PRECISION RISK: same as test_bug_lowercase_fixme_with_colon above -- any fix
    that makes FIXME case-insensitive must still respect the colon requirement,
    or a mixed-case mention without a colon would also start matching.
    """
    hits = _scan_text(tmp_path, "FixMe: this is broken")
    assert hits, "'FixMe: this is broken' (mixed-case) must be detected"


def test_bug_lowercase_bare_todo_alone_on_line(tmp_path: Path) -> None:
    """BUG: lowercase bare 'todo' alone on its own line -- combines the
    colon-anchoring defect (test_bug_bare_todo_alone_on_line) with a casing
    permutation TODO's own IGNORECASE flag does not save it from, because the
    root cause here is the missing colon, not case.

    PRECISION RISK: "todo" is an ordinary English word (task list, to-do app);
    prose using it must not be flagged -- see
    test_fp_lowercase_todo_word_in_ordinary_prose below, added here because the
    sibling file's only colon-less-TODO false positive anchor is uppercase.
    """
    hits = _scan_text(tmp_path, "todo")
    assert hits, "a bare lowercase 'todo' alone on a line must be detected"


# ---------------------------------------------------------------------------
# NEW PRECISION ANCHORS -- must stay green forever. Each one is the named risk
# for a MUST-DETECT test above; if a coder's fix flips any of these to non-empty,
# the fix reintroduced the KI-BO-3 defect in a new shape.
# ---------------------------------------------------------------------------


def test_fp_lowercase_fixme_convention_discussion_note(tmp_path: Path) -> None:
    """Named risk for test_bug_lowercase_fixme_with_colon: prose describing the
    convention in lowercase, WITHOUT backtick quoting, must not be flagged.
    """
    hits = _scan_text(
        tmp_path,
        "This convention (fixme: for known low-priority bugs) is sometimes written in lowercase in commit messages.",
    )
    assert hits == [], f"lowercase 'fixme:' discussed as a convention in prose must not be flagged, got: {hits}"


def test_fp_todo_owner_tag_convention_named_in_prose(tmp_path: Path) -> None:
    """Named risk for test_bug_todo_owner_tag_paren_form: prose naming the
    TODO(owner): convention, unquoted, mid-sentence, must not be flagged.
    """
    hits = _scan_text(
        tmp_path,
        "Contributors write comments like TODO(owner): to tag the assignee.",
    )
    assert hits == [], f"the TODO(owner): convention named in prose must not be flagged, got: {hits}"


def test_fp_titlecase_placeholder_starts_a_sentence(tmp_path: Path) -> None:
    """Named risk for test_bug_titlecase_placeholder_with_colon: an ordinary
    sentence that happens to start with the capitalized word "Placeholder" must
    not be flagged.
    """
    hits = _scan_text(tmp_path, "Placeholder text appears when a field is empty.")
    assert hits == [], f"a sentence starting with the word 'Placeholder' must not be flagged, got: {hits}"


def test_fp_lowercase_todo_word_in_ordinary_prose(tmp_path: Path) -> None:
    """Named risk for test_bug_lowercase_bare_todo_alone_on_line: the ordinary
    English word "todo" used mid-sentence (not alone on its line, not at the
    line start) must not be flagged.
    """
    hits = _scan_text(tmp_path, "This todo list app helps you track daily tasks.")
    assert hits == [], f"the ordinary word 'todo' used mid-sentence must not be flagged, got: {hits}"


# ---------------------------------------------------------------------------
# MUST REMAIN GREEN -- sanity checks for cases from the broader "think past the
# list" set that are ALREADY correctly handled today (verified against the
# compiled patterns before writing these). Included so a recall-widening fix
# cannot accidentally regress them; NOT evidence of a bug.
# ---------------------------------------------------------------------------


def test_still_detects_colon_marker_inside_indented_list_item(tmp_path: Path) -> None:
    """A real 'TODO:' marker indented inside a markdown list item (a common
    checklist shape) is already detected today, because the regex searches the
    whole line regardless of a leading bullet -- confirm a recall-widening fix
    does not accidentally scope detection to line-start-only and lose this.
    """
    hits = _scan_text(tmp_path, "- TODO: fix this bullet point before shipping")
    assert hits, "a real 'TODO:' marker inside a list item must still be detected"


def test_still_detects_marker_on_final_line_with_no_trailing_newline(tmp_path: Path) -> None:
    """A marker on the last line of a file with NO trailing newline (the raw
    fixture bytes end mid-line, no \\n) is already handled correctly today
    because str.splitlines() does not require a trailing newline -- confirm this
    keeps working after any recall-floor fix.
    """
    content = "Some introductory text with no marker on it.\nPLACEHOLDER"
    assert not content.endswith("\n"), "fixture must genuinely lack a trailing newline"
    hits = _scan_text(tmp_path, content)
    assert hits and hits[0]["line"] == 2, (
        f"a marker on the final line with no trailing newline must still be detected, got: {hits}"
    )


# ---------------------------------------------------------------------------
# MUST NOT BE DETECTED -- new precision anchors for the "think past the list"
# structural shapes (heading-only doc, table-of-contents-only doc). These are
# NOT bugs to fix; they document that this module's line-level marker regexes
# do not accidentally fire on structural markdown that merely LOOKS like
# unfinished scaffolding (a document that is only headings, or only a TOC, is
# a real and common legitimate document shape, not evidence of an unfilled
# marker -- and per the sibling file's SCOPE NOTE, heading-only/empty-stub
# detection is deliberately a SEPARATE mechanism (documentation-verifier's own
# 6c/6d sub-checks), not part of this module's contract).
# ---------------------------------------------------------------------------


def test_fp_heading_only_document_scans_clean(tmp_path: Path) -> None:
    """A document whose entire body is headings, no prose, no markers, must
    scan clean -- heading-only-stub detection is out of scope for this module.
    """
    content = "# Overview\n\n## Background\n\n## Details\n\n## Next Steps\n"
    hits = _scan_text(tmp_path, content)
    assert hits == [], f"a heading-only document with no markers must scan clean, got: {hits}"


def test_fp_table_of_contents_only_document_scans_clean(tmp_path: Path) -> None:
    """A document that is only a table of contents (a bullet list of links, no
    marker words) must scan clean.
    """
    content = (
        "# Table of Contents\n\n"
        "- [Introduction](#introduction)\n"
        "- [Setup](#setup)\n"
        "- [Usage](#usage)\n"
    )
    hits = _scan_text(tmp_path, content)
    assert hits == [], f"a table-of-contents-only document must scan clean, got: {hits}"


# ---------------------------------------------------------------------------
# CONSIDERED, NOT ASSERTED -- judgement calls from the "think past the list"
# brief that this file deliberately does NOT turn into red MUST-DETECT tests,
# with the reasoning recorded so it isn't silently re-litigated later.
#
# 1. `@todo`, `XXX`, `HACK` -- PROPOSED, not BUG. This module's own docstring
#    enumerates exactly five marker conventions it claims to detect (TODO:,
#    PLACEHOLDER, "Replace with", <!-- QUESTION, FIXME:). None of these three
#    are in that list. Asserting them would be a feature request for new marker
#    vocabulary, not a fix to a claimed-but-broken behaviour -- exactly the
#    "smuggled feature request" the dispatch brief warned against. If a future
#    ticket wants this module to also recognise `@todo`/`XXX`/`HACK`, that
#    belongs in its own ticket with its own false-positive corpus (XXX in
#    particular is a byte sequence that shows up in hex dumps, censored text,
#    and placeholder version numbers ("v1.XXX") -- a real false-positive risk
#    that deserves dedicated analysis, not a drive-by assertion here).
#
# 2. A bare marker word (no colon) indented inside a markdown list item, e.g.
#    "- PLACEHOLDER" used as an unfilled checklist entry -- genuinely a BUG
#    under _is_marker_line's current exact-string-equality check (line.strip()
#    == "PLACEHOLDER" is False for "- PLACEHOLDER"), and NOT one of the six
#    pr-reviewer findings -- a newly discovered gap. It is deliberately NOT
#    asserted as a MUST-DETECT test here because it is very plausibly
#    UNRESOLVABLE at this module's line-level granularity: "- PLACEHOLDER" as an
#    unfilled checklist entry and "- PLACEHOLDER" as one bullet in a list that
#    NAMES the supported markers (the bulleted-list form of the sibling file's
#    test_fp_marker_named_in_a_list_of_scanned_markers) are byte-identical
#    lines with opposite correct verdicts. No per-line structural check can
#    discriminate them; doing so would need multi-line context (e.g. do the
#    sibling bullets look like other marker names, or like prose) that this
#    module's one-hit-per-line architecture does not have. Recorded here as a
#    known limitation for a human decision, not asserted as a red test with no
#    honest path to green.
#
# 3. TODO followed by punctuation other than a colon at the line start (e.g.
#    "TODO - fix this before shipping" with a dash) -- plausible, but not one
#    of the six reproduced forms and not implied by any of them as tightly as
#    the parenthesized-owner form is. Left unasserted rather than guessed at.
# ---------------------------------------------------------------------------
