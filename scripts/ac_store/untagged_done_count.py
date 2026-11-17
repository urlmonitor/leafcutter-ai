"""
MODULE: untagged_done_count
GOAL: Measure the KM-ADM-005 untagged-done backlog: the finished (work_status done)
    acceptance-criteria records that no ``# covers:`` test tag names, WITHOUT counting
    the records the done gate itself waives, and report each exclusion as a count
    paired with its ground.
BUSINESS CONTEXT: KM-ADM-005-1. The ratchet in
    unit_tests/docs/test_artifact_graph_covers_scope.py counted every finished record
    no test tags, so every legitimate test-free close (``test_required: false`` with a
    stated reason, which check-done-proof accepts) tripped it. The ratchet must agree
    with the gate, so the waiver decision is the gate's own shared predicate
    ``is_covers_tag_waived`` (BO-2500a-1-ii), looked up at call time and never copied.
    Grounds follow ACS-1100b-1: an exclusion whose ground is not on PUBLISHED_GROUNDS
    is an unexplained shortfall and fails the sum check.
    KM-ADM-005-3: a finished L0, L1 or docs-only composite whose children the done
    gate's own composite rule proves leaves the count under a fourth ground that says
    the tags were read and the tests were not run. The rule
    ``_done_proof_composite._unproven_composite_children`` is reached as a module
    attribute at call time, never copied.
ARCHITECTURE: ``measure(ac_root, test_roots)`` reads the whole store once (records,
    id set, live-children index) and collects the ``# covers:`` tags, then classifies
    each finished record exactly once, in this order: tagged, superseded, waived,
    proved through its children, untagged. Hence
    ``untagged + sum(exclusions) + tagged == finished`` (``sum_holds``) unless an
    exclusion lacks a published ground (``unexplained_shortfall``). A record reaches
    the gate rule only when it is level L0/L1 or docs-only AND its covered_by lists
    every live record whose parent it is. The gate rule resolves children through an
    index of the store, so no per-child directory walk is paid.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

try:  # flat import: the deployed store imports its siblings as top-level modules
    import _done_proof_composite as _composite
    import _done_proof_phase_helpers as _helpers
    import ac_parent_id
    import ac_retirement
except ImportError:  # pragma: no cover - package-style import (repo checkout)
    from scripts.ac_store import _done_proof_composite as _composite
    from scripts.ac_store import _done_proof_phase_helpers as _helpers
    from scripts.ac_store import ac_parent_id, ac_retirement

GROUND_SUPERSEDED = "superseded"
GROUND_WAIVED = "waived: declared test-free with a stated reason"
GROUND_PROVED = "proved through its children (tags read, tests not run)"
PUBLISHED_GROUNDS = frozenset({GROUND_SUPERSEDED, GROUND_WAIVED, GROUND_PROVED})

_DONE_RE = re.compile(r"^work_status:\s*done\s*$", re.M)
_ID_LINE_RE = re.compile(r"^id:\s*(.+?)\s*$", re.M)
_PARENT_LINE_RE = re.compile(r"^parent:\s*(.+?)\s*$", re.M)
_RETIRED_LINE_RE = re.compile(r"^status:\s*[\"']?superseded", re.M)
_SUPERSEDED_RE = re.compile(r"^superseded(_by)?$")
_COVERS_RE = re.compile(r"covers:\s*([A-Za-z0-9\-_,\s\"']+)")
_TAG_SUFFIXES = {".py", ".ts", ".tsx", ".js"}


@dataclass
class Measurement:
    """Result of one untagged-done measurement."""

    finished: int = 0
    tagged: int = 0
    untagged: list[str] = field(default_factory=list)
    exclusions: dict[str, int] = field(default_factory=dict)
    excluded_ids: dict[str, list[str]] = field(default_factory=dict)
    unexplained_shortfall: int = 0
    unreadable: list[str] = field(default_factory=list)
    parent_field_only: int = 0  # records related to a parent only through the parent field

    @property
    def sum_holds(self) -> bool:
        """Return whether untagged + exclusions + tagged equals finished."""
        if self.unreadable:
            return False
        return len(self.untagged) + sum(self.exclusions.values()) + self.tagged == self.finished

    def assert_sum(self) -> None:
        """Raise AssertionError when the sum does not hold."""
        assert not self.unreadable, f"unreadable done-record files (not counted): {self.unreadable}"
        assert self.sum_holds, (
            f"untagged ({len(self.untagged)}) + exclusions ({dict(self.exclusions)}) + tagged ({self.tagged})"
            f" != finished ({self.finished}); unexplained shortfall: {self.unexplained_shortfall}"
        )

    def exclusion_lines(self) -> list[str]:
        """Return one ``<count> - <ground>`` line per explained exclusion."""
        return [f"{count} - {ground}" for ground, count in sorted(self.exclusions.items())]


def _strip_quotes(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        token = token[1:-1]
    return token.strip()


@dataclass
class _Store:
    """Everything read from the store in one walk (KM-ADM-005-3)."""

    records: list[dict] = field(default_factory=list)  # every readable record with an id
    paths: dict[str, Path] = field(default_factory=dict)  # filename stem -> first path
    unreadable: list[str] = field(default_factory=list)  # done-record files that could not be read
    skipped_field_only: int = 0  # unparsed, never-retired files related to a parent only by the parent field

    @property
    def finished(self) -> list[dict]:
        """Return the records whose work_status is done."""
        return [r for r in self.records if r.get("work_status") == "done"]


def _parse_record(text: str) -> dict | None:
    """Return the record parsed from *text*, or None when it is not a mapping with an id."""
    try:
        data = yaml.safe_load(text)  # pure-Python parser: a C-parser site must be declared (TQ-600a-11)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) and data.get("id") is not None else None


def _line_value(pattern: re.Pattern[str], text: str) -> str:
    """Return the quote-stripped value of the first line of *text* matching *pattern*, or ''."""
    match = pattern.search(text)
    return _strip_quotes(match.group(1).split("#")[0]) if match else ""


def _may_parent_a_candidate(path: Path, text: str, candidates: frozenset[str]) -> bool:
    """Return whether the cheap reading of *text* relates it to a candidate composite.

    Related means the ``parent:`` line, or the parent derived from the ``id:`` line or the filename
    stem, names a candidate. Everything else cannot enter the candidate's live-children set.
    """
    ids = {path.stem, _line_value(_ID_LINE_RE, text)} - {""}
    related = {_line_value(_PARENT_LINE_RE, text)} | {ac_parent_id.derive_parent_id(i) for i in ids}
    return bool(related & candidates)


def _cheap_field_only(text: str) -> int:
    """Return 1 when *text* names a parent on its ``parent:`` line that differs from the id-derived one."""
    ac_id = _line_value(_ID_LINE_RE, text)
    named = _line_value(_PARENT_LINE_RE, text)
    return int(bool(ac_id) and bool(named) and named != ac_parent_id.derive_parent_id(ac_id))


def _load_store(ac_root: Path) -> _Store:
    """Read every file under *ac_root* once and parse only the records the ratchet can need.

    Parsed in full: each done-looking record, and each other record whose parent could be a finished
    L0/L1/docs composite (the only records whose liveness ``_covered_by_complete`` asks about).
    ``paths`` still names every file, so ``store_ids`` stays the full set of stems.
    """
    store = _Store()
    texts: dict[Path, str] = {}
    for path in sorted(Path(ac_root).rglob("*.yaml")):
        store.paths.setdefault(path.stem, path)
        try:
            texts[path] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            store.unreadable.append(str(path))
    others: list[Path] = []
    for path, text in texts.items():
        if not _DONE_RE.search(text):
            others.append(path)
            continue
        data = _parse_record(text)
        if data is None:
            store.unreadable.append(str(path))
        else:
            store.records.append(data)
    candidates = frozenset(
        _strip_quotes(str(r["id"])) for r in store.finished if _docs_or_top_level(r) and r.get("covered_by")
    )
    for path in others:
        text = texts[path]
        if not (_RETIRED_LINE_RE.search(text) or _may_parent_a_candidate(path, text, candidates)):
            store.skipped_field_only += _cheap_field_only(text)  # never retired: counts without a parse
            continue
        data = _parse_record(text)
        if data is not None:
            store.records.append(data)
    return store


class _IndexedRoot:
    """Stands in for the store root when the gate rule resolves a child by id.

    The gate's ``_resolve_child_ac`` walks the whole store with ``rglob`` once per child; this answers
    the same ``<id>.yaml`` query from the index built by the one walk of ``_load_store``.
    """

    def __init__(self, paths: Mapping[str, Path]) -> None:
        self._paths = paths

    def rglob(self, pattern: str) -> list[Path]:
        """Return the one path whose stem is the queried id, or nothing."""
        path = self._paths.get(pattern.removesuffix(".yaml"))
        return [path] if path is not None else []


@dataclass
class _Context:
    """Store-wide inputs, computed once per measurement."""

    tags: set[str]  # the ratchet's own reading: decides the 'tagged' bucket only
    gate_tags: set[str]  # the done gate's own reading (COVERS_TAG_RE): handed to the gate rule only
    store_ids: frozenset[str]
    root: _IndexedRoot
    live_children: dict[str, set[str]]
    parent_field_only: int = 0


def _tags_in_file(path: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    tags: set[str] = set()
    for line in text.splitlines():
        match = _COVERS_RE.search(line)
        if match:
            tags.update(t for t in (_strip_quotes(x) for x in re.split(r"[,\s]+", match.group(1))) if t)
    return tags


def collect_covers_tags(test_roots: Sequence[Path]) -> set[str]:
    """Return every id named by a ``# covers:`` line under *test_roots*."""
    tagged: set[str] = set()
    for root in test_roots:
        if not Path(root).exists():
            continue
        for path in Path(root).rglob("*"):
            if path.is_dir() or path.suffix not in _TAG_SUFFIXES:
                continue
            if "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            tagged |= _tags_in_file(path)
    return tagged


