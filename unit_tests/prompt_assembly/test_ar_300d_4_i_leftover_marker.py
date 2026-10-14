"""AR-300d-4-i -- a definition still carrying a leftover retired marker compiles to
ONE section and NO visible token, and the leftover is reported by definition name.

Source of truth: .../AR-300d-4-i.yaml. Fixtures: frontmatter via yaml.safe_dump
(write_template); compiled by the REAL compile_agent_template; the report is read
from the REAL ``build_placeholder_detection.scan_for_placeholders`` (the AC names
that module as the right home of the leftover-token report; contract in
_ar_300ad_support.py item 3).

NOT PINNED (blocked on slice 3): that the retired-token SET is DERIVED from the
registration AR-300b-2 introduces. That registration does not exist yet, so
test_both_retired_tokens_are_covered asserts coverage of both tokens only.

RED BASELINE (measured): with a registry record the compiler substitutes the
legacy registry table AT the token AND appends the declared table (two sections);
without a registry the token stays visible in the prompt; nothing reports the
leftover (scan_for_placeholders has no rule for the retired tokens).
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    REPO_ROOT,
    RETIRED_SKILLS_TOKEN,
    RETIRED_SPAWN_TOKEN,
    ability_rows,
    accounts,
    agent_fm,
    captured_report,
    compile_with,
    make_skill,
    named_in_accounts,
    source_templates,
    write_template,
)
from build_placeholder_detection import scan_for_placeholders  # noqa: E402

SKILLS = {"zz-alpha": "Alpha skill forges alpha widgets on request",
          "zz-beta": "Beta skill polishes beta gadgets on request"}
KNOWN = set(SKILLS)
GRANT = [{"skill_id": "zz-alpha", "mode": "always"}]
STEM = "zz-left"


def _body(token: str) -> str:
    return f"# Agent\n\nDo the work.\n\n{token}\n\n## Closing\n\nFinish cleanly.\n"


def _template(tmp_path: Path, token: str, stem: str = STEM) -> Path:
    return write_template(tmp_path / "templates" / "agents" / f"{stem}.md", agent_fm(stem, GRANT), _body(token))


def _skills_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    for sid, desc in SKILLS.items():
        make_skill(root, sid, desc)
    return root


def _agents(state: str):
    if state == "record_present":
        # mid-migration reality: the registry still lists the same ability
        return [{"id": STEM, "template_path": f"templates/agents/{STEM}.md", "skills_used": ["zz-alpha"]}]
    if state == "record_other":
        # the registry names a DIFFERENT ability than the declaration, so a compiler
        # that still substitutes the registry list at the token is observable
        return [{"id": STEM, "template_path": f"templates/agents/{STEM}.md", "skills_used": ["zz-beta"]}]
    if state == "record_absent":
        return [{"id": "someone-else", "template_path": "templates/agents/someone-else.md", "skills_used": ["zz-alpha"]}]
    return None


@pytest.mark.parametrize("registry_state", ["record_present", "record_absent"])
def test_definition_with_a_leftover_marker_compiles_to_exactly_one_section(tmp_path, registry_state):
    # covers: AR-300d-4-i
    # angle: boundary
    """AR-300d-4-i: a template declaring a grant AND still carrying the retired
    ``{{my_skills_used}}`` token compiles to a prompt that names the granted
    ability ONCE -- one account, one row -- not twice. RED today: with a registry
    record the token is replaced by the legacy table and the declared table is
    appended too; with no record the compiler raises."""
    tpl = _template(tmp_path, RETIRED_SKILLS_TOKEN)
    text = compile_with(tpl, agents=_agents(registry_state), skills_root=_skills_root(tmp_path))
    found = accounts(text, KNOWN)
    assert len(found) == 1, f"{len(found)} accounts of the granted abilities: {[a['heading'] for a in found]}"
    assert named_in_accounts(text, KNOWN) == {"zz-alpha"}
    assert len(ability_rows(text, KNOWN)["zz-alpha"]) == 1, "granted ability named more than once"


@pytest.mark.parametrize("registry_state", ["record_other", "no_registry"])
def test_no_marker_token_remains_visible_in_the_compiled_prompt(tmp_path, registry_state):
    # covers: AR-300d-4-i
    # angle: deployed
    """AR-300d-4-i: the retired token appears NOWHERE in the compiled prompt -- it
    is stripped, not left as ``{{...}}`` noise the agent would read as content.
    RED today with no registry (the token survives verbatim)."""
    tpl = _template(tmp_path, RETIRED_SKILLS_TOKEN)
    text = compile_with(tpl, agents=_agents(registry_state), skills_root=_skills_root(tmp_path))
    assert RETIRED_SKILLS_TOKEN not in text
    assert not re.search(r"\{\{\s*my_skills_used\s*\}\}", text)
    assert "{{" not in text and "}}" not in text, "a template-token residue survives in the compiled prompt"
    assert named_in_accounts(text, KNOWN) == {"zz-alpha"}, "control: the declared section was still delivered"


def test_leftover_marker_is_reported_naming_the_definition(tmp_path):
    # covers: AR-300d-4-i
    # angle: criterion
    """AR-300d-4-i: the placeholder scan reports the leftover retired token and
    names the template it is in (relative path ending in the file name). Controls:
    a clean template, the token merely DISCUSSED in inline code, and the token in
    a fenced example are NOT reported -- the report does not fire on prose."""
    left = _template(tmp_path, RETIRED_SKILLS_TOKEN, "zz-left")
    clean = write_template(tmp_path / "templates" / "agents" / "zz-clean.md", agent_fm("zz-clean", GRANT), _body("Plain line."))
    inline = write_template(tmp_path / "templates" / "agents" / "zz-inline.md", agent_fm("zz-inline", GRANT),
                            _body("The old design used the `{{my_skills_used}}` token; do not add it back."))
    fenced = write_template(tmp_path / "templates" / "agents" / "zz-fenced.md", agent_fm("zz-fenced", GRANT),
                            _body("```\n{{my_skills_used}}\n```"))
    hits = scan_for_placeholders(tmp_path, paths=[left, clean, inline, fenced])
    retired = [h for h in hits if "my_skills_used" in h["marker"]]
    assert [h["path"] for h in retired] == [str(left.relative_to(tmp_path))], f"hits: {hits}"
    assert retired[0]["path"].endswith("zz-left.md")


def test_compiling_a_template_with_a_leftover_marker_reports_it_by_name(tmp_path, capsys, caplog):
    # covers: AR-300d-4-i
    # angle: seam
    """AR-300d-4-i (when the build compiles): compiling the template reports the
    leftover token and the template's file name -- so the residue is visible while
    the prompt itself comes out correct. The report channel is any of stdout /
    stderr / a WARNING+ log record. Control: compiling a clean template mentions
    neither."""
    caplog.set_level(logging.DEBUG)
    skills_root = _skills_root(tmp_path)
    clean = write_template(tmp_path / "templates" / "agents" / "zz-clean.md", agent_fm("zz-clean", GRANT), _body("Plain line."))
    compile_with(clean, agents=_agents("record_present"), skills_root=skills_root)
    quiet = captured_report(capsys, caplog)
    assert "my_skills_used" not in quiet and "zz-clean" not in quiet

    caplog.clear()
    tpl = _template(tmp_path, RETIRED_SKILLS_TOKEN)
    compile_with(tpl, agents=_agents("record_present"), skills_root=skills_root)
    report = captured_report(capsys, caplog)
    assert "zz-left.md" in report and "my_skills_used" in report, f"no report naming the definition: {report[-300:]!r}"


def test_both_retired_tokens_are_covered(tmp_path):
    # covers: AR-300d-4-i
    # angle: boundary
    """AR-300d-4-i: BOTH retired tokens (``{{my_skills_used}}`` and
    ``{{my_spawn_allowlist}}``) are detected, each naming its own template; and on
    the REAL source tree (population derived from the templates, none carries
    either token) the scan reports no retired token -- coverage without noise.
    The DERIVED-from-registration half is not pinned (slice 3, AR-300b-2)."""
    skills_left = _template(tmp_path, RETIRED_SKILLS_TOKEN, "zz-skills-left")
    spawn_left = _template(tmp_path, RETIRED_SPAWN_TOKEN, "zz-spawn-left")
    hits = scan_for_placeholders(tmp_path, paths=[skills_left, spawn_left])
    by_path = {h["path"]: h["marker"] for h in hits if "my_" in h["marker"]}
    assert set(by_path) == {str(skills_left.relative_to(tmp_path)), str(spawn_left.relative_to(tmp_path))}
    assert "my_skills_used" in by_path[str(skills_left.relative_to(tmp_path))]
    assert "my_spawn_allowlist" in by_path[str(spawn_left.relative_to(tmp_path))]

    real = source_templates()
    assert len(real) > 30
    real_hits = [h for h in scan_for_placeholders(REPO_ROOT, paths=real)
                 if "my_skills_used" in h["marker"] or "my_spawn_allowlist" in h["marker"]]
    assert real_hits == []
