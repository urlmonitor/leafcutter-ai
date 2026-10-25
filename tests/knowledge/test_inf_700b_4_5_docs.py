"""
MODULE: test_inf_700b_4_5_docs
GOAL: Close-out (coverage-close) tests for the documentation ACs INF-700b-5 (the
    agent knowledge system reference) and INF-700b-4 (the knowledge capture path
    sequence diagram). The docs predate these tests by design, so the tests are
    GREEN on arrival; discrimination is proven by mutating a scratch copy of the
    docs (see INF_700B_DOCS_ROOT below), never by a red-first run.
DOCS ROOT OVERRIDE: set INF_700B_DOCS_ROOT to a directory holding a copy of
    docs/architecture/{agent_knowledge_system.md,components/knowledge-system.md,
    diagrams/c3-038-...md}. Docs are read from there; the package (scripts,
    templates, config) is always resolved against the real repository root.
"""
# @ac-tag: INF-700b-4
# @ac-tag: INF-700b-5

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
DOCS = Path(os.environ.get("INF_700B_DOCS_ROOT") or REPO)
REF = "docs/architecture/agent_knowledge_system.md"
COMP = "docs/architecture/components/knowledge-system.md"
DIAG = "docs/architecture/diagrams/c3-038-knowledge-capture-path-sequence.md"
SKILL = REPO / "templates/skills/agent-telemetry/SKILL.md"
RETIRED = ("route-learning", "capture-learning")

# Runtime or deliberately-nonexistent artefacts the reference names on purpose.
RUNTIME_ALLOW = {
    "debugging/logs/agent_telemetry.jsonl": "live runtime stream, not packaged",
    "debugging/logs/knowledge_emissions.jsonl": "the relative default literal the doc warns about",
    "memory/feedback_itpo_bo1700_worktree_gate_parity.md": "doc states it never existed",
    "knowledge_emissions.jsonl": "runtime stream file name",
    "agent_telemetry.jsonl": "runtime stream file name",
    "SKILL.md": "generic file name",
    "PROJECT_CONTEXT.md": "generic file name",
    "project_context.md": "named by the doc as the incorrect spelling",
    ".leafcutter/config/knowledge_sink.json": "build output; its keys are checked separately",
}
PATH_EXT = (".py", ".js", ".json", ".yaml", ".md", ".jsonl")
TIMING = ("after", "on commit", "automatically", "upon", "whenever", "each time",
          "immediately", "triggered", "scheduled", "before commit", "on sign-off",
          "then", "once", "following")
NEGATION = re.compile(r"\b(not|no|never|until|without|unless|only|retired)\b", re.I)
AUTO = re.compile(r"automatic(ally)?|on commit|harvester\s+(routes|writes)\s+each", re.I)


def _read(rel: str) -> str:
    return (DOCS / rel).read_text(encoding="utf-8")


def _body(text: str) -> str:
    """Drop frontmatter, fenced blocks and HTML comments."""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def _frontmatter(text: str) -> dict:
    return yaml.safe_load(re.match(r"---\n(.*?)\n---\n", text, re.S).group(1))


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n\s*\n", text) if s.strip()]


def _section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def _sink_keys() -> set[str]:
    """Key names the package itself defines for knowledge_sink.json."""
    src = (REPO / "scripts/knowledge/sink_resolution.py").read_text(encoding="utf-8")
    keys = set(re.findall(r'^_(?:ROOT|KNOWLEDGE|TELEMETRY)_KEY\s*=\s*"(\w+)"', src, re.M))
    keys.add("feedback_sink")
    deployed = REPO / ".leafcutter/config/knowledge_sink.json"
    if deployed.is_file():
        assert keys <= set(json.loads(deployed.read_text())), "deployed declaration lacks keys"
    return keys


@lru_cache(maxsize=1)
def _basename_index() -> frozenset[str]:
    names: set[str] = set()
    for top in ("scripts", "templates"):
        for _d, _s, files in os.walk(REPO / top):
            names.update(files)
    return frozenset(names)


def _is_package_value(tok: str) -> bool:
    """A kebab token that is a quoted outcome/verdict value in the report or emit script."""
    srcs = ("scripts/knowledge/health/capture_health_report.py",
            "templates/skills/agent-telemetry/scripts/emit_event.py")
    return any(f'"{tok}"' in (REPO / s).read_text(encoding="utf-8") for s in srcs)


def _resolves(token: str, base: Path | None = None) -> bool:
    if token in RUNTIME_ALLOW:
        return True
    if "/" not in token:
        return token in _basename_index()
    roots = [REPO, REPO / "templates/skills", REPO / "templates",
             base or REPO / "docs/architecture"]
    return any((r / token).exists() for r in roots)


def _spans(text: str) -> list[str]:
    return re.findall(r"`([^`\n]+)`", _body(text))


