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
        keyed on each record's top-level ``id`` field. ``_read_yaml_id`` tries
        a cheap line-scan fast path (``_fast_scan_top_level_id``) before ever
        constructing a YAML parser; it falls back to a full parse (PyYAML,
        with a minimal fallback parser when PyYAML is unavailable) only when
        the line scan cannot prove its result matches what a full parse would
        produce. This exists because yaml.safe_load-ing every file purely to
        read one top-level scalar measured 10+ seconds against this store's
        real ~3100-file collection -- see the DECISION HISTORY entry below.
      - decisions / diagrams: flat (non-recursive) walk of *.md files, keyed
        on a number captured from the filename via a compiled regex.
    Each per-file read failure (unreadable, unparsable, non-matching
    filename) is fail-open at the file level: it still counts toward
    inspected_count but contributes no claim, since a file whose number
    cannot be determined cannot be said to have claimed one.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1.yaml

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122a-1]: Extracted from check_identifier_uniqueness.py
    to keep both that module and this one under the 400-line new-file limit
    (check-file-size pre-commit hook).
  - 2026-08-18 [python-coder/GE-122a-1]: Added _fast_scan_top_level_id as the
    fast path ahead of yaml.safe_load in _read_yaml_id. pr-reviewer measured
    run_uniqueness_pass at 10.2-11.4s against this repo's real collection
    (3092 AC yaml files), isolated to scan_acceptance_criteria's per-file
    yaml.safe_load call -- against the ticket's own <5s commit-time budget
    ("a commit-time gate slower than that gets bypassed"). The fast path
    recognizes only unambiguous id shapes and falls back to a full parse for
    everything else, so correctness is unchanged: measured against the real
    collection post-fix at under 5s (see the sign-off comment for exact
    timings).
  - 2026-08-25 [python-coder/GE-122e-3, bug-fix]: Fixed a fail-open defect
    found by pr-reviewer (feedback-id fb_2026-08-24_94dc4ba4, finding
    [H-3]): scan_acceptance_criteria and _scan_filename_numbered (backing
    scan_decisions / scan_diagrams) returned
    NamespaceVerdict(passed=True, inspected_count=0, findings=[]) whenever
    their root directory did not exist -- so a wrong or renamed
    collection_root reported a clean pass over a namespace that was never
    actually inspected. Per the contract fixed in
    unit_tests/commit_guardian/test_ge_122e_3_root_resolution.py's module
    docstring ("THE CONTRACT DECISION"), a namespace may report
    passed=True ONLY when its root was actually resolved (walked),
    regardless of whether that walk found zero or many artifacts. An
    ENTIRELY MISSING root now reports passed=False with an empty findings
    list (there is nothing to name; the root itself is the finding) --
    distinguishable from a genuine collision, which always populates
    findings. A root that EXISTS as a real, empty directory is unaffected
    and still passes cleanly with inspected_count == 0: that is a
    legitimately empty, resolved namespace, not a misconfiguration.
  - 2026-08-19 [python-coder/GE-122a-1]: Fixed a correctness bug in
    _fast_scan_top_level_id caught by
    unit_tests/commit_guardian/test_ge_122a_1_fast_path_equivalence.py: the
    fast path returned an unquoted plain scalar's raw source text (e.g.
    'no', '007', '0x1F') even where PyYAML's implicit resolvers coerce that
    same token to a non-string value under a full parse (False, 7, 31) --
    making two records that YAML considers identical (e.g. ids 'no' and
    'False') look like two different ids, silently hiding a real collision.
    Fixed by asking PyYAML's own yaml.resolver.Resolver what tag it would
    assign a plain scalar (_plain_scalar_is_unambiguous_string) and bailing
    out to the full-parse fallback whenever the tag is not
    tag:yaml.org,2002:str, rather than hand-rolling a denylist of coercible
    tokens that would drift from PyYAML's actual resolver set. Also bails
    out on any embedded C0 control character (_contains_control_character,
    e.g. a raw tab) since that makes a full parse raise ScannerError with no
    usable claim, which the fast path cannot reproduce by returning a
    literal string. The resolver is constructed ONCE at module scope
    (_RESOLVER) to keep the per-file cost of the fast path negligible.
  - 2026-08-25 [python-coder/GE-122e-3, bug-fix, pr-reviewer findings
    [H-2]/[H-2b], feedback-id fb_2026-08-24_94dc4ba4]: Fixed two more shapes
    where _fast_scan_top_level_id returned a WRONG non-None answer -- the
    dangerous case, since _read_yaml_id only falls back to a full parse when
    the fast path returns None, so a wrong non-None answer was never
    corrected: (1) a multi-document YAML stream ("id: GE-1\n---\nid: GE-2\n")
    -- the fast path returned the LAST top-level id line it saw ('GE-2')
    where a full yaml.safe_load raises ComposerError (no usable claim at
    all); (2) a plain scalar folded across an indented continuation line
    ("id: foo\n  bar\n") -- the fast path returned only the first line's
    text ('foo') where a full parse folds the continuation per YAML's
    plain-scalar line-folding rule ({'id': 'foo bar'}). Fixed by making the
    fast path DECLINE (return None, letting the existing full-parse
    fallback run) on both shapes, per _is_document_separator_line and
    _plain_scalar_has_continuation, rather than attempting to reproduce
    ComposerError detection or line-folding in the fast scan itself --
    declining is always safe, answering wrongly is not. Re-verified the
    equivalence harness against this repo's real ~3100-file AC collection
    afterward to confirm the fast path's performance win survives: see the
    sign-off comment for the exact fallback-count and wall-clock numbers.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

