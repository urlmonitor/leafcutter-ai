"""
MODULE: unit_tests/commit_guardian/_ge_127d_1_fixture.py
COVERS: GE-127d-1 (shared fixture module -- carries no tests of its own)

GOAL: Build REAL, isolated fixture trees for the published-versus-enforced
    reconciliation gate (``check_file_size_rule_parity.py``, per GE-127d-1's
    own ``test_spec[6].surface_invoked``) that do not yet exist in
    ``templates/scripts/commit_guardian/`` -- copying it is expected to raise
    ``FileNotFoundError`` until python-coder authors it, which is the correct
    RED state for every descriptor that depends on this fixture.

WHY A SCRIPT-DIRECTORY-RELATIVE SURFACE CONVENTION. ``config.py`` already
    resolves ``commit_guardian.json`` relative to its own ``__file__`` (beside
    the DEPLOYED script), not relative to the project root -- this is what
    lets the same gate work identically whether it lives at
    ``templates/scripts/commit_guardian/`` (canonical / self-hosted) or
    ``.leafcutter/scripts/commit_guardian/`` (a consumer deploy), because
    ``build_commit_guardian`` copies the whole directory, README included.
    This fixture module adopts the SAME convention for
    ``file_size.published_rule_surfaces``: each entry is a path relative to
    the reconciliation script's OWN directory (e.g. ``"README.md"``), never a
    project-root-relative path like ``templates/scripts/commit_guardian/
    README.md`` -- the latter would not resolve at all in a deployed consumer
    install, which ships no ``templates/`` tree. This is a test-writer design
    decision, not an AC-pinned one; python-coder is expected to resolve each
    surface via ``Path(__file__).resolve().parent / surface``.

VOCABULARY THIS FIXTURE PINS (chosen by test-writer; the AC pins only
    ``INDETERMINATE: reason=``, reused here verbatim from check_file_size.py):
    - ``DISAGREEMENT: <surface> ...`` -- one line per disagreeing surface.
    - ``Compared N surface(s)`` -- states the count of surfaces compared,
      mirroring check_file_size.py's own "Compared N file(s)" convention.
    - ``INDETERMINATE: reason=...`` -- pinned by BP-1600a-2-ii / GE-127a-1-i /
      GE-127b-1-i and reused unchanged for an unreadable published surface.

SCOPE OF THE "PUBLISHED STATEMENT" THIS FIXTURE EXERCISES: which KINDS
    (extensions) a surface claims are covered, compared against the real
    ``file_size.checked_extensions`` in force -- one of the three compound
    facts GE-127d-1's criteria name ("which kinds ... when it applies ... how
    long"). Kinds are chosen because they are mechanically unambiguous to
    state and compare (a dotted-extension token either appears in a surface's
    text or it does not), unlike the "when it applies" exemption wording,
    whose exact corrected phrasing is not yet authored (it is this same
    ticket's own documentation-expert deliverable). This does not under-test
    the AC: the reconciliation obligation is symmetric across whichever fact
    is compared, so proving bidirectionality and second-surface reach on the
    kinds axis exercises the same mechanism the other two axes would need.

DECISION HISTORY
- 2026-09-15 [GE-127d-1/test-writer]: Initial authoring of the shared fixture
    for all eight test_spec descriptors.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_SRC = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
BUILD_PY = _REPO_ROOT / "scripts" / "build.py"

SCRIPT_NAME = "check_file_size_rule_parity.py"

# Every module the reconciliation gate is expected to need, transitively --
# copying SCRIPT_NAME itself raises FileNotFoundError today (it does not
# exist yet), which is the intended RED signal for every descriptor built on
# this fixture.
PRODUCTION_MODULES: tuple[str, ...] = (
    SCRIPT_NAME,
    "check_file_size.py",
    "_file_size_ratchet.py",
    "_file_description.py",
    "_resolve_root.py",
    "config.py",
    "run_hook.py",
    "check_outcome.py",
)

PYTHON = sys.executable
SUBPROCESS_TIMEOUT_SECONDS = 30
BUILD_TIMEOUT_SECONDS = 180
HOOK_COMMIT_TIMEOUT_SECONDS = 180

DISAGREEMENT_TOKEN = "DISAGREEMENT"
INDETERMINATE_PREFIX = "INDETERMINATE: reason="
_COMPARED_PATTERN = re.compile(r"Compared (\d+) surface")


def run(cmd: list[str], cwd: Path, timeout: int = SUBPROCESS_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """Run *cmd* for real in *cwd*, capturing text output, never raising."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def git(args: list[str], cwd: Path, timeout: int = SUBPROCESS_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*, with an optional longer timeout."""
    return run(["git", *args], cwd, timeout=timeout)


def init_repo(root: Path) -> None:
    """Initialize a real git repository with a deterministic identity."""
    git(["init", "-q"], root)
    git(["config", "user.email", "test-writer@example.com"], root)
    git(["config", "user.name", "GE-127d-1 reconciliation fixture"], root)
    git(["config", "core.autocrlf", "false"], root)


