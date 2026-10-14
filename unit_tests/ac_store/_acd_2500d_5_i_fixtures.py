"""
MODULE: unit_tests/ac_store/_acd_2500d_5_i_fixtures.py
GOAL: Shared store/tree builders and the real-CLI runner for the ACD-2500d-5-i tests
    (test_acd_2500d_5_i.py and unit_tests/ac_driven_dev/rule_check/test_acd_2500d_5_i_deploy_declaration.py).
    Not collected: no test functions.
BUSINESS CONTEXT: ACD-2500d-5-i (ticket 28): scripts/ac_store/design_prepass.py is the deterministic
    pre-pass that tells the code-aware agent the mechanical file facts (declared file states, test
    directory existence, reference file type and area). The AC's three-requirement batch R1/R2/R3 is
    built here once.
ARCHITECTURE: Records are written with the REAL serializer (yaml.safe_dump via _rule_check_fixtures'
    Store) into a tmp consumer-style repo; the tree the pre-pass judges (scripts/a.py, the test
    directory, the reference files) is created under the same tmp root, which is also passed as
    --repo-root. The pre-pass is always run as a subprocess (its production entry point) and its
    stdout is kept as BYTES, so byte-identity is judged on the real output.

PUBLIC API:
    batch_store(tmp_path) -> Store            the R1/R2/R3 batch of the AC (ids R1..R3 below)
    run_prepass(store, ids, *extra, cwd=None) -> PrepassRun    (.exit_code .stdout(bytes) .stderr .report)
    dirs_of(report_record) -> {path without trailing slash: exists}
    declared_states(report_record) -> {path: state}
    tree_bytes(root) -> {relative POSIX path: bytes}   (read-only proof)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import REPO_ROOT, Store, make_store, valid_record  # noqa: E402

PREPASS_SCRIPT = REPO_ROOT / "scripts" / "ac_store" / "design_prepass.py"
R1, R2, R3 = "ZZP-1", "ZZP-2", "ZZP-3"
BATCH_IDS = [R1, R2, R3]
MISSING = "scripts/missing.py"
SIBLING = "scripts/ac_store/sibling.py"
NEW_FILE = "scripts/ac_store/new_thing.py"
DOC_REFERENCE = "docs/reference/notes.md"


class PrepassRun(NamedTuple):
    """One real invocation of the pre-pass CLI."""

    exit_code: int
    stdout: bytes
    stderr: str
    report: dict | None


def reference_requirements(reference: str) -> dict:
    """The structured (object-form) it_requirements naming `reference` as reference_file_path."""
    return {
        "config_schema_fragment": {"type": "string"},
        "reference_file_path": reference,
        "n_location_rule": "1",
        "required_skills": ["python-coder"],
        "post_write_commands": [],
    }


def spec_entry(name: str, target_dir: str) -> dict:
    """A minimal test_spec entry (the legacy shape: name and target_dir)."""
    return {"name": name, "target_dir": target_dir, "framework": "pytest", "type": "unit"}


def r1_record() -> dict:
    """R1: declares the existing scripts/a.py, names an existing and a missing test directory."""
    return valid_record(
        R1,
        declared_files=[{"path": "scripts/a.py", "state": "existing"}],
        test_spec=[spec_entry("test_a", "unit_tests/ac_store/"), spec_entry("test_b", "unit_tests/missing_dir/")],
    )


def r2_record() -> dict:
    """R2: a to-be-created file plus a same-type, same-area reference file."""
    return valid_record(
        R2,
        declared_files=[{"path": NEW_FILE, "state": "to_be_created"}],
        it_requirements=reference_requirements(SIBLING),
    )


def r3_record() -> dict:
    """R3: scripts/missing.py (neither present nor to-be-created) and a different-type reference."""
    return valid_record(
        R3,
        declared_files=[{"path": MISSING, "state": "existing"}],
        it_requirements=reference_requirements(DOC_REFERENCE),
    )


def write_tree(root: Path, files: dict[str, str]) -> None:
    """Create `files` ({relative POSIX path: text}) under `root`, LF line endings."""
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)


def batch_store(tmp_path: Path, extra_records: list[dict] | None = None) -> Store:
    """The AC's batch: R1, R2, R3 (plus `extra_records`) over a tree holding scripts/a.py,
    unit_tests/ac_store/, the sibling reference and a markdown reference; scripts/missing.py
    and unit_tests/missing_dir/ are deliberately absent."""
    store = make_store(tmp_path, [r1_record(), r2_record(), r3_record(), *(extra_records or [])])
    write_tree(
        store.repo_root,
        {
            "scripts/a.py": "A = 1\n",
            SIBLING: "SIBLING = 1\n",
            DOC_REFERENCE: "# notes\n",
            "unit_tests/ac_store/test_existing.py": "def test_x():\n    pass\n",
        },
    )
    return store


def run_prepass(store: Store, ids: list[str], *extra: str, cwd: Path | None = None) -> PrepassRun:
    """`python scripts/ac_store/design_prepass.py --ids A,B --store-root .. --repo-root ..` as a subprocess.

    stdout is kept as bytes; `report` is the parsed JSON document, or None when stdout is empty.
    """
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    argv = [
        sys.executable, str(PREPASS_SCRIPT), "--ids", ",".join(ids),
        "--store-root", str(store.repo_root / "docs" / "acceptance-criteria"),
        "--repo-root", str(store.repo_root), *extra,
    ]
    proc = subprocess.run(argv, cwd=str(cwd or store.repo_root), capture_output=True, timeout=60, env=env)
    report: Any = json.loads(proc.stdout) if proc.stdout.strip() else None
    return PrepassRun(proc.returncode, proc.stdout, proc.stderr.decode("utf-8", "replace"), report)


def record_of(report: dict, record_id: str) -> dict:
    """The report's entry for `record_id` (fails loudly, naming the ids present)."""
    found = [item for item in report["records"] if item["id"] == record_id]
    assert len(found) == 1, f"expected one report entry for {record_id}, got ids {[r['id'] for r in report['records']]}"
    return found[0]


def declared_states(report_record: dict) -> dict[str, str]:
    """{declared path: state} of one report entry."""
    return {item["path"]: item["state"] for item in report_record["declared_files"]}


def dirs_of(report_record: dict) -> dict[str, bool]:
    """{test directory without a trailing slash: exists} of one report entry."""
    return {item["path"].rstrip("/"): item["exists"] for item in report_record["test_dirs"]}


def tree_bytes(root: Path) -> dict[str, bytes]:
    """{relative POSIX path: bytes} for every file under `root` (read-only proof)."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(Path(root).rglob("*")) if p.is_file()}
