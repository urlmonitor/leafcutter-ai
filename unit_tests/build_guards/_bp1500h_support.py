"""
MODULE: unit_tests/build_guards/_bp1500h_support.py
GOAL: Shared test-only helpers for the BP-1500h-1 / -1-i / -1-ii / -2 tests:
    build a scratch consumer whose settings file sets a file-location setting
    to a chosen value, run it through the build, and read the output back.
ARCHITECTURE: Two runners.
    * ``real_build`` drives the REAL ``scripts/build.py`` as a subprocess into
      a scratch target (never the worktree). Results are cached per scenario
      for the test session, so each distinct project is built exactly once.
      Tests using it carry ``@pytest.mark.shared_layout_mutator`` -- they own
      a private build, the project's settings differ from the shared layout.
    * ``run_driver`` runs the build's three setting-reading steps in a fresh
      process (see ``_bp1500h_driver.py``) -- cheap, used for the per-key set.
    Settings files are written with ``json.dump`` (the real serializer); the
    shipped default for a key is READ from ``config/skills_config.default.json``,
    never typed here.

PINNED NAMES (from the AC it_requirements, not guessed): the helper module is
    ``scripts/config_paths.py`` exposing ``resolve_file_setting(config, key,
    target_root)``.
"""

from __future__ import annotations

import atexit
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = WORKTREE_ROOT / "scripts"
BUILD_SCRIPT = SCRIPTS_DIR / "build.py"
DRIVER = Path(__file__).resolve().parent / "_bp1500h_driver.py"
DEFAULTS_JSON = WORKTREE_ROOT / "config" / "skills_config.default.json"

HELPER_MODULE = "config_paths"
HELPER_FUNCTION = "resolve_file_setting"
CHANGELOG_KEY = "changelog_categories_path"
PRECOMMIT_KEY = "precommit_autofix_config_path"
REACHABILITY_KEY = "reachability_exemptions_path"
README_KEY = "testing_context.readme_path"

_SCRATCH_DIRS: list[Path] = []
_BUILD_CACHE: dict[str, "BuildRun"] = {}
_DRIVER_CACHE: dict[str, "DriverRun"] = {}


@atexit.register
def _cleanup_scratch() -> None:
    for scratch in _SCRATCH_DIRS:
        shutil.rmtree(scratch, ignore_errors=True)


@dataclass
class BuildRun:
    """A finished real build of one scratch project."""

    target: Path
    returncode: int
    output: str


@dataclass
class DriverRun:
    """A finished driver run: step output plus the parsed result line."""

    target: Path
    returncode: int
    output: str
    result: dict[str, Any]


def shipped_default(key: str) -> str | None:
    """The shipped default for *key*, read from skills_config.default.json."""
    data = json.loads(DEFAULTS_JSON.read_text(encoding="utf-8"))
    node: Any = data
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, str) else None


def settings_for(key: str, value: str | None) -> dict[str, Any]:
    """Settings dict setting *key* to *value*; ``None`` leaves the key absent."""
    parent, _, leaf = key.rpartition(".")
    if parent:
        return {parent: {} if value is None else {leaf: value}}
    return {} if value is None else {key: value}


def _new_scratch() -> Path:
    scratch = Path(tempfile.mkdtemp(prefix="bp1500h_"))
    _SCRATCH_DIRS.append(scratch)
    project = scratch / "consumer_project"
    project.mkdir()
    return project


def _write_settings(project: Path, settings: dict[str, Any]) -> None:
    settings_dir = project / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    with (settings_dir / "skills_config.json").open("w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)


def _plant(project: Path, plant: dict[str, str] | None) -> None:
    for rel, text in (plant or {}).items():
        target = project / rel
        if rel.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")


def real_build(settings: dict[str, Any], plant: dict[str, str] | None = None) -> BuildRun:
    """Build a scratch consumer with *settings* via the real ``build.py``."""
    cache_key = json.dumps([settings, plant], sort_keys=True)
    if cache_key not in _BUILD_CACHE:
        project = _new_scratch()
        _write_settings(project, settings)
        _plant(project, plant)
        proc = subprocess.run(
            [sys.executable, str(BUILD_SCRIPT), "--target-dir", str(project)],
            capture_output=True,
            text=True,
            timeout=420,
            check=False,
        )
        _BUILD_CACHE[cache_key] = BuildRun(
            project, proc.returncode, proc.stdout + proc.stderr
        )
    return _BUILD_CACHE[cache_key]


def run_driver(settings: dict[str, Any], plant: dict[str, str] | None = None) -> DriverRun:
    """Run the setting-reading steps in a fresh process for *settings*."""
    cache_key = json.dumps([settings, plant], sort_keys=True)
    if cache_key not in _DRIVER_CACHE:
        project = _new_scratch()
        _write_settings(project, settings)
        _plant(project, plant)
        proc = subprocess.run(
            [sys.executable, str(DRIVER), str(WORKTREE_ROOT), str(project)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        out = proc.stdout + proc.stderr
        result: dict[str, Any] = {}
        for line in out.splitlines():
            if line.startswith("__RESULT__"):
                result = json.loads(line[len("__RESULT__"):])
        _DRIVER_CACHE[cache_key] = DriverRun(project, proc.returncode, out, result)
    return _DRIVER_CACHE[cache_key]


def lines_with(output: str, *needles: str) -> list[str]:
    """Output lines containing every needle (case-insensitive)."""
    low = [n.lower() for n in needles]
    return [ln for ln in output.splitlines() if all(n in ln.lower() for n in low)]


def not_configured_lines(output: str, key: str) -> list[str]:
    """Lines saying *key* is 'not configured' (the key's last segment)."""
    return lines_with(output, "not configured", key.rpartition(".")[2])


def directory_read_lines(output: str, project: Path) -> list[str]:
    """Lines reporting an attempt to open a folder / the project as a file."""
    bad = []
    for ln in output.splitlines():
        if "is a directory" in ln.lower() or f"could not read {project}" in ln:
            bad.append(ln)
    return bad


def compiled_changelog_step3(project: Path) -> str:
    """Step 3 text of the compiled changelog-agent prompt a build produced."""
    found = [
        p for p in project.rglob("changelog-agent.md") if "templates" not in p.parts
    ]
    assert found, f"build produced no compiled changelog-agent prompt under {project}"
    text = found[0].read_text(encoding="utf-8")
    match = re.search(r"## Step 3.*?(?=\n## Step 4)", text, re.DOTALL)
    assert match, "compiled changelog-agent prompt has no Step 3 section"
    return match.group(0)
