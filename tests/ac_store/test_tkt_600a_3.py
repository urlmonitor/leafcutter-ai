"""
MODULE: tests/ac_store/test_tkt_600a_3.py
GOAL: Failing tests for TKT-600a-3 -- a ticket generated from a record that
    declares its files (``declared_files``, ACD-1600c-4) touches exactly those
    files in declared order, marks to_be_created paths in the ticket body,
    reads the list only through scripts/ac_store/declared_files.py, and the
    --verify readiness report names the declared-files list as the source of
    each path.
BUSINESS CONTEXT: KI-ACS-002 -- files_touched used to be guessed from
    doc_links and prose. Fixture R below is the AC's own scenario.
ARCHITECTURE: The fixture AC is written with yaml.safe_dump (real serializer),
    the REAL generate_ticket_from_ac.py CLI is run by subprocess, and the
    written ticket / --verify output is read back. The guard is the real
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

_AC_STORE_DIR = str(WORKTREE_ROOT / "scripts" / "ac_store")
if _AC_STORE_DIR not in sys.path:
    sys.path.insert(0, _AC_STORE_DIR)

EXISTING = "scripts/ac_store/scan_ac_store.py"
CREATED = "unit_tests/ac_store/test_hold_reasons.py"
EXCLUDED = [
    "templates/agents/it-po.md",
    "docs/reference/ac-schema.md",
    "scripts/goal_to_epic.py",
]
R_ID = "TKTX-600a-3"
_CREATE_MARKER = re.compile(r"to[ _-]be[ _-]created|creates?\b|will be created", re.I)


def _record_r() -> dict:
    return {
        "id": R_ID,
        "title": "Declared files record",
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
        "declared_files": [
            {"path": EXISTING, "state": "existing"},
            {"path": CREATED, "state": "to_be_created"},
        ],
        "doc_links": [
            {"path": "templates/agents/it-po.md", "relationship": "modifies", "status": "exists"},
            {"path": "docs/reference/ac-schema.md", "relationship": "describes", "status": "exists"},
        ],
        "it_requirements": ["Modify scripts/goal_to_epic.py to emit the new field."],
    }


def _write_r(ac_dir: Path, record: dict | None = None) -> None:
    ac_dir.mkdir(parents=True, exist_ok=True)
    with open(ac_dir / f"{R_ID}.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(record or _record_r(), fh, allow_unicode=True)


def _run(ac_root: Path, tickets_root: Path, *extra: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(GEN_SCRIPT), "--ac", R_ID, "--ac-root", str(ac_root),
           "--tickets-root", str(tickets_root), "--location-kind", "standalone", *extra]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=WORKTREE_ROOT)


def _generate(root: Path, record: dict | None = None) -> tuple[Path, dict, str]:
    ac_dir, tickets = root / "ac", root / "tickets"
    tickets.mkdir(parents=True)
    _write_r(ac_dir, record)
    res = _run(ac_dir, tickets)
    assert res.returncode == 0, f"{res.stderr}\n{res.stdout}"
    files = list(tickets.glob(f"*{R_ID}.md"))
    assert len(files) == 1, files
    text = files[0].read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---", 2)[1])
    return files[0], fm, text


def _load_guard():
    spec = importlib.util.spec_from_file_location("guard_under_test_600a3", GUARD_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_declared_record_files_touched_is_declared_list_in_order(tmp_path):
    # covers: TKT-600a-3
    # angle: criterion
    """files_touched is exactly [scan_ac_store.py, test_hold_reasons.py] in
    declared order; the to_be_created path is emitted although absent."""
    _, fm, _ = _generate(tmp_path)
    assert fm["files_touched"] == [EXISTING, CREATED]


def test_doc_links_and_prose_paths_excluded_for_declared_record(tmp_path):
    # covers: TKT-600a-3
    # angle: failure
    """The modifies doc_link, the describes doc_link and the prose-named
    (on-disk) goal_to_epic.py are not on files_touched. Control: the declared
    paths ARE present, so an empty list cannot pass."""
    _, fm, _ = _generate(tmp_path)
    assert len(fm["files_touched"]) == 2
    for path in EXCLUDED:
        assert (WORKTREE_ROOT / path).exists(), f"fixture path vanished: {path}"
        assert path not in fm["files_touched"]
    assert EXISTING in fm["files_touched"] and CREATED in fm["files_touched"]


def test_ticket_marks_to_be_created_file(tmp_path):
    # covers: TKT-600a-3
    # angle: criterion
    """The ticket body states test_hold_reasons.py is created by the work and
    does not so mark scan_ac_store.py."""
    _, _, text = _generate(tmp_path)
    body = text.split("---", 2)[2]
    created_lines = [ln for ln in body.splitlines() if CREATED in ln]
    existing_lines = [ln for ln in body.splitlines() if EXISTING in ln]
    assert any(_CREATE_MARKER.search(ln) for ln in created_lines), created_lines
    assert existing_lines, "scan_ac_store.py must be listed in the body too"
    assert not any(_CREATE_MARKER.search(ln) for ln in existing_lines), existing_lines


def test_files_touched_equals_store_declared_answer(tmp_path):
    # covers: TKT-600a-3
    # angle: seam
    """Pipe the seam's real answer (declared_files.get_declared_files over the
    on-disk record) against the generated ticket's files_touched. A reversed
    declaration must yield the reversed list (catches sort/reorder)."""
    import declared_files  # real seam module

    _, fm, _ = _generate(tmp_path / "a")
    record = yaml.safe_load((tmp_path / "a" / "ac" / f"{R_ID}.yaml").read_text(encoding="utf-8"))
    answer = declared_files.get_declared_files(record)
    assert not isinstance(answer, declared_files.NoDeclaredFiles)
    assert fm["files_touched"] == [e["path"] for e in answer]

    record["declared_files"].reverse()
    _, fm2, _ = _generate(tmp_path / "b", record)
    assert fm2["files_touched"] == [CREATED, EXISTING]


def test_readiness_report_names_declared_list_as_source_per_path(tmp_path):
    # covers: TKT-600a-3
    # angle: criterion
    """--verify prints one provenance line per path naming the declared-files
    list, and no count-only 'from doc_links' PASS line."""
    ac_dir, tickets = tmp_path / "ac", tmp_path / "tickets"
    tickets.mkdir()
    _write_r(ac_dir)
    res = _run(ac_dir, tickets, "--verify")
    out = res.stdout + res.stderr
    src = re.compile(r"declared[ _-]files", re.I)
    for path in (EXISTING, CREATED):
        lines = [ln for ln in out.splitlines() if path in ln and src.search(ln)]
        assert len(lines) == 1, f"expected one provenance line for {path}; output:\n{out}"
    assert "path(s) from doc_links" not in out


def test_generated_declared_ticket_passes_frontmatter_guard(tmp_path):
    # covers: TKT-600a-3
    # angle: boundary
    """The real ticket_frontmatter_guard reports no violation, and the
    to_be_created (absent-on-disk) path is still emitted as a flat string."""
    path, _, text = _generate(tmp_path)
    guard = _load_guard()
    fm = guard.parse_frontmatter(text)
    assert fm["files_touched"] == [EXISTING, CREATED]
    assert all(isinstance(e, str) for e in fm["files_touched"])
    assert guard.validate(fm, path) == []


def test_tkt_600a_3_reachable_from_entry_point(tmp_path):
    # covers: TKT-600a-3
    # angle: reachability
    """Entry point: CLI script scripts/ac_store/generate_ticket_from_ac.py run
    as a subprocess with real argv; the declared list in the written ticket
    and determinism on regeneration are asserted from its output."""
    _, fm1, text1 = _generate(tmp_path / "a")
    _, fm2, text2 = _generate(tmp_path / "b")
    assert fm1["files_touched"] == [EXISTING, CREATED]
    assert fm1["files_touched"] == fm2["files_touched"]

    def surface(t: str) -> list[str]:
        return [ln for ln in t.split("---", 2)[2].splitlines() if CREATED in ln or EXISTING in ln]

    assert surface(text1) == surface(text2)
