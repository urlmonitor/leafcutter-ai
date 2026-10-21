"""AR-400a-3 / a-3-ii / b-3 / b-3-i..iv / c-2 -- the package's OWN tree passes the rewritten reference
gate on its first build, and each template fix is what made its finding go away (TDD red phase).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400a-3.yaml, AR-400a-3-ii.yaml, AR-400b-3.yaml, AR-400b-3-{i,ii,iii,iv}.yaml, AR-400c-2.yaml.
The compiled-prompt halves of these ACs already live in test_ar_400a_3_template_refs.py,
test_ar_400b_3_template_refs.py and test_ar_400c_2_3_cleanup.py; this file holds the validator halves.

Every test drives the REAL validator CLI over (a) the checked-out package and (b) a COPY of it with
exactly one fix reverted or one fault planted. Real-tree passes are only evidence because the paired
copy proves the gate fails when the thing is put back (the revert / control rows).

Real-tree assertions allow NO exceptions: sql-coder's postgres and sql-test must be cleared too, by
AR-400d-1-i marking them ``provided_by: project`` (the gate reports no finding for a marked grant).
"""

from __future__ import annotations

import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402

# instance -> (fault kinds accepted for the reverted copy, ability text, finding names the subject)
INSTANCES = {
    "research-agent": ((F.UNGRANTED,), "knowledge-query"),
    "python-coder": ((F.NONEXIST, F.CASE), "sign-off"),
    "architecture-diagram-author": ((F.CASE,), "Write-C4-Diagram"),
    "sql-coder": ((F.AGENT,), "sql-query"),
}
RETIRED = ("find-context-candle", "import-scanner", "trade-analysis", "route-learning")


def _kind_hits(out: str, kinds: tuple[str, ...], ability: str, subject: str) -> list[str]:
    return [h for k in kinds for h in F.of_kind(out, k, ability, subject)]


def test_real_tree_reports_zero_nonexistent_findings_with_full_counts():
    # covers: AR-400a-3
    # angle: real_artifact
    """The validator over the checked-out package reports no 'ability does not exist' finding, no retired id (find-context-candle, import-scanner, trade-analysis, route-learning)
    as an instruction, and its examined counts equal the definitions/guides present. Control row: a
    probe told in plain prose to 'Load the `route-learning` skill' IS reported, so the real tree's
    silence is the gate looking, not the gate absent."""
    rc, out = F.real_cli()
    assert F.of_kind(out, F.NONEXIST) == [], F.of_kind(out, F.NONEXIST)
    for retired in RETIRED:
        assert [f for f in F.findings(out) if F.names(f, retired)] == [], f"{retired} still an instruction"
    defs, guides = H.expected_counts(F.REPO_ROOT)
    assert defs in H.reported(out, "definition") and guides in H.reported(out, "guide"), (defs, guides, out[-600:])
    _, ctl = F.slice_cli(lambda root: F.plant(root, "probe-agent", ["Load the `route-learning` skill and apply it."]))
    assert len(F.of_kind(ctl, F.NONEXIST, "route-learning", "probe-agent")) == 1, (
        f"prose-form dangling instruction not reported: {ctl[-800:]}")
    assert rc == (1 if F.findings(out) else 0), "exit code disagrees with the findings printed"


def test_reintroducing_a_dangling_instruction_into_a_copy_fails():
    # covers: AR-400a-3
    # angle: discrimination
    """Negative control: in a copy of the real tree, restore the 'Load `.claude/skills/route-learning/
    SKILL.md`' line in templates/skills/README.md; the validator fails naming that guide."""
    def revert(root):
        F.swap(root / "templates" / "skills" / "README.md", "Load `.claude/skills/route-knowledge/SKILL.md`",
               "Load `.claude/skills/route-learning/SKILL.md`")

    rc, out = F.slice_cli(revert)
    hits = F.of_kind(out, F.NONEXIST, "route-learning", "templates/skills/README.md")
    assert len(hits) == 1, f"the guide was not named: {out[-1200:]}"
    assert rc == 1, out[-800:]


def test_validator_reports_no_ability_finding_for_retrospective_agent():
    # covers: AR-400a-3-ii
    # angle: real_artifact
    """The validator over the real tree reports neither 'does not exist' nor 'not granted' for
    retrospective-agent; removing ONLY the new route-knowledge grant from a copy produces a 'not
    granted' finding (the Skill tool stays, so it is the grant that is missing)."""
    _, out = F.real_cli()
    assert F.about(out, "retrospective-agent") == [], F.about(out, "retrospective-agent")
    rc, reverted = F.slice_cli(lambda root: F.drop_grant(root, "retrospective-agent", "route-knowledge"))
    hits = F.of_kind(reverted, F.UNGRANTED, "route-knowledge", "retrospective-agent")
    assert len(hits) >= 1, f"removing the grant produced no 'not granted' finding: {reverted[-1200:]}"
    assert rc == 1, reverted[-800:]


