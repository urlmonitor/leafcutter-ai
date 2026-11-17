"""
MODULE: test_inf_100c_5_ii
GOAL: RED tests for INF-100c-5-ii (KI-FC-003) -- the hook sentinel is neither reported as an unknown
    writer nor credited to any agent, and neither categories file documents a sentinel submission
    does not implement (the removed [all_agents] comment).
AC: INF-100c-5-ii. The production contract these tests assume is documented in _inf_100c_5_fixtures.
"""
# @ac-tag: INF-100c-5-ii

from __future__ import annotations

import re

import pytest

from tests.conftest import load_fixture
from unit_tests.feedback import _inf_100c_5_fixtures as fx

_SOURCE_COPY = "config/feedback_categories.yaml"
_TEMPLATE_COPY = "templates/config/feedback_categories.yaml"
_MISSPELT = "ac-validater"


def _hook_reports(output: str) -> list[str]:
    return [ln for ln in fx.report_lines(output) if re.search(r"\bhook\b", ln)]


def _subsequence(small: list[str], big: list[str]) -> bool:
    it = iter(big)
    return all(item in it for item in small)


@pytest.mark.shared_layout_mutator
def test_hook_in_process_finding_is_not_reported_as_unknown_by_the_build(tmp_path):
    # covers: INF-100c-5-ii
    # angle: reachability
    # must_catch: a check that treats every writer not in the registry as unknown and so flags hook on every build
    # must_catch: a check with its own hard-coded sentinel list that is not taken from submission's rule
    """Real build.py --validate-only: process-finding stays [hook] and hook is never reported; a variant proves the report is live."""
    root = fx.copy_package(tmp_path)
    fx.edit_categories(root, fx.register_newly_registered)
    cwd = tmp_path / "cwd"
    cwd.mkdir()

    rc, out = fx.validate_only(root, cwd)
    assert rc == 0, f"control: the registered copy must validate:\n{out[-1500:]}"
    assert _hook_reports(out) == [], f"hook was reported as a writer that names no agent: {_hook_reports(out)}"

    fx.edit_categories(root, fx.add_to("process-finding", _MISSPELT))
    rc_live, out_live = fx.validate_only(root, cwd)
    live = [ln for ln in fx.report_lines(out_live) if _MISSPELT in ln]
    assert len(live) == 1, f"the unknown-writer report must be live for the variant:\n{out_live[-2000:]}"
    assert "process-finding" in live[0]
    assert _hook_reports(out_live) == [], "hook must still be omitted beside a misspelt name"
    assert rc_live == 0


def test_hook_credits_no_signing_off_agent(tmp_path):
    # covers: INF-100c-5-ii
    # angle: discrimination
    # must_catch: a check that treats hook as a wildcard crediting every signing-off agent
    # must_catch: a check that credits an agent through a sentinel that submission would reject
    """process-finding is [hook]; the signer listed in no other category is still missing, the listed one is not."""
    world = fx.make_world(
        tmp_path,
        signing=["python-coder", "zz-lonely-signer"],
        lists={"complete": ["python-coder"], "process-finding": ["hook"]},
    )

    result = fx.run_check(world)

    assert result["missing_writers"] == ["zz-lonely-signer"]
    assert "zz-lonely-signer" in fx.failure_text(result)
    assert result["unknown_writers"] == [], "hook is a sentinel, not an unknown writer"
    assert not any("hook" in w for w in result["warnings"])


def test_neither_copy_of_the_categories_file_documents_all_agents():
    # covers: INF-100c-5-ii
    # angle: discrimination
    # must_catch: the all_agents comment removed from one copy but left in the other
    # must_catch: the comment reworded so it still offers a sentinel submission does not honour
    # must_catch: the comment removal also dropping an allowed_writers entry
    """Both shipped copies: no all_agents text, the [hook] note kept, and no allowed_writers entry lost."""
    pre_edit = load_fixture("inf_100c_5_ii/pre_edit_allowed_writers")
    assert sorted(pre_edit) == sorted(fx.NINE), "fixture: the nine categories of the pre-edit file"
    for relative in (_SOURCE_COPY, _TEMPLATE_COPY):
        text = (fx.REPO_ROOT / relative).read_text(encoding="utf-8")
        header = text.split("\ncategories:", 1)[0]  # the schema comment; the decision history may name the removal
        comments = [ln for ln in header.splitlines() if ln.lstrip().startswith("#")]
        assert "\ncategories:" in text, f"{relative}: fixture sanity, the file must carry its categories key"
        assert not re.search(r"all[_ -]?agents", header, re.IGNORECASE), f"{relative} still documents the all_agents sentinel"
        assert any("[hook]" in ln for ln in comments), f"{relative} lost the [hook] note"
        now = fx.shipped_lists(relative)
        assert sorted(now) == sorted(pre_edit), f"{relative} changed its category set"
        for category, before in pre_edit.items():
            assert _subsequence(before, now[category]), (
                f"{relative}: {category} lost or reordered an entry of its pre-edit list {before}: {now[category]}"
            )
        assert now["process-finding"] == ["hook"], f"{relative}: process-finding must stay [hook]"
