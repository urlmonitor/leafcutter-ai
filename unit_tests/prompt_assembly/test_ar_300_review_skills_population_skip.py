"""AR-300 review finding 3 -- the skills side must treat "nothing declared anywhere" the way
the spawn side does: SKIP, visibly, and let the build proceed.

Today ``agent_ability_gate._verdict_findings`` lets ``verify_abilities`` raise
``EmptyPopulationError("abilities")`` and turns it into a REFUSING finding, whereas
``_spawn_findings`` returns no findings when nothing is permitted. A package with agent
templates and a registry but no ``skills:`` declaration therefore cannot build, while an
equivalent sub-agent-free package can. The verdict function itself keeps raising on zero
(existing tests rely on it) -- only the gate's disposition changes, so this file never asserts
anything about ``verify_abilities``.

AC mapping: AR-300c-3 ("the comparison is made for every agent ... reporting the count examined":
a skipped comparison must say so rather than read as a clean one) for the skip itself;
AR-300c-5-iii for the test that the skip does not swallow a refusing sub-agent finding.

Note for the wiring slice (finding 2): AR-300a-1-i makes an empty DECLARATIONS side a failure of
the compiled-prompt delivery verifier. That is a different comparison (compiled prompt vs
declaration), so these tests drive only the ability gate (``refuse_on_ability_findings``, the
call ``build_main_helpers._run_validation_guards`` makes). If the build-level delivery gate is
wired unconditionally, a skills-free package would still be refused there; that gate needs the
same "nothing declared -> skipped, stated" disposition for finding 3's "builds (exit 0)" to hold
end to end.

RED MAP:
  nothing declared anywhere      -> gate exits 1 ("no abilities examined"); expected exit 0 + skip line
  sub-agents only (no skills)    -> same
  unresolvable sub-agent, no skills -> exits 1 but ONLY about the empty population: the spawn
                                      finding is never computed, so the ghost is not named
Controls (pass today, assert the harness): a package that DOES declare a skill prints no skip line.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import agent_fm, planted_package  # noqa: E402
from _ar_300b_support import BODY, SKILLS, grant, registry_for  # noqa: E402
from _ar_300e_support import records_for, run_gate, sfm, workers  # noqa: E402


def _skip_lines(text: str) -> list[str]:
    """Lines saying the skills comparison was skipped because nothing is declared."""
    out = []
    for line in text.splitlines():
        low = line.lower()
        if "skip" in low and ("skill" in low or "abilit" in low) and ("declar" in low or "nothing" in low):
            out.append(line)
    return out


def _plain_package(base: Path) -> Path:
    templates = {"zz-one": (agent_fm("zz-one"), BODY), "zz-two": (agent_fm("zz-two"), BODY)}
    return planted_package(base, templates, SKILLS, registry_agents=registry_for_plain(templates))


def registry_for_plain(templates: dict) -> list[dict]:
    """Registry rows that claim no ability and no sub-agent (consistent with plain templates)."""
    return [{**r, "spawn_allowlist": [], "skills_invoked": [], "skills_used": []} for r in registry_for(templates)]


def test_ac300c3_package_declaring_no_skills_builds_and_says_the_comparison_was_skipped(tmp_path, capsys):
    # covers: AR-300c-3
    # angle: boundary
    """AR-300c-3: templates + a non-empty registry, no ``skills:`` anywhere -> exit 0 AND a visible
    line saying the skills comparison was skipped because nothing is declared. Control first: one
    skilled agent in an otherwise identical package prints NO such line (the skip is conditional on
    emptiness). Wrong versions caught: refusing (today), and passing in silence (a skip nobody can
    see reads as a clean comparison)."""
    templates = {"zz-one": (agent_fm("zz-one"), BODY), "zz-skilled": (agent_fm("zz-skilled", grant("zz-alpha")), BODY)}
    records = [{**r, "spawn_allowlist": []} for r in registry_for(templates)]
    rc, out = run_gate(planted_package(tmp_path / "ctl", templates, SKILLS, registry_agents=records), capsys)
    assert rc == 0 and not _skip_lines(out), f"control: a declared skill must be compared, not skipped: rc={rc} {out[-500:]}"

    rc, out = run_gate(_plain_package(tmp_path / "plain"), capsys)
    assert rc == 0, f"a package with no skills declared anywhere was refused: {out[-600:]}"
    assert _skip_lines(out), f"the skipped skills comparison is silent (no visible line): {out[-600:]}"


def test_ac300c3_sub_agent_only_package_builds_and_says_the_skills_comparison_was_skipped(tmp_path, capsys):
    # covers: AR-300c-3
    # angle: seam
    """AR-300c-3: a package whose only declarations are sub-agents (the shape the spawn side already
    tolerates in the other direction) passes the gate with exit 0, still compares the sub-agents,
    and states the skills skip. The spawn comparison is proven to have RUN by a registry copy that
    disagrees (reported by name, report-only so it does not refuse). Wrong version caught: a skip
    that also switches the spawn comparison off."""
    templates = {"zz-boss": (sfm("zz-boss", spawn=["zz-worker"]), BODY), **workers("zz-worker")}
    records = records_for(templates, registry_spawn={"zz-boss": []})
    pkg = planted_package(tmp_path / "pkg", templates, SKILLS, registry_agents=records)
    rc, out = run_gate(pkg, capsys)
    assert rc == 0, f"a sub-agents-only package was refused: {out[-600:]}"
    assert _skip_lines(out), f"the skipped skills comparison is silent: {out[-600:]}"
    assert [ln for ln in out.splitlines() if "zz-boss" in ln and "zz-worker" in ln], \
        f"the sub-agent comparison did not run alongside the skip: {out[-600:]}"


def test_ac300c5iii_skipping_the_skills_side_does_not_swallow_an_unresolvable_sub_agent(tmp_path, capsys):
    # covers: AR-300c-5-iii
    # angle: discrimination
    """AR-300c-5-iii: no skills declared AND an agent permitted a sub-agent with no definition ->
    the build still refuses, and the refusal names the declaring agent and the ghost. Today the
    empty-skills raise returns early and the sub-agent finding is never computed, so the refusal
    (if any) is only about the empty population. Wrong version caught: a skip implemented as an
    early return that hides every other finding."""
    templates = {"zz-boss": (sfm("zz-boss", spawn=["zz-ghost"]), BODY)}
    records = records_for(templates)
    pkg = planted_package(tmp_path / "pkg", templates, SKILLS, registry_agents=records)
    rc, out = run_gate(pkg, capsys)
    assert rc == 1, f"an unresolvable sub-agent was not refused: exit {rc}"
    assert [ln for ln in out.splitlines() if "zz-boss" in ln and "zz-ghost" in ln], \
        f"the refusal does not name the agent and the unresolvable sub-agent: {out[-600:]}"
