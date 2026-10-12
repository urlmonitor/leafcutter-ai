"""
Tests for TQ-600a-1 — "The reference layout is produced once for the whole
run, and shared across workers rather than rebuilt by each."

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-1.yaml
(test_spec + test_rationale). The ticket's ## Test Requirements table is
derived from that YAML; where the two differ, the YAML wins.

STRUCTURAL SPLIT NOTE (GE-127a-1, 2026-09-22): this file originally held
all 7 tests for this AC in one class; the check-file-size pre-commit hook
blocked the commit at 449 counted lines against the 400-line limit. The
two `-n 2` cross-worker tests (originally tests 3 and 4) were extracted to
the sibling file ``test_tq_600a_1_multiworker.py`` — a natural, cohesive
pair, since both exercise real multi-worker `-n 2` behavior. Shared
helpers (`_read_jsonl`, `_write_consumer_test`, `_rmtree_if_exists`) and
constants moved to `_test_helpers.py`, imported by both files. This is a
pure structural refactor: no test name, assertion, `# covers:`/`# angle:`
tag, or docstring content changed or was lost — see the sibling file for
tests 3 and 4's own docstrings (also unchanged).

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds
this to make the tests below green — see Source-of-Truth Discipline
Rule 5: expand the test, don't shrink production, and the inverse holds
at authoring time too: these tests ARE the contract until a documented,
justified reason changes them).

No such module exists yet. Every test below is expected to fail at
collection (ModuleNotFoundError / fixture 'shared_reference_layout' not
found) until python-coder implements it. That is the correct RED state.

1. Plugin module: ``scripts/suite_performance/pytest_shared_reference_layout.py``
   (new package; needs ``scripts/suite_performance/__init__.py`` to mirror
   ``scripts/ac_store/__init__.py`` — ``scripts/`` itself has no
   ``__init__.py`` and is a PEP 420 namespace package, per the existing
   per-directory conftest.py comments in this repo).

2. REGISTRATION SURFACE — the load-bearing one. This repo already has a
   precedent for "a surface the whole run loads": pytest.ini's addopts
   line already reads
       -p scripts.ac_store.pytest_ac_enforcement
   A whole-suite-loaded fixture must be registered the same way — via
   pytest.ini's ``-p`` addopts (or a root conftest.py, if that is what
   python-coder chooses) — NEVER via a per-directory conftest.py, because
   this repo's only existing conftest files
   (unit_tests/{agents,portability,hooks,commit_guardian}/conftest.py) are
   verified to be nothing but sys.path shims, invisible outside their own
   directory. See the "Ticket-scope note" in the sign-off comment for why
   this matters for this ticket's files_touched list.

   Test 7 (test_tq_600a_1_reachable_from_entry_point) is deliberately
   designed to FAIL if the fixture is registered somewhere less than
   suite-wide (e.g. only in unit_tests/portability/conftest.py): it places
   its consumer test in unit_tests/suite_performance/ — a directory with no
   conftest.py of its own — and invokes pytest with NO explicit ``-p``
   override, relying entirely on whatever real, whole-suite registration
   surface python-coder actually wires up.

3. FIXTURE — a pytest fixture named ``shared_reference_layout`` (any scope
   name internally, but behaviourally "produced at most once per run,
   shared across workers") that returns a ``pathlib.Path`` to the deployed
   package root (i.e. the directory ``python scripts/build.py --target-dir
   <that path>`` was run against).

4. LOW-LEVEL FUNCTION — ``get_or_produce_shared_layout() -> pathlib.Path``,
   the cross-process-safe function the fixture wraps. Exposed directly so
   test_tq600a_1_a_cached_layout_requested_many_times_executes_only_one_deploy
   (a `type: unit` test per the AC's test_spec — no subprocess pytest
   session needed) can call it directly in-process and count real
   subprocess launches via a monkeypatch of ``subprocess.run``.

5. EXECUTION SIGNAL — every time (and only when) a real
   ``python scripts/build.py --target-dir <path>`` subprocess is actually
   executed, the production code must append one JSON line to the file
   named by the environment variable
       LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG
   if that variable is set (no-op if unset, so this instrumentation is
   invisible to a real run). One line per real execution:
       {"event": "deploy_executed", "target_dir": "<path>",
        "pid": <int>, "worker": "<PYTEST_XDIST_WORKER or 'master'>"}
   This is how the harness in tests 1, 3, 4, and 7 counts real deploys
   independently of anything the run reports about itself (per Implementation
   Note "THE DEPLOY SIGNAL FIRES ON EXECUTION, NOT ON HANDOUT" and per
   instruction point 4 in this ticket's dispatch: "the harness must
   independently count real build.py --target-dir subprocess invocations").

6. COMPLETENESS MARKER — ``.build_manifest.json`` at the layout root, written
   by ``_write_and_verify_manifest`` near the end of ``scripts/build.py``'s
   ``main()`` (confirmed by reading scripts/build.py: it runs after
   ``_run_phases`` completes and before the later stale-cleanup / shim
   steps). A layout root handed out before ``.build_manifest.json`` exists
   is a layout that is not yet complete.

Reachability entry-point resolution (BP-1100g-2): this AC's test_spec named
no explicit entry point for the reachability test, so it was resolved here.
This is a pytest plugin/fixture, not a CLI/hook/slash-command/workflow-step,
so its only real caller is a real pytest session that loads the project's
actual, un-augmented registration surface (pytest.ini / a root conftest).
Steps 1-4 of the resolution procedure were walked: no CLI wrapper owns this
behaviour (build.py is a dependency of it, not its caller), it is not a
registered pre-commit hook, it backs no slash command, and it is not a
workflow step — the fixture itself IS the entry point a real pytest run
exercises. Recorded as `result: resolved` in this ticket's
completion_manifest.
======================================================================
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock as mock
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


class TestTQ600a1SharedReferenceLayout(unittest.TestCase):
    """RED test stubs for TQ-600a-1. See module docstring for the assumed
    production contract these tests are pinned to. Tests 3 and 4 (the
    `-n 2` cross-worker pair) live in the sibling file
    test_tq_600a_1_multiworker.py — see that file's own module docstring
    for the note explaining the split."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    # ------------------------------------------------------------------
    # Test 1 — criterion
    # ------------------------------------------------------------------
    def test_tq600a_1_a_selection_of_read_only_consumers_deploys_the_package_once_MANUAL(
        self,
    ):
        # covers: TQ-600a-1
        # angle: criterion
        """
        A child pytest session over at least three read-only consumer tests
        executes exactly one real `build.py --target-dir` subprocess,
        observed independently of anything the run reports about itself
        (counted via the JSONL execution log, not via pytest's own summary).

        SLOW (real ~60s deploy) — suffixed _MANUAL per
        testing_context.manual_test_suffix; this genuinely cannot complete
        inside max_test_duration_seconds because it exercises the real
        subprocess this whole AC exists to stop repeating.
        """
        children_dir = self.tmp_path / "children"
        # TQ-600a-5 note: these consumers only ever read the deployed layout
        # and never mutate it, so they explicitly declare
        # @pytest.mark.shared_layout_reader. Before TQ-600a-5's marker-based
        # routing landed, EVERY consumer -- declared or not -- was handed the
        # one shared layout by default; TQ-600a-5 changed that default so an
        # UNDECLARED consumer now correctly receives its own private copy
        # instead, which would silently break this test's "exactly one
        # deploy" assertion below unless these consumers declare themselves.
        consumer_body = """
            import os
            import pytest
            from pathlib import Path

            @pytest.mark.shared_layout_reader
            def test_consumer_{n}(shared_reference_layout):
                root = Path(shared_reference_layout)
                assert root.exists()
                assert (root / ".build_manifest.json").exists()
        """
        for n in range(3):
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
            1,
            len(deploy_events),
            msg=f"expected exactly one real deploy, observed: {deploy_events}",
        )

    # ------------------------------------------------------------------
    # Test 2 — criterion
    # ------------------------------------------------------------------
    def test_tq600a_1_every_consumer_receives_the_identical_layout_root_MANUAL(self):
        # covers: TQ-600a-1
        # angle: criterion
        """
        Two consumers in the same session that ask for the layout root
        receive the identical path string, not two paths whose contents
        happen to match.

        SLOW (real deploy, paid once for the whole session) — _MANUAL.
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
        # instead, which would silently break this test's "identical root"
        # assertion below unless these consumers declare themselves.
        consumer_body = """
            import os
            import pytest
            from pathlib import Path

            @pytest.mark.shared_layout_reader
            def test_reads_root_{n}(shared_reference_layout):
                out = Path(os.environ["RESULT_DIR"]) / "root_{n}.txt"
                out.write_text(str(shared_reference_layout))
        """
        for n in ("a", "b"):
            _write_consumer_test(
                children_dir, f"test_reads_root_{n}.py", consumer_body.format(n=n)
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
        root_a = (result_dir / "root_a.txt").read_text(encoding="utf-8")
        root_b = (result_dir / "root_b.txt").read_text(encoding="utf-8")
        self.assertEqual(
            root_a,
            root_b,
            msg="two consumers in the same session received different root strings",
        )

    # ------------------------------------------------------------------
    # Test 5 — failure. NAMED MUTATION: publish root when production
    # begins instead of when it finishes.
    # ------------------------------------------------------------------
    def test_tq600a_1_no_consumer_is_handed_a_root_before_its_layout_is_complete_MANUAL(
        self,
    ):
        # covers: TQ-600a-1
        # angle: failure
        """
        A second requester arriving while the first is mid-production waits,
        and the layout it is then handed is complete — the deploy's full
        expected file set, not a partially written tree.

        NAMED MUTATION this test alone catches: publish the root when
        production begins instead of when it finishes. Under that mutation
        the second (waiting) caller's returned root would be observed to
        lack `.build_manifest.json` (written near the end of
        scripts/build.py's main() — confirmed by reading build.py) at the
        moment its call returns. The fourth AC clause says this case
        cannot arise, so it must be provoked deliberately, per the AC's
        own wording, to be checked: two threads call the (assumed)
        low-level `get_or_produce_shared_layout()` directly, staggered so
        the second thread's call is issued while the real ~60s deploy the
        first thread triggered is still running.

        SLOW (real deploy) — _MANUAL.
        """
        try:
            plugin = importlib.import_module(
                "scripts.suite_performance.pytest_shared_reference_layout"
            )
        except ImportError as exc:  # expected RED: module does not exist yet
            self.fail(
                "scripts.suite_performance.pytest_shared_reference_layout "
                f"does not exist yet (expected until python-coder implements "
                f"TQ-600a-1): {exc}"
            )
            return

        results: dict[str, Path] = {}
        errors: list[BaseException] = []

        def _call(key: str) -> None:
            try:
                results[key] = plugin.get_or_produce_shared_layout()
            except BaseException as exc:  # noqa: BLE001 - captured for assertion, not swallowed
                errors.append(exc)

        t1 = threading.Thread(target=_call, args=("first",))
        t1.start()
        time.sleep(1.0)  # deploy takes ~60s; 1s reliably lands mid-production
        t2 = threading.Thread(target=_call, args=("second",))
        t2.start()
        t1.join(timeout=_REAL_DEPLOY_SUBPROCESS_TIMEOUT_S)
        t2.join(timeout=_REAL_DEPLOY_SUBPROCESS_TIMEOUT_S)

        self.assertFalse(errors, msg=f"unexpected errors from producer threads: {errors}")
        self.assertIn("first", results)
        self.assertIn("second", results)
        self.assertEqual(
            str(results["first"]),
            str(results["second"]),
            msg="both threads must be handed the identical root",
        )
        for key, root in results.items():
            manifest = Path(root) / ".build_manifest.json"
            self.assertTrue(
                manifest.exists(),
                msg=(
                    f"{key} caller was handed root {root!r} before its layout "
                    "was complete: .build_manifest.json is missing"
                ),
            )

    # ------------------------------------------------------------------
    # Test 6 — boundary (type: unit). NAMED MUTATION: produce a fresh
    # layout on every request.
    # ------------------------------------------------------------------
    def test_tq600a_1_a_cached_layout_requested_many_times_executes_only_one_deploy(
        self,
    ):
        # covers: TQ-600a-1
        # angle: boundary
        """
        Fifty requests within one run execute one deploy subprocess. The
        observation is of executions the harness counted (a monkeypatched
        subprocess.run), not of any figure the run reported — the reported
        figure and its bound are TQ-600a-6's.

        NAMED MUTATION this test alone catches: produce a fresh layout on
        every request.

        type: unit per the AC's test_spec — calls the low-level function
        directly in-process (no subprocess pytest session), so this stays
        fast.
        """
        try:
            plugin = importlib.import_module(
                "scripts.suite_performance.pytest_shared_reference_layout"
            )
        except ImportError as exc:
            self.fail(
                "scripts.suite_performance.pytest_shared_reference_layout "
                f"does not exist yet (expected until python-coder implements "
                f"TQ-600a-1): {exc}"
            )
            return

        call_count = {"n": 0}
        real_run = subprocess.run

        def _counting_run(cmd, *args, **kwargs):
            if isinstance(cmd, (list, tuple)) and any(
                "build.py" in str(part) for part in cmd
            ):
                call_count["n"] += 1
            return real_run(cmd, *args, **kwargs)

        with mock.patch("subprocess.run", side_effect=_counting_run):
            roots = [plugin.get_or_produce_shared_layout() for _ in range(50)]

        self.assertEqual(
            1,
            call_count["n"],
            msg=f"expected exactly one deploy subprocess across 50 requests, observed {call_count['n']}",
        )
        self.assertEqual(
            1,
            len({str(r) for r in roots}),
            msg="all 50 requests must receive the identical cached root",
        )

    # ------------------------------------------------------------------
    # Test 7 — reachability
    # ------------------------------------------------------------------
    def test_tq_600a_1_reachable_from_entry_point_MANUAL(self):
        # covers: TQ-600a-1
        # angle: reachability
        """
        REQUIRED reachability test (BP-1100g-2). This AC's test_spec named
        no entry point, so one was resolved: `shared_reference_layout` is a
        pytest fixture/plugin, not a CLI/hook/slash-command/workflow-step —
        its only real caller is a real, un-augmented pytest session that
        loads this repo's actual whole-suite registration surface (pytest.ini
        or a root conftest, whichever python-coder chooses).

        Deliberately does NOT pass an explicit `-p` override (unlike tests
        1-6): the consumer test file below is placed in
        unit_tests/suite_performance/ itself, a directory with no
        conftest.py of its own. If python-coder registers the fixture only
        in a narrower surface (e.g. only unit_tests/portability/conftest.py,
        which the ticket's original files_touched list would produce), this
        test fails with "fixture 'shared_reference_layout' not found" even
        though tests 1-6 (which force-load the plugin via `-p`) would stay
        green — that gap is exactly what this test exists to catch.

        Asserts not just that the fixture resolves, but that its result is
        CONSUMED in control flow (a real file read from the returned root),
        satisfying the reachability angle's "result is consumed in control
        flow" requirement, not merely "importable".

        SLOW (real deploy, via the real un-augmented registration path) —
        _MANUAL.
        """
        children_dir = _SUITE_PERF_DIR / "_reachability_children"
        self.addCleanup(_rmtree_if_exists, children_dir)
        consumer_body = """
            from pathlib import Path

            def test_consumes_real_registration(shared_reference_layout):
                root = Path(shared_reference_layout)
                # Consume the result in control flow: read a real file the
                # deploy produced, don't just assert the symbol exists.
                manifest = root / ".build_manifest.json"
                assert manifest.exists(), "layout incomplete or fixture is a stub"
                assert len(manifest.read_text(encoding="utf-8")) > 0
        """
        _write_consumer_test(
            children_dir, "test_real_entry_point_consumer.py", consumer_body
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
        self.assertGreaterEqual(
            len(deploy_events),
            1,
            msg="the real entry point never actually executed a deploy",
        )


if __name__ == "__main__":
    unittest.main()
