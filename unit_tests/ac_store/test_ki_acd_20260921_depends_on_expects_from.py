"""
MODULE: unit_tests/ac_store/test_ki_acd_20260921_depends_on_expects_from.py
GOAL: Regression coverage for the 2026-09-21 defect filed against
    ``_build_ticket_depends_on`` (``scripts/ac_store/_gtfa_store.py``):
    an AC's ``expects_from`` names a genuine producer-AC dependency, and that
    edge was silently dropped from the generated ticket's ``depends_on``
    whenever the consuming AC's own ``depends_on`` field did not ALSO name
    the same producer — observed to correlate with (but, per this file's
    findings, NOT caused by) the consuming AC's ``delivers_to`` being null.

    Reproduction table from the filed defect (four records generated in one
    pass from the same tree):

        AC            delivers_to   expects_from   resulting depends_on
        BO-4100d-1    populated     (none)         []            -- correct
        BO-4100d-2    null          BO-4100d-1     []            -- WRONG (sibling edge dropped)
        BO-4100d-3    populated     BO-4100d-1     [ticket-for-d-1]  -- correct
        BO-4100d-3-i  null          BO-4100d-3     []            -- correct for a DIFFERENT
                                                                     reason (KI-ACD-021: the
                                                                     target is d-3-i's own
                                                                     PARENT, always dropped)

    ACTUAL MECHANISM (confirmed by reading _gtfa_store.py before any fix was
    applied, not by trusting the ``delivers_to``-null inference): before this
    fix, ``_build_ticket_depends_on`` read ONLY ``ac.get("depends_on")`` and
    never consulted ``expects_from`` at all. The correlation with a null
    ``delivers_to`` on the CONSUMING record is coincidental to how those
    fixture records happened to be authored (a ``depends_on`` field mirroring
    ``expects_from`` was present on d-3 but absent on d-2) — the code path
    itself has no branch on ``delivers_to`` whatsoever. This was verified by
    calling ``_build_ticket_depends_on`` directly with
    ``delivers_to: None`` AND an explicit ``depends_on`` field: the edge
    resolved correctly regardless of ``delivers_to``, proving the null
    ``delivers_to`` inference in the filed defect is NOT the causal
    mechanism. The real defect is scope, not a conditional: ``expects_from``
    was never a candidate-id source at all.

    test_sibling_edge_from_expects_from_survives_when_delivers_to_is_null is
    the regression test for Defect 1 and is RED against the pre-fix code
    (confirmed by running it with the fix in _gtfa_store.py reverted — see
    the sign-off comment / handback report for the captured failure output).

    test_parent_edge_from_expects_from_still_dropped is the sibling-vs-parent
    discriminator required by the filed defect: BO-4100d-3-i's target is its
    own structural PARENT (KI-ACD-021's territory, a separate, already-
    tracked defect), and this fix must NOT also start emitting that edge --
    doing so would be a scope change this ticket does not ask for and would
    need its own verification.

ARCHITECTURE: Behavioral, subprocess-based tests mirroring the established
    pattern in unit_tests/ac_store/test_tkt_600a_2.py: invoke
    generate_ticket_from_ac.py for real against a temp AC store and temp
    tickets root, then parse the generated ticket's actual YAML frontmatter.
    Two ACs are generated in sequence into the SAME tickets root so the
    consumer's dependency can resolve to a real, already-written sibling
    ticket file (mirroring how ``_find_existing_ticket`` is meant to be used
    across a multi-ticket generation pass).

COVERS: KI-ACD-20260921 (Defect 1) -- filed as
    docs/known-issues/ac-driven-dev/open-high-ki-acd-20260921-1615.md on
    another branch; not present in this worktree, so the reproduction table
    above is transcribed in full rather than cited by path.
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
# Defect 1, scenario 1 (the regression test) — a SIBLING named only in
# expects_from, on a consumer whose delivers_to is null, must survive.
# ---------------------------------------------------------------------------


class TestSiblingEdgeFromExpectsFromSurvivesRegardlessOfDeliversTo:
    def test_sibling_edge_from_expects_from_survives_when_delivers_to_is_null(
        self, tmp_path: Path
    ) -> None:
        # covers: KI-ACD-20260921 (Defect 1)
        # angle: criterion
        """BO-4100d-2 shape: producer AC 'ZZDEP-9200-1' is generated first (a
        real, standalone AC — its own delivers_to is populated, mirroring
        BO-4100d-1). The consumer 'ZZDEP-9200-2' carries `delivers_to: null`
        and `expects_from: {ac_id: ZZDEP-9200-1}`, with NO `depends_on` field
        of its own at all — the exact shape that dropped the edge before this
        fix, because the old code read only `depends_on`.

        Must be RED before the fix in _gtfa_store.py's
        _build_ticket_depends_on (it read only ac.get("depends_on") and never
        consulted expects_from): the resulting depends_on was `[]`.

        After the fix, depends_on must name the producer's generated ticket
        file — proving the edge is derived from expects_from directly, not
        merely from a depends_on field the author happened to mirror it into.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        producer_id = "ZZDEP-9200-1"
        consumer_id = "ZZDEP-9200-2"

        producer_data = _ac(
            producer_id,
            delivers_to={
                "agent": "python-coder",
                "contract": "a fixture producer contract",
            },
        )
        producer_ticket = _generate_ticket(producer_id, ac_dir, tickets_dir, producer_data)
        assert producer_ticket.is_file()

        consumer_data = _ac(
            consumer_id,
            delivers_to=None,
            expects_from={
                "ac_id": producer_id,
                "contract": "the fixture producer contract",
            },
        )
        consumer_ticket = _generate_ticket(consumer_id, ac_dir, tickets_dir, consumer_data)
        fm = _parse_frontmatter(consumer_ticket)

        depends_on = fm.get("depends_on") or []
        assert depends_on == [producer_ticket.name], (
            f"depends_on must name the producer's ticket file "
            f"({producer_ticket.name!r}) purely because expects_from names "
            f"it — this must hold even though the consumer's own delivers_to "
            f"is null and it carries no depends_on field of its own. "
            f"Got depends_on={depends_on!r}."
        )


