"""
Authoring-stage "could not establish" message assembly for GE-122d-3.

MODULE: _identifier_uniqueness_could_not_establish
GOAL: Build the GE-122d-3 could-not-establish JSON entries and the
    human-readable message lines the authoring-time PostToolUse hook
    (``templates/hooks/check_identifier_uniqueness_authoring.py``) prints
    when the shared whole-collection uniqueness pass reports at least one
    individually unreadable or unparsable artifact. Split out of that
    sibling hook module to keep it under the project's 400-line file-size
    ratchet (``check_file_size.py`` / GE-127b-1: an already-oversized file
    may not grow past its previous length) after adding this AC's own logic
    pushed it over that ceiling.
BUSINESS CONTEXT: GE-122d-3 requires the same three statements at every
    stage a namespace could not establish uniqueness for -- the named
    artifact, an explicit "not established" statement, and the attempted
    read count. At the authoring stage specifically, the author already
    knows about the file they just wrote, so the count that matters to them
    is how many OTHER, pre-existing artifacts in the namespace were actually
    inspected -- this module's ``build_could_not_establish_entries`` excludes
    that one file from the reported count when it falls inside the affected
    namespace's own root, so this stage reports the same count the
    commit-time and shared-build stages would report for an otherwise-
    identical pre-existing collection.
ARCHITECTURE: Pure functions, no I/O of their own -- consumed by
    ``check_identifier_uniqueness_authoring.py``'s ``evaluate_identifier_uniqueness``
    and ``_build_block_message``. Lives in ``scripts/commit_guardian/``
    (deployed wholesale by ``build_commit_guardian`` -- an ``rglob("*")``
    directory copy with NO underscore-prefix skip, unlike
    ``templates/hooks/*.py``'s wildcard deploy mapping, which deliberately
    SKIPS any filename starting with ``_`` per ``_per_platform_mappings``).
    An earlier version of this split placed this module directly under
    ``templates/hooks/`` as a plain sibling of the authoring hook; that
    silently never deployed at all, because the hooks glob's underscore
    skip treats a leading underscore as "not a hook" (see DECISION HISTORY
    below). The authoring hook therefore locates this module the same way
    it already locates the cross-directory shared uniqueness module --
    ``_find_shared_module_path``'s ancestor walk -- rather than a plain
    same-directory import, since this module now lives one level away from
    the hook that consumes it.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-3.yaml
  - templates/hooks/check_identifier_uniqueness_authoring.py
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py

DECISION HISTORY:
  - 2026-09-07 [python-coder/GE-122d-3]: Extracted from
    check_identifier_uniqueness_authoring.py, which had grown to 752 lines
    (previous HEAD length 572, already past the 400-line limit) after this
    AC's could-not-establish additions -- check_file_size.py's ratchet
    (GE-127b-1) refuses an already-oversized file that grows past its own
    previous length, so the new logic had to move to a fresh sibling file
    rather than staying inline.
  - 2026-09-07 [python-coder/GE-122d-3, bug-fix]: Moved from
    ``templates/hooks/_identifier_uniqueness_could_not_establish.py`` (the
    first split attempt) to this location. Reproduced empirically:
    ``test_ge_122d_1.py``'s own ``test_shared_module_imports_from_both_deployed_layouts``
    built a real deployed fixture via ``build_hooks()`` and the deployed
    ``check_identifier_uniqueness_authoring.py`` raised
    ``ModuleNotFoundError: No module named '_identifier_uniqueness_could_not_establish'``
    -- the hooks-directory wildcard deploy mapping (``_per_platform_mappings``
    in ``build_phases.py``) explicitly skips any ``templates/hooks/*.py``
    filename starting with ``_``, so the sibling file was never copied to
    ANY deployed hooks directory at all. ``scripts/commit_guardian/`` has no
    such filter (``build_commit_guardian`` deploys every file under it via
    ``rglob("*")``), matching where this repo's other underscore-prefixed
    shared modules (``_uniqueness_types.py``, ``_commit_disposition.py``,
    ...) already live.
"""

from __future__ import annotations

from pathlib import Path

