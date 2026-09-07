"""
MODULE: unit_tests/commit_guardian/test_bp_100n_4_ii.py
GOAL: BP-100n-4-ii — the reachability check must state four numbers in every
    run (gate scripts found on disk and compared, registry entries read,
    scripts reported as invoked by nothing, scripts treated as declared
    non-gates), so a run that examined nothing cannot look like a run that
    examined everything. An unlistable or listable-but-empty gate-script
    directory, and an unreadable or unparseable registry, must each be named
    by its own specific reason and must fail — never state a clean
    zero-invoked-by-nothing verdict.
BUSINESS CONTEXT: KI-CG-034 (169 files examined, 169 skipped, zero compared,
    exit 0), KI-CG-012, KI-CG-018, and the AC-store validator's bare-directory
    no-op (exit 0 for eight days having checked zero files) are the four
    precedents this AC exists to make structurally impossible for THIS
    guard's two new populations (BP-100n-4's disk side and its
    generated-configuration read). See
    docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100n-4-ii.yaml
    and docs/known-issues/commit-guardian.md.

NEW PRODUCTION BEHAVIOUR THIS TEST FILE SPECIFIES (does not exist yet):
    Extends the same RESULT-line and INDETERMINATE contract test_bp_100n_4.py
    and test_bp_100n_4_i.py already specify:
      ``check-hook-trigger-reachability: RESULT total=... unreachable=...
      exempt=... nothing_to_match=... compared=<n> registered=<n>
      unreferenced=<n> declared_non_gate=<n>``
      ``INDETERMINATE: reason=<text>`` on stderr, exit 2 — REUSED verbatim
      (BP-100k-4-i's existing vocabulary and exit-status contract; never a
      third verdict set). The reason text must NAME which of the two
      disk-side situations applies ("unlistable" vs. "empty" — exact
      wording is the implementer's, but the two reasons must be
      distinguishable strings, asserted below via distinct keyword
      substrings) and which of the two registry-side situations applies
      ("unreadable" vs. "unparseable").

    TEST INTERFACE CONTRACT (NEW env var this AC's test suite introduces,
    mirrors the existing HOOK_TEST_CONFIG convention this same script
    already honours for the registry side):
      ``HOOK_TEST_GATE_DIR`` — when set, the disk-side census walks THIS
      directory instead of the directory holding the running script. Used
      here to make the disk listing genuinely unlistable or genuinely empty
      without disturbing the script's own directory (which must stay
      listable for the interpreter to load the script at all — see
      BP-100k-4-i's own standing constraint that an indeterminate path be
      exercised by making the lookup genuinely unavailable at run time,
      never by asserting an error branch exists in the source). Production
      code never sets this variable.

SPLIT NOTE (check-file-size, BP-100n-4-ii itself): this module originally
    held all eight test_spec descriptors for this AC. Splitting purely to
    keep this NEW file under check-file-size's absolute 400-counted-line cap
    for new files, two sibling modules were split off, each named for the
    property it covers rather than "_part2" (mirroring this same directory's
    established test_bp_100k_4_ii.py / test_bp_100k_4_ii_registry_shapes.py
    convention: shared fixtures are IMPORTED via importlib under a private
    module name, never copy-pasted — see each sibling's own docstring):
      - test_bp_100n_4_ii_indeterminate_disk_and_registry.py — test_spec 2
        (unlistable gate-script directory), test_spec 3 (listable-but-empty
        gate-script directory), test_spec 4 (unreadable/unparseable
        registry), and test_spec 5 (an indeterminate disk listing never
        emits a clean verdict) — the four INDETERMINATE fail-closed
        situations across the disk side and the registry side.
      - test_bp_100n_4_ii_execution_surfaces.py — test_spec 7 (the
        registered hook entry point, determinate and indeterminate) and
        test_spec 8 (the deployed copy failing closed).
    This module keeps test_spec 1 (the LOAD-BEARING descriptor proving the
    declared-non-gate path: it is the only test in this AC family that
    exercises the ``hook_trigger_reachability_exemption_registry`` script-
    keyed entry to raise ``declared_non_gate``) and test_spec 6 (a clean
    synthetic population states a positive compared count) — the two
    descriptors that establish the four RESULT-line numbers move correctly.

RED BASELINE (expected): every test below is RED. Neither the disk-side
    floor, the four-number RESULT line, nor the HOOK_TEST_GATE_DIR
    resolution exist yet — regex searches against the new fields return
    None, and INDETERMINATE is never emitted for a disk-side condition
    today because there is no disk side at all.

    Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep":
    every test executes the real check_hook_trigger_reachability.py as a
    subprocess, and every indeterminate scenario is exercised by making the
    underlying lookup GENUINELY unavailable at run time (permission bits
    removed via os.chmod, a nonexistent path, a corrupt file written to
    disk) — never by reading the guard's source for an error branch.
"""

