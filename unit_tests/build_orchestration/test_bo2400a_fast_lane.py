"""
MODULE: unit_tests/build_orchestration/test_bo2400a_fast_lane.py
GOAL: RED test stubs for BO-2400a-2, BO-2400a-2-i, BO-2400a-3, BO-2400a-3-i,
      BO-2400a-4, BO-2400a-4-i.

=== Interface contract under test (to be implemented by python-coder) ===

Location: scripts/build_orchestration/fast_lane.py

    select_batch(
        *,
        ac_root: Path,
        limit: int,
    ) -> list[str]

        Select up to `limit` ready leaf ACs from `ac_root` and return their ids
        in a deterministic, total-order (priority asc, complexity asc, id asc) —
        the same order as scan_ac_store._sort_ready.  Reuses the existing
        scan_ac_store filtering/sorting logic so fast-lane selection tracks the
        same readiness semantics as the scanner.  No agent, no LLM, no network
        call in the selection path.

        Ready leaf AC requirements (same as scan_ac_store):
            - level: L2 or L3
            - status: active
            - readiness: approved  (not draft, not reviewed)
            - work_status: todo
            - all depends_on are work_status: done (or empty)

        Args:
            ac_root:  Root directory of the AC YAML store.
            limit:    Maximum number of ACs to return (cohesion cap M).

        Returns:
            Ordered list of at most `limit` ready AC ids.  Empty list when no
            ready ACs exist.  Does NOT modify the store — leftover ACs remain
            in their ready state for a subsequent loop iteration.

    -----------------------------------------------------------------------

    verify_red_baseline(
        *,
        ac_ids: list[str],
        test_root: Path,
        base_ref: str | None = None,
    ) -> dict

        AMENDED 2026-08-17 (BO-2400a-3, decomposed into BO-2400a-3-i..viii —
        see unit_tests/build_orchestration/test_bo2400a_3_amended_red_baseline.py
        for the full amended contract).  Find all test files under `test_root`
        whose functions carry a "# covers: <id>" tag for any id in `ac_ids`,
        partition them into newly-added and pre-existing using git at
        test-function granularity against the worktree's merge-base with
        origin/main (or `base_ref` when supplied), run them via pytest, and
        pass when at least one NEWLY-ADDED test is red — not when ALL of them
        are (the pre-amendment rule, replaced because a partially-implemented
        AC legitimately has some already-green covering tests).

        The pass/fail signal is derived from the pytest process exit code AND
        per-test "-v" output — not from agent judgment.  The function is
        idempotent: re-running against the same unchanged worktree yields the
        same verdict and performs no git writes (no fetch, no ref update).

        Returns a dict with ALL of the following keys:

            "gate_passed" (bool)
                True iff at least one newly-added covering test is red.

            "reason" (str | None)
                None when gate_passed is True; otherwise exactly one of
                "no_new_covering_tests", "all_new_tests_green_at_baseline",
                "no_red_outcome_among_new_tests", or
                "baseline_partition_unavailable" (the fail-closed case when
                the git partition cannot be resolved).

            "red", "green_at_baseline", "inconclusive" (list[dict])
                Newly-added tests classified red / green / inconclusive
                (FAILED+XFAIL red; PASSED+XPASS green; SKIPPED+ERROR+
                unrecognised inconclusive).  Each entry is
                {"nodeid": str, "ac_id": str, "outcome": str}.

            "preexisting" (list[dict])
                Pre-existing covering tests in the same entry shape — reported
                but excluded from the verdict entirely.

        The coder agent must NOT be dispatched unless gate_passed is True.
        The pre-amendment keys "all_red", "offender", and "offender_ac_id" are
        REMOVED — a version-skewed caller reading a missing key as falsy must
        fail closed, not silently pass.

    -----------------------------------------------------------------------

    verify_green_and_coverage(
        *,
        ac_ids: list[str],
        test_root: Path,
        ac_root: Path,
    ) -> dict

        Run all tests linked to any id in `ac_ids` (found via "# covers:<id>"
        tags in `test_root`) and verify:
          (a) Every test passes — the batch test run exits zero.
          (b) Every AC id in `ac_ids` has at least one test tagged with it.

        Reuses done_proof.verify_done_eligible to derive the per-AC verdict
        so coverage semantics stay in sync with the done-proof gate.

        Commit staging is gated on BOTH conditions; neither alone is
        sufficient.  The function is idempotent.

        Returns a dict with ALL of the following keys:

            "green" (bool)
                True iff all linked tests pass (exit zero).

            "coverage_ok" (bool)
                True iff every id in `ac_ids` has >=1 covering test.

            "uncovered_ac_ids" (list[str])
                IDs from `ac_ids` that have no covering "# covers:<id>" test.
                Empty list when coverage_ok is True.

            "failing_tests" (list[str])
                pytest nodeids of tests that did not pass.
                Empty list when green is True.

=== Fixture-authenticity mandate (BO-2500c) ===

  All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML
  literals).  All test fixtures are real .py files with genuine bodies that
  pass or fail under pytest.  No mocking of pass/fail signals.

=== Red baseline ===

  All tests are RED until python-coder creates
  scripts/build_orchestration/fast_lane.py and implements the three functions
  above.  The ImportError produced by the missing module IS the intended red
  state — it confirms the production code does not yet exist.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring — same pattern as test_bo2400b_path_selection.py
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
sys.path.insert(0, str(_MODULE_DIR))

# These imports raise ImportError until python-coder creates fast_lane.py.
# That ImportError IS the intended red state — it confirms the production
# code does not yet exist.
from fast_lane import select_batch, verify_green_and_coverage, verify_red_baseline  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _write_approved_ac(
    ac_root: Path,
    ac_id: str,
    *,
    priority: str = "medium",
    estimated_complexity: str = "S",
    work_status: str = "todo",
    depends_on: list | None = None,
) -> Path:
    """Write a minimal approved, active, leaf L2 AC YAML for select_batch tests.

    Uses yaml.safe_dump (fixture-authenticity mandate — no hand-typed YAML).
    Only ACs with readiness=approved are picked up by the scanner.

    Args:
        ac_root: Root directory of the synthetic AC store.
        ac_id: Identifier for the AC.
        priority: AC priority field ("critical", "high", "medium", "low").
        estimated_complexity: AC complexity field ("S", "M", "L", "XL").
        work_status: AC work status ("todo", "done").
        depends_on: List of AC ids this AC depends on (default: empty).

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": "L2",
        "status": "active",
        "work_status": work_status,
        "readiness": "approved",
        "priority": priority,
        "estimated_complexity": estimated_complexity,
        "depends_on": depends_on if depends_on is not None else [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    # Mandate: use yaml.safe_dump — not a hand-typed YAML literal.
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_test_file(test_root: Path, filename: str, content: str) -> Path:
    """Write a Python test file to test_root using textwrap.dedent.

    Args:
        test_root: Directory to place the test file.
        filename: Filename (e.g. "test_my_feature.py").
        content: Python source; leading whitespace is dedented automatically.

    Returns:
        Path to the written test file.
    """
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def _run_git(args: list[str], cwd: Path) -> None:
    """Run a git subcommand in *cwd*, raising AssertionError on failure."""
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {cwd} (exit {result.returncode}): "
            f"{result.stderr}"
        )


