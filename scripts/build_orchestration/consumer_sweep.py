"""
MODULE: scripts/build_orchestration/consumer_sweep.py
GOAL: The sweep list steps: ``record`` stores the test writer's list of edits to existing tests and
    fixtures; ``check`` stops the work when an edit to an existing test or fixture is not named in
    a list that still matches it (TQ-500g-3-i).
BUSINESS CONTEXT: Changing an existing test is allowed only when the test writer swept the
    consumers and said so. The check decides from the code at the base ref against the working
    tree and from the recorded lists -- never from a writer's claim that its list is complete.
    ``wrong_version_gate.py finish`` calls ``check`` first, on every drive that reaches commit.
ARCHITECTURE: Public module with its own CLI (steps ``record`` and ``check``) and exactly one JSON
    object on stdout; progress logging goes to stderr only. Lists live at
    ``<git-dir>/leafcutter/work/<work-key>/consumer_sweep.json`` (written atomically through
    ``_wvr_gate.atomic_write_bytes``). Edit comparison: ``_cs_edits``. TQ-500g-3-ii adds the
    runs (``_cs_runs``) and TQ-500g-3-iii the assertion comparison (``_cs_asserts``) to the same
    ``check`` JSON (``removed``, ``weakened``, ``loosened``, ``inconclusive``); no second CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path, PurePosixPath

import _cs_asserts as asserts_mod
import _cs_edits as edits_mod
import _cs_runs as runs_mod
import _wvr_gate as gate_mod
from _wvr_scope import ChangesError, DiffCache, is_test_path, path_refusal
from _wvw_write import _plain_segment

_LOG = logging.getLogger("consumer_sweep")
_STATUSES = frozenset({"strengthened", "unaffected", "removed"})
_LIST_NAME = "consumer_sweep.json"
_DEVICE_NAMES = frozenset({"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)),
                           *(f"LPT{n}" for n in range(1, 10))})
_LINE_BREAKS = re.compile(r"[\r\n]")


def _check_shape(**fields: object) -> dict:
    """The one check JSON object: every key present, ``passed`` derived from ``reason`` and ``error``."""
    out: dict = {"passed": True, "applicable": False, "reason": None, "unlisted": [], "weakened": [],
                 "loosened": [], "removed": [], "inconclusive": [], "error": None}
    out.update(fields)
    out["passed"] = out["reason"] is None and out["error"] is None
    return out


def _refused(why: str) -> tuple[dict, int]:
    """The record result of a refused list: nothing was written."""
    return {"recorded": False, "path": None, "error": why, "entries": 0}, 1


def _key_problem(work_key: str) -> str | None:
    """Why *work_key* cannot be a directory name on every platform, or ``None``."""
    if not _plain_segment(work_key) or work_key != work_key.rstrip(". "):
        return f"the work key {work_key!r} is not one plain path segment"
    if work_key.split(".")[0].strip().upper() in _DEVICE_NAMES:
        return f"the work key {work_key!r} is a reserved device name"
    return None


def _path_problem(root: Path, file: object) -> str | None:
    """Why *file* is not a canonical repo-relative POSIX path inside the repo, or ``None``."""
    if (not isinstance(file, str) or "\\" in file or file == "." or PurePosixPath(file).as_posix() != file
            or path_refusal(root, file)):
        return f"{file!r} is not a canonical repo-relative POSIX path inside the repo"
    return None


def _entry_problem(root: Path, item: object) -> str | None:
    """Why one stdin entry is refused, or ``None``."""
    if not isinstance(item, dict):
        return "an entry is not an object"
    test, note = item.get("test"), item.get("note")
    if item.get("status") not in _STATUSES:
        return f"unknown status {item.get('status')!r}"
    if not isinstance(note, str) or not note.strip() or _LINE_BREAKS.search(note.strip()):
        return "an entry needs a non-empty one-line note"
    if not isinstance(test, str) or not test.strip() or _LINE_BREAKS.search(test):
        return "an entry needs a one-line test name"
    return _path_problem(root, item.get("file"))


def _resolve_base(test_root: Path, base_ref: str) -> str:
    """The commit sha *base_ref* names (raises ``GateError`` when it names none)."""
    return gate_mod.git_text(test_root, "rev-parse", "--verify", f"{base_ref}^{{commit}}")


def record(work_key: str, test_root: Path, raw: str, base_ref: str = "HEAD") -> tuple[dict, int]:
    """Validate the stdin list, add the fingerprints and the base commit, and store it."""
    problem = _key_problem(work_key)
    if problem:
        return _refused(problem)
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return _refused(f"the list is not parseable JSON: {exc}")
    items = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return _refused("the list needs an entries array")
    try:
        root = Path(gate_mod.git_text(test_root, "rev-parse", "--show-toplevel"))
        git_dir = Path(gate_mod.git_text(test_root, "rev-parse", "--absolute-git-dir"))
        base_sha = _resolve_base(test_root, base_ref or "HEAD")
    except gate_mod.GateError as exc:
        return _refused(f"internal error: {exc}")
    for item in items:
        problem = _entry_problem(root, item)
        if problem:
            return _refused(problem)
    stored = [{"file": i["file"], "test": i["test"], "status": i["status"], "note": i["note"],
               "fingerprint": edits_mod.current_fingerprint(root, i["file"], i["test"])} for i in items]
    path = git_dir / "leafcutter" / "work" / work_key / _LIST_NAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        gate_mod.atomic_write_bytes(path, json.dumps({"base": base_sha, "entries": stored}, indent=2).encode("utf-8"))
    except OSError as exc:
        _LOG.warning("the list could not be written: %s", exc)
        return _refused(f"the list could not be written: {exc}")
    return {"recorded": True, "path": str(path), "error": None, "entries": len(stored)}, 0


def _moved_files(root: Path, recorded: str, current: str) -> set[str] | None:
    """Files any commit in ``recorded..current`` touched (even if undone later); ``None`` unless an ancestor."""
    try:
        gate_mod.git_text(root, "merge-base", "--is-ancestor", recorded, current)
        names = gate_mod.git_text(root, "log", "--format=", "--name-only", "-z", f"{recorded}..{current}")
    except gate_mod.GateError as exc:
        _LOG.info("sweep list base %s is not usable against %s: %s", recorded, current, exc)
        return None
    return {n for n in names.split(chr(0)) if n}


def _honoured(data: dict, root: Path, base_sha: str) -> list[dict]:
    """The entries of one list that still hold at *base_sha* (none when its base is unrelated)."""
    found = [e for e in data["entries"] if isinstance(e, dict)] if isinstance(data["entries"], list) else []
    recorded = data.get("base")
    if recorded == base_sha:
        return found
    if not isinstance(recorded, str) or not recorded:
        return []
    moved = _moved_files(root, recorded, base_sha)
    if moved is None:
        return []
    return [e for e in found if e.get("file") not in moved]


def read_lists(git_dir: Path, base_sha: str, root: Path) -> list[dict]:
    """Every honoured entry of every readable list under ``<git-dir>/leafcutter/work/*/``.

    A list is honoured at its own base, or at a later base that descends from it, for each entry whose
    file no commit in between touched. Any git failure leaves the entry unhonoured.
    """
    entries: list[dict] = []
    for path in sorted((git_dir / "leafcutter" / "work").glob(f"*/{_LIST_NAME}")):
        try:
            data = json.loads(path.read_bytes().decode("utf-8"))
            data["entries"]  # noqa: B018 -- a list without entries is unreadable
        except (OSError, ValueError, KeyError, TypeError) as exc:
            _LOG.warning("sweep list %s is unreadable and excuses nothing: %s", path, exc)
            continue
        entries.extend(_honoured(data, root, base_sha))
    return entries


