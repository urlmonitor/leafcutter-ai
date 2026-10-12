"""
MODULE: scripts/build_orchestration/wrong_version_runner.py
GOAL: The ONE shared wrong-version runner every build route calls: once the code
    passes, each wrong version the guarding tests name is applied, run and undone,
    and a wrong version that survives (or is never validly run) stops the work.
BUSINESS CONTEXT: TQ-500g-1-i / -ii / -iii. A test that passes on the finished
    code but would also pass on a wrong version proves nothing. The verdict comes
    from real pytest runs alone: scope is declared in the AC ``test_spec`` (never
    inferred), each test answers for the wrong versions its OWN entry names,
    "the fix undone" is prepared from git against the base ref, and the code is put
    back byte for byte after every run, even a run that is cut short.
ARCHITECTURE: Public module (no leading underscore: scripts/evals imports it) with
    its own CLI, siblings ``_wvr_scope`` (scope, manifest, fix undone),
    ``_wvr_pytest`` (one run, read through the shared parser and kind rule),
    ``_wvr_verdict`` (rows and the verdict) and ``_wvr_gate`` (copies, journal,
    recovery under ``<git-dir>/leafcutter/wrong-version-runs/<run-id>/``).
    ``run`` prints exactly one JSON object on stdout (logging goes to stderr) and
    exits 0 when ``gate_passed`` else 1; an internal error still prints that shape
    with ``gate_passed`` false. ``recover`` prints ``{restored, ok, copy_dir}``.
    Every ``run`` begins with the same recovery. Never uses git stash.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import _wvr_gate as gate_mod
from _wvr_pytest import PytestRun, run_selected
from _wvr_scope import UNDONE_NAME, ScopedTest, build_alterations, load_manifest, prepare_fix_undone, resolve_scope, wrong_version_key
from _wvr_verdict import NO_SOURCE_OUTCOME, NOT_APPLIED, NOT_PREPARED, assemble, classify_run, row

_LOG = logging.getLogger("wrong_version_runner")
NO_TESTS_OUTCOME = "wrong-version runs not applicable: no covering test declares a wrong version or the discrimination angle"
_NOT_IN_SCOPE = "not in scope for the runs: its test_spec entry names no wrong version and does not declare the discrimination angle"


@dataclass
class WrongVersion:
    """One wrong version to run and the tests whose own entry names it."""

    key: str
    name: str
    holders: list[ScopedTest] = field(default_factory=list)

    @property
    def is_undone(self) -> bool:
        """True for "the fix undone"."""
        return self.key == wrong_version_key(UNDONE_NAME)


class PutBackFailed(Exception):
    """The code could not be put back; the work stops."""


def _wrong_versions(tests: list[ScopedTest]) -> list[WrongVersion]:
    """List the wrong versions to run: named ones in order, then the fix undone."""
    ordered: dict[str, WrongVersion] = {}
    for test in tests:
        for key, name in test.versions.items():
            ordered.setdefault(key, WrongVersion(key, name)).holders.append(test)
    undone = ordered.pop(wrong_version_key(UNDONE_NAME), WrongVersion(wrong_version_key(UNDONE_NAME), UNDONE_NAME))
    return [*ordered.values(), undone]


def _interrupted(_signum: int, _frame: object) -> None:
    """Turn a termination signal into a KeyboardInterrupt so the put-back runs."""
    raise KeyboardInterrupt


@dataclass
class Context:
    """Everything one run needs."""

    root: Path
    test_root_rel: str | None
    ac_root_rel: str | None
    base_ref: str
    manifest: dict[str, dict]
    manifest_problem: str
    gate: gate_mod.RunGate
    undone: tuple[dict[str, bytes], str, str] | None = None
    interrupted: bool = False


def _prepare(wv: WrongVersion, ctx: Context) -> tuple[dict[str, bytes], str, str]:
    """Prepare the alteration of *wv*; return ``(files, state, detail)`` (state ``ready`` when usable)."""
    if wv.is_undone:
        if ctx.undone is None:
            ctx.undone = prepare_fix_undone(ctx.root, ctx.base_ref, ctx.test_root_rel, ctx.ac_root_rel)
        return ctx.undone
    entry = ctx.manifest.get(wv.key)
    if entry is None:
        extra = f" ({ctx.manifest_problem})" if ctx.manifest_problem else ""
        return {}, "invalid", f"no entry in the alterations manifest{extra}"
    files, problem = build_alterations(entry, ctx.root, ctx.test_root_rel)
    return ({}, "invalid", problem) if problem else (files, "ready", "")


def _files_for(wv: WrongVersion, ctx: Context) -> tuple[dict[str, bytes], list[dict]]:
    """Return ``(files to apply, rows)``; rows are set when *wv* cannot be run."""
    files, state, detail = _prepare(wv, ctx)

    def rows(result: str, text: str) -> list[dict]:
        return [row(t.label, wv.name, result, text) for t in wv.holders] or [row("", wv.name, result, text)]

    if state == "not_applicable":
        return {}, [row("", wv.name, "not_applicable", detail)]
    if state != "ready":
        return {}, rows("invalid", detail if detail.startswith(NOT_PREPARED) else f"{NOT_PREPARED}: {detail}")
    try:
        changed = {rel: data for rel, data in files.items() if _as_written(ctx.root, rel) != data}
    except OSError as exc:
        return {}, rows("invalid", f"{NOT_PREPARED}: a file to alter cannot be read ({exc}); nothing was altered")
    return (changed, []) if changed else ({}, rows("not_applied", NOT_APPLIED))


def _as_written(root: Path, rel: str) -> bytes | None:
    """Return the working file's bytes; ``None`` only when it does not exist (other errors raise)."""
    try:
        return (root / rel).read_bytes()
    except FileNotFoundError:
        return None


