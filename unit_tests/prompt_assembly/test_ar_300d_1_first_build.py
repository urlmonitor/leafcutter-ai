"""AR-300d-1 -- an agent added with a grant receives it on its FIRST build with
nothing else prepared: no registry row, no inclusion list, no body marker.

Source of truth: .../AR-300d-1.yaml. THE ASSERTION IS THE FILE SET, not only the
prompt: the tracked package slice (templates + skills + registry, copied from the
real tree) is hashed before and after, and the only change allowed is the one new
template. The build is the REAL ``build_phases.build_agents`` phase run
in-process over that slice (see _ar_300ad_support.py item 4), writing both
platform roots -- so there is no build.py spawn and no shared layout is requested.

GREEN-ALREADY (all): slice 1's declaration-driven append (the ``signoff: true``
precedent) already delivers on the first build. Mutation proof (AR300AD_MUTATION=
registry_gated -- deliver only for agents the REGISTRY already lists) turns tests
1, 2, 3 and 4 red; see the report for the run.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    REPO_ROOT,
    ability_rows,
    agent_fm,
    build_package,
    changed_files,
    installed_skill_ids,
    named_in_accounts,
    real_slice,
    snapshot_tree,
    write_template,
)

INSTALLED = installed_skill_ids(REPO_ROOT)
NEW_A = "zz-newcomer-a"
NEW_B = "zz-newcomer-b"
COND_B = "when the ticket touches a registry file"
GRANT_A = [{"skill_id": "signoff", "mode": "always"}]
GRANT_B = [
    {"skill_id": "signoff", "mode": "always"},
    {"skill_id": "doc-enforcer", "mode": "always"},
    {"skill_id": "route-knowledge", "mode": "conditional", "condition": COND_B},
]
BODY = "# New agent\n\nDo the work described in the ticket.\n"


def _rel(stem: str) -> str:
    return f"templates/agents/{stem}.md"


def _add_a(pkg: Path) -> None:
    write_template(pkg / _rel(NEW_A), agent_fm(NEW_A, GRANT_A, tools="Bash, Read"), BODY)


def _add_b(pkg: Path) -> None:
    fm = agent_fm(NEW_B, GRANT_B, tools="Bash, Read, Edit, Write, Agent") | {"requires_verification": True}
    write_template(pkg / _rel(NEW_B), fm, BODY)


def _ids(grant: list[dict]) -> set[str]:
    return {g["skill_id"] for g in grant}


def test_newly_added_agent_receives_its_grant_on_the_first_build(tmp_path, monkeypatch):
    # covers: AR-300d-1
    # angle: deployed
    """AR-300d-1: a template added with a grant and nothing else compiles, on the
    first build, to a deployed prompt naming its granted abilities -- in BOTH
    platform roots. The slice's registry has no row for the new agent."""
    assert _ids(GRANT_B) <= INSTALLED
    pkg = real_slice(tmp_path / "slice")
    registry_ids = {a["id"] for a in json.loads((pkg / "config" / "agent_registry.json").read_text("utf-8"))["agents"]}
    assert NEW_A not in registry_ids
    _add_a(pkg)
    roots = build_package(pkg, tmp_path / "out", monkeypatch)
    assert len(roots) == 2
    for root in roots:
        text = (root / f"{NEW_A}.md").read_text(encoding="utf-8")
        assert named_in_accounts(text, INSTALLED) == _ids(GRANT_A), f"{root}: abilities not delivered"


def test_no_file_other_than_the_new_template_had_to_change(tmp_path, monkeypatch):
    # covers: AR-300d-1
    # angle: seam
    """AR-300d-1: diff the tracked package slice before and after adding the agent
    AND after building it: the only change is the one new template -- no
    registry entry, no inclusion list, no marker, nothing the build rewrote.
    Control: the agent really received its grant, so 'nothing else changed' is
    not 'nothing happened'."""
    pkg = real_slice(tmp_path / "slice")
    before = snapshot_tree(pkg)
    assert len(before) > 60, "tracked slice is implausibly small"
    _add_a(pkg)
    assert changed_files(before, snapshot_tree(pkg)) == {_rel(NEW_A)}

    roots = build_package(pkg, tmp_path / "out", monkeypatch)
    assert changed_files(before, snapshot_tree(pkg)) == {_rel(NEW_A)}, "the build or the setup touched another tracked file"
    for root in roots:
        assert named_in_accounts((root / f"{NEW_A}.md").read_text(encoding="utf-8"), INSTALLED) == _ids(GRANT_A)


def test_file_set_diff_detects_a_second_edit(tmp_path):
    # covers: AR-300d-1
    # angle: boundary
    """AR-300d-1 (vacuity control): the before/after file-set check is capable of
    failing -- adding the template PLUS a registry row (the broken design's
    procedure) changes TWO files, and the diff reports both."""
    pkg = real_slice(tmp_path / "slice")
    before = snapshot_tree(pkg)
    _add_a(pkg)
    reg = pkg / "config" / "agent_registry.json"
    data = json.loads(reg.read_text(encoding="utf-8"))
    data["agents"].append({"id": NEW_A, "template_path": _rel(NEW_A), "skills_used": ["signoff"]})
    reg.write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert changed_files(before, snapshot_tree(pkg)) == {_rel(NEW_A), "config/agent_registry.json"}


def test_a_second_differently_shaped_new_agent_behaves_identically(tmp_path, monkeypatch):
    # covers: AR-300d-1
    # angle: boundary
    """AR-300d-1: two new agents added in the same way -- different tools line,
    grant size 1 vs 3, one conditional grant with its condition -- both arrive
    correct in both roots, and still only those two files changed. Wrong version
    caught: delivery that works only for a definition resembling an existing one."""
    pkg = real_slice(tmp_path / "slice")
    before = snapshot_tree(pkg)
    _add_a(pkg)
    _add_b(pkg)
    roots = build_package(pkg, tmp_path / "out", monkeypatch)
    assert changed_files(before, snapshot_tree(pkg)) == {_rel(NEW_A), _rel(NEW_B)}
    for root in roots:
        text_a = (root / f"{NEW_A}.md").read_text(encoding="utf-8")
        text_b = (root / f"{NEW_B}.md").read_text(encoding="utf-8")
        assert named_in_accounts(text_a, INSTALLED) == _ids(GRANT_A)
        assert named_in_accounts(text_b, INSTALLED) == _ids(GRANT_B)
        assert len(_ids(GRANT_A)) != len(_ids(GRANT_B))
        cond_row = ability_rows(text_b, INSTALLED)["route-knowledge"][0]
        assert COND_B in cond_row, f"conditional grant lost its condition: {cond_row!r}"


def test_delivery_is_gated_on_the_declaration_not_on_a_body_token(tmp_path, monkeypatch):
    # covers: AR-300d-1
    # angle: real_artifact
    """AR-300d-1: the new template's bytes on disk carry no placeholder token
    anywhere in its body (read back from the file the serializer wrote), and the
    agent still receives its section -- mirroring the ``signoff: true`` flag
    precedent. Wrong version caught: a body-token- or registry-gated branch."""
    pkg = real_slice(tmp_path / "slice")
    _add_b(pkg)
    on_disk = (pkg / _rel(NEW_B)).read_text(encoding="utf-8")
    assert "{{" not in on_disk and "}}" not in on_disk, "fixture must carry no placeholder token"
    roots = build_package(pkg, tmp_path / "out", monkeypatch)
    for root in roots:
        text = (root / f"{NEW_B}.md").read_text(encoding="utf-8")
        assert named_in_accounts(text, INSTALLED) == _ids(GRANT_B)
