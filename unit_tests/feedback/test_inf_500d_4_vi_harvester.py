"""
MODULE: test_inf_500d_4_vi_harvester
GOAL: RED tests for review-fix defect H-5 -- the knowledge-harvester agent prompt still sends the agent to a
    workspace-relative sink, so in an inherited-root worktree it reports "nothing to harvest".
AC: INF-500d-4-vi (agent instructions no longer send logs to the workspace that is about to be deleted),
    INF-400c-4-i (every surface resolves the knowledge sink through the one declared location);
    ADR-069 section 3 (a worktree INHERITS the enduring root, so its declared sink lies outside it).

THE DEFECT: ``templates/agents/knowledge-harvester.md`` (a) pre-flights with
    ``ls debugging/logs/knowledge_emissions.jsonl`` and tells the agent to stop with "Sink file not found ...
    nothing to harvest" when that fails, (b) shows ``--sink debugging/logs/knowledge_emissions.jsonl`` as the
    way to harvest from a custom path and (c) restates the sink and a state path in its report template. In an
    inherited-root worktree the declared sink is in the enduring root, ``debugging/logs`` does not exist in the
    worktree, so (a) fires on a worktree that holds records and the agent never harvests. The scan in
    ``test_inf_500d_4_vi.py`` missed it because its destination regex exempted ``knowledge_emissions``.

HOW THE PROMPT IS EXERCISED (behavioural, not grep-only): the fenced shell blocks of the DEPLOYED prompt's
    "Pre-Flight Checks" and "Harvesting" sections are lifted out and run, each in a fresh ``bash -c`` (agents do
    not share shell state between calls), from the root of an inherited-root worktree whose declared knowledge
    sink holds records written by the REAL producer (``emit_knowledge.py``). The ``scripts/knowledge/`` prefix
    is pointed at the temp install; nothing else is rewritten. No build.py is spawned.
"""
# @ac-tag: INF-500d-4-vi

from __future__ import annotations

import re
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback import _inf_500d_4_vi_helpers as vh

pytestmark = pytest.mark.shared_layout_reader

_TEXTS = ("harvester prompt learning one", "harvester prompt learning two")
_KNOWLEDGE_PREFIX_RE = re.compile(r"(?:[\w.\-]+/)*(scripts/knowledge/)")
_VOCABULARY = h.REPO_ROOT / "config" / "entry_kind_vocabulary.json"
_ROUTED = re.compile(r"\b2 learnings routed\b")


def _harvester_prompt(layout: Path) -> str:
    path = Path(layout) / ".leafcutter" / "agents" / "knowledge-harvester.md"
    assert path.is_file(), f"the knowledge-harvester prompt is not deployed at {path}"
    return path.read_text(encoding="utf-8")


