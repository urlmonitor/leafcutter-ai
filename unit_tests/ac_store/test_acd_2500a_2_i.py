"""
MODULE: test_acd_2500a_2_i
GOAL: Red-first specification of ACD-2500a-2-i: a missing parent back-link is
    appended to the parent's covered_by exactly once and nothing else in the
    parent changes (scripts/ac_store/requirement_rule_check.py, family
    "parent-to-child back-links", ticket 10).
BUSINESS CONTEXT: The business analyst adds a child but forgets to list it in the
    parent. There is exactly one correct repair, so the check makes it; a child
    whose parent record does not exist is a decision for a person, never a record
    the check invents.
ARCHITECTURE: Every test runs the real check through `main(argv)` or a
    subprocess over records written by yaml.safe_dump (see _rule_check_fixtures).
    "Byte-identical" claims compare raw bytes read with the bytes API, so CRLF and
    hand-written comments in a record prove the writer is field-targeted and not a
    load/dump rewrite.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rule_check_fixtures import (  # noqa: E402
    FAMILY_BACKLINKS,
    # The protected-fields family's 'not evaluated' entries (ACD-2500a-2-vi / -vii)
    # are not this file's subject; every other finding is kept.
    check_store_other_families as check_store,
    cli_argv,
    finding_text,
    findings_for,
    hierarchy,
    make_store,
    run_cli_subprocess_other_families as run_cli_subprocess,
    snapshot_tree,
    valid_record,
)

_PARENT = "ACD-9990a"
_KIDS = ("ACD-9990a-1", "ACD-9990a-2", "ACD-9990a-3")
_ADDED = "ACD-9990a-3"


def _missing_backlink_records() -> list[dict]:
    """L0 + L1 + three children; the L1 lists only the first two children."""
    return hierarchy("ACD-9990", 3, l1={"covered_by": [_KIDS[0], _KIDS[1]]})


def _strip_key_block(text: str, key: str) -> str:
    """`text` without the column-0 `key:` line and the lines that belong to its value
    (indented lines or `- ` items): style-agnostic, so flow and block lists both go."""
    kept: list[str] = []
    skipping = False
    for line in re.findall(r"[^\n]*\n|[^\n]+", text):
        if line.startswith(f"{key}:"):
            skipping = True
            continue
        if skipping and (line[:1] in (" ", "\t") or re.match(r"-[ \r\n]", line)):
            continue
        skipping = False
        kept.append(line)
    return "".join(kept)


def test_missing_backlink_appended_in_order(tmp_path):
    # covers: ACD-2500a-2-i
    # angle: criterion
    """The parent's covered_by reads [a-1, a-2, a-3]: existing order kept, the
    missing child appended last, and the run passes."""
    store = make_store(tmp_path, _missing_backlink_records())

    exit_code, report = check_store(store)

    assert store.read(_PARENT)["covered_by"] == list(_KIDS)
    assert report["verdict"] == "passed", report["findings"]
    assert exit_code == 0


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_parent_other_fields_byte_identical(tmp_path, newline):
    # covers: ACD-2500a-2-i
    # angle: real_artifact
    """Every byte of the parent outside the covered_by value is unchanged. The parent
    is serialized by yaml.safe_dump, then given a leading hand-written comment and
    (in the crlf variant) CRLF line endings -- a whole-file load/dump rewrite loses
    the comment and the endings, a field-targeted edit keeps both."""
    store = make_store(tmp_path, _missing_backlink_records())
    parent_path = store.path(_PARENT)
    original = parent_path.read_bytes().decode("utf-8")
    original = "# hand-written note kept verbatim\n" + original
    original = original.replace("\n", newline)
    parent_path.write_bytes(original.encode("utf-8"))
    siblings_before = {
        name: data for name, data in snapshot_tree(store.folder).items()
        if name != parent_path.name
    }

    check_store(store)

    after = parent_path.read_bytes().decode("utf-8")
    assert after != original  # the back-link was written ...
    assert _strip_key_block(after, "covered_by") == _strip_key_block(original, "covered_by")
    assert after.count("covered_by:") == original.count("covered_by:") == 1
    assert _ADDED in after
    if newline == "\r\n":  # ... and no bare LF crept in
        assert "\n" not in after.replace("\r\n", "")
    siblings_after = {
        name: data for name, data in snapshot_tree(store.folder).items()
        if name != parent_path.name
    }
    assert siblings_after == siblings_before  # no other record was touched


def test_backlink_fix_reported_once_naming_parent_and_id(tmp_path):
    # covers: ACD-2500a-2-i
    # angle: criterion
    """One 'fixed' entry names the parent's file and the id added; it is the only
    finding of the run."""
    store = make_store(tmp_path, _missing_backlink_records())

    _, report = check_store(store)

    assert len(report["findings"]) == 1, report["findings"]
    finding = report["findings"][0]
    assert finding["rule_family"] == FAMILY_BACKLINKS == "parent-to-child back-links"
    assert finding["disposition"] == "fixed"
    assert finding["file"] == store.rel(_PARENT)
    assert finding["record_id"] == _PARENT
    assert _ADDED in finding_text(finding)


def test_second_run_changes_nothing(tmp_path):
    # covers: ACD-2500a-2-i
    # angle: criterion
    """An immediate second run writes no byte, reports no 'fixed' entry, and still
    passes (a repair that appended again would show up as a duplicate id)."""
    store = make_store(tmp_path, _missing_backlink_records())
    check_store(store)
    frozen = snapshot_tree(store.folder)

    exit_code, rerun = check_store(store)

    assert snapshot_tree(store.folder) == frozen
    assert [f for f in rerun["findings"] if f["disposition"] == "fixed"] == []
    assert store.read(_PARENT)["covered_by"] == list(_KIDS)
    assert rerun["verdict"] == "passed" and exit_code == 0


def test_missing_parent_reported_and_not_created(tmp_path):
    # covers: ACD-2500a-2-i
    # angle: failure
    """A child whose derived parent has no record in the folder is 'needs a decision'
    naming the child and the missing parent, the run fails, and no parent file (or
    any other file) appears. A sibling chain with its parent present is the control:
    it produces no back-link finding."""
    orphan = valid_record(_ADDED, level="L2", depends_on=[_PARENT])
    control = hierarchy("ACD-9980", 1)  # complete chain: its back-links are fine
    store = make_store(tmp_path, [orphan, *control])
    before = snapshot_tree(store.folder)

    exit_code, report = check_store(store)

    findings = findings_for(report, rule_family=FAMILY_BACKLINKS)
    assert len(findings) == 1, report["findings"]
    assert findings[0]["record_id"] == _ADDED
    assert findings[0]["disposition"] == "needs a decision"
    assert findings[0]["file"] == store.rel(_ADDED)
    assert _ADDED in finding_text(findings[0]) and _PARENT in finding_text(findings[0])
    assert snapshot_tree(store.folder) == before  # nothing written, nothing created
    assert not store.path(_PARENT).exists()
    assert report["verdict"] == "failed" and exit_code == 1


def test_acd_2500a_2_i_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500a-2-i
    # angle: reachability
    """Real CLI subprocess: exit 0, one 'fixed' back-link entry on stdout, and the
    append is on disk -- the effect plan-feature relies on."""
    store = make_store(tmp_path, _missing_backlink_records())

    run = run_cli_subprocess(cli_argv(store), cwd=store.repo_root)

    assert run.exit_code == 0, run.stderr
    assert run.report["verdict"] == "passed"
    fixed = findings_for(run.report, rule_family=FAMILY_BACKLINKS)
    assert [f["disposition"] for f in fixed] == ["fixed"]
    assert store.read(_PARENT)["covered_by"] == list(_KIDS)
