"""
MODULE: test_inf_100c_5_iv
GOAL: Tests for INF-100c-5-iv (KI-FC-003) -- every agent that signs off today is a registered feedback
    writer in the shipped categories files: both AC-coverage gates (already on main since c3a469610,
    pinned here) and restructuring-specialist + change-scope-reviewer (still missing).
AC: INF-100c-5-iv. The production contract these tests assume is documented in _inf_100c_5_fixtures.
"""
# @ac-tag: INF-100c-5-iv

from __future__ import annotations

import pytest

from unit_tests.feedback import _inf_100c_5_fixtures as fx

_GATES = ("ac-validator", "ac-fulfillment-gate")
_ROLE_RESTRICTED = ("quality-concern", "subagent-quality", "process-finding")


def _assert_exactly_the_six(lists: dict[str, list[str]], names: tuple[str, ...]) -> None:
    assert sorted(lists) == sorted(fx.NINE), f"the shipped file must carry the nine categories: {sorted(lists)}"
    for name in names:
        homes = [c for c, writers in lists.items() if name in writers]
        assert sorted(homes) == sorted(fx.SIX), f"{name} must be a writer of exactly the six categories, found {sorted(homes)}"
        for category in fx.SIX:
            assert lists[category].count(name) == 1, f"{name} must appear once in {category}: {lists[category]}"
        for category in _ROLE_RESTRICTED:
            assert name not in lists[category], f"{name} must not be a writer of the role-restricted {category}"


@pytest.mark.shared_layout_mutator
def test_shipped_package_validate_only_build_passes_the_writer_check(tmp_path):
    # covers: INF-100c-5-iv
    # angle: reachability
    # must_catch: restructuring-specialist or change-scope-reviewer left out of the shipped lists
    """The real scripts/build.py --validate-only on the package as shipped exits 0 with no missing-writer failure."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()

    # liveness control (a different reason to fail): the writer check is wired in and sees the real roster --
    # a copy with one real signing-off agent unlisted must fail and name it. Without it a green shipped run
    # could mean the check never ran.
    root = fx.copy_package(tmp_path)
    fx.edit_categories(root, fx.compose(fx.register_newly_registered, fx.drop_everywhere("python-coder")))
    rc_live, out_live = fx.validate_only(root, cwd)
    assert rc_live != 0 and "python-coder" in out_live, f"control: the writer check is not wired in:\n{out_live[-1500:]}"

    rc, out = fx.validate_only(fx.REPO_ROOT, cwd)

    assert rc == 0, f"the shipped package must pass its own writer check:\n{out[-2500:]}"
    assert fx.success_line_printed(out)
    feedback_lines = [ln for ln in out.splitlines() if "feedback" in ln.lower()]
    for name in fx.NEWLY_REGISTERED:
        assert not any(name in ln for ln in feedback_lines), f"{name} is named by a feedback line of the shipped build"


def test_shipped_categories_name_no_unregistered_writer(tmp_path):
    # covers: INF-100c-5-iv
    # angle: criterion
    """The check run on the shipped agents, categories file and registry reports no unknown writer and no missing writer."""
    result = fx.load_check().check_feedback_writers(
        fx.REPO_ROOT / "templates" / "agents",
        fx.REPO_ROOT / "templates" / "config" / "feedback_categories.yaml",
        fx.REPO_ROOT / "config" / "agent_registry.json",
    )

    assert result["unknown_writers"] == []
    assert result["missing_writers"] == [], "every agent that signs off must be a writer of some category"
    assert result["failures"] == []


def test_both_ac_gates_are_writers_of_exactly_the_six_categories():
    # covers: INF-100c-5-iv
    # angle: discrimination
    # must_catch: a gate missing from success-pattern or any one of the six
    # must_catch: a gate added to the reviewer-only quality-concern category
    # must_catch: a gate listed twice in one category
    """ac-validator and ac-fulfillment-gate: in the six categories once each, in none of the three role-restricted ones."""
    _assert_exactly_the_six(fx.shipped_lists("templates/config/feedback_categories.yaml"), _GATES)


def test_restructuring_and_scope_reviewer_are_writers_of_exactly_the_six_categories():
    # covers: INF-100c-5-iv
    # angle: discrimination
    # must_catch: the two agents added to complete only
    # must_catch: the two agents added to a seventh category such as quality-concern
    """restructuring-specialist and change-scope-reviewer: the same six categories once each, none of the three others."""
    _assert_exactly_the_six(fx.shipped_lists("templates/config/feedback_categories.yaml"), fx.NEWLY_REGISTERED)


def test_source_and_template_copies_list_the_same_allowed_writers():
    # covers: INF-100c-5-iv
    # angle: discrimination
    # must_catch: the four agents added to one copy only
    # must_catch: the same agents added to the two copies in a different order
    """config/ and templates/config/ copies: the same nine categories with identical, identically ordered writer lists."""
    source = fx.shipped_lists("config/feedback_categories.yaml")
    template = fx.shipped_lists("templates/config/feedback_categories.yaml")

    assert sorted(source) == sorted(template) == sorted(fx.NINE)
    assert [len(source[c]) for c in fx.NINE] == [len(template[c]) for c in fx.NINE]
    assert all(source[c] for c in fx.SIX), "control: the six broad categories are non-empty, so equality is not vacuous"
    for category in fx.NINE:
        assert source[category] == template[category], f"{category}: the two copies diverge"
