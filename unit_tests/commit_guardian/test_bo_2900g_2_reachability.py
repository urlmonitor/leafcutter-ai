"""
MODULE: unit_tests/commit_guardian/test_bo_2900g_2_reachability.py
COVERS: BO-2900g-2

GOAL: PRODUCTION ENTRY POINT test. Run the deployed check-ac-schema gate (the
canonical source under templates/scripts/commit_guardian/, exercised via
subprocess exactly as unit_tests/commit_guardian/test_check_ac_schema.py
already does for this hook) against a staged AC file whose criteria assert a
durable effect but which carries no declares_side_effect declaration, and
assert the gate produces the documented outcome (block, or auto-corrects the
record) — never by importing the validator module directly.

CURRENT STATE (2026-08-18): No derivation of declares_side_effect exists in
_ac_schema_validators.py or check_ac_schema.py at all (grep confirms zero
hits). The gate today exits 0 on such a record with no correction and no
complaint about the missing declaration — RED against this test's assertion
that *something* observable happens.
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

_DURABLE_NO_DECLARATION_YAML = textwrap.dedent("""\
    id: ZZ-2900g-2-r
    title: "Fixture asserting a durable effect with no declaration"
    component: build-orchestration
    components:
      - build_orchestration
    status: active
    created_by: "tickets/00_inbox/epics/EPIC-Test/01_test.md"
    criteria: |
      Given a change
      When the tool runs
      Then a file is written to disk and can be read back
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


class TestDeclarationPresentViaTheDeployedAcSchemaGate:
    def test_bo_2900g_2_declaration_present_via_the_deployed_ac_schema_gate(self) -> None:
        # covers: BO-2900g-2
        """A real AC file whose criteria assert a durable effect but carries no
        declares_side_effect must be flagged by the deployed gate — either
        blocked (non-zero exit naming the missing declaration) or the record
        must be auto-corrected on disk to carry declares_side_effect: true."""
        # Assert, never skip. This is a DEPLOYED-layer test: it proves the real
        # gate flags a durable-effect record carrying no declaration. If the
        # deployed script is absent the gate cannot fire at all — which is the
        # failure this test guards, so skipping would report it as a pass.
        assert HOOK_SCRIPT.is_file(), (
            f"deployed hook script not found: {HOOK_SCRIPT} — run "
            f"`python scripts/build.py --target-dir .` first; a missing deployed "
            f"gate is a failure, not a reason to skip"
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = _write_ac_file(root, "ZZ-2900g-2-r.yaml", _DURABLE_NO_DECLARATION_YAML)
            result = _run_hook_staged(root, [path])

            corrected_text = path.read_text(encoding="utf-8")
            was_corrected = "declares_side_effect: true" in corrected_text

        assert result.returncode != 0 or was_corrected, (
            "the deployed check-ac-schema gate must either block a durable-"
            "effect record lacking declares_side_effect, or auto-correct it "
            f"on disk. Got exit={result.returncode}, corrected={was_corrected}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        if result.returncode != 0:
            combined = (result.stdout + result.stderr).lower()
            assert "declares_side_effect" in combined, (
                "a blocking exit must name the missing declaration by field "
                f"name so the offender is discoverable:\n{combined}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
