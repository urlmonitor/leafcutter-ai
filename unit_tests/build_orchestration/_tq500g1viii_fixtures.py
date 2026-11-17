"""
MODULE: unit_tests/build_orchestration/_tq500g1viii_fixtures.py
GOAL: Shared helpers for the TQ-500g-1-viii record tests: running the three gate CLIs with ``--record <ticket-key>``
    (heavy_lane_gate, the runner's run step, the finish wrapper) and reading the records they leave.
BUSINESS CONTEXT: The records are the hook's only input, so they must be written by the gate CLIs themselves, on
    every outcome. Every run is a subprocess on the REAL sandboxes of the TQ-500g-1 family (a real git repo, a real AC
    store written with yaml.safe_dump, replies written with json.dumps), so nothing a CLI prints is typed by hand.
    Today none of the three CLIs knows ``--record`` (argparse exits 2 with no JSON), so each run fails the shared
    parse helper's assertion, never an import.
ARCHITECTURE: Not a test file (leading underscore). The hook and the marker helpers come from
    unit_tests/commit_guardian/_tq500g1viii_fixtures.py (one definition of how a hook is driven).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1v_gate_fixtures as g
import unit_tests.build_orchestration._tq500g1x_fixtures as x
import unit_tests.commit_guardian._tq500g1viii_fixtures as hk

HL_AC = "TQ-FIX-8-SEAM"
RB_NA = "red-baseline reader not applicable: no source requirement"


def gate_dir(work: Path) -> Path:
    return hk.git_dir(work) / "leafcutter" / "gate-verdicts"


def read_record(work: Path, key: str, gate: str) -> dict | None:
    """The record the CLI left, or None when it left none (a record that does not parse is an AssertionError)."""
    path = gate_dir(work) / key / f"{gate}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        msg = f"{path} is not parseable JSON: {exc}"
        raise AssertionError(msg) from exc


def listing(work: Path) -> set[str]:
    """Every file under gate-verdicts (relative, POSIX), to prove 'writes nothing'."""
    root = gate_dir(work)
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} if root.is_dir() else set()


def heavy_sandbox(root: Path) -> tuple[Path, Path]:
    """A real clone whose AC TQ-FIX-8-SEAM has two newly-added tests that go red by assertion/absence (a proper red)."""
    work, _ = gitfx.make_worktree(root)
    ac_root = work / "docs" / "acceptance-criteria"
    gitfx.write_ac_yaml(ac_root, HL_AC, gitfx.t1_t2_t3_test_spec())
    gitfx.write_t1_t2_t3_test_files(work / "tests", HL_AC, include={gitfx.T2_NAME, gitfx.T3_NAME})
    return work, ac_root


def heavy(work: Path, ac_root: Path, ids: str | None, record: str | None = None):
    """Run ``heavy_lane_gate`` (with ``--record`` when given); return ``(proc, parsed JSON)``."""
    cmd = [sys.executable, str(gitfx.GATE_SCRIPT), "heavy_lane_gate", "--test-root", str(work), "--ac-root", str(ac_root)]
    cmd += ["--source-ac", ids] if ids else []
    cmd += ["--record", record] if record is not None else []
    proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=300, env=hk.env(source_tree=False))
    return proc, ix.parse_one_json(proc, "heavy_lane_gate")


def runner(sb: Any, manifest: Path, *, record: str | None = None, ids: bool = True):
    """Run the runner's ``run`` step (``--record`` when given; no ``--ac-ids`` when *ids* is False)."""
    cmd = [sys.executable, str(ix.RUNNER), "run", "--test-root", str(sb.work), "--ac-root", str(sb.ac_root),
           "--base-ref", sb.base_sha, "--alterations", str(manifest)]
    cmd += ["--ac-ids", ix.AC_ID] if ids else []
    cmd += ["--record", record] if record is not None else []
    proc = subprocess.run(cmd, cwd=sb.work, capture_output=True, text=True, timeout=600, env=x.env())
    return proc, ix.parse_one_json(proc, "runner")


def finish(sb: x.XSandbox, stdin: str, *, record: str | None = None, ac_ids: str | None = ix.AC_ID, work_key: str = ix.WORK_KEY):
    """Run the finish wrapper (``--record`` when given); return ``(proc, parsed JSON)``."""
    cmd = g.finish_cmd(sb, ac_ids=ac_ids, work_key=work_key) + (["--record", record] if record is not None else [])
    raw = subprocess.run(cmd, cwd=sb.work, input=stdin.encode("utf-8"), capture_output=True, timeout=900, env=x.env())
    proc = subprocess.CompletedProcess(raw.args, raw.returncode, raw.stdout.decode("utf-8", "replace"), raw.stderr.decode("utf-8", "replace"))
    return proc, ix.parse_one_json(proc, "finish")


def survivor_reply() -> str:
    """A complete reply in which wrong version N1 is a no-op rewrite, so the covering tests pass under it (a survivor)."""
    entries = g.full_entries()
    entries[0] = ix.prep(x.N1, ("refresh_config.py", x.COND, x.COND + " or False"))
    return g.reply_text(entries)
