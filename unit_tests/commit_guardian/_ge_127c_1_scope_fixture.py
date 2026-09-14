"""
MODULE: unit_tests/commit_guardian/_ge_127c_1_scope_fixture.py
COVERS: GE-127c-1 (shared fixture module -- carries no tests of its own)

GOAL: Hold every helper the four GE-127c-1 test files
    (test_ge_127c_1_scope_declaration.py, test_ge_127c_1_scope_config_driven.py,
    test_ge_127c_1_dividing_advice.py, test_ge_127c_1_deployed_reachability.py)
    share, so splitting the original single test_ge_127c_1.py (579 counted
    lines against the 400-line check-file-size limit -- the very gate this AC
    widened) does not duplicate a single line of fixture logic across the
    split. This module adapts the shape of
    unit_tests/commit_guardian/_ge_127a_1_ordinary_commit_fixture.py, the
    established precedent for exactly this situation on this branch's sibling
    PR.

BUSINESS CONTEXT: see
    docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/
    GE-127c-1.yaml and its parents GE-127c.yaml / GE-127.yaml.

EXERCISE STRATEGY (per CLAUDE.md "Gate / Workflow ACs -- Verify
    Behaviorally, Not by Grep" and this repo's Fixture Authenticity Rule):
    every helper here drives a REAL `git init`, REAL commits/staging, and
    invokes the REAL check_file_size.py (directly, via the REAL run_hook.py
    wrapper, or -- for probes that must not touch the tracked production
    config -- via a REAL, unmodified COPY of the whole commit_guardian/
    directory whose OWN commit_guardian.json is edited) as a subprocess,
    reading the actual process exit code and stdout/stderr.

DECISION HISTORY
- 2026-09-14 [GE-127c-1/test-writer]: Split out of test_ge_127c_1.py (which
    had grown to 579 counted lines against the 400-line check-file-size
    limit) into a private shared-fixture sibling module, mirroring
    _ge_127a_1_ordinary_commit_fixture.py. Pure move -- no fixture logic
    changed. See the four sibling test files' own DECISION HISTORY entries
    for the counted-line accounting after the split.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMIT_GUARDIAN_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
CHECK_FILE_SIZE = COMMIT_GUARDIAN_DIR / "check_file_size.py"
RUN_HOOK = COMMIT_GUARDIAN_DIR / "run_hook.py"
BUILD_PY = REPO_ROOT / "scripts" / "build.py"
CONFIG_PATH = COMMIT_GUARDIAN_DIR / "commit_guardian.json"

PYTHON = sys.executable
SUBPROCESS_TIMEOUT_SECONDS = 30
BUILD_TIMEOUT_SECONDS = 180

# Modules check_file_size.py needs beside it to run standalone from a copy.
CHECK_FILE_SIZE_SIBLINGS = [
    "check_file_size.py",
    "config.py",
    "_resolve_root.py",
    "_file_size_ratchet.py",
    "commit_guardian.json",
]
RUN_HOOK_SIBLINGS = [*CHECK_FILE_SIZE_SIBLINGS, "run_hook.py", "check_outcome.py"]

# Advice lines produced by check_file_size.py's refusal always begin with
# this phrase today ("Use the `...` ... to intelligently split this ...
# file."). Extracted from real process output, never from source text.
ADVICE_LINE_RE = re.compile(r"^\s*Use the .*$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=check,
    )


def init_repo(root: Path) -> None:
    """Initialize a real git repository with a deterministic committer identity."""
    git(["init", "-q"], root)
    git(["config", "user.email", "test-writer@example.com"], root)
    git(["config", "user.name", "GE-127c-1 test fixture"], root)


def commit_all(root: Path, message: str) -> None:
    """Stage everything and make a real commit."""
    git(["add", "-A"], root)
    git(["commit", "-q", "-m", message], root)


def stage_all(root: Path) -> None:
    """Stage everything without committing."""
    git(["add", "-A"], root)


def content(n_lines: int, tag: str = "v") -> str:
    """Build deterministic, docstring-free plain-text content counting as n_lines."""
    return "\n".join(f"{tag}_{i:06d} = {i}" for i in range(n_lines)) + "\n"


def new_repo(prefix: str) -> Path:
    """Create a fresh, empty, real git repository in a new temp directory."""
    root = Path(tempfile.mkdtemp(prefix=prefix))
    init_repo(root)
    return root


def run_check(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke the REAL, unmodified check_file_size.py against *cwd*."""
    return subprocess.run(
        [PYTHON, str(CHECK_FILE_SIZE)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


def run_check_via_hook(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke check_file_size.py through the REAL, registered run_hook.py wrapper."""
    return subprocess.run(
        [PYTHON, str(RUN_HOOK), str(CHECK_FILE_SIZE)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


def copy_commit_guardian(
    file_size_overrides: dict | None = None, include_run_hook: bool = False
) -> Path:
    """Copy the real commit_guardian scripts (plus config) into a fresh temp dir.

    Used ONLY to probe a scope the real production commit_guardian.json does
    not yet carry, without ever mutating the real, tracked config file. The
    copied modules are byte-identical to production; only the copy's OWN
    commit_guardian.json's ``file_size`` section is optionally overridden.

    Args:
        file_size_overrides: If given, merged into the copy's own
            ``file_size`` config section (e.g. to add an extension to
            ``checked_extensions`` with a matching ``line_limits`` entry).
        include_run_hook: If True, also copy run_hook.py and check_outcome.py
            so the copy can be driven through the hook wrapper too.

    Returns:
        Path to the fresh directory holding the copied scripts.
    """
    dst = Path(tempfile.mkdtemp(prefix="ge127c1_cg_"))
    names = list(CHECK_FILE_SIZE_SIBLINGS)
    if include_run_hook:
        names = RUN_HOOK_SIBLINGS
    for name in names:
        shutil.copy2(COMMIT_GUARDIAN_DIR / name, dst / name)
    if file_size_overrides:
        config_path = dst / "commit_guardian.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config.setdefault("file_size", {}).update(file_size_overrides)
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return dst


def run_direct(commit_guardian_dir: Path, cwd: Path) -> subprocess.CompletedProcess:
    """Invoke a COPIED check_file_size.py (see copy_commit_guardian) against *cwd*."""
    return subprocess.run(
        [PYTHON, str(commit_guardian_dir / "check_file_size.py")],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


def lines_containing(text: str, token: str) -> list[str]:
    return [line for line in text.splitlines() if token in line]


def asserts_kind_measured(combined: str, ext: str) -> bool:
    """True if some line states *ext* was measured (word stem 'measur')."""
    return any(re.search(r"measur", line, re.IGNORECASE) for line in lines_containing(combined, ext))


def asserts_kind_not_measured(combined: str, ext: str) -> bool:
    """True if some line states *ext* was explicitly NOT measured this run."""
    for line in lines_containing(combined, ext):
        if re.search(r"measur", line, re.IGNORECASE) and re.search(
            r"\bnot\b|\bunmeasured\b|\bskip", line, re.IGNORECASE
        ):
            return True
    return False


def advice_lines(combined: str) -> set[str]:
    """Extract the distinct dividing-advice line(s) a refusal actually printed."""
    return {line.strip() for line in ADVICE_LINE_RE.findall(combined)}


def refusal_advice_for_extension(ext: str) -> set[str]:
    """Force *ext* alone into scope with a tiny limit, refuse a file of that
    kind, and return the distinct advice line(s) that REAL refusal produced.

    This is empirical, not a source-grep: it runs the real check_file_size.py
    (from a throwaway copy whose OWN config names only *ext*) against a real
    over-limit file of that extension and reads what it actually printed.
    """
    root = Path(tempfile.mkdtemp(prefix="ge127c1_advice_repo_"))
    cg = copy_commit_guardian(file_size_overrides={"checked_extensions": [ext], "line_limits": {ext: 1}})
    try:
        init_repo(root)
        (root / f"probe{ext}").write_text(content(5), encoding="utf-8")
        stage_all(root)
        result = run_direct(cg, root)
        return advice_lines(result.stdout + result.stderr)
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(cg, ignore_errors=True)
