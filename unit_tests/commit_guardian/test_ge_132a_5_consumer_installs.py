"""
MODULE: unit_tests/commit_guardian/test_ge_132a_5_consumer_installs.py
COVERS: GE-132a-5 -- the commit-time remedy-declaration leg of check-hook-parity
    applies only in the package checkout. A consumer that vendors the package (its
    hook_parity canonical manifest points at leafcutter/templates/...) gets a
    not-applicable line, not could_not_check; the parity legs that apply to a
    consumer keep refusing; the package checkout still fails closed on an absent or
    invalid templates/scripts/precommit-autofix.json.

GOAL: Reproduce the DIAGraph failure of 2026-11-25 (a pin-bump commit touching
    scripts/commit_guardian/ refused with "committed package declaration table
    templates/scripts/precommit-autofix.json is missing", RESULT: could_not_check)
    and prove the fix does not weaken the package-side gate.

REACHABILITY ENTRY POINT: check_hook_parity.py run as a process, exactly as the
    pre-commit stanza runs it: from the deployed .leafcutter/scripts/commit_guardian/
    copy in the consumer, from the template tree in the package-shaped root. Layouts
    are copies of the REAL tracked guardian scripts, manifests and table; no build.py.

DECISION HISTORY
- 2026-11-25 [GE-132a-5/quick-fix]: Initial RED authoring.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARDIAN_SRC = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
LEGACY_SRC = REPO_ROOT / "templates" / "commit-guardian"
TABLE_SRC = REPO_ROOT / "templates" / "scripts" / "precommit-autofix.json"
TABLE_REL = "templates/scripts/precommit-autofix.json"
VENDOR = "leafcutter"
DEPLOYED_REL = ".leafcutter/scripts/commit_guardian"
TIMEOUT = 120


def _copy_guardian(dest: Path) -> None:
    """Copy the real guardian scripts to ``dest`` (no bytecode caches)."""
    shutil.copytree(GUARDIAN_SRC, dest, ignore=shutil.ignore_patterns("__pycache__"))


def _vendored_manifest() -> dict:
    """The real manifest with hook_parity pointed at a vendored leafcutter/ copy,
    as DIAGraph's commit_guardian_overlay.json does."""
    manifest = json.loads((GUARDIAN_SRC / "commit_guardian.json").read_text(encoding="utf-8"))
    manifest["hook_parity"].update(
        {
            "runtime_dir": "scripts/commit_guardian",
            "canonical_template_dir": f"{VENDOR}/templates/scripts/commit_guardian",
            "legacy_template_dir": f"{VENDOR}/templates/commit-guardian",
            "deployed_output_dir": DEPLOYED_REL,
            "manifests": {
                "canonical": f"{VENDOR}/templates/scripts/commit_guardian/commit_guardian.json",
                "legacy": f"{VENDOR}/templates/commit-guardian/commit_guardian.json",
            },
        }
    )
    return manifest


