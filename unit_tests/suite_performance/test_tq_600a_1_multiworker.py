"""
Cross-worker (`-n 2`) tests for TQ-600a-1 — "The reference layout is
produced once for the whole run, and shared across workers rather than
rebuilt by each."

STRUCTURAL SPLIT NOTE (GE-127a-1, 2026-09-22): these two tests
(originally tests 3 and 4 of ``test_tq_600a_1.py``) were extracted into
this sibling file because the original single-file
``TestTQ600a1SharedReferenceLayout`` class tripped the check-file-size
pre-commit hook at 449 counted lines against the 400-line limit. Both
tests here exercise real pytest-xdist multi-worker (`-n 2`) behavior — a
natural, cohesive pair distinct from the single-worker tests that remain
in ``test_tq_600a_1.py``. This is a pure structural refactor: no test
name, assertion, `# covers:`/`# angle:` tag, or docstring content changed
or was lost in the move.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-1.yaml
(test_spec + test_rationale). See ``test_tq_600a_1.py``'s own module
docstring for the full "ASSUMED PRODUCTION CONTRACT" both files' tests are
pinned to (plugin module, registration surface, fixture, low-level
function, execution signal, and completeness marker) — not repeated here
to avoid duplicating load-bearing documentation across two files.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ._test_helpers import (
    _EXECUTION_LOG_ENV_VAR,
    _REAL_DEPLOY_SUBPROCESS_TIMEOUT_S,
    _WORKTREE_ROOT,
    _read_jsonl,
    _write_consumer_test,
)


class TestTQ600a1SharedReferenceLayoutMultiWorker(unittest.TestCase):
    """RED test stubs for TQ-600a-1's cross-worker (`-n 2`) clauses. See
    test_tq_600a_1.py's module docstring for the assumed production
    contract these tests are pinned to."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    # ------------------------------------------------------------------
    # Test 3 — criterion. NAMED MUTATION: plain session-scoped fixture with
    # no cross-process lock -> observed count becomes the worker count.
    # ------------------------------------------------------------------
    def test_tq600a_1_a_run_spread_across_several_workers_still_executes_exactly_one_deploy_MANUAL(
        self,
    ):
        # covers: TQ-600a-1
        # angle: criterion
        """
        With more than one worker, the number of `build.py --target-dir`
        subprocesses observed ACROSS ALL WORKERS is exactly one — counted
        by the harness itself (the JSONL execution log), not read from
        anything the run reports.

        NAMED MUTATION this test alone catches: a plain
        `@pytest.fixture(scope="session")` with no cross-process lock. Under
        that mutation each of the 2 xdist workers produces its own layout,
        so the observed deploy count becomes 2 while
        test_tq600a_1_a_selection_of_read_only_consumers_deploys_the_package_once
        (single-worker) stays green at 1. Only a real multi-worker
        subprocess run can distinguish "once per run" from "once per
        worker" — this is the whole reason this descriptor exists (see the
        AC's test_rationale).

        REQUIRES pytest-xdist (the `-n` flag). Not currently a declared
        dependency of this repo (checked requirements-dev.txt — absent) —
        see the test-writer sign-off comment for the flagged dependency gap.

        SLOW (real deploy(s)) — _MANUAL.
        """
        children_dir = self.tmp_path / "children"
        # TQ-600a-5 note: these consumers only ever read the deployed layout
        # and never mutate it, so they explicitly declare
        # @pytest.mark.shared_layout_reader. Before TQ-600a-5's marker-based
        # routing landed, EVERY consumer -- declared or not -- was handed the
        # one shared layout by default; TQ-600a-5 changed that default so an
        # UNDECLARED consumer now correctly receives its own private copy
        # instead, which would silently break this test's "exactly one
        # deploy across all workers" assertion below unless these consumers
        # declare themselves.
        consumer_body = """
            import pytest
            from pathlib import Path

            @pytest.mark.shared_layout_reader
            def test_consumer_{n}(shared_reference_layout):
                assert Path(shared_reference_layout).exists()
        """
        for n in range(4):
            _write_consumer_test(
                children_dir, f"test_consumer_{n}.py", consumer_body.format(n=n)
            )

        log_path = self.tmp_path / "execution_log.jsonl"
        env = dict(os.environ)
        env[_EXECUTION_LOG_ENV_VAR] = str(log_path)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(children_dir),
                "-p",
                "scripts.suite_performance.pytest_shared_reference_layout",
                "-n",
                "2",
                "-q",
            ],
            cwd=str(_WORKTREE_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=_REAL_DEPLOY_SUBPROCESS_TIMEOUT_S,
        )
        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "child multi-worker session failed (this may indicate "
                "pytest-xdist is not installed — see sign-off comment for "
                "the flagged dependency gap):\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            ),
        )
        entries = _read_jsonl(log_path)
        deploy_events = [e for e in entries if e.get("event") == "deploy_executed"]
        self.assertEqual(
            1,
            len(deploy_events),
            msg=(
                "expected exactly one real deploy across ALL workers, "
                f"observed: {deploy_events} (a count > 1 here means the "
                "fixture is only worker-scoped, not run-scoped)"
            ),
        )

    # ------------------------------------------------------------------
    # Test 4 — boundary. NAMED MUTATION: derive run-scoped dir from each
    # worker's own base tempdir instead of the workers' common base.
    # ------------------------------------------------------------------
    def test_tq600a_1_consumers_on_different_workers_receive_the_identical_root_path_MANUAL(
        self,
    ):
        # covers: TQ-600a-1
        # angle: boundary
        """
        Two consumers pinned to different workers report root paths that
        are the identical string.

        NAMED MUTATION this test alone catches: deriving the run-scoped
        directory from each worker's own base temporary directory (e.g.
        `tmp_path_factory.getbasetemp()` without `.parent`) rather than the
        workers' COMMON base. Under that mutation every worker gets a valid,
        EXISTING, but DIFFERENT root — test 3 above (which only counts
        deploys, not root identity) would still see xdist collapse work
        onto whichever worker acquires a lock first in some
        implementations, so it is this identity check, not the count
        check, that isolates the "common base tempdir" requirement.

        REQUIRES pytest-xdist. SLOW (real deploy(s)) — _MANUAL.
        """
        children_dir = self.tmp_path / "children"
        result_dir = self.tmp_path / "results"
        result_dir.mkdir(parents=True, exist_ok=True)

        # TQ-600a-5 note: these consumers only ever read the deployed layout
        # and never mutate it, so they explicitly declare
        # @pytest.mark.shared_layout_reader. Before TQ-600a-5's marker-based
        # routing landed, EVERY consumer -- declared or not -- was handed the
        # one shared layout by default; TQ-600a-5 changed that default so an
        # UNDECLARED consumer now correctly receives its own private copy
        # instead, which would silently break this test's "identical root
        # across workers" assertion below unless these consumers declare
        # themselves.
        consumer_body = """
            import os
            import pytest
            from pathlib import Path

            @pytest.mark.shared_layout_reader
            def test_reports_root(shared_reference_layout):
                worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
                out = Path(os.environ["RESULT_DIR"]) / f"root_{worker}.txt"
                out.write_text(str(shared_reference_layout))
        """
        # Two separate files so each is scheduled to a different worker
        # under `-n 2 --dist loadscope`-equivalent default (loadscheduling
        # still spreads distinct test files/items across the 2 workers).
        for n in range(2):
            _write_consumer_test(
                children_dir, f"test_reports_root_{n}.py", consumer_body
            )

        env = dict(os.environ)
        env["RESULT_DIR"] = str(result_dir)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(children_dir),
                "-p",
                "scripts.suite_performance.pytest_shared_reference_layout",
                "-n",
                "2",
                "-q",
            ],
            cwd=str(_WORKTREE_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=_REAL_DEPLOY_SUBPROCESS_TIMEOUT_S,
        )
        self.assertEqual(
            0,
            result.returncode,
            msg=f"child multi-worker session failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        root_files = sorted(result_dir.glob("root_*.txt"))
        self.assertGreaterEqual(
            len(root_files),
            2,
            msg=f"expected reports from >=2 distinct workers, found: {root_files}",
        )
        roots = {f.read_text(encoding="utf-8") for f in root_files}
        self.assertEqual(
            1,
            len(roots),
            msg=f"workers received DIFFERENT root paths (expected identical): {roots}",
        )


if __name__ == "__main__":
    unittest.main()
