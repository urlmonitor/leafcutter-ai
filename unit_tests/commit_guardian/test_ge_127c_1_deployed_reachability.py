"""
MODULE: unit_tests/commit_guardian/test_ge_127c_1_deployed_reachability.py
COVERS: GE-127c-1 -- "The outcome states which kinds of file it measured, so
    a kind that was never measured is not read as having passed"

GOAL: RED test-first stubs for the two descriptors that prove GE-127c-1's
    declaration behaviour is reachable from a REAL entry point rather than
    only from a direct script invocation:

    - reachability: the declaration appears in the REAL, registered
      run_hook.py wrapper's own output (the production entry point this
      AC's test_spec names), not only when check_file_size.py is called
      directly; and
    - deployed: after a REAL build.py deploy, the DEPLOYED
      commit_guardian.json -- the one config.py:19 actually resolves beside
      the deployed script -- carries the pinned scope, and the deployed
      gate applies it.

    Both descriptors share the theme "does this survive past the source
    tree, through a real production entry point" -- the reachability
    descriptor for the registered hook wrapper, the deployed descriptor for
    a from-scratch build.py deploy. See test_ge_127c_1_scope_declaration.py
    for the sibling descriptors covering the declaration's content, and
    _ge_127c_1_scope_fixture.py for every shared helper.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127c-1.yaml and its parents GE-127c.yaml / GE-127.yaml.

DECISION HISTORY
- 2026-09-14 [GE-127c-1/test-writer]: Initial authoring of all seven RED
    test stubs per GE-127c-1's test_spec, in test_ge_127c_1.py. Verified RED
    via `python -m unittest discover -s unit_tests/commit_guardian -t . -p
    "test_ge_127c_1.py"`.
- 2026-09-14 [GE-127c-1/test-writer]: Split out of test_ge_127c_1.py (579
    counted lines, over the 400-line check-file-size limit this AC itself
    widened) into this file, grouped by what these two descriptors prove:
    the declaration survives past a direct script call, through a real
    production entry point (the registered hook wrapper; a real build.py
    deploy). Pure move -- no assertion changed. Re-verified RED via
    `python -m pytest
    unit_tests/commit_guardian/test_ge_127c_1_deployed_reachability.py -v`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _ge_127c_1_scope_fixture import (  # noqa: E402
    BUILD_PY,
    BUILD_TIMEOUT_SECONDS,
    PYTHON,
    SUBPROCESS_TIMEOUT_SECONDS,
    asserts_kind_measured,
    asserts_kind_not_measured,
    commit_all,
    content,
    init_repo,
    run_check_via_hook,
    stage_all,
)

# ---------------------------------------------------------------------------
# 6. Reachability -- the declared kinds reach the registered hook output
# ---------------------------------------------------------------------------


class TestDeclaredKindsReachTheRegisteredHookOutput(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        init_repo(self.root)

    def test_ge_127c_1_the_declared_kinds_reach_the_registered_hook_output(self):
        # covers: GE-127c-1
        # angle: reachability
        """PRODUCTION ENTRY POINT. Run the gate as a subprocess through the
        REAL, registered run_hook.py wrapper (mirroring the consumer-layout
        entry point ``python .leafcutter/scripts/commit_guardian/run_hook.py
        .leafcutter/scripts/commit_guardian/check_file_size.py`` this AC's
        test_spec names) and assert the statement of measured / not-measured
        kinds appears in the hook's own output stream, and that the exit
        status is the commit outcome (0, since nothing here is refused)
        rather than an advisory note only a direct function call could see.

        RED TODAY: identical reasoning to the declaration descriptors in
        test_ge_127c_1_scope_declaration.py -- no measured-kinds statement
        exists anywhere in check_file_size.py's output today, so neither
        assertion can be satisfied, regardless of entry point.
        """
        (self.root / "in_scope.py").write_text(content(10), encoding="utf-8")
        (self.root / "out_of_scope.css").write_text("body { color: red; }\n", encoding="utf-8")
        stage_all(self.root)

        result = run_check_via_hook(self.root)
        combined = result.stdout + result.stderr

        self.assertTrue(
            asserts_kind_measured(combined, ".py"),
            msg=f"The registered hook's own output must state .py was measured. Got: {combined!r}",
        )
        self.assertTrue(
            asserts_kind_not_measured(combined, ".css"),
            msg=f"The registered hook's own output must state .css was NOT measured. Got: {combined!r}",
        )
        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "Neither staged file is refused; this commit must complete "
                f"through the registered entry point. Got: stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            ),
        )


# ---------------------------------------------------------------------------
# 7. Deployed -- the deployed configuration carries the pinned scope
# ---------------------------------------------------------------------------

_SHARED_BUILD_DIR: Path | None = None


def setUpModule() -> None:  # noqa: N802 -- unittest module-level hook name
    """Build the project once into a shared temp dir for every test to copy."""
    global _SHARED_BUILD_DIR
    base = Path(tempfile.mkdtemp(prefix="ge127c1_build_"))
    result = subprocess.run(
        [PYTHON, str(BUILD_PY), "--target-dir", str(base)],
        capture_output=True,
        text=True,
        timeout=BUILD_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        shutil.rmtree(base, ignore_errors=True)
        raise RuntimeError(f"build.py itself failed during setUpModule: stdout={result.stdout} stderr={result.stderr}")
    _SHARED_BUILD_DIR = base


def tearDownModule() -> None:  # noqa: N802 -- unittest module-level hook name
    """Remove the shared build output after every test in this module has run."""
    if _SHARED_BUILD_DIR is not None:
        shutil.rmtree(_SHARED_BUILD_DIR, ignore_errors=True)


def _fresh_deployed_repo() -> Path:
    """Copy the shared build.py output into a fresh temp dir and return its path."""
    assert _SHARED_BUILD_DIR is not None, "setUpModule must run before any test"
    dst = Path(tempfile.mkdtemp(prefix="ge127c1_repo_"))
    shutil.copytree(_SHARED_BUILD_DIR, dst, dirs_exist_ok=True)
    return dst


def _run_registered_hook(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke the REAL pre-commit CLI, targeting the check-file-size hook id."""
    return subprocess.run(
        ["pre-commit", "run", "check-file-size"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


class TestDeployedConfigurationCarriesThePinnedScopeAndApplies(unittest.TestCase):
    """After a REAL build.py deploy, the deployed commit_guardian.json --
    the one config.py:19 actually resolves beside the deployed script --
    must carry the pinned scope and the deployed gate must apply it."""

    def setUp(self) -> None:
        self.root = _fresh_deployed_repo()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        init_repo(self.root)
        commit_all(self.root, "initial deploy")

    def test_ge_127c_1_the_deployed_configuration_carries_the_pinned_scope_and_the_deployed_gate_applies_it(self):
        # covers: GE-127c-1
        # angle: deployed
        """This is the descriptor that catches the single most likely way
        for this record to appear done and change nothing: the canonical
        template edited and the build never re-run. config.py:19 resolves
        commit_guardian.json relative to __file__ -- i.e. beside the
        DEPLOYED script -- so a scope change written only into
        templates/scripts/commit_guardian/commit_guardian.json is invisible
        to the deployed gate until build.py is re-run.

        RED TODAY: the deployed commit_guardian.json's file_size section is
        copied verbatim from today's real template ({.py, .sql} only), so
        the pinned-extension membership check below fails, naming every
        missing kind.
        """
        deployed_config_path = self.root / "scripts" / "commit_guardian" / "commit_guardian.json"
        self.assertTrue(
            deployed_config_path.exists(),
            msg=f"{deployed_config_path} was not deployed by build.py.",
        )

        deployed_config = json.loads(deployed_config_path.read_text(encoding="utf-8"))
        deployed_file_size = deployed_config.get("file_size", {})
        deployed_extensions = set(deployed_file_size.get("checked_extensions", []))
        deployed_limits = deployed_file_size.get("line_limits", {})

        pinned_extensions = {".py", ".sql", ".js", ".mjs", ".ts", ".tsx", ".sh"}
        pinned_limits = {".py": 400, ".sql": 600, ".js": 1000, ".mjs": 1000, ".ts": 400, ".tsx": 400, ".sh": 400}

        missing = pinned_extensions - deployed_extensions
        self.assertFalse(
            missing,
            msg=(
                "The DEPLOYED commit_guardian.json is missing these pinned "
                f"kinds from checked_extensions: {sorted(missing)}. Deployed "
                f"checked_extensions={sorted(deployed_extensions)!r}"
            ),
        )
        mismatched = {
            ext: (deployed_limits.get(ext), pinned_limits[ext])
            for ext in pinned_extensions
            if deployed_limits.get(ext) != pinned_limits[ext]
        }
        self.assertFalse(
            mismatched,
            msg=(
                "The DEPLOYED commit_guardian.json's line_limits do not "
                f"match the pinned per-kind limits: {mismatched!r} "
                "(ext: (deployed, pinned))"
            ),
        )

        oversized_js = self.root / "workflow.js"
        oversized_js.write_text(content(1001), encoding="utf-8")
        stage_all(self.root)

        result = _run_registered_hook(self.root)
        combined = result.stdout + result.stderr
        self.assertNotIn(
            "ModuleNotFoundError",
            combined,
            msg=f"Deployed check-file-size crashed importing a dependency. Got: {combined!r}",
        )
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "The DEPLOYED gate, in a cold process, must refuse a real "
                f"1001-line .js file at the pinned 1000-line limit. Got: "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            ),
        )
        self.assertIn("workflow.js", combined, msg=f"Outcome must name the file. Got: {combined!r}")


if __name__ == "__main__":
    unittest.main()
