"""Shared helpers for the AR-300c test files (test-writer, TDD red phase).

ASSUMED PRODUCTION CONTRACT (the tests ARE the contract until a documented,
justified reason changes them -- the ACs do not name these identifiers, so the
test-writer fixed them here; python-coder builds to them):

1. Frontmatter key: ``skills`` -- a YAML list, sibling of ``tools:``,
   whose entries are ``{skill_id, mode, condition?}`` (INF-600a-1's shape,
   ``mode`` is ``always`` | ``conditional``). Absent key == no grant. The
   registry fields keep their names (``skills_used`` / ``skills_invoked``);
   only the frontmatter key is ``skills`` (never the retired registry name).
   ``descriptive_only: true`` registry entries describe behaviour and are NOT
   grants: they are never written into ``skills:`` and the verifier ignores
   them on the registry side.
2. Migration tool (one-shot, NOT wired into the build):
   ``python scripts/migrate_agent_abilities.py --package-root <dir>
   [--report <json path>]``. Reads ``<dir>/config/agent_registry.json`` and
   ``<dir>/templates/agents/*.md``; inserts ONLY the ``skills`` key
   into each granted template's frontmatter; regenerates the registry's
   derived ability fields from the declarations; writes a JSON report::

       {"counts": {"skills_used": N, "skills_invoked": M, "union": U},
        "agents": [{"agent": id, "sources": ["skills_used"|"skills_invoked"...],
                    "abilities": [skill ids]}, ...],
        "excluded": [{"agent": id, "skill_id": id, "reason": str}, ...],
        "conflicts": [...], "review": [...]}

   ``excluded`` lists every descriptive_only entry left out. Exit code 0 on
   success.
3. Verification module ``scripts/agent_ability_verdict.py`` exposing
   ``verify_abilities(declarations, registry_agents, *, packaged_skills_root,
   project_root, output_root_name=".leafcutter") -> dict`` with keys
   ``examined_count`` (agents: union of declaration holders and registry
   entries), ``abilities_examined`` / ``resolved_count`` (abilities),
   ``ok`` (bool) and ``findings`` (list of dicts). Finding kinds:
   ``divergent`` | ``declaration-only`` | ``record-only`` (each with
   ``agent``, ``declared_abilities``, ``recorded_abilities``) and
   ``unresolved`` (``agent``, ``ability``, ``looked_in`` = list of
   ``{"surface": "packaged"|"project_local", "path": str, "found": False}``).
   A zero-agent or zero-ability population raises ``ValueError``.
4. Compilation keeps the existing public signature
   ``template_compiler.compile_agent_template(template_path, config,
   registry_path=, agents=, skills_root=)`` -- the exact text build_agents
   writes (before the components table) -- and delivers the abilities section
   from the frontmatter declaration ONLY.

The compiled-prompt "abilities section" is located format-agnostically: a
``##``/``###`` heading containing ``abilit*`` or ``skill(s)``; abilities named
are the first token of each table row / list item / sub-heading under it that
is an installed skill id.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from template_compiler import (  # noqa: E402
    compile_agent_template,
    parse_frontmatter,
)

GRANT_KEY = "skills"
PRISTINE_REGISTRY = Path(__file__).resolve().parent / "fixtures_ar_300c" / "agent_registry.pre_migration.json"
# Overridable so tests can be mutation-checked against a lazy stub script.
MIGRATION_SCRIPT = Path(
    os.environ.get("AR300C_MIGRATION_SCRIPT") or SCRIPTS_DIR / "migrate_agent_abilities.py"
)

_HEADING_RE = re.compile(r"^#{2,3}\s+.*\b(abilit\w*|skills?)\b", re.IGNORECASE)
_NAMED_RE = re.compile(r"^\s*(?:\||[-*]|#{3,6})\s*[`*]*([a-z][a-z0-9_-]*)")


def installed_skill_ids(package_root: Path) -> set[str]:
    skills = package_root / "templates" / "skills"
    return {p.parent.name for p in skills.glob("*/SKILL.md")}


def declared_entries(fm: dict) -> list[dict]:
    out = []
    for e in fm.get(GRANT_KEY) or []:
        out.append(e if isinstance(e, dict) else {"skill_id": e})
    return out


def declared_ids(fm: dict) -> set[str]:
    return {e["skill_id"] for e in declared_entries(fm)}


def named_abilities(compiled: str, installed: set[str]) -> set[str]:
    """Abilities named in the compiled prompt's abilities section(s)."""
    named: set[str] = set()
    in_section = False
    for line in compiled.splitlines():
        if line.startswith("## ") or line.startswith("### "):
            in_section = bool(_HEADING_RE.match(line))
            m = _NAMED_RE.match(line)
            if in_section and line.startswith("### ") and m and m.group(1) in installed:
                named.add(m.group(1))
            continue
        if in_section:
            m = _NAMED_RE.match(line)
            if m and m.group(1) in installed:
                named.add(m.group(1))
    return named


def output_root_name(layout: Path) -> str:
    for cand in (layout / ".claude" / "skills_config.json",
                 layout / "config" / "skills_config.default.json"):
        if cand.is_file():
            val = json.loads(cand.read_text(encoding="utf-8")).get("output_root")
            if val:
                return val
    return ".leafcutter"


def compiled_agent_roots(layout: Path) -> list[Path]:
    """Every platform root the build wrote agent prompts to, found under the
    declared output root (never the .claude/agents shim)."""
    out_root = layout / output_root_name(layout)
    return sorted(
        d for d in out_root.rglob("agents")
        if d.is_dir() and any(d.glob("*.md"))
    )


