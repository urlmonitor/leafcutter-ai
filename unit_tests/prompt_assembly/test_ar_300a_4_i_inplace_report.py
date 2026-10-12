"""AR-300a-4-i -- a SOURCE definition that states its own abilities in its body
is reported by name when the build runs, with duplicate-vs-contradiction
severity, while a definition that merely discusses skills in prose is not.

Source of truth: .../AR-300a-4-i.yaml. This detector legitimately reads SOURCE
templates (its subject is what an author wrote in place) -- it is the one check
here that does; the compiled-prompt checks live in the other AR-300a files.
Contract (new module ``scripts/agent_inplace_abilities.py``): see
_ar_300ad_support.py item 2.

Fixtures: frontmatter via yaml.safe_dump (write_template); bodies are markdown
prose. The "states its own grant" body mirrors the real python-coder.md shape.

RED BASELINE: the detector module does not exist and compile_agent_template
reports nothing, so every test fails (absence / assertion red).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    REPO_ROOT,
    agent_fm,
    captured_report,
    compile_with,
    inplace_module,
    make_skill,
    source_templates,
    write_template,
)

KNOWN = {"zz-alpha", "zz-beta", "zz-gamma"}
GRANT_AB = [{"skill_id": "zz-alpha", "mode": "always"}, {"skill_id": "zz-beta", "mode": "always"}]


def _stating_body(*ids: str) -> str:
    rows = "\n".join(f"| {i} | hand-written description of {i} |" for i in ids)
    return f"# Agent\n\nDo the work.\n\n## Your Available Skills\n\n| Skill | Description |\n|---|---|\n{rows}\n\n## Notes\n\nDone.\n"


PROSE_BODIES = {
    "zz-prose-rules": "# Agent\n\n## Skill Usage Rules\n\nInvoke the `zz-alpha` skill via the Skill tool before committing; skills are optional.\n",
    "zz-prose-checks": "# Agent\n\n## Pre-Completion Checks\n\n### 1. zz-alpha\n\nInvoke zz-alpha on every file you touched.\n\n### 2. zz-beta\n\nThen run zz-beta.\n",
    "zz-prose-fenced": "# Agent\n\n## Response Payload\n\n```\n### Skills run\n- zz-alpha: <pass>\n- zz-beta: <pass>\n```\n",
}


def _dir(tmp_path: Path, templates: dict) -> Path:
    d = tmp_path / "templates" / "agents"
    for stem, (fm, body) in templates.items():
        write_template(d / f"{stem}.md", fm, body)
    return d


def _by_name(result: dict) -> dict[str, dict]:
    return {f["template"]: f for f in result["findings"]}


def test_template_stating_its_own_grant_in_the_body_is_reported_by_name(tmp_path):
    # covers: AR-300a-4-i
    # angle: criterion
    """AR-300a-4-i: a source template stating its abilities in its body is
    reported -- the template named, the in-place abilities, and the declared
    grant. (In-place names 1 of the 2 declared, like the real python-coder.)"""
    d = _dir(tmp_path, {
        "zz-stating": (agent_fm("zz-stating", GRANT_AB), _stating_body("zz-alpha")),
        "zz-clean": (agent_fm("zz-clean", GRANT_AB), "# Agent\n\nDo the work.\n"),
    })
    result = inplace_module().detect_inplace_abilities(d, known_skill_ids=KNOWN)
    findings = _by_name(result)
    assert set(findings) == {"zz-stating.md"}, f"reported: {sorted(findings)}"
    f = findings["zz-stating.md"]
    assert sorted(f["inplace_abilities"]) == ["zz-alpha"]
    assert sorted(f["declared_abilities"]) == ["zz-alpha", "zz-beta"]


def test_report_labels_agreement_as_duplicate_and_divergence_as_contradiction(tmp_path):
    # covers: AR-300a-4-i
    # angle: criterion
    """AR-300a-4-i: an in-place list matching the declaration is a ``duplicate``;
    ANY difference is a ``contradiction`` -- fewer (subset), more (extra id), or
    no declaration at all. Wrong version caught: treating a subset as agreement."""
    d = _dir(tmp_path, {
        "zz-dup": (agent_fm("zz-dup", GRANT_AB), _stating_body("zz-alpha", "zz-beta")),
        "zz-subset": (agent_fm("zz-subset", GRANT_AB), _stating_body("zz-alpha")),
        "zz-extra": (agent_fm("zz-extra", GRANT_AB[:1]), _stating_body("zz-alpha", "zz-gamma")),
        "zz-nodecl": (agent_fm("zz-nodecl"), _stating_body("zz-alpha")),
    })
    result = inplace_module().detect_inplace_abilities(d, known_skill_ids=KNOWN)
    kinds = {name: f["kind"] for name, f in _by_name(result).items()}
    assert kinds == {
        "zz-dup.md": "duplicate",
        "zz-subset.md": "contradiction",
        "zz-extra.md": "contradiction",
        "zz-nodecl.md": "contradiction",
    }


def test_template_merely_discussing_abilities_in_prose_is_not_reported(tmp_path):
    # covers: AR-300a-4-i
    # angle: failure
    """AR-300a-4-i control: templates whose prose mentions skills -- a prose
    section, numbered ``### 1. <id>`` headings, a FENCED example list -- produce
    NO finding even though they name installed skill ids; the one stating
    template added as a control row IS reported (so silence is not a dead
    detector). Wrong version caught: matching the bare word 'skills' or the id."""
    templates = {stem: (agent_fm(stem, GRANT_AB), body) for stem, body in PROSE_BODIES.items()}
    d = _dir(tmp_path, templates)
    clean = inplace_module().detect_inplace_abilities(d, known_skill_ids=KNOWN)
    assert clean["examined_count"] == 3
    assert clean["findings"] == [] and clean["stating_count"] == 0

    write_template(d / "zz-control.md", agent_fm("zz-control", GRANT_AB), _stating_body("zz-alpha"))
    with_control = inplace_module().detect_inplace_abilities(d, known_skill_ids=KNOWN)
    assert set(_by_name(with_control)) == {"zz-control.md"}
    assert with_control["examined_count"] == 4 and with_control["stating_count"] == 1


def test_real_templates_other_than_the_known_instance_are_not_reported():
    # covers: AR-300a-4-i
    # angle: failure
    """AR-300a-4-i control on the REAL source tree: the detector over the real
    ``templates/agents`` does not fire across the tree -- at most python-coder
    (today's one hand-written section; after repair, none) is reported, never
    any of the ~60 templates that merely discuss skills. Examined is derived."""
    result = inplace_module().detect_inplace_abilities(
        REPO_ROOT / "templates" / "agents",
        known_skill_ids={p.parent.name for p in (REPO_ROOT / "templates" / "skills").glob("*/SKILL.md")},
    )
    assert result["examined_count"] == len(source_templates()) > 30
    reported = {f["template"] for f in result["findings"]}
    assert reported <= {"python-coder.md"}, f"false positives across the tree: {sorted(reported)}"


def test_detector_reports_counts_examined_and_found(tmp_path):
    # covers: AR-300a-4-i
    # angle: boundary
    """AR-300a-4-i: the detector states how many source templates it examined and
    how many stated their own grant; ZERO examined is a failure, not a clean
    result; a non-empty population with none stating is a legitimate clean tree
    that still reports its counts."""
    mod = inplace_module()
    d = _dir(tmp_path / "mixed", {
        "zz-a": (agent_fm("zz-a", GRANT_AB), _stating_body("zz-alpha")),
        "zz-b": (agent_fm("zz-b", GRANT_AB), "# Agent\n"),
        "zz-c": (agent_fm("zz-c"), "# Agent\n"),
    })
    mixed = mod.detect_inplace_abilities(d, known_skill_ids=KNOWN)
    assert (mixed["examined_count"], mixed["stating_count"]) == (3, 1)

    empty = tmp_path / "none" / "templates" / "agents"
    empty.mkdir(parents=True)
    zero = mod.detect_inplace_abilities(empty, known_skill_ids=KNOWN)
    assert zero["examined_count"] == 0 and zero["ok"] is False

    clean_dir = _dir(tmp_path / "clean", {"zz-x": (agent_fm("zz-x", GRANT_AB), "# Agent\n"),
                                          "zz-y": (agent_fm("zz-y"), "# Agent\n")})
    clean = mod.detect_inplace_abilities(clean_dir, known_skill_ids=KNOWN)
    assert (clean["examined_count"], clean["stating_count"]) == (2, 0)
    assert clean["ok"] is True and clean["findings"] == []


def test_detector_resolves_template_paths_from_the_repository_root(tmp_path, monkeypatch):
    # covers: AR-300a-4-i
    # angle: deployed
    """AR-300a-4-i: invoked from a subdirectory, an unrelated directory, or a
    worktree, the detector (called with no path) still finds the real template
    population instead of matching nothing and exiting clean. Population is
    derived from the source tree, never a literal."""
    mod = inplace_module()
    expected = len(source_templates())
    assert expected > 30
    other = tmp_path / "somewhere" / "else"
    other.mkdir(parents=True)
    for cwd in (REPO_ROOT / "unit_tests", other, tmp_path):
        monkeypatch.chdir(cwd)
        result = mod.detect_inplace_abilities()
        assert result["examined_count"] == expected, f"from cwd={cwd}: examined {result['examined_count']}"
        assert result["ok"] is True


def test_compiling_a_template_that_states_its_own_grant_reports_it_by_name(tmp_path, capsys, caplog):
    # covers: AR-300a-4-i
    # angle: seam
    """AR-300a-4-i (when the build runs): compiling a source template that states
    its own grant reports it by file name with its severity label -- duplicate
    when the in-place list matches the declaration, contradiction when it does
    not. Control: compiling a clean template reports neither word. The report
    channel is any of stdout / stderr / a WARNING+ log record."""
    caplog.set_level(logging.DEBUG)
    skills_root = tmp_path / "skills"
    for sid in ("zz-alpha", "zz-beta"):
        make_skill(skills_root, sid, f"{sid} fixture skill")
    src = tmp_path / "src"

    clean = write_template(src / "zz-clean.md", agent_fm("zz-clean", GRANT_AB), "# Agent\n\nDo the work.\n")
    compile_with(clean, agents=None, skills_root=skills_root)
    quiet = captured_report(capsys, caplog).lower()
    assert "duplicate" not in quiet and "contradiction" not in quiet and "zz-clean" not in quiet

    for stem, ids, label in (("zz-dupe", ("zz-alpha", "zz-beta"), "duplicate"),
                             ("zz-contra", ("zz-alpha",), "contradiction")):
        caplog.clear()
        tpl = write_template(src / f"{stem}.md", agent_fm(stem, GRANT_AB), _stating_body(*ids))
        compile_with(tpl, agents=None, skills_root=skills_root)
        report = captured_report(capsys, caplog)
        assert f"{stem}.md" in report, f"report does not name {stem}.md: {report[-300:]!r}"
        assert label in report.lower(), f"report lacks the severity label {label!r}"
