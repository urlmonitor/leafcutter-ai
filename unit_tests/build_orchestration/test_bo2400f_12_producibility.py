"""
MODULE: unit_tests/build_orchestration/test_bo2400f_12_producibility.py
GOAL: RED tests for BO-2400f-12 / BO-2400f-12-i / BO-2400f-12-ii — the
      producibility-verdict computation that a fast-lane run must consult,
      alongside the resolved connected build set, before it claims anything
      or dispatches the first build agent.

=== Target contract (does not exist yet — this is greenfield) ===

scripts/build_orchestration/fast_lane.py must gain:

  1. A pure function::

         def compute_producibility_verdict(
             ac_ids: list[str], *, ac_root: Path
         ) -> dict:

     returning ``{"producible": bool, "unproducible": [ {"ac_id", "declared_producer",
     "declared_proof", "reason"} , ... ]}``. An AC is unproducible when it
     positively declares a deliverable or proof obligation this lane's roster
     cannot satisfy — today that means ``test_required: false`` (declared_proof
     the roster cannot honour, since the roster proves work with a passing
     covering test only) OR an ``assigned_agent`` naming an agent outside the
     roster the lane actually dispatches (``python-coder`` from the Coder phase
     and ``test-writer`` from the Test Writer phase — and nothing else; notably
     NOT ``sql-coder`` or ``frontend-coder``, which only build-feature.js and
     build-ticket.js dispatch). Absence of either field is producible (BO-2400f-12-ii
     — the check is positive-declaration-only; an unannotated record is never
     refused). ``readiness``, ``priority``, ``req_status``, and ``status`` play
     no part in the decision (BO-2400f-12-ii — pointing at an AC is still the
     operator's go-ahead regardless of approval state).

     The function performs NO writes — it only reads AC YAML off disk — so a
     refusing run built on top of it never mutates the store (BO-2400f-12-i).

  2. A CLI subcommand ``check_producibility``::

         python3 fast_lane.py check_producibility --ac-ids <csv> --ac-root <dir>

     prints the verdict dict as JSON to stdout; exits 0 when producible is
     True, 1 otherwise (fail-closed, mirroring every other gate subcommand's
     exit-code convention in this module).

=== Red baseline ===

Every test below imports ``compute_producibility_verdict`` from
``scripts/build_orchestration/fast_lane.py`` (ImportError — the function does
not exist) or invokes the ``check_producibility`` CLI subcommand as a real
subprocess (non-zero exit / "invalid choice" argparse error — the subcommand
is not registered). Both are the intended RED state.

=== Fixture-authenticity mandate (BO-2500c / 2h.2) ===

All AC YAML fixtures are written via yaml.safe_dump (never a hand-typed YAML
literal), mirroring unit_tests/workflows/test_bo2600b_lane_scope_aiming.py and
unit_tests/build_orchestration/test_fast_lane_connected.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FAST_LANE_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
_FAST_LANE_PY = _FAST_LANE_MODULE_DIR / "fast_lane.py"


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str = "L2",
    work_status: str = "todo",
    readiness: str = "approved",
    test_required: bool | None = None,
    assigned_agent: str | None = "unset",
) -> Path:
    """Write a minimal, valid AC YAML using yaml.safe_dump (never hand-typed).

    ``assigned_agent="unset"`` (the sentinel default) means "omit the field
    entirely" — distinct from an explicit ``assigned_agent=None`` which is not
    used here since real AC records either name an agent or omit the key.
    ``test_required=None`` likewise omits the field (most of the store predates
    it); pass ``True``/``False`` to declare it explicitly.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": level,
        "status": "active",
        "work_status": work_status,
        "readiness": readiness,
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": [],
        "covered_by": [],
        "amended_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    if test_required is not None:
        data["test_required"] = test_required
    if assigned_agent != "unset":
        data["assigned_agent"] = assigned_agent
    path = subdir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _import_compute_producibility_verdict():
    """Import the target function, letting ImportError propagate as the RED signal."""
    if str(_FAST_LANE_MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(_FAST_LANE_MODULE_DIR))
    from fast_lane import compute_producibility_verdict  # noqa: PLC0415

    return compute_producibility_verdict


