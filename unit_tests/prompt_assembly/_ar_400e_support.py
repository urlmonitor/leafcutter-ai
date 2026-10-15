"""Support for the AR-400e tests (retire the derived ``skills_used`` registry field).

Every helper runs the REAL production entry point of one "view" of a specialist's
abilities over a temporary copy of the package and returns what that view says as
``View(count, abilities)``: ``abilities`` maps a specialist id to the set of ability
ids the view lists for it, ``count`` is the number of specialists the view examined.

ASSUMED PRODUCTION CONTRACT (the coder implements exactly this; nothing here names a
new helper -- only existing entry points and what they print or return):

* briefing: ``render_effective_prompt.assemble`` + ``render_markdown`` -- the abilities
  are the bullets under the ``### Skills ...`` heading; ``descriptive_only`` ones absent.
* validation: ``build_phases_agent_validation.validate_agent_self_description`` -- made
  observable by a sterile copy (no skill resolves, no ``category``), so it prints one
  ``Registry entry '<id>' ...`` line per specialist examined and per ability examined.
* diagram: CLI ``scripts/generate_agent_diagram.py --diagram skill --registry <copy>``;
  EVERY specialist gets a node in the ``Agents`` subgraph, abilities are the links.
* graph: ``knowledge_query.build_knowledge_map`` over a trimmed project root that carries
  the REAL ``agents`` and ``skills`` surface entries of ``config/paths.json``; the edge
  label stays ``skills_used`` (decision 12), sourced from ``skills_invoked`` ids.
* card: ``generate_agent_cards.build_agent_cards`` -- the ``## Skills Used`` table.
* verdict: ``agent_ability_verdict.verify_abilities``.
* hook: ``templates/scripts/commit_guardian/transform_agent_registry.py --package-root``.

Fixture bytes: registries are ``json`` dumps of deep copies of REAL records; templates
are copies of the real ones (frontmatter bytes from the real files) or ``yaml.safe_dump``.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
HOOK = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "transform_agent_registry.py"
SNAPSHOT = Path(__file__).resolve().parent / "fixtures_ar_400e" / "agent_registry.2026-10-12.json"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from template_compiler import parse_frontmatter  # noqa: E402

GHOST = "ghost-ability-ar400e"
# Edge label of a specialist->ability edge (decision 12: stays skills_used; a relabel to
# skills_invoked is a wrong version and is caught because both are accepted here and the
# test then asserts the label set is exactly {"skills_used"}).
ABILITY_LABELS = ("skills_used", "skills_invoked")


class View(NamedTuple):
    examined: int
    abilities: dict[str, set[str]]


def dump(data: dict) -> str:
    """The one way the hook writes the registry (4-space indent, UTF-8, final newline)."""
    return json.dumps(data, indent=4, ensure_ascii=False) + "\n"


def registry(root: Path) -> dict:
    return json.loads((root / "config" / "agent_registry.json").read_text(encoding="utf-8"))


def write_registry(root: Path, data: dict) -> None:
    (root / "config" / "agent_registry.json").write_text(dump(data), encoding="utf-8")


def _entry(item: Any) -> dict:
    raw = {"skill_id": item} if isinstance(item, str) else item
    out = {"skill_id": raw["skill_id"], "mode": raw.get("mode") or "always"}
    if raw.get("condition"):
        out["condition"] = str(raw["condition"])
    return out


def declared(root: Path) -> dict[str, list[dict]]:
    """Specialist id (frontmatter ``name``) -> declared grants, read independently of production."""
    out: dict[str, list[dict]] = {}
    for path in sorted((root / "templates" / "agents").glob("*.md")):
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("name"):
            out[fm["name"]] = [_entry(i) for i in fm.get("skills") or []]
    return out


def declared_ids(root: Path) -> dict[str, set[str]]:
    return {a: {e["skill_id"] for e in es} for a, es in declared(root).items()}


def lean_root(base: Path, *, name: str = "pkg") -> Path:
    """A REAL (no symlink) slice: config/, templates/ (agents + skills + guides)."""
    root = base / name
    skip = shutil.ignore_patterns("__pycache__")
    shutil.copytree(REPO_ROOT / "config", root / "config", ignore=skip)
    shutil.copytree(REPO_ROOT / "templates", root / "templates", ignore=skip)
    return root


def run_hook(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HOOK), "--package-root", str(root)],
                          capture_output=True, text=True, timeout=120, check=False)


def strip_retired(root: Path) -> None:
    """Hand-delete ``skills_used`` from every record (no-op once the field is gone)."""
    data = registry(root)
    for rec in data["agents"]:
        rec.pop("skills_used", None)
    write_registry(root, data)


def regenerated_root(base: Path, *, name: str = "regen") -> Path:
    """Slice whose registry is the hook's output, with any retired field removed by hand."""
    root = lean_root(base, name=name)
    assert run_hook(root).returncode == 0
    strip_retired(root)
    return root


