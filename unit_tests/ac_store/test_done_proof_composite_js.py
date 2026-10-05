"""Composite proofs discover child tags and honor both language runners.

AC fixtures use the real YAML serializer; sources carry only child tags. The
fast tests control the runner boundary, leaving discovery and verdicts real.
This reproduces UXP-523's three TypeScript files being handed to pytest.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ac_store"))
import done_proof  # noqa: E402


def _ac(root: Path, identifier: str, children: tuple[str, ...] = ()) -> None:
    """Serialize a minimal active AC with its actual child references."""
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{identifier}.yaml").write_text(
        yaml.safe_dump({"id": identifier, "status": "active", "work_status": "done",
                        "covered_by": list(children)}), encoding="utf-8"
    )


def _source(root: Path, name: str, identifier: str, *, passing: bool = True) -> Path:
    """Write runnable assertions rather than covers-only source placeholders."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    if path.suffix == ".py":
        text = f"def test_contract():\n    # covers: {identifier}\n    assert {passing}\n"
    else:
        text = f"// covers: {identifier}\ntest('contract', () => {{ expect({str(passing).lower()}).toBe(true); }});\n"
    path.write_text(text, encoding="utf-8")
    return path


def _three_children(tmp_path: Path) -> tuple[Path, Path, list[Path]]:
    """Create the real failing shape: four children in three TS files."""
    ac_root, test_root = tmp_path / "acs", tmp_path / "web"
    children = tuple(f"FX-100-{index}" for index in range(1, 5))
    _ac(ac_root, "FX-100", children)
    for identifier in children:
        _ac(ac_root, identifier)
    sources = [_source(test_root, name, identifier) for name, identifier in zip(
        ("drawer.contracts.test.tsx", "explorer.contracts.test.tsx", "flows.contracts.test.ts"), children
    )]
    with sources[-1].open("a", encoding="utf-8") as stream:
        stream.write("// covers: FX-100-4\n")
    (test_root / "package.json").write_text('{"private":true}', encoding="utf-8")
    return ac_root, test_root, sources


def test_three_ts_child_files_are_proved_by_js_runner(tmp_path, monkeypatch):
    """No parent tag is needed, and every discovered child contributes proof."""
    # covers: BO-2500a-6
    ac_root, test_root, sources = _three_children(tmp_path)
    calls = []

    def js_runner(files, *, project_dir):
        calls.append((set(files), project_dir))
        return {str(path): "PASSED" for path in files}

    def unexpected_pytest(files):
        pytest.fail(f"TypeScript child proof incorrectly routed to pytest: {files}")

    monkeypatch.setattr(done_proof, "run_vitest_and_parse", js_runner)
    monkeypatch.setattr(done_proof, "_run_pytest_and_parse", unexpected_pytest)
    verdict = done_proof.verify_done_eligible("FX-100", ac_root=ac_root, test_root=test_root)
    assert verdict["eligible"], verdict
    assert set(verdict["passing_tests"]) == {str(path) for path in sources}
    assert calls == [(set(sources), test_root)]


def test_mixed_child_proof_runs_both_languages(tmp_path, monkeypatch):
    """The Python phase cannot absorb, skip, or replace TypeScript proof."""
    # covers: BO-2500e-4
    ac_root, test_root = tmp_path / "acs", tmp_path / "tests"
    _ac(ac_root, "FX-200", ("FX-200-1", "FX-200-2"))
    for identifier in ("FX-200-1", "FX-200-2"):
        _ac(ac_root, identifier)
    py = _source(test_root, "test_python.py", "FX-200-1")
    ts = _source(test_root, "browser.test.ts", "FX-200-2")
    (test_root / "package.json").write_text('{}', encoding="utf-8")
    calls = []

    def python_runner(files):
        assert files == [py], "Only Python sources belong in pytest"
        calls.append("python")
        return {f"{py.name}::test_contract": "PASSED"}

    def js_runner(files, *, project_dir):
        assert files == [ts]
        calls.append("typescript")
        return {str(ts): "PASSED"}

    monkeypatch.setattr(done_proof, "_run_pytest_and_parse", python_runner)
    monkeypatch.setattr(done_proof, "run_vitest_and_parse", js_runner)
    verdict = done_proof.verify_done_eligible("FX-200", ac_root=ac_root, test_root=test_root)
    assert verdict["eligible"], verdict
    assert len(verdict["passing_tests"]) == 2
    assert calls == ["python", "typescript"]


