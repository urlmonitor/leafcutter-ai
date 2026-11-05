"""
MODULE: scripts/build_orchestration/_cs_runs.py
GOAL: The base-versus-now pytest runs of the sweep check (TQ-500g-3-ii): an existing test that passed
    before the work and is now skipped, expected to fail, or gone is "weakened".
BUSINESS CONTEXT: Weakening is a runtime fact, so the decision comes from running the same test files on
    both sides -- never from the writer's list. The list supplies one exit only: a ``removed`` entry with a
    note and an ``absent`` fingerprint excuses an absent test (never a skipped or expected-to-fail one),
    and the test then appears under ``removed`` with the note as the reason. A run that did not finish, a
    contradictory run or a file that does not collect is inconclusive and stops the work, never passes.
ARCHITECTURE: The base side runs in an export of the base ref (``git archive`` read by ``tarfile``) in a
    temp dir that is always removed; the working tree, the index, the stash and the worktree list are never
    touched. Both sides go through ``_wvr_pytest.run_selected`` (``NodeSpec.cwd`` = the side's root, repo
    relative file arguments, so node ids compare equal). ``consumer_sweep.check`` calls :func:`run_checks`.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import _cs_edits as edits_mod
import _wvr_gate as gate_mod
from _wvr_pytest import NodeSpec, PytestRun, run_selected
from _wvr_scope import is_test_path

_LOG = logging.getLogger("consumer_sweep")
_CONFIG_NAMES = frozenset({"pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"})
_NO_TESTS = 5
_WHAT = {"SKIPPED": "skipped", "XFAIL": "expected to fail", "XPASS": "expected to fail"}


@dataclass
class RunsResult:
    """What the runs found: weakened / removed / inconclusive items and whether any run was in scope."""

    weakened: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)
    inconclusive: list[dict] = field(default_factory=list)
    in_scope: bool = False


def _is_runnable(rel: str) -> bool:
    """True for a ``.py`` file pytest collects as tests (a conftest or helper is not run itself)."""
    name = rel.rsplit("/", 1)[-1]
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _base_files(root: Path, base_sha: str) -> list[str]:
    """Every file path at the base commit (raises ``GateError`` when git cannot list it)."""
    return [p for p in gate_mod.git_text(root, "ls-tree", "-r", "--name-only", "-z", base_sha).split(chr(0)) if p]


def _widened(rel: str, folders: list[str]) -> bool:
    """True when a changed conftest / config file sits in a folder at or above *rel* (``.`` is the repo root)."""
    return any(f == "." or rel.startswith(f + "/") for f in folders)


def scope_files(pairs: list[tuple[str, str]], base_files: list[str], test_root_rel: str | None) -> list[str]:
    """The test files both sides run: changed or deleted existing ones, widened by a conftest or config change.

    A config file governs the folder it sits in, so a nested unrelated one (``docs/pyproject.toml``) widens
    nothing; one at the repo root, above the test root or inside it covers the tests below it.
    """
    names = [(st, p, PurePosixPath(p).name) for st, p in pairs]
    tests = [(st, p, n) for st, p, n in names if is_test_path(p, test_root_rel)]
    wanted = {p for st, p, _n in tests if st[:1] != "A" and _is_runnable(p)}
    folders = [PurePosixPath(p).parent.as_posix() for _st, p, n in tests if n == "conftest.py"]
    folders += [PurePosixPath(p).parent.as_posix() for _st, p, n in names if n in _CONFIG_NAMES]
    wanted.update(r for r in base_files if _runnable_test(r, test_root_rel) and _widened(r, folders))
    return sorted(wanted)


def _runnable_test(rel: str, test_root_rel: str | None) -> bool:
    """True for a runnable test file inside the test root (a stray ``test_*.py`` elsewhere is not widened to)."""
    prefix = (test_root_rel or "").strip("/")
    return _is_runnable(rel) and is_test_path(rel, test_root_rel) and (not prefix or rel.startswith(prefix + "/"))


def _rmtree(path: Path) -> None:
    """Remove *path* completely (read-only files included); log, never raise, when it cannot."""

    def _chmod_retry(func, name, _exc):  # noqa: ANN001 -- shutil's onexc protocol
        os.chmod(name, 0o700)
        func(name)

    try:
        shutil.rmtree(path, onexc=_chmod_retry)
    except OSError as exc:
        _LOG.warning("the base export %s could not be removed: %s", path, exc)


class ExportError(subprocess.SubprocessError):
    """``git archive`` of the base ref exited with a failure status."""

    def __init__(self, returncode: int) -> None:
        super().__init__(f"git archive exited {returncode}")


def _keep_member(member: tarfile.TarInfo, dest: str) -> tarfile.TarInfo | None:
    """The ``data`` filter's view of *member*; symlinks and hardlinks are dropped (never needed to run tests)."""
    if member.issym() or member.islnk():
        return None
    return tarfile.data_filter(member, dest)


