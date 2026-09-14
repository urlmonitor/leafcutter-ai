"""
MODULE: _bp_100k_3_iii_harness
GOAL: Shared fixture-building and gate-invocation helpers for
    test_bp_100k_3_iii.py (BP-100k-3-iii). Not a test module itself (leading
    underscore, no TestCase) — mirrors the unit_tests/product_truth/
    _bounds_harness.py precedent of extracting fixture plumbing so the test
    file itself stays a readable list of behavioural assertions.
BUSINESS CONTEXT: BP-100k-3-iii proves that the four never-build-determined
    files measured on the reporting machine are declared exemptions in the
    REAL commit_guardian.json, and that two stale orphaned deploy artifacts
    remain coverage gaps rather than being silently exempted. Every helper
    here exists to drive the REAL, deployed check_output_drift.py and the
    REAL _drift_exemptions/build_phases modules — never a stand-in.
ARCHITECTURE: A synthetic workspace mirrors a real self-hosted install
    (``<workspace>/leafcutter-ai`` as package root, deployed outputs directly
    under ``<workspace>/...``). ``build_gate_workspace`` is the single entry
    point most tests need: it writes every registered (manifest-matching) and
    unregistered file, writes the manifest, deploys the real
    templates/scripts/commit_guardian/ tree (real commit_guardian.json
    included), and returns the hook path to run.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
TEMPLATES_DIR = REPO_ROOT / "templates"
CG_TEMPLATES_SRC = TEMPLATES_DIR / "scripts" / "commit_guardian"

SUBPROCESS_TIMEOUT_SECONDS = 15

RESULT_LINE_RE = re.compile(
    r"check-output-drift:\s*RESULT\s+verified=(\d+)\s+uncomparable=(\d+)\s+"
    r"exempt=(\d+)\s+gaps=(\d+)\s+drifted=(\d+)\s+missing=(\d+)\s+"
    r"unreadable=(\d+)"
)

# The four files measured present-and-unregistered on the reporting machine
# that no build run can ever produce deterministic content for.
FOUR_EXEMPT_PATHS = [
    ".claude/settings.local.json",
    ".claude/scheduled_tasks.lock",
    ".claude/skills_config.json",
    ".claude/changelog_categories.md",
]

# The two files measured present-and-unregistered on the reporting machine
# that ARE stale deploy artifacts of a now-deprecated skill and a now-deleted
# script — real gaps, never exemption candidates.
ORPHAN_PATHS = [
    ".gemini/skills/frontend-design/SKILL.md",
    "scripts/commit_guardian/known_failing_tests.py",
]


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def write_file(path: Path, content: bytes) -> None:
    """Write *content* to *path*, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def build_gate_workspace(
    workspace: Path, registered: dict[str, bytes], unregistered: list[str]
) -> Path:
    """Build a synthetic self-hosted install tree and return the deployed hook.

    ``registered`` keys are workspace-relative paths written to disk AND
    recorded in the manifest's ``output_mappings`` with a matching hash, so
    ``_derive_scan_dirs()`` adds their parent directory to the gate's scan
    set exactly as a real manifest entry would (BP-100k-2's parent-of-every-
    recorded-key derivation) — this is what makes the gate ever inspect
    ``.claude/``, ``.gemini/``, or ``scripts/commit_guardian/`` at all, since
    none of those bare directories are in ``main()``'s own floor_dirs.
    ``unregistered`` paths are written to disk but never recorded, so they
    surface as either a declared exemption or a coverage gap.

    Args:
        workspace: Temp directory to build the synthetic layout inside.
        registered: Map of workspace-relative path -> file content, each
            written and recorded as a matching, verified manifest entry.
        unregistered: Workspace-relative paths written but never recorded.

    Returns:
        Absolute path to the deployed check_output_drift.py to run.
    """
    pkg_root = workspace / "leafcutter-ai"
    (pkg_root / "templates" / "scripts" / "commit_guardian").mkdir(parents=True)

    output_mappings = {}
    for rel, content in registered.items():
        write_file(workspace / rel, content)
        output_mappings[rel] = {
            "template": f"templates/{rel}",
            "expected_output_hash": sha256_bytes(content),
        }
    for rel in unregistered:
        write_file(workspace / rel, b"content with no manifest record\n")

    manifest = {"output_mappings": output_mappings, "package_root": pkg_root.name}
    (workspace / ".build_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    deployed_dir = workspace / ".leafcutter" / "scripts" / "commit_guardian"
    shutil.copytree(CG_TEMPLATES_SRC, deployed_dir, ignore=shutil.ignore_patterns("__pycache__"))
    return deployed_dir / "check_output_drift.py"


def run_gate_with_real_registry(hook_path: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Execute the deployed gate as a subprocess, reading the REAL registry.

    Strips ``HOOK_TEST_CONFIG`` from the subprocess environment (even if
    inherited from an outer caller) so this run always reads the real,
    deployed ``commit_guardian.json`` — never a test-only override.
    """
    env = os.environ.copy()
    env.pop("HOOK_TEST_CONFIG", None)
    return subprocess.run(
        [sys.executable, str(hook_path)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


def extract_exempt_ground(combined_output: str, key: str) -> str | None:
    """Extract the ground text of an ``UNCOMPARABLE: EXEMPT <key> ground=...`` line."""
    match = re.search(rf"UNCOMPARABLE: EXEMPT {re.escape(key)} ground=(.+)", combined_output)
    return match.group(1).strip() if match else None


def _restore_module(name: str, previous) -> None:
    """Put ``sys.modules[name]`` back exactly as it was before a fresh import.

    Forcing a fresh import means evicting whatever was already in
    ``sys.modules`` under that name. Dropping the fresh copy on the way out is
    NOT enough, and leaving it in place is worse: either way the next test to
    import that name gets a different module object than the one it, or the
    code under test, already holds — module-level state silently forks.

    That is not hypothetical. Leaving ``build_phases`` evicted broke four tests
    in unit_tests/test_workflow_variant_transform.py, but only when they ran in
    the same process as this file. Each file passed alone, so the damage was
    invisible to any per-file run and surfaced only in the full CI suite.

    Args:
        name: Module name that was evicted.
        previous: The object removed from ``sys.modules``, or None if the name
            was absent before.
    """
    if previous is not None:
        sys.modules[name] = previous
    else:
        sys.modules.pop(name, None)


@contextmanager
def real_drift_exemptions_module():
    """Yield the real, deployed _drift_exemptions module, freshly imported.

    Forces a fresh import bound to the real templates/ source tree (never a
    synthetic copy some other test may have imported under the same module
    name), and guarantees ``HOOK_TEST_CONFIG`` is unset for the duration so
    ``load_exemption_registry`` reads the real, colocated commit_guardian.json.
    Restores ``sys.path``, ``sys.modules``, and the environment on exit —
    see ``_restore_module`` for why restoring, not merely popping, matters.
    """
    old_hook_test_config = os.environ.pop("HOOK_TEST_CONFIG", None)
    inserted = str(CG_TEMPLATES_SRC) not in sys.path
    if inserted:
        sys.path.insert(0, str(CG_TEMPLATES_SRC))
    previous = sys.modules.pop("_drift_exemptions", None)
    try:
        import _drift_exemptions as module  # noqa: PLC0415

        yield module
    finally:
        if old_hook_test_config is not None:
            os.environ["HOOK_TEST_CONFIG"] = old_hook_test_config
        if inserted and str(CG_TEMPLATES_SRC) in sys.path:
            sys.path.remove(str(CG_TEMPLATES_SRC))
        _restore_module("_drift_exemptions", previous)


@contextmanager
def real_build_phases_module():
    """Yield the real scripts/build_phases module, freshly imported.

    Restores ``sys.modules['build_phases']`` to whatever was there before —
    see ``_restore_module``.
    """
    inserted = str(SCRIPTS_DIR) not in sys.path
    if inserted:
        sys.path.insert(0, str(SCRIPTS_DIR))
    previous = sys.modules.pop("build_phases", None)
    try:
        import build_phases  # noqa: PLC0415

        yield build_phases
    finally:
        if inserted and str(SCRIPTS_DIR) in sys.path:
            sys.path.remove(str(SCRIPTS_DIR))
        _restore_module("build_phases", previous)
