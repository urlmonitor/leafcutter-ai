"""
MODULE: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
GOAL: RED test stubs for a NEW fast_lane.py CLI subcommand, ``heavy_lane_gate``
    -- the DESIGN CHANGE (decided after the first cut of TQ-500f-3-ii landed
    the gate's decision logic inline in driveTicketPhases()) that moves the
    heavy lane's red-baseline decision OUT of build-feature.js / build-ticket.js
    (both already over the JS file-size limit) and INTO fast_lane.py itself,
    so each JS driver keeps only a thin dispatch + fail-closed parse of one
    JSON object this subcommand prints.

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-ii.yaml

PINNED CONTRACT (NOT yet implemented -- ``heavy_lane_gate`` is not a
recognised fast_lane.py subcommand today):

    python fast_lane.py heavy_lane_gate --source-ac <id-or-empty> \\
        --test-root <dir> --ac-root <dir>

Prints exactly one JSON object on stdout:

    * No / empty ``--source-ac``:
          {"gate_passed": true, "applicable": false,
           "outcome": "red-baseline reader not applicable: no source requirement",
           "verified": false}
      exit 0.
    * ``--source-ac`` with a declared (must_catch / angle:discrimination)
      newly-added covering test whose only red is an absence red:
          {"gate_passed": false, "applicable": true, "verified": false,
           "reason": "declared_test_refused_absence_only_red",
           ...every verify_red_baseline verdict field (red, green_at_baseline,
           inconclusive, preexisting, refused)}
      non-zero exit.
    * ``--source-ac`` with a proper (non-absence) red:
          {"gate_passed": true, "applicable": true, "verified": true, ...}
      exit 0.

NO SECOND READER: for the same ``--source-ac``/``--test-root``/``--ac-root``
inputs, ``heavy_lane_gate``'s own verdict (minus its wrapper keys
``applicable``/``verified``/``outcome``) equals ``verify_red_baseline``'s own
verdict called with the SAME ``--ac-root`` -- ``heavy_lane_gate`` wraps that
one existing reader, it never re-implements the absence/assertion
classification itself.

TODAY (unmodified code): ``heavy_lane_gate`` is not a recognised subcommand
at all -- every test below fails with argparse's ``error: argument
subcommand: invalid choice: 'heavy_lane_gate'`` (exit 2, empty stdout).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as fx  # noqa: E402


def _run_heavy_lane_gate(*, source_ac: str | None, test_root: Path, ac_root: Path) -> subprocess.CompletedProcess:
    argv = [
        sys.executable,
        str(fx.GATE_SCRIPT),
        "heavy_lane_gate",
        "--test-root",
        str(test_root),
        "--ac-root",
        str(ac_root),
    ]
    if source_ac is not None:
        argv.extend(["--source-ac", source_ac])
    return subprocess.run(argv, capture_output=True, text=True, timeout=120)


def _parse_stdout(proc: subprocess.CompletedProcess) -> dict:
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            "heavy_lane_gate must print exactly one parseable JSON object on "
            f"stdout: {exc}. exit={proc.returncode} stdout={proc.stdout!r} "
            f"stderr={proc.stderr!r}"
        ) from None


def test_heavy_lane_gate_with_no_source_ac_reports_not_applicable():
    # covers: TQ-500f-3-ii
    # angle: boundary
    """The empty edge of --source-ac: no source requirement to gate against.
    gate_passed is true (never blocks a ticket with nothing to verify),
    applicable is false, and the outcome names the exact decided phrase K3's
    workflow-level test also pins. Exit 0.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        work_dir, _base_sha = fx.make_worktree(tmp_root)
        ac_root = work_dir / "docs" / "acceptance-criteria"
        ac_root.mkdir(parents=True, exist_ok=True)

        proc = _run_heavy_lane_gate(source_ac=None, test_root=work_dir, ac_root=ac_root)
        verdict = _parse_stdout(proc)

        assert verdict.get("gate_passed") is True, f"verdict={verdict!r}"
        assert verdict.get("applicable") is False, f"verdict={verdict!r}"
        assert verdict.get("verified") is False, f"verdict={verdict!r}"
        assert (
            verdict.get("outcome")
            == "red-baseline reader not applicable: no source requirement"
        ), f"verdict={verdict!r}"
        assert verdict.get("interpreter") == sys.executable, f"verdict={verdict!r}"
        assert proc.returncode == 0, (
            f"exit code must be 0 (gate_passed=True) when there is no source "
            f"requirement to gate against; got {proc.returncode}, verdict={verdict!r}"
        )