def plant_stray(root: Path, count: int = 8) -> dict[str, str]:
    """Hand-plant ``skills_used`` naming one real skill the agent does NOT declare."""
    decl = declared_ids(root)
    skills = sorted(p.name for p in (root / "templates" / "skills").iterdir() if (p / "SKILL.md").is_file())
    data, planted = registry(root), dict[str, str]()
    for rec in data["agents"]:
        spare = [s for s in skills if s not in decl.get(rec["id"], set())]
        if spare and len(planted) < count:
            rec["skills_used"] = [spare[0]]
            planted[rec["id"]] = spare[0]
    write_registry(root, data)
    assert planted, "planted nothing"
    return planted


def plant_descriptive(root: Path, count: int = 4) -> dict[str, str]:
    """Add a ``descriptive_only`` ``skills_invoked`` entry naming a real, undeclared skill."""
    decl = declared_ids(root)
    skills = sorted(p.name for p in (root / "templates" / "skills").iterdir() if (p / "SKILL.md").is_file())
    data, planted = registry(root), dict[str, str]()
    for rec in data["agents"]:
        spare = [s for s in skills if s not in decl.get(rec["id"], set())]
        if spare and len(planted) < count:
            rec.setdefault("skills_invoked", []).append(
                {"skill_id": spare[0], "mode": "conditional", "descriptive_only": True})
            planted[rec["id"]] = spare[0]
    write_registry(root, data)
    assert planted, "planted nothing"
    return planted


def plant_specialist(root: Path, name: str, skills: list, *, used_only: list | None = None) -> None:
    """Plant a specialist: template via yaml.safe_dump, record cloned from product-owner."""
    fm = {"name": name, "description": f"{name} planted", "tools": "Bash, Read, Skill",
          "model": "sonnet", "produces": "analysis", "skills": skills}
    (root / "templates" / "agents" / f"{name}.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\nbody\n", encoding="utf-8")
    data = registry(root)
    rec = copy.deepcopy(next(a for a in data["agents"] if a["id"] == "product-owner"))
    rec.update({"id": name, "name": name, "template_path": f"templates/agents/{name}.md",
                "skills_invoked": [] if used_only is not None else [_entry(s) for s in skills]})
    rec.pop("skills_used", None)
    if used_only is not None:
        rec["skills_used"] = list(used_only)
    data["agents"] = [a for a in data["agents"] if a["id"] != name] + [rec]
    write_registry(root, data)


def declare_extra(root: Path, agent: str, skill_id: str) -> None:
    """Add one grant to an existing template's ``skills:`` declaration (frontmatter re-dumped)."""
    path = root / "templates" / "agents" / f"{agent}.md"
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    head = yaml.safe_load(text[3:end])
    head["skills"] = list(head.get("skills") or []) + [{"skill_id": skill_id, "mode": "always"}]
    path.write_text("---\n" + yaml.safe_dump(head, sort_keys=False) + text[end + 1:], encoding="utf-8")


def snapshot_populations() -> tuple[list[str], list[str]]:
    """(older-field-only, newer-field-only) specialist ids from the 2026-10-12 snapshot."""
    def ids(rec: dict, field: str) -> list[str]:
        return [e["skill_id"] if isinstance(e, dict) else e for e in rec.get(field) or []
                if not (isinstance(e, dict) and e.get("descriptive_only"))]
    agents = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["agents"]
    older = [a["id"] for a in agents if ids(a, "skills_used") and not ids(a, "skills_invoked")]
    newer = [a["id"] for a in agents if ids(a, "skills_invoked") and not ids(a, "skills_used")]
    assert older and newer, "snapshot yielded an empty population"
    return sorted(older), sorted(newer)


