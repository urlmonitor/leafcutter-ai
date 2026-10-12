"""AR-300d-3-i -- revoking an agent's LAST ability leaves NO empty section behind,
and the result is the SAME state as an agent never granted anything (one shared
emit/omit decision), whether the key is left empty or deleted.

Source of truth: .../AR-300d-3-i.yaml. Evidence = compiled prompts of real
``build_agents`` runs over a planted package, rebuilt INTO the directory that held
the granted prompt (stale tree). Revoked and never-granted agents share the same
``name`` and body so a byte-for-byte comparison is a real equivalence test, not
two absence checks.

GREEN-ALREADY (all three): slice 1 normalises absent / empty / null to the same
"no section" value before the emit/omit decision. Mutation proofs:
AR300AD_MUTATION=empty_list_heading (an explicit empty list emits a bare heading)
turns tests 1, 2 (empty-key leg) and 3 red; AR300AD_MUTATION=accumulate turns
tests 1 and 2 red.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    abilities_heading_lines,
    accounts,
    agent_fm,
    build_package,
    compile_with,
    make_skill,
    named_in_accounts,
    planted_package,
    write_template,
)

SKILLS = {"zz-alpha": "Alpha skill forges alpha widgets on request"}
KNOWN = set(SKILLS)
BODY = "# Agent\n\nDo the work.\n"
SAME_NAME = "zz-agent"
ONE = [{"skill_id": "zz-alpha", "mode": "always"}]


def _fm(skills_state: str) -> dict:
    """Same name every time; only the declaration state differs."""
    fm = agent_fm(SAME_NAME, ONE if skills_state == "granted" else None)
    if skills_state == "empty":
        fm["skills"] = []
    return fm


def _package(tmp_path: Path):
    templates = {
        "zz-revoked-empty": (_fm("granted"), BODY),
        "zz-revoked-deleted": (_fm("granted"), BODY),
        "zz-never": (_fm("never"), BODY),
    }
    return planted_package(tmp_path / "slice", templates, SKILLS)


def _revoke(pkg: Path) -> None:
    """Revoke the one ability two ways: key left present-but-empty, key deleted."""
    agents = pkg / "templates" / "agents"
    write_template(agents / "zz-revoked-empty.md", _fm("empty"), BODY)
    write_template(agents / "zz-revoked-deleted.md", _fm("never"), BODY)


def test_revoking_the_last_ability_leaves_no_abilities_section(tmp_path, monkeypatch):
    # covers: AR-300d-3-i
    # angle: boundary
    """AR-300d-3-i: an agent granted exactly one ability, then revoked, compiles
    (over the stale tree that held the granted prompt) to a prompt with no
    abilities heading, no account and no heading followed by an empty list --
    for the present-but-empty AND the deleted-key revocation. Control: before the
    revocation the one ability WAS named, in both roots."""
    pkg = _package(tmp_path)
    out = tmp_path / "out"
    roots = build_package(pkg, out, monkeypatch)
    for root in roots:
        for stem in ("zz-revoked-empty", "zz-revoked-deleted"):
            text = (root / f"{stem}.md").read_text(encoding="utf-8")
            assert named_in_accounts(text, KNOWN) == {"zz-alpha"}, "control: grant not delivered first"
    _revoke(pkg)
    roots = build_package(pkg, out, monkeypatch)
    for root in roots:
        for stem in ("zz-revoked-empty", "zz-revoked-deleted"):
            text = (root / f"{stem}.md").read_text(encoding="utf-8")
            assert abilities_heading_lines(text) == [], f"bare heading left behind in {root}/{stem}"
            assert accounts(text, KNOWN) == []
            assert "zz-alpha" not in text and "Available Skills" not in text


def test_revoked_agent_prompt_matches_a_never_granted_agent_prompt(tmp_path, monkeypatch):
    # covers: AR-300d-3-i
    # angle: deployed
    """AR-300d-3-i: the revoked agent's compiled prompt is BYTE-IDENTICAL to that
    of an agent that was never granted anything (same name, same body) -- the same
    state, not merely two states that both lack a heading -- in both roots and
    for both revocation shapes."""
    pkg = _package(tmp_path)
    out = tmp_path / "out"
    build_package(pkg, out, monkeypatch)
    _revoke(pkg)
    roots = build_package(pkg, out, monkeypatch)
    compared = 0
    for root in roots:
        never = (root / "zz-never.md").read_text(encoding="utf-8")
        assert SAME_NAME in never and "Do the work." in never, "control: the never-granted prompt is a real prompt"
        for stem in ("zz-revoked-empty", "zz-revoked-deleted"):
            compared += 1
            assert (root / f"{stem}.md").read_text(encoding="utf-8") == never, f"{stem} differs from never-granted in {root}"
    assert compared == 4


def test_emptied_key_and_deleted_key_produce_the_same_result(tmp_path):
    # covers: AR-300d-3-i
    # angle: boundary
    """AR-300d-3-i: leaving the declaration key present-but-empty (``[]`` or a bare
    null) and deleting it entirely both reach the omit branch identically -- the
    compiled bytes are equal. Control: the granted form differs and has a
    heading (so equality is not 'the compiler ignores the key')."""
    skills_root = tmp_path / "skills"
    for sid, desc in SKILLS.items():
        make_skill(skills_root, sid, desc)

    def compiled(label: str, fm: dict) -> str:
        tpl = write_template(tmp_path / label / "zz-agent.md", fm, BODY)
        return compile_with(tpl, agents=None, skills_root=skills_root)

    empty = compiled("empty", _fm("empty"))
    null = compiled("null", {**_fm("never"), "skills": None})
    deleted = compiled("deleted", _fm("never"))
    granted = compiled("granted", _fm("granted"))
    assert empty == null == deleted
    assert abilities_heading_lines(empty) == []
    assert granted != deleted and len(abilities_heading_lines(granted)) == 1
