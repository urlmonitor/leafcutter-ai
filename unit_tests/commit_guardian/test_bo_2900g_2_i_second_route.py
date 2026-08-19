"""
MODULE: unit_tests/commit_guardian/test_bo_2900g_2_i_second_route.py
COVERS: BO-2900g-2-i

GOAL: PRODUCTION ENTRY POINT test on a SECOND real authoring route (the
deployed check-ac-schema gate via subprocess, as opposed to the direct
derivation call used in test_bo_2900g_2_i.py's unit-level tests). A new
durable-effect record authored through the pre-commit path must receive the
same outcome without that route having been modified specially for this AC.

CURRENT STATE (2026-08-18): No derivation exists in the gate at all — the
hook exits 0 on a durable-effect record with no declares_side_effect and
performs no correction. RED against the assertion that the second route
also produces the documented outcome.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

HOOK_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_ac_schema.py"
)
SCHEMA_FILE = (
    Path(__file__).resolve().parent.parent.parent / "config" / "ac_store_schema.json"
)

_NEW_RECORD_YAML = textwrap.dedent("""\
    id: ZZ-2900g-2-i-route2
    title: "New record authored through the pre-commit route"
    component: build-orchestration
    components:
      - build_orchestration
    status: active
    created_by: "tickets/00_inbox/epics/EPIC-Test/01_test.md"
    criteria: |
      Given a change
      When the tool runs
      Then a record is persisted to the database
    priority: medium
    readiness: draft
""")


def _write_ac_file(directory: Path, filename: str, content: str) -> Path:
    import shutil

    if SCHEMA_FILE.is_file():
        config_dir = directory / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCHEMA_FILE, config_dir / "ac_store_schema.json")

    ac_dir = directory / "docs" / "acceptance-criteria"
    ac_dir.mkdir(parents=True, exist_ok=True)
    path = ac_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def _run_hook_staged(root: Path, staged: list[Path]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOOK_ROOT"] = str(root)
    env["HOOK_TEST_STAGED_FILES"] = os.pathsep.join(str(p) for p in staged)
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class TestSecondAuthoringRouteInheritsTheDerivation:
    def test_bo_2900g_2_i_second_authoring_route_inherits_the_derivation(self) -> None:
        # covers: BO-2900g-2-i
        """A new durable-effect record authored through the pre-commit gate
        route must receive the declaration outcome (block or auto-correct),
        matching the outcome the direct-derivation route produces, without
        this route having been given special-case knowledge of the AC."""
        # Assert, never skip. This is a DEPLOYED-layer test: it proves the
        # pre-commit gate route reaches the same outcome as direct derivation.
        # A missing deployed script is exactly the condition that would make the
        # second route silently do nothing — skipping would report that as a pass.
        assert HOOK_SCRIPT.is_file(), (
            f"deployed hook script not found: {HOOK_SCRIPT} — run "
            f"`python scripts/build.py --target-dir .` first; a missing deployed "
            f"gate is a failure, not a reason to skip"
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = _write_ac_file(root, "ZZ-2900g-2-i-route2.yaml", _NEW_RECORD_YAML)
            result = _run_hook_staged(root, [path])
            corrected_text = path.read_text(encoding="utf-8")
            was_corrected = "declares_side_effect: true" in corrected_text

        assert result.returncode != 0 or was_corrected, (
            "the second authoring route (pre-commit gate) must produce the "
            f"same documented outcome as the first. Got exit={result.returncode}, "
            f"corrected={was_corrected}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
