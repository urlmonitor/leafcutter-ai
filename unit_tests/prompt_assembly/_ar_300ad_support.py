"""Shared helpers for the AR-300a / AR-300d test files (slice 2, test-writer,
TDD red phase). Imports -- never edits -- the slice 1 helpers in
``_ar_300c_support.py``.

ASSUMED PRODUCTION CONTRACT FOR SLICE 2 (the ACs do not name these
identifiers, so the test-writer fixed them here; python-coder builds to them
unless a documented, justified reason changes them):

1. Delivery verifier -- NEW module ``scripts/agent_grant_delivery.py`` exposing::

       verify_grants_delivered(declarations, compiled_roots, *,
                               expected_prompt_count, known_skill_ids) -> dict

   ``declarations``: ``{template_stem: [skills entries]}`` for the agents that
   declare a grant (entries are the frontmatter ``skills`` shape). A compiled
   prompt whose stem is absent from it is an UNGRANTED agent.
   ``compiled_roots``: every platform root the build wrote (list of Path; a
   missing path or a broken symlink is an unreadable root, never skipped).
   ``expected_prompt_count``: how many compiled prompts the build produced on
   this run (all roots together), supplied by the caller from the build.
   ``known_skill_ids``: installed skill ids (used to recognise which rows of a
   compiled section NAME an ability, as opposed to prose).
   Never raises on an empty / short population -- it returns ``ok: False``.
   Returned verdict (ADR-037 shape)::

       {"ok": bool,
        "inspected_count": int,        # compiled prompts read, all roots
        "granted_count": int,          # distinct agents recognised as granted
        "conditional_grant_count": int,# conditional grants across granted agents
        "complete_count": int,         # (agent, root) = whole grant, ONE account
        "no_section_count": int,       # (agent, root) = ungranted, no account
        "expected_prompt_count": int,
        "roots_examined": [str, ...],
        "population_source": str,      # non-empty: where the population came from
        "findings": [ {...}, ... ]}

   Finding kinds (each finding is a dict with ``kind``):
     ``empty-population`` + ``side`` in {"compiled_prompts","declarations"}
         (both sides listed when both are empty);
     ``short-population`` + ``inspected`` + ``expected``;
     ``undelivered`` (granted agent, NO account) + ``agent`` + ``platform_root``
         + ``missing`` (sorted ids);
     ``short-section`` (granted agent, account names a strict subset);
     ``extra-ability`` (account names an id that was not granted) + ``extra``;
     ``second-account`` (more than one account) + ``accounts`` (int);
     ``unexpected-section`` (ungranted agent carrying an account).
   Every per-prompt finding carries ``agent`` (template stem) and
   ``platform_root`` (the root path as supplied, as str). Partition invariant:
   ``complete_count + no_section_count + (#distinct (agent, platform_root) in
   per-prompt findings) == inspected_count``.
   An "account" is a ``##``/``###`` section OUTSIDE code fences whose heading
   mentions skill(s)/abilit* AND which names at least one installed skill id
   as a table-row / list-item / sub-heading first token -- or whose heading is
   the bare delivered one ("Your Available Skills"/"Abilities"/...) even with
   no rows. A prose section that merely discusses skills is NOT an account.

2. In-place detector -- NEW module ``scripts/agent_inplace_abilities.py``::

       detect_inplace_abilities(templates_dir=None, *, known_skill_ids=None) -> dict

   Reads SOURCE templates (``templates_dir/*.md``, names starting ``_``
   skipped). ``templates_dir=None`` resolves the package's own
   ``templates/agents`` from the module location, never from cwd;
   ``known_skill_ids=None`` derives them from the sibling ``templates/skills``.
   Returns ``{"ok": bool, "examined_count": int, "stating_count": int,
   "findings": [{"template": "<file name>", "kind": "duplicate"|
   "contradiction", "inplace_abilities": [ids], "declared_abilities": [ids]}]}``.
   ``ok`` is False when ``examined_count == 0`` and otherwise True even when
   findings exist (findings are reported by severity; zero stating templates
   on a non-empty population is a legitimate clean tree). ``duplicate`` = the
   in-place id set equals the declared id set; any other difference
   (subset, superset, disjoint, or no declaration) = ``contradiction``.
   A template states ITS OWN grant when a prose (non-fenced) section whose
   heading mentions skill(s)/abilit* names installed skill ids as rows;
   prose that merely mentions skills does not.
   ``compile_agent_template`` ALSO reports such a template by name while
   compiling it (any of stdout / stderr / a log record at WARNING+ carrying
   the template file name and the word ``duplicate`` or ``contradiction``).

3. Leftover retired marker -- ``build_placeholder_detection.scan_for_placeholders
   (target_root, paths=[template])`` returns a hit whose ``marker`` contains
   ``my_skills_used`` (resp. ``my_spawn_allowlist``) and whose ``path`` ends
   with the template's file name, for a template whose body carries the retired
   token on a line of its own. ``compile_agent_template`` strips the
   ``{{my_skills_used}}`` token from the compiled prompt (never substitutes,
   never uses it as a placement site) and ALSO reports the leftover by template
   file name + token while compiling (same channels as 2). Whether the
   retired-token SET is derived from AR-300b-2's registration is NOT pinned
   here: that registration does not exist yet (slice 3).

4. ``build_phases.build_agents(target_root, config, dry_run, force)`` (the real
   build phase, force=True is the CLI default) is exercised IN-PROCESS over a
   small package slice by pointing ``build_phases.PACKAGE_ROOT / TEMPLATES_DIR
   / REGISTRY_PATH / SKILLS_TEMPLATE_DIR`` at the slice (monkeypatch). It
   writes ``<target>/agents`` and ``<target>/gemini/agents`` -- the same two
   platform roots build.py writes. That is a mutate-then-build WITHOUT a
   build.py spawn, so no test here needs ``shared_layout_mutator``.

MUTATION SEAM (tests only): env ``AR300AD_MUTATION=<name>`` makes this module
break the delivery behaviour so a green test can be shown to go red:
``noop_append`` (nothing delivered; layout readers see section-stripped
copies), ``empty_list_heading`` (an explicit empty grant emits a bare
heading), ``drop_last_ability`` (short section), ``registry_gated`` (deliver
only for agents the REGISTRY already lists), ``shared_leak`` (an ability seen
on one agent leaks to every agent compiled later), ``accumulate`` (a section
remembers abilities from earlier builds). Production code is never edited.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300c_support import (  # noqa: E402,F401
    GRANT_KEY,
    REPO_ROOT,
    SCRIPTS_DIR,
    compiled_agent_roots,
    declared_entries,
    declared_ids,
    installed_skill_ids,
    parse_frontmatter,
    template_frontmatter,
    write_template,
)
from template_compiler import compile_agent_template  # noqa: E402

TEMPLATES_AGENTS = REPO_ROOT / "templates" / "agents"
RETIRED_SKILLS_TOKEN = "{{my_skills_used}}"
RETIRED_SPAWN_TOKEN = "{{my_spawn_allowlist}}"
MUTATION = os.environ.get("AR300AD_MUTATION", "")

ABILITIES_HEADING_RE = re.compile(
    r"^#{2,3}\s+(?:your\s+)?(?:available\s+)?(?:skills?|abilit(?:y|ies))\s*$", re.IGNORECASE
)
_SKILLISH_HEADING_RE = re.compile(r"^#{2,3}\s+.*\b(abilit\w*|skills?)\b", re.IGNORECASE)
_NAMED_RE = re.compile(r"^\s*(?:\||[-*]|#{3,6})\s*[`*]*([a-z][a-z0-9_-]*)")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+\S")


# ----------------------------------------------------------------- mutations
def _install_mutation() -> None:
    import template_compiler as tc
    from agent_ability_verdict import normalize_entries

    original = tc.append_declared_skills
    seen: set[str] = set()
    memory: dict[str, set[str]] = {}
    registry_names = {
        a["id"] for a in json.loads((REPO_ROOT / "config" / "agent_registry.json").read_text("utf-8"))["agents"]
    }

    def with_skills(fm: dict, ids_in_order: list[str], base: list[dict]) -> dict:
        by_id = {e["skill_id"]: e for e in base}
        entries = [by_id.get(i, {"skill_id": i, "mode": "always"}) for i in ids_in_order]
        out = dict(fm)
        out[GRANT_KEY] = entries
        return out

    def patched(body, fm, skills_root, **kwargs):
        # **kwargs forwards whatever the real compiler passes (e.g. ``agent=<stem>``)
        # so registration still happens wherever a mutation delegates to the original.
        entries = normalize_entries(fm.get(GRANT_KEY))
        if MUTATION == "noop_append":
            return body
        if MUTATION == "empty_list_heading":
            if GRANT_KEY in fm and not fm[GRANT_KEY]:
                return body.rstrip("\n") + "\n\n## Your Available Skills\n\n| Skill | Mode | Description |\n|---|---|---|\n"
            return original(body, fm, skills_root, **kwargs)
        if MUTATION == "heading_for_all":
            if entries:
                return original(body, fm, skills_root, **kwargs)
            return body.rstrip("\n") + "\n\n## Your Available Skills\n\n| Skill | Mode | Description |\n|---|---|---|\n"
        if MUTATION == "drop_last_ability":
            return original(body, {**fm, GRANT_KEY: [e for e in entries[:-1]]}, skills_root, **kwargs)
        if MUTATION == "registry_gated":
            return original(body, fm, skills_root, **kwargs) if fm.get("name") in registry_names else body
        if MUTATION == "shared_leak":
            seen.update(e["skill_id"] for e in entries)
            return original(body, with_skills(fm, sorted(seen), entries), skills_root, **kwargs)
        if MUTATION == "accumulate":
            mem = memory.setdefault(str(fm.get("name")), set())
            mem.update(e["skill_id"] for e in entries)
            return original(body, with_skills(fm, sorted(mem), entries), skills_root, **kwargs)
        return original(body, fm, skills_root, **kwargs)

    tc.append_declared_skills = patched


if MUTATION in {"noop_append", "empty_list_heading", "drop_last_ability", "heading_for_all",
                "registry_gated", "shared_leak", "accumulate"}:
    _install_mutation()

if MUTATION == "gate_demands_condition":
    # a wrong gate that demands a condition on EVERY grant, ``always`` included
    import agent_ability_gate as _gate

    _orig_errors = _gate.ability_errors

    def _strict_errors(pkg, config, *a, **kw):
        errs = list(_orig_errors(pkg, config, *a, **kw))
        for tpl in sorted((Path(pkg) / "templates" / "agents").glob("*.md")):
            for e in (template_frontmatter(tpl).get(GRANT_KEY) or []):
                if isinstance(e, dict) and not str(e.get("condition") or "").strip():
                    errs.append(f"{tpl.name}: grant {e.get('skill_id')} has no condition")
        return errs

    _gate.ability_errors = _strict_errors

if MUTATION == "token_survives":
    # a compiler that leaves the retired token behind as residue
    import template_compiler as _tc

    _orig_compile = _tc.compile_agent_template

    def _residue_compile(*a, **kw):
        return _orig_compile(*a, **kw).rstrip("\n") + "\n\n{{my_skills_used}}\n"

    compile_agent_template = _residue_compile


def strip_delivered_sections(text: str) -> str:
    """Remove every bare abilities section (heading through the next ``## ``)."""
    out, skipping = [], False
    for line in text.split("\n"):
        if line.startswith("## "):
            skipping = bool(ABILITIES_HEADING_RE.match(line))
            if skipping:
                continue
        if not skipping:
            out.append(line)
    return "\n".join(out).rstrip("\n") + "\n"


def layout_roots(layout: Path) -> list[Path]:
    """Compiled agent-prompt roots of a deployed layout (declared output root,
    never the ``.claude/agents`` shim). Under ``AR300AD_MUTATION=noop_append``
    returns section-stripped COPIES so a green reader can be shown to go red."""
    roots = compiled_agent_roots(layout)
    if MUTATION == "heading_for_all":
        tmp = Path(tempfile.mkdtemp(prefix="ar300ad_mut_"))
        out = []
        for root in roots:
            dst = tmp / root.relative_to(layout)
            shutil.copytree(root, dst)
            decl = set(real_declarations())
            for md in agent_prompts(dst):
                if md.stem not in decl:
                    md.write_text(md.read_text(encoding="utf-8").rstrip("\n")
                                  + "\n\n## Your Available Skills\n\n| Skill | Mode | Description |\n|---|---|---|\n",
                                  encoding="utf-8")
            out.append(dst)
        return out
    if MUTATION != "noop_append":
        return roots
    tmp = Path(tempfile.mkdtemp(prefix="ar300ad_mut_"))
    out = []
    for root in roots:
        dst = tmp / root.relative_to(layout)
        shutil.copytree(root, dst)
        for md in dst.glob("*.md"):
            md.write_text(strip_delivered_sections(md.read_text(encoding="utf-8")), encoding="utf-8")
        out.append(dst)
    return out


# --------------------------------------------------------- compiled-prompt reading
def prose_lines(text: str):
    """Yield the lines of ``text`` that are outside code fences."""
    open_ch = None
    for line in text.splitlines():
        m = _FENCE_RE.match(line)
        if m:
            ch = m.group(1)[0]
            if open_ch is None:
                open_ch = ch
                continue
            if ch == open_ch:
                open_ch = None
                continue
        if open_ch is None:
            yield line


def accounts(text: str, installed: set[str]) -> list[dict]:
    """Every account of the agent's abilities in ``text`` (see contract 1).
    Anchored on structure (heading + installed-id rows), never on a bare
    word count; fenced examples and prose sections are ignored."""
    found, cur = [], None
    for line in prose_lines(text):
        hm = _HEADING_LINE_RE.match(line)
        if hm:
            level = len(hm.group(1))
            if cur is not None and level <= cur["level"]:
                found.append(cur)
                cur = None
            if cur is None:
                if 2 <= level <= 3 and _SKILLISH_HEADING_RE.match(line):
                    cur = {"heading": line.strip(), "level": level, "ids": [],
                           "bare_ok": bool(ABILITIES_HEADING_RE.match(line))}
                continue
        if cur is not None:
            n = _NAMED_RE.match(line)
            if n and n.group(1) in installed:
                cur["ids"].append(n.group(1))
    if cur is not None:
        found.append(cur)
    return [a for a in found if a["ids"] or a["bare_ok"]]


def named_in_accounts(text: str, installed: set[str]) -> set[str]:
    return {i for a in accounts(text, installed) for i in a["ids"]}


def abilities_heading_lines(text: str) -> list[str]:
    return [ln for ln in prose_lines(text) if ABILITIES_HEADING_RE.match(ln)]


def ability_rows(text: str, installed: set[str]) -> dict[str, list[str]]:
    """skill id -> the account lines (rows) that name it."""
    rows: dict[str, list[str]] = {}
    in_account = False
    heading_level = 0
    for line in prose_lines(text):
        hm = _HEADING_LINE_RE.match(line)
        if hm:
            level = len(hm.group(1))
            if in_account and level <= heading_level:
                in_account = False
            if not in_account and 2 <= level <= 3 and _SKILLISH_HEADING_RE.match(line):
                in_account, heading_level = True, level
                continue
        if in_account:
            n = _NAMED_RE.match(line)
            if n and n.group(1) in installed:
                rows.setdefault(n.group(1), []).append(line)
    return rows


def skill_description(skill_md: Path) -> str:
    """Independent read of a SKILL.md frontmatter ``description`` (normalised
    the way a table cell is: whitespace collapsed, ``|`` escaped)."""
    text = skill_md.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    fm = yaml.safe_load(text[3:end]) or {}
    return " ".join(str(fm.get("description", "")).replace("|", "\\|").split())


# ------------------------------------------------------------------ fixtures
def make_skill(root: Path, skill_id: str, description: str) -> Path:
    """Write a fixture skill whose frontmatter comes from the real serializer."""
    d = root / skill_id
    d.mkdir(parents=True, exist_ok=True)
    fm = yaml.safe_dump({"name": skill_id, "description": description}, sort_keys=False).rstrip()
    (d / "SKILL.md").write_text(f"---\n{fm}\n---\n\nbody for {skill_id}\n", encoding="utf-8")
    return d


def agent_fm(name: str, skills=None, tools: str = "Bash, Read") -> dict:
    fm = {"name": name, "description": f"{name} fixture agent", "model": "sonnet", "tools": tools}
    if skills is not None:
        fm[GRANT_KEY] = skills
    return fm


def planted_package(base: Path, templates: dict, skills: dict[str, str],
                    registry_agents: list[dict] | None = None) -> Path:
    """A minimal package slice: ``templates/agents`` from ``templates``
    (``{stem: (frontmatter dict, body)}``), ``templates/skills`` fixture skills
    (``{id: description}``) and ``config/agent_registry.json``."""
    pkg = base / "pkg"
    for stem, (fm, body) in templates.items():
        write_template(pkg / "templates" / "agents" / f"{stem}.md", fm, body)
    for sid, desc in skills.items():
        make_skill(pkg / "templates" / "skills", sid, desc)
    (pkg / "config").mkdir(parents=True, exist_ok=True)
    (pkg / "config" / "agent_registry.json").write_text(
        json.dumps({"agents": registry_agents or []}, indent=2), encoding="utf-8")
    return pkg


def real_slice(base: Path) -> Path:
    """The real, current templates/agents + templates/skills + registry, copied
    (the 'tracked tree' the build reads)."""
    pkg = base / "pkg"
    shutil.copytree(TEMPLATES_AGENTS, pkg / "templates" / "agents")
    shutil.copytree(REPO_ROOT / "templates" / "skills", pkg / "templates" / "skills")
    (pkg / "config").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "config" / "agent_registry.json", pkg / "config" / "agent_registry.json")
    return pkg


