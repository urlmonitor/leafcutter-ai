#!/usr/bin/env python3
"""
MODULE: _gtfa_files_touched
GOAL: Derive a generated ticket's ``files_touched`` list from what the AC
    record actually declares — its ``it_requirements`` edit surface and its
    ``doc_links`` — and resolve any ``reference_pattern`` glob to the one
    concrete path it names.
BUSINESS CONTEXT: ``files_touched`` is the ticket's file-scope signal: it
    drives change-scope review and, per the repo's own phantom-done history, a
    wrong list is a direct phantom-done vector — an illustrative path quoted in
    prose that lands in ``files_touched`` can block a whole epic drive, and a
    real surface dropped from it leaves the coder with no scope at all.
ARCHITECTURE: Three independent filters sit in front of the prose harvest, and
    the ordering between them is deliberate:

    1. Token detection (``_extract_paths_from_prose``) — shape only.
    2. Structured self-declaration (``_paths_declared_non_edit_surface_only``)
       — the record's own ``doc_links`` relationship enum wins over a prose
       repetition of the same path.
    3. On-disk existence (``_is_real_prose_path``) — a directory is never an
       edit surface, so this asks ``is_file()`` and not ``exists()``.

    None of the three reads English prose for authorial intent; each asks a
    mechanical question, which is why a false exclusion (the worse error) stays
    bounded. The worktree root used by filter 3 is reached through
    ``_gtfa_seams`` so a patch on the shell redirects it.
"""

from __future__ import annotations

import glob as _glob
import importlib
import logging
from pathlib import Path
from typing import Any

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)

logger = logging.getLogger(_gtfa_seams.logger_name())

_EDIT_SURFACE_RELATIONSHIPS = _gtfa_constants._EDIT_SURFACE_RELATIONSHIPS
_KNOWN_PATH_PREFIXES = _gtfa_constants._KNOWN_PATH_PREFIXES
_PROSE_PATH_EXTENSIONS = _gtfa_constants._PROSE_PATH_EXTENSIONS
_PROSE_PATH_TOKEN_RE = _gtfa_constants._PROSE_PATH_TOKEN_RE
_SOURCE_CODE_EXTENSIONS = _gtfa_constants._SOURCE_CODE_EXTENSIONS


def _extract_local_paths(
    doc_links: list[Any],
    *,
    relationships: frozenset[str] | None = None,
) -> list[str]:
    """Extract local file paths from a doc_links list.

    Accepts BOTH supported ``doc_links`` entry shapes per the AC-store
    schema:

    * A ``{path, relationship, status}`` dict — filtered by *relationships*
      exactly as before (only edit-surface relationships are included when
      *relationships* is provided).
    * A plain path string — this shape carries no ``relationship`` field, so
      the relationship filter cannot apply to it. Instead, a plain-string
      entry is included only when it is an implementation-relevant local
      source path (extension in ``_SOURCE_CODE_EXTENSIONS``). This keeps the
      derivation union-preserving over real implementation sources (never a
      first-wins or single-element reduction that silently drops a
      referenced path — ACD-400b-6) while still excluding purely
      informational doc pages (``docs/**.md``, ``docs/**.yaml`` reference
      pages, architecture docs) from ``files_touched``.

    Filters out entries whose path starts with 'http' (URLs) in both shapes.
    Any entry that is neither a string nor a dict is malformed; it is
    skipped with a WARNING rather than raising (repo error-handling policy).

    Args:
        doc_links: List of doc_link dicts or plain path strings (or
                   None/empty).
        relationships: Optional frozenset of relationship strings to include
                       for dict-shaped entries. When ``None`` (default) no
                       relationship filtering is applied to dict entries.

    Returns:
        List of local path strings (may be empty).
    """
    if not doc_links:
        return []
    local: list[str] = []
    for link in doc_links:
        if isinstance(link, dict):
            if relationships is not None:
                rel = link.get("relationship", "")
                if rel not in relationships:
                    continue
            path_val = link.get("path", "")
            if isinstance(path_val, str) and path_val and not path_val.startswith("http"):
                local.append(path_val)
        elif isinstance(link, str):
            if link and not link.startswith("http") and Path(link).suffix.lower() in (
                _SOURCE_CODE_EXTENSIONS
            ):
                local.append(link)
        else:
            logger.warning(
                "Skipping malformed doc_links entry (expected str or dict): %r", link
            )
    return local


