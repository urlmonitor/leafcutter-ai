"""Shared helpers for the AR-300 spawn-allowlist slice (slice 5, test-writer, TDD red
phase). Imports -- never edits -- the slice 1-4 helpers.

ASSUMED PRODUCTION CONTRACT FOR SLICE 5. The ACs fix the frontmatter key
(``spawn_allowlist``), the macro (``__ticket_phase_agents__``), the preparation name
(``spawn_allowlist``) and the verdict field names; they do not name the modules, so the
test-writer fixed the following (python-coder builds to them unless a documented,
justified reason changes them). Everything else is exercised through EXISTING entry
points (``compile_agent_template``, ``build_phases.build_agents``,
``agent_ability_gate.refuse_on_ability_findings``,
``agent_preparation_delivery.verify_preparations_delivered`` /
``refuse_on_undelivered_preparations``, ``registry_validator.validate_agent_registry``,
the ``transform_agent_registry.py`` hook CLI).

1. Declaration: frontmatter key ``spawn_allowlist`` -- a YAML list of agent ids, sibling
   of ``tools:``; ``__ticket_phase_agents__`` is ONE list item, resolved on every compile
   against the registry's ``is_ticket_phase`` flags. Absent key == empty list == no
   permission. The registry's own ``spawn_allowlist`` is a DERIVED copy.
2. Delivery: ``compile_agent_template`` appends ONE generated section for an agent with a
   non-empty declaration (``register_preparation('spawn_allowlist', <prompt stem>,
   <section text>, True)``, computed through ``compute_preparation``); none otherwise.
   The section is located FORMAT-AGNOSTICALLY (see ``spawn_accounts``): a ``##``/``###``
   heading whose text contains "sub-agent(s)" outside code fences, naming agent ids as the
   first token of table rows / list items / sub-headings (or the bare heading "Your
   Available Sub-Agents" with no rows). Role/Tier columns are optional.
3. Migration (one-shot, NOT in the build): ``python scripts/migrate_agent_spawn_allowlist.py
   --package-root DIR [--report JSON]``. Inserts ONLY the ``spawn_allowlist`` key into each
   template's frontmatter; writes a report ``{"agents": [{"agent": id, "sub_agents":
   [{"id": id, "sources": ["registry"|"frontmatter"|"body_table", ...]}]}],
   "disagreeing_agents": [id, ...], "source_holder_counts": {"registry": n, "frontmatter":
   n, "body_table": n}}`` (a holder = an agent the source gives >= 1 permission). Exit 0.
4. Verdict: ``agent_ability_verdict.verify_spawn_allowlists(declarations, registry_agents,
   *, packaged_agents_root, project_root, output_root_name=".leafcutter",
   ticket_phase_ids=None) -> dict`` with ``examined_count`` (union of declaring agents and
   agents whose registry copy is non-empty), ``agents_examined`` (declaring agents whose
   sub-agents were resolved), ``sub_agents_resolved``, ``ok`` and ``findings``. Comparison
   findings ``{agent, field: "spawn_allowlist", declared, recorded, kind: divergent |
   declaration-only | record-only, severity: "report"}``; resolution findings ``{agent,
   sub_agent, kind: "unresolvable-sub-agent", lookups_failed: ["packaged"[, "project_local"]
   ...], severity: "refuse"}`` (``sub_agent`` is the macro token for an empty macro).
   ``declarations`` holds the declared lists verbatim (macro literal). A zero population
   raises ``agent_ability_verdict.EmptyPopulationError`` (a ``ValueError``). The same
   verdict feeds ``refuse_on_ability_findings`` (report-only comparison, refusing resolution).
5. Tool grant: ``skill_tool_grant_validator.check_spawn_tool_grants(template_dir)`` returns
   ``{"examined_count", "granted_count", "findings": [{"agent", "declared_sub_agents",
   "declared_tools", "suggested_action"}]}`` exactly like ``check_skill_tool_grants`` but for
   the (``spawn_allowlist``, ``Agent``) pair, sharing ONE ``tools:`` parse with it;
   ``validate_agent_registry`` includes its errors in the same pass.

MUTATION SEAM: none (production names are not fixed enough to patch); wrong-version
proofs are by construction in each test (exact set equality, byte comparison).
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402,F401
    REPO_ROOT,
    SCRIPTS_DIR,
    agent_fm,
    agent_prompts,
    build_package,
    captured_report,
    compile_with,
    planted_package,
    prose_lines,
    read_prompts,
    real_slice,
    snapshot_tree,
    source_templates,
    template_frontmatter,
    write_template,
)
from _ar_300b_support import BODY, SKILLS, Built, grant, prep_module  # noqa: E402,F401
from _ar_300c_support import PRISTINE_REGISTRY, parse_frontmatter, strip_frontmatter_keys  # noqa: E402,F401

KEY = "spawn_allowlist"
MACRO = "__ticket_phase_agents__"
HERE = Path(__file__).resolve().parent
PRISTINE_SPAWN_TEMPLATES = HERE / "fixtures_ar_300e" / "templates_pre_spawn_migration"
TABLE_STEMS = ("business-analyst", "frontend-coder", "test-writer", "python-coder", "architect-review")
FRONTMATTER_STEMS = ("frontend-coder", "onboard", "ac-triage", "onboard-config-section")
SPAWN_MIGRATION_SCRIPT = Path(
    os.environ.get("AR300E_MIGRATION_SCRIPT") or SCRIPTS_DIR / "migrate_agent_spawn_allowlist.py")
DEEP_TARGETS = ("architect-review-deep", "conflict-resolver-deep")

_SUB_HEADING_RE = re.compile(r"^#{2,3}\s+.*\b(?:sub-?agents?|spawn\s+allowlist)\b", re.IGNORECASE)
_BARE_HEADING_RE = re.compile(r"^#{2,3}\s+(?:your\s+)?(?:available\s+|permitted\s+)?sub-?agents?\s*$", re.IGNORECASE)
# A row of an account: table row, bullet, numbered item or sub-heading naming an id first.
_NAMED_RE = re.compile(r"^\s*(?:\||[-*]|\d+[.)]|#{3,6})\s*[`*]*([a-z][a-z0-9_-]*)")
# Inside a code fence a hand-written LIST is one id per line (optionally bulleted / numbered).
_FENCED_ID_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])?\s*[`*]*([a-z][a-z0-9_-]*)[`*]*\s*(?:[:—–-].*)?$")
_FENCE_LINE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
HAND_WRITTEN_STEMS = TABLE_STEMS + ("ticket-supervisor",)
_HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+\S")
_TABLE_ROW_RE = re.compile(r"^\|\s*([a-z][a-z0-9-]*)\s*\|")


# ------------------------------------------------------------------ declarations
def resolve_declared(declared: list[str], registry_agents: list[dict]) -> list[str]:
    """Expand the macro against ``is_ticket_phase`` (registry order), dedupe, keep order."""
    out: list[str] = []
    for item in declared:
        for sid in ([a["id"] for a in registry_agents if a.get("is_ticket_phase")] if item == MACRO else [item]):
            if sid not in out:
                out.append(sid)
    return out


def real_registry() -> list[dict]:
    return json.loads((REPO_ROOT / "config" / "agent_registry.json").read_text("utf-8"))["agents"]


def real_spawn_declarations() -> dict[str, list[str]]:
    """{template stem: declared list} for every real template with a NON-EMPTY declaration."""
    out = {}
    for tpl in source_templates():
        decl = template_frontmatter(tpl).get(KEY) or []
        if decl:
            out[tpl.stem] = list(decl)
    return out


def real_known_ids() -> set[str]:
    return {a["id"] for a in real_registry()} | {t.stem for t in source_templates()}


# --------------------------------------------------------------- compiled prompts
def spawn_accounts(text: str, known: set[str]) -> list[dict]:
    """Every account of the agent's permitted sub-agents in ``text`` (contract item 2): a
    ``##``/``###`` heading about sub-agents / the spawn allowlist whose section NAMES known
    agent ids as table rows, bullets, numbered items, sub-headings, or one-id-per-line inside
    a fenced block (ticket-supervisor's former shape). Anchored on structure, never on a bare
    word count: prose that merely mentions the heading, and a heading over nothing that
    names an agent, are not accounts."""
    found, cur, fence = [], None, None
    for line in text.splitlines():
        fm = _FENCE_LINE_RE.match(line)
        if fm:
            char = fm.group(1)[0]
            if fence is None:
                fence = char
                continue
            if char == fence:
                fence = None
                continue
        if fence is not None:
            m = _FENCED_ID_RE.match(line) if cur is not None else None
            if m and m.group(1) in known:
                cur["ids"].append(m.group(1))
            continue
        hm = _HEADING_LINE_RE.match(line)
        if hm:
            level = len(hm.group(1))
            if cur is not None and level <= cur["level"]:
                found.append(cur)
                cur = None
            if cur is None:
                if 2 <= level <= 3 and _SUB_HEADING_RE.match(line):
                    cur = {"heading": line.strip(), "level": level, "ids": [],
                           "bare_ok": bool(_BARE_HEADING_RE.match(line))}
                continue
        if cur is not None:
            m = _NAMED_RE.match(line)
            if m and m.group(1) in known:
                cur["ids"].append(m.group(1))
    if cur is not None:
        found.append(cur)
    return [a for a in found if a["ids"] or a["bare_ok"]]


def named_sub_agents(text: str, known: set[str]) -> set[str]:
    return {i for a in spawn_accounts(text, known) for i in a["ids"]}


def single_account_report(roots: list[Path], resolved: dict[str, list[str]], known: set[str]) -> dict:
    """The whole-population single-account assertion: EVERY compiled prompt in EVERY root
    is examined (never a list of known templates). An agent is an offender when its
    prompt does not carry exactly one account (zero when nothing is permitted), or the
    account names a sub-agent it was not permitted, omits one it was, or names one twice."""
    examined, offenders = 0, []
    for root in roots:
        for prompt in agent_prompts(root):
            examined += 1
            accounts = spawn_accounts(prompt.read_text(encoding="utf-8"), known)
            ids = [i for a in accounts for i in a["ids"]]
            want = set(resolved.get(prompt.stem, []))
            if len(accounts) != (1 if want else 0) or set(ids) != want or len(ids) != len(set(ids)):
                offenders.append({"agent": prompt.stem, "root": str(root), "accounts": len(accounts),
                                  "named": sorted(set(ids)), "want": sorted(want)})
    return {"examined": examined, "offenders": offenders}


# ------------------------------------------------------------- planted packages
def sfm(name: str, spawn=None, tools: str = "Bash, Read, Agent", skills=None) -> dict:
    fm = agent_fm(name, skills, tools)
    if spawn is not None:
        fm[KEY] = list(spawn)
    return fm


def records_for(templates: dict, *, ticket_phase=(), registry_spawn=None) -> list[dict]:
    """Registry records consistent with ``templates``; ``registry_spawn`` overrides the
    derived copy per agent (default: the declaration as written)."""
    out = []
    for stem, (fm, _body) in templates.items():
        copy = (registry_spawn or {}).get(stem, fm.get(KEY, []))
        out.append({"id": stem, "template_path": f"templates/agents/{stem}.md", "role": f"{stem} role",
                    "tier": "phase", "is_ticket_phase": stem in ticket_phase, "spawn_allowlist": list(copy),
                    "skills_invoked": [dict(e) for e in fm.get("skills", [])]})
    return out


def spawn_package(base: Path, templates: dict, *, ticket_phase=(), registry_spawn=None, extra_records=()) -> Path:
    records = records_for(templates, ticket_phase=ticket_phase, registry_spawn=registry_spawn)
    return planted_package(base, templates, SKILLS, registry_agents=records + list(extra_records))


def with_skilled(templates: dict) -> dict:
    """Add one skill-granting agent so the ability gate's skills population is non-empty
    (the skills half of the verdict is not under test here)."""
    return {**templates, "zz-skilled": (sfm("zz-skilled", skills=grant("zz-alpha")), BODY)}


def build_in(pkg: Path, out: Path, monkeypatch, *, allow_unchanged: bool | None = None) -> list[Path]:
    """The REAL build_agents phase in-process. A REbuild into an output root that already
    holds prompts may legitimately write nothing (an edit that changes no output is exactly
    what some tests prove), so only a FIRST build is asserted non-empty."""
    if allow_unchanged is None:
        allow_unchanged = any((out / "agents").glob("*.md"))
    return build_package(pkg, out, monkeypatch, allow_unchanged=allow_unchanged)


def edit_declaration(pkg: Path, stem: str, spawn) -> None:
    """Rewrite ONLY ``stem``'s frontmatter ``spawn_allowlist`` (None removes the key)."""
    path = pkg / "templates" / "agents" / f"{stem}.md"
    fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    fm = {k: v for k, v in fm.items() if k != KEY}
    if spawn is not None:
        fm[KEY] = list(spawn)
    write_template(path, fm, body.lstrip("\n"))


def run_gate(pkg: Path, capsys, dry_run: bool = False) -> tuple[int, str]:
    """The build's ability guard over ``pkg``: (exit code, everything it printed)."""
    import agent_ability_gate

    rc = agent_ability_gate.refuse_on_ability_findings(pkg, {"output_root": ".leafcutter"}, dry_run)
    out = capsys.readouterr()
    return rc, out.out + "\n" + out.err


def spawn_verdict(declarations: dict, registry_agents: list[dict], pkg: Path, **kw) -> dict:
    import agent_ability_verdict as mod

    fn = getattr(mod, "verify_spawn_allowlists", None)
    assert fn is not None, "agent_ability_verdict.verify_spawn_allowlists is not implemented"
    return fn(declarations, registry_agents, packaged_agents_root=pkg / "templates" / "agents",
              project_root=pkg.parent, **kw)


def spawn_registrations(built_preparations: list[dict]) -> list[dict]:
    return [p for p in built_preparations if p["preparation_name"] == "spawn_allowlist"]


def strip_spawn_sections(text: str) -> str:
    """Remove every sub-agent account section (heading through the next ``## ``)."""
    out, skipping = [], False
    for line in text.split("\n"):
        if line.startswith("## "):
            skipping = bool(_SUB_HEADING_RE.match(line))
            if skipping:
                continue
        if not skipping:
            out.append(line)
    return "\n".join(out).rstrip("\n") + "\n"


# ------------------------------------------------------ pristine (pre-migration) data
def copy_pristine_spawn_package(dst: Path) -> Path:
    """The real tree in its PRE-spawn-migration state: the pristine registry, the real
    templates with every ``spawn_allowlist`` key stripped at text level, then the
    verbatim pre-migration snapshots of the eight templates that carried a source of
    their own overlaid (five hand-written tables, four frontmatter keys)."""
    (dst / "config").mkdir(parents=True)
    shutil.copy2(PRISTINE_REGISTRY, dst / "config" / "agent_registry.json")
    agents = dst / "templates" / "agents"
    shutil.copytree(REPO_ROOT / "templates" / "agents", agents)
    for tpl in sorted(agents.glob("*.md")):
        new, removed = strip_frontmatter_keys(tpl.read_text(encoding="utf-8"), (KEY,))
        if removed:
            tpl.write_text(new, encoding="utf-8")
    snaps = sorted(PRISTINE_SPAWN_TEMPLATES.glob("*.md"))
    assert len(snaps) == len(TABLE_STEMS) + len(FRONTMATTER_STEMS) - 1, f"pristine snapshots missing: {snaps}"
    for snap in snaps:
        shutil.copy2(snap, agents / snap.name)
    tabled = sorted(t.stem for t in agents.glob("*.md")
                    if "## Your Available Sub-Agents" in t.read_text(encoding="utf-8").split("\n"))
    assert tabled == sorted(TABLE_STEMS), f"pristine guard: hand-written tables on {tabled}"
    keyed = sorted(t.stem for t in agents.glob("*.md") if KEY in template_frontmatter(t))
    assert keyed == sorted(FRONTMATTER_STEMS), f"pristine guard: frontmatter keys on {keyed}"
    return dst


def source_sets(pkg: Path) -> dict[str, dict]:
    """INDEPENDENT oracle: per agent id, what each of the three sources records, parsed
    from the pristine package without any production code."""
    registry = json.loads((pkg / "config" / "agent_registry.json").read_text("utf-8"))["agents"]
    out: dict[str, dict] = {}
    for rec in registry:
        tp = rec.get("template_path")
        if not tp or not (pkg / tp).is_file():
            continue
        fm, body = parse_frontmatter((pkg / tp).read_text(encoding="utf-8"))
        table, inside = [], False
        for line in body.split("\n"):
            if line.strip() == "## Your Available Sub-Agents":
                inside = True
                continue
            if inside and line.startswith("## "):
                break
            m = _TABLE_ROW_RE.match(line) if inside else None
            if m and m.group(1) != "agent":
                table.append(m.group(1))
        out[rec["id"]] = {"stem": Path(tp).stem, "registry": list(rec.get("spawn_allowlist") or []),
                          "has_key": KEY in fm, "frontmatter": list(fm.get(KEY) or []), "body_table": table}
    return out


def union_of(sources: dict) -> set[str]:
    return set(sources["registry"]) | set(sources["frontmatter"]) | set(sources["body_table"])


def run_spawn_migration(pkg: Path, report: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SPAWN_MIGRATION_SCRIPT), "--package-root", str(pkg),
                           "--report", str(report)], capture_output=True, text=True, timeout=120, check=False)