def _apply_run_restore(ctx: Context, wv: WrongVersion, files: dict[str, bytes], tests: list[ScopedTest]) -> PytestRun:
    """Apply *wv*, run *tests* once, and ALWAYS put the code back before returning.

    Raises:
        PutBackFailed: When the byte comparison still fails after the put-back.
    """
    run = PytestRun("crash", "the run did not start")
    try:
        ctx.gate.apply(wv.name, files)
        run = run_selected([t.node for t in tests])
    except gate_mod.GateError as exc:
        run = PytestRun("crash", str(exc))
    except OSError as exc:
        run = PytestRun("crash", f"the alteration could not be written: {exc}")
    except KeyboardInterrupt:
        ctx.interrupted = True
        run = PytestRun("interrupted", "the drive was interrupted")
    finally:
        back = ctx.gate.restore()
        if not back.ok:
            raise PutBackFailed("; ".join(back.failures))  # chained over any in-flight exception
    return run


def _baseline(tests: list[ScopedTest]) -> tuple[list[dict], bool]:
    """Run every in-scope test once on the code as written; return ``(rows, ok)``."""
    run = run_selected([t.node for t in tests])
    if run.status != "ran":
        return [row(t.label, "", "not_run", f"the run on the code as written was cut short ({run.status}): {run.detail}") for t in tests], False
    bad = [t for t in tests if run.outcome.get(t.node.identity) != "PASSED"]
    rows = [row(t.label, "", "not_run", f"failing on the code as written (outcome {run.outcome.get(t.node.identity, 'none')})") for t in bad]
    return rows, not bad


def _execute(ac_ids: list[str], test_root: Path, ac_root: Path, base_ref: str, alterations: str | None) -> dict:
    """Do the whole run and return the verdict dict."""
    if not ac_ids:
        return assemble([], applicable=False, outcome=NO_SOURCE_OUTCOME)
    gate_dir = gate_mod.gate_root(test_root)
    recovered = gate_mod.recover_all(gate_dir)
    if not recovered.ok:
        return _stopped("; ".join(recovered.failures))
    scope = resolve_scope(ac_ids, test_root, ac_root)
    if scope.problem:
        return assemble([row("", "", "invalid", scope.problem)], reason_override=scope.problem)
    out_rows = [row(label, "", "not_in_scope", _NOT_IN_SCOPE) for label in scope.out_of_scope]
    out_rows += [row(name, "", "invalid", f"declared test not found: {name} is declared in test_spec but no covers-tagged test of that name exists") for name in scope.missing]
    if not scope.tests and not scope.missing:
        return assemble(out_rows, applicable=False, outcome=NO_TESTS_OUTCOME)
    return _verdict_for(scope.tests, out_rows, test_root, ac_root, base_ref, alterations, gate_dir)


def _stopped(message: str, rows: list[dict] | None = None) -> dict:
    """The verdict of a run that must stop because the code may still be altered."""
    return assemble(rows or [row("", "", "not_run", message)], reason_override=message, outcome=message)


def _rel_to(root: Path, path: Path) -> str | None:
    """Return *path* relative to *root* (POSIX), or ``None`` when it lies outside."""
    rel = os.path.relpath(os.path.realpath(path), os.path.realpath(root)).replace("\\", "/")
    return None if rel.startswith("..") or os.path.isabs(rel) else rel


