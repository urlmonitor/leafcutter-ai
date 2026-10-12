"""
Tests for TQ-600a-1-i — "Nobody pays for the shared layout when nobody
asked for it."

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/
TQ-600a-1-i.yaml (test_spec + it_requirements). The ticket's ## Test
Requirements table is derived from that YAML; where the two differ, the
YAML wins.

SEQUENCING NOTE (test-writer, 2026-09-28): this AC's `amended_by` history
records a deliberate sequencing gap left by the business-analyst and
it-po passes on 2026-09-28. The AC's criteria name TWO reported-count
descriptors:

  - test_tq600a_1_i_a_selection_with_no_consumer_reports_zero_deploys
  - test_tq600a_1_i_widening_by_one_consumer_takes_the_count_from_zero_to_one

Both read the run's REPORTED deploy figure. That reporting surface does
not exist yet: TQ-600a-6 (two waves out) declares
`pytest_shared_reference_layout.py` at `modifies` in its own AC and is the
one that will instrument the reported count. Building a throwaway emitter
here to satisfy these two descriptors would duplicate work TQ-600a-6 is
explicitly scoped to do, and risks a shape mismatch between this ticket's
guess and TQ-600a-6's real contract. Per supervisor instruction, both
descriptors are DEFERRED to TQ-600a-6's own build — this is a pre-
authorized, expected deferral, not a dropped requirement. See this
ticket's `## Comments` sign-off entry and `## Implementation Notes` for
the same note recorded on the ticket itself.

The remaining three descriptors do NOT depend on that reporting surface:
they observe production via the EXECUTION LOG
(`emit_execution_signal()` / `EXECUTION_LOG_ENV_VAR` in
`_shared_layout_coordination.py`), which TQ-600a-1 already implemented
and merged. All three are written below as real, runnable tests.

======================================================================
PRODUCTION CONTRACT THIS FILE PINS (already implemented and merged under
TQ-600a-1, PR #941 — this ticket's coder phase is expected to be a no-op
or near-no-op; these tests PROTECT existing behaviour rather than await
new production code):

1. `scripts.suite_performance.pytest_shared_reference_layout.
   shared_reference_layout` is a `scope="session"` fixture that is
   REQUEST-SCOPED, not autouse: it is invoked only when a test declares
   it as a parameter. A test that never names it as a parameter must
   never trigger `get_or_produce_shared_layout()`.
2. Laziness holds PER WORKER under pytest-xdist, not just per run: a
   worker OS process to which no consuming test is ever scheduled must
   never call `get_or_produce_shared_layout()` itself — production must
   not be triggered from a worker-startup hook that runs unconditionally
   for every worker.
3. Every time (and only when) a real `python <target>/scripts/build.py
   --target-dir <target>` subprocess actually executes, production
   appends one JSON line to the file named by
   `LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG` (see
   `_shared_layout_coordination.emit_execution_signal`), tagged with the
   emitting worker's id (`PYTEST_XDIST_WORKER`, or `"master"` outside
   xdist). This is the independent observation instrument every test
   below uses — none of them read anything the run reports about itself.

Reachability entry-point resolution (BP-1100g-2): this AC's test_spec
named no explicit entry point. Per Step 0 of the resolution procedure, no
entry point was named upstream, so Step 1 was walked directly: this is a
pytest plugin/fixture, not a CLI/hook/slash-command/workflow-step, so its
only real caller is a real pytest session loading the project's actual,
un-augmented registration surface (`pytest.ini`'s `-p` addopts entry for
`scripts.suite_performance.pytest_shared_reference_layout`, confirmed
present by reading `pytest.ini` directly). Recorded as `result: resolved`
in this ticket's completion_manifest.
======================================================================
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
    _SUITE_PERF_DIR,
    _WORKTREE_ROOT,
    _read_jsonl,
    _rmtree_if_exists,
    _write_consumer_test,
)

# Idle-worker count for the per-worker laziness test. More idle workers
# raise the odds of catching the NAMED MUTATION (production triggered
# from a worker-startup hook that fires on every worker): under that
# mutation, whichever worker wins the cross-process lock race emits the
# deploy signal, and that race is decided by OS scheduling at worker
# startup, before any test item is assigned. With 1 real consumer against
# N idle workers, an idle worker winning the race (and thereby exposing
# the mutation) has probability N / (N + 1). N=3 (four total workers)
# trades a modest amount of worker-startup overhead for a 3-in-4 chance
# of catching the mutation in a single run, consistent with the
# inherent-xdist-raciness caveat already documented in the sibling
# TQ-600a-1 multi-worker tests.
_IDLE_WORKER_COUNT = 3
_XDIST_WORKER_TOTAL = str(_IDLE_WORKER_COUNT + 1)


class TestTQ600a1iSharedLayoutLaziness(unittest.TestCase):
    """Real test stubs for TQ-600a-1-i. See module docstring for the
    production contract these tests pin, and for the deferral note on
    the two reported-count descriptors this file deliberately omits."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    # ------------------------------------------------------------------
    # Descriptor 3 — failure. NAMED MUTATION: make the fixture
    # session-autouse (eager).
    # ------------------------------------------------------------------
    def test_tq600a_1_i_no_deploy_subprocess_runs_for_the_zero_consumer_selection(
        self,
    ):
        # covers: TQ-600a-1-i
        # angle: failure
        """
        A child pytest session over tests that NEVER request the
        `shared_reference_layout` fixture as a parameter executes zero
        real deploy subprocesses, observed independently of anything the
        run reports about itself (the JSONL execution log, not a report
        figure — the report figure is TQ-600a-6's, deferred per the
        module docstring).

        NAMED MUTATION this test alone catches: make the fixture
        `autouse=True`. Under that mutation, pytest invokes the fixture
        function once per session BEFORE any test body runs, regardless
        of whether any test names it as a parameter — so production
        fires even though not one test below ever asks for it. A
        report-only assertion ("the reported count is 0") could still
        pass under this mutation if the emitter only increments on an
        explicit fixture *request* rather than on invocation; observing
        the execution log directly closes that gap.

        Fast: no real deploy occurs under correct (non-autouse,
        request-scoped) production, so this is not a _MANUAL test.
        """
        children_dir = self.tmp_path / "children"
        never_asks_body = """
            def test_never_asks_{n}():
                assert 1 + 1 == 2
        """
        for n in range(3):
            _write_consumer_test(
                children_dir, f"test_never_asks_{n}.py", never_asks_body.format(n=n)
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
            msg=f"child session failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        entries = _read_jsonl(log_path)
        deploy_events = [e for e in entries if e.get("event") == "deploy_executed"]
        self.assertEqual(
            0,
            len(deploy_events),
            msg=(
                "a selection with no consumer must execute zero real deploy "
                f"subprocesses; observed: {deploy_events}"
            ),
        )

    # ------------------------------------------------------------------
    # Descriptor 4 — boundary. NAMED MUTATION: create the layout in a
    # worker-startup hook.
    # ------------------------------------------------------------------
    def test_tq600a_1_i_a_worker_with_no_scheduled_consumer_produces_nothing_MANUAL(
        self,
    ):
        # covers: TQ-600a-1-i
        # angle: boundary
        """
        Under pytest-xdist with more than one worker, and exactly ONE
        consuming test in the whole session, the worker(s) that never
        receive that test item never emit a deploy signal — even though
        every worker OS process starts up.

        NAMED MUTATION this test alone catches: produce the layout from
        a worker-startup hook (e.g. `pytest_configure`) that fires
        unconditionally on every worker, before test items are
        distributed. Under correct (lazy, request-triggered) production,
        `get_or_produce_shared_layout()` is only ever called from inside
        the fixture, which is only ever invoked by the one worker that
        actually runs the consuming test — so the "worker" field on every
        emitted deploy signal must equal that worker's id, never an idle
        one's. Under the mutation, every worker's startup hook races for
        the cross-process lock at boot, before assignment is even known;
        an idle worker winning that race is directly observable as its id
        appearing on a deploy signal. See the module-level
        `_IDLE_WORKER_COUNT` comment for why this uses more than the
        minimum two workers, and for the acknowledged residual
        (inherent-xdist-race) chance of a false negative in a single run.

        REQUIRES pytest-xdist (`-n`) — confirmed a declared dependency of
        this repo (`requirements-dev.txt: pytest-xdist>=3.5`) and
        importable in this environment.

        SLOW (real ~60-90s deploy, paid by exactly one worker) — _MANUAL.
        """
        children_dir = self.tmp_path / "children"
        result_dir = self.tmp_path / "results"
        result_dir.mkdir(parents=True, exist_ok=True)

        consumer_body = """
            import os
            from pathlib import Path

            def test_the_one_consumer(shared_reference_layout):
                assert Path(shared_reference_layout).exists()
                worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
                out = Path(os.environ["RESULT_DIR"]) / "consumer_worker.txt"
                out.write_text(worker, encoding="utf-8")
        """
        _write_consumer_test(children_dir, "test_the_one_consumer.py", consumer_body)

        log_path = self.tmp_path / "execution_log.jsonl"
        env = dict(os.environ)
        env[_EXECUTION_LOG_ENV_VAR] = str(log_path)
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
                _XDIST_WORKER_TOTAL,
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

        consumer_worker_file = result_dir / "consumer_worker.txt"
        self.assertTrue(
            consumer_worker_file.exists(),
            msg="the one consuming test never ran or never reported its worker id",
        )
        consumer_worker = consumer_worker_file.read_text(encoding="utf-8").strip()

        entries = _read_jsonl(log_path)
        deploy_events = [e for e in entries if e.get("event") == "deploy_executed"]
        self.assertEqual(
            1,
            len(deploy_events),
            msg=f"expected exactly one real deploy across all workers, observed: {deploy_events}",
        )
        deploying_workers = {e.get("worker") for e in deploy_events}
        self.assertEqual(
            {consumer_worker},
            deploying_workers,
            msg=(
                "a worker with no scheduled consumer produced a layout: "
                f"deploying worker(s) {deploying_workers} != the one "
                f"consuming worker {consumer_worker!r} (idle workers must "
                "never enter production)"
            ),
        )

    # ------------------------------------------------------------------
    # Descriptor 5 — reachability (REQUIRED).
    # ------------------------------------------------------------------
    def test_tq_600a_1_i_reachable_from_entry_point_MANUAL(self):
        # covers: TQ-600a-1-i
        # angle: reachability
        """
        REQUIRED reachability test (BP-1100g-2). Invokes the REAL,
        un-augmented pytest entry point — no explicit `-p` override,
        relying entirely on `pytest.ini`'s whole-suite `-p` addopts
        registration — over a session mixing two tests that never
        request the fixture with exactly one that does.

        This is deliberately distinct from TQ-600a-1's own reachability
        test (which only proved the positive "at least one consumer"
        case reaches the real registration surface): it proves the
        SAME real, un-augmented entry point also holds this AC's
        constraint — that the non-consuming tests trigger no production
        at all, while the one consumer's request is genuinely served,
        AND its result is consumed in control flow (a real file read
        from the produced root), not merely imported and asserted
        importable.

        SLOW (one real deploy, via the real un-augmented registration
        path) — _MANUAL.
        """
        # Must live INSIDE the worktree, not under a tempfile.TemporaryDirectory
        # (which lands in /tmp): pytest's rootdir/inifile discovery walks up
        # from the given path's own ancestry, not from `cwd`, so a /tmp path
        # would never find this repo's pytest.ini and its `-p` addopts entry
        # -- silently defeating the very "real, un-augmented registration"
        # this test exists to prove. Mirrors test_tq_600a_1.py's own
        # reachability test, which uses `_SUITE_PERF_DIR` for the same reason.
        children_dir = _SUITE_PERF_DIR / "_reachability_children_tq600a1i"
        self.addCleanup(_rmtree_if_exists, children_dir)
        never_asks_body = """
            def test_never_asks_{n}():
                assert True
        """
        for n in range(2):
            _write_consumer_test(
                children_dir, f"test_never_asks_{n}.py", never_asks_body.format(n=n)
            )
        consumer_body = """
            from pathlib import Path

            def test_consumes_via_real_entry_point(shared_reference_layout):
                root = Path(shared_reference_layout)
                manifest = root / ".build_manifest.json"
                assert manifest.exists(), "layout incomplete or fixture is a stub"
                assert len(manifest.read_text(encoding="utf-8")) > 0
        """
        _write_consumer_test(
            children_dir, "test_the_one_real_consumer.py", consumer_body
        )

        log_path = self.tmp_path / "execution_log.jsonl"
        env = dict(os.environ)
        env[_EXECUTION_LOG_ENV_VAR] = str(log_path)

        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(children_dir), "-q"],
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
                "real, un-augmented pytest entry point could not reach the "
                "shared_reference_layout fixture — the registration surface "
                "is not whole-suite-loaded:\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            ),
        )
        entries = _read_jsonl(log_path)
        deploy_events = [e for e in entries if e.get("event") == "deploy_executed"]
        self.assertEqual(
            1,
            len(deploy_events),
            msg=(
                "expected exactly one real deploy triggered by the one "
                f"consuming test via the real entry point, observed: {deploy_events}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
