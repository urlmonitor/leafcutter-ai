"""
MODULE: test_bp_1500d_4
AC: BP-1500d-4 -- "A check that finds no readable record says so, instead of
    returning the all-clear it returns when nothing is wrong"

Expected RED at authoring time: both deployed drift checks print a WARNING when
the record is missing and then return 0 -- byte-identical to their all-clear.
Every run is a subprocess of the DEPLOYED copy inside a real out-of-package
install built by the shared BP-1500d-1 harness (no second harness).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from ._bp1500d1_harness import REAL_PACKAGE_ROOT, HarnessBuild, build_out_of_package_harness, probe_child_sys_path
from ._bp1500d2_support import (
    MANIFEST_NAME,
    copy_project,
    load_record,
    new_scratch,
    scrubbed_env,
)

CHECKS = ["check_build_drift.py", "check_output_drift.py"]
_DEPLOYED = Path(".leafcutter/scripts/commit_guardian")


@pytest.fixture(scope="module")
def built() -> HarnessBuild:
    hb = build_out_of_package_harness()
    assert hb.proc.returncode == 0, hb.proc.stderr[-500:]
    yield hb
    hb.cleanup()


@pytest.fixture()
def project(built: HarnessBuild):
    s = new_scratch("bp1500d4_")
    proj = copy_project(built, s / "proj")
    # Keep the producing package beside the copy (same relative position), so
    # the good install is a genuine all-clear; freshness is not this AC's verdict.
    shutil.copytree(built.package_dir, s / built.package_dir.name)
    yield proj
    shutil.rmtree(s, ignore_errors=True)


def run_check(project: Path, name: str, via_runner: bool = False) -> tuple[int, str]:
    """Run the DEPLOYED check as a subprocess from inside the project."""
    env = scrubbed_env()
    sys_path = probe_child_sys_path(project, env)
    package = str(REAL_PACKAGE_ROOT.resolve()).lower()
    leaked = [p for p in sys_path if p and str(Path(p).resolve()).lower().startswith(package)]
    assert not leaked, f"child can see the package checkout: {leaked}"
    assert not str(Path(project).resolve()).lower().startswith(package)
    script = project / _DEPLOYED / name
    argv = [sys.executable, str(script)]
    if via_runner:
        argv = [sys.executable, str(project / _DEPLOYED / "run_hook.py"), str(script)]
    p = subprocess.run(argv, cwd=str(project), env=env, capture_output=True, text=True, timeout=180, check=False)
    return p.returncode, p.stdout + p.stderr


def _could_not_read(out: str) -> bool:
    return "could not read" in out.lower()


@pytest.mark.parametrize("name", CHECKS)
def test_bp_1500d_4_check_reports_could_not_read_and_names_the_project_and_the_record_when_none_is_present(
    project: Path, name: str
) -> None:
    # covers: BP-1500d-4
    # angle: criterion
    rec = project / MANIFEST_NAME
    rec.unlink()
    rc_absent, out_absent = run_check(project, name)
    assert _could_not_read(out_absent), out_absent[-800:]
    assert str(project) in out_absent or project.as_posix() in out_absent, "must name the project"
    assert MANIFEST_NAME in out_absent, "must name the record file"
    assert "drifted=" not in out_absent, "a could-not-read report must not carry a drift verdict"

    rec.write_text('{"output_mappings": {"truncated', encoding="utf-8")  # present, unreadable
    rc_bad, out_bad = run_check(project, name)
    assert _could_not_read(out_bad), out_bad[-800:]
    assert MANIFEST_NAME in out_bad and "drifted=" not in out_bad
    assert out_bad != out_absent, "absent and present-but-unreadable must be distinguishable"
    assert rc_bad != 0, "a malformed record must not fall through to the all-clear"


@pytest.mark.parametrize("name", CHECKS)
def test_bp_1500d_4_the_could_not_read_verdict_is_distinguishable_from_the_all_clear_to_an_automated_caller(
    project: Path, name: str
) -> None:
    # covers: BP-1500d-4
    # angle: seam
    rc_clear, out_clear = run_check(project, name)
    assert rc_clear == 0 and not _could_not_read(out_clear), out_clear[-500:]
    (project / MANIFEST_NAME).unlink()
    rc_none, out_none = run_check(project, name)
    assert rc_none != rc_clear, (
        f"{name}: exit status {rc_none} is identical to the all-clear -- an automated caller cannot tell them apart"
    )


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


@pytest.mark.parametrize("name", CHECKS)
def test_bp_1500d_4_the_deployed_copy_of_each_check_produces_the_new_verdict_through_its_real_invocation_surface(
    project: Path, name: str
) -> None:
    # covers: BP-1500d-4
    # angle: reachability
    # Production entry: the hook runner the pre-commit stanza invokes, on the deployed copy.
    rc_clear, _ = run_check(project, name, via_runner=True)
    assert rc_clear == 0
    (project / MANIFEST_NAME).unlink()
    rc_none, out = run_check(project, name, via_runner=True)
    assert rc_none != 0 and _could_not_read(out), (rc_none, out[-600:])

    # Consumption half, parsed as data: the registered hook runs this script
    # through the runner with no masking, and no CI step swallows its status.
    cfg = yaml.safe_load((REAL_PACKAGE_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = [h for r in cfg["repos"] for h in r["hooks"] if name in h.get("entry", "")]
    assert len(hooks) == 1, hooks
    entry = hooks[0]["entry"]
    assert "run_hook.py" in entry and not any(t in entry for t in ("||", "|", ";", "&&"))
    for wf in (REAL_PACKAGE_ROOT / ".github" / "workflows").glob("*.yml"):
        doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
        for step in (d for d in _walk(doc) if "run" in d or "uses" in d):
            text = json.dumps(step)
            if name in text or hooks[0]["id"] in text:
                assert not step.get("continue-on-error"), f"{wf.name}: step masks the verdict"
                assert "|| true" not in str(step.get("run", ""))


@pytest.mark.parametrize("name", CHECKS)
def test_bp_1500d_4_three_run_control_remove_substitute_restore_changes_the_verdict_each_time(
    project: Path, name: str
) -> None:
    # covers: BP-1500d-4
    # angle: failure
    rec = project / MANIFEST_NAME
    good = rec.read_bytes()

    rc1, out1 = run_check(project, name)  # (1) good install
    assert rc1 == 0 and not _could_not_read(out1)

    rec.unlink()  # (2) removed
    rc2, out2 = run_check(project, name)
    assert rc2 != rc1 and _could_not_read(out2), out2[-500:]

    rec.write_bytes(good)  # (3) restored
    rc3, out3 = run_check(project, name)
    assert rc3 == rc1 and not _could_not_read(out3)

    # (4) substitute record keyed to a location it is not read from: absolute
    # keys under a folder that does not exist, so none of them resolves here.
    record = json.loads(good)
    elsewhere = (project.parent / "written-elsewhere").resolve()
    record["output_mappings"] = {(elsewhere / k).as_posix(): v for k, v in record["output_mappings"].items()}
    rec.write_text(json.dumps(record, indent=2), encoding="utf-8")
    assert rec.read_bytes() != good
    rc4, out4 = run_check(project, name)
    assert rc4 != rc1 and _could_not_read(out4), out4[-500:]

    rec.write_bytes(good)  # final restore
    rc5, out5 = run_check(project, name)
    assert rc5 == rc1 and not _could_not_read(out5)


def test_bp_1500d_4_the_could_not_read_verdict_makes_no_judgement_about_whether_the_install_has_fallen_behind(
    project: Path,
) -> None:
    # covers: BP-1500d-4
    # angle: deployed
    # (a) no readable record: could-not-read, and no drift/freshness claim.
    rec = project / MANIFEST_NAME
    good = rec.read_bytes()
    rec.unlink()
    for name in CHECKS:
        rc, out = run_check(project, name)
        assert _could_not_read(out) and rc != 0, (name, rc, out[-400:])
        assert "drifted=" not in out and "stale" not in out.lower() and "behind" not in out.lower()
    rec.write_bytes(good)

    # (b) readable record, install genuinely stale: edit a deployed output.
    record = load_record(project)
    victim = next(k for k in record["output_mappings"] if (project / k).is_file() and k.endswith(".md"))
    (project / victim).write_text("edited after the build\n", encoding="utf-8")
    rc, out = run_check(project, "check_output_drift.py")
    assert rc != 0, "a stale-but-readable install must still be judged by the drift comparison"
    assert not _could_not_read(out), "a readable record must never yield the could-not-read verdict"

    # and a readable record with a wrong template hash for the build-drift check.
    flat = next(k for k, v in record.items() if isinstance(v, str) and len(v) == 64)
    record[flat] = "0" * 64
    rec.write_text(json.dumps(record, indent=2), encoding="utf-8")
    rc, out = run_check(project, "check_build_drift.py")
    assert not _could_not_read(out), out[-400:]
