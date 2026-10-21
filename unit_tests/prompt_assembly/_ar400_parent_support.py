"""Shared helpers for the seven AR-400 parent-closure test files (AR-400, AR-400a .. AR-400f).

Each parent proves its own promise through real entry points rather than restating a child's
unit test. Readers look at the session's shared deployed layout (nothing here builds); the two
parents that must build (AR-400a, AR-400d) do so in their own test files.

ASSUMED CONTRACT (nothing here names a production helper that does not exist):

  * a deployed layout holds the compiled prompts under ``<output root>/agents`` and
    ``<output root>/gemini/agents``, the abilities under ``<output root>/skills`` and the derived
    registry under ``<output root>/config``; compiled prompts keep the specialist's ``name`` but not
    its ``skills:`` declaration, so the grant side is ALWAYS read from ``templates/agents``;
  * the "deployed view" of the package is a slice whose ``templates/agents``, ``templates/skills``
    and registry are the deployed copies, so the real validator CLI and the real recognition rule
    can be pointed at what actually ships.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar_400e_support as E  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402
from _ar_300ad_support import (  # noqa: E402
    abilities_heading_lines,
    accounts,
    agent_prompts,
    installed_skill_ids,
    layout_roots,
    real_declarations,
    source_templates,
    strip_delivered_sections,
    verdict_for,
)
from _ar_300c_support import compiled_agent_roots, output_root_name  # noqa: E402
from skill_ref_recognition import recognise  # noqa: E402
from template_compiler import parse_frontmatter  # noqa: E402

REPO = F.REPO_ROOT


def deployed_dir(layout) -> Path:
    return Path(layout) / output_root_name(Path(layout))


def deployed_skill_ids(layout) -> set[str]:
    return {p.parent.name for p in (deployed_dir(layout) / "skills").glob("*/SKILL.md")}


def deployed_registry(layout) -> dict:
    return json.loads((deployed_dir(layout) / "config" / "agent_registry.json").read_text(encoding="utf-8"))


def prompts_by_root(layout) -> dict[str, dict[str, str]]:
    """``{platform root (relative): {specialist name: compiled prompt}}`` for every root the build wrote."""
    out: dict[str, dict[str, str]] = {}
    for root in compiled_agent_roots(Path(layout)):
        named: dict[str, str] = {}
        for path in agent_prompts(root):
            text = path.read_text(encoding="utf-8")
            named[parse_frontmatter(text)[0]["name"]] = text
        out[root.relative_to(layout).as_posix()] = named
    return out


def delivery_verdict(layout) -> tuple[dict, int]:
    """The build's own grant-delivery verdict (``agent_grant_delivery``) over every compiled prompt in every
    platform root of ``layout``, and the number of prompts it was expected to inspect."""
    roots = layout_roots(Path(layout))
    expected = len(source_templates()) * len(roots)
    verdict = verdict_for(real_declarations(), roots, expected=expected, known=installed_skill_ids(REPO))
    return verdict, expected


def delivered_headings(text: str) -> int:
    """How many delivered ``## Your Available Skills`` style headings a compiled prompt carries."""
    return len(abilities_heading_lines(text))


def definitions() -> dict[str, set[str]]:
    """Specialist name -> the ability ids its OWN definition under ``templates/agents`` declares."""
    return E.declared_ids(REPO)


def hidden_grants() -> dict[str, set[str]]:
    """Specialist -> granted ids marked ``provided_by: project`` that the package ships no ability for."""
    return E.project_supplied_unshipped(REPO)


def not_installed_stated(text: str, ability: str) -> bool:
    """A prose line (not a table row) saying ``ability`` is not installed."""
    return any(not ln.lstrip().startswith("|") and F.names(ln, ability) and "not installed" in ln.lower()
               for ln in text.splitlines())


def account_problems(prompts: dict[str, str], decl: dict[str, set[str]], hidden: dict[str, set[str]],
                     installed: set[str]) -> list[str]:
    """Where the abilities a compiled prompt names differ from its own definition's declaration.

    (Whether a prompt carries ONE account is the build's own delivery verdict: ``delivery_verdict``.)
    A project-supplied grant the package does not ship must be STATED as not installed and must not be a
    row (it is recognised as a row here by adding it to ``installed`` for that specialist only)."""
    bad: list[str] = []
    for agent, granted in sorted(decl.items()):
        text = prompts.get(agent)
        if text is None:
            bad.append(f"{agent}: no compiled prompt")
            continue
        gone = hidden.get(agent, set())
        found = accounts(text, installed | gone)
        named = {i for a in found for i in a["ids"]}
        if named != granted - gone:
            bad.append(f"{agent}: lists {sorted(named)}, definition declares {sorted(granted - gone)}")
        bad += [f"{agent}: does not state {s} is not installed" for s in sorted(gone)
                if not not_installed_stated(text, s)]
    return bad


def instruction_problems(prompts: dict[str, str], grants: dict[str, set[str]], hidden: dict[str, set[str]],
                         known: set[str], agent_ids: set[str]) -> tuple[list[str], int, int]:
    """(problems, specialists examined, instructions seen): each ability a compiled prompt tells its
    specialist to use must be in the grant ``grants`` (read from the definition) and in the prompt's
    delivered abilities section (or be stated as not installed when project-supplied)."""
    bad: list[str] = []
    seen = 0
    for agent, text in sorted(prompts.items()):
        gone = hidden.get(agent, set())
        refs = recognise(strip_delivered_sections(text), known | gone, agent_ids, agent)
        used = {r["canonical_id"] for r in refs
                if r["canonical_id"] and not r["citation"] and not r["names_agent"]}
        seen += len(used)
        own = grants.get(agent, set())
        bad += [f"{agent}: told to use {s}, its own definition grants {sorted(own)}" for s in sorted(used - own)]
        named = {i for a in accounts(text, known | gone) for i in a["ids"]}
        bad += [f"{agent}: told to use {s}, absent from its delivered abilities section"
                for s in sorted((used & own) - gone - named)]
    return bad, len(prompts), seen