def test_heavy_lane_gate_refuses_declared_absence_only_red():
    # covers: TQ-500f-3-ii
    # angle: failure
    """--source-ac names an AC with a declared (must_catch) covering test
    whose only red is absence: gate_passed is false, applicable/verified
    reflect a refused, unverified gate, and the reason names the refusal.
    Exit non-zero.
    """
    ac_id = "TQ-FIX-3II-GATE-REFUSE"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        work_dir, _base_sha = fx.make_worktree(tmp_root)
        ac_root = work_dir / "docs" / "acceptance-criteria"
        fx.write_ac_yaml(ac_root, ac_id, fx.t1_t2_t3_test_spec())
        test_root = work_dir / "tests"
        fx.write_t1_t2_t3_test_files(test_root, ac_id)

        proc = _run_heavy_lane_gate(source_ac=ac_id, test_root=work_dir, ac_root=ac_root)
        verdict = _parse_stdout(proc)

        assert verdict.get("gate_passed") is False, f"verdict={verdict!r}"
        assert verdict.get("applicable") is True, f"verdict={verdict!r}"
        assert verdict.get("verified") is False, f"verdict={verdict!r}"
        assert (
            verdict.get("reason") == "declared_test_refused_absence_only_red"
        ), f"verdict={verdict!r}"
        assert fx.find_by_name(verdict.get("refused"), fx.T1_NAME) is not None, (
            f"the wrapped verify_red_baseline verdict fields (e.g. 'refused') "
            f"must still be present on the heavy_lane_gate payload; verdict={verdict!r}"
        )
        assert proc.returncode != 0, (
            f"exit code must be non-zero when gate_passed is False; got "
            f"{proc.returncode}, verdict={verdict!r}"
        )


def test_heavy_lane_gate_passes_and_is_verified_for_proper_red():
    # covers: TQ-500f-3-ii
    # angle: criterion
    """--source-ac names an AC whose only newly-added covering test is a
    proper (non-absence) red: gate_passed is true, applicable AND verified
    are both true. Exit 0.
    """
    ac_id = "TQ-FIX-3II-GATE-PASS"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        work_dir, _base_sha = fx.make_worktree(tmp_root)
        ac_root = work_dir / "docs" / "acceptance-criteria"
        fx.write_ac_yaml(ac_root, ac_id, fx.t1_t2_t3_test_spec())
        test_root = work_dir / "tests"
        fx.write_t1_t2_t3_test_files(test_root, ac_id, include={fx.T2_NAME, fx.T3_NAME})

        proc = _run_heavy_lane_gate(source_ac=ac_id, test_root=work_dir, ac_root=ac_root)
        verdict = _parse_stdout(proc)

        assert verdict.get("gate_passed") is True, f"verdict={verdict!r}"
        assert verdict.get("applicable") is True, f"verdict={verdict!r}"
        assert verdict.get("verified") is True, f"verdict={verdict!r}"
        assert proc.returncode == 0, (
            f"exit code must be 0 when gate_passed is True; got "
            f"{proc.returncode}, verdict={verdict!r}"
        )