def _extract_stream(stream, dest: Path) -> None:
    """Extract the regular files and folders of the tar *stream* into *dest* (no seeking needed)."""
    with tarfile.open(fileobj=stream, mode="r|") as tar:
        for member in tar:
            kept = _keep_member(member, str(dest))
            if kept is not None:
                tar.extract(kept, dest, filter="fully_trusted")


def _export(root: Path, base_sha: str, dest: Path) -> None:
    """Extract ``git archive`` of *base_sha* into *dest* (raises OSError / TarError / SubprocessError)."""
    cmd = ["git", "-C", str(root), "archive", "--format=tar", base_sha]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)  # noqa: S603
        try:
            _extract_stream(proc.stdout, dest)
            while proc.stdout.read(65536):  # the tar's end padding: let git finish so its status is real
                pass
            proc.wait(timeout=120)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=30)
            proc.stdout.close()
    except OSError as exc:
        _LOG.warning("git archive of %s failed: %s", base_sha, exc)
        raise
    if proc.returncode != 0:
        raise ExportError(proc.returncode)


def _run_side(files: list[str], side_root: Path) -> PytestRun:
    """One pytest run of repo-relative *files* with *side_root* as the working directory.

    Exit status 5 (no test collected at all, e.g. files holding only fixtures) is a run with nothing in it.
    """
    run = run_selected([NodeSpec(Path(f), (), side_root) for f in files])
    if run.status == "crash" and run.returncode == _NO_TESTS:
        return PytestRun("ran", module_skipped=run.module_skipped)
    return run


def _failed_files(run: PytestRun, files: list[str]) -> set[str]:
    """The files of *files* the run could not collect (its kind plugin named the module)."""
    folded = [c.casefold() for c in run.collection_failed]
    return {f for f in files if any(c == f.casefold() or c.endswith("/" + f.casefold()) for c in folded)}


def _chain(nodeid: str) -> str:
    """The ``Class::method`` / ``function`` part of *nodeid* without its ``[param-id]``."""
    return nodeid.split("::", 1)[1].split("[", 1)[0] if "::" in nodeid else ""


def _tail(nodeid: str) -> str:
    """The part of *nodeid* after the file, ``[param-id]`` kept."""
    return nodeid.split("::", 1)[1] if "::" in nodeid else ""


def _excuses(entries: list[dict], file: str, nodeid: str) -> str | None:
    """The note of the recorded ``removed`` entry that excuses the absent *nodeid*, or ``None``."""
    names = {_tail(nodeid), _chain(nodeid)}
    for e in entries:
        note = e.get("note")
        if (e.get("status") == "removed" and e.get("file") == file and e.get("fingerprint") == edits_mod.ABSENT
                and e.get("test") in names and isinstance(note, str) and note.strip()):
            return note
    return None


