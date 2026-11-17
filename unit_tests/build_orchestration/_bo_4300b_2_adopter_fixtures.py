"""
MODULE: unit_tests/build_orchestration/_bo_4300b_2_adopter_fixtures.py
GOAL: Real-git fixtures for an ADOPTER project that keeps the tools' package in
    a sub-folder (a git submodule, or an ordinary tracked folder) -- the layout
    of DIAGraph, whose package lives at <repo>/leafcutter/ -- and for a project
    that IS the package (the self-host layout). Used by the BO-4300b-2-iii and
    BO-4300b-2-iv proofs.
BUSINESS CONTEXT: The workspace maker used to look for the install build only
    at <workspace>/scripts/build.py, which is the package's own layout. In an
    adopter that folder is the adopter's own, so every workspace was refused
    BOOTSTRAP_FAILED "scripts/build.py is absent" (DIAGraph, build v21.0.93).
ARCHITECTURE: Stdlib-only. Builds a bare hub for the package and one for the
    adopter, a seed for each (deleted once pushed) and a project clone with its
    submodule initialised, as a developer's main checkout would have it. The
    package's build entry point is the shared stub (never the real
    scripts/build.py). Local-path submodules need ``protocol.file.allow``;
    FILE_PROTOCOL carries it as environment config so no git config file is
    touched.

NOT a test file itself (leading underscore). Nothing in here is collected by pytest.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from unit_tests.build_orchestration import _workspace_maker_build_helpers as _bh
from unit_tests.build_orchestration._workspace_maker_fixtures import run_maker  # fixtures first: builders cycle
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env

# Allows git to clone a submodule from a local path (git >= 2.38.1 refuses by default).
FILE_PROTOCOL = {
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "protocol.file.allow",
    "GIT_CONFIG_VALUE_0": "always",
}
PACKAGE_DIR = "leafcutter"
PACKAGE_STAMP = "package-own-build-stamp-4300b2iii"
ADOPTER_STAMP = "adopter-root-stamp-4300b2iii"
# The signature that tells the package apart from any folder with a build.py of its own.
PACKAGE_MARKER = Path("templates") / "scripts" / "worktree.py"

# An adopter's OWN scripts/build.py, unrelated to the package: it must never be run.
OWN_FAILING_BUILD = (
    "import sys\n"
    "print('ADOPTER-OWN-BUILD-WAS-RUN', file=sys.stderr)\n"
    "sys.exit(3)\n"
)


def git(args: list[str], cwd: Path, mkdir: bool = False) -> subprocess.CompletedProcess:
    """Run isolated fixture git in *cwd* (local-path submodules allowed); raise AssertionError on failure."""
    cwd = Path(cwd)
    if mkdir:
        cwd.mkdir(parents=True, exist_ok=True)
    try:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True,
                              env={**_isolated_git_env(), **FILE_PROTOCOL})
    except subprocess.CalledProcessError as exc:
        msg = f"git {args} failed in {cwd}: {exc.stderr}"
        raise AssertionError(msg) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        msg = f"could not launch git {args} in {cwd}: {exc}"
        raise AssertionError(msg) from exc


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


def package_files() -> dict[str, str]:
    """The package's own tree: its stub build entry point, the package signature and its stamp."""
    return {
        "scripts/build.py": _bh.stub_build_py_source("reject"),
        PACKAGE_MARKER.as_posix(): "# the package's own workspace maker (fixture marker)\n",
        "BUILD_STAMP.txt": PACKAGE_STAMP + "\n",
    }


def _seed_and_push(seed: Path, hub: Path, files: dict[str, str], before_commit=None) -> None:
    """Create *hub* (bare) and a seed repo with *files*, commit, push to main, delete the seed."""
    git(["-c", "init.defaultBranch=main", "init", "--bare", "-q"], hub, mkdir=True)
    git(["-c", "init.defaultBranch=main", "init", "-q"], seed, mkdir=True)
    _write(seed, files)
    if before_commit is not None:
        before_commit(seed)
    git(["add", "-A"], seed)
    git(["commit", "-q", "-m", "fixture content"], seed)
    git(["remote", "add", "origin", str(hub)], seed)
    git(["push", "-q", "-u", "origin", "main"], seed)
    shutil.rmtree(seed, ignore_errors=True)


