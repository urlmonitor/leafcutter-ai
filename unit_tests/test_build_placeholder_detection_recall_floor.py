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
# MUST-DETECT (BUG) -- GE-122: PLACEHOLDER is the only marker validator that
# does not use the positional discriminator _is_marker_at_line_start, even
# though _is_bare_todo_marker, _is_replace_with_marker and _is_fixme_marker
# all combine it with their own regex. Verified behaviourally before writing
# this section: '- TODO', '- FIXME: broken', and '- Replace with the real
# value' are each caught today; '- PLACEHOLDER' (the identical bulleted-list
# shape) is not, because _is_placeholder_marker's only fallback past the
# alone-on-line / HTML-comment / colon checks is "return False" -- it never
# consults _is_marker_at_line_start at all. This is an inconsistency between
# markers that share the same validator family, not a deliberate carve-out:
# nothing in _is_placeholder_marker's own docstring argues PLACEHOLDER needs
# weaker positional coverage than its four siblings.
#
# NOTE ON "CONSIDERED, NOT ASSERTED" ITEM 2 BELOW: that item, written for an
# earlier round of this module's hardening, declined to assert this exact
# case as unresolvable -- "- PLACEHOLDER" as an unfilled checklist entry and
# "- PLACEHOLDER" as one bullet in a list naming the supported markers were
# judged byte-identical with opposite correct verdicts, with no per-line
# discriminator available. GE-122 revisits that judgement: TODO already pays
# this exact cost today ('- TODO' is caught unconditionally via
# _is_bare_todo_marker's identical use of _is_marker_at_line_start), and the
# one real instance of the false-positive shape found in this repository
# (tickets/99_done/EPIC-AcPipelineDeployGaps/done/
# 05_fix_build_ac_script_invocation_paths.md:190, "1. Placeholder not
# substituted...") is trivially silenced with backticks. The false NEGATIVE
# this trades against -- a bare, unfilled PLACEHOLDER checklist entry sailing
# through -- is judged the strictly worse failure. See
# test_fp_placeholder_named_in_a_list_is_now_an_accepted_cost below for the
# false positive this decision knowingly accepts, recorded rather than hidden.
# ---------------------------------------------------------------------------


def test_bug_placeholder_dash_bullet_no_colon(tmp_path: Path) -> None:
    """BUG (GE-122): '- PLACEHOLDER' -- a bare PLACEHOLDER marker as a dash-
    bulleted, unfilled checklist entry -- is invisible today because
    _is_placeholder_marker never falls back to _is_marker_at_line_start the
    way _is_bare_todo_marker/_is_replace_with_marker/_is_fixme_marker do.

    PRECISION RISK: the accepted cost is a list item that legitimately opens
    with the word "Placeholder" in prose, e.g. the real repository instance
    "1. Placeholder not substituted (template not compiled through
    `inject_config`) ->" -- see
    test_fp_placeholder_named_in_a_list_is_now_an_accepted_cost below, which
    pins that this specific real line is NOW flagged (an accepted,
    documented trade, not an oversight) once the fix lands.
    """
    hits = _scan_text(tmp_path, "- PLACEHOLDER")
    assert hits, "'- PLACEHOLDER' (bare marker, dash-bulleted checklist entry) must be detected"


def test_bug_placeholder_asterisk_bullet_no_colon(tmp_path: Path) -> None:
    """BUG (GE-122): '* PLACEHOLDER' -- the asterisk-bullet sibling of the
    dash form above; _LEADING_MARKER_PREFIX already treats '-', '*', and '+'
    identically, so this is the same defect on a different bullet glyph.
    """
    hits = _scan_text(tmp_path, "* PLACEHOLDER")
    assert hits, "'* PLACEHOLDER' (bare marker, asterisk-bulleted checklist entry) must be detected"


def test_bug_placeholder_plus_bullet_no_colon(tmp_path: Path) -> None:
    """BUG (GE-122): '+ PLACEHOLDER' -- the '+' bullet sibling, completing the
    three list-item glyphs _LEADING_MARKER_PREFIX already recognises.
    """
    hits = _scan_text(tmp_path, "+ PLACEHOLDER")
    assert hits, "'+ PLACEHOLDER' (bare marker, plus-bulleted checklist entry) must be detected"


