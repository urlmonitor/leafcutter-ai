"""
MODULE: _presence_only_scanner
GOAL: Diff-parsing and pattern-detection helpers for check_presence_only_
    assertions.py — split out to keep the hook entry-point module under the
    project's 400-line file-size limit (see check-file-size pre-commit hook).
BUSINESS CONTEXT: Implements the actual staged-hunk scan for BP-1100b-5:
    detecting a newly added presence-only test assertion (substring form or
    regex-declaration form) over a scanned-source file, honouring the
    `# presence-only: <reason>` waiver escape hatch. Private module (leading
    underscore) — not a hook entry point itself, imported only by
    check_presence_only_assertions.py.
ARCHITECTURE: Pure functions over already-read diff text and already-loaded
    config values — no I/O, no subprocess, no filesystem access. The public
    surface is `split_diff_into_file_blocks()` (diff parsing) and
    `scan_file_block()` (detection), plus the `Violation` / `Waiver`
    dataclasses `check_presence_only_assertions.py` reports on. Detection
    proceeds per-candidate: find a presence-only-shaped line, then scan
    BACKWARD within the same file block for the nearest preceding line that
    (a) references a configured scanned-source file and (b) is a waiver-
    marker comment — both searches run independently so a waiver above the
    source-reference line is still found.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------

_DIFF_FILE_HEADER_RE = re.compile(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)$")
_TEST_FILE_PATH_RE = re.compile(r"(^|/)(test_[^/]+\.py|[^/]+_test\.py)$")


def is_test_file_path(path: str) -> bool:
    """Return True if ``path`` looks like a Python test file."""
    return bool(_TEST_FILE_PATH_RE.search(path))


def split_diff_into_file_blocks(
    diff_text: str,
) -> list[tuple[str, list[str], frozenset[int]]]:
    """Split a unified diff into (new_file_path, added_lines, hunk_starts).

    ``added_lines`` preserves the original line order within the file's
    hunks, with the leading ``+`` stripped. The ``+++ b/...`` file-trailer
    line is never treated as content.

    ``hunk_starts`` holds the index into ``added_lines`` at which each hunk's
    contribution begins. Because this function CONCATENATES every hunk's added
    lines into one list, two edits hundreds of lines apart in the real file end
    up adjacent here. Without the boundaries, a backward scan cannot tell "the
    line above" from "the last line of an unrelated edit elsewhere in the
    file" — which let a waiver comment in one hunk waive an assertion in
    another, and let a path literal in one edit be attributed to an assertion
    in another (BP-1100b-5).

    Args:
        diff_text: Full text of a unified diff (e.g. `git diff --cached`).

    Returns:
        List of (new_path, added_lines, hunk_starts) tuples, one per file.
    """
    blocks: list[tuple[str, list[str], frozenset[int]]] = []
    current_path: str | None = None
    current_added: list[str] = []
    current_starts: list[int] = []

    for line in diff_text.splitlines():
        header = _DIFF_FILE_HEADER_RE.match(line)
        if header:
            if current_path is not None:
                blocks.append(
                    (current_path, current_added, frozenset(current_starts))
                )
            current_path = header.group("b")
            current_added = []
            current_starts = []
            continue
        if current_path is None:
            continue
        if line.startswith("@@"):
            # The next added line begins a new hunk. Recorded even if the hunk
            # turns out to contribute no added lines — a stale index is inert,
            # a missing one silently merges two hunks.
            current_starts.append(len(current_added))
            continue
        if line.startswith("+++"):
            continue
        if line.startswith("+"):
            current_added.append(line[1:])

    if current_path is not None:
        blocks.append((current_path, current_added, frozenset(current_starts)))
    return blocks


# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

# A properly-quoted string literal, honouring the OPENING quote character for
# the close (via a backreference) rather than stopping at the first quote of
# either type — a literal like 'Workflow("build-feature"' embeds a DIFFERENT
# quote character and must not be truncated at it.
_QUOTED_STRING_RE = re.compile(r"""(?P<q>['"])(?P<lit>(?:(?!(?P=q)).)*)(?P=q)""")

# Substring form, bare `in` comparison: `'literal' in some_var`.
_SUBSTRING_BARE_IN_RE = re.compile(
    r"""(?P<q>['"])(?P<lit>(?:(?!(?P=q)).)*)(?P=q)\s+in\s+\w+"""
)
# Substring form, assertIn(...) call: `assertIn('literal', some_var)`.
_SUBSTRING_ASSERT_IN_RE = re.compile(
    r"""assertIn\s*\(\s*(?P<q>['"])(?P<lit>(?:(?!(?P=q)).)*)(?P=q)"""
)
# A literal "looks like a code/behavioural claim" (not a bare documentation
# marker) when it contains an identifier immediately followed by `(`.
_CALL_SHAPE_RE = re.compile(r"[A-Za-z_]\w*\s*\(")

# ...or when the whole literal is a bare code identifier. Requiring `(` meant
# the criteria's OWN headline example — "an assertion that the string
# `emit_agent_telemetry` is contained in that file's contents" — was never a
# candidate, and neither were the incumbent `choose_lane` /
# `emit_agent_telemetry` violations the check was calibrated on. A function
# name asserted without its parentheses is the same presence-only claim.
_BARE_SNAKE_IDENT_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
_BARE_CAMEL_IDENT_RE = re.compile(r"^[a-z]+(?:[A-Z][a-z0-9]*)+$")

# The discriminator that separates a code claim from a documentation marker
# must NOT be "has parentheses" — that was only ever a proxy, and it excluded
# real code while admitting nothing useful. An AC id is the actual non-target.
_AC_ID_RE = re.compile(r"^[A-Z]{2,5}-\d+[a-z]?(?:-\d+)*(?:-[ivxlc]+)?$")


def _is_code_shaped(literal: str) -> bool:
    """Return True when ``literal`` reads as a code/behavioural claim.

    A path, an AC id, or free prose is not a code claim. A call form
    (``foo(``), a snake_case identifier, or a camelCase identifier is.
    """
    text = literal.strip()
    if not text:
        return False
    if _AC_ID_RE.match(text):
        return False
    if _CALL_SHAPE_RE.search(text):
        return True
    if "/" in text or " " in text:
        return False
    return bool(
        _BARE_SNAKE_IDENT_RE.match(text) or _BARE_CAMEL_IDENT_RE.match(text)
    )

# Regex-declaration form: matched as LITERAL TEXT (the backslashes below are
# themselves the pattern being searched for, not regex metacharacters being
# interpreted) — e.g. `re.compile(r"function\s+someHelper\s*\(")`.
_REGEX_DECL_FORM_RE = re.compile(
    r"function\\s\+(?P<name>[A-Za-z_]\w*)\\s\*\\\("
)
# A line that USES a previously compiled regex pattern (`.search(`/`.match(`).
_REGEX_USE_RE = re.compile(r"\.(?:search|match|test)\s*\(")


@dataclass
class Violation:
    """An unwaived presence-only assertion found in a staged hunk."""

    test_file: str
    symbol: str
    source_file: str
    kind: str  # "substring" | "regex-declaration"


@dataclass
class Waiver:
    """A waived presence-only assertion (non-empty `# presence-only:` reason)."""

    test_file: str
    symbol: str
    source_file: str
    reason: str


def _quoted_literals(line: str) -> list[str]:
    """Return every single- or double-quoted string literal on a line.

    Honours the opening quote character for the close (see
    ``_QUOTED_STRING_RE``), so a literal containing an embedded quote of the
    OTHER type (e.g. ``'Workflow("build-feature"'``) is not truncated early.
    """
    return [m.group("lit") for m in _QUOTED_STRING_RE.finditer(line)]


def _matches_scanned_source(line: str, globs: list[str]) -> str | None:
    """Return the first quoted literal on ``line`` matching a configured glob.

    Args:
        line: A single added line (already stripped of its leading ``+``).
        globs: The configured ``scanned_source_globs`` list.

    Returns:
        The matched literal (a source-file path), or None if no quoted
        literal on the line matches any configured glob.
    """
    literals = _quoted_literals(line)
    for literal in literals:
        for glob in globs:
            if fnmatch.fnmatch(literal, glob):
                return literal

    # Whole-literal matching alone misses the dominant real-world idiom. The
    # in-tree form is a pathlib join:
    #
    #     _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"
    #
    # which yields four separate literals, none of which fnmatch a glob like
    # "templates/workflows-js/**/*.js". Both of the incumbent violations this
    # check was calibrated against are written that way, and both went
    # undetected: the guard shipped unable to see the exact code its own AC
    # cites as the thing to catch. Re-join consecutive literals on the line
    # with "/" and retry, so a path assembled by the `/` operator is matched
    # the same as one written inline.
    if len(literals) > 1:
        joined = "/".join(literals)
        for glob in globs:
            if fnmatch.fnmatch(joined, glob):
                return joined
        # Also try every trailing sub-path, so a leading variable (_REPO_ROOT)
        # or an absolute prefix does not defeat a relative glob.
        for start in range(1, len(literals)):
            tail = "/".join(literals[start:])
            for glob in globs:
                if fnmatch.fnmatch(tail, glob):
                    return tail
    return None


def _waiver_reason(line: str, marker_re: re.Pattern) -> str | None:
    """Return the captured reason if ``line`` is a waiver-marker comment.

    Returns the raw (unstripped) captured text, or None if the line does not
    match the waiver-marker pattern at all. Callers decide whether an empty
    (post-strip) reason suppresses — this function only extracts.
    """
    match = marker_re.match(line)
    if match:
        return match.group(1)
    return None


#: How many added lines above an assertion may be searched for its WAIVER
#: comment. Deliberately tight: the criteria say the assertion "is preceded
#: by" a waiver and the hook's own report says "directly above". An unbounded
#: search meant one `# presence-only:` comment waived EVERY later assertion in
#: the same file block, including ones added 900 lines and several hunks away
#: — a single comment silently switching the guard off for the rest of a file.
_WAIVER_SCAN_LIMIT = 10

#: The SOURCE-FILE search is deliberately NOT bounded the same way, because
#: the two searches have different semantics and bounding them identically
#: breaks one to fix the other.
#:
#: A waiver is a statement about ONE assertion, so proximity is the contract.
#: A source-file reference is a statement about a BLOCK: the dominant real
#: idiom is read-once/assert-many —
#:
#:     content = (_REPO_ROOT / "templates" / "workflows-js" / "x.js").read_text()
#:     assert "alpha(" in content
#:     assert "beta(" in content
#:     ...                       # a dozen more
#:
#: — where one path literal governs every assertion below it. Applying the
#: 10-line waiver bound to the source search made assertion #11 lose its
#: source reference and escape detection entirely: a FALSE NEGATIVE in exactly
#: the shape this guard exists to catch, introduced by the fix for the
#: over-waiving bug. The source search therefore runs to the start of the
#: current hunk, which is the real scope boundary — an unrelated edit
#: elsewhere in the file is a different hunk and cannot leak its path in.
#:
#: This asymmetry is the point. Bounding both produced a guard that was
#: simultaneously too permissive about waivers and too blind about sources.




def _scan_backward(
    added_lines: list[str],
    from_index: int,
    globs: list[str],
    marker_re: re.Pattern,
    hunk_starts: frozenset[int] = frozenset(),
) -> tuple[str | None, str | None]:
    """Scan backward from ``from_index`` for a source-ref and a waiver.

    The scan is bounded twice over: it looks at most ``_BACKWARD_SCAN_LIMIT``
    lines back, and it stops at a hunk boundary. Hunk boundaries matter
    because ``split_diff_into_file_blocks`` concatenates every added line for
    a file across all its hunks — so without the reset, two edits in unrelated
    parts of the same file are adjacent in this list even though they are
    hundreds of lines apart in the file itself.

    Args:
        added_lines: All added lines for the current file block.
        from_index: Index to start scanning backward from (exclusive).
        globs: Configured scanned_source_globs.
        marker_re: Compiled waiver-marker regex.
        hunk_starts: Indices into ``added_lines`` at which a new hunk begins.
            The scan will not cross one.

    Returns:
        (source_file_or_None, waiver_reason_or_None). The waiver reason is
        the RAW captured text (may be empty/whitespace) of the nearest
        waiver-marker line; both searches stop as soon as their own target is
        found, independently, so a waiver above the source line is still seen.
    """
    source_file: str | None = None
    waiver_reason: str | None = None
    waiver_floor = from_index - _WAIVER_SCAN_LIMIT

    for j in range(from_index - 1, -1, -1):
        line = added_lines[j]

        # Source reference: searched to the start of this hunk (see the
        # _WAIVER_SCAN_LIMIT commentary — read-once/assert-many means one path
        # literal governs every assertion below it in the same hunk).
        if source_file is None:
            source_file = _matches_scanned_source(line, globs)

        # Waiver: only counts within the proximity bound, so one comment
        # cannot silently waive the rest of the file.
        if waiver_reason is None and j >= waiver_floor:
            waiver_reason = _waiver_reason(line, marker_re)

        if source_file is not None and waiver_reason is not None:
            break
        if j in hunk_starts:
            break  # hunk boundary is the real scope edge for both searches

    return source_file, waiver_reason


def _scan_substring_form(
    added_lines: list[str],
    globs: list[str],
    marker_re: re.Pattern,
    hunk_starts: frozenset[int] = frozenset(),
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """Detect substring-form presence-only candidates in a file's added lines.

    Returns:
        (unwaived, waived) — each a list of (symbol, source_file, reason)
        tuples; ``reason`` is "" for the unwaived list.
    """
    unwaived: list[tuple[str, str, str]] = []
    waived: list[tuple[str, str, str]] = []

    for i, line in enumerate(added_lines):
        literal = None
        match = _SUBSTRING_ASSERT_IN_RE.search(line)
        if match:
            literal = match.group("lit")
        else:
            match = _SUBSTRING_BARE_IN_RE.search(line)
            if match:
                literal = match.group("lit")
        if literal is None or not _is_code_shaped(literal):
            continue

        source_file, raw_reason = _scan_backward(
            added_lines, i, globs, marker_re, hunk_starts
        )
        if source_file is None:
            continue  # AC-9: not a scanned source — out of scope.

        reason = (raw_reason or "").strip()
        if raw_reason is not None and reason:
            waived.append((literal, source_file, reason))
        else:
            unwaived.append((literal, source_file, ""))

    return unwaived, waived


def _scan_regex_declaration_form(
    added_lines: list[str],
    globs: list[str],
    marker_re: re.Pattern,
    hunk_starts: frozenset[int] = frozenset(),
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """Detect regex-declaration-form presence-only candidates.

    Returns:
        (unwaived, waived) — same shape as ``_scan_substring_form``.
    """
    unwaived: list[tuple[str, str, str]] = []
    waived: list[tuple[str, str, str]] = []

    for i, line in enumerate(added_lines):
        decl_match = _REGEX_DECL_FORM_RE.search(line)
        if not decl_match:
            continue
        symbol = decl_match.group("name")

        # The declaration's OWN line rarely has the source reference before
        # it (the read_text() call is typically declared just AFTER the
        # regex, then used together in a .search()/.match() call) — anchor
        # the proximity scan on the nearest FOLLOWING usage line instead of
        # the declaration line itself.
        anchor = i
        for k in range(i + 1, len(added_lines)):
            if _REGEX_USE_RE.search(added_lines[k]):
                anchor = k
                break

        source_file, raw_reason = _scan_backward(
            added_lines, anchor, globs, marker_re, hunk_starts
        )
        if source_file is None:
            continue

        reason = (raw_reason or "").strip()
        if raw_reason is not None and reason:
            waived.append((symbol, source_file, reason))
        else:
            unwaived.append((symbol, source_file, ""))

    return unwaived, waived


def scan_file_block(
    test_file: str,
    added_lines: list[str],
    globs: list[str],
    marker_re: re.Pattern,
    hunk_starts: frozenset[int] = frozenset(),
) -> tuple[list[Violation], list[Waiver]]:
    """Scan one test file's added lines for presence-only assertions.

    Args:
        test_file: The new-side path of the file this block belongs to.
        added_lines: Added lines for this file (leading `+` already stripped).
        globs: Configured scanned_source_globs.
        marker_re: Compiled waiver-marker regex.
        hunk_starts: Indices in ``added_lines`` where each hunk begins, from
            ``split_diff_into_file_blocks``. Defaults to empty, which treats
            the block as one contiguous hunk — correct for a single-hunk diff
            and for direct callers that do not have the boundaries.

    Returns:
        (violations, waivers) found in this file block.
    """
    violations: list[Violation] = []
    waivers: list[Waiver] = []

    sub_unwaived, sub_waived = _scan_substring_form(
        added_lines, globs, marker_re, hunk_starts
    )
    for symbol, source_file, _ in sub_unwaived:
        violations.append(Violation(test_file, symbol, source_file, "substring"))
    for symbol, source_file, reason in sub_waived:
        waivers.append(Waiver(test_file, symbol, source_file, reason))

    regex_unwaived, regex_waived = _scan_regex_declaration_form(
        added_lines, globs, marker_re, hunk_starts
    )
    for symbol, source_file, _ in regex_unwaived:
        violations.append(Violation(test_file, symbol, source_file, "regex-declaration"))
    for symbol, source_file, reason in regex_waived:
        waivers.append(Waiver(test_file, symbol, source_file, reason))

    return violations, waivers


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-08-18 [EPIC-BuildPipelinePhantomRemediation/09]: Created. Split out
#   of check_presence_only_assertions.py to keep the hook entry-point module
#   under the 400-line file-size limit. See BP-1100b-5.
# ===========================================================================
