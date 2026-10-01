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
            raise ValueError("invalid source locator")
        return "".join(text.splitlines(keepends=True)[start - 1 : end]).encode("utf-8")
    raise ValueError("unsupported source locator")


def _yaml_pointer(text: str, locator: str) -> str:
    """Select the exact YAML or JSON value span for a canonical pointer.

    Args:
        text: Decoded source document preserving whitespace.
        locator: Canonical source pointer, heading or line-range selector.

    Returns:
        Resolved canonical text value.
    """
    import yaml

    node = yaml.compose(text, Loader=yaml.SafeLoader)
    for part in locator.lstrip("/").split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, yaml.MappingNode):
            raise ValueError("source locator is not a mapping key")
        matches = [value for name, value in node.value if name.value == key]
        if len(matches) != 1:
            raise ValueError("source locator not found or ambiguous")
        node = matches[0]
    if isinstance(node, yaml.ScalarNode) and node.tag == "tag:yaml.org,2002:str":
        return node.value
    return text[node.start_mark.index : node.end_mark.index]


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
        raise ValueError("source locator not found")
    return "".join(lines[start:])


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 18:55 [python-coder]: Keep requested facts separate from execution success and preserve canonical field meaning. (#KM-500/KM-500e-2)
