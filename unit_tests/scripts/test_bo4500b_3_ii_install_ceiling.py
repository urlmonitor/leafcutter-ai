"""
MODULE: unit_tests/scripts/test_bo4500b_3_ii_install_ceiling.py
GOAL: BO-4500b-3-ii install-side proofs -- a missing or malformed max_transient_retries fails the
    install naming the setting; the configured ceiling reaches the installed block.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
import _bo4500b3_support as S  # noqa: E402

BAD = {
    "missing": lambda cfg: cfg.pop("max_transient_retries"),
    "string": lambda cfg: cfg.__setitem__("max_transient_retries", "three"),
    "negative": lambda cfg: cfg.__setitem__("max_transient_retries", -1),
    "float": lambda cfg: cfg.__setitem__("max_transient_retries", 2.5),
}


def test_missing_ceiling_fails_install_naming_the_setting(tmp_path, monkeypatch):
    # covers: BO-4500b-3-ii
    # angle: failure
    """Missing / non-integer / negative ceiling: install fails naming max_transient_retries and the file."""
    for label, mutate in BAD.items():
        inst = S.render_block(tmp_path / label, monkeypatch, mutate)
        assert inst.error is not None, f"{label}: install succeeded with a bad ceiling"
        msg = str(inst.error)
        assert "max_transient_retries" in msg, (label, msg)
        assert "commit_step.json" in msg, (label, msg)


def test_failed_ceiling_install_leaves_no_route_with_a_supplied_default(tmp_path, monkeypatch):
    # covers: BO-4500b-3-ii
    # angle: failure
    """After a failed install the previously installed route is byte-identical, with no default."""
    good = S.render_block(tmp_path / "good", monkeypatch)
    assert good.error is None and good.text and "{{config" not in good.text, good.error
    route = good.target / "workflows" / "commit-route.js"
    before = route.read_bytes()
    bad = S.render_block(tmp_path / "good", monkeypatch, BAD["missing"])
    assert bad.error is not None, "install with a missing ceiling did not fail"
    assert route.read_bytes() == before
    assert "{{config" not in route.read_text(encoding="utf-8")


def test_configured_ceiling_is_reachable_through_the_install(tmp_path, monkeypatch):
    # covers: BO-4500b-3-ii
    # angle: reachability
    """The real entry point with a fixture ceiling of 5: five retries then report."""
    def mutate(cfg):
        cfg["max_transient_retries"] = 5
    inst = S.render_block(tmp_path, monkeypatch, mutate)
    assert inst.error is None, inst.error
    answers = [S.commit_answer("refused", "step_index_locked") for _ in range(6)]
    decisions, _ = S.run_sequence(inst.text, answers)
    assert S.names(decisions) == ["retry"] * 5 + ["report"], decisions
