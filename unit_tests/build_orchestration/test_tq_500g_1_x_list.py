"""
MODULE: test_tq_500g_1_x_list
GOAL: TQ-500g-1-x, the writer's ``list`` step: a name whose test entries declare no
    in-scope file takes the non-test files the work changed relative to --base-ref.
BUSINESS CONTEXT: Real git sandbox (TQ-9101: refresh_config.py changed in a commit,
    retry_policy.py untracked, a test file changed, legacy_refresh.py deleted, settings.py
    untouched) + a real AC store (yaml.safe_dump); the CLI is driven as a subprocess.
"""

from __future__ import annotations

import subprocess
import sys

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1x_fixtures as x

DERIVED = ["refresh_config.py", "retry_policy.py"]


def test_list_declared_name_keeps_exactly_its_declared_files(tmp_path):
    # covers: TQ-500g-1-x
    # angle: criterion
    # Catches: the derived changed files merged into a declared scope
    # Catches: a declared scope narrowed to the files the work changed
    item = x.listed(x.build(tmp_path))[x.N1]
    assert item["files"] == ["settings.py", "refresh_config.py"], item
    assert item["scope"] == "declared", item
    assert "retry_policy.py" not in item["files"]


def test_list_name_declared_on_any_entry_derives_nothing(tmp_path):
    # covers: TQ-500g-1-x
    # angle: boundary
    # Catches: scope decided per entry, so the undeclared entry adds the changed files
    item = x.listed(x.build(tmp_path))[x.N3]
    assert item["files"] == ["settings.py"], item
    assert item["scope"] == "declared", item


def test_list_unscoped_names_take_the_changed_non_test_files(tmp_path):
    # covers: TQ-500g-1-x
    # angle: criterion
    # Catches: a deleted file listed in the derived scope
    # Catches: a test file the work changed listed in the derived scope
    # Catches: every non-test file of the repository used as the derived scope
    out = x.listed(x.build(tmp_path))
    for name in (x.N2, x.N9):
        assert out[name]["files"] == DERIVED, (name, out[name])
        assert out[name]["scope"] == "derived", (name, out[name])
        for left_out in ("settings.py", x.TEST_FILE, "legacy_refresh.py"):
            assert left_out not in out[name]["files"], (name, left_out)
    assert out[x.N1]["scope"] == "declared", "control: a declared name stays declared"


def test_derived_scope_counts_committed_uncommitted_and_untracked_changes(tmp_path):
    # covers: TQ-500g-1-x
    # angle: boundary
    # Catches: only committed changes counted (base ref to HEAD instead of the working tree)
    # Catches: an untracked new file left out of the derived scope
    # Catches: a git-ignored file listed in the derived scope
    sb = x.build(tmp_path)
    x._wb(sb.work / "helpers.py", x.HELPERS + "VALUE = 2\n")  # modified, never committed
    x._wb(sb.work / "scratch.ignored", "ignored new file\n")  # new, matches .gitignore
    files = x.listed(sb)[x.N2]["files"]
    assert files == ["helpers.py", "refresh_config.py", "retry_policy.py"], files


def test_derived_scope_rename_counts_new_path_only_and_excludes_the_ac_store(tmp_path):
    # covers: TQ-500g-1-x
    # angle: boundary
    # Catches: a renamed file's old path listed in the derived scope
    # Catches: AC store files listed as in scope for a wrong version
    sb = x.build(tmp_path, ac_inside=True)
    gitfx.run_git(["mv", "old_name.py", "new_name.py"], cwd=sb.work)
    x.amend_ac_store(sb)
    out = x.listed(sb)
    for name in (x.N2, x.N9):
        assert out[name]["files"] == ["new_name.py", "refresh_config.py", "retry_policy.py"], (name, out[name])
        assert out[name]["scope"] == "derived"