def _extract_paths_from_prose(text: str) -> list[str]:
    """Extract file path tokens from a prose bullet string.

    A token is included only when it contains at least one ``/`` separator
    AND satisfies one of two conditions:

    * Its final path component ends in a recognized extension from
      ``_PROSE_PATH_EXTENSIONS`` (e.g. ``scripts/foo.py``, ``docs/bar.md``).
    * The token begins with a known path prefix from ``_KNOWN_PATH_PREFIXES``
      (e.g. ``scripts/``, ``docs/``) even when it carries no extension.

    Bare words such as ``"pipeline"`` or prose phrases such as
    ``"system architecture"`` never satisfy either condition because they
    contain no ``/`` character, so they are never extracted.

    Args:
        text: A prose bullet string (one item from a list-form it_requirements).

    Returns:
        List of file path strings found in *text* (may be empty).
    """
    found: list[str] = []
    for match in _PROSE_PATH_TOKEN_RE.finditer(text):
        token = match.group(0)
        # Check for a recognized extension on the final path component.
        dot_pos = token.rfind(".")
        slash_pos = token.rfind("/")
        if dot_pos > slash_pos:
            # The dot is after the last slash — it belongs to the filename component.
            ext = token[dot_pos:].lower()
            if ext in _PROSE_PATH_EXTENSIONS:
                found.append(token)
                continue
        # No recognized extension: fall back to known-prefix check.
        if any(token.startswith(prefix) for prefix in _KNOWN_PATH_PREFIXES):
            found.append(token)
    return found


def _resolve_worktree_root_or_none() -> "Path | None":
    """Resolve the worktree root from this module's own location, or None.

    Wraps :func:`_find_worktree_root` so callers that must degrade gracefully
    (rather than raise) when no ``.git`` marker is found — e.g. the prose
    path-existence gate below, which is a best-effort filter, not a hard
    requirement — can treat "root not found" as "skip the filter".

    Returns:
        The worktree root path, or ``None`` when no ``.git`` marker is found.
    """
    try:
        return _gtfa_seams.find_worktree_root(Path(__file__))
    except FileNotFoundError:
        return None


def _is_real_prose_path(token: str, worktree_root: "Path | None") -> bool:
    """Return True when *token* names a real **file** that exists on disk.

    TKT-600a-1: a narrative it_requirements bullet may quote example paths
    purely to illustrate a scenario (e.g. ``"src/foo.py"`` in a sentence
    describing an exploit) — such tokens satisfy ``_extract_paths_from_prose``'s
    extension/prefix heuristics but do not name a real edit-surface file, so
    they must not leak into ``files_touched``. Gating on on-disk existence
    (per the AC's own remediation note: "gate on file existence") distinguishes
    illustrative examples from real paths without narrowing the token-detection
    regex, which would risk dropping genuine paths that happen to look unusual.

    ``is_file()``, not ``exists()`` — a **directory is never an edit surface**,
    and this is the distinction the existence gate alone got wrong. A bullet
    naming ``docs/acceptance-criteria`` or ``templates/skills`` to describe
    *where* a rule applies passes ``exists()`` precisely because those
    directories do exist, so three bare directories were written into a
    generated ticket's ``files_touched`` and blocked an epic drive. Requiring a
    file keeps the discrimination mechanical: it asks a property of the
    filesystem, never of the sentence's intent.

    This deliberately leaves one case in ``TKT-600a-1``'s criteria unmet: an
    illustrative path that both has an extension and happens to exist is still
    harvested. Separating that from a genuine surface needs authorial intent
    read out of English prose, which the AC's ``it_requirements`` note records
    as a rejected approach — it fires on no cue in the real failing bullet and
    silently drops real surfaces elsewhere. A false exclusion is the worse
    error of the two, so the mechanical rule stops here.

    When *worktree_root* is ``None`` (root could not be resolved), the gate is
    skipped and the token is treated as real — this preserves prior behaviour
    in contexts where the worktree cannot be located, rather than silently
    dropping every prose-extracted path.

    Args:
        token: Candidate path token extracted from prose.
        worktree_root: Resolved worktree root, or ``None``.

    Returns:
        True when the token names an existing file (or the root could not be
        resolved), False when the root resolved and the token names a
        directory or nothing at all.
    """
    if worktree_root is None:
        return True
    return (worktree_root / token).is_file()


