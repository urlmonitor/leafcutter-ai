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
ARCHITECTURE: ``measure(ac_root, test_roots)`` loads every finished record, collects
    the ``# covers:`` tags, then classifies each finished record exactly once, in this
    order: tagged, superseded, waived, untagged. Hence
    ``untagged + sum(exclusions) + tagged == finished`` (``sum_holds``) unless an
    exclusion lacks a published ground (``unexplained_shortfall``).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

try:  # flat import: the deployed store imports its siblings as top-level modules
    import _done_proof_phase_helpers as _helpers
except ImportError:  # pragma: no cover - package-style import (repo checkout)
    from scripts.ac_store import _done_proof_phase_helpers as _helpers

GROUND_SUPERSEDED = "superseded"
GROUND_WAIVED = "waived: declared test-free with a stated reason"
PUBLISHED_GROUNDS = frozenset({GROUND_SUPERSEDED, GROUND_WAIVED})

_DONE_RE = re.compile(r"^work_status:\s*done\s*$", re.M)
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
    unexplained_shortfall: int = 0
    unreadable: list[str] = field(default_factory=list)

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


def _load_finished(ac_root: Path) -> tuple[list[dict], list[str]]:
    """Return the parsed done records and the paths that could not be read or parsed."""
    records: list[dict] = []
    unreadable: list[str] = []
    for path in sorted(Path(ac_root).rglob("*.yaml")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            unreadable.append(str(path))
            continue
        if not _DONE_RE.search(text):
            continue
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            unreadable.append(str(path))
            continue
        if not isinstance(data, dict) or data.get("id") is None:
            unreadable.append(str(path))
        elif data.get("work_status") == "done":
            records.append(data)
    return records, unreadable


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


def _exclusion_ground(record: Mapping) -> str | None:
    """Return the ground on which the done gate leaves *record* out, or None."""
    if _SUPERSEDED_RE.match(str(record.get("status", "")).strip()):
        return GROUND_SUPERSEDED
    if _helpers.is_covers_tag_waived(record):
        return GROUND_WAIVED
    return None


def measure(ac_root: Path, test_roots: Sequence[Path]) -> Measurement:
    """Measure the untagged-done backlog of the store at *ac_root*."""
    records, unreadable = _load_finished(ac_root)
    tags = collect_covers_tags(test_roots)
    result = Measurement(finished=len(records), unreadable=unreadable)
    for record in records:
        ac_id = _strip_quotes(str(record["id"]))
        ground = None if ac_id in tags else _exclusion_ground(record)
        if ac_id in tags:
            result.tagged += 1
        elif ground is None:
            result.untagged.append(ac_id)
        elif ground in PUBLISHED_GROUNDS:
            result.exclusions[ground] = result.exclusions.get(ground, 0) + 1
        else:
            result.unexplained_shortfall += 1
    result.untagged.sort()
    return result