def _context(test_root: Path) -> tuple[Path, Path, str | None]:
    """The repo root, the git dir and the test root relative to the repo (``None`` when it is the repo)."""
    root = Path(gate_mod.git_text(test_root, "rev-parse", "--show-toplevel"))
    git_dir = Path(gate_mod.git_text(test_root, "rev-parse", "--absolute-git-dir"))
    rel = os.path.relpath(os.path.realpath(test_root), os.path.realpath(root)).replace("\\", "/")
    return root, git_dir, (None if rel in {".", ""} or rel.startswith("..") else rel)


def _compare(root: Path, base_ref: str, files: list[str]) -> tuple[list[edits_mod.Edit], list[dict]]:
    """All edits of the changed existing test files, and the files that could not be compared."""
    found: list[edits_mod.Edit] = []
    inconclusive: list[dict] = []
    for rel in files:
        try:
            base, now = edits_mod.read_sources(root, base_ref, rel)
        except UnicodeDecodeError as exc:
            inconclusive.append({"file": rel, "detail": f"{rel} is not UTF-8 text: {exc.reason}"})
            continue
        result = edits_mod.compare_file(rel, base, now)
        found.extend(result.edits)
        if result.problem:
            inconclusive.append({"file": rel, "detail": result.problem})
    return found, inconclusive


