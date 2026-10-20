"""
MODULE: _rc_records
GOAL: Find, load and index the requirement records the rule check examines, and hold
    the Context every rule family receives -- records with line numbers, repo-root
    handling, the store-wide id index and the readiness before-state.
BUSINESS CONTEXT: ACD-2500a-1 / -1-i / -1-ii. The check works on a feature folder it is
    handed, independent of the git index. An unreadable file is a `failed` finding that
    names file and line; a folder with no records is a failed check, never a silent pass.
ARCHITECTURE: `load_folder` returns (records, findings, files_seen); `records_checked`
    is `files_seen`, so a malformed file still counts (architect note D6). `Record` is a
    dict subclass (a family reads `record["covered_by"]`) that also carries `.file`
    (repo-root-relative POSIX), `.path` and `.text`. The checked folder uses
    yaml.SafeLoader, never the C accessor: the C loader accepts input the pure loader
    rejects, and finding that is this check's job. The store-wide id index is a
    directory walk by FILENAME (every record file is named <id>.yaml) with a lazy parse
    only for ids referenced from outside the folder. `Context` is the one object a
    family sees; its attributes are listed on the class. Deployed flat into
    <root>/scripts/ac_store/ (AC_STORE_DEPLOY_MAP).

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500a-1]: Created per the architect-review note
    (sections 1 and 7, D5-D8, D10).
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from _rc_report import DISPOSITION_FAILED, FAMILY_RECORD_READABLE, Finding

_REGISTRY_FILE = "index.yaml"
_SUFFIXES = (".yaml", ".yml")


class Record(dict):
    """A parsed requirement record: a dict plus `.file` (repo-relative POSIX), `.path`, `.text`."""

    file: str
    path: Path
    text: str


def to_rel_posix(path: Path, repo_root: Path) -> str:
    """Repo-root-relative POSIX form of `path`; the plain POSIX path when outside the root."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(Path(repo_root).resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def infer_repo_root(location: Path) -> Path:
    """Nearest ancestor of `location` holding docs/acceptance-criteria, else the cwd."""
    for candidate in (Path(location).resolve(), *Path(location).resolve().parents):
        if (candidate / "docs" / "acceptance-criteria").is_dir():
            return candidate
    return Path.cwd()


def discover(folder: Path) -> list[Path]:
    """Every record-candidate YAML file under `folder`, sorted; the index registry is skipped."""
    if not Path(folder).is_dir():
        return []
    found = [
        p for p in Path(folder).rglob("*")
        if p.is_file() and p.suffix.lower() in _SUFFIXES and p.name != _REGISTRY_FILE
    ]
    return sorted(found)


def _unreadable(path: Path, repo_root: Path, message: str, line: int | None) -> Finding:
    """The `failed` finding for a record file that could not be read."""
    return Finding(
        to_rel_posix(path, repo_root), None, FAMILY_RECORD_READABLE, DISPOSITION_FAILED,
        message, subject="unreadable", line=line,
    )


def load_one(path: Path, repo_root: Path) -> Record | Finding:
    """Parse one record file; a Finding (`failed`, with the line when known) if it cannot be."""
    try:
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
        data = yaml.load(text, Loader=yaml.SafeLoader)  # noqa: S506 - SafeLoader, see module docstring
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        problem = getattr(exc, "problem", None) or str(exc)
        return _unreadable(
            path, repo_root, f"record could not be read: YAML syntax error ({problem})",
            mark.line + 1 if mark is not None else None,
        )
    except (OSError, UnicodeDecodeError) as exc:
        return _unreadable(path, repo_root, f"record could not be read: {exc}", None)
    if not isinstance(data, dict) or not data.get("id"):
        return _unreadable(path, repo_root, "record could not be read: not a requirement record (no top-level id)", None)
    record = Record(data)
    record.file, record.path, record.text = to_rel_posix(path, repo_root), Path(path), text
    return record


def load_folder(folder: Path, repo_root: Path) -> tuple[list[Record], list[Finding], int]:
    """Load every record under `folder`: (records, load findings, files seen)."""
    return load_paths(discover(folder), repo_root)


def load_paths(files: list[Path], repo_root: Path) -> tuple[list[Record], list[Finding], int]:
    """Load the given record files: (records, load findings, files seen)."""
    records: list[Record] = []
    findings: list[Finding] = []
    for path in files:
        loaded = load_one(path, repo_root)
        if isinstance(loaded, Finding):
            findings.append(loaded)
        else:
            records.append(loaded)
    return records, findings, len(files)