def test_bug_placeholder_ordinal_dot_bullet_no_colon(tmp_path: Path) -> None:
    """BUG (GE-122): '1. PLACEHOLDER' -- the ordinal-list form ("1.") that
    _LEADING_MARKER_PREFIX's \\d+[.)] alternative already recognises for
    every OTHER marker's positional check.
    """
    hits = _scan_text(tmp_path, "1. PLACEHOLDER")
    assert hits, "'1. PLACEHOLDER' (bare marker, dot-ordinal checklist entry) must be detected"


def test_bug_placeholder_ordinal_paren_bullet_no_colon(tmp_path: Path) -> None:
    """BUG (GE-122): '1) PLACEHOLDER' -- the parenthesis-ordinal sibling of
    the dot-ordinal form above.
    """
    hits = _scan_text(tmp_path, "1) PLACEHOLDER")
    assert hits, "'1) PLACEHOLDER' (bare marker, paren-ordinal checklist entry) must be detected"


def test_bug_placeholder_indented_dash_bullet_no_colon(tmp_path: Path) -> None:
    """BUG (GE-122): '  - PLACEHOLDER' -- an indented dash-bulleted entry (a
    nested checklist item), confirming the leading-whitespace half of
    _LEADING_MARKER_PREFIX is exercised too, not just an unindented bullet.
    """
    hits = _scan_text(tmp_path, "  - PLACEHOLDER")
    assert hits, "'  - PLACEHOLDER' (indented, bare marker checklist entry) must be detected"


def test_bug_placeholder_lowercase_bullet_no_colon(tmp_path: Path) -> None:
    """BUG (GE-122): '- placeholder' -- the lowercase form of the same
    bulleted, colon-less defect; PLACEHOLDER's regex is already
    re.IGNORECASE, so only the missing positional fallback stands between
    this and detection.

    PRECISION RISK: this is the same phrase, same case, as
    test_fp_placeholder_word_in_ordinary_prose's "the placeholder detection
    step scans for markers left unfilled." in the sibling file -- but that
    string is never the first content on its line (it opens with "the "), so
    a positional fix that requires _is_marker_at_line_start cannot conflate
    the two.
    """
    hits = _scan_text(tmp_path, "- placeholder")
    assert hits, "'- placeholder' (lowercase, bare marker checklist entry) must be detected"


def test_bug_placeholder_titlecase_with_colon_bulleted(tmp_path: Path) -> None:
    """RECALL (GE-122) sanity check -- NOT actually red: '- Placeholder: fill
    this in' is already caught today via _is_placeholder_marker's existing
    colon check (the colon sits immediately after the matched word,
    independent of the bullet prefix). Included here, alongside the bare-
    word forms above, because the GE-122 dispatch names it explicitly as
    part of the same recall list; kept green by the fix as a "must remain
    detected" anchor on the colon branch the fix does not touch.
    """
    hits = _scan_text(tmp_path, "- Placeholder: fill this in")
    assert hits, "'- Placeholder: fill this in' (bulleted, colon-anchored marker) must be detected"


def test_bug_placeholder_real_world_announced_but_unwritten_anchor(tmp_path: Path) -> None:
    """RECALL, real-world anchor (GE-122) -- NOT actually red either, for the
    same reason as the titlecase-with-colon case immediately above: the real
    line from templates/skills/write-c4-diagram/SKILL.md:505,
    "- Placeholder: L1, L2, L4 examples will be added as Phase 5 tickets
    land.", is a GENUINE announced-but-unwritten marker (Phase 5 has not
    landed as of this writing) and is the single strongest real-world
    justification for treating PLACEHOLDER's positional gap as a defect
    worth fixing at all -- but it already scans as a hit today because its
    colon sits immediately after the matched word, via the pre-existing
    colon branch, independent of the bullet-prefix bug this section's other
    BUG tests pin. Kept here, verbatim, as the anchor that motivated this
    whole section, and as a regression pin: any future change to the colon
    branch must not stop catching it.
    """
    hits = _scan_text(
        tmp_path,
        "- Placeholder: L1, L2, L4 examples will be added as Phase 5 tickets land.",
    )
    assert hits, (
        "the real, currently-true announced-but-unwritten line from "
        "templates/skills/write-c4-diagram/SKILL.md:505 must be detected"
    )