def _adopter_base_files(config: dict | None, extra: dict[str, str] | None) -> dict[str, str]:
    files = {
        "README.md": "adopter project shop\n",
        "BUILD_STAMP.txt": ADOPTER_STAMP + "\n",
        ".claude/skills_config.json": json.dumps(config or {"docs_root": "docs/"}, indent=2) + "\n",
    }
    files.update(extra or {})
    return files


def make_adopter(tmp: Path, *, package: str = "submodule", own_build: str | None = None,
                 config: dict | None = None, extra: dict[str, str] | None = None) -> dict[str, Path]:
    """Build an adopter "shop" holding the package at shop/leafcutter/ and no scripts/build.py of the package.

    Args:
        tmp: Directory everything is built under (sources in ``src/``, the project in ``parent/shop``).
        package: ``"submodule"`` (a real git submodule) or ``"folder"`` (an ordinary tracked folder).
        own_build: Source for shop's OWN ``scripts/build.py`` (absent when ``None``).
        config: shop's ``.claude/skills_config.json`` content.
        extra: Further files committed into shop.

    Returns:
        ``{"project": Path, "hub": Path, "package_hub": Path}``.
    """
    src = Path(tmp) / "src"
    package_hub = src / "package-hub.git"
    _seed_and_push(src / "package-seed", package_hub, package_files())
    files = _adopter_base_files(config, extra)
    if own_build is not None:
        files["scripts/build.py"] = own_build
    if package == "folder":
        files.update({f"{PACKAGE_DIR}/{rel}": text for rel, text in package_files().items()})

    def _hooks_and_submodule(seed: Path) -> None:
        _bh.write_hook_declarations(seed)  # shop's own scripts/commit_guardian/ + .pre-commit-config.yaml
        if package == "submodule":
            git(["submodule", "add", "-q", str(package_hub), PACKAGE_DIR], seed)

    hub = src / "shop-hub.git"
    _seed_and_push(src / "shop-seed", hub, files, before_commit=_hooks_and_submodule)
    project = Path(tmp) / "parent" / "shop"
    git(["clone", "-q", str(hub), str(project)], project.parent, mkdir=True)
    if package == "submodule":
        git(["submodule", "update", "--init", "-q"], project)  # the main checkout has its package
    return {"project": project, "hub": hub, "package_hub": package_hub}


def make_self_host(tmp: Path) -> dict[str, Path]:
    """Build a project that IS the package (scripts/build.py + the package signature at its root)."""
    src = Path(tmp) / "src"
    hub = src / "self-hub.git"
    files = {**package_files(), "README.md": "the package itself\n",
             ".claude/skills_config.json": json.dumps({"docs_root": "docs/"}, indent=2) + "\n"}
    _seed_and_push(src / "self-seed", hub, files, before_commit=_bh.write_hook_declarations)
    project = Path(tmp) / "parent" / "pkg"
    git(["clone", "-q", str(hub), str(project)], project.parent, mkdir=True)
    return {"project": project, "hub": hub}


def ensure(project: Path, slug: str = "alpha", kind: str = "feature") -> dict:
    """Run the DEPLOYED maker's ensure from *project*'s top folder (local-path submodules allowed)."""
    return run_maker(["ensure", "--kind", kind, "--slug", slug], cwd=project, env=dict(FILE_PROTOCOL), timeout=180)


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-11-17 [test-writer/BO-4300b-2-iii]: Created the adopter (submodule / nested folder) and
#   self-host fixtures for the BO-4300b-2-iii/-iv proofs. (#TICKETLESS reason=quick-fix-ac-first)
# ===========================================================================
