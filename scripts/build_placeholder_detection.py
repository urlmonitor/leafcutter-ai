"""
MODULE: build_placeholder_detection
GOAL: Post-build scan that detects TODO/PLACEHOLDER markers in generated files
    and reports them so the onboard agent can surface them to the user.
BUSINESS CONTEXT: build.py writes files like docs/vision.md and docs/roadmap.json
    with placeholder content (e.g. "TODO: Replace with..."). Without detection,
    the onboard agent sees "file exists" and moves on, leaving stale placeholders
    that confuse downstream agents.
ARCHITECTURE: Single public function scan_for_placeholders() that walks a set of
    output paths and returns a list of PlaceholderHit dicts. Called by build.py as
    a post-build phase; results are passed to the onboard agent for user reporting.
    Also invoked directly by templates/agents/documentation-verifier.md Step 6a via
    a `python3 -c` one-liner, so the return shape (list of dicts with keys `path`,
    `line`, `marker`, `context`) is a cross-surface contract -- do not rename or
    drop those keys without updating that template's parsing instructions too.

    Each marker convention is matched by a regex PLUS a validator function (see
    _MARKER_RULES). The validator exists to discriminate a genuine, unresolved
    scaffolding marker from the same literal word/phrase used in ordinary prose
    that DISCUSSES this detection mechanism -- see
    unit_tests/test_build_placeholder_detection_context_discrimination.py for the
    false-positive corpus this logic eliminates, and the "must still detect a real
    marker" tests in the same file that pin the floor this logic must not fall
    below.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

_INLINE_CODE_SPAN = re.compile(r"`[^`]*`")


def _is_within_inline_code(line: str, start: int, end: int) -> bool:
    """Return True when the [start, end) match span sits fully inside a
    single-backtick inline-code span on `line`.

    Inline code (`` `TODO:` ``) is how prose SHOWS a marker as a worked
    example without leaving one behind -- a real, unresolved marker a
    contributor forgot to remove is essentially never wrapped in backticks,
    so excluding inline-code matches is a safe, narrow cut. This deliberately
    does NOT exclude triple-backtick fenced blocks: a whole fenced sample can
    legitimately contain scaffolding someone forgot to fill in, and each line
    is evaluated independently here, so a multi-line fence is never treated
    as a single suppressed span.
    """
    for span in _INLINE_CODE_SPAN.finditer(line):
        if span.start() <= start and end <= span.end():
            return True
    return False


def _is_marker_line(line: str, match: re.Match[str]) -> bool:
    """Return True when the matched marker text is the entire (whitespace-
    stripped) line.

    A bare marker word alone on its own line is the classic unfilled-
    scaffolding shape (e.g. a lone `PLACEHOLDER` line left after a template
    was copied, or a lone `TODO` left when a section was stubbed out).
    Prose that mentions the same word is never the ENTIRE line -- it sits
    inside a sentence with surrounding words -- so this check discriminates
    the two. Comparing against `match.group(0)` (the exact text the regex
    found) rather than a hardcoded literal means this stays correct for any
    casing the now-IGNORECASE marker regexes match, with no separate
    case-fold step needed.
    """
    return line.strip() == match.group(0)


# A marker preceded by nothing but whitespace and, optionally, a single
# leading list-item bullet ("-", "*", "+") or ordinal ("1.", "2)") is
# structurally the START of the line's real content -- the shape a genuine,
# unresolved marker takes when someone leaves it at the top of a stubbed
# section or a checklist item. Prose that NAMES or DISCUSSES the same marker
# is never the first thing on its line -- there is always a lead-in clause
# or surrounding words before it -- so this discriminates a real marker from
# a mid-sentence mention without relying on letter case at all. This is the
# positional half of the case-insensitivity fix below: "replace with the
# real description" (a genuine marker) and "...replace with a value that
# matches your conventions." (ordinary prose) are the identical phrase in
# the identical case, differing ONLY in line position -- IGNORECASE alone
# cannot tell them apart, so several validators below combine it with this
# check instead of the colon anchor TODO:/FIXME: use.
_LEADING_MARKER_PREFIX = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*")


def _is_marker_at_line_start(line: str, start: int) -> bool:
    """Return True when only whitespace/bullet syntax precedes `start`."""
    return _LEADING_MARKER_PREFIX.fullmatch(line[:start]) is not None


# GE-122b: the PLACEHOLDER-only sibling of _LEADING_MARKER_PREFIX above, with the
# bullet/ordinal alternation REQUIRED rather than optional. _LEADING_MARKER_PREFIX's
# trailing `?` lets bare indentation (whitespace with no bullet or ordinal at all)
# qualify as "marker position" -- harmless for TODO/FIXME/"Replace with" (no repo-wide
# evidence of a false-positive cost), but for PLACEHOLDER it turned every indented,
# line-wrapped prose paragraph that happens to start with the word "placeholder" into
# a false positive. A real repo-wide before/after scan (committed HEAD vs working
# tree, 4815 files) measured this precisely: BEFORE 72 hits / AFTER 94 / 24 NEW / 2
# REMOVED, with 23 of the 24 new hits being wrapped-prose false positives across 12 AC
# YAML files, 4 agent templates, a generated agent card, 4 tickets, and 2 skill docs.
# The verified arithmetic for the fix: the OPTIONAL rule detects 9/9 genuine
# bulleted/ordinal PLACEHOLDER markers but false-positives on 10/10 representative
# wrapped-prose samples; REQUIRING an actual bullet/ordinal keeps the identical 9/9
# detection rate while dropping false positives to 0/10 -- there is no recall cost
# measured anywhere in this repository, only a precision gain. See
# unit_tests/test_build_placeholder_detection_context_discrimination.py's "GE-122b
# PRECISION REGRESSION" section and unit_tests/test_build_placeholder_detection_recall_floor.py's
# "GE-122b (bullet-required precision fix)" section for the full test coverage this
# regex and its helper below satisfy.
_LEADING_BULLET_REQUIRED = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _is_marker_after_bullet(line: str, start: int) -> bool:
    """Return True when only whitespace followed by a REQUIRED bullet/ordinal
    (`-`, `*`, `+`, `1.`, `1)`) precedes `start` -- bare indentation with no
    bullet or ordinal at all does NOT qualify.

    This is PLACEHOLDER's stricter positional check (GE-122b), a sibling of
    _is_marker_at_line_start used by every other marker validator. See
    _LEADING_BULLET_REQUIRED's own comment for why PLACEHOLDER alone needs the
    bullet to be mandatory rather than optional.
    """
    return _LEADING_BULLET_REQUIRED.fullmatch(line[:start]) is not None


# An HTML comment opener (`<!--`) plus optional whitespace, anchored to the END
# of whatever text precedes the marker match -- i.e. "nothing sits between the
# comment opener and the marker except optional whitespace". Anchoring with `$`
# against `line[:match.start()]` (rather than a per-marker literal like the old
# `<!--\s*PLACEHOLDER\b` regex) is what lets every marker share ONE
# implementation: the check is defined purely in terms of "what comes right
# before this match", not "this specific marker word following `<!--`". See
# _is_within_html_comment_marker for the GE-122 rationale.
_HTML_COMMENT_OPENER_IMMEDIATELY_BEFORE = re.compile(r"<!--\s*$")


# BO-2200b-3-ii: quoting a marker is not carrying one.
#
# MEASURED PER MARKER, BEFORE AND AFTER. Recorded here because the defect this
# fixes was not a bad regex — it was a false-positive cost measured for
# PLACEHOLDER (2 hits) and asserted for all six markers, which left the marker
# responsible for two thirds of all hits untightened while the comment claimed
# there was nothing to gain. Repeating that as one aggregate number would
# reproduce the defect in a new place. Scan of 5,634 md/yaml files, this repo:
#
#     marker            before   after   delta
#     todo:                 31      22      -9
#     todo (bare)           16      12      -4
#     <!-- question:        16      16       0
#     replace with           3       3       0
#     placeholder            2       2       0
#     TOTAL                 68      55     -13
#
# All 13 removals were verified individually as false positives: Mermaid state
# transitions, count fields, quoted grep evidence, and Gherkin lines naming the
# markers — every one of them inside a fence or after heading text. Zero genuine
# markers were lost; the one case that WAS initially lost
# (ui-context.template.md:39) is why the heading rule starts at `##`.
#
# Note what the numbers do NOT show: `placeholder` is unchanged at 2, so the
# emphasis fix below has no measured effect on this corpus. It was found by
# probing rather than in the wild and is pinned by test, not by this table. Say
# so rather than implying the table validates it.
#
# The two rules below are LINE-CONTEXT rules, applied to every marker before its
# own validator runs. They are deliberately NOT positional rules on the marker
# itself -- see the warning in _is_marker_in_reportable_context about why a
# positional rule on `TODO:` would be the wrong fix.
#
# A fenced block is the block-level form of the inline-code (`backtick`)
# exemption the validators already apply. It cannot be recognised per-line: the
# scan loop has to carry the open/closed state across lines, which is why this
# lives in _scan_text_for_placeholders rather than in a validator.
#
# A fence must be CLOSED BY THE SAME CHARACTER it was opened with. That is real
# markdown, and it is also load-bearing here rather than pedantry: the
# commit-guardian register quotes a compiler diagnostic inside a ``` block whose
# caret line reads `~~~~~~~~~~~~~~~~~~^~~`. A rule that treats any ``` or ~~~ run
# as a delimiter counts that line as a fence, inverts the open/closed parity for
# the remaining ~1100 lines of the file, and re-reports every marker the fence
# rule was added to suppress. The first version of this fix did exactly that and
# the real-register test caught it -- a synthetic fixture would not have, because
# nobody writes a stray caret underline into a fixture.
_FENCE_DELIMITER = re.compile(r"^\s*(?P<fence>`{3,}|~{3,})")

# A marker sitting AFTER other heading text is part of a title. One that OPENS
# the heading text is a stub and must still be reported -- a blanket heading
# exclusion would let `## TODO: fill this in` through.
#
# LEVEL 2 AND DEEPER ONLY, and that bound is deliberate. A single `#` is
# indistinguishable from a comment in YAML, shell, Python and the YAML-ish blocks
# markdown templates embed. Including H1 dropped a genuine marker in
# `templates/docs/ui-context.template.md:39`:
#
#       # - TODO: add your own design/brand/style-guide doc path(s) here, if any.
#
# -- a commented-out list item in a config template, where `# ` parsed as the
# heading and the TODO sat after it. `##`..`######` carry no such ambiguity. The
# cost of the bound is a residual false positive on an H1 whose *title* mentions a
# marker after other words; that shape does not occur in this repo, and it is the
# cheaper of the two errors: a missed marker ships a stub, a spurious one is
# merely noise. (BO-2200b-3-ii.)
_MARKDOWN_HEADING = re.compile(r"^\s*#{2,6}\s+")


def _is_marker_in_reportable_context(line: str, start: int) -> bool:
    """Return False when the line's own shape makes this marker a quotation.

    Applies to EVERY marker, ahead of the per-marker validator.

    WARNING TO A FUTURE EDITOR. The heading rule below exists because
    `### KI-BO-021 -- TODO: ...` was reported as a stub. The tempting cure is
    to require `TODO:` to sit at a marker position (line start, after a bullet,
    after a comment introducer). Do NOT do that. The gate's single most
    important true positive is the roadmap sentinel a freshly installed
    CLAUDE.md carries:

        Current outcome: TODO: Replace with the single must-achieve outcome ...

    Its marker is mid-line after ordinary prose, so any positional rule on the
    colon markers silently drops it. That case is pinned by
    test_canonical_mid_line_todo_marker_still_reported precisely so this
    reasoning cannot be lost. (BO-2200b-3-ii, KI-CG-033.)

    Args:
        line: The full source line.
        start: Index in `line` where the marker match begins.

    Returns:
        True when the marker may be reported subject to its own validator.
    """
    heading = _MARKDOWN_HEADING.match(line)
    if heading is not None:
        return start == heading.end()
    return True


def _is_within_html_comment_marker(line: str, match: re.Match[str]) -> bool:
    """Return True when `match` is the first real content inside an HTML
    comment opener (`<!--` plus optional whitespace) on `line`.

    GE-122: `_is_placeholder_marker` used to be the ONLY validator with a
    dedicated `<!--\\s*PLACEHOLDER\\b` branch, so the identical HTML-comment-
    wrapped scaffolding shape ('<!-- TODO -->', '<!-- FIXME -->', '<!--
    Replace with ... -->') escaped detection for every OTHER marker: none of
    them had an equivalent branch, and `_is_marker_at_line_start` rejects
    '<!-- ' as a prefix outright (it is neither whitespace nor a bullet/
    ordinal). That per-marker literal regex was itself the defect -- a
    hardcoded pattern for one marker cannot be kept in sync with its
    siblings by construction. This helper instead derives the check from
    `match.start()` and the text before it, so `_is_bare_todo_marker`,
    `_is_fixme_marker`, `_is_replace_with_marker`, and
    `_is_placeholder_marker` all consult the exact same implementation and
    cannot drift apart again.

    Deliberately does NOT special-case QUESTION: that marker's own regex
    (`<!--\\s*QUESTION\\s*:`) already requires a trailing colon, which is
    what keeps the colon-less '<!-- QUESTION -->' worked-example form clean
    by design -- QUESTION is matched via `_default_validator`, which never
    calls this helper, so that boundary is untouched here.
    """
    return _HTML_COMMENT_OPENER_IMMEDIATELY_BEFORE.search(line[: match.start()]) is not None


def _is_placeholder_marker(line: str, match: re.Match[str]) -> bool:
    """Validator for the PLACEHOLDER marker.

    PLACEHOLDER has no natural trailing punctuation the way TODO:/FIXME: do,
    so a bare `\\bPLACEHOLDER\\b` regex also matches the ordinary English word
    ("the placeholder detection step...") and even an ALL-CAPS mention in a
    sentence that lists marker names ("...and PLACEHOLDER."). Case alone
    cannot separate those last two -- both are spelled identically in caps.

    A PRIOR version of this validator tried to resolve that with a bare
    trailing-colon test (`line[match.end():match.end()+1] == ":"`) instead of
    the positional check every sibling validator uses. That single
    substitution was wrong in BOTH directions at once (GE-122):

    - RECALL HOLE: the colon test cannot see a marker that has no colon at
      all, so '- PLACEHOLDER', '1. PLACEHOLDER', '- placeholder' and their
      bullet/ordinal siblings were missed, even though the identical shape
      ('- TODO', '- FIXME: broken', '- Replace with the real value') was
      already caught for every OTHER marker via _is_marker_at_line_start.
    - PRECISION HOLE: the colon test fires on a colon ANYWHERE on the line,
      with no positional requirement, so 'MISSED   placeholder: fill this
      in' -- a line that merely QUOTES the marker mid-sentence inside a
      fenced example -- was wrongly flagged even though "placeholder:" is
      nowhere near the start of the line.

    Both holes close the same way: replace the colon test with the
    positional discriminator _is_marker_at_line_start, mirroring
    _is_fixme_marker (see that validator's docstring for the general
    rationale -- a genuine marker opens its line; a mid-sentence mention of
    the same word/phrase never does). This validator is now structurally
    identical to _is_fixme_marker plus the HTML-comment check every sibling
    validator now shares via _is_within_html_comment_marker (GE-122); the
    ad hoc, PLACEHOLDER-only `<!--\\s*PLACEHOLDER\\b` regex that used to sit
    here was itself the original defect, so a future editor changing this
    validator's HTML-comment handling should change the shared helper, not
    re-introduce a per-marker literal.

    One narrow refinement PLACEHOLDER needs that FIXME/TODO do not: when the
    match sits at ABSOLUTE column 0 (nothing at all precedes it -- no bullet,
    no ordinal, no indentation), a bare positional check cannot tell a
    genuine marker ("Placeholder: fill this in") from an ordinary sentence
    that simply happens to open with the word ("Placeholder text appears
    when a field is empty."; the wrapped-paragraph lines in this module's own
    canonical caller, templates/agents/documentation-verifier.md, that begin
    "placeholder content..." / "Placeholder content detected..." purely
    because of markdown line-wrapping). "PLACEHOLDER" is common enough as the
    literal first word of an unrelated English sentence that this ambiguity
    is worth resolving narrowly rather than accepting as a cost the way
    TODO/FIXME do (see _is_bare_todo_marker's own docstring, where a bare
    "TODO fix this before shipping" at column 0 is deliberately flagged
    despite the identical ambiguity). So column-0 matches fall back to the
    original colon-adjacency test instead of the bare positional check --
    "Placeholder:" still qualifies, "Placeholder " followed by prose does
    not. Anything preceded by so much as a bullet, ordinal, or indentation
    (i.e. NOT column 0) uses the plain positional check like every sibling
    validator, so '- PLACEHOLDER', '1. PLACEHOLDER', etc. are still caught
    with no colon required, and a match preceded by ordinary prose text (a
    non-bullet, non-whitespace prefix, e.g. 'MISSED   placeholder: fill this
    in') is correctly excluded either way, whether or not a colon follows.

    GE-122b (2026-08-25): that "not column 0" branch originally called the
    shared _is_marker_at_line_start, whose _LEADING_MARKER_PREFIX regex makes
    the bullet/ordinal OPTIONAL -- so bare indentation with no bullet at all
    also qualified as "marker position". That is harmless for TODO, FIXME,
    and "Replace with" (no repo-wide evidence any of them need tightening,
    and they have used the optional form since before this fix -- do not
    "harmonise" them onto the stricter rule below, it is deliberately
    PLACEHOLDER-only), but for PLACEHOLDER it turned every line-wrapped prose
    paragraph that merely opens with the word "placeholder" after markdown/
    YAML indentation into a false positive. A real repo-wide before/after
    scan (committed HEAD vs working tree, 4815 files) measured this
    precisely: 24 NEW hits, 23 of them false positives spanning 12 AC YAML
    files, 4 agent templates, a generated agent card, 4 tickets, and 2 skill
    docs -- all wrapped prose, none a real marker. PLACEHOLDER is a common
    English noun in this codebase's prose in a way TODO and FIXME are not
    (the same reasoning that motivates the column-0 colon carve-out just
    above), so it needs a stricter positional bar than its siblings: this
    branch now calls _is_marker_after_bullet, whose _LEADING_BULLET_REQUIRED
    regex makes the bullet/ordinal mandatory. The verified arithmetic: the
    optional rule detects 9/9 genuine bulleted/ordinal PLACEHOLDER markers
    but false-positives on 10/10 representative wrapped-prose samples;
    requiring an actual bullet/ordinal keeps the identical 9/9 detection
    rate while dropping false positives to 0/10 -- no measured recall cost,
    only a precision gain. A future editor tempted to loosen this back to
    the optional form should re-run that repo-wide scan first and weigh the
    23-false-positive cost it will reintroduce.

    The marker regex is case-insensitive (re.IGNORECASE) so lowercase and
    mixed-case scaffolding ("placeholder: fill this in", "Placeholder: fill
    this in") is caught too; the alone-on-line, HTML-comment, and
    positional checks are all case-agnostic on their own (they compare
    against the literal text the regex matched, not a hardcoded literal),
    so no separate case-fold step is needed here.
    """
    if _is_within_inline_code(line, match.start(), match.end()):
        return False
    if _is_marker_line(line, match):
        return True
    if _is_within_html_comment_marker(line, match):
        return True
    if match.start() == 0:
        return line[match.end() : match.end() + 1] == ":"
    return _is_marker_after_bullet(line, match.start())


def _default_validator(line: str, match: re.Match[str]) -> bool:
    """Validator for markers whose regex already encodes enough structure
    (a required trailing colon, or a `<!--` HTML-comment anchor) that the
    only remaining false-positive shape is a worked example quoted in inline
    code -- so this only needs the backtick exclusion.
    """
    return not _is_within_inline_code(line, match.start(), match.end())


def _is_replace_with_marker(line: str, match: re.Match[str]) -> bool:
    """Validator for the "Replace with" marker.

    The marker regex is now case-insensitive (re.IGNORECASE) so a template
    whose own "TODO: " prefix has already been stripped, leaving a bare
    lowercase "replace with the real description", is still caught -- but
    case-insensitivity ALONE cannot discriminate this marker: "replace with
    the real description" (a genuine marker, line-initial) and "...replace
    with a value that matches your conventions." (ordinary prose,
    mid-sentence) are the exact same phrase in the exact same case; they
    differ only in WHERE they sit on the line. Requiring the match to be the
    first real content on the line (_is_marker_at_line_start) is the
    positional discriminator that resolves this -- case-insensitivity
    without it would flag both strings or neither.

    The slash-adjacency check is kept as a second, narrower guard for a doc
    that NAMES the marker in a slash-delimited list alongside its siblings
    (e.g. "contains TODO/PLACEHOLDER/Replace with/FIXME/QUESTION/TBD
    markers"). That shape already fails the line-start check too (the
    phrase is never first on the line inside a slash list), but the two
    checks target different failure shapes, so both are kept explicit
    rather than relying on one to accidentally cover the other.
    """
    if _is_within_inline_code(line, match.start(), match.end()):
        return False
    before = line[match.start() - 1 : match.start()]
    after = line[match.end() : match.end() + 1]
    if before == "/" or after == "/":
        return False
    return _is_marker_at_line_start(line, match.start()) or _is_within_html_comment_marker(line, match)


def _is_bare_todo_marker(line: str, match: re.Match[str]) -> bool:
    """Validator for a bare TODO with no trailing colon at all.

    Covers three of the pr-reviewer's reproduced gaps with one validator: a
    lone "TODO" alone on its line, "TODO fix this before shipping" (no
    colon anywhere), and the GitHub-style owner-tag form "TODO(alice): fix
    this before shipping" (the "(alice)" breaks the \\s* bridge the
    colon-anchored \\bTODO\\s*: rule needs, but this bare-word match still
    finds the leading "TODO" regardless of what follows it -- it does not
    need its own owner-tag-specific regex).

    All three are only genuine markers when TODO is the first real content
    on the line: "Contributors write comments like TODO(owner): to tag the
    assignee." is the identical "TODO(owner):" text at a different
    position (mid-sentence, naming the convention), so this defers to the
    same positional check _is_replace_with_marker uses rather than the
    colon rule's simpler backtick-only guard.
    """
    if _is_within_inline_code(line, match.start(), match.end()):
        return False
    if _is_marker_line(line, match):
        return True
    return _is_marker_at_line_start(line, match.start()) or _is_within_html_comment_marker(line, match)


def _is_fixme_marker(line: str, match: re.Match[str]) -> bool:
    """Validator for the FIXME: marker.

    The marker regex is now case-insensitive (re.IGNORECASE) so lowercase
    and mixed-case scaffolding ("fixme: this needs attention", "FixMe: this
    is broken") is caught, not just the all-caps form. Case-insensitivity
    alone would also re-flag a doc that discusses the convention in
    lowercase prose inside a parenthetical aside (e.g. "This convention
    (fixme: for known low-priority bugs) is sometimes written in lowercase
    in commit messages.") -- that string has a real trailing colon too, so
    the colon anchor by itself cannot rule it out. Requiring FIXME to be
    the first real content on the line (_is_marker_at_line_start) is what
    discriminates the two: a genuine "FIXME: ..." marker opens its line; a
    parenthetical or mid-sentence mention of the convention never does.
    """
    if _is_within_inline_code(line, match.start(), match.end()):
        return False
    if _is_marker_line(line, match):
        return True
    return _is_marker_at_line_start(line, match.start()) or _is_within_html_comment_marker(line, match)


_MarkerValidator = Callable[[str, "re.Match[str]"], bool]
_MarkerRule = tuple[re.Pattern[str], _MarkerValidator]

_MARKER_RULES: list[_MarkerRule] = [
    (re.compile(r"\bTODO\s*:", re.IGNORECASE), _default_validator),
    # Bare TODO with no colon at all -- "TODO fix this before shipping", a
    # lone "TODO" alone on a line, or the parenthesized owner-tag form
    # "TODO(alice):" (the "(alice)" breaks the \s* bridge the colon rule
    # above needs). Listed directly AFTER the colon rule so a real
    # "TODO: ..." line still reports the more specific "TODO:" marker text;
    # this rule only ever fires when the colon rule did not match at all,
    # or matched but was excluded (e.g. inline code).
    (re.compile(r"\bTODO\b", re.IGNORECASE), _is_bare_todo_marker),
    (re.compile(r"\bPLACEHOLDER\b", re.IGNORECASE), _is_placeholder_marker),
    # Matched case-insensitively; see _is_replace_with_marker for why case
    # alone cannot discriminate this marker from mid-sentence prose using
    # the identical phrase -- the validator's positional check is what does.
    (re.compile(r"\bReplace with\b", re.IGNORECASE), _is_replace_with_marker),
    # Requiring a trailing colon (mirroring TODO:/FIXME:) separates a real
    # open question ("<!-- QUESTION: should this cover retries too? -->")
    # from prose that shows the comment CONVENTION as a worked example
    # ("<!-- QUESTION --> comment style is used to flag..."), which never
    # carries real question text -- hence no colon -- after the keyword.
    (re.compile(r"<!--\s*QUESTION\s*:", re.IGNORECASE), _default_validator),
    # Matched case-insensitively; see _is_fixme_marker for why the
    # positional check, not case, is what discriminates a real FIXME:
    # marker from a lowercase mid-sentence mention of the convention.
    (re.compile(r"\bFIXME\s*:", re.IGNORECASE), _is_fixme_marker),
    # Bare FIXME with no colon at all -- mirrors the TODO/bare-TODO split
    # above. FIXME previously had ONLY the colon-anchored rule, so a
    # colon-less FIXME (e.g. '<!-- FIXME -->', GE-122) never matched any
    # pattern at all, regardless of validator logic. _is_fixme_marker
    # already handles both shapes identically (alone-on-line / line-start /
    # HTML-comment), so it is reused as-is rather than duplicated. Listed
    # directly AFTER the colon rule so a real "FIXME: ..." line still
    # reports the more specific "FIXME:" marker text; this rule only ever
    # fires when the colon rule did not match at all, or matched but was
    # excluded.
    (re.compile(r"\bFIXME\b", re.IGNORECASE), _is_fixme_marker),
]

_SKIP_EXTENSIONS = frozenset({".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2"})


def scan_for_placeholders(
    target_root: Path,
    paths: list[Path] | None = None,
) -> list[dict[str, Any]]:
    """Scan output files for placeholder markers.

    Args:
        target_root: Absolute path to the target project root.
        paths: Specific paths to scan. If None, scans a default set of
            files known to contain placeholders after build.

    Returns:
        List of dicts with keys: path (str, relative to target_root),
        line (int), marker (str), context (str — the line content).
    """
    if paths is None:
        paths = _default_scan_paths(target_root)

    hits: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        if path.suffix.lower() in _SKIP_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits.extend(_scan_text_for_placeholders(text, path, target_root))
    return hits


def _scan_text_for_placeholders(text: str, path: Path, target_root: Path) -> list[dict[str, Any]]:
    """Scan one file's already-read text for genuine placeholder markers.

    Args:
        text: The file's full text content.
        path: Absolute path to the file (used to compute the reported
            relative path).
        target_root: Absolute path to the target project root.

    Returns:
        List of hit dicts (see scan_for_placeholders' docstring for shape).
        Each line contributes at most one hit -- the first marker rule that
        matches AND validates wins, mirroring the pre-existing one-hit-per-
        line behaviour.
    """
    hits: list[dict[str, Any]] = []
    open_fence_char: str | None = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        # BO-2200b-3-ii: skip fenced code blocks, and the fence lines themselves.
        # A fence closes only on its OWN character -- see _FENCE_DELIMITER.
        fence = _FENCE_DELIMITER.match(line)
        if fence is not None:
            fence_char = fence.group("fence")[0]
            if open_fence_char is None:
                open_fence_char = fence_char
                continue
            if fence_char == open_fence_char:
                open_fence_char = None
                continue
        if open_fence_char is not None:
            continue
        for pattern, validator in _MARKER_RULES:
            match = pattern.search(line)
            if (
                match
                and _is_marker_in_reportable_context(line, match.start())
                and validator(line, match)
            ):
                hits.append({
                    "path": str(path.relative_to(target_root)),
                    "line": lineno,
                    "marker": match.group(0),
                    "context": line.strip(),
                })
                break
    return hits


def _default_scan_paths(target_root: Path) -> list[Path]:
    """Return the default set of paths to scan for placeholders.

    Args:
        target_root: Absolute path to the target project root.

    Returns:
        List of Path objects to scan.
    """
    candidates = [
        target_root / "docs" / "vision.md",
        target_root / "docs" / "roadmap.json",
        target_root / "CLAUDE.md",
    ]
    return [p for p in candidates if p.exists()]


def format_placeholder_report(hits: list[dict[str, Any]]) -> str:
    """Format placeholder hits as a human-readable report.

    Args:
        hits: List of placeholder hit dicts from scan_for_placeholders().

    Returns:
        Markdown-formatted report string, or empty string if no hits.
    """
    if not hits:
        return ""
    by_file: dict[str, list[dict[str, Any]]] = {}
    for hit in hits:
        by_file.setdefault(hit["path"], []).append(hit)
    lines = ["## Placeholder Content Detected", ""]
    for path, file_hits in sorted(by_file.items()):
        lines.append(f"**{path}** ({len(file_hits)} marker{'s' if len(file_hits) != 1 else ''}):")
        for hit in file_hits:
            lines.append(f"  - Line {hit['line']}: `{hit['marker']}` — {hit['context']}")
        lines.append("")
    lines.append(
        "Each hit above is an unresolved marker left in generated content — fill it in "
        "or remove it before treating the file as done. If a line only DISCUSSES a "
        "marker rather than leaving one behind, wrap it in single backticks; inline "
        "code is exempt from this scan by design. Recognised conventions: TODO, "
        "PLACEHOLDER, Replace with, FIXME, `<!-- QUESTION:`."
    )
    return "\n".join(lines)


# DECISION HISTORY
# ================================================================================
# - 2026-08-25 00:00 [python-coder]: Fixed _is_placeholder_marker to consult the
#   _is_marker_at_line_start positional discriminator (mirroring _is_fixme_marker),
#   closing both a recall hole (bulleted/ordinal bare PLACEHOLDER markers like
#   '- PLACEHOLDER' were missed) and a precision hole (the old bare colon test fired
#   on a colon anywhere on the line, flagging mid-sentence quotes such as 'MISSED
#   placeholder: fill this in'). A column-0 case retains the colon check as a narrow
#   exception, since a bare marker with nothing preceding it is otherwise
#   indistinguishable from an ordinary sentence that happens to open with the same
#   word. Also added a short actionable footer to format_placeholder_report()
#   explaining what a hit means and naming the five recognised marker conventions.
#   (#TICKETLESS reason=ge122-integrity-worktree-dispatch-no-ticket)
# - 2026-08-25 00:00 [python-coder]: GE-122 HTML-comment marker parity. Extracted
#   _is_within_html_comment_marker(line, match) -- derived from match.start() and
#   the text preceding it, not a per-marker literal regex -- and consulted it from
#   _is_bare_todo_marker, _is_fixme_marker, and _is_replace_with_marker alongside
#   their existing _is_marker_at_line_start check. Refactored _is_placeholder_marker's
#   hardcoded `<!--\s*PLACEHOLDER\b` branch to call the same helper, so all four
#   validators share one implementation and cannot drift apart again -- that drift
#   (PLACEHOLDER alone catching '<!-- TODO -->'-shaped scaffolding for every other
#   marker) was the defect. QUESTION is untouched: it is matched via
#   _default_validator, which never calls the new helper, so its colon requirement
#   (and the deliberate '<!-- QUESTION -->' no-colon exemption) is unaffected.
#   (#TICKETLESS reason=ge122-integrity-worktree-dispatch-no-ticket)
# - 2026-08-25 00:00 [python-coder]: GE-122b precision correction. The prior fix's
#   _is_marker_at_line_start reuse made PLACEHOLDER's positional check accept bare
#   indentation with no bullet/ordinal at all (the shared _LEADING_MARKER_PREFIX's
#   bullet group is optional), false-positiving 23 wrapped-prose lines repo-wide
#   (measured before/after across 4815 files: 72 -> 94 hits, 24 new, 23 of them
#   false positives). Added _LEADING_BULLET_REQUIRED (bullet/ordinal mandatory) and
#   _is_marker_after_bullet(), and pointed _is_placeholder_marker's non-column-0
#   branch at the new helper instead of _is_marker_at_line_start. TODO, FIXME, and
#   "Replace with" are deliberately UNCHANGED -- they have used the optional-bullet
#   form since before this regression and there is no repo-wide evidence they need
#   tightening; this is a PLACEHOLDER-only correction, not a harmonisation.
#   (#TICKETLESS reason=ge122-integrity-worktree-dispatch-no-ticket)
