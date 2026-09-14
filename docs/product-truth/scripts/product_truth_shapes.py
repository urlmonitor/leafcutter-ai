"""
MODULE: product_truth_shapes
GOAL: Carry the record through a field reshape -- read a field in its old and
    new shape, write it only in the new one -- and report a newly introduced
    field that has not been filled in yet (UXP-700e-3-i).
BUSINESS CONTEXT: A step's `expands_to` was a single child-journey id; the shape
    wants a list, so one step can drill into more than one journey. Measured on
    2026-09-07 it was a string in 3 journeys (5 steps). Rewriting every journey
    in one migration would land an unreviewable diff and break any artifact a
    reader still holds in the old shape, so the reshape is read-both /
    write-new: every reader accepts both shapes, and every writer emits only
    the list, so the string shape disappears as journeys are rewritten.
    A branch's `outcome_kind` is new (present in 0 journeys). While it is being
    introduced its absence is a field to fill, reported as such, never a
    violation -- the first enforcement of a new field warns rather than blocks
    (UXP-700e-1-i's transition window).
ARCHITECTURE: Pure, stateless leaf module. `expansion_targets` is the one read
    of `expands_to` every consumer goes through (generator rollup, hierarchy
    maps, cycle and dangling-reference checks), so no consumer can be left
    reading only one shape. `normalise_flow_shapes` is applied by load_flows(),
    the single journey reader, so whatever the generator writes back is already
    in the new shape.
"""
from __future__ import annotations

#: The declared kinds of a branch outcome: another valid route to the goal, a
#: failure that is recovered from or reported, or an exit that ends the journey
#: before its goal. Mirrored by the enum in flow.schema.json.
OUTCOME_KINDS = ("alternative", "failure", "exit")


def expansion_targets(node: dict) -> list[str]:
    """Return the child journey ids a node drills into, in either shape.

    Args:
        node: A step or branch.

    Returns:
        A single-value `expands_to` as a list holding that one id; a list as
        written; an absent or empty one as an empty list.
    """
    value = node.get("expands_to")
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)


def normalise_flow_shapes(flow: dict) -> dict:
    """Rewrite *flow*'s reshaped fields into their new shape, in place.

    Args:
        flow: A journey as read from disk.

    Returns:
        The same journey, every `expands_to` now a list, so anything written
        from it is written only in the new shape.
    """
    for node in [*flow.get("steps", []), *flow.get("branches", [])]:
        if isinstance(node.get("expands_to"), str):
            node["expands_to"] = expansion_targets(node)
    return flow


def combine_statuses(statuses: list[str]) -> str:
    """Roll several impl statuses into one: all done -> done, none started -> not_started.

    Anything else -- any in_progress, or a mix -- is in_progress. An empty list is
    not_started.
    """
    if statuses and all(status == "done" for status in statuses):
        return "done"
    if all(status == "not_started" for status in statuses):
        return "not_started"
    return "in_progress"


def count_branches(flows: dict) -> int:
    """Return how many branches the journeys carry."""
    return sum(len(flow.get("branches") or []) for flow in flows.values())


def _check_outcome_kinds(flows: dict, warnings: list[str]) -> int:
    """Report each journey's branches that carry no outcome kind yet.

    One warning per journey, naming its unfilled branches. Never an error: the
    field is being introduced, so its absence is work to do, not a violation.

    Args:
        flows: ``{flow_id -> flow}``.
        warnings: Shared warning list.

    Returns:
        How many branches still need an outcome kind.
    """
    unfilled = 0
    for flow_id, flow in sorted(flows.items()):
        missing = [branch.get("id", "?") for branch in flow.get("branches") or [] if not branch.get("outcome_kind")]
        if missing:
            unfilled += len(missing)
            warnings.append(
                f"[to-be-filled] {flow_id}: branches {', '.join(repr(m) for m in missing)} have no "
                f"outcome_kind yet -- a field being introduced, to be filled with one of {', '.join(OUTCOME_KINDS)}"
            )
    return unfilled


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder]: UXP-700e-3-i -- new module. `expands_to` is read as
  a string or a list and written as a list; `outcome_kind` absence warns as
  to-be-filled. The AC names no outcome vocabulary, so the three kinds are
  chosen by reading the 17 branches in the store: each reads as one of them
  (a declined payment is a failure, an empty cart an exit, a mockup-only
  authoring route an alternative). Filling them in is left to the authors.
  A step expanding into several journeys rolls up with the same rule a step's
  own ACs do (combine_statuses), so one child expanded behaves exactly as the
  single-value shape did. (#EPIC-TruthfulProjectRecord/44)
====================================================================
"""