def _index_live_children(store: _Store, store_ids: frozenset[str]) -> tuple[dict[str, set[str]], int]:
    """Return ``{parent id: ids of its live records}`` and how many records only the parent field relates.

    A record is a child of the parent named by its ``parent`` field or by ``derive_parent_id`` of its id
    (either source counts). A record the shared retirement predicate retires is not live.
    """
    children: dict[str, set[str]] = {}
    field_only = 0
    for record in store.records:
        if ac_retirement.is_retired(record, store_ids):
            continue
        ac_id = _strip_quotes(str(record["id"]))
        derived = ac_parent_id.derive_parent_id(ac_id)
        named = _strip_quotes(str(record.get("parent") or ""))
        field_only += bool(named) and named != derived
        for parent in {p for p in (named, derived) if p}:
            children.setdefault(parent, set()).add(ac_id)
    return children, field_only


def _build_context(store: _Store, test_roots: Sequence[Path]) -> _Context:
    """Compute the store-wide inputs once per measurement."""
    store_ids = frozenset(store.paths)
    live_children, field_only = _index_live_children(store, store_ids)
    gate_tags: set[str] = set()
    for root in test_roots:
        gate_tags |= _composite._collect_all_covered_ids(Path(root))  # the gate's COVERS_TAG_RE scan
    return _Context(
        tags=collect_covers_tags(test_roots),
        gate_tags=gate_tags,
        store_ids=store_ids,
        root=_IndexedRoot(store.paths),
        live_children=live_children,
        parent_field_only=field_only + store.skipped_field_only,
    )


