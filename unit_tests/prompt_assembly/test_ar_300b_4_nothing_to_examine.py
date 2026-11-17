"""AR-300b-4 -- a run that recognised NO per-agent preparations (or found no
compiled prompt, or reached only part of the tree) FAILS and says which side came
back empty; the guarantee cannot pass by looking at nothing (KI-ACS-001).

Source of truth: .../AR-300b-4.yaml. Contract: _ar_300b_support.py (B, C). A
sibling of AR-300a-1-i: it guards the delivery guarantee's OWN derived
population (the registered preparations), derived separately from the abilities
comparison's. Compiled trees are authentic (the REAL ``build_agents`` over a
planted package).

RED BASELINE: scripts/agent_preparation_delivery.py does not exist (absence red).
"""

from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300b_support import (  # noqa: E402
    COUNTS_RE,
    fresh_build,
    per_agent,
    population,
    strip_abilities,
    verdict_of,
)


def _sides(verdict: dict) -> list[str]:
    return sorted(f["side"] for f in population(verdict, "empty-population"))


def _out(capsys) -> str:
    out = capsys.readouterr()
    return out.out + "\n" + out.err


def test_zero_recognised_preparations_fails_naming_the_preparation_side(tmp_path, monkeypatch, capsys):
    # covers: AR-300b-4
    # angle: failure
    """AR-300b-4: with the derived preparation set EMPTY (explicit empty list, and
    the run registry reset) over a complete, healthy compiled tree the verdict is
    not ok, names exactly the ``preparations`` side (the prompts were fine), has
    no per-agent finding, and the build seam exits 1 saying it had nothing to
    examine. Control: the same tree with the real registrations is clean.
    Wrong version caught: an all-clear returned for an empty derivation."""
    built = fresh_build(tmp_path, monkeypatch)
    assert verdict_of(built.mod, built.roots, built.preparations, built.expected)["ok"] is True, "control"
    verdict = verdict_of(built.mod, built.roots, [], built.expected)
    assert verdict["ok"] is False and _sides(verdict) == ["preparations"]
    assert per_agent(verdict) == [] and verdict["inspected_prompt_count"] == built.expected
    built.mod.reset_preparations()
    capsys.readouterr()
    rc = built.mod.refuse_on_undelivered_preparations(
        built.project, {"output_root": ".leafcutter"}, False, expected_prompt_count=built.expected)
    text = _out(capsys).lower()
    assert rc == 1 and "nothing to examine" in text and "preparations" in text


def test_zero_compiled_prompts_fails_naming_the_prompt_side(tmp_path, monkeypatch):
    # covers: AR-300b-4
    # angle: failure
    """AR-300b-4: preparations recognised but the roots hold no agent prompt (empty
    directories, and a directory with only a nameless README) fails and names
    exactly the ``compiled_prompts`` side. Wrong version caught: reporting no
    failures because there was nothing to compare against."""
    built = fresh_build(tmp_path, monkeypatch)
    assert built.preparations, "control: nothing registered"
    empty_roots = [tmp_path / "empty" / "agents", tmp_path / "empty" / "gemini" / "agents"]
    for root in empty_roots:
        root.mkdir(parents=True)
    (empty_roots[1] / "README.md").write_text("# not an agent prompt\n", encoding="utf-8")
    verdict = verdict_of(built.mod, empty_roots, built.preparations, built.expected)
    assert verdict["ok"] is False and _sides(verdict) == ["compiled_prompts"]
    assert verdict["inspected_prompt_count"] == 0


def test_nothing_to_examine_output_differs_from_everything_arrived_output(tmp_path, monkeypatch):
    # covers: AR-300b-4
    # angle: boundary
    """AR-300b-4: the reports are distinguishable from ONE run's output alone: the
    clean verdict states its counts, never 'nothing to examine', is ok with no
    findings; the preparation-side and prompt-side empties each say 'nothing to
    examine', name their own side, are not ok, and differ from each other.
    Wrong version caught: both states producing an empty findings list with no
    other difference."""
    built = fresh_build(tmp_path, monkeypatch)
    empty_roots = [tmp_path / "empty" / "agents"]
    empty_roots[0].mkdir(parents=True)
    clean = verdict_of(built.mod, built.roots, built.preparations, built.expected)
    no_preps = verdict_of(built.mod, built.roots, [], built.expected)
    no_prompts = verdict_of(built.mod, empty_roots, built.preparations, built.expected)
    render = built.mod.render_preparation_verdict
    texts = {k: render(v).lower() for k, v in (("clean", clean), ("preps", no_preps), ("prompts", no_prompts))}
    assert clean["ok"] and not no_preps["ok"] and not no_prompts["ok"]
    assert "nothing to examine" not in texts["clean"] and COUNTS_RE.search(texts["clean"])
    assert "nothing to examine" in texts["preps"] and "nothing to examine" in texts["prompts"]
    assert "preparations" in texts["preps"] and "compiled prompts" in texts["prompts"]
    assert len(set(texts.values())) == 3, "two of the three states render identically"