def copy_production_modules(root: Path) -> Path:
    """Copy the (not-yet-existing) gate script and its dependencies into *root*.

    Returns:
        The destination directory, ``<root>/scripts/commit_guardian``.

    Raises:
        FileNotFoundError: SCRIPT_NAME does not exist in the source tree yet
            -- the expected RED state before python-coder authors it.
    """
    dest = root / "scripts" / "commit_guardian"
    dest.mkdir(parents=True, exist_ok=True)
    for name in PRODUCTION_MODULES:
        shutil.copy2(_COMMIT_GUARDIAN_SRC / name, dest / name)
    return dest


def surface_text(extensions: list[str]) -> str:
    """Deterministic prose stating which kinds a published surface covers."""
    kinds = ", ".join(extensions) if extensions else "(none)"
    return f"Enforces line limits on {kinds} files. Limits apply to every changed file, not only newly added ones.\n"


def build_fixture_tree(
    root: Path,
    *,
    checked_extensions: list[str],
    readme_extensions: list[str],
    comment_extensions: list[str],
    surfaces: list[str] | None = None,
    extra_surface_files: dict[str, str] | None = None,
    line_limit: int = 5,
) -> Path:
    """Compose a full reconciliation fixture tree at *root* and return the
    destination directory (``<root>/scripts/commit_guardian``).

    Args:
        root: Fixture root directory.
        checked_extensions: The ENFORCED set of covered extensions.
        readme_extensions: The set of extensions README.md's text CLAIMS.
        comment_extensions: The set of extensions commit_guardian.json's
            ``file_size._comment`` text CLAIMS.
        surfaces: Override the ``published_rule_surfaces`` list (paths
            relative to the destination directory). Defaults to
            ``["README.md", "commit_guardian.json"]``.
        extra_surface_files: Extra ``{filename: text}`` surface files to
            write beside the script, for the anti-hard-coded-list descriptor.
        line_limit: The single per-extension line limit used throughout.
    """
    dest = copy_production_modules(root)

    if extra_surface_files:
        for name, text in extra_surface_files.items():
            (dest / name).write_text(text, encoding="utf-8")

    line_limits = {ext: line_limit for ext in checked_extensions}
    config = {
        "file_size": {
            "_comment": surface_text(comment_extensions),
            "line_limits": line_limits,
            "default_limit": line_limit,
            "checked_extensions": checked_extensions,
            "published_rule_surfaces": surfaces if surfaces is not None else ["README.md", "commit_guardian.json"],
        }
    }
    (dest / "commit_guardian.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (dest / "README.md").write_text(surface_text(readme_extensions), encoding="utf-8")
    return dest


def run_direct(root: Path) -> subprocess.CompletedProcess:
    """Invoke the fixture's own copy of the reconciliation gate directly."""
    return run([PYTHON, str(root / "scripts" / "commit_guardian" / SCRIPT_NAME)], root)


def parse_compared_count(text: str) -> int | None:
    """Extract the "Compared N surface(s)" count the gate's own output states."""
    match = _COMPARED_PATTERN.search(text)
    return int(match.group(1)) if match else None


def disagreement_lines(combined: str) -> list[str]:
    """Return every line reporting a disagreement (the pinned prefix)."""
    return [line for line in combined.splitlines() if line.startswith(f"{DISAGREEMENT_TOKEN}:")]


def indeterminate_lines(combined: str) -> list[str]:
    """Return every line reporting the pinned INDETERMINATE outcome."""
    return [line for line in combined.splitlines() if line.startswith(INDETERMINATE_PREFIX)]


def write_precommit_config(root: Path) -> None:
    """Write a `.pre-commit-config.yaml` wiring the reconciliation hook ALONE."""
    body = (
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: check-file-size-rule-parity\n"
        "        name: Check File Size Rule Parity\n"
        "        entry: python scripts/commit_guardian/run_hook.py "
        f"scripts/commit_guardian/{SCRIPT_NAME}\n"
        "        language: system\n"
        "        pass_filenames: false\n"
        "        always_run: true\n"
    )
    (root / ".pre-commit-config.yaml").write_text(body, encoding="utf-8")


def install_precommit(root: Path) -> None:
    """Install the real pre-commit hook into *root*'s `.git/hooks/`."""
    result = run(["pre-commit", "install", "-f"], root)
    assert result.returncode == 0, f"pre-commit install failed: stdout={result.stdout!r} stderr={result.stderr!r}"


def stage_all(root: Path) -> None:
    """Stage every file in *root* (a throwaway fixture repo -- `-A` is safe here)."""
    git(["add", "-A"], root)


def commit(root: Path, message: str) -> subprocess.CompletedProcess:
    """Perform a REAL, ordinary `git commit` -- the production entry point."""
    return git(["commit", "-m", message], root, timeout=HOOK_COMMIT_TIMEOUT_SECONDS)


def build_deployed_fixture_repo(root: Path) -> None:
    """Build a REAL `build.py` deploy at *root*."""
    result = run([PYTHON, str(BUILD_PY), "--target-dir", str(root)], _REPO_ROOT, timeout=BUILD_TIMEOUT_SECONDS)
    assert result.returncode == 0, f"build.py itself failed: stdout={result.stdout!r} stderr={result.stderr!r}"


def deployed_script_path(root: Path) -> Path:
    """Return the path to the DEPLOYED copy of the reconciliation gate."""
    return root / "scripts" / "commit_guardian" / SCRIPT_NAME