from _uniqueness_types import Finding, NamespaceVerdict  # type: ignore[import]

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

    Used when PyYAML is unavailable. Sufficient for extracting a record's
    top-level ``id`` field, which is all this pass needs from an AC file.

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


def _parse_yaml_dict(content: str, source_label: Path) -> dict | None:
    """Parse a YAML string into a dict, preferring PyYAML with a minimal fallback.

    Args:
        content: Raw YAML text read from source_label.
        source_label: Path used in warning messages on parse failure.

    Returns:
        The parsed dict, or None on parse failure or non-dict content.
    """
    if not _YAML_AVAILABLE:
        return _parse_yaml_minimal(content)
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: YAML parse error in {source_label}: {exc}",
            file=sys.stderr,
        )
        return None
    return data if isinstance(data, dict) else None


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
        PyYAML itself is unavailable, since in that case the full-parse
        fallback (`_parse_yaml_minimal`) does not apply YAML's implicit
        resolvers either, so there is nothing for the fast path to diverge
        from.
    """
    if _RESOLVER is None:
        return True
    tag = _RESOLVER.resolve(yaml.nodes.ScalarNode, value, (True, False))
    return tag == _STR_TAG


def _contains_control_character(value: str) -> bool:
    """Detect a raw control character (e.g. an embedded tab) in a plain
    scalar's value text.

    A raw tab -- or other C0 control character -- inside an unquoted YAML
    scalar is not legal token content; a full parse raises ScannerError
    rather than reading it as a string, and this module's contract is that
    an unparsable record yields NO claim (never an invented one). The fast
    path cannot reproduce a parse failure, so it must bail out to the full
    parse whenever one of these characters is present, rather than accept
    text a real parser would reject outright.

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

    Only trusted as "simple" when the value is properly terminated with the
    same quote character and contains no embedded quote or (for
    double-quoted values) backslash escape -- either of which could change
    the value a full YAML parse would produce in a way this cheap scan
    cannot safely reproduce.

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


def _is_document_separator_line(raw_line: str) -> bool:
    """Detect a YAML document-separator line (``---``) at column 0.

    A document separator ANYWHERE in the stream -- including as the very
    first line -- makes this function decline outright (see
    `_fast_scan_top_level_id`'s docstring): a multi-document stream makes
    ``yaml.safe_load`` raise ``ComposerError`` (no usable claim at all), and
    the fast path's single-pass line scan has no cheap way to distinguish
    "a lone leading document-start marker" from "a real second document
    follows" without doing the equivalent of a real parse. Declining on
    every ``---`` line -- even a harmless leading one -- is the safe,
    conservative choice; it costs a handful of extra full-parse fallbacks
    against this store's real collection (see the DECISION HISTORY
    equivalence-harness numbers), never a wrong answer.

    Args:
        raw_line: One line of raw YAML text (no trailing newline).

    Returns:
        True if `raw_line` is a document-separator line: exactly ``---``,
        or ``---`` followed by whitespace (a directives-end marker with
        trailing content on the same line).
    """
    if raw_line == "---":
        return True
    return raw_line.startswith("---") and len(raw_line) > 3 and raw_line[3] in (" ", "\t")


