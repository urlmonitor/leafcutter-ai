#!/usr/bin/env python3
"""
MODULE: design_prepass
GOAL: Print, as ONE deterministic JSON document, the mechanical file facts of a batch of
    requirement records for the code-aware test designer: per declared file `exists` /
    `to_be_created` / `neither`, per named test directory its existence, per reference file its
    existence, same file type and same area. Read-only.
BUSINESS CONTEXT: ACD-2500d-5-i (ADR-071, ADR-072; G4 architect note section 3). The agent that
    opens source files must not guess whether a file is in the tree; this script tells it, and
    the workflow reads the report from disk (no report = no dispatch). The definitions of
    "same type" and "same area" live here and in docs/reference/code-aware-step.md.
ARCHITECTURE: `python design_prepass.py --ids A,B [--store-root DIR] [--repo-root DIR]
    [--test-root unit_tests/]`. Roots resolve as in requirement_rule_check; --test-root defaults to
    skills_config `testing_context.test_root`, else `unit_tests/`. stdout is exactly one JSON
    document written as bytes (LF only, sorted keys, lists sorted by id and path, no timestamps),
    so two runs are byte-identical. Any error (unknown id, unreadable record, bad flag) prints
    nothing on stdout, a message on stderr and exits non-zero (1 failure, 2 usage). Records are
    read once each and only `exists` calls touch the tree. Declared files are read only through
    declared_files.get_declared_files. In scope: a leaf (L2/L3) record with a test_intent,
    declared files or package_surface true; other ids are skipped silently. Flat sibling
    modules _rc_records, _rc_report, _test_intent and declared_files; deployed to
    <root>/scripts/ac_store/.

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500d-5-i]: Created per the G4 architect note, section 3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from _rc_records import build_id_index, infer_repo_root, load_one
from _rc_report import Finding
from _test_intent import intent_entries
from declared_files import NoDeclaredFiles, get_declared_files

DEFAULT_TEST_ROOT = "unit_tests/"
PENDING_MARKER = "reference file pending"
MAX_CANDIDATES = 10
LEAF_LEVELS = ("L2", "L3")
STATE_EXISTS, STATE_TO_BE_CREATED, STATE_NEITHER = "exists", "to_be_created", "neither"
_CONFIG_DIRS = (".claude", ".leafcutter")


def in_repo(path: str) -> bool:
    """True when `path` is a relative path that stays inside the repo (no drive, root or `..`)."""
    posix = path.replace("\\", "/")
    if PureWindowsPath(path).drive or PurePosixPath(posix).is_absolute():
        return False
    return bool(posix) and ".." not in PurePosixPath(posix).parts


def _exists(repo_root: Path, path: str, *, directory: bool = False) -> bool:
    """Existence of a repo-relative path; a path outside the repo never exists."""
    if not in_repo(path):
        return False
    target = repo_root / path
    return target.is_dir() if directory else target.exists()


def declared_entries(record: dict) -> list[dict]:
    """The record's well-formed declared entries ({path: str, state}), in declared order."""
    declared = get_declared_files(record)
    if isinstance(declared, NoDeclaredFiles):
        return []
    return [e for e in declared if isinstance(e, dict) and isinstance(e.get("path"), str) and e["path"]]


def file_state(repo_root: Path, entry: dict) -> str:
    """The tree wins: exists > declared to_be_created > neither."""
    if _exists(repo_root, entry["path"]):
        return STATE_EXISTS
    return STATE_TO_BE_CREATED if entry.get("state") == "to_be_created" else STATE_NEITHER


def deliverable_of(entries: list[dict]) -> str | None:
    """First declared to_be_created path, else the first declared path, else None."""
    created = [e["path"] for e in entries if e.get("state") == "to_be_created"]
    return (created or [e["path"] for e in entries] or [None])[0]


def _parent(path: str) -> str:
    """Parent directory of a path, POSIX form."""
    return PurePosixPath(path.replace("\\", "/")).parent.as_posix()


def _suffix(path: str) -> str:
    """Lower-cased file suffix of a path."""
    return PurePosixPath(path.replace("\\", "/")).suffix.lower()


def reference_entry(repo_root: Path, path: str, deliverable: str | None) -> dict:
    """{path, exists, same_type, same_area} judged against the deliverable's suffix and directory."""
    return {
        "path": path,
        "exists": _exists(repo_root, path),
        "same_type": deliverable is not None and _suffix(path) == _suffix(deliverable),
        "same_area": deliverable is not None and _parent(path) == _parent(deliverable),
    }


def _candidates(repo_root: Path, deliverable: str | None) -> list[str]:
    """Up to MAX_CANDIDATES sorted siblings of the deliverable: same directory, same suffix, not itself."""
    if deliverable is None or not in_repo(deliverable):
        return []
    folder = _parent(deliverable)
    here = repo_root / folder
    if not here.is_dir():
        return []
    own = PurePosixPath(deliverable.replace("\\", "/")).name
    names = sorted(
        p.name for p in here.iterdir() if p.is_file() and p.suffix.lower() == _suffix(deliverable) and p.name != own
    )
    return [(PurePosixPath(folder) / name).as_posix() for name in names[:MAX_CANDIDATES]]