def deployed_view(layout, base) -> Path:
    """A slice whose agents, abilities and registry are the DEPLOYED copies (so the real validator and the
    real recognition rule read what ships). ``base`` is a fresh scratch directory."""
    dep = deployed_dir(layout)
    root = H.make_slice(base)
    for name in ("agents", "skills"):
        shutil.rmtree(root / "templates" / name)
        shutil.copytree(dep / name, root / "templates" / name)
    shutil.copy2(dep / "config" / "agent_registry.json", root / "config" / "agent_registry.json")
    return root


def dangling_instructions(root: Path, supplied: dict[str, set[str]]) -> tuple[list[str], int, int]:
    """(findings, definitions scanned, guides scanned): instructions in the deployed copies of a view root
    (its agents and abilities) that name an ability nobody ships. Citations and sentences about another
    specialist are not instructions (AR-400b-2)."""
    skills = root / "templates" / "skills"
    known = {d.name for d in skills.iterdir() if d.is_dir()}
    agent_ids = {a["id"] for a in H._registry(root)["agents"]}
    findings: list[str] = []
    counts = {"definitions": 0, "guides": 0}
    deployed_copies = sorted(p for sub in ("agents", "skills") for p in (root / "templates" / sub).rglob("*.md"))
    for path in deployed_copies:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)[0] if path.parent.name == "agents" else {}
        subject = fm.get("name") if isinstance(fm, dict) else None
        counts["definitions" if subject else "guides"] += 1
        extra = supplied.get(subject, set()) if subject else set()
        body = strip_delivered_sections(text) if subject else text
        for ref in recognise(body, known | extra, agent_ids, subject):
            if ref["citation"] or ref["names_agent"] or ref["canonical_id"] in extra:
                continue
            if ref["canonical_id"] is None:
                findings.append(f"{path.relative_to(root).as_posix()}:{ref['line']} {ref['ability_text']}")
    return findings, counts["definitions"], counts["guides"]


# ------------------------------------------------------------------ AR-400e views of the deployed layout


def prompt_view(prompts: dict[str, str], decl, hidden, installed) -> E.View:
    out = {a: {i for acc in accounts(t, installed | hidden.get(a, set())) for i in acc["ids"]}
           for a, t in prompts.items()}
    return E.View(len(out), out)


def registry_view(layout) -> E.View:
    out: dict[str, set[str]] = {}
    for rec in deployed_registry(layout)["agents"]:
        out[rec["id"]] = {e["skill_id"] if isinstance(e, dict) else e for e in rec.get("skills_invoked") or []
                          if not (isinstance(e, dict) and e.get("descriptive_only"))}
    return E.View(len(out), out)


def diagram_view(layout, base: Path) -> E.View:
    (base / "config").mkdir(parents=True)
    shutil.copy2(deployed_dir(layout) / "config" / "agent_registry.json", base / "config" / "agent_registry.json")
    return E.view_diagram(base)


def graph_view(layout) -> E.View:
    """The deployed knowledge-graph CLI over the deployed install's own ``config/paths.json``."""
    dep = deployed_dir(layout)
    cp = subprocess.run([sys.executable, str(dep / "scripts" / "knowledge_query.py"), "--project-root", str(dep),
                         "--format", "json"],
                        capture_output=True, text=True, timeout=300, check=False)
    assert cp.returncode == 0, cp.stderr[-800:]
    data = json.loads(cp.stdout)
    ids = {n["id"] for n in data["nodes"] if n["surface"] == "agents"}
    out: dict[str, set[str]] = {a: set() for a in ids}
    for edge in data["edges"]:
        if edge["type"] == "skills_used" and edge["source"] in ids:
            out[edge["source"]].add(edge["target"])
    return E.View(len(ids), out)


def committed_card_view(decl: dict[str, set[str]]) -> E.View:
    """The published cards in the checked-out tree (``docs/agents/cards``; the shared layout holds none)."""
    out: dict[str, set[str]] = {}
    for agent in decl:
        path = REPO / "docs" / "agents" / "cards" / f"{agent}.card.md"
        parts = re.split(r"^## Skills Used\s*\n", path.read_text(encoding="utf-8"), maxsplit=1, flags=re.M) \
            if path.is_file() else []
        if len(parts) == 2:
            body = re.split(r"^(?:---|## )", parts[1], maxsplit=1, flags=re.M)[0]
            out[agent] = {m[1] for m in map(E._ROW.match, body.splitlines()) if m}
    return E.View(len(out), out)


def wrong_views_caught(expected: dict[str, set[str]]) -> list[bool]:
    """Each wrong view (emptied, union-reading, missing an empty-grant specialist) must be reported by
    ``E.mismatches``; the list is all True when the comparison discriminates."""
    agents = sorted(expected)
    rich = next(a for a in agents if expected[a])
    empty = next(a for a in agents if not expected[a])
    wrong = [E.View(len(agents), {**expected, rich: set()}),
             E.View(len(agents), {**expected, rich: expected[rich] | {"stray-ability"}}),
             E.View(len(agents) - 1, {a: s for a, s in expected.items() if a != empty})]
    return [bool(E.mismatches("control", v, expected)) for v in wrong]
