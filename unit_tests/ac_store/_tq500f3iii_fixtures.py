"""
MODULE: unit_tests/ac_store/_tq500f3iii_fixtures.py
GOAL: Shared real-file / real-pytest fixtures for the TQ-500f-3-iii test
    family (a covering tag is matched to the ONE test it sits on).
BUSINESS CONTEXT: The proof-of-done check (scripts/ac_store/done_proof.py) and
    the red-baseline reader (scripts/build_orchestration/fast_lane.py
    verify_red_baseline) both match a covering tag to a test-run result. They
    used to match on (file basename, bare function name), so two tests sharing
    those collapsed onto one result. This module builds the T1..T4 collision
    fixture named in the AC's Given clause, plus the inherited-test, the
    parametrised-test and the duplicate-collection fixtures its test_spec
    names.
ARCHITECTURE: Every fixture is REAL bytes on disk -- real ``.py`` test files
    that the real pytest then runs (nodeids come from real pytest output,
    never a hand-typed dict), and AC records written by ``yaml.safe_dump``
    (CLAUDE.md Fixture Authenticity Rule 2h.2). The done-proof side is driven
    through a fresh subprocess that imports ``done_proof`` from a scripts
    directory the caller names (the source tree or a DEPLOYED copy), so a
    stale ``sys.modules`` entry or an ``importlib.reload`` can never mask a
    cold-import error.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_SCRIPTS = REPO_ROOT / "scripts"
SOURCE_AC_STORE_SCRIPTS = SOURCE_SCRIPTS / "ac_store"
SOURCE_CHECK_DONE_PROOF = SOURCE_SCRIPTS / "commit_guardian" / "check_done_proof.py"
SOURCE_FAST_LANE = SOURCE_SCRIPTS / "build_orchestration" / "fast_lane.py"

T1, T2, T3, T4 = "TQ-9001", "TQ-9002", "TQ-9003", "TQ-9004"
T1_T4_IDS = (T1, T2, T3, T4)
# The verdicts the AC's Then clause states, tag by tag.
EXPECTED_ELIGIBLE = {T1: False, T2: True, T3: True, T4: False}

# Nodeids (relative to the fixture repo root) the four tags must resolve to in
# the FORWARD arrangement. The reversed arrangement swaps the directories of T3
# and T4 -- see build_collision_repo.
_REFRESH = "unit_tests/ac_store/test_refresh.py"
FORWARD_NODEIDS = {
    T1: f"{_REFRESH}::TestRetryGate::test_blocks_when_not_due",
    T2: f"{_REFRESH}::TestExportGate::test_blocks_when_not_due",
    T3: "unit_tests/ac_store/test_config.py::test_loads_defaults",
    T4: "unit_tests/build_orchestration/test_config.py::test_loads_defaults",
}
REVERSED_NODEIDS = {
    T1: FORWARD_NODEIDS[T1],
    T2: FORWARD_NODEIDS[T2],
    T3: "unit_tests/build_orchestration/test_config.py::test_loads_defaults",
    T4: "unit_tests/ac_store/test_config.py::test_loads_defaults",
}


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def init_packages(root: Path, *rels: str) -> None:
    """Create ``__init__.py`` for every dir in each rel path (same-basename test files need packages)."""
    for rel in rels:
        current = root
        for part in Path(rel).parts:
            current = current / part
            (current / "__init__.py").parent.mkdir(parents=True, exist_ok=True)
            (current / "__init__.py").touch()


def write_pytest_ini(root: Path) -> None:
    """Anchor pytest's rootdir at *root* so nodeids are root-relative."""
    write(root / "pytest.ini", "[pytest]\n")


def write_ac_store(ac_root: Path, ac_ids, *, work_status: str = "done", test_spec_by_id: dict | None = None) -> None:
    """Write one active AC record per id through the real serializer."""
    ac_root.mkdir(parents=True, exist_ok=True)
    for ac_id in ac_ids:
        record = {
            "id": ac_id,
            "title": f"Synthetic TQ-500f-3-iii fixture AC {ac_id}",
            "component": "testing-quality",
            "components": ["testing_quality"],
            "level": "L3",
            "status": "active",
            "work_status": work_status,
            "readiness": "draft",
            "priority": "medium",
            "depends_on": [],
            "amended_by": [],
            "covered_by": [],
            "implemented_by": [],
            "superseded_by": None,
            "criteria": "Given a fixture\nWhen checked\nThen judged\n",
        }
        if test_spec_by_id and ac_id in test_spec_by_id:
            record["test_spec"] = test_spec_by_id[ac_id]
        (ac_root / f"{ac_id}.yaml").write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")


def build_collision_repo(root: Path, *, reverse: bool = False) -> dict[str, str]:
    """Write the T1..T4 fixture under *root* and return ``{tag: expected nodeid}``.

    T1/T2 share a file and a function name in two classes; T3/T4 share a file
    basename and a function name in two package directories. T1 and T4 fail,
    T2 and T3 pass. ``reverse=True`` changes the order pytest reports the four
    tests in: the two classes swap positions and T3/T4 swap directories.
    """
    init_packages(root, "unit_tests/ac_store", "unit_tests/build_orchestration")
    write_pytest_ini(root)
    retry = f"""\
        class TestRetryGate:
            def test_blocks_when_not_due(self):
                # covers: {T1}
                assert 1 == 2, "retry gate lets a not-due refresh through"
        """
    export = f"""\
        class TestExportGate:
            def test_blocks_when_not_due(self):
                # covers: {T2}
                assert 1 == 1
        """
    classes = [export, retry] if reverse else [retry, export]
    write(root / _REFRESH, "\n".join(textwrap.dedent(c) for c in classes))
    passing = """\
        def test_loads_defaults():
            # covers: {ac}
            assert 1 == 1
        """
    failing = """\
        def test_loads_defaults():
            # covers: {ac}
            assert 1 == 2, "defaults did not load"
        """
    nodeids = REVERSED_NODEIDS if reverse else FORWARD_NODEIDS
    for ac_id, body in ((T3, passing), (T4, failing)):
        rel = nodeids[ac_id].split("::")[0]
        write(root / rel, body.replace("{ac}", ac_id))
    return dict(nodeids)


