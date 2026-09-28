"""
Per-namespace directory walks for the whole-collection uniqueness pass.

MODULE: _uniqueness_scanners
GOAL: Walk each of the three fixed namespaces (acceptance-criteria,
    decisions, diagrams) and produce a NamespaceVerdict naming every number
    claimed by two or more artifacts. Split out of check_identifier_uniqueness.py
    to keep both files under the project's 400-line-per-new-file limit.
BUSINESS CONTEXT: See check_identifier_uniqueness.py's module docstring for
    the full GE-122 rationale. This module owns the actual filesystem I/O:
    every *.yaml / *.md file encountered increments inspected_count during
    the walk itself, before any attempt to parse it, so the count reflects
    what was actually inspected rather than what happened to parse cleanly.
ARCHITECTURE: Two walk shapes, both non-git, pure filesystem:
      - acceptance-criteria: recursive walk of docs/acceptance-criteria/**/*.yaml,
        keyed on each record's top-level ``id`` field. ``_read_yaml_id``
        tries a cheap line-scan fast path (``_fast_scan_top_level_id``)
        before constructing a YAML parser, falling back to a full parse
        (PyYAML, or a minimal fallback) only when the scan cannot prove its
        result matches -- yaml.safe_load-ing every file measured 10+ seconds
        against this store's real ~3100-file collection (DECISION HISTORY).
      - decisions / diagrams: flat (non-recursive) walk of *.md files, keyed
        on a number captured from the filename via a compiled regex.
    A non-matching filename is fail-open at the file level: it still counts
    toward inspected_count but contributes no claim. A genuinely unreadable
    or unparsable acceptance-criteria file is NOT fail-open (GE-122d-3,
    2026-09-07 DECISION HISTORY entry below): it yields
    outcome=OUTCOME_COULD_NOT_ESTABLISH rather than a silent clean pass.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1.yaml

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122a-1]: Extracted from check_identifier_uniqueness.py
    to keep both that module and this one under the 400-line new-file limit
    (check-file-size pre-commit hook).
  - 2026-08-18 [python-coder/GE-122a-1]: Added _fast_scan_top_level_id as the
    fast path ahead of yaml.safe_load in _read_yaml_id. pr-reviewer measured
    run_uniqueness_pass at 10.2-11.4s against this repo's real ~3092-file AC
    collection, against the ticket's own <5s commit-time budget. The fast
    path recognizes only unambiguous id shapes and falls back to a full
    parse otherwise, so correctness is unchanged; measured post-fix at
    under 5s (see the sign-off comment for exact timings).
  - 2026-08-25 [python-coder/GE-122e-3, bug-fix, feedback-id
    fb_2026-08-24_94dc4ba4, finding [H-3]]: scan_acceptance_criteria and
    _scan_filename_numbered returned ``passed=True, inspected_count=0`` for
    a MISSING root -- a wrong/renamed collection_root reported clean over a
    namespace never inspected. Per "THE CONTRACT DECISION"
    (test_ge_122e_3_root_resolution.py), passed=True only when the root was
    actually resolved. An entirely missing root now reports passed=False
    with empty findings (nothing to name); an EXISTING empty directory is
    unaffected and still passes with inspected_count==0.
  - 2026-08-19 [python-coder/GE-122a-1]: Fixed a correctness bug in
    _fast_scan_top_level_id (test_ge_122a_1_fast_path_equivalence.py): the
    fast path returned an unquoted plain scalar's raw text (e.g. 'no',
    '007') even where PyYAML's implicit resolvers coerce it to a non-string
    (False, 7) under a full parse -- hiding a real collision between two ids
    YAML considers identical. Fixed by asking PyYAML's own
    yaml.resolver.Resolver what tag it would assign
    (_plain_scalar_is_unambiguous_string), bailing to the full-parse
    fallback whenever the tag isn't ``tag:yaml.org,2002:str``, rather than a
    hand-rolled denylist that would drift from PyYAML's resolver set. Also
    bails on any embedded C0 control character
    (_contains_control_character), which makes a full parse raise
    ScannerError. Resolver constructed ONCE at module scope (_RESOLVER).
  - 2026-08-25 [python-coder/GE-122e-3, bug-fix, findings [H-2]/[H-2b],
    feedback-id fb_2026-08-24_94dc4ba4]: Fixed two shapes where
    _fast_scan_top_level_id returned a WRONG non-None answer (dangerous,
    since the None-only fallback never corrects it): (1) a multi-document
    YAML stream -- fast path returned the LAST id line where a full parse
    raises ComposerError; (2) a plain scalar folded across an indented
    continuation line -- fast path returned only the first line where a
    full parse folds the continuation. Fixed by making the fast path
    DECLINE (return None) on both, per _is_document_separator_line and
    _plain_scalar_has_continuation -- declining is always safe.
  - 2026-08-25 [python-coder/GE-122a-1, bug-fix, finding [H-4], feedback-id
    fb_2026-08-24_94dc4ba4]: _is_document_separator_line recognized only
    ``---``; ``...`` (document-end) was unrecognized, so a mid-stream
    ``...`` was skipped as text and the fast path fabricated a claim from
    whatever ``id:`` line followed. Fixed via a shared
    _is_document_boundary_token(raw_line, token) helper. Unlike ``---``, a
    lone ``...`` terminating the record's LAST line is legal YAML, so
    _is_document_separator_line takes an ``is_last_line`` flag and only
    declines on a non-final ``...`` (the actually malformed shape).
  - 2026-09-07 [python-coder/GE-122d-3, bug-fix]: Fixed the per-file
    fail-open gap: an AC record that could not be READ (OSError) or PARSED
    (YAMLError) counted toward inspected_count but contributed no claim, and
    the namespace still reported ``passed=True`` -- indistinguishable from
    clean. ``_parse_yaml_dict`` now returns a ``(value, parse_failed)``
    tuple, and a new ``_read_yaml_id_with_failure_flag`` wraps it into a
    ``(value, could_not_establish)`` pair -- ``_read_yaml_id`` itself keeps
    its EXACT original ``str | None`` signature (a pre-existing direct
    consumer, test_ge_122a_1_fast_path_equivalence.py, asserts on it against
    a full-parse oracle across ~30 shapes) and is now a thin wrapper over
    the new function. ``scan_acceptance_criteria`` calls the new function
    directly, collecting failed paths into a new ``unreadable_paths`` list
    fed to ``_build_namespace_verdict``, which reports
    ``outcome=OUTCOME_COULD_NOT_ESTABLISH`` (``passed=False``) whenever
    non-empty -- taking precedence over ``OUTCOME_CONTESTED`` since an
    unread artifact means the collection was never fully inspected. A
    well-formed record with no ``id`` field is UNCHANGED (not a read/parse
    failure). Also gave the missing-root branches the same
    ``OUTCOME_COULD_NOT_ESTABLISH``/``unreadable_paths=[str(root)]`` shape,
    additive alongside GE-122e-3/H-1's existing ``passed=False, findings=[]``.
    See unit_tests/commit_guardian/test_ge_122d_3.py's "THE CONTRACT
    DECISION" for the full widening.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

from _uniqueness_types import (  # type: ignore[import]
    OUTCOME_CLEAN,
    OUTCOME_CONTESTED,
    OUTCOME_COULD_NOT_ESTABLISH,
    Finding,
    NamespaceVerdict,
)

try:
    import yaml  # type: ignore[import]

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


_HOOK_PREFIX = "[check_identifier_uniqueness]"

_ADR_FILENAME_RE = re.compile(r"^ADR-(\d+)-.*\.md$", re.IGNORECASE)
_DIAGRAM_FILENAME_RE = re.compile(r"^c(\d+)-(\d+)-.*\.md$", re.IGNORECASE)

# Constructed ONCE at module scope (not per call) so the fast path's
# per-file cost stays a cheap attribute lookup + method call rather than
# paying resolver-construction cost on every one of ~3100 files -- see the
# DECISION HISTORY entry on the resolver-based fix below.
_STR_TAG = "tag:yaml.org,2002:str"
_RESOLVER = yaml.resolver.Resolver() if _YAML_AVAILABLE else None


# ---------------------------------------------------------------------------
# YAML loading (soft dependency on PyYAML; minimal fallback for id-only reads)
# ---------------------------------------------------------------------------


def _parse_yaml_minimal(content: str) -> dict | None:
    """Parse only top-level scalar ``key: value`` lines from a YAML string.

    Used when PyYAML is unavailable; sufficient for reading an AC file's id.

    Args:
        content: Raw YAML text.

    Returns:
        A dict of top-level scalar fields, or None if none were found.
    """
    result: dict = {}
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#") or line[0:1] in (" ", "\t"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip("'\"")
    return result or None


def _parse_yaml_dict(content: str, source_label: Path) -> tuple[dict | None, bool]:
    """Parse a YAML string into a dict, preferring PyYAML with a minimal fallback.

    Args:
        content: Raw YAML text read from source_label.
        source_label: Path used in warning messages on parse failure.

    Returns:
        A ``(parsed_dict_or_None, parse_failed)`` tuple (GE-122d-3).
        ``parse_failed`` is True only when PyYAML raised ``YAMLError`` --
        content that is genuinely not well-formed YAML at all. It is False
        when parsing succeeded but produced something other than a dict
        (e.g. a bare scalar or a list): that is not a malformed record, only
        one with no top-level fields to claim, so it must not be reported as
        a could-not-read/parse condition.
    """
    if not _YAML_AVAILABLE:
        return _parse_yaml_minimal(content), False
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: YAML parse error in {source_label}: {exc}",
            file=sys.stderr,
        )
        return None, True
    return (data if isinstance(data, dict) else None), False


_UNSAFE_SCALAR_PREFIXES = ("|", ">", "&", "*", "!", "%", "@", "`", "[", "{", "#")


def _plain_scalar_is_unambiguous_string(value: str) -> bool:
    """Ask PyYAML's own implicit resolver whether a PLAIN (unquoted) scalar
    would be read back as a plain string by a full parse.

    This is deliberately NOT a hand-rolled denylist of
    ``null|true|false|yes|no|on|off|~|<digits>`` -- that would be guesswork
    that drifts from PyYAML's actual resolver set. Instead it asks the same
    ``yaml.resolver.Resolver`` machinery ``yaml.safe_load`` itself uses:
    ``Resolver.resolve`` returns the tag PyYAML would assign an unquoted
    scalar with this text. If that tag is anything other than
    ``tag:yaml.org,2002:str`` (e.g. ``:bool``, ``:int``, ``:null``,
    ``:float``), a full parse would COERCE this value to a non-string
    Python object, so the fast path must not claim it -- the caller falls
    back to a full parse instead.

    Args:
        value: The raw, unquoted scalar text (already stripped).

    Returns:
        True when it is safe for the fast path to use `value` as-is; False
        when the caller must fall back to a full parse. Always True when
        PyYAML is unavailable, since the minimal fallback doesn't apply
        implicit resolvers either, so there is nothing to diverge from.
    """
    if _RESOLVER is None:
        return True
    tag = _RESOLVER.resolve(yaml.nodes.ScalarNode, value, (True, False))
    return tag == _STR_TAG


def _contains_control_character(value: str) -> bool:
    """Detect a raw control character (e.g. an embedded tab) in a plain
    scalar's value text.

    A raw C0 control character inside an unquoted YAML scalar is not legal
    token content -- a full parse raises ScannerError rather than reading it
    as a string. The fast path cannot reproduce a parse failure, so it must
    bail to the full parse rather than accept text a real parser would
    reject.

    Args:
        value: The raw, unquoted scalar text (already stripped of leading
            and trailing whitespace, but not of embedded characters).

    Returns:
        True if any character in `value` is a C0 control character
        (codepoint below 0x20).
    """
    return any(ord(ch) < 0x20 for ch in value)


def _strip_simple_quoted_scalar(value: str, quote: str) -> str | None:
    """Strip a simple, non-escaped quoted scalar's surrounding quote chars.

    Only trusted as "simple" when properly terminated with the same quote
    character and containing no embedded quote or (double-quoted) backslash
    escape -- either could change what a full parse produces in a way this
    cheap scan cannot reproduce.

    Args:
        value: The raw value text; must start with quote (caller's contract).
        quote: The quote character in use, ``'"'`` or ``"'"``.

    Returns:
        The unquoted inner string, or None if it cannot be proven simple.
    """
    if len(value) < 2 or not value.endswith(quote):
        return None
    inner = value[1:-1]
    if quote in inner or (quote == '"' and "\\" in inner):
        return None
    return inner


def _is_document_boundary_token(raw_line: str, token: str) -> bool:
    """Detect a bare YAML document-boundary token (``---`` or ``...``) at
    column 0 of one line.

    Only column 0 counts as a boundary: an INDENTED occurrence is a
    continuation line, a QUOTED/MID-VALUE one is ordinary content.
    Requiring `raw_line` to literally START WITH `token` (never merely
    contain it) is what keeps those shapes from being misdetected.

    Args:
        raw_line: One line of raw YAML text (no trailing newline).
        token: The boundary token to check for, ``"---"`` or ``"..."``.

    Returns:
        True if `raw_line` is exactly `token`, or `token` followed by
        whitespace (space or tab) with trailing content on the same line.
    """
    if raw_line == token:
        return True
    return raw_line.startswith(token) and len(raw_line) > 3 and raw_line[3] in (" ", "\t")


def _is_document_separator_line(raw_line: str, *, is_last_line: bool) -> bool:
    """Detect a YAML document-boundary line (``---`` or ``...``) at column 0
    that forces the fast path to decline.

    ``---`` (document-start) declines ANYWHERE in the stream: a
    multi-document stream makes ``yaml.safe_load`` raise ``ComposerError``,
    and the single-pass scan has no cheap way to tell "a harmless leading
    marker" from "a real second document follows" -- conservative, costs a
    handful of extra full-parse fallbacks, never a wrong answer.

    ``...`` (document-end) is NOT symmetric: a lone ``...`` terminating the
    record's LAST line is legal YAML that parses cleanly (declining there
    would be a needless fallback), but a ``...`` that is NOT the last line
    means illegal trailing content (a full parse raises ParserError/
    ScannerError) that the fast path would otherwise skip as text and
    fabricate a claim from whatever ``id:`` follows. `is_last_line`
    distinguishes the two.

    Args:
        raw_line: One line of raw YAML text (no trailing newline).
        is_last_line: True when `raw_line` is the record's final line; only
            relevant to the ``...`` check.

    Returns:
        True if `raw_line` forces the fast path to decline.
    """
    if _is_document_boundary_token(raw_line, "---"):
        return True
    return _is_document_boundary_token(raw_line, "...") and not is_last_line


def _plain_scalar_has_continuation(lines: list[str], id_line_index: int) -> bool:
    """Check whether a plain-scalar ``id`` value would be folded together
    with a following, more-indented continuation line under a full YAML
    parse.

    YAML's plain-scalar line-folding rule joins a plain scalar's first line
    with any immediately-following, deeper-indented line (skipping blanks)
    until a line at column 0 or shallower. The fast path's single-line scan
    cannot reproduce this, so it must decline whenever a continuation is
    possible rather than guess (see "plain_scalar_continuation" in
    test_ge_122a_1_fast_path_equivalence.py).

    Args:
        lines: The full record's lines (``content.splitlines()``).
        id_line_index: Index, within `lines`, of the line holding the
            plain-scalar ``id:`` value being checked.

    Returns:
        True if the first non-blank line after `id_line_index` is indented
        (a possible continuation, decline). False if it starts at column 0
        or there is no more content (no continuation possible).
    """
    for line in lines[id_line_index + 1 :]:
        if line.strip() == "":
            continue
        return line[0] in (" ", "\t")
    return False


def _fast_scan_top_level_id(content: str) -> str | None:
    """Cheaply extract a record's top-level ``id`` field via a line scan.

    FAST PATH ahead of a full YAML parse: a single pass over raw lines, no
    parser construction, recognizing only the ``id`` value shapes this
    store's AC records actually use -- a bare plain scalar, or a simple
    single/double-quoted scalar with no embedded quote, backslash escape, or
    inline comment. Every other shape bails out with None ("cannot prove
    this matches yaml.safe_load") so the caller falls back to a full parse.

    A QUOTED value is trusted directly once ``_strip_simple_quoted_scalar``
    proves it simple (never subject to YAML's implicit resolvers). A PLAIN
    (unquoted) value is different -- YAML coerces tokens like ``null``,
    ``no``, ``007`` to a non-string value -- so this asks PyYAML's own
    resolver what tag it would assign (`_plain_scalar_is_unambiguous_string`)
    rather than hand-rolling a denylist that would drift from PyYAML's own
    resolver set, and bails to a full parse whenever the tag isn't
    ``tag:yaml.org,2002:str``. Also bails on an embedded C0 control
    character (`_contains_control_character`), which makes a full parse
    raise ScannerError.

    Two further shapes force a decline because they'd otherwise produce a
    WRONG non-None answer (never corrected by the None-fallback, the
    dangerous case): a document-boundary token (``---`` anywhere, or a
    non-final ``...`` -- `_is_document_separator_line`; a full parse raises
    Composer/Parser/ScannerError, no usable claim, where the fast path would
    otherwise fabricate a claim from the last ``id:`` line it saw); and a
    plain-scalar ``id`` immediately followed by a more-indented continuation
    line (`_plain_scalar_has_continuation` -- a full parse FOLDS it in,
    where the single-line scan would silently drop it).

    Only a zero-indent line is top-level (no legal top-level ``id`` in this
    schema nests under another key); a malformed duplicate key resolves to
    the LAST such line, matching PyYAML's own last-value-wins behavior.

    Args:
        content: Raw YAML text of the record.

    Returns:
        The extracted id string, or None if no line unambiguously matches.
    """
    lines = content.splitlines()
    last_index = len(lines) - 1
    found: str | None = None
    for index, raw_line in enumerate(lines):
        if _is_document_separator_line(raw_line, is_last_line=index == last_index):
            return None
        if not raw_line or raw_line[0] in (" ", "\t", "#"):
            continue
        if not raw_line.startswith("id:"):
            continue
        value = raw_line[len("id:") :].strip()
        if not value or value.startswith(_UNSAFE_SCALAR_PREFIXES):
            return None
        if value.startswith('"') or value.startswith("'"):
            stripped = _strip_simple_quoted_scalar(value, value[0])
            if stripped is None:
                return None
            found = stripped
            continue
        if "#" in value or ":" in value:
            return None
        if _contains_control_character(value):
            return None
        if not _plain_scalar_is_unambiguous_string(value):
            return None
        if _plain_scalar_has_continuation(lines, index):
            return None
        found = value
    return found or None


def _read_yaml_id(yaml_path: Path) -> str | None:
    """Read one AC YAML file's top-level ``id`` field (thin wrapper).

    Discards the could-not-establish flag -- kept at this EXACT original
    ``str | None`` signature (GE-122a-1) because
    test_ge_122a_1_fast_path_equivalence.py calls this function directly
    against a full-parse oracle across ~30 shapes (CLAUDE.md "Function
    Signature Extension" rule). ``scan_acceptance_criteria`` calls
    ``_read_yaml_id_with_failure_flag`` directly instead (GE-122d-3).

    Args:
        yaml_path: Path to the .yaml file to read.

    Returns:
        The non-empty ``id`` field value as a string, or None.
    """
    record_id, _could_not_establish = _read_yaml_id_with_failure_flag(yaml_path)
    return record_id


def _read_yaml_id_with_failure_flag(yaml_path: Path) -> tuple[str | None, bool]:
    """Read one AC YAML file's ``id``, plus whether the read/parse itself
    failed outright (GE-122d-3).

    Tries the cheap _fast_scan_top_level_id line-scan first, falling back to
    a full YAML parse (_parse_yaml_dict) when the fast scan cannot prove its
    result matches -- see that function's docstring for which shapes are
    unambiguous.

    Args:
        yaml_path: Path to the .yaml file to read.

    Returns:
        A ``(record_id_or_None, could_not_establish)`` tuple.
        ``could_not_establish`` is True when the file could not be READ
        (``OSError``/``UnicodeDecodeError``) or PARSED (a genuine YAML parse
        failure) at all -- this AC's Gherkin "cannot read or cannot parse".
        False otherwise, INCLUDING a well-formed record with no ``id`` field
        (not a read/parse failure -- nothing to claim, unchanged fail-open).
    """
    try:
        content = yaml_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read {yaml_path}: {exc}",
            file=sys.stderr,
        )
        return None, True

    fast_id = _fast_scan_top_level_id(content)
    if fast_id is not None:
        return fast_id, False

    data, parse_failed = _parse_yaml_dict(content, yaml_path)
    if parse_failed:
        return None, True
    if data is None:
        return None, False
    record_id = str(data.get("id", "")).strip()
    return (record_id or None), False


# ---------------------------------------------------------------------------
# Namespace verdict assembly
# ---------------------------------------------------------------------------


def _build_namespace_verdict(
    claims: dict[str, list[Path]],
    inspected_count: int,
    unreadable_paths: list[str] | None = None,
) -> NamespaceVerdict:
    """Turn a number->claimant-paths map into a NamespaceVerdict.

    A number is only reported when two or more artifacts claim it -- grouping
    by contested number (not by claimant file) is what keeps the finding
    count at "one per collision" rather than "one per file in a collision".

    Args:
        claims: Mapping of claimed number to the list of paths that claim it.
        inspected_count: Total artifacts walked in this namespace.
        unreadable_paths: ADDITIVE (GE-122d-3). Artifact paths this namespace
            could not read or parse. When non-empty, ``outcome`` is
            ``OUTCOME_COULD_NOT_ESTABLISH`` regardless of ``claims`` -- an
            unread artifact takes precedence over what WAS established.

    Returns:
        The assembled NamespaceVerdict. ``passed`` is True only when there is
        neither a collision NOR an unreadable artifact.
    """
    unreadable_paths = list(unreadable_paths or [])
    findings = [
        Finding(number=number, paths=[str(p) for p in paths])
        for number, paths in sorted(claims.items())
        if len(paths) > 1
    ]
    if unreadable_paths:
        outcome = OUTCOME_COULD_NOT_ESTABLISH
    elif findings:
        outcome = OUTCOME_CONTESTED
    else:
        outcome = OUTCOME_CLEAN
    return NamespaceVerdict(
        passed=not findings and not unreadable_paths,
        inspected_count=inspected_count,
        findings=findings,
        outcome=outcome,
        unreadable_paths=unreadable_paths,
    )


# ---------------------------------------------------------------------------
# Per-namespace directory walks
# ---------------------------------------------------------------------------


def scan_acceptance_criteria(ac_root: Path) -> NamespaceVerdict:
    """Walk the acceptance-criteria namespace and detect id collisions.

    Recursively walks every *.yaml file under ac_root, mirroring the real
    store's component/goal-folder shape. Every file encountered counts
    toward inspected_count regardless of whether it parses.

    Args:
        ac_root: Path to the docs/acceptance-criteria/ directory.

    Returns:
        The NamespaceVerdict for the acceptance-criteria namespace. A
        missing ac_root reports passed=False, inspected_count=0, empty
        findings, and outcome OUTCOME_COULD_NOT_ESTABLISH naming ac_root in
        unreadable_paths (GE-122d-3) -- a misconfiguration, not an empty
        namespace. An EXISTING empty ac_root still passes cleanly with
        inspected_count=0 (GE-122e-3 "THE CONTRACT DECISION",
        test_ge_122e_3_root_resolution.py). A SINGLE unreadable/unparsable
        artifact within an otherwise-resolved ac_root also yields
        OUTCOME_COULD_NOT_ESTABLISH naming that artifact, while every OTHER
        file still counts toward inspected_count and any collision it is
        part of.
    """
    if not ac_root.is_dir():
        return NamespaceVerdict(
            passed=False,
            inspected_count=0,
            findings=[],
            outcome=OUTCOME_COULD_NOT_ESTABLISH,
            unreadable_paths=[str(ac_root)],
        )

    claims: dict[str, list[Path]] = {}
    unreadable_paths: list[str] = []
    inspected_count = 0
    for yaml_path in sorted(ac_root.rglob("*.yaml")):
        inspected_count += 1
        record_id, could_not_establish = _read_yaml_id_with_failure_flag(yaml_path)
        if could_not_establish:
            unreadable_paths.append(str(yaml_path))
            continue
        if record_id is None:
            continue
        claims.setdefault(record_id, []).append(yaml_path)

    return _build_namespace_verdict(claims, inspected_count, unreadable_paths)


def _scan_filename_numbered(
    directory: Path,
    pattern: re.Pattern[str],
    number_of: Callable[[re.Match[str]], str],
) -> NamespaceVerdict:
    """Scan a flat directory of *.md files whose filenames encode a number.

    Non-recursive by design: both docs/architecture/adrs/ and
    docs/architecture/diagrams/ are flat namespaces in this store. Every
    *.md file counts toward inspected_count regardless of whether its
    filename matches pattern.

    Args:
        directory: Directory to scan for *.md files.
        pattern: Compiled regex matched against each filename.
        number_of: Callable taking a regex Match and returning the
            contested-number string for that filename.

    Returns:
        The NamespaceVerdict for the namespace rooted at directory. A
        missing directory reports passed=False, inspected_count=0, empty
        findings, and outcome OUTCOME_COULD_NOT_ESTABLISH naming directory
        in unreadable_paths (GE-122d-3) -- a misconfiguration, not an empty
        namespace. An EXISTING empty directory still passes cleanly with
        inspected_count=0 (GE-122e-3 "THE CONTRACT DECISION",
        test_ge_122e_3_root_resolution.py).
    """
    if not directory.is_dir():
        return NamespaceVerdict(
            passed=False,
            inspected_count=0,
            findings=[],
            outcome=OUTCOME_COULD_NOT_ESTABLISH,
            unreadable_paths=[str(directory)],
        )

    claims: dict[str, list[Path]] = {}
    inspected_count = 0
    for md_path in sorted(directory.glob("*.md")):
        inspected_count += 1
        match = pattern.match(md_path.name)
        if match is None:
            continue
        claims.setdefault(number_of(match), []).append(md_path)

    return _build_namespace_verdict(claims, inspected_count)


def scan_decisions(adr_root: Path) -> NamespaceVerdict:
    """Walk the decisions namespace and detect ADR integer collisions.

    Args:
        adr_root: Path to the docs/architecture/adrs/ directory.

    Returns:
        The NamespaceVerdict for the decisions namespace.
    """
    return _scan_filename_numbered(adr_root, _ADR_FILENAME_RE, lambda m: m.group(1))


def scan_diagrams(diagram_root: Path) -> NamespaceVerdict:
    """Walk the diagrams namespace and detect level-and-sequence collisions.

    Args:
        diagram_root: Path to the docs/architecture/diagrams/ directory.

    Returns:
        The NamespaceVerdict for the diagrams namespace.
    """
    return _scan_filename_numbered(
        diagram_root,
        _DIAGRAM_FILENAME_RE,
        lambda m: f"c{m.group(1)}-{m.group(2)}",
    )