def _paths_declared_non_edit_surface_only(doc_links: list[Any]) -> frozenset[str]:
    """Return paths the record declares ONLY at non-edit-surface relationships.

    TKT-600a-2: a record's ``doc_links`` is a structured, authored declaration
    of what each linked path IS to this work. When a path is declared at a
    relationship outside ``_EDIT_SURFACE_RELATIONSHIPS`` (e.g. ``related``,
    ``describes``) and is declared NOWHERE ELSE in the same record at an
    edit-surface relationship, the record has already stated that this path is
    context, not a surface — a prose bullet that happens to also name the same
    path must not override that self-declaration (Source 1 in
    :func:`_build_files_touched`).

    Only dict-shaped ``doc_links`` entries carry a ``relationship`` field, so
    plain-string entries are not considered here — there is nothing for them
    to declare. A path declared at an edit-surface relationship ANYWHERE in
    the record is never suppressed, even if the same path also carries a
    non-edit-surface declaration elsewhere (scenario 5 — the edit-surface
    declaration wins).

    Args:
        doc_links: The AC record's ``doc_links`` list (or None/empty).

    Returns:
        Frozenset of path strings declared at a non-edit-surface relationship
        and never declared at an edit-surface relationship.
    """
    if not doc_links:
        return frozenset()
    relationships_by_path: dict[str, set[str]] = {}
    for link in doc_links:
        if not isinstance(link, dict):
            continue
        path_val = link.get("path", "")
        rel = link.get("relationship", "")
        if isinstance(path_val, str) and path_val:
            relationships_by_path.setdefault(path_val, set()).add(rel)
    return frozenset(
        path
        for path, rels in relationships_by_path.items()
        if not (rels & _EDIT_SURFACE_RELATIONSHIPS)
    )


def _prose_edit_surface(it_req: list, suppressed: frozenset[str]) -> set[str]:
    """Harvest edit-surface paths from list-form (prose) ``it_requirements``.

    Each bullet is scanned for file path tokens, then each candidate token is
    gated on NOT being a path the record's own doc_links already declared
    non-edit-surface (TKT-600a-2) and on on-disk existence (TKT-600a-1), so
    illustrative example paths and self-contradicted paths never leak into
    ``files_touched``.

    Args:
        it_req: The list-form ``it_requirements`` value (prose bullets).
        suppressed: Paths the record declared only at non-edit-surface
            relationships.

    Returns:
        Set of surviving path strings.
    """
    worktree_root = _resolve_worktree_root_or_none()
    paths: set[str] = set()
    for bullet in it_req:
        if isinstance(bullet, str):
            for path_token in _extract_paths_from_prose(bullet):
                if path_token in suppressed:
                    continue
                if _is_real_prose_path(path_token, worktree_root):
                    paths.add(path_token)
    return paths


