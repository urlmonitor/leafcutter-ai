"""
MODULE: unit_tests/commit_guardian/test_bp_100k_5_i.py
GOAL: BP-100k-5-i — the anti-shortcut guard on BP-100k-5. The unexamined
    deployed population must reach zero by REGISTERING the deploy surface
    (recording each real deployed file's expected hash in output_mappings),
    never by declaring a single exemption that covers a whole directory of
    build-produced outputs. The cheapest wrong fix for BP-100k-5 is exactly
    that bulk exemption — it would satisfy the letter (not-compared count
    reads zero) while rebuilding the silent suppression list BP-100k-3
    removed. This file is the guard that must fail on that shortcut and
    pass only on real per-file registration.
BUSINESS CONTEXT: see test_bp_100k_5.py's module docstring for the root
    cause (``_OUTPUT_REL_TO_CANONICAL``'s single-path-component filter
    dropping every multi-segment ``shim_map`` entry, e.g.
    ``scripts/commit_guardian``). This file additionally probes the
    exemption-registry mechanism (``_drift_exemptions.py``,
    ``HOOK_TEST_CONFIG``) to prove that a directory-shaped entry cannot
    silently cover the newly-widened population, and that a hand-edit to a
    file DRAWN FROM that population is caught once real coverage exists.
ARCHITECTURE / EXERCISE STRATEGY: setUpClass builds a real, isolated,
    freshly-built tree exactly as test_bp_100k_5.py does (real
    templates/scripts/config copied into a consumer-layout temp workspace,
    real ``build.py --target-dir`` subprocess, real deployed gate copy
    executed as a subprocess). Every test then executes the DEPLOYED gate
    again against that same real tree — never a synthesized subset (the
    AC's own constraint: "the omitted files are exactly the ones a
    hand-picked fixture would leave out"). Per CLAUDE.md's standing rule
    ("Gate / Workflow ACs — Verify Behaviorally, Not by Grep"), no test
    here greps the gate source or any config file; the bulk-exemption probe
    injects its candidate entry through the REAL ``HOOK_TEST_CONFIG``
    data-interface the gate itself reads at runtime (the same interface
    test_bp_100k_3.py's own contract uses), then reads the gate's own
    emitted output — never the exemption registry's raw text.
RED BASELINE (captured 2026-08-25, before any production-code change,
    against a real isolated build): the real deployed surface's
    scripts/commit_guardian/ family (118 files, including the drift gates'
    own deployed copies) is entirely unregistered and entirely uncollected
    — not even a GAP is emitted for it — so every assertion below that
    requires the widened population to be individually accounted for, or
    to be drift-detectable once hand-edited, is RED today.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SYNTHETIC_PACKAGE_HELPER_PATH = (
    _REPO_ROOT / "unit_tests" / "build_guards" / "test_bp_100k_2.py"
)

_BUILD_TIMEOUT_SECONDS = 180
_SUBPROCESS_TIMEOUT_SECONDS = 20

_DEPLOYED_SURFACE_DIRS = (".claude", ".gemini", "scripts")
_RULES_SUBPATH = Path(".leafcutter") / ".agents" / "rules"

# The single highest-value probe file named in the coordinator's root-cause
# finding: a deployed file under a MULTI-SEGMENT shim_map prefix
# ("scripts/commit_guardian") — the exact family
# _OUTPUT_REL_TO_CANONICAL's "if '/' not in output_rel" filter excludes.
# It is also the drift gate's own deployed copy: the drift gates do not
# police the drift gates until this AC closes that gap.
_PROBE_KEY = "scripts/commit_guardian/check_output_drift.py"

_RESULT_LINE_RE = re.compile(
    r"(check-build-drift|check-output-drift):\s*RESULT\s+"
    r"verified=(\d+)\s+uncomparable=(\d+)\s+exempt=(\d+)\s+gaps=(\d+)\s+"
    r"drifted=(\d+)",
    re.IGNORECASE,
)
_UNCOMPARABLE_KEY_RE = re.compile(r"^UNCOMPARABLE:\s*(GAP|EXEMPT)\s+(\S+)", re.MULTILINE)


def _load_build_synthetic_full_package():
    """Load ``_build_synthetic_full_package`` from test_bp_100k_2.py.

    See test_bp_100k_5.py's identical helper for the full rationale — loaded
    read-only via ``importlib`` under a private module name so this file
    never duplicates the copy-the-real-templates logic and never collides
    with pytest's own collection of test_bp_100k_2.py.

    Returns:
        The ``_build_synthetic_full_package(workspace: Path) -> Path``
        function object from that module.
    """
    spec = importlib.util.spec_from_file_location(
        "_bp100k5i_synthetic_package_helper", _SYNTHETIC_PACKAGE_HELPER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module._build_synthetic_full_package


def _run_hook(
    hook_path: Path, cwd: Path, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    """Execute a real deployed gate module as a subprocess.

    Args:
        hook_path: Absolute path to the deployed gate module to execute.
        cwd: Working directory to run the subprocess in.
        extra_env: Optional environment overrides layered on top of the
            current process environment (e.g. ``HOOK_TEST_CONFIG``).

    Returns:
        The completed subprocess result (returncode, stdout, stderr captured).
    """
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(hook_path)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _real_deployed_files(workspace: Path) -> set[str]:
    """Walk the real, on-disk deployed surface and return repo-root-relative keys.

    See test_bp_100k_5.py's identical helper for the full rationale
    (symlink-following is required — several of these directories are
    shims, not copies).

    Args:
        workspace: The isolated, freshly-built target root.

    Returns:
        Set of forward-slash, workspace-relative path strings for every real
        file found (``__pycache__`` excluded).
    """
    files: set[str] = set()
    roots = [workspace / d for d in _DEPLOYED_SURFACE_DIRS]
    roots.append(workspace / _RULES_SUBPATH)
    for root in roots:
        if not root.exists():
            continue
        for dirpath, _dirnames, filenames in os.walk(root, followlinks=True):
            if "__pycache__" in Path(dirpath).parts:
                continue
            for name in filenames:
                p = Path(dirpath) / name
                files.add(p.relative_to(workspace).as_posix())
    return files


def _accounted_keys(combined: str, compared_keys: set[str]) -> set[str]:
    """Return every key the gate's own output accounts for in some way.

    "Accounted for" means either compared (present in output_mappings, so
    its hash was actually checked) or individually named in an
    UNCOMPARABLE: GAP/EXEMPT line. A key present in neither bucket is
    silently invisible to the run.

    Args:
        combined: Combined stdout+stderr from a gate subprocess run.
        compared_keys: The manifest's output_mappings keys.

    Returns:
        Union of compared_keys and every individually-named GAP/EXEMPT key.
    """
    named = {key for _verdict, key in _UNCOMPARABLE_KEY_RE.findall(combined)}
    return compared_keys | named


class TestUnexaminedPopulationReachesZeroByRegistrationNotExemption(unittest.TestCase):
    """BP-100k-5-i: on a freshly built, unmodified tree the unexamined count
    must be zero via real registration; a directory-wide exemption must not
    be able to fake that zero; and a hand-edit to a file drawn from the
    newly-covered population must be caught."""

    _workspace: Path
    _build_result: subprocess.CompletedProcess[str]
    _hook: Path
    _manifest_path: Path

    @classmethod
    def setUpClass(cls) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmpdir.cleanup)
        cls._workspace = Path(tmpdir.name)

        build_synthetic_full_package = _load_build_synthetic_full_package()
        pkg_root = build_synthetic_full_package(cls._workspace)
        build_script = pkg_root / "scripts" / "build.py"

        cls._build_result = subprocess.run(
            [sys.executable, str(build_script), "--target-dir", str(cls._workspace)],
            cwd=str(cls._workspace),
            capture_output=True,
            text=True,
            timeout=_BUILD_TIMEOUT_SECONDS,
        )
        cls._hook = cls._workspace / "scripts" / "commit_guardian" / "check_output_drift.py"
        cls._manifest_path = cls._workspace / ".build_manifest.json"

    def setUp(self) -> None:
        if self._build_result.returncode != 0:
            self.fail(
                "setup bug: the real build over an isolated, freshly copied "
                "checkout failed. "
                f"stdout:\n{self._build_result.stdout}\n"
                f"stderr:\n{self._build_result.stderr}"
            )
        if not self._hook.exists():
            self.fail(f"setup bug: deployed hook not found at {self._hook}")

        self._probe_path = self._workspace / _PROBE_KEY
        if not self._probe_path.exists():
            self.fail(
                f"setup bug: expected the real deployed hook copy at "
                f"{self._probe_path} — the probe file this AC's guard "
                "targets must exist on a real build."
            )

        manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        output_mappings = manifest.get("output_mappings", {})
        if not output_mappings:
            self.fail(
                "setup bug: the real, freshly built manifest has an empty "
                "output_mappings — every assertion below would pass "
                "vacuously."
            )
        self._compared_keys = set(output_mappings.keys())

        self._actual_files = _real_deployed_files(self._workspace)
        if not self._actual_files:
            self.fail("setup bug: no real deployed files found.")

    def test_freshly_built_tree_yields_zero_unexamined_deployed_files(self) -> None:
        # covers: BP-100k-5-i
        result = _run_hook(self._hook, self._workspace)
        combined = result.stdout + result.stderr
        accounted = _accounted_keys(combined, self._compared_keys)
        unexamined = sorted(self._actual_files - accounted)
        self.assertEqual(
            [],
            unexamined[:15],
            msg=(
                f"{len(unexamined)} deployed file(s) are unexamined "
                "(neither compared, nor named as a GAP, nor named as an "
                "EXEMPT) on a freshly built, unmodified tree — the "
                f"not-compared count must be zero (BP-100k-5-i). Sample: "
                f"{unexamined[:15]}. Output:\n{combined}"
            ),
        )

    def test_compared_count_equals_the_build_recorded_write_count(self) -> None:
        # covers: BP-100k-5-i
        result = _run_hook(self._hook, self._workspace)
        combined = result.stdout + result.stderr
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(match, f"No RESULT summary line. Output:\n{combined}")
        assert match is not None  # narrowing for mypy; assertIsNotNone above is the real check
        verified = int(match.group(2))
        self.assertEqual(
            len(self._actual_files),
            verified,
            msg=(
                f"verified={verified} does not equal the real deployed "
                f"file count ({len(self._actual_files)}) on a freshly "
                "built, unmodified tree — the compared count must equal "
                "the number of files the build recorded as having written "
                f"(BP-100k-5-i). Output:\n{combined}"
            ),
        )

    def test_no_build_produced_file_is_covered_by_a_directory_wide_exemption(self) -> None:
        # covers: BP-100k-5-i
        bulk_config = {
            "drift_gate_exemption_registry": [
                {
                    "path": "scripts/commit_guardian",
                    "ground": "bulk-exempt attempt over a whole directory of build-produced outputs",
                },
            ]
        }
        config_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f:
                json.dump(bulk_config, f)
                config_path = f.name
            result = _run_hook(
                self._hook, self._workspace, extra_env={"HOOK_TEST_CONFIG": config_path}
            )
        finally:
            if config_path is not None:
                os.unlink(config_path)
        combined = result.stdout + result.stderr

        self.assertNotIn(
            f"UNCOMPARABLE: EXEMPT {_PROBE_KEY}",
            combined,
            msg=(
                f"A single directory-wide exemption entry for "
                f"'scripts/commit_guardian' silently covered {_PROBE_KEY} "
                "— the exact bulk-exemption shortcut this AC forbids. An "
                "exemption must apply to a named individual artifact, "
                f"never to a whole directory of build-produced outputs. "
                f"Output:\n{combined}"
            ),
        )
        accounted = _accounted_keys(combined, self._compared_keys)
        self.assertIn(
            _PROBE_KEY,
            accounted,
            msg=(
                f"{_PROBE_KEY} is a real deployed file the build wrote, "
                "but even with an (illegitimate) directory-wide exemption "
                "entry present it is still neither compared, nor "
                "individually named as a GAP, nor individually named as a "
                "valid EXEMPT. BP-100k-5-i requires the newly-covered "
                "population to be accounted for by REGISTRATION, not by a "
                f"bulk exemption — and today it is accounted for by "
                f"neither. Output:\n{combined}"
            ),
        )

    def test_hand_edit_to_a_newly_covered_deployed_file_is_reported_as_drift(self) -> None:
        # covers: BP-100k-5-i
        real_probe_path = self._probe_path.resolve()
        original = real_probe_path.read_bytes()
        try:
            real_probe_path.write_bytes(original + b"\n# BP-100k-5-i drift probe\n")
            result = _run_hook(self._hook, self._workspace)
            combined = result.stdout + result.stderr

            self.assertIn(
                _PROBE_KEY,
                combined,
                msg=(
                    f"Hand-editing {_PROBE_KEY} (drawn from the newly "
                    "covered, previously invisible population) produced no "
                    "mention of it at all in the gate's output — the "
                    "widened coverage is not being exercised. "
                    f"Output:\n{combined}"
                ),
            )
            self.assertNotEqual(
                0,
                result.returncode,
                msg=(
                    f"Hand-editing {_PROBE_KEY} did not fail the run. A "
                    "file drawn from the newly-covered population must be "
                    "drift-detected exactly like any other registered "
                    f"output (BP-100k-5-i). Output:\n{combined}"
                ),
            )
        finally:
            real_probe_path.write_bytes(original)

    def test_clean_tree_still_passes_after_the_wider_population(self) -> None:
        # covers: BP-100k-5-i
        result = _run_hook(self._hook, self._workspace)
        combined = result.stdout + result.stderr
        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A freshly built, unmodified tree must still exit 0 once "
                f"the population is widened. Output:\n{combined}"
            ),
        )
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(match, f"No RESULT summary line. Output:\n{combined}")
        assert match is not None  # narrowing for mypy; assertIsNotNone above is the real check
        drifted = int(match.group(6))
        self.assertEqual(
            0,
            drifted,
            msg=f"A freshly built, unmodified tree reported drift. Output:\n{combined}",
        )
        verified = int(match.group(2))
        self.assertEqual(
            len(self._actual_files),
            verified,
            msg=(
                "The widened population's verified count "
                f"({verified}) must equal the real deployed total "
                f"({len(self._actual_files)}) on a clean tree, not just "
                "the narrower legacy count — a clean exit code alone does "
                "not prove the wider population was actually examined "
                f"(BP-100k-5-i). Output:\n{combined}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
