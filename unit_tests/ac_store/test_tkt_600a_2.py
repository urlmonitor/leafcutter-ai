"""
MODULE: unit_tests/ac_store/test_tkt_600a_2.py
GOAL: RED test stubs for TKT-600a-2 — a path an AC record's own doc_links
    declares at a non-edit-surface relationship (``related``, ``describes``)
    must not be re-promoted into ``files_touched`` merely because the same
    path is also named in a prose ``it_requirements`` bullet.

    TKT-600a-1 already gates prose-harvested path tokens on on-disk
    existence (``_is_real_prose_path``), which distinguishes illustrative
    examples from real paths using the filesystem. TKT-600a-2 adds a SECOND,
    independent filter in front of the SAME harvest: a structured
    ``doc_links``-relationship check. If the record has already declared a
    path at a relationship outside ``_EDIT_SURFACE_RELATIONSHIPS`` (e.g.
    ``related``, ``describes``) and has declared that path NOWHERE as an
    edit surface, a prose repetition of that path must not enter
    ``files_touched``.

    Real mechanism this AC targets (confirmed by reading
    generate_ticket_from_ac.py's ``_build_files_touched``): Source 1 (prose
    harvest) currently adds any token that passes
    ``_extract_paths_from_prose`` + ``_is_real_prose_path`` (on-disk
    existence) to the ``paths`` set, with NO cross-check against Source 2's
    (doc_links) relationship declarations for that same path. A path
    declared ``related`` in doc_links (and thus excluded from Source 2 by
    the ``_EDIT_SURFACE_RELATIONSHIPS`` filter) sails straight into
    ``files_touched`` anyway if it is also named in prose and exists on
    disk — exactly the GE-123d-3 / GE-123d-4-i failure this AC's notes
    document.

    MUST BE RED before the corresponding fix lands in
    generate_ticket_from_ac.py. Per this AC's own "ON PROVING IT" note, every
    fixture path in scenarios 2, 3, and 5 below EXISTS on disk as a real
    file, so the pre-existing on-disk existence gate cannot satisfy any
    assertion by proxy (the exact phantom-done shape that reopened
    TKT-600a-1 once already).

ARCHITECTURE: All tests are BEHAVIORAL — they invoke
    generate_ticket_from_ac.py as a real subprocess against a temp AC store
    and temp tickets root (mirroring the established pattern in
    unit_tests/ac_store/test_generator_frontmatter_gaps.py), then parse the
    actual generated ticket's YAML frontmatter. Fixture AC YAML files are
    written via ``yaml.dump()`` — never a hand-indented literal — per the
    project's fixture-authenticity rule.

TICKET: TKT-600a-2
COVERS: TKT-600a-2
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GEN_SCRIPT = _REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"


class _FrontmatterError(ValueError):
    """Raised when a generated ticket's frontmatter cannot be parsed."""


# ---------------------------------------------------------------------------
# Shared fixture / invocation helpers (mirrors test_generator_frontmatter_gaps.py)
# ---------------------------------------------------------------------------

_BASE_AC_FIELDS: dict = {
    "component": "ticket-creation",
    "level": "L2",
    "status": "active",
    "req_status": "active",
    "work_status": "todo",
    "assigned_agent": "python-coder",
    "estimated_complexity": "S",
    "change_target": "code",
    "risk_surface": "contract_boundary",
    "doc_links": [],
    "depends_on": [],
    "implemented_by": [],
}


def _ac(ac_id: str, **overrides: object) -> dict:
    """Build a minimal, guard-satisfying AC record, merging in *overrides*.

    Args:
        ac_id: The AC id (used to derive a default title).
        **overrides: Fields that replace the base defaults (e.g. doc_links,
            it_requirements, criteria).

    Returns:
        A dict ready to be written as an AC YAML fixture.
    """
    data: dict = dict(_BASE_AC_FIELDS)
    data["title"] = f"Fixture for {ac_id}"
    data["criteria"] = (
        "Given a test fixture\nWhen the generator runs\nThen a ticket is produced.\n"
    )
    data.update(overrides)
    return data


def _write_ac(ac_dir: Path, ac_id: str, data: dict) -> Path:
    """Write a real AC YAML fixture via yaml.dump — never a hand-indented literal.

    Args:
        ac_dir: Directory to write the AC YAML file into.
        ac_id: The AC id (used for both the filename and the `id` field).
        data: The AC record fields (without `id` — it is injected here).

    Returns:
        Path to the written AC YAML file.
    """
    record = {"id": ac_id, **data}
    ac_path = ac_dir / f"{ac_id}.yaml"
    with open(ac_path, "w", encoding="utf-8") as fh:
        yaml.dump(record, fh, default_flow_style=False, allow_unicode=True)
    return ac_path