def test_fp_placeholder_named_in_a_list_is_now_an_accepted_cost(tmp_path: Path) -> None:
    """ACCEPTED COST (GE-122) -- documents, rather than hides, the false
    positive the fix knowingly introduces: the real repository line
    tickets/99_done/EPIC-AcPipelineDeployGaps/done/
    05_fix_build_ac_script_invocation_paths.md:190, "1. Placeholder not
    substituted (template not compiled through `inject_config`) ->", is
    ordinary prose that happens to open a numbered list item with the word
    "Placeholder". After the GE-122 fix it WILL be flagged, because it is
    positionally indistinguishable from a genuine unfilled ordinal-list
    marker. This is deliberately NOT a "must not be detected" test -- it is
    the opposite: a record that this specific false positive is judged
    acceptable (trivially silenced with backticks) against the false
    negative it prevents (a bare PLACEHOLDER checklist entry sailing
    through). Asserted as `hits` (truthy) so a future attempt to special-
    case this exact line back to clean is visibly a scope decision, not a
    silent regression.
    """
    hits = _scan_text(
        tmp_path,
        "1. Placeholder not substituted (template not compiled through `inject_config`) ->",
    )
    assert hits, (
        "GE-122 accepts this as a false positive going forward -- prose opening a "
        "numbered list item with 'Placeholder' is now flagged, same as any other "
        "ordinal-bulleted bare marker; got no hits, meaning the positional fix was "
        "not applied (or was applied with an unwanted carve-out)"
    )


# ---------------------------------------------------------------------------
# CONSISTENCY (GE-122) -- the test that would have caught the original
# defect: every marker convention this module claims to detect must catch
# the same bulleted-list-item shape. This is deliberately NOT limited to
# PLACEHOLDER -- had this exact parametrization existed already, the fact
# that PLACEHOLDER was the ONLY one of five that failed it would have been
# impossible to ship silently.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("marker_name", "content"),
    [
        ("todo", "- TODO"),
        ("placeholder", "- PLACEHOLDER"),
        ("fixme", "- FIXME: broken"),
        ("replace_with", "- Replace with the real value"),
        ("question_html_comment", "- <!-- QUESTION: is this covered? -->"),
    ],
)
def test_consistency_bullet_prefixed_form_detected_for_every_marker_convention(
    tmp_path: Path, marker_name: str, content: str
) -> None:
    """CONSISTENCY (GE-122) -- the test that would have caught the original
    defect. All five marker conventions this module's own docstring claims
    to detect (TODO:, PLACEHOLDER, "Replace with", <!-- QUESTION, FIXME:)
    must catch the identical dash-bulleted-list-item shape. Verified
    behaviourally before this fix: TODO, FIXME, Replace-with and the
    QUESTION HTML-comment form are ALL caught in this shape today;
    PLACEHOLDER alone is missed -- confirming it, and only it, skips the
    positional discriminator its four siblings share. Parametrized (rather
    than five independent tests) specifically so a future regression that
    silently drops parity for any ONE marker fails in the same place this
    one would have.
    """
    hits = _scan_text(tmp_path, content, filename=f"{marker_name}.md")
    assert hits, f"a bullet-prefixed {content!r} must be detected for the {marker_name} convention"


# ---------------------------------------------------------------------------
# MUST-DETECT (BUG) -- GE-122, HTML-comment marker parity: _is_placeholder_marker
# has a dedicated `<!--\s*PLACEHOLDER\b` branch that no sibling validator shares,
# so the identical HTML-comment-wrapped scaffolding shape ('<!-- TODO -->',
# '<!-- FIXME -->', '<!-- Replace with ... -->') escapes detection for every
# OTHER marker. Verified behaviourally before writing this section against the
# compiled patterns: PLACEHOLDER's HTML-comment form is caught unconditionally;
# the other three fall through to _is_marker_at_line_start (or, for FIXME, have
# no bare/colon-less rule to fall through to at all), which rejects '<!-- ' as a
# prefix -- it is neither whitespace nor a bullet/ordinal -- so they are missed
# regardless of case. This is the identical shape of asymmetry the bullet-prefix
# CONSISTENCY section above found for a different positional gap: PLACEHOLDER's
# ad hoc branch papers over ONE shape (HTML comments) while its siblings' shared
# positional discriminator papers over ANOTHER (bullets); a real fix should give
# every marker BOTH, not add yet another one-off branch.
#
# THE BOUNDARY THAT MUST NOT MOVE: '<!-- QUESTION -->' (no colon) stays CLEAN --
# that asymmetry is deliberate (see _MARKER_RULES' own comment: the QUESTION
# pattern requires a trailing colon specifically so the colon-less form can be
# used to show the comment CONVENTION as a worked example, not a real question).
# Do not fold QUESTION into a "bare HTML-comment form must be detected" fix --
# see test_fp_question_html_comment_without_colon_stays_clean in the sibling
# file for the pinned precision anchor.
#
# Blast radius checked before writing this section:
# `grep -rniE "<!--\s*(TODO|FIXME|Replace with)" docs/ templates/ tickets/`
# returns matches ONLY in templates/CLAUDE.md.template and
# templates/ANTIGRAVITY.md.template, and every one of those already carries a
# colon ('<!-- TODO: fill in ... -->') -- i.e. they are already caught today via
# the pre-existing colon-anchored `\bTODO\s*:` rule, which has no positional
# check at all, so this widening (which only changes the colon-LESS, bare form)
# does not add any new hit there. tickets/ and docs/ have zero matches of any
# form. Closing this gap therefore creates no new false positive anywhere in
# this repository.
# ---------------------------------------------------------------------------


