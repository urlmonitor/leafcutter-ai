"""
MODULE: _bp900h4_layout_helpers
AC: BP-900h-4 / BP-900h-4-i
GOAL: Test-only construction helpers shared by test_bp_900h_4.py and
    test_bp_900h_4_i.py. Builds REAL consumer-layout installs — a package
    checkout (a real git clone or a real git worktree, never a hand-copied
    directory) sibling to a REAL ``scripts/build.py``-produced deployed
    output root — so the declaring-file resolution fixture is anchored to
    genuine filesystem structure rather than an approximation of it.

WHY A REAL CLONE / WORKTREE, NOT A COPY: BP-900h-4-i's constraint "THE
    WORKTREE LAYOUT MUST BE A REAL GIT WORKTREE, not a copied directory" is
    load-bearing — the reported trigger for KI-BP-003 is that a directory
    populated in the main checkout is EMPTY in a linked worktree (worktrees
    share the object store but not untracked/gitignored working-tree state).
    A ``shutil.copytree`` reproduces the contents and therefore reproduces
    neither the trigger nor the defect. ``git worktree add`` against this
    very checkout's shared object store is fast (confirmed <1s for a full
    clone, ~1s for a worktree add, in-session) and gives the real distinction.

Both helpers are safe to call from any test file rooted at this repository's
own checkout (``_WORKTREE_ROOT`` is resolved relative to this file, three
parents up: unit_tests/portability/_this_file.py -> repo root).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]


def make_package_checkout(dest: Path, *, as_worktree: bool) -> Path:
    """Create a REAL, independent package checkout at *dest*.

    as_worktree=False: a real ``git clone --local`` of this repository —
        a genuine non-worktree checkout (its own ``.git`` directory).
    as_worktree=True: a real ``git worktree add`` linked to this repo's
        object store — a genuine git worktree (``.git`` is a file pointing
        at the shared store, and untracked/gitignored directories that
        happen to be populated in the main checkout are NOT copied).
    """
    dest = Path(dest)
    if as_worktree:
        subprocess.run(
            [
                "git", "-C", str(_WORKTREE_ROOT), "worktree", "add",
                "--quiet", "--detach", str(dest), "HEAD",
            ],
            check=True, capture_output=True, text=True, timeout=60,
        )
    else:
        subprocess.run(
            ["git", "clone", "--local", "--quiet", str(_WORKTREE_ROOT), str(dest)],
            check=True, capture_output=True, text=True, timeout=60,
        )
    return dest


def remove_package_checkout(dest: Path, *, was_worktree: bool) -> None:
    """Tear down a checkout created by ``make_package_checkout``.

    A worktree must be deregistered via ``git worktree remove`` — deleting
    its directory alone leaves a dangling entry in the shared
    ``.git/worktrees/`` metadata.
    """
    dest = Path(dest)
    if was_worktree:
        subprocess.run(
            ["git", "-C", str(_WORKTREE_ROOT), "worktree", "remove", "--force", str(dest)],
            check=False, capture_output=True, text=True, timeout=60,
        )
        subprocess.run(
            ["git", "-C", str(_WORKTREE_ROOT), "worktree", "prune"],
            check=False, capture_output=True, text=True, timeout=30,
        )
    else:
        shutil.rmtree(dest, ignore_errors=True)


def build_consumer_install(
    package_dir: Path, deployed_parent: Path, *, extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the REAL ``scripts/build.py`` from *package_dir* into
    *deployed_parent*, producing a deployed output root as a sibling of
    nothing in particular — the caller decides what *deployed_parent*
    contains before/after. With no *extra_args*, mirrors the exact CI
    invocation shape (``python <package>/scripts/build.py --target-dir
    <target>``). BP-900h-4-i's layout-sweep fixtures pass
    ``extra_args=["--no-shims"]`` to stay inside the fast-lane red-baseline
    gate's fixed 60s pytest budget (confirmed in-session: install_shims adds
    ~3-5s per real build, and that AC alone needs four independent real
    builds in one pytest session) — shim installation is orthogonal to
    declaring-file resolution, so this does not weaken that AC's fixture.
    BP-900h-4's own fixture (test_bp_900h_4.py) deliberately does NOT pass
    this, to keep its single build byte-for-byte the real CI shape.
    """
    deployed_parent = Path(deployed_parent)
    deployed_parent.mkdir(parents=True, exist_ok=True)
    build_script = Path(package_dir) / "scripts" / "build.py"
    return subprocess.run(
        [sys.executable, str(build_script), "--target-dir", str(deployed_parent),
         *(extra_args or [])],
        capture_output=True, text=True, timeout=120,
    )


def find_output_root(target_dir: Path, *, exclude_name: str | None = None) -> Path:
    """Return the deployed output root inside *target_dir* (the directory
    holding ``scripts/``). Keyed on ``scripts/`` for the same reason
    test_bp_900g_4.py's identical helper is: agent markdown deploys to more
    than one location, but scripts land only under the single output root.

    *exclude_name* must be passed whenever *target_dir* also contains the
    PACKAGE checkout as a sibling of the deployed root (this AC's own CI
    layout shape) — the package checkout has its own real ``scripts/``
    directory and would otherwise be indistinguishable from the deployed
    output root by this heuristic alone.
    """
    target_dir = Path(target_dir)
    candidates = sorted(
        p for p in target_dir.iterdir()
        if p.is_dir() and (p / "scripts").is_dir() and p.name != exclude_name
    )
    assert len(candidates) == 1, (
        f"Expected exactly one deployed output root under {target_dir} "
        f"(a directory containing a 'scripts/' subdirectory); found "
        f"{[p.name for p in candidates]}."
    )
    return candidates[0]
