"""
MODULE: unit_tests/ac_store/_reachability_anchor.py
GOAL: Shared, non-collected predicate deciding whether a real-store AC record can
    anchor the derived-test reachability-floor assertions in
    test_derived_test_reachability_floor.py.
WHY: The generator emits ``## Test Requirements`` for a record with no authored
    ``test_spec`` only when an implementation ``.py`` is in scope. The predicate
    is computed here independently from the record's own fields, deliberately
    not by calling the generator's private gate, so choosing an anchor and then
    asserting the generator emits a block is not tautological.
"""

from __future__ import annotations

_EDIT_SURFACE_RELATIONSHIPS = frozenset(
    {"constrains", "creates", "implements", "modifies", "specifies"}
)


def is_implementation_py(path: object) -> bool:
    """Return True when *path* names a non-test ``.py`` outside docs/ and tickets/."""
    if not isinstance(path, str):
        return False
    segments = [s for s in path.strip().replace("\\", "/").split("/") if s not in ("", ".")]
    if not segments or not segments[-1].endswith(".py"):
        return False
    if "docs" in segments[:-1] or "tickets" in segments[:-1]:
        return False
    base = segments[-1]
    return not (base.startswith("test_") or base.endswith("_test.py"))


def declares_implementation_py(record: dict) -> bool:
    """Return True when the record's OWN fields put an implementation .py in scope.

    A structured ``it_requirements.reference_file_path``, or a ``doc_links``
    entry on an edit-surface relationship (or a plain string path), that names
    an implementation ``.py``. An un-enriched draft carries neither.
    """
    it_req = record.get("it_requirements")
    if isinstance(it_req, dict) and is_implementation_py(it_req.get("reference_file_path")):
        return True
    for link in record.get("doc_links") or []:
        if isinstance(link, str) and is_implementation_py(link):
            return True
        if (
            isinstance(link, dict)
            and link.get("relationship") in _EDIT_SURFACE_RELATIONSHIPS
            and is_implementation_py(link.get("path"))
        ):
            return True
    return False