def migrate_spawn_or_fail(pkg: Path) -> dict:
    """Run the real migration CLI; return its parsed report (red when absent / non-zero)."""
    report = pkg.parent / (pkg.name + "_spawn_report.json")
    proc = run_spawn_migration(pkg, report)
    assert proc.returncode == 0, f"spawn migration CLI failed (exit {proc.returncode}): {proc.stderr[-600:]}"
    assert report.is_file(), "spawn migration wrote no report"
    return json.loads(report.read_text(encoding="utf-8"))


def declared_after(pkg: Path, stem: str) -> list[str] | None:
    """The template's declared list after migration (None when the key is absent)."""
    fm = template_frontmatter(pkg / "templates" / "agents" / f"{stem}.md")
    return list(fm[KEY]) if KEY in fm else None


def template_bytes(pkg: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted((pkg / "templates" / "agents").glob("*.md"))}


def real_build_prompts(tmp_path: Path, monkeypatch):
    """The REAL ``build_agents`` in-process over a copy of the actual tree, registry reset
    first; returns (roots, preparations)."""
    mod = prep_module()
    mod.reset_preparations()
    pkg = real_slice(tmp_path / "src")
    roots = build_package(pkg, tmp_path / "project" / ".leafcutter", monkeypatch)
    return roots, list(mod.get_preparations())


