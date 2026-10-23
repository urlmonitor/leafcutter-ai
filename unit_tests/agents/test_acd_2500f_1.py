"""
MODULE: unit_tests/agents/test_acd_2500f_1.py
COVERS: ACD-2500f-1
GOAL: Red-first specification of ticket 10: the product-owner, business-analyst and
    test-designer profiles (templates/agents/<id>.md frontmatter) declare they produce
    "requirement_records"; the product-owner and business-analyst profiles declare one change
    surface, the requirement store (docs/acceptance-criteria/), instead of "none"; the registry
    entries and the generated agent cards show the same values; and the agents declaring
    "requirement_records" are exactly it-po, product-owner, business-analyst and test-designer.
DESIGN: as in ACD-2500e-1 (test_acd_2500e_1.py), the registry entry carries produces but no
    mutates, so "registry = profile" compares produces; the card is compared with
    generate_agent_cards.render_io_contract for the template (outputs and mutates).
INTERPRETATION PINNED HERE: the card renderer has no produces row, so "the card shows the
    profile's produces" is checked as: the template's produces is requirement_records, the card
    holds the exact rendered Input / Output Contract of the template, and that contract names
    `requirement_records` (the it-po precedent: the store mutates entry is named
    requirement_records, "in the same terms as the it-po entry").
HONEST LIMIT: these tests prove the declared profiles (parsed frontmatter, parsed JSON, the real
    validator, the real card renderer), not that a model behaves as declared. Nothing here spawns
    build.py.
RED STATE: every test fails on an assertion about today's profiles (produces analysis, mutates
    none); none on an import.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
REGISTRY = REPO / "config" / "agent_registry.json"
TEMPLATES = REPO / "templates" / "agents"
CARDS = REPO / "docs" / "agents" / "cards"
VALUE = "requirement_records"
STORE = "docs/acceptance-criteria/"
THREE = ("product-owner", "business-analyst", "test-designer")
# Record fields each agent writes; its mutates description must name at least one of them.
FIELDS_WRITTEN = {
    "product-owner": ("title", "criteria"),
    "business-analyst": ("criteria",),
}

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _template(agent_id: str) -> dict:
    """Parsed frontmatter of the real template (the project's own parser)."""
    from template_compiler import parse_frontmatter

    path = TEMPLATES / f"{agent_id}.md"
    assert path.is_file(), f"{path} is missing"
    frontmatter, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return frontmatter


def _agents() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["agents"]


def _entry(agent_id: str) -> dict:
    found = [agent for agent in _agents() if agent["id"] == agent_id]
    assert len(found) == 1, f"expected exactly one registry entry {agent_id!r}, found {len(found)}"
    return found[0]


def _env() -> dict:
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


# --------------------------------------------------------------------------
# the profiles
# --------------------------------------------------------------------------
@pytest.mark.parametrize("agent_id", THREE)
def test_three_profiles_produce_requirement_records(agent_id):
    # covers: ACD-2500f-1
    # angle: criterion
    """The template frontmatter's `produces` is exactly `requirement_records` (not `analysis`)."""
    assert _template(agent_id).get("produces") == VALUE


@pytest.mark.parametrize("agent_id", ("product-owner", "business-analyst"))
def test_po_and_ba_declare_requirement_store_change_surface(agent_id):
    # covers: ACD-2500f-1
    # angle: criterion
    """`mutates` has no entry named `none` and exactly one entry whose `surface` names
    docs/acceptance-criteria/, with a non-empty description that names record fields the agent
    writes (title/criteria for the PO, criteria for the BA). Wrong versions this catches:
    leaving `none` beside the new entry, naming the store only in prose, an empty description."""
    mutates = _template(agent_id).get("mutates") or []
    assert "none" not in [item.get("name") for item in mutates], f"still declares no change: {mutates}"
    on_store = [item for item in mutates if STORE in str(item.get("surface", ""))]
    assert len(on_store) == 1, f"exactly one mutates entry must name {STORE}: {mutates}"
    description = str(on_store[0].get("description") or "").strip()
    assert description, "the store mutates entry has no description"
    assert any(field in description for field in FIELDS_WRITTEN[agent_id]), (
        f"the description names none of the record fields {FIELDS_WRITTEN[agent_id]}: {description!r}"
    )


# --------------------------------------------------------------------------
# the derived copies: registry entry and agent card
# --------------------------------------------------------------------------
@pytest.mark.parametrize("agent_id", THREE)
def test_registry_entries_match_profile_produces(agent_id):
    # covers: ACD-2500f-1
    # angle: seam
    """config/agent_registry.json's `produces` equals the template's `produces`, which is
    `requirement_records`; both read from the real files, never retyped."""
    template, entry = _template(agent_id), _entry(agent_id)
    assert entry["produces"] == template.get("produces") == VALUE, (entry["produces"], template.get("produces"))


@pytest.mark.parametrize("agent_id", THREE)
def test_cards_show_profile_produces(agent_id):
    # covers: ACD-2500f-1
    # angle: real_artifact
    """The committed card docs/agents/cards/<id>.card.md (read, never rebuilt) contains the exact
    output of generate_agent_cards.render_io_contract for the real template, so a hand edit or an
    un-regenerated card fails; the template's produces is `requirement_records` and that rendered
    contract names it."""
    import generate_agent_cards

    template = _template(agent_id)
    assert template.get("produces") == VALUE, f"the profile still produces {template.get('produces')!r}"
    expected = generate_agent_cards.render_io_contract(template).strip()
    card = (CARDS / f"{agent_id}.card.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert expected in card, f"docs/agents/cards/{agent_id}.card.md is not the rendered template profile"
    assert f"`{VALUE}`" in expected, "the card's contract section does not show requirement_records"
    assert "| `none` |" not in expected, "the card still shows the agent changes nothing"


def test_requirement_record_writers_are_exactly_four():
    # covers: ACD-2500f-1
    # angle: criterion
    """Over the real registry: the set of ids with produces == requirement_records is exactly
    {it-po, product-owner, business-analyst, test-designer}."""
    writers = {agent["id"] for agent in _agents() if agent.get("produces") == VALUE}
    assert writers == {"it-po", *THREE}, sorted(writers)


# --------------------------------------------------------------------------
# reachability: the build's own registry gate
# --------------------------------------------------------------------------
def _package_copy(tmp_path: Path) -> Path:
    """A tmp copy of what scripts/registry_validator.py reads (as test_acd_2500e_1.py builds it)."""
    root = tmp_path / "pkg"
    shutil.copytree(SCRIPTS, root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(REPO / "config", root / "config")
    for sub in ("agents", "skills", "workflows-js"):
        shutil.copytree(REPO / "templates" / sub, root / "templates" / sub)
    return root


def _validate(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "registry_validator.py")],
        capture_output=True, text=True, encoding="utf-8", timeout=180, env=_env(), cwd=str(root),
    )


def test_registry_gate_accepts_the_new_profiles(tmp_path):
    # covers: ACD-2500f-1
    # angle: reachability
    """Entry point: `python scripts/registry_validator.py` as a subprocess on a tmp copy of the
    package. The copy's own product-owner, business-analyst and test-designer entries are at
    requirement_records (as committed, not set by this test) and the gate exits 0; control: one
    entry set to the typo `requirement_record` exits 1 and names it (the gate is live)."""
    root = _package_copy(tmp_path)
    path = root / "config" / "agent_registry.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    copied = {agent["id"]: agent.get("produces") for agent in data["agents"] if agent["id"] in THREE}
    assert copied == dict.fromkeys(THREE, VALUE), f"committed registry values: {copied}"

    proc = _validate(root)
    assert proc.returncode == 0, "registry gate rejects the profiles:\n" + proc.stdout + proc.stderr

    typo = copy.deepcopy(data)
    for agent in typo["agents"]:
        if agent["id"] == "business-analyst":
            agent["produces"] = "requirement_record"
    path.write_text(json.dumps(typo, indent=2), encoding="utf-8")
    control = _validate(root)
    assert control.returncode == 1 and "business-analyst" in control.stdout, control.stdout + control.stderr