def compare_runs(base: PytestRun, now: PytestRun, entries: list[dict], skip_absent: set[str]) -> RunsResult:
    """Weakened and removed items: PASSED at the base, SKIPPED / XFAIL / XPASS / absent now.

    Args:
        base: The base-side run.
        now: The working-tree run.
        entries: The honoured sweep list entries (only the ``removed`` exit is read).
        skip_absent: Files that failed to collect now; their missing node ids are not judged.

    Returns:
        The :class:`RunsResult` with ``weakened`` and ``removed`` filled.
    """
    result = RunsResult(in_scope=True)
    seen_removed: set[tuple[str, str]] = set()
    for nodeid, outcome in sorted(base.by_nodeid.items()):
        if outcome != "PASSED":
            continue
        file, test = nodeid.split("::", 1)[0], _chain(nodeid)
        now_outcome = now.by_nodeid.get(nodeid)
        what = "removed" if now_outcome is None else _WHAT.get(now_outcome)
        if what == "removed" and file in now.module_skipped:
            what = "skipped"  # the whole module is skipped at collection: never a removal, never excusable
        if what is None or (what == "removed" and file in skip_absent):
            continue
        note = _excuses(entries, file, nodeid) if what == "removed" else None
        if note is None:
            result.weakened.append({"file": file, "test": test, "nodeid": nodeid, "what": what})
        elif (file, test) not in seen_removed:
            seen_removed.add((file, test))
            result.removed.append({"file": file, "test": test, "nodeid": nodeid, "reason": note})
    return result


def _not_ran(side: str, run: PytestRun, files: list[str]) -> list[dict]:
    """One inconclusive item per file when the *side* run did not finish."""
    return [{"file": f, "detail": f"the {side} run of {f} did not finish: {run.detail}"} for f in files]


def _run_both(root: Path, base_sha: str, files: list[str], entries: list[dict]) -> RunsResult:
    """Export the base, run both sides, compare; the export is removed whatever happened."""
    export = Path(tempfile.mkdtemp(prefix="leafcutter_cs_base_"))
    try:
        try:
            _export(root, base_sha, export)
        except (OSError, tarfile.TarError, subprocess.SubprocessError) as exc:
            detail = f"the base ref {base_sha} could not be exported for the base run: {exc}"
            return RunsResult([], [], [{"file": f, "detail": detail} for f in files], True)
        base_files = [f for f in files if (export / f).is_file()]
        base = _run_side(base_files, export)
    finally:
        _rmtree(export)
    now = _run_side([f for f in files if (root / f).is_file()], root)
    bad = [i for side, run, fs in (("base", base, base_files), ("working-tree", now, files)) if run.status != "ran"
           for i in _not_ran(side, run, fs)]
    if bad:
        return RunsResult([], [], bad, True)
    base_bad, now_bad = _failed_files(base, base_files), _failed_files(now, files)
    result = compare_runs(base, now, entries, now_bad)
    for side, names in (("base", base_bad), ("working-tree", now_bad)):
        result.inconclusive.extend({"file": f, "detail": f"{f} did not collect in the {side} run"} for f in sorted(names))
    result.weakened = [w for w in result.weakened if w["file"] not in base_bad | now_bad]
    return result


def run_checks(root: Path, base_sha: str, pairs: list[tuple[str, str]], test_root_rel: str | None,
               entries: list[dict]) -> RunsResult:
    """Run the in-scope test files at the base and now and report what the work weakened.

    Args:
        root: Repo root (the working tree).
        base_sha: The base commit.
        pairs: ``[(status, path)]`` of the working tree against the base.
        test_root_rel: The test root relative to the repo, or ``None``.
        entries: Honoured sweep list entries.

    Returns:
        The :class:`RunsResult`; nothing in scope means no runs.
    """
    try:
        files = scope_files(pairs, _base_files(root, base_sha), test_root_rel)
    except gate_mod.GateError as exc:
        return RunsResult([], [], [{"file": None, "detail": f"the files at the base ref could not be listed: {exc}"}], True)
    if not files:
        return RunsResult()
    return _run_both(root, base_sha, files, entries)