def _unresolved(text: str, base: Path | None = None) -> list[str]:
    """Every backticked path / script / skill / agent / config key that fails to resolve."""
    keys, bad = _sink_keys(), []
    for span in _spans(text):
        tok = span.split()[0].rstrip(".,:;") if span.split() else ""
        if not tok or tok.startswith("-") or re.search(r"[<{*…\[(=§]", tok):
            continue
        if tok.endswith(PATH_EXT) or "/" in tok:
            ok = _resolves(tok.rstrip("/"), base)
        elif re.fullmatch(r"[a-z]+(_[a-z]+)*", tok) and tok.endswith(("_sink", "_stream", "_root")):
            ok = tok in keys
        elif re.fullmatch(r"[a-z]+(-[a-z]+)+", tok) and tok not in RETIRED:
            ok = (REPO / "templates/skills" / tok).is_dir() or (
                REPO / "templates/agents" / f"{tok}.md").is_file() or _is_package_value(tok)
        else:
            continue
        if not ok:
            bad.append(tok)
    return bad


def _links(text: str) -> list[str]:
    return [m for m in re.findall(r"\]\(([^)#\s]+)\)", _body(text)) if "://" not in m]


def _emit_record(tmp: Path, name: str, with_ticket: bool) -> dict:
    """Run the real emit_knowledge.py CLI in an isolated copy and read the record back."""
    root = tmp / name
    shutil.copytree(REPO / "scripts/knowledge", root / "scripts/knowledge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    sink = root / "sink.jsonl"
    cmd = [sys.executable, str(root / "scripts/knowledge/emit_knowledge.py"),
           "--agent", "doc-probe", "--component", "knowledge_system",
           "--destination", "(unrouted)", "--entry-kind", "unclassified",
           "--text", "Probe learning body that is distinct from every other field.",
           "--sink", str(sink),
           "--vocabulary", str(REPO / "config/entry_kind_vocabulary.json")]
    if with_ticket:
        cmd += ["--ticket", "tickets/probe.md"]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    lines = sink.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def _field_table() -> dict[str, str]:
    sec = _section(_read(REF), "## §2 The Knowledge Record", "### Compatibility rule")
    rows = {}
    for line in sec.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("| `") and len(cells) >= 4:
            rows[cells[0].strip("`")] = cells[2]
    return rows


# --------------------------------------------------------------------------
# INF-700b-5: reference documentation
# --------------------------------------------------------------------------

def test_ac5_every_named_path_script_skill_and_key_resolves():
    # covers: INF-700b-5
    # angle: criterion
    """AC-5: every directory, file and step the reference names exists as given."""
    assert _unresolved(_read(REF)) == []
    passage = [p for p in _read(COMP).split("\n\n") if "retired names" in p]
    assert len(passage) == 1
    assert _unresolved(passage[0]) == []
    assert "agent_knowledge_system.md" in passage[0]


def test_ac5_checker_fails_on_one_bogus_path_control():
    # covers: INF-700b-5
    # angle: failure
    """AC-5 control: one bogus path, script, skill and key each make the checker fail."""
    text = ("`scripts/knowledge/emit_knowledge.py` ok. `scripts/knowledge/nope_nope.py` "
            "`templates/skills/no-such-skill/SKILL.md` `ghost_helper.py` `bogus_stream` "
            "`phantom-skill`")
    assert _unresolved(text) == ["scripts/knowledge/nope_nope.py",
                                 "templates/skills/no-such-skill/SKILL.md",
                                 "ghost_helper.py", "bogus_stream", "phantom-skill"]
    assert _unresolved("`scripts/knowledge/emit_knowledge.py` `operational_telemetry_stream`") == []
    assert _unresolved("`made_up_sink`") == ["made_up_sink"]


def test_ac5_markdown_links_in_reference_resolve():
    # covers: INF-700b-5
    # angle: criterion
    """AC-5: relative links in the reference point at files that exist."""
    base = (DOCS / REF).parent
    missing = [ln for ln in _links(_read(REF)) if not (base / ln).exists()
               and not (REPO / REF).parent.joinpath(ln).exists()]
    assert missing == []


def test_ac5_field_table_equals_keys_of_a_really_written_record(tmp_path):
    # covers: INF-700b-5
    # angle: seam
    """AC-5: the table lists exactly the keys emit_knowledge.py writes, `ticket` optional."""
    table = _field_table()
    full = _emit_record(tmp_path, "full", with_ticket=True)
    bare = _emit_record(tmp_path, "bare", with_ticket=False)
    assert set(table) == set(full)
    optional = {k for k, req in table.items() if req.lower().startswith("no")}
    assert optional == {"ticket"}
    assert set(bare) == set(table) - optional
    assert len(table) == 8 and len(bare) == 7


def test_ac5_text_is_named_the_content_field():
    # covers: INF-700b-5
    # angle: criterion
    """AC-5: `text` is the single content field and its purpose cell says so."""
    sec = _section(_read(REF), "## §2 The Knowledge Record", "### Compatibility rule")
    assert re.search(r"`text` is the single field that\s+carries content", sec)
    assert "content" in _field_table()["text"] or "content" in sec.split("| `text` |")[1].split("\n")[0]


def test_ac5_retired_names_only_in_sentences_calling_them_retired():
    # covers: INF-700b-5
    # angle: boundary
    """AC-5: route-learning / capture-learning appear only where called retired."""
    seen = 0
    for rel in (REF, COMP):
        for sentence in _sentences(_body(_read(rel))):
            for name in RETIRED:
                if name in sentence:
                    seen += 1
                    assert "retired" in sentence.lower(), sentence
    assert seen >= 2


def _wired_bullet() -> str:
    sec = _section(_read(REF), "- **Wired.**", "\n\nThe criterion")
    return sec


def test_ac5_wired_routes_named_equal_guardrail_wired_set():
    # covers: INF-700b-5
    # angle: seam
    """AC-5: the routes the doc calls wired equal knowledge_routing_wiring.wired."""
    gates = yaml.safe_load((REPO / "config/guardrail_gates.yaml").read_text(encoding="utf-8"))
    wired = set(gates["knowledge_routing_wiring"]["wired"])
    clause = _wired_bullet().split(";", 1)[0]
    named = set(re.findall(r"`([\w.-]+\.js)`", clause))
    assert named == wired and len(wired) == 3
    rest = set(re.findall(r"`([\w.-]+\.js)`", _wired_bullet())) - named
    assert rest and not rest & wired
    for js in named | rest:
        assert (REPO / "templates/workflows-js" / js).is_file(), js


def test_ac5_no_present_tense_automatic_routing_claim():
    # covers: INF-700b-5
    # angle: discrimination
    """AC-5: any automatic-routing wording is negated or tied to the wired list."""
    offenders = [s for s in _sentences(_body(_read(REF)))
                 if AUTO.search(s) and not NEGATION.search(s)]
    assert offenders == []
    assert "INF-700a" in _section(_read(REF), "## §4 Routing", "## Sequence Diagram")


def test_ac5_no_learning_and_failure_instructions_point_at_real_skill_sections():
    # covers: INF-700b-5
    # angle: reachability
    """AC-5: the named agent-telemetry commands are real headings in its SKILL.md."""
    headings = set(re.findall(r"^## (.+)$", SKILL.read_text(encoding="utf-8"), re.M))
    sec1 = _section(_read(REF), "## §1 What an Agent Does", "## §2")
    named = {s for s in re.findall(r"`([^`\n]*capture attempt)`", sec1)}
    assert named == {"Nothing-to-record capture attempt", "Failed capture attempt"}
    assert named <= headings


def test_ac5_failure_location_is_the_telemetry_stream_key_not_the_sink():
    # covers: INF-700b-5
    # angle: criterion
    """AC-5: failures are recorded on operational_telemetry_stream, a different stream."""
    sec3 = _section(_read(REF), "## §3 Capture Attempts", "### Capture-health report")
    keys = _sink_keys()
    assert "operational_telemetry_stream" in keys and "operational_telemetry_stream" in sec3
    assert re.search(r"not the knowledge-emission sink", sec3)
    failed_row = [ln for ln in sec3.splitlines() if ln.startswith("| `failed`")][0]
    assert "missing_target" in failed_row
    assert "capture_health_report.py" in _read(REF)


# --------------------------------------------------------------------------
# INF-700b-4: sequence diagram
# --------------------------------------------------------------------------

# participant id -> (label token that must appear in its label, package targets).
# A target is a repo path, or ("key", name) for a knowledge_sink.json key.
PARTICIPANTS = {
    "PA": ("Phase agent", ["templates/agents"]),
    "S7": ("signoff", ["templates/skills/signoff/SKILL.md"]),
    "EK": ("emit_knowledge.py", ["scripts/knowledge/emit_knowledge.py"]),
    "SINK": ("knowledge_emission_sink", [("key", "knowledge_emission_sink")]),
    "EE": ("emit_event.py", ["templates/skills/agent-telemetry/scripts/emit_event.py"]),
    "TEL": ("operational_telemetry_stream", [("key", "operational_telemetry_stream")]),
    "HV": ("harvest_learnings.py", ["scripts/knowledge/harvest_learnings.py",
                                    "templates/agents/knowledge-harvester.md"]),
    "HR": ("capture_health_report.py", ["scripts/knowledge/health/capture_health_report.py"]),
}
MSG = re.compile(r"^\s*(\w+)\s*(-->>|->>)\s*(\w+)\s*:\s*(.*)$")


def _mermaid(text: str | None = None) -> list[str]:
    text = text if text is not None else _read(DIAG)
    blocks = re.findall(r"```mermaid\n(.*?)```", text, re.S)
    assert len(blocks) == 1 and blocks[0].lstrip().startswith("sequenceDiagram")
    return [ln.rstrip() for ln in blocks[0].splitlines()]


def _declared(lines: list[str]) -> dict[str, str]:
    out = {}
    for ln in lines:
        m = re.match(r"\s*participant\s+(\w+)\s+as\s+(.*)$", ln)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _messages(lines: list[str]) -> list[tuple[str, str, str]]:
    return [(m.group(1), m.group(3), m.group(4)) for m in map(MSG.match, lines) if m]


def _kw(line: str) -> str:
    return line.strip().split(" ", 1)[0]


def test_ac4_every_participant_maps_to_an_existing_artefact():
    # covers: INF-700b-4
    # angle: criterion
    """AC-4: each participant maps to a package artefact; none is unmapped."""
    declared = _declared(_mermaid())
    assert set(declared) == set(PARTICIPANTS)
    keys = _sink_keys()
    for pid, (token, targets) in PARTICIPANTS.items():
        assert token in declared[pid].replace("<br/>", ""), pid
        for target in targets:
            if isinstance(target, tuple):
                assert target[1] in keys, (pid, target)
            else:
                assert (REPO / target).exists(), (pid, target)


def test_ac4_two_distinct_branches_success_to_sink_failure_to_telemetry_only():
    # covers: INF-700b-4
    # angle: boundary
    """AC-4: success ends at the sink; cannot-complete ends at telemetry, no sink write."""
    lines = _mermaid()
    top = [i for i, ln in enumerate(lines) if _kw(ln) in ("alt", "else") and ln.startswith("    ")
           and not ln.startswith("     ")]
    assert len(top) >= 3  # alt plus at least two else => at least three branches
    ends = [i for i, ln in enumerate(lines) if _kw(ln) == "end" and ln.startswith("    ")
            and not ln.startswith("     ")]
    bounds = top + [ends[0]]
    segs = [lines[a + 1:b] for a, b in zip(bounds, bounds[1:])]
    success, cannot = segs[0], segs[1]
    assert any(m[1] == "SINK" for m in _messages(success))
    assert not any(m[1] == "SINK" for m in _messages(cannot))
    failed_tel = [m for m in _messages(cannot) if m[1] == "TEL"]
    assert len(failed_tel) == 2 and all("failed" in m[2] for m in failed_tel)


def test_ac4_alt_else_end_and_rect_end_are_balanced():
    # covers: INF-700b-4
    # angle: failure
    """AC-4: blocks open and close in order; else only inside an alt."""
    stack: list[str] = []
    for ln in _mermaid():
        word = _kw(ln)
        if word in ("alt", "rect"):
            stack.append(word)
        elif word == "else":
            assert stack and stack[-1] == "alt", "else outside an alt"
        elif word == "end":
            assert stack, "end without an open block"
            stack.pop()
    assert stack == []


def test_ac4_routing_boundary_marked_and_routing_messages_assert_no_timing():
    # covers: INF-700b-4
    # angle: discrimination
    """AC-4: boundary note precedes the rect; HV messages contain no timing word."""
    lines = _mermaid()
    text = [ln.strip() for ln in lines]
    obligation = next(i for i, ln in enumerate(text) if "obligation ends" in ln)
    rect = next(i for i, ln in enumerate(text) if ln.startswith("rect"))
    assert obligation < rect
    routing = [m for m in _messages(lines) if m[0] == "HV"]
    assert len(routing) == 2
    for _src, _dst, msg in routing:
        low = msg.lower()
        assert not [w for w in TIMING if re.search(rf"\b{re.escape(w)}\b", low)], msg
    boundary_note = text[rect + 1].lower()
    assert "does not say when" in boundary_note


def test_ac4_names_no_retired_step_anywhere_in_the_diagram_page():
    # covers: INF-700b-4
    # angle: criterion
    """AC-4: neither retired name appears anywhere on the diagram page."""
    page = _read(DIAG).lower()
    assert [n for n in RETIRED if n in page] == []


def test_ac4_reference_and_diagram_link_each_other():
    # covers: INF-700b-4
    # angle: seam
    """AC-4: reference links and lists the diagram; the diagram's parent points back."""
    ref_text, diag_text = _read(REF), _read(DIAG)
    ref_fm, diag_fm = _frontmatter(ref_text), _frontmatter(diag_text)
    name = "c3-038-knowledge-capture-path-sequence.md"
    assert DIAG in ref_fm["children"]
    assert f"diagrams/{name}" in _links(ref_text)
    assert diag_fm["parent"] == REF
    assert "../agent_knowledge_system.md" in _links(diag_text)
    assert (REPO / REF).is_file() and (REPO / DIAG).is_file()
