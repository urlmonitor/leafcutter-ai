"""
Pre-commit hook to detect copy-paste duplicate code using jscpd.

Scans staged source files for duplicate code blocks (copy-paste clones) and
either warns or blocks the commit depending on configuration. When jscpd is
not installed, the hook exits cleanly with code 0 (fail-open) and emits an
advisory message so the developer knows how to install it.

jscpd v4.x changed its CLI flags in an incompatible way. When v4.x is
detected on the system, the hook skips scanning, emits a warning to stderr
recommending jscpd v3.x, and exits 0 (fail-open).

WSL2 path handling: when the working tree root starts with ``/mnt/c/`` (a WSL2
mount of a Windows filesystem), jscpd is unreliable when invoked directly
against that filesystem.  In that case the hook copies the staged files into a
temporary Linux-native directory and runs jscpd there instead, preserving the
same staged-only scope without the NTFS performance and reliability issues.

Usage:
    python scripts/commit_guardian/run_hook.py scripts/commit_guardian/check_duplicate_code.py

MODULE: check_duplicate_code.py
GOAL: Detect duplicate (copy-paste) code at commit time using jscpd.
BUSINESS CONTEXT: Copy-paste clones accumulate technical debt; catching them
    early at commit time is cheaper than fixing them after the fact.
ARCHITECTURE: Part of the commit_guardian hook suite; delegates scanning to the
    jscpd binary and reads configuration from commit_guardian.json.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _resolve_root import find_project_root  # type: ignore[import]

project_root = find_project_root()

from config import (  # type: ignore[import]  # noqa: E402
    DUPLICATE_CODE_ENABLED,
    DUPLICATE_CODE_MIN_LINES,
    DUPLICATE_CODE_MIN_TOKENS,
    DUPLICATE_CODE_STRICT,
    DUPLICATE_CODE_THRESHOLD,
)

_INSTALL_HINT = (
    "Install jscpd v3.x with:\n"
    "  npm install -g jscpd@^3\n"
    "or, if you prefer a project-local install:\n"
    "  npm install --save-dev jscpd@^3\n"
    "and ensure the binary is on your PATH."
)

_V4_WARNING = (
    "[check-duplicate-code] Warning: jscpd v4.x has incompatible CLI flags "
    "and is not supported.\n"
    "Duplicate-code scanning was skipped.\n"
    "Please install jscpd v3.x instead:\n"
    f"{_INSTALL_HINT}"
)


def _jscpd_binary() -> str | None:
    """Return the path to the jscpd binary, or None if not found.

    Returns:
        str | None: Absolute path to jscpd, or None when absent from PATH.
    """
    return shutil.which("jscpd")


def _get_jscpd_major_version(jscpd_path: str) -> int | None:
    """Return the major version of jscpd at the given path, or None on failure.

    Runs ``jscpd --version``, parses the first semver-like token from stdout
    or stderr, and returns the integer major version component.  Returns
    ``None`` when the version string cannot be determined (e.g. the binary
    fails to start, or produces unrecognised output).

    Args:
        jscpd_path: Absolute path to the jscpd binary.

    Returns:
        int | None: The major version number, or None if it cannot be parsed.
    """
    try:
        result = subprocess.run(
            [jscpd_path, "--version"],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        print(
            f"[check-duplicate-code] Could not determine jscpd version: {exc}",
            file=sys.stderr,
        )
        return None

    # jscpd may print the version on stdout or stderr depending on the release.
    combined = (result.stdout + result.stderr).strip()
    match = re.search(r"(\d+)\.\d+\.\d+", combined)
    if not match:
        return None
    return int(match.group(1))


def get_staged_source_files() -> list[str]:
    """Return a list of staged source file paths (ACM filter, excluding .md).

    Returns:
        list[str]: Staged file paths that jscpd should scan.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"[check-duplicate-code] git diff failed: {exc}", file=sys.stderr)
        return []

    lines = result.stdout.strip().splitlines()
    return [f for f in lines if f and not f.endswith(".md")]


def _is_wsl2_ntfs_mount(root: Path) -> bool:
    """Return True when *root* is located on a WSL2 NTFS mount.

    A path that starts with ``/mnt/c/`` (or any ``/mnt/<single-letter>/``
    variant) is a WSL2 mount of a Windows drive letter.  jscpd is unreliable
    when invoked from such a path because the NTFS filesystem presents
    non-standard permission bits that confuse Node.js's ``fs.readdir``.

    Args:
        root: The absolute path to the working-tree root.

    Returns:
        bool: True when the root is under a WSL2 Windows drive mount.
    """
    parts = root.parts  # e.g. ('/', 'mnt', 'c', ...)
    return len(parts) >= 3 and parts[0] == "/" and parts[1] == "mnt" and len(parts[2]) == 1


def _copy_staged_files_to_tmpdir(
    staged_files: list[str],
    project_root: Path,
    tmp_dir: str,
) -> list[str]:
    """Copy staged files from the project root into *tmp_dir*, preserving layout.

    Each file in *staged_files* (relative to *project_root*) is copied to the
    same relative path under *tmp_dir*.  Missing directories are created
    automatically.  Files that cannot be read are silently skipped so that a
    single unreadable file does not abort the entire scan.

    Args:
        staged_files: Relative file paths (from ``git diff --cached``).
        project_root: Absolute path to the working-tree root.
        tmp_dir: Absolute path to the temporary staging directory.

    Returns:
        list[str]: Absolute paths inside *tmp_dir* for the files that were
        successfully copied.  Empty if no files could be copied.
    """
    tmp_path = Path(tmp_dir)
    copied: list[str] = []
    for rel in staged_files:
        src = project_root / rel
        dst = tmp_path / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            copied.append(str(dst))
        except OSError as exc:
            print(
                f"[check-duplicate-code] Could not stage {rel} into tmp dir: {exc}",
                file=sys.stderr,
            )
    return copied