def _docs_or_top_level(record: Mapping) -> bool:
    """Return whether *record* is level L0/L1 or its change_target is exactly docs (fail closed)."""
    if record.get("level") in ("L0", "L1"):
        return True
    target = record.get("change_target")
    if isinstance(target, list):
        target = target[0] if len(target) == 1 else None
    return target == "docs"


def _covered_by_complete(record: Mapping, ac_id: str, ctx: _Context) -> bool:
    """Return whether covered_by lists every live record on disk whose parent is *ac_id*."""
    listed = set(_composite._composite_child_ids(record.get("covered_by")))
    return ctx.live_children.get(ac_id, set()) <= listed


def _proved_through_children(record: Mapping, ac_id: str, ctx: _Context) -> bool:
    """Return whether the gate's own composite rule finds no unproven child of *record* (and b, c hold)."""
    if not _composite._composite_child_ids(record.get("covered_by")):
        return False
    if not _docs_or_top_level(record) or not _covered_by_complete(record, ac_id, ctx):
        return False
    unproven = _composite._unproven_composite_children(record, ctx.root, ctx.gate_tags, store_ids=ctx.store_ids)
    return not unproven


def _exclusion_ground(record: Mapping, ac_id: str, ctx: _Context) -> str | None:
    """Return the ground on which *record* leaves the count, or None; tested superseded, waived, proved."""
    if _SUPERSEDED_RE.match(str(record.get("status", "")).strip()):
        return GROUND_SUPERSEDED
    if _helpers.is_covers_tag_waived(record):
        return GROUND_WAIVED
    if _proved_through_children(record, ac_id, ctx):
        return GROUND_PROVED
    return None


def _place(result: Measurement, ac_id: str, ground: str | None) -> None:
    """Put one finished, untagged record into its bucket."""
    if ground is None:
        result.untagged.append(ac_id)
    elif ground in PUBLISHED_GROUNDS:
        result.exclusions[ground] = result.exclusions.get(ground, 0) + 1
        result.excluded_ids.setdefault(ground, []).append(ac_id)
    else:
        result.unexplained_shortfall += 1


def measure(ac_root: Path, test_roots: Sequence[Path]) -> Measurement:
    """Measure the untagged-done backlog of the store at *ac_root*."""
    store = _load_store(ac_root)
    ctx = _build_context(store, test_roots)
    finished = store.finished
    result = Measurement(finished=len(finished), unreadable=store.unreadable, parent_field_only=ctx.parent_field_only)
    for record in finished:
        ac_id = _strip_quotes(str(record["id"]))
        if ac_id in ctx.tags:
            result.tagged += 1
        else:
            _place(result, ac_id, _exclusion_ground(record, ac_id, ctx))
    result.untagged.sort()
    for ids in result.excluded_ids.values():
        ids.sort()
    return result