def report_location(raw: str, folder: Path, repo_root: Path) -> str:
    """The `location` for the report: repo-relative POSIX when the folder exists, else the raw argument."""
    if Path(folder).is_dir():
        return to_rel_posix(folder, repo_root)
    return raw


def build_id_index(store_root: Path) -> dict[str, Path]:
    """{record id: file} for the whole store, by FILENAME (a directory walk, no YAML parse)."""
    index: dict[str, Path] = {}
    for current, _dirs, names in os.walk(store_root):
        for name in sorted(names):
            stem, suffix = os.path.splitext(name)
            if suffix.lower() in _SUFFIXES and name != _REGISTRY_FILE:
                index.setdefault(stem, Path(current) / name)
    return index


def common_location(store_root: Path, ids: list[str], index: dict[str, Path]) -> Path | None:
    """Deepest common directory of the ids' files, never above <store-root>/<component>/.

    None when no id is in the store. Ids spread over several components fall back to the
    first found id's component directory (a store-root-wide scan would blow the time budget).
    """
    files = [index[i] for i in ids if i in index]
    if not files:
        return None
    parents = [str(p.parent) for p in files]
    common = Path(os.path.commonpath(parents))
    store = Path(store_root)
    try:
        depth = len(common.resolve().relative_to(store.resolve()).parts)
    except ValueError:
        return common
    if depth >= 1:
        return common
    return store / files[0].resolve().relative_to(store.resolve()).parts[0]


def unreachable_id_findings(ids: list[str], index: dict[str, Path], folder: Path | None, raw: str) -> list[Finding]:
    """`failed` findings for ids the check cannot honour: absent from the store, or outside `folder`."""
    missing = [i for i in ids if i not in index]
    outside = [i for i in ids if i in index and (folder is None or not _is_under(index[i], folder))]
    found: list[Finding] = []
    if missing:
        found.append(Finding(raw, None, FAMILY_RECORD_READABLE, DISPOSITION_FAILED,
                             f"record ids {missing} do not exist in the store", subject="ids"))
    if outside:
        found.append(Finding(raw, None, FAMILY_RECORD_READABLE, DISPOSITION_FAILED,
                             f"record ids {outside} are outside the checked folder; check them separately",
                             subject="ids-outside-folder"))
    return found


def _is_under(path: Path, folder: Path) -> bool:
    """True when `path` lies inside `folder`."""
    try:
        Path(path).resolve().relative_to(Path(folder).resolve())
    except ValueError:
        return False
    return True


