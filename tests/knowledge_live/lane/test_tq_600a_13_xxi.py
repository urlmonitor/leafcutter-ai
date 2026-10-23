"""TQ-600a-13-xxi against the REAL disposable graph databases the live lane starts.

Needs the three disposable Neo4j instances of the Proof-of-done check (17687, 18087, 18088). Unlike the other tests of
this folder it NEVER skips for an unreachable database: the live lane exists to supply one, so an unreachable
instance is a failure here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]  # tests/knowledge_live/lane/<this file>
INSTANCES = {17687: "leafcutter-local-tests", 18087: "leafcutter-domain-tests", 18088: "leafcutter-native-tests"}
IMAGE = "neo4j:5.26-community"
POPULATION = {
    "pass": "def test_pass():\n    assert True\n",
    "fail": "def test_fail():\n    assert False\n",
    "flaky": (
        "import os\nfrom pathlib import Path\n\n\ndef test_flaky():\n    log = Path(os.environ['LIVE_STATE_DIR']) / 'flaky.log'\n"
        "    with log.open('a', encoding='utf-8') as handle:\n        handle.write('x\\n')\n    assert len(log.read_text().split()) >= 2\n"
    ),
}


def _version_of(port: int, password: str) -> tuple[str, str]:
    """(version, edition) the instance on ``port`` reports; an unreachable instance FAILS the test."""
    from neo4j import GraphDatabase  # noqa: PLC0415 -- only this test needs the driver

    try:
        with GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=("neo4j", password)) as driver, driver.session() as session:
            row = session.run("CALL dbms.components() YIELD versions, edition RETURN versions[0] AS version, edition").single()
    except Exception as exc:  # noqa: BLE001 -- any driver failure is "not reachable"; the test must fail, never skip
        pytest.fail(f"disposable database on port {port} is not reachable: {exc}")
    return row["version"], row["edition"]


def _synthetic_project(root: Path) -> None:
    folder = root / "tests" / "knowledge_live"
    folder.mkdir(parents=True)
    for name, source in POPULATION.items():
        (folder / f"test_{name}.py").write_text(source, encoding="utf-8")
    (root / "pytest.ini").write_text('[pytest]\naddopts = -m "not manual and not timing_ratio"\nmarkers =\n    manual: m\n    timing_ratio: t\n', encoding="utf-8")
    (root / "scripts").symlink_to(REPO_ROOT / "scripts", target_is_directory=True)


def _lane(root: Path, *args: str, address: str, state: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTEST_", "GITHUB_"))}
    env.update({"LIVE_DB_ADDRESS": address, "LIVE_DB_STARTUP_LIMIT": "30", "LIVE_STATE_DIR": str(state), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    command = ["python", "-m", "pytest", "tests/knowledge_live/", "-p", "no:cacheprovider"]
    argv = [sys.executable, "scripts/ci/post_merge_suite.py", *args, "--", *command]
    return subprocess.run(argv, cwd=str(root), env=env, capture_output=True, text=True, timeout=300, check=False)  # noqa: S603


@pytest.mark.manual
def test_tq_600a_13_xxi_the_live_lane_runs_against_the_same_real_databases_as_proof_of_done_MANUAL():
    # covers: TQ-600a-13-xxi
    # angle: real_artifact
    """Three real instances answer on the Proof-of-done addresses and version; the lane runs pass/fail/fail-then-pass against the real one.

    Wrong version caught: an instance on a drifted port or image tag from the Proof-of-done check's (the workflow's live_run
    services are compared to the literal ports and image, then each instance is asked for its version).
    """
    suite = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "post-merge-suite.yml").read_text(encoding="utf-8"))
    live_run = (suite.get("jobs") or {}).get("live_run")
    assert live_run is not None, "post-merge-suite.yml has no live_run job"
    services = (live_run.get("services") or {}).values()
    assert {s["image"] for s in services} == {IMAGE}, "the live lane's instances must use the Proof-of-done image tag"
    assert {int(str(p).split(":")[0]) for s in services for p in s.get("ports", [])} == set(INSTANCES), "the live lane's instances must sit on the Proof-of-done ports"
    for port, password in INSTANCES.items():
        version, edition = _version_of(port, password)
        assert version.startswith("5.26"), f"port {port} reports version {version}"
        assert edition == "community", f"port {port} reports edition {edition}"
    with tempfile.TemporaryDirectory() as raw:
        root, state = Path(raw) / "project", Path(raw) / "state"
        state.mkdir()
        _synthetic_project(root)
        out = Path(raw) / "out"
        out.mkdir()
        first = _lane(root, "run", "--lane", "live", "--report", str(out / "first.json"), "--failures", str(out / "failures.txt"), address="127.0.0.1:17687", state=state)
        assert first.returncode == 0, first.stderr[-1500:]
        results = json.loads((out / "first.json").read_text(encoding="utf-8"))["results"]
        assert {k.rsplit("::", 1)[1]: v for k, v in results.items()} == {"test_pass": "passed", "test_fail": "failed", "test_flaky": "failed"}
        second = _lane(root, "retry", "--lane", "live", "--failures", str(out / "failures.txt"), "--report", str(out / "retry.json"), address="127.0.0.1:17687", state=state)
        assert second.returncode == 0, second.stderr[-1500:]
        retried = json.loads((out / "retry.json").read_text(encoding="utf-8"))["results"]
        assert {k.rsplit("::", 1)[1]: v for k, v in retried.items()} == {"test_fail": "failed", "test_flaky": "passed"}
