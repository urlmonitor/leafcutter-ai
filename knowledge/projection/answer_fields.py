"""MODULE: answer_fields
GOAL: Project exact canonical field values and attributable availability metadata.
BUSINESS CONTEXT: Missing work status must never be replaced by lifecycle status.
ARCHITECTURE: Pure mapping of validated source records into disposable projection data.
"""

from __future__ import annotations

AC_FIELDS = (
    "status",
    "req_status",
    "work_status",
    "readiness",
    "priority",
    "level",
    "parent",
    "covered_by",
    "implemented_by",
    "depends_on",
    "test_required",
    "criteria",
)
ENTITY_FIELDS = ("canonical_id", "kind", "title", "source_sha", "source_locator")


def projected_fields(record: dict, has_children: bool) -> dict:
    """Copy source values without defaults, and retain evidence of absent fields.

    Args:
        record: One schema-validated canonical AC record.
        has_children: Whether another canonical AC explicitly names this record as parent.

    Returns:
        Projection properties; criteria text remains behind progressive disclosure.
    """
    values = {name: record[name] for name in AC_FIELDS if name != "criteria" and name in record}
    values["source_fields"] = {
        name: "present" if record.get(name) is not None else "canonical_absent"
        for name in AC_FIELDS
    }
    values["has_children"] = has_children
    values["structural_parent"] = structural_parent(record)
    values["structural_parent_locator"] = "/parent" if record.get("parent") else "/id"
    return values


def mapped_fields(kinds: list[str]) -> dict[str, list[str]]:
    """Advertise mapped field names, not evidence that every record has a value.

    Args:
        kinds: Approved canonical kinds mapped by this generation.

    Returns:
        Mapped field vocabulary for each approved kind.
    """
    return {
        kind: list(ENTITY_FIELDS)
        + (
            (list(AC_FIELDS) + ["structural_parent", "has_children"])
            if kind == "AcceptanceCriterion"
            else []
        )
        for kind in kinds
    }


def structural_parent(record: dict) -> str | None:
    """Use the canonical shared hierarchy algorithm, retaining explicit overrides.

    Args:
        record: Schema-validated canonical AC record.

    Returns:
        Explicit parent or the canonical ID-derived structural parent.
    """
    from scripts.ac_store.ac_parent_id import derive_parent_id

    return record.get("parent") or derive_parent_id(record["id"])


def mapped_relationships(selected: dict) -> list[str]:
    """Advertise the approved mapping vocabulary independent of existing matches.

    Args:
        selected: Approved canonical surface definitions.

    Returns:
        Supported relationship types, including types with no matches at this revision.
    """
    return sorted(
        {
            "component_membership" if field == "components" else field
            for definition in selected.values()
            for field in definition.get("edge_fields", [])
        }
    )


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 18:55 [python-coder]: Keep requested facts separate from execution success and preserve canonical field meaning. (#KM-500/KM-500e-2)
