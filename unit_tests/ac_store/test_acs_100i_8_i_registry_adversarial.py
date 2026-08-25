"""
MODULE: test_acs_100i_8_i_registry_adversarial
GOAL: Pin ACS-100i-8-i — the three adversarial readings of the registration
    check: a cited record that DENIES the surface, a change that cites nothing
    at all, and a multi-AC change where only one of the cited records declares.
BUSINESS CONTEXT:
    s1 — omission and denial must both be refused, but they are different acts
    and the message must say which one it saw. An omission is an oversight; a
    `package_surface: false` on a change that adds a registration is a
    contradiction between the record and the change, and a reviewer needs to
    read it as one.
    s2 — the uncited-change hole (CONCESSION 2 on ACS-100i-8), closed rather
    than merely documented. Note the blast radius: every package-registry edit
    made outside the AC path stops working. That is consistent with the standing
    project rule that new work goes through acceptance criteria, and an uncited
    change is precisely how an undeclared surface would arrive.
    s3 — stops the check being over-strict in the ordinary multi-AC case, where
    one behavioural AC declares the surface and its siblings do not.
ARCHITECTURE: Same real-git harness as ACS-100i-8; see
    _acs_100i_registry_support's module docstring for the full hook contract.
    Currently RED because the hook does not exist.

AC: ACS-100i-8-i (docs/acceptance-criteria/ac-store/
    ACS-100-structured-requirements/ACS-100i-8-i.yaml)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acs_100i_registry_support import (  # noqa: E402
    AGENT_REGISTRY_REL,
    make_repo,
    run_check,
    stage_new_agent,
)


def test_cited_record_denying_the_surface_is_reported_as_a_contradiction(tmp_path):
    # covers: ACS-100i-8-i
    """ACS-100i-8-i s1: when the only cited record carries
    `package_surface: false` and the change adds a registry entry, the change is
    refused, and the refusal states that the cited record DENIES registering a
    package surface while the change adds one — naming both the record and the
    entry.

    Discriminating case: an implementation that treats `false` and "absent"
    identically still refuses, so it passes a naive "is it refused?" test. It
    fails here, because the message must distinguish a contradiction from a
    missing field.
    """
    repo = make_repo(tmp_path, {"ACS-901": False})
    stage_new_agent(repo, "glossary-triage")

    run = run_check(repo, "feat(agents): add glossary-triage\n\nCloses ACS-901\n")
    lowered = run.output.lower()

    assert run.refused, (
        "a registry addition cited only to a record that denies the surface "
        f"must be refused; exit={run.returncode}\n{run.output}"
    )
    assert "ACS-901" in run.output and "glossary-triage" in run.output, (
        "the refusal must name both the record and the entry; "
        f"output:\n{run.output}"
    )
    assert "denies" in lowered or "contradict" in lowered, (
        "the refusal must report a contradiction between the record and the "
        "change, not a missing field — an incorrect declaration and an omitted "
        f"one are different acts. Output:\n{run.output}"
    )
    assert "missing" not in lowered, (
        "the record is not missing a declaration; it made one and it says "
        f"false. Reporting it as missing misleads the reviewer. Output:\n{run.output}"
    )


def test_registry_addition_citing_no_acceptance_criterion_is_refused(tmp_path):
    # covers: ACS-100i-8-i
    """ACS-100i-8-i s2: a change that adds a new registry entry and cites no
    acceptance criterion at all must be refused, the refusal must state that
    such a change has to cite the AC that declares it, and it must name the
    registry file and the entry key.

    This closes the hole the parent AC records as CONCESSION 2: the check can
    only reconcile against criteria a change cites, so an uncited change would
    otherwise be the free path for an undeclared surface.
    """
    repo = make_repo(tmp_path, {"ACS-901": True})
    stage_new_agent(repo, "glossary-triage")

    run = run_check(repo, "feat(agents): add glossary-triage\n")

    assert run.refused, (
        "a registry addition citing no acceptance criterion must be refused — "
        "otherwise citing nothing is the way around the gate; "
        f"exit={run.returncode}\n{run.output}"
    )
    assert AGENT_REGISTRY_REL in run.output and "glossary-triage" in run.output, (
        "the refusal must name the registry file and the entry key; "
        f"output:\n{run.output}"
    )
    assert "cite" in run.output.lower(), (
        "the refusal must state that a change adding a package-registry entry "
        f"must cite the acceptance criterion that declares it; output:\n{run.output}"
    )


def test_one_declaring_record_among_several_cited_is_sufficient(tmp_path):
    # covers: ACS-100i-8-i
    """ACS-100i-8-i s3: a change citing three acceptance criteria, exactly one of
    which carries `package_surface: true`, is allowed — and the two records that
    made no declaration are not reported.

    Discriminating case: an implementation that requires EVERY cited record to
    declare passes both refusal tests above and fails here. This is the ordinary
    multi-AC shape, where one behavioural AC declares the surface and its
    siblings do not.
    """
    repo = make_repo(tmp_path, {"ACS-901": None, "ACS-902": True, "ACS-903": False})
    stage_new_agent(repo, "glossary-triage")

    run = run_check(
        repo,
        "feat(agents): add glossary-triage\n\nCloses ACS-901, ACS-902 and ACS-903\n",
    )

    assert not run.refused, (
        "one declaring record among the cited set is sufficient; "
        f"exit={run.returncode}\n{run.output}"
    )
    assert "ACS-901" not in run.output, (
        "a cited record that made no declaration must not be reported when "
        f"another cited record declared the surface; output:\n{run.output}"
    )
    assert "ACS-903" not in run.output, (
        "a cited sibling carrying package_surface: false must not be reported "
        "as a problem when another cited record declared the surface — one "
        f"declaring record suffices; output:\n{run.output}"
    )