# ---------------------------------------------------------------------------
# Defect 1, scenario 2 — the parent-edge case (KI-ACD-021 territory) must
# stay dropped; this fix must not accidentally widen into that separate bug.
# ---------------------------------------------------------------------------


class TestParentEdgeFromExpectsFromStillDropped:
    def test_parent_edge_from_expects_from_still_dropped(self, tmp_path: Path) -> None:
        # covers: KI-ACD-20260921 (Defect 1) -- discriminator vs KI-ACD-021
        # angle: boundary
        """BO-4100d-3-i shape: the CHILD's expects_from names its own
        structural PARENT ('ZZDEP-9201-1' is the parent of
        'ZZDEP-9201-1-i'). This is KI-ACD-021's territory (parent edges are
        dropped by design — that is a separate, already-tracked defect this
        ticket does not touch), and the fix for Defect 1 must not
        accidentally start emitting the parent edge too: doing so would be
        an (unclaimed, unverified) fix for KI-ACD-021, not for Defect 1.

        depends_on must remain empty.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        parent_id = "ZZDEP-9201-1"
        child_id = "ZZDEP-9201-1-i"

        parent_data = _ac(
            parent_id,
            delivers_to={"agent": "python-coder", "contract": "parent contract"},
        )
        _generate_ticket(parent_id, ac_dir, tickets_dir, parent_data)

        child_data = _ac(
            child_id,
            delivers_to=None,
            expects_from={"ac_id": parent_id, "contract": "parent's own output"},
        )
        child_ticket = _generate_ticket(child_id, ac_dir, tickets_dir, child_data)
        fm = _parse_frontmatter(child_ticket)

        depends_on = fm.get("depends_on") or []
        assert depends_on == [], (
            f"depends_on must remain empty when expects_from names the "
            f"record's own structural parent ({parent_id!r}) -- that is "
            f"KI-ACD-021's territory, a separate, already-tracked defect this "
            f"fix does not touch. Got depends_on={depends_on!r}."
        )


# ---------------------------------------------------------------------------
# Defect 1, scenario 3 — both depends_on and expects_from name the SAME
# producer: no duplicate entry.
# ---------------------------------------------------------------------------


class TestDependsOnAndExpectsFromNamingSameProducerDeduplicate:
    def test_same_producer_named_in_both_fields_appears_once(
        self, tmp_path: Path
    ) -> None:
        # covers: KI-ACD-20260921 (Defect 1)
        # angle: boundary
        """BO-4100d-3 shape: the consumer carries BOTH an authored
        `depends_on: [producer_id]` AND an `expects_from` naming the same
        producer. depends_on must contain exactly one entry for it -- the
        union of the two sources must de-duplicate, not double-list the same
        ticket.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        producer_id = "ZZDEP-9202-1"
        consumer_id = "ZZDEP-9202-2"

        producer_data = _ac(
            producer_id,
            delivers_to={"agent": "python-coder", "contract": "producer contract"},
        )
        producer_ticket = _generate_ticket(producer_id, ac_dir, tickets_dir, producer_data)

        consumer_data = _ac(
            consumer_id,
            delivers_to={"agent": "python-coder", "contract": "consumer contract"},
            depends_on=[producer_id],
            expects_from={"ac_id": producer_id, "contract": "producer contract"},
        )
        consumer_ticket = _generate_ticket(consumer_id, ac_dir, tickets_dir, consumer_data)
        fm = _parse_frontmatter(consumer_ticket)

        depends_on = fm.get("depends_on") or []
        assert depends_on == [producer_ticket.name], (
            f"depends_on must name the producer's ticket exactly once even "
            f"though both depends_on and expects_from name it. "
            f"Got depends_on={depends_on!r}."
        )
