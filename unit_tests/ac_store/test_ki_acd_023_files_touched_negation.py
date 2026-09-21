"""
MODULE: unit_tests/ac_store/test_ki_acd_023_files_touched_negation.py
GOAL: Regression coverage for the 2026-09-21 KI-ACD-023 recurrence (third
    "populated but wrong" occurrence): an ``it_requirements`` bullet naming a
    path in an explicit "must not touch it" sense had that path scraped into
    ``files_touched`` anyway.

    Real, on-disk evidence (BO-1800f-4.yaml, found while investigating this
    ticket — this worktree's copy, unmodified by this change):

        it_requirements bullet: "Run THAT script only — not scripts/build.py,
        whose doc-index phase overwrites the tracked docs/INDEX.md with a
        `No docs found.` stub in this workspace layout (KI-BP-016)."

        it_requirements bullet: "DISCOVERABILITY IS ESTABLISHED THROUGH
        docs/INDEX.md, NOT BY CREATING docs/reference/README.md."

    Before this fix, `_build_files_touched(BO-1800f-4-record)` included BOTH
    `scripts/build.py` (the script the record explicitly says NOT to run)
    and `docs/reference/README.md` (the file the record explicitly says NOT
    to create) — neither is declared anywhere in the record's doc_links, so
    neither the existing on-disk-existence gate (TKT-600a-1) nor the
    doc_links self-declaration suppression (TKT-600a-2) could catch either.

FIX (narrow, per the ticket's "fix the narrower bug and say what you left"
    instruction — full removal of prose-scraping was evaluated and rejected;
    see the sign-off / handback report for the store-wide evidence):
    `_is_prose_path_negated` (scripts/ac_store/_gtfa_files_touched.py) excludes
    a prose-harvested path token when the literal word "not" appears within a
    short lookback window immediately before the token in its own bullet —
    "not scripts/build.py", "NOT BY CREATING docs/reference/README.md". This
    is a narrow LEXICAL rule, not semantic-intent parsing: it does not
    recognise negation phrased AFTER the path ("docs/foo.md must not be
    touched") — that is a known, named gap, not silently dropped from scope
    (see the handback report's "Anything found and not fixed" section).

ARCHITECTURE: Behavioral, subprocess-based tests mirroring
    unit_tests/ac_store/test_tkt_600a_2.py's established pattern: invoke
    generate_ticket_from_ac.py for real against a temp AC store, then parse
    the generated ticket's actual frontmatter `files_touched` list. Fixture
    prose is phrased with the negation word immediately preceding the path
    (the "not <verb(s)> <path>" shape both real occurrences share), per this
    fix's documented scope.

COVERS: KI-ACD-023 (docs/known-issues/ac-driven-dev/open-high-ki-acd-023.md),
    2026-09-21 recurrence.
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
# Shared fixture / invocation helpers (mirrors test_tkt_600a_2.py)
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
    """Build a minimal, guard-satisfying AC record, merging in *overrides*."""
    data: dict = dict(_BASE_AC_FIELDS)
    data["title"] = f"Fixture for {ac_id}"
    data["criteria"] = (
        "Given a test fixture\nWhen the generator runs\nThen a ticket is produced.\n"
    )
    data.update(overrides)
    return data


def _write_ac(ac_dir: Path, ac_id: str, data: dict) -> Path:
    """Write a real AC YAML fixture via yaml.dump — never a hand-indented literal."""
    record = {"id": ac_id, **data}
    ac_path = ac_dir / f"{ac_id}.yaml"
    with open(ac_path, "w", encoding="utf-8") as fh:
        yaml.dump(record, fh, default_flow_style=False, allow_unicode=True)
    return ac_path


def _run_generator(
    ac_id: str, ac_root: Path, tickets_root: Path
) -> subprocess.CompletedProcess:
    """Run generate_ticket_from_ac.py as a real subprocess against temp roots."""
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
    """Write the fixture AC, generate its ticket, and return the ticket's path."""
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
    """Parse the YAML frontmatter block from a generated ticket file."""
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
# Scenario 1 — "not <path>" (zero words between "not" and the token), the
# BO-1800f-4 "not scripts/build.py" shape.
# ---------------------------------------------------------------------------


