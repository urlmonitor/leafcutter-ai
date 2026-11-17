"""
MODULE: test_tq_500g_1_ix_list
GOAL: TQ-500g-1-ix, second scenario: the writer's ``list`` step (the owed names and
    their in-scope files), and its agreement with the write step and the runner.
BUSINESS CONTEXT: Real sandbox repo + real AC store (TQ-9101 owes nine names plus
    two aliases; TQ-9102 declares none) + json.dump replies; CLI only.
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter

import unit_tests.build_orchestration._tq500g1_fixtures as fx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix


def _listed(sb, ids: str = ix.IDS) -> dict:
    proc, out = ix.run_writer(sb, "list", ac_ids=ids)
    assert proc.returncode == 0 and out["error"] is None, (proc.returncode, out)
    return out


def test_list_each_owed_name_once_verbatim_with_its_in_scope_files(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: criterion
    # Catches: a name declared on two test entries listed twice
    # Catches: in-scope files merged across names, so settings.py listed for every name
    sb = ix.build_sandbox(tmp_path)
    out = _listed(sb)
    names = ix.list_names(out)
    assert len(names) == 9 and sorted(names) == sorted(ix.OWED), names
    assert Counter(names)[ix.N1] == 1, "N1 is declared on two entries and must be listed once"
    files = {o["name"]: o["files"] for o in out["owed"]}
    assert files[ix.N7] == ["refresh_config.py", "settings.py"]
    assert [n for n in ix.OWED if files[n] == ["refresh_config.py"]] == [n for n in ix.OWED if n != ix.N7]
    assert list(out) == ["owed", "error"] and all(list(o)[:2] == ["name", "files"] for o in out["owed"])  # TQ-500g-1-x adds "scope" after these


def test_list_omits_aliases_and_test_files(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: discrimination
    # Catches: an alias listed as an owed name
    # Catches: a test's own file listed as in scope
    # Catches: a name spelled differently from the test entries (trimmed or case-folded)
    sb = ix.build_sandbox(tmp_path)
    out = _listed(sb)
    names = ix.list_names(out)
    assert names and [n for n in names if n.strip().casefold() in {ix.ALIAS, ix.UNDONE}] == [], names
    assert set(names) == set(ix.OWED), "every listed name is spelled exactly as a test entry spells it"
    listed_files = [f for o in out["owed"] for f in o["files"]]
    assert listed_files and ix.TEST_FILE not in listed_files, listed_files
    assert [f for f in listed_files if f.startswith("tests/") or "/test_" in f or f.startswith("test_")] == []


def test_list_requirement_without_wrong_versions_lists_nothing_and_exits_0(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: boundary
    # Catches: a requirement with no declared wrong version treated as an error
    sb = ix.build_sandbox(tmp_path)
    proc, alone = ix.run_writer(sb, "list", ac_ids=ix.AC_ID_2)
    assert proc.returncode == 0, (proc.returncode, alone)
    assert alone == {"owed": [], "error": None}
    both, only_first = _listed(sb, ix.IDS), _listed(sb, ix.AC_ID)
    assert len(only_first["owed"]) == 9, "control: TQ-9101 alone owes nine names"
    assert both == only_first, "TQ-9102 adds no name and no file"


def test_list_writer_and_runner_owed_sets_agree(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: seam
    # Catches: the list step reading the AC store with its own parser that drops an entry the runner keeps
    # Catches: the write step deriving scope from the reply instead of the shared reader
    sb = ix.build_sandbox(tmp_path)
    listed = _listed(sb, ix.AC_ID)
    names = ix.list_names(listed)
    verdict = fx.parse_json(subprocess.run(
        [sys.executable, str(ix.RUNNER), "run", "--ac-ids", ix.AC_ID, "--test-root", str(sb.work),
         "--ac-root", str(sb.ac_root), "--base-ref", "HEAD"],
        cwd=sb.work, capture_output=True, text=True, timeout=420, env=ix._env()))
    held = {r["wrong_version"] for r in verdict["results"]} - {ix.UNDONE}
    assert held and held == set(names), f"runner holds {sorted(held)}, list prints {sorted(names)}"
    try_settings = [ix.prep(n, ("settings.py", "TIMEOUT = 5", "TIMEOUT = 6")) for n in names]
    proc, out = ix.write_default(sb, try_settings, in_scope_files={n: ["settings.py"] for n in names})
    assert proc.returncode == 0 and out["written"] is True, out
    m = ix.load_manifest(sb)
    assert [e["name"] for e in m["entries"]] == names, "manifest names/order differ from the list"
    in_scope = {o["name"] for o in listed["owed"] if "settings.py" in o["files"]}
    assert in_scope == {ix.N7}, "fixture: only N7 has settings.py in scope"
    assert {e["name"] for e in m["entries"] if e["status"] == "prepared"} == in_scope
    for n in set(names) - in_scope:
        ix.assert_refused(m, n, f'settings.py is not in scope for "{n}"')


def test_list_changes_no_file_and_creates_no_work_folder(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: criterion
    sb = ix.build_sandbox(tmp_path)
    before = (fx.git_state(sb.work), fx.tree_digest(sb.work))
    assert "scratch_note.txt" in before[0]["status"], "fixture: the status must not be empty"
    out = _listed(sb)
    assert len(out["owed"]) == 9, "control: the list really ran"
    assert (fx.git_state(sb.work), fx.tree_digest(sb.work)) == before
    assert not (sb.git_dir / "leafcutter" / "work").exists(), "listing created a work folder"


def test_list_cli_end_to_end_prints_owed_json(tmp_path):
    # covers: TQ-500g-1-ix
    # angle: reachability
    # surface_invoked: python scripts/build_orchestration/wrong_version_writer.py list
    sb = ix.build_sandbox(tmp_path)
    proc, out = ix.run_writer(sb, "list")
    assert proc.returncode == 0, proc.stderr
    assert list(out) == ["owed", "error"] and out["error"] is None and len(out["owed"]) == 9, out
    bad_proc, bad = ix.run_writer(sb, "list", ac_root=tmp_path / "no-such-store")
    assert bad_proc.returncode == 1, bad_proc.returncode
    assert list(bad) == ["owed", "error"] and bad["owed"] == [], bad
    assert isinstance(bad["error"], str) and bad["error"].strip(), bad