# ---------------------------------------------------------------- views


def briefing_markdown(root: Path, agent: str) -> str:
    """The rendered effective prompt (brief form) of one specialist over ``root``."""
    import render_effective_prompt as rep

    payload = rep.assemble(agent=agent, ac_id=None, ticket_path=None, repo_root=root, dep_depth=0)
    return rep.render_markdown(payload, root, 0, brief=True)


def view_briefing(root: Path, agents: list[str]) -> View:
    out: dict[str, set[str]] = {}
    for agent in agents:
        md = briefing_markdown(root, agent)
        # the LAST "### Skills" heading: an agent body (inside its fence) may carry one of its own
        pieces = re.split(r"^### Skills\b[^\n]*\n", md, flags=re.M)
        body = re.split(r"^(?:---|#{1,3} )", pieces[-1], maxsplit=1, flags=re.M)[0] if len(pieces) > 1 else ""
        out[agent] = set(re.findall(r"^- `([^`]+)`", body, flags=re.M))
    return View(len(out), out)


def view_validation(root: Path, scratch: Path) -> View:
    """Sterile copy: no skill resolves and no record has ``category``, so every examined
    specialist and every examined non-descriptive ability is printed as a problem line."""
    import build_phases_agent_validation as val

    pkg = scratch / "sterile"
    shutil.rmtree(pkg, ignore_errors=True)
    (pkg / "config").mkdir(parents=True)
    shutil.copytree(root / "templates" / "agents", pkg / "templates" / "agents")
    (pkg / "templates" / "skills").mkdir(parents=True)
    (pkg / "config" / "skill_registry.json").write_text('{"skills": []}', encoding="utf-8")
    data = registry(root)
    for rec in data["agents"]:
        rec.pop("category", None)
    write_registry(pkg, data)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        val.validate_agent_self_description(pkg, {}, False, "error", package_root=pkg)
    text = buf.getvalue()
    examined = set(re.findall(r"Registry entry '([^']+)' missing required field 'category'", text))
    abilities: dict[str, set[str]] = {a: set() for a in examined}
    for agent, sid in re.findall(r"Registry entry '([^']+)' has unresolvable \w+ skill_id '([^']+)'", text):
        abilities.setdefault(agent, set()).add(sid)
    return View(len(examined), abilities)


def view_validation_errors(root: Path) -> tuple[int, str]:
    """The build's registry validation over ``root`` as-is (real skills): (error_count, stdout)."""
    import build_phases_agent_validation as val

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        errors, _warn = val.validate_agent_self_description(root, {}, False, "error", package_root=root)
    return errors, buf.getvalue()


def diagram_stdout(registry_path: Path) -> str:
    cp = subprocess.run([sys.executable, str(SCRIPTS / "generate_agent_diagram.py"), "--diagram", "skill",
                         "--registry", str(registry_path)], capture_output=True, text=True, timeout=120, check=False)
    assert cp.returncode == 0, cp.stderr
    return cp.stdout


def view_diagram(root: Path) -> View:
    text = diagram_stdout(root / "config" / "agent_registry.json")
    agents = dict(re.findall(r'^\s+(a_\w+)\["([^"]+)"\]', text, flags=re.M))
    skills = dict(re.findall(r"^\s+(s_\w+)\{\{['\"]?([^'\"}]+)['\"]?\}\}", text, flags=re.M))
    out: dict[str, set[str]] = {label: set() for label in agents.values()}
    for a_node, s_node in re.findall(r"^\s+(a_\w+) --> (s_\w+)", text, flags=re.M):
        out.setdefault(agents.get(a_node, a_node), set()).add(skills.get(s_node, s_node))
    return View(len(agents), out)


class GraphView(NamedTuple):
    view: View
    declined: list
    invalid: list
    edge_types: set[str]
    edge_total: int


def trimmed_project(root: Path) -> Path:
    """Project root holding the registries and the REAL agents/skills surfaces of paths.json."""
    real = json.loads((REPO_ROOT / "config" / "paths.json").read_text(encoding="utf-8"))
    trimmed = {"surfaces": {k: copy.deepcopy(real["surfaces"][k]) for k in ("agents", "skills")}}
    (root / "config" / "paths.json").write_text(json.dumps(trimmed, indent=2), encoding="utf-8")
    return root


