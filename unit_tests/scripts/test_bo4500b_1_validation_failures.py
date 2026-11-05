"""
MODULE: unit_tests/scripts/test_bo4500b_1_validation_failures.py
GOAL: BO-4500b-1-i..v -- the shared-block fill validates the whole route set (unknown block,
    empty source, unused source, stale awaiting-adoption declaration, hand-filled pair,
    nesting, overlap, unpaired or mismatched markers) before it writes any installed route,
    and reports every failure with route path, 1-based marker line and block name.
Every failure test installs once successfully, changes a source so an earlier route WOULD be
rewritten, applies the fault, and requires the failed install to leave the installed set intact.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bo4500b1_support as S  # noqa: E402

REL = "templates/workflows-js/"


def _run(pkg, capsys, extra=None):
    """Run the real install; return (succeeded, all failure text: exception + stderr)."""
    capsys.readouterr()
    ok, text = True, ""
    try:
        S.install(pkg, extra)
    except SystemExit as exc:
        ok, text = exc.code in (0, None), str(exc.code)
    except Exception as exc:  # noqa: BLE001 - any install error is the observable under test
        ok, text = False, f"{type(exc).__name__}: {exc}"
    return ok, text + "\n" + capsys.readouterr().err


def _snapshot(out: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in out.glob("*")} if out.exists() else {}


def _line(text: str, n: int) -> bool:
    return re.search(rf"(?::|line\s*){n}\b", text) is not None


def _failed_install(tmp_path, monkeypatch, capsys, mutate):
    """Good install, then source change + fault; return (ok, text, before, after, out)."""
    pkg = S.make_package(tmp_path, monkeypatch)
    out = S.install(pkg)
    src = pkg.wf / "_shared" / "alpha-answer.js"
    src.write_text(src.read_text(encoding="utf-8").replace("alpha ", "ALPHA-NEW "), encoding="utf-8")
    mutate(pkg)
    before = _snapshot(out)
    ok, text = _run(pkg, capsys)
    return ok, text, before, _snapshot(out), out


def _unknown(pkg):
    routes = "// route A\n// pad\n// pad\n" + S.pair("ALPHA-ANSWR") + "console.log('a');\n"
    (pkg.wf / "route-c.js").write_text(routes, encoding="utf-8")


def _empty_source(pkg):
    (pkg.wf / "_shared" / "alpha-answer.js").write_text(" \t\r\n \n", encoding="utf-8")


def _unused(pkg):
    (pkg.wf / "route-b.js").write_text("// route B\n" + S.pair("ALPHA-ANSWER"), encoding="utf-8")


def _declare(pkg, mapping):
    (pkg.wf / "_shared" / "awaiting-adoption.json").write_text(json.dumps(mapping), encoding="utf-8")


def _stale(pkg):
    _declare(pkg, {"BETA-ANSWER": ["BO-9999a-1", "BO-9999a-2"]})


def _hand_filled(pkg):
    (pkg.wf / "route-c.js").write_text(
        "// c\n// ALPHA-ANSWER-START\nreturn { action: 'continue' };\n// ALPHA-ANSWER-END\n", encoding="utf-8")


def _nested(pkg):
    (pkg.wf / "route-c.js").write_text(
        "// c\n// pad\n// ALPHA-ANSWER-START\n// BETA-ANSWER-START\n// BETA-ANSWER-END\n// ALPHA-ANSWER-END\n",
        encoding="utf-8")


def _overlap(pkg):
    (pkg.wf / "route-c.js").write_text(
        "// c\n// pad\n// ALPHA-ANSWER-START\n// BETA-ANSWER-START\n// ALPHA-ANSWER-END\n// BETA-ANSWER-END\n",
        encoding="utf-8")


def _malformed(pkg):
    (pkg.wf / "route-a.js").write_text("// a\n// pad\n// ALPHA-ANSWER-START\nconsole.log(1);\n", encoding="utf-8")
    (pkg.wf / "route-b.js").write_text("// b\n// pad\n// ALPHA-ANSWER-END\nconsole.log(2);\n", encoding="utf-8")
    (pkg.wf / "route-c.js").write_text(
        "// c\n// pad\n// ALPHA-ANSWER-START\n// BETA-ANSWER-END\n", encoding="utf-8")
    # keep ALPHA and BETA used elsewhere so only the malformed markers can be the cause
    (pkg.wf / "route-d.js").write_text(
        "// d\n" + S.pair("ALPHA-ANSWER") + S.pair("BETA-ANSWER"), encoding="utf-8")


# ---------------------------------------------------------------- BO-4500b-1-i

def test_unknown_block_name_fails_install_with_diagnosing_message(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-i
    # angle: failure
    """Unknown ALPHA-ANSWR: message names route, start-marker line, the name, sorted known names."""
    ok, text, *_ = _failed_install(tmp_path, monkeypatch, capsys, _unknown)
    assert not ok
    assert REL + "route-c.js" in text
    assert _line(text, 4)
    assert "ALPHA-ANSWR" in text
    assert re.search(r"ALPHA-ANSWER\W+BETA-ANSWER", text), text


def test_failed_install_leaves_installed_routes_untouched(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-i
    # angle: failure
    """Unknown-name and whitespace-only-source failures leave every installed route as it was."""
    for sub, mutate in (("u", _unknown), ("e", _empty_source)):
        ok, _text, before, after, out = _failed_install(tmp_path / sub, monkeypatch, capsys, mutate)
        assert not ok, sub
        assert before and before == after, sub
        assert b"ALPHA-NEW" not in b"".join(after.values()), sub


def test_whitespace_only_source_fails_naming_block_and_every_needing_route(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-i
    # angle: failure
    """ALPHA source of spaces, tabs, CR, LF: failure names ALPHA-ANSWER as empty and routes A and B."""
    ok, text, *_ = _failed_install(tmp_path, monkeypatch, capsys, _empty_source)
    assert not ok
    assert "ALPHA-ANSWER" in text and re.search(r"(?i)\bempty\b", text), text
    assert REL + "route-a.js" in text and REL + "route-b.js" in text


def test_no_installed_route_carries_empty_marker_pair_after_failure(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-i
    # angle: failure
    """Fresh target + empty ALPHA source: nothing installed carries an empty ALPHA pair."""
    pkg = S.make_package(tmp_path, monkeypatch)
    _empty_source(pkg)
    ok, _text = _run(pkg, capsys)
    assert not ok
    for p in (pkg.target / "workflows").glob("*") if (pkg.target / "workflows").exists() else []:
        assert not re.search(r"// ALPHA-ANSWER-START\s*\n\s*// ALPHA-ANSWER-END", p.read_text(encoding="utf-8")), p


def test_validation_failures_are_reachable_from_the_workflow_build_phase(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-i
    # angle: reachability
    """build_phases.build_workflow_scripts itself surfaces the unknown-name failure, and a clean
    package through the same entry point still succeeds (control)."""
    pkg = S.make_package(tmp_path, monkeypatch)
    _unknown(pkg)
    ok, text = _run(pkg, capsys)
    assert not ok and "ALPHA-ANSWR" in text
    good = S.make_package(tmp_path / "good", monkeypatch)
    ok, text = _run(good, capsys)
    assert ok, text


# --------------------------------------------------------------- BO-4500b-1-ii

def test_unused_undeclared_source_fails_install(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-ii
    # angle: failure
    """BETA source, no route marks it, no declaration: fails naming BETA-ANSWER as unused."""
    ok, text, *_ = _failed_install(tmp_path, monkeypatch, capsys, _unused)
    assert not ok
    assert "BETA-ANSWER" in text and re.search(r"(?i)no route uses|unused|not used by any route", text), text


def test_unused_and_stale_failures_leave_installed_routes_untouched(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-ii
    # angle: failure
    """Unused-source and stale-declaration failures leave the installed set byte identical."""
    for sub, mutate in (("unused", _unused), ("stale", _stale)):
        ok, _text, before, after, _out = _failed_install(tmp_path / sub, monkeypatch, capsys, mutate)
        assert not ok, sub
        assert before and before == after, sub


def test_declared_awaiting_adoption_install_completes(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-ii
    # angle: criterion
    """With BETA declared for BO-9999a-1 and BO-9999a-2 the install completes."""
    pkg = S.make_package(tmp_path, monkeypatch)
    _unused(pkg)
    _declare(pkg, {"BETA-ANSWER": ["BO-9999a-1", "BO-9999a-2"]})
    ok, text = _run(pkg, capsys)
    assert ok, text
    assert (pkg.target / "workflows" / "route-a.js").exists()


def test_awaiting_adoption_is_reported_on_every_install(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-ii
    # angle: criterion
    """Normal output of two consecutive installs names BETA-ANSWER and the adopters in order."""
    pkg = S.make_package(tmp_path, monkeypatch)
    _unused(pkg)
    _declare(pkg, {"BETA-ANSWER": ["BO-9999a-1", "BO-9999a-2"]})
    for _ in range(2):
        capsys.readouterr()
        S.install(pkg)
        out = capsys.readouterr().out
        assert re.search(r"(?i)awaiting adoption", out), out
        assert "BETA-ANSWER" in out
        assert 0 <= out.find("BO-9999a-1") < out.find("BO-9999a-2"), out


def test_declaration_goes_stale_once_a_route_marks_the_block(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-ii
    # angle: discrimination
    """Route B marks BETA while the declaration lists adopters: stale. Empty adopters = no declaration.

    Wrong versions caught: a declaration honoured even when a route uses the block; an empty
    adopter list accepted as a valid declaration.
    """
    pkg = S.make_package(tmp_path, monkeypatch)
    _stale(pkg)
    ok, text = _run(pkg, capsys)
    assert not ok
    assert "BETA-ANSWER" in text and re.search(r"(?i)stale", text) and REL + "route-b.js" in text, text
    empty = S.make_package(tmp_path / "empty", monkeypatch)
    _unused(empty)
    _declare(empty, {"BETA-ANSWER": []})
    ok, text = _run(empty, capsys)
    assert not ok and "BETA-ANSWER" in text, text


def test_awaiting_adoption_declaration_is_reachable_from_the_workflow_build_phase(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-ii
    # angle: reachability
    """The real build_workflow_scripts entry point reports the adopters on its normal output."""
    pkg = S.make_package(tmp_path, monkeypatch)
    _unused(pkg)
    _declare(pkg, {"BETA-ANSWER": ["BO-9999a-1", "BO-9999a-2"]})
    capsys.readouterr()
    written = S.build_phases.build_workflow_scripts(
        pkg.target, {"workflows": {"enabled": True}, "output_root": ".leafcutter"}, dry_run=False, force=True)
    out = capsys.readouterr().out
    assert written >= 1
    assert "BO-9999a-1" in out and "BO-9999a-2" in out


# -------------------------------------------------------------- BO-4500b-1-iii

def test_text_between_template_markers_fails_install(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-iii
    # angle: failure
    """A line, or only whitespace, between route markers fails naming route, block, 'must be empty'."""
    ok, text, *_ = _failed_install(tmp_path / "text", monkeypatch, capsys, _hand_filled)
    assert not ok
    assert REL + "route-c.js" in text and "ALPHA-ANSWER" in text and "must be empty" in text, text

    def blank(pkg):
        (pkg.wf / "route-c.js").write_text("// c\n// ALPHA-ANSWER-START\n   \n// ALPHA-ANSWER-END\n",
                                           encoding="utf-8")

    ok, text, *_ = _failed_install(tmp_path / "ws", monkeypatch, capsys, blank)
    assert not ok, "whitespace-only text between markers must count as text"
    assert REL + "route-c.js" in text and "ALPHA-ANSWER" in text and "must be empty" in text, text


def test_hand_filled_template_failure_leaves_installed_routes_untouched(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-iii
    # angle: failure
    """Failed installs on a hand-filled template leave the installed set byte identical."""
    ok, _text, before, after, _out = _failed_install(tmp_path, monkeypatch, capsys, _hand_filled)
    assert not ok
    assert before and before == after


def test_template_text_equal_to_source_is_still_refused(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-iii
    # angle: discrimination
    """Template pair holding exactly the ALPHA source is refused like any other text.

    Wrong versions caught: refuse only text that differs from the source; allow a matching pair.
    """
    def equal(pkg):
        src = (pkg.wf / "_shared" / "alpha-answer.js").read_text(encoding="utf-8")
        (pkg.wf / "route-c.js").write_text(
            f"// c\n// ALPHA-ANSWER-START\n{src}// ALPHA-ANSWER-END\n", encoding="utf-8")

    ok, text, before, after, _out = _failed_install(tmp_path, monkeypatch, capsys, equal)
    assert not ok
    assert REL + "route-c.js" in text and "ALPHA-ANSWER" in text and "must be empty" in text, text
    assert before == after


def test_hand_filled_template_is_reachable_from_the_workflow_build_phase(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-iii
    # angle: reachability
    """The real entry point surfaces the hand-filled failure."""
    pkg = S.make_package(tmp_path, monkeypatch)
    _hand_filled(pkg)
    ok, text = _run(pkg, capsys)
    assert not ok and "must be empty" in text, text


# --------------------------------------------------------------- BO-4500b-1-iv

def _nest_fixture(pkg, which):
    routes = {
        "nested": "// b\n// pad\n// ALPHA-ANSWER-START\n// BETA-ANSWER-START\n"
                  "// BETA-ANSWER-END\n// ALPHA-ANSWER-END\n",
        "overlap": "// b\n// pad\n// ALPHA-ANSWER-START\n// BETA-ANSWER-START\n"
                   "// ALPHA-ANSWER-END\n// BETA-ANSWER-END\n",
    }
    (pkg.wf / "route-c.js").write_text(routes[which], encoding="utf-8")


def test_nested_blocks_fail_install_naming_both_and_lines(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-iv
    # angle: failure
    """Nested BETA in ALPHA: names route, both blocks, both start lines, 'inside'."""
    ok, text, *_ = _failed_install(tmp_path, monkeypatch, capsys, _nested)
    assert not ok
    assert REL + "route-c.js" in text and "ALPHA-ANSWER" in text and "BETA-ANSWER" in text
    assert _line(text, 3) and _line(text, 4), text
    assert re.search(r"(?is)BETA-ANSWER.{0,80}inside.{0,40}ALPHA-ANSWER", text), text


def test_nesting_and_overlap_failures_leave_installed_routes_untouched(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-iv
    # angle: failure
    """Nesting and overlap failures leave the installed set byte identical."""
    for sub, mutate in (("n", _nested), ("o", _overlap)):
        ok, _text, before, after, _out = _failed_install(tmp_path / sub, monkeypatch, capsys, mutate)
        assert not ok, sub
        assert before and before == after, sub


def test_overlapping_blocks_fail_install_as_overlap_not_nesting(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-iv
    # angle: discrimination
    """Overlap is reported as overlap; two separate places for the same block stay allowed.

    Wrong versions caught: detect nesting only and let overlap through; refuse two separate
    places for the same block.
    """
    ok, text, *_ = _failed_install(tmp_path / "o", monkeypatch, capsys, _overlap)
    assert not ok
    assert re.search(r"(?i)overlap", text), text
    assert REL + "route-c.js" in text and "ALPHA-ANSWER" in text and "BETA-ANSWER" in text
    assert _line(text, 3) and _line(text, 4), text

    pkg = S.make_package(tmp_path / "twice", monkeypatch)
    (pkg.wf / "route-c.js").write_text(
        "// c\n" + S.pair("ALPHA-ANSWER") + "// mid\n" + S.pair("ALPHA-ANSWER"), encoding="utf-8")
    ok, text = _run(pkg, capsys)
    assert ok, text
    installed = (pkg.target / "workflows" / "route-c.js").read_text(encoding="utf-8")
    assert installed.count("function alphaBlock") == 2


def test_nesting_check_is_reachable_from_the_workflow_build_phase(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-iv
    # angle: reachability
    """The real entry point surfaces the nesting failure."""
    pkg = S.make_package(tmp_path, monkeypatch)
    _nest_fixture(pkg, "nested")
    ok, text = _run(pkg, capsys)
    assert not ok and re.search(r"(?i)inside", text), text


# ---------------------------------------------------------------- BO-4500b-1-v

def test_malformed_markers_fail_with_one_message_per_route(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-v
    # angle: failure
    """Routes A, B, C each yield a message with route path, 1-based offending line, what is wrong."""
    ok, text, *_ = _failed_install(tmp_path, monkeypatch, capsys, _malformed)
    assert not ok
    for name in ("route-a.js", "route-b.js", "route-c.js"):
        lines = [ln for ln in text.splitlines() if REL + name in ln]
        assert lines, f"{name} not named: {text}"
        assert any(_line(ln, 3) for ln in lines), (name, lines)
    tail = text[text.index(REL + "route-c.js"):]
    assert "ALPHA-ANSWER" in tail and "BETA-ANSWER" in tail, tail


def test_all_malformed_routes_are_named_in_one_failed_install(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-v
    # angle: discrimination
    """One failed install names A, B and C in path order.

    Wrong versions caught: stop at the first malformed route; fill an unpaired start marker to
    end of file; silently skip a malformed route.
    """
    ok, text, _before, after, out = _failed_install(tmp_path, monkeypatch, capsys, _malformed)
    assert not ok
    pos = [text.find(REL + n) for n in ("route-a.js", "route-b.js", "route-c.js")]
    assert all(p >= 0 for p in pos), text
    assert pos == sorted(pos), text
    assert b"console.log(1)" not in after.get("route-a.js", b""), "unpaired start filled to end of file"


def test_malformed_marker_failure_leaves_installed_routes_untouched(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-v
    # angle: failure
    """The failed malformed-marker install leaves the installed set byte identical."""
    ok, _text, before, after, _out = _failed_install(tmp_path, monkeypatch, capsys, _malformed)
    assert not ok
    assert before and before == after


def test_malformed_marker_check_is_reachable_from_the_workflow_build_phase(tmp_path, monkeypatch, capsys):
    # covers: BO-4500b-1-v
    # angle: reachability
    """The real entry point surfaces the three-route failure."""
    pkg = S.make_package(tmp_path, monkeypatch)
    _malformed(pkg)
    ok, text = _run(pkg, capsys)
    assert not ok
    for name in ("route-a.js", "route-b.js", "route-c.js"):
        assert REL + name in text, text
