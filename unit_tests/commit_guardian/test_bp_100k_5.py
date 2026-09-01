"""
MODULE: unit_tests/commit_guardian/test_bp_100k_5.py
GOAL: BP-100k-5 — the output-drift gate's inspected population must equal
    the real deployed surface the build actually wrote, not a set inferred
    from directories the gate already knows how to look in. A verified count
    reported with no denominator (and with no accounting for what was never
    even collected) is a phantom pass in numeric form.
BUSINESS CONTEXT: check_output_drift.py's live RESULT line reads
    ``verified=275 uncomparable=2 exempt=0 gaps=2 drifted=27`` against a
    manifest whose ``output_mappings`` holds exactly 275 keys (165
    ``.claude/``, 94 ``.gemini/``, 16 ``.leafcutter/.agents/rules/*.md``).
    ``_derive_scan_dirs()`` builds its scan set from the parent directories
    of those 275 keys plus a hardcoded ``.claude/*`` floor — so any real
    deployed directory no manifest key's parent ever points at is NEVER
    added to the scan set, and ``_collect_output_files()`` therefore never
    even walks it. The root cause traced to ``scripts/build_helpers.py``:
    ``_compute_output_mappings()`` translates an output-root-relative path
    to its canonical, shim-resolved form via
    ``_OUTPUT_REL_TO_CANONICAL`` — but that reverse lookup is built with
    ``if "/" not in output_rel``, which EXCLUDES every multi-segment
    ``shim_map`` entry (``scripts/commit_guardian``, ``scripts/doc_compliance``,
    ``scripts/feedback``). ``_canonicalize_output_path()`` therefore returns
    None for every file under those three directories, and
    ``_compute_output_mappings()`` silently drops them — no record that they
    were dropped. The result, confirmed empirically against a real, fresh,
    isolated build in this ticket's investigation: 174 of 449 real deployed
    files under the ``.claude/``, ``.gemini/``, and (shimmed) ``scripts/``
    trees are recorded NOWHERE, the gate's own RESULT line still reads
    ``gaps=0`` (they are not merely uncomparable — they are never collected
    at all), and the run exits 0 (clean). The highest-value instance of this
    defect: ALL real deployed files under ``scripts/commit_guardian/`` —
    including the drift gates' own deployed copies
    (``check_output_drift.py``, ``check_build_drift.py``) — are covered by
    NOTHING. The drift gates do not police the drift gates.
    See docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
    BP-100k-5.yaml.
ARCHITECTURE / EXERCISE STRATEGY: every test below EXECUTES the real,
    unmodified-by-this-file check_output_drift.py as a subprocess over a
    REAL, freshly built, isolated deployed tree (never a synthesized
    fixture that only records what it wants tested — a fixture whose
    manifest recorded every file in its own tree would hide precisely the
    unrecorded-population defect this AC is about). setUpClass copies the
    REAL ``templates/``, ``scripts/``, and ``config/`` trees into an
    isolated ``tempfile.TemporaryDirectory`` laid out as
    ``<workspace>/leafcutter-ai`` (the supported consumer layout
    ``_compute_output_mappings()`` requires — package_root ==
    target_root/leafcutter-ai — reusing
    ``unit_tests.build_guards.test_bp_100k_2._build_synthetic_full_package``
    read-only via ``importlib`` rather than duplicating it), then invokes
    the REAL ``python <workspace>/leafcutter-ai/scripts/build.py
    --target-dir <workspace>`` CLI subprocess — every phase, unabridged,
    exactly as ``build-self.sh`` runs it — and finally executes the
    DEPLOYED gate copy at ``<workspace>/scripts/commit_guardian/
    check_output_drift.py`` (the real shimmed entry point pre-commit
    invokes) as a subprocess. Ground truth for "the real deployed surface"
    is computed independently by walking the real, on-disk
    ``.claude/``, ``.gemini/``, ``scripts/``, and
    ``.leafcutter/.agents/rules`` trees (following symlinks — several of
    these ARE shims, not copies), never by reading the gate's own idea of
    what it scanned. Per the standing rule in CLAUDE.md ("Gate / Workflow
    ACs — Verify Behaviorally, Not by Grep"), no test here greps the gate
    source or a config file; every assertion reads the gate's own emitted
    RESULT line / UNCOMPARABLE: lines / exit status from a real subprocess
    run.
RED BASELINE (captured 2026-08-25, before any production-code change,
    against a real isolated build): 174 real deployed files (most of them
    under ``scripts/commit_guardian/``, ``scripts/doc_compliance/``, and
    ``scripts/feedback/``) are absent from ``output_mappings`` AND absent
    from every ``UNCOMPARABLE:`` line — RESULT read
    ``verified=275 uncomparable=0 exempt=0 gaps=0 drifted=0``, exit 0
    (clean), while 174 real files were never inspected at all.

TestPartialExaminationIsNeverReportedAsClean (added post-fix, 2026-08-25) is
    deliberately NOT part of ``TestOutputDriftGateExaminesFullDeployedSurface``
    and does NOT share its real-full-build ``setUpClass`` fixture. That shared
    fixture's accounted-for set becomes COMPLETE once BP-100k-5 is actually
    fixed for the real deploy tree — which is exactly what a correct fix is
    supposed to do — so an assertion of the shape "assume at least one real
    deployed file is unaccounted for" is self-contradictory once the fix
    lands: it would have to fail on its own precondition guard for the fix to
    be correct. The property under test ("a run that examined only part of
    the deployed surface must not exit 0") is a property of the GATE, not an
    observation about today's real tree, so this class manufactures its own
    permanently-incomplete population directly — a manifest that deliberately
    omits one file from a directory the scan set reaches only via a sibling
    manifest key's parent — independent of how complete the real build's own
    manifest coverage is on any given day.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_CG_TEMPLATES_SRC = _TEMPLATES_DIR / "scripts" / "commit_guardian"
_SYNTHETIC_PACKAGE_HELPER_PATH = (
    _REPO_ROOT / "unit_tests" / "build_guards" / "test_bp_100k_2.py"
)

_BUILD_TIMEOUT_SECONDS = 180
_SUBPROCESS_TIMEOUT_SECONDS = 20

# The real deployed surface this AC is about. ".claude" and ".gemini" are
# real self-contained deploy targets today; "scripts" (top-level) is a
# THIRD, SEPARATE deploy target reached only via the shim symlinks
# install_shims() creates for the multi-segment shim_map entries
# (scripts/commit_guardian, scripts/doc_compliance, scripts/feedback) — the
# exact family _compute_output_mappings() silently drops. Walking with
# os.walk(followlinks=True) is required or these shimmed files would be
# invisible to the TEST's own ground truth too, which would make every
# assertion below pass vacuously.
_DEPLOYED_SURFACE_DIRS = (".claude", ".gemini", "scripts")
_RULES_SUBPATH = Path(".leafcutter") / ".agents" / "rules"

_RESULT_LINE_RE = re.compile(
    r"(check-build-drift|check-output-drift):\s*RESULT\s+"
    r"verified=(\d+)\s+uncomparable=(\d+)\s+exempt=(\d+)\s+gaps=(\d+)\s+"
    r"drifted=(\d+)",
    re.IGNORECASE,
)
_UNCOMPARABLE_KEY_RE = re.compile(r"^UNCOMPARABLE:\s*(GAP|EXEMPT)\s+(\S+)", re.MULTILINE)


def _load_build_synthetic_full_package():
    """Load ``_build_synthetic_full_package`` from test_bp_100k_2.py.

    Loaded read-only via ``importlib.util.spec_from_file_location`` under a
    private module name rather than duplicating the copy-the-real-templates
    logic in this file, matching the precedent in test_bp_100k_3_i.py. Never
    imported as a bare ``test_bp_100k_2`` module name, so this does not
    collide with pytest's own collection of that file.

    Returns:
        The ``_build_synthetic_full_package(workspace: Path) -> Path``
        function object from that module.
    """
    spec = importlib.util.spec_from_file_location(
        "_bp100k5_synthetic_package_helper", _SYNTHETIC_PACKAGE_HELPER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module._build_synthetic_full_package


def _run_hook(hook_path: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Execute a real deployed gate module as a subprocess.

    Args:
        hook_path: Absolute path to the deployed gate module to execute.
        cwd: Working directory to run the subprocess in.

    Returns:
        The completed subprocess result (returncode, stdout, stderr captured).
    """
    return subprocess.run(
        [sys.executable, str(hook_path)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _real_deployed_files(workspace: Path) -> set[str]:
    """Walk the real, on-disk deployed surface and return repo-root-relative keys.

    Follows symlinks (``os.walk(followlinks=True)``) because the real deploy
    layout SHIMS several directories (``<workspace>/.gemini`` ->
    ``.leafcutter/gemini``; ``<workspace>/scripts/commit_guardian`` ->
    ``.leafcutter/scripts/commit_guardian``, etc.) rather than copying them —
    a plain, non-symlink-following walk would silently see zero files under
    those shimmed paths and undercount the very population this AC is about.

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


class TestOutputDriftGateExaminesFullDeployedSurface(unittest.TestCase):
    """BP-100k-5: the gate's inspected population (compared + individually
    named GAP/EXEMPT) must equal the real deployed surface, not a subset
    silently bounded by directories no manifest key's parent ever mentions."""

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
                "checkout failed, so this class cannot establish the "
                "'build has just run' precondition. "
                f"stdout:\n{self._build_result.stdout}\n"
                f"stderr:\n{self._build_result.stderr}"
            )
        if not self._hook.exists():
            self.fail(f"setup bug: deployed hook not found at {self._hook}")

        manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        self._output_mappings = manifest.get("output_mappings", {})
        if not self._output_mappings:
            self.fail(
                "setup bug: the real, freshly built manifest has an empty "
                "output_mappings — every assertion below would pass "
                "vacuously over zero artifacts."
            )

        self._actual_files = _real_deployed_files(self._workspace)
        if not self._actual_files:
            self.fail(
                "setup bug: no real deployed files found under the real "
                "deployed surface directories."
            )

        result = _run_hook(self._hook, self._workspace)
        self._combined = result.stdout + result.stderr
        self._returncode = result.returncode

        self._gap_keys: set[str] = set()
        self._exempt_keys: set[str] = set()
        for verdict, key in _UNCOMPARABLE_KEY_RE.findall(self._combined):
            if verdict == "GAP":
                self._gap_keys.add(key)
            else:
                self._exempt_keys.add(key)

        self._compared_keys = set(self._output_mappings.keys())
        self._accounted_for = self._compared_keys | self._gap_keys | self._exempt_keys

    def test_a_deployed_file_in_an_unrecorded_directory_is_still_collected(self) -> None:
        # covers: BP-100k-5
        probe_key = "scripts/commit_guardian/check_output_drift.py"
        probe_path = self._workspace / probe_key
        self.assertTrue(
            probe_path.exists(),
            f"setup bug: expected the real deployed hook copy at {probe_path}",
        )
        self.assertIn(
            probe_key,
            self._accounted_for,
            msg=(
                f"{probe_key} — the deployed drift-gate hook itself — is a "
                "real, on-disk deployed output, but was neither compared "
                "(present in output_mappings), named as an "
                "UNCOMPARABLE: GAP, nor named as an UNCOMPARABLE: EXEMPT. "
                "It is entirely invisible to this run: _derive_scan_dirs() "
                "never adds scripts/commit_guardian/ to the scan set "
                "because no manifest key's parent directory ever points "
                f"there (BP-100k-5). Full output:\n{self._combined}"
            ),
        )

    def test_inspection_set_equals_what_the_build_recorded_writing(self) -> None:
        # covers: BP-100k-5
        missing = sorted(self._actual_files - self._accounted_for)
        self.assertEqual(
            [],
            missing[:15],
            msg=(
                f"{len(missing)} of {len(self._actual_files)} real deployed "
                "file(s) are neither compared, nor named as a GAP, nor "
                "named as an EXEMPT — the inspected population does not "
                "equal the real deployed surface the build wrote "
                f"(BP-100k-5). Sample of uninspected files: {missing[:15]}"
            ),
        )

    def test_run_summary_reports_compared_and_not_compared_counts_together(self) -> None:
        # covers: BP-100k-5
        match = _RESULT_LINE_RE.search(self._combined)
        self.assertIsNotNone(
            match, f"No RESULT summary line found. Output:\n{self._combined}"
        )
        assert match is not None  # narrowing for mypy; assertIsNotNone above is the real check
        verified = int(match.group(2))
        uncomparable = int(match.group(3))
        self.assertEqual(
            len(self._actual_files),
            verified + uncomparable,
            msg=(
                f"verified ({verified}) + uncomparable ({uncomparable}) = "
                f"{verified + uncomparable} does not equal the real "
                f"deployed file count ({len(self._actual_files)}). The run "
                "summary's counts are not reported against the true size "
                "of the deployed population (BP-100k-5) — several hundred "
                "deployed files are simply never counted in either figure. "
                f"Output:\n{self._combined}"
            ),
        )

    def test_every_uncompared_deployed_file_is_individually_accounted_for(self) -> None:
        # covers: BP-100k-5
        not_compared = self._actual_files - self._compared_keys
        unaccounted = sorted(
            f for f in not_compared
            if f not in self._gap_keys and f not in self._exempt_keys
        )
        self.assertEqual(
            [],
            unaccounted[:15],
            msg=(
                f"{len(unaccounted)} deployed file(s) the gate did not "
                "compare are ALSO absent from both the GAP and EXEMPT "
                "per-artifact lines — silently unaccounted for (BP-100k-5). "
                f"Sample: {unaccounted[:15]}"
            ),
        )