def _make_git_worktree(tmp_root: Path) -> Path:
    """Create an origin repo with a placeholder commit, clone it, return the clone.

    verify_red_baseline (amended 2026-08-17) requires its test_root to be
    inside a git worktree with an ``origin/main`` remote-tracking ref so it
    can resolve the default ``git merge-base HEAD origin/main`` baseline — a
    bare tempdir, or a repo with no origin, now fails closed with
    baseline_partition_unavailable. The clone mirrors the real fast-lane
    worktree (always freshly cloned off origin/main): any file written into
    the clone afterwards and left uncommitted is, by construction, absent
    from the merge-base and classified newly-added.

    Args:
        tmp_root: Parent directory to create "origin" and "work" subdirs in.

    Returns:
        Path to the cloned "work" worktree.
    """
    origin_dir = tmp_root / "origin"
    origin_dir.mkdir(parents=True, exist_ok=True)
    _run_git(["init", "-b", "main", "-q"], cwd=origin_dir)
    _run_git(["config", "user.email", "test-writer@example.com"], cwd=origin_dir)
    _run_git(["config", "user.name", "Test Writer"], cwd=origin_dir)
    (origin_dir / "README.md").write_text("placeholder\n", encoding="utf-8")
    _run_git(["add", "-A"], cwd=origin_dir)
    _run_git(["commit", "-q", "-m", "base"], cwd=origin_dir)

    work_dir = tmp_root / "work"
    _run_git(["clone", "-q", str(origin_dir), str(work_dir)], cwd=tmp_root)
    _run_git(["config", "user.email", "test-writer@example.com"], cwd=work_dir)
    _run_git(["config", "user.name", "Test Writer"], cwd=work_dir)
    return work_dir


def _tag_names(entries: object) -> set[str]:
    """Return the set of trailing '::func_name' suffixes present in *entries*."""
    out: set[str] = set()
    for entry in entries or []:
        nodeid = str(entry.get("nodeid", ""))
        if "::" in nodeid:
            out.add(nodeid.rsplit("::", 1)[-1])
    return out


# ---------------------------------------------------------------------------
# TestSelectBatch — BO-2400a-2, BO-2400a-2-i
# ---------------------------------------------------------------------------


