"""
MODULE: build_phases_self_description
GOAL: Supply the one-line fix hints the build prints when an agent template is
    missing a self-description frontmatter field.
BUSINESS CONTEXT: build_phases.py is grandfathered far over the 400-content-line
    check-file-size limit, and the GE-127b-1 ratchet refuses any change that
    leaves it longer than it was. BP-1000a-7 fixed _write() there without
    changing its size, but its DECISION HISTORY entry is counted, so the file
    needed headroom. This helper was the cleanest thing to move: pure, stateless,
    private, with a single caller and no reference from any other file.
ARCHITECTURE: One pure function. build_phases.py imports it at module level so
    validate_agent_self_description() -- its only caller -- is unchanged, the
    same pattern build_phases_knowledge.py and build_phases_product_truth.py
    already follow. It imports nothing from build_phases, so there is no cycle.
"""

from __future__ import annotations

_HINTS: dict[str, str] = {
    "behavioral_patterns": (
        "Add a behavioral_patterns array listing conditional behaviors, "
        "gates, and delegation rules. Example: "
        "behavioral_patterns: [{name: 'Stop-and-Ask', trigger: '...', "
        "behavior: '...', related_agent: null}]"
    ),
    "pre_flight_reads": (
        "Add a pre_flight_reads list of documents the agent reads before "
        "starting work. Example: pre_flight_reads: ['ticket body', "
        "'cited ADRs']"
    ),
    "inputs": (
        "Add an inputs list describing what the agent receives. Example: "
        "inputs: [{name: ticket_path, type: path, description: 'Path to ticket'}]"
    ),
    "outputs": (
        "Add an outputs list describing what the agent produces. Example: "
        "outputs: [{name: 'Sign-off comment', type: comment, "
        "description: 'status: ok | blocker'}]"
    ),
    "mutates": (
        "Add a mutates list describing what the agent modifies. Example: "
        "mutates: [{name: 'Ticket frontmatter', type: file, "
        "description: 'agents.<name>: signed_off'}]"
    ),
}


def _self_desc_field_hint(field: str) -> str:
    """Return a one-line fix hint for a missing self-description frontmatter field.

    Args:
        field: The missing frontmatter field name.

    Returns:
        A short string describing what the field should contain.
    """
    return _HINTS.get(field, f"Populate the '{field}' field in the agent template frontmatter.")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/BP-1000a-7]: Extracted _self_desc_field_hint from
#   build_phases.py to give that file room under the GE-127b-1 ratchet for
#   BP-1000a-7's _write() fix. Pure move with one change of shape: the hint
#   table is now a module-level constant instead of a dict rebuilt on every
#   call. Same keys, same text, same fallback. (#BP-1000a-7)
# ====================================================================
