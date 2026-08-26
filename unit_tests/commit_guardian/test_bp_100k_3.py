"""
MODULE: unit_tests/commit_guardian/test_bp_100k_3.py
GOAL: BP-100k-3 — check_build_drift.py and check_output_drift.py must never
    fold an artifact they could not compare into a silent, clean-looking
    pass. An artifact the build deliberately does not manage must be
    reported as a DECLARED EXEMPTION naming its ground; an artifact that is
    neither recorded in the manifest nor declared exempt must be reported
    as a COVERAGE GAP naming the artifact and the registering action; the
    gate's run summary must carry a non-zero count of artifacts it could
    not compare; and "could not compare" must be distinguishable from
    "compared and matched" in both output and exit status.
BUSINESS CONTEXT: Today, both gates print a bare INFO line for an
    unregistered artifact ("... not in manifest ...", "... not in
    output_mappings ...") and then exit 0 — a reader and CI both see a
    pass. Ticket 07 (BP-100k-1/2, committed a78700a9) closed the manifest
    gaps that made comparison impossible in the first place; this ticket
    fixes what the gates SAY and RETURN about anything still uncomparable
    after that. See docs/acceptance-criteria/build_pipeline/
    BP-100-reliable-builds/BP-100k-3.yaml.
ARCHITECTURE / EXERCISE STRATEGY: every test below EXECUTES the real,
    unmodified-by-this-file gate module as a subprocess against a
    synthesized deployed layout (never a grep of the gate's source) — the
    same pattern proven in test_bp_100k_1.py / test_bp_100k_2.py /
    test_bp_1100b_5.py. The manifest and exemption registry are both
    written via their real serializer (json.dump), never hand-typed
    literals, per the Fixture Authenticity Rule.

    Exemption declarations are injected via a NEW env var this test file
    specifies for python-coder, mirroring the HOOK_TEST_CONFIG convention
    already introduced by check_presence_only_assertions.py
    (test_bp_1100b_5.py):

      HOOK_TEST_CONFIG: path to a JSON file containing ONLY the
        `drift_gate_exemption_registry` key — a list of
        ``{"path": <repo-root-relative artifact key>, "ground": <text>}``
        objects — used INSTEAD OF loading commit_guardian.json. When unset,
        the hook must fall back to its production behaviour: read
        `drift_gate_exemption_registry` from the real, colocated
        commit_guardian.json (the REGISTRATION SURFACE named in this
        ticket's Implementation Notes — templates/scripts/commit_guardian/
        commit_guardian.json, deployed alongside the hook itself).

OUTPUT + EXIT-CODE CONTRACT SPECIFIED BY THIS TEST FILE (the target for
    python-coder — both gates must share it so "the same exemption
    registry" (AC-5) is meaningfully testable):

    Per uncomparable artifact, exactly one line:
      "UNCOMPARABLE: EXEMPT <key> ground=<ground text>"
      "UNCOMPARABLE: GAP <key> action=run build.py to register it"
    A registry entry with no non-blank `ground` is rejected (not silently
    honoured) and its artifact falls through to the GAP form, plus one line:
      "REJECTED EXEMPTION ENTRY: <key> reason=no ground stated"

    Exactly ONE aggregate summary line per full gate invocation (combining
    every template/output family the gate scans in that run):
      "<gate-name>: RESULT verified=<N> uncomparable=<M> drifted=<D>"
    where <gate-name> is "check-build-drift" or "check-output-drift",
    uncomparable = exempt-count + gap-count, and an uncomparable artifact is
    NEVER counted in <N> (AC-4's "never counted among the artifacts it
    verified").

    Exit status: 0 when uncomparable == 0 and drifted == 0; 1 when
    drifted > 0 (preserves the existing BLOCKED contract from
    test_bp_100k_1.py / test_bp_100k_2.py); 2 when drifted == 0 and
    uncomparable > 0. This is the AC-4 discriminator: a run containing an
    uncomparable artifact must never exit 0.

RED BASELINE (expected, captured before any production-code change): every
    test in this file is RED — none of UNCOMPARABLE:/RESULT/REJECTED
    EXEMPTION lines exist in the current implementation, which only prints
    a bare INFO line and always exits 0 for an unregistered artifact.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_CG_TEMPLATES_SRC = _TEMPLATES_DIR / "scripts" / "commit_guardian"
_CHECK_BUILD_DRIFT_SRC = _CG_TEMPLATES_SRC / "check_build_drift.py"
_CHECK_OUTPUT_DRIFT_SRC = _CG_TEMPLATES_SRC / "check_output_drift.py"

_SUBPROCESS_TIMEOUT_SECONDS = 15

# `uncomparable` remains the gaps+exempt TOTAL; `exempt` and `gaps` break it
# down. The breakdown was added because the single total made BP-100k-3 ("a
# non-zero uncomparable count must not describe the run as clean") read as
# contradicting BP-100k-3-i ("each gate reports clean and exits zero" on a
# freshly built tree that legitimately carries grounded exemptions). Only GAPS
# drive the verdict, so both hold at once.
_RESULT_LINE_RE = re.compile(
    r"(check-build-drift|check-output-drift):\s*RESULT\s+"
    r"verified=(\d+)\s+uncomparable=(\d+)\s+exempt=(\d+)\s+gaps=(\d+)\s+"
    r"drifted=(\d+)",
    re.IGNORECASE,
)

_DEFAULT_GROUND = "hand-maintained documentation; not build-managed"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes.

    Args:
        data: Raw bytes to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest string.
    """
    return hashlib.sha256(data).hexdigest()


