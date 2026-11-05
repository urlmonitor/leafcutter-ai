"""ACD-2500f-2 and its parent ACD-2500f -- the produces guidance and the requirement writers' profiles.

ACD-2500f-2 is ``test_required: false`` (a prompt-only change to templates/agents/llm-expert.md section P1). Its
checks read the delivered signal table and apply it the way an agent author would, to the real business-analyst
and architect-review templates, so a guidance that again lets a planning role decide the value turns them red.
The ACD-2500f check reads the four requirement writers' real profiles and the real registry.
"""

from __future__ import annotations

import json
import re

import yaml

from unit_tests.ac_driven_dev.doc_deliverables import _doc_support as D

TEMPLATES = D.REPO / "templates" / "agents"
LLM_EXPERT = TEMPLATES / "llm-expert.md"
STORE = "docs/acceptance-criteria/"
WRITERS = ("product-owner", "business-analyst", "it-po", "test-designer")
# A line that maps a planning or analysis role to the produces value analysis, in prose or as a mapping.
_ROLE_TO_ANALYSIS = re.compile(r"role:? ?`?(planning|analysis)`?\s*(→|->|=>|maps to)\s*`?analysis\b"
                               r"|[\"'](planning|analysis)[\"']\s*:\s*[\"']analysis[\"']")


def _registry() -> dict[str, dict]:
    registry = json.loads((D.REPO / "config" / "agent_registry.json").read_text(encoding="utf-8"))
    return {agent["id"]: agent for agent in registry["agents"]}


def _front(agent_id: str) -> dict:
    match = re.match(r"---\r?\n(.*?)\r?\n---", D.read(TEMPLATES / f"{agent_id}.md"), re.DOTALL)
    assert match, f"{agent_id}.md has no frontmatter"
    return yaml.safe_load(match.group(1))


def _writes_store(front: dict) -> bool:
    return any(STORE in str(m.get("surface", "")) for m in front.get("mutates") or [] if isinstance(m, dict))


def _signal_rows() -> dict[int, tuple[str, str]]:
    sec = D.section(D.read(LLM_EXPERT), "§P1 — Inference signals")
    rows = re.findall(r"^\| (\d+) \| (.+?) \| (.+?) \|$", sec, re.M)
    assert rows, "control: section P1 has a signal table"
    return {int(n): (signal, hint) for n, signal, hint in rows}


def _guided_value(front: dict, role: str) -> str | None:
    """What section P1 leads to for one template: the highest-ranked signal that applies decides."""
    for _, (signal, hint) in sorted(_signal_rows().items()):
        if "requirement records" in signal and _writes_store(front):
            value = re.search(r"the value is `([a-z_]+)`", hint)
            if value is None:
                raise AssertionError(f"P1 hint for the requirement-records signal names no value: {hint!r}")
            return value.group(1)
        if signal.startswith("`role:`"):
            found = re.search(r"`role: " + re.escape(role) + r"` → (?:likely )?`([a-z_]+)`", hint)
            if found:
                return found.group(1)
    return None


# ---------------------------------------------------------------- ACD-2500f-2
def test_guidance_names_requirement_writing_as_the_signal_ranked_above_the_role():
    # covers: ACD-2500f-2
    # angle: criterion
    """Section P1 names writing requirement records (the store's mutates surface) as the signal for
    requirement_records, ranked above the role signal, and says a planning role alone never decides it."""
    rows = _signal_rows()
    req = [n for n, (signal, _) in rows.items() if "requirement records" in signal]
    role = [n for n, (signal, _) in rows.items() if signal.startswith("`role:`")]
    assert len(req) == 1 and len(role) == 1, rows
    signal, hint = rows[req[0]]
    assert req[0] < role[0], "the requirement-records signal must rank above the role signal"
    assert STORE in signal and "`mutates:`" in signal
    D.assert_all(hint, ["the value is `requirement_records`", "This outranks the role signal",
                        "a planning role alone never decides it"], "llm-expert.md section P1")
    assert "`role: planning` → `analysis` unless signal 1 applies" in rows[role[0]][1]


def test_guidance_leads_business_analyst_to_requirement_records_and_architect_review_to_todays_value():
    # covers: ACD-2500f-2
    # angle: real_artifact
    """Followed on the real templates, the guidance gives business-analyst requirement_records (not
    analysis) and architect-review, which writes no requirement records, the value it declares today. The
    role is the template's, or the registry entry's where the template carries none (architect-review)."""
    registry = _registry()
    ba, architect = _front("business-analyst"), _front("architect-review")
    assert _writes_store(ba) and not _writes_store(architect), "control: only the BA writes requirement records"
    assert _guided_value(ba, ba.get("role") or registry["business-analyst"]["role"]) == "requirement_records"
    role = architect.get("role") or registry["architect-review"]["role"]
    assert _guided_value(architect, role) == architect["produces"] == registry["architect-review"]["produces"]


def test_no_other_template_or_skill_maps_a_requirement_writing_role_to_analysis():
    # covers: ACD-2500f-2
    # angle: discrimination
    """Across templates/agents and templates/skills, the only line mapping a planning or analysis role to
    analysis is the llm-expert P1 role row, and that row carries the 'unless signal 1 applies' exception."""
    files = sorted(TEMPLATES.glob("*.md")) + sorted((D.REPO / "templates" / "skills").rglob("*.md"))
    hits = [(path.relative_to(D.REPO).as_posix(), line) for path in files
            for line in path.read_text(encoding="utf-8").splitlines() if _ROLE_TO_ANALYSIS.search(line)]
    assert [path for path, _ in hits] == ["templates/agents/llm-expert.md"], hits
    assert "unless signal 1 applies" in hits[0][1]


# ---------------------------------------------------------------- ACD-2500f (parent)
def test_parent_every_requirement_writer_profile_says_so_in_the_same_terms():
    # covers: ACD-2500f
    # angle: criterion
    """The product, analysis, technical-planning and test-design agents each declare produces
    requirement_records and a mutates entry with the same name and the same requirement-store surface; the
    registry lists exactly these four as requirement-record producers."""
    terms = set()
    for agent_id in WRITERS:
        front = _front(agent_id)
        assert front["produces"] == "requirement_records", agent_id
        entries = [m for m in front.get("mutates") or [] if STORE in str(m.get("surface", ""))]
        assert len(entries) == 1, (agent_id, front.get("mutates"))
        terms.add((entries[0]["name"], entries[0]["surface"]))
    assert terms == {("requirement_records", "AC YAML store (docs/acceptance-criteria/)")}, terms
    producers = {i for i, agent in _registry().items() if agent.get("produces") == "requirement_records"}
    assert producers == set(WRITERS), producers
