"""
MODULE: test_tkt_600a_3_i_reachability
GOAL: Reachability proof for TKT-600a-3-i: the real generate_ticket_from_ac.py CLI,
    run as a subprocess on a tmp_path store holding a legacy (no declared_files)
    record, labels the derivation "derived, not declared". Writes only to tmp_path.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
GEN_SCRIPT = WORKTREE_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"
L_ID = "TKTX-600a3ir"


def test_tkt_600a_3_i_cli_labels_legacy_derivation_derived_not_declared(tmp_path):
    """TKT-600a-3-i: generator CLI (subprocess) labels a legacy record's files as derived."""
    # covers: TKT-600a-3-i
    # angle: reachability
    ac_dir, tickets = tmp_path / "ac", tmp_path / "tickets"
    ac_dir.mkdir()
    tickets.mkdir()
    record = {
        "id": L_ID, "title": "Legacy no declared files", "component": "test", "level": "L2",
        "status": "active", "change_target": "code", "risk_surface": "internal",
        "work_status": "todo",
        "criteria": "Given a record,\nWhen a ticket is generated,\nThen it is produced.\n",
        "assigned_agent": "python-coder", "estimated_complexity": "S",
        "depends_on": [], "implemented_by": [],
        "doc_links": [
            {"path": "scripts/build.py", "relationship": "modifies", "status": "exists"},
            {"path": "docs/reference/ac-schema.md", "relationship": "describes", "status": "exists"},
        ],
    }
    assert "declared_files" not in record
    (ac_dir / f"{L_ID}.yaml").write_text(yaml.safe_dump(record), encoding="utf-8")
    cmd = [sys.executable, str(GEN_SCRIPT), "--ac", L_ID, "--ac-root", str(ac_dir),
           "--tickets-root", str(tickets), "--location-kind", "standalone"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=WORKTREE_ROOT)
    assert proc.returncode == 0, f"{proc.stderr}\n{proc.stdout}"
    files = list(tickets.glob(f"*{L_ID}.md"))
    assert len(files) == 1, files
    text = files[0].read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---", 2)[1])
    assert "scripts/build.py" in fm["files_touched"]
    assert "docs/reference/ac-schema.md" not in fm["files_touched"]
    assert f"derived from documentation links and technical requirements rather than declared (record {L_ID})" in text
    assert re.search(r"^- `scripts/build\.py` — derived from ", text, re.M)
