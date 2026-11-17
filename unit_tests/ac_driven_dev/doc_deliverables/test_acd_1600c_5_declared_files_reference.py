"""ACD-1600c-5 -- the declared-files section of docs/reference/ac-schema.md (content checks).

The AC is ``test_required: false`` (documentation deliverable). Each test reads the delivered section
"The `declared_files` Field" and asserts one clause of the AC's criteria is actually stated there, so a
deleted section or a dropped clause turns it red.
"""

from __future__ import annotations

from unit_tests.ac_driven_dev.doc_deliverables import _doc_support as D

PAGE = D.REPO / "docs" / "reference" / "ac-schema.md"


def _sec() -> str:
    return D.section(D.read(PAGE), "The `declared_files` Field")


def test_declared_files_list_path_form_and_two_markers():
    # covers: ACD-1600c-5
    # angle: criterion
    """The section describes the list, the path form and both markers."""
    D.assert_all(
        _sec(),
        ["`declared_files`", "`existing`", "`to_be_created`", "Repository-root-relative path, forward slashes",
         "Never a regenerated copy such as `.leafcutter/scripts/x.py`", "in declared order"],
        "ac-schema.md declared_files section",
    )


def test_declared_files_is_only_answer_and_doc_links_never_count():
    # covers: ACD-1600c-5
    # angle: criterion
    """It states the list is the only answer and that doc_links of any relationship are not part of it."""
    sec = _sec()
    D.assert_all(sec, ["The only answer", "which files does this work change"], "ac-schema.md")
    D.assert_all(
        sec,
        ["`doc_links` entries of any relationship (`modifies`, `describes`, `related`) never count"],
        "ac-schema.md",
    )


def test_declared_files_refusals_versus_reports():
    # covers: ACD-1600c-5
    # angle: criterion
    """It states which entries refuse a requirement and which are only reported."""
    sec = D.flat(_sec())
    for refusal in ("neither present in the tree nor marked `to_be_created`", "Path outside the repository",
                    "inside a regenerated copy", "Empty list"):
        assert refusal in sec, f"refusal case not stated: {refusal}"
    assert "`to_be_created` entry whose file already exists | Report only" in sec
    assert "A refusal blocks the commit; a report never does." in sec


def test_declared_files_no_declared_files_state():
    # covers: ACD-1600c-5
    # angle: criterion
    """It states the 'no declared files' state, 'not evaluated' reporting and that nothing fills the list in."""
    D.assert_all(
        _sec(),
        ['the state "no declared files"', "`not evaluated: no declared files`, never as passed",
         "Nothing fills the list in automatically"],
        "ac-schema.md declared_files section",
    )


def test_declared_files_worked_example_predicts_the_reported_entry():
    # covers: ACD-1600c-5
    # angle: criterion
    """A worked example declares one existing and one to-be-created file and says which one the check reports
    if the new file already existed (the to_be_created one), and that the commit proceeds."""
    sec = _sec()
    assert "path: scripts/ac_store/scan_ac_store.py\n    state: existing" in sec
    assert "path: unit_tests/ac_store/test_scan_extra.py\n    state: to_be_created" in sec
    flat = D.flat(sec)
    assert "the second entry is the one reported" in flat
    assert "is marked to be created but already exists" in flat
    assert "the commit proceeds" in flat
