"""AR-300 review finding 2 -- the BUILD must consume the grant-delivery verification.

``agent_grant_delivery.verify_grants_delivered`` reads the compiled prompts and finds a short
section, an ability that was not granted, an ungranted agent carrying a section, or a second
account. It has no production caller, so none of those reach the build's exit status. AR-300a-1
it_requirements: "The authoritative gate is the delivery verification that reads the compiled
prompts" and "Failure refuses rather than warns -- the build reports failure and exits non-zero".

Each test runs the layout's OWN build.py in a subprocess over a PRIVATE copy of the deployed
layout (``shared_layout_mutator``), through a wrapper that breaks ONLY the compiler's delivery of
the abilities section for one named agent (the way ``_ar_300ad_support``'s mutations do), so the
compiler's own correctness is not what is under test: the build-level gate is. The preparation
gate (AR-300b) cannot catch these -- it compares what was registered to the prompt, and the
wrapper registers the same (wrong) text it delivers. The wrapper prints ``AR300R-MUTATED`` when
the mutation fired; a test fails with a harness message if it did not (no vacuous refusals).

SECOND ACCOUNT (decision). AR-300a-4 requires one account per prompt and that a second one is
"caught rather than accumulated"; AR-300a-4-i (the source-side detector) says a duplicate (same
abilities) is "merely a duplicate" and must not block a mid-migration tree, while a contradiction
is the real defect. So: a second account that CONTRADICTS (names an ungranted ability, or omits a
granted one) refuses -- it is already an extra-ability / short-section failure; a second account
that merely DUPLICATES the declaration is REPORTED by name and the build still exits 0. The
duplicate test pins that choice; the contradiction case is covered by the extra-ability test.

AC mapping: AR-300a-1 (short section, named ability missing), AR-300a-3 ("none carrying a section
that names fewer abilities" / ungranted agent carries none), AR-300a-4 (extra ability; duplicate
account reported).

RED MAP: each refusal test fails today on ``returncode != 0`` (the build exits 0 -- nothing consumes
the verdict); the duplicate test fails on the missing report line.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import REPO_ROOT, installed_skill_ids, real_declarations, source_templates  # noqa: E402

MARK = "AR300R-MUTATED"

WRAPPER = '''
import json, os, runpy, sys
build = sys.argv[1]
sys.path.insert(0, os.path.dirname(build))
import agent_declared_sections as ads
import build_phases  # noqa: F401
from agent_ability_verdict import normalize_entries
cfg = json.loads(os.environ["AR300R_CFG"])
_orig = ads.append_declared_skills
_ROW = "| %s | always | injected by the review wrapper |"
def patched(body, fm, skills_root, agent=None):
    if agent != cfg["victim"]:
        return _orig(body, fm, skills_root, agent=agent)
    mode, entries = cfg["mode"], normalize_entries(fm.get("skills"))
    print("AR300R-MUTATED %s %s" % (agent, mode), flush=True)
    if mode == "short":
        return _orig(body, {**fm, "skills": entries[:-1]}, skills_root, agent=agent)
    if mode == "extra":
        return _orig(body, {**fm, "skills": entries + [{"skill_id": cfg["extra"], "mode": "always"}]},
                     skills_root, agent=agent)
    if mode == "ungranted":
        head = "## Your Available Skills\\n\\n| Skill | Mode | Description |\\n|---|---|---|\\n"
        return body.rstrip("\\n") + "\\n\\n" + head + _ROW % cfg["extra"] + "\\n"
    out = _orig(body, fm, skills_root, agent=agent)
    return out.rstrip("\\n") + "\\n\\n" + out[out.rindex("## Your Available Skills"):]
ads.append_declared_skills = patched
sys.argv = sys.argv[1:]
runpy.run_path(build, run_name="__main__")
'''


def _ids(entries: list) -> list[str]:
    return [e if isinstance(e, str) else e["skill_id"] for e in entries]


def _plan(kind: str) -> dict:
    """Pick the victim (and any extra ability) from the REAL tree by parsing, never by name."""
    declared = {stem: _ids(entries) for stem, entries in sorted(real_declarations().items())}
    installed = installed_skill_ids(REPO_ROOT)
    if kind == "ungranted":
        stems = sorted({t.stem for t in source_templates()} - set(declared))
        return {"victim": stems[0], "mode": kind, "extra": sorted(installed)[0]}
    victim = next(stem for stem, ids in declared.items() if len(ids) >= 2)
    extra = sorted(installed - set(declared[victim]))[0]
    return {"victim": victim, "mode": kind, "extra": extra, "ids": declared[victim], "last": declared[victim][-1]}


def _build(layout: Path, work: Path, plan: dict) -> tuple[subprocess.CompletedProcess, str]:
    wrapper = work / "wrapper_break_one_section.py"
    wrapper.write_text(WRAPPER, encoding="utf-8")
    env = {**os.environ, "AR300R_CFG": json.dumps(plan)}
    proc = subprocess.run([sys.executable, str(wrapper), str(layout / "scripts" / "build.py"), "--target-dir",
                           str(layout)], cwd=str(layout), capture_output=True, text=True, timeout=480,
                          check=False, env=env)
    out = proc.stdout + "\n" + proc.stderr
    assert f"{MARK} {plan['victim']} {plan['mode']}" in out, f"harness: the mutation never fired: {out[-700:]}"
    return proc, out


def _named(out: str, *needles: str) -> list[str]:
    return [ln for ln in out.splitlines() if all(n in ln for n in needles)]


@pytest.mark.shared_layout_mutator
def test_ac300a1_build_refuses_when_a_compiled_section_is_short(shared_reference_layout, tmp_path):
    # covers: AR-300a-1
    # angle: reachability
    """AR-300a-1: the compiler is made to drop the LAST granted ability from one agent's section.
    The build exits non-zero, and a line names that agent and the missing ability. Wrong versions
    caught: a verifier nothing calls (today: exit 0); a gate that only warns; a refusal that does
    not say which ability is missing."""
    plan = _plan("short")
    proc, out = _build(shared_reference_layout, tmp_path, plan)
    assert proc.returncode != 0, f"a build whose {plan['victim']} section lacks {plan['last']} exited 0"
    assert _named(out, plan["victim"], plan["last"]), f"no line names {plan['victim']} and {plan['last']}: {out[-900:]}"


@pytest.mark.shared_layout_mutator
def test_ac300a4_build_refuses_when_a_section_names_an_ability_not_granted(shared_reference_layout, tmp_path):
    # covers: AR-300a-4
    # angle: reachability
    """AR-300a-4: one agent's section names an installed ability its declaration does not grant.
    The build exits non-zero and a line names the agent and the extra ability. Wrong version
    caught: a one-directional (subset) check that only notices missing abilities."""
    plan = _plan("extra")
    proc, out = _build(shared_reference_layout, tmp_path, plan)
    assert proc.returncode != 0, f"a build whose {plan['victim']} section names ungranted {plan['extra']} exited 0"
    assert _named(out, plan["victim"], plan["extra"]), f"no line names {plan['victim']} and {plan['extra']}: {out[-900:]}"


@pytest.mark.shared_layout_mutator
def test_ac300a3_build_refuses_when_an_ungranted_agent_carries_an_abilities_section(shared_reference_layout, tmp_path):
    # covers: AR-300a-3
    # angle: reachability
    """AR-300a-3: an agent that declares no grant ends up with an abilities section. The build
    exits non-zero and a line names the agent. Wrong version caught: a gate that only checks
    granted agents (the negative population is the one the unconditional-append shape corrupts)."""
    plan = _plan("ungranted")
    proc, out = _build(shared_reference_layout, tmp_path, plan)
    assert proc.returncode != 0, f"a build whose ungranted {plan['victim']} carries a section exited 0"
    assert _named(out, plan["victim"], plan["extra"]), f"no line names {plan['victim']} and {plan['extra']}: {out[-900:]}"


@pytest.mark.shared_layout_mutator
def test_ac300a4_build_reports_a_duplicate_second_account_by_name_without_refusing(shared_reference_layout, tmp_path):
    # covers: AR-300a-4
    # angle: discrimination
    """AR-300a-4 / AR-300a-4-i: the same section appears twice in one prompt (identical abilities,
    so a duplicate, not a contradiction). The build STILL exits 0 -- a mid-migration tree must
    build -- but a line names the agent and says second/duplicate account, so the property is
    caught rather than accumulated. Wrong versions caught: silence (today); refusing a mere
    duplicate (blocks the tree the AC says must stay buildable)."""
    plan = _plan("duplicate")
    proc, out = _build(shared_reference_layout, tmp_path, plan)
    assert proc.returncode == 0, f"a duplicate account refused the build (it must only be reported): {out[-700:]}"
    # The compile-time SOURCE detector already prints "<template> states its own ..." lines (it
    # matches today on real templates), so those are excluded: the report asked for here is about
    # the COMPILED prompt carrying two accounts, and must say so ("second-account", "two accounts").
    hits = [ln for ln in _named(out, plan["victim"])
            if "states its own" not in ln and "account" in ln.lower()
            and any(w in ln.lower() for w in ("second", "duplicate", "two"))]
    assert hits, f"the duplicate second account of {plan['victim']} is not reported by name: {out[-900:]}"
