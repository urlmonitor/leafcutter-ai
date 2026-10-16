"""
MODULE: tests/ac_store/test_tkt_600a_3_i.py
GOAL: Failing tests for TKT-600a-3-i -- a ticket generated from a record in the
    "no declared files" state keeps the existing doc_links derivation for
    files_touched but labels it "derived, not declared" in the ticket body and in
    the --verify readiness report (INFO, never PASS), never calls a derived path
    "declared", and is not refused.
BUSINESS CONTEXT: KI-ACS-002 -- a check that cannot judge correctness must report
    INFO, not PASS, and report provenance honestly per path.
ARCHITECTURE: Record L is written with yaml.safe_dump (real serializer); the REAL
    scripts/ac_store/generate_ticket_from_ac.py CLI runs by subprocess; the written
    ticket and --verify output are read back. The guard is the real
    templates/hooks/ticket_frontmatter_guard.py.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import yaml

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
GEN_SCRIPT = WORKTREE_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"
GUARD_SCRIPT = WORKTREE_ROOT / "templates" / "hooks" / "ticket_frontmatter_guard.py"

L_ID = "TKTX-600a-3i"
DERIVED = "scripts/build.py"
DESCRIBED = "docs/reference/ac-schema.md"
# Phrases that legitimately NEGATE "declared" (the label itself) -- stripped before
# checking that no derived path is described as declared.
_NEGATED = re.compile(r"(not|rather than|never|un|non)[ -]?declared", re.I)


def _record_l() -> dict:
    return {
        "id": L_ID,
        "title": "No declared files record",
        "component": "test",
        "level": "L2",
        "status": "active",
        "change_target": "code",
        "risk_surface": "internal",
        "work_status": "todo",
        "criteria": "Given a record,\nWhen a ticket is generated,\nThen it is produced.\n",
        "assigned_agent": "python-coder",
        "estimated_complexity": "S",
        "depends_on": [],
        "implemented_by": [],
        "doc_links": [
            {"path": DERIVED, "relationship": "modifies", "status": "exists"},
            {"path": DESCRIBED, "relationship": "describes", "status": "exists"},
        ],
    }


def _run(root: Path, *extra: str) -> subprocess.CompletedProcess:
    ac_dir, tickets = root / "ac", root / "tickets"
    ac_dir.mkdir(parents=True, exist_ok=True)
    tickets.mkdir(parents=True, exist_ok=True)
    record = _record_l()
    assert "declared_files" not in record  # precondition: 'no declared files' state
    with open(ac_dir / f"{L_ID}.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(record, fh, allow_unicode=True)
    cmd = [sys.executable, str(GEN_SCRIPT), "--ac", L_ID, "--ac-root", str(ac_dir),
           "--tickets-root", str(tickets), "--location-kind", "standalone", *extra]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=WORKTREE_ROOT)


def _generate(root: Path) -> tuple[Path, dict, str]:
    res = _run(root)
    assert res.returncode == 0, f"{res.stderr}\n{res.stdout}"
    files = list((root / "tickets").glob(f"*{L_ID}.md"))
    assert len(files) == 1, files
    text = files[0].read_text(encoding="utf-8")
    return files[0], yaml.safe_load(text.split("---", 2)[1]), text


def _body(text: str) -> str:
    return text.split("---", 2)[2]


def test_no_declared_files_record_uses_existing_derivation(tmp_path):
    # covers: TKT-600a-3-i
    # angle: criterion
    """files_touched contains the modifies doc_link and not the describes one."""
    _, fm, _ = _generate(tmp_path)
    assert DERIVED in fm["files_touched"]
    assert DESCRIBED not in fm["files_touched"]


def test_ticket_states_files_derived_not_declared_naming_record(tmp_path):
    # covers: TKT-600a-3-i
    # angle: criterion
    """A body line says the files were derived from documentation links /
    technical requirements rather than declared, and names L."""
    _, _, text = _generate(tmp_path)
    lines = [ln for ln in _body(text).splitlines()
             if L_ID in ln and re.search(r"derived", ln, re.I)
             and re.search(r"doc(umentation)?[ _]links", ln, re.I)
             and re.search(r"(not|rather than)[ -]declared", ln, re.I)]
    assert lines, "no 'derived ... rather than declared' statement naming L in the ticket body"


def test_readiness_report_shows_derived_not_declared_not_pass(tmp_path):
    # covers: TKT-600a-3-i
    # angle: failure
    """--verify: the surface is INFO 'derived, not declared' for L, each derived
    path carries its true source, and no PASS line vouches for the surface."""
    out = (lambda r: r.stdout + r.stderr)(_run(tmp_path, "--verify"))
    info = [ln for ln in out.splitlines() if re.search(r"derived, not declared", ln, re.I)
            and "[INFO]" in ln and L_ID in ln]
    assert info, f"no '[INFO] ... derived, not declared' line naming {L_ID}; output:\n{out}"
    path_lines = [ln for ln in out.splitlines() if DERIVED in ln and "doc_links" in ln
                  and "files_touched:" not in ln and not ln.lstrip().startswith("- ")]
    assert path_lines, "each derived path must carry its true source (doc_links)"
    for ln in out.splitlines():
        if "[PASS]" in ln:
            assert "files_touched" not in ln and "path(s)" not in ln and "derived" not in ln, ln


def test_no_derived_path_described_as_declared(tmp_path):
    # covers: TKT-600a-3-i
    # angle: discrimination
    """No ticket-body or report line naming a derived path calls it declared.
    Wrong version caught: simply reusing the TKT-600a-3 declared-record wording."""
    _, _, text = _generate(tmp_path)
    ticket = _body(text)
    res = _run(tmp_path, "--verify")
    report = res.stdout + res.stderr
    for blob in (ticket, report):
        for ln in blob.splitlines():
            if DERIVED in ln:
                assert not re.search(r"declared", _NEGATED.sub("", ln), re.I), ln
    # control: the honest label exists at all (an empty implementation cannot pass)
    assert re.search(r"derived, not declared", report, re.I)


def test_generation_not_refused_for_no_declared_files_record(tmp_path):
    # covers: TKT-600a-3-i
    # angle: boundary
    """Exit 0, ticket written, passes the real ticket_frontmatter_guard."""
    path, _, text = _generate(tmp_path)
    spec = importlib.util.spec_from_file_location("guard_under_test_600a3i", GUARD_SCRIPT)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    fm = guard.parse_frontmatter(text)
    assert fm["files_touched"] == [DERIVED]
    assert guard.validate(fm, path) == []
    # label present, so generation succeeded WITH the new honest marking
    assert re.search(r"derived, not declared|rather than declared", _body(text), re.I)
