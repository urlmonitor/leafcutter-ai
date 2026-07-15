"""
MODULE: unit_tests/ac_store/test_pytest_ac_enforcement.py
GOAL: Verify the anti-silent-masking guarantees of the AC enforcement pytest
    plugin (scripts/ac_store/pytest_ac_enforcement.py).
BUSINESS CONTEXT: The plugin downgrades a failing test to XFAIL when the AC it
    covers is not "done" (a TDD convenience). A prior audit found this masking
    was SILENT and also (historically) risked hiding regressions in shipped
    work. These tests lock in three guarantees:
      (a) a failure covering a work_status: done AC is NEVER masked — it stays a
          real failure;
      (b) a masked (not-done AC) failure is announced LOUDLY and counted in the
          end-of-session summary — never a silent green;
      (c) AC_ENFORCE_STRICT=1 disables masking entirely — every AC-tagged
          failure surfaces as a real failure.

These are exercised by running a real subprocess pytest against a tiny temp
test file plus a synthetic AC store injected via LEAFCUTTER_AC_STORE_ROOT — the
exact invocation shape the plugin documents (-p scripts.ac_store.pytest_ac_enforcement).
This mirrors the "run the real code path" style used across the ac_store suite.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# The AC ids used by the synthetic store / temp tests.
_DONE_AC = "ZZ-DONE-1"
_TODO_AC = "ZZ-TODO-1"


def _write(path: Path, body: str) -> None:
    """Write *body* to *path*, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _make_ac_store(root: Path) -> None:
    """Create a two-AC synthetic store: one done, one todo."""
    store = root / "acceptance-criteria"
    _write(
        store / "done.yaml",
        f'id: "{_DONE_AC}"\nwork_status: done\ncomponent: x\n',
    )
    _write(
        store / "todo.yaml",
        f'id: "{_TODO_AC}"\nwork_status: todo\ncomponent: x\n',
    )


_TEST_FILE_BODY = f'''
def test_failure_for_done_ac():
    # covers: {_DONE_AC}
    assert False, "done-AC failure must NOT be masked"


def test_failure_for_todo_ac():
    # covers: {_TODO_AC}
    assert False, "todo-AC failure is masked by default"
'''


def _run_plugin_pytest(*, strict: bool) -> subprocess.CompletedProcess[str]:
    """Run a subprocess pytest with the plugin loaded against a temp test file.

    Args:
        strict: When True, sets AC_ENFORCE_STRICT=1 to disable masking.

    Returns:
        The CompletedProcess with combined stdout captured.
    """
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        store_root = tmp / "store"
        _make_ac_store(store_root)
        test_file = tmp / "test_probe_ac_enforcement.py"
        _write(test_file, _TEST_FILE_BODY)

        env = dict(os.environ)
        env["LEAFCUTTER_AC_STORE_ROOT"] = str(store_root / "acceptance-criteria")
        # Make scripts.ac_store importable regardless of caller cwd.
        env["PYTHONPATH"] = os.pathsep.join(
            [str(_REPO_ROOT), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
        if strict:
            env["AC_ENFORCE_STRICT"] = "1"
        else:
            env.pop("AC_ENFORCE_STRICT", None)

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "-p",
            "scripts.ac_store.pytest_ac_enforcement",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "-rA",
            "-v",
        ]
        return subprocess.run(
            cmd,
            cwd=str(_REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )


class TestDoneAcFailureNeverMasked(unittest.TestCase):
    """(a) A failure covering a work_status: done AC must stay a real failure."""

    def test_done_ac_failure_is_not_masked(self) -> None:
        proc = _run_plugin_pytest(strict=False)
        out = proc.stdout + proc.stderr

        # The suite must be RED because the done-AC test genuinely failed.
        self.assertNotEqual(
            proc.returncode,
            0,
            msg=f"Suite exited 0 — done-AC failure was masked.\n{out}",
        )
        # Exactly one real failure (the done-AC test); the todo-AC test is xfail.
        self.assertIn(
            "1 failed",
            out,
            msg=f"Expected exactly '1 failed' (the done AC).\n{out}",
        )
        self.assertIn(
            "test_failure_for_done_ac",
            out,
            msg=f"Done-AC test not reported as a failure.\n{out}",
        )
        # The masked summary must NOT list the done AC.
        self.assertNotIn(
            _DONE_AC,
            _masked_summary_block(out),
            msg=f"Done AC {_DONE_AC} appeared in the masked-failure summary.\n{out}",
        )


class TestMaskedFailureIsLoud(unittest.TestCase):
    """(b) A masked (not-done AC) failure must be announced loudly + counted."""

    def test_todo_ac_failure_is_masked_loudly(self) -> None:
        proc = _run_plugin_pytest(strict=False)
        out = proc.stdout + proc.stderr

        # It IS downgraded to xfail (still masked by default).
        self.assertIn(
            "1 xfailed",
            out,
            msg=f"Todo-AC failure was not downgraded to xfail.\n{out}",
        )
        # Per-test loud line during the run.
        self.assertIn(
            "AC-ENFORCEMENT [MASKED FAILURE]",
            out,
            msg=f"No per-test masked-failure line emitted.\n{out}",
        )
        # End-of-session summary naming the count AND the AC id.
        self.assertIn(
            "AC-ENFORCEMENT SUMMARY",
            out,
            msg=f"No end-of-session masked-failure summary emitted.\n{out}",
        )
        self.assertIn(
            "1 AC-tagged failure(s) were masked",
            out,
            msg=f"Summary did not report the masked count.\n{out}",
        )
        self.assertIn(
            _TODO_AC,
            out,
            msg=f"Summary did not name the masked AC id {_TODO_AC}.\n{out}",
        )


class TestStrictModeDisablesMasking(unittest.TestCase):
    """(c) AC_ENFORCE_STRICT=1 disables masking — every failure is real."""

    def test_strict_mode_surfaces_all_failures(self) -> None:
        proc = _run_plugin_pytest(strict=True)
        out = proc.stdout + proc.stderr

        self.assertNotEqual(
            proc.returncode,
            0,
            msg=f"Strict mode exited 0 — failures were still masked.\n{out}",
        )
        # BOTH tests are real failures now; nothing is downgraded to xfail.
        self.assertIn(
            "2 failed",
            out,
            msg=f"Strict mode did not surface both failures.\n{out}",
        )
        self.assertNotIn(
            "xfailed",
            out,
            msg=f"Strict mode still produced an xfail outcome.\n{out}",
        )
        # No masked-failure summary should be printed when masking is off.
        self.assertNotIn(
            "AC-ENFORCEMENT SUMMARY",
            out,
            msg=f"Masked-failure summary printed despite strict mode.\n{out}",
        )
        # The strict notice should be visible for the not-done AC.
        self.assertIn(
            "AC-ENFORCEMENT [STRICT]",
            out,
            msg=f"No strict-mode notice emitted for the not-done AC.\n{out}",
        )


def _masked_summary_block(output: str) -> str:
    """Return the text after the masked-failure summary header, or ''.

    Isolates the summary region so a test can assert an AC id is absent from
    the *summary* specifically (the id may legitimately appear elsewhere in
    the run output, e.g. in a covers-tag echo).
    """
    marker = "AC-ENFORCEMENT SUMMARY"
    idx = output.find(marker)
    if idx == -1:
        return ""
    return output[idx:]


if __name__ == "__main__":
    unittest.main()