def _build_files_touched(ac: dict[str, Any]) -> list[str]:
    """Build the sorted, de-duplicated ``files_touched`` list for a generated ticket.

    The list is the union of:

    1. The ``reference_file_path`` named in ``it_requirements`` (structured form),
       or file path tokens extracted from prose bullets when ``it_requirements``
       is a list of strings (list form — TKT-500f-8-i), FILTERED to tokens that
       name a file actually present on disk (TKT-600a-1) — illustrative example
       paths quoted only to describe a scenario (e.g. ``src/foo.py`` in prose
       that never touches a real ``src/`` tree) do not exist on disk and are
       excluded, while a real edit-surface path named in a bullet (e.g.
       ``scripts/goal_to_epic.py``) survives — AND further filtered to exclude
       any token the record's own ``doc_links`` has already declared as
       non-edit-surface and nowhere as an edit surface (TKT-600a-2): the
       record's structured self-declaration wins over a prose repetition.
    2. Paths from ``doc_links`` whose ``relationship`` is one of the edit-surface
       relationships defined in ``_EDIT_SURFACE_RELATIONSHIPS`` (``constrains``,
       ``creates``, ``implements``, ``modifies``, ``specifies``).

    Doc_links with ``relationship`` set to ``describes`` or ``related`` are
    informational only and are excluded from ``files_touched``.  Paths that
    appear in both sources are deduplicated so each path is listed exactly once.
    The returned list is sorted deterministically so that regenerating the same
    AC always yields byte-identical output.

    Args:
        ac: Parsed AC record dict.

    Returns:
        Sorted list of unique local path strings (may be empty).
    """
    paths: set[str] = set()
    doc_links = ac.get("doc_links") or []
    suppressed = _paths_declared_non_edit_surface_only(doc_links)

    # Source 1 — it_requirements edit surface.
    # Structured form: a dict with an explicit reference_file_path key. This
    # form is trusted verbatim — it is an authored, structured field, not a
    # prose token, so neither the existence gate nor the suppression rule
    # applies to it.
    # List form (TKT-500f-8-i): see _prose_edit_surface.
    it_req = ac.get("it_requirements")
    if isinstance(it_req, dict):
        ref_path = it_req.get("reference_file_path", "")
        if isinstance(ref_path, str) and ref_path:
            paths.add(ref_path)
    elif isinstance(it_req, list):
        paths |= _prose_edit_surface(it_req, suppressed)

    # Source 2 — doc_links edit-surface entries
    for path_val in _extract_local_paths(
        doc_links, relationships=_EDIT_SURFACE_RELATIONSHIPS
    ):
        paths.add(path_val)

    return sorted(paths)


def _resolve_reference_patterns(it_req: dict, ac_id: str) -> dict:
    """Resolve ``reference_pattern`` globs in an it_requirements dict to concrete paths.

    When the ``reference_pattern`` key is present, the glob is expanded against
    the filesystem.  Exactly one match is required — zero matches raises
    ``ValueError`` (authoring error: the pattern resolves to nothing, or the
    target file is missing).

    The function returns a shallow copy of *it_req* with ``reference_pattern``
    replaced by the single resolved concrete path string.  When the key is
    absent the original dict is returned unchanged.

    Args:
        it_req: The ``it_requirements`` dict from the AC record.
        ac_id: AC identifier, included in error messages so the author can
               trace the broken pattern back to its source AC.

    Returns:
        Shallow copy of *it_req* with ``reference_pattern`` replaced by the
        resolved concrete path, or *it_req* unchanged when the key is absent.

    Raises:
        ValueError: When ``reference_pattern`` resolves to zero files.
    """
    if "reference_pattern" not in it_req:
        return it_req

    pattern = str(it_req["reference_pattern"])
    try:
        matches = _glob.glob(pattern)
    except OSError as exc:
        raise ValueError(  # noqa: TRY003
            f"AC '{ac_id}': error expanding reference_pattern {pattern!r}: {exc}"
        ) from exc

    if not matches:
        raise ValueError(  # noqa: TRY003
            f"AC '{ac_id}': reference_pattern {pattern!r} resolves to no files. "
            "Ensure the referenced file exists or correct the pattern in the AC."
        )

    resolved_req = dict(it_req)
    resolved_req["reference_pattern"] = matches[0]
    return resolved_req
