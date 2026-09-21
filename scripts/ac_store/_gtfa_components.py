#!/usr/bin/env python3
"""
MODULE: _gtfa_components
GOAL: Resolve an AC's component vocabulary into the underscore graph ids that
    belong in a generated ticket's ``components`` LIST, and say so loudly when
    a value cannot be resolved.
BUSINESS CONTEXT: ``docs/components.json`` is the SSOT for component graph ids
    and the knowledge graph's ``component_membership`` edges are built from the
    ticket's ``components`` list, so a kebab namespace key written through
    unresolved produces a ticket that is silently disconnected from its
    component. The resolution is deliberately data-driven — validity is
    membership in components.json, never a hard-coded name list — so adding a
    component is a registry edit.
ARCHITECTURE: An unresolvable value is passed through VERBATIM with a WARNING
    rather than dropped, so the Component-vocab CI check can still see it; a
    silent drop would turn a visible authoring error into an invisible one.

    Two seams matter here and both go through ``_gtfa_seams``:

    * ``_COMPONENT_MIGRATION_MAP`` is assigned in the SHELL's module body (so
      ``importlib.reload`` re-runs it — ``test_tkt_500f_18_i`` depends on that)
      and is therefore read back through the shell, never cached here.
    * ``_find_worktree_root`` is reached through the shell so that
      ``test_tkt_500f_17``'s patch redirects the components.json lookup to its
      test-double root.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
from pathlib import Path

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)

logger = logging.getLogger(_gtfa_seams.logger_name())

AcRecord = _gtfa_constants.AcRecord


# ---------------------------------------------------------------------------
# Component vocabulary: kebab → underscore normalisation
# ---------------------------------------------------------------------------


def _load_migration_map() -> dict[str, str]:
    """Load the canonical kebab-to-underscore MIGRATION_MAP from the side-effect-free data module.

    MODULE: generate_ticket_from_ac
    GOAL: Resolve the sibling data module at
          ``scripts/ac_store/_component_migration_map.py`` and import its
          ``MIGRATION_MAP`` dict so that the generated ticket's ``components``
          LIST carries the underscore graph id rather than the kebab namespace
          scalar.  The data module contains only the dict literal — no
          logging.basicConfig or other side effects (TKT-500f-18).

    Degradation contract (TKT-500f-18-i):
        - Any exec-phase error (SyntaxError, RuntimeError, OSError, etc.) is
          caught; a WARNING is logged naming the failed source; ``{}`` is
          returned so the module-level assignment never raises.
        - When the data module loads but returns an empty MIGRATION_MAP (e.g.
          in tests that patch importlib), the function falls back to an
          auto-derived map built from docs/components.json so that callers
          still receive a non-empty mapping.

    Returns:
        Mapping from kebab component namespace key to underscore graph id.
        Returns ``{}`` only when exec_module raises; otherwise returns a
        non-empty map sourced from the data module or docs/components.json.

    DECISION HISTORY:
        TKT-500f-18 (2026-07-21): Replaced exec-based load of
        migrate_component_vocab.py (which called logging.basicConfig at module
        level) with _component_migration_map.py — a plain data module with no
        side effects.
        TKT-500f-18-i (2026-07-21): Broadened except clause to include
        SyntaxError and RuntimeError; added components.json fallback for the
        empty-map case.
    """
    sibling = Path(__file__).resolve().parent / "_component_migration_map.py"
    try:
        spec = importlib.util.spec_from_file_location("_component_migration_map", sibling)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        migration_map: dict[str, str] = dict(getattr(mod, "MIGRATION_MAP", {}) or {})
    except (OSError, AttributeError, ImportError, SyntaxError, RuntimeError) as exc:
        logger.warning("Cannot load MIGRATION_MAP from %s: %s", sibling, exc)
        return {}

    if migration_map:
        return migration_map

    # Fallback: when the data module loaded but returned an empty map (e.g.
    # test doubles that blank out MIGRATION_MAP), auto-derive a minimal map
    # from docs/components.json so callers still get a non-empty mapping.
    # No WARNING is emitted here — an empty module map is not an error.
    try:
        repo_root = _gtfa_seams.find_worktree_root(Path(__file__))
        components_path = repo_root / "docs" / "components.json"
        with open(components_path, encoding="utf-8") as fh:
            data = json.load(fh)
        valid_ids: set[str] = set(data.get("components", {}).keys())
        # Derive kebab→underscore pairs by converting each underscore id
        # to its hyphenated form.  This is not the canonical MIGRATION_MAP
        # (which handles non-obvious mappings like ticket-creation →
        # ticket_creation_pipeline) but it covers the simple 1:1 cases and
        # ensures a non-empty return when the data module had no entries.
        return {vid.replace("_", "-"): vid for vid in valid_ids}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Cannot build fallback migration map from docs/components.json: %s", exc
        )
        return {}


def _load_valid_component_ids() -> frozenset[str]:
    """Load the set of valid component graph IDs from docs/components.json.

    MODULE: generate_ticket_from_ac
    GOAL: Provide the authoritative set of valid underscore graph IDs so that
          ``_build_components_list`` can validate resolved component values and
          emit targeted WARNINGs for values absent from the registry.
    BUSINESS CONTEXT: docs/components.json is the SSOT for component graph IDs.
          Any resolved component value absent from this set is suspect and
          should be surfaced to the author via a WARNING rather than silently
          inserted into the generated ticket.
    ARCHITECTURE: I/O boundary function — catches read/parse errors and
          returns an empty frozenset (no validation) rather than propagating.
          Calls ``_find_worktree_root`` so that unit tests can patch it to
          supply a controlled test-double components.json.

    Returns:
        frozenset of underscore component id strings from docs/components.json,
        or an empty frozenset when the file cannot be found or read (in which
        case no validity check is performed by callers).

    DECISION HISTORY:
        TKT-500f-17 (2026-07-21): Introduced to support data-driven validity
        checking in ``_build_components_list`` — validity is determined by
        membership in docs/components.json, not by the partial MIGRATION_MAP.
    """
    try:
        repo_root = _gtfa_seams.find_worktree_root(Path(__file__))
        components_path = repo_root / "docs" / "components.json"
        with open(components_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return frozenset(data.get("components", {}).keys())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Cannot load valid component IDs from docs/components.json: %s", exc
        )
        return frozenset()


def _build_components_list(ac: AcRecord, ac_id: str = "") -> list[str]:
    """Build the ``components`` LIST for a generated ticket frontmatter.

    Prefers the AC's own ``components`` field when non-empty.  When the field
    holds a SCALAR string (not a YAML list), it is treated as a single
    component id and wrapped in a one-element list — applying the
    ``_COMPONENT_MIGRATION_MAP`` kebab→underscore lookup so that kebab
    namespace keys (e.g. ``ticket-creation``) are resolved to their
    components.json graph ids (e.g. ``ticket_creation_pipeline``).

    When the field holds a YAML LIST, each element is normalised through
    ``_COMPONENT_MIGRATION_MAP`` and then validated against the set of valid
    ids loaded from docs/components.json (TKT-500f-16 / TKT-500f-17).
    Elements whose resolved value is absent from docs/components.json receive
    a WARNING that names both the source AC id and the offending value.
    Warnings are emitted at most once per distinct unresolved value (AC-3
    deduplication).  The unresolved value is passed through VERBATIM so the
    Component-vocab CI check can surface it; it is never silently dropped.
    Duplicate resolved values are deduped in the output (order-preserving).

    When the field is absent or falsy, the scalar ``component`` key is
    normalised via ``_COMPONENT_MIGRATION_MAP``, falling back to the raw
    value when the key is absent from the map.

    The scalar ``component`` field in the ticket frontmatter is left unchanged
    — only the LIST is normalised to the components.json graph vocabulary.

    Args:
        ac: Parsed AC record dict.
        ac_id: The AC identifier; used in WARNING messages so the author can
               trace an unresolvable component value back to its source AC.

    Returns:
        List of underscore graph ids for the generated ticket ``components`` LIST.

    DECISION HISTORY:
        TKT-500f-15 (2026-07-21): Added ``isinstance(existing, str)`` branch to
        prevent ``list(str)`` per-character shatter when the YAML ``components``
        field is a scalar string.  A scalar string is now treated as a single
        value and resolved through ``_COMPONENT_MIGRATION_MAP`` before wrapping.
        TKT-500f-16 (2026-07-21): LIST elements are now each normalised through
        ``_COMPONENT_MIGRATION_MAP`` instead of passed through with ``list()``.
        Previously kebab elements such as ``build-pipeline`` passed straight
        through without normalisation.
        TKT-500f-17 / TKT-500f-17-i (2026-07-21): Added docs/components.json
        validity check for LIST elements; WARNING emitted once per distinct
        unresolvable value naming both the AC id and the value; unresolved
        values passed through verbatim (not dropped).
    """
    # Read the map off the shell rather than caching it here: the shell's
    # module body assigns it, so importlib.reload(shell) must be visible.
    migration_map = _gtfa_seams.component_migration_map()
    existing = ac.get("components")
    if existing:
        if isinstance(existing, str):
            return [migration_map.get(existing, existing)]
        # LIST case: normalise each element, validate against components.json.
        valid_ids = _load_valid_component_ids()
        result: list[str] = []
        seen_resolved: set[str] = set()   # order-preserving dedup of resolved values
        warned_values: set[str] = set()   # dedup WARNING emissions per distinct value
        for el in existing:
            resolved: str = migration_map.get(el, el)
            if resolved not in seen_resolved:
                seen_resolved.add(resolved)
                result.append(resolved)
            # Validity check: warn once per distinct unresolved value when the
            # resolved id is absent from docs/components.json.  Skip the check
            # when valid_ids is empty (components.json unavailable) to avoid
            # false positives.
            if valid_ids and resolved not in valid_ids and resolved not in warned_values:
                logger.warning(
                    "AC '%s': component value %r cannot be resolved to a valid "
                    "docs/components.json graph id",
                    ac_id,
                    resolved,
                )
                warned_values.add(resolved)
        return result
    kebab = str(ac.get("component") or "unknown")
    return [str(migration_map.get(kebab, kebab))]
