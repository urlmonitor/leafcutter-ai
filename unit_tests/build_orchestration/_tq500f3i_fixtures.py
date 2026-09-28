"""
MODULE: unit_tests/build_orchestration/_tq500f3i_fixtures.py
GOAL: Shared real-git-repo + real-AC-YAML-store fixtures for the TQ-500f-3-i
    (fast-lane reader) and TQ-500f-3-ii (heavy-lane wiring, seam test) test
    families.
BUSINESS CONTEXT: TQ-500f-3-i extends the ONE existing verify_red_baseline
    reader (scripts/build_orchestration/fast_lane.py +
    _fl_red_baseline_support.py) to refuse an absence-only red (ImportError /
    AttributeError / ModuleNotFoundError) for a covering test whose AC
    test_spec entry declares ``must_catch`` or ``angle: discrimination``. This
    module builds the T1/T2/T3 fixture named in TQ-500f-3-i's own criteria:
        T1: must_catch declared, only red is a function-level ImportError
            (absence) -> must be REFUSED.
        T2: must_catch declared, red is an AssertionError -> must be ACCEPTED.
        T3: no must_catch / no angle: discrimination, red is a function-level
            ImportError (absence) -> must still be ACCEPTED (the control
            against a reader that refuses every import-error red).
    Mirrors the git-fixture pattern already established in
    test_bo2400a_3_amended_red_baseline.py (real git init/clone, real pytest
    files, never a hand-typed pytest-output literal) -- see that file's own
    docstring for the rationale.
ARCHITECTURE: AC YAML fixtures are built as plain dicts and written via
    yaml.safe_dump (never a hand-typed YAML string) per CLAUDE.md's Fixture
    Authenticity Rule (2h.2) -- a hand-typed YAML literal would reproduce the
    author's own mental model of the format rather than proving the reader
    parses what the REAL serializer emits.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE_SCRIPT = REPO_ROOT / "scripts" / "build_orchestration" / "fast_lane.py"

# The real subdirectories fast_lane.py (and the modules it imports via
# _fl_common.py's sys.path wiring: done_proof, scan_ac_store, ac_parent_id,
# check_changelog_presence) needs present as SIBLINGS under the same
# "scripts" parent -- see _fl_common.py's own module docstring.
_FAST_LANE_SIBLING_DIRS = ("build_orchestration", "ac_store", "release")


def install_fast_lane_scripts_into(worktree_root: Path) -> Path:
    """Copy the REAL, on-disk fast_lane.py module family into
    ``<worktree_root>/.leafcutter/scripts/`` -- the SAME cwd-relative
    ``{{config.output_root}}/scripts/...`` location build-feature.js's own
    gate-dispatch command resolves against (see _fl_common.py / the
    ``AC_STORE_REL_PATH`` convention in build-feature.js) -- so a command
    captured from a real dispatch and re-pointed at a disposable git
    worktree fixture can actually be executed for real, not merely
    constructed.

    Mirrors the "build a real, physically distinct copy on disk" technique
    unit_tests/workflows/test_acd_2100a_1.py already established for the
    sibling `{{config.output_root}}`-resolution family, generalised to a
    real multi-module package rather than one single-file stub.

    Args:
        worktree_root: The disposable git worktree fixture's root directory.

    Returns:
        Absolute path to the copied ``fast_lane.py``, i.e.
        ``<worktree_root>/.leafcutter/scripts/build_orchestration/fast_lane.py``.
    """
    dest_scripts_dir = worktree_root / ".leafcutter" / "scripts"
    dest_scripts_dir.mkdir(parents=True, exist_ok=True)
    for name in _FAST_LANE_SIBLING_DIRS:
        src = REPO_ROOT / "scripts" / name
        dest = dest_scripts_dir / name
        if dest.exists():
            continue
        shutil.copytree(
            src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
    return dest_scripts_dir / "build_orchestration" / "fast_lane.py"

# The declared "wrong version" phrase every must_catch-carrying entry in this
# fixture family uses -- copied verbatim from TQ-500f-3-i's own criteria.
MUST_CATCH_REVERT_FIX = "revert the fix"


def run_git(args: list[str], cwd: Path) -> str:
    """Run a read-only-or-mutating git subcommand in *cwd*; raise on failure."""
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {cwd} (exit {result.returncode}): "
            f"{result.stderr}"
        )
    return result.stdout


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    run_git(["init", "-b", "main", "-q"], cwd=path)
    run_git(["config", "user.email", "test-writer@example.com"], cwd=path)
    run_git(["config", "user.name", "Test Writer"], cwd=path)
    run_git(["config", "core.autocrlf", "false"], cwd=path)


def commit_all(path: Path, message: str) -> str:
    """Stage everything, commit, and return the new commit's full sha."""
    run_git(["add", "-A"], cwd=path)
    run_git(["commit", "-q", "-m", message], cwd=path)
    return run_git(["rev-parse", "HEAD"], cwd=path).strip()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def make_worktree(tmp_root: Path, base_files: dict[str, str] | None = None) -> tuple[Path, str]:
    """Create an origin repo with *base_files* committed, clone it, return (work_dir, base_sha).

    Mirrors test_bo2400a_3_amended_red_baseline.py's ``_make_worktree``: the
    clone's HEAD == origin/main (no divergence) after cloning, so any file
    subsequently written into the clone and left uncommitted is -- by
    construction -- absent from the merge-base version and classified
    newly-added.
    """
    origin_dir = tmp_root / "origin"
    init_repo(origin_dir)
    if not base_files:
        write(origin_dir / "README.md", "placeholder\n")
    else:
        for rel_path, content in base_files.items():
            write(origin_dir / rel_path, content)
    base_sha = commit_all(origin_dir, "base")

    work_dir = tmp_root / "work"
    run_git(["clone", "-q", str(origin_dir), str(work_dir)], cwd=tmp_root)
    run_git(["config", "user.email", "test-writer@example.com"], cwd=work_dir)
    run_git(["config", "user.name", "Test Writer"], cwd=work_dir)
    run_git(["config", "core.autocrlf", "false"], cwd=work_dir)
    return work_dir, base_sha