def test_heavy_lane_gate_verdict_equals_verify_red_baseline_no_second_reader():
    # covers: TQ-500f-3-ii
    # angle: seam
    """For the SAME --source-ac / --test-root / --ac-root inputs,
    heavy_lane_gate's verdict (minus its own applicable/verified/outcome
    wrapper keys) equals a direct verify_red_baseline --ac-root call's
    verdict -- heavy_lane_gate must WRAP the one existing reader, never
    re-implement the classification itself (no second reader).
    """
    ac_id = "TQ-FIX-3II-GATE-SEAM"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        work_dir, _base_sha = fx.make_worktree(tmp_root)
        ac_root = work_dir / "docs" / "acceptance-criteria"
        fx.write_ac_yaml(ac_root, ac_id, fx.t1_t2_t3_test_spec())
        test_root = work_dir / "tests"
        fx.write_t1_t2_t3_test_files(test_root, ac_id)

        gate_proc = _run_heavy_lane_gate(source_ac=ac_id, test_root=work_dir, ac_root=ac_root)
        gate_verdict = _parse_stdout(gate_proc)

        direct_proc = subprocess.run(
            [
                sys.executable,
                str(fx.GATE_SCRIPT),
                "verify_red_baseline",
                "--ac-ids",
                ac_id,
                "--test-root",
                str(work_dir),
                "--ac-root",
                str(ac_root),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        try:
            direct_verdict = json.loads(direct_proc.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"direct verify_red_baseline call did not print parseable JSON: {exc}. "
                f"stdout={direct_proc.stdout!r} stderr={direct_proc.stderr!r}"
            ) from None

        sys.path.insert(0, str(fx.GATE_SCRIPT.parent))
        from _fl_heavy_lane_gate import HEAVY_WRAPPER_KEYS as wrapper_only_keys  # noqa: E402

        gate_core = {k: v for k, v in gate_verdict.items() if k not in wrapper_only_keys}

        assert gate_core == direct_verdict, (
            "heavy_lane_gate must wrap verify_red_baseline's own verdict "
            "unchanged (no second reader) -- after stripping its own "
            f"applicable/verified/outcome wrapper keys, the remainder must equal "
            f"a direct verify_red_baseline --ac-root call's verdict for the SAME "
            f"inputs: heavy_lane_gate={gate_core!r} direct={direct_verdict!r}"
        )


def test_verify_red_baseline_refuses_when_pytest_not_importable():
    # covers: TQ-500f-3-ii
    # angle: failure
    """The launching interpreter cannot import pytest (the Windows-venv-vs-
    Store-python3 trap): verify_red_baseline must say so with
    reason "test_interpreter_unusable", carry the running sys.executable as
    ``interpreter``, and start no pytest process at all -- instead of running
    every test to an ERROR and reporting "no_red_outcome_among_new_tests".
    """
    import importlib.util
    from unittest import mock

    sys.path.insert(0, str(fx.GATE_SCRIPT.parent))
    import fast_lane  # noqa: E402

    real_find_spec = importlib.util.find_spec

    def _find_spec_without_pytest(name, *args, **kwargs):
        if name == "pytest":
            return None
        return real_find_spec(name, *args, **kwargs)

    ac_id = "TQ-FIX-3II-NOPYTEST"
    with tempfile.TemporaryDirectory() as tmp:
        work_dir, _base_sha = fx.make_worktree(Path(tmp))
        ac_root = work_dir / "docs" / "acceptance-criteria"
        fx.write_ac_yaml(ac_root, ac_id, fx.t1_t2_t3_test_spec())
        fx.write_t1_t2_t3_test_files(work_dir / "tests", ac_id)

        with mock.patch("importlib.util.find_spec", side_effect=_find_spec_without_pytest), \
                mock.patch.object(fast_lane, "_run_pytest_and_parse", return_value={}) as plain_runner, \
                mock.patch.object(
                    fast_lane, "_run_pytest_and_parse_with_kind", return_value=({}, {})
                ) as kind_runner:
            verdict = fast_lane.verify_red_baseline(
                ac_ids=[ac_id], test_root=work_dir, ac_root=ac_root
            )

        assert verdict.get("gate_passed") is False, f"verdict={verdict!r}"
        assert verdict.get("reason") == "test_interpreter_unusable", f"verdict={verdict!r}"
        assert verdict.get("interpreter") == sys.executable, f"verdict={verdict!r}"
        assert plain_runner.call_count == 0 and kind_runner.call_count == 0, (
            "no pytest process may be started once pytest is known to be "
            f"unimportable; plain={plain_runner.call_count} kind={kind_runner.call_count}"
        )


def test_real_gate_verdict_carries_launching_interpreter():
    # covers: TQ-500f-3-ii
    # angle: real_artifact
    """Run the real CLI as a subprocess against the real git fixture: the
    printed heavy_lane_gate verdict names the interpreter that launched it,
    so a halt can say which environment judged the tests.
    """
    ac_id = "TQ-FIX-3II-GATE-INTERP"
    with tempfile.TemporaryDirectory() as tmp:
        work_dir, _base_sha = fx.make_worktree(Path(tmp))
        ac_root = work_dir / "docs" / "acceptance-criteria"
        fx.write_ac_yaml(ac_root, ac_id, fx.t1_t2_t3_test_spec())
        fx.write_t1_t2_t3_test_files(work_dir / "tests", ac_id, include={fx.T2_NAME, fx.T3_NAME})

        proc = _run_heavy_lane_gate(source_ac=ac_id, test_root=work_dir, ac_root=ac_root)
        verdict = _parse_stdout(proc)

        assert verdict.get("interpreter") == sys.executable, (
            "the verdict must carry the interpreter that launched the gate "
            f"({sys.executable!r}); verdict={verdict!r}"
        )