def registry_agents(root: Path) -> list[dict]:
    data = json.loads((root / "config" / "agent_registry.json").read_text(encoding="utf-8"))
    return data["agents"]


def registry_ids(agent: dict, field: str) -> list[str]:
    out = []
    for e in agent.get(field) or []:
        out.append(e["skill_id"] if isinstance(e, dict) else e)
    return out


def descriptive_only_ids(agent: dict) -> set[str]:
    """Ids this agent's registry record flags ``descriptive_only`` (not grants)."""
    return {
        e["skill_id"]
        for f in ("skills_used", "skills_invoked")
        for e in (agent.get(f) or [])
        if isinstance(e, dict) and e.get("descriptive_only")
    }


def granted_ids(agent: dict) -> set[str]:
    """Union of both registry fields, minus descriptive_only entries."""
    return (set(registry_ids(agent, "skills_used"))
            | set(registry_ids(agent, "skills_invoked"))) - descriptive_only_ids(agent)


def template_stem(agent: dict) -> str | None:
    tp = agent.get("template_path")
    return Path(tp).stem if tp else None


def write_template(path: Path, fm: dict, body: str = "# Fixture agent\n\nDo the work.\n") -> Path:
    """Write a template whose frontmatter comes from the real serializer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False).rstrip()
    path.write_text(f"---\n{fm_text}\n---\n\n{body}", encoding="utf-8")
    return path


def compile_template(template_path: Path, agents: list[dict], registry_path: Path) -> str:
    return compile_agent_template(
        template_path,
        {"output_root": ".leafcutter"},
        registry_path=registry_path,
        agents=agents,
        skills_root=REPO_ROOT / "templates" / "skills",
    )


def strip_grant_key(text: str) -> tuple[str, int]:
    """Remove the ``skills:`` key and its item lines from a template's
    frontmatter, at TEXT level, changing nothing else. Returns (text, lines
    removed)."""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return text, 0
    try:
        end = lines.index("---", 1)
    except ValueError:
        return text, 0
    out, removed, skipping = [lines[0]], 0, False
    for line in lines[1:end]:
        if line.startswith(f"{GRANT_KEY}:"):
            skipping, removed = True, removed + 1
            continue
        if skipping and (line.startswith("- ") or line.startswith(" ") or line.startswith("-\t")):
            removed += 1
            continue
        skipping = False
        out.append(line)
    out.extend(lines[end:])
    return "\n".join(out), removed


STRIPPED_COUNTS: dict[Path, int] = {}


def pristine_registry_agents() -> list[dict]:
    """The registry as it was BEFORE consolidation (verbatim git-HEAD bytes
    captured in the fixtures dir): both rival fields, original populations."""
    return json.loads(PRISTINE_REGISTRY.read_text(encoding="utf-8"))["agents"]


def copy_package_slice(dst: Path) -> Path:
    """Copy exactly the inputs the migration/compiler read, in their
    PRE-MIGRATION state: the real (possibly already-migrated) templates with
    the ``skills:`` key stripped at text level, and the pristine pre-migration
    registry. Guards: nothing stripped == the real tree gave us nothing to
    un-migrate (loud failure); any template still carrying the key after the
    strip == not pristine."""
    (dst / "config").mkdir(parents=True)
    shutil.copy2(PRISTINE_REGISTRY, dst / "config" / "agent_registry.json")
    shutil.copytree(REPO_ROOT / "templates" / "agents", dst / "templates" / "agents")
    shutil.copytree(REPO_ROOT / "templates" / "skills", dst / "templates" / "skills")
    stripped = 0
    for tpl in sorted((dst / "templates" / "agents").glob("*.md")):
        text = tpl.read_text(encoding="utf-8")
        new, n = strip_grant_key(text)
        if n:
            tpl.write_text(new, encoding="utf-8")
            stripped += 1
    assert stripped > 0, "pristine guard: 0 templates had a `skills:` key to strip (empty population)"
    leftover = [t.name for t in (dst / "templates" / "agents").glob("*.md")
                if GRANT_KEY in template_frontmatter(t)]
    assert not leftover, f"pristine guard: templates still carry {GRANT_KEY}: {leftover}"
    STRIPPED_COUNTS[dst] = stripped
    return dst


def run_migration(pkg: Path, report: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(MIGRATION_SCRIPT), "--package-root", str(pkg),
         "--report", str(report)],
        capture_output=True, text=True, timeout=120, check=False,
    )


def migrate_or_fail(pkg: Path) -> dict:
    """Run the real migration CLI; return its parsed report. Fails (red) when
    the tool is absent or exits non-zero."""
    report = pkg.parent / (pkg.name + "_report.json")
    proc = run_migration(pkg, report)
    assert proc.returncode == 0, (
        f"migration CLI failed (exit {proc.returncode}): {proc.stderr[-800:]}"
    )
    assert report.is_file(), "migration wrote no report"
    return json.loads(report.read_text(encoding="utf-8"))


def add_registry_agent(pkg: Path, record: dict) -> None:
    path = pkg / "config" / "agent_registry.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["agents"].append(record)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_skills(root: Path, ids: list[str]) -> Path:
    for sid in ids:
        d = root / sid
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {sid}\ndescription: fixture skill {sid}\n---\n\nbody\n",
            encoding="utf-8",
        )
    return root


def template_frontmatter(path: Path) -> dict:
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return fm
