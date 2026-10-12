"""MODULE: product_truth_text
GOAL: Serialize and replace derived AC backlinks without changing adjacent YAML.
BUSINESS CONTEXT: Product-flow links must remain reproducible and preserve authored metadata.
ARCHITECTURE: Pure text helpers used by the single-writer generator; no filesystem writes.

DECISION HISTORY
- 2026-10-02 14:20 [commit]: Extract unchanged backlink serialization and replacement
  from the oversized generator, preserving its public imports and regression fix.
  (#TICKETLESS reason=retrieval-publication-size-ratchet)
"""
from __future__ import annotations

import re

# Include indentless sequence items and column-zero comments; stop at the
# next top-level field or document boundary. Preserve comments on removal.
_PRODUCT_TRUTH_BLOCK = re.compile(r"^product_truth:.*?(?=^(?!-(?:\s|$)|#)\S|\Z)", re.MULTILINE | re.DOTALL)


def serialize_product_truth(entries: list) -> str:
    """Deterministically serialize a product_truth list as a YAML block.

    Hand-rolled (not yaml.dump) to guarantee byte-stable, 2-space-indented output
    that matches the surrounding AC store style and round-trips through
    yaml.safe_load to exactly the input entries.
    """
    lines = ["product_truth:"]
    for entry in entries:
        lines.append(f"  - flow: {entry['flow']}")
        lines.append(f"    node: {entry['node']}")
        lines.append(f"    node_kind: {entry['node_kind']}")
        lines.append(f"    flow_kind: {entry['flow_kind']}")
        lines.append(f"    screen: {_scalar(entry['screen'])}")
        lines.append(f"    mock_data: {_scalar(entry['mock_data'])}")
        if entry["entities"]:
            lines.append("    entities:")
            lines.extend(f"      - {entity}" for entity in entry["entities"])
        else:
            lines.append("    entities: []")
        lines.append(f"    source: {entry['source']}")
        lines.append(f"    asof: '{entry['asof']}'")
    return "\n".join(lines) + "\n"


def _scalar(value) -> str:
    """Render a controlled-vocabulary scalar (or None) as a YAML plain scalar."""
    return "null" if value is None else str(value)


def apply_product_truth_text(text: str, entries: list) -> str:
    """Return AC file text with its product_truth block replaced (or removed)."""
    stripped = _PRODUCT_TRUTH_BLOCK.sub(
        lambda match: "".join(line for line in match[0].splitlines(keepends=True) if line.startswith("#")), text)
    if entries:
        return stripped.rstrip("\n") + "\n" + serialize_product_truth(entries)
    if stripped and not stripped.endswith("\n"):
        return stripped + "\n"
    return stripped