def build_package(pkg: Path, target: Path, monkeypatch, *, allow_unchanged: bool = False) -> list[Path]:
    """Run the REAL ``build_agents`` phase in-process over ``pkg`` into
    ``target``; return the two platform roots it wrote (claude + gemini)."""
    import build_phases

    monkeypatch.setattr(build_phases, "PACKAGE_ROOT", pkg)
    monkeypatch.setattr(build_phases, "TEMPLATES_DIR", pkg / "templates")
    monkeypatch.setattr(build_phases, "REGISTRY_PATH", pkg / "config" / "agent_registry.json")
    monkeypatch.setattr(build_phases, "SKILLS_TEMPLATE_DIR", pkg / "templates" / "skills")
    written = build_phases.build_agents(target, {"output_root": ".leafcutter"}, False, True)
    assert written > 0 or allow_unchanged, "build_agents wrote nothing (empty build)"
    roots = [target / "agents", target / "gemini" / "agents"]
    assert all(any(r.glob("*.md")) for r in roots), f"a platform root is empty: {roots}"
    return roots


def compile_with(template_path: Path, *, agents=None, skills_root: Path | None = None) -> str:
    return compile_agent_template(
        template_path, {"output_root": ".leafcutter"},
        registry_path=None, agents=agents, skills_root=skills_root,
    )