def test_bug_html_comment_bare_todo_no_colon(tmp_path: Path) -> None:
    """BUG: '<!-- TODO -->' -- the bare TODO regex matches inside the comment,
    but _is_bare_todo_marker's _is_marker_at_line_start check rejects '<!-- '
    as a prefix (neither whitespace nor a bullet/ordinal), so this identical
    scaffolding shape to '<!-- PLACEHOLDER -->' (already caught via
    PLACEHOLDER's dedicated branch) is missed for TODO.

    PRECISION RISK: none beyond the QUESTION boundary noted in the section
    docstring above -- a positional/HTML-comment-aware fix for TODO must not
    also start flagging '<!-- QUESTION -->' (no colon), which stays clean by
    design.
    """
    hits = _scan_text(tmp_path, "<!-- TODO -->")
    assert hits, "'<!-- TODO -->' (HTML-comment-wrapped bare TODO) must be detected"


def test_bug_html_comment_bare_todo_lowercase(tmp_path: Path) -> None:
    """BUG: '<!-- todo -->' -- lowercase form of the same defect; TODO's bare
    regex is already re.IGNORECASE, so only the positional gap stands between
    this and detection.
    """
    hits = _scan_text(tmp_path, "<!-- todo -->")
    assert hits, "'<!-- todo -->' (lowercase, HTML-comment-wrapped) must be detected"


def test_bug_html_comment_bare_fixme_no_colon(tmp_path: Path) -> None:
    """BUG: '<!-- FIXME -->' -- FIXME has no bare (colon-less) regex at all
    (unlike TODO, which has both a colon-anchored and a bare rule), so a
    colon-less FIXME is invisible regardless of position. Closing this
    requires giving FIXME (and "Replace with") the same bare-marker coverage
    TODO already has, not just a positional fix.
    """
    hits = _scan_text(tmp_path, "<!-- FIXME -->")
    assert hits, "'<!-- FIXME -->' (HTML-comment-wrapped bare FIXME) must be detected"


def test_bug_html_comment_bare_fixme_lowercase(tmp_path: Path) -> None:
    """BUG: '<!-- fixme -->' -- lowercase form of the same defect."""
    hits = _scan_text(tmp_path, "<!-- fixme -->")
    assert hits, "'<!-- fixme -->' (lowercase, HTML-comment-wrapped) must be detected"


def test_bug_html_comment_replace_with_no_colon(tmp_path: Path) -> None:
    """BUG: '<!-- Replace with the real thing -->' -- "Replace with" always
    defers to _is_marker_at_line_start (it has no default/colon-anchored
    variant at all), which rejects the '<!-- ' prefix the same way it rejects
    every other non-bullet, non-whitespace prefix.
    """
    hits = _scan_text(tmp_path, "<!-- Replace with the real thing -->")
    assert hits, "'<!-- Replace with the real thing -->' (HTML-comment-wrapped) must be detected"


def test_bug_html_comment_bare_todo_indented(tmp_path: Path) -> None:
    """BUG: '  <!-- TODO -->' -- an indented HTML comment, the shape an HTML
    comment commonly takes when nested inside a markdown list item. Leading
    whitespace alone does not help: _LEADING_MARKER_PREFIX allows whitespace
    before a bullet/ordinal, but the match still sits after '<!-- ', not
    after only whitespace, so the positional check still rejects it.
    """
    hits = _scan_text(tmp_path, "  <!-- TODO -->")
    assert hits, "'  <!-- TODO -->' (indented, HTML-comment-wrapped) must be detected"


