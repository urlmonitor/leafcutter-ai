"""
MODULE: unit_tests/agents/test_acd_2500e_1.py
COVERS: ACD-2500e-1
GOAL: Red-first specification of ticket 41 (G5): the technical planner's published profile
    (templates/agents/it-po.md frontmatter) says it MUTATES requirement records in the AC store
    and PRODUCES requirement records, and the registry entry and the generated agent card show
    the same values. Today the profile says `mutates: none` and `produces: analysis` while its
    tools include Write and Edit.
DESIGN: the G5 architect note (D4, user decision 2026-10-15, Option A): `requirement_records` is
    added to the CLOSED produces vocabulary (scripts/registry_validator.py, the registry schema's
    two enums). Nothing branches on the value except `== "production_code"`. The registry entry
    has no `mutates` and no `tools`, so "registry = template" means produces and description;
    "card = template" means the Input / Output Contract section (outputs and mutates).
HONEST LIMIT: a template is a prompt; these tests prove the declared profile (parsed frontmatter,
    parsed JSON, the real validator, the real card renderer), not that a model behaves as declared.
    Nothing here spawns build.py: the card is checked against the renderer, not rebuilt.
RED STATE: every test fails on an assertion about the current profile or vocabulary; none on an import.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
REGISTRY = REPO / "config" / "agent_registry.json"
SCHEMA = REPO / "config" / "agent_registry.schema.json"
TEMPLATE = REPO / "templates" / "agents" / "it-po.md"
CARD = REPO / "docs" / "agents" / "cards" / "it-po.card.md"
VALUE = "requirement_records"
STORE = "docs/acceptance-criteria/"
# A claim: a verb of authoring/choosing, then (within 40 chars, same sentence, no negator) the
# test design or reference files. "It writes no test design." is the opposite of a claim.
_CLAIM = re.compile(
    r"\b(?:write|writes|author|authors|choose|chooses|pick|picks|select|selects|design|designs)\b"
    r"([^.]{0,40}?)(?:test design|reference files?)",
    re.IGNORECASE,
)
_NEGATOR = re.compile(r"\b(?:no|not|never|neither|nor|without)\b|n't", re.IGNORECASE)

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _template() -> dict:
    """Parsed frontmatter of the real it-po template (the project's own parser)."""
    from template_compiler import parse_frontmatter

    assert TEMPLATE.is_file(), "templates/agents/it-po.md is missing"
    frontmatter, _ = parse_frontmatter(TEMPLATE.read_text(encoding="utf-8"))
    return frontmatter


def _entry() -> dict:
    agents = json.loads(REGISTRY.read_text(encoding="utf-8"))["agents"]
    found = [agent for agent in agents if agent["id"] == "it-po"]
    assert len(found) == 1, f"expected exactly one registry entry 'it-po', found {len(found)}"
    return found[0]


def _flat(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _claims(description: str) -> list[str]:
    """Fragments of `description` that CLAIM test design / reference-file authorship."""
    found = []
    for m in _CLAIM.finditer(description):
        lead = description[: m.start()].rsplit(".", 1)[-1][-30:]  # same sentence, just before the verb
        if not _NEGATOR.search(lead) and not _NEGATOR.search(m.group(1)):
            found.append(m.group(0))
    return found


def _env() -> dict:
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


# --------------------------------------------------------------------------
# AC-1: the profile says the planner changes requirement records
# --------------------------------------------------------------------------
def test_it_po_mutates_requirement_store():
    # covers: ACD-2500e-1
    # angle: criterion
    """AC-1: the template's `mutates` has no entry named `none` and exactly one entry that names
    the requirement store (docs/acceptance-criteria/) on its `surface`. Wrong versions this
    catches: leaving `none` next to the new entry; naming the store only in prose."""
    mutates = _template().get("mutates") or []
    names = [item.get("name") for item in mutates]
    assert "none" not in names, f"profile still declares it changes nothing: {mutates}"
    on_store = [item for item in mutates if STORE in str(item.get("surface", ""))]
    assert len(on_store) == 1, f"exactly one mutates entry must name {STORE}: {mutates}"
    assert on_store[0]["name"] == VALUE


def test_it_po_outputs_name_requirement_records_beside_the_report():
    # covers: ACD-2500e-1
    # angle: criterion
    """AC-2 (outputs half of D4): `outputs` gains `requirement_records` (type record_fields) and
    KEEPS `completion_report` -- the sign-off payload is still an output."""
    outputs = {item.get("name"): item for item in _template().get("outputs") or []}
    assert VALUE in outputs, f"outputs declare no {VALUE}: {sorted(outputs)}"
    assert outputs[VALUE].get("type") == "record_fields"
    assert "completion_report" in outputs, "the sign-off payload output must stay"


# --------------------------------------------------------------------------
# AC-2: produces requirement records, in the closed vocabulary
# --------------------------------------------------------------------------
def test_it_po_produces_requirement_records():
    # covers: ACD-2500e-1
    # angle: criterion
    """AC-2: the template's `produces` is exactly `requirement_records`, instead of `analysis`."""
    assert _template().get("produces") == VALUE


def test_requirement_records_is_in_the_closed_produces_vocabulary_and_typos_are_not():
    # covers: ACD-2500e-1
    # angle: seam
    """The REAL validator (registry_validator.validate_produces_field) accepts `requirement_records`
    on a registry entry; the control values `analysis` (old value) is still accepted while the
    typos `requirement_record` and `requirement-records` are rejected naming the agent. The
    registry schema's `produces` enum and its ambiguity `candidate_values` enum both list the value
    (the build validates the registry against the schema)."""
    import registry_validator

    template_dir = REPO / "templates" / "agents"

    def errors_for(value: str) -> list[str]:
        return registry_validator.validate_produces_field(
            [{**_entry(), "produces": value}], template_dir
        )

    assert errors_for("analysis") == [], "control: an existing value must stay valid"
    for typo in ("requirement_record", "requirement-records"):
        rejected = errors_for(typo)
        assert rejected and "it-po" in rejected[0], f"typo {typo!r} must be rejected: {rejected}"
    assert errors_for(VALUE) == [], f"{VALUE!r} is not in registry_validator's produces vocabulary"

    produces = json.loads(SCHEMA.read_text(encoding="utf-8"))["definitions"]["agent"]["properties"]  # agents.items is a $ref
    enums = [
        produces["produces"]["oneOf"][0]["enum"],
        produces["llm_ambiguity_comment"]["properties"]["candidate_values"]["items"]["enum"],
    ]
    for enum in enums:
        assert VALUE in enum, f"registry schema enum lacks {VALUE}: {enum}"


# --------------------------------------------------------------------------
# AC-3: the description claims no test design and no reference-file choice
# --------------------------------------------------------------------------
def test_description_claims_no_test_design_or_reference_file_choice():
    # covers: ACD-2500e-1
    # angle: discrimination
    """AC-3: no description of the planner CLAIMS test-design or reference-file authorship -- the
    template, the registry entry and the card all carry the same description, and none claims it.
    The detector is a regex on the claim, not a substring: it must flag 'writes the test design'
    and 'chooses reference files' and must NOT flag 'It writes no test design.' (the control that a
    substring test would wrongly fail on). The registry description is the one that is not yet the
    template's, so it is the surface that goes red."""
    assert _claims("The planner writes the test design for each clause.")
    assert _claims("It chooses reference files for the build.")
    assert _claims("Authors test design and picks the reference file.")
    assert not _claims("It writes no test design.")
    assert not _claims("It does not choose reference files.")

    template = _flat(_template().get("description"))
    registry = _flat(_entry().get("description"))
    card_front = CARD.read_text(encoding="utf-8").split("---", 2)[1]
    assert _flat(registry) == template, (
        "the registry description must be the template's description, not an older summary"
    )
    for surface, description in (("template", template), ("registry", registry), ("card", _flat(card_front))):
        assert not _claims(description), f"{surface} description claims it: {_claims(description)}"


# --------------------------------------------------------------------------
# AC-4: the registry entry and the card show the profile's values
# --------------------------------------------------------------------------
def test_it_po_registry_matches_profile():
    # covers: ACD-2500e-1
    # angle: seam
    """AC-4 (registry half): config/agent_registry.json's it-po entry shows the template's
    `produces` and `description`. The registry has no `mutates`; mutates is compared template to
    card in the next test. Both values are read from the REAL files, not retyped."""
    template, entry = _template(), _entry()
    assert entry["produces"] == template["produces"] == VALUE
    assert _flat(entry["description"]) == _flat(template["description"])


def test_card_shows_the_corrected_profile_not_a_stale_one():
    # covers: ACD-2500e-1
    # angle: real_artifact
    """AC-4 (card half): the committed card contains the exact output of
    generate_agent_cards.render_io_contract for the real template's frontmatter, so a hand edit or
    an un-regenerated card fails; and that section shows `requirement_records` under Mutates and no
    `none` row. (Equality alone is green today -- template and card are both stale -- so the
    corrected-profile conjunct is what makes this red now.)"""
    import generate_agent_cards

    expected = generate_agent_cards.render_io_contract(_template()).strip()
    card = CARD.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "| `none` |" not in expected, "the template still declares the planner changes nothing"
    assert f"| `{VALUE}` |" in expected, "the template's contract section does not name the records"
    assert expected in card, "docs/agents/cards/it-po.card.md is not the rendered template profile"
    mutates_section = card.split("### Mutates (Side Effects)", 1)[1]
    assert f"`{VALUE}`" in mutates_section.split("\n---", 1)[0]


# --------------------------------------------------------------------------
# reachability: the build's own registry gate
# --------------------------------------------------------------------------
def _package_copy(tmp_path: Path) -> Path:
    """A tmp copy of the package surface scripts/registry_validator.py reads: its own scripts,
    config, agent and skill templates, and the workflows that count as external spawners. `__file__`-relative, so it validates the COPY."""
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


def _set_produces(root: Path, value: str) -> None:
    path = root / "config" / "agent_registry.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for agent in data["agents"]:
        if agent["id"] == "it-po":
            agent["produces"] = value
    path.write_text(json.dumps(copy.deepcopy(data), indent=2), encoding="utf-8")


def test_acd_2500e_1_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500e-1
    # angle: reachability
    """Entry point resolved (Step 1.1, CLI under scripts/ with a __main__ guard):
    `python scripts/registry_validator.py` as a subprocess on a tmp copy of the package -- the
    build's own registry gate. Baseline (copy unchanged) exits 0 (the harness is sound); with the
    it-po entry's `produces` set to `requirement_records` it must still exit 0; the typo control
    `requirement_record` exits 1 and names it-po (the gate is live, and the value, not the
    harness, decides). Red today: the value is outside the closed vocabulary."""
    root = _package_copy(tmp_path)
    baseline = _validate(root)
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr

    _set_produces(root, "requirement_record")
    control = _validate(root)
    assert control.returncode == 1 and "it-po" in control.stdout, control.stdout + control.stderr

    _set_produces(root, VALUE)
    proc = _validate(root)
    assert proc.returncode == 0, "registry gate rejects the value:\n" + proc.stdout + proc.stderr