def test_real_tree_has_zero_ungranted_case_or_agent_findings():
    # covers: AR-400b-3
    # angle: real_artifact
    """The validator over the checked-out package reports zero 'not granted', 'differs only in case'
    and 'names an agent' findings, with definitions examined equal to the definitions present.
    Control row: a copy holding one planted instance of each of the three kinds reports all three."""
    rc, out = F.real_cli()
    for kind in (F.UNGRANTED, F.CASE, F.AGENT):
        assert F.of_kind(out, kind) == [], f"real tree has '{kind}' findings: {F.of_kind(out, kind)}"
    defs, _guides = H.expected_counts(F.REPO_ROOT)
    assert defs in H.reported(out, "definition"), (defs, out[-600:])

    def plant_three(root):
        F.plant(root, "probe-ug", ["Load the `knowledge-query` skill first."])
        F.plant(root, "probe-case", ["Step 1 -- Load the Write-C4-Diagram Skill"])
        F.plant(root, "probe-ag", ["Use the `sql-query` skill if available to scaffold the object"])

    _, ctl = F.slice_cli(plant_three)
    for kind, who in ((F.UNGRANTED, "probe-ug"), (F.CASE, "probe-case"), (F.AGENT, "probe-ag")):
        assert len(F.of_kind(ctl, kind, subject=who)) == 1, f"control: '{kind}' not reported for {who}: {ctl[-1200:]}"
    assert rc == (1 if F.findings(out) else 0)


def test_reverting_each_instance_fix_reproduces_its_finding():
    # covers: AR-400b-3
    # angle: discrimination
    # must_catch: a finding was cleared by loosening the recognition rule instead of fixing the template
    """For each of research-agent, python-coder, architecture-diagram-author and sql-coder, a copy of
    the real tree with ONLY that instance's fix undone fails with the expected kind for that
    specialist -- so the template edit, not a looser recognition rule, is what cleared it."""
    missing = []
    for instance, (kinds, ability) in INSTANCES.items():
        if not _kind_hits(F.reverted_cli(instance), kinds, ability, instance):
            missing.append((instance, kinds, ability))
    assert not missing, f"reverting these fixes did not reproduce their finding: {missing}"


def test_validator_has_no_not_granted_finding_for_research_agent():
    # covers: AR-400b-3-i
    # angle: real_artifact
    """Real tree: no 'not granted' finding for research-agent. Revert control: dropping only the
    knowledge-query grant from a copy yields exactly that finding."""
    assert F.of_kind(F.real_cli()[1], F.UNGRANTED, subject="research-agent") == []
    assert len(F.of_kind(F.reverted_cli("research-agent"), F.UNGRANTED, "knowledge-query", "research-agent")) == 1


def test_validator_has_no_finding_for_python_coder_signoff():
    # covers: AR-400b-3-ii
    # angle: real_artifact
    """Real tree: no finding for python-coder about sign-off or signoff. Revert control: restoring
    'Resolve and load the sign-off skill' in a copy fails with 'ability does not exist' (or 'differs
    only in case') for sign-off."""
    mine = [f for f in F.about(F.real_cli()[1], "python-coder") if F.names(f, "sign-off") or F.names(f, "signoff")]
    assert mine == [], mine
    assert len(_kind_hits(F.reverted_cli("python-coder"), (F.NONEXIST, F.CASE), "sign-off", "python-coder")) == 1


def test_validator_has_no_case_finding_for_diagram_author():
    # covers: AR-400b-3-iii
    # angle: real_artifact
    """Real tree: no 'differs only in case' finding for architecture-diagram-author. Revert control:
    restoring the 'Load the Write-C4-Diagram Skill' heading in a copy produces one."""
    assert F.of_kind(F.real_cli()[1], F.CASE, subject="architecture-diagram-author") == []
    assert len(F.of_kind(F.reverted_cli("architecture-diagram-author"), F.CASE, "Write-C4-Diagram",
                         "architecture-diagram-author")) == 1


def test_validator_has_no_names_an_agent_finding_for_sql_coder():
    # covers: AR-400b-3-iv
    # angle: real_artifact
    # must_catch: sql-query is removed from spawn_allowlist instead of the sentence being rewritten
    """Real tree: no 'names an agent' finding for sql-coder AND sql-query is still in its own
    spawn_allowlist (the over-correction of deleting the permission). Revert control: restoring the
    'sql-query skill if available' sentence in a copy produces the finding."""
    assert F.of_kind(F.real_cli()[1], F.AGENT, subject="sql-coder") == []
    text = (F.REPO_ROOT / "templates" / "agents" / "sql-coder.md").read_text(encoding="utf-8")
    head = yaml.safe_load(text[3:text.find("\n---", 3)])
    assert "sql-query" in head["spawn_allowlist"], "sql-query was dropped from sql-coder's hand-off list"
    assert len(F.of_kind(F.reverted_cli("sql-coder"), F.AGENT, "sql-query", "sql-coder")) == 1


def test_product_owner_citation_is_exempt_from_the_grant_check_through_the_validator():
    # covers: AR-400c-2
    # angle: criterion
    """product-owner no longer grants signoff but still cites signoff's SKILL.md as the event-shape
    source: the validator over the real tree reports no finding for it (a citation is exempt from the
    grant check). Control: rewriting that citation in a copy as 'Load `templates/skills/signoff/
    SKILL.md` and follow ...' IS 'not granted' for product-owner / signoff, so the exemption is what
    keeps the real tree clean."""
    assert F.about(F.real_cli()[1], "product-owner") == []

    def rewrite(root):
        F.swap(root / "templates" / "agents" / "product-owner.md",
               "defined in `templates/skills/signoff/SKILL.md` §7 step 2 (deployed:",
               "Load `templates/skills/signoff/SKILL.md` and follow §7 step 2 (deployed:")

    rc, out = F.slice_cli(rewrite)
    assert len(F.of_kind(out, F.UNGRANTED, "signoff", "product-owner")) == 1, out[-1200:]
    assert rc == 1, out[-800:]