def _run_check_producibility_cli(ac_ids: list[str], ac_root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(_FAST_LANE_PY),
            "check_producibility",
            "--ac-ids",
            ",".join(ac_ids),
            "--ac-root",
            str(ac_root),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestComputeProducibilityVerdictUnit(unittest.TestCase):
    """Function-level RED tests — BO-2400f-12 / -ii."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "docs" / "acceptance-criteria"
        self.ac_root.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac12_declared_test_required_false_is_unproducible(self) -> None:
        # covers: BO-2400f-12
        """A member declaring test_required: false is unproducible — the
        roster proves work with a passing covering test only, and this
        member has declared it cannot be proved that way.
        """
        _write_ac(self.ac_root, "FLT-950a", test_required=False)
        compute_producibility_verdict = _import_compute_producibility_verdict()

        verdict = compute_producibility_verdict(["FLT-950a"], ac_root=self.ac_root)

        self.assertFalse(
            verdict["producible"],
            f"A test_required: false member must make the verdict unproducible. Got: {verdict}",
        )
        ids = [entry["ac_id"] for entry in verdict["unproducible"]]
        self.assertIn("FLT-950a", ids, f"FLT-950a must be named in unproducible. Got: {verdict}")

    def test_ac12_declared_producer_outside_roster_is_unproducible(self) -> None:
        # covers: BO-2400f-12
        """A member whose assigned_agent names an agent outside the roster
        (python-coder, test-writer) is unproducible.
        """
        _write_ac(self.ac_root, "FLT-950b", assigned_agent="documentation-expert")
        compute_producibility_verdict = _import_compute_producibility_verdict()

        verdict = compute_producibility_verdict(["FLT-950b"], ac_root=self.ac_root)

        self.assertFalse(verdict["producible"], f"Got: {verdict}")
        entry = next((e for e in verdict["unproducible"] if e["ac_id"] == "FLT-950b"), None)
        self.assertIsNotNone(entry, f"FLT-950b must be named in unproducible. Got: {verdict}")
        self.assertEqual(entry.get("declared_producer"), "documentation-expert")

    def test_ac12_roster_excludes_agents_this_lane_never_dispatches(self) -> None:
        # covers: BO-2400f-12
        """sql-coder and frontend-coder are unproducible; test-writer is not.

        Regression pin for the defect pr-reviewer blocked on the first build of
        this criterion: the roster shipped as
        {python-coder, sql-coder, frontend-coder}, but fast-lane-ship.js
        dispatches neither sql-coder nor frontend-coder from any phase — every
        Coder-phase dispatch hardcodes python-coder. That made the guard judge
        29 real not-done frontend-coder records producible and hand them to the
        wrong agent, which is precisely the late failure this criterion exists
        to pre-empt.

        test-writer is asserted producible in the same test on purpose: the
        cheap over-correction is to narrow the roster to python-coder alone,
        which would start refusing the 41 not-done test-writer records the Test
        Writer phase can genuinely produce. The roster must track the
        dispatches — both directions.
        """
        for agent in ("sql-coder", "frontend-coder"):
            with self.subTest(assigned_agent=agent):
                ac_id = f"FLT-951-{agent}"
                _write_ac(self.ac_root, ac_id, assigned_agent=agent)
                compute_producibility_verdict = _import_compute_producibility_verdict()

                verdict = compute_producibility_verdict([ac_id], ac_root=self.ac_root)

                self.assertFalse(
                    verdict["producible"],
                    f"{agent} is dispatched by no phase of this lane, so a member "
                    f"declaring it must be unproducible. Got: {verdict}",
                )
                entry = next(
                    (e for e in verdict["unproducible"] if e["ac_id"] == ac_id), None
                )
                self.assertIsNotNone(entry, f"{ac_id} must be named. Got: {verdict}")
                self.assertEqual(entry.get("declared_producer"), agent)

        _write_ac(self.ac_root, "FLT-951-test-writer", assigned_agent="test-writer")
        compute_producibility_verdict = _import_compute_producibility_verdict()

        verdict = compute_producibility_verdict(
            ["FLT-951-test-writer"], ac_root=self.ac_root
        )

        self.assertTrue(
            verdict["producible"],
            "The Test Writer phase really does dispatch test-writer, so a member "
            f"declaring it must NOT be refused. Got: {verdict}",
        )

        # Same assertion through the deployed CLI, in a fresh process. The
        # in-process call above imports from the source tree; the workflow only
        # ever reaches this logic via the subprocess boundary, so prove the
        # roster is right on the path the lane actually uses.
        proc = _run_check_producibility_cli(
            ["FLT-951-frontend-coder", "FLT-951-test-writer"], self.ac_root
        )
        # Exit 1 IS the contract for an unproducible verdict ("Exits 0 when
        # producible, 1 otherwise (fail-closed)") — not a crash. Assert it
        # explicitly so a future change that starts exiting 0 on a refusal,
        # which the workflow's plain-falsy read would take as "proceed", fails
        # here instead of silently re-opening the gate.
        self.assertEqual(
            proc.returncode,
            1,
            f"An unproducible verdict must exit 1. stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        cli_verdict = json.loads(proc.stdout)
        self.assertFalse(cli_verdict["producible"], f"Got: {cli_verdict}")
        named = {e["ac_id"] for e in cli_verdict["unproducible"]}
        self.assertEqual(
            named,
            {"FLT-951-frontend-coder"},
            "The CLI must refuse exactly the frontend-coder member and leave the "
            f"test-writer member alone. Got: {cli_verdict}",
        )

    def test_ac12_ii_undeclared_member_defaults_to_producible(self) -> None:
        # covers: BO-2400f-12-ii
        """A member with neither test_required nor assigned_agent declared is
        producible — silence is not a declaration, and defaulting to
        unproducible would refuse most of the store (87+ records predate
        these fields entirely).
        """
        _write_ac(self.ac_root, "FLT-950c")  # no test_required, no assigned_agent
        compute_producibility_verdict = _import_compute_producibility_verdict()

        verdict = compute_producibility_verdict(["FLT-950c"], ac_root=self.ac_root)

        self.assertTrue(verdict["producible"], f"An undeclared member must default producible. Got: {verdict}")
        self.assertEqual(verdict["unproducible"], [])

    def test_ac12_ii_ordinary_code_member_with_test_required_true_is_producible(self) -> None:
        # covers: BO-2400f-12-ii
        """A member explicitly declaring test_required: true is producible —
        this is exactly the deliverable the roster proves.
        """
        _write_ac(self.ac_root, "FLT-950d", test_required=True, assigned_agent="python-coder")
        compute_producibility_verdict = _import_compute_producibility_verdict()

        verdict = compute_producibility_verdict(["FLT-950d"], ac_root=self.ac_root)

        self.assertTrue(verdict["producible"], f"Got: {verdict}")

    def test_ac12_ii_readiness_and_priority_never_read(self) -> None:
        # covers: BO-2400f-12-ii
        """A draft-readiness, low-priority, ordinary code member is NOT
        refused — readiness/priority must play no part in the decision
        (BO-2400f-2 makes selection readiness-agnostic; this guard must not
        quietly reintroduce an approval gate under a new name).
        """
        subdir = self.ac_root / "test-component"
        subdir.mkdir(parents=True, exist_ok=True)
        data = {
            "id": "FLT-950e",
            "title": "Draft readiness ordinary code AC",
            "component": "build-orchestration",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "readiness": "draft",
            "req_status": "draft",
            "priority": "low",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": [],
        }
        (subdir / "FLT-950e.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        compute_producibility_verdict = _import_compute_producibility_verdict()

        verdict = compute_producibility_verdict(["FLT-950e"], ac_root=self.ac_root)

        self.assertTrue(
            verdict["producible"],
            f"readiness/priority must never cause a refusal. Got: {verdict}",
        )

    def test_ac12_mixed_set_names_only_the_unproducible_member(self) -> None:
        # covers: BO-2400f-12
        """A set of three members with exactly one unproducible does not widen
        the refusal to the other two — they are absent from unproducible.
        """
        _write_ac(self.ac_root, "FLT-950f")
        _write_ac(self.ac_root, "FLT-950g", test_required=False)
        _write_ac(self.ac_root, "FLT-950h")
        compute_producibility_verdict = _import_compute_producibility_verdict()

        verdict = compute_producibility_verdict(
            ["FLT-950f", "FLT-950g", "FLT-950h"], ac_root=self.ac_root
        )

        self.assertFalse(verdict["producible"])
        ids = [entry["ac_id"] for entry in verdict["unproducible"]]
        self.assertEqual(
            ids, ["FLT-950g"], f"Only FLT-950g should be named unproducible. Got: {verdict}"
        )


class TestComputeProducibilityVerdictIsInert(unittest.TestCase):
    """BO-2400f-12-i: computing the verdict must never mutate the store."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "docs" / "acceptance-criteria"
        self.ac_root.mkdir(parents=True)
        self.path = _write_ac(self.ac_root, "FLT-951a", test_required=False)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac12_i_computing_the_verdict_leaves_the_file_byte_identical(self) -> None:
        # covers: BO-2400f-12-i
        """Reading a record to decide producibility must not write to it —
        work_status and every other byte must be unchanged afterwards."""
        before = _read_bytes(self.path)
        compute_producibility_verdict = _import_compute_producibility_verdict()

        compute_producibility_verdict(["FLT-951a"], ac_root=self.ac_root)

        after = _read_bytes(self.path)
        self.assertEqual(
            before, after, "compute_producibility_verdict must not write to the AC YAML store."
        )

    def test_ac12_i_repeated_calls_are_inert_and_deterministic(self) -> None:
        # covers: BO-2400f-12-i
        """Calling the verdict twice against the same store yields the same
        verdict both times and leaves the file byte-identical after each
        call — a refusal is not a state transition."""
        compute_producibility_verdict = _import_compute_producibility_verdict()
        before = _read_bytes(self.path)

        first = compute_producibility_verdict(["FLT-951a"], ac_root=self.ac_root)
        after_first = _read_bytes(self.path)
        second = compute_producibility_verdict(["FLT-951a"], ac_root=self.ac_root)
        after_second = _read_bytes(self.path)

        self.assertEqual(first, second, "Two calls against an unchanged store must agree.")
        self.assertEqual(before, after_first)
        self.assertEqual(before, after_second)


class TestCheckProducibilityCliRealSubprocess(unittest.TestCase):
    """Real-subprocess (real-artifact) tests for the check_producibility CLI —
    BO-2400f-12's mandatory real-artifact evidence."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "docs" / "acceptance-criteria"
        self.ac_root.mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_resolver_reports_unproducible_members_on_the_real_store(self) -> None:
        # covers: BO-2400f-12
        """Run check_producibility as a REAL subprocess against an on-disk
        fixture store written with yaml.safe_dump (never a hand-built dict
        stubbing the CLI). The unproducible member's declared producer and
        proof obligation must be present in stdout's JSON verdict, and the
        exit code must be non-zero (fail-closed).
        """
        _write_ac(self.ac_root, "FLT-952a", test_required=False, assigned_agent="llm-expert")
        _write_ac(self.ac_root, "FLT-952b")

        proc = _run_check_producibility_cli(["FLT-952a", "FLT-952b"], self.ac_root)

        self.assertNotEqual(
            proc.returncode,
            0,
            f"check_producibility must exit non-zero when the set is unproducible. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        try:
            verdict = json.loads(proc.stdout.strip())
        except (json.JSONDecodeError, ValueError):
            self.fail(
                f"check_producibility must print a JSON verdict to stdout. Got stdout={proc.stdout!r} "
                f"stderr={proc.stderr!r}"
            )
        self.assertFalse(verdict.get("producible"))
        entry = next((e for e in verdict.get("unproducible", []) if e.get("ac_id") == "FLT-952a"), None)
        self.assertIsNotNone(
            entry, f"FLT-952a must be named in the real subprocess's unproducible list. Got: {verdict}"
        )
        self.assertEqual(entry.get("declared_producer"), "llm-expert")

    def test_undeclared_members_default_to_producible_real_subprocess(self) -> None:
        # covers: BO-2400f-12-ii
        """Against a real on-disk store of records carrying neither a stated
        proof obligation nor a stated producer, the resolver's verdict lists
        no unproducible members and exits 0."""
        _write_ac(self.ac_root, "FLT-953a")
        _write_ac(self.ac_root, "FLT-953b")

        proc = _run_check_producibility_cli(["FLT-953a", "FLT-953b"], self.ac_root)

        self.assertEqual(
            proc.returncode,
            0,
            f"An all-undeclared set must be producible (exit 0). stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )
        verdict = json.loads(proc.stdout.strip())
        self.assertTrue(verdict.get("producible"))
        self.assertEqual(verdict.get("unproducible"), [])


if __name__ == "__main__":
    unittest.main()
