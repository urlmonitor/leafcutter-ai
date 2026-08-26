"""
MODULE: unit_tests/commit_guardian/test_bp_100k_5_ii.py
GOAL: BP-100k-5-ii — close the real coverage gap BP-100k-5's widened scan
    surfaced: a "write-if-absent scaffold" family of files committed at a
    ``.claude/``-rooted path in this repo (CLAUDE.md, docs/{vision,roadmap,
    glossary,glossary_blacklist}, tickets/{README.md,ticket_lifecycle.json,
    every folder's .gitkeep}, unit_tests/README.md) with no CURRENT build
    phase writing to that exact location. Once BP-100k-5 made ".claude"
    itself part of the scanned tree (any bare-".claude"-parented
    output_mappings key — settings.json, precommit-autofix.json,
    changelog_categories.md — pulls the whole directory into
    ``_derive_scan_dirs()``), these 15 real, git-tracked files were swept up
    and reported as ``UNCOMPARABLE: GAP`` on every commit, blocking the
    ``always_run: true`` gate permanently.
BUSINESS CONTEXT: ten of the fifteen (every .gitkeep, tickets/README.md,
    ticket_lifecycle.json, unit_tests/README.md) still render byte-identical
    to a real template/constant source, so ``build_helpers.py``'s
    ``_register_scaffold_if_unmodified`` gate (the SAME still-matches-the-
    pristine-render mechanism already used for
    ``.claude/precommit-autofix.json`` / ``.claude/changelog_categories.md``)
    registers them while pristine and releases them (never reports drift)
    the moment a project's copy diverges. The other five (CLAUDE.md,
    vision.md, roadmap.json, glossary.md, glossary_blacklist.md) are
    write-if-absent IDENTITY scaffolds the project is expected to own and
    hand-edit immediately after seeding — a pristine-render registration
    would only ever survive one commit — so they are declared as grounded,
    individually-named entries in commit_guardian.json's
    ``drift_gate_exemption_registry`` instead.
    See docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
    BP-100k-5.yaml and the ticket that authored this fix.
ARCHITECTURE / EXERCISE STRATEGY: mirrors test_bp_100k_5.py exactly — a
    REAL, isolated, freshly built consumer-layout tree
    (``<workspace>/leafcutter-ai``, built via
    ``unit_tests.build_guards.test_bp_100k_2._build_synthetic_full_package``,
    loaded read-only via ``importlib`` rather than duplicated), then the
    REAL ``python <workspace>/leafcutter-ai/scripts/build.py --target-dir
    <workspace>`` CLI subprocess, then the REAL deployed
    ``check_output_drift.py`` copy invoked as a subprocess. The 15 target
    files are seeded into the synthetic workspace's ``.claude/`` tree from
    THIS repo's own REAL, on-disk, git-tracked copies (never a hand-typed
    fixture) — per CLAUDE.md's "Spot-check the REAL data format" rule, this
    is the actual artifact the gate scans in production, not a paraphrase of
    it. Per CLAUDE.md's "Gate / Workflow ACs — Verify Behaviorally, Not by
    Grep" rule, no test here greps the gate source or a config file; every
    assertion reads the gate's own emitted RESULT / UNCOMPARABLE: lines from
    a real subprocess run.
RED BASELINE (captured 2026-08-25, before any production-code change,
    against a real isolated build seeded with the real committed
    ``.claude/`` scaffold files): all 15 target keys are reported as
    ``UNCOMPARABLE: GAP <key> action=run build.py to register it`` and the
    hook exits 2 — confirmed by reverting the ``build_helpers.py`` /
    ``commit_guardian.json`` changes locally and re-running this file, which
    turns every test below red (see the ticket's sign-off comment for the
    exact command used).
"""

from __future__ import annotations

import importlib.util
import re
import shutil
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

