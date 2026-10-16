"""
MODULE: test_acd_1600c_1_i_reachability
GOAL: Reachability proof for ACD-1600c-1-i: the real scan_ac_store.py CLI, run as a
    subprocess with --enforce-impl-readiness, holds the real ACs ACD-300c-3 and
    TQ-200a-1 (no declared files) out of the ready/dispatch set.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCAN = _REPO_ROOT / "scripts" / "ac_store" / "scan_ac_store.py"
_STORE = _REPO_ROOT / "docs" / "acceptance-criteria"
_IDS = ("ACD-300c-3", "TQ-200a-1")


def _real_record(ac_id: str) -> dict:
    hits = list(_STORE.rglob(f"{ac_id}.yaml"))
    assert len(hits) == 1, hits
    rec = yaml.safe_load(hits[0].read_text(encoding="utf-8"))
    assert "declared_files" not in rec, f"{ac_id} now declares files; fixture is stale"
    rec["readiness"] = "approved"
    rec["depends_on"] = []
    return rec


def test_acd_1600c_1_i_cli_holds_back_records_without_file_targets(tmp_path):
    """ACD-1600c-1-i: scan CLI (subprocess) holds back records with no file targets."""
    # covers: ACD-1600c-1-i
    # angle: reachability
    for ac_id in _IDS:
        (tmp_path / f"{ac_id}.yaml").write_text(yaml.safe_dump(_real_record(ac_id)), encoding="utf-8")
    cmd = [sys.executable, str(_SCAN), "--json", "--ac-root", str(tmp_path), "--enforce-impl-readiness"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(_REPO_ROOT))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    flagged = {r["ac_id"]: r for r in out["not_implementation_ready"]}
    assert set(flagged) == set(_IDS)
    for ac_id in _IDS:
        assert "missing file targets" in flagged[ac_id]["reasons"]
        assert flagged[ac_id]["held_back"] is True
    assert out["ready"] == []
