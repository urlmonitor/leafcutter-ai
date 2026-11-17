"""
MODULE: unit_tests/commit_guardian/test_acs_900d_4_v_first_real_retirement.py
GOAL: RED real-artifact tests for ACS-900d-4-v -- the first real retirement. The real
    INF-600g-3 and INF-600g-3-i records (specifying the advisory skills_invoked
    cross-reference that AR-400c-1 deleted) become status superseded_by with
    superseded_by [AR-400c-1], and every AC-store gate passes with the records otherwise
    exactly as they sit on main.

FIXTURE AUTHENTICITY: no record is hand-authored. The whole real INF-600 folder (so
INF-600g-1 and INF-600g-2 resolve) and the real AR-400c-1 are copied BYTE FOR BYTE into a
throwaway git repo's store. The ONLY edit is the two-field retirement (status and
superseded_by) applied to the raw bytes of INF-600g-3 and INF-600g-3-i, which are then
staged together with their parent INF-600g. INF-600g is staged as an unchanged file by
keeping it out of the base commit (a file identical to HEAD cannot be staged).

GATES ('every AC-store commit gate'): check_done_proof.py (pre-commit and ci-changed),
check_ac_schema.py, check_ac_parent_covered_by.py, check_ac_limits.py and
scripts/ac_store/validate_ac_schema.py, each a fresh subprocess. These hooks read the index
and ignore argv, so a clean exit proves nothing alone: the control test stages deliberately
broken copies and requires the hooks to refuse them. check_ac_limits.py has no control (its
only refusal is a child-count cap that these records cannot reach).

DEPLOYED LAYOUT: one test runs check_done_proof.py and check_ac_schema.py from the
session-shared reference layout (@pytest.mark.shared_layout_reader; no build.py of its own),
which catches a predicate module missing from the build deploy list.

DECISION HISTORY
- 2026-10-15 [test-writer/ACS-900d-4-v]: Initial RED authoring.
"""
from __future__ import annotations

import filecmp
import re
import shutil
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _acs_900d_4_fixtures as fx  # noqa: E402

INF_REL = Path("docs/acceptance-criteria/infrastructure/INF-600-self-describing-agents")
AR_REL = Path("docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400c-1.yaml")
REAL_INF = fx.REPO_ROOT / INF_REL
REAL_AR = fx.REPO_ROOT / AR_REL
PARENT, MIDDLE, LEAF = "INF-600g", "INF-600g-3", "INF-600g-3-i"
IDS = (PARENT, MIDDLE, LEAF)


def _retire_bytes(raw: bytes) -> bytes:
    """The two-field retirement edit, applied to the record's raw bytes."""
    raw, n_status = re.subn(rb"(?m)^status: active$", b"status: superseded_by", raw)
    successor = f"superseded_by: [{fx.SUCCESSOR}]".encode()
    raw, n_by = re.subn(rb"(?m)^superseded_by: null$", successor, raw)
    assert (n_status, n_by) == (1, 1), f"unexpected record shape: status x{n_status}, superseded_by x{n_by}"
    return raw


def _unretire_bytes(raw: bytes) -> bytes:
    """Undo the two-field edit if the real record already carries it (it does once merged)."""
    raw = re.sub(rb"(?m)^status: superseded_by$", b"status: active", raw)
    return re.sub(rb"(?m)^superseded_by: \[" + fx.SUCCESSOR.encode() + rb"\]$", b"superseded_by: null", raw)


def _copy_real_store(root: Path) -> Path:
    """A repo whose store holds the real INF-600 folder and AR-400c-1, byte for byte.

    INF-600g-3 and -3-i are put back in their pre-retirement shape, so the staged
    change is exactly the two-field edit whether or not the real store is retired.
    """
    repo = fx.make_repo(root)
    shutil.copytree(REAL_INF, repo / INF_REL, dirs_exist_ok=True)
    (repo / AR_REL).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REAL_AR, repo / AR_REL)
    for ac_id in (MIDDLE, LEAF):
        path = _path(repo, ac_id)
        path.write_bytes(_unretire_bytes(path.read_bytes()))
    return repo