class TestDirectlyNegatedPathIsExcluded:
    def test_not_prefixed_path_is_excluded_from_files_touched(
        self, tmp_path: Path
    ) -> None:
        # covers: KI-ACD-023
        # angle: criterion
        """A bullet naming a real, non-doc_links-declared path immediately
        preceded by the word "not" ("must not edit <path>") must not have
        that path enter files_touched, even though it is a real file, real
        extension, and would otherwise satisfy every existing filter.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZNEG-9300-1"
        forbidden_path = "scripts/ac_store/generate_ticket_from_ac.py"
        ac_data = _ac(
            ac_id,
            doc_links=[],
            it_requirements=[
                f"This record's own fix must not edit {forbidden_path} — it "
                f"belongs to a different, already-approved change and touching "
                f"it here would widen scope.",
            ],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        files_touched = fm.get("files_touched") or []
        assert forbidden_path not in files_touched, (
            f"files_touched must not contain {forbidden_path!r} — its own "
            f"bullet explicitly says 'must not edit' it. "
            f"Got files_touched={files_touched!r}."
        )


# ---------------------------------------------------------------------------
# Scenario 2 — "NOT BY CREATING <path>" (two words between "not" and the
# token), the BO-1800f-4 "NOT BY CREATING docs/reference/README.md" shape.
# ---------------------------------------------------------------------------


class TestNegatedPathWithInterveningWordsIsExcluded:
    def test_negated_path_with_two_intervening_words_is_excluded(
        self, tmp_path: Path
    ) -> None:
        # covers: KI-ACD-023
        # angle: boundary
        """The lookback window must reach past a short intervening phrase
        ("NOT BY CREATING <path>") — not just a bare "not <path>" — since
        this is the exact phrasing of the second real BO-1800f-4 occurrence.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZNEG-9300-2"
        forbidden_path = "docs/reference/does-not-exist-yet.md"
        ac_data = _ac(
            ac_id,
            doc_links=[],
            it_requirements=[
                f"DISCOVERABILITY IS ESTABLISHED THROUGH THE EXISTING INDEX, "
                f"NOT BY CREATING {forbidden_path} — the index step must be "
                f"skipped and reported, not silently worked around.",
            ],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        files_touched = fm.get("files_touched") or []
        assert forbidden_path not in files_touched, (
            f"files_touched must not contain {forbidden_path!r} — its bullet "
            f"explicitly says 'NOT BY CREATING' it, with two words between "
            f"'NOT' and the path. Got files_touched={files_touched!r}."
        )


# ---------------------------------------------------------------------------
# Scenario 3 — boundary control: an UN-negated real path in the same bullet
# style must still be harvested (the fix must not become a blanket
# narrowing of the prose harvest).
# ---------------------------------------------------------------------------


class TestUnnegatedPathInSameStyleBulletStillHarvested:
    def test_unnegated_path_is_still_harvested(self, tmp_path: Path) -> None:
        # covers: KI-ACD-023
        # angle: boundary
        """A path token with NO 'not' anywhere near it in its bullet must
        still enter files_touched — proving the negation filter is scoped to
        genuinely negated mentions, not a general narrowing of the existing
        prose-harvest behavior (TKT-500f-8-i).
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        ac_id = "ZZNEG-9300-3"
        real_edit_path = "scripts/goal_to_epic.py"
        ac_data = _ac(
            ac_id,
            doc_links=[],
            it_requirements=[
                f"Modify {real_edit_path} to add the new dispatch branch.",
            ],
        )
        ticket_path = _generate_ticket(ac_id, ac_dir, tickets_dir, ac_data)
        fm = _parse_frontmatter(ticket_path)

        files_touched = fm.get("files_touched") or []
        assert real_edit_path in files_touched, (
            f"files_touched must still contain {real_edit_path!r} — nothing "
            f"in its bullet negates it, so the new filter must not affect "
            f"it. Got files_touched={files_touched!r}."
        )


# ---------------------------------------------------------------------------
# Scenario 4 — real-artifact spot check against the actual on-disk record
# that motivated this fix (BO-1800f-4.yaml), not a synthetic fixture.
# ---------------------------------------------------------------------------


class TestRealOnDiskRecordNoLongerLeaksNegatedPaths:
    def test_bo_1800f_4_files_touched_excludes_both_negated_paths(self) -> None:
        # covers: KI-ACD-023
        # angle: real_artifact
        """Load the ACTUAL on-disk BO-1800f-4.yaml (not a hand-authored
        fixture reproducing the reporter's own bias) and confirm
        _build_files_touched no longer includes 'scripts/build.py' or
        'docs/reference/README.md' — the two paths this record's own prose
        explicitly forbids touching.
        """
        sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))
        import generate_ticket_from_ac as gen  # noqa: PLC0415

        record_path = (
            _REPO_ROOT
            / "docs"
            / "acceptance-criteria"
            / "build-orchestration"
            / "BO-1800-isolated-parallel-delivery"
            / "BO-1800f-4.yaml"
        )
        assert record_path.is_file(), f"fixture record missing: {record_path}"
        data = yaml.safe_load(record_path.read_text(encoding="utf-8"))

        files_touched = gen._build_files_touched(data)

        assert "scripts/build.py" not in files_touched, (
            f"BO-1800f-4's own it_requirements says 'not scripts/build.py'. "
            f"Got files_touched={files_touched!r}."
        )
        assert "docs/reference/README.md" not in files_touched, (
            f"BO-1800f-4's own it_requirements says 'NOT BY CREATING "
            f"docs/reference/README.md'. Got files_touched={files_touched!r}."
        )
