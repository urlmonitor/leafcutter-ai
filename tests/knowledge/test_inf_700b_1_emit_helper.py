"""
MODULE: test_inf_700b_1_emit_helper
GOAL: RED behavioural tests for AC INF-700b-1 -- an agent that finishes with a
    learning leaves a durable record of it by following the signoff section 7
    capture step verbatim. The step must name ONE command (the deployed
    ``emit_knowledge.py``), and that command must, with no ``--sink`` argument,
    append exactly one clean ``knowledge_captured`` line to the declared sink.
AC: INF-700b-1 (source_ac); ADR-034 Amendment 1; ADR-069.

WHAT IS EXPECTED TO BE RED TODAY AND WHY
    * Section 7 (and the three v3 agent emission blocks) say "Append the event
      there (create the file if it does not exist yet)" and name NO command,
      so the extraction of an ``emit_knowledge.py`` command from the DEPLOYED
      text finds nothing.
    * ``emit_knowledge.py`` makes ``--sink`` required (argparse exits 2 when
      it is absent).
    * The sentinel ``entry_kind`` ``unclassified`` is outside the declared
      vocabulary, so the helper REJECTS it and writes nothing.
    * ``_append_jsonl`` calls ``mkdir(parents=True)``, so it conjures a
      vanished project root and ``debugging/logs`` from nothing.

REAL-ARTIFACT NOTE: the prompt text is read from the DEPLOYED shared reference
    layout (``shared_reference_layout``, ``@pytest.mark.shared_layout_reader``);
    the command run is the one extracted from that text; the helper runs as a
    fresh subprocess from a private COPY of the deployed ``.leafcutter`` tree
    (the shared layout is never written to); the declaration is the deployed
    ``knowledge_sink.json`` round-tripped through ``json`` with only the paths
    changed. Nothing is passed by grepping source for a string.
"""
# @ac-tag: INF-700b-1

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_TIMEOUT_SECONDS = 60
_LEARNING = "The capture helper must exit 0 on every path.\nSecond line: keep the newline."
_HELPER_REL = Path("scripts") / "knowledge" / "emit_knowledge.py"
_STREAM_KEYS = (
    "knowledge_emission_sink",
    "operational_telemetry_stream",
    "feedback_sink",
)
_FLAG_VALUES = {
    "--agent": "test-writer",
    "--component": "knowledge_system",
    "--destination": "(unrouted)",
    "--entry-kind": "unclassified",
    "--text": _LEARNING,
    "--ticket": "tickets/00_inbox/TICKET-probe.md",
}
_AGENT_SURFACES = {
    "product-owner": "agents/product-owner.md",
    "business-analyst": "agents/business-analyst.md",
    "it-po": "agents/it-po.md",
}
_FORBIDDEN_HAND_APPEND = (
    re.compile(r"append the event", re.IGNORECASE),
    re.compile(r"create the file if it does not exist", re.IGNORECASE),
    re.compile(r">>"),
    re.compile(r"\becho\b"),
    re.compile(r"\btee\b"),
    re.compile(r"knowledge_emissions\.jsonl"),
    re.compile(r"debugging/logs"),
)


# ---------------------------------------------------------------------------
# reading the DEPLOYED prompts and extracting the command they prescribe
# ---------------------------------------------------------------------------

def _deployed(layout: Path) -> Path:
    root = Path(layout) / ".leafcutter"
    assert root.is_dir(), f"the shared layout has no deployed .leafcutter at {root}"
    return root


def _section_seven(layout: Path) -> str:
    text = (_deployed(layout) / "skills" / "signoff" / "SKILL.md").read_text(encoding="utf-8")
    start = text.index("## §7 Knowledge Capture Step")
    return text[start : text.index("## §8", start)]


