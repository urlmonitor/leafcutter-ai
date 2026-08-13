"""
MODULE: unit_tests/commit_guardian/test_ge_118a_1_check_secrets_layout.py
GOAL: GE-118a-1 — check_secrets.py must resolve scan_secrets from the layout
    build.py actually deploys (.leafcutter/skills/security-scanner/scripts),
    not only the hardcoded commit_guardian.json default
    (".claude/skills/security-scanner/scripts"), so the pre-commit hook does
    not crash with ModuleNotFoundError inside a git worktree.
BUSINESS CONTEXT: In a git worktree, `find_project_root()` resolves the
    worktree root via `git rev-parse --show-toplevel`. The worktree root has
    a `.leafcutter` symlink/copy (build output) but no `.claude/` directory
    (that is only materialized in the main checkout by `install_shims`).
    check_secrets.py's module-level `sys.path.insert(0, project_root /
    SECURITY_SCANNER_SCRIPTS_DIR)` + `from scan_secrets import scan_files`
    therefore raises `ModuleNotFoundError` and blocks every commit made from
    a worktree until the resolution is made layout-aware.
ARCHITECTURE / EXERCISE STRATEGY (documented per test-writer ticket
    instructions): check_secrets.py performs its scanner-directory
    resolution as MODULE-LEVEL statements (import time, not inside a
    function), so there is no importable seam to call directly without
    either (a) inventing a resolver-function API the coder has not written
    yet, which would over-constrain the fix, or (b) exercising the hook the
    way it is actually invoked in production: as a subprocess, with its cwd
    pointed at a synthesized fake project root.

    This module chooses (b) — subprocess invocation — because:
      1. It reproduces the EXACT failure mode (`ModuleNotFoundError` raised
         at module-import time, before `main()` ever runs) rather than a
         proxy for it.
      2. It does not presume any particular fix shape (resolver function,
         try/except fallback chain, __file__-relative walk, etc.) — any
         correct fix makes this test pass, whatever internal shape it takes.
      3. It matches the literal repro steps that surfaced the defect live
         (BO-2600 worktree): `cd <worktree>; git commit` failing where the
         main checkout succeeds.

    Each fake project root is `git init`-ed so that
    `_resolve_root.find_project_root()`'s primary strategy
    (`git rev-parse --show-toplevel`) resolves project_root to the fake root
    exactly as it would for a real worktree, rather than falling through to
    the `__file__`-ancestor-walk fallback (which would silently resolve to
    the REAL repo root and mask the defect this test exists to catch).

    The subprocess environment is deliberately cleared of PYTHONPATH (via
    `env=` with only PATH/HOME) so that the real
    templates/skills/security-scanner/scripts/scan_secrets.py checked into
    THIS repo cannot leak onto sys.path and produce a false green — the only
    scan_secrets.py the subprocess can see is the one materialized under the
    fake root's own layout.

DECISION HISTORY
- 2026-08-13 [GE-118a-1/test-writer]: Initial authoring. Both tests verified
  RED/GREEN by hand before commit (see ticket sign-off comment for the exact
  captured output): the worktree-layout test reproduces the real
  `ModuleNotFoundError: No module named 'scan_secrets'` today; the
  main-checkout-layout test already passes today and is the backward-compat
  regression guard the fix must not break.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# templates/scripts/commit_guardian/check_secrets.py — the canonical template
# source that build.py deploys to consumer projects (ADR-001: edit this copy).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CHECK_SECRETS = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_secrets.py"
)

_STUB_SCAN_SECRETS = (
    "def scan_files(files, project_root=None):\n"
    "    return []\n"
)

_SUBPROCESS_TIMEOUT_SECONDS = 10


def _make_fake_project_root(base: Path, scanner_layout: str) -> Path:
    """Build a fake git project root with a scan_secrets.py under one layout.

    Args:
        base: A tempdir to build the fake root inside.
        scanner_layout: Relative dir (e.g. ".leafcutter/skills/security-scanner/scripts"
            or ".claude/skills/security-scanner/scripts") in which to place a stub
            scan_secrets.py exposing a scan_files() callable.

    Returns:
        Path to the fake project root (== base), already `git init`-ed so that
        `git rev-parse --show-toplevel` resolves to it.
    """
    subprocess.run(
        ["git", "init", "-q", str(base)],
        check=True,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )
    scripts_dir = base / scanner_layout
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "scan_secrets.py").write_text(_STUB_SCAN_SECRETS, encoding="utf-8")
    return base


def _run_check_secrets_in(fake_root: Path) -> subprocess.CompletedProcess:
    """Invoke the real check_secrets.py as a subprocess with cwd=fake_root.

    A clean env (only PATH/HOME) prevents the real, checked-in
    templates/skills/security-scanner/scripts/scan_secrets.py from leaking
    onto sys.path via an inherited PYTHONPATH, which would mask the defect.

    Args:
        fake_root: The synthesized project root to run inside.

    Returns:
        The completed subprocess result (returncode, stdout, stderr captured).
    """
    return subprocess.run(
        [sys.executable, str(_CHECK_SECRETS)],
        cwd=str(fake_root),
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(fake_root)},
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


class TestCheckSecretsScannerLayoutResolution(unittest.TestCase):
    """GE-118a-1: check_secrets must resolve scan_secrets from the deployed layout."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base = Path(self._tmpdir.name)

    def test_check_secrets_imports_scan_secrets_in_worktree_layout(self):
        # covers: GE-118a-1
        """With ONLY the .leafcutter deployed layout present (no .claude
        scripts dir at all — the real shape of a git worktree, per
        _resolve_root.find_project_root() preferring `git rev-parse
        --show-toplevel`), check_secrets.py must resolve and import
        scan_secrets without ModuleNotFoundError.

        FAILS TODAY: check_secrets.py hardcodes
        project_root / SECURITY_SCANNER_SCRIPTS_DIR
        (commit_guardian.json default: ".claude/skills/security-scanner/scripts"),
        which does not exist under this fake worktree root, so
        `from scan_secrets import scan_files` raises ModuleNotFoundError at
        module-import time and the subprocess exits non-zero.
        """
        fake_root = _make_fake_project_root(
            self.base, ".leafcutter/skills/security-scanner/scripts"
        )
        # Sanity: assert there is genuinely no .claude scripts dir present,
        # so a pass here cannot be explained by the old hardcoded path.
        self.assertFalse((fake_root / ".claude").exists())

        result = _run_check_secrets_in(fake_root)

        self.assertNotIn(
            "ModuleNotFoundError",
            result.stderr,
            msg=(
                "check_secrets.py crashed trying to import scan_secrets from "
                "the deployed .leafcutter layout. This is the GE-118a-1 defect: "
                f"stderr was:\n{result.stderr}"
            ),
        )
        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "check_secrets.py must exit 0 (clean, no staged secrets) when "
                f"the scanner is resolvable in the deployed layout. stderr:\n{result.stderr}"
            ),
        )

    def test_check_secrets_main_checkout_layout_still_works(self):
        # covers: GE-118a-1
        """Backward-compatibility guard: the main-checkout layout
        (.claude/skills/security-scanner/scripts/scan_secrets.py present,
        matching the hardcoded commit_guardian.json default) must keep
        working exactly as it does today after the worktree-layout fix
        lands.

        This test already PASSES before the fix (verified by hand — see the
        test-writer sign-off comment for the exact captured output) and MUST
        continue to pass after the fix. It is the regression guard proving
        the fix does not narrow or break the existing main-checkout path.
        """
        fake_root = _make_fake_project_root(
            self.base, ".claude/skills/security-scanner/scripts"
        )

        result = _run_check_secrets_in(fake_root)

        self.assertNotIn(
            "ModuleNotFoundError",
            result.stderr,
            msg=f"main-checkout layout regressed. stderr:\n{result.stderr}",
        )
        self.assertEqual(
            0,
            result.returncode,
            msg=f"main-checkout layout regressed. stderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