def yaml_block(key: str, value) -> str:
    return yaml.safe_dump({key: value}, sort_keys=False).rstrip("\n")


def workers(*ids: str) -> dict:
    """Plain agents (declare nothing) so that sub-agent ids resolve to a packaged template."""
    return {i: (sfm(i, tools="Bash, Read"), BODY) for i in ids}


def stale_compiled(project_root: Path, stem: str) -> None:
    """Leave a compiled prompt for ``stem`` -- authentic bytes from the real compiler -- in
    both platform roots of ``project_root``'s output root, as an earlier build would have
    (the template it came from is NOT part of the package)."""
    tpl = write_template(project_root / "_stale_src" / f"{stem}.md", sfm(stem, tools="Bash, Read"), BODY)
    text = compile_with(tpl, agents=None, skills_root=None)
    for sub in ("agents", "gemini/agents"):
        root = project_root / ".leafcutter" / sub
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{stem}.md").write_text(text, encoding="utf-8")


def fresh_spawn_build(tmp_path: Path, monkeypatch, templates: dict, **kw):
    """Reset the run registry, run the REAL ``build_agents`` in-process over a planted
    package; returns (prep module, package, compiled roots, registered preparations)."""
    mod = prep_module()
    mod.reset_preparations()
    pkg = spawn_package(tmp_path / "src", templates, **kw)
    roots = build_in(pkg, tmp_path / "project" / ".leafcutter", monkeypatch)
    return mod, pkg, roots, list(mod.get_preparations())


def has_sub_agent_heading(text: str) -> bool:
    """Any prose heading about sub-agents at all (a bare heading over nothing included)."""
    return any(_SUB_HEADING_RE.match(line) for line in prose_lines(text))


def set_registry(pkg: Path, edit) -> None:
    """Apply ``edit({id: record})`` to the package's registry file (and nothing else)."""
    path = pkg / "config" / "agent_registry.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    edit({a["id"]: a for a in data["agents"]})
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def drop_registry_records(pkg: Path, *ids: str) -> None:
    path = pkg / "config" / "agent_registry.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["agents"] = [a for a in data["agents"] if a["id"] not in ids]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