def _verdict_for(tests: list[ScopedTest], out_rows: list[dict], test_root: Path, ac_root: Path, base_ref: str,
                 alterations: str | None, gate_dir: Path) -> dict:
    """Run the baseline and each wrong version; return the verdict."""
    root = Path(gate_mod.git_text(test_root, "rev-parse", "--show-toplevel"))
    manifest, problem = load_manifest(alterations)
    run_id = f"{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    ctx = Context(root, _rel_to(root, test_root), _rel_to(root, ac_root), base_ref, manifest, problem,
                  gate_mod.RunGate(root, gate_dir / run_id))
    unresolved = [t for t in tests if t.node is None]
    rows = [row(t.label, "", "invalid", t.issue) for t in unresolved] + out_rows
    runnable = [t for t in tests if t.node is not None]
    if not runnable:
        return assemble(rows)
    base_rows, ok = _baseline(runnable)
    if not ok:
        reason = "failing on the code as written" if base_rows and "failing" in base_rows[0]["detail"] else "unfinished"
        return assemble(rows + base_rows, reason_override=reason if reason != "unfinished" else None)
    for wv in _wrong_versions(runnable):
        files, early = _files_for(wv, ctx)
        if early:
            rows += early
            continue
        try:
            run = _apply_run_restore(ctx, wv, files, runnable if wv.is_undone else wv.holders)
        except PutBackFailed as exc:
            rows.append(row("", wv.name, "not_run", str(exc)))
            return _stopped(str(exc), rows)
        rows += classify_run(runnable if wv.is_undone else wv.holders, wv.holders, run, wv.name, wv.is_undone)
        if ctx.interrupted:
            break
    return assemble(rows)


def run_runner(ac_ids: list[str], test_root: Path, ac_root: Path, base_ref: str = "HEAD", alterations: str | None = None) -> dict:
    """Public in-process entry: return the verdict dict (never raises for a run failure).

    Args:
        ac_ids: Requirement ids whose covering tests are held to wrong versions.
        test_root: Root directory scanned for covering tests (inside the worktree).
        ac_root: Root of the AC store.
        base_ref: The ref the work began from ("the fix undone" is this content).
        alterations: Path of the TQ-500g-1-iv alterations manifest, or ``None``.

    Returns:
        The verdict dict; an internal error gives ``gate_passed`` false.
    """
    try:
        return _execute(ac_ids, Path(test_root), Path(ac_root), base_ref or "HEAD", alterations)
    except Exception as exc:  # noqa: BLE001 -- the JSON shape must print whatever went wrong
        return _failure_verdict(exc, Path(test_root))


def _failure_verdict(exc: BaseException, test_root: Path) -> dict:
    """Build the verdict of an internal error; say so when the code may still be altered."""
    _LOG.warning("wrong-version runner internal error: %r", exc)
    reason = f"internal error: {exc!r}"
    if isinstance(exc, PutBackFailed):
        reason = str(exc)
    else:
        try:
            left = gate_mod.recover_all(gate_mod.gate_root(test_root))
        except (gate_mod.GateError, OSError) as rec_exc:
            reason += f"; the code may still be altered (recovery could not run: {rec_exc})"
        else:
            if not left.ok:
                reason += "; " + "; ".join(left.failures)
    return assemble([row("", "", "not_run", reason)], reason_override=reason, outcome=reason)


def recover(cwd: Path) -> dict:
    """The recovery step: put back any file with an open journal entry.

    Args:
        cwd: Any directory inside the worktree.

    Returns:
        ``{restored, ok, copy_dir}``.
    """
    try:
        result = gate_mod.recover_all(gate_mod.gate_root(cwd))
    except gate_mod.GateError as exc:
        _LOG.warning("recovery could not run: %s", exc)
        return {"restored": [], "ok": False, "copy_dir": None, "detail": str(exc)}
    return {"restored": result.restored, "ok": result.ok, "copy_dir": result.copy_dir,
            "detail": "; ".join(result.failures)}


def _parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Shared wrong-version runner (TQ-500g-1)")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Apply, run and undo each wrong version; print one JSON verdict")
    run.add_argument("--ac-ids", default="")
    run.add_argument("--test-root", required=True)
    run.add_argument("--ac-root", required=True)
    run.add_argument("--base-ref", default="HEAD")
    run.add_argument("--alterations", default="")
    sub.add_parser("recover", help="Put back any file a cut-short run left altered")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print exactly one JSON object on stdout; exit 0 only when it passes.

    Args:
        argv: Arguments (default ``sys.argv[1:]``).

    Returns:
        The process exit code.
    """
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
    args = _parser().parse_args(argv)
    for name in ("SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _interrupted)
    with contextlib.redirect_stdout(sys.stderr):
        if args.command == "recover":
            payload = recover(Path.cwd())
            ok = payload["ok"]
        else:
            ids = [i.strip() for i in args.ac_ids.split(",") if i.strip()]
            try:
                payload = run_runner(ids, Path(args.test_root), Path(args.ac_root), args.base_ref, args.alterations or None)
            except BaseException as exc:  # noqa: BLE001 -- KeyboardInterrupt and friends still print the shape
                payload = _failure_verdict(exc, Path(args.test_root))
            ok = payload["gate_passed"]
    print(json.dumps(payload))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
