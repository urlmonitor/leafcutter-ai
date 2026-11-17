"""
MODULE: _bp1500d2_support
AC: BP-1500d-2 -- "The record still reads after the project is moved, copied or
    opened somewhere else"

GOAL: Test-only helpers for relocating a REAL out-of-package install (built by
    the shared BP-1500d-1 harness, never a second harness) and reading its
    record through the DEPLOYED reader as a subprocess.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
from dataclasses import dataclass
from pathlib import Path

from ._bp1500d1_harness import HarnessBuild, REAL_PACKAGE_ROOT, probe_child_sys_path

READER_REL = Path(".leafcutter/scripts/commit_guardian/check_output_drift.py")
MANIFEST_NAME = ".build_manifest.json"
_RESULT_RE = re.compile(r"RESULT\s+(.*)")


@dataclass
class Read:
    returncode: int
    output: str
    counts: dict

    @property
    def verified(self) -> int:
        return self.counts.get("verified", 0)


def scrubbed_env() -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def read_with_deployed_reader(project: Path) -> Read:
    """Run the DEPLOYED check_output_drift.py from inside *project* as a
    subprocess: cwd is the project (never the package tree), PYTHONPATH is
    scrubbed, and the child's real sys.path is probed for package paths."""
    env = scrubbed_env()
    sys_path = probe_child_sys_path(project, env)
    package = str(REAL_PACKAGE_ROOT.resolve()).lower()
    leaked = [p for p in sys_path if p and str(Path(p).resolve()).lower().startswith(package)]
    assert not leaked, f"reader child can see the package checkout via sys.path: {leaked}"
    proc = subprocess.run(
        [sys.executable, str(project / READER_REL)],
        cwd=str(project), env=env, capture_output=True, text=True, timeout=120, check=False,
    )
    out = proc.stdout + proc.stderr
    counts: dict = {}
    for m in _RESULT_RE.finditer(out):
        counts = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", m.group(1))}
    return Read(proc.returncode, out, counts)


def copy_project(hb: HarnessBuild, dest: Path) -> Path:
    """Copy the built receiving project (and only it) to *dest*."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(hb.target_root, dest)
    return dest


def new_scratch(prefix: str = "bp1500d2_") -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix)).resolve()


def assert_package_absent_from_ancestors(project: Path, package_dir_name: str) -> None:
    """Fixture precondition: the producing package is in no ancestor of the
    project, as a sibling or as a scripts/build.py."""
    for anc in project.resolve().parents:
        assert not (anc / package_dir_name).exists(), f"package dir found under {anc}"
        assert not (anc / "scripts" / "build.py").exists(), f"package build.py found under {anc}"
    assert not (project / package_dir_name).exists()


def load_record(project: Path) -> dict:
    return json.loads((project / MANIFEST_NAME).read_text(encoding="utf-8"))


def non_portable_keys(record: dict) -> list[str]:
    """Entry keys (deployed-artifact keys AND the flat template-hash keys) whose
    form only means something from where the record was written: absolute, or
    reaching outside the project with a '..' step."""
    keys = list(record.get("output_mappings", {})) + [
        k for k, v in record.items() if isinstance(v, str) and len(v) == 64
    ]
    bad = []
    for k in keys:
        norm = k.replace("\\", "/")
        if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm) or ".." in norm.split("/"):
            bad.append(k)
    return bad


def location_keyed(project: Path) -> None:
    """Rewrite the project's record so each deployed-artifact entry is keyed to
    the absolute location the record sits in NOW (the deliberately
    non-portable form), serialized by json.dump like the real writer."""
    rec = load_record(project)
    rec["output_mappings"] = {
        (project.resolve() / k).as_posix(): v for k, v in rec["output_mappings"].items()
    }
    (project / MANIFEST_NAME).write_text(json.dumps(rec, indent=2), encoding="utf-8")