def _path(repo: Path, ac_id: str) -> Path:
    return repo / INF_REL / f"{ac_id}.yaml"


def _retirement_repo(tmp_path: Path, name: str):
    """Real store, with INF-600g-3 and -3-i retired and staged beside INF-600g."""
    repo = _copy_real_store(tmp_path / name)
    fx.commit_base(repo, exclude=(INF_REL / f"{PARENT}.yaml",))
    staged = [_path(repo, i) for i in IDS]
    for path in staged[1:]:
        path.write_bytes(_retire_bytes(path.read_bytes()))
    fx.stage(repo, *staged)
    return repo, staged


def _rewrite(path: Path, old: bytes, new: bytes) -> None:
    raw = path.read_bytes()
    assert old in raw, f"{path.name} does not contain {old!r}"
    path.write_bytes(raw.replace(old, new, 1))


def _assert_copies_identical(repo: Path) -> None:
    """Every copied file equals the real one, except the two records edited on purpose."""
    edited = {f"{MIDDLE}.yaml", f"{LEAF}.yaml"}
    for real in sorted(REAL_INF.glob("*.yaml")):
        copy = repo / INF_REL / real.name
        if real.name in edited:
            continue
        assert filecmp.cmp(real, copy, shallow=False), f"{real.name} differs from the real record"
    assert filecmp.cmp(REAL_AR, repo / AR_REL, shallow=False), "AR-400c-1 differs from the real record"


def _gate_results(repo: Path, staged: list[Path], hooks_dir: Path = fx.TEMPLATE_HOOKS, *, full: bool = True) -> dict:
    """Run the gates over the staged set; ci-changed runs after the staged set is committed."""
    results = {
        "check_done_proof (pre-commit)": fx.done_proof(repo, hooks_dir=hooks_dir),
        "check_ac_schema": fx.schema_hook(repo, hooks_dir=hooks_dir),
    }
    if full:
        results["check_ac_parent_covered_by"] = fx.parent_hook(repo, hooks_dir=hooks_dir)
        results["check_ac_limits"] = fx.limits_hook(repo, hooks_dir=hooks_dir)
        results["validate_ac_schema"] = fx.validate_schema(repo, *staged)
        fx.commit_staged(repo)
        results["check_done_proof (ci-changed)"] = fx.done_proof(repo, "ci-changed", base="HEAD~1")
    return results


def _assert_all_pass(results: dict) -> None:
    for gate, proc in results.items():
        text = fx.out(proc)
        assert proc.returncode == 0, f"{gate} refused the real retirement (exit {proc.returncode}): {text!r}"
        assert not fx.done_proof_refusals(proc), f"{gate} named a record: {text!r}"


def test_real_inf_600g_3_retirement_passes_every_ac_store_gate(tmp_path: Path) -> None:
    # covers: ACS-900d-4-v
    # angle: real_artifact
    """The real INF-600g, -3 and -3-i, retired with only the two-field edit, pass every gate."""
    repo, staged = _retirement_repo(tmp_path, "real")
    _assert_copies_identical(repo)

    _assert_all_pass(_gate_results(repo, staged))


def _deployed_hooks(layout: Path) -> Path:
    candidates = [layout / "scripts" / "commit_guardian", layout / ".leafcutter" / "scripts" / "commit_guardian"]
    found = next((c for c in candidates if (c / "check_done_proof.py").is_file()), None)
    assert found is not None, f"check_done_proof.py is not deployed under {layout}"
    return found


