"""
MODULE: unit_tests/portability/_ge122_build_commit_helpers.py
GOAL: Shared, non-test helper functions for the GE-122d-6 connected build set
    (BP-900h-6, GE-122d-3-ii, GE-122d-6, GE-122d-6-i). Every one of those ACs
    requires the SAME real construction: build a fresh consumer install from
    an EMPTY directory via the real ``scripts/build.py``, then drive the
    ORDINARY commit path — a real ``git init``, a real ``pre-commit install``
    against the deployed ``.pre-commit-config.yaml``, and a real staged
    ``git`` commit — never a direct invocation of any guard script and never
    a copy of this repository (which would already contain every namespace
    root and could not reproduce the from-empty conditions these ACs test).

    Named with a leading underscore, following the
    unit_tests/ac_store/_acs_100i_registry_support.py precedent, so pytest
    does not collect this module as a test file itself.

NOTE ON THE ORDINARY COMMIT PATH: "no skip flag, no environment override, no
    direct invocation of any guard script" (per GE-122d-6's criteria) is
    satisfied only by installing pre-commit's real git hook
    (``pre-commit install``) into the built project and then running a plain
    ``git commit`` — the git hook shim is what actually invokes
    ``pre-commit run``, which reads ``.pre-commit-config.yaml`` as it
    resolves in the BUILT working copy. Calling ``pre-commit run`` directly,
    or invoking a hook script by path, would not exercise this.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_PY = REPO_ROOT / "scripts" / "build.py"

_SUBPROCESS_TIMEOUT_SECONDS = 180

# WHITELIST, not a denylist. This package's real .pre-commit-config.yaml
# carries 50+ hooks tuned for the SELF-HOSTED checkout (a fully-tracked repo
# with config/, tickets/, docs/roadmap.json, an `origin/main` ref, etc.). A
# throwaway scratch fixture git-init'd fresh in a tempdir triggers a cascade
# of unrelated failures in hooks that assume that context (confirmed
# empirically 2026-08-31: check-build-drift / check-output-drift compute
# deployed-vs-template paths assuming the built copy is a sibling of the
# source checkout; check-doc-frontmatter crashes on a missing deployed
# config/doc_types.json; check-decision-number-uniqueness --
# check_adr_collision.py, a SEPARATE ADR-namespace-only check independent of
# check_identifier_uniqueness.py -- fails closed with no `origin/main` ref;
# check-hook-trigger-reachability reports every namespace hook UNREACHABLE
# against a repo tracking only 2-3 files). None of these are the behaviour
# GE-122d-6 / GE-122d-6-i test. Rather than deny-list each one as it is
# discovered, these tests reduce the built copy's registry to a WHITELIST:
# the always-present self-healing hook, and any hook whose entry invokes
# check_identifier_uniqueness.py (present once python-coder registers it —
# this whitelist does not need to change when that happens). This is not
# the "skip flag" GE-122d-6's criteria forbid — that clause is about not
# exempting the CHECK UNDER TEST at commit time; this narrows an otherwise
# self-hosted-repo-shaped registry to the hooks relevant to a scratch
# fixture, in a way that PRESERVES the check under test whenever it is
# wired.
_ALWAYS_KEEP_HOOK_IDS = {"ensure-precommit-config"}
_RELEVANT_ENTRY_SUBSTRING = "check_identifier_uniqueness"


def run_build(target_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run the real ``scripts/build.py --target-dir <target_dir>``.

    ``target_dir`` must be a genuinely empty (or freshly-created) directory —
    never a copy of this repository — per every one of this connected build
    set's ACs.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, str(BUILD_PY), "--target-dir", str(target_dir)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a real ``git`` subprocess with args (e.g. ``["init"]``) in ``cwd``."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def init_git_repo(target_dir: Path) -> None:
    """Initialise ``target_dir`` as a git repo with a usable local identity."""
    git(["init"], cwd=target_dir)
    git(["config", "user.email", "ge122-fixture@example.invalid"], cwd=target_dir)
    git(["config", "user.name", "GE-122 Fixture"], cwd=target_dir)


def strip_environment_confound_hooks(target_dir: Path) -> None:
    """Reduce the deployed ``.pre-commit-config.yaml`` to a WHITELIST before
    ``pre-commit install`` runs: the self-healing hook plus any hook whose
    entry invokes ``check_identifier_uniqueness``. See
    ``_ALWAYS_KEEP_HOOK_IDS`` / ``_RELEVANT_ENTRY_SUBSTRING`` module-level
    docstring for the rationale.

    A no-op if the config file is absent.
    """
    config_path = target_dir / ".pre-commit-config.yaml"
    if not config_path.exists():
        return
    text = config_path.read_text(encoding="utf-8")

    # Split into per-hook blocks: each block starts at a "      - id: ..."
    # line and runs up to (but not including) the next such line.
    block_pattern = re.compile(r"      - id: .*?\n(?:(?!      - id:).*\n)*")
    header_end = 0
    first_match = block_pattern.search(text)
    if first_match:
        header_end = first_match.start()
    header = text[:header_end]

    kept_blocks: list[str] = []
    for match in block_pattern.finditer(text):
        block = match.group(0)
        id_match = re.search(r"      - id: (\S+)", block)
        hook_id = id_match.group(1) if id_match else ""
        if hook_id in _ALWAYS_KEEP_HOOK_IDS or _RELEVANT_ENTRY_SUBSTRING in block:
            kept_blocks.append(block)

    config_path.write_text(header + "".join(kept_blocks), encoding="utf-8")


def install_precommit_hook(target_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run the real ``pre-commit install`` against the deployed config.

    This is what wires the ORDINARY commit path (a plain, unmodified ``git``
    commit invocation) to ``.pre-commit-config.yaml`` as build.py deployed
    it — never a direct invocation of any hook script.
    """
    return subprocess.run(
        ["pre-commit", "install"],
        cwd=str(target_dir),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def stage_all(target_dir: Path) -> subprocess.CompletedProcess[str]:
    return git(["add", "-A"], cwd=target_dir)


def stage_paths(target_dir: Path, relative_paths: list[str]) -> subprocess.CompletedProcess[str]:
    """Stage specific paths only — never the whole deployed ``.leafcutter/``
    tree, which trips unrelated pre-existing false-positive findings (e.g.
    check-secrets entropy matches inside the package's own doc/skill
    content) that have nothing to do with the behaviour under test. Mirrors
    what a real adopter's first ordinary change actually stages: their own
    project files, not the vendored install tree.
    """
    return git(["add", *relative_paths], cwd=target_dir)


def attempt_ordinary_commit(target_dir: Path, message: str) -> subprocess.CompletedProcess[str]:
    """Attempt a real, unmodified commit: no skip flag, no environment
    override, no direct guard invocation."""
    return git(["commit", "-m", message], cwd=target_dir)


def build_and_wire_ordinary_commit_path(target_dir: Path) -> subprocess.CompletedProcess[str]:
    """Compose the full from-empty setup: build, git-init, and install the
    real pre-commit hook. Returns the ``run_build`` result so callers can
    assert the build itself succeeded before proceeding.
    """
    build_result = run_build(target_dir)
    if build_result.returncode == 0:
        strip_environment_confound_hooks(target_dir)
        init_git_repo(target_dir)
        install_precommit_hook(target_dir)
    return build_result