from __future__ import annotations

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
_CG_TEMPLATES_SRC = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_REACHABILITY_HOOK_NAME = "check_hook_trigger_reachability.py"

_SUBPROCESS_TIMEOUT_SECONDS = 30

_RESULT_LINE_RE = re.compile(
    r"check-hook-trigger-reachability:\s*RESULT\b"
    r".*?\bcompared=(\d+)\b"
    r".*?\bregistered=(\d+)\b"
    r".*?\bunreferenced=(\d+)\b"
    r".*?\bdeclared_non_gate=(\d+)\b",
    re.IGNORECASE | re.DOTALL,
)
_INDETERMINATE_LINE_RE = re.compile(r"INDETERMINATE:\s*reason=(.+)")


# ---------------------------------------------------------------------------
# Shared helpers (also imported, read-only, by this AC's sibling modules —
# see the SPLIT NOTE above)
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "bp100n4iitest@example.com"], repo)
    _git(["config", "user.name", "BP-100n-4-ii Test"], repo)


def _commit_all(repo: Path, message: str) -> None:
    _git(["add", "-A"], repo)
    _git(["commit", "-m", message], repo)


def _deploy_gate_dir_copy(workspace: Path) -> Path:
    dest = workspace / "commit_guardian_copy"
    shutil.copytree(_CG_TEMPLATES_SRC, dest, ignore=shutil.ignore_patterns("__pycache__"))
    return dest