@pytest.mark.shared_layout_reader
def test_real_retirement_passes_in_deployed_layout(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: ACS-900d-4-v
    # angle: deployed
    """The same staged set passes check_done_proof.py and check_ac_schema.py run from the deployed layout.

    A predicate module missing from the build deploy list fails here, not in the source-tree run.
    """
    hooks = _deployed_hooks(shared_reference_layout)
    repo, staged = _retirement_repo(tmp_path, "deployed")

    results = _gate_results(repo, staged, hooks_dir=hooks, full=False)

    assert (hooks / "check_ac_schema.py").is_file(), "check_ac_schema.py is not deployed"
    _assert_all_pass(results)


def test_real_retirement_needs_no_test_contract_tag_or_field_edit(tmp_path: Path) -> None:
    # covers: ACS-900d-4-v
    # angle: criterion
    """After the gates pass, both records equal the edited copies; no covers tag, contract or field edit."""
    repo, staged = _retirement_repo(tmp_path, "untouched")
    edited = {p: p.read_bytes() for p in staged[1:]}

    _assert_all_pass(_gate_results(repo, staged, full=False))

    for path, content in edited.items():
        assert path.read_bytes() == content, f"a gate rewrote {path.name}"
        record = yaml.safe_load(content)
        assert (record["readiness"], record["change_target"], record["work_status"]) == ("approved", "code", "done")
        assert "test_spec" not in record and "test_required" not in record, f"{path.name} gained a test contract"
    tagged = [
        p for p in repo.rglob("*") if p.suffix in {".py", ".ts", ".tsx"} and ".git" not in p.parts
        and re.search(r"covers:\s*INF-600g-3", p.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert not tagged, f"a covers tag naming a retired record exists: {tagged}"


def _control_repo(tmp_path: Path, name: str, *, break_leaf: bool = False, break_parent: bool = False):
    """Real store; INF-600g-3-i staged UNretired (done, active), optionally with a broken copy."""
    repo = _copy_real_store(tmp_path / name)
    leaf, middle = _path(repo, LEAF), _path(repo, MIDDLE)
    fx.commit_base(repo, exclude=(INF_REL / f"{LEAF}.yaml",))
    staged = [leaf]
    if break_leaf:
        _rewrite(leaf, b"work_status: done", b"work_status: finished")
    if break_parent:
        _retire_leaf = _retire_bytes(leaf.read_bytes())
        leaf.write_bytes(_retire_leaf)
        _rewrite(middle, b"covered_by: [INF-600g-3-i]", b"covered_by: []")
        staged.append(middle)
    fx.stage(repo, *staged)
    return repo, staged


def test_gates_inspected_the_staged_inf_records(tmp_path: Path) -> None:
    # covers: ACS-900d-4-v
    # angle: reachability
    """Control runs: deliberately broken staged copies are refused, so the clean pass is not a no-op.

    Wrong version caught: a hook that reads a different index or path and inspects nothing.
    Done-proof: INF-600g-3-i left active at done with no covers tag. Schema gates: a copy with
    work_status 'finished'. Parent link: a retired -3-i whose parent -3 no longer lists it.
    """
    repo, _ = _control_repo(tmp_path, "ctl_done_proof")
    done = fx.done_proof(repo)
    assert LEAF in fx.done_proof_refusals(done) and done.returncode != 0, (
        f"done-proof did not refuse the unretired {LEAF}: {fx.out(done)!r}"
    )

    repo, staged = _control_repo(tmp_path, "ctl_schema", break_leaf=True)
    schema, ci_schema = fx.schema_hook(repo), fx.validate_schema(repo, *staged)
    assert schema.returncode != 0 and fx.mentions(fx.out(schema), LEAF), fx.out(schema)
    assert ci_schema.returncode != 0 and "'finished'" in fx.out(ci_schema), fx.out(ci_schema)

    repo, _ = _control_repo(tmp_path, "ctl_parent", break_parent=True)
    parent = fx.parent_hook(repo)
    assert parent.returncode != 0 and fx.mentions(fx.out(parent), LEAF), (
        f"parent covered_by gate did not inspect the staged records: {fx.out(parent)!r}"
    )