def _build_synthetic_workspace(workspace: Path) -> Path:
    """Build a minimal synthetic self-hosted layout under ``workspace``.

    Mirrors the layout ``_resolve_manifest_path`` discovers in real
    self-hosted installs: ``<workspace>/leafcutter-ai`` is the package root
    (holds ``templates/`` and the manifest); deployed outputs live directly
    under ``<workspace>/.claude/...`` (repo-root == workspace, the same
    relative depth check_output_drift.py's own main() assumes).

    Args:
        workspace: Temp directory to build the synthetic layout inside.

    Returns:
        Absolute path to the synthetic package root
        (``<workspace>/leafcutter-ai``).
    """
    pkg_root = workspace / "leafcutter-ai"
    (pkg_root / "templates" / "agents").mkdir(parents=True)
    (pkg_root / "templates" / "scripts" / "commit_guardian").mkdir(parents=True)
    (workspace / ".claude" / "agents").mkdir(parents=True)
    return pkg_root


def _write_manifest(pkg_root: Path, template_hashes: dict, output_mappings: dict) -> None:
    """Write .build_manifest.json via the real JSON serializer.

    The manifest is written to the WORKSPACE root (``pkg_root.parent``), not
    into the package directory, because the gates resolve their comparison base
    as ``manifest_path.parent``. In a real install the manifest and the deployed
    outputs share one root — the build's ``target_root`` — so a fixture that put
    the manifest under ``leafcutter-ai/`` while deploying outputs to
    ``<workspace>/.claude/`` would describe a layout that cannot occur, and the
    keys it computed would match nothing.

    Args:
        pkg_root: Synthetic package root (``<workspace>/leafcutter-ai``). The
            manifest lands in its parent, alongside the deployed ``.claude/``
            tree, mirroring a real consumer install.
        template_hashes: Flat dict of manifest-key -> sha256 hex string.
        output_mappings: The output_mappings section (may be empty).
    """
    manifest = dict(template_hashes)
    manifest["output_mappings"] = output_mappings
    # Mirror what the real write_build_manifest() records: where the package
    # sits relative to the manifest's directory. This fixture models a consumer
    # install, so the package is one level down.
    manifest["package_root"] = pkg_root.name
    (pkg_root.parent / ".build_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def _deploy_commit_guardian_dir(workspace: Path) -> Path:
    """Copy the REAL, unmodified templates/scripts/commit_guardian/ tree.

    Copies byte-for-byte (never paraphrased) into a synthesized deployed
    layout (``<workspace>/.leafcutter/scripts/commit_guardian/``), the same
    relative depth used by test_bp_100k_1.py / test_bp_100k_2.py. This
    brings along ``_resolve_root.py``, ``config.py``, and the real
    ``commit_guardian.json`` alongside the two gate modules, so any import
    the eventual implementation adds (e.g. ``from config import ...``)
    resolves without a separate copy step.

    Args:
        workspace: Temp directory to build the fake deployment inside.

    Returns:
        Absolute path to the deployed commit_guardian directory.
    """
    deployed_dir = workspace / ".leafcutter" / "scripts" / "commit_guardian"
    shutil.copytree(
        _CG_TEMPLATES_SRC, deployed_dir, ignore=shutil.ignore_patterns("__pycache__")
    )
    return deployed_dir


def _exemption_config(entries: list[dict]) -> dict:
    """Build the HOOK_TEST_CONFIG payload for a given exemption entry list.

    Args:
        entries: List of ``{"path": ..., "ground": ...}``-shaped dicts (a
            "ground" key may be omitted or blank to exercise rejection).

    Returns:
        The full HOOK_TEST_CONFIG dict, keyed exactly as the real
        commit_guardian.json's `drift_gate_exemption_registry` section.
    """
    return {"drift_gate_exemption_registry": entries}


def _run_hook(
    hook_path: Path, cwd: Path, exemption_config: dict | None = None
) -> subprocess.CompletedProcess:
    """Execute a deployed gate module as a subprocess, exactly as pre-commit does.

    Args:
        hook_path: Absolute path to the (copied) gate module to execute.
        cwd: Working directory to run the subprocess in.
        exemption_config: Optional HOOK_TEST_CONFIG payload (see
            ``_exemption_config``). When None, HOOK_TEST_CONFIG is omitted
            entirely, exercising the hook's own commit_guardian.json
            fallback (empty/absent exemption registry).

    Returns:
        The completed subprocess result (returncode, stdout, stderr captured).
    """
    env = os.environ.copy()
    config_path: str | None = None
    if exemption_config is not None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(exemption_config, f)
            config_path = f.name
        env["HOOK_TEST_CONFIG"] = config_path

    try:
        return subprocess.run(
            [sys.executable, str(hook_path)],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    finally:
        if config_path is not None:
            os.unlink(config_path)


def _make_build_drift_scenario(workspace: Path) -> dict:
    """Build a templates/agents/ scenario with one tracked, one exempt-
    candidate, and one orphan .md artifact.

    Args:
        workspace: Temp directory to build the synthetic layout inside.

    Returns:
        Dict with pkg_root and the three repo-root-relative manifest keys.
    """
    pkg_root = _build_synthetic_workspace(workspace)
    agents_dir = pkg_root / "templates" / "agents"

    tracked_content = b"# Tracked template\nmatches the manifest\n"
    tracked = agents_dir / "tracked_ok.md"
    tracked.write_bytes(tracked_content)

    exempt = agents_dir / "exempt_hand_maintained.md"
    exempt.write_bytes(b"# Hand-maintained doc\nnot build-managed\n")

    orphan = agents_dir / "orphan_new_template.md"
    orphan.write_bytes(b"# Orphan template\nnever registered\n")

    tracked_key = tracked.relative_to(workspace).as_posix()
    exempt_key = exempt.relative_to(workspace).as_posix()
    orphan_key = orphan.relative_to(workspace).as_posix()

    _write_manifest(pkg_root, {tracked_key: _sha256_bytes(tracked_content)}, {})

    return {
        "pkg_root": pkg_root,
        "tracked_key": tracked_key,
        "exempt_key": exempt_key,
        "orphan_key": orphan_key,
    }


def _make_all_matched_scenario(workspace: Path) -> dict:
    """Build a templates/agents/ scenario with a single, fully-registered,
    matching artifact — zero uncomparable, zero drift.

    Args:
        workspace: Temp directory to build the synthetic layout inside.

    Returns:
        Dict with pkg_root and the artifact's repo-root-relative key.
    """
    pkg_root = _build_synthetic_workspace(workspace)
    agents_dir = pkg_root / "templates" / "agents"

    content = b"# Tracked-only template\n"
    tracked = agents_dir / "tracked_only.md"
    tracked.write_bytes(content)
    key = tracked.relative_to(workspace).as_posix()

    _write_manifest(pkg_root, {key: _sha256_bytes(content)}, {})

    return {"pkg_root": pkg_root, "tracked_key": key}


# ---------------------------------------------------------------------------
# AC-1: declared exemption reported as exempt, naming its ground.
# ---------------------------------------------------------------------------


class TestDeclaredExemptionReportedWithGround(unittest.TestCase):
    """AC-1: a declared-exempt hand-maintained artifact is reported as
    exempt and its ground is named."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.scenario = _make_build_drift_scenario(self.workspace)
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_build_drift.py"

    def test_declared_exemption_is_reported_as_exempt_and_names_its_ground(self) -> None:
        # covers: BP-100k-3
        config = _exemption_config(
            [{"path": self.scenario["exempt_key"], "ground": _DEFAULT_GROUND}]
        )
        result = _run_hook(self.hook, self.workspace, exemption_config=config)
        combined = result.stdout + result.stderr

        self.assertIn(
            f"UNCOMPARABLE: EXEMPT {self.scenario['exempt_key']}",
            combined,
            msg=(
                "The declared-exempt hand-maintained artifact was not reported "
                f"as an exemption. Output:\n{combined}"
            ),
        )
        self.assertIn(
            _DEFAULT_GROUND,
            combined,
            msg=f"The declared exemption's ground was not named in the output. Output:\n{combined}",
        )


# ---------------------------------------------------------------------------
# AC-2: unrecorded, undeclared artifact reported as a coverage gap.
# ---------------------------------------------------------------------------


class TestUnrecordedUndeclaredArtifactIsCoverageGap(unittest.TestCase):
    """AC-2: an artifact neither recorded in the manifest nor declared
    exempt is reported as a coverage gap naming the artifact and the
    registering action."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.scenario = _make_build_drift_scenario(self.workspace)
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_build_drift.py"

    def test_unrecorded_undeclared_artifact_is_reported_as_a_coverage_gap(self) -> None:
        # covers: BP-100k-3
        config = _exemption_config(
            [{"path": self.scenario["exempt_key"], "ground": _DEFAULT_GROUND}]
        )
        result = _run_hook(self.hook, self.workspace, exemption_config=config)
        combined = result.stdout + result.stderr

        self.assertIn(
            f"UNCOMPARABLE: GAP {self.scenario['orphan_key']}",
            combined,
            msg=(
                "The unrecorded, undeclared artifact was not reported as a "
                f"coverage gap. Output:\n{combined}"
            ),
        )
        self.assertIn(
            "build.py",
            combined,
            msg=f"The coverage-gap report does not name the registering action. Output:\n{combined}",
        )


# ---------------------------------------------------------------------------
# AC-3: run summary carries a non-zero uncomparable count.
# ---------------------------------------------------------------------------


class TestRunSummaryCountsUncomparableArtifacts(unittest.TestCase):
    """AC-3: the run summary states a non-zero count of artifacts the gate
    could not compare."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.scenario = _make_build_drift_scenario(self.workspace)
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_build_drift.py"

    def test_run_summary_counts_uncomparable_artifacts_and_is_not_called_clean(self) -> None:
        # covers: BP-100k-3
        config = _exemption_config(
            [{"path": self.scenario["exempt_key"], "ground": _DEFAULT_GROUND}]
        )
        result = _run_hook(self.hook, self.workspace, exemption_config=config)
        combined = result.stdout + result.stderr

        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "No RESULT summary line found (expected "
                "'check-build-drift: RESULT verified=<N> uncomparable=<M> "
                f"drifted=<D>'). Output:\n{combined}"
            ),
        )
        uncomparable = int(match.group(3))
        self.assertGreater(
            uncomparable,
            0,
            msg=(
                "The run summary's uncomparable count is not positive despite "
                f"one exempt and one gap artifact in this run. Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# AC-4: uncomparable is distinguishable from compared in output AND exit
# status; an uncomparable artifact is never counted as verified.
# ---------------------------------------------------------------------------


class TestUncomparableDistinguishableFromComparedAndExitDiffers(unittest.TestCase):
    """AC-4: an uncomparable artifact is absent from the verified count, and
    the exit status of an uncomparable run differs from an all-matched run."""

    def setUp(self) -> None:
        self._gap_tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._gap_tmpdir.cleanup)
        self.gap_workspace = Path(self._gap_tmpdir.name)
        self.gap_scenario = _make_build_drift_scenario(self.gap_workspace)
        self.gap_hook = (
            _deploy_commit_guardian_dir(self.gap_workspace) / "check_build_drift.py"
        )

        self._clean_tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._clean_tmpdir.cleanup)
        self.clean_workspace = Path(self._clean_tmpdir.name)
        self.clean_scenario = _make_all_matched_scenario(self.clean_workspace)
        self.clean_hook = (
            _deploy_commit_guardian_dir(self.clean_workspace) / "check_build_drift.py"
        )

    def test_uncomparable_is_distinguishable_from_compared_in_output_and_exit_status(
        self,
    ) -> None:
        # covers: BP-100k-3
        gap_config = _exemption_config(
            [{"path": self.gap_scenario["exempt_key"], "ground": _DEFAULT_GROUND}]
        )
        result_gap = _run_hook(self.gap_hook, self.gap_workspace, exemption_config=gap_config)
        combined_gap = result_gap.stdout + result_gap.stderr

        match_gap = _RESULT_LINE_RE.search(combined_gap)
        self.assertIsNotNone(
            match_gap, msg=f"No RESULT summary line in the uncomparable run. Output:\n{combined_gap}"
        )
        verified_gap = int(match_gap.group(2))
        uncomparable_gap = int(match_gap.group(3))
        self.assertEqual(
            1,
            verified_gap,
            msg=(
                "The exempt and gap artifacts must never be counted as "
                f"verified. Output:\n{combined_gap}"
            ),
        )
        self.assertGreaterEqual(
            uncomparable_gap,
            2,
            msg=f"Expected both the exempt and the gap artifact to count as uncomparable. Output:\n{combined_gap}",
        )

        result_clean = _run_hook(self.clean_hook, self.clean_workspace, exemption_config=None)
        combined_clean = result_clean.stdout + result_clean.stderr
        match_clean = _RESULT_LINE_RE.search(combined_clean)
        self.assertIsNotNone(
            match_clean, msg=f"No RESULT summary line in the all-matched run. Output:\n{combined_clean}"
        )
        self.assertEqual(
            0,
            int(match_clean.group(3)),
            msg=f"An all-matched run must have zero uncomparable artifacts. Output:\n{combined_clean}",
        )

        self.assertEqual(
            0,
            result_clean.returncode,
            msg=f"An all-matched, non-drifted run must exit 0. Output:\n{combined_clean}",
        )
        self.assertNotEqual(
            0,
            result_gap.returncode,
            msg=f"A run containing an uncomparable artifact must not exit 0. Output:\n{combined_gap}",
        )
        self.assertNotEqual(
            result_gap.returncode,
            result_clean.returncode,
            msg=(
                "The exit status of a run with an uncomparable artifact must "
                "differ from the exit status of an all-matched run. "
                f"gap={result_gap.returncode} clean={result_clean.returncode}"
            ),
        )


# ---------------------------------------------------------------------------
# AC-5 (first half): both gates honour the same exemption registry.
# ---------------------------------------------------------------------------


class TestBothGatesHonourSameExemptionRegistry(unittest.TestCase):
    """AC-5: check_build_drift.py and check_output_drift.py, each executed
    against the same declared exemption, both report it as exempt."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_workspace(self.workspace)

        self.build_exempt = self.pkg_root / "templates" / "agents" / "exempt_shared.md"
        self.build_exempt.write_bytes(b"# shared exempt build artifact\n")
        self.build_exempt_key = self.build_exempt.relative_to(self.workspace).as_posix()

        self.output_exempt = self.workspace / ".claude" / "agents" / "exempt_shared_output.md"
        self.output_exempt.write_bytes(b"# shared exempt deployed output\n")
        self.output_exempt_key = self.output_exempt.relative_to(self.workspace).as_posix()

        _write_manifest(self.pkg_root, {}, {})
        deployed_dir = _deploy_commit_guardian_dir(self.workspace)
        self.build_hook = deployed_dir / "check_build_drift.py"
        self.output_hook = deployed_dir / "check_output_drift.py"

    def test_both_gates_honour_the_same_exemption_registry(self) -> None:
        # covers: BP-100k-3
        shared_ground = "shared exemption ground text honoured by both gate families"
        shared_config = _exemption_config(
            [
                {"path": self.build_exempt_key, "ground": shared_ground},
                {"path": self.output_exempt_key, "ground": shared_ground},
            ]
        )

        result_build = _run_hook(self.build_hook, self.workspace, exemption_config=shared_config)
        result_output = _run_hook(self.output_hook, self.workspace, exemption_config=shared_config)

        combined_build = result_build.stdout + result_build.stderr
        combined_output = result_output.stdout + result_output.stderr

        self.assertIn(
            f"UNCOMPARABLE: EXEMPT {self.build_exempt_key}",
            combined_build,
            msg=f"check-build-drift did not honour the shared exemption registry. Output:\n{combined_build}",
        )
        self.assertIn(shared_ground, combined_build, msg=f"Ground missing from check-build-drift output. Output:\n{combined_build}")

        self.assertIn(
            f"UNCOMPARABLE: EXEMPT {self.output_exempt_key}",
            combined_output,
            msg=f"check-output-drift did not honour the shared exemption registry. Output:\n{combined_output}",
        )
        self.assertIn(shared_ground, combined_output, msg=f"Ground missing from check-output-drift output. Output:\n{combined_output}")


# ---------------------------------------------------------------------------
# AC-5 (second half): a groundless entry is rejected, not silently honoured.
# ---------------------------------------------------------------------------


class TestExemptionEntryWithoutGroundIsRejected(unittest.TestCase):
    """AC-5: an exemption entry carrying no stated ground is rejected — the
    artifact falls through to a coverage gap, never a silent exemption."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_workspace(self.workspace)

        self.artifact = self.pkg_root / "templates" / "agents" / "would_be_exempt.md"
        self.artifact.write_bytes(b"# candidate for exemption\n")
        self.key = self.artifact.relative_to(self.workspace).as_posix()

        _write_manifest(self.pkg_root, {}, {})
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_build_drift.py"

    def test_exemption_entry_without_a_ground_is_rejected(self) -> None:
        # covers: BP-100k-3
        cases = [
            ("missing ground key", {"path": self.key}),
            ("empty-string ground", {"path": self.key, "ground": ""}),
            ("whitespace-only ground", {"path": self.key, "ground": "   "}),
        ]
        for label, entry in cases:
            with self.subTest(case=label):
                config = _exemption_config([entry])
                result = _run_hook(self.hook, self.workspace, exemption_config=config)
                combined = result.stdout + result.stderr

                self.assertIn(
                    f"REJECTED EXEMPTION ENTRY: {self.key}",
                    combined,
                    msg=f"A groundless exemption entry ({label}) was not rejected. Output:\n{combined}",
                )
                self.assertNotIn(
                    f"UNCOMPARABLE: EXEMPT {self.key}",
                    combined,
                    msg=(
                        f"A groundless exemption entry ({label}) silently exempted "
                        f"the artifact instead of being rejected. Output:\n{combined}"
                    ),
                )
                self.assertIn(
                    f"UNCOMPARABLE: GAP {self.key}",
                    combined,
                    msg=(
                        f"A rejected exemption entry ({label}) must fall through to "
                        f"a coverage gap, not be suppressed entirely. Output:\n{combined}"
                    ),
                )


# ---------------------------------------------------------------------------
# Regression: check_output_drift() the FUNCTION and main() must agree.
#
# Adversarial review (2026-08-25) found that main() reimplemented the whole
# scan+report+verdict sequence inline and never called the module-level
# check_output_drift() function at all. That left check_output_drift() still
# carrying the OLDER, permissive contract described in the r1 DECISION
# HISTORY entry ("legacy 0/1 contract preserved for direct callers"): it
# returned 0 and printed no RESULT line even when the tree held an
# unrecorded, undeclared output. A caller that imports and invokes
# check_output_drift() directly — this module's own docstring names
# unit_tests/build_guards/test_bp100_drift_docs_compile.py as exactly such a
# caller — got a silent clean verdict on a gap the real pre-commit hook
# (main()) would have blocked. Two contracts in one module is how the next
# drift-gate regression hides: whichever code path a caller happens to take
# decides whether drift is caught at all.
# ---------------------------------------------------------------------------


class TestFunctionAndMainAgreeOnAnUnrecordedArtifact(unittest.TestCase):
    """check_output_drift() (the function) and main() (the hook entry point)
    must apply the identical contract to the identical tree: given an
    unrecorded, undeclared output, BOTH must signal it (never return/exit 0)
    and BOTH must emit the RESULT summary line."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)
        self.pkg_root = _build_synthetic_workspace(self.workspace)

        agents_dir = self.workspace / ".claude" / "agents"

        recorded_content = b"# recorded output\nmatches the manifest\n"
        self.recorded = agents_dir / "recorded.md"
        self.recorded.write_bytes(recorded_content)
        recorded_key = self.recorded.relative_to(self.workspace).as_posix()

        # Never registered in output_mappings and never declared exempt — the
        # unrecorded artifact both entry points must signal as a GAP.
        self.unrecorded = agents_dir / "unrecorded_new_output.md"
        self.unrecorded.write_bytes(b"# unrecorded output\nnever registered\n")
        self.unrecorded_key = self.unrecorded.relative_to(self.workspace).as_posix()

        _write_manifest(
            self.pkg_root,
            {},
            {
                recorded_key: {
                    "template": "templates/agents/recorded.md",
                    "expected_output_hash": _sha256_bytes(recorded_content),
                }
            },
        )

        self.deployed_dir = _deploy_commit_guardian_dir(self.workspace)
        self.hook = self.deployed_dir / "check_output_drift.py"
        self.manifest_path = self.workspace / ".build_manifest.json"

    def _import_deployed_module(self):
        """Load the deployed check_output_drift.py as a fresh module object.

        Uses importlib.util (never a plain ``import``) so this test drives
        the SAME on-disk deployed copy ``_run_hook`` executes as a subprocess
        — never a hand-typed re-implementation — while still getting a fresh
        module object per test (a sys.modules-cached import would let one
        test's module state leak into another's).
        """
        spec = importlib.util.spec_from_file_location(
            "check_output_drift_function_contract_probe", self.hook
        )
        module = importlib.util.module_from_spec(spec)
        guardian_dir = self.hook.parent
        if str(guardian_dir) not in sys.path:
            sys.path.insert(0, str(guardian_dir))
        spec.loader.exec_module(module)
        return module

    def test_function_signals_the_gap_and_emits_the_result_line(self) -> None:
        # covers: BP-100k-3
        module = self._import_deployed_module()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            result = module.check_output_drift(
                output_dirs=[self.workspace / ".claude" / "agents"],
                manifest_path=self.manifest_path,
                repo_root=self.workspace,
            )
        combined = stderr.getvalue()

        self.assertNotEqual(
            0,
            result,
            msg=(
                "check_output_drift() the FUNCTION returned 0 (clean) on a "
                f"tree with an unrecorded, undeclared output "
                f"({self.unrecorded_key}). A direct caller of this function "
                "must never see a clean verdict the pre-commit hook itself "
                f"would block. Output:\n{combined}"
            ),
        )
        self.assertIn(
            f"UNCOMPARABLE: GAP {self.unrecorded_key}",
            combined,
            msg=(
                "check_output_drift() the FUNCTION did not report the "
                f"unrecorded output as a coverage gap. Output:\n{combined}"
            ),
        )
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "check_output_drift() the FUNCTION printed no RESULT summary "
                f"line. Output:\n{combined}"
            ),
        )

    def test_main_signals_the_same_gap_and_emits_the_result_line(self) -> None:
        # covers: BP-100k-3
        result = _run_hook(self.hook, self.workspace, exemption_config=None)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "check-output-drift's main() exited 0 (clean) on a tree with "
                f"an unrecorded, undeclared output ({self.unrecorded_key}). "
                f"Output:\n{combined}"
            ),
        )
        self.assertIn(
            f"UNCOMPARABLE: GAP {self.unrecorded_key}",
            combined,
            msg=f"main() did not report the unrecorded output as a coverage gap. Output:\n{combined}",
        )
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=f"main() printed no RESULT summary line. Output:\n{combined}",
        )

    def test_function_and_main_reach_the_identical_verdict(self) -> None:
        # covers: BP-100k-3
        module = self._import_deployed_module()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            function_result = module.check_output_drift(
                output_dirs=[self.workspace / ".claude" / "agents"],
                manifest_path=self.manifest_path,
                repo_root=self.workspace,
            )

        main_result = _run_hook(self.hook, self.workspace, exemption_config=None)

        # Both entry points scan the identical tree, so they must reach the
        # identical tri-state verdict (0 clean / 1 drift / 2 gap) — not
        # merely "both non-zero". A bare both-non-zero check would stay green
        # even if a future change reintroduced two contracts that happened to
        # both fail, for different reasons, on this particular fixture.
        self.assertEqual(
            function_result,
            main_result.returncode,
            msg=(
                "check_output_drift() the FUNCTION and main() disagreed on "
                f"the exit verdict for the identical tree: "
                f"function={function_result} main={main_result.returncode}."
            ),
        )


if __name__ == "__main__":
    unittest.main()
