"""
MODULE: knowledge_file_nodes
GOAL: Resolve a relationship field's raw string values that name a file
      (implemented_by, covered_by, files_touched, and any other field a
      surface declares in its own ``file_path_fields``) onto real,
      path-keyed graph nodes instead of raw-string leaves that only survive
      because the old exemption let them through.
BUSINESS CONTEXT: KM-KGS-100d-4 (and its children -i missing-node ambiguity,
    -ii present/missing marking, -iii decline reporting, -iv surface
    restriction). A file-path value is canonicalised (anchor stripped,
    separators normalised, absolute-inside-root made repo-relative), looked
    up in an index of every node's own source path (INDEX-FIRST), and lands
    on that node only when the hit is unambiguous (KM-KGS-100d-4-i).
    Otherwise it lands on a ``files``-surface node keyed by the canonical
    path, created once per distinct path and marked present or missing by a
    single existence check under the project root (KM-KGS-100d-4-ii). A
    value that is not path-shaped keeps ordinary id resolution (a child AC
    id such as KM-EX-011-i); if that id is on no node, the value is declined
    with a reason, never silently dropped (KM-KGS-100d-4-iii). No field name
    and no surface name is special-cased anywhere in this module (KM-KGS-
    100c-2): every candidate arrives already tagged with the surface's own
    field name, and the same four functions run for every one of them.
ARCHITECTURE: Sibling module to knowledge_query.py, loaded the same way that
    file loads knowledge_frontmatter_reader.py — via
    ``importlib.util.spec_from_file_location`` resolved relative to
    knowledge_query.py's own ``__file__`` — so the same resolution works
    both from source (``scripts/``) and from a deployed consumer's
    ``.leafcutter/scripts/`` with no ``scripts/`` directory on ``sys.path``.
    This module never imports knowledge_query (that would be circular); the
    ``NodeRecord``/``EdgeRecord`` classes are passed in by the caller so this
    module has zero dependency on its caller's module identity. Stdlib-only
    (KM-KQS-007).
KNOWN LIMITATION (pr-reviewer M-2, 2026-09-25): ``_strip_anchor`` splits at
    the first ``#`` or ``::`` unconditionally, so a filename that genuinely
    CONTAINS one of those characters (not as an anchor delimiter) would be
    split as if it were an anchor. There are no such filenames in this repo
    today (``git ls-files | grep '#'`` is empty), and fixing it would change
    the anchor rule itself (KM-KGS-100d-4's canonicalisation order), which is
    out of scope for this defect fix.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

#: The two decline reasons this module ever reports (KM-KGS-100d-4-iii).
#: A real-repository test asserts every stderr decline line's reason is one
#: of exactly these two strings, so a third reason must never be introduced.
NOT_A_PATH_REASON = "not a file path in this project"
FOREIGN_ABSOLUTE_REASON = "absolute path outside this project"

_DRIVE_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:/")
_DRIVE_PREFIX_RE = re.compile(r"^([A-Za-z]):(/.*)?$")


class DeclineRecord(NamedTuple):
    """One relationship value that could not resolve to a node or a file.

    Attributes:
        surface: The surface the value's field belongs to (e.g. ``"acs"``).
        doc: Repo-relative POSIX path of the file the value was read from.
        field: The field name the value was read from (equals the produced
            edge_type for every file-path field; these fields are never
            remapped the way ``components`` is).
        value: The value exactly as read, before any canonicalisation --
            printed verbatim so an operator can find it in the source file.
        reason: One of ``NOT_A_PATH_REASON`` or ``FOREIGN_ABSOLUTE_REASON``.
    """

    surface: str
    doc: str
    field: str
    value: str
    reason: str


def format_decline_line(decline: DeclineRecord) -> str:
    """Render one decline as the pipe-delimited stderr line.

    Args:
        decline: The decline to render.

    Returns:
        A single line: ``DECLINED | surface=... | doc=... | field=... |
        value=... | reason=...``. Pipe-delimited so a value containing
        spaces or punctuation (e.g. a free-text PR title) never breaks
        parsing.
    """
    return (
        f"DECLINED | surface={decline.surface} | doc={decline.doc} | "
        f"field={decline.field} | value={decline.value} | reason={decline.reason}"
    )


def _strip_anchor(value: str) -> tuple[str, str | None]:
    """Strip one trailing ``#symbol`` or ``::test`` anchor, keeping it aside.

    Splits at the FIRST occurrence of ``#`` or ``::`` (whichever comes
    first), not the last: a covered_by value may be a full pytest node id
    with both a class and a method (``path.py::Class::test_method``), and
    the anchor kept aside is everything after the path -- itself allowed to
    contain a further ``::`` -- so the path portion that becomes the node id
    never retains a stray ``::`` or ``#``.

    Args:
        value: The raw relationship value, anchor still attached.

    Returns:
        ``(value_without_anchor, anchor_or_None)``.
    """
    idx_hash = value.find("#")
    idx_double_colon = value.find("::")
    if idx_double_colon != -1 and (idx_hash == -1 or idx_double_colon < idx_hash):
        return value[:idx_double_colon], value[idx_double_colon + 2 :]
    if idx_hash != -1:
        return value[:idx_hash], value[idx_hash + 1 :]
    return value, None


def _normalize_separators(value: str) -> str:
    """Backslashes become ``/``; drop a leading ``./`` and a trailing ``/``.

    Never case-folds: git paths are case-sensitive.

    Args:
        value: The anchor-stripped value.

    Returns:
        The value with separators normalised.
    """
    posix_value = value.replace("\\", "/")
    if posix_value.startswith("./"):
        posix_value = posix_value[2:]
    if len(posix_value) > 1 and posix_value.endswith("/"):
        posix_value = posix_value.rstrip("/")
    return posix_value


def _is_absolute_string(value: str) -> bool:
    """Return whether ``value`` looks like an absolute path on any OS.

    Deliberately string-based rather than ``Path.is_absolute()``: a POSIX
    absolute value such as ``/home/x`` is NOT absolute under ``pathlib`` on
    Windows (it lacks a drive), which would silently defeat the foreign
    -absolute-path detection when the test host and the fixture's imagined
    OS differ.

    Args:
        value: A separator-normalised (forward-slash) value.

    Returns:
        True if ``value`` starts with ``/`` or a drive letter (``C:/``).
    """
    return value.startswith("/") or bool(_DRIVE_ABSOLUTE_RE.match(value))


def _split_drive(value: str) -> tuple[str | None, str]:
    """Split a Windows drive-letter prefix (``C:``) from the rest of ``value``.

    Args:
        value: A separator-normalised value.

    Returns:
        ``(drive_letter, rest)`` when ``value`` starts with a drive letter
        (``rest`` keeps its own leading ``/``, e.g. ``("C", "/Users/x")``);
        ``(None, value)`` unchanged otherwise (a POSIX-style value, or a
        plain relative value).
    """
    match = _DRIVE_PREFIX_RE.match(value)
    if match:
        return match.group(1), match.group(2) or ""
    return None, value


def _split_absolute(value: str, project_root_posix: str) -> tuple[str, bool]:
    """Make an absolute-inside-root value repo-relative; flag a foreign one.

    A Windows drive letter is compared case-INSENSITIVELY (``c:`` and ``C:``
    name the same drive), because a value's own spelling need not match how
    ``project_root`` happened to resolve. Everything after the drive letter
    -- and every POSIX-style value with no drive at all -- is still compared
    exactly, never case-folded: a differently-cased TAIL (e.g.
    ``Scripts/Foo.py`` vs ``scripts/foo.py``) must stay a distinct value.

    Args:
        value: A separator-normalised value.
        project_root_posix: ``project_root`` as a forward-slash string, no
            trailing slash.

    Returns:
        ``(canonical_value, is_foreign)``. ``is_foreign`` is True only for an
        absolute value outside ``project_root`` -- never recovered by
        suffix-matching against a repo path.
    """
    if not _is_absolute_string(value):
        return value, False
    value_drive, value_rest = _split_drive(value)
    root_drive, root_rest = _split_drive(project_root_posix)
    if value_drive is None or root_drive is None or value_drive.lower() != root_drive.lower():
        # No drive letter on one or both sides, or the drives differ
        # outright: fall back to an exact, whole-string comparison.
        if value == project_root_posix:
            return "", False
        prefix = project_root_posix + "/"
        if value.startswith(prefix):
            return value[len(prefix) :], False
        return value, True
    # Same drive letter (case-insensitively) -- compare the rest exactly.
    if value_rest == root_rest:
        return "", False
    prefix = root_rest + "/"
    if value_rest.startswith(prefix):
        return value_rest[len(prefix) :], False
    return value, True


def _collapse_relative_segments(value: str) -> str | None:
    """Lexically collapse ``.``/``..`` segments; None when it escapes the root.

    Pure string/list segment arithmetic -- never touches the filesystem (no
    ``resolve()``), so it can never follow a symlink and can only "escape"
    via a ``..`` segment literally present in ``value``. ``value`` is always
    relative here (an absolute value already had any in-root prefix removed,
    or was declined as foreign, before this runs).

    Args:
        value: A relative, separator-normalised value.

    Returns:
        The collapsed relative path (``""`` when it collapses to the project
        root itself -- staying AT the root is not an escape), or None when a
        ``..`` segment would climb above the project root.
    """
    segments: list[str] = []
    for part in value.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not segments:
                return None
            segments.pop()
        else:
            segments.append(part)
    return "/".join(segments)


def _is_path_shaped(value: str, project_root: Path) -> bool:
    """Decide path-shapedness after canonicalisation (KM-KGS-100d-4-iii).

    A value is path-shaped if it exists under the project root, OR it has
    no whitespace and either contains ``/`` or ends in a file extension.
    The existence arm is what keeps a root-level extensionless file (e.g.
    ``Makefile``, ``.gitignore``) resolvable. ``value`` is always already
    ``..``-collapsed (see ``_collapse_relative_segments``), so this
    existence check can never traverse outside the project root.

    Args:
        value: The canonicalised (repo-relative, or unresolved) value.
        project_root: Absolute path to the project root.

    Returns:
        True when the value should be resolved as a file path.
    """
    if (project_root / value).exists():
        return True
    if any(ch.isspace() for ch in value):
        return False
    if "/" in value:
        return True
    return bool(Path(value).suffix)


def _canonical_node_source(path: Path, project_root_posix: str) -> str:
    """Reduce a node's own source ``path`` to a repo-relative POSIX string.

    Args:
        path: The node's source file path (absolute or relative).
        project_root_posix: ``project_root`` as a forward-slash string, no
            trailing slash.

    Returns:
        The repo-relative POSIX path when ``path`` is under the project
        root; ``path``'s own POSIX form otherwise.
    """
    posix_path = Path(path).as_posix()
    if posix_path == project_root_posix:
        return ""
    prefix = project_root_posix + "/"
    if posix_path.startswith(prefix):
        return posix_path[len(prefix) :]
    return posix_path


def _build_path_index(nodes, project_root_posix: str) -> dict:
    """Index nodes by their own canonical source path (INDEX-FIRST).

    Built only over nodes actually read from a file -- never over synthetic
    nodes (component hubs, files nodes), which is why the caller passes only
    ``primary_nodes`` here.

    Args:
        nodes: Primary (non-synthetic) NodeRecords.
        project_root_posix: See ``_canonical_node_source``.

    Returns:
        Dict mapping canonical source path to the list of nodes read from
        it (more than one entry means that path is ambiguous by source).
    """
    index: dict[str, list] = {}
    for node in nodes:
        key = _canonical_node_source(node.path, project_root_posix)
        index.setdefault(key, []).append(node)
    return index


def _id_counts(nodes) -> dict[str, int]:
    """Count how many nodes carry each id, map-wide (for ambiguity by id)."""
    counts: dict[str, int] = {}
    for node in nodes:
        counts[node.id] = counts.get(node.id, 0) + 1
    return counts


def _make_files_node(canon: str, project_root: Path, node_record_cls):
    """Build a new ``files``-surface node for a canonical path.

    Existence is tested once, here, per distinct canonical path -- never
    once per edge, and never against the process cwd.

    Args:
        canon: The canonical repo-relative path.
        project_root: Absolute path to the project root.
        node_record_cls: The caller's ``NodeRecord`` class.

    Returns:
        A new NodeRecord on the ``files`` surface, marked present or missing.
    """
    exists = (project_root / canon).exists()
    name = Path(canon).name or canon
    return node_record_cls(
        id=canon,
        surface="files",
        title=name,
        description="",
        path=project_root / canon,
        missing=not exists,
    )


def _get_or_create_files_node(canon, project_root, files_registry, other_ids, node_record_cls):
    """Reuse or create the one files node for ``canon``; guard id safety.

    ID SAFETY (KM-KGS-100d-4): if a non-file node already carries exactly
    this id, no second node with that id is created; the caller declines
    the edge instead through the same channel as any other decline.

    Args:
        canon: The canonical repo-relative path.
        project_root: Absolute path to the project root.
        files_registry: Mutable dict of canon path -> already-created files
            node, shared across the whole resolution pass so a path becomes
            a node exactly once.
        other_ids: Frozen set of every primary/hub node id (never a files id).
        node_record_cls: The caller's ``NodeRecord`` class.

    Returns:
        The (possibly newly created) files NodeRecord, or None on an id
        collision.
    """
    existing = files_registry.get(canon)
    if existing is not None:
        return existing
    if canon in other_ids:
        return None
    node = _make_files_node(canon, project_root, node_record_cls)
    files_registry[canon] = node
    return node


def _resolve_single(raw_value, project_root, project_root_posix, path_index, id_counts, other_ids, files_registry, node_record_cls):
    """Resolve one raw relationship value to a target id, or a decline reason.

    Args:
        raw_value: The value exactly as read from the surface's record.
        project_root: Absolute path to the project root.
        project_root_posix: ``project_root`` as a forward-slash string.
        path_index: See ``_build_path_index``.
        id_counts: See ``_id_counts`` (over primary + hub nodes).
        other_ids: Frozen set of every primary/hub node id.
        files_registry: Mutable dict of canon path -> files node (grown here).
        node_record_cls: The caller's ``NodeRecord`` class.

    Returns:
        ``(target_id, anchor, decline_reason)``. Exactly one of
        ``target_id`` / ``decline_reason`` is non-None.
    """
    stripped, anchor = _strip_anchor(raw_value)
    normalized = _normalize_separators(stripped)
    root_relative, is_foreign = _split_absolute(normalized, project_root_posix)
    if is_foreign:
        return None, anchor, FOREIGN_ABSOLUTE_REASON

    canon = _collapse_relative_segments(root_relative)
    if canon is None:
        # A '..' segment climbs above the project root -- declined, never
        # turned into a files node whose id would carry the escaping '..'.
        return None, anchor, NOT_A_PATH_REASON

    if _is_path_shaped(canon, project_root):
        candidates = path_index.get(canon, [])
        if len(candidates) == 1 and id_counts.get(candidates[0].id, 0) == 1:
            return candidates[0].id, anchor, None
        node = _get_or_create_files_node(canon, project_root, files_registry, other_ids, node_record_cls)
        if node is None:
            return None, anchor, NOT_A_PATH_REASON
        return node.id, anchor, None

    if canon in other_ids:
        return canon, anchor, None
    return None, anchor, NOT_A_PATH_REASON


def resolve_file_path_edges(
    *,
    project_root: Path,
    pending,
    primary_nodes,
    hub_nodes,
    node_record_cls,
    edge_record_cls,
):
    """Resolve every pending file-path relationship value for one build.

    Args:
        project_root: Absolute path to the project root.
        pending: Iterable of ``(surface, source_node, field, raw_value)``
            tuples, one per candidate value from a field the source
            surface declared in its own ``file_path_fields``.
        primary_nodes: Every NodeRecord read from a file this build (no
            synthetic hubs, no files nodes) -- the INDEX-FIRST source set.
        hub_nodes: Synthetic component-hub NodeRecords created earlier in
            the same post-processing step.
        node_record_cls: The caller's ``NodeRecord`` class.
        edge_record_cls: The caller's ``EdgeRecord`` class.

    Returns:
        ``(new_files_nodes, resolved_edges, declines)``.
    """
    project_root_posix = Path(project_root).as_posix()
    path_index = _build_path_index(primary_nodes, project_root_posix)
    id_counts = _id_counts(list(primary_nodes) + list(hub_nodes))
    other_ids = frozenset(id_counts.keys())
    files_registry: dict[str, object] = {}
    resolved_edges = []
    declines: list[DeclineRecord] = []

    for surface, source_node, field, raw_value in pending:
        target_id, anchor, reason = _resolve_single(
            raw_value, project_root, project_root_posix, path_index, id_counts, other_ids, files_registry, node_record_cls
        )
        if reason is not None:
            doc = _canonical_node_source(source_node.path, project_root_posix)
            declines.append(DeclineRecord(surface, doc, field, raw_value, reason))
            continue
        resolved_edges.append(
            edge_record_cls(source_id=source_node.id, target_id=target_id, edge_type=field, anchor=anchor)
        )

    return list(files_registry.values()), resolved_edges, declines


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-25 [python-coder/KM-KGS-100d-4 epic]: Initial authoring. New
  sibling module to knowledge_query.py (kept separate so
  knowledge_query.py's own check-file-size ratchet baseline is not grown by
  this feature). Implements canonicalisation (anchor strip, separator
  normalisation, absolute-inside-root -> repo-relative), the INDEX-FIRST
  path index with the KM-KGS-100d-4-i ambiguity rule (unique source path AND
  unique id, never a name-based fallback of any kind), present/missing
  marking on files nodes tested once per distinct path (KM-KGS-100d-4-ii),
  and decline reporting for a value that is neither an on-map id nor a
  project-relative path, with a distinct reason for a foreign absolute path
  never recovered by suffix (KM-KGS-100d-4-iii). NodeRecord/EdgeRecord
  classes are dependency-injected by the caller so this module never imports
  knowledge_query (avoiding a circular sibling-load). (#TICKETLESS
  reason=km-fast-lane-file-nodes)
- 2026-09-25 11:38 [python-coder/pr-reviewer fixes]: Fixed two
  canonicalisation defects pr-reviewer found. (1) _split_absolute compared
  an absolute value against project_root_posix with a case-sensitive
  startswith(), so a Windows drive-letter case mismatch (e.g. value spelled
  'c:/...' against a root that resolved to 'C:/...') was misclassified as
  foreign and declined. Added _split_drive() and made _split_absolute
  compare only the drive-letter segment case-insensitively; the repo
  -relative tail (and any POSIX-style value with no drive at all) is still
  compared exactly, never case-folded. (2) _is_path_shaped's existence
  check, (project_root / value).exists(), genuinely traverses '..'
  segments through the OS, so a value like 'scripts/../..' (the project
  root's own parent) was judged path-shaped and became a files node whose
  id carried the escaping '..', and an interior '..' that stayed inside
  the root (e.g. 'scripts/../config/paths.json') kept the uncollapsed
  string as its own node id instead of converging on the already
  -canonical spelling. Added _collapse_relative_segments(), a pure
  string/list lexical collapse (never resolve(), so it can never follow a
  symlink) run in _resolve_single right after the foreign-path check and
  before _is_path_shaped: a '..' that would climb above the project root
  returns None and is declined with NOT_A_PATH_REASON (the ordinary decline
  channel, so it gets the usual DECLINED stderr line and count); an
  interior '..' that stays inside the root collapses to its canonical form
  before any further resolution step sees it, so the disk-existence check
  can never traverse outside the root and both spellings land on the same
  node. (#TICKETLESS reason=km-fast-lane-file-nodes-canon-fixes)
====================================================================
"""
