"""
MODULE: unit_tests/commit_guardian/_ge_127a_1_ordinary_commit_fixture.py
COVERS: GE-127a-1 (shared fixture module -- carries no tests of its own)

GOAL: Build a REAL, isolated git repository wired so an ORDINARY `git commit`
    -- no extra command, no extra flag, and nothing invoked by hand -- routes
    through the REAL `check_file_size.py` gate via the REAL `run_hook.py`
    dispatcher, and `.pre-commit-config.yaml` carries `check-file-size` ALONE.

WHY A SINGLE-HOOK FIXTURE. GE-127a-1's own notes ("OPEN COVERAGE GAP, RECORDED
    2026-09-08") record that a full commit round-trip in a nested build target
    trips an unrelated `check-build-drift` failure that has nothing to do with
    file size, and that the fix is "a temporary repository whose
    `.pre-commit-config.yaml` carries the file-size hook ALONE, so an ordinary
    commit exercises this gate and nothing else" -- the same fixture shape
    `test_ge_120g_1.py`'s `_build_fixture_repo()` / `_install_precommit()`
    already use for a sibling AC. This module adapts that shape: it copies the
    real gate script plus every module it imports (verified by actually
    running the hook in a throwaway fixture at authoring time -- see the
    DECISION HISTORY below -- not by reading the import list alone), so the
    deployed-copy descriptor can also surface a `ModuleNotFoundError` for a
    helper missing a deploy-map entry rather than passing on source-tree
    greenness.

WHAT THIS BUYS OVER THE PRIOR `pre-commit run check-file-size` SUBSTITUTION:
    a real `git commit` is the actual mechanism GE-127a-1's Given/When clauses
    name ("performs an ordinary commit"). `pre-commit run <id>` is itself an
    extra command invoked by hand and proves nothing about whether the
    ordinary commit path ever reaches the gate -- a build where the manifest
    entry exists but the hook was never wired into the commit chain would
    still pass every `pre-commit run` invocation. Only a real `git commit`,
    with the hook installed via a real `pre-commit install`, can fail to
    reach the gate at all.

MUTATION HELPERS (the BA's two named injections, GE-127a-1's test_spec):
    `apply_mutation_refuse_regardless_of_length` and
    `apply_mutation_report_all_staged_as_offenders` patch the FIXTURE'S OWN
    COPY of `check_file_size.py` on disk (never the template source) by
    locating an exact, known source snippet and replacing it -- raising
    loudly if that snippet is not found, so a future change to the production
    comparison logic cannot silently turn either injection into a no-op.

DECISION HISTORY
- 2026-09-14 [test-writer/GE-127a-1]: Rewrote the five descriptors' shared
    fixture to drive a REAL ordinary `git commit` (closing GE-127a-1's own
    recorded coverage gap) rather than `pre-commit run check-file-size`.
    Verified in a throwaway /tmp fixture at authoring time that copying
    exactly `check_file_size.py`, `_resolve_root.py`, `_file_size_ratchet.py`,
    `config.py`, `run_hook.py` and `check_outcome.py` (the last for
    `run_hook.py`'s own import) is sufficient -- no `ModuleNotFoundError` at
    any commit in that manual run -- confirmed by actually installing
    `pre-commit` and committing, not by reading the import graph alone.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_SRC = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_BUILD_PY = _REPO_ROOT / "scripts" / "build.py"

# Every module check_file_size.py needs to run, transitively, plus
# check_outcome.py for run_hook.py's own import. Verified by actually running
# the hook in a throwaway fixture -- see module docstring.
PRODUCTION_MODULES: tuple[str, ...] = (
    "check_file_size.py",
    "_resolve_root.py",
    "_file_size_ratchet.py",
    "config.py",
    "run_hook.py",
    "check_outcome.py",
)

PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 30
_BUILD_TIMEOUT_SECONDS = 180

# Toggle for the one-off ablation proof described in this ticket's own
# "Verify before reporting" step: flip to False, rerun the crossing-refusal
# descriptor, confirm it goes RED, then flip back. Left True for every
# committed test run -- this is a manual verification lever, not a runtime
# test parameter.
INCLUDE_CHECK_FILE_SIZE_HOOK = True


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run *cmd* for real in *cwd*, capturing text output, never raising."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*."""
    return run(["git", *args], cwd)


def init_repo(root: Path) -> None:
    """Initialize a real git repository with a deterministic identity."""
    git(["init", "-q"], root)
    git(["config", "user.email", "test-writer@example.com"], root)
    git(["config", "user.name", "GE-127a-1 ordinary-commit fixture"], root)
    git(["config", "core.autocrlf", "false"], root)


def copy_production_modules(root: Path) -> None:
    """Copy the real gate script and its dependencies into *root*."""
    dest = root / "scripts" / "commit_guardian"
    dest.mkdir(parents=True, exist_ok=True)
    for name in PRODUCTION_MODULES:
        shutil.copy2(_COMMIT_GUARDIAN_SRC / name, dest / name)


def write_config_json(root: Path, line_limit: int) -> None:
    """Write a minimal commit_guardian.json beside the copied gate script.

    config.py resolves ``_CONFIG_PATH`` relative to its own ``__file__``, so
    this MUST sit beside the deployed script, never at the repo root.
    """
    config = {
        "file_size": {
            "line_limits": {".py": line_limit},
            "default_limit": line_limit,
            "checked_extensions": [".py"],
        }
    }
    dest = root / "scripts" / "commit_guardian" / "commit_guardian.json"
    dest.write_text(json.dumps(config), encoding="utf-8")