def write_compiled_tree(base: Path, templates: dict, skills_root: Path,
                        root_names=("agents", "gemini/agents")) -> list[Path]:
    """Compile ``templates`` with the REAL compiler and write the prompts into
    each platform root (authentic compiled bytes, never a typed literal)."""
    src = base / "src_templates"
    roots = [base / "compiled" / name for name in root_names]
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
    for stem, (fm, body) in templates.items():
        tpl = write_template(src / f"{stem}.md", fm, body)
        text = compile_with(tpl, agents=None, skills_root=skills_root)
        for root in roots:
            (root / f"{stem}.md").write_text(text, encoding="utf-8")
    return roots


def is_agent_file(path: Path) -> bool:
    """An agent definition/prompt is a ``.md`` whose own YAML frontmatter carries a
    ``name`` (derived from the file's content, not from a list of excluded names:
    README.md and the ``_*`` partials declare none, so they are not agents)."""
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return isinstance(fm, dict) and bool(fm.get("name"))


def agent_prompts(root: Path) -> list[Path]:
    """The agent prompts in a compiled root (non-agent files such as README.md excluded)."""
    return [p for p in sorted(root.glob("*.md")) if is_agent_file(p)]


def read_prompts(root: Path) -> dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8") for p in agent_prompts(root)}