def write_ac_yaml(ac_root: Path, ac_id: str, test_spec: list[dict], **extra) -> Path:
    """Write a minimal, real AC YAML record via yaml.safe_dump (never hand-typed).

    Args:
        ac_root: Directory the AC store root the reader will be pointed at.
        ac_id: The AC's ``id`` field.
        test_spec: The ``test_spec`` list -- entries the reader matches a
            covering test's function name against for ``must_catch`` /
            ``angle``.
        **extra: Additional top-level fields (e.g. ``criteria``) merged in.

    Returns:
        Path to the written YAML file.
    """
    record: dict = {
        "id": ac_id,
        "component": "testing_quality",
        "level": "L3",
        "status": "active",
        "test_spec": test_spec,
    }
    record.update(extra)
    path = ac_root / f"{ac_id}.yaml"
    ac_root.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# T1/T2/T3 fixture builders -- the shape named in TQ-500f-3-i's own criteria.
# ---------------------------------------------------------------------------

T1_NAME = "test_t1_absence_must_catch"
T2_NAME = "test_t2_assertion_must_catch"
T3_NAME = "test_t3_absence_undeclared"


def t1_t2_t3_test_spec() -> list[dict]:
    return [
        {"name": T1_NAME, "must_catch": [MUST_CATCH_REVERT_FIX]},
        {"name": T2_NAME, "must_catch": [MUST_CATCH_REVERT_FIX]},
        {"name": T3_NAME},
    ]


def write_t1_t2_t3_test_files(test_root: Path, ac_id: str, *, include: set[str] | None = None) -> None:
    """Write the T1/T2/T3 fixture test files, each tagged '# covers: <ac_id>'.

    Args:
        test_root: Directory to write the .py test files into.
        ac_id: The AC id every function's covers-tag names.
        include: When given, only the named function(s) are written (used to
            build the T2+T3-only control fixture). Defaults to all three.
    """
    wanted = include if include is not None else {T1_NAME, T2_NAME, T3_NAME}
    if T1_NAME in wanted:
        write(
            test_root / "test_t1_absence.py",
            f"""\
            def {T1_NAME}():
                # covers: {ac_id}
                from doesnotexist_refresh_config_v2_mod import refresh_config_v2
                refresh_config_v2()
            """,
        )
    if T2_NAME in wanted:
        write(
            test_root / "test_t2_assertion.py",
            f"""\
            def {T2_NAME}():
                # covers: {ac_id}
                assert 1 == 3, "expected 1 refresh call, got 3"
            """,
        )
    if T3_NAME in wanted:
        write(
            test_root / "test_t3_absence_undeclared.py",
            f"""\
            def {T3_NAME}():
                # covers: {ac_id}
                from doesnotexist_summarise_window_mod import summarise_window
                summarise_window()
            """,
        )


def names(entries: list[dict] | None) -> set[str]:
    """Return the set of trailing '::func_name' suffixes present in *entries*."""
    out: set[str] = set()
    for entry in entries or []:
        nodeid = str(entry.get("nodeid", ""))
        if "::" in nodeid:
            out.add(nodeid.rsplit("::", 1)[-1])
        elif nodeid:
            out.add(nodeid)
    return out


def find_by_name(entries: list[dict] | None, func_name: str) -> dict | None:
    """Find the entry in *entries* whose nodeid ends with '::<func_name>'."""
    for entry in entries or []:
        nodeid = str(entry.get("nodeid", ""))
        if nodeid.endswith(f"::{func_name}") or nodeid == func_name:
            return entry
    return None
