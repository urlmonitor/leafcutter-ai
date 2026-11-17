"""
MODULE: unit_tests/commit_guardian/bp_100k_3/_support.py
GOAL: Shared fixture builders, the subprocess runner and the per-test
    workspace base classes for the BP-100k-3 suite in this package. The tests
    live in ``test_bp_100k_3_build_drift_reporting.py`` (AC-1 to AC-4),
    ``test_bp_100k_3_exemption_registry.py`` (AC-5) and
    ``test_bp_100k_3_function_and_main.py`` (the function/main agreement
    regression).

    BP-100k-3 — check_build_drift.py and check_output_drift.py must never
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
ARCHITECTURE / EXERCISE STRATEGY: every test in this suite EXECUTES the
    real, unmodified-by-this-suite gate module as a subprocess against a
    synthesized deployed layout (never a grep of the gate's source) — the
    same pattern proven in test_bp_100k_1.py / test_bp_100k_2.py /
    test_bp_1100b_5.py. The manifest and exemption registry are both
    written via their real serializer (json.dump), never hand-typed
    literals, per the Fixture Authenticity Rule.

    Exemption declarations are injected via a NEW env var this suite
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

OUTPUT + EXIT-CODE CONTRACT SPECIFIED BY THIS SUITE (the target for
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
    test in this suite is RED — none of UNCOMPARABLE:/RESULT/REJECTED
    EXEMPTION lines exist in the current implementation, which only prints
    a bare INFO line and always exits 0 for an unregistered artifact.

DECISION HISTORY:
- 2026-11-16 [split-oversized-tests]: Split from the single
  unit_tests/commit_guardian/test_bp_100k_3.py, which stood over the
  400-line file-size limit. This module keeps the helpers and constants;
  the nine tests moved unchanged into three test modules. The per-test
  workspace setUp that every class repeated is now WorkspaceTestCase, with
  BuildDriftScenarioTestCase (AC-1/2/3) and SyntheticPackageTestCase (AC-5
  and the regression class) on top of it. Two constants nothing read,
  _CHECK_BUILD_DRIFT_SRC and _CHECK_OUTPUT_DRIFT_SRC, were dropped.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_CG_TEMPLATES_SRC = _TEMPLATES_DIR / "scripts" / "commit_guardian"

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
# Shared per-test setUp. Every test gets a fresh temporary workspace that
# addCleanup removes; the two subclasses add the starting layout their
# test classes share.
# ---------------------------------------------------------------------------


class WorkspaceTestCase(unittest.TestCase):
    """Gives each test its own temporary workspace directory."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)


class BuildDriftScenarioTestCase(WorkspaceTestCase):
    """The AC-1/2/3 starting point: the build-drift scenario (one tracked,
    one exempt-candidate and one orphan template) and a deployed copy of
    check_build_drift.py."""

    def setUp(self) -> None:
        super().setUp()
        self.scenario = _make_build_drift_scenario(self.workspace)
        self.hook = _deploy_commit_guardian_dir(self.workspace) / "check_build_drift.py"


class SyntheticPackageTestCase(WorkspaceTestCase):
    """A workspace that already holds the synthetic package layout; the
    subclass writes its own artifacts and manifest on top of it."""

    def setUp(self) -> None:
        super().setUp()
        self.pkg_root = _build_synthetic_workspace(self.workspace)