def snapshot_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def changed_files(before: dict[str, str], after: dict[str, str]) -> set[str]:
    keys = set(before) | set(after)
    if MUTATION == "diff_blind":  # a file-set check blind to config/ changes
        keys = {k for k in keys if not k.startswith("config/")}
    return {k for k in keys if before.get(k) != after.get(k)}


# ------------------------------------------------------------ real-tree reads
def source_templates() -> list[Path]:
    return [t for t in sorted(TEMPLATES_AGENTS.glob("*.md"))
            if not t.name.startswith("_") and is_agent_file(t)]


def real_declarations() -> dict[str, list]:
    """{template stem: raw ``skills`` entries} for every real template that
    declares a non-empty grant (derived by parsing, never enumerated)."""
    out = {}
    for tpl in source_templates():
        entries = template_frontmatter(tpl).get(GRANT_KEY) or []
        if entries:
            out[tpl.stem] = entries
    return out


# --------------------------------------------------------- production modules
def delivery_module():
    """Import the (not-yet-written) delivery verifier module, fresh failure
    if absent so the red is a clear test failure."""
    return importlib.import_module("agent_grant_delivery")


def inplace_module():
    return importlib.import_module("agent_inplace_abilities")


def verdict_for(declarations: dict, roots: list[Path], *, expected: int, known: set[str]) -> dict:
    return delivery_module().verify_grants_delivered(
        declarations, roots, expected_prompt_count=expected, known_skill_ids=known)


def per_prompt_findings(verdict: dict) -> list[dict]:
    return [f for f in verdict["findings"] if "agent" in f]


def captured_report(capsys, caplog) -> str:
    out, err = capsys.readouterr()
    return out + "\n" + err + "\n" + caplog.text