def reference_files(repo_root: Path, record: dict, deliverable: str | None) -> list[dict]:
    """The named reference file plus, for a pending record only, the sibling candidates; sorted by path."""
    requirements = record.get("it_requirements")
    named = requirements.get("reference_file_path") if isinstance(requirements, dict) else None
    paths = [named] if isinstance(named, str) and named else []
    if record.get("hold_reason") == PENDING_MARKER:
        paths += _candidates(repo_root, deliverable)
    return [reference_entry(repo_root, p, deliverable) for p in sorted(set(paths))]


def named_test_dirs(repo_root: Path, record: dict, entries: list[dict], test_root: str) -> list[dict]:
    """Distinct test_spec target_dirs plus `<test-root>/<parent dir name>` per declared file; sorted."""
    spec = record.get("test_spec")
    named = {
        str(item["target_dir"]).replace("\\", "/").rstrip("/")
        for item in (spec if isinstance(spec, list) else [])
        if isinstance(item, dict) and item.get("target_dir")
    }
    root = test_root.replace("\\", "/").strip("/")
    for entry in entries:
        name = PurePosixPath(_parent(entry["path"])).name if in_repo(entry["path"]) else ""
        if name:
            named.add(f"{root}/{name}")
    return [{"path": d, "exists": _exists(repo_root, d, directory=True)} for d in sorted(named)]


def in_scope(record: dict) -> bool:
    """A leaf with a test_intent, declared files or package_surface true."""
    if record.get("level") not in LEAF_LEVELS:
        return False
    return bool(
        intent_entries(record) is not None or declared_entries(record) or record.get("package_surface") is True
    )


def record_report(repo_root: Path, record: dict, test_root: str) -> dict[str, Any]:
    """The report entry of one in-scope record."""
    entries = declared_entries(record)
    return {
        "id": str(record["id"]),
        "declared_files": sorted(
            ({"path": e["path"], "state": file_state(repo_root, e)} for e in entries), key=lambda d: d["path"]
        ),
        "test_dirs": named_test_dirs(repo_root, record, entries, test_root),
        "reference_files": reference_files(repo_root, record, deliverable_of(entries)),
    }


def load_batch(repo_root: Path, store_root: Path, ids: list[str]) -> tuple[list[dict], str | None]:
    """Load each id once: (records, None), or ([], the message) for an unknown or unreadable id."""
    index = build_id_index(store_root)
    unknown = sorted(i for i in ids if i not in index)
    if unknown:
        return [], f"record ids {unknown} do not exist in the store"
    loaded = [load_one(index[i], repo_root) for i in ids]
    for item in loaded:
        if isinstance(item, Finding):
            return [], f"{item.file}: {item.message}"
    return loaded, None


def build_report(repo_root: Path, records: list[dict], test_root: str) -> dict[str, Any]:
    """The report of the in-scope records, sorted by id."""
    scoped = sorted((r for r in records if in_scope(r)), key=lambda r: str(r["id"]))
    return {
        "batch": [str(r["id"]) for r in scoped],
        "records": [record_report(repo_root, r, test_root) for r in scoped],
    }


def default_test_root(repo_root: Path) -> str:
    """`testing_context.test_root` of the project's skills_config.json, else `unit_tests/`."""
    for platform_dir in _CONFIG_DIRS:
        config = repo_root / platform_dir / "skills_config.json"
        if not config.is_file():
            continue
        try:
            value = json.loads(config.read_text(encoding="utf-8")).get("testing_context", {}).get("test_root")
        except (OSError, ValueError, AttributeError) as exc:
            print(f"design_prepass: ignoring unreadable {config}: {exc}", file=sys.stderr)
            return DEFAULT_TEST_ROOT
        return value if isinstance(value, str) and value else DEFAULT_TEST_ROOT
    return DEFAULT_TEST_ROOT


def _build_parser() -> argparse.ArgumentParser:
    """The CLI parser (flags and root resolution copy requirement_rule_check)."""
    parser = argparse.ArgumentParser(prog="design_prepass", description="Print the file facts of a batch of records.")
    parser.add_argument("--ids", required=True, help="comma-separated record ids")
    parser.add_argument("--store-root", help="default <repo-root>/docs/acceptance-criteria")
    parser.add_argument("--repo-root", help="default: nearest ancestor of the cwd holding docs/acceptance-criteria")
    parser.add_argument("--test-root", help="default: skills_config testing_context.test_root, else unit_tests/")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print the JSON report on stdout; any error prints none and exits non-zero."""
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2
    ids = list(dict.fromkeys(i.strip() for i in args.ids.split(",") if i.strip()))
    if not ids:
        print("design_prepass: --ids names no record", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root).resolve() if args.repo_root else infer_repo_root(Path.cwd())
    store_root = Path(args.store_root).resolve() if args.store_root else repo_root / "docs" / "acceptance-criteria"
    try:
        records, problem = load_batch(repo_root, store_root, ids)
        report = build_report(repo_root, records, args.test_root or default_test_root(repo_root))
    except OSError as exc:
        problem = str(exc)
    if problem:
        print(f"design_prepass: {problem}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write((json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode("ascii"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
