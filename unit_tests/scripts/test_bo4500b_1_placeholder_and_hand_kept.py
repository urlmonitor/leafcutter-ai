"""
MODULE: unit_tests/scripts/test_bo4500b_1_placeholder_and_hand_kept.py
GOAL: BO-4500b-1 / BO-4500b-1-i -- an unresolvable {{config.*}} placeholder inside a shared
    block fails the install, and a marker pair whose name has no source but holds text fails
    unless declared in _shared/hand-kept.json.
Split out of test_bo4500b_1_validation_failures.py (file-size limit); reuses its helpers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bo4500b1_support as S  # noqa: E402
from test_bo4500b_1_validation_failures import REL, _failed_install, _line, _run  # noqa: E402


def _bad_placeholder(pkg):
    (pkg.wf / "_shared" / "alpha-answer.js").write_text(
        "function alphaBlock() {\n  return '{{config.no_such_key}}';\n}\n", encoding="utf-8")


def _hand_text_unknown(pkg):
    (pkg.wf / "route-c.js").write_text(
        "// c\n// pad\n// ALPHA-ANSWR-START\nconst kept = 1;\n// ALPHA-ANSWR-END\n", encoding="utf-8")


def test_unresolvable_block_placeholder_fails_install_naming_source_line_and_key(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1
    # angle: failure
    """ALPHA source with {{config.no_such_key}} on line 2: install fails naming source, line, placeholder.

    Wrong versions caught: an unknown placeholder passed through raw into every installed route.
    """
    ok, text, before, after, _out = _failed_install(tmp_path, monkeypatch, capsys, _bad_placeholder)
    assert not ok
    assert f"{REL}_shared/alpha-answer.js:2" in text, text
    assert "{{config.no_such_key}}" in text, text
    assert before and before == after
    assert b"no_such_key" not in b"".join(after.values())


def test_unknown_name_pair_holding_text_fails_unless_declared_hand_kept(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-i
    # angle: discrimination
    """ALPHA-ANSWR pair holding text fails naming route, line, block; declared hand-kept it installs unchanged.

    Wrong versions caught: a pair with an unknown name and text skipped silently.
    """
    ok, text, before, after, _out = _failed_install(tmp_path / "bad", monkeypatch, capsys, _hand_text_unknown)
    assert not ok
    assert REL + "route-c.js" in text and "ALPHA-ANSWR" in text and _line(text, 3), text
    assert "hand-kept" in text and before == after

    pkg = S.make_package(tmp_path / "kept", monkeypatch)
    _hand_text_unknown(pkg)
    (pkg.wf / "_shared" / "hand-kept.json").write_text(
        json.dumps({"ALPHA-ANSWR": "kept on purpose in this test"}), encoding="utf-8")
    ok, text = _run(pkg, capsys)
    assert ok, text
    installed = (pkg.target / "workflows" / "route-c.js").read_text(encoding="utf-8")
    assert "// ALPHA-ANSWR-START\nconst kept = 1;\n// ALPHA-ANSWR-END\n" in installed
    assert not (pkg.target / "workflows" / "hand-kept.json").exists()