@pytest.mark.parametrize("outcome", ["FAILED", "SKIPPED", None])
def test_nonpassing_or_absent_ts_child_proof_blocks_parent(tmp_path, monkeypatch, outcome):
    """A successful sibling cannot hide failed, skipped, or missing TS evidence."""
    # covers: BO-2500e-4
    ac_root, test_root, sources = _three_children(tmp_path)

    def js_runner(files, *, project_dir):
        results = {str(path): "PASSED" for path in files}
        if outcome is None:
            results.pop(str(sources[-1]))
        else:
            results[str(sources[-1])] = outcome
        return results

    monkeypatch.setattr(done_proof, "run_vitest_and_parse", js_runner)
    verdict = done_proof.verify_done_eligible("FX-100", ac_root=ac_root, test_root=test_root)
    assert not verdict["eligible"]
    assert str(sources[-1]) in verdict["failing_tests"]
    assert "JS test(s) failed" in verdict["reason"]


def test_missing_vitest_blocks_composite_with_useful_reason(tmp_path):
    """No installed runner must not become a pass or a Python collection error."""
    # covers: BO-2500e-3
    ac_root, test_root, _ = _three_children(tmp_path)
    verdict = done_proof.verify_done_eligible("FX-100", ac_root=ac_root, test_root=test_root)
    assert not verdict["eligible"]
    assert "JS runner unavailable" in verdict["reason"]
    assert "vitest binary not found" in verdict["reason"]


def test_uncovered_child_refuses_before_any_runner(tmp_path, monkeypatch):
    """Keep all-child coverage, including an untagged child beside passing files."""
    # covers: BO-2500a-6
    ac_root, test_root, _ = _three_children(tmp_path)
    _ac(ac_root, "FX-100-5")
    _ac(ac_root, "FX-100", tuple(f"FX-100-{index}" for index in range(1, 6)))

    def forbidden(*args, **kwargs):
        pytest.fail("Runners must not execute while a child has no linked proof")

    monkeypatch.setattr(done_proof, "_run_pytest_and_parse", forbidden)
    monkeypatch.setattr(done_proof, "run_vitest_and_parse", forbidden)
    verdict = done_proof.verify_done_eligible("FX-100", ac_root=ac_root, test_root=test_root)
    assert not verdict["eligible"]
    assert "uncovered children: FX-100-5" in verdict["reason"]


def test_direct_ts_leaf_keeps_existing_file_proof_semantics(tmp_path, monkeypatch):
    """The same child remains independently provable without a parent shortcut."""
    # covers: BO-2500e-1
    ac_root, test_root, sources = _three_children(tmp_path)
    calls = []

    def js_runner(files, *, project_dir):
        calls.append(files)
        return {str(path): "PASSED" for path in files}

    monkeypatch.setattr(done_proof, "run_vitest_and_parse", js_runner)
    verdict = done_proof.verify_done_eligible("FX-100-1", ac_root=ac_root, test_root=test_root)
    assert verdict["eligible"], verdict
    assert verdict["passing_tests"] == [str(sources[0])]
    assert calls == [[sources[0]]]