def test_fewer_prompts_examined_than_the_build_compiled_fails(tmp_path, monkeypatch):
    # covers: AR-300b-4
    # angle: boundary
    """AR-300b-4: the build compiled 8 prompts (4 agents x 2 roots) but only 6 are
    present to examine -- every present prompt is delivered, so the ONLY failure
    is the partial reach: a short-population finding carrying inspected == 6 and
    expected == 8. Control: the same registrations over the full tree are clean.
    Wrong version caught: a guarantee that silently reached part of the tree is
    read as clean."""
    built = fresh_build(tmp_path, monkeypatch)
    keep = [p for p in built.preparations if p["agent"] in {"zz-holder-a", "zz-holder-b"}]
    assert keep and verdict_of(built.mod, built.roots, keep, built.expected)["ok"] is True, "control"
    for stem in ("zz-holder-c", "zz-plain"):
        (built.roots[0] / f"{stem}.md").unlink()
    verdict = verdict_of(built.mod, built.roots, keep, built.expected)
    assert verdict["ok"] is False and per_agent(verdict) == []
    short = population(verdict, "short-population")
    assert [(f["inspected"], f["expected"]) for f in short] == [(6, 8)]
    assert verdict["inspected_prompt_count"] == 6 and verdict["expected_prompt_count"] == 8


def test_unresolvable_output_root_fails_rather_than_resolving_to_empty(tmp_path, monkeypatch, capsys):
    # covers: AR-300b-4
    # angle: deployed
    """AR-300b-4: through the build seam, each way the compiled side goes empty
    exits 1 naming the unreadable root instead of resolving to an empty population
    and a clean exit: (1) no compiled tree at all (a fresh worktree), (2) the
    ``agents`` root is a broken symlink, (3) the declared output root is absent
    although a complete ``.claude/agents`` copy exists (a stale shim is never
    the fallback). Control: the intact tree is accepted (rc 0)."""
    built = fresh_build(tmp_path, monkeypatch)
    cfg, expected = {"output_root": ".leafcutter"}, built.expected
    assert built.mod.refuse_on_undelivered_preparations(
        built.project, cfg, False, expected_prompt_count=expected) == 0, "control"
    shim = built.project / ".claude" / "agents"
    shutil.copytree(built.roots[0], shim)
    capsys.readouterr()

    shutil.rmtree(built.out_root / "gemini")
    (built.out_root / "agents").rename(tmp_path / "moved_agents")
    (built.out_root / "agents").symlink_to(tmp_path / "does_not_exist", target_is_directory=True)
    rc = built.mod.refuse_on_undelivered_preparations(built.project, cfg, False, expected_prompt_count=expected)
    text = _out(capsys)
    assert rc == 1 and str(built.out_root / "agents") in text, text[-500:]

    (built.out_root / "agents").unlink()
    shutil.rmtree(built.out_root)
    rc = built.mod.refuse_on_undelivered_preparations(built.project, cfg, False, expected_prompt_count=expected)
    text = _out(capsys)
    assert rc == 1 and str(built.out_root) in text, "absent compiled tree resolved to a clean/empty result"
    assert any(shim.glob("*.md")), "control: the stale shim copy was complete and readable"


def test_compiled_roots_come_from_the_declared_output_root(tmp_path, monkeypatch, capsys):
    # covers: AR-300b-4
    # angle: deployed
    """AR-300b-4 (resolution rule): with a NON-default declared output root the
    seam reads ``<project>/<output_root>/agents`` and ``.../gemini/agents`` --
    a complete tree there is accepted although a decoy ``.claude/agents`` shim
    holds a prompt stripped of its abilities section, and the reverse (broken
    declared tree, pristine shim) is refused. Wrong version caught: reading the
    hard-coded ``.claude/agents`` path."""
    built = fresh_build(tmp_path, monkeypatch)
    declared = built.project / "zz_declared_out"
    shutil.move(str(built.out_root), str(declared))
    decoy = built.project / ".claude" / "agents"
    shutil.copytree(declared / "agents", decoy)
    strip_abilities([decoy], ["zz-holder-a"])
    cfg = {"output_root": "zz_declared_out"}
    capsys.readouterr()
    rc = built.mod.refuse_on_undelivered_preparations(
        built.project, cfg, False, expected_prompt_count=built.expected)
    assert rc == 0, f"a complete declared tree was refused (decoy shim read?): {_out(capsys)[-400:]}"
    shutil.copy2(declared / "gemini" / "agents" / "zz-holder-a.md", decoy / "zz-holder-a.md")
    strip_abilities([declared / "agents"], ["zz-holder-a"])
    capsys.readouterr()
    rc = built.mod.refuse_on_undelivered_preparations(
        built.project, cfg, False, expected_prompt_count=built.expected)
    assert rc == 1 and "zz-holder-a" in _out(capsys), "a broken declared tree was accepted"
