"""AR-300d-5-i -- a newly added ticket-phase agent is permitted to every agent holding the
ticket-phase entry with NO edit to those agents: the macro is a standing rule resolved
afresh on every build from the CURRENT ``is_ticket_phase`` flags; un-marking removes the
agent from every macro holder's section and from nowhere else; an agent never marked is
never named through the entry.

Source of truth: .../AR-300d-5-i.yaml. Fixture package: planted agents + a planted
registry (the flag is authored there today and this criterion does not move it), built with
the REAL ``build_agents`` phase in-process.

  zz-super     declares only ``__ticket_phase_agents__``
  zz-explicit  declares zz-np and zz-p2 by name (never through the macro)
  zz-p1, zz-p2 ticket-phase on day one; zz-np never; zz-new is added later

RED BASELINE (slice 5): nothing delivers a section from the declaration, so the control
assertion (the supervisor names zz-p1 and zz-p2) fails first.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300e_support import (  # noqa: E402
    BODY,
    MACRO,
    build_in,
    named_sub_agents,
    read_prompts,
    set_registry,
    sfm,
    spawn_package,
    workers,
    write_template,
)

TEMPLATES = {
    "zz-super": (sfm("zz-super", [MACRO]), BODY),
    "zz-explicit": (sfm("zz-explicit", ["zz-np", "zz-p2"]), BODY),
    **workers("zz-p1", "zz-p2", "zz-np"),
}
KNOWN = set(TEMPLATES) | {"zz-new"}


def _built(tmp_path: Path, monkeypatch):
    pkg = spawn_package(tmp_path / "slice", TEMPLATES, ticket_phase=("zz-p1", "zz-p2"))
    out = tmp_path / "out"
    roots = build_in(pkg, out, monkeypatch)
    for root in roots:
        assert _named(root, "zz-super") == {"zz-p1", "zz-p2"}, "control: day-one macro resolution"
    return pkg, out, roots


def _named(root: Path, stem: str) -> set[str]:
    return named_sub_agents((root / f"{stem}.md").read_text(encoding="utf-8"), KNOWN)


def _add_new_ticket_phase_agent(pkg: Path) -> None:
    write_template(pkg / "templates" / "agents" / "zz-new.md", sfm("zz-new", tools="Bash, Read"), BODY)
    reg = pkg / "config" / "agent_registry.json"
    data = json.loads(reg.read_text(encoding="utf-8"))
    data["agents"].append({"id": "zz-new", "template_path": "templates/agents/zz-new.md", "role": "new role",
                           "tier": "phase", "is_ticket_phase": True, "spawn_allowlist": [],
                           "skills_used": [], "skills_invoked": []})
    reg.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_new_ticket_phase_agent_appears_in_ticket_supervisor_section(tmp_path, monkeypatch):
    # covers: AR-300d-5-i
    # angle: criterion
    """AR-300d-5-i: adding a new agent marked ``is_ticket_phase`` true makes the macro
    holder's compiled prompt (both roots) name it among its permitted sub-agents on the next
    build, with no edit to the holder."""
    pkg, out, _roots = _built(tmp_path, monkeypatch)
    _add_new_ticket_phase_agent(pkg)
    roots = build_in(pkg, out, monkeypatch)
    assert len(roots) == 2
    for root in roots:
        assert _named(root, "zz-super") == {"zz-p1", "zz-p2", "zz-new"}


def test_ticket_supervisor_definition_is_byte_identical_before_and_after(tmp_path, monkeypatch):
    # covers: AR-300d-5-i
    # angle: discrimination
    """AR-300d-5-i: the macro holder's own definition is byte-identical before and after the
    new agent is added AND compiled, and still holds the literal macro. The setup edits
    nothing but the registry flag and the new agent's files (a test that edits the holder
    during setup would pass on the broken design). Wrong version caught: the migration or
    build expands the macro into names written back into the holder's declaration."""
    pkg, out, _roots = _built(tmp_path, monkeypatch)
    holder = pkg / "templates" / "agents" / "zz-super.md"
    before = holder.read_bytes()
    _add_new_ticket_phase_agent(pkg)
    roots = build_in(pkg, out, monkeypatch)
    assert all(_named(r, "zz-super") == {"zz-p1", "zz-p2", "zz-new"} for r in roots), "control: not delivered"
    assert holder.read_bytes() == before, "the holder's definition changed"
    assert MACRO in holder.read_text(encoding="utf-8")


def test_unmarked_agent_stops_being_named_through_the_macro(tmp_path, monkeypatch):
    # covers: AR-300d-5-i
    # angle: boundary
    """AR-300d-5-i: an agent whose ``is_ticket_phase`` flips to false is absent from the
    macro holder's section on the next build (in both roots) -- and from nowhere else: an
    agent that names it explicitly (zz-explicit) still does, and no unrelated prompt moves."""
    pkg, out, roots = _built(tmp_path, monkeypatch)
    before = {r: read_prompts(r) for r in roots}
    set_registry(pkg, lambda by_id: by_id["zz-p2"].update(is_ticket_phase=False))
    roots = build_in(pkg, out, monkeypatch, allow_unchanged=True)
    for root in roots:
        after = read_prompts(root)
        assert _named(root, "zz-super") == {"zz-p1"}
        assert "zz-p2" in _named(root, "zz-explicit"), "un-marking removed an explicit permission"
        for stem in ("zz-explicit", "zz-p1", "zz-p2", "zz-np"):
            assert after[stem] == before[root][stem], f"{stem} changed when zz-p2 was un-marked"


def test_agent_not_marked_ticket_phase_is_never_named_through_the_macro(tmp_path, monkeypatch):
    # covers: AR-300d-5-i
    # angle: failure
    """AR-300d-5-i: no agent with ``is_ticket_phase`` false appears in the macro holder's
    section unless the holder declares it explicitly -- whatever its tier or role. Control:
    zz-explicit names zz-np because it DECLARES it, so naming works and the macro is what
    stays closed."""
    _pkg, _out, roots = _built(tmp_path, monkeypatch)
    for root in roots:
        assert "zz-np" not in _named(root, "zz-super")
        assert "zz-np" in _named(root, "zz-explicit")
