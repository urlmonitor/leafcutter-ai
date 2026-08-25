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


def _is_placeholder_marker(line: str, match: re.Match[str]) -> bool:
    """Validator for the PLACEHOLDER marker.

    PLACEHOLDER has no natural trailing punctuation the way TODO:/FIXME: do,
    so a bare `\\bPLACEHOLDER\\b` regex also matches the ordinary English word
    ("the placeholder detection step...") and even an ALL-CAPS mention in a
    sentence that lists marker names ("...and PLACEHOLDER."). Case alone
    cannot separate those last two -- both are spelled identically in caps --
    so PLACEHOLDER additionally requires one of the structural shapes that
    make TODO:/FIXME:/QUESTION: unambiguous markers: alone on its line,
    wrapped in an HTML comment, or immediately followed by a colon.

    The marker regex is now case-insensitive (re.IGNORECASE) so lowercase
    and mixed-case scaffolding ("placeholder: fill this in", "Placeholder:
    fill this in") is caught too. That widening does not need a positional
    check the way "Replace with"/FIXME do: the alone-on-line and colon
    checks below already compare against the literal text the regex
    matched (not a hardcoded literal), so they are case-agnostic on their
    own; the HTML-comment regex is matched case-insensitively for the same
    reason.
    """
    if _is_within_inline_code(line, match.start(), match.end()):
        return False
    if _is_marker_line(line, match):
        return True
    if re.search(r"<!--\s*PLACEHOLDER\b", line, re.IGNORECASE):
        return True
    return line[match.end() : match.end() + 1] == ":"


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
    return _is_marker_at_line_start(line, match.start())


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
    return _is_marker_at_line_start(line, match.start())


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
    return _is_marker_at_line_start(line, match.start())


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
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern, validator in _MARKER_RULES:
            match = pattern.search(line)
            if match and validator(line, match):
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
    return "\n".join(lines)