def test_list_marks_each_name_declared_or_derived_additively(tmp_path):
    # covers: TQ-500g-1-x
    # angle: criterion
    # Catches: every name marked declared whatever its entries carry
    # Catches: the scope marker replacing or renaming the name or files key
    proc, out = x.run_list(x.build(tmp_path))
    assert proc.returncode == 0 and list(out) == ["owed", "error"], (proc.returncode, list(out))
    assert all(list(o) == ["name", "files", "scope"] for o in out["owed"]), out["owed"]
    scopes = {o["name"]: o["scope"] for o in out["owed"]}
    assert scopes == {x.N1: "declared", x.N3: "declared", x.N2: "derived", x.N9: "derived"}, scopes


def test_list_changes_no_file_index_or_stash(tmp_path):
    # covers: TQ-500g-1-x
    # angle: criterion
    # Catches: untracked files made visible to the diff with git add or intent-to-add
    sb = x.build(tmp_path)
    before = x.snapshot(sb)
    assert "retry_policy.py" in before["status"], "fixture: retry_policy.py is untracked"
    out = x.listed(sb)
    assert out[x.N2]["files"] == DERIVED, "the list must really have run the derived scope"
    assert x.snapshot(sb) == before
    assert not (sb.git_dir / "leafcutter" / "work").exists(), "listing created a work folder"


def test_only_a_test_file_changed_gives_unscoped_names_an_empty_derived_scope(tmp_path):
    # covers: TQ-500g-1-x
    # angle: boundary
    # Catches: an empty derived scope widened to the whole repository
    # Catches: a name with an empty derived scope dropped from the owed list
    out = x.listed(x.build(tmp_path, shape="test_only"))
    assert sorted(out) == sorted(x.OWED), list(out)
    for name in (x.N2, x.N9):
        assert (out[name]["files"], out[name]["scope"]) == ([], "derived"), (name, out[name])
    assert (out[x.N1]["files"], out[x.N1]["scope"]) == (x.SETTINGS_FILES, "declared")


def test_list_cli_takes_base_ref_and_defaults_to_head(tmp_path):
    # covers: TQ-500g-1-x
    # angle: reachability
    sb = x.build(tmp_path)
    cmd_head = [sys.executable, str(ix.WRITER), "list", "--ac-ids", x.AC_ID, "--ac-root", str(sb.ac_root),
                "--test-root", str(sb.work)]
    proc = subprocess.run(cmd_head, cwd=sb.work, capture_output=True, text=True, timeout=120, env=x.env())
    out = ix.parse_one_json(proc)
    assert proc.returncode == 0 and list(out) == ["owed", "error"] and out["error"] is None
    assert all("scope" in o for o in out["owed"]), out
    assert {o["name"]: o["files"] for o in out["owed"]}[x.N2] == ["retry_policy.py"], "default is HEAD"
    given = x.listed(sb)  # --base-ref <base commit>
    assert given[x.N2]["files"] == DERIVED, "the ref given is the one used"
    empty = x.listed(sb, base_ref="")
    assert empty[x.N2]["files"] == ["retry_policy.py"], "an empty --base-ref means HEAD"


def test_declared_only_list_matches_the_ix_contract(tmp_path):
    # covers: TQ-500g-1-x
    # angle: seam
    # Catches: the list failing when every name is declared and the base ref cannot be resolved
    sb = ix.build_sandbox(tmp_path)
    proc, out = ix.run_writer(sb, "list")  # no --base-ref
    assert proc.returncode == 0 and out["error"] is None, (proc.returncode, out)
    assert sorted(ix.list_names(out)) == sorted(ix.OWED)
    assert all(o.get("scope") == "declared" for o in out["owed"]), out["owed"]
    files = {o["name"]: o["files"] for o in out["owed"]}
    assert files[ix.N7] == ["refresh_config.py", "settings.py"]
    assert all(files[n] == ["refresh_config.py"] for n in ix.OWED if n != ix.N7)
    unresolved = x.listed(sb, base_ref=x.NO_REF, ac_ids=ix.IDS)
    assert sorted(unresolved) == sorted(ix.OWED), "declared-only needs no resolvable base ref"
