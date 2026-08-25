"""
MODULE: test_acs_100i_8_registry_declaration_gate
GOAL: Pin ACS-100i-8 — a package surface cannot come into existence without a
    record that declared it. Adding a NEW entry to a package registry is refused
    at commit time unless at least one cited acceptance criterion carries
    `package_surface: true`.
BUSINESS CONTEXT: This is the criterion that keeps ACS-100i-6's narrowing from
    being a switch-off. The declaration is under the author's control and can
    simply be omitted; the registration is not — a package surface exists because
    an entry appears in a registry the build reads, and that entry cannot be left
    out without failing to ship the feature. CONCESSION 1 on the parent AC:
    detection moves from authoring time to landing time. What survives is the
    guarantee that a surface cannot reach a consumer undeclared.
ARCHITECTURE: Every test drives a throwaway git repository with real `git add`
    and runs the hook as a subprocess with cwd set to that repo, so
    `git rev-parse --show-toplevel` and `git diff --cached` behave as in a real
    commit. Nothing is mocked. The full contract the hook must satisfy — script
    path, invocation, staged-file source, citation source, exit codes, watched
    registries, "new entry" definition — is documented in
    _acs_100i_registry_support's module docstring.

    Currently RED for the strongest possible reason: no such hook exists. The
    harness asserts its absence explicitly rather than letting python's "can't
    open file" exit code masquerade as a refusal.

AC: ACS-100i-8 (docs/acceptance-criteria/ac-store/
    ACS-100-structured-requirements/ACS-100i-8.yaml)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acs_100i_registry_support import (  # noqa: E402
    AGENT_REGISTRY_REL,
    make_repo,
    run_check,
    stage_edited_agent,
    stage_new_agent,
    stage_removed_agent,
    stage_unrelated_edit,
)


def test_registry_addition_is_refused_when_no_cited_record_declares(tmp_path):
    # covers: ACS-100i-8
    """ACS-100i-8 s1: a change adding a new agent-registry entry, citing an AC
    that carries no `package_surface` declaration, must be refused — and the
    refusal must name the registry file, the key of the entry being added, and
    every acceptance criterion the change cited.

    This is the hole the narrowing would otherwise open: the author registers a
    real package surface and never writes the marker.
    """
    repo = make_repo(tmp_path, {"ACS-901": None, "ACS-902": None})
    stage_new_agent(repo, "glossary-triage")

    run = run_check(repo, "feat(agents): add glossary-triage\n\nCloses ACS-901, ACS-902\n")

    assert run.refused, (
        "adding a new package-registry entry with no cited record declaring a "
        f"package surface must be refused; the check exited 0.\n{run.output}"
    )
    assert AGENT_REGISTRY_REL in run.output, (
        f"the refusal must name the registry file {AGENT_REGISTRY_REL}; "
        f"output:\n{run.output}"
    )
    assert "glossary-triage" in run.output, (
        f"the refusal must name the key of the entry being added; output:\n{run.output}"
    )
    for cited in ("ACS-901", "ACS-902"):
        assert cited in run.output, (
            f"the refusal must name every acceptance criterion the change cited; "
            f"{cited} is absent from:\n{run.output}"
        )


def test_registry_addition_is_allowed_when_a_cited_record_declares(tmp_path):
    # covers: ACS-100i-8
    """ACS-100i-8 s2: the same change is allowed when a cited record carries
    `package_surface: true`.

    The anti-over-broadening half: the check must not simply refuse every
    registry addition, or it would be indistinguishable from banning
    registrations outright.
    """
    repo = make_repo(tmp_path, {"ACS-901": True})
    stage_new_agent(repo, "glossary-triage")

    run = run_check(repo, "feat(agents): add glossary-triage\n\nCloses ACS-901\n")

    assert not run.refused, (
        "a registry addition whose cited record declares package_surface: true "
        f"must be allowed; exit={run.returncode}\n{run.output}"
    )


def test_editing_an_existing_registry_entry_needs_no_declaration(tmp_path):
    # covers: ACS-100i-8
    """ACS-100i-8 s3: changing the value of an entry already present in a
    package registry requires no declaration. The obligation attaches to bringing
    a surface into existence, not to maintaining one.

    Discriminating case: a naive implementation that flags any diff touching a
    watched registry passes the first two tests and fails this one.
    """
    repo = make_repo(tmp_path, {"ACS-901": None})
    stage_edited_agent(repo, "research-agent", tier="phase")

    run = run_check(repo, "chore(agents): retier research-agent\n\nRefs ACS-901\n")

    assert not run.refused, (
        "editing an existing registry entry adds no surface and must be "
        f"allowed with no declaration; exit={run.returncode}\n{run.output}"
    )


def test_removing_a_registry_entry_needs_no_declaration(tmp_path):
    # covers: ACS-100i-8
    """ACS-100i-8 s3 (removal half): removing an entry, and adding none, is
    allowed with no declaration required."""
    repo = make_repo(tmp_path, {"ACS-901": None})
    stage_removed_agent(repo, "research-agent")

    run = run_check(repo, "chore(agents): drop research-agent\n\nRefs ACS-901\n")

    assert not run.refused, (
        "removing a registry entry brings no surface into existence and must be "
        f"allowed; exit={run.returncode}\n{run.output}"
    )


def test_change_touching_no_registry_reports_nothing_to_evaluate(tmp_path):
    # covers: ACS-100i-8
    """ACS-100i-8 s4: a change that touches no package registry is allowed, and
    the check must report that it had nothing to evaluate rather than reporting
    a pass.

    Deliberate, per the AC: a check that reports "pass" when it examined nothing
    is the KI-ACS-001 failure mode, and it would make this criterion
    unfalsifiable. Exit 0 is correct here — the output wording is what carries
    the distinction.
    """
    repo = make_repo(tmp_path, {"ACS-901": None})
    stage_unrelated_edit(repo)

    run = run_check(repo, "docs: add a note\n\nRefs ACS-901\n")
    lowered = run.output.lower()

    assert not run.refused, (
        f"a change touching no package registry must be allowed; "
        f"exit={run.returncode}\n{run.output}"
    )
    assert "nothing to evaluate" in lowered, (
        "the check must state that it had nothing to evaluate, so an empty "
        f"examination is distinguishable from a pass; output:\n{run.output}"
    )
    assert "pass" not in lowered and "ok:" not in lowered, (
        "an empty examination must not be reported as a pass; "
        f"output:\n{run.output}"
    )