def view_graph(root: Path) -> GraphView:
    import knowledge_query as kq

    trimmed_project(root)
    paths = root / "config" / "paths.json"
    entry_declines: list = []
    nodes, edges, _d, _p = kq._collect_all_ex(root, paths, entry_declines=entry_declines)
    agent_ids = {n.id for n in nodes if n.surface == "agents"}
    skill_ids = {n.id for n in nodes if n.surface == "skills"}
    out: dict[str, set[str]] = {a: set() for a in agent_ids}
    total, types = 0, set()
    for e in edges:
        # agent->ability edges carry the ability label; spawned_by etc. are other relationships
        # (an id such as build-ac is both an agent and a skill, so filter on the label, not the target).
        if e.source_id in agent_ids and e.target_id in skill_ids and e.edge_type in ABILITY_LABELS:
            out[e.source_id].add(e.target_id)
            types.add(e.edge_type)
            total += 1
    km = kq.build_knowledge_map(root, paths)
    invalid = [r for r in kq.validate_knowledge_map(km, root, paths) if r.surface == "agents" and not r.valid]
    return GraphView(View(len(agent_ids), out), entry_declines, invalid, types, total)


_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*([^|]*?)\s*\|\s*(.*?)\s*\|$")


def view_cards(root: Path) -> tuple[View, dict[str, list[tuple[str, str, str]]]]:
    import generate_agent_cards as cards

    with contextlib.redirect_stdout(io.StringIO()):
        cards.build_agent_cards(root, {}, False, True)
    out: dict[str, set[str]] = {}
    rows: dict[str, list[tuple[str, str, str]]] = {}
    specialists = set(declared(root))
    for card in sorted((root / "docs" / "agents" / "cards").glob("*.card.md")):
        agent = card.name[: -len(".card.md")]
        if agent not in specialists:  # e.g. README.card.md is a guide, not a specialist
            continue
        section = re.split(r"^## Skills Used\s*\n", card.read_text(encoding="utf-8"), maxsplit=1, flags=re.M)[1]
        body = re.split(r"^(?:---|## )", section, maxsplit=1, flags=re.M)[0]
        rows[agent] = [(m[1], m[2], m[3]) for m in map(_ROW.match, body.splitlines()) if m]
        out[agent] = {r[0] for r in rows[agent]}
    return View(len(out), out), rows


def view_verdict(root: Path, scratch: Path) -> tuple[View, dict]:
    import agent_ability_verdict as verdict

    decl_raw = {}
    for path in sorted((root / "templates" / "agents").glob("*.md")):
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("name"):
            decl_raw[fm["name"]] = fm.get("skills") or []
    result = verdict.verify_abilities(decl_raw, registry(root)["agents"],
                                      packaged_skills_root=root / "templates" / "skills", project_root=scratch)
    ids = declared_ids(root)
    out = {a: set(s) for a, s in ids.items()}
    for f in result["findings"]:
        if "recorded_abilities" in f:
            out[f["agent"]] = set(f["recorded_abilities"])
    return View(result["examined_count"], out), result


def all_views(root: Path, scratch: Path) -> dict[str, View]:
    """Run all six views over ``root``; ``graph`` also exposes its extras via ``view_graph``."""
    decl = declared_ids(root)
    return {"briefing": view_briefing(root, sorted(decl)), "validation": view_validation(root, scratch),
            "diagram": view_diagram(root), "graph": view_graph(root).view,
            "card": view_cards(root)[0], "verdict": view_verdict(root, scratch)[0]}


def mismatches(name: str, view: View, expected: dict[str, set[str]]) -> list[str]:
    """Human-readable disagreements between a view and the declared sets."""
    bad = [f"{name}: {a} lists {sorted(view.abilities.get(a, set()))} != declared {sorted(want)}"
           for a, want in sorted(expected.items()) if a in view.abilities and view.abilities[a] != want]
    bad += [f"{name}: {a} is absent from the view" for a in sorted(expected) if a not in view.abilities]
    if view.examined != len(expected):
        bad.append(f"{name}: examined {view.examined} specialists, tree has {len(expected)}")
    return bad