def run_done_proof_driver(scripts_dir: Path, ac_root: Path, test_root: Path, ac_ids, tmp_dir: Path, *, cwd: Path | None = None) -> dict:
    """Run ``done_proof.verify_done_eligible`` for each id in a FRESH subprocess.

    *scripts_dir* is a ``scripts`` directory (the source tree's, or a deployed
    ``.leafcutter/scripts``) holding ``ac_store/done_proof.py``. Returns
    ``{ac_id: verdict_dict}``. Raises AssertionError carrying stderr when the
    driver cannot import or run (e.g. a ModuleNotFoundError in a deployed copy).
    """
    driver = tmp_dir / "_tq500f3iii_driver.py"
    driver.write_text(
        textwrap.dedent(
            """\
            import json, sys
            from pathlib import Path
            scripts = Path(sys.argv[1])
            sys.path.insert(0, str(scripts))
            sys.path.insert(0, str(scripts / "ac_store"))
            import done_proof
            ac_root, test_root = Path(sys.argv[2]), Path(sys.argv[3])
            out = {a: done_proof.verify_done_eligible(a, ac_root=ac_root, test_root=test_root) for a in sys.argv[4:]}
            print("DRIVER_JSON=" + json.dumps(out, default=str))
            """
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(driver), str(scripts_dir), str(ac_root), str(test_root), *ac_ids],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(cwd or test_root),
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("DRIVER_JSON=")]
    if proc.returncode != 0 or not lines:
        raise AssertionError(  # noqa: TRY003
            f"done_proof driver failed (exit {proc.returncode}) using {scripts_dir}:\nstderr={proc.stderr[-1500:]}\nstdout={proc.stdout[-500:]}"
        )
    return json.loads(lines[-1][len("DRIVER_JSON="):])


def run_check_done_proof_ci(script: Path, ac_root: Path, test_root: Path) -> subprocess.CompletedProcess:
    """Run the check_done_proof hook entry point in ci mode as a subprocess."""
    return subprocess.run(
        [sys.executable, str(script), "--mode", "ci", "--ac-root", str(ac_root), "--test-root", str(test_root)],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(test_root),
    )


def violated_ids(proc: subprocess.CompletedProcess) -> set[str]:
    """AC ids the hook printed as violations (``[check-done-proof] <id>: <reason>``)."""
    found: set[str] = set()
    for line in proc.stdout.splitlines():
        if line.startswith("[check-done-proof] "):
            head = line[len("[check-done-proof] "):].split(":", 1)[0].strip()
            if re.fullmatch(r"[A-Z]+-\d+[a-z0-9-]*", head):  # skips summary lines such as "exemptions in force"
                found.add(head)
    return found


def run_verify_red_baseline(fast_lane: Path, ac_ids, test_root: Path, ac_root: Path, *, base_ref: str | None = None) -> dict:
    """Run ``fast_lane.py verify_red_baseline`` as a subprocess and parse its JSON verdict."""
    argv = [sys.executable, str(fast_lane), "verify_red_baseline", "--ac-ids", ",".join(ac_ids), "--test-root", str(test_root), "--ac-root", str(ac_root)]
    if base_ref:
        argv += ["--base-ref", base_ref]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=300, cwd=str(test_root))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(  # noqa: TRY003
            f"verify_red_baseline printed no JSON verdict ({exc}); exit={proc.returncode} stdout={proc.stdout[-800:]!r} stderr={proc.stderr[-1500:]!r}"
        ) from exc


def norm(nodeid: str) -> str:
    return nodeid.replace("\\", "/")


def nodeid_matches(actual: str, expected_suffix: str) -> bool:
    """Compare a reported nodeid to an expected root-relative nodeid (either may carry a prefix dir)."""
    a, e = norm(actual), norm(expected_suffix)
    return a == e or a.endswith("/" + e)


def entry_nodeids(entries) -> dict[str, list[str]]:
    """``{ac_id: [nodeid, ...]}`` from a red/green report list."""
    out: dict[str, list[str]] = {}
    for entry in entries or []:
        out.setdefault(entry.get("ac_id", ""), []).append(entry.get("nodeid", ""))
    return out


def attribution_from_red_baseline(verdict: dict) -> dict[str, list[str]]:
    """Every tag -> nodeid attribution the red-baseline verdict carries, red or green."""
    merged: dict[str, list[str]] = {}
    for key in ("red", "green_at_baseline", "inconclusive", "preexisting"):
        for ac_id, nodeids in entry_nodeids(verdict.get(key)).items():
            merged.setdefault(ac_id, []).extend(nodeids)
    return merged


def attribution_from_done_proof(verdicts: dict) -> dict[str, list[str]]:
    """Every tag -> nodeid attribution the done-proof verdicts carry (passing + failing)."""
    return {
        ac_id: list(v.get("passing_tests", [])) + list(v.get("failing_tests", []))
        for ac_id, v in verdicts.items()
    }


def eligible_map(verdicts: dict) -> dict[str, bool]:
    return {ac_id: bool(v.get("eligible")) for ac_id, v in verdicts.items()}