#: Each namespace's own root, relative to the collection root passed to
#: run_uniqueness_pass -- mirrors run_uniqueness_pass's own namespace wiring
#: in check_identifier_uniqueness.py (GE-122d-3). Used only to decide whether
#: the file the author just wrote falls inside a given namespace, so its own
#: read can be excluded from that namespace's could-not-establish message
#: (see namespace_contains_edited_path) -- never used to decide pass/fail.
NAMESPACE_RELATIVE_ROOTS: dict[str, tuple[str, ...]] = {
    "acceptance-criteria": ("docs", "acceptance-criteria"),
    "decisions": ("docs", "architecture", "adrs"),
    "diagrams": ("docs", "architecture", "diagrams"),
    "work-items": ("tickets",),
}


def namespace_contains_edited_path(namespace: str, root_path: str, edited_path: str | None) -> bool:
    """Return True iff ``edited_path`` falls under ``namespace``'s own root.

    Used only to decide whether the file the author just wrote should be
    excluded from a could-not-establish message's reported inspected_count
    (GE-122d-3): the author already knows about their own new file, so the
    number that matters to them is how many OTHER, pre-existing artifacts in
    the namespace were actually inspected -- letting the authoring-time
    message report the same count the commit-time and shared-build stages
    would report for an otherwise-identical pre-existing collection, rather
    than one inflated by the very write that triggered this evaluation. Never
    used to decide pass/fail or blocking -- purely a message-count
    adjustment.

    Args:
        namespace: The namespace name (a key of NAMESPACE_RELATIVE_ROOTS).
        root_path: The collection root passed to run_uniqueness_pass.
        edited_path: The author's just-written file path, or None/empty when
            the PostToolUse payload named no usable path.

    Returns:
        True iff `edited_path` is set, resolvable, and falls under this
        namespace's own root directory.
    """
    if not edited_path:
        return False
    relative_parts = NAMESPACE_RELATIVE_ROOTS.get(namespace)
    if relative_parts is None:
        return False
    namespace_root = Path(root_path).joinpath(*relative_parts)
    try:
        return Path(edited_path).resolve().is_relative_to(namespace_root.resolve())
    except (OSError, ValueError):
        return False


def build_could_not_establish_entries(verdict, root_path: str, edited_path: str | None) -> list[dict]:
    """Build the ``could_not_establish`` JSON entries for every namespace
    holding at least one individually unreadable or unparsable artifact.

    Args:
        verdict: The UniquenessVerdict from ``run_uniqueness_pass``.
        root_path: The collection root that produced ``verdict``.
        edited_path: The author's just-written file path, or None -- see
            ``namespace_contains_edited_path``.

    Returns:
        List of ``{"namespace": str, "unreadable_paths": [str, ...],
        "inspected_count": int}`` entries, one per namespace with a
        non-empty ``unreadable_paths``. ``inspected_count`` excludes the
        author's own just-written file when it falls inside that namespace's
        root (see ``namespace_contains_edited_path``'s docstring for why).
    """
    entries = []
    for namespace, namespace_verdict in sorted(verdict.namespaces.items()):
        if not namespace_verdict.unreadable_paths:
            continue
        inspected_count = namespace_verdict.inspected_count
        if namespace_contains_edited_path(namespace, root_path, edited_path):
            inspected_count = max(0, inspected_count - 1)
        entries.append(
            {
                "namespace": namespace,
                "unreadable_paths": list(namespace_verdict.unreadable_paths),
                "inspected_count": inspected_count,
            }
        )
    return entries


def append_could_not_establish_lines(lines: list[str], evaluation: dict) -> None:
    """Append the GE-122d-3 could-not-establish statements to a block message.

    For each namespace holding at least one individually unreadable or
    unparsable artifact, names every such artifact, then states explicitly
    that uniqueness for that namespace was not established and how many of
    its artifacts were actually read -- the same three statements GE-122d-3
    requires at every stage, never reverting the author's own just-written
    file (this function only appends text; it performs no filesystem I/O).

    Args:
        lines: The message lines built so far; mutated in place.
        evaluation: The parsed JSON payload returned by
            ``evaluate_identifier_uniqueness``.
    """
    for entry in evaluation.get("could_not_establish", []):
        namespace = entry["namespace"]
        inspected_count = entry["inspected_count"]
        unreadable_paths = entry["unreadable_paths"]
        for path in unreadable_paths:
            lines.append(f"  could not read or parse: {path}")
        lines.append(
            f"  namespace '{namespace}': uniqueness was NOT established "
            f"({inspected_count} inspected, {len(unreadable_paths)} could not be read or parsed)."
        )
