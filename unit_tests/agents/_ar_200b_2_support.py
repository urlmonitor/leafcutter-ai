"""Support helpers for the AR-200b-2 / AR-200b-2-i tests (skill-tool grant check).

ASSUMED PRODUCTION CONTRACT (the coder implements exactly this):

  scripts/skill_tool_grant_validator.py  (sibling of registry_verification_flags.py)
    INVOKING_TOOL = "Skill"
    ERROR_PREFIX  = "skill-tool-grant:"
    check_skill_tool_grants(template_dir: Path) -> dict
        {"examined_count": int, "granted_count": int,
         "findings": [{"agent": str, "granted_abilities": [skill_id, ...],
                       "declared_tools": [tool, ...], "suggested_action": str}]}
    validate_skill_tool_grants(template_dir: Path) -> list[str]
        error strings, each beginning ERROR_PREFIX; also an error when the
        population resolves to zero agents (or the directory is missing).

  scripts/registry_validator.validate_agent_registry(package_root) calls
  validate_skill_tool_grants(<root>/templates/agents), returns its errors, and
  prints one line  "[INFO] skill-tool-grant: examined=<N> granted=<G>".
  build.py already refuses on a non-empty error list, and
  `python scripts/registry_validator.py` exits 1 on one (ADR-050: refuse).

Everything below is TEST-side: an independent derivation of the population
from the real templates through production's parse_frontmatter, plus planted
fixtures written with yaml.safe_dump (never hand-typed frontmatter).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
REAL_TEMPLATES = REPO_ROOT / "templates" / "agents"
INVOKING_TOOL = "Skill"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from template_compiler import parse_frontmatter  # noqa: E402


def load_checker() -> Any:
    """Cold-import the production check module (ImportError until it exists)."""
    import importlib

    return importlib.import_module("skill_tool_grant_validator")


def tools_of(fm: dict[str, Any]) -> list[str] | None:
    """Independent reading of `tools:`; None means the key is absent."""
    raw = fm.get("tools")
    if raw is None:
        return None
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    return [str(t).strip() for t in raw]


def abilities_of(fm: dict[str, Any]) -> list[str]:
    """Granted skill ids; absent or empty grant -> []."""
    return [e["skill_id"] for e in (fm.get("skills") or [])]


def derive_population(template_dir: Path) -> list[dict[str, Any]]:
    """Every agent (frontmatter `name:`) with its tools and granted abilities."""
    population = []
    for path in sorted(template_dir.glob("*.md")):
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm.get("name"):
            continue
        population.append(
            {
                "name": fm["name"],
                "tools": tools_of(fm),
                "abilities": abilities_of(fm),
                "path": path,
            }
        )
    return population


def shortfall_names(population: list[dict[str, Any]]) -> set[str]:
    """Agents holding a grant whose tools (absent == none) lack exact Skill."""
    return {
        a["name"]
        for a in population
        if a["abilities"] and INVOKING_TOOL not in (a["tools"] or [])
    }


def write_agent(
    template_dir: Path,
    name: str,
    tools: str | None,
    skills: list[str] | None,
) -> Path:
    """Write one agent template; frontmatter bytes come from yaml.safe_dump.

    tools=None omits the key; skills=None omits the key; skills=[] writes an
    empty list; otherwise each id becomes a {skill_id, mode} entry.
    """
    fm: dict[str, Any] = {"name": name, "description": f"planted {name}"}
    if tools is not None:
        fm["tools"] = tools
    if skills is not None:
        fm["skills"] = [{"skill_id": s, "mode": "always"} for s in skills]
    text = "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\nbody\n"
    path = template_dir / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


_TOOLS_START = re.compile(r"^tools:[ \t]*", re.MULTILINE)
_COMMENT = re.compile(r"[ \t]+#.*$")


def _split_comment(line: str) -> tuple[str, str]:
    """(content, trailing '  # comment' kept verbatim or '')."""
    m = _COMMENT.search(line)
    return (line[: m.start()], m.group(0)) if m else (line, "")


def _tools_block(text: str) -> tuple[int, int, list[str]]:
    """Span of the whole `tools:` value: first line + indented continuations."""
    start = _TOOLS_START.search(text)
    assert start, "template has no tools: line to rewrite"
    lines = text[start.start():].split("\n")
    count = 1
    while count < len(lines) and lines[count][:1] in (" ", "\t") and lines[count].strip():
        count += 1
    block = lines[:count]
    return start.start(), start.start() + len("\n".join(block)), block


def _rewrite_tools(path: Path, want_skill: bool) -> None:
    """Add or remove the exact token Skill, preserving comments, folds, layout.

    Everything outside the tools value stays byte-identical. The result is
    re-parsed with production's parse_frontmatter and asserted, so a rewrite
    that silently failed raises instead of yielding a vacuous fixture.
    """
    text = path.read_text(encoding="utf-8")
    before, _ = parse_frontmatter(text)
    begin, end, block = _tools_block(text)
    new_block: list[str] = []
    for i, raw in enumerate(block):
        content, comment = _split_comment(raw)
        prefix = _TOOLS_START.match(content).group(0) if i == 0 else content[: len(content) - len(content.lstrip())]
        body = content[len(prefix):]
        trailing_comma = body.rstrip().endswith(",")
        kept = [p.strip() for p in body.split(",") if p.strip() and p.strip() != INVOKING_TOOL]
        if not kept and i > 0:
            continue
        new_block.append(prefix + ", ".join(kept) + ("," if trailing_comma and kept else "") + comment)
    last_content, last_comment = _split_comment(new_block[-1])
    new_block[-1] = last_content.rstrip().rstrip(",") + last_comment
    if want_skill:
        last_content, last_comment = _split_comment(new_block[-1])
        sep = " " if last_content.rstrip().endswith(":") else ", "
        new_block[-1] = last_content.rstrip() + sep + INVOKING_TOOL + last_comment
    path.write_text(text[:begin] + "\n".join(new_block) + text[end:], encoding="utf-8")
    after, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    got = tools_of(after) or []
    base = [t for t in (tools_of(before) or []) if t != INVOKING_TOOL]
    assert [t for t in got if t != INVOKING_TOOL] == base, f"{path.name}: other tools changed: {got}"
    assert (INVOKING_TOOL in got) == want_skill, f"{path.name}: rewrite did not leave Skill={want_skill}: {got}"
    assert got.count(INVOKING_TOOL) <= 1


def remove_skill_tool(path: Path) -> None:
    _rewrite_tools(path, want_skill=False)


def add_skill_tool(path: Path) -> None:
    """Idempotent: a template that already holds Skill is left unchanged."""
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    if INVOKING_TOOL not in (tools_of(fm) or []):
        _rewrite_tools(path, want_skill=True)


ERROR_PREFIX = "skill-tool-grant:"


def add_grant(path: Path, skill_ids: list[str]) -> None:
    """Add a `skills:` grant to a template that has none, via yaml.safe_dump."""
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    block = yaml.safe_dump(
        {"skills": [{"skill_id": s, "mode": "always"} for s in skill_ids]},
        sort_keys=False,
    ).rstrip("\n")
    path.write_text(text[:end] + "\n" + block + text[end:], encoding="utf-8")
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert abilities_of(fm) == skill_ids, "add_grant produced an unparseable block"


def prefixed(errors: list[str]) -> list[str]:
    """The errors that come from the skill-tool-grant check."""
    return [e for e in errors if e.startswith(ERROR_PREFIX)]


def run_validate(package_root: Path) -> tuple[list[str], str]:
    """In-process validate_agent_registry(package_root) -> (errors, stdout)."""
    import contextlib
    import io

    from registry_validator import validate_agent_registry

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        errors = validate_agent_registry(package_root)
    return errors, buf.getvalue()


def make_package(dest: Path) -> Path:
    """A minimal package root: real config + copied agent templates + skills link.

    No build.py spawn. The agent templates are copied so a test may mutate them.
    """
    dest.mkdir(parents=True, exist_ok=True)
    for entry in REPO_ROOT.iterdir():
        if entry.name in {".git", "config", "templates", "scripts", "unit_tests"}:
            continue
        (dest / entry.name).symlink_to(entry)
    shutil.copytree(REPO_ROOT / "config", dest / "config")
    (dest / "templates").mkdir()
    for entry in (REPO_ROOT / "templates").iterdir():
        if entry.name != "agents":
            (dest / "templates" / entry.name).symlink_to(entry)
    shutil.copytree(REAL_TEMPLATES, dest / "templates" / "agents")
    return dest


def make_clean_package(dest: Path) -> Path:
    """make_package, then grant `Skill` to every agent that holds a grant."""
    root = make_package(dest)
    for agent in derive_population(root / "templates" / "agents"):
        if agent["abilities"]:
            add_skill_tool(agent["path"])
    return root


def run_registry_cli(package_root: Path) -> subprocess.CompletedProcess[str]:
    """Run the real `python scripts/registry_validator.py` against package_root."""
    scripts = package_root / "scripts"
    if not scripts.exists():
        scripts.mkdir()
        for py in SCRIPTS_DIR.glob("*.py"):
            shutil.copy2(py, scripts / py.name)
    return subprocess.run(
        [sys.executable, str(scripts / "registry_validator.py")],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