# The real, git-tracked scaffold files this fix registers/exempts, relative
# to the repo root. Split by the route this ticket applied — asserted
# separately below because a Route A (registered) key and a Route B
# (exempted) key must show up differently in the gate's own output.
_ROUTE_A_KEYS = (
    ".claude/tickets/README.md",
    ".claude/tickets/ticket_lifecycle.json",
    ".claude/tickets/00_inbox/.gitkeep",
    ".claude/tickets/00_inbox/epics/.gitkeep",
    ".claude/tickets/01_todo/.gitkeep",
    ".claude/tickets/99_done/.gitkeep",
    ".claude/tickets/99_rejected/.gitkeep",
    ".claude/tickets/epics/.gitkeep",
    ".claude/changelogs/.gitkeep",
    ".claude/unit_tests/README.md",
)
_ROUTE_B_KEYS = (
    ".claude/CLAUDE.md",
    ".claude/docs/vision.md",
    ".claude/docs/roadmap.json",
    ".claude/docs/glossary.md",
    ".claude/docs/glossary_blacklist.md",
)
_ALL_TARGET_KEYS = _ROUTE_A_KEYS + _ROUTE_B_KEYS

_RESULT_LINE_RE = re.compile(
    r"check-output-drift:\s*RESULT\s+"
    r"verified=(\d+)\s+uncomparable=(\d+)\s+exempt=(\d+)\s+gaps=(\d+)\s+"
    r"drifted=(\d+)",
    re.IGNORECASE,
)
# GAP lines end "... <key> action=<text>"; EXEMPT lines end
# "... <key> ground=<text>" (see check_output_drift.py's _scan_output_files).
# Both trailing fields are captured into the same group 3 — callers only
# read it for EXEMPT verdicts.
_UNCOMPARABLE_KEY_RE = re.compile(
    r"^UNCOMPARABLE:\s*(GAP|EXEMPT)\s+(\S+)\s+(?:action|ground)=(.*)$", re.MULTILINE
)