class BeforeState:
    """The readiness each record had when the stage started: from a snapshot file or a git ref."""

    def __init__(self, snapshot: dict[str, Any] | None = None, ref: str | None = None) -> None:
        self.snapshot = snapshot
        self.ref = ref
        self._by_file: dict[str, tuple[bool, Any]] = {}
        self.error: str | None = None

    @classmethod
    def from_snapshot_file(cls, path: Path) -> BeforeState:
        """Load `{id: readiness|null}` from JSON; `.error` is set when it cannot be read."""
        state = cls(snapshot={})
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            state.error = f"before-state unavailable: cannot read snapshot {Path(path).name}: {exc}"
            return state
        if not isinstance(data, dict):
            state.error = "before-state unavailable: snapshot is not a JSON object"
            return state
        state.snapshot = data
        return state

    def prefetch(self, records: list[Record], repo_root: Path) -> None:
        """For a git ref: read every record's committed text in ONE `git cat-file --batch`."""
        if self.ref is None or self.error:
            return
        try:
            verify = subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "--verify", f"{self.ref}^{{commit}}"],
                capture_output=True, timeout=60, check=False,
            )
            if verify.returncode != 0:
                self.error = f"before-state unavailable: git ref {self.ref!r} does not resolve"
                return
            wanted = [r.file for r in records]
            batch = subprocess.run(
                ["git", "-C", str(repo_root), "cat-file", "--batch"],
                input="".join(f"{self.ref}:{p}\n" for p in wanted).encode("utf-8"),
                capture_output=True, timeout=60, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.error = f"before-state unavailable: git failed ({exc})"
            return
        self._parse_batch(wanted, batch.stdout)

    def _parse_batch(self, wanted: list[str], out: bytes) -> None:
        """Read `git cat-file --batch` output: one header (+ blob) per wanted path, in order."""
        pos = 0
        for rel in wanted:
            end = out.find(b"\n", pos)
            header = out[pos:end].split() if end >= 0 else []
            pos = end + 1
            if len(header) == 3 and header[1] == b"blob":
                size = int(header[2])
                self._by_file[rel] = (True, _readiness_of(out[pos:pos + size]))
                pos += size + 1
            else:
                self._by_file[rel] = (False, None)

    def lookup(self, record: Record) -> tuple[bool, Any]:
        """(existed at stage start, readiness then) for `record`."""
        if self.ref is not None:
            return self._by_file.get(record.file, (False, None))
        snapshot = self.snapshot or {}
        rid = str(record["id"])
        return (rid in snapshot, snapshot.get(rid))


def _readiness_of(blob: bytes) -> Any:
    """The `readiness` of a committed record blob; None when it does not parse."""
    try:
        data = yaml.load(blob.decode("utf-8"), Loader=yaml.SafeLoader)  # noqa: S506
    except (yaml.YAMLError, UnicodeDecodeError):
        return None
    return data.get("readiness") if isinstance(data, dict) else None


@dataclass(eq=False)
class Context:
    """Everything a rule family may read. Families never write (only `_rc_edit` does).

    repo_root, folder, store_root: Paths. stage: the --stage value. records: the records
    of the checked folder in the CURRENT pass (re-bound between passes). schema /
    registry_ids / registry_path / schema_path: the rule sources of the store's record
    check. surface_map_path: the --surface-map override or None. migration_map: the
    namespace-to-graph-ids map (--migration-map or the shipped one). before: BeforeState
    or None. changed_since: the --changed-since REV (checked set = changed files only) or None. families: the FAMILIES in force (the record-schema adapter reads their
    CLAIMS_SUBJECTS).
    """

    repo_root: Path
    folder: Path
    store_root: Path
    stage: str = ""
    records: list[Record] = field(default_factory=list)
    schema: dict[str, Any] | None = None
    schema_path: Path | None = None
    registry_ids: set[str] = field(default_factory=set)
    registry_path: Path | None = None
    surface_map_path: Path | None = None
    migration_map: dict[str, Any] = field(default_factory=dict)
    before: BeforeState | None = None
    families: list[Any] = field(default_factory=list)
    changed_since: str | None = None
    _peer_cache: dict[Path, list[Record]] = field(default_factory=dict)
    _index: dict[str, Path] | None = None
    _store_cache: dict[str, Record | None] = field(default_factory=dict)

    @property
    def wide(self) -> bool:
        """True in --changed-since mode, where the checked set is only part of the folder."""
        return self.changed_since is not None

    @property
    def id_index(self) -> dict[str, Path]:
        """The store-wide {id: file} index, walked once on first use."""
        if self._index is None:
            self._index = build_id_index(self.store_root)
        return self._index

    def sibling(self, record_id: str) -> Record | None:
        """The record `record_id` from the CHECKED set (current pass); in `wide` mode also any store record."""
        found = next((r for r in self.records if r["id"] == record_id), None)
        return found if found is not None or not self.wide else self.store_record(record_id)

    def peers(self, record: Record) -> list[Record]:
        """The records a cross-record rule compares `record` with: the checked set, plus in `wide`
        (--changed-since) mode the unchanged records of the same folder."""
        if not self.wide:
            return self.records
        folder = record.path.parent
        if folder not in self._peer_cache:
            self._peer_cache[folder] = load_folder(folder, self.repo_root)[0]
        have = {r.file for r in self.records}
        return [*self.records, *(r for r in self._peer_cache[folder] if r.file not in have)]

    def forget_loaded(self) -> None:
        """Drop lazily loaded store/peer records (call after a repair rewrote files)."""
        self._store_cache.clear()
        self._peer_cache.clear()

    def store_record(self, record_id: str) -> Record | None:
        """Lazy parse of any record in the store by id (producers outside the folder); None if absent/unreadable."""
        if record_id not in self._store_cache:
            path = self.id_index.get(record_id)
            loaded = load_one(path, self.repo_root) if path else None
            self._store_cache[record_id] = loaded if isinstance(loaded, Record) else None
        return self._store_cache[record_id]

    def before_state(self, record: Record) -> tuple[bool, Any]:
        """(existed at stage start, readiness then); (False, None) when no before-state is loaded."""
        return self.before.lookup(record) if self.before is not None else (False, None)

    def claimed_subjects(self) -> set[str]:
        """Record-check subjects some registered family owns (see _rc_record_schema)."""
        return {s for fam in self.families for s in getattr(fam, "CLAIMS_SUBJECTS", ())}