def main() -> int:
    """Run duplicate code detection on staged files.

    Returns:
        int: Exit code — 0 for pass (or fail-open), 1 to block the commit.
    """
    if not DUPLICATE_CODE_ENABLED:
        return 0

    jscpd = _jscpd_binary()
    if jscpd is None:
        print(
            "[check-duplicate-code] Advisory: jscpd binary not found on PATH.\n"
            "Duplicate-code detection was skipped.\n"
            f"{_INSTALL_HINT}",
            file=sys.stderr,
        )
        return 0

    major = _get_jscpd_major_version(jscpd)
    if major is not None and major >= 4:
        print(_V4_WARNING, file=sys.stderr)
        return 0

    staged_files = get_staged_source_files()
    if not staged_files:
        return 0

    # ------------------------------------------------------------------
    # WSL2 path guard — AC GE-100a-2
    # When the project root lives on an NTFS mount (/mnt/c/ …) we copy the
    # staged files into a native Linux tmpfs before invoking jscpd so that
    # jscpd never touches the slow/unreliable Windows filesystem.
    # ------------------------------------------------------------------
    use_tmpdir = _is_wsl2_ntfs_mount(project_root)

    if use_tmpdir:
        try:
            tmp_dir_obj = tempfile.TemporaryDirectory(prefix="jscpd_staged_")
        except OSError as exc:
            print(
                f"[check-duplicate-code] Could not create temp dir for WSL2 scan: {exc}\n"
                "Skipping duplicate-code check (fail-open).",
                file=sys.stderr,
            )
            return 0
        with tmp_dir_obj:
            scan_targets = _copy_staged_files_to_tmpdir(
                staged_files, project_root, tmp_dir_obj.name
            )
            if not scan_targets:
                return 0
            return _run_jscpd(jscpd, scan_targets)
    else:
        return _run_jscpd(jscpd, staged_files)


def _run_jscpd(jscpd: str, targets: list[str]) -> int:
    """Invoke jscpd against *targets* and return an exit code.

    Args:
        jscpd: Absolute path to the jscpd binary.
        targets: File paths to scan (either relative project paths or
                 absolute paths inside a temp directory).

    Returns:
        int: 0 for pass (or fail-open), 1 to block the commit when strict.
    """
    cmd = [
        jscpd,
        "--min-lines", str(DUPLICATE_CODE_MIN_LINES),
        "--min-tokens", str(DUPLICATE_CODE_MIN_TOKENS),
        "--threshold", str(DUPLICATE_CODE_THRESHOLD),
        "--reporters", "console",
        "--",
    ] + targets

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as exc:
        print(
            f"[check-duplicate-code] Failed to invoke jscpd: {exc}\n"
            "Skipping duplicate-code check (fail-open).",
            file=sys.stderr,
        )
        return 0

    if result.returncode != 0:
        mode = "ERROR" if DUPLICATE_CODE_STRICT else "WARNING"
        print(
            f"\n[check-duplicate-code] Duplicate Code Check — {mode}\n"
            f"{result.stdout}",
            file=sys.stderr,
        )
        if DUPLICATE_CODE_STRICT:
            print(
                "Commit blocked. Reduce copy-paste clones above the threshold "
                "or set duplicate_code.strict to false to warn only.",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-17 [python-coder/TICKET-20260616-GE-100a]: Created hook. Implements AC
  GE-100a (fail-open when jscpd binary is missing) and the skeleton required by
  the broader GE-100 epic. Binary-missing path: exits 0, prints advisory to
  stderr with install guidance. OSError on subprocess.run also exits 0
  (fail-open) per the same policy. Strict mode (exit 1) only triggers when
  jscpd is present AND returns a non-zero exit code AND strict: true in config.
- 2026-06-18 [python-coder/TICKET-20260616-GE-100a-1]: Implements AC GE-100a-1
  (fail-open when jscpd v4.x is installed). Added _get_jscpd_major_version()
  which runs `jscpd --version`, parses the major version via regex, and returns
  the integer major component. In main(), after finding the binary, the major
  version is checked; if >= 4 the hook prints _V4_WARNING to stderr and exits 0
  without invoking jscpd for scanning. OSError during `jscpd --version` returns
  None (version unknown), which causes the hook to proceed with scanning rather
  than blocking — conservative fail-open choice.
- 2026-06-18 [python-coder/TICKET-20260616-GE-100a-2]: Implements AC GE-100a-2
  (force staged-only scan when working tree is under /mnt/c/ WSL2 mount). Added
  _is_wsl2_ntfs_mount() to detect /mnt/<letter>/ paths, _copy_staged_files_to_tmpdir()
  to mirror staged files into a native Linux temp directory, and _run_jscpd() to
  hold the jscpd invocation logic (extracted from main() so both the normal and
  WSL2 paths can share it). When WSL2 is detected, staged files are copied to
  tempfile.TemporaryDirectory, jscpd is invoked there, and the temp dir is cleaned
  up. No user-visible error about the WSL2 path is emitted. Fail-open on OSError
  when creating the temp dir.
====================================================================
"""