def _load_build_synthetic_full_package():
    """Load ``_build_synthetic_full_package`` from test_bp_100k_2.py.

    Loaded read-only via ``importlib.util.spec_from_file_location`` under a
    private module name (matching test_bp_100k_5.py's identical helper)
    rather than duplicating the copy-the-real-templates logic here, and
    never imported as a bare ``test_bp_100k_2`` module name so this does not
    collide with pytest's own collection of that file.

    Returns:
        The ``_build_synthetic_full_package(workspace: Path) -> Path``
        function object from that module.
    """
    spec = importlib.util.spec_from_file_location(
        "_bp100k5ii_synthetic_package_helper", _SYNTHETIC_PACKAGE_HELPER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module._build_synthetic_full_package


def _run_hook(hook_path: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Execute the real deployed gate module as a subprocess.

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


def _seed_real_claude_scaffold(workspace: Path) -> None:
    """Copy THIS repo's real, committed ``.claude/`` scaffold files into workspace.

    Uses the actual on-disk, git-tracked artifacts (never a hand-typed
    fixture) so the test exercises the exact byte content the gate compares
    in production — per CLAUDE.md's "Spot-check the REAL data format" rule.
    The 8 ``.gitkeep`` files are always empty by contract, so they are
    written directly rather than copied.

    Args:
        workspace: The isolated, freshly-created target root to seed.
    """
    real_content_files = (
        ".claude/CLAUDE.md",
        ".claude/docs/vision.md",
        ".claude/docs/roadmap.json",
        ".claude/docs/glossary.md",
        ".claude/docs/glossary_blacklist.md",
        ".claude/tickets/README.md",
        ".claude/tickets/ticket_lifecycle.json",
        ".claude/unit_tests/README.md",
    )
    for rel in real_content_files:
        src = _REPO_ROOT / rel
        if not src.is_file():
            raise unittest.SkipTest(
                f"setup precondition unmet: {src} is not a real file in this "
                "checkout — cannot seed the real artifact this test exercises."
            )
        dst = workspace / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    gitkeep_rels = (
        ".claude/tickets/00_inbox/.gitkeep",
        ".claude/tickets/00_inbox/epics/.gitkeep",
        ".claude/tickets/01_todo/.gitkeep",
        ".claude/tickets/99_done/.gitkeep",
        ".claude/tickets/99_rejected/.gitkeep",
        ".claude/tickets/epics/.gitkeep",
        ".claude/changelogs/.gitkeep",
    )
    for rel in gitkeep_rels:
        dst = workspace / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"")


class TestCommittedClaudeScaffoldGroupClearsTheGate(unittest.TestCase):
    """BP-100k-5-ii: the 15-file scaffold group must never report as GAP on
    a freshly built, unmodified tree; the 5 identity files must show up as
    grounded EXEMPT entries, not silent passes."""

    @classmethod
    def setUpClass(cls) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmpdir.cleanup)
        cls._workspace = Path(tmpdir.name)

        _seed_real_claude_scaffold(cls._workspace)

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

    def setUp(self) -> None:
        if self._build_result.returncode != 0:
            self.fail(
                "setup bug: the real build over an isolated, freshly seeded "
                "checkout failed. "
                f"stdout:\n{self._build_result.stdout}\n"
                f"stderr:\n{self._build_result.stderr}"
            )
        if not self._hook.exists():
            self.fail(f"setup bug: deployed hook not found at {self._hook}")

        for rel in _ALL_TARGET_KEYS:
            self.assertTrue(
                (self._workspace / rel).is_file(),
                f"setup bug: seeded file {rel} not found in the workspace "
                "before running the gate.",
            )

        result = _run_hook(self._hook, self._workspace)
        self._combined = result.stdout + result.stderr
        self._returncode = result.returncode

        self._gap_keys: set[str] = set()
        self._exempt_grounds: dict[str, str] = {}
        for verdict, key, ground in _UNCOMPARABLE_KEY_RE.findall(self._combined):
            if verdict == "GAP":
                self._gap_keys.add(key)
            else:
                self._exempt_grounds[key] = ground

    def test_no_scaffold_group_file_is_reported_as_a_gap(self) -> None:
        # covers: BP-100k-5
        still_gapping = sorted(k for k in _ALL_TARGET_KEYS if k in self._gap_keys)
        self.assertEqual(
            [],
            still_gapping,
            msg=(
                f"{len(still_gapping)} of the {len(_ALL_TARGET_KEYS)} "
                "write-if-absent scaffold group file(s) are still reported "
                f"as UNCOMPARABLE: GAP: {still_gapping}. Output:\n{self._combined}"
            ),
        )

    def test_route_a_files_are_registered_and_compared_not_merely_ignored(self) -> None:
        # covers: BP-100k-5
        for key in _ROUTE_A_KEYS:
            with self.subTest(key=key):
                self.assertNotIn(
                    key,
                    self._exempt_grounds,
                    msg=(
                        f"{key} is a Route A (register-while-pristine) file "
                        "but was reported as EXEMPT instead of being silently "
                        f"verified. Output:\n{self._combined}"
                    ),
                )
                self.assertNotIn(
                    key,
                    self._gap_keys,
                    msg=f"{key} still reported as GAP. Output:\n{self._combined}",
                )

    def test_route_b_files_are_declared_exempt_with_a_real_ground(self) -> None:
        # covers: BP-100k-5
        for key in _ROUTE_B_KEYS:
            with self.subTest(key=key):
                self.assertIn(
                    key,
                    self._exempt_grounds,
                    msg=(
                        f"{key} is a Route B (grounded-exemption) identity "
                        "scaffold but was not reported as EXEMPT at all — "
                        f"either silently dropped or still a GAP. Output:\n{self._combined}"
                    ),
                )
                ground = self._exempt_grounds[key]
                self.assertTrue(
                    ground and ground.strip() and ground.strip() != "None",
                    msg=(
                        f"{key} was reported as EXEMPT with a blank/missing "
                        f"ground: {ground!r}. Output:\n{self._combined}"
                    ),
                )

    def test_clean_tree_exits_zero_for_the_scaffold_group(self) -> None:
        # covers: BP-100k-5
        match = _RESULT_LINE_RE.search(self._combined)
        self.assertIsNotNone(match, f"No RESULT summary line. Output:\n{self._combined}")
        gaps = int(match.group(4))
        self.assertEqual(
            0,
            gaps,
            msg=(
                f"RESULT reports gaps={gaps} on a freshly built, unmodified "
                f"tree seeded with the real scaffold group. Output:\n{self._combined}"
            ),
        )
        self.assertEqual(
            0,
            self._returncode,
            msg=f"Freshly built tree did not exit 0. Output:\n{self._combined}",
        )


