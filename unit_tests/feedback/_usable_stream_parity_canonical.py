"""
MODULE: _usable_stream_parity_canonical
GOAL: The DEPLOYED canonical usable-stream rule, asked once per (rule content, row state,
    file) and re-based onto the install that asked (AC INF-500d-4-ix).
BUSINESS CONTEXT: Every copy of a row is compared with the same canonical answer, so
    asking a fresh interpreter once per copy repeats identical work. The memo key carries
    a digest of every deployed rule file and a fingerprint of the row's declaration and
    directories, so editing a private layout's ``sink_resolution.py`` (or changing a row)
    is never answered from a stale entry.
ARCHITECTURE: A thread-safe module-level memo (one lock per key, so concurrent pairs of
    the same row ask once). Locations are stored with the asking install's tree replaced
    by a marker and restored onto each caller's own tree, so a copy's location can still
    be compared with the canonical one. Failures are never memoised.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback._usable_stream_parity_core import ParityError, Verdict, python_verdict
from unit_tests.feedback._usable_stream_parity_rows import InstalledRow

_SINK_RESOLUTION = ".leafcutter/scripts/knowledge/sink_resolution.py"
_TREE_MARK = "<TREE>"
_CANONICAL_PROBE = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import sink_resolution as sr
out_root, filename = Path(sys.argv[2]), sys.argv[3]
if filename:
    values, why = sr.read_absolute_values(out_root, ("operational_log_root",))
    location = str(Path(values["operational_log_root"]) / filename) if values else None
else:
    stream, why = sr.read_usable_stream(out_root, "operational_telemetry_stream")
    location = str(stream) if stream is not None else None
if location is not None and not sr.enduring_root_exists(out_root):
    location, why = None, "stale: the enduring root that holds the log root is gone"
print(json.dumps({"location": location, "detail": why}))
"""

_MEMO: dict[tuple, tuple] = {}
_MEMO_LOCKS: dict[tuple, threading.Lock] = {}
_MEMO_GUARD = threading.Lock()


def _rule_digest(knowledge_dir: Path) -> str:
    """Digest of every file of the deployed sink query, so editing a private layout's rule changes the key."""
    digest = hashlib.sha256()
    try:
        for path in sorted(p for p in knowledge_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            digest.update(str(path.relative_to(knowledge_dir)).encode())
            digest.update(path.read_bytes())
    except OSError as exc:
        reason = f"cannot read the deployed rule under {knowledge_dir}: {exc}"
        raise ParityError("canonical", reason) from exc
    return digest.hexdigest()


def _row_fingerprint(installed: InstalledRow) -> str:
    """The declaration text and the directories beside the project: everything the rule's answer depends on."""
    declaration = h.declaration_path(installed.out_root)
    try:
        text = declaration.read_text(encoding="utf-8") if declaration.is_file() else "<absent>"
    except OSError as exc:
        reason = f"cannot read the declaration of row {installed.name}: {exc}"
        raise ParityError("canonical", reason) from exc
    beside = sorted(str(p.relative_to(installed.tree)) for child in installed.tree.iterdir()
                    if child.name != "project" for p in (child, *child.rglob("*")) if p.is_dir())
    return text.replace(str(installed.tree), _TREE_MARK) + "\n" + "\n".join(beside)


def canonical_verdict(layout_dir: Path, installed: InstalledRow, filename: str | None = None) -> Verdict:
    """The DEPLOYED canonical rule, answered by a fresh interpreter.

    Usable iff ``read_usable_stream`` accepts the declared telemetry stream and the enduring
    root is live; with *filename* set, that file placed directly under the declared root.
    Memoised per (content of the deployed rule, row state, filename); the answer is re-based
    onto *installed*'s own tree so a location can be compared with a copy's.
    """
    knowledge = Path(layout_dir) / _SINK_RESOLUTION
    if not knowledge.is_file():
        reason = f"the deployed rule is missing at {knowledge}"
        raise ParityError("canonical", reason)
    key = (_rule_digest(knowledge.parent), installed.name, filename or "", _row_fingerprint(installed))
    with _MEMO_GUARD:
        lock = _MEMO_LOCKS.setdefault(key, threading.Lock())
    tree = str(installed.tree)
    with lock:
        if key not in _MEMO:
            args = [_CANONICAL_PROBE, str(knowledge.parent), str(installed.out_root), filename or ""]
            answer = python_verdict(args, installed.tree, "canonical")
            where = str(answer.location).replace(tree, _TREE_MARK) if answer.location else None
            _MEMO[key] = (answer.usable, where, (answer.detail or "").replace(tree, _TREE_MARK))
        usable, where, detail = _MEMO[key]
    return Verdict(usable, Path(where.replace(_TREE_MARK, tree)) if where else None, detail.replace(_TREE_MARK, tree))


# DECISION HISTORY
# ================================================================================
# - 2026-10-14 16:00 [python-coder]: Split out of the copies module; memoised per rule content, row state and filename. (#TICKET-INF-500d-4-ix)
