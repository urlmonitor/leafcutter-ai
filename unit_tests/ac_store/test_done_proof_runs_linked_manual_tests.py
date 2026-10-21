"""The done-proof oracle runs an AC's linked ``_MANUAL`` tests (ticket 19, KI-ACS-20261013).

Type: integration. Angles: regression, real_artifact, negative_control.

Each test builds a temp AC store and a temp test tree whose ``pytest.ini``
carries the repository's own manual-deselect setup (the
``pytest_manual_deselect`` plugin plus ``-m "not manual"`` in addopts), so the
default deselection really happens. The real ``verify_done_eligible`` is then
driven against that tree.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts" / "ac_store"))

from done_proof import verify_done_eligible  # noqa: E402

_AC_ID = "ZZ-MANUAL-PROOF"
_PLUGIN = _REPO / "scripts" / "suite_performance" / "pytest_manual_deselect.py"
_PYTEST_INI = textwrap.dedent('''\
    [pytest]
    strict_markers = true
    addopts = -m "not manual and not timing_ratio" -p scripts.suite_performance.pytest_manual_deselect
    markers =
        manual: auto-applied to every test whose name ends in _MANUAL
        timing_ratio: asserts a wall-clock ratio
    pythonpath = .
    ''')


def _fixture(root: Path, passing: bool) -> tuple[Path, Path, Path]:
    """Write an AC linking only one ``_MANUAL`` test, plus an unlinked manual sibling.

    Returns ``(ac_root, test_root, sentinel)``; *sentinel* is written only if
    the UNLINKED manual sibling runs.
    """
    ac_root, test_root = root / "acs", root / "tests"
    ac_root.mkdir()
    test_root.mkdir()
    plugin_dir = root / "scripts" / "suite_performance"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy(_PLUGIN, plugin_dir / _PLUGIN.name)
    (root / "pytest.ini").write_text(_PYTEST_INI, encoding="utf-8")
    (ac_root / "proof.yaml").write_text(yaml.safe_dump({
        "id": _AC_ID, "status": "active", "work_status": "done", "covered_by": []}),
        encoding="utf-8")
    sentinel = root / "unlinked_manual_ran.txt"
    (test_root / "test_manual_proof.py").write_text(textwrap.dedent(f'''\
        import unittest
        from pathlib import Path

        class ManualProof(unittest.TestCase):
            # covers: {_AC_ID}
            # angle: criterion
            def test_slow_proof_MANUAL(self):
                self.assertTrue({passing!r})

            def test_unlinked_sibling_MANUAL(self):
                Path({str(sentinel)!r}).write_text("ran", encoding="utf-8")
        '''), encoding="utf-8")
    return ac_root, test_root, sentinel


class TestDoneProofRunsLinkedManualTests(unittest.TestCase):
    """A linked ``_MANUAL`` test is run by the oracle and judged on its real outcome."""

    # covers: BO-2500a-3
    # angle: regression
    def test_linked_manual_test_is_run_and_counts_when_it_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            acs, tests, sentinel = _fixture(Path(temporary), passing=True)
            verdict = verify_done_eligible(_AC_ID, ac_root=acs, test_root=tests)
            unlinked_ran = sentinel.exists()
        self.assertTrue(verdict["eligible"], verdict)
        self.assertTrue(
            any(node.endswith("::test_slow_proof_MANUAL") for node in verdict["passing_tests"]),
            verdict,
        )
        self.assertFalse(unlinked_ran, "only the AC's linked node ids may run")

    # covers: BO-2500a-2
    # angle: negative_control
    def test_failing_linked_manual_test_is_refused_with_its_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            acs, tests, _ = _fixture(Path(temporary), passing=False)
            verdict = verify_done_eligible(_AC_ID, ac_root=acs, test_root=tests)
        self.assertFalse(verdict["eligible"], verdict)
        self.assertIn("linked test failed:", verdict["reason"])
        self.assertIn("test_slow_proof_MANUAL", verdict["reason"])
        self.assertNotIn("not run", verdict["reason"])

    # covers: TQ-600a-13
    # angle: regression
    def test_default_run_still_deselects_manual_tests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, tests, sentinel = _fixture(root, passing=True)
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-v", "--no-header", str(tests)],
                capture_output=True, text=True, cwd=root, timeout=120, check=False,
            )
            unlinked_ran = sentinel.exists()
        self.assertIn("2 deselected", proc.stdout, proc.stdout + proc.stderr)
        self.assertNotIn("test_slow_proof_MANUAL PASSED", proc.stdout)
        self.assertFalse(unlinked_ran)


if __name__ == "__main__":
    unittest.main()