class TestCustomisedRouteAScaffoldIsReleasedNotDrifted(unittest.TestCase):
    """BP-100k-5-ii: once a project customises a Route A scaffold file, the
    NEXT build must release it from comparison (drop it from
    output_mappings) rather than reporting a hash-mismatch DRIFT violation —
    a customisation is not a policy breach the way editing a build-generated
    output normally is, for a file explicitly registered as
    still-matches-the-pristine-render only."""

    @classmethod
    def setUpClass(cls) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmpdir.cleanup)
        cls._workspace = Path(tmpdir.name)
        cls._probe_key = ".claude/tickets/README.md"

        _seed_real_claude_scaffold(cls._workspace)

        build_synthetic_full_package = _load_build_synthetic_full_package()
        pkg_root = build_synthetic_full_package(cls._workspace)
        cls._build_script = pkg_root / "scripts" / "build.py"

        first_build = subprocess.run(
            [sys.executable, str(cls._build_script), "--target-dir", str(cls._workspace)],
            cwd=str(cls._workspace),
            capture_output=True,
            text=True,
            timeout=_BUILD_TIMEOUT_SECONDS,
        )
        cls._first_build = first_build
        cls._hook = cls._workspace / "scripts" / "commit_guardian" / "check_output_drift.py"

        # Customise the probe file BEFORE the second build, exactly as a
        # project hand-editing a scaffold would, then rebuild so the
        # manifest is regenerated against the now-diverged on-disk content.
        probe_path = cls._workspace / cls._probe_key
        original = probe_path.read_text(encoding="utf-8")
        probe_path.write_text(
            original + "\n<!-- project customisation -->\n", encoding="utf-8"
        )
        cls._second_build = subprocess.run(
            [sys.executable, str(cls._build_script), "--target-dir", str(cls._workspace)],
            cwd=str(cls._workspace),
            capture_output=True,
            text=True,
            timeout=_BUILD_TIMEOUT_SECONDS,
        )

    def setUp(self) -> None:
        if self._first_build.returncode != 0:
            self.fail(
                f"setup bug: first build failed. stdout:\n{self._first_build.stdout}\n"
                f"stderr:\n{self._first_build.stderr}"
            )
        if self._second_build.returncode != 0:
            self.fail(
                f"setup bug: second build (after customisation) failed. "
                f"stdout:\n{self._second_build.stdout}\n"
                f"stderr:\n{self._second_build.stderr}"
            )
        result = _run_hook(self._hook, self._workspace)
        self._combined = result.stdout + result.stderr
        self._returncode = result.returncode

    def test_customised_scaffold_is_not_reported_as_drift(self) -> None:
        # covers: BP-100k-5
        self.assertNotIn(
            f"output:   {self._probe_key}",
            self._combined,
            msg=(
                f"{self._probe_key} was customised (a normal, expected "
                "action for this file class) but the gate reported it in "
                "the BLOCKED directly-edited-output block — it should have "
                "been silently released from comparison instead. "
                f"Output:\n{self._combined}"
            ),
        )

    def test_customised_scaffold_falls_back_to_an_individually_named_gap(self) -> None:
        # covers: BP-100k-5
        gap_re = re.compile(
            rf"^UNCOMPARABLE:\s*GAP\s+{re.escape(self._probe_key)}\b", re.MULTILINE
        )
        self.assertRegex(
            self._combined,
            gap_re,
            msg=(
                f"{self._probe_key}, once customised, must be released from "
                "output_mappings and reported as its own UNCOMPARABLE: GAP "
                f"(never silently dropped). Output:\n{self._combined}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
