"""
MODULE: knowledge_frontmatter_reader
GOAL: Stdlib-only YAML/frontmatter reader for the knowledge-query script:
    locate the frontmatter end, strip matched quotes, split flow-sequence
    items, parse inline scalar values, measure line indentation, strip
    inline comments, recognise mapping-item text, parse block-list
    children, and parse both markdown frontmatter (``---`` delimited) and
    plain AC YAML files into a flat field dict.
BUSINESS CONTEXT: Extracted verbatim out of scripts/knowledge_query.py
    (KM-KGS-100a-3-xi) once the KM-KGS-100a-3-i..-x reader-behaviour fixes
    pushed knowledge_query.py's own code length over its origin/main
    baseline, which the check-file-size ratchet (GE-127a-1 / GE-127b-1)
    refuses for an already-oversized file. This is a pure structural move:
    no reader rule from KM-KGS-100a-3-i..-x changed. Every field value this
    reader produces for every real .yaml AC file and every real .md
    frontmatter file in the repository is identical, file for file and
    field for field, to what the pre-extraction reader produced — see the
    whole-store .yaml differential (KM-KGS-100a-3-viii) and the whole-repo
    .md differential (KM-KGS-100a-3-xi's test_km_kgs_100a_3_xi_deploy.py)
    for the 0-mismatch proof this extraction must keep passing.
ARCHITECTURE: Ten functions, all re-exported as attributes of
    knowledge_query — the SAME function objects, not copies — so every
    existing importer keeps working unchanged, including
    scripts/visualise_knowledge_graph.py, which loads knowledge_query.py
    via ``importlib.util.spec_from_file_location`` with no ``scripts/``
    directory on ``sys.path``. knowledge_query locates this sibling module
    relative to its own ``__file__`` (never a hard-coded filename and never
    a ``sys.path`` lookup), so the re-export holds both from the package
    source ``scripts/`` directory and from a deployed consumer's
    ``.leafcutter/scripts/`` directory — see knowledge_query.py's own
    ``_load_reader_module`` for the loader. Stdlib-only: no third-party
    imports, enforced by the same forbidden-import scan applied to
    knowledge_query.py itself (KM-KQS-007).
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Frontmatter parser (stdlib only, mirrors roadmap_query.py pattern)
# ---------------------------------------------------------------------------


def _find_frontmatter_end(lines: list[str]) -> int:
    """Return the index of the closing ``---`` delimiter, or -1 if absent.

    Args:
        lines: All lines of the file. Assumes ``lines[0]`` is ``---``.

    Returns:
        Line index of the closing delimiter, or -1 if not found.
    """
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return i
    return -1


def _strip_matched_quotes(value: str) -> str:
    """Strip a matched surrounding pair of quote characters from a value.

    Only strips when the first and last character are the same quote
    character (both double or both single). A quote character elsewhere in
    the string — including one at only one end — is left untouched, so an
    unquoted item containing an interior quote is never corrupted.

    Args:
        value: Candidate string, already trimmed of surrounding whitespace.

    Returns:
        The value with a matched surrounding quote pair removed, or the
        original value when no matched pair is present.
    """
    if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
        return value[1:-1]
    return value


def _split_flow_sequence_items(inner: str) -> list[str]:
    """Split the inner text of a YAML flow sequence on commas, quote-aware.

    A comma inside a matched single- or double-quoted region is treated as
    part of the item's text rather than an item separator, so a quoted item
    whose free text contains commas (e.g. a ``::test_function`` suffix that
    happens to read like a sentence) is not split into fragments.

    Args:
        inner: Text between the ``[`` and ``]`` of an inline flow sequence.

    Returns:
        List of raw (still possibly quoted) item strings, split on the
        unquoted commas only.
    """
    items: list[str] = []
    current: list[str] = []
    quote_char: str | None = None
    for ch in inner:
        if quote_char is not None:
            current.append(ch)
            if ch == quote_char:
                quote_char = None
            continue
        if ch in ('"', "'"):
            quote_char = ch
            current.append(ch)
            continue
        if ch == ",":
            items.append("".join(current))
            current = []
            continue
        current.append(ch)
    items.append("".join(current))
    return items


def _parse_scalar_value(raw: str) -> Any:
    """Parse an inline scalar YAML value string.

    Handles booleans, null, quoted strings, empty flow sequences (``[]``),
    and simple non-nested flow sequences (``[item1, item2]``).

    Args:
        raw: Trimmed right-hand side of a ``key: value`` YAML line.

    Returns:
        True, False, None, a list (for flow-sequence syntax), or a string.
    """
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in ("null", "~"):
        return None
    if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
        return raw[1:-1]
    # Handle inline YAML flow sequences: [] or [item1, item2, ...]
    # Only handles simple non-nested cases (sufficient for AC YAML files).
    if len(raw) >= 2 and raw[0] == "[" and raw[-1] == "]":
        inner = raw[1:-1].strip()
        if not inner:
            return []
        raw_items = _split_flow_sequence_items(inner)
        items = [_strip_matched_quotes(item.strip()) for item in raw_items]
        return [item for item in items if item]
    return raw


_MAPPING_ITEM_PATTERN = re.compile(r"^[\w][\w_-]*:(\s|$)")


def _line_indent(line: str) -> int:
    """Return the number of leading space characters on a line.

    Args:
        line: A raw (unstripped) line of text.

    Returns:
        Count of leading space characters. Tabs are not treated as
        indentation for this purpose since the AC/frontmatter block lists
        this reader handles are space-indented.
    """
    return len(line) - len(line.lstrip(" "))


def _strip_inline_comment(value: str) -> str:
    """Strip a trailing ``# comment`` from a block-list item's raw text.

    A ``#`` preceded by at least one space or tab starts a comment; the
    text before it is returned with trailing whitespace trimmed off. A
    ``#`` with no preceding whitespace (glued to a token, e.g.
    ``path#symbol``) is left untouched, consistent with
    KM-KGS-100a-3-v. A ``#`` inside a matched quoted span (single or
    double) is also left untouched — the scan tracks quote state so an
    interior ``#`` is never mistaken for a comment start, consistent with
    KM-KGS-100a-3-iii. When a quoted item is followed by trailing text
    (e.g. ``"a b"  # note``), the comment is detected after the closing
    quote and the quotes themselves are left for a later
    ``_strip_matched_quotes`` call to remove.

    Args:
        value: Item text with the leading ``- `` (or nothing, for a
            continuation line) already removed and outer whitespace
            already trimmed.

    Returns:
        The value with a trailing comment removed, or unchanged when no
        comment-starting ``#`` is found.
    """
    quote_char: str | None = None
    for i, ch in enumerate(value):
        if quote_char is not None:
            if ch == quote_char:
                quote_char = None
            continue
        if ch in ('"', "'"):
            quote_char = ch
            continue
        if ch == "#" and i > 0 and value[i - 1] in (" ", "\t"):
            return value[:i].rstrip()
    return value


def _is_mapping_item_text(text: str) -> bool:
    """Return True when a list item's text looks like a YAML mapping entry.

    Matches a leading ``key:`` (word characters, hyphens or underscores)
    followed by whitespace or end-of-string, e.g. ``path: unit_tests/x.py``.
    Used to decide whether a deeper-indented continuation line should fold
    into the item's value (plain scalar) or be discarded (mapping item —
    the produced value for a mapping item is an explicit non-goal per
    KM-KGS-100a-3-x).

    Args:
        text: Item text with any trailing comment already stripped, but
            with quotes not yet stripped.

    Returns:
        True when the text looks like a mapping item's first field.
    """
    return bool(_MAPPING_ITEM_PATTERN.match(text))


def _parse_block_children(lines: list[str], start: int, end: int) -> tuple[list[str], int]:
    """Collect YAML list items from lines following a bare ``key:`` line.

    Accepts ``- item`` lines at any indentation — column zero, two spaces,
    four spaces, or any other depth — since indentation is not itself
    significant to YAML block-list membership. The indentation of the
    list's *first* item fixes the item column for the rest of the list: a
    later line is a new item only when it is a ``- `` line at that same
    column. A deeper-indented ``- `` line (e.g. a nested list inside a
    mapping item, as in ``docs/acceptance-criteria/index.yaml``'s
    ``components`` -> ``directory_patterns``) is therefore never mistaken
    for a sibling item of this list.

    Blank lines and comment lines (a line whose first non-space character
    is ``#``, at any indentation including column zero) are skipped: they
    neither end the list nor become an item, even when a column-zero
    comment's text happens to look like a ``key: value`` line (e.g.
    ``# covers: KM-EX-010``).

    A non-blank, non-comment line indented deeper than the item column
    continues the current item rather than ending the list. For a plain
    scalar item the continuation is folded in — joined to the preceding
    text with a single space, its own leading indentation stripped — the
    same way PyYAML folds a wrapped plain scalar. For a mapping item (item
    text matching ``key: value``) continuation lines are discarded rather
    than folded, since the resulting value for a mapping item is an
    explicit non-goal; discarding still guarantees the continuation never
    ends the list and never absorbs the next top-level key's items.

    The scan stops at the first non-blank, non-comment line that is
    neither a same-column ``- `` item nor a deeper continuation — in
    practice, the next top-level key — so a differently-indented list
    belonging to a following key is never absorbed into this one.

    A trailing ``# comment`` on an unquoted item is stripped (see
    ``_strip_inline_comment``); a comment glued to a token or inside a
    quoted item is preserved.

    Args:
        lines: All lines of the file.
        start: Index of the first line after the bare ``key:`` line.
        end: Index of the closing ``---`` delimiter (or end of file).

    Returns:
        A tuple of (list_of_items, next_line_index).
    """
    children: list[str] = []
    current_value: str | None = None
    current_is_mapping = False
    item_indent: int | None = None
    j = start

    while j < end:
        raw_line = lines[j]
        stripped = raw_line.strip()
        if stripped == "" or stripped.startswith("#"):
            j += 1
            continue

        indent = _line_indent(raw_line)
        is_item_line = stripped.startswith("- ") and (
            item_indent is None or indent == item_indent
        )
        if is_item_line:
            if current_value is not None:
                children.append(_strip_matched_quotes(current_value))
            item_indent = indent
            current_value = _strip_inline_comment(stripped[2:].strip())
            current_is_mapping = _is_mapping_item_text(current_value)
            j += 1
            continue

        if item_indent is not None and indent > item_indent:
            if not current_is_mapping:
                cont_text = _strip_inline_comment(stripped)
                current_value = f"{current_value} {cont_text}"
            j += 1
            continue

        break

    if current_value is not None:
        children.append(_strip_matched_quotes(current_value))
    return children, j


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Extract YAML frontmatter fields from a markdown file's text.

    Args:
        text: Full text content of a file.

    Returns:
        Dict of frontmatter field names to values. Empty dict when absent.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = _find_frontmatter_end(lines)
    if end == -1:
        return {}
    fm: dict[str, Any] = {}
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip() or line.startswith("  "):
            i += 1
            continue
        m = re.match(r"^(\w[\w_-]*):\s*(.*)", line)
        if not m:
            i += 1
            continue
        key = m.group(1)
        raw = m.group(2).strip()
        if raw == "":
            children, i = _parse_block_children(lines, i + 1, end)
            if children:
                fm[key] = children
            continue
        fm[key] = _parse_scalar_value(raw)
        i += 1
    return fm


def _parse_yaml_file(text: str) -> dict[str, Any]:
    """Parse a plain YAML file (no ``---`` delimiters) and return a flat field dict.

    Handles only the scalar and block-list syntax used by AC YAML files:
    - ``key: value`` scalar lines at column 0
    - ``key: |`` multiline block scalars (value collected as-is)
    - ``key:`` bare lines followed by indented ``- item`` list lines

    This is intentionally minimal — it covers the AC YAML schema and nothing
    more. It does not support nested mappings, anchors, or flow scalars.
    Stdlib-only: no third-party imports (PyYAML is explicitly excluded by the
    project's stdlib-only policy and by the AC test suite's forbidden-imports
    check).

    Args:
        text: Full text content of a YAML file (no frontmatter delimiters).

    Returns:
        Dict of field names to parsed values.  Empty dict on empty input.
    """
    lines = text.splitlines()
    total = len(lines)
    result: dict[str, Any] = {}
    i = 0
    while i < total:
        line = lines[i]
        # Skip blank lines and comment lines
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        # Skip indented lines at the top level (they belong to a prior block)
        if line.startswith("  ") or line.startswith("\t"):
            i += 1
            continue
        m = re.match(r"^(\w[\w_-]*):\s*(.*)", line)
        if not m:
            i += 1
            continue
        key = m.group(1)
        raw = m.group(2).strip()
        # Block scalar indicator ``|`` or ``>``
        if raw in ("|", ">"):
            # Collect all indented lines following as a single string
            block_lines: list[str] = []
            i += 1
            while i < total and (lines[i].startswith("  ") or lines[i].startswith("\t") or lines[i].strip() == ""):
                block_lines.append(lines[i])
                i += 1
            # Dedent by 2 spaces if applicable, then join
            dedented = []
            for bl in block_lines:
                if bl.startswith("  "):
                    dedented.append(bl[2:])
                elif bl.startswith("\t"):
                    dedented.append(bl[1:])
                else:
                    dedented.append(bl)
            result[key] = "\n".join(dedented).rstrip()
            continue
        # Bare key — may be followed by block list items
        if raw == "":
            children, i = _parse_block_children(lines, i + 1, total)
            if children:
                result[key] = children
            continue
        # Inline scalar value
        result[key] = _parse_scalar_value(raw)
        i += 1
    return result


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-17 12:00 [python-coder]: Extracted verbatim from
  scripts/knowledge_query.py. (#TICKETLESS reason=km-kgs-100a-3-xi-fastlane)
  Moved the ten reader functions (_find_frontmatter_end,
  _strip_matched_quotes, _split_flow_sequence_items, _parse_scalar_value,
  _line_indent, _strip_inline_comment, _is_mapping_item_text,
  _parse_block_children, _parse_frontmatter, _parse_yaml_file) plus the
  _MAPPING_ITEM_PATTERN constant they share, unchanged, into this new
  sibling module — no reader rule from KM-KGS-100a-3-i..-x changed. Done
  because knowledge_query.py's code length (1104 content lines) exceeded
  its origin/main baseline (1013), which the check-file-size ratchet
  refuses for an already-oversized file. knowledge_query.py re-exports all
  ten names as the SAME function objects (see its own
  ``_load_reader_module``), so every existing caller and importer —
  including scripts/visualise_knowledge_graph.py's
  ``spec_from_file_location`` load with no ``scripts/`` on ``sys.path`` —
  keeps working unchanged. Deployment wiring
  (scripts/build_phases_knowledge.py, scripts/build.py,
  scripts/build_phases_workflows.py) updated in the same change so this
  module ships alongside knowledge_query.py in every consumer install.
====================================================================
"""