def _emission_block(layout: Path, rel: str) -> str:
    text = (_deployed(layout) / rel).read_text(encoding="utf-8")
    match = re.search(r"^## (?:S|§)\d+ Knowledge Loop — Emission.*?(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert match, f"deployed {rel} has no 'Knowledge Loop — Emission' block"
    return match.group(0)


def _candidate_snippets(section: str) -> list[str]:
    fenced = [m.group(1) for m in re.finditer(r"```[A-Za-z]*\n(.*?)```", section, re.DOTALL)]
    inline = [m.group(1) for m in re.finditer(r"`([^`\n]+)`", section)]
    return fenced + inline


def _extract_command(section: str) -> list[str] | None:
    """Return the argv tokens of the ``emit_knowledge.py ... --text`` command in *section*, or ``None``."""
    for snippet in _candidate_snippets(section):
        if "emit_knowledge.py" not in snippet or "--text" not in snippet:
            continue
        joined = re.sub(r"\\\r?\n", " ", snippet).replace("[", " ").replace("]", " ")
        for line in joined.splitlines():
            if "emit_knowledge.py" in line:
                return shlex.split(line)
    return None


def _script_token(tokens: list[str]) -> str:
    return next(tok for tok in tokens if tok.endswith("emit_knowledge.py"))


def _bind(tokens: list[str], project: Path) -> list[str]:
    """Substitute only the documented flag values; return a runnable argv (no shell involved)."""
    script = _script_token(tokens)
    rest = tokens[tokens.index(script) + 1 :]
    bound: list[str] = []
    skip = False
    for position, tok in enumerate(rest):
        if skip:
            skip = False
            continue
        bound.append(tok)
        if tok in _FLAG_VALUES and position + 1 < len(rest):
            bound.append(_FLAG_VALUES[tok])
            skip = True
    return [sys.executable, "-B", str(project / script), *bound]


# ---------------------------------------------------------------------------
# a private project built from a COPY of the deployed tree
# ---------------------------------------------------------------------------

def _snapshot(root: Path) -> set[str]:
    seen: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in (*dirnames, *filenames):
            seen.add(os.path.relpath(os.path.join(dirpath, name), root))
    return seen


def _declare(deployed: Path, log_root: Path, sink: Path | None = None) -> None:
    """Round-trip the deployed declaration, re-pointing every stream at *log_root*."""
    path = deployed / "config" / "knowledge_sink.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["operational_log_root"] = str(log_root)
    for key in _STREAM_KEYS:
        data[key] = str(log_root / Path(data[key]).name)
    if sink is not None:
        data["knowledge_emission_sink"] = str(sink)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _project(tmp_path: Path, layout: Path, case: str) -> dict[str, Path]:
    """Build ``world/proj`` with a copied deployed ``.leafcutter`` and a declaration of the given *case*."""
    world = tmp_path / "world"
    project = world / "proj"
    cwd = project / "work"
    cwd.mkdir(parents=True)
    deployed = project / ".leafcutter"
    shutil.copytree(_deployed(layout), deployed, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
    log_root = project / "debugging" / "logs"
    sink = None
    if case in ("live", "unusable"):
        log_root.mkdir(parents=True)
    if case == "unusable":
        sink = project / "elsewhere" / "knowledge_emissions.jsonl"
    if case == "stale":
        log_root = world / "vanished_project" / "debugging" / "logs"
    if case == "missing_log_dir":
        (world / "durable").mkdir()
        log_root = world / "durable" / "logs"
    if case == "absent":
        (deployed / "config" / "knowledge_sink.json").unlink()
    else:
        _declare(deployed, log_root, sink)
    final_sink = sink or log_root / "knowledge_emissions.jsonl"
    return {"world": world, "project": project, "cwd": cwd, "deployed": deployed,
            "log_root": log_root, "sink": final_sink}


def _run(argv: list[str], cwd: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    tmpdir = tmp_path / "scratch_tmp"
    tmpdir.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(tmpdir))
    return subprocess.run(argv, capture_output=True, text=True, cwd=str(cwd), timeout=_TIMEOUT_SECONDS,
                          check=False, env=env)


def _emit_argv(proj: dict[str, Path], entry_kind: str, *extra: str) -> list[str]:
    return [sys.executable, "-B", str(proj["deployed"] / _HELPER_REL),
            "--agent", "test-writer", "--component", "knowledge_system", "--destination", "(unrouted)",
            "--entry-kind", entry_kind, "--text", _LEARNING, *extra]


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _telemetry_stream(proj: dict[str, Path]) -> Path:
    """The declared operational telemetry stream, read from the project's own (round-tripped) declaration."""
    declaration = json.loads((proj["deployed"] / "config" / "knowledge_sink.json").read_text(encoding="utf-8"))
    return Path(declaration["operational_telemetry_stream"])


def _assert_one_recorded_attempt(proj: dict[str, Path], agent: str) -> None:
    """ADR-034 Amendment 2 A2.4: a successful capture writes exactly one ``recorded`` capture_attempt line."""
    records = [json.loads(ln) for ln in _lines(_telemetry_stream(proj))]
    assert len(records) == 1, f"the telemetry stream must hold exactly one line, got {records!r}"
    record = records[0]
    assert record["event_type"] == "capture_attempt", record
    assert record["payload"]["outcome"] == "recorded", record
    assert record["agent_name"] == agent, record
    assert record["payload"]["missing_target"] is None, record


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

@pytest.mark.shared_layout_reader
def test_section_7_command_lands_one_clean_record_in_the_declared_sink(shared_reference_layout, tmp_path):
    # covers: INF-700b-1
    # covers: INF-700b
    # angle: reachability
    """Run the command the DEPLOYED section 7 prescribes, with no --sink, against a live declaration.

    Must be green only when section 7 names an ``emit_knowledge.py ... --text`` command, the helper
    resolves the declared sink itself, and exactly one ``json.loads``-clean line with the learning
    (newline preserved) lands there. The only other file created is the declared telemetry stream,
    holding the one ``recorded`` capture attempt the helper writes itself (ADR-034 Amendment 2 A2.4).
    """
    tokens = _extract_command(_section_seven(shared_reference_layout))
    assert tokens is not None, (
        "deployed signoff section 7 names no `emit_knowledge.py ... --text ...` command: "
        "the agent is left to hand-compose the append"
    )
    assert "--sink" not in tokens, "section 7's command must not restate a sink path (no --sink)"
    proj = _project(tmp_path, shared_reference_layout, "live")
    before = _snapshot(proj["world"])
    result = _run(_bind(tokens, proj["project"]), proj["project"], tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    lines = _lines(proj["sink"])
    assert len(lines) == 1, f"the declared sink must gain exactly one line, got {lines!r}"
    record = json.loads(lines[0])
    assert record["event"] == "knowledge_captured"
    assert record["text"] == _LEARNING and "\n" in record["text"]
    created = _snapshot(proj["world"]) - before
    expected = {os.path.relpath(proj["sink"], proj["world"]),
                os.path.relpath(_telemetry_stream(proj), proj["world"])}
    assert created == expected, f"unexpected files created: {created}"
    _assert_one_recorded_attempt(proj, "test-writer")


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("how", ["declared_sink", "explicit_sink"])
def test_unclassified_sentinel_is_accepted_and_recorded(shared_reference_layout, tmp_path, how):
    # covers: INF-700b-1
    # angle: real_artifact
    """``--entry-kind unclassified`` is recorded verbatim; the vocabulary file is left untouched.

    The ``explicit_sink`` row isolates the sentinel rejection from the optional-``--sink`` defect.
    The control row (an ordinary unknown kind) must STILL be rejected: it is the wrong version
    "accept every entry_kind" that this test must catch.
    """
    proj = _project(tmp_path, shared_reference_layout, "live")
    vocab = proj["deployed"] / "config" / "entry_kind_vocabulary.json"
    vocab_before = vocab.read_bytes()
    rejection_log = proj["log_root"] / "knowledge_rejections.jsonl"
    extra = ["--rejection-log", str(rejection_log)]
    if how == "explicit_sink":
        extra += ["--sink", str(proj["sink"])]
    result = _run(_emit_argv(proj, "unclassified", *extra), proj["project"], tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    lines = _lines(proj["sink"])
    assert len(lines) == 1, f"the sentinel must be recorded as exactly one line, got {lines!r} ({result.stderr!r})"
    record = json.loads(lines[0])
    assert record["entry_kind"] == "unclassified" and record["text"] == _LEARNING
    assert not rejection_log.exists(), "the sentinel must not be written to any rejection log"
    assert "REJECTED" not in result.stdout + result.stderr
    assert vocab.read_bytes() == vocab_before, "config/entry_kind_vocabulary.json must be byte-identical"
    # control row: a different out-of-vocabulary kind keeps today's rejection behaviour.
    control = _run(_emit_argv(proj, "not_a_real_kind", *extra, *(["--sink", str(proj["sink"])] if how == "explicit_sink" else [])),
                   proj["project"], tmp_path)
    assert control.returncode == 0
    assert len(_lines(proj["sink"])) == 1, "an ordinary unknown entry_kind must still write nothing to the sink"
    assert len(_lines(rejection_log)) == 1, "an ordinary unknown entry_kind must still be counted in the rejection log"


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize(
    "case, reason_words",
    [
        ("absent", ("absent", "declaration", "knowledge_sink")),
        ("stale", ("stale", "no longer exists")),
        ("unusable", ("operational_log_root", "not directly under", "usable")),
    ],
)
def test_absent_or_stale_declaration_creates_nothing_and_fails_open(shared_reference_layout, tmp_path, case, reason_words):
    # covers: INF-700b-1
    # angle: failure
    """No usable declaration -> exit 0, a stderr warning naming the refusal, and NOTHING created anywhere."""
    proj = _project(tmp_path, shared_reference_layout, case)
    before = _snapshot(proj["world"])
    result = _run(_emit_argv(proj, "unclassified"), proj["cwd"], tmp_path)
    assert result.returncode == 0, f"must fail open, got {result.returncode}: stderr={result.stderr!r}"
    stderr = result.stderr.lower()
    assert stderr.strip(), "a refusal must be reported on stderr"
    assert any(word in stderr for word in reason_words), f"stderr does not name the refusal ({case}): {result.stderr!r}"
    assert "required" not in stderr, f"stderr is an argument-parsing error, not a refusal: {result.stderr!r}"
    created = _snapshot(proj["world"]) - before
    assert not created, f"a refused write must create nothing, but created {sorted(created)}"
    assert not proj["sink"].exists()
    assert not (proj["cwd"] / "debugging").exists(), "the cwd-relative debugging/logs fallback must not be used"


@pytest.mark.shared_layout_reader
def test_live_root_with_missing_log_dir_creates_only_the_log_dir(shared_reference_layout, tmp_path):
    # covers: INF-700b-1
    # angle: boundary
    """Fourth row of the fail-open family: a live enduring root whose log directory is missing.

    Only the log directory and the two files inside it may appear: the sink, and the telemetry stream
    holding the one ``recorded`` capture attempt (ADR-034 Amendment 2 A2.4). The live root itself is
    not touched.
    """
    proj = _project(tmp_path, shared_reference_layout, "missing_log_dir")
    before = _snapshot(proj["world"])
    result = _run(_emit_argv(proj, "unclassified"), proj["cwd"], tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    created = _snapshot(proj["world"]) - before
    log_dir = os.path.relpath(proj["log_root"], proj["world"])
    stream = os.path.relpath(_telemetry_stream(proj), proj["world"])
    assert os.path.dirname(stream) == log_dir, "the telemetry stream lands in the same log dir"
    assert created == {log_dir, os.path.join(log_dir, "knowledge_emissions.jsonl"), stream}, (
        f"created: {sorted(created)}")
    assert len(_lines(proj["sink"])) == 1
    _assert_one_recorded_attempt(proj, "test-writer")


@pytest.mark.shared_layout_reader
def test_deployed_section_7_names_emit_helper_and_no_hand_append(shared_reference_layout, tmp_path):
    # covers: INF-700b-1
    # angle: reachability
    """Section 7 and the three v3 emission blocks name ONE helper invocation, it resolves, nothing hand-appends."""
    surfaces = {"signoff section 7": _section_seven(shared_reference_layout)}
    for name, rel in _AGENT_SURFACES.items():
        surfaces[name] = _emission_block(shared_reference_layout, rel)
    problems: list[str] = []
    shapes: dict[str, tuple[str, frozenset[str]]] = {}
    for name, text in surfaces.items():
        tokens = _extract_command(text)
        if tokens is None:
            problems.append(f"{name}: names no `emit_knowledge.py ... --text ...` command")
        else:
            flags = frozenset(t for t in tokens if t.startswith("--")) - {"--ticket"}
            shapes[name] = (_script_token(tokens), flags)
        problems += [f"{name}: still carries /{p.pattern}/" for p in _FORBIDDEN_HAND_APPEND if p.search(text)]
    if len(set(shapes.values())) > 1:
        problems.append(f"the four surfaces do not name the same invocation: {shapes}")
    if any("--sink" in flags for _script, flags in shapes.values()):
        problems.append("a surface restates --sink")
    assert not problems, "\n".join(problems)
    script_token = next(iter(shapes.values()))[0]
    result = _run([sys.executable, "-B", str(Path(shared_reference_layout) / script_token), "--help"],
                  Path(shared_reference_layout), tmp_path)
    assert result.returncode == 0 and "--entry-kind" in result.stdout, (
        f"the named script path {script_token!r} does not resolve from the deployed root: {result.stderr!r}"
    )