def test_bug_html_comment_bare_fixme_indented(tmp_path: Path) -> None:
    """BUG: '  <!-- FIXME -->' -- the indented sibling of the FIXME case above."""
    hits = _scan_text(tmp_path, "  <!-- FIXME -->")
    assert hits, "'  <!-- FIXME -->' (indented, HTML-comment-wrapped) must be detected"


def test_bug_html_comment_todo_bare_with_trailing_text(tmp_path: Path) -> None:
    """BUG: '<!-- TODO wire this up -->' -- trailing instructional text, no
    colon at all. Same defect as the bare '<!-- TODO -->' case above; included
    separately because trailing prose after the marker (rather than a bare
    marker alone) is the more common real-world scaffolding shape.
    """
    hits = _scan_text(tmp_path, "<!-- TODO wire this up -->")
    assert hits, "'<!-- TODO wire this up -->' (HTML-comment-wrapped, trailing text, no colon) must be detected"


def test_still_detects_html_comment_todo_with_colon_and_trailing_text(tmp_path: Path) -> None:
    """RECALL sanity check -- NOT actually red: '<!-- TODO: wire this up -->'
    is already caught today, because the colon-anchored `\\bTODO\\s*:` pattern
    matches regardless of position (its validator, _default_validator, only
    excludes inline code) -- the colon, not the comment wrapper, is what makes
    this one already work. Included alongside the colon-less forms above so a
    fix to the positional/bare-marker gap cannot be mistaken for also being
    required here; a regression on this specific shape would mean the fix
    broke the pre-existing colon-anchored path, not that it failed to widen
    recall.
    """
    hits = _scan_text(tmp_path, "<!-- TODO: wire this up -->")
    assert hits, "'<!-- TODO: wire this up -->' (colon-anchored, already-caught form) must be detected"