def _run_generator(
    ac_id: str, ac_root: Path, tickets_root: Path
) -> subprocess.CompletedProcess:
    """Run generate_ticket_from_ac.py as a real subprocess against temp roots.

    Args:
        ac_id: The AC id to generate a ticket for.
        ac_root: Temp directory containing the fixture AC YAML.
        tickets_root: Temp directory to write the generated ticket into.

    Returns:
        The completed subprocess result (stdout/stderr/returncode captured).
    """
    cmd = [
        sys.executable,
        str(_GEN_SCRIPT),
        "--ac",
        ac_id,
        "--ac-root",
        str(ac_root),
        "--tickets-root",
        str(tickets_root),
        "--location-kind",
        "standalone",
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


def _generate_ticket(ac_id: str, ac_dir: Path, tickets_dir: Path, ac_data: dict) -> Path:
    """Write the fixture AC, generate its ticket, and return the ticket's path.

    Args:
        ac_id: The AC id.
        ac_dir: Temp AC store root (already created).
        tickets_dir: Temp tickets root (already created).
        ac_data: AC record fields (see `_ac`).

    Returns:
        Path to the single generated ticket file.
    """
    _write_ac(ac_dir, ac_id, ac_data)
    result = _run_generator(ac_id, ac_dir, tickets_dir)
    assert result.returncode == 0, (
        f"generator failed for {ac_id}: rc={result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    matches = list(tickets_dir.glob(f"TICKET-*-{ac_id}.md"))
    assert len(matches) == 1, f"expected exactly one ticket for {ac_id}, got {matches}"
    return matches[0]


def _parse_frontmatter(ticket_path: Path) -> dict:
    """Parse the YAML frontmatter block from a generated ticket file.

    Args:
        ticket_path: Path to the generated ticket markdown file.

    Returns:
        The parsed frontmatter mapping.

    Raises:
        _FrontmatterError: When the file has no closed frontmatter block, or
            the block does not parse to a mapping.
    """
    content = ticket_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise _FrontmatterError(f"{ticket_path}: no frontmatter block")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise _FrontmatterError(f"{ticket_path}: frontmatter block not closed")
    fm = yaml.safe_load(parts[1])
    if not isinstance(fm, dict):
        raise _FrontmatterError(f"{ticket_path}: frontmatter did not parse to a mapping")
    return fm


# ---------------------------------------------------------------------------
# TKT-600a-2 scenario 1 — non-edit-surface doc_links declaration suppresses
# the prose-duplicate; the real (GE-123d-3-shaped) motivating failure.
# ---------------------------------------------------------------------------


class TestNonEditSurfaceDeclarationSuppressesFilesTouched:
    def test_related_doc_links_path_named_in_prose_is_suppressed(
        self, tmp_path: Path
    ) -> None:
        # covers: TKT-600a-2
        # angle: criterion
        """TKT-600a-2 scenario 1: doc_links declares
        'templates/scripts/commit_guardian/check_secrets.py' at relationship
        'modifies' and 'docs/known-issues/commit-guardian.md' at relationship
        'related'; a prose it_requirements bullet also names the 'related'
        path. files_touched must be EXACTLY the modifies path — the related
        path must be absent.

        Must be RED before the fix: _build_files_touched's Source 1 (prose
        harvest) has no cross-check against Source 2's (doc_links)
        relationship declarations, so the 'related' path — named in prose and
        real on disk — is added to files_touched anyway via Source 1,
        producing files_touched with BOTH paths (the exact GE-123d-3 /
        GE-123d-4-i failure this AC documents).
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZGAP-9100a-1"
        edit_surface_path = "templates/scripts/commit_guardian/check_secrets.py"
        non_edit_surface_path = "docs/known-issues/commit-guardian.md"
        ac_data = _ac(
            ac_id,
            criteria=(
                "Given doc_links declares a modifies path and a related path\n"
                "And prose also names the related path\n"
                "When the ticket is generated\n"
                "Then files_touched excludes the related path.\n"
            ),
            doc_links=[
                {
                    "path": edit_surface_path,
                    "relationship": "modifies",
                    "status": "exists",
                },
                {
                    "path": non_edit_surface_path,
                    "relationship": "related",
                    "status": "exists",
                },
            ],
            it_requirements=[
                f"See {non_edit_surface_path} for the known-issue register this "
                f"work must not touch — context only.",
            ],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        files_touched = fm.get("files_touched") or []
        assert non_edit_surface_path not in files_touched, (
            f"files_touched must not contain {non_edit_surface_path!r} — the "
            f"record's own doc_links declares it at relationship 'related' "
            f"(non-edit-surface) and NOWHERE as an edit surface. A prose "
            f"repetition of a path the record itself declared non-edit-surface "
            f"must not promote it. Got files_touched={files_touched!r}."
        )
        assert files_touched == [edit_surface_path], (
            f"files_touched must be exactly [{edit_surface_path!r}]. "
            f"Got files_touched={files_touched!r}."
        )


# ---------------------------------------------------------------------------
# TKT-600a-2 scenario 2 — prose-only path, no doc_links entry at all, must
# still be harvested (TKT-500f-8-i behavior unchanged).
# ---------------------------------------------------------------------------


class TestProseOnlyPathWithNoDocLinksStillHarvested:
    def test_prose_only_path_with_no_doc_links_entry_is_harvested(
        self, tmp_path: Path
    ) -> None:
        # covers: TKT-600a-2
        # angle: boundary
        """TKT-600a-2 scenario 2: a prose it_requirements bullet names
        'scripts/goal_to_epic.py'; the record's doc_links contain no entry
        for that path at any relationship. files_touched must still contain
        it — the new suppression rule must not fire when there is no
        declaration to consult (TKT-500f-8-i behavior must remain unchanged).

        This is the boundary case that proves the new rule is scoped to
        genuine record self-contradiction, not a blanket narrowing of the
        prose harvest. The fixture path exists on disk as a real file, so
        the pre-existing existence gate (TKT-600a-1) cannot itself explain a
        pass here.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZGAP-9100b-1"
        prose_only_path = "scripts/goal_to_epic.py"
        ac_data = _ac(
            ac_id,
            criteria=(
                "Given a prose bullet names a real path with no doc_links entry\n"
                "When the ticket is generated\n"
                "Then files_touched contains that path.\n"
            ),
            doc_links=[],
            it_requirements=[
                f"Modify {prose_only_path} to add the new dispatch branch.",
            ],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        files_touched = fm.get("files_touched") or []
        assert prose_only_path in files_touched, (
            f"files_touched must still contain {prose_only_path!r} — the record "
            f"declares nothing about this path in doc_links, so there is no "
            f"declaration for the new suppression rule to consult, and "
            f"TKT-500f-8-i's prose-harvest behavior must remain unchanged. "
            f"Got files_touched={files_touched!r}."
        )


# ---------------------------------------------------------------------------
# TKT-600a-2 scenario 3 — edit-surface doc_links declaration AND prose both
# name the same path: exactly one entry, no duplicates.
# ---------------------------------------------------------------------------


class TestEditSurfacePathNamedInBothSourcesAppearsOnce:
    def test_modifies_path_named_in_prose_too_appears_exactly_once(
        self, tmp_path: Path
    ) -> None:
        # covers: TKT-600a-2
        # angle: boundary
        """TKT-600a-2 scenario 3: doc_links declares
        'scripts/ac_store/generate_ticket_from_ac.py' at relationship
        'modifies', and a prose it_requirements bullet also names that same
        path. files_touched must contain it exactly once — no duplicate
        entry.

        The fixture path exists on disk as a real file (it IS this module),
        so the pre-existing existence gate cannot explain a pass by removing
        the prose-harvested duplicate.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZGAP-9100c-1"
        shared_path = "scripts/ac_store/generate_ticket_from_ac.py"
        ac_data = _ac(
            ac_id,
            criteria=(
                "Given doc_links declares a modifies path also named in prose\n"
                "When the ticket is generated\n"
                "Then files_touched contains that path exactly once.\n"
            ),
            doc_links=[
                {
                    "path": shared_path,
                    "relationship": "modifies",
                    "status": "exists",
                },
            ],
            it_requirements=[
                f"Add the new suppression rule to {shared_path}'s "
                f"_build_files_touched function.",
            ],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        files_touched = fm.get("files_touched") or []
        occurrences = files_touched.count(shared_path)
        assert occurrences == 1, (
            f"files_touched must contain {shared_path!r} exactly once (it is "
            f"named both in doc_links at an edit-surface relationship and in "
            f"prose). Got files_touched={files_touched!r} "
            f"(occurrences={occurrences})."
        )


# ---------------------------------------------------------------------------
# TKT-600a-2 scenario 4 — 'describes' relationship (not just 'related')
# also suppresses; the rule is relationship-SET based.
# ---------------------------------------------------------------------------


class TestDescribesRelationshipAlsoSuppresses:
    def test_describes_doc_links_path_named_in_prose_is_suppressed(
        self, tmp_path: Path
    ) -> None:
        # covers: TKT-600a-2
        # angle: criterion
        """TKT-600a-2 scenario 4: doc_links declares
        'docs/architecture/components/ticket-lifecycle.md' at relationship
        'describes', and a prose it_requirements bullet also names that
        path. files_touched must NOT contain it — the suppression is decided
        by the relationship being outside the edit-surface set
        (_EDIT_SURFACE_RELATIONSHIPS), not by matching a single relationship
        value ('related' alone). This proves the rule is
        relationship-SET based.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZGAP-9100d-1"
        describes_path = "docs/architecture/components/ticket-lifecycle.md"
        ac_data = _ac(
            ac_id,
            criteria=(
                "Given doc_links declares a describes path also named in prose\n"
                "When the ticket is generated\n"
                "Then files_touched excludes that path.\n"
            ),
            doc_links=[
                {
                    "path": describes_path,
                    "relationship": "describes",
                    "status": "exists",
                },
            ],
            it_requirements=[
                f"Read {describes_path} for the ticket-lifecycle background "
                f"before starting — informational only.",
            ],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        files_touched = fm.get("files_touched") or []
        assert describes_path not in files_touched, (
            f"files_touched must not contain {describes_path!r} — the record's "
            f"doc_links declares it at relationship 'describes', which is "
            f"outside _EDIT_SURFACE_RELATIONSHIPS just like 'related'. The "
            f"suppression must be decided by relationship-SET membership, not "
            f"by a single hardcoded value. Got files_touched={files_touched!r}."
        )


# ---------------------------------------------------------------------------
# TKT-600a-2 scenario 5 — same path declared twice (non-edit-surface AND
# edit-surface): the edit-surface declaration wins.
# ---------------------------------------------------------------------------


class TestEditSurfaceDeclarationWinsOverNonEditSurfaceForSamePath:
    def test_path_declared_both_related_and_modifies_is_not_suppressed(
        self, tmp_path: Path
    ) -> None:
        # covers: TKT-600a-2
        # angle: boundary
        """TKT-600a-2 scenario 5: the record declares the SAME path
        'scripts/ac_store/generate_ticket_from_ac.py' TWICE in doc_links —
        once at relationship 'related' and once at relationship 'modifies' —
        and a prose bullet also names that path. files_touched must contain
        it — an explicit edit-surface declaration anywhere in the record
        wins over a non-edit-surface declaration of the same path. The
        suppression applies ONLY to paths declared as non-edit-surface and
        declared NOWHERE as an edit surface.

        This is the case that most directly distinguishes a correct
        implementation from an over-broad one that suppresses any path with
        ANY non-edit-surface doc_links entry, ignoring a co-existing
        edit-surface declaration of the same path.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZGAP-9100e-1"
        dual_declared_path = "scripts/ac_store/generate_ticket_from_ac.py"
        ac_data = _ac(
            ac_id,
            criteria=(
                "Given doc_links declares the same path both related and modifies\n"
                "When the ticket is generated\n"
                "Then files_touched contains that path.\n"
            ),
            doc_links=[
                {
                    "path": dual_declared_path,
                    "relationship": "related",
                    "status": "exists",
                },
                {
                    "path": dual_declared_path,
                    "relationship": "modifies",
                    "status": "exists",
                },
            ],
            it_requirements=[
                f"Add the new suppression rule to {dual_declared_path}.",
            ],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        files_touched = fm.get("files_touched") or []
        assert dual_declared_path in files_touched, (
            f"files_touched must contain {dual_declared_path!r} — the record "
            f"ALSO declares it at relationship 'modifies' (an edit-surface "
            f"relationship) elsewhere in doc_links, so the edit-surface "
            f"declaration must win over the co-existing 'related' declaration "
            f"of the SAME path. Suppression applies only to paths declared as "
            f"non-edit-surface and declared NOWHERE as an edit surface. "
            f"Got files_touched={files_touched!r}."
        )
