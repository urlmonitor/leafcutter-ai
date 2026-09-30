#!/usr/bin/env python3
"""
MODULE: _gtfa_store
GOAL: Find things in the two stores the generator reads — an AC record by id in
    the acceptance-criteria store, an already-generated ticket by its
    ``source_ac`` in the tickets tree — and turn an AC's dependency edges
    (``depends_on`` AND ``expects_from``, a list of AC ids either way) into a
    ticket-level ``depends_on`` the frontmatter guard accepts.
BUSINESS CONTEXT: A generated ticket is standalone — one ticket per AC — but
    the source AC's ``depends_on`` speaks in AC ids, and so does ``ac_id`` on
    an ``expects_from`` entry: both name a producer AC this record's ticket
    must run after. ``ticket_frontmatter_guard`` requires every ticket
    ``depends_on`` entry to resolve to a sibling ticket FILE in the same
    folder, so copying either AC value verbatim hard-blocks the generated
    ticket with "depends_on references missing file" (ACD-400b-7). The
    translation is therefore not cosmetic: it is what makes the ticket
    dispatchable at all. KI-ACD-20260921 (Defect 1): before this module read
    ``expects_from`` too, a record whose authoring convention omitted
    ``depends_on`` lost the edge outright even when ``expects_from`` named the
    exact same producer.
ARCHITECTURE: Both lookups are whole-tree scans that swallow per-file read and
    parse errors and continue, because one unreadable record in a 4000-record
    store must not stop a generation. A dropped ``depends_on`` entry is
    WARNED about by name rather than dropped in silence — the drop is
    load-bearing (it keeps the ticket guard-valid) but it is still a loss, and
    an unexplained loss is indistinguishable from a bug.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)

logger = logging.getLogger(_gtfa_seams.logger_name())

# ``AcRecord`` is bound at RUNTIME by the ``else`` branch, off the sibling
# module object resolved above through importlib under a prefix COMPUTED from
# ``__name__`` -- see the "Sibling wiring" note in generate_ticket_from_ac.py
# for why a literal relative import there would break one of the two supported
# layouts. A computed name is opaque to a type checker, so that rebind reads as
# a VARIABLE and mypy rejects every annotation using it ("Variable ... is not
# valid as a type"). The TYPE_CHECKING branch declares the alias statically and
# is never executed, so the runtime binding is unchanged.
if TYPE_CHECKING:  # pragma: no cover - a static declaration, never executed
    from ._gtfa_constants import AcRecord
else:
    AcRecord = _gtfa_constants.AcRecord


# ---------------------------------------------------------------------------
# AC lookup
# ---------------------------------------------------------------------------


def _find_ac_by_id(ac_root: Path, ac_id: str) -> tuple[Path, AcRecord] | None:
    """Search *ac_root* recursively for a YAML file with id: *ac_id*.

    Args:
        ac_root: Root directory of the AC store.
        ac_id: The AC id to search for.

    Returns:
        ``(path, record)`` when found; ``None`` when not found or parse error.
    """
    for yaml_path in sorted(ac_root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError) as exc:
            print(f"WARNING: {yaml_path}: could not read: {exc}", file=sys.stderr)
            continue
        else:
            if isinstance(data, dict) and data.get("id") == ac_id:
                return yaml_path, data
    return None


# ---------------------------------------------------------------------------
# Idempotency guard
# ---------------------------------------------------------------------------


def _find_existing_ticket(tickets_root: Path, ac_id: str) -> Path | None:
    """Search *tickets_root* for a ticket with source_ac: *ac_id* in frontmatter.

    Args:
        tickets_root: Root directory to search for existing tickets.
        ac_id: The AC id to search for.

    Returns:
        Path to the existing ticket, or None when not found.
    """
    for md_path in tickets_root.rglob("*.md"):
        try:
            content = md_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not content.startswith("---"):
            continue
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            continue
        else:
            if isinstance(fm, dict) and fm.get("source_ac") == ac_id:
                return md_path
    return None


# ---------------------------------------------------------------------------
# Parent AC resolution
# ---------------------------------------------------------------------------


def _load_derive_parent_id_fn(*, warn_context: str = "parent genre resolution"):
    """Load ``ac_parent_id.derive_parent_id`` from the sibling module, or None.

    Shared loader used by both :func:`_load_parent_ac` (parent-genre
    resolution) and :func:`_build_ticket_depends_on` (TKT-600a-1: dropping a
    structural-parent AC id from a generated ticket's ``depends_on``) so the
    ``importlib.util`` sibling-load boilerplate exists in exactly one place.

    Args:
        warn_context: Short phrase naming the caller's use case, interpolated
            into the WARNING messages so log output stays traceable to the
            feature that needed the function.

    Returns:
        The ``derive_parent_id`` callable, or ``None`` when the sibling
        module cannot be loaded or does not define it.

    DECISION HISTORY:
        BO-2200c-3 (2026-08-11): Introduced (as inline logic in
        ``_load_parent_ac``) to support parent-genre resolution. Uses
        importlib.util (same pattern as _load_migration_map) for robust
        sibling-module import regardless of sys.path state.
        TKT-600a-1 (2026-08-18): Extracted into this shared helper so
        ``_build_ticket_depends_on`` can reuse the same loader instead of
        duplicating the importlib boilerplate.
    """
    sibling = Path(__file__).resolve().parent / "ac_parent_id.py"
    try:
        spec = importlib.util.spec_from_file_location("ac_parent_id", sibling)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        derive_fn = getattr(mod, "derive_parent_id", None)
    except (OSError, AttributeError, ImportError, SyntaxError) as exc:
        logger.warning(
            "Cannot load ac_parent_id module for %s: %s", warn_context, exc
        )
        return None

    if derive_fn is None:
        logger.warning(
            "ac_parent_id module has no derive_parent_id function; "
            "%s unavailable",
            warn_context,
        )
        return None
    return derive_fn


def _load_parent_ac(ac_id: str, ac_root: Path) -> "AcRecord | None":
    """Load the parent L1 AC record for *ac_id* from the AC store.

    Derives the parent ID using ``ac_parent_id.derive_parent_id``, then
    searches *ac_root* for the parent YAML file via :func:`_find_ac_by_id`.
    Returns ``None`` and logs a WARNING when:

    - The ``ac_parent_id`` module cannot be loaded from the sibling directory.
    - The parent ID cannot be derived (root AC or malformed ID).
    - No YAML with the derived parent ID is found under *ac_root*.

    File I/O for YAML reads is handled inside :func:`_find_ac_by_id`; the
    only new I/O here is the ``importlib.util`` load of the sibling module
    (wrapped in a specific except clause per Error Handling Policy Rule 1),
    delegated to :func:`_load_derive_parent_id_fn`.

    Args:
        ac_id: Leaf AC identifier (e.g. ``"BO-2200c-3"``).
        ac_root: Root directory of the AC store.

    Returns:
        Parsed parent AC record dict, or ``None`` on any failure.

    DECISION HISTORY:
        BO-2200c-3 (2026-08-11): Introduced to support parent-genre resolution.
        Uses importlib.util (same pattern as _load_migration_map) for robust
        sibling-module import regardless of sys.path state.
        TKT-600a-1 (2026-08-18): Delegated the sibling-module load to the
        shared :func:`_load_derive_parent_id_fn` helper.
    """
    derive_fn = _load_derive_parent_id_fn(warn_context="parent genre resolution")
    if derive_fn is None:
        return None

    parent_id: "str | None" = derive_fn(ac_id)
    if not parent_id:
        logger.warning(
            "Cannot derive parent ID from %r (root AC or malformed ID); "
            "parent genre resolution unavailable",
            ac_id,
        )
        return None

    result = _find_ac_by_id(ac_root, parent_id)
    if result is None:
        logger.warning(
            "Parent AC %r not found in %s; parent genre resolution unavailable",
            parent_id,
            ac_root,
        )
        return None

    _, parent_ac = result
    return parent_ac


def _expects_from_ac_ids(value: object) -> list[str]:
    """Extract the upstream AC ids named in an ``expects_from`` field.

    KI-ACD-20260921 (Defect 1): ``expects_from`` names the AC that produces a
    contract this record consumes, which is a genuine ticket-level ordering
    dependency in exactly the same sense as an authored ``depends_on`` entry
    — the confirmed defect is that :func:`_build_ticket_depends_on` read only
    ``depends_on`` and never consulted this field at all, so a record whose
    authoring convention left ``depends_on`` empty (observed to correlate
    with, but NOT caused by, a null ``delivers_to`` on the *consuming*
    record) silently lost the edge even though a genuine sibling dependency
    was named right there in ``expects_from``.

    ``expects_from`` may be authored as a single mapping or as a list of
    mappings (mirrors ``_gtfa_contracts._as_contract_entries``'s normalisation
    rule; duplicated here in miniature rather than imported, to avoid the
    circular import ``_gtfa_contracts -> _gtfa_doc_genre -> _gtfa_store``).

    Args:
        value: The raw ``expects_from`` field from an AC record.

    Returns:
        List of upstream AC id strings named by the field (may be empty).
    """
    if isinstance(value, dict):
        entries: list = [value]
    elif isinstance(value, list):
        entries = [entry for entry in value if isinstance(entry, dict)]
    else:
        entries = []
    return [
        entry["ac_id"]
        for entry in entries
        if isinstance(entry.get("ac_id"), str) and entry.get("ac_id")
    ]


def _build_ticket_depends_on(
    ac: AcRecord,
    ac_id: str,
    tickets_root: "Path | None",
) -> list[str]:
    """Translate the source AC's dependency edges into a guard-valid ticket list.

    TKT-600a-1: a generated ticket is standalone (one ticket per AC), but the
    source AC's own ``depends_on`` lists AC identifiers — typically its
    structural parent, sometimes a genuine sibling dependency.
    ``templates/hooks/ticket_frontmatter_guard.py``'s ``_check_depends_on``
    requires every ticket ``depends_on`` entry to resolve to a sibling ticket
    file in the same tickets folder, so an AC id can never be copied verbatim.

    KI-ACD-20260921 (Defect 1): the candidate id set is the UNION of
    ``depends_on`` and any ``ac_id`` named in ``expects_from`` (via
    :func:`_expects_from_ac_ids`) — an ``expects_from`` entry names a real
    producer dependency regardless of whether the consuming record's own
    ``delivers_to`` is null, so it must be classified on equal footing with
    an authored ``depends_on`` entry, not silently dropped for want of a
    mirrored ``depends_on`` value. Both sources are merged, order-preserved
    and de-duplicated, before classification.

    Each candidate id is then classified:

    * The AC's own structural parent (via ``ac_parent_id.derive_parent_id``)
      is always dropped — it is not a ticket-level dependency (KI-ACD-021 is
      the separate, already-tracked defect about this case).
    * An AC id with an already-generated, co-located ticket in *tickets_root*
      (found via :func:`_find_existing_ticket` matching ``source_ac``) is
      translated to that ticket's filename, preserving the dependency.
    * Any other AC id (dangling — no ticket exists for it in scope) is
      dropped, with a WARNING naming the dropped id so the omission is
      traceable rather than silently lossy.

    Args:
        ac: Parsed AC record dict.
        ac_id: The AC id the ticket is being generated for.
        tickets_root: Root directory to search for co-located sibling
            tickets, or ``None`` when unavailable (e.g. a caller that has not
            resolved a tickets root) — in that case every entry is dangling
            and the result is always ``[]``.

    Returns:
        List of ticket filenames (each a guard-valid ``depends_on`` entry).
        Empty when the AC declares no dependencies (from either source), none
        survive classification, or *tickets_root* is ``None``.
    """
    raw_deps = ac.get("depends_on")
    if not isinstance(raw_deps, list):
        raw_deps = []
    expects_ids = _expects_from_ac_ids(ac.get("expects_from"))

    candidates: list[str] = []
    seen: set[str] = set()
    for dep in [*raw_deps, *expects_ids]:
        if isinstance(dep, str) and dep and dep not in seen:
            seen.add(dep)
            candidates.append(dep)

    if not candidates or tickets_root is None:
        return []

    own_parent_id = None
    derive_fn = _load_derive_parent_id_fn(warn_context="depends_on structural-parent drop")
    if derive_fn is not None:
        own_parent_id = derive_fn(ac_id)

    resolved: list[str] = []
    for dep in candidates:
        if dep == own_parent_id:
            # Structural parent — never a ticket-level dependency (dropped
            # silently; this is the expected, common case, not an omission).
            continue
        existing = _find_existing_ticket(tickets_root, dep)
        if existing is not None:
            resolved.append(existing.name)
        else:
            logger.warning(
                "AC '%s': dependency entry %r (from depends_on or expects_from) has "
                "no co-located ticket in %s; dropping it to keep the generated "
                "ticket's depends_on guard-valid.",
                ac_id,
                dep,
                tickets_root,
            )
    return resolved
