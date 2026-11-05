"""
MODULE: unit_tests/evals/tq200d3/test_tq200d3_seam
GOAL: RED tests for TQ-200d-3 that pin the seam between the real pre-pass (scripts/ac_store/design_prepass.py)
    and the input the test-designer eval builds for a row: the same ingredients as plan-feature.js
    dispatchTestDesign (record ids, the verbatim report, ac_store_path), the test-design group only.
Target: scripts/evals/designer_eval/ (build_dispatch_input), scripts/evals/produced_tests_mode.py,
    scripts/ac_store/design_prepass.py
"""

from __future__ import annotations

import json

import pytest

import unit_tests.evals.tq200d3._helpers as h

GROUP_ONE_FIELDS = ("test_spec", "test_design_authorship", "test_design_opened_files")
GROUP_TWO_WORDS = ("file_findings", "file findings", "file-findings", "reference_file_path")


def _tamper(sandbox, report: dict) -> str:
    """Flip the on-disk state of the first declared file of the batch (delete it if it exists, create it if not)."""
    declared = report["records"][0]["declared_files"][0]
    target = sandbox / declared["path"]
    if declared["state"] == "exists":
        target.unlink()
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# created after the sandbox was built\n", encoding="utf-8")
    return declared["path"]


@pytest.mark.parametrize("key", sorted(h.ROW_IDS))
def test_designer_row_input_carries_the_real_prepass_report(tmp_path, key):
    # covers: TQ-200d-3
    # angle: seam
    # must_catch: pre-pass report built by the eval instead of design_prepass.py
    # must_catch: dispatch asks for the file-findings group too
    row = h.real_row(key)
    expected = row["expected"]
    ids, store = expected["records"], expected["store"]
    assert ids == [h.AC_IDS[key]], ids
    designer = h.module("designer_eval")
    assert callable(getattr(designer, "build_dispatch_input", None)), "designer_eval.build_dispatch_input(row, sandbox) -> str"
    sandbox = h.build_row_sandbox(key, tmp_path)

    # The REAL producer: what design_prepass.py prints for this row's sandbox.
    proc = h.run_prepass(sandbox, store, ids)
    assert proc.returncode == 0, proc.stderr[-400:]
    report = proc.stdout.strip()
    parsed = json.loads(report)
    assert parsed["batch"] == ids and parsed["records"] and parsed["records"][0]["declared_files"], parsed

    # The consumer: the input the mode builds for the agent.
    text = designer.build_dispatch_input(row, sandbox)
    assert isinstance(text, str)
    assert report in text, "the input must embed the pre-pass report verbatim (the bytes the script printed)"
    for ac_id in ids:
        assert ac_id in text
    assert (sandbox / store).as_posix() in text, "the input names the sandbox store path (ac_store_path)"
    for field in GROUP_ONE_FIELDS:
        assert field in text, f"the input must ask for the test-design group ({field})"
    lowered = text.lower()
    for word in GROUP_TWO_WORDS:
        assert word not in lowered, f"the input must not ask for the file-findings group: {word!r}"

    # The report is built from the sandbox AS IT IS when the input is built, not from a recorded or cached copy.
    changed = _tamper(sandbox, parsed)
    after = h.run_prepass(sandbox, store, ids)
    assert after.returncode == 0, after.stderr[-400:]
    assert after.stdout.strip() != report, f"control: changing {changed} must change the report"
    text_after = designer.build_dispatch_input(row, sandbox)
    assert after.stdout.strip() in text_after
    assert report not in text_after, "the input still carries the stale report"
    assert text_after != text


def test_designer_row_input_does_not_hand_the_agent_what_the_row_scores(tmp_path):
    # covers: TQ-200d-3
    # angle: seam
    # The text the agent receives holds neither the wrong versions the row scores nor the recorded gold output.
    row = h.real_row("bug")
    designer = h.module("designer_eval")
    sandbox = h.build_row_sandbox("bug", tmp_path)
    text = designer.build_dispatch_input(row, sandbox)
    for name in (h.REVERT, h.ALIAS, h.ALWAYS, h.DROP_RETRY):
        assert name not in text, f"the input must not hand the agent the wrong versions the row scores: {name!r}"
    assert "gold" not in text.lower() and "recorded" not in text.lower()
