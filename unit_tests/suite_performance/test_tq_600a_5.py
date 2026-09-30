"""
Tests for TQ-600a-5 — "A test that has not said which kind it is gets the
safe kind."

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-5.yaml
(test_spec + test_rationale). The ticket's ## Test Requirements table is
derived from that YAML; where the two differ, the YAML wins.

STRUCTURAL SPLIT NOTE: this AC has 10 named tests. Tests 1-5 (the
three-way routing cases: undeclared / declared-reader / declared-mutator,
plus the anti-glob NAMED MUTATION) live here. Tests 6-10 (the two separate
reported counts, fail-safe-not-fail-fast, marker registration, and
reachability) live in the sibling file ``test_tq_600a_5_reporting.py``,
kept under the repo's GE-127a-1 400-line file-size limit. Shared helpers
and the marker/env-var constants live in ``_test_helpers_tq_600a_5.py``,
imported by both files -- see that module for the exact interface.

======================================================================
ASSUMED PRODUCTION CONTRACT (written by test-writer; python-coder builds
this to make the tests below green -- see Source-of-Truth Discipline
Rule 5: expand the test, don't shrink production, and the inverse holds
at authoring time too: these tests ARE the contract until a documented,
justified reason changes them).

TQ-600a-5's own notes field is explicit that "what form the declaration
takes is not specified [in the AC] and is an it-po decision" -- but
it_requirement 1 already settled the FORM as "a registered pytest marker".
The exact marker names, the routing record's shape, and how the existing
`shared_reference_layout` fixture (TQ-600a-1) is extended to route are
test-writer's call, made here and documented so python-coder implements
against a single, unambiguous target.

No such routing logic exists yet. Every test below is expected to fail —
either at collection (pytest.ini has no `markers =` section yet, so a
custom mark is merely unregistered, not yet a routing signal) or at
assertion time (the `shared_reference_layout` fixture from TQ-600a-1
today unconditionally returns the one shared layout for every requester,
regardless of marker) — until python-coder implements this AC. That is
the correct RED state.

1. TWO REGISTERED MARKERS, read at fixture-request time from the
   requesting test item's own metadata (``request.node.get_closest_marker``
   or equivalent) -- never from the test's file name or directory:
     - ``shared_layout_reader`` -- read-only consumer; must be handed the
       real shared reference layout (TQ-600a-1's canonical
       ``get_or_produce_shared_layout()`` result).
     - ``shared_layout_mutator`` -- must be handed a private copy of its
       own, never the shared root.
   Both are registered in pytest.ini's ``[pytest] markers =`` section
   (Implementation Notes point 1; TQ-600a-8 reads this registration too).

2. THE EXISTING ``shared_reference_layout`` FIXTURE (TQ-600a-1,
   scripts/suite_performance/pytest_shared_reference_layout.py) BECOMES
   MARKER-AWARE. This AC's own files_touched names only this plugin file
   and pytest.ini -- no new fixture name -- so the routing selector lives
   inside the fixture that already exists:
     - requester carries ``shared_layout_reader`` -> returns
       ``get_or_produce_shared_layout()`` (the one true shared root).
     - requester carries ``shared_layout_mutator`` -> produces and returns
       a PRIVATE copy, never the shared root, never cached/reused across
       requesters.
     - requester carries NEITHER (undeclared) -> safe default: same
       private-copy path as a declared mutator (fail-safe, not fail-fast --
       Implementation Notes point 2), but additionally recorded as
       "undeclared" per point 3 below.

3. THE ROUTING RECORD. Two channels, both required (test_spec entry 2:
   "Read the emitted record, not an in-process structure" -- and it_requirement
   2: "named by node id in the run's own record"):
     a. JSONL file named by the env var
            LEAFCUTTER_SHARED_LAYOUT_ROUTING_LOG
        (no-op if unset). One line per routed test, appended at the point
        routing is decided (fixture-request time):
            {"event": "routed_shared_reader", "nodeid": "<request.node.nodeid>"}
            {"event": "routed_unshared_mutator", "nodeid": "<...>"}
            {"event": "routed_unshared_undeclared", "nodeid": "<...>"}
        Plus exactly one summary line at session finish:
            {"event": "routing_summary",
             "declared_mutator_count": <int>, "undeclared_count": <int>}
        THE TWO COUNT FIELDS ARE NAMED SEPARATELY AND MUST NEVER BE MERGED
        (Implementation Notes point 3 / TQ-600a-6's amended bound: the
        declared-mutator figure is the bound's second term; the undeclared
        figure is reported ALONGSIDE it and excluded from it).
     b. Terminal/console output (pytest_terminal_summary or equivalent):
        one line per undeclared test naming it by node id, e.g.
            shared-layout-routing: UNDECLARED <nodeid>
        plus one summary line, e.g.
            shared-layout-routing: declared_mutators=<N> undeclared=<M>

4. ROUTING MUST NOT CONSULT THE TEST'S FILE NAME OR DIRECTORY, for either
   branch (Implementation Notes point 5; test 5 below is the NAMED
   MUTATION descriptor for exactly this).

5. UNDECLARED MUST NEVER FAIL, ERROR, OR SKIP THE TEST ITSELF (test 8,
   in the sibling file) -- fail-safe was a deliberate BA decision, not
   an oversight.

6. pytest.ini's addopts also gains ``--strict-markers`` (test-writer's
   assumed choice, test 9 in the sibling file) so a MISSPELLED marker
   variant is a hard collection error rather than a silently-tolerated
   custom mark indistinguishable from an honest, deliberate omission.

Reachability entry-point resolution (BP-1100g-2): as with TQ-600a-1, this
is a pytest plugin/fixture extension, not a CLI/hook/slash-command/
workflow-step. Its only real caller is a real, un-augmented pytest session
loading this repo's actual whole-suite registration surface (pytest.ini).
See test_tq_600a_5_reporting.py's test 10 and this file's sign-off comment
for the recorded `result: resolved`.
======================================================================
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ._test_helpers import _read_jsonl, _rmtree_if_exists, _write_consumer_test
from ._test_helpers_tq_600a_5 import (
    MUTATOR_MARKER,
    READER_MARKER,
    ROUTING_LOG_ENV_VAR,
    consumer_source,
    direct_root_source,
    read_root,
    run_child_session,
)


class TestTQ600a5RoutingCases(unittest.TestCase):
    """RED test stubs for TQ-600a-5's three routing cases (tests 1-5). See
    module docstring for the assumed production contract these tests are
    pinned to."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.children_dir = self.tmp_path / "children"
        self.result_dir = self.tmp_path / "results"
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(_rmtree_if_exists, self.children_dir)

    def _env(self) -> dict[str, str]:
        return {"RESULT_DIR": str(self.result_dir)}

    # ------------------------------------------------------------------
    # Test 1 — criterion
    # ------------------------------------------------------------------
    def test_tq600a_5_an_undeclared_test_receives_its_own_copy_MANUAL(self):
        # covers: TQ-600a-5
        # angle: criterion
        """
        A test that requests ``shared_reference_layout`` and declares
        nothing is handed a root that is NOT the shared reference layout
        root -- compared, within the same child session, against a
        reference test that calls ``get_or_produce_shared_layout()``
        directly.

        SLOW (two real deploys: the shared one + the undeclared test's own
        private copy) — _MANUAL.
        """
        _write_consumer_test(
            self.children_dir, "test_direct.py", direct_root_source("direct.txt")
        )
        _write_consumer_test(
            self.children_dir,
            "test_undeclared.py",
            consumer_source("undeclared_consumer", "undeclared.txt", marker=None),
        )
        result = run_child_session(self.children_dir, env_overrides=self._env())
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        direct_root = read_root(self.result_dir, "direct.txt")
        undeclared_root = read_root(self.result_dir, "undeclared.txt")
        self.assertNotEqual(
            direct_root,
            undeclared_root,
            msg="an undeclared test was handed the shared reference layout root",
        )

    # ------------------------------------------------------------------
    # Test 2 — criterion
    # ------------------------------------------------------------------
    def test_tq600a_5_an_undeclared_test_is_named_in_the_runs_own_record_MANUAL(self):
        # covers: TQ-600a-5
        # angle: criterion
        """
        The run's own emitted JSONL record AND its console output name the
        undeclared test by node id as having taken the unshared path
        without declaring why. Read the emitted artifacts, not an
        in-process structure.

        SLOW (real private deploy for the undeclared test) — _MANUAL.
        """
        _write_consumer_test(
            self.children_dir,
            "test_undeclared_named.py",
            consumer_source("undeclared_named", "undeclared_named.txt", marker=None),
        )
        log_path = self.tmp_path / "routing_log.jsonl"
        env = dict(self._env())
        env[ROUTING_LOG_ENV_VAR] = str(log_path)
        result = run_child_session(self.children_dir, env_overrides=env)
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        needle = "test_undeclared_named.py::test_undeclared_named"
        entries = _read_jsonl(log_path)
        undeclared_entries = [
            e for e in entries if e.get("event") == "routed_unshared_undeclared"
        ]
        self.assertTrue(
            any(needle in e.get("nodeid", "") for e in undeclared_entries),
            msg=f"undeclared test not named in JSONL record: {entries}",
        )
        combined_output = result.stdout + result.stderr
        self.assertIn(
            needle,
            combined_output,
            msg=(
                "undeclared test not named by node id in the run's own "
                f"console output: {combined_output}"
            ),
        )

    # ------------------------------------------------------------------
    # Test 3 — boundary (positive branch)
    # ------------------------------------------------------------------
    def test_tq600a_5_a_test_declared_a_reader_receives_the_shared_layout_MANUAL(self):
        # covers: TQ-600a-5
        # angle: boundary
        """
        A test carrying the reader marker is handed the identical root a
        direct ``get_or_produce_shared_layout()`` call in the same session
        receives -- proven discriminating (not just true because the
        fixture is currently unconditional) by also requiring an
        UNDECLARED test in the SAME session to be handed something
        DIFFERENT. Without the second assertion this test passes vacuously
        against today's pre-TQ-600a-5 fixture, which already hands the
        shared root to every requester regardless of marker -- confirmed
        while authoring these tests (test-runner sign-off comment records
        the observed vacuous PASSED result and this fix).

        SLOW (shared deploy + the undeclared test's own private deploy)
        — _MANUAL.
        """
        _write_consumer_test(
            self.children_dir, "test_direct.py", direct_root_source("direct.txt")
        )
        _write_consumer_test(
            self.children_dir,
            "test_reader.py",
            consumer_source("declared_reader", "reader.txt", marker=READER_MARKER),
        )
        _write_consumer_test(
            self.children_dir,
            "test_undeclared_control.py",
            consumer_source("undeclared_control", "undeclared_control.txt", marker=None),
        )
        result = run_child_session(self.children_dir, env_overrides=self._env())
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        self.assertNotEqual(
            read_root(self.result_dir, "direct.txt"),
            read_root(self.result_dir, "undeclared_control.txt"),
            msg=(
                "control check failed: an undeclared test in the same "
                "session was ALSO handed the shared layout -- this test's "
                "positive-branch assertion below would then be vacuously "
                "true regardless of whether the reader marker is honoured"
            ),
        )
        self.assertEqual(
            read_root(self.result_dir, "direct.txt"),
            read_root(self.result_dir, "reader.txt"),
            msg="a declared reader was not handed the shared reference layout",
        )

    # ------------------------------------------------------------------
    # Test 4 — boundary (third case: declared mutator)
    # ------------------------------------------------------------------
    def test_tq600a_5_a_test_declared_a_mutator_receives_its_own_copy_MANUAL(self):
        # covers: TQ-600a-5
        # angle: boundary
        """
        A test carrying the mutator marker is handed a root DIFFERENT from
        the shared reference layout -- the third case, distinct from both
        "declared reader" (test 3) and (by declaration alone, not
        behaviour) "undeclared" (tests 1-2). An implementation with only
        two branches (declared-reader vs. everything else) would pass
        tests 1, 3, 4 individually since undeclared and declared-mutator
        both currently expect the SAME behaviour; test 5 below is what
        actually excludes that two-branch shape by probing the SELECTOR,
        not just the outcome.

        SLOW (real private deploy) — _MANUAL.
        """
        _write_consumer_test(
            self.children_dir, "test_direct.py", direct_root_source("direct.txt")
        )
        _write_consumer_test(
            self.children_dir,
            "test_mutator.py",
            consumer_source("declared_mutator", "mutator.txt", marker=MUTATOR_MARKER),
        )
        result = run_child_session(self.children_dir, env_overrides=self._env())
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        self.assertNotEqual(
            read_root(self.result_dir, "direct.txt"),
            read_root(self.result_dir, "mutator.txt"),
            msg="a declared mutator was handed the shared reference layout",
        )

    # ------------------------------------------------------------------
    # Test 5 — failure. NAMED MUTATION: replace the marker lookup with a
    # filename or directory rule.
    # ------------------------------------------------------------------
    def test_tq600a_5_the_declaration_selects_the_path_not_the_file_name_or_location_MANUAL(
        self,
    ):
        # covers: TQ-600a-5
        # angle: failure
        """
        A reader-declared test whose filename matches the known mutator
        glob (``test_bp_900g_8*``, the CLAUDE.md-documented proxy pattern)
        still receives the shared layout, and a mutator-declared test with
        an ORDINARY filename sitting alongside readers still receives its
        own copy.

        NAMED MUTATION this test alone catches: replace the marker lookup
        with a filename/directory rule (e.g. "anything matching
        test_bp_900g_8* gets its own copy, everything else gets shared").
        Every other test in this file uses ordinary, non-matching
        filenames with correct markers, so they stay green under that
        mutation -- only the reader-marked-but-glob-named file here
        exposes it: under a filename rule it would be shunted to a
        private copy despite declaring itself a reader.

        SLOW (two real deploys) — _MANUAL.
        """
        _write_consumer_test(
            self.children_dir, "test_direct.py", direct_root_source("direct.txt")
        )
        # Reader-declared, but named exactly like the known mutator glob.
        _write_consumer_test(
            self.children_dir,
            "test_bp_900g_8_fake_reader.py",
            consumer_source("fake_reader", "fake_reader.txt", marker=READER_MARKER),
        )
        # Mutator-declared, ordinary filename, sitting alongside the above.
        _write_consumer_test(
            self.children_dir,
            "test_ordinary_declared_mutator.py",
            consumer_source(
                "ordinary_mutator", "ordinary_mutator.txt", marker=MUTATOR_MARKER
            ),
        )
        result = run_child_session(self.children_dir, env_overrides=self._env())
        self.assertEqual(
            0, result.returncode, msg=f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        direct_root = read_root(self.result_dir, "direct.txt")
        self.assertEqual(
            direct_root,
            read_root(self.result_dir, "fake_reader.txt"),
            msg=(
                "reader-declared test named like the mutator glob was NOT "
                "given the shared layout -- routing appears to consult the "
                "file name instead of the declaration"
            ),
        )
        self.assertNotEqual(
            direct_root,
            read_root(self.result_dir, "ordinary_mutator.txt"),
            msg=(
                "mutator-declared test with an ordinary filename was given "
                "the shared layout -- routing appears to consult the file "
                "name instead of the declaration"
            ),
        )


if __name__ == "__main__":
    unittest.main()
