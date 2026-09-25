"""
MODULE: unit_tests/commit_guardian/test_tq_500f_check_ac_schema_missing_bridge_warning.py
COVERS: TQ-500f-2-i

REVIEW-FINDING FOLLOW-UP (round 2). The prior batch found
scripts/commit_guardian/check_ac_schema.py emitting jsonschema's generic
message for bad test_spec[].angle/.must_catch values — that gap has since
been closed for the HAPPY resolution path: check_ac_schema.py now imports
`test_spec_entry_errors` from a new sibling,
scripts/commit_guardian/_test_spec_entry_bridge.py, which resolves
scripts/ac_store/ onto sys.path via _ac_store_locator.ensure_ac_store_on_syspath()
and imports scripts/ac_store/_ac_schema_test_spec_validators.py's real
`test_spec_entry_errors`.

THE GAP THIS FILE COVERS: the bridge's own fallback is silently fail-open —

    try:
        from _ac_schema_test_spec_validators import (
            test_spec_entry_errors as _shared_test_spec_entry_errors,
        )
    except ImportError:
        _shared_test_spec_entry_errors = None
    ...
    def test_spec_entry_errors(path, data, schema):
        if _shared_test_spec_entry_errors is None:
            return []          # <-- no WARNING anywhere on this path
        return _shared_test_spec_entry_errors(path, data, schema)

— confirmed by reading scripts/commit_guardian/_test_spec_entry_bridge.py at
HEAD: the ImportError branch prints nothing. So when the entry-naming
module cannot be resolved, validation still runs (the generic jsonschema
pass is untouched and still blocks a bad-angle AC — the hook is NOT broken),
but the entry-naming enhancement silently vanishes with no operator-visible
signal at all — the same "fail-open, but say so" posture this hook already
applies everywhere else (see e.g. its own "WARNING: jsonschema is not
importable ... validation was SKIPPED" precedent one layer up in
_ac_schema_validators.py). This test proves that gap is real, today.

HOOK PATH NOTE: this file drives scripts/commit_guardian/check_ac_schema.py
(the SAME path unit_tests/commit_guardian/test_tq_500f_check_ac_schema_entry_naming.py
already uses, kept consistent with the rest of that batch). That path is a
gitignored BUILD copy (see .gitignore:12) — the tracked git SOURCE is
templates/scripts/commit_guardian/check_ac_schema.py. The two are
byte-identical at the time of writing (confirmed via `diff`, 0 lines) and
this file's whole point is to run an ISOLATED COPY of the commit_guardian
directory anyway (never the checked-out copy in place), so the choice of
source-vs-build origin for that one-time copy does not change what is
exercised. templates/scripts/commit_guardian/_ac_store_locator.py's own
ARCHITECTURE docstring documents the very deploy mechanism (a verbatim
directory copy) that makes the two identical.

HARNESS — SIMULATING "THE MODULE CANNOT BE IMPORTED" WITHOUT TOUCHING REAL
FILES: a whole-directory `shutil.copytree` of the real commit_guardian/ into
a throwaway tempfile.TemporaryDirectory() (auto-cleaned even on assertion
failure), run from there. Alongside it, a throwaway scripts/ac_store/
sibling is built containing ONLY an empty `done_proof.py` stub — enough to
satisfy _ac_store_locator.resolve_ac_store_dir()'s own detection rule
(`(candidate / "done_proof.py").is_file()`, read directly from that file's
source before writing this test) so path resolution SUCCEEDS, while
_ac_schema_test_spec_validators.py itself is deliberately absent — the
precise "resolvable directory, missing module" shape the bridge's ImportError
branch exists to handle. PYTHONPATH is stripped from the subprocess
environment so no real scripts/ac_store/ can leak in and mask the gap.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_REAL_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
_SCHEMA_FILE = _REPO_ROOT / "config" / "ac_store_schema.json"
_ENTRY_NAME = "test_gate_blocks_on_missing_input"

_BASE_FIELDS = {
    "component": "finalize",
    "components": ["finalize"],
    "status": "active",
    "created_by": "tickets/test.md",
    "priority": "medium",
    "readiness": "draft",
}


def _build_isolated_layout(root: Path) -> tuple[Path, Path]:
    """Build a throwaway repo-shaped layout missing only the bridge target.

    Returns:
        (hook_script_path, staged_ac_yaml_path)
    """
    # 1) An isolated copy of the whole commit_guardian/ directory — the
    #    hook plus every real sibling it needs (_ac_schema_validators.py,
    #    _test_spec_entry_bridge.py, _ac_store_locator.py, _ac_store_index.py, ...).
    hook_dir = root / "scripts" / "commit_guardian"
    shutil.copytree(
        _REAL_COMMIT_GUARDIAN_DIR,
        hook_dir,
        ignore=shutil.ignore_patterns("__pycache__"),
    )

    # 2) A throwaway ac_store/ sibling: present (so _ac_store_locator's own
    #    candidate-1 check `_HERE.parent / "ac_store"` resolves) and carrying
    #    an empty done_proof.py (so resolve_ac_store_dir()'s own is_file()
    #    probe succeeds) — but WITHOUT _ac_schema_test_spec_validators.py.
    ac_store_dir = root / "scripts" / "ac_store"
    ac_store_dir.mkdir(parents=True, exist_ok=True)
    (ac_store_dir / "done_proof.py").write_text("", encoding="utf-8")

    # 3) A throwaway store: real schema copy + one staged bad-angle AC.
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_SCHEMA_FILE, config_dir / "ac_store_schema.json")

    ac_dir = root / "docs" / "acceptance-criteria"
    ac_dir.mkdir(parents=True, exist_ok=True)
    record = dict(_BASE_FIELDS)
    record["id"] = "ZZP-920"
    record["title"] = "TQ-500f missing-bridge probe"
    record["criteria"] = "Given x\nWhen y\nThen z\n"
    record["test_spec"] = [
        {
            "name": _ENTRY_NAME,
            "target_dir": "unit_tests/ac_store/",
            "angle": "discriminating",
        }
    ]
    ac_path = ac_dir / "ZZP-920.yaml"
    ac_path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")

    return hook_dir / "check_ac_schema.py", ac_path


class TestMissingBridgeModuleWarnsInsteadOfSilentlySkipping:
    """angle: failure — the fail-open path for a resolvable-but-incomplete
    ac_store/ sibling must be loud, not silent."""

    def test_missing_bridge_module_warns_instead_of_silently_skipping(self) -> None:
        # covers: TQ-500f-2-i
        # angle: failure
        """WRONG VERSION THIS CATCHES (today's actual code, confirmed live):
        _test_spec_entry_bridge.py's `except ImportError:
        _shared_test_spec_entry_errors = None` branch prints nothing, and
        `test_spec_entry_errors()` then returns `[]` in total silence. A
        commit author (or a future reader of CI logs) sees the AC rejected —
        correctly, since the generic jsonschema pass is unaffected — with no
        indication that the entry-naming enhancement never ran at all."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hook_script, ac_path = _build_isolated_layout(root)

            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env["HOOK_ROOT"] = str(root)
            env["HOOK_TEST_STAGED_FILES"] = str(ac_path)
            env["HOOK_NO_GIT"] = "1"

            result = subprocess.run(
                [sys.executable, str(hook_script)],
                env=env,
                capture_output=True,
                text=True,
                cwd=str(root),
                timeout=60,
            )

        # Still blocked: the generic jsonschema pass does not depend on the
        # bridge, so a bad-angle AC must still fail validation either way.
        assert result.returncode != 0, (
            f"a bad-angle AC must still be rejected even when the "
            f"entry-naming bridge cannot resolve its target module.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        stderr = result.stderr
        assert "1 file(s) failed validation" in stderr, (
            f"hook must report exactly one failed file (proves it saw the "
            f"staged probe): {stderr}"
        )

        assert "WARNING" in stderr, (
            f"a resolvable-but-incomplete ac_store/ sibling (done_proof.py "
            f"present, _ac_schema_test_spec_validators.py absent) must "
            f"produce a WARNING, not silence:\n{stderr}"
        )
        assert "_ac_schema_test_spec_validators" in stderr, (
            f"the WARNING must name the specific missing module:\n{stderr}"
        )
        assert (
            "entry-naming" in stderr.lower()
            or "did not run" in stderr.lower()
            or "not run" in stderr.lower()
        ), (
            f"the WARNING must say the entry-naming check did not run (not "
            f"just that a module was missing):\n{stderr}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
