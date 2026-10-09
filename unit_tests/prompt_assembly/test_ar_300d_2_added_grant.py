"""AR-300d-2 -- an ability granted to an existing agent reaches it on the NEXT
build with no second edit, reaches NO other agent (blast radius over the whole
compiled tree), and an ability created and granted in the same edit arrives too.

Source of truth: .../AR-300d-2.yaml. Evidence = compiled prompts of two real
``build_agents`` runs (before / after the edit) over a copy of the real tree,
compared by content in BOTH platform roots. The edit touches ONLY one agent's
frontmatter declaration (text-level insertion; the registry is never edited).

GREEN-ALREADY (all three): slice 1's append reads the declaration on every
build. Mutation proofs: AR300AD_MUTATION=shared_leak (an ability seen on one
agent leaks to every agent compiled later) turns test 2 red;
AR300AD_MUTATION=noop_append turns tests 1 and 3 red.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    GRANT_KEY,
    REPO_ROOT,
    ability_rows,
    build_package,
    declared_ids,
    installed_skill_ids,
    make_skill,
    named_in_accounts,
    read_prompts,
    real_declarations,
    real_slice,
    source_templates,
    template_frontmatter,
)

INSTALLED = installed_skill_ids(REPO_ROOT)


def _ids(entries) -> set[str]:
    return {e["skill_id"] if isinstance(e, dict) else e for e in entries}


def _first_granted() -> str:
    """A granted agent that is not last in build order (so a leak to 'later'
    agents has somewhere to go)."""
    return sorted(real_declarations())[0]


def _add_grant_text(path: Path, skill_id: str) -> None:
    """Insert ONE item at the end of the template's ``skills:`` list, at text
    level -- nothing else in the file changes."""
    lines = path.read_text(encoding="utf-8").split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.startswith(f"{GRANT_KEY}:"))
    end = start + 1
    while end < len(lines) and (lines[end].startswith("- ") or lines[end].startswith("  ")):
        end += 1
    lines[end:end] = [f"- skill_id: {skill_id}", "  mode: always"]
    path.write_text("\n".join(lines), encoding="utf-8")


def _unused_ability() -> str:
    used = set().union(*(_ids(e) for e in real_declarations().values()))
    spare = sorted(INSTALLED - used)
    assert spare, "no installed ability is unclaimed; cannot isolate a leak"
    return spare[0]


def _baseline(tmp_path: Path, monkeypatch):
    pkg = real_slice(tmp_path / "slice")
    roots_a = build_package(pkg, tmp_path / "out_a", monkeypatch)
    return pkg, roots_a


def test_ability_added_to_one_declaration_appears_in_that_agents_next_compiled_prompt(tmp_path, monkeypatch):
    # covers: AR-300d-2
    # angle: deployed
    """AR-300d-2: one further ability added to ONE agent's declaration and to
    nothing else is named, on the next build, in that agent's compiled prompt in
    both roots, alongside the abilities it already named."""
    target, new = _first_granted(), _unused_ability()
    pkg, roots_a = _baseline(tmp_path, monkeypatch)
    already = _ids(real_declarations()[target])
    assert new not in already
    _add_grant_text(pkg / "templates" / "agents" / f"{target}.md", new)
    assert declared_ids(template_frontmatter(pkg / "templates" / "agents" / f"{target}.md")) == already | {new}
    roots_b = build_package(pkg, tmp_path / "out_b", monkeypatch)
    for root_a, root_b in zip(roots_a, roots_b):
        before = named_in_accounts((root_a / f"{target}.md").read_text(encoding="utf-8"), INSTALLED)
        after = named_in_accounts((root_b / f"{target}.md").read_text(encoding="utf-8"), INSTALLED)
        assert before == already, "control: the baseline did not name the original grant"
        assert after == already | {new}, f"{root_b}: {sorted(after ^ (already | {new}))}"


def test_no_other_agents_compiled_prompt_changed(tmp_path, monkeypatch):
    # covers: AR-300d-2
    # angle: seam
    """AR-300d-2: after the grant, EVERY other compiled prompt in EVERY platform
    root is byte-identical to the build before it -- the ability was not handed
    to everyone through a shared structure. Counted: the number of unchanged
    prompts compared is (agents - 1) x roots, and the edited agent's prompt DID
    change (control)."""
    target, new = _first_granted(), _unused_ability()
    pkg, roots_a = _baseline(tmp_path, monkeypatch)
    _add_grant_text(pkg / "templates" / "agents" / f"{target}.md", new)
    roots_b = build_package(pkg, tmp_path / "out_b", monkeypatch)

    compared, drifted = 0, []
    for root_a, root_b in zip(roots_a, roots_b):
        before, after = read_prompts(root_a), read_prompts(root_b)
        assert set(before) == set(after)
        assert before[target] != after[target], "control: the edited agent's prompt did not change"
        for stem in sorted(before):
            if stem == target:
                continue
            compared += 1
            if before[stem] != after[stem]:
                drifted.append((root_b.parent.name, stem))
    assert compared == (len(source_templates()) - 1) * 2 > 0
    assert not drifted, f"{len(drifted)}/{compared} other prompts changed: {drifted[:5]}"


def test_ability_newly_added_to_the_project_and_granted_in_the_same_edit_arrives(tmp_path, monkeypatch):
    # covers: AR-300d-2
    # angle: boundary
    """AR-300d-2: a BRAND-NEW ability (a skill directory that did not exist at the
    first build), created and granted in one edit, reaches the agent on the next
    build with its own description -- the grantable set is not fixed at an
    earlier moment -- and still no other agent changes."""
    target = _first_granted()
    pkg, roots_a = _baseline(tmp_path, monkeypatch)
    fresh = "zz-fresh-skill"
    assert fresh not in INSTALLED
    purpose = "Fresh skill created in the same edit that grants it"
    make_skill(pkg / "templates" / "skills", fresh, purpose)
    _add_grant_text(pkg / "templates" / "agents" / f"{target}.md", fresh)
    roots_b = build_package(pkg, tmp_path / "out_b", monkeypatch)

    already = _ids(real_declarations()[target])
    for root_a, root_b in zip(roots_a, roots_b):
        text = (root_b / f"{target}.md").read_text(encoding="utf-8")
        assert named_in_accounts(text, INSTALLED | {fresh}) == already | {fresh}
        assert purpose in ability_rows(text, INSTALLED | {fresh})[fresh][0]
        before, after = read_prompts(root_a), read_prompts(root_b)
        assert all(before[s] == after[s] for s in before if s != target)
