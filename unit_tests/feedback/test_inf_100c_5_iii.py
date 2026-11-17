"""
MODULE: test_inf_100c_5_iii
GOAL: RED tests for INF-100c-5-iii (KI-FC-003) -- only agents whose definition sets signoff: true are
    required to be feedback writers; an absent field and signoff: false both mean not required.
AC: INF-100c-5-iii. The production contract these tests assume is documented in _inf_100c_5_fixtures.
"""
# @ac-tag: INF-100c-5-iii

from __future__ import annotations

import pytest

from unit_tests.feedback import _inf_100c_5_fixtures as fx

_NON_SIGNERS = ("research-agent", "epic-supervisor", "sql-coder")


@pytest.mark.shared_layout_mutator
def test_build_does_not_fail_on_a_non_signing_off_agent_with_no_category(tmp_path):
    # covers: INF-100c-5-iii
    # angle: reachability
    # must_catch: a check that requires every registered agent to be a writer
    """Real build.py --validate-only: research-agent is listed nowhere and the build passes; the check is proven live."""
    root = fx.copy_package(tmp_path)
    fx.edit_categories(root, fx.compose(fx.register_newly_registered, fx.drop_everywhere("research-agent")))
    cwd = tmp_path / "cwd"
    cwd.mkdir()

    rc, out = fx.validate_only(root, cwd)
    assert rc == 0, f"research-agent signs off nowhere; the build must not fail on its account:\n{out[-2000:]}"
    assert "research-agent" not in "\n".join(fx.report_lines(out)), "research-agent was named by the writer check"

    # liveness control (a different reason to fail): a REAL signing-off agent dropped from every list is caught,
    # and the failure names it but still not research-agent -- so the pass above is not a check that never ran.
    fx.edit_categories(root, fx.drop_everywhere("python-coder"))
    rc_live, out_live = fx.validate_only(root, cwd)
    assert rc_live != 0, f"control: python-coder signs off and is now listed nowhere:\n{out_live[-2000:]}"
    assert "python-coder" in out_live
    assert "research-agent" not in "\n".join(fx.report_lines(out_live))


def test_absent_and_false_signoff_agents_are_never_named_missing(tmp_path):
    # covers: INF-100c-5-iii
    # angle: discrimination
    # must_catch: an absent signoff field read as true
    # must_catch: signoff false read as true because the string is truthy
    # must_catch: a required set widened by is_ticket_phase, tier or tools
    """research-agent (no field), epic-supervisor (false), sql-coder (no field): none missing; a true signer still is."""
    widening = {"tier": "phase", "is_ticket_phase": True, "tools": ["Bash", "Read", "Edit"]}
    world = fx.make_world(
        tmp_path,
        signing=["zz-true-signer"],
        others=[("research-agent", fx._ABSENT), ("epic-supervisor", False), ("sql-coder", fx._ABSENT)],
        lists={"complete": ["zz-listed-elsewhere"]},
        extra_registered=["zz-listed-elsewhere"],
    )
    for name in _NON_SIGNERS:  # rewrite the three with the widening fields a wrong "required" rule might key on
        signoff = False if name == "epic-supervisor" else fx._ABSENT
        fx.write_agent(world.agents_dir, name, signoff, **widening)

    result = fx.run_check(world)

    assert result["missing_writers"] == ["zz-true-signer"], "exactly the signoff: true agent, and no other"
    for name in _NON_SIGNERS:
        assert name not in fx.failure_text(result), f"{name} does not sign off but was named"

    # malformed value: reported naming its file, never guessed as true or false
    fx.write_agent(world.agents_dir, "zz-malformed", "maybe")
    fx.write_registry(world.registry_path, [*_NON_SIGNERS, "zz-true-signer", "zz-listed-elsewhere", "zz-malformed"])
    malformed = fx.run_check(world)
    assert any("zz-malformed.md" in f for f in malformed["failures"]), (
        f"a non-boolean signoff must be reported naming its definition file: {malformed['failures']}"
    )
    assert "zz-malformed" not in malformed["missing_writers"], "a malformed signoff must not be guessed as true"


def test_listed_non_signing_off_agents_are_still_known_agents(tmp_path):
    # covers: INF-100c-5-iii
    # angle: discrimination
    # must_catch: a known-agent set built from the signing-off agents only
    """epic-supervisor and sql-coder are listed, registered, and sign off nowhere: not unknown. A stray name still is."""
    world = fx.make_world(
        tmp_path,
        signing=["python-coder"],
        others=[("epic-supervisor", False), "sql-coder"],
        lists={"complete": ["python-coder", "sql-coder"], "tooling-issue": ["epic-supervisor", "zz-never-registered"]},
    )

    result = fx.run_check(world)

    assert result["unknown_writers"] == [{"writer": "zz-never-registered", "categories": ["tooling-issue"]}]
    assert result["missing_writers"] == []
    reported = " ".join(result["warnings"])
    assert "epic-supervisor" not in reported and "sql-coder" not in reported
