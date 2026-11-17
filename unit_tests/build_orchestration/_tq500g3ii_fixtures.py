"""
MODULE: unit_tests/build_orchestration/_tq500g3ii_fixtures.py
GOAL: Shared REAL scratch git repos and CLI drivers for the TQ-500g-3-ii tests (the base-vs-now pytest
    runs inside consumer_sweep.py check, reached through wrong_version_gate.py finish).
BUSINESS CONTEXT: "Passed before the work, skipped / expected to fail / gone now" is a runtime fact, so
    every fixture is a real git repo whose base commit holds real passing tests; the work is an
    UNCOMMITTED edit on top (routes pass --base-ref HEAD). Lists go through the real record step; the
    edits to existing tests are recorded as strengthened (or removed) so TQ-500g-3-i passes and only
    TQ-500g-3-ii's own outcome decides.
ARCHITECTURE: Not a test file. Builds on _tq500g3i_fixtures / _tq500g3i_review_fixtures. Today the
    check prints weakened == [] and passed true for these repos, so every test is red on an assertion.
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.build_orchestration._tq500g3i_fixtures as fx
import unit_tests.build_orchestration._tq500g3i_review_fixtures as rfx

REFRESH, RETRY, EXPORT, LEGACY, PARAM = (f"tests/test_{n}.py" for n in ("refresh", "retry", "export", "legacy", "param"))
A, B, C, D, E = ("test_refresh_skips_when_not_due", "test_retry_caps_at_five", "test_export_header",
                 "test_refresh_runs_when_due", "test_legacy_cron_refresh")
E_NOTE = "the requirement removes the legacy cron refresh this test covered"
SKIP_MARK = "@pytest.mark.skip(reason='later')\n"
XFAIL_MARK = "@pytest.mark.xfail(reason='flaky')\n"

HEAD = "import pytest\n\n\n"  # every base file imports pytest, so a mark is no module-level edit
BASE = {
    REFRESH: HEAD + f"def {A}():\n    assert 1 + 1 == 2\n\n\ndef {D}():\n    assert 2 + 2 == 4\n",
    RETRY: HEAD + f"def {B}():\n    assert 5 == 5\n",
    EXPORT: HEAD + f"def {C}():\n    assert 'h' == 'h'\n\n\ndef test_export_body():\n    assert 'b' == 'b'\n",
    LEGACY: HEAD + f"def {E}():\n    assert 'cron' == 'cron'\n\n\ndef test_legacy_noop():\n    assert 0 == 0\n",
}


def sub(text: str, old: str, new: str) -> str:
    assert old in text, f"{old!r} is not in the text"
    return text.replace(old, new, 1)


def skip_a(text: str) -> str:
    """The refresh file with A marked to be skipped."""
    return sub(text, f"def {A}", f"{SKIP_MARK}def {A}")


def strengthen_d(text: str) -> str:
    return sub(text, "assert 2 + 2 == 4", "assert 2 + 2 == 4\n    assert 2 * 2 == 4")


def xfail_b(text: str) -> str:
    """B marked to be expected to fail (and made to fail, so it reports XFAIL)."""
    return sub(sub(text, f"def {B}", f"{XFAIL_MARK}def {B}"), "assert 5 == 5", "assert 5 == 6")


def drop_c(text: str) -> str:
    return sub(text, f"def {C}():\n    assert 'h' == 'h'\n\n\n", "")


def drop_e(text: str) -> str:
    return sub(text, f"def {E}():\n    assert 'cron' == 'cron'\n\n\n", "")


def scenario(tmp: Path, work: dict, base: dict | None = None) -> fx.Repo:
    """A repo with *base* committed (default BASE) and *work* ({path: fn(text) -> text}) applied uncommitted."""
    repo = fx.build(tmp, edits=(), add_new_file=False)
    files = base or BASE
    for rel, text in files.items():
        fx.write(repo.path(rel), text)
    fx.gitfx.commit_all(repo.root, "base with the existing passing tests")
    for rel, change in work.items():
        fx.write(repo.path(rel), change(fx.read(repo.path(rel))))
    return repo


def listed(file: str, test: str, status: str = "strengthened", note: str = "swept the consumers") -> dict:
    return fx.entry(file, test, status, note)


def run_check(repo: fx.Repo, env_extra: dict | None = None):
    """``consumer_sweep.py check`` with extra environment; return ``(proc, JSON)``."""
    return rfx.run_cli(repo, rfx.check_args(repo), env_extra=env_extra)


def whats(out: dict) -> dict[str, str]:
    """``{test: what}`` of the weakened items."""
    return {i["test"]: i["what"] for i in out["weakened"]}


def snapshot(repo: fx.Repo) -> dict[str, bytes]:
    """Every working-tree file outside .git, by relative path."""
    return {p.relative_to(repo.root).as_posix(): p.read_bytes()
            for p in sorted(repo.root.rglob("*")) if p.is_file() and ".git" not in p.relative_to(repo.root).parts}


def git_text(repo: fx.Repo, *args: str) -> str:
    return fx.gitfx.run_git(list(args), cwd=repo.root)
