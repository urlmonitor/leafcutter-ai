"""AR-400d -- an ability the project supplies is delivered when present, reported and carried on when absent, and is
never confused with a mistyped package grant (composite-closure contract; one real build.py run).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400d.yaml (test_spec).

Test 1 is this parent's one real build (``shared_layout_mutator``, a scratch consumer): both outcomes of a
project-supplied grant in the same install. Test 2 proves the two cases are never confused in either direction
through the real validator CLI on a copy (no build). Test 3 reads the checked-out tree and the shared deployed
layout (``shared_layout_reader``) to prove residue was removed rather than dressed up as project-supplied.

NOT FAITHFUL TO THE LETTER (test 2): the validator CLI prints no "not installed" report -- that report is the
build's (asserted in test 1) -- so for the marked specialist the CLI is asserted to print no refusing line at all.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3b_fixtures as G  # noqa: E402
import _ar400_parent_support as P  # noqa: E402
from template_compiler import parse_frontmatter  # noqa: E402

PROBE = "probe-coder"
SQL_TEST_BODY = "Apply the `sql-test` skill before finishing"
SUPPLIED, TYPO, UNSHIPPED = "probe-supplied", "probe-typo", "ghost-proj"
MARKED_GRANTS = {("sql-coder", "postgres"), ("sql-coder", "sql-test")}


def _lines_naming(out: str, agent: str, ability: str) -> list[str]:
    return [ln.strip() for ln in out.splitlines() if agent in ln and F.names(ln, ability)]


@pytest.mark.shared_layout_mutator
def test_ar_400d_one_build_delivers_present_and_reports_absent_project_ability():
    # covers: AR-400d
    # angle: criterion
    # must_catch: a missing project-supplied ability refuses the install
    # must_catch: a present project-supplied ability is not delivered because it is looked for in the package
    """One real build.py run into a scratch consumer whose .leafcutter/skills holds ability A (postgres) but not B
    (sql-test), from a package copy where one specialist grants both marked as supplied by the project: the build
    exits 0, the compiled prompt offers A (with the PROJECT copy's description) and states B is not installed,
    and the output names B for that specialist exactly once, at neither warning nor error severity, and never
    reports A as missing."""
    sc = G.new_scenario([(PROBE, [G.POSTGRES_BODY, SQL_TEST_BODY], (G.marked("postgres"), G.marked("sql-test")))],
                        {"postgres": G.PROJECT_MARK})
    rc, out = G.build(sc)
    assert rc == 0, out[-1500:]
    about_b = _lines_naming(out, PROBE, "sql-test")
    assert len(about_b) == 1 and re.search(r"not found", about_b[0], re.IGNORECASE), about_b
    assert len(G.info_lines(out, PROBE, "sql-test", r"not found")) == 1 and G.finding_lines(out, PROBE, "sql-test") == []
    assert [ln for ln in _lines_naming(out, PROBE, "postgres") if re.search(r"not found|not installed|missing", ln, re.I)] == []
    prompts = G.compiled(sc.project, PROBE)
    assert len(prompts) >= 2, sorted(prompts)
    for where, text in prompts.items():
        rows = G.ability_rows(text, "postgres")
        assert len(rows) == 1 and G.PROJECT_MARK in rows[0], f"{where}: {rows}"
        assert G.ability_rows(text, "sql-test") == [] and P.not_installed_stated(text, "sql-test"), where


def _plant_marked_and_unmarked(root) -> None:
    body = [f"Apply the `{UNSHIPPED}` skill before writing"]
    F.plant(root, SUPPLIED, body, grants=(G.marked(UNSHIPPED),))
    F.plant(root, TYPO, body, grants=(UNSHIPPED,))


def test_ar_400d_marking_rescues_only_the_marked_grant_of_the_same_id():
    # covers: AR-400d
    # angle: discrimination
    # must_catch: any grant to an unshipped id is treated as project-supplied, so a typo in a package grant is rescued
    # must_catch: the marking is ignored, so the project-supplied grant refuses the build
    """In one package copy two specialists grant the same unshipped ability id, one marked as supplied by the
    project and one unmarked. The validator CLI exits non-zero with exactly one nonexistent-ability finding,
    naming the unmarked specialist, and prints no refusing line for the marked one."""
    rc, out = F.slice_cli(_plant_marked_and_unmarked)
    hits = F.of_kind(out, F.NONEXIST, UNSHIPPED)
    assert len(hits) == 1 and F.names(hits[0], TYPO), f"expected one finding, for {TYPO}: {hits}\n{out[-900:]}"
    refusing = [ln for ln in out.splitlines() if SUPPLIED in ln and (ln.startswith("ERROR") or any(k in ln.lower() for k in F.KINDS))]
    assert refusing == [] and rc != 0, (refusing, rc)
    assert F.findings(out) == hits, "only the mistyped package grant may be reported"


def _mentions(roots: dict[str, dict[str, str]]) -> set[tuple[str, str]]:
    return {(where, agent) for where, prompts in roots.items() for agent, text in prompts.items()
            if "collector-enforcer" in text.lower()}


def _marked_pairs_in_tree() -> set[tuple[str, str]]:
    """Every (specialist, ability) the checked-out definitions mark ``provided_by: project``."""
    out = set()
    for path in sorted((F.REPO_ROOT / "templates" / "agents").glob("*.md")):
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        out |= {(fm["name"], e["skill_id"]) for e in fm.get("skills") or []
                if isinstance(e, dict) and e.get("provided_by") == "project"}
    return out


@pytest.mark.shared_layout_reader
def test_ar_400d_real_tree_marks_only_sql_coder_database_abilities_as_project_supplied(shared_reference_layout):
    # covers: AR-400d
    # angle: real_artifact
    # must_catch: package-specific residue from another project is silenced by marking it as project-supplied instead of being removed
    """Over the checked-out tree and the shared deployed layout: the only grants marked as supplied by the project
    are sql-coder's postgres and sql-test (in the definitions AND in the deployed registry), and no compiled
    specialist prompt, in any platform root, mentions collector-enforcer. Control: the scan sees the two real marks
    and flags a planted mention."""
    assert _marked_pairs_in_tree() == MARKED_GRANTS
    registry = {(r["id"], e["skill_id"]) for r in P.deployed_registry(shared_reference_layout)["agents"]
                for e in r.get("skills_invoked") or [] if isinstance(e, dict) and e.get("provided_by")}
    assert registry == MARKED_GRANTS, registry
    roots = P.prompts_by_root(shared_reference_layout)
    assert len(roots) >= 2 and all(len(p) == len(P.definitions()) for p in roots.values()), sorted(roots)
    assert _mentions(roots) == set(), sorted(_mentions(roots))
    planted = {"planted-root": {"probe": "Run the collector-enforcer skill.", "other": "Nothing to see."}}
    assert _mentions(planted) == {("planted-root", "probe")}, "control: the scan must flag a planted mention"
