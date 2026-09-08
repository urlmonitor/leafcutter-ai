"""
MODULE: unit_tests/commit_guardian/_bo_2900d_fixtures.py
GOAL: Shared real-artifact fixture builders for BO-2900d-1 / BO-2900d-2 tests.

Not a test file itself (does not match test_*.py) so pytest never collects it
directly. Builds a genuinely git-initialised, on-disk fixture project so the
deployed ``scripts/commit_guardian/check_done_proof.py`` CLI (the real
"reachability guard" entry point per BO-2900a-3 / BO-2900d's own
reference_file_path) can be run against it via subprocess exactly as it is
invoked from CI (.github/workflows/ci.yml:228: ``python
scripts/commit_guardian/check_done_proof.py --mode ci ...``) and from the
pre-commit hook registry (commit_guardian.json id "check-done-proof").

All fixture YAML is produced via ``yaml.safe_dump`` (never a hand-typed
literal) per the Fixture Authenticity Rule (test-writer skill 2h.2) — a
hand-typed AC/registry file reproduces the author's mental model of the
format, which is exactly the blind spot EPIC-PhantomDoneFilesTouched shipped
on (indented-dash fixtures vs column-0 real output).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHECK_DONE_PROOF_SCRIPT = (
    REPO_ROOT / "scripts" / "commit_guardian" / "check_done_proof.py"
)


def init_fixture_project(tmp_path: Path) -> Path:
    """Create a git-initialised fixture project root with the directories
    ``check_done_proof.py`` and ``verify_done_eligible`` need: docs/acceptance-
    criteria, config (for the reachability_exemptions.yaml registry the guard
    is expected to read from *this* project root once find_project_root()
    resolves it via ``git rev-parse --show-toplevel`` with cwd=root), and a
    test tree plus a source tree for fixture "units".
    """
    root = tmp_path
    subprocess.run(
        ["git", "init", "-q"], cwd=str(root), check=True, capture_output=True
    )
    (root / "docs" / "acceptance-criteria").mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    write_exemptions(root, [])
    return root


def write_exemptions(root: Path, entries: list[dict]) -> Path:
    """Write config/reachability_exemptions.yaml via the real YAML serializer.

    ``entries`` is the exact list the AC store schema fragment describes:
    ``{item, kind, reason, recorded, recorded_by}`` dicts under the
    top-level ``exemptions`` key (BO-2900d-1 it_requirements).
    """
    path = root / "config" / "reachability_exemptions.yaml"
    path.write_text(
        yaml.safe_dump({"exemptions": entries}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def write_done_ac(
    ac_dir: Path,
    ac_id: str,
    *,
    work_status: str = "done",
) -> Path:
    """Write a minimal, schema-plausible AC YAML via yaml.safe_dump."""
    data = {
        "id": ac_id,
        "title": f"Fixture record for {ac_id}",
        "component": "build-orchestration",
        "components": ["build_orchestration"],
        "status": "active",
        "work_status": work_status,
        "readiness": "reviewed",
        "priority": "medium",
        "criteria": (
            "Given a fixture unit\n"
            "When the reachability guard evaluates it\n"
            "Then the fixture behaves as this test requires\n"
        ),
    }
    path = ac_dir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def write_no_entry_unit(src_dir: Path, rel_path: str, body: str = "def do_thing():\n    return 42\n") -> Path:
    """Write a fixture "unit with no runtime way in": a plain module with a
    pure function, no ``if __name__ == '__main__':`` guard, and (by
    construction) no caller anywhere in the fixture tree except a test that
    imports it directly.
    """
    path = src_dir / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def write_direct_import_test(
    test_dir: Path,
    filename: str,
    *,
    ac_id: str,
    module_name: str,
    src_dir_for_import: Path,
) -> Path:
    """Write a covers-tagged test that imports the fixture unit DIRECTLY
    (never through a real entry point) — the exact shape BO-2900d-1's
    criteria describes as "a unit of code that exposes no runtime way in".
    """
    path = test_dir / filename
    path.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(src_dir_for_import)!r})\n"
        f"from {module_name} import do_thing\n\n\n"
        "def test_fixture_unit_via_direct_import():\n"
        f"    # covers: {ac_id}\n"
        "    assert do_thing() == 42\n",
        encoding="utf-8",
    )
    return path


def run_check_done_proof(
    root: Path,
    *,
    ac_root: Path,
    test_root: Path,
    mode: str = "ci",
) -> subprocess.CompletedProcess:
    """Run the REAL deployed check_done_proof.py CLI via subprocess, cwd=root.

    Mirrors the exact invocation shape used in .github/workflows/ci.yml:228
    (``--mode ci`` / ``--mode ci-changed``) and the commit_guardian.json
    "check-done-proof" hook registration — never imports the module directly,
    so a change to the CLI wiring itself would be caught, not just a change
    to an internal helper.
    """
    assert CHECK_DONE_PROOF_SCRIPT.is_file(), (
        f"deployed guard script not found: {CHECK_DONE_PROOF_SCRIPT} — "
        f"run `python scripts/build.py --target-dir .` first"
    )
    return subprocess.run(
        [
            sys.executable,
            str(CHECK_DONE_PROOF_SCRIPT),
            "--mode",
            mode,
            "--ac-root",
            str(ac_root),
            "--test-root",
            str(test_root),
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