def _run_reachability_hook(
    script_path: Path, cwd: Path, env_overrides: dict | None = None
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _write_gate_script(path: Path) -> None:
    path.write_text("#!/usr/bin/env python3\nimport sys\n\nsys.exit(0)\n", encoding="utf-8")


def _write_registry_config(
    entries: list[dict], exemption_entries: list[dict] | None = None
) -> str:
    """Write a HOOK_TEST_CONFIG-shaped registry override via json.dump (the
    real serializer, never a hand-typed literal)."""
    import tempfile as _tempfile

    fd, path = _tempfile.mkstemp(suffix=".json")
    os.close(fd)
    payload: dict = {"hooks_manifest": {"hooks": entries}}
    if exemption_entries is not None:
        payload["hook_trigger_reachability_exemption_registry"] = exemption_entries
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


class _FixtureRepoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        _init_repo(self.workspace)
        self.gate_dir = _deploy_gate_dir_copy(self.workspace)
        self.script_path = self.gate_dir / _REACHABILITY_HOOK_NAME
        _commit_all(self.workspace, "initial real gate-directory fixture copy")

    def tearDown(self) -> None:
        self._tmp.cleanup()


# ---------------------------------------------------------------------------
# test_spec 1: the summary states all four population numbers.
# ---------------------------------------------------------------------------


class TestSummaryStatesAllFourPopulationNumbers(_FixtureRepoTestCase):
    def test_bp_100n_4_ii_the_summary_states_all_four_population_numbers(self) -> None:
        # covers: BP-100n-4-ii
        # angle: criterion
        """Asserted by varying each population between runs and requiring
        the corresponding stated number to move with it — never by matching
        a fixed literal, which would pass on four hard-coded numbers.
        """
        run1 = _run_reachability_hook(self.script_path, self.workspace)
        out1 = run1.stdout + run1.stderr
        m1 = _RESULT_LINE_RE.search(out1)
        self.assertIsNotNone(
            m1, f"expected all four population counts on the first run; got {out1!r}"
        )
        compared1, registered1, unreferenced1, declared1 = (int(x) for x in m1.groups())

        _write_gate_script(self.gate_dir / "check_bp_100n_4_ii_novel_fixture.py")
        _commit_all(self.workspace, "added one gate script")

        run2 = _run_reachability_hook(self.script_path, self.workspace)
        out2 = run2.stdout + run2.stderr
        m2 = _RESULT_LINE_RE.search(out2)
        self.assertIsNotNone(
            m2, f"expected all four population counts on the second run; got {out2!r}"
        )
        compared2, registered2, unreferenced2, _declared2 = (int(x) for x in m2.groups())

        self.assertEqual(
            compared2, compared1 + 1, "adding a gate script must raise the compared count"
        )
        self.assertEqual(
            unreferenced2,
            unreferenced1 + 1,
            "the added, unregistered script must raise the unreferenced count",
        )
        self.assertEqual(
            registered2,
            registered1,
            "adding a gate script must not change how many registry entries were read",
        )

        registry_path = self.gate_dir / "commit_guardian.json"
        with open(registry_path, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("hook_trigger_reachability_exemption_registry", [])
        data["hook_trigger_reachability_exemption_registry"].append(
            {
                "script": "check_bp_100n_4_ii_novel_fixture.py",
                "ground": "fixture-only helper",
            }
        )
        with open(registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        _commit_all(self.workspace, "declared the new script a non-gate")

        run3 = _run_reachability_hook(self.script_path, self.workspace)
        out3 = run3.stdout + run3.stderr
        m3 = _RESULT_LINE_RE.search(out3)
        self.assertIsNotNone(m3, f"expected all four counts on the third run; got {out3!r}")
        _compared3, _registered3, unreferenced3, declared3 = (int(x) for x in m3.groups())

        self.assertEqual(
            declared3,
            declared1 + 1,
            "declaring the added script a non-gate must raise declared_non_gate",
        )
        self.assertEqual(
            unreferenced3,
            unreferenced1,
            "declaring the added script a non-gate must remove it from unreferenced",
        )


# ---------------------------------------------------------------------------
# test_spec 6: a clean run states a compared count greater than zero.
# ---------------------------------------------------------------------------


class TestCleanRunStatesComparedCountGreaterThanZero(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        _init_repo(self.workspace)
        self.gate_dir = _deploy_gate_dir_copy(self.workspace)
        self.script_path = self.gate_dir / _REACHABILITY_HOOK_NAME
        self.synth_dir = self.workspace / "synth_gate_dir"
        self.synth_dir.mkdir()
        _write_gate_script(self.synth_dir / "check_invoked_fixture.py")
        _write_gate_script(self.synth_dir / "check_declared_fixture.py")
        self.registry_config_path = _write_registry_config(
            entries=[
                {
                    "id": "check-invoked-fixture",
                    "name": "Invoked fixture",
                    "entry": "python run_hook.py check_invoked_fixture.py",
                    "language": "system",
                    "always_run": True,
                    "pass_filenames": False,
                    "stages": ["pre-commit"],
                }
            ],
            exemption_entries=[
                {"script": "check_declared_fixture.py", "ground": "fixture-only helper"}
            ],
        )
        _commit_all(self.workspace, "initial fixture copy plus synthetic clean population")

    def tearDown(self) -> None:
        os.unlink(self.registry_config_path)
        self._tmp.cleanup()

    def test_bp_100n_4_ii_a_clean_run_states_a_compared_count_greater_than_zero(self) -> None:
        # covers: BP-100n-4-ii
        # angle: criterion
        """Over a synthetic population in which every gate script is either
        invoked or declared, the stated compared count is greater than
        zero, and it is that positive number — not the mere absence of
        findings — that establishes the run as clean.
        """
        result = _run_reachability_hook(
            self.script_path,
            self.workspace,
            env_overrides={
                "HOOK_TEST_GATE_DIR": str(self.synth_dir),
                "HOOK_TEST_CONFIG": self.registry_config_path,
            },
        )
        output = result.stdout + result.stderr
        match = _RESULT_LINE_RE.search(output)
        self.assertIsNotNone(match, f"expected the RESULT line on a clean run; got {output!r}")
        compared = int(match.group(1))
        self.assertGreater(compared, 0)
        self.assertEqual(
            result.returncode,
            0,
            "a run in which every gate script is invoked or declared must exit clean",
        )


if __name__ == "__main__":
    unittest.main()
