"""
MODULE: unit_tests/commit_guardian/test_acs_900d_4_retired_record_exemption.py
GOAL: RED gate tests for ACS-900d-4 -- a superseded record that names EXISTING
    successors is retired and is no longer held to the is-it-built-and-tested-now
    rules (covering test, test contract, unfinished children), while an active twin
    and a deprecated record still are.

Every scenario runs the real hooks as subprocesses against a throwaway git repo with
the records staged (check_done_proof.py in precommit / ci-changed / ci modes, and
check_ac_schema.py; source copies under templates/scripts/commit_guardian/). Nothing
here greps for a function call. The retired record is always judged next to a control:
the active twin (still refused) or the unpatched run (passes).

Discrimination tests (the active twin, the deprecated records) are EXPECTED to be green
on main: they pin what must NOT change. Named wrong versions caught: done-proof skipped
for every record; skipped for any record whose superseded_by field is merely present;
the predicate treating any non-active status as retired; a second, private copy of the
retired rule inside any one gate (the seam test).

DECISION HISTORY
- 2026-10-15 [test-writer/ACS-900d-4]: Initial RED authoring.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _acs_900d_4_fixtures as fx  # noqa: E402

X_ID = "RT-100a-1"
CHILD_ID = "RT-100a-1-i"
TAG_REASON = f"covers: {X_ID}"


def _retired_x() -> dict:
    return fx.retired_record(X_ID)


def _retired_pair() -> list[dict]:
    """X-1 retired at done, covering its own retired todo child (no tests, no contract)."""
    child = fx.retired_record(CHILD_ID, level="L3", work_status="todo", depends_on=[X_ID])
    return [fx.retired_record(X_ID, covered_by=[CHILD_ID]), child]


def _staged_repo(tmp_path: Path, name: str, records: list[dict]):
    repo = fx.make_repo(tmp_path / name)
    paths = fx.stage_scenario(repo, records)
    return repo, paths


def _assert_clean(label: str, proc) -> None:
    refusals = fx.done_proof_refusals(proc)
    assert proc.returncode == 0 and not refusals, f"{label} refused (exit {proc.returncode}): {fx.out(proc)!r}"


def test_retired_done_record_passes_staged_done_proof(tmp_path: Path) -> None:
    # covers: ACS-900d-4
    # angle: criterion
    """A staged retired record (superseded_by [AR-400c-1], done, no covers tag) is not refused pre-commit."""
    repo, _ = _staged_repo(tmp_path, "precommit", [_retired_x()])
    proc = fx.done_proof(repo)

    assert not fx.done_proof_refusals(proc).get(X_ID), f"retired record refused: {fx.out(proc)!r}"
    _assert_clean("pre-commit done-proof", proc)


def test_retired_done_record_passes_ci_changed_done_proof(tmp_path: Path) -> None:
    # covers: ACS-900d-4
    # angle: seam
    """The same record passes both CI paths, so the pre-commit and CI verdicts agree.

    ci-changed and ci read the store through _build_ac_status_map, a different producer
    than the pre-commit YAML read; all three verdicts are compared.
    """
    repo, _ = _staged_repo(tmp_path, "ci", [_retired_x()])
    results = fx.run_all_done_proof_paths(repo)

    for label, proc in results.items():
        _assert_clean(f"{label} done-proof", proc)


def test_retired_record_passes_every_forward_gate(tmp_path: Path) -> None:
    # covers: ACS-900d-4
    # angle: reachability
    """done-proof and the schema gate give no covering-test, test-contract or unfinished-children refusal.

    The pair puts X-1 (done, composite over a retired child) and X-1-i (todo, approved code,
    no contract) in one commit, so each of the three refusal kinds has something to refuse.
    """
    repo, _ = _staged_repo(tmp_path, "forward", _retired_pair())
    done = fx.done_proof(repo)
    schema = fx.schema_hook(repo)

    _assert_clean("done-proof", done)
    assert schema.returncode == 0, f"schema gate refused: {fx.out(schema)!r}"
    for ac_id in (X_ID, CHILD_ID):
        assert not fx.mentions(fx.out(schema), ac_id), f"schema gate names {ac_id}: {fx.out(schema)!r}"
    assert fx.TEST_CONTRACT_REFUSAL not in fx.out(schema)


def test_retired_record_work_status_unchanged_after_gates(tmp_path: Path) -> None:
    # covers: ACS-900d-4
    # angle: criterion
    """After the gates run the staged files are byte-identical and work_status still reads done."""
    repo, paths = _staged_repo(tmp_path, "unchanged", _retired_pair())
    before = {p: p.read_bytes() for p in paths}
    done = fx.done_proof(repo)
    schema = fx.schema_hook(repo)

    _assert_clean("done-proof", done)
    assert schema.returncode == 0, f"schema gate refused: {fx.out(schema)!r}"
    for path, content in before.items():
        assert path.read_bytes() == content, f"a gate rewrote {path.name}"
    assert "work_status: done" in paths[0].read_text(encoding="utf-8")


def test_active_twin_still_refused_for_missing_covering_test(tmp_path: Path) -> None:
    # covers: ACS-900d-4
    # angle: discrimination
    """Identical except status active and superseded_by null: refused with the covers-tag reason.

    Wrong versions caught: done-proof skipped for every record; skipped whenever a
    superseded_by key is present (the twin carries it, set to null).
    """
    twin = fx.active_twin(_retired_x())
    assert twin["superseded_by"] is None and "superseded_by" in twin
    repo, _ = _staged_repo(tmp_path, "twin", [twin])
    results = fx.run_all_done_proof_paths(repo)

    reason = fx.done_proof_refusals(results["precommit"]).get(X_ID, "")
    assert results["precommit"].returncode != 0 and TAG_REASON in reason, fx.out(results["precommit"])
    for label in ("ci_changed", "ci"):
        ci_reason = fx.done_proof_refusals(results[label]).get(X_ID, "")
        assert f"no linked test found for {X_ID}" in ci_reason, f"{label}: {fx.out(results[label])!r}"


def test_deprecated_record_without_successor_still_refused(tmp_path: Path) -> None:
    # covers: ACS-900d-4
    # angle: discrimination
    """status deprecated at done with no covers tag is refused, with or without superseded_by set.

    Wrong version caught: the predicate treats any non-active status as retired. The second
    row sets a valid successor on a deprecated record: deprecated is NEVER retired.
    """
    bare = fx.ac_record(X_ID, status="deprecated")
    with_successor = fx.ac_record(X_ID, status="deprecated", superseded_by=[fx.SUCCESSOR])
    for name, record in (("bare", bare), ("with_successor", with_successor)):
        repo, _ = _staged_repo(tmp_path, name, [record])
        proc = fx.done_proof(repo)
        reason = fx.done_proof_refusals(proc).get(X_ID, "")
        assert proc.returncode != 0 and TAG_REASON in reason, f"deprecated ({name}) not refused: {fx.out(proc)!r}"


def _assert_patched(label: str, proc) -> None:
    assert proc.returncode != fx.RUNNER_UNPATCHABLE and "RUNNER-CANNOT-PATCH" not in proc.stdout, (
        f"{label}: scripts/ac_store/ac_retirement.py does not exist, so there is no shared "
        f"predicate to patch: {proc.stdout!r}"
    )
    assert "RUNNER-PATCHED" in proc.stdout, f"{label}: the predicate was not patched: {fx.out(proc)!r}"


def _seam_done_proof(tmp_path: Path, runner: Path) -> None:
    control_repo, _ = _staged_repo(tmp_path, "seam_dp_control", [_retired_x()])
    for label, proc in fx.run_all_done_proof_paths(control_repo).items():
        _assert_clean(f"control {label}", proc)
    repo, _ = _staged_repo(tmp_path, "seam_dp", [_retired_x()])
    patched = fx.run_all_done_proof_paths(repo, runner=runner)
    for label, proc in patched.items():
        _assert_patched(f"done-proof {label}", proc)
        assert X_ID in fx.done_proof_refusals(proc), f"{label} ignored the patched predicate: {fx.out(proc)!r}"


def _seam_composite(tmp_path: Path, runner: Path) -> None:
    states = ("live_done", "live_done", "retired_todo")
    control_repo = fx.make_repo(tmp_path / "seam_comp_control")
    fx.composite_scenario(control_repo, states)
    for label, proc in fx.run_all_done_proof_paths(control_repo).items():
        _assert_clean(f"control composite {label}", proc)
    repo = fx.make_repo(tmp_path / "seam_comp")
    fx.composite_scenario(repo, states)
    patched = fx.run_all_done_proof_paths(repo, runner=runner)
    for label in ("precommit", "ci_changed"):
        _assert_patched(f"composite {label}", patched[label])
        reason = fx.done_proof_refusals(patched[label]).get(fx.PARENT_ID, "")
        assert fx.mentions(reason, fx.KIDS[2]), f"composite {label} did not consult the predicate: {reason!r}"


def _seam_test_contract(tmp_path: Path, runner: Path) -> None:
    record = fx.retired_record(CHILD_ID, level="L3", work_status="todo")
    control_repo, _ = _staged_repo(tmp_path, "seam_tc_control", [record])
    control = fx.schema_hook(control_repo)
    assert control.returncode == 0, f"control: retired todo record refused: {fx.out(control)!r}"
    repo, _ = _staged_repo(tmp_path, "seam_tc", [record])
    patched = fx.schema_hook(repo, runner=runner)
    _assert_patched("validate_test_contract", patched)
    assert patched.returncode != 0 and fx.TEST_CONTRACT_REFUSAL in fx.out(patched), (
        f"validate_test_contract ignored the patched predicate: {fx.out(patched)!r}"
    )


def test_single_predicate_definition_drives_all_gates(tmp_path: Path) -> None:
    # covers: ACS-900d-4
    # angle: seam
    """Patching the shared predicate to 'never retired' makes every gate refuse the retired records.

    Covers check_done_proof (pre-commit and both CI paths), the composite rollup (both
    paths) and validate_test_contract. Each gate is first run UNPATCHED as a control (it
    passes) and then through a runner that replaces ac_retirement.is_retired before the
    hook starts. A gate carrying its own copy of the rule would keep passing here.
    """
    runner = fx.seam_runner(tmp_path)
    _assert_patched("probe", fx.done_proof(fx.make_repo(tmp_path / "probe"), runner=runner))

    _seam_done_proof(tmp_path, runner)
    _seam_composite(tmp_path, runner)
    _seam_test_contract(tmp_path, runner)