def test_incomplete_python_proof_stops_before_ts(tmp_path, monkeypatch):
    """An interrupted Python run cannot be rescued by a passing JavaScript phase."""
    # covers: BO-2500e-4
    ac_root, test_root, _ = _three_children(tmp_path)
    _source(test_root, "test_python.py", "FX-100-1")

    def incomplete(files):
        assert all(path.suffix == ".py" for path in files)
        return {done_proof._PYTEST_RUN_INCOMPLETE_SENTINEL: "fixture process interrupted"}

    def forbidden(*args, **kwargs):
        pytest.fail("TypeScript proof must not hide unfinished Python proof")

    monkeypatch.setattr(done_proof, "_run_pytest_and_parse", incomplete)
    monkeypatch.setattr(done_proof, "run_vitest_and_parse", forbidden)
    verdict = done_proof.verify_done_eligible("FX-100", ac_root=ac_root, test_root=test_root)
    assert not verdict["eligible"]
    assert "fixture process interrupted" in verdict["reason"]


@pytest.mark.parametrize("mixed,passing", [(False, True), (True, True), (True, False)])
def test_real_vitest_assertions_control_composite_verdict(tmp_path, monkeypatch, mixed, passing):
    """Execute real TS assertions and parse real JSON; mock only launcher packaging.

    Windows cannot directly launch the Unix npm shim. This fixture selects the
    installed Vitest JS entry point via Node while retaining production command
    arguments, execution, report parser, source discovery, and eligibility logic.
    No test outcome is manufactured. A failed assertion must survive both phases.
    """
    # covers: BO-2500a-6
    node = shutil.which("node")
    vitest = ROOT / "leafcutter-web" / "node_modules" / "vitest" / "vitest.mjs"
    assert node, "Required runtime proof cannot run: install Node.js and expose node on PATH"
    assert vitest.is_file(), (
        "Required runtime proof cannot run: install web dependencies with npm ci "
        f"in {ROOT / 'leafcutter-web'} (missing {vitest})"
    )
    ac_root, test_root, sources = _three_children(tmp_path)
    _source(test_root, sources[-1].name, "FX-100-3", passing=passing)
    with sources[-1].open("a", encoding="utf-8") as stream:
        stream.write("// covers: FX-100-4\n")
    if mixed:
        _ac(ac_root, "FX-100-5")
        _ac(ac_root, "FX-100", tuple(f"FX-100-{index}" for index in range(1, 6)))
        _source(test_root, "test_python.py", "FX-100-5")
    (test_root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (test_root / "vitest.config.mjs").write_text(
        "export default {test:{globals:true,environment:'node',maxWorkers:1}};\n", encoding="utf-8"
    )
    shim = test_root / "node_modules" / ".bin" / "vitest"
    shim.parent.mkdir(parents=True)
    shim.write_text("fixture launcher selected by _build_vitest_command\n", encoding="utf-8")
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    build_command = done_proof._build_vitest_command
    execute = done_proof._execute_vitest
    reports = []

    def node_command(*args):
        return [node, str(vitest), *build_command(*args)[1:]]

    def record_execution(command, cwd):
        result = execute(command, cwd)
        assert result is not None, "Actual fixture Vitest process timed out"
        report_file = tmp_path / "actual-vitest-report.json"
        report_file.write_text(result.stdout, encoding="utf-8")
        report = json.loads(report_file.read_text(encoding="utf-8"))
        reports.append((result.returncode, report))
        return result

    monkeypatch.setattr(done_proof, "_build_vitest_command", node_command)
    monkeypatch.setattr(done_proof, "_execute_vitest", record_execution)
    verdict = done_proof.verify_done_eligible("FX-100", ac_root=ac_root, test_root=test_root)
    assert len(reports) == 1
    returncode, report = reports[0]
    assert report["numTotalTests"] == 3
    assert report["numFailedTests"] == (0 if passing else 1)
    assert returncode == (0 if passing else 1)
    assert verdict["eligible"] is passing, verdict
    assert len(verdict["passing_tests"]) == (3 if passing else 2) + int(mixed)
    if not passing:
        assert str(sources[-1]) in verdict["failing_tests"]