class TestSelectBatch(unittest.TestCase):
    """Tests for select_batch() — deterministic AC selection with cohesion cap.

    AC scope: BO-2400a-2 (deterministic script, no agent), BO-2400a-2-i
    (truncate at cap, overflow stays ready).
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac2_selection_is_deterministic(self) -> None:
        # covers: BO-2400a-2
        """Running select_batch twice against the same store yields the identical ordered list.

        To make this green, select_batch must:
        - Produce a stable total ordering (priority asc → complexity asc → id asc)
        - Return byte-identical lists on consecutive calls against an unchanged store
        """
        _write_approved_ac(self.ac_root, "BO-FL-TEST-001", priority="medium", estimated_complexity="S")
        _write_approved_ac(self.ac_root, "BO-FL-TEST-002", priority="high", estimated_complexity="M")
        _write_approved_ac(self.ac_root, "BO-FL-TEST-003", priority="medium", estimated_complexity="M")

        first_run = select_batch(ac_root=self.ac_root, limit=10)
        second_run = select_batch(ac_root=self.ac_root, limit=10)

        self.assertEqual(
            first_run,
            second_run,
            "select_batch must return the identical ordered list on consecutive calls "
            "against an unchanged store (deterministic — BO-2400a-2).",
        )
        self.assertIsInstance(first_run, list, "select_batch must return a list.")

    def test_ac2_deterministic_sort_order(self) -> None:
        # covers: BO-2400a-2
        """The stable order is: priority asc (critical<high<medium<low), then id asc.

        High-priority AC must appear before medium-priority AC in the output.
        To make this green, select_batch must use _sort_ready or equivalent.
        """
        _write_approved_ac(self.ac_root, "BO-FL-TEST-010", priority="medium", estimated_complexity="S")
        _write_approved_ac(self.ac_root, "BO-FL-TEST-011", priority="high", estimated_complexity="S")

        result = select_batch(ac_root=self.ac_root, limit=10)

        # high priority comes before medium priority
        self.assertIn("BO-FL-TEST-010", result, "Medium-priority AC must be in results.")
        self.assertIn("BO-FL-TEST-011", result, "High-priority AC must be in results.")
        high_idx = result.index("BO-FL-TEST-011")
        medium_idx = result.index("BO-FL-TEST-010")
        self.assertLess(
            high_idx,
            medium_idx,
            "High-priority AC must appear before medium-priority AC in the sorted batch "
            "(deterministic ordering — BO-2400a-2).",
        )

    def test_ac2_empty_store_returns_empty_list(self) -> None:
        # covers: BO-2400a-2
        """An AC store with no ready ACs returns an empty list.

        To make this green, select_batch must return [] without error
        when no approved ready ACs exist.
        """
        self.ac_root.mkdir(parents=True, exist_ok=True)
        result = select_batch(ac_root=self.ac_root, limit=5)
        self.assertEqual(
            result,
            [],
            "select_batch must return [] when no ready approved ACs exist.",
        )

    def test_ac2i_batch_truncated_to_limit(self) -> None:
        # covers: BO-2400a-2-i
        """When ready ACs exceed the limit, the batch is truncated to at most `limit` items.

        To make this green, select_batch must:
        - Write 4 ready ACs to the store
        - Accept limit=2
        - Return exactly 2 ids (the first 2 in the stable order)
        """
        _write_approved_ac(self.ac_root, "BO-FL-CAP-001", priority="high", estimated_complexity="S")
        _write_approved_ac(self.ac_root, "BO-FL-CAP-002", priority="high", estimated_complexity="S")
        _write_approved_ac(self.ac_root, "BO-FL-CAP-003", priority="high", estimated_complexity="S")
        _write_approved_ac(self.ac_root, "BO-FL-CAP-004", priority="high", estimated_complexity="S")

        result = select_batch(ac_root=self.ac_root, limit=2)

        self.assertLessEqual(
            len(result),
            2,
            "select_batch must return at most `limit` ACs when the store has more "
            "ready ACs than the cap (BO-2400a-2-i).",
        )
        self.assertEqual(
            len(result),
            2,
            "select_batch must return exactly `limit` ACs when the store has >= limit "
            "ready ACs available.",
        )

    def test_ac2i_overflow_acs_excluded_from_returned_batch(self) -> None:
        # covers: BO-2400a-2-i
        """ACs beyond the cohesion cap are NOT included in the returned batch.

        They remain untouched in the store — select_batch must not modify or
        consume them.  To make this green, select_batch must truncate to `limit`
        without deleting or marking the remainder.

        The store is written with 3 ready ACs; limit=2.  The third AC must
        not appear in the result, but must still exist on disk (unchanged).
        """
        _write_approved_ac(self.ac_root, "BO-FL-OVF-AAA", priority="medium", estimated_complexity="S")
        _write_approved_ac(self.ac_root, "BO-FL-OVF-BBB", priority="medium", estimated_complexity="S")
        _write_approved_ac(self.ac_root, "BO-FL-OVF-CCC", priority="medium", estimated_complexity="S")

        result = select_batch(ac_root=self.ac_root, limit=2)

        self.assertEqual(len(result), 2, "Expected exactly 2 ACs in the batch (limit=2).")

        # All three ACs are returned in two runs of limit=10 — the overflowing one is not lost.
        full_result = select_batch(ac_root=self.ac_root, limit=10)
        self.assertEqual(
            len(full_result),
            3,
            "All 3 ACs must still be selectable when limit is relaxed — select_batch "
            "must NOT consume or remove the overflow AC (BO-2400a-2-i).",
        )

    def test_ac2_only_approved_ready_acs_selected(self) -> None:
        # covers: BO-2400a-2
        """Draft or non-active ACs must not be included in the batch.

        A draft AC and a done AC must be excluded; only approved+active+todo
        ACs appear in the result.
        """
        # The 'approved' AC should be selected.
        _write_approved_ac(self.ac_root, "BO-FL-FILT-GOOD", priority="medium", estimated_complexity="S")

        # A draft AC — not approved; must be excluded.
        draft_subdir = self.ac_root / "test-component"
        draft_subdir.mkdir(parents=True, exist_ok=True)
        draft_data = {
            "id": "BO-FL-FILT-DRAFT",
            "title": "Draft AC — must be excluded",
            "component": "build-orchestration",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "readiness": "draft",  # NOT approved → must be excluded
            "priority": "high",
            "estimated_complexity": "S",
            "depends_on": [],
            "amended_by": [],
            "covered_by": [],
            "implemented_by": [],
            "superseded_by": None,
        }
        (draft_subdir / "BO-FL-FILT-DRAFT.yaml").write_text(
            yaml.safe_dump(draft_data, allow_unicode=True), encoding="utf-8"
        )

        result = select_batch(ac_root=self.ac_root, limit=10)

        self.assertIn(
            "BO-FL-FILT-GOOD",
            result,
            "Approved, active, todo AC must be included in the batch.",
        )
        self.assertNotIn(
            "BO-FL-FILT-DRAFT",
            result,
            "Draft (not approved) AC must NOT be included in the batch.",
        )


# ---------------------------------------------------------------------------
# TestVerifyRedBaseline — BO-2400a-3, BO-2400a-3-i
# ---------------------------------------------------------------------------


class TestVerifyRedBaseline(unittest.TestCase):
    """Tests for verify_red_baseline() — gate that checks the red baseline.

    AC scope: BO-2400a-3 (script gate confirms a red baseline before the
    coder runs), BO-2400a-3-i (halts with a named reason and the offending
    tests when no newly-added test is red).

    AMENDED 2026-08-17: verify_red_baseline now requires a real git worktree
    with an origin/main remote-tracking ref to resolve its newly-added /
    pre-existing partition (BO-2400a-3-ii), so every fixture here writes its
    test files inside a real cloned git worktree (see _make_git_worktree)
    rather than a bare tempdir.  The pass rule also changed from "every batch
    test must be red" to "at least one NEWLY-ADDED test must be red"
    (BO-2400a-3-v) — see test_bo2400a_3_amended_red_baseline.py for the full
    amended contract (16 additional tests covering the git partition, outcome
    classification, fail-closed behavior, and idempotency in depth).
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp_root = Path(self._tmp.name)
        work_dir = _make_git_worktree(tmp_root)
        self.test_root = work_dir / "tests"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac3_gate_passes_when_a_new_batch_test_is_red(self) -> None:
        # covers: BO-2400a-3
        """When a newly-added batch test fails, verify_red_baseline passes the gate.

        The test fixture is a real .py file whose test asserts False — it
        genuinely fails under pytest.  No mocking.  The pass/fail signal is
        derived from the pytest exit code and -v output.

        To make this green, verify_red_baseline must:
        - Scan test_root for tests tagged '# covers: <ac_id>'
        - Classify the test newly-added (absent from the git base commit)
        - Run it via pytest as a subprocess and observe FAILED
        - Return gate_passed=True, reason=None
        """
        ac_id = "BO-FL-RED-001"
        _write_test_file(
            self.test_root,
            "test_red_baseline_failing.py",
            f"""\
            def test_genuinely_fails_before_implementation():
                # covers: {ac_id}
                assert False, "intentional failure — implementation not yet written"
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=self.test_root)

        self.assertTrue(
            verdict.get("gate_passed") is True,
            "verify_red_baseline must return gate_passed=True when a newly-added "
            f"batch test is red (BO-2400a-3); got {verdict!r}.",
        )
        self.assertIsNone(
            verdict.get("reason"),
            "reason must be None when the gate passes.",
        )

    def test_ac3_multiple_failing_new_tests_pass_the_gate(self) -> None:
        # covers: BO-2400a-3
        """Two newly-added batch tests that both fail must pass the gate.

        Covers the N>=2 batch case from the AC (the test-writer writes one set
        of stubs for the entire batch; at least one must be red before the
        coder runs).
        """
        ac_id_a = "BO-FL-RED-002a"
        ac_id_b = "BO-FL-RED-002b"
        _write_test_file(
            self.test_root,
            "test_batch_both_red.py",
            f"""\
            def test_fails_for_ac_a():
                # covers: {ac_id_a}
                assert False, "AC a not yet implemented"

            def test_fails_for_ac_b():
                # covers: {ac_id_b}
                raise NotImplementedError("AC b not yet implemented")
            """,
        )

        verdict = verify_red_baseline(
            ac_ids=[ac_id_a, ac_id_b], test_root=self.test_root
        )

        self.assertTrue(
            verdict.get("gate_passed") is True,
            "An all-red newly-added batch (N=2) must pass the gate (BO-2400a-3); "
            f"got {verdict!r}.",
        )
        self.assertEqual(
            _tag_names(verdict.get("red")),
            {"test_fails_for_ac_a", "test_fails_for_ac_b"},
        )

    def test_ac3i_halts_when_the_only_new_batch_test_passes(self) -> None:
        # covers: BO-2400a-3-i
        """When the only newly-added batch test passes, the gate halts.

        A passing newly-added test before implementation is a
        green-at-baseline signal — it means either the production code
        already exists or the test is under-specified.  With no other
        newly-added test to establish a red baseline, the gate must halt
        (gate_passed=False) so the coder is NOT dispatched.

        The test fixture is a real .py file whose test just passes (`pass`).
        """
        ac_id = "BO-FL-RED-003"
        _write_test_file(
            self.test_root,
            "test_passes_before_implementation.py",
            f"""\
            def test_already_passes_before_coder_runs():
                # covers: {ac_id}
                pass  # incorrectly passes before implementation — gate must detect this
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=self.test_root)

        self.assertFalse(
            verdict.get("gate_passed"),
            "verify_red_baseline must halt (gate_passed=False) when the only "
            f"newly-added batch test already passes (BO-2400a-3-i); got {verdict!r}.",
        )
        self.assertEqual(verdict.get("reason"), "all_new_tests_green_at_baseline")

    def test_ac3i_halt_names_offending_test_in_green_at_baseline(self) -> None:
        # covers: BO-2400a-3-i
        """The halt report must name the offending (green) test and its AC id.

        The halt report must name every newly-added covering test with its
        observed outcome so the operator can see why no red baseline was
        established (BO-2400a-3-i).

        To make this green, verify_red_baseline must report the passing test
        in `green_at_baseline` with its nodeid and ac_id.
        """
        ac_id = "BO-FL-RED-004"
        _write_test_file(
            self.test_root,
            "test_offender_identification.py",
            f"""\
            def test_green_at_baseline_offender():
                # covers: {ac_id}
                pass  # this passes — it is the offender
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=self.test_root)

        self.assertFalse(
            verdict.get("gate_passed"), "Must halt when the only new test passes."
        )
        green_entries = verdict.get("green_at_baseline")
        self.assertIn(
            "test_green_at_baseline_offender",
            _tag_names(green_entries),
            "The green_at_baseline entries must name the offending test function so "
            f"the halt report is actionable (BO-2400a-3-i); got {green_entries!r}.",
        )
        for entry in green_entries or []:
            self.assertEqual(
                entry.get("ac_id"),
                ac_id,
                "Each green_at_baseline entry must name the AC id of the offending "
                "test so the operator can trace back to the specific behavior "
                "under test (BO-2400a-3-i).",
            )

    def test_ac3_verdict_has_required_keys(self) -> None:
        # covers: BO-2400a-3
        """The verdict dict must contain the pinned amended-contract keys.

        To make this green, verify_red_baseline must return a dict with
        gate_passed, reason, red, green_at_baseline, inconclusive, and
        preexisting present regardless of the verdict.  The pre-amendment
        keys (all_red, offender, offender_ac_id) are REMOVED — a
        version-skewed caller reading a missing key as falsy must fail
        closed, not silently pass.
        """
        ac_id = "BO-FL-RED-006"
        _write_test_file(
            self.test_root,
            "test_verdict_keys.py",
            f"""\
            def test_fails_for_key_check():
                # covers: {ac_id}
                assert False, "always fails — checking verdict shape"
            """,
        )

        verdict = verify_red_baseline(ac_ids=[ac_id], test_root=self.test_root)

        for key in (
            "gate_passed",
            "reason",
            "red",
            "green_at_baseline",
            "inconclusive",
            "preexisting",
        ):
            self.assertIn(
                key,
                verdict,
                f"verify_red_baseline verdict must contain key '{key}' (BO-2400a-3).",
            )
        self.assertIsInstance(verdict["gate_passed"], bool, "gate_passed must be a bool.")
        for removed_key in ("all_red", "offender", "offender_ac_id"):
            self.assertNotIn(
                removed_key,
                verdict,
                f"The pre-amendment key '{removed_key}' must be removed, not kept as "
                "an alias — a version-skewed caller reading a missing key as falsy "
                "must fail closed rather than silently pass.",
            )


# ---------------------------------------------------------------------------
# TestVerifyGreenAndCoverage — BO-2400a-4, BO-2400a-4-i
# ---------------------------------------------------------------------------


class TestVerifyGreenAndCoverage(unittest.TestCase):
    """Tests for verify_green_and_coverage() — gate for green tests + coverage.

    AC scope: BO-2400a-4 (gate checks all pass + all ACs covered),
              BO-2400a-4-i (refuses commit when tests still failing).
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_active_ac(self, ac_id: str) -> None:
        """Write a minimal active AC YAML for done_proof coverage checks."""
        subdir = self.ac_root / "test-component"
        subdir.mkdir(parents=True, exist_ok=True)
        path = subdir / f"{ac_id}.yaml"
        data: dict = {
            "id": ac_id,
            "title": f"Synthetic active AC {ac_id}",
            "component": "build-orchestration",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "readiness": "approved",
            "priority": "medium",
            "estimated_complexity": "S",
            "depends_on": [],
            "amended_by": [],
            "covered_by": [],
            "implemented_by": [],
            "superseded_by": None,
        }
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    def _write_composite_ac(self, ac_id: str, covered_by: list[str]) -> None:
        """Write a minimal composite AC YAML (non-empty covered_by) for the
        H-1 false-pass regression test.

        Uses yaml.safe_dump (fixture-authenticity mandate) — never a
        hand-typed YAML literal.
        """
        subdir = self.ac_root / "test-component"
        subdir.mkdir(parents=True, exist_ok=True)
        path = subdir / f"{ac_id}.yaml"
        data: dict = {
            "id": ac_id,
            "title": f"Synthetic composite AC {ac_id}",
            "component": "build-orchestration",
            "level": "L1",
            "status": "active",
            "work_status": "done",
            "readiness": "reviewed",
            "priority": "medium",
            "depends_on": [],
            "amended_by": [],
            "covered_by": covered_by,
            "implemented_by": [],
            "superseded_by": None,
        }
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    def test_h1_composite_with_uncovered_child_is_not_a_false_pass(self) -> None:
        # covers: BO-2500a-6
        """H-1 regression: a composite AC whose real child has ZERO linked
        tests must be reported as uncovered — verify_green_and_coverage must
        NOT false-pass it.

        BO-2500a-6 taught verify_done_eligible to derive a composite's
        eligibility from its children (see done_proof._verify_composite_
        eligible), which introduced two NEW reason-string shapes:
        "composite {id} has no coverable children" and "composite {id} has
        uncovered children: {ids}". verify_green_and_coverage's original
        coverage check substring-matched the OLD leaf-only reason text
        "no linked test found" — neither new composite reason contains that
        substring, so an uncovered composite verdict (eligible=False) was
        silently reported as coverage_ok=True, uncovered_ac_ids=[] — a FALSE
        PASS that could let mark_done_built_acs flip an unproven composite
        AC to work_status: done.

        RED before the fix: coverage_ok is True and uncovered_ac_ids is []
        even though the composite's only child has no covering test at all.
        GREEN after the fix: verify_green_and_coverage must read the
        structured verdict["eligible"] field (not the prose reason string)
        and report coverage_ok=False with the composite id in
        uncovered_ac_ids.
        """
        composite_id = "BO-FL-H1-COMPOSITE-UNCOV"
        child_id = "BO-FL-H1-COMPOSITE-UNCOV-CHILD"
        self._write_composite_ac(composite_id, covered_by=[child_id])
        self._write_active_ac(child_id)
        # Deliberately no test file anywhere — the child has zero linked tests.

        verdict = verify_green_and_coverage(
            ac_ids=[composite_id], test_root=self.test_root, ac_root=self.ac_root
        )

        self.assertFalse(
            verdict["coverage_ok"],
            "A composite AC whose child has zero linked tests must NOT be "
            f"reported as coverage_ok=True (false pass). Got: {verdict}",
        )
        self.assertIn(
            composite_id,
            verdict.get("uncovered_ac_ids", []),
            "The uncovered composite AC id must be named in uncovered_ac_ids "
            f"so the caller refuses to mark it done. Got: {verdict}",
        )

    def test_ac4_gate_passes_when_all_batch_tests_pass(self) -> None:
        # covers: BO-2400a-4
        """The gate returns green=True when all batch tests pass.

        The test fixture is a real .py file whose test body passes.  No mocking.
        The pass signal is derived from the actual pytest exit code.

        To make this green, verify_green_and_coverage must:
        - Find tests tagged '# covers: <ac_id>'
        - Run them via pytest as a subprocess
        - Confirm all pass (exit zero)
        - Return {"green": True, ...}
        """
        ac_id = "BO-FL-GRN-001"
        self._write_active_ac(ac_id)
        _write_test_file(
            self.test_root,
            "test_genuinely_passes.py",
            f"""\
            def test_passes_after_implementation():
                # covers: {ac_id}
                pass  # implementation is done; test passes
            """,
        )

        verdict = verify_green_and_coverage(
            ac_ids=[ac_id], test_root=self.test_root, ac_root=self.ac_root
        )

        self.assertTrue(
            verdict["green"],
            "verify_green_and_coverage must return green=True when all batch tests pass "
            "(BO-2400a-4).",
        )
        self.assertEqual(
            verdict.get("failing_tests", []),
            [],
            "failing_tests must be empty when all tests pass.",
        )

    def test_ac4_coverage_gate_passes_when_every_ac_id_has_a_covers_tag(self) -> None:
        # covers: BO-2400a-4
        """The gate returns coverage_ok=True when every AC id has >= 1 covering test.

        Two ACs, each with one passing test tagged for it.  Both must be
        covered and coverage_ok must be True.
        """
        ac_id_a = "BO-FL-GRN-002a"
        ac_id_b = "BO-FL-GRN-002b"
        self._write_active_ac(ac_id_a)
        self._write_active_ac(ac_id_b)
        _write_test_file(
            self.test_root,
            "test_both_acs_covered.py",
            f"""\
            def test_covers_ac_a():
                # covers: {ac_id_a}
                pass

            def test_covers_ac_b():
                # covers: {ac_id_b}
                pass
            """,
        )

        verdict = verify_green_and_coverage(
            ac_ids=[ac_id_a, ac_id_b], test_root=self.test_root, ac_root=self.ac_root
        )

        self.assertTrue(verdict["green"], "Both tests pass — green must be True.")
        self.assertTrue(
            verdict["coverage_ok"],
            "Every AC id has a covers tag — coverage_ok must be True (BO-2400a-4).",
        )
        self.assertEqual(
            verdict.get("uncovered_ac_ids", []),
            [],
            "uncovered_ac_ids must be empty when every AC has a covering test.",
        )

    def test_ac4_coverage_gate_fails_when_ac_id_has_no_covers_tag(self) -> None:
        # covers: BO-2400a-4
        """coverage_ok is False when any AC id in the batch has no covering test.

        One AC is covered, one is not.  The uncovered AC must be reported in
        uncovered_ac_ids and coverage_ok must be False.

        To make this green, verify_green_and_coverage must check EVERY id in
        ac_ids — a single missing tag fails the coverage gate.
        """
        ac_id_covered = "BO-FL-GRN-003a"
        ac_id_missing = "BO-FL-GRN-003b"
        self._write_active_ac(ac_id_covered)
        self._write_active_ac(ac_id_missing)
        _write_test_file(
            self.test_root,
            "test_only_one_ac_covered.py",
            f"""\
            def test_covers_only_first_ac():
                # covers: {ac_id_covered}
                pass  # covers ac_id_covered but NOT ac_id_missing
            """,
        )

        verdict = verify_green_and_coverage(
            ac_ids=[ac_id_covered, ac_id_missing],
            test_root=self.test_root,
            ac_root=self.ac_root,
        )

        self.assertFalse(
            verdict["coverage_ok"],
            "coverage_ok must be False when any batch AC id lacks a covering test "
            "(BO-2400a-4).",
        )
        uncovered = verdict.get("uncovered_ac_ids", [])
        self.assertIn(
            ac_id_missing,
            uncovered,
            "The uncovered AC id must be listed in uncovered_ac_ids (BO-2400a-4).",
        )
        self.assertNotIn(
            ac_id_covered,
            uncovered,
            "The covered AC id must NOT be in uncovered_ac_ids.",
        )

    def test_ac4i_commit_refused_when_batch_tests_still_failing(self) -> None:
        # covers: BO-2400a-4-i
        """The gate returns green=False when batch tests are still failing after coder ran.

        Commit staging must NOT proceed when green=False.  The verdict must
        expose this clearly so the caller can refuse staging.

        The test fixture is a real .py file whose body fails (assert False).
        """
        ac_id = "BO-FL-GRN-004"
        self._write_active_ac(ac_id)
        _write_test_file(
            self.test_root,
            "test_still_fails_after_coder.py",
            f"""\
            def test_not_yet_passing():
                # covers: {ac_id}
                assert False, "coder did not implement this yet"
            """,
        )

        verdict = verify_green_and_coverage(
            ac_ids=[ac_id], test_root=self.test_root, ac_root=self.ac_root
        )

        self.assertFalse(
            verdict["green"],
            "verify_green_and_coverage must return green=False when batch tests still "
            "fail after the coder ran (BO-2400a-4-i).",
        )
        self.assertTrue(
            len(verdict.get("failing_tests", [])) > 0,
            "failing_tests must be non-empty when batch tests still fail.",
        )

    def test_ac4i_reports_failing_ac_ids(self) -> None:
        # covers: BO-2400a-4-i
        """The verdict must report the AC ids whose covering tests are still failing.

        The loop uses failing_tests to map back to AC ids so the operator sees
        which behaviors remain unmet.

        Two ACs: one passing, one failing.  The failing AC's id must appear in
        uncovered_ac_ids or be derivable from failing_tests.
        """
        ac_id_done = "BO-FL-GRN-005a"
        ac_id_notdone = "BO-FL-GRN-005b"
        self._write_active_ac(ac_id_done)
        self._write_active_ac(ac_id_notdone)
        _write_test_file(
            self.test_root,
            "test_partial_implementation.py",
            f"""\
            def test_first_ac_done():
                # covers: {ac_id_done}
                pass  # passes — this AC's work is done

            def test_second_ac_not_done():
                # covers: {ac_id_notdone}
                assert False, "second AC not yet implemented"
            """,
        )

        verdict = verify_green_and_coverage(
            ac_ids=[ac_id_done, ac_id_notdone],
            test_root=self.test_root,
            ac_root=self.ac_root,
        )

        self.assertFalse(
            verdict["green"],
            "green must be False when any batch test fails (BO-2400a-4-i).",
        )
        failing = verdict.get("failing_tests", [])
        self.assertTrue(
            len(failing) > 0,
            "failing_tests must be non-empty, listing which tests block commit staging.",
        )
        # The failing test function name must be traceable to the AC.
        any_failing_names = " ".join(str(f) for f in failing)
        self.assertIn(
            "test_second_ac_not_done",
            any_failing_names,
            "The failing_tests list must name the specific failing test so the "
            "operator can trace it to its AC (BO-2400a-4-i).",
        )

    def test_ac4_verdict_has_all_required_keys(self) -> None:
        # covers: BO-2400a-4
        """The verdict dict must contain green, coverage_ok, uncovered_ac_ids, failing_tests.

        To make this green, verify_green_and_coverage must return a dict with
        all four keys present regardless of the verdict outcome.
        """
        ac_id = "BO-FL-GRN-006"
        self._write_active_ac(ac_id)
        _write_test_file(
            self.test_root,
            "test_verdict_shape_check.py",
            f"""\
            def test_always_passes_for_shape_check():
                # covers: {ac_id}
                pass
            """,
        )

        verdict = verify_green_and_coverage(
            ac_ids=[ac_id], test_root=self.test_root, ac_root=self.ac_root
        )

        for key in ("green", "coverage_ok", "uncovered_ac_ids", "failing_tests"):
            self.assertIn(
                key,
                verdict,
                f"verify_green_and_coverage verdict must contain key '{key}' (BO-2400a-4).",
            )
        self.assertIsInstance(verdict["green"], bool, "green must be a bool.")
        self.assertIsInstance(verdict["coverage_ok"], bool, "coverage_ok must be a bool.")
        self.assertIsInstance(verdict["uncovered_ac_ids"], list, "uncovered_ac_ids must be a list.")
        self.assertIsInstance(verdict["failing_tests"], list, "failing_tests must be a list.")

    def test_ac4_both_green_and_coverage_required_for_staging(self) -> None:
        # covers: BO-2400a-4
        """Commit staging is gated on BOTH green AND coverage_ok — neither alone suffices.

        Scenario: tests pass (green=True) but one AC id has no covering test
        (coverage_ok=False).  Staging must NOT proceed.  The caller must
        check both flags and refuse unless both are True.

        To make this green, verify_green_and_coverage must correctly set both
        flags independently so the caller can evaluate the conjunction.
        """
        ac_id_covered = "BO-FL-GRN-007a"
        ac_id_uncovered = "BO-FL-GRN-007b"
        self._write_active_ac(ac_id_covered)
        self._write_active_ac(ac_id_uncovered)
        _write_test_file(
            self.test_root,
            "test_passes_but_missing_coverage.py",
            f"""\
            def test_passes_for_first_ac_only():
                # covers: {ac_id_covered}
                pass  # ac_id_uncovered has no covering test — staging must be refused
            """,
        )

        verdict = verify_green_and_coverage(
            ac_ids=[ac_id_covered, ac_id_uncovered],
            test_root=self.test_root,
            ac_root=self.ac_root,
        )

        # Tests pass → green=True; but one AC is uncovered → coverage_ok=False.
        # The caller must check BOTH to decide whether to stage.
        self.assertTrue(
            verdict["green"],
            "green must be True since all tests that exist do pass.",
        )
        self.assertFalse(
            verdict["coverage_ok"],
            "coverage_ok must be False when one AC id has no covering test — "
            "neither green alone nor coverage alone is sufficient for staging "
            "(BO-2400a-4).",
        )


if __name__ == "__main__":
    unittest.main()
