"""AR-400f -- a specialist's hand-off declaration says each thing once: no entry is covered by another entry or
repeated, and removing today's redundant entry kept the permission (composite-closure contract; zero build.py runs
of its own).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400f.yaml (test_spec).

Test 1 reads the checked-out declarations and the shared deployed layout (``shared_layout_reader``): the
declarations are read RAW from ``templates/agents`` (the registry copy is de-duplicated, so it can never show a
repeat) and judged against the registry's ``is_ticket_phase``, independently of the gate under test; the compiled
hand-off lists are read from the deployed prompts. Test 2 drives the real validator CLI on one package copy.

HONEST SCOPE: test 2 needs the AR-400f-1 gate (slice 3c) -- it is the one that fails until the gate lands.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3c_fixtures as X  # noqa: E402
import _ar400_parent_support as P  # noqa: E402
from _ar_300e_support import real_known_ids, spawn_accounts  # noqa: E402
from template_compiler import parse_frontmatter  # noqa: E402

COVERED, TWICE_SUP, CONTROL = "probe-covered", "probe-twice", "probe-control"


def _redundant_entries(declared: list[str], phase_ids: set[str]) -> list[str]:
    """Entries of one RAW declaration that another entry already covers or that repeat an earlier entry."""
    covered = phase_ids if X.MACRO in declared else set()
    seen: set[str] = set()
    bad: list[str] = []
    for entry in declared:
        if entry in seen or entry in covered:
            bad.append(entry)
        seen.add(entry)
    return bad


def _declarations() -> dict[str, list[str]]:
    """Specialist -> its own raw ``spawn_allowlist`` (the list as written, repeats kept)."""
    out: dict[str, list[str]] = {}
    for path in sorted((F.REPO_ROOT / "templates" / "agents").glob("*.md")):
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("name"):
            out[fm["name"]] = list(fm.get("spawn_allowlist") or [])
    return out


def _compiled_hand_offs(prompts: dict[str, str], known: set[str]) -> dict[str, list[str]]:
    """Specialist -> the ids of its compiled sub-agent account (empty when it has none; never more than one account)."""
    out: dict[str, list[str]] = {}
    for agent, text in prompts.items():
        accounts = spawn_accounts(text, known | {agent})
        assert len(accounts) <= 1, f"{agent}: {len(accounts)} hand-off accounts"
        out[agent] = accounts[0]["ids"] if accounts else []
    return out


def _repeat_first_entry(text: str, known: set[str]) -> str:
    """``text`` with the one line that names its first hand-off entry in the account written twice."""
    before = _compiled_hand_offs({"ticket-supervisor": text}, known)["ticket-supervisor"]
    for line in (ln for ln in text.splitlines() if F.names(ln, before[0])):
        candidate = text.replace(line + "\n", line + "\n" + line + "\n", 1)
        if len(_compiled_hand_offs({"ticket-supervisor": candidate}, known)["ticket-supervisor"]) > len(before):
            return candidate
    return pytest.fail("no line of the hand-off account could be doubled")


@pytest.mark.shared_layout_reader
def test_ar_400f_every_deployed_hand_off_list_names_each_specialist_once(shared_reference_layout):
    # covers: AR-400f
    # angle: deployed
    # must_catch: the redundant entry is removed by dropping llm-expert from ticket-supervisor's reach altogether
    """No specialist's own hand-off declaration names an entry another entry already covers or names one entry twice;
    every compiled hand-off list, in every platform root, names each specialist once; ticket-supervisor's compiled
    list still includes llm-expert. Controls: the declaration scan flags a covered entry and a repeat in a synthetic
    declaration and the macro users are a non-empty population; the compiled-list scan sees repeats when fed one."""
    declared = _declarations()
    phase_ids = {a["id"] for a in P.deployed_registry(shared_reference_layout)["agents"] if a.get("is_ticket_phase")}
    assert "llm-expert" in phase_ids and sum(1 for d in declared.values() if X.MACRO in d) >= 1
    assert {a: _redundant_entries(d, phase_ids) for a, d in declared.items() if _redundant_entries(d, phase_ids)} == {}
    assert _redundant_entries([X.MACRO, "brainstorm-lead", "llm-expert"], phase_ids) == ["llm-expert"]
    assert _redundant_entries(["research-agent", "research-agent"], phase_ids) == ["research-agent"]

    roots = P.prompts_by_root(shared_reference_layout)
    known = real_known_ids()
    for where, prompts in roots.items():
        lists = _compiled_hand_offs(prompts, known)
        repeated = {a: sorted({i for i in ids if ids.count(i) > 1}) for a, ids in lists.items() if len(ids) != len(set(ids))}
        assert repeated == {} and len(lists) == len(declared), (where, repeated)
        assert sum(1 for ids in lists.values() if ids) >= 10, f"{where}: too few compiled hand-off lists to mean anything"
        assert lists["ticket-supervisor"].count("llm-expert") == 1, f"{where}: {lists['ticket-supervisor']}"
    supervisor = roots[sorted(roots)[0]]["ticket-supervisor"]
    doubled = _compiled_hand_offs({"ticket-supervisor": _repeat_first_entry(supervisor, known)}, known)["ticket-supervisor"]
    assert len(doubled) == len(set(doubled)) + 1, "control: a repeated compiled entry must be visible to the scan"


def _plant_three_declarations(root) -> None:
    """One specialist whose macro covers a listed ticket-phase specialist, one naming a specialist twice, and a control
    whose explicit entry (brainstorm-lead) is NOT ticket-phase so the macro does not cover it."""
    assert X.is_phase(root, "llm-expert") and not X.is_phase(root, "brainstorm-lead")
    X.plant_handoff(root, COVERED, [X.MACRO, "llm-expert"])
    X.plant_handoff(root, TWICE_SUP, ["research-agent", "research-agent"])
    X.plant_handoff(root, CONTROL, [X.MACRO, "brainstorm-lead"])


def test_ar_400f_covered_and_repeated_entries_each_refuse_naming_the_redundant_entry():
    # covers: AR-400f
    # angle: discrimination
    # must_catch: the declaration is quietly de-duplicated at compile time and accepted
    # must_catch: every explicit entry beside the macro is flagged, including one the macro does not cover
    """In one package copy: one specialist declares every-ticket-phase-agent plus a ticket-phase specialist, a second
    names the same specialist twice, a third names a non-ticket-phase specialist beside the macro. The registry
    validator CLI exits non-zero with exactly two redundant-entry findings, each naming its specialist and the
    redundant entry, and none for the third."""
    rc, out = F.slice_cli(_plant_three_declarations)
    hits = X.hand_off_hits(out)
    mine = {name: [h for h in hits if F.names(h, name)] for name in (COVERED, TWICE_SUP, CONTROL)}
    assert len(hits) == 2 and [len(v) for v in mine.values()] == [1, 1, 0], f"expected two findings, not for {CONTROL}: {hits}\n{out[-900:]}"
    assert X.REDUNDANT in mine[COVERED][0].lower() and X.names_all(mine[COVERED][0], "llm-expert", X.MACRO), mine
    assert X.TWICE in mine[TWICE_SUP][0].lower() and X.names_all(mine[TWICE_SUP][0], "research-agent"), mine
    assert X.redundancy_warnings(out) == [] and rc != 0, f"exit {rc}: a redundancy must refuse, not warn"
    assert F.findings(out) == [], "only the hand-off redundancies may be wrong in the copy"
