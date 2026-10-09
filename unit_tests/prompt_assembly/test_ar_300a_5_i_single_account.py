"""AR-300a-5-i -- no compiled prompt carries a hand-written sub-agent table beside the
delivered one: exactly ONE account of the agent's permitted sub-agents, and it is the
generated one; the property holds for EVERY compiled prompt, so a table added later is
caught rather than accumulated; prose that merely mentions the heading is not a second
account.

Source of truth: .../AR-300a-5-i.yaml. Contract: _ar_300e_support.py item 2. The
whole-population assertion is ``single_account_report`` (every prompt in every root; it
never iterates a list of known templates). The production half is the compile-time
report of a hand-written account, labelled ``duplicate`` (it equals the declaration) or
``contradiction`` (it differs), exactly as AR-300a-4-i reports a hand-written abilities
section (same channels: stdout / stderr / a WARNING+ log record carrying the file name).

RED BASELINE (slice 5): the five tables are still in the bodies, four of the five agents
declare nothing, nothing is delivered, and the compiler reports no hand-written
sub-agent account (assertion red).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import layout_roots  # noqa: E402
from _ar_300b_support import norm  # noqa: E402
from _ar_300e_support import (  # noqa: E402
    BODY,
    HAND_WRITTEN_STEMS,
    REPO_ROOT,
    TABLE_STEMS,
    captured_report,
    compile_with,
    fresh_spawn_build,
    has_sub_agent_heading,
    parse_frontmatter,
    real_build_prompts,
    real_known_ids,
    real_registry,
    real_spawn_declarations,
    records_for,
    resolve_declared,
    sfm,
    single_account_report,
    source_templates,
    spawn_accounts,
    spawn_registrations,
    workers,
    write_template,
)

TABLE_HEADING = "## Your Available Sub-Agents"
LIST_HEADING = "### Spawn Allowlist (is_ticket_phase agents)"
LIST_FIXTURE = (Path(__file__).resolve().parent / "fixtures_ar_300e" / "ticket_supervisor_spawn_list_section.md")


def _list_bodies(*ids: str) -> dict[str, str]:
    """Hand-written sub-agent LISTS in the three shapes the AC names. The fenced one is
    ticket-supervisor's former section, VERBATIM from git HEAD with only the ids inside its
    fence replaced by ``ids`` (the heading, lead-in sentence and trailer survive)."""
    lines = LIST_FIXTURE.read_text(encoding="utf-8").split("\n")
    assert lines[0] == LIST_HEADING, "fixture drifted"
    first = next(i for i, ln in enumerate(lines) if ln.startswith("```"))
    last = next(i for i in range(first + 1, len(lines)) if lines[i].startswith("```"))
    fenced = "\n".join(lines[: first + 1] + list(ids) + lines[last:])
    bullets = "\n".join(f"- {i}" for i in ids)
    numbered = "\n".join(f"{n}. `{i}`" for n, i in enumerate(ids, 1))
    return {"zz-fenced": f"# Agent\n\nDo the work.\n\n{fenced}\n",
            "zz-bullets": f"# Agent\n\nDo the work.\n\n### Spawn Allowlist\n\nYou may spawn:\n\n{bullets}\n\n## Notes\n\nDone.\n",
            "zz-numbered": f"# Agent\n\nDo the work.\n\n## Your Permitted Sub-Agents\n\n{numbered}\n\n## Notes\n\nDone.\n"}


def _table_body(*ids: str) -> str:
    rows = "\n".join(f"| {i} | hand-written role | utility |" for i in ids)
    return f"# Agent\n\nDo the work.\n\n{TABLE_HEADING}\n\n| Agent | Role | Tier |\n|---|---|---|\n{rows}\n\n## Notes\n\nDone.\n"


def _resolved_real() -> dict[str, list[str]]:
    registry = real_registry()
    return {stem: resolve_declared(decl, registry) for stem, decl in real_spawn_declarations().items()}


@pytest.mark.shared_layout_reader
def test_six_formerly_hand_written_agents_carry_exactly_one_sub_agent_account(shared_reference_layout):
    # covers: AR-300a-5-i
    # angle: deployed
    """AR-300a-5-i: the compiled prompts of business-analyst, frontend-coder, test-writer,
    python-coder, architect-review (five hand-written tables) and ticket-supervisor (a fenced
    list under '### Spawn Allowlist (is_ticket_phase agents)'), in BOTH roots, each contain
    exactly one sub-agent account, and it is the delivered one: it names exactly what the
    agent's own declaration permits, and ticket-supervisor no longer carries the fenced list.
    Red today: the hand-written accounts survive and five of the six declare nothing."""
    roots = layout_roots(shared_reference_layout)
    assert len(roots) >= 2
    resolved, known = _resolved_real(), real_known_ids()
    wrong = []
    for root in roots:
        for stem in HAND_WRITTEN_STEMS:
            text = (root / f"{stem}.md").read_text(encoding="utf-8")
            accounts = spawn_accounts(text, known)
            ids = sorted(i for a in accounts for i in a["ids"])
            if len(accounts) != 1 or not resolved.get(stem) or ids != sorted(resolved[stem]):
                wrong.append((root.parent.name, stem, len(accounts), ids, sorted(resolved.get(stem, []))))
        ts = (root / "ticket-supervisor.md").read_text(encoding="utf-8")
        if LIST_HEADING in ts:
            wrong.append((root.parent.name, "ticket-supervisor", "still carries", LIST_HEADING))
    assert not wrong, f"{len(wrong)} hand-written accounts survive or are not one delivered account: {wrong[:4]}"


@pytest.mark.shared_layout_reader
def test_single_account_names_exactly_the_declared_sub_agents(shared_reference_layout):
    # covers: AR-300a-5-i
    # angle: real_artifact
    """AR-300a-5-i: over EVERY compiled prompt in both roots the surviving account equals the
    declaration in both directions (none named that was not permitted, none permitted that
    goes unnamed); python-coder's account names test-runner, the permission only its table
    held."""
    roots = layout_roots(shared_reference_layout)
    resolved, known = _resolved_real(), real_known_ids()
    report = single_account_report(roots, resolved, known)
    assert report["examined"] == len(source_templates()) * len(roots) > 0
    assert not report["offenders"], f"{len(report['offenders'])} prompts: {report['offenders'][:4]}"
    for root in roots:
        text = (root / "python-coder.md").read_text(encoding="utf-8")
        assert "test-runner" in {i for a in spawn_accounts(text, known) for i in a["ids"]}


def test_a_hand_written_table_planted_in_another_template_is_caught(tmp_path, monkeypatch, capsys, caplog):
    # covers: AR-300a-5-i
    # angle: discrimination
    """AR-300a-5-i: a hand-written sub-agent table planted in templates OUTSIDE the five is
    caught -- the compiler reports each by file name with its severity label (duplicate when
    the table equals the declaration, contradiction when it differs), a clean control is not
    reported, and the whole-population single-account check over the compiled tree names
    exactly the planted agents. Wrong version caught: an assertion that iterates only the
    five known templates."""
    caplog.set_level(logging.DEBUG)
    templates = {"zz-clean": (sfm("zz-clean", ["zz-w1"]), BODY),
                 "zz-dup": (sfm("zz-dup", ["zz-w1"]), _table_body("zz-w1")),
                 "zz-contra": (sfm("zz-contra", ["zz-w1"]), _table_body("zz-w1", "zz-w2")),
                 **workers("zz-w1", "zz-w2")}
    agents = records_for(templates)
    src = tmp_path / "compile_src"
    for stem, label in (("zz-clean", None), ("zz-dup", "duplicate"), ("zz-contra", "contradiction")):
        caplog.clear()
        capsys.readouterr()
        tpl = write_template(src / f"{stem}.md", *templates[stem])
        compile_with(tpl, agents=agents, skills_root=None)
        report = captured_report(capsys, caplog)
        if label is None:
            assert f"{stem}.md" not in report and "duplicate" not in report.lower() and "contradiction" not in report.lower()
        else:
            assert f"{stem}.md" in report, f"the hand-written table in {stem} was not reported: {report[-300:]!r}"
            assert label in report.lower(), f"{stem}: missing severity label {label!r}"
    _mod, _pkg, roots, _preps = fresh_spawn_build(tmp_path / "build", monkeypatch, templates)
    resolved = {s: list(fm.get("spawn_allowlist", [])) for s, (fm, _b) in templates.items()}
    report = single_account_report(roots, resolved, set(templates))
    assert report["examined"] == len(templates) * len(roots)
    assert sorted({o["agent"] for o in report["offenders"]}) == ["zz-contra", "zz-dup"], report["offenders"]


def test_a_hand_written_sub_agent_list_planted_in_another_template_is_caught(tmp_path, monkeypatch, capsys, caplog):
    # covers: AR-300a-5-i
    # angle: discrimination
    """AR-300a-5-i: a hand-written LIST of the agent's own permitted sub-agents planted in
    templates outside the six -- ticket-supervisor's former fenced shape (verbatim fixture),
    a bulleted list, a numbered list -- is caught: the compiler reports each by file name as a
    ``contradiction`` (it names zz-w2 beyond the declaration), a clean control is not
    reported, and the whole-population single-account check over the compiled tree names
    exactly the planted agents. Wrong versions caught: a detector that recognises only tables
    (the fenced and numbered lists would stay silent and accumulate); an assertion that
    iterates only the six known templates."""
    caplog.set_level(logging.DEBUG)
    planted = _list_bodies("zz-w1", "zz-w2")
    templates = {"zz-clean": (sfm("zz-clean", ["zz-w1"]), BODY), **workers("zz-w1", "zz-w2"),
                 **{stem: (sfm(stem, ["zz-w1"]), body) for stem, body in planted.items()}}
    agents = records_for(templates)
    src = tmp_path / "compile_src"
    for stem in ("zz-clean", *planted):
        caplog.clear()
        capsys.readouterr()
        compile_with(write_template(src / f"{stem}.md", *templates[stem]), agents=agents, skills_root=None)
        report = captured_report(capsys, caplog)
        if stem == "zz-clean":
            assert f"{stem}.md" not in report and "contradiction" not in report.lower()
        else:
            assert f"{stem}.md" in report, f"the hand-written list in {stem} was not reported: {report[-300:]!r}"
            assert "contradiction" in report.lower(), f"{stem}: missing severity label"
    _mod, _pkg, roots, _preps = fresh_spawn_build(tmp_path / "build", monkeypatch, templates)
    resolved = {s: list(fm.get("spawn_allowlist", [])) for s, (fm, _b) in templates.items()}
    report = single_account_report(roots, resolved, set(templates))
    assert report["examined"] == len(templates) * len(roots)
    assert sorted({o["agent"] for o in report["offenders"]}) == sorted(planted), report["offenders"]


def test_single_account_property_counts_every_compiled_prompt(tmp_path, monkeypatch):
    # covers: AR-300a-5-i
    # angle: boundary
    """AR-300a-5-i: on a real in-process build of the REAL templates the single-account check
    reports how many compiled prompts it examined across both roots (one per template per
    root, derived), finds no offender, and an empty population is exposed rather than passed:
    the same check over no roots reports ZERO examined (so the count assertion above fails
    on it instead of reading clean)."""
    roots, _preps = real_build_prompts(tmp_path, monkeypatch)
    resolved, known = _resolved_real(), real_known_ids()
    report = single_account_report(roots, resolved, known)
    assert len(roots) == 2 and report["examined"] == len(source_templates()) * 2
    assert not report["offenders"], f"{len(report['offenders'])} prompts are not one delivered account: {report['offenders'][:4]}"
    empty = single_account_report([], resolved, known)
    assert empty["examined"] == 0, "the check must expose an empty population, not swallow it"


def test_prose_mention_of_sub_agent_tables_is_not_a_second_account(tmp_path, monkeypatch, capsys, caplog):
    # covers: AR-300a-5-i
    # angle: failure
    """AR-300a-5-i: a body that mentions the ``## Your Available Sub-Agents`` heading in
    checklist prose without stating its own sub-agents (llm-expert's shape) is NOT a second
    account: its compiled prompt carries exactly the one delivered section and the compiler
    reports nothing about it. Control row: a real hand-written table IS reported, so silence
    is not a dead detector."""
    caplog.set_level(logging.DEBUG)
    prose = ("# Agent\n\n## Review Checklist\n\n4. **Sub-agents declared** -- any prompt that invokes the\n"
             f"   `Agent` tool must include a `{TABLE_HEADING}` or a bulleted list under\n"
             "   `### Spawn Allowlist` naming zz-w1 and zz-w2.\n")
    templates = {"zz-prose": (sfm("zz-prose", ["zz-w1"]), prose), "zz-table": (sfm("zz-table", ["zz-w1"]), _table_body("zz-w1")),
                 **workers("zz-w1")}
    _mod, _pkg, roots, _preps = fresh_spawn_build(tmp_path / "build", monkeypatch, templates)
    for root in roots:
        accounts = spawn_accounts((root / "zz-prose.md").read_text(encoding="utf-8"), set(templates))
        assert [a["ids"] for a in accounts] == [["zz-w1"]], f"{root.parent.name}: {accounts}"
    capsys.readouterr()
    caplog.clear()
    src = tmp_path / "compile_src"
    for stem in ("zz-prose", "zz-table"):
        compile_with(write_template(src / f"{stem}.md", *templates[stem]), agents=records_for(templates), skills_root=None)
    report = captured_report(capsys, caplog)
    assert "zz-prose.md" not in report, f"prose was reported as an account: {report[-300:]!r}"
    assert "zz-table.md" in report, "control: the real hand-written table was not reported"


def test_delivered_account_is_generated_not_hand_written(tmp_path, monkeypatch):
    # covers: AR-300a-5-i
    # angle: real_artifact
    """AR-300a-5-i (resolution means DELETING the accounts, not suppressing delivery): on a real
    in-process build, each of the six formerly hand-written agents has its account REGISTERED as a
    generated ``spawn_allowlist`` preparation whose text is what the compiled prompt carries,
    and its source template no longer carries a hand-written sub-agent section."""
    roots, preps = real_build_prompts(tmp_path, monkeypatch)
    for stem in HAND_WRITTEN_STEMS:
        registered = spawn_registrations([p for p in preps if p["agent"] == stem])
        assert len(registered) >= 1, f"{stem}: no generated sub-agent preparation was registered"
        for root in roots:
            assert any(norm(p["content"]) in norm((root / f"{stem}.md").read_text(encoding="utf-8")) for p in registered)
        _fm, body = parse_frontmatter((REPO_ROOT / "templates" / "agents" / f"{stem}.md").read_text(encoding="utf-8"))
        assert not has_sub_agent_heading(body), f"{stem}: the hand-written sub-agent section is still in the body"
