"""AR-300d-3 -- a revoked ability stops appearing in the agent's prompt on the
next build: derived afresh (also over a STALE compiled tree), no trace anywhere
in the prompt, per agent not per ability, and the derived registry copy follows.

Source of truth: .../AR-300d-3.yaml. Fixture package: planted agents + fixture
skills (frontmatter by yaml.safe_dump), built with the REAL ``build_agents``
phase in-process; revocation = rewriting ONE template's declaration.

  zz-holder-a  grants alpha, beta, gamma  -> beta is revoked from THIS agent only
  zz-holder-b  grants beta                -> must still name beta
  zz-holder-c  grants beta, gamma         -> must still name beta
  zz-plain     grants nothing             -> must stay byte-identical

GREEN-ALREADY: tests 1-4 (slice 1 derives the section afresh from frontmatter).
Mutation proof: AR300AD_MUTATION=accumulate (a section remembers abilities from
earlier builds) turns tests 1, 2 and 4 red.
RED: test 5 -- no mechanism regenerates the registry's derived copy from the
declarations (the migration tool is registry->declaration only); see the note in
that test. This is flagged to the caller as a contract decision.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    agent_fm,
    build_package,
    named_in_accounts,
    planted_package,
    read_prompts,
    write_template,
)

SKILLS = {
    "zz-alpha": "Alpha skill forges alpha widgets on request",
    "zz-beta": "Beta skill audits beta ledgers before release",
    "zz-gamma": "Gamma skill reconciles gamma queues nightly",
}
BODY = "# Agent\n\nDo the work.\n"


def _g(*ids: str) -> list[dict]:
    return [{"skill_id": i, "mode": "always"} for i in ids]


TEMPLATES = {
    "zz-holder-a": (agent_fm("zz-holder-a", _g("zz-alpha", "zz-beta", "zz-gamma")), BODY),
    "zz-holder-b": (agent_fm("zz-holder-b", _g("zz-beta")), BODY),
    "zz-holder-c": (agent_fm("zz-holder-c", _g("zz-beta", "zz-gamma")), BODY),
    "zz-plain": (agent_fm("zz-plain"), BODY),
}


def _revoke_beta_from_a(pkg: Path) -> None:
    write_template(pkg / "templates" / "agents" / "zz-holder-a.md",
                   agent_fm("zz-holder-a", _g("zz-alpha", "zz-gamma")), BODY)


def _built(tmp_path: Path, monkeypatch):
    pkg = planted_package(tmp_path / "slice", TEMPLATES, SKILLS)
    out = tmp_path / "out"
    roots = build_package(pkg, out, monkeypatch)
    return pkg, out, roots


def test_revoked_ability_disappears_from_the_agents_next_compiled_prompt(tmp_path, monkeypatch):
    # covers: AR-300d-3
    # angle: deployed
    """AR-300d-3: one of three granted abilities removed from the declaration
    (and nothing else) leaves the next compiled prompt naming the remaining two
    and not the removed one, in both roots. Control: before the revocation all
    three were named."""
    pkg, out, roots = _built(tmp_path, monkeypatch)
    known = set(SKILLS)
    for root in roots:
        assert named_in_accounts((root / "zz-holder-a.md").read_text(encoding="utf-8"), known) == set(SKILLS)
    _revoke_beta_from_a(pkg)
    roots = build_package(pkg, out, monkeypatch)
    for root in roots:
        text = (root / "zz-holder-a.md").read_text(encoding="utf-8")
        assert named_in_accounts(text, known) == {"zz-alpha", "zz-gamma"}


def test_no_trace_of_the_removed_ability_survives_anywhere_in_the_prompt(tmp_path, monkeypatch):
    # covers: AR-300d-3
    # angle: real_artifact
    """AR-300d-3: the removed ability's name appears NOWHERE in the whole compiled
    prompt (not merely nowhere in the abilities section) -- a summary line, a
    second block or a stale row would all still tell the agent it holds it.
    Control: the same prompt DID contain the name before the revocation."""
    pkg, out, roots = _built(tmp_path, monkeypatch)
    for root in roots:
        assert (root / "zz-holder-a.md").read_text(encoding="utf-8").count("zz-beta") >= 1, "control"
    _revoke_beta_from_a(pkg)
    roots = build_package(pkg, out, monkeypatch)
    for root in roots:
        text = (root / "zz-holder-a.md").read_text(encoding="utf-8")
        assert "zz-beta" not in text.lower(), f"trace of the revoked ability in {root}"


def test_other_agents_granted_the_same_ability_still_name_it(tmp_path, monkeypatch):
    # covers: AR-300d-3
    # angle: boundary
    """AR-300d-3: revocation is PER AGENT -- the other holders of the ability still
    name it and every other prompt (holders and the ungranted agent) is
    byte-identical to the build before. Wrong version caught: removing the
    ability from a shared structure."""
    pkg, out, roots = _built(tmp_path, monkeypatch)
    before = {r: read_prompts(r) for r in roots}
    _revoke_beta_from_a(pkg)
    roots = build_package(pkg, out, monkeypatch)
    compared = 0
    for root in roots:
        after = read_prompts(root)
        for stem in ("zz-holder-b", "zz-holder-c", "zz-plain"):
            compared += 1
            assert after[stem] == before[root][stem], f"{stem} changed in {root}"
        for stem in ("zz-holder-b", "zz-holder-c"):
            assert "zz-beta" in named_in_accounts(after[stem], set(SKILLS))
    assert compared == 6


def test_revocation_holds_when_rebuilding_over_a_stale_compiled_tree(tmp_path, monkeypatch):
    # covers: AR-300d-3
    # angle: deployed
    """AR-300d-3: rebuilding INTO the directory that already holds the previous
    compiled prompts (the gitignored tree persists across builds) still removes
    the revoked ability; the section is derived afresh, not patched. A THIRD
    rebuild with nothing changed is byte-stable (no accumulation)."""
    pkg, out, roots = _built(tmp_path, monkeypatch)
    stale = {r: (r / "zz-holder-a.md").read_text(encoding="utf-8") for r in roots}
    assert all("zz-beta" in t for t in stale.values()), "control: stale tree holds the old grant"
    _revoke_beta_from_a(pkg)
    build_package(pkg, out, monkeypatch)
    after_revoke = {r: (r / "zz-holder-a.md").read_text(encoding="utf-8") for r in roots}
    for text in after_revoke.values():
        assert "zz-beta" not in text and named_in_accounts(text, set(SKILLS)) == {"zz-alpha", "zz-gamma"}
    build_package(pkg, out, monkeypatch, allow_unchanged=True)
    assert {r: (r / "zz-holder-a.md").read_text(encoding="utf-8") for r in roots} == after_revoke


def test_derived_registry_copy_follows_the_revocation(tmp_path, monkeypatch, capsys):
    # covers: AR-300d-3
    # angle: seam
    """AR-300d-3 (registry seam, user decision 2026-10-09): the BUILD never writes the
    package source tree and never refuses over a stale registry copy. After
    revoking zz-beta from zz-holder-a's declaration only: the build continues
    (exit 0); its output REPORTS the divergence naming zz-holder-a and zz-beta and
    not zz-holder-b; the compiled prompt names the declaration; and
    config/agent_registry.json is BYTE-IDENTICAL before and after. Wrong versions
    caught: a build that refuses on a stale copy (a second edit becomes mandatory),
    one that silently rewrites the registry, one that stays silent.

    The copy FOLLOWING the revocation is the pre-commit transform hook's job and is
    covered by that hook's own tests (slice 1), not here; a stale copy in this test
    is deliberate, not a bug."""
    from agent_ability_gate import ability_errors
    import build_main_helpers
    from argparse import Namespace

    base = {"zz-holder-a": TEMPLATES["zz-holder-a"], "zz-holder-b": TEMPLATES["zz-holder-b"]}
    records = [
        {"id": stem, "template_path": f"templates/agents/{stem}.md", "skills_used": [],
         "skills_invoked": [dict(g) for g in fm["skills"]]}
        for stem, (fm, _b) in base.items()
    ]
    pkg = planted_package(tmp_path / "pkg_root", base, SKILLS, registry_agents=records)
    config = {"output_root": ".leafcutter"}
    assert ability_errors(pkg, config) == [], "control: planted package must start consistent"

    _revoke_beta_from_a(pkg)
    diverged = ability_errors(pkg, config)
    assert diverged and any("zz-holder-a" in e for e in diverged), "control: revocation alone must diverge the copy"

    reg_path = pkg / "config" / "agent_registry.json"
    registry_before = reg_path.read_bytes()

    # The build's own guard stage (the one build.py main() runs before compiling).
    # None means "carry on building"; an int is an early exit code.
    rc = build_main_helpers._run_validation_guards(
        config, pkg, Namespace(dry_run=False, validate_only=False), lambda *a, **k: 0, ())
    out = capsys.readouterr()
    reported = out.out + out.err
    assert "zz-holder-a" in reported and "zz-beta" in reported, f"divergence not reported: {reported!r}"
    assert "zz-holder-b" not in reported, "an agent that did not diverge was reported"
    assert rc is None, f"build stopped (exit {rc}) over a stale registry copy; it must report and continue"

    roots = build_package(pkg, tmp_path / "out", monkeypatch, allow_unchanged=True)
    for root in roots:
        text = (root / "zz-holder-a.md").read_text(encoding="utf-8")
        assert named_in_accounts(text, set(SKILLS)) == {"zz-alpha", "zz-gamma"}
        assert "zz-beta" not in text
    assert reg_path.read_bytes() == registry_before, "the build wrote to the package source tree"