def _section_blocks(text: str, heading: str) -> list[str]:
    """The fenced code blocks between ``## <heading>`` and the next ``## `` heading, in order."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == f"## {heading}"), None)
    assert start is not None, f"the harvester prompt no longer has a '## {heading}' section"
    blocks: list[str] = []
    fence, current = False, []
    for line in lines[start + 1:]:
        if not fence and line.startswith("## "):
            break
        if line.strip().startswith("```"):
            if fence:
                blocks.append("\n".join(current))
            fence, current = not fence, []
        elif fence:
            current.append(line)
    return blocks


def _prepare(block: str, out_root: Path, tmpdir: Path) -> str:
    """The block as an agent would run it: ``/tmp/`` confined, ``scripts/knowledge/`` pointed at the temp install."""
    text = block.replace("/tmp/", f"{tmpdir}/")
    return _KNOWLEDGE_PREFIX_RE.sub(lambda m: f"{out_root}/{m.group(1)}", text)


def _worktree(base: Path, *, with_records: bool) -> tuple[Path, Path, Path, Path]:
    """An inherited-root worktree (declared root OUTSIDE the project). Returns ``(project, out_root, sink, destination)``.

    With ``with_records`` the declared knowledge sink holds ``_TEXTS`` as real ``knowledge_captured`` events.
    """
    log_root = base / "enduring_project" / "debugging" / "logs"
    log_root.mkdir(parents=True)
    project = base / "worktree"
    project.mkdir()
    out_root = h.deploy_install(project)
    h.declare(out_root, log_root)
    sink = Path(h.read_declaration(out_root)["knowledge_emission_sink"])
    assert project not in sink.parents, "fixture: an inherited root puts the sink outside the worktree"
    destination = base / "surfaces" / "glossary.md"
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    if with_records:
        for text in _TEXTS:
            proc = h.run_py(
                out_root / "scripts" / "knowledge" / "emit_knowledge.py",
                ["--agent", "python-coder", "--component", "knowledge_system", "--destination", str(destination),
                 "--entry-kind", "glossary", "--text", text, "--ticket", "tickets/00_inbox/t.md",
                 "--sink", str(sink), "--vocabulary", str(_VOCABULARY)],
                project, tmpdir)
            assert proc.returncode == 0, f"fixture: the real producer failed: {proc.stdout!r} {proc.stderr!r}"
        assert len(h.read_records(sink)) == len(_TEXTS), "fixture: the producer must have emitted both events"
    return project, out_root, sink, destination


def test_the_harvester_preflight_finds_the_declared_sink_in_an_inherited_root_worktree(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-vi
    # covers: INF-400c-4-i
    # angle: reachability
    """The pre-flight 'is the sink reachable' block, run verbatim from an inherited-root worktree that holds
    records, succeeds; the same block fails when the declared sink really is absent (so it is not vacuous)."""
    blocks = _section_blocks(_harvester_prompt(shared_reference_layout), "Pre-Flight Checks")
    assert len(blocks) >= 2, f"the pre-flight carries a sink check and a script check; found {len(blocks)} block(s)"
    sink_check, script_check = blocks[0], blocks[1]

    (tmp_path / "with").mkdir()
    project, out_root, sink, _destination = _worktree(tmp_path / "with", with_records=True)
    tmpdir = tmp_path / "with" / "tmpdir"
    found = vh._shell(_prepare(sink_check, out_root, tmpdir), project, tmpdir)
    assert found.returncode == 0, (
        "the pre-flight reports the sink missing in a worktree that HOLDS records (the harvester agent would stop "
        f"with 'nothing to harvest'): rc={found.returncode} stdout={found.stdout!r} stderr={found.stderr!r}\n"
        f"block:\n{sink_check}")
    assert sink.is_file()
    scripts = vh._shell(_prepare(script_check, out_root, tmpdir), project, tmpdir)
    assert scripts.returncode == 0, f"the script-present check must pass in a deployed install: {scripts.stderr!r}"

    # Control: a worktree whose declared sink was never written -- the same block must now FAIL.
    (tmp_path / "without").mkdir()
    n_project, n_out, n_sink, _d = _worktree(tmp_path / "without", with_records=False)
    assert not n_sink.exists()
    absent = vh._shell(_prepare(sink_check, n_out, tmp_path / "without" / "tmpdir"), n_project, tmp_path / "without" / "tmpdir")
    assert absent.returncode != 0, f"the pre-flight cannot tell an empty install from a populated one: {absent.stdout!r}"


def test_every_harvest_command_in_the_prompt_drains_the_declared_sink(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-vi
    # covers: INF-400c-4-i
    # angle: seam
    """Each fenced command of the 'Harvesting' section, run verbatim in its own inherited-root worktree with
    records present, finds the declared sink and routes both of them (a dry run routes nothing to disk) -- none
    reports 'nothing to harvest', 'not found' or exits 1."""
    blocks = _section_blocks(_harvester_prompt(shared_reference_layout), "Harvesting")
    assert len(blocks) >= 2, f"the prompt must keep a normal and a dry-run harvest command; found {len(blocks)} block(s)"
    assert any("--dry-run" in b for b in blocks) and any("--dry-run" not in b for b in blocks), (
        "the prompt must carry both a real and a dry-run harvest command")

    breaches = []
    for index, block in enumerate(blocks):
        base = tmp_path / f"block_{index}"
        base.mkdir()
        project, out_root, sink, destination = _worktree(base, with_records=True)
        tmpdir = base / "tmpdir"
        proc = vh._shell(_prepare(block, out_root, tmpdir), project, tmpdir)
        label = f"block {index + 1} ({block.strip().splitlines()[-1][:90]!r})"
        output = proc.stdout + proc.stderr
        if proc.returncode != 0:
            breaches.append(f"{label}: exited {proc.returncode}: {output.strip()[:200]!r}")
        elif not _ROUTED.search(proc.stdout):
            breaches.append(f"{label}: did not route the declared sink's 2 records: {proc.stdout!r}")
        elif "--dry-run" in block:
            if destination.exists():
                breaches.append(f"{label}: a dry run wrote a knowledge surface")
        elif not destination.is_file() or destination.read_text(encoding="utf-8").splitlines() != list(_TEXTS):
            breaches.append(f"{label}: the records were not routed exactly once to {destination}")
        if (project / "debugging").exists():
            breaches.append(f"{label}: created {project / 'debugging'} beneath the disposable worktree")
    assert not breaches, "\n  ".join(["a harvester prompt command did not drain the declared sink:", *breaches])


def test_the_harvester_prompt_restates_no_workspace_relative_log_path(shared_reference_layout):
    # covers: INF-500d-4-vi
    # angle: criterion
    """The harvester prompt's body never names ``debugging/logs/...``: the sink and the state file are obtained from
    the declared location, not restated (the report template included)."""
    text = _harvester_prompt(shared_reference_layout)
    body = text.split("\n---\n", 2)[-1] if text.startswith("---") else text
    assert "You are the `knowledge-harvester` agent" in body, "fixture: the front-matter split must leave the prompt body"
    mentions = [
        f"{number}: {line.strip()[:140]}"
        for number, line in enumerate(body.splitlines(), start=1)
        if vh._ANY_MENTION.search(line)
    ]
    assert not mentions, f"{len(mentions)} body line(s) still restate a workspace-relative log path:\n  " + "\n  ".join(mentions)


def test_the_scan_regex_no_longer_exempts_the_knowledge_sink():
    # covers: INF-500d-4-vi
    # angle: discrimination
    """Wrong version this catches: restoring ``(?!knowledge_emissions)``. The destination scan must flag the shipped
    bad harvester forms in every quote style, and still leave an innocent declared-sink command alone."""
    bad = [
        "python3 scripts/knowledge/harvest_learnings.py --sink debugging/logs/knowledge_emissions.jsonl",
        "python3 scripts/knowledge/harvest_learnings.py --sink 'debugging/logs/knowledge_emissions.jsonl'",
        'python3 scripts/knowledge/harvest_learnings.py --sink="./debugging/logs/knowledge_emissions.jsonl"',
        "echo '{}' >> debugging/logs/knowledge_emissions.jsonl",
        'SINK="debugging/logs/knowledge_emissions.jsonl"',
    ]
    for sample in bad:
        assert vh._destination_hits(sample), f"the scan is blind to: {sample}"
    good = "python3 scripts/knowledge/harvest_learnings.py --sink \"$(python3 sink_resolution.py --print-location knowledge)\""
    assert not vh._destination_hits(good), "the scan flags an innocent declared-sink command"
