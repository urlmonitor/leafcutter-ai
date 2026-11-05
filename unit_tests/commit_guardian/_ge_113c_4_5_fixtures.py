"""
MODULE: unit_tests/commit_guardian/_ge_113c_4_5_fixtures.py
GOAL: Shared fixture helpers for the GE-113c-4 (check_mermaid_parent_link.py)
      and GE-113c-5 (check_adr_cross_reference.py) test modules. Not a test
      file itself.
BUSINESS CONTEXT: Both hooks join every path they read to
      ``Path(__file__).resolve().parents[2]`` -- ``templates/`` for the
      package source copy and ``.leafcutter/`` for the installed copy that
      .pre-commit-config.yaml runs -- so neither ever reads the staged
      documents of the project it guards. The tests drive each hook the way
      pre-commit does: a REAL temporary git repository with REAL staged
      fixture documents, the hook run as a REAL subprocess with cwd inside
      that repository.
ARCHITECTURE: The installed layout mirrors
      _ge_113c_1_vi_fixtures.deploy_hook: the hook, _resolve_root.py and
      check_outcome.py (which the fixed hooks import) are copied into
      ``<repo>/.leafcutter/scripts/commit_guardian/``. No build.py is spawned
      and no POSIX flock is needed, so every test runs locally as well as on
      CI. The subprocess environment is stripped of PYTHONPATH and every
      GIT_* variable, so neither this checkout's modules nor an outer
      pre-commit run's index can leak into the fixture repository.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_CG_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
INSTALLED_REL_DIR = Path(".leafcutter") / "scripts" / "commit_guardian"
SUPPORT_MODULES = ("_resolve_root.py", "check_outcome.py")

# A marker line the instrumented check_outcome copy prints, so a test can tell
# a result emitted through check_outcome.emit_result from a literal minted in
# the hook itself.
EMIT_MARKER = "FIXTURE-CHECK-OUTCOME-EMIT-RESULT-CALLED:"

_TIMEOUT_SECONDS = 30


def deploy_installed_copy(repo: Path, hook_name: str) -> Path:
    """Copy a hook and its support modules into the installed layout of `repo`.

    Returns:
        The repository-relative path of the installed hook.
    """
    deployed_dir = repo / INSTALLED_REL_DIR
    deployed_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(TEMPLATES_CG_DIR / hook_name, deployed_dir / hook_name)
    for name in SUPPORT_MODULES:
        shutil.copy(TEMPLATES_CG_DIR / name, deployed_dir / name)
    return INSTALLED_REL_DIR / hook_name


def instrument_installed_check_outcome(repo: Path) -> None:
    """Make the installed check_outcome.emit_result also print EMIT_MARKER.

    The real module source is kept verbatim; a wrapper is appended that
    rebinds emit_result, so the RESULT line itself is still the real one.
    """
    target = repo / INSTALLED_REL_DIR / "check_outcome.py"
    source = (TEMPLATES_CG_DIR / "check_outcome.py").read_text(encoding="utf-8")
    wrapper = (
        "\n\n_fixture_real_emit_result = emit_result\n\n\n"
        "def emit_result(outcome):\n"
        f"    print({EMIT_MARKER!r} + ' ' + str(outcome), file=sys.stdout)\n"
        "    _fixture_real_emit_result(outcome)\n"
    )
    target.write_text(source + wrapper, encoding="utf-8")


def source_copy(hook_name: str) -> Path:
    """Absolute path of the package source copy of a hook."""
    return TEMPLATES_CG_DIR / hook_name


def clean_env() -> dict[str, str]:
    """A subprocess environment with no PYTHONPATH and no GIT_* variables."""
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("GIT_") and k != "PYTHONPATH"
    }
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def git_init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True, env=clean_env())


def git_add(repo: Path, *rel_paths: str) -> None:
    subprocess.run(["git", "add", *rel_paths], cwd=str(repo), check=True, env=clean_env())


def write_markdown(path: Path, frontmatter: dict, body: str) -> None:
    """Write a markdown document whose frontmatter comes from yaml.safe_dump."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.safe_dump(frontmatter, sort_keys=False)
    path.write_text(f"---\n{fm_text}---\n\n{body}", encoding="utf-8")


def run_hook(hook: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a hook as a subprocess, the way pre-commit does.

    `hook` may be relative (resolved against `cwd`, as the pre-commit entry
    ``python .leafcutter/scripts/commit_guardian/<hook>.py`` is) or absolute.
    """
    return subprocess.run(
        [sys.executable, str(hook), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=clean_env(),
        timeout=_TIMEOUT_SECONDS,
    )


def output_of(proc: subprocess.CompletedProcess) -> str:
    """stdout and stderr of a finished hook run, joined."""
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def result_lines(proc: subprocess.CompletedProcess) -> list[str]:
    """The machine-readable ``RESULT: ...`` lines a hook printed to stdout."""
    return [
        line.strip() for line in (proc.stdout or "").splitlines()
        if line.strip().startswith("RESULT: ")
    ]
