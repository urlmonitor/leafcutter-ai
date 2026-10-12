"""MODULE: requested_fields
GOAL: Read explicitly requested source fields without expanding summary disclosure.
BUSINESS CONTEXT: An authored test specification must be cited before claiming it was retrieved.
ARCHITECTURE: Immutable source-reader port, finite pointers and existing per-item byte bounds.
"""
from __future__ import annotations

import json
import yaml

from knowledge.contracts import Entity, KnowledgeRetrievalRequest
from knowledge.errors import KnowledgeError
from knowledge.ports import SourceResolver

SOURCE_FIELDS = {"test_spec": "/test_spec"}


async def read_fields(node: Entity, request: KnowledgeRetrievalRequest,
                      resolver: SourceResolver | None, remaining: int) -> tuple[dict, dict, dict, list[str]]:
    """Read only offered additional fields at source disclosure, preserving exact source text.

    Args:
        node: Canonical entity with pinned repository, revision, file hash and path.
        request: Original requirements and current disclosure level.
        resolver: Existing trusted immutable source adapter.
        remaining: Unspent source-content bytes for this entity.

    Returns:
        Parsed values, exact excerpts, field availability and explicit limitations.
    """
    fields = request.answer_requirements.required_fields if request.answer_requirements else []
    values, excerpts, availability, limitations = {}, {}, {}, []
    for name in fields:
        if name not in SOURCE_FIELDS:
            continue
        if request.disclosure_level != 3:
            availability[name] = "disclosure_omitted"
            continue
        value, text, reason = await _read(node, name, resolver, remaining)
        availability[name] = reason
        if reason != "present":
            limitations.append(f"requested source field {name} is {reason}")
            continue
        values[name], excerpts[name] = value, text
        remaining -= len(text.encode("utf-8"))
    return values, excerpts, availability, limitations


async def _read(node: Entity, name: str, resolver: SourceResolver | None,
                remaining: int) -> tuple[object, str, str]:
    """Refuse missing, malformed or cut source fields without fabricating absence reasons.

    Args:
        node: Entity identifying an immutable source file.
        name: Finite approved source field.
        resolver: Existing source reader, if configured.
        remaining: Shared byte allowance left after the main source excerpt.

    Returns:
        Actual decoded value and exact text, or explicit unknown/truncated availability.
    """
    if remaining <= 0:
        return None, "", "truncated"
    if resolver is None:
        return None, "", "unknown"
    try:
        reference = node.source.model_copy(update={"locator": SOURCE_FIELDS[name]})
        text = await resolver.read(reference, remaining + 4)
        if len(text.encode("utf-8")) > remaining:
            return None, "", "truncated"
        value = yaml.safe_load(text)
        if not isinstance(value, list) or any(not isinstance(entry, dict) for entry in value):
            return None, "", "unknown"
        json.dumps(value)  # Require JSON-safe source values before constructing the public envelope.
        return value, text, "present"
    except (OSError, ValueError, TypeError, KnowledgeError, yaml.YAMLError):
        return None, "", "unknown"


# DECISION HISTORY
# ================================================================================
# - 2026-10-09 17:00 [python-coder]: Retrieve requested authored test specifications from pinned source with exact field citations. (#KM-500/KM-500e-1-i)