# ---------------------------------------------------------------------------
# test_partial_examination_is_not_reported_as_clean — deliberately its OWN
# TestCase with its OWN fixture. See the module docstring's "added post-fix"
# note for why this must NOT share TestOutputDriftGateExaminesFullDeployed
# Surface's real-full-build setUpClass fixture.
# ---------------------------------------------------------------------------


class TestPartialExaminationIsNeverReportedAsClean(unittest.TestCase):
    """BP-100k-5: a permanent, fixture-independent property of the gate.

    Manufactures a deploy tree containing a file the manifest does not
    record, sitting in a directory that is NOT one of check_output_drift.py's
    five hardcoded floor dirs (``.claude/{agents,skills,commands,hooks,
    workflows}``) — the scan set reaches that directory ONLY because a
    sibling manifest key's parent points at it (``_derive_scan_dirs()``,
    BP-100k-2/5's own derivation mechanism). Because the directory IS
    reached, the unrecorded sibling is not silently invisible — it is
    collected and must be reported as an ``UNCOMPARABLE: GAP`` (BP-100k-3),
    which must never let the run exit 0. This is independent of the real
    build's own manifest completeness on any given day: it exercises the
    scan-derivation + gap-reporting mechanism directly rather than observing
    today's real deploy tree.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)

        pkg_root = self.workspace / "leafcutter-ai"
        (pkg_root / "templates" / "agents").mkdir(parents=True)
        (pkg_root / "templates" / "scripts" / "commit_guardian").mkdir(parents=True)

        # Off-floor directory: NOT one of the five hardcoded floor dirs, so
        # the ONLY way the scan set reaches it is via a manifest key's parent
        # (BP-100k-2/5's derivation mechanism) — never a fixed, hardcoded list.
        off_floor_dir = self.workspace / ".claude" / "config"
        off_floor_dir.mkdir(parents=True)

        tracked_content = b"# recorded output in an off-floor directory\n"
        tracked_path = off_floor_dir / "tracked.md"
        tracked_path.write_bytes(tracked_content)
        self._tracked_key = tracked_path.relative_to(self.workspace).as_posix()

        # Never recorded anywhere. Collected ONLY because off_floor_dir was
        # added to the scan set as the parent of self._tracked_key above; if
        # that derivation mechanism did not exist, this file would never be
        # collected at all and would be silently invisible — the BP-100k-5
        # defect this AC exists to close.
        self._orphan_path = off_floor_dir / "orphan.md"
        self._orphan_path.write_bytes(b"# never recorded anywhere\n")
        self._orphan_key = self._orphan_path.relative_to(self.workspace).as_posix()

        manifest = {
            "output_mappings": {
                self._tracked_key: {
                    "template": "templates/agents/tracked.md",
                    "expected_output_hash": hashlib.sha256(tracked_content).hexdigest(),
                }
            },
            "package_root": pkg_root.name,
        }
        (self.workspace / ".build_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        deployed_dir = self.workspace / ".leafcutter" / "scripts" / "commit_guardian"
        shutil.copytree(
            _CG_TEMPLATES_SRC, deployed_dir, ignore=shutil.ignore_patterns("__pycache__")
        )
        self.hook = deployed_dir / "check_output_drift.py"

    def test_partial_examination_is_not_reported_as_clean(self) -> None:
        # covers: BP-100k-5
        result = _run_hook(self.hook, self.workspace)
        combined = result.stdout + result.stderr
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                f"A deploy tree containing {self._orphan_key} — unrecorded, "
                "sitting in a directory reached only via another manifest "
                "key's parent — exited 0 (clean). A run that examined only "
                "part of the deployed surface must never exit as though it "
                f"examined all of it (BP-100k-5). Output:\n{combined}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
