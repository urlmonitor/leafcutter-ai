"""
MODULE: kernel.observability.observation_map
GOAL: Map the kernel's span kinds and names to Langfuse observation types per the design's
    observation map.
BUSINESS CONTEXT: Langfuse filters and dashboards depend on observation types; nodes, native
    graph capabilities, the retrieval adapter and retrieval sources must be distinguishable at a
    glance instead of all appearing as plain spans (design part 5).
ARCHITECTURE: Pure function used by LangfuseTracer. Callers keep passing their own kinds
    ("node", "capability", ...) so the scheduler stays free of Langfuse vocabulary; the mapping
    lives here. Kinds that already are Langfuse types pass through unchanged.
"""

from __future__ import annotations

LANGFUSE_TYPES = frozenset({"span", "agent", "tool", "chain", "retriever", "evaluator",
                            "guardrail"})
#: Span kind used by callers -> Langfuse type (capability is refined by name below).
KIND_TO_TYPE = {"node": "chain", "capability": "agent", "retrieval": "retriever",
                "retriever": "retriever", "tool": "tool"}
#: Capability ids backed by the retrieval adapter (a tool, not an agent graph).
RETRIEVAL_ADAPTER_PREFIX = "capability.retrieve."


def observation_type(name: str, kind: str) -> str:
    """Return the Langfuse observation type for a span.

    Args:
        name: Observation name, for example `capability.retrieve.repository`.
        kind: Caller-supplied kind (`node`, `capability`, `retriever` or a Langfuse type).

    Returns:
        str: One of the Langfuse observation types; unknown kinds fall back to `span`.
    """
    if kind == "capability" and name.startswith(RETRIEVAL_ADAPTER_PREFIX):
        return "tool"
    if kind in LANGFUSE_TYPES:
        return kind
    return KIND_TO_TYPE.get(kind, "span")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 00:30 [python-coder]: Mapping is tracer-side (not in scheduler nodes) because
#   context.py and nodes_execute.py pass "node"/"capability" kinds and are outside this
#   change's boundary; the retrieval adapter is recognised by its `retrieve.` id prefix.
#   (#KernelBootstrapV0/OBS)
# ====================================================================