# ---------------------------------------------------------------------------
# CONSISTENCY (GE-122, HTML-comment parity) -- the test that would have caught
# the original defect. Mirrors test_consistency_bullet_prefixed_form_detected_
# for_every_marker_convention above, for the HTML-comment shape instead of the
# bullet-prefix shape.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("marker_name", "content"),
    [
        ("todo", "<!-- TODO -->"),
        ("placeholder", "<!-- PLACEHOLDER -->"),
        ("fixme", "<!-- FIXME -->"),
        ("replace_with", "<!-- Replace with the real thing -->"),
    ],
)
def test_consistency_html_comment_form_detected_for_every_marker_convention(
    tmp_path: Path, marker_name: str, content: str
) -> None:
    """CONSISTENCY (GE-122, HTML-comment parity) -- the test that would have
    caught the original defect. Every marker convention this module's own
    docstring claims to detect must catch the identical bare, colon-less
    HTML-comment shape. Verified behaviourally before writing this test:
    PLACEHOLDER alone is caught here today, via its own one-off
    `<!--\\s*PLACEHOLDER\\b` branch; TODO, FIXME, and Replace-with are all
    missed, confirming PLACEHOLDER's dedicated branch is covering a gap its
    three siblings never got. QUESTION is deliberately excluded from this
    parametrization: unlike the other four, QUESTION's own convention
    REQUIRES a trailing colon by design (the colon-less '<!-- QUESTION -->'
    form is how prose shows the comment convention as a worked example, not a
    real marker) -- see test_fp_question_html_comment_without_colon_stays_clean
    in the sibling file for that pinned boundary. Mirrors
    test_consistency_bullet_prefixed_form_detected_for_every_marker_convention
    above, which pins the identical kind of asymmetry for a different
    positional shape.
    """
    hits = _scan_text(tmp_path, content, filename=f"{marker_name}_html_comment.md")
    assert hits, f"an HTML-comment-wrapped {content!r} must be detected for the {marker_name} convention"


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
# GE-122b (bullet-required precision fix, 2026-08-25) -- RECALL FLOOR ANCHOR.
# The OPTIONAL-bullet widening above (this whole file) was itself found to be
# a precision bug: `_LEADING_MARKER_PREFIX`'s bullet/ordinal group is
# optional, so bare indentation with no bullet at all also qualified,
# false-positiving 23 real wrapped-prose lines repo-wide (see the sibling
# context-discrimination file's "GE-122b PRECISION REGRESSION" section for
# the full accounting). The fix REQUIRES an actual bullet or ordinal for
# PLACEHOLDER's positional path specifically -- TODO/FIXME/"Replace with"
# keep the pre-existing optional-bullet form untouched (out of scope; no
# repo-wide evidence they need tightening).
#
# This single parametrized test collects the nine genuine bulleted/ordinal
# PLACEHOLDER forms already pinned individually above (each already has its
# own dedicated test in this file) into one place, tagged as the concrete
# "detect 9/9" half of the verified arithmetic that justified the fix:
#
#     OPTIONAL (before)   detect 9/9   false-positive 10/10 (wrapped prose)
#     REQUIRED (after)    detect 9/9   false-positive  0/10
#
# Every one of these nine carries a REAL bullet or ordinal, so tightening the
# positional check from "optional bullet" to "required bullet" costs nothing
# here -- this test is ALREADY GREEN today (the optional rule is a superset of
# the required one) and must STAY green after the tightening lands. If a
# future editor's "fix" to the precision bug ever turns any of these red, the
# editor over-corrected by requiring more than a bullet/ordinal (e.g.
# accidentally also demanding a colon), which would reopen the exact recall
# hole GE-122's original positional fix closed.
#
# THE LESSON: measuring a widening's cost from a grep that only covers one
# shape (here: "does a bulleted false positive exist?") cannot tell you
# whether the fix ALSO introduced a wider, unbulleted false-positive shape
# nobody grepped for. The only measurement that catches that is a repo-wide
# before/after diff -- see the sibling file's canary test for the one that
# actually would have caught this regression before it shipped.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        "- PLACEHOLDER",
        "* PLACEHOLDER",
        "+ PLACEHOLDER",
        "1. PLACEHOLDER",
        "1) PLACEHOLDER",
        "  - PLACEHOLDER",
        "- placeholder",
        "- Placeholder: fill this in",
        "- Placeholder: L1, L2, L4 examples will be added as Phase 5 tickets land.",
    ],
)
def test_ge122b_bullet_required_recall_floor_all_nine_forms_still_caught(tmp_path: Path, content: str) -> None:
    # covers: UNKNOWN
    """GE-122b recall-floor anchor: all nine genuine bulleted/ordinal
    PLACEHOLDER forms -- the "detect 9/9" half of the verified arithmetic
    that justifies requiring an actual bullet/ordinal instead of bare
    indentation -- must remain detected once that tightening lands. This is
    NOT a red test on arrival (every form here already carries a real bullet
    or ordinal, so today's looser OPTIONAL rule already catches all nine);
    it is a floor that a future precision fix must not fall below.
    """
    hits = _scan_text(tmp_path, content)
    assert hits, f"{content!r} carries a real bullet/ordinal and must remain a detected PLACEHOLDER marker, got: {hits}"


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
# 2. RESOLVED BY GE-122 -- superseded, kept for history. A bare marker word (no
#    colon) indented inside a markdown list item, e.g. "- PLACEHOLDER" used as
#    an unfilled checklist entry, was judged UNRESOLVABLE here: "- PLACEHOLDER"
#    as an unfilled checklist entry and "- PLACEHOLDER" as one bullet in a list
#    that NAMES the supported markers were judged byte-identical lines with
#    opposite correct verdicts, with no per-line structural check able to tell
#    them apart. GE-122 revisits this: TODO already pays the identical cost
#    unconditionally today ('- TODO' is caught via _is_bare_todo_marker's use
#    of _is_marker_at_line_start, with no carve-out for a bulleted list that
#    NAMES the markers), so leaving PLACEHOLDER as the one exception was an
#    inconsistency, not a considered trade honoured elsewhere. The decision is
#    now: accept the false positive (a list item that opens with the word
#    "Placeholder" in prose is flagged) in exchange for eliminating the false
#    negative (a bare, unfilled PLACEHOLDER checklist entry sailing through) --
#    see the "MUST-DETECT (BUG) -- GE-122" section above for the asserted red
#    tests and test_fp_placeholder_named_in_a_list_is_now_an_accepted_cost for
#    the false positive this now knowingly accepts.
#
# 3. TODO followed by punctuation other than a colon at the line start (e.g.
#    "TODO - fix this before shipping" with a dash) -- plausible, but not one
#    of the six reproduced forms and not implied by any of them as tightly as
#    the parenthesized-owner form is. Left unasserted rather than guessed at.
# ---------------------------------------------------------------------------