def check(test_root: Path, base_ref: str) -> dict:
    """Compare the work against the base ref and the recorded lists; return the check JSON object."""
    ref = base_ref or "HEAD"
    try:
        root, git_dir, test_root_rel = _context(test_root)
        base_sha = _resolve_base(test_root, ref)
        pairs = DiffCache(root, ref).get()
        changed = sorted({p for st, p in pairs if st[:1] != "A" and is_test_path(p, test_root_rel)})
        found, inconclusive = _compare(root, ref, changed)
    except (gate_mod.GateError, ChangesError, OSError, UnicodeDecodeError) as exc:
        detail = f'the base ref "{ref}" or the changed files could not be read: {exc}'
        return _check_shape(applicable=True, reason="inconclusive", inconclusive=[{"file": None, "detail": detail}])
    entries = read_lists(git_dir, base_sha, root)
    unlisted = edits_mod.unlisted_edits(found, entries)
    loosened = asserts_mod.loosened_of(found)
    ran = runs_mod.run_checks(root, base_sha, pairs, test_root_rel, entries)
    inconclusive = inconclusive + ran.inconclusive
    reason = None
    if unlisted:
        reason = "unlisted" if entries else "sweep list missing"
    elif ran.weakened:
        reason = "weakened"
    elif loosened:
        reason = "loosened"
    elif inconclusive:
        reason = "inconclusive"
    return _check_shape(applicable=bool(found or inconclusive or ran.in_scope), reason=reason,
                        inconclusive=inconclusive, weakened=ran.weakened, loosened=loosened, removed=ran.removed,
                        unlisted=[{"file": e.file, "test": e.test} for e in unlisted])


def _parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Sweep list record and check (TQ-500g-3-i)")
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="store the test writer's list (JSON on stdin)")
    rec.add_argument("--work-key", required=True)
    rec.add_argument("--test-root", required=True)
    rec.add_argument("--base-ref", default="HEAD")
    chk = sub.add_parser("check", help="stop on an existing test or fixture edit no list names")
    chk.add_argument("--test-root", required=True)
    chk.add_argument("--base-ref", default="HEAD")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print exactly one JSON object on stdout; exit 0 only when recorded / passed."""
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
    args = _parser().parse_args(argv)
    try:
        if args.command == "record":
            payload, code = record(args.work_key, Path(args.test_root), sys.stdin.buffer.read().decode("utf-8-sig"),
                                   args.base_ref)
        else:
            payload = check(Path(args.test_root), args.base_ref)
            code = 0 if payload["passed"] else 1
    except Exception as exc:  # noqa: BLE001 -- the one-JSON-object contract holds whatever failed
        _LOG.warning("the %s step failed: %s", args.command, exc)
        failed = f"internal error: {exc}"
        payload = _refused(failed)[0] if args.command == "record" else _check_shape(error=failed)
        code = 1
    print(json.dumps(payload))
    return code


if __name__ == "__main__":
    sys.exit(main())
