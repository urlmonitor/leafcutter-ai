"""
MODULE: test_inf_100c_5_i
GOAL: RED tests for INF-100c-5-i (KI-FC-003 direction 2) -- a feedback writer that names no
    registered agent is reported by the build, once, with every category it appears in.
AC: INF-100c-5-i. The production contract these tests assume is documented in _inf_100c_5_fixtures.
"""
# @ac-tag: INF-100c-5-i

from __future__ import annotations

import pytest

from unit_tests.feedback import _inf_100c_5_fixtures as fx

_STALE = "ac-validater"  # the misspelling the AC names


def _unknown_world(tmp_path, lists, registered_only=()):
    """One signing agent that is listed everywhere it needs to be, plus registered non-signing writers."""
    return fx.make_world(
        tmp_path,
        signing=["python-coder"],
        others=["sql-coder", "epic-supervisor"],
        lists=lists,
        extra_registered=list(registered_only),
    )


@pytest.mark.shared_layout_mutator
def test_build_output_reports_a_misspelt_writer_at_warning_without_failing(tmp_path):
    # covers: INF-100c-5-i
    # angle: reachability
    # must_catch: a report printed only under a verbose or debug flag
    # must_catch: a report that makes the build fail by itself
    """Real build.py --validate-only (no verbose flag) prints ac-validater at WARNING and still exits 0."""
    root = fx.copy_package(tmp_path)
    fx.edit_categories(root, fx.compose(fx.register_newly_registered, fx.add_to("blocker", _STALE)))
    cwd = tmp_path / "cwd"
    cwd.mkdir()

    rc, out = fx.validate_only(root, cwd)

    lines = [ln for ln in fx.report_lines(out) if _STALE in ln]
    assert len(lines) == 1, f"expected exactly one warning line naming {_STALE}:\n{out[-2000:]}"
    assert "blocker" in lines[0], f"the report must name the category it appears in: {lines[0]!r}"
    assert rc == 0, f"a misspelt writer alone must not fail the build (caveat: undecided):\n{out[-2000:]}"
    assert fx.success_line_printed(out)
    # false-positive controls: registered agents and the hook sentinel are never reported
    for innocent in ("sql-coder", "epic-supervisor", "python-coder"):
        assert not any(innocent in ln for ln in fx.report_lines(out)), f"{innocent} was reported as unknown"
    assert not any("hook" in ln.split() for ln in fx.report_lines(out))


def test_unknown_writer_entry_names_the_category_it_appears_in(tmp_path):
    # covers: INF-100c-5-i
    # angle: criterion
    """A blocker list holding ac-validater yields one unknown_writers entry whose categories are exactly [blocker]."""
    world = _unknown_world(tmp_path, {"complete": ["python-coder"], "blocker": ["python-coder", _STALE]})

    result = fx.run_check(world)

    assert result["unknown_writers"] == [{"writer": _STALE, "categories": ["blocker"]}]
    assert result["missing_writers"] == []
    assert len(result["warnings"]) == 1 and _STALE in result["warnings"][0] and "blocker" in result["warnings"][0]
    assert result["failures"] == [], "an unknown writer must not by itself fail the build"


def test_writer_in_three_categories_is_reported_once_with_all_three(tmp_path):
    # covers: INF-100c-5-i
    # angle: discrimination
    # must_catch: a loop that reports the same writer once per category
    # must_catch: an entry that keeps only the first category it was found in
    # must_catch: categories listed in file order instead of sorted order
    """The stale name sits in complete, knowledge-gap and blocker (file order); one entry, sorted categories."""
    stale = "ac-renamed-long-ago"
    world = _unknown_world(
        tmp_path,
        {"complete": ["python-coder", stale], "knowledge-gap": [stale], "blocker": ["python-coder", stale]},
    )

    result = fx.run_check(world)

    assert result["unknown_writers"] == [{"writer": stale, "categories": ["blocker", "complete", "knowledge-gap"]}]
    assert len(result["warnings"]) == 1, f"reported once, not once per category: {result['warnings']}"
    for category in ("blocker", "complete", "knowledge-gap"):
        assert category in result["warnings"][0]


def test_registered_writers_are_not_reported_as_unknown(tmp_path):
    # covers: INF-100c-5-i
    # angle: discrimination
    # must_catch: a known set built from the signing-off agents only, which flags sql-coder and epic-supervisor
    # must_catch: a known set copied into the check instead of read from the registry
    """sql-coder, epic-supervisor and a registry-only agent are listed and registered (none signs off): not reported."""
    registry_only = "zz-registry-only-writer"
    world = _unknown_world(
        tmp_path,
        {
            "complete": ["python-coder", "sql-coder"],
            "tooling-issue": ["epic-supervisor", registry_only],
            "blocker": [_STALE],
        },
        registered_only=[registry_only],
    )

    result = fx.run_check(world)

    assert result["unknown_writers"] == [{"writer": _STALE, "categories": ["blocker"]}], (
        "only the unregistered name may be reported (the control proves the report is live)"
    )
    reported = " ".join(result["warnings"])
    for innocent in ("sql-coder", "epic-supervisor", registry_only):
        assert innocent not in reported