def write_precommit_config(root: Path, include_file_size_hook: bool = True) -> None:
    """Write a `.pre-commit-config.yaml` wiring `check-file-size` ALONE.

    ``include_file_size_hook=False`` produces a config with no hooks at all
    -- used only for the manual ablation proof described in this ticket's
    "Verify before reporting" step (see ``INCLUDE_CHECK_FILE_SIZE_HOOK``).
    """
    if include_file_size_hook:
        body = (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: check-file-size\n"
            "        name: Check File Size\n"
            "        entry: python scripts/commit_guardian/run_hook.py "
            "scripts/commit_guardian/check_file_size.py\n"
            "        language: system\n"
            "        pass_filenames: false\n"
            "        always_run: true\n"
        )
    else:
        body = "repos: []\n"
    (root / ".pre-commit-config.yaml").write_text(body, encoding="utf-8")


def build_minimal_fixture_repo(root: Path, line_limit: int) -> None:
    """Compose a full minimal, source-copied fixture repo at *root*."""
    copy_production_modules(root)
    write_config_json(root, line_limit)
    write_precommit_config(root, include_file_size_hook=INCLUDE_CHECK_FILE_SIZE_HOOK)
    init_repo(root)


def build_deployed_fixture_repo(root: Path) -> None:
    """Build a REAL `build.py` deploy at *root*, wired the same minimal way.

    The deployed `.pre-commit-config.yaml` build.py itself would generate
    carries every registered hook, including `check-build-drift`, which
    fails in a nested build target for reasons unrelated to file size (see
    module docstring). Overwriting it with the single-hook config here is
    what lets an ordinary commit reach ONLY the deployed `check-file-size`
    copy without that collateral failure.
    """
    result = run([PYTHON, str(_BUILD_PY), "--target-dir", str(root)], _REPO_ROOT)
    assert result.returncode == 0, (
        f"build.py itself failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    write_precommit_config(root, include_file_size_hook=INCLUDE_CHECK_FILE_SIZE_HOOK)
    init_repo(root)


def install_precommit(root: Path) -> None:
    """Install the real pre-commit hook into *root*'s `.git/hooks/`."""
    result = run(["pre-commit", "install", "-f"], root)
    assert result.returncode == 0, (
        f"pre-commit install failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def configured_limit(root: Path) -> int:
    """Read the REAL configured `.py` limit back from the fixture's own config."""
    config_path = root / "scripts" / "commit_guardian" / "commit_guardian.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    return config["file_size"]["line_limits"][".py"]


def content_lines(n_lines: int, tag: str = "v") -> str:
    """Deterministic, docstring-free plain-Python content counting as n_lines."""
    return "\n".join(f"{tag}_{i:06d} = {i}" for i in range(n_lines)) + "\n"


def stage(root: Path, paths: list[str]) -> None:
    """Stage exactly *paths* -- never `-A` -- so copied fixture scripts and
    the generated `.pre-commit-config.yaml` are never accidentally committed.
    """
    git(["add", "--", *paths], root)


def commit(root: Path, message: str) -> subprocess.CompletedProcess:
    """Perform a REAL, ordinary `git commit` -- the production entry point
    every descriptor in this record must exercise. No extra flag beyond
    `-m` is passed; nothing about the gate is invoked by hand.
    """
    return git(["commit", "-m", message], root)


def check_file_size_path(root: Path) -> Path:
    """Return the path to the fixture's own copy of check_file_size.py."""
    return root / "scripts" / "commit_guardian" / "check_file_size.py"


_REFUSE_ONLY_OVER_LIMIT = (
    '    if lines > limit:\n'
    '        return "too_large", lines, limit\n'
    '    return "pass", lines, None\n'
)
_REFUSE_REGARDLESS_OF_LENGTH = '    return "too_large", lines, limit\n'

_REPORT_ONLY_REAL_OFFENDERS = (
    '            if verdict == "grew":\n'
    '                grown_files.append((filepath, reference, lines))\n'
    '            elif verdict == "too_large":\n'
    '                failed_files.append((filepath, lines, reference))\n'
    '            else:\n'
    '                passed_files.append((filepath, lines, is_new))\n'
)
_REPORT_ALL_STAGED_AS_OFFENDERS = (
    '            failed_files.append((filepath, lines, get_limit_for_extension(filepath)))\n'
)


def apply_mutation_refuse_regardless_of_length(root: Path) -> str:
    """BA's injection 1: a file AT OR BELOW its permitted length is refused
    alongside one above it. Patches the fixture's own copy of
    check_file_size.py in place and returns the original text for revert.
    """
    path = check_file_size_path(root)
    original = path.read_text(encoding="utf-8")
    assert _REFUSE_ONLY_OVER_LIMIT in original, (
        "mutation target snippet not found -- check_file_size.py's "
        "_classify_file comparison may have changed shape"
    )
    path.write_text(original.replace(_REFUSE_ONLY_OVER_LIMIT, _REFUSE_REGARDLESS_OF_LENGTH), encoding="utf-8")
    return original


def apply_mutation_report_all_staged_as_offenders(root: Path) -> str:
    """BA's injection 2: every staged file of a covered kind is included in
    the reported set regardless of its measured length. Patches the
    fixture's own copy of check_file_size.py in place and returns the
    original text for revert.
    """
    path = check_file_size_path(root)
    original = path.read_text(encoding="utf-8")
    assert _REPORT_ONLY_REAL_OFFENDERS in original, (
        "mutation target snippet not found -- check_file_size.py's main() "
        "classification loop may have changed shape"
    )
    path.write_text(original.replace(_REPORT_ONLY_REAL_OFFENDERS, _REPORT_ALL_STAGED_AS_OFFENDERS), encoding="utf-8")
    return original


def restore_check_file_size(root: Path, original_text: str) -> None:
    """Revert a mutation applied above, restoring the exact original text."""
    check_file_size_path(root).write_text(original_text, encoding="utf-8")
