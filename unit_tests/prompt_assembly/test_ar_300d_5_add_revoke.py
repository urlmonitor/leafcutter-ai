"""AR-300d-5 -- a sub-agent permission granted or revoked in an agent's declaration takes
effect on the next build, with no second edit and no marker: derived afresh on every
compile (also over a STALE compiled tree), per agent not per sub-agent, and a brand-new
agent that only declares receives its section on its first build.

Source of truth: .../AR-300d-5.yaml. Fixture package: planted agents (frontmatter by
yaml.safe_dump), built with the REAL ``build_agents`` phase in-process; add / revoke =
rewriting ONE template's declaration.

  zz-holder-a  permits w1, w2   -> w3 is added, then w2 is revoked, from THIS agent only
  zz-holder-b  permits w2       -> must still name w2 throughout
  zz-holder-c  permits w3       -> must stay byte-identical when a-gains-w3
  zz-plain     permits nothing  -> must stay byte-identical

RED BASELINE (slice 5): nothing delivers a section from the declaration, so the very
first control assertion (the holder names its declared sub-agents) fails.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300e_support import (  # noqa: E402
    BODY,
    build_in,
    drop_registry_records,
    edit_declaration,
    named_sub_agents,
    read_prompts,
    sfm,
    spawn_package,
    workers,
    write_template,
)

TEMPLATES = {
    "zz-holder-a": (sfm("zz-holder-a", ["zz-w1", "zz-w2"]), BODY),
    "zz-holder-b": (sfm("zz-holder-b", ["zz-w2"]), BODY),
    "zz-holder-c": (sfm("zz-holder-c", ["zz-w3"]), BODY),
    "zz-plain": (sfm("zz-plain"), BODY),
    **workers("zz-w1", "zz-w2", "zz-w3"),
}
KNOWN = set(TEMPLATES) | {"zz-newcomer", "zz-norow"}


def _built(tmp_path: Path, monkeypatch):
    pkg = spawn_package(tmp_path / "slice", TEMPLATES)
    out = tmp_path / "out"
    return pkg, out, build_in(pkg, out, monkeypatch)


def _named(root: Path, stem: str) -> set[str]:
    return named_sub_agents((root / f"{stem}.md").read_text(encoding="utf-8"), KNOWN)


def test_sub_agent_added_to_declaration_appears_on_next_compile(tmp_path, monkeypatch):
    # covers: AR-300d-5
    # angle: criterion
    """AR-300d-5: one sub-agent added to an existing agent's declaration (and nothing else)
    makes its compiled prompt, in BOTH roots, name it beside the ones it already named.
    Control: before the edit the prompt named exactly the first two."""
    pkg, out, roots = _built(tmp_path, monkeypatch)
    for root in roots:
        assert _named(root, "zz-holder-a") == {"zz-w1", "zz-w2"}
    edit_declaration(pkg, "zz-holder-a", ["zz-w1", "zz-w2", "zz-w3"])
    roots = build_in(pkg, out, monkeypatch)
    assert len(roots) == 2
    for root in roots:
        assert _named(root, "zz-holder-a") == {"zz-w1", "zz-w2", "zz-w3"}


def test_sub_agent_removed_from_declaration_vanishes_over_a_stale_compiled_tree(tmp_path, monkeypatch):
    # covers: AR-300d-5
    # angle: discrimination
    """AR-300d-5: removing one sub-agent from the declaration ONLY, then compiling INTO the
    directory that already holds the previous build, leaves no mention of it anywhere in that
    agent's prompt (not merely in the section); a further rebuild with nothing changed is
    byte-stable. Control: the stale prompt DID name it. Wrong version caught: the compiler
    patches or appends into the existing compiled prompt instead of regenerating it."""
    pkg, out, roots = _built(tmp_path, monkeypatch)
    stale = {r: (r / "zz-holder-a.md").read_text(encoding="utf-8") for r in roots}
    assert all("zz-w2" in t for t in stale.values()), "control: the stale tree holds the old permission"
    assert all(_named(r, "zz-holder-a") == {"zz-w1", "zz-w2"} for r in roots)
    edit_declaration(pkg, "zz-holder-a", ["zz-w1"])
    build_in(pkg, out, monkeypatch)
    after = {r: (r / "zz-holder-a.md").read_text(encoding="utf-8") for r in roots}
    for root, text in after.items():
        assert "zz-w2" not in text, f"trace of the revoked sub-agent in {root}"
        assert _named(root, "zz-holder-a") == {"zz-w1"}
    build_in(pkg, out, monkeypatch, allow_unchanged=True)
    assert {r: (r / "zz-holder-a.md").read_text(encoding="utf-8") for r in roots} == after


def test_no_other_agents_compiled_prompt_changes_on_add_or_revoke(tmp_path, monkeypatch):
    # covers: AR-300d-5
    # angle: discrimination
    """AR-300d-5: across the add AND the revoke every other compiled prompt -- including
    another agent permitted the same sub-agent (zz-holder-b keeps w2, zz-holder-c is permitted
    the w3 that holder-a gains) -- is byte-identical in both roots. Wrong version caught: the
    section computed from a shared structure rather than per agent."""
    pkg, out, roots = _built(tmp_path, monkeypatch)
    base = {r: read_prompts(r) for r in roots}
    others = [s for s in TEMPLATES if s != "zz-holder-a"]
    edit_declaration(pkg, "zz-holder-a", ["zz-w1", "zz-w2", "zz-w3"])
    build_in(pkg, out, monkeypatch)
    compared = 0
    for root in roots:
        after_add = read_prompts(root)
        assert _named(root, "zz-holder-a") == {"zz-w1", "zz-w2", "zz-w3"}, "control: the add did not happen"
        for stem in others:
            compared += 1
            assert after_add[stem] == base[root][stem], f"{stem} changed on the add in {root}"
    edit_declaration(pkg, "zz-holder-a", ["zz-w1", "zz-w3"])
    build_in(pkg, out, monkeypatch)
    for root in roots:
        after_revoke = read_prompts(root)
        assert _named(root, "zz-holder-a") == {"zz-w1", "zz-w3"}, "control: the revoke did not happen"
        for stem in others:
            compared += 1
            assert after_revoke[stem] == base[root][stem], f"{stem} changed on the revoke in {root}"
        assert "zz-w2" in _named(root, "zz-holder-b")
    assert compared == 2 * 2 * len(others)


def test_new_agent_with_only_a_declaration_receives_its_section_on_first_compile(tmp_path, monkeypatch):
    # covers: AR-300d-5
    # angle: seam
    """AR-300d-5: a NEW template carrying only a ``spawn_allowlist`` declaration -- no
    registry entry for it, no list of agents to include, no marker in its body -- receives its
    section on its very first build, naming a sub-agent that has no registry row either (the
    optional columns tolerate a missing row; naming never depends on them). Wrong version
    caught: a marker per template, or a registry-gated section."""
    pkg, out, _roots = _built(tmp_path, monkeypatch)
    write_template(pkg / "templates" / "agents" / "zz-newcomer.md",
                   sfm("zz-newcomer", ["zz-w1", "zz-norow"]), BODY)
    write_template(pkg / "templates" / "agents" / "zz-norow.md", sfm("zz-norow", tools="Bash, Read"), BODY)
    drop_registry_records(pkg, "zz-newcomer", "zz-norow")
    roots = build_in(pkg, out, monkeypatch)
    assert len(roots) == 2
    for root in roots:
        text = (root / "zz-newcomer.md").read_text(encoding="utf-8")
        assert "{{" not in text and "my_spawn_allowlist" not in text
        assert named_sub_agents(text, KNOWN) == {"zz-w1", "zz-norow"}
