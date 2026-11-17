"""AR-300c-5 -- which sub-agents an agent may dispatch is declared ONCE, in the agent's
own frontmatter (``spawn_allowlist``, beside ``tools``), and delivery reads only that.

Source of truth: .../AR-300c-5.yaml. Contract: _ar_300e_support.py items 1 and 2.
Evidence is the COMPILED prompt (real in-process ``build_agents`` over a planted
package, or the deployed layout), never the registry copy.

RED BASELINE (slice 5): nothing delivers a sub-agent section from the declaration, so
the compiled prompt names no sub-agent for any declaring agent (assertion red, kind
``assertion``); the real-template test is red because the registry still holds
permissions no template declares.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import layout_roots  # noqa: E402
from _ar_300e_support import (  # noqa: E402
    BODY,
    KEY,
    MACRO,
    REPO_ROOT,
    build_in,
    edit_declaration,
    named_sub_agents,
    parse_frontmatter,
    read_prompts,
    real_known_ids,
    real_registry,
    real_spawn_declarations,
    resolve_declared,
    sfm,
    snapshot_tree,
    source_templates,
    spawn_accounts,
    spawn_package,
    template_frontmatter,
)


def _workers(*ids: str) -> dict:
    return {i: (sfm(i, tools="Bash, Read"), BODY) for i in ids}


def _boss_pkg(tmp_path: Path, declared, **kw):
    templates = {"zz-boss": (sfm("zz-boss", declared), BODY), **_workers("zz-w1", "zz-w2", "zz-w3")}
    return spawn_package(tmp_path / "src", templates, **kw), set(templates)


def _set_registry(pkg: Path, edit) -> None:
    path = pkg / "config" / "agent_registry.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    edit({a["id"]: a for a in data["agents"]})
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@pytest.mark.shared_layout_reader
def test_compiled_sub_agents_equal_the_frontmatter_declaration(shared_reference_layout):
    # covers: AR-300c-5
    # angle: deployed
    """AR-300c-5: after a real build, every agent whose template declares a non-empty
    ``spawn_allowlist`` has, in BOTH platform roots, a compiled prompt naming exactly the
    declared sub-agents (macro resolved) -- none added, none omitted. Wrong versions caught:
    a section that names a sample, one root only, nothing delivered (red today: the
    declaring agent ``onboard`` gets no section)."""
    roots = layout_roots(shared_reference_layout)
    assert len(roots) >= 2, f"expected claude + gemini compiled roots, found {roots}"
    declared, registry, known = real_spawn_declarations(), real_registry(), real_known_ids()
    assert declared, "0 declaring agents examined: an empty population is not a pass"
    examined, wrong = 0, []
    for stem, decl in sorted(declared.items()):
        want = set(resolve_declared(decl, registry))
        for root in roots:
            examined += 1
            got = named_sub_agents((root / f"{stem}.md").read_text(encoding="utf-8"), known)
            if got != want:
                wrong.append((root.parent.name, stem, sorted(want ^ got)))
    assert examined == len(declared) * len(roots)
    assert not wrong, f"{len(wrong)}/{examined} compiled prompts differ from their declaration: {wrong[:5]}"


def test_editing_only_the_declaration_changes_the_compiled_prompt(tmp_path, monkeypatch):
    # covers: AR-300c-5
    # angle: criterion
    """AR-300c-5: changing ONLY the frontmatter ``spawn_allowlist`` changes the compiled
    section on the next build -- exactly one source file differs between the two builds, the
    registry is untouched, and no other agent's prompt moves. Control: before the edit the
    prompt names exactly the first declaration (red today: nothing is delivered)."""
    pkg, known = _boss_pkg(tmp_path, ["zz-w1"])
    out = tmp_path / "out"
    roots = build_in(pkg, out, monkeypatch)
    for root in roots:
        assert named_sub_agents((root / "zz-boss.md").read_text(encoding="utf-8"), known) == {"zz-w1"}
    before_src, before_prompts = snapshot_tree(pkg), {r: read_prompts(r) for r in roots}
    edit_declaration(pkg, "zz-boss", ["zz-w1", "zz-w2"])
    after_src = snapshot_tree(pkg)
    assert {k for k in set(before_src) | set(after_src) if before_src.get(k) != after_src.get(k)} == \
        {"templates/agents/zz-boss.md"}, "the edit touched more than the one declaration"
    roots = build_in(pkg, out, monkeypatch)
    for root in roots:
        prompts = read_prompts(root)
        assert named_sub_agents(prompts["zz-boss"], known) == {"zz-w1", "zz-w2"}
        for stem in ("zz-w1", "zz-w2", "zz-w3"):
            assert prompts[stem] == before_prompts[root][stem], f"{stem} changed with the edit"


def test_editing_only_the_registry_spawn_allowlist_changes_nothing_compiled(tmp_path, monkeypatch):
    # covers: AR-300c-5
    # angle: discrimination
    """AR-300c-5 (the negative clause): the central registry's record of permitted
    sub-agents does NOT feed delivery. The registry disagrees with the declaration for
    ``zz-boss`` (and lists sub-agents for ``zz-undeclared``, which declares none): the
    prompt must name exactly the declaration (not the registry field, not the union of the
    two) and the undeclared agent gets no section. Then ONLY the registry field is edited
    again and every compiled prompt is byte-identical. Wrong versions caught: delivery reads
    the registry spawn_allowlist (today's build_per_agent_spawn_table); delivery merges the
    registry field with the declaration."""
    templates = {"zz-boss": (sfm("zz-boss", ["zz-w1"]), BODY), "zz-undeclared": (sfm("zz-undeclared"), BODY),
                 **_workers("zz-w1", "zz-w2", "zz-w3")}
    pkg = spawn_package(tmp_path / "src", templates,
                        registry_spawn={"zz-boss": ["zz-w2", "zz-w3"], "zz-undeclared": ["zz-w1"]})
    known, out = set(templates), tmp_path / "out"
    roots = build_in(pkg, out, monkeypatch)
    for root in roots:
        prompts = read_prompts(root)
        assert named_sub_agents(prompts["zz-boss"], known) == {"zz-w1"}
        assert spawn_accounts(prompts["zz-undeclared"], known) == []
    first = {r: read_prompts(r) for r in roots}
    templates_before = snapshot_tree(pkg / "templates")
    _set_registry(pkg, lambda by_id: (by_id["zz-boss"].update(spawn_allowlist=["zz-w3"]),
                                      by_id["zz-undeclared"].update(spawn_allowlist=["zz-w2", "zz-w3"])))
    roots = build_in(pkg, out, monkeypatch, allow_unchanged=True)
    assert snapshot_tree(pkg / "templates") == templates_before
    assert {r: read_prompts(r) for r in roots} == first, "a registry-only edit changed a compiled prompt"


def test_ticket_phase_macro_stays_one_entry_and_resolves_per_build(tmp_path, monkeypatch):
    # covers: AR-300c-5
    # angle: boundary
    """AR-300c-5: the declaration keeps ``__ticket_phase_agents__`` as ONE list item; the
    compiled section names the agents whose ``is_ticket_phase`` is true on THAT build, each
    once and never the literal token; marking one more agent (registry flag only, no template
    edit) names it on the next build. Wrong version caught: pre-expanding the macro."""
    templates = {"zz-super": (sfm("zz-super", [MACRO]), BODY), **_workers("zz-p1", "zz-p2", "zz-p3", "zz-np")}
    pkg = spawn_package(tmp_path / "src", templates, ticket_phase=("zz-p1", "zz-p2"))
    assert template_frontmatter(pkg / "templates" / "agents" / "zz-super.md")[KEY] == [MACRO]
    known, out = set(templates), tmp_path / "out"
    roots = build_in(pkg, out, monkeypatch)
    for root in roots:
        text = (root / "zz-super.md").read_text(encoding="utf-8")
        accounts = spawn_accounts(text, known)
        assert [sorted(a["ids"]) for a in accounts] == [["zz-p1", "zz-p2"]], accounts
        assert MACRO not in text
    source_before = (pkg / "templates" / "agents" / "zz-super.md").read_bytes()
    _set_registry(pkg, lambda by_id: by_id["zz-p3"].update(is_ticket_phase=True))
    roots = build_in(pkg, out, monkeypatch, allow_unchanged=True)
    for root in roots:
        accounts = spawn_accounts((root / "zz-super.md").read_text(encoding="utf-8"), known)
        assert [sorted(a["ids"]) for a in accounts] == [["zz-p1", "zz-p2", "zz-p3"]]
    assert (pkg / "templates" / "agents" / "zz-super.md").read_bytes() == source_before


def test_real_registry_copy_follows_the_declarations_and_still_validates(capsys):
    # covers: AR-300c-5-ii
    # angle: real_artifact
    """AR-300c-5-ii (the real build's own guard): once the registry's spawn lists are the
    derived copy of the declarations, the REAL registry validates with no error -- in
    particular no ``asymmetric spawn`` error (a sub-agent's ``spawned_by`` must list every agent
    whose declaration permits it). That field is NOT derived (the hook changes no other byte),
    so the union's new edge python-coder -> test-runner needs ``test-runner.spawned_by`` edited
    by hand or the real build REFUSES. Red today: 23 agents hold a registry permission their
    header does not declare."""
    from registry_validator import validate_agent_registry

    errors = validate_agent_registry(REPO_ROOT)
    capsys.readouterr()
    declared = {t.stem: list(template_frontmatter(t).get(KEY) or []) for t in source_templates()}
    divergent = sorted(a["id"] for a in real_registry() if a.get("template_path")
                       and set(a.get("spawn_allowlist") or []) != set(declared.get(Path(a["template_path"]).stem, [])))
    assert not divergent, f"{len(divergent)} registry copies differ from their declaration: {divergent}"
    assert errors == [], f"the real registry no longer validates: {errors}"


def test_tools_and_spawn_allowlist_parse_from_the_same_block_on_real_templates():
    # covers: AR-300c-5
    # angle: real_artifact
    """AR-300c-5: on the REAL templates, ONE frontmatter parse returns the tools AND the
    ``spawn_allowlist`` of every agent, including templates whose on-disk ``tools:`` line
    carries a trailing YAML comment (the clean-fixture blind spot). The comment never leaks
    into a tool token, and every agent the registry records a permission for DECLARES it in
    that same block (red today: the registry holds permissions no header declares)."""
    by_stem = {Path(a["template_path"]).stem: a for a in real_registry() if a.get("template_path")}
    examined, commented, record_only = 0, [], []
    for tpl in source_templates():
        text = tpl.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        raw = fm.get("tools")
        tokens = [t.strip() for t in (raw.split(",") if isinstance(raw, str) else raw or []) if str(t).strip()]
        assert all("#" not in t and " " not in t for t in tokens), f"{tpl.name}: comment leaked into {tokens}"
        examined += 1
        if re.search(r"^tools:[^\n]*\s#", text, re.MULTILINE):
            commented.append(tpl.stem)
        record = by_stem.get(tpl.stem)
        if record and record.get("spawn_allowlist") and KEY not in fm:
            record_only.append(tpl.stem)
    assert examined > 30 and commented, f"examined={examined}, templates with a tools comment={commented}"
    assert not record_only, f"{len(record_only)} agents hold a registry permission their header does not declare: {record_only}"
