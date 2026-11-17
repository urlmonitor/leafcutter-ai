"""
MODULE: unit_tests/commit_guardian/test_ge_127g_5.py
COVERS: GE-127g-5 -- a set-aside location is still a bounded place: each entry
    declares ``report_above_lines``; a document above it is REPORTED (size,
    ceiling, source) while the commit completes; an entry with no ceiling is
    REJECTED.

GOAL: RED test-first stubs, one per declared test_spec descriptor. Each drives
    the REAL check_doc_length.py as a subprocess against a real throwaway git
    repo with a real ``git add``. The declaration is written by the fixture;
    every size / ceiling / headroom expectation is computed from what the
    fixture constructed, never pinned.

REACHABILITY ENTRY POINT (resolved, BP-1100g-2 Step 1.1): CLI script --
    ``python check_doc_length.py`` with cwd at the staged repo (source copy for
    six descriptors, the DEPLOYED copy for the seventh).

Output-shape assumptions (the AC fixes words, not layout) are listed in
    _ge_127g_5_fixture.py: the over-ceiling statement is a paragraph containing
    "ceiling"; headroom is "headroom" + a signed integer (ceiling - size).

Named mutations caught: refusing on the ceiling (arms 2, 3); report taken from
    classify_dimension's verdict (arm 3 only); a literal ceiling in the gate
    (arm 4a, arm 5); pinned figures (arm 4b); judging set-aside docs against the
    authored limit (arm 1); defaulted ceiling (arm 5); an undeployed helper
    (deployed arm).

DECISION HISTORY
- 2026-10-14 [GE-127g-5/test-writer]: Initial RED authoring.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127g_5_fixture as fx  # noqa: E402

LIMIT = fx.shipped_limit()
CEIL = LIMIT * 4  # the fixture's declared ceiling, derived from the shipped limit
DOC = f"{fx.LOC_A}generated.md"
HAND = "docs/hand-authored.md"
ENTRIES = [fx.entry(fx.LOC_A, fx.GROUND_A, CEIL), fx.entry(fx.LOC_B, fx.GROUND_B, CEIL)]


def _run(tmp_path: Path, committed: int, staged: int, entries: list[dict] | None = None):
    """Gate run over a repo whose DOC stood at *committed* body lines at HEAD and is restaged at *staged*."""
    guardian = fx.make_guardian(tmp_path / "guardian", entries if entries is not None else ENTRIES)
    repo = fx.build_repo(tmp_path / "repo", committed={DOC: committed}, staged={DOC: staged, HAND: 10})
    return fx.run_gate(repo, guardian)


def test_regeneration_below_the_ceiling_completes_and_stays_set_aside(tmp_path: Path) -> None:
    # covers: GE-127g-5
    # angle: criterion
    """Arm 1, the negative control against the cheapest "bound". DOC stood above
    the authored limit and below its ceiling at HEAD, and is restaged longer but
    still below the ceiling, beside one hand-authored document. The commit
    completes; DOC is reported SET ASIDE; it is NOT judged against the authored
    limit (judged figure counts only the hand-authored doc); it is not reported
    within-limit; and it is not reported as above any ceiling.

    Wrong versions caught: obtaining the bound by judging set-aside documents
    against the authored limit after all (the growth ratchet would refuse DOC);
    moving documents out of the set-aside count into the judged count.
    """
    result = _run(tmp_path, committed=LIMIT + 100, staged=LIMIT + 160)
    out = fx.output_of(result)

    assert result.returncode == fx.CLEAN_EXIT, f"commit refused (exit {result.returncode}): {out!r}"
    assert DOC in out, f"set-aside document not reported: {out!r}"
    assert fx.count_of(out, "set aside") == 1, f"DOC not counted as set aside: {out!r}"
    assert fx.count_of(out, "judged") == 1, f"DOC was judged (or judged figure absent); only {HAND} is judged: {out!r}"
    assert "BLOCKED" not in out, f"set-aside document was judged against the authored limit: {out!r}"
    assert not fx.ceiling_statement_for(out, DOC), f"DOC is below its ceiling but reported above it: {out!r}"
    for line in (ln for ln in out.splitlines() if DOC in ln):
        assert "within" not in line.lower() and "PASSED" not in line, f"DOC reported as compliant: {line!r}"


def test_crossing_the_ceiling_reports_size_ceiling_and_source_and_still_completes(tmp_path: Path) -> None:
    # covers: GE-127g-5
    # angle: criterion
    """Arm 2. The regeneration leaves DOC above its declared ceiling. The commit
    COMPLETES (asserted first, on its own); the report states the measured size,
    the ceiling it was measured against, and NAMES the source the location's
    ground identifies. A second declared location (not staged) has a different
    source, which must not be named. All figures computed by the fixture.

    Wrong versions caught: refusing on the ceiling; taking the report from the
    refusal path; reporting "enormous" without naming the responsible source.
    """
    staged = CEIL + 40
    result = _run(tmp_path, committed=CEIL - 30, staged=staged)
    out = fx.output_of(result)

    assert result.returncode == fx.CLEAN_EXIT, f"crossing the ceiling must not refuse (exit {result.returncode}): {out!r}"
    statement = fx.ceiling_statement_for(out, DOC)
    assert statement, f"no ceiling statement names {DOC}: {out!r}"
    assert str(fx.measured(staged)) in statement, f"measured size {fx.measured(staged)} not stated: {statement!r}"
    assert str(CEIL) in statement, f"declared ceiling {CEIL} not stated: {statement!r}"
    assert fx.SOURCE_A in statement, f"source identified by the ground ({fx.SOURCE_A}) not named: {statement!r}"
    assert fx.SOURCE_B not in out, f"source of an unrelated, unstaged location was named: {out!r}"


def test_shrinking_while_still_above_the_ceiling_is_still_reported(tmp_path: Path) -> None:
    # covers: GE-127g-5
    # angle: discrimination
    """Arm 3, the load-bearing entry. DOC is ABOVE its ceiling at HEAD and the
    regeneration leaves it SHORTER but still above. Against the ceiling that is
    classify_dimension's growth branch returning "pass", so a report triggered
    from the verdict word says nothing. The commit completes AND the run still
    states DOC stands above its location's ceiling, with size and ceiling.

    Wrong versions caught: deriving the report from classify_dimension's verdict
    (stated only on "over"/"grew"); reporting only on the crossing commit;
    refusing while above the ceiling.
    """
    staged = CEIL + 20
    result = _run(tmp_path, committed=CEIL + 80, staged=staged)
    out = fx.output_of(result)

    assert result.returncode == fx.CLEAN_EXIT, f"a shrinking document above its ceiling must not refuse: {out!r}"
    statement = fx.ceiling_statement_for(out, DOC)
    assert statement, f"document still above its ceiling was not reported: {out!r}"
    assert str(fx.measured(staged)) in statement, f"measured size {fx.measured(staged)} not stated: {statement!r}"
    assert str(CEIL) in statement, f"declared ceiling {CEIL} not stated: {statement!r}"


def test_raising_the_declared_ceiling_makes_the_report_disappear(tmp_path: Path) -> None:
    # covers: GE-127g-5
    # angle: discrimination
    """Arm 4, first half. The same staged content as arm 3, run twice: once under
    the original declared ceiling (control -- the report MUST be present) and
    once with the entry's report_above_lines raised above BOTH the parent size
    and the staged size (so this exercises the crossing branch, not growth).
    Under the raised ceiling the run does not state DOC stands above its ceiling
    and names no document as standing above any ceiling.

    Wrong versions caught: one ceiling written into the gate's own code; reading
    the ceiling from the declaration but caching it across runs.
    """
    committed, staged = CEIL + 80, CEIL + 20
    control_dir = tmp_path / "control"
    raised_dir = tmp_path / "raised"
    control_dir.mkdir()
    raised_dir.mkdir()

    control = fx.output_of(_run(control_dir, committed, staged))
    assert fx.ceiling_statement_for(control, DOC), f"control run (declared ceiling) must report DOC: {control!r}"

    raised_ceiling = fx.measured(committed) + CEIL  # above both parent and staged sizes
    raised_entries = [fx.entry(fx.LOC_A, fx.GROUND_A, raised_ceiling), fx.entry(fx.LOC_B, fx.GROUND_B, CEIL)]
    result = _run(raised_dir, committed, staged, entries=raised_entries)
    out = fx.output_of(result)

    assert result.returncode == fx.CLEAN_EXIT, f"commit refused under a raised ceiling: {out!r}"
    assert not fx.ceiling_statement_for(out, DOC), f"DOC reported above a ceiling it is below: {out!r}"
    assert not [p for p in fx.ceiling_paragraphs(out) if ".md" in p], (
        f"a document is still named as standing above a ceiling: {fx.ceiling_paragraphs(out)!r}"
    )


def test_stated_size_and_headroom_follow_the_tree_when_the_ceiling_is_held(tmp_path: Path) -> None:
    # covers: GE-127g-5
    # angle: discrimination
    """Arm 4, second half. Hold report_above_lines fixed and regenerate DOC larger
    again: the stated size equals the size newly measured from the staged
    content, and the stated headroom (ceiling - size, signed) is smaller than the
    first run's by EXACTLY the number of lines the document grew. Growth and both
    sizes are computed by the fixture.

    Wrong versions caught: figures stated as numbers observed at implementation
    time; headroom derived from a cached/previous size instead of the staged
    content.
    """
    parent = CEIL + 30
    first_staged, second_staged = CEIL + 60, CEIL + 140
    grew = second_staged - first_staged
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()

    first = fx.ceiling_statement_for(fx.output_of(_run(first_dir, parent, first_staged)), DOC)
    second = fx.ceiling_statement_for(fx.output_of(_run(second_dir, parent, second_staged)), DOC)

    assert str(fx.measured(first_staged)) in first, f"first run: size {fx.measured(first_staged)} not stated: {first!r}"
    assert str(fx.measured(second_staged)) in second, f"second run: size {fx.measured(second_staged)} not stated: {second!r}"
    assert str(fx.measured(first_staged)) not in second, f"second run still states the first run's size: {second!r}"
    head_first, head_second = fx.stated_headroom(first), fx.stated_headroom(second)
    assert head_first is not None and head_second is not None, f"headroom not stated: {first!r} / {second!r}"
    assert head_first - head_second == grew, (
        f"headroom fell by {head_first - head_second}, document grew by {grew} ({head_first} -> {head_second})"
    )


def test_declaring_a_location_without_a_ceiling_is_refused_and_names_the_entry(tmp_path: Path) -> None:
    # covers: GE-127g-5
    # angle: failure
    """Arm 5, the one refusal this record admits. Every staged document is well
    inside the authored limit (so a defaulted ceiling -- unbounded, or the
    authored limit -- would let the commit complete). An entry carrying a ground
    and NO report_above_lines makes the commit fail, and the report names that
    entry and the missing key. A second declaration -- ceiling present, ground
    blank -- is also refused but is diagnosed differently (names the ground, not
    the ceiling key).

    Wrong versions caught: treating a missing ceiling as unbounded; as the
    authored limit; one message that cannot tell a missing ground from a
    missing ceiling.
    """
    no_ceiling_loc = "docs/gen-noceiling/"
    blank_ground_loc = "docs/gen-blankground/"
    staged = {f"{no_ceiling_loc}doc.md": 10, HAND: 10}

    guardian = fx.make_guardian(tmp_path / "g_no_ceiling", [fx.entry(no_ceiling_loc, fx.GROUND_A)])
    repo = fx.build_repo(tmp_path / "r_no_ceiling", committed={}, staged=staged)
    missing = fx.run_gate(repo, guardian)
    missing_out = fx.output_of(missing)

    assert missing.returncode != fx.CLEAN_EXIT, f"an entry with no ceiling was honoured (exit 0): {missing_out!r}"
    assert no_ceiling_loc in missing_out, f"refusal does not name the offending entry: {missing_out!r}"
    assert fx.CEILING_KEY in missing_out, f"refusal does not say the ceiling ({fx.CEILING_KEY}) is what is missing: {missing_out!r}"

    guardian2 = fx.make_guardian(tmp_path / "g_blank_ground", [fx.entry(blank_ground_loc, "   ", CEIL)])
    repo2 = fx.build_repo(tmp_path / "r_blank_ground", committed={}, staged={f"{blank_ground_loc}doc.md": 10, HAND: 10})
    blank = fx.run_gate(repo2, guardian2)
    blank_out = fx.output_of(blank)

    assert blank.returncode != fx.CLEAN_EXIT, f"an entry with a blank ground was honoured: {blank_out!r}"
    assert blank_ground_loc in blank_out, f"blank-ground refusal does not name the entry: {blank_out!r}"
    assert "ground" in blank_out.lower(), f"blank-ground refusal does not say the ground is missing: {blank_out!r}"
    assert fx.CEILING_KEY not in blank_out, f"blank-ground refusal blames the ceiling instead: {blank_out!r}"
    assert missing_out != blank_out, "the two refusals are indistinguishable"


@pytest.mark.shared_layout_reader
def test_deployed_gate_reads_the_declared_ceilings_and_reports_above_them(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-127g-5
    # angle: deployed
    """The DEPLOYED check_doc_length.py, run cold from the shared build layout over
    a staged document above its location's DEPLOYED declared ceiling, completes
    and states the over-ceiling report (size and ceiling read from the deployed
    declaration) -- not a ModuleNotFoundError. Only READS the layout.

    Wrong versions caught: the over-ceiling helper placed outside
    templates/scripts/commit_guardian/ with no deploy-map entry; editing the
    deployed copy instead of the templates/ source (the deployed declaration
    would carry no ceilings).
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
    location = next(e for e in declared if e["path"].endswith("/"))
    assert fx.CEILING_KEY in location, f"deployed declaration carries no ceiling for {location['path']}: {location!r}"
    ceiling = int(location[fx.CEILING_KEY])

    doc = f"{location['path']}fixture-over-ceiling.md"
    staged = ceiling + 50
    repo = fx.build_repo(tmp_path / "deployed", committed={}, staged={doc: staged})
    result = fx.run_gate(repo, deployed)
    out = fx.output_of(result)

    assert "ModuleNotFoundError" not in out, f"deployed gate crashed importing a dependency: {out!r}"
    assert result.returncode == fx.CLEAN_EXIT, f"deployed gate refused a document above its ceiling: {out!r}"
    statement = fx.ceiling_statement_for(out, doc)
    assert statement, f"deployed gate did not report {doc} above its ceiling: {out!r}"
    assert str(fx.measured(staged)) in statement and str(ceiling) in statement, (
        f"deployed report lacks size {fx.measured(staged)} / ceiling {ceiling}: {statement!r}"
    )
