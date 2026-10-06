"""MODULE: source_excerpt
GOAL: Resolve source locators before bounded disclosure.
BUSINESS CONTEXT: A criteria citation must not silently return the YAML header.
ARCHITECTURE: Pure source-data selection; hashes refer to the entire original file.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Honor locators before slicing bytes. (#TICKET-KM-400d-2)
"""

from __future__ import annotations

import re
from typing import NoReturn

import yaml


def _fail(message: str) -> NoReturn:
    """Refuse an unresolved source selector without falling back to the whole document."""
    raise ValueError(message)


def excerpt(payload: bytes, locator: str) -> bytes:
    """Select a YAML pointer or Markdown heading without inventing source text.

    Args:
        payload: Original source bytes; hashes are computed before excerpting.
        locator: Canonical source pointer, heading or line-range selector.

    Returns:
        Selected immutable source bytes.
    """
    if not locator:
        return payload
    text = payload.decode("utf-8")
    if locator.startswith("/"):
        return _yaml_pointer(text, locator).encode("utf-8")
    if locator.startswith("#"):
        return _heading(text, locator[1:]).encode("utf-8")
    match = re.fullmatch(r"L([1-9][0-9]*)(?:-L?([1-9][0-9]*))?", locator)
    if match:
        start, end = int(match[1]), int(match[2] or match[1])
        if end < start:
            _fail("invalid source locator")
        return "".join(text.splitlines(keepends=True)[start - 1 : end]).encode("utf-8")
    _fail("unsupported source locator")


def _yaml_pointer(text: str, locator: str) -> str:
    """Select the exact YAML or JSON value span for a canonical pointer.

    Args:
        text: Decoded source document preserving whitespace.
        locator: Canonical source pointer, heading or line-range selector.

    Returns:
        Resolved canonical text value.
    """
    node = yaml.compose(text, Loader=yaml.SafeLoader)
    if node is None:
        _fail("source locator has no document")
    for part in locator[1:].split("/"):
        if re.search(r"~(?![01])", part):
            _fail("invalid source locator escape")
        key = part.replace("~1", "/").replace("~0", "~")
        node = _pointer_step(node, key)
    if isinstance(node, yaml.ScalarNode) and node.tag == "tag:yaml.org,2002:str":
        return node.value
    return text[node.start_mark.index : node.end_mark.index]


def _pointer_step(node: yaml.Node, key: str) -> yaml.Node:
    """Select one unique mapping member or canonical nonnegative sequence index."""
    if isinstance(node, yaml.MappingNode):
        matches = [value for name, value in node.value if name.value == key]
        if len(matches) != 1:
            _fail("source locator not found or ambiguous")
        return matches[0]
    if isinstance(node, yaml.SequenceNode) and re.fullmatch(r"0|[1-9][0-9]*", key):
        index = int(key)
        if index < len(node.value):
            return node.value[index]
    _fail("source locator does not select a mapping member or sequence item")


def _heading(text: str, anchor: str) -> str:
    """Select the source span below the requested Markdown heading.

    Args:
        text: Decoded source document preserving whitespace.
        anchor: Markdown heading identifier to locate.

    Returns:
        Resolved canonical text value.
    """
    lines = text.splitlines(keepends=True)
    start = None
    depth = 0
    for position, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match is None:
            continue
        slug = re.sub(r"[^a-z0-9 -]", "", match[2].lower()).replace(" ", "-")
        if start is not None and len(match[1]) <= depth:
            return "".join(lines[start:position])
        if slug == anchor:
            start, depth = position, len(match[1])
    if start is None:
        _fail("source locator not found")
    return "".join(lines[start:])


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 18:55 [python-coder]: Keep requested facts separate from execution success and preserve canonical field meaning. (#KM-500/KM-500e-2)
# - 2026-10-03 18:35 [python-coder]: Resolve exact mapping and sequence pointers for routed evidence, preserving escaped and empty keys while refusing malformed selectors. (#DK-300/entity-context)
