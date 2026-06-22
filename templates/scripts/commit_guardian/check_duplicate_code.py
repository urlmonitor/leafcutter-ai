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

Output format (GE-100b): duplicate pairs are emitted as human-readable lines:
    [check-duplicate-code] WARNING: Duplicate block detected
      Source: path/to/file.py lines 10-20
      Clone:  path/to/other.py lines 30-40

Only clones that involve at least one staged file are reported. Clones between
two non-staged files are silently discarded (GE-100b-1).

Timeout handling (GE-100c-1): when the jscpd subprocess takes longer than 30 seconds
to complete, the hook terminates the subprocess, emits a warning to stderr, and exits
with code 0 (fail-open despite strict mode). The commit proceeds without duplicate
checking.

Blocking message (GE-100c): when strict mode is enabled and duplicates exceed the
configured threshold, the commit is blocked with a message that states both the
measured duplication percentage and the configured threshold:
    [check-duplicate-code] Commit blocked. Measured duplication: 8.0% (threshold: 5%).
    Reduce copy-paste clones or set duplicate_code.strict to false to warn only.

Usage:
    python scripts/commit_guardian/run_hook.py scripts/commit_guardian/check_duplicate_code.py

MODULE: check_duplicate_code.py
GOAL: Detect duplicate (copy-paste) code at commit time using jscpd.
BUSINESS CONTEXT: Copy-paste clones accumulate technical debt; catching them
    early at commit time is cheaper than fixing them after the fact.
ARCHITECTURE: Part of the commit_guardian hook suite; delegates scanning to the
    jscpd binary and reads configuration from commit_guardian.json. Uses jscpd's
    JSON reporter to parse structured output, then filters and formats clone
    pairs as human-readable warnings. Only pairs that include at least one
    staged file are reported (staged-only scope).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _resolve_root import find_project_root  # type: ignore[import]

project_root = find_project_root()

