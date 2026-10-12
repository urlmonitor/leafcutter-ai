"""Support helpers for the AR-200b-3 / AR-200b-3-i tests (spawn-tool grant check: an agent
permitted to dispatch sub-agents holds the ``Agent`` tool). Imports -- never edits -- the
AR-200b-2 helpers.

ASSUMED PRODUCTION CONTRACT (the ACs say "generalise skill_tool_grant_validator over
(declaration-key, invoking-tool) pairs"; the test-writer fixed these names; python-coder
builds to them unless a documented, justified reason changes them):

  scripts/skill_tool_grant_validator.py  (the SAME module, one shared ``tools:`` parse)
    check_spawn_tool_grants(template_dir: Path) -> dict
        {"examined_count": int,      # agents (frontmatter ``name:``) examined
         "granted_count": int,       # agents holding a permission (macro entry counts alone)
         "findings": [{"agent": str, "declared_sub_agents": [str, ...] (macro as declared),
                       "declared_tools": [str, ...], "suggested_action": str}]}
        Absent/empty ``tools:`` permits nothing; absent or empty ``spawn_allowlist`` holds
        no permission. The registry's own spawn_allowlist is never consulted.
  scripts/registry_validator.validate_agent_registry(package_root) includes the spawn
  pair's error strings in the SAME pass as the skills pair's, and prints a counts line that
  names ``spawn`` and carries ``examined=<N>`` and the number of agents holding a permission
  (``permitted=`` / ``granted=`` / ``held=``), e.g. ``[INFO] spawn-tool-grant: examined=59
  granted=24``. A shortfall is an error string in the skills pair's shape, with prefix
  ``spawn-tool-grant:`` -- ``spawn-tool-grant: agent '<name>' is permitted [<sub-agents>] but
  its tools [<tools>] lack 'Agent'. Grant the Agent tool: ...`` (see SHAPE_RE) -- and the
  build refuses.

Everything below is TEST-side: an independent derivation of the population from the real
templates through production's parse_frontmatter, plus fixtures written with
yaml.safe_dump -- except where the real on-disk shape cannot be produced by a serializer (a
trailing YAML comment), where REAL template bytes are edited token by token.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

_HELPER = Path(__file__).resolve().parent / "_ar_200b_2_support.py"
if "_ar_200b_2_support" in sys.modules:
    S2: Any = sys.modules["_ar_200b_2_support"]
else:
    _spec = importlib.util.spec_from_file_location("_ar_200b_2_support", _HELPER)
    S2 = importlib.util.module_from_spec(_spec)
    sys.modules["_ar_200b_2_support"] = S2
    _spec.loader.exec_module(S2)

REPO_ROOT: Path = S2.REPO_ROOT
REAL_TEMPLATES: Path = S2.REAL_TEMPLATES
parse_frontmatter = S2.parse_frontmatter
tools_of = S2.tools_of
run_validate = S2.run_validate
make_package = S2.make_package
make_clean_package = S2.make_clean_package
INVOKING_TOOL = "Agent"
KEY = "spawn_allowlist"
MACRO = "__ticket_phase_agents__"
_COUNTS_RE = re.compile(r"spawn[^\n]*examined=(\d+)[^\n]*?(?:permitted|granted|held)=(\d+)", re.IGNORECASE)


def check_spawn(template_dir: Path) -> dict:
    """Call the (not-yet-written) spawn pair of the validator; a clear red when absent."""
    mod = S2.load_checker()
    fn = getattr(mod, "check_spawn_tool_grants", None)
    assert fn is not None, "skill_tool_grant_validator.check_spawn_tool_grants is not implemented"
    return fn(template_dir)


def spawn_of(fm: dict[str, Any]) -> list[str] | None:
    """Independent reading of the declaration; None means the key is absent."""
    raw = fm.get(KEY)
    return None if raw is None else [str(x) for x in raw]


def derive_population(template_dir: Path) -> list[dict[str, Any]]:
    """Every agent (frontmatter `name:`) with its tools and declared sub-agents."""
    out = []
    for path in sorted(template_dir.glob("*.md")):
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        if fm.get("name"):
            out.append({"name": fm["name"], "tools": tools_of(fm), "spawn": spawn_of(fm), "path": path,
                        "skills": [e["skill_id"] for e in (fm.get("skills") or [])]})
    return out


def holders(population: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [a for a in population if a["spawn"]]


def shortfall_names(population: list[dict[str, Any]]) -> set[str]:
    return {a["name"] for a in holders(population) if INVOKING_TOOL not in (a["tools"] or [])}


def write_spawn_agent(template_dir: Path, name: str, tools: str | None, spawn: list[str] | None,
                      skills: list[str] | None = None) -> Path:
    """One agent template; frontmatter bytes from yaml.safe_dump. tools=None / spawn=None
    omit the key; spawn=[] writes an explicit empty list."""
    fm: dict[str, Any] = {"name": name, "description": f"planted {name}"}
    if tools is not None:
        fm["tools"] = tools
    if spawn is not None:
        fm[KEY] = list(spawn)
    if skills is not None:
        fm["skills"] = [{"skill_id": s, "mode": "always"} for s in skills]
    path = template_dir / f"{name}.md"
    path.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\nbody\n", encoding="utf-8")
    return path


def add_spawn_declaration(path: Path, ids: list[str]) -> None:
    """Insert a ``spawn_allowlist`` key (real serializer); a template that already declares
    one (the real tree after the migration) has that key replaced, never duplicated."""
    lines, kept, skipping = path.read_text(encoding="utf-8").split("\n"), [], False
    close = lines.index("---", 1)
    for i, line in enumerate(lines):
        if 0 < i < close and line.startswith(f"{KEY}:"):
            skipping = True
            continue
        if skipping and 0 < i < close and (line.startswith("- ") or line.startswith(" ")):
            continue
        skipping = False
        kept.append(line)
    text = "\n".join(kept)
    end = text.find("\n---", 3)
    block = yaml.safe_dump({KEY: ids}, sort_keys=False).rstrip("\n")
    path.write_text(text[:end] + "\n" + block + text[end:], encoding="utf-8")
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert spawn_of(fm) == ids, "add_spawn_declaration produced an unparseable block"


_TOOLS_LINE = re.compile(r"^tools:[^\n]*$", re.MULTILINE)
_COMMENT = re.compile(r"[ \t]+#.*$")


def set_tools_line(path: Path, tokens: list[str], *, keep_comment: bool = True, comment: str | None = None) -> None:
    """Replace the value of a REAL template's single-line ``tools:`` with ``tokens``,
    keeping (or replacing) its trailing ``  # comment`` byte for byte, and re-parse to prove
    the rewrite landed. Everything outside the line stays byte-identical."""
    text = path.read_text(encoding="utf-8")
    line = _TOOLS_LINE.search(text)
    assert line, f"{path.name} has no single-line tools:"
    old_comment = _COMMENT.search(line.group(0))
    tail = comment if comment is not None else (old_comment.group(0) if old_comment and keep_comment else "")
    path.write_text(text[: line.start()] + "tools: " + ", ".join(tokens) + tail + text[line.end():], encoding="utf-8")
    got = tools_of(parse_frontmatter(path.read_text(encoding="utf-8"))[0]) or []
    assert got == tokens, f"{path.name}: tools rewrite left {got}, wanted {tokens}"


def rename_agent(path: Path, new_name: str) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(re.sub(r"^name:[^\n]*$", f"name: {new_name}", text, count=1, flags=re.MULTILINE), encoding="utf-8")


def add_agent_tool(path: Path) -> None:
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    tools = tools_of(fm) or []
    if INVOKING_TOOL not in tools:
        set_tools_line(path, tools + [INVOKING_TOOL]) if tools else _grant_to_empty(path)


def _grant_to_empty(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    path.write_text(text[:end] + "\ntools: Agent" + text[end:], encoding="utf-8")


def remove_agent_tool(path: Path) -> None:
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    tools = [t for t in (tools_of(fm) or []) if t != INVOKING_TOOL]
    set_tools_line(path, tools)


def make_clean_spawn_package(dest: Path) -> Path:
    """make_clean_package (Skill granted to every skill holder), then ``Agent`` granted to
    every agent whose declaration permits a sub-agent. Nothing is spawned; templates copied."""
    root = make_clean_package(dest)
    for agent in holders(derive_population(root / "templates" / "agents")):
        add_agent_tool(agent["path"])
    return root


SPAWN_PREFIX = "spawn-tool-grant:"
SKILL_PREFIX = "skill-tool-grant:"
# Both pairs render ONE shape: "<prefix> agent '<name>' ... lack '<Tool>'. Grant the <Tool> tool ...".
SHAPE_RE = re.compile(r"^(?P<prefix>(?:skill|spawn)-tool-grant:) agent '(?P<name>[^']+)' .*"
                      r"lack '(?P<tool>[A-Za-z]+)'\.\s+Grant the (?P=tool) tool", re.DOTALL)


def spawn_errors(errors: list[str], name: str) -> list[str]:
    """The spawn pair's errors for ``name`` (other registry findings, e.g. asymmetric-spawn
    messages, are not this check's and are ignored)."""
    return [e for e in errors if e.startswith(SPAWN_PREFIX) and f"'{name}'" in e]


def skill_errors(errors: list[str], name: str) -> list[str]:
    return [e for e in errors if e.startswith(SKILL_PREFIX) and f"'{name}'" in e]


def counts_line(stdout: str) -> tuple[int, int] | None:
    m = _COUNTS_RE.search(stdout)
    return (int(m.group(1)), int(m.group(2))) if m else None


def copy_real_templates(dest: Path) -> Path:
    shutil.copytree(REAL_TEMPLATES, dest)
    return dest
