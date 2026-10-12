"""
MODULE: unit_tests/build_orchestration/_tq500g1_review_fixtures.py
GOAL: Shared helpers for the review-finding regression tests of the wrong-version
    runner (test_tq_500g_1_review*.py): in-process access to the private runner
    modules, plain sandboxes with exact file control, and tree/git probes.
BUSINESS CONTEXT: TQ-500g-1-i / -iii review findings. Sandboxes are REAL git repos
    built through _tq500g1_fixtures / _tq500f3i_fixtures (yaml.safe_dump AC store,
    real pytest runs); nothing here hand-types a pytest result.
ARCHITECTURE: Not a test file. Inserts scripts/build_orchestration on sys.path (as
    the runner's own siblings do) so the private modules import by bare name.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1_fixtures as fx

_SCRIPTS = str(fx.REPO_ROOT / "scripts" / "build_orchestration")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import _wvr_gate as gate_mod  # noqa: E402, F401
import _wvr_scope as scope_mod  # noqa: E402, F401
import wrong_version_runner as wvr  # noqa: E402

AC_ID = fx.AC_ID


def inproc(sb: fx.Sandbox) -> dict:
    """Call ``run_runner`` in-process against *sb* (cwd must already be sb.work)."""
    return wvr.run_runner([AC_ID], sb.test_root, sb.ac_root, sb.base_sha, str(sb.manifest))


def attempt(fn, *args, **kwargs):
    """Return ``(result, exception)``; today's raising behaviour is observed, not raised."""
    try:
        return fn(*args, **kwargs), None
    except BaseException as exc:  # noqa: BLE001 -- the wrong behaviour under test
        return None, exc


def read_or_none(path: Path) -> bytes | None:
    """Bytes of *path*, or ``None`` when it is not a readable file."""
    try:
        return path.read_bytes()
    except OSError:
        return None


def status(work: Path) -> str:
    """``git status --porcelain`` of *work*."""
    return gitfx.run_git(["status", "--porcelain"], cwd=work)


def text_of(verdict: dict) -> str:
    """Every string in *verdict*, normalised, joined (for 'mentions X' assertions)."""
    return fx.norm(" || ".join(fx.walk_strings(verdict)))


def write_manifest(sb: fx.Sandbox, name: str, files: list[dict]) -> None:
    """Replace the manifest with one prepared entry for *name* over *files*."""
    entry = {"name": name, "status": "prepared", "reason": None, "diff": "", "files": files}
    sb.manifest.write_text(json.dumps({"work_key": "tq-9101-rev", "entries": [entry]}), encoding="utf-8")


def plain_sandbox(root: Path, *, base: dict[str, str], final: dict[str, str | None], tests: dict[str, str],
                  must_catch: dict[str, list[str]], ac_rel: str | None = None) -> fx.Sandbox:
    """Build a git sandbox with exact base files, then the work's final state.

    Args:
        base: Files committed at the base ref.
        final: Files after the work (``None`` deletes a file or whole directory).
        tests: ``{file name under fx_tests: source}`` (each test carries ``# covers:`` itself).
        must_catch: ``{test function: [wrong versions]}`` declared in the AC test_spec.
        ac_rel: AC store dir relative to the work tree (default: outside it).
    """
    import shutil

    base = {".gitignore": "__pycache__/\n.pytest_cache/\n", **base}
    work, base_sha = gitfx.make_worktree(root, base)
    for rel, text in final.items():
        path = work / rel
        if text is None:
            shutil.rmtree(path) if path.is_dir() else path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
    for name, src in tests.items():
        fx._wb(work / "fx_tests" / name, src)
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    ac = work / ac_rel if ac_rel else root / "ac_store"
    gitfx.write_ac_yaml(ac, AC_ID, [{"name": fn, "must_catch": list(wv)} for fn, wv in must_catch.items()])
    gitfx.commit_all(work, "the work")
    manifest = state / "alterations.json"
    manifest.write_text(json.dumps({"work_key": "tq-9101-rev", "entries": []}), encoding="utf-8")
    return fx.Sandbox(root, work, work / "fx_tests", ac, base_sha, manifest, b"", None,
                      state / "probe.jsonl", state / "runlog.jsonl", state / "release.marker")