def _plain_scalar_has_continuation(lines: list[str], id_line_index: int) -> bool:
    """Check whether a plain-scalar ``id`` value would be folded together
    with a following, more-indented continuation line under a full YAML
    parse.

    YAML's plain-scalar line-folding rule joins a plain scalar's first line
    with any immediately-following line indented deeper than the key itself
    (column 0 here), skipping blank lines, until it reaches a line at
    column 0 or shallower. The fast path's single-line scan sees only the
    first line and cannot reproduce this folding (see
    "plain_scalar_continuation" in
    unit_tests/commit_guardian/test_ge_122a_1_fast_path_equivalence.py), so
    it must decline whenever a continuation is possible rather than guess.

    Args:
        lines: The full record's lines (``content.splitlines()``).
        id_line_index: Index, within `lines`, of the line holding the
            plain-scalar ``id:`` value being checked.

    Returns:
        True if the first non-blank line after `id_line_index` is indented
        (starts with a space or tab) -- a possible continuation, so the
        caller must decline. False if that line starts at column 0 (a new
        top-level key, or end of content) -- no continuation is possible.
    """
    for line in lines[id_line_index + 1 :]:
        if line.strip() == "":
            continue
        return line[0] in (" ", "\t")
    return False


def _fast_scan_top_level_id(content: str) -> str | None:
    """Cheaply extract a record's top-level ``id`` field via a line scan.

    This is the FAST PATH ahead of a full YAML parse (PyYAML or the minimal
    fallback): a single pass over the raw lines with no parser construction
    at all, which recognizes only the ``id`` value shapes this store's AC
    records actually use in practice -- a bare plain scalar, or a simple
    single/double-quoted plain scalar with no embedded quote, backslash
    escape, or inline comment. Every other shape (block scalars, flow
    collections, anchors/aliases/tags, an inline ``#`` comment, an embedded
    colon) makes this function bail out with None -- "cannot prove this
    matches what yaml.safe_load would produce" -- so the caller falls back
    to a full parse rather than ever guess at the value.

    A quoted value is trusted directly once ``_strip_simple_quoted_scalar``
    proves it simple: a quoted scalar is never subject to YAML's implicit
    resolvers, so ``'007'`` and ``"null"`` stay literal strings under a full
    parse too. An UNQUOTED (plain) value is different: YAML applies implicit
    resolution to plain scalars, coercing tokens like ``null``, ``true``,
    ``no``, ``007``, or ``0x1F`` to a non-string Python value. Rather than
    hand-roll a denylist of such tokens (guesswork that drifts as PyYAML's
    resolver set changes), this function asks PyYAML's own
    ``yaml.resolver.Resolver`` what tag it would assign the plain scalar
    (`_plain_scalar_is_unambiguous_string`) and bails out to a full parse
    whenever that tag is not ``tag:yaml.org,2002:str``. It also bails out on
    any embedded C0 control character (`_contains_control_character`) --
    e.g. a raw tab -- since that makes a full parse raise ScannerError
    (no usable claim), which the fast path cannot reproduce by returning a
    literal string.

    Two further shapes (pr-reviewer finding [H-2]/[H-2b], feedback-id
    fb_2026-08-24_94dc4ba4) also force a decline, because both make this
    function return a WRONG non-None answer rather than merely an
    unrecognized one -- the dangerous case, since a wrong answer is never
    corrected by the caller's None-triggered fallback:
      - A document separator (``---``) ANYWHERE in the stream
        (`_is_document_separator_line`) -- a multi-document stream makes a
        full parse raise ``ComposerError`` (no usable claim at all), where
        the fast path would otherwise return the LAST top-level ``id:``
        line it sees, silently manufacturing a claim a full parse never
        produces.
      - A plain-scalar ``id`` value immediately followed by a
        more-indented continuation line (`_plain_scalar_has_continuation`)
        -- a full parse FOLDS the continuation into the same scalar
        (joined with a single space), where the fast path's single-line
        scan would otherwise return only the first line's text, silently
        dropping the continuation.

    Only a line with zero leading whitespace is treated as top-level, since
    no legal top-level ``id`` in this store's schema is nested under another
    key. When more than one such line is present (a malformed duplicate
    key), the LAST one wins, matching PyYAML's own last-value-wins behavior
    for a mapping with a duplicate key.

    Args:
        content: Raw YAML text of the record.

    Returns:
        The extracted id string, or None if no line unambiguously matches.
    """
    lines = content.splitlines()
    found: str | None = None
    for index, raw_line in enumerate(lines):
        if _is_document_separator_line(raw_line):
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
    """Read one AC YAML file from disk and return its top-level ``id`` field.

    Tries the cheap _fast_scan_top_level_id line-scan first and only falls
    back to a full YAML parse (_parse_yaml_dict) when the fast scan cannot
    prove its result matches a full parse's -- see that function's docstring
    for exactly which shapes are considered unambiguous.

    Fails open per file: an unreadable or unparsable file contributes to the
    namespace's inspected_count (tracked by the caller during the walk) but
    makes no claim, since a file whose id cannot be determined cannot be said
    to have claimed a number.

    Args:
        yaml_path: Path to the .yaml file to read.

    Returns:
        The non-empty ``id`` field value as a string, or None.
    """
    try:
        content = yaml_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read {yaml_path}: {exc}",
            file=sys.stderr,
        )
        return None

    fast_id = _fast_scan_top_level_id(content)
    if fast_id is not None:
        return fast_id

    data = _parse_yaml_dict(content, yaml_path)
    if data is None:
        return None
    record_id = str(data.get("id", "")).strip()
    return record_id or None