def _consumer(tmp_path: Path) -> Path:
    """A DIAGraph-shaped consumer: the package vendored under leafcutter/ (with its
    own table, as a checked-out submodule has), runtime and deployed guardian
    copies carrying the vendored hook_parity config, and no package files of its own."""
    root = tmp_path / "consumer"
    vendored = root / VENDOR / "templates"
    _copy_guardian(vendored / "scripts" / "commit_guardian")
    shutil.copytree(LEGACY_SRC, vendored / "commit-guardian")
    shutil.copy2(TABLE_SRC, vendored / "scripts" / "precommit-autofix.json")
    text = json.dumps(_vendored_manifest(), indent=2)
    for rel in ("scripts/commit_guardian", DEPLOYED_REL):
        _copy_guardian(root / rel)
        (root / rel / "commit_guardian.json").write_text(text, encoding="utf-8")
    assert not (root / TABLE_REL).exists()
    assert not (root / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json").exists()
    return root


def _package(tmp_path: Path) -> Path:
    """A package-shaped root: the real template tree with its own config."""
    root = tmp_path / "package"
    _copy_guardian(root / "templates" / "scripts" / "commit_guardian")
    shutil.copytree(LEGACY_SRC, root / "templates" / "commit-guardian")
    return root


def _run(root: Path, script: Path) -> subprocess.CompletedProcess:
    """Run check_hook_parity.py as a process with cwd at ``root``."""
    return subprocess.run(
        [sys.executable, "-I", "-B", str(script)],
        cwd=str(root), capture_output=True, text=True, timeout=TIMEOUT, check=False,
    )


def _could_not_check(output: str) -> bool:
    return "could_not_check" in output or "could not check" in output


def test_ge132a5_vendored_consumer_reports_not_applicable(tmp_path: Path) -> None:
    # covers: GE-132a-5
    # angle: real_artifact
    """The observed DIAGraph failure: the canonical manifest exists (vendored copy),
    the project tracks no package table, and the hook must not say could_not_check."""
    root = _consumer(tmp_path)
    ran = _run(root, root / DEPLOYED_REL / "check_hook_parity.py")
    output = ran.stdout + ran.stderr
    assert not _could_not_check(output), f"consumer reported could-not-check: {output!r}"
    assert "is missing" not in output, f"consumer judged a package table it does not track: {output!r}"
    assert ran.returncode == 0, f"consumer with every parity leg holding must exit 0: {output!r}"
    assert "not applicable" in output.lower(), f"no explicit not-applicable line (silent pass): {output!r}"
    assert f"{VENDOR}/templates/scripts/commit_guardian/commit_guardian.json" in output, (
        f"not-applicable line does not name the canonical manifest: {output!r}"
    )


def test_ge132a5_vendored_consumer_still_refuses_deployed_drift(tmp_path: Path) -> None:
    # covers: GE-132a-5
    # angle: failure
    """The parity legs that apply to a consumer keep running and keep refusing."""
    root = _consumer(tmp_path)
    (root / DEPLOYED_REL / "check_doc_length.py").unlink()
    ran = _run(root, root / "scripts" / "commit_guardian" / "check_hook_parity.py")
    output = ran.stdout + ran.stderr
    assert ran.returncode == 1, f"deployed drift in a consumer must still refuse: {output!r}"
    assert "check_doc_length.py" in output, f"missing deployed script not named: {output!r}"


def test_ge132a5_package_checkout_missing_or_broken_table_fails_closed(tmp_path: Path) -> None:
    # covers: GE-132a-5
    # angle: failure
    """In the package checkout the committed table is mandatory: absent or invalid
    is could_not_check (exit 2), never not-applicable. Control: the real table passes."""
    root = _package(tmp_path)
    script = root / "templates" / "scripts" / "commit_guardian" / "check_hook_parity.py"

    absent = _run(root, script)
    output = absent.stdout + absent.stderr
    assert absent.returncode == 2, f"absent committed table must be could-not-check: {output!r}"
    assert _could_not_check(output) and TABLE_REL in output, f"absent table not reported: {output!r}"
    assert "remedy-declaration check not applicable" not in output, (
        f"package checkout misread as a consumer: {output!r}"
    )

    (root / TABLE_REL).write_text("{ this is not json", encoding="utf-8")
    broken = _run(root, script)
    output = broken.stdout + broken.stderr
    assert broken.returncode == 2, f"invalid committed table must be could-not-check: {output!r}"
    assert _could_not_check(output) and TABLE_REL in output, f"invalid table not reported: {output!r}"

    shutil.copy2(TABLE_SRC, root / TABLE_REL)
    control = _run(root, script)
    output = control.stdout + control.stderr
    assert control.returncode == 0, f"control: the real committed table must pass: {output!r}"
    assert not _could_not_check(output), f"control reported could-not-check: {output!r}"
