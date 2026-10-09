"""Shared helpers for test_tq_600b_2.py (see its module docstring for the contract)."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parent / "data_tq_600b_2"

# shape key -> (committed fixture, fixed-location marker the OFFENDER line must name)
SHAPE_FIXTURES = {
    "a": (DATA / "shape_a_literal_absolute_path.py.txt", "leaf_fixed_shape_a"),
    "b": (DATA / "shape_b_gettempdir_constant.py.txt", "leaf_fixed_shape_b"),
    "c": (DATA / "shape_c_fixed_dir_and_prefix.py.txt", "leaf_fixed_shape_c_"),
    "d": (DATA / "shape_d_module_level_constant.py.txt", "leaf_fixed_shape_d"),
}
CLEAN_FIXTURE = DATA / "clean_per_test_tmp_path.py.txt"
UNPARSEABLE_FIXTURE = DATA / "unparseable.py.txt"
SITE_DECLARED = DATA / "site_declared_exempt.py.txt"
SITE_UNDECLARED = DATA / "site_undeclared.py.txt"


def place(root: Path, fixture: Path, name: str) -> Path:
    """Copy a committed fixture's bytes verbatim into ``root`` under ``name``."""
    target = root / name
    target.write_bytes(fixture.read_bytes())
    return target


def run_examination(*roots: Path) -> subprocess.CompletedProcess:
    """Run the examination CLI against explicit roots, from the repo root."""
    argv = [sys.executable, "-m", "scripts.suite_performance.check_fixed_scratch_paths"]
    for root in roots:
        argv += ["--root", str(root)]
    return subprocess.run(  # noqa: S603
        argv, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False
    )


def inspected_count(stdout: str) -> int:
    """Parse the ``inspected: N`` line; -1 when the output carries none."""
    match = re.search(r"^inspected:\s*(\d+)\s*$", stdout, flags=re.MULTILINE)
    return int(match.group(1)) if match else -1


def lines_starting(stdout: str, prefix: str) -> list[str]:
    """Output lines that begin with ``prefix``."""
    return [line for line in stdout.splitlines() if line.startswith(prefix)]