# ---------------------------------------------------------------------------
# Namespace verdict assembly
# ---------------------------------------------------------------------------


def _build_namespace_verdict(
    claims: dict[str, list[Path]],
    inspected_count: int,
) -> NamespaceVerdict:
    """Turn a number->claimant-paths map into a NamespaceVerdict.

    A number is only reported when two or more artifacts claim it -- grouping
    by contested number (not by claimant file) is what keeps the finding
    count at "one per collision" rather than "one per file in a collision".

    Args:
        claims: Mapping of claimed number to the list of paths that claim it.
        inspected_count: Total artifacts walked in this namespace.

    Returns:
        The assembled NamespaceVerdict.
    """
    findings = [
        Finding(number=number, paths=[str(p) for p in paths])
        for number, paths in sorted(claims.items())
        if len(paths) > 1
    ]
    return NamespaceVerdict(
        passed=not findings,
        inspected_count=inspected_count,
        findings=findings,
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
        The NamespaceVerdict for the acceptance-criteria namespace. When
        ac_root does not exist at all, reports passed=False with
        inspected_count=0 and an empty findings list -- the root itself was
        never resolved, so this is a misconfiguration, not evidence of a
        genuinely empty namespace. An EXISTING but empty ac_root still
        passes cleanly with inspected_count=0 (see GE-122e-3 "THE CONTRACT
        DECISION" in unit_tests/commit_guardian/test_ge_122e_3_root_resolution.py).
    """
    if not ac_root.is_dir():
        return NamespaceVerdict(passed=False, inspected_count=0, findings=[])

    claims: dict[str, list[Path]] = {}
    inspected_count = 0
    for yaml_path in sorted(ac_root.rglob("*.yaml")):
        inspected_count += 1
        record_id = _read_yaml_id(yaml_path)
        if record_id is None:
            continue
        claims.setdefault(record_id, []).append(yaml_path)

    return _build_namespace_verdict(claims, inspected_count)


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
        The NamespaceVerdict for the namespace rooted at directory. When
        directory does not exist at all, reports passed=False with
        inspected_count=0 and an empty findings list -- the root itself was
        never resolved, so this is a misconfiguration, not evidence of a
        genuinely empty namespace. An EXISTING but empty directory still
        passes cleanly with inspected_count=0 (see GE-122e-3 "THE CONTRACT
        DECISION" in unit_tests/commit_guardian/test_ge_122e_3_root_resolution.py).
    """
    if not directory.is_dir():
        return NamespaceVerdict(passed=False, inspected_count=0, findings=[])

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
