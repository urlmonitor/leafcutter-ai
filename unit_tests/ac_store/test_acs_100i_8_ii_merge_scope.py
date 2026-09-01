"""
MODULE: test_acs_100i_8_ii_merge_scope
GOAL: Pin the KI-BP-20260901-0812 fix — the ACS-100i-8 package-surface
    declaration gate must scope "new entry" to what a commit itself introduces
    relative to EVERY parent, not merely to HEAD, so a merge that only carries
    an already-declared upstream registration is not treated as a fresh one.
BUSINESS CONTEXT: The gate correctly refuses an undeclared package-surface
    registration. Before this fix it computed "new" as "in the staged tree,
    absent from HEAD" — which is right for an ordinary commit (one parent) but
    wrong for a merge commit (two parents): HEAD names only the parent being
    merged INTO, so an entry the OTHER parent (``MERGE_HEAD``) already
    registered reads as "new" purely because it is new to HEAD's history, even
    though it is not new to the repository. Every branch merging `origin/main`
    after `check-ticket-signoff-parity` landed there hit exactly this refusal.
    The fix must not weaken the gate: a merge that introduces a genuinely new,
    undeclared entry — present in NEITHER parent — must still be refused. That
    negative control is the point of this file, not an afterthought.

    OCTOPUS COVERAGE: the first fix pass detected a merge via `git rev-parse
    -q --verify MERGE_HEAD`, which resolves only the FIRST line of
    `MERGE_HEAD`. A real octopus merge (three or more parents) writes one line
    per named branch, so that probe silently dropped every parent after the
    first — an entry genuinely carried by the THIRD parent was still refused.
    `test_octopus_merge_carrying_entry_on_third_parent_only_needs_no_citation`
    and its negative-control sibling pin the fix (reading `MERGE_HEAD` off
    disk in full) against a real three-way merge.
ARCHITECTURE: Same real-git, subprocess-invoked harness as
    test_acs_100i_8_registry_declaration_gate.py (nothing mocked). The merge
    scenarios are built with an actual diverged two-branch (or, for the
    octopus cases, three-way) history and `git merge --no-commit`, so
    `MERGE_HEAD` is genuinely present when the hook runs — the same state a
    real `commit-msg` hook observes mid-merge.
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
    merge_head_line_count,
    run_check,
    stage_merge_carrying_new_agent,
    stage_merge_with_edited_agent,
    stage_merge_with_genuinely_new_agent,
    stage_new_agent,
    stage_octopus_merge_carrying_third_parent_only,
    stage_octopus_merge_with_genuinely_new_agent,
)


def test_merge_carrying_already_declared_entry_needs_no_citation(tmp_path):
    # covers: ACS-100i-8-ii
    """KI-BP-20260901-0812 regression: a merge that only brings in an entry the
    OTHER parent already registered must be allowed with no citation at all.

    The entry is "new" relative to HEAD (the branch being merged into) but is
    already present in MERGE_HEAD (the branch being merged in) — it was
    registered by an earlier commit on that branch, not by this merge. The
    fixed gate must recognise it as carried, not introduced.
    """
    repo = make_repo(tmp_path, {"ACS-901": None})
    stage_merge_carrying_new_agent(repo, "check-ticket-signoff-parity")

    run = run_check(repo, "Merge base into feature-branch\n")

    assert not run.refused, (
        "a merge carrying an entry already registered by the branch being "
        f"merged in must be allowed with no citation; exit={run.returncode}\n"
        f"{run.output}"
    )


def test_merge_introducing_a_genuinely_new_entry_is_still_refused(tmp_path):
    # covers: ACS-100i-8-ii
    """Negative control: merge-scoping must not become a way to smuggle a real,
    undeclared registration through.

    The merge carries `check-ticket-signoff-parity` (present on the base
    branch, must pass free) AND separately stages `brand-new-surface` — an
    entry absent from BOTH parents, added only while the merge is in progress.
    That second entry has no declaring citation and must still block the
    commit. If this test goes green together with the regression test above
    for the wrong reason (e.g. the fix stopped checking merges at all), this
    is the one that catches it.
    """
    repo = make_repo(tmp_path, {"ACS-901": None})
    stage_merge_with_genuinely_new_agent(
        repo, "check-ticket-signoff-parity", "brand-new-surface"
    )

    run = run_check(repo, "Merge base into feature-branch\n\nRefs ACS-901\n")

    assert run.refused, (
        "a merge that introduces an entry absent from BOTH parents must still "
        f"be refused even though it also carries an already-declared entry; "
        f"exit={run.returncode}\n{run.output}"
    )
    assert "brand-new-surface" in run.output, (
        f"the refusal must name the genuinely new entry; output:\n{run.output}"
    )
    assert AGENT_REGISTRY_REL in run.output, (
        f"the refusal must name the registry file; output:\n{run.output}"
    )


def test_ordinary_single_parent_commit_behaviour_is_unchanged(tmp_path):
    # covers: ACS-100i-8-ii
    """Control: an ordinary, non-merge commit that adds a new entry WITH a
    proper declaring citation must still be allowed, exactly as before the fix.

    Pins that merge-scoping is additive — it only widens the parent set when a
    merge is actually in progress (`MERGE_HEAD` resolves) — and does not alter
    the single-parent path, which stays scoped to HEAD alone.
    """
    repo = make_repo(tmp_path, {"ACS-901": True})
    stage_new_agent(repo, "glossary-triage")

    run = run_check(repo, "feat(agents): add glossary-triage\n\nCloses ACS-901\n")

    assert not run.refused, (
        "an ordinary single-parent commit with a declaring citation must "
        f"still be allowed; exit={run.returncode}\n{run.output}"
    )


def test_ordinary_single_parent_commit_without_declaration_is_still_refused(tmp_path):
    # covers: ACS-100i-8-ii
    """Control (negative): an ordinary, non-merge commit that adds a new entry
    with NO declaring citation must still be refused, exactly as before the
    fix — merge-scoping must not leak into the single-parent path.
    """
    repo = make_repo(tmp_path, {"ACS-901": None})
    stage_new_agent(repo, "glossary-triage")

    run = run_check(repo, "feat(agents): add glossary-triage\n\nCloses ACS-901\n")

    assert run.refused, (
        "an ordinary single-parent commit with no declaring citation must "
        f"still be refused; exit={run.returncode}\n{run.output}"
    )


def test_editing_an_entry_during_a_merge_needs_no_declaration(tmp_path):
    # covers: ACS-100i-8-ii
    """Editing (not adding) an entry that is already present on both sides of a
    merge is not a registration, and must be allowed with no citation — on a
    REAL merge, with ``MERGE_HEAD`` genuinely present, not the bare
    single-parent edit already pinned by
    ``test_editing_an_existing_registry_entry_needs_no_declaration`` in
    ``test_acs_100i_8_registry_declaration_gate.py``. That sibling test is the
    single-parent case; this one must actually exercise the merge path or it
    adds nothing beyond restating the sibling under a merge-flavoured name.
    """
    repo = make_repo(tmp_path, {"ACS-901": None})
    stage_merge_with_edited_agent(repo, "research-agent", tier="phase")

    run = run_check(repo, "Merge base into feature-branch\n\nRefs ACS-901\n")

    assert not run.refused, (
        "editing an existing entry already present on both sides of a real "
        f"merge must be allowed with no declaration; exit={run.returncode}\n"
        f"{run.output}"
    )


def test_octopus_merge_carrying_entry_on_third_parent_only_needs_no_citation(tmp_path):
    # covers: ACS-100i-8-ii
    """The octopus-merge reproduction: ``git rev-parse -q --verify MERGE_HEAD``
    resolves only the FIRST line of ``MERGE_HEAD``, so a three-way merge whose
    only carried entry lives on the THIRD parent (absent from the base branch
    and from the second named branch) was still refused before this fix.

    Builds a real ``git merge --no-commit --no-ff branch-a branch-b branch-c``
    (asserted to leave 3 lines in ``MERGE_HEAD``, not silently collapsed to
    fewer), where the entry was registered on ``branch-c``'s tip only.
    """
    repo = make_repo(tmp_path, {"ACS-901": None})
    stage_octopus_merge_carrying_third_parent_only(repo, "check-ticket-signoff-parity")

    assert merge_head_line_count(repo) == 3, (
        "fixture must produce a genuine 3-parent octopus merge, or this test "
        "does not exercise the third-and-later MERGE_HEAD line at all"
    )

    run = run_check(repo, "Merge branch-a, branch-b, branch-c into base\n")

    assert not run.refused, (
        "an octopus merge carrying an entry registered by its THIRD parent "
        "only must be allowed with no citation; a probe that reads only the "
        f"first MERGE_HEAD line would wrongly refuse this; exit="
        f"{run.returncode}\n{run.output}"
    )


def test_octopus_merge_introducing_a_genuinely_new_entry_is_still_refused(tmp_path):
    # covers: ACS-100i-8-ii
    """Negative control for the octopus case: carrying a third-parent entry
    must not become a way to smuggle a genuinely new, undeclared entry through
    an octopus merge either. Without this, the octopus fix above could be
    satisfied by exempting merges entirely, which would pass this file's
    two-parent negative control while leaving the octopus path wide open.
    """
    repo = make_repo(tmp_path, {"ACS-901": None})
    stage_octopus_merge_with_genuinely_new_agent(
        repo, "check-ticket-signoff-parity", "brand-new-octopus-surface"
    )

    run = run_check(repo, "Merge branch-a, branch-b, branch-c into base\n\nRefs ACS-901\n")

    assert run.refused, (
        "an octopus merge that introduces an entry absent from ALL parents "
        "must still be refused even though it also carries a third-parent "
        f"entry; exit={run.returncode}\n{run.output}"
    )
    assert "brand-new-octopus-surface" in run.output, (
        f"the refusal must name the genuinely new entry; output:\n{run.output}"
    )
    assert AGENT_REGISTRY_REL in run.output, (
        f"the refusal must name the registry file; output:\n{run.output}"
    )