from config import (  # type: ignore[import]  # noqa: E402
    DUPLICATE_CODE_CHECKED_EXTENSIONS,
    DUPLICATE_CODE_ENABLED,
    DUPLICATE_CODE_MIN_LINES,
    DUPLICATE_CODE_MIN_TOKENS,
    DUPLICATE_CODE_STRICT,
    DUPLICATE_CODE_THRESHOLD_PERCENT,
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
    """Return a list of staged source file paths filtered by checked_extensions.

    Only files whose extension is in DUPLICATE_CODE_CHECKED_EXTENSIONS are
    returned. The list is relative to the project root (as reported by git).

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
    checked_exts = set(DUPLICATE_CODE_CHECKED_EXTENSIONS)
    return [
        f for f in lines
        if f and Path(f).suffix in checked_exts
    ]


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
    root: Path,
    tmp_dir: str,
) -> list[str]:
    """Copy staged files from the project root into *tmp_dir*, preserving layout.

    Each file in *staged_files* (relative to *root*) is copied to the
    same relative path under *tmp_dir*.  Missing directories are created
    automatically.  Files that cannot be read are silently skipped so that a
    single unreadable file does not abort the entire scan.

    Args:
        staged_files: Relative file paths (from ``git diff --cached``).
        root: Absolute path to the working-tree root.
        tmp_dir: Absolute path to the temporary staging directory.

    Returns:
        list[str]: Absolute paths inside *tmp_dir* for the files that were
        successfully copied.  Empty if no files could be copied.
    """
    tmp_path = Path(tmp_dir)
    copied: list[str] = []
    for rel in staged_files:
        src = root / rel
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


def _normalise_path(raw: str, scan_root: str | None, orig_root: Path) -> str:
    """Convert an absolute jscpd path back to a project-relative path.

    When jscpd runs inside a temp directory (WSL2 mode), the paths it reports
    are absolute inside the temp dir. This function strips *scan_root* from
    the front so callers always deal in project-relative paths.

    When running normally (not WSL2), paths may already be relative or
    absolute relative to *orig_root*; we normalise them to be relative to
    *orig_root* in either case.

    Args:
        raw: The raw path string from jscpd JSON output.
        scan_root: Absolute path of the temp directory used for scanning, or
                   None when not using a temp directory.
        orig_root: Absolute path to the actual project root.

    Returns:
        str: A project-relative path string (POSIX separators).
    """
    p = Path(raw)
    if scan_root is not None:
        scan_root_path = Path(scan_root)
        try:
            return str(p.relative_to(scan_root_path))
        except ValueError:
            pass
    try:
        return str(p.relative_to(orig_root))
    except ValueError:
        return raw


def _extract_percentage(jscpd_output: str) -> float | None:
    """Extract the overall duplication percentage from jscpd JSON output.

    jscpd's JSON reporter writes a top-level ``statistics`` key with a ``total``
    sub-object that contains a ``percentage`` float (duplication by lines, two
    decimal precision).  This function extracts that value for use in the
    threshold-blocking error message required by GE-100c.

    Args:
        jscpd_output: Raw stdout from jscpd (expected to be JSON).

    Returns:
        float | None: The measured duplication percentage, or None if the field
        cannot be extracted (e.g. invalid JSON or missing key).
    """
    try:
        data = json.loads(jscpd_output)
    except json.JSONDecodeError:
        return None

    try:
        return float(data["statistics"]["total"]["percentage"])
    except (KeyError, TypeError, ValueError):
        return None


def _parse_clones(
    jscpd_output: str,
    staged_set: set[str],
    scan_root: str | None,
) -> list[tuple[str, int, int, str, int, int]]:
    """Parse jscpd JSON output and return clones that involve a staged file.

    jscpd's JSON reporter writes a top-level ``duplicates`` array.  Each
    element describes one clone pair:

    .. code-block:: json

        {
            "firstFile": { "name": "...", "start": 10, "end": 20 },
            "secondFile": { "name": "...", "start": 30, "end": 40 }
        }

    Only pairs where at least one of the two files is in *staged_set* are
    returned (GE-100b-1: staged-only filter).

    Args:
        jscpd_output: Raw stdout from jscpd (expected to be JSON).
        staged_set: Set of project-relative paths for staged files.
        scan_root: Absolute path of the temp dir if WSL2 mode, else None.

    Returns:
        list of tuples: Each tuple is
        (src_path, src_start, src_end, dst_path, dst_start, dst_end)
        where paths are project-relative strings and line numbers are ints.
    """
    try:
        data = json.loads(jscpd_output)
    except json.JSONDecodeError:
        # jscpd did not produce valid JSON — fall back to treating all output
        # as opaque (no structured filtering possible).
        return []

    duplicates = data.get("duplicates", [])
    results: list[tuple[str, int, int, str, int, int]] = []

    for dup in duplicates:
        first = dup.get("firstFile", {})
        second = dup.get("secondFile", {})

        src_raw = first.get("name", "")
        dst_raw = second.get("name", "")

        src_path = _normalise_path(src_raw, scan_root, project_root)
        dst_path = _normalise_path(dst_raw, scan_root, project_root)

        src_start = int(first.get("start", 0))
        src_end = int(first.get("end", 0))
        dst_start = int(second.get("start", 0))
        dst_end = int(second.get("end", 0))

        # Staged-only filter (GE-100b-1): at least one side must be staged.
        if src_path not in staged_set and dst_path not in staged_set:
            continue

        results.append((src_path, src_start, src_end, dst_path, dst_start, dst_end))

    return results


def _emit_clone_warnings(
    clones: list[tuple[str, int, int, str, int, int]],
    mode: str,
) -> None:
    """Print human-readable clone warnings to stderr.

    Each clone pair is reported as:

        [check-duplicate-code] <mode>: Duplicate block detected
          Source: <file> lines <start>-<end>
          Clone:  <file> lines <start>-<end>

    Args:
        clones: List of clone tuples from _parse_clones().
        mode: "WARNING" or "ERROR" depending on strict mode.
    """
    for src_path, src_start, src_end, dst_path, dst_start, dst_end in clones:
        print(
            f"\n[check-duplicate-code] {mode}: Duplicate block detected\n"
            f"  Source: {src_path} lines {src_start}-{src_end}\n"
            f"  Clone:  {dst_path} lines {dst_start}-{dst_end}",
            file=sys.stderr,
        )


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
            return _run_jscpd(
                jscpd,
                scan_targets,
                staged_set=set(staged_files),
                scan_root=tmp_dir_obj.name,
            )
    else:
        return _run_jscpd(
            jscpd,
            staged_files,
            staged_set=set(staged_files),
            scan_root=None,
        )


def _run_jscpd(
    jscpd: str,
    targets: list[str],
    staged_set: set[str],
    scan_root: str | None,
) -> int:
    """Invoke jscpd against *targets* and return an exit code.

    Uses the JSON reporter so that structured output can be parsed and
    filtered to only report clones involving staged files (GE-100b-1).
    Human-readable warnings are emitted to stderr for each relevant clone
    pair (GE-100b).

    Args:
        jscpd: Absolute path to the jscpd binary.
        targets: File paths to scan (either relative project paths or
                 absolute paths inside a temp directory).
        staged_set: Set of project-relative staged file paths used for
                    the staged-only filter.
        scan_root: Absolute path of the temp dir (WSL2 mode) or None.

    Returns:
        int: 0 for pass (or fail-open), 1 to block the commit when strict.
    """
    # Write JSON output to a temp file so stdout capture stays clean.
    try:
        json_fd, json_path = tempfile.mkstemp(suffix=".json", prefix="jscpd_out_")
        os.close(json_fd)
    except OSError as exc:
        print(
            f"[check-duplicate-code] Could not create temp file for jscpd output: {exc}\n"
            "Skipping duplicate-code check (fail-open).",
            file=sys.stderr,
        )
        return 0

    try:
        cmd = [
            jscpd,
            "--min-lines", str(DUPLICATE_CODE_MIN_LINES),
            "--min-tokens", str(DUPLICATE_CODE_MIN_TOKENS),
            "--threshold", str(DUPLICATE_CODE_THRESHOLD_PERCENT),
            "--reporters", "json",
            "--output", str(Path(json_path).parent),
            "--",
        ] + targets

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            print(
                "[check-duplicate-code] Warning: jscpd timed out after 30 seconds.\n"
                "Duplicate-code scanning was skipped (fail-open).",
                file=sys.stderr,
            )
            return 0
        except OSError as exc:
            print(
                f"[check-duplicate-code] Failed to invoke jscpd: {exc}\n"
                "Skipping duplicate-code check (fail-open).",
                file=sys.stderr,
            )
            return 0

        # jscpd exits non-zero when duplicates exceed the threshold.
        if result.returncode == 0:
            return 0

        # Read JSON output from temp file (jscpd writes jscpd-report.json).
        report_path = Path(json_path).parent / "jscpd-report.json"
        raw_json = ""
        if report_path.exists():
            try:
                with open(report_path, encoding="utf-8") as fh:
                    raw_json = fh.read()
            except OSError as exc:
                print(
                    f"[check-duplicate-code] Could not read jscpd report: {exc}",
                    file=sys.stderr,
                )

        clones = _parse_clones(raw_json, staged_set, scan_root)
        measured_pct = _extract_percentage(raw_json)

        if not clones:
            # No clones involving staged files — pass silently.
            return 0

        mode = "ERROR" if DUPLICATE_CODE_STRICT else "WARNING"
        _emit_clone_warnings(clones, mode)

        if DUPLICATE_CODE_STRICT:
            if measured_pct is not None:
                pct_line = (
                    f"Measured duplication: {measured_pct:.1f}% "
                    f"(threshold: {DUPLICATE_CODE_THRESHOLD_PERCENT}%)."
                )
            else:
                pct_line = f"Threshold: {DUPLICATE_CODE_THRESHOLD_PERCENT}% (measured percentage unavailable)."
            print(
                f"\n[check-duplicate-code] Commit blocked. {pct_line}\n"
                "Reduce copy-paste clones or set duplicate_code.strict to false to warn only.",
                file=sys.stderr,
            )
            return 1

        return 0

    finally:
        # Clean up temp JSON file regardless of outcome.
        try:
            Path(json_path).unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-18 [python-coder/TICKET-20260616-GE-100c-1]: Implements AC GE-100c-1 (fail-open
  on jscpd subprocess timeout). Added timeout=30 to subprocess.run() in _run_jscpd() and
  added a subprocess.TimeoutExpired handler that emits a warning to stderr and exits 0
  regardless of strict mode. The subprocess is terminated by Python's subprocess.run()
  when the timeout fires. Module docstring updated with GE-100c-1 timeout behaviour block.
- 2026-06-18 [python-coder/TICKET-20260616-GE-100c]: Implements AC GE-100c (strict-mode
  threshold blocking with measured vs configured percentage in the error message). Added
  _extract_percentage() which reads data["statistics"]["total"]["percentage"] from the
  jscpd JSON report and returns it as a float (None on missing/invalid). Updated
  _run_jscpd() to call _extract_percentage() alongside _parse_clones() and embed the
  measured percentage in the commit-blocked message: "Measured duplication: X.X%
  (threshold: Y%)." Falls back to reporting only the configured threshold when the
  measured value is unavailable. Module docstring updated with GE-100c output format.
- 2026-06-18 [python-coder/TICKET-20260616-GE-100b]: Implements AC GE-100b (human-readable
  duplicate pair output) and GE-100b-1 (staged-only filter). Replaced --reporters console
  with --reporters json + --output to get structured jscpd output. Added _parse_clones()
  which reads jscpd-report.json, converts raw paths to project-relative paths via
  _normalise_path(), and filters clone pairs to only those involving at least one staged
  file. Added _emit_clone_warnings() which prints "Source: <file> lines N-M / Clone: <file>
  lines N-M" to stderr for each relevant pair. Added checked_extensions filtering in
  get_staged_source_files() (previously excluded only .md; now only includes extensions in
  DUPLICATE_CODE_CHECKED_EXTENSIONS). Added DUPLICATE_CODE_THRESHOLD_PERCENT (replaces the
  old DUPLICATE_CODE_THRESHOLD int) and DUPLICATE_CODE_CHECKED_EXTENSIONS imports. The
  _run_jscpd() signature gained staged_set and scan_root parameters to support the filter.
  Exit code semantics unchanged: 0 when strict=false (warn-only), 1 when strict=true and
  clones exist involving staged files.
- 2026-06-18 [python-coder/TICKET-20260616-GE-100a-2]: Implements AC GE-100a-2
  (force staged-only scan when working tree is under /mnt/c/ WSL2 mount). Added
  _is_wsl2_ntfs_mount() to detect /mnt/<letter>/ paths, _copy_staged_files_to_tmpdir()
  to mirror staged files into a native Linux temp directory, and _run_jscpd() to
  hold the jscpd invocation logic (extracted from main() so both the normal and
  WSL2 paths can share it). When WSL2 is detected, staged files are copied to
  tempfile.TemporaryDirectory, jscpd is invoked there, and the temp dir is cleaned
  up. No user-visible error about the WSL2 path is emitted. Fail-open on OSError
  when creating the temp dir.
- 2026-06-18 [python-coder/TICKET-20260616-GE-100a-1]: Implements AC GE-100a-1
  (fail-open when jscpd v4.x is installed). Added _get_jscpd_major_version()
  which runs `jscpd --version`, parses the major version via regex, and returns
  the integer major component. In main(), after finding the binary, the major
  version is checked; if >= 4 the hook prints _V4_WARNING to stderr and exits 0
  without invoking jscpd for scanning. OSError during `jscpd --version` returns
  None (version unknown), which causes the hook to proceed with scanning rather
  than blocking — conservative fail-open choice.
- 2026-06-17 [python-coder/TICKET-20260616-GE-100a]: Created hook. Implements AC
  GE-100a (fail-open when jscpd binary is missing) and the skeleton required by
  the broader GE-100 epic. Binary-missing path: exits 0, prints advisory to
  stderr with install guidance. OSError on subprocess.run also exits 0
  (fail-open) per the same policy. Strict mode (exit 1) only triggers when
  jscpd is present AND returns a non-zero exit code AND strict: true in config.
====================================================================
"""
