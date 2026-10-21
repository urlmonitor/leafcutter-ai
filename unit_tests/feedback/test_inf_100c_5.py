"""
MODULE: test_inf_100c_5
GOAL: RED tests for INF-100c-5 (KI-FC-003) -- the build fails when an agent that signs off is in
    no feedback category's allowed_writers, and the one failure names every such agent.
AC: INF-100c-5. The production contract these tests assume is documented in _inf_100c_5_fixtures.
"""
# @ac-tag: INF-100c-5

from __future__ import annotations

import json

import pytest

from unit_tests.feedback import _inf_100c_5_fixtures as fx

_LISTED_SIGNER = "python-coder"


def _lone_signer_world(tmp_path, signer):
    """Only ``signer`` is unlisted; a listed signer and two non-signing agents are the controls."""
    return fx.make_world(
        tmp_path,
        signing=[signer, _LISTED_SIGNER],
        others=["research-agent", ("epic-supervisor", False)],
        lists={"complete": [_LISTED_SIGNER, "research-agent"], "blocker": [_LISTED_SIGNER]},
    )


def _two_missing_world(tmp_path, names):
    """Unlisted signers written in REVERSE sorted order, one listed signer as the control."""
    return fx.make_world(
        tmp_path,
        signing=[*sorted(names, reverse=True), _LISTED_SIGNER],
        lists={"complete": [_LISTED_SIGNER], "blocker": [_LISTED_SIGNER]},
    )


@pytest.mark.shared_layout_mutator
def test_validate_only_build_exits_nonzero_when_a_signing_off_agent_has_no_category(tmp_path):
    # covers: INF-100c-5
    # angle: reachability
    """The real build.py --validate-only, over a package copy, fails before reporting success."""
    root = fx.copy_package(tmp_path)
    fx.edit_categories(root, fx.compose(fx.register_newly_registered, fx.drop_everywhere("restructuring-specialist")))
    cwd = tmp_path / "cwd"
    cwd.mkdir()

    rc, out = fx.validate_only(root, cwd)

    assert rc != 0, f"the build must fail when restructuring-specialist signs off but is listed nowhere:\n{out[-1500:]}"
    assert not fx.success_line_printed(out), "the build reported success despite the omission"
    assert "restructuring-specialist" in out, f"the failure must name the agent:\n{out[-1500:]}"

    # control, passing for a different reason: with both agents registered the SAME copy validates
    fx.edit_categories(root, fx.register_newly_registered)
    rc_ok, out_ok = fx.validate_only(root, cwd)
    assert rc_ok == 0, f"control: the registered copy must pass validation:\n{out_ok[-1500:]}"
    assert fx.success_line_printed(out_ok)


def test_failure_message_names_the_signing_off_agent_with_no_category(tmp_path):
    # covers: INF-100c-5
    # angle: discrimination
    # must_catch: a check that reads signoff from config/agent_registry.json, which carries no signoff flags, and so names nobody
    # must_catch: a check that joins the wrong way round and names a listed agent instead of the unlisted one
    # must_catch: a check with the agent names or the count of 24 hard-coded
    """Only restructuring-specialist signs off unlisted; it, and no other agent, is named."""
    world = _lone_signer_world(tmp_path, "restructuring-specialist")
    assert "signoff" not in world.registry_path.read_text(encoding="utf-8"), "fixture: the registry carries no signoff flags"

    result = fx.run_check(world)

    assert result["missing_writers"] == ["restructuring-specialist"]
    assert len(result["failures"]) == 1, result["failures"]
    text = fx.failure_text(result)
    assert "restructuring-specialist" in text
    assert "signs off" in text.lower() and "no feedback category" in text.lower(), text
    for bystander in (_LISTED_SIGNER, "research-agent", "epic-supervisor"):
        assert bystander not in text, f"{bystander} is not a violation but was named: {text}"

    # a different name, a different roster size: nothing about the roster is hard-coded
    novel = fx.run_check(_lone_signer_world(tmp_path / "second", "zz-novel-signer"))
    assert novel["missing_writers"] == ["zz-novel-signer"]
    assert "zz-novel-signer" in fx.failure_text(novel)
    assert "restructuring-specialist" not in fx.failure_text(novel)


def test_one_failure_message_names_every_missing_agent_sorted(tmp_path):
    # covers: INF-100c-5
    # angle: discrimination
    # must_catch: a check that raises on the first missing agent and never names the second
    # must_catch: a check that emits one message per agent so the first message names only one
    # must_catch: a check that lists the agents in directory order instead of sorted order
    """restructuring-specialist and change-scope-reviewer both missing: one message, both names, sorted, stable."""
    world = _two_missing_world(tmp_path, list(fx.NEWLY_REGISTERED))
    before = fx.tree_bytes(tmp_path)

    first = fx.run_check(world)
    second = fx.run_check(world)

    assert first["missing_writers"] == ["change-scope-reviewer", "restructuring-specialist"]
    assert len(first["failures"]) == 1, f"one message for all violations, got {first['failures']}"
    text = fx.failure_text(first)
    assert text.index("change-scope-reviewer") < text.index("restructuring-specialist"), text
    assert _LISTED_SIGNER not in text
    assert json.dumps(first).encode() == json.dumps(second).encode(), "two runs on the same inputs must be byte-identical"
    assert fx.tree_bytes(tmp_path) == before, "the check must be read-only"

    # six unlisted signers, written in reverse order, still come out sorted in the list AND the message
    names = [f"zz-signer-{c}" for c in "fecbad"]
    wide = fx.run_check(_two_missing_world(tmp_path / "wide", names))
    assert wide["missing_writers"] == sorted(names)
    positions = [fx.failure_text(wide).index(n) for n in sorted(names)]
    assert positions == sorted(positions), "the message must list the agents in sorted order"
    assert len(wide["failures"]) == 1


def test_check_passes_once_both_agents_are_added_to_complete(tmp_path):
    # covers: INF-100c-5
    # angle: criterion
    """Adding the two agents to the complete category alone clears missing_writers and the failure."""
    world = _two_missing_world(tmp_path, list(fx.NEWLY_REGISTERED))
    broken = fx.run_check(world)
    assert broken["missing_writers"] == ["change-scope-reviewer", "restructuring-specialist"], "control: the fixture must start broken"

    fx.write_categories(
        world.categories_path,
        {"complete": [_LISTED_SIGNER, *fx.NEWLY_REGISTERED], "blocker": [_LISTED_SIGNER]},
    )
    fixed = fx.run_check(world)

    assert fixed["missing_writers"] == []
    assert fixed["failures"] == []
