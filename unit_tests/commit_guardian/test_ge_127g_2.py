"""
MODULE: unit_tests/commit_guardian/test_ge_127g_2.py
COVERS: GE-127g-2 -- every document set aside is reported as set aside, on the
    ground its declaration carries, and the judged / set-aside populations are
    counted separately and move independently.

GOAL: RED test-first stubs, one per declared test_spec descriptor. Each drives
    the REAL check_doc_length.py as a subprocess against a real throwaway git
    repo with a real ``git add`` -- never a grep of the source. The declaration
    the gate reads is written by the fixture with grounds the fixture chose, so
    the reported ground is compared with the string the FIXTURE wrote, not a
    literal in the test and not a copy in the gate.

REACHABILITY ENTRY POINT (resolved, BP-1100g-2 Step 1.1): CLI script --
    ``python check_doc_length.py`` run with cwd at the staged repo (source copy
    for four descriptors, the DEPLOYED copy for the fifth).

Wrong versions the descriptors catch: silent skip; the two figures hardcoded as
    observed (arms 2/3/4 red); one combined total (arms 2/3 red); set-aside docs
    counted as compliant (arm 1 / arm 4); the count printed only when non-zero
    (arm 4); a second copy of each ground in the gate (arm 1).

DECISION HISTORY
- 2026-10-14 [GE-127g-2/test-writer]: Initial RED authoring.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127g_5_fixture as fx  # noqa: E402

SMALL = 20  # body lines: well inside any shipped authored limit
HAND_DOCS = ("docs/hand-one.md", "docs/hand-two.md", "docs/hand-three.md")
SET_ASIDE_DOCS = (f"{fx.LOC_A}one.md", f"{fx.LOC_B}two.md")
ENTRIES = [fx.entry(fx.LOC_A, fx.GROUND_A, 100000), fx.entry(fx.LOC_B, fx.GROUND_B, 100000)]


def _staged(*rels: str) -> dict[str, int]:
    return {rel: SMALL for rel in rels}


def _run(tmp_path: Path, *rels: str):
    guardian = fx.make_guardian(tmp_path / "guardian", ENTRIES)
    repo = fx.build_repo(tmp_path / "repo", committed={}, staged=_staged(*rels))
    return fx.run_gate(repo, guardian)


def _lines_naming(output: str, rel: str) -> list[str]:
    return [line for line in output.splitlines() if rel in line]


def test_judged_and_set_aside_counts_reported_separately_with_grounds(tmp_path: Path) -> None:
    # covers: GE-127g-2
    # angle: criterion
    """Arm 1. 5 documents staged -- 2 in declared locations, 3 hand-authored, all
    within their limits. The commit completes; the run states 3 judged and 2 set
    aside; each set-aside document is named and the ground the FIXTURE wrote into
    its declared entry appears; neither set-aside document is reported as within
    its permitted length.

    Must implement: a separate count per population plus the per-document ground
    read from the matching declaration entry. Wrong versions caught: set aside
    without reporting; set-aside docs folded into the compliant count; a second
    copy of the grounds in the gate (the fixture's unique grounds are not in it).
    """
    result = _run(tmp_path, *HAND_DOCS, *SET_ASIDE_DOCS)
    out = fx.output_of(result)

    assert result.returncode == fx.CLEAN_EXIT, f"commit refused (exit {result.returncode}): {out!r}"
    assert fx.count_of(out, "judged") == len(HAND_DOCS), f"judged figure wrong/absent: {out!r}"
    assert fx.count_of(out, "set aside") == len(SET_ASIDE_DOCS), f"set-aside figure wrong/absent: {out!r}"
    for rel in SET_ASIDE_DOCS:
        assert rel in out, f"set-aside document {rel} not named: {out!r}"
    assert fx.GROUND_A in out, f"ground declared for {fx.LOC_A} not reported: {out!r}"
    assert fx.GROUND_B in out, f"ground declared for {fx.LOC_B} not reported: {out!r}"
    for rel in SET_ASIDE_DOCS:
        for line in _lines_naming(out, rel):
            assert not re.search(r"within|PASSED|compliant|compared", line, re.IGNORECASE), (
                f"set-aside document {rel} reported as measured/compliant: {line!r}"
            )


def test_judged_figure_moves_when_only_the_judged_population_moves(tmp_path: Path) -> None:
    # covers: GE-127g-2
    # angle: discrimination
    """Arm 2. The same commit plus one further hand-authored document: the judged
    figure is one higher than the same-fixture baseline run and the set-aside
    figure is unchanged. Both runs are made here, so neither figure is a pinned
    number.

    Wrong versions caught: the two figures hardcoded as observed; one combined
    "documents handled" figure (it would move the wrong number).
    """
    base_dir = tmp_path / "base"
    more_dir = tmp_path / "more"
    base_dir.mkdir()
    more_dir.mkdir()
    baseline = fx.output_of(_run(base_dir, *HAND_DOCS, *SET_ASIDE_DOCS))
    extra = "docs/hand-four.md"
    moved_result = _run(more_dir, *HAND_DOCS, extra, *SET_ASIDE_DOCS)
    moved = fx.output_of(moved_result)

    assert moved_result.returncode == fx.CLEAN_EXIT, f"commit refused: {moved!r}"
    assert fx.count_of(moved, "judged") == len(HAND_DOCS) + 1, f"judged figure did not move to {len(HAND_DOCS) + 1}: {moved!r}"
    assert fx.count_of(moved, "set aside") == len(SET_ASIDE_DOCS), f"set-aside figure moved: {moved!r}"
    assert fx.count_of(baseline, "judged") == len(HAND_DOCS), f"baseline judged figure absent: {baseline!r}"


def test_set_aside_figure_moves_when_only_the_set_aside_population_moves(tmp_path: Path) -> None:
    # covers: GE-127g-2
    # angle: discrimination
    """Arm 3, the opposite direction. The same commit plus one further document in
    a declared location: judged unchanged, set aside one higher, and the newly
    staged document is among those named.

    Wrong versions caught: figures hardcoded as observed; deriving one figure
    from the other or from a total (a total of staged docs would move the judged
    figure the wrong way).
    """
    extra = f"{fx.LOC_A}three.md"
    result = _run(tmp_path, *HAND_DOCS, *SET_ASIDE_DOCS, extra)
    out = fx.output_of(result)

    assert result.returncode == fx.CLEAN_EXIT, f"commit refused: {out!r}"
    assert fx.count_of(out, "judged") == len(HAND_DOCS), f"judged figure moved or absent: {out!r}"
    assert fx.count_of(out, "set aside") == len(SET_ASIDE_DOCS) + 1, f"set-aside figure did not move: {out!r}"
    assert extra in out, f"newly staged set-aside document {extra} not named: {out!r}"


def test_all_set_aside_commit_states_zero_judged_and_claims_no_compliance(tmp_path: Path) -> None:
    # covers: GE-127g-2
    # angle: failure
    """Arm 4, the house failure. Every staged document is inside a declared
    location. The commit completes; the run states 0 judged; and -- asserted
    separately -- it does NOT claim that no document exceeded its permitted
    length, because none was measured.

    Wrong versions caught: printing the count only when non-zero (the present
    ``if checked_count > 0`` guard prints nothing, so the zero statement is
    absent); reporting compliance over a population of zero.
    """
    result = _run(tmp_path, *SET_ASIDE_DOCS)
    out = fx.output_of(result)

    assert result.returncode == fx.CLEAN_EXIT, f"commit refused: {out!r}"
    assert fx.count_of(out, "judged") == 0, f"a zero-population run must state 0 judged: {out!r}"
    assert fx.count_of(out, "set aside") == len(SET_ASIDE_DOCS), f"set-aside figure wrong/absent: {out!r}"
    assert not re.search(r"\b(no|none of the)\b[^\n]*\bexceed", out, re.IGNORECASE), (
        f"run claims nothing exceeded its limit over an empty judged population: {out!r}"
    )
    assert not re.search(r"within (their|its) (permitted )?(length|limit)", out, re.IGNORECASE), (
        f"run claims compliance over an empty judged population: {out!r}"
    )
    assert "PASSED" not in out, f"run reports a pass over an empty judged population: {out!r}"


@pytest.mark.shared_layout_reader
def test_deployed_gate_reports_both_populations_and_the_declared_grounds(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-127g-2
    # angle: deployed
    """The DEPLOYED check_doc_length.py, run cold from the shared build layout over
    a mixed staged set, states both figures and at least one declared ground --
    not a ModuleNotFoundError. The ground is read from the DEPLOYED declaration.
    Only READS the layout; no private build.py.

    Wrong version caught: the reporting helper placed outside
    templates/scripts/commit_guardian/ with no deploy-map entry (deployed hook
    crashes while source-tree tests stay green).
    """
    deployed = None
    for candidate in (
        shared_reference_layout / "scripts" / "commit_guardian",
        shared_reference_layout / ".leafcutter" / "scripts" / "commit_guardian",
    ):
        if (candidate / "check_doc_length.py").exists():
            deployed = candidate
            break
    assert deployed is not None, f"check_doc_length.py not deployed under {shared_reference_layout}"
    declared = json.loads((deployed / fx.CONFIG_NAME).read_text(encoding="utf-8"))["doc_length"]["set_aside_locations"]
    location = declared[0]
    in_location = [f"{location['path']}fixture-{i}.md" for i in range(2)] if location["path"].endswith("/") else [location["path"]]

    repo = fx.build_repo(tmp_path / "deployed", committed={}, staged=_staged(*HAND_DOCS, *in_location))
    result = fx.run_gate(repo, deployed)
    out = fx.output_of(result)

    assert "ModuleNotFoundError" not in out, f"deployed gate crashed importing a dependency: {out!r}"
    assert result.returncode == fx.CLEAN_EXIT, f"deployed gate refused (exit {result.returncode}): {out!r}"
    assert fx.count_of(out, "judged") == len(HAND_DOCS), f"deployed run: judged figure wrong/absent: {out!r}"
    assert fx.count_of(out, "set aside") == len(in_location), f"deployed run: set-aside figure wrong/absent: {out!r}"
    assert location["ground"] in out, f"deployed run did not report the declared ground: {out!r}"
