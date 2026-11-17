"""AR-300b-1-iii -- once the sub-agent section is delivered, a compiled prompt missing it
fails the build through the SAME gate as a missing abilities section: the section is a
REGISTERED preparation (``spawn_allowlist``), never a name written into the gate, and an
agent permitted no sub-agents registers nothing so it can never be reported.

Source of truth: .../AR-300b-1-iii.yaml. Contract: slice 3 (``_ar_300b_support.py``) --
``compute_preparation`` / ``register_preparation(preparation_name='spawn_allowlist', agent,
content, destination_offered=True)``, ``verify_preparations_delivered`` (ONE verdict) and the
build seam ``refuse_on_undelivered_preparations`` -- plus _ar_300e_support.py item 2.
Tests that strip a section mutate COPIES / the in-process build output, never the shared
reference layout, and never spawn a build.py.

RED BASELINE (slice 5): nothing registers a ``spawn_allowlist`` preparation, so the first
control assertion of every test fails (assertion red).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import strip_delivered_sections  # noqa: E402
from _ar_300b_support import abilities_preps, copy_roots, grant  # noqa: E402
from _ar_300e_support import (  # noqa: E402
    BODY,
    fresh_spawn_build,
    prep_module,
    real_build_prompts,
    sfm,
    source_templates,
    spawn_registrations,
    strip_spawn_sections,
    workers,
)

CONFIG = {"output_root": ".leafcutter"}


def _templates() -> dict:
    return {"zz-a": (sfm("zz-a", ["zz-w1"]), BODY),
            "zz-b": (sfm("zz-b", ["zz-w1", "zz-w2"]), BODY),
            "zz-g": (sfm("zz-g", ["zz-w1"], skills=grant("zz-alpha")), BODY),
            "zz-n": (sfm("zz-n"), BODY), "zz-e": (sfm("zz-e", []), BODY), **workers("zz-w1", "zz-w2")}


def _rewrite(path: Path, edit) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(edit(text), encoding="utf-8")
    assert path.read_text(encoding="utf-8") != text, f"control: {path} had nothing to strip"


def test_missing_sub_agent_section_in_one_root_fails_naming_agent_preparation_root(tmp_path, monkeypatch, capsys):
    # covers: AR-300b-1-iii
    # angle: deployed
    """AR-300b-1-iii: with ONE permitted agent's sub-agent section stripped from its
    gemini-root compiled prompt only (declaration and registry copy both correct), the
    verdict has a finding naming that agent, preparation ``spawn_allowlist`` and that platform
    root, and the build seam returns 1. Control: before the strip the same seam returns 0."""
    templates = _templates()
    mod, _pkg, roots, preps = fresh_spawn_build(tmp_path, monkeypatch, templates)
    assert {p["agent"] for p in spawn_registrations(preps)} == {"zz-a", "zz-b", "zz-g"}, "control: nothing registered"
    project, expected = tmp_path / "project", len(templates) * len(roots)
    assert mod.refuse_on_undelivered_preparations(project, CONFIG, False, expected_prompt_count=expected) == 0
    capsys.readouterr()
    _rewrite(roots[1] / "zz-b.md", strip_spawn_sections)
    verdict = mod.verify_preparations_delivered(list(roots), expected_prompt_count=expected, preparations=preps)
    hits = [(f["agent"], f["preparation"], f["platform_root"]) for f in verdict["findings"] if "agent" in f]
    assert verdict["ok"] is False and hits == [("zz-b", "spawn_allowlist", str(roots[1]))], hits
    assert mod.refuse_on_undelivered_preparations(project, CONFIG, False, expected_prompt_count=expected) == 1
    printed = capsys.readouterr()
    assert "zz-b" in printed.out + printed.err and "spawn_allowlist" in printed.out + printed.err


def test_sub_agent_and_abilities_findings_come_from_the_same_verdict(tmp_path, monkeypatch):
    # covers: AR-300b-1-iii
    # angle: discrimination
    """AR-300b-1-iii: stripping BOTH an abilities section and a sub-agent section from one
    agent yields BOTH findings in ONE ``verify_preparations_delivered`` verdict, and renaming
    the spawn preparation in the registration alone changes the reported name with no edit to
    the gate. Wrong versions caught: a spawn-specific check written beside the generic gate;
    a gate iterating a hard-coded list of preparation names."""
    templates = _templates()
    mod, _pkg, roots, preps = fresh_spawn_build(tmp_path, monkeypatch, templates)
    abilities = abilities_preps(preps, "zz-g", "zz-alpha")
    assert abilities and spawn_registrations([p for p in preps if p["agent"] == "zz-g"]), "control: both registered"
    copies = copy_roots(roots, tmp_path / "copies")
    _rewrite(copies[0] / "zz-g.md", lambda t: strip_spawn_sections(strip_delivered_sections(t)))
    expected = len(templates) * len(copies)
    verdict = mod.verify_preparations_delivered(copies, expected_prompt_count=expected, preparations=preps)
    names = {f["preparation"] for f in verdict["findings"] if f.get("agent") == "zz-g"}
    assert names == {"spawn_allowlist", abilities[0]["preparation_name"]}, names
    renamed = [dict(p, preparation_name="zz_renamed_spawn") if p["preparation_name"] == "spawn_allowlist" else p
               for p in preps]
    again = mod.verify_preparations_delivered(copies, expected_prompt_count=expected, preparations=renamed)
    assert {f["preparation"] for f in again["findings"] if f.get("agent") == "zz-g"} == \
        {"zz_renamed_spawn", abilities[0]["preparation_name"]}


def test_clean_run_counts_spawn_allowlist_among_preparation_kinds(tmp_path, monkeypatch):
    # covers: AR-300b-1-iii
    # angle: real_artifact
    """AR-300b-1-iii: on a compiled tree where every permitted agent carries its section --
    a planted package AND the REAL templates built in-process -- the verdict has no
    ``spawn_allowlist`` finding and lists ``spawn_allowlist`` among the preparation kinds it
    examined (counted in ``inspected_preparation_kinds``)."""
    templates = _templates()
    mod, _pkg, roots, preps = fresh_spawn_build(tmp_path / "planted", monkeypatch, templates)
    verdict = mod.verify_preparations_delivered(list(roots), expected_prompt_count=len(templates) * 2, preparations=preps)
    assert verdict["ok"] is True, verdict["findings"]
    assert "spawn_allowlist" in verdict["preparation_kinds"]
    assert verdict["inspected_preparation_kinds"] == len(verdict["preparation_kinds"])
    real_roots, real_preps = real_build_prompts(tmp_path / "real", monkeypatch)
    real = prep_module().verify_preparations_delivered(
        list(real_roots), expected_prompt_count=len(source_templates()) * 2, preparations=real_preps)
    assert "spawn_allowlist" in real["preparation_kinds"], real["preparation_kinds"]
    assert not [f for f in real["findings"] if f.get("preparation") == "spawn_allowlist"]


def test_agent_permitted_no_sub_agents_is_not_reported(tmp_path, monkeypatch):
    # covers: AR-300b-1-iii
    # angle: failure
    """AR-300b-1-iii: an agent with no ``spawn_allowlist`` (and one with ``[]``) has NO
    registered spawn preparation and produces no finding although its compiled prompt has no
    section; the declaring agents DO register (control), so the quiet is not a dead gate. The
    exemption is the absence of a registration, not a filter inside the gate."""
    templates = _templates()
    mod, _pkg, roots, preps = fresh_spawn_build(tmp_path, monkeypatch, templates)
    registered = {p["agent"] for p in spawn_registrations(preps)}
    assert registered == {"zz-a", "zz-b", "zz-g"}, f"registered agents: {sorted(registered)}"
    assert not registered & {"zz-n", "zz-e"}
    verdict = mod.verify_preparations_delivered(list(roots), expected_prompt_count=len(templates) * 2, preparations=preps)
    assert not [f for f in verdict["findings"] if f.get("agent") in {"zz-n", "zz-e"}]
    for root in roots:
        for stem in ("zz-n", "zz-e"):
            assert "Sub-Agents" not in (root / f"{stem}.md").read_text(encoding="utf-8")
