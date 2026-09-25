"""
MODULE: unit_tests/ac_store/test_validate_ac_walks_directories.py
GOAL: ACS-100i-7-ii — scripts/ac_store/validate_ac.py (the package-surface
    spec validator) walks a directory argument recursively and never reports
    success for a run that examined no records.

BUSINESS CONTEXT: KI-ACS-001 was fixed in validate_ac_schema.py only. Its
    sibling validate_ac.py — which templates/agents/it-po.md tells agents to
    run — still dropped a directory argument at its suffix filter, printed
    "No YAML files to validate." and exited 0 having checked nothing. A
    validator that cannot tell "clean" from "I was given nothing" is consulted
    for reassurance it cannot give.

ARCHITECTURE: The validator is always run as a real subprocess over a temp
    store in ``tmp_path``. Fixtures are produced by the real YAML serializer
    (``yaml.safe_dump``), never hand-indented literals (test-writer §2h.2).

DOC_LINKS:
  - docs/known-issues/ac-store/open-high-ki-acs-20260925-validate-ac-bare-directory-exits-0.md
  - docs/acceptance-criteria/ac-store/ACS-100-structured-requirements/ACS-100i-7-ii.yaml
"""
# covers: ACS-100i-7-ii
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VALIDATOR = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke validate_ac.py as a subprocess — the way every caller reaches it."""
    return subprocess.run(
        [sys.executable, str(_VALIDATOR), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
    )


def _record(ac_id: str, it_requirements: Any) -> dict[str, Any]:
    """Return a package-surface-declaring AC record with the given spec."""
    return {
        "id": ac_id,
        "title": "Fixture record for the validate_ac directory-walk tests",
        "component": "ac-store",
        "components": ["ac_store"],
        "level": "L3",
        "status": "active",
        "readiness": "approved",
        "priority": "medium",
        "criteria": "Given a fixture\nWhen validated\nThen only the planted defect is reported",
        "assigned_agent": "python-coder",
        "package_surface": True,
        "it_requirements": it_requirements,
    }


def _complete_spec() -> dict[str, Any]:
    """Return a structured spec whose reference_file_path exists in this repo."""
    return {
        "config_schema_fragment": {"type": "object"},
        "reference_file_path": "config/ac_store_schema.json",
        "n_location_rule": "1",
        "required_skills": ["python-coder"],
        "post_write_commands": [],
    }


def _write(path: Path, data: dict[str, Any]) -> Path:
    """Serialize ``data`` with the real YAML producer and write it to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_directory_with_nested_invalid_record_is_refused(tmp_path: Path) -> None:
    """A directory is walked recursively; the nested invalid record fails the run."""
    # covers: ACS-100i-7-ii
    store = tmp_path / "ac-store"
    feature = store / "ACS-999-feature"
    _write(feature / "ACS-999a.yaml", _record("ACS-999a", _complete_spec()))
    bad = _write(
        feature / "ACS-999b.yaml",
        _record("ACS-999b", ["a list of strings", "is not a structured spec"]),
    )

    run = _run(str(store))

    assert run.returncode != 0, (
        "a directory holding an invalid package-surface record must fail the run; "
        f"exit={run.returncode}\n{run.stdout}{run.stderr}"
    )
    output = run.stdout + run.stderr
    assert bad.name in output, f"the refusal must name the invalid record:\n{output}"
    assert "ACS-999a.yaml" not in output, f"the valid record must not be refused:\n{output}"
    assert "No YAML files to validate." not in output


def test_empty_directory_exits_non_zero(tmp_path: Path) -> None:
    """A directory resolving to zero records is not a pass."""
    # covers: ACS-100i-7-ii
    empty = tmp_path / "empty-store"
    empty.mkdir()

    run = _run(str(empty))

    assert run.returncode != 0, (
        "a run that examined zero records must exit non-zero; "
        f"exit={run.returncode}\n{run.stdout}{run.stderr}"
    )


def test_directory_with_only_index_yaml_exits_non_zero(tmp_path: Path) -> None:
    """index.yaml is the component registry, not an AC — it is skipped by the walk."""
    # covers: ACS-100i-7-ii
    store = tmp_path / "registry-only"
    _write(store / "index.yaml", {"components": [{"id": "ac-store", "prefix": "ACS"}]})

    run = _run(str(store))

    assert run.returncode != 0, (
        "a directory whose only YAML is index.yaml examined zero records and must "
        f"exit non-zero; exit={run.returncode}\n{run.stdout}{run.stderr}"
    )


def test_single_valid_file_exits_zero(tmp_path: Path) -> None:
    """A single valid record passed by file path still passes, as before."""
    # covers: ACS-100i-7-ii
    good = _write(tmp_path / "ACS-999a.yaml", _record("ACS-999a", _complete_spec()))

    run = _run(str(good))

    assert run.returncode == 0, (
        f"a single valid record must pass; exit={run.returncode}\n{run.stdout}{run.stderr}"
    )
