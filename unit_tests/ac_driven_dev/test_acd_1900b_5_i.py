"""
MODULE: unit_tests/ac_driven_dev/test_acd_1900b_5_i.py
GOAL: Failing behavioral stubs for ACD-1900b-5-i — "a traceability block the gate
      cannot interpret is never a green sign-off".

TICKET: tickets/00_inbox/TICKET-20260818-ACD-1900b-5-i.md
AC STORE: docs/acceptance-criteria/ac-driven-dev/ACD-1900-safe-migration/ACD-1900b-5-i.yaml

BUSINESS CONTEXT
----------------
The ticket generator (scripts/ac_store/generate_ticket_from_ac.py) emits a
two-key ``ac_traceability: {id, path}`` block on every generated ticket. The
running ac-fulfillment-gate (templates/agents/ac-fulfillment-gate.md, Step 1)
only ever extracts a THREE-key list form (``l2``, ``l3``, ``ac_path``). On a
generator-produced ticket the gate's "working list" is therefore always
EMPTY, and its Step 5 ok-rule ("every AC in the working list is passed or
skipped") is vacuously true over that empty list — the gate signs off green
having verified NOTHING.

This suite specifies the coverage-resolution API that fixes the vacuous-truth
bug, per the AC's ``delivers_to`` contracts:

    resolve_coverage(ticket_path: str) -> {
        "resolved_acs": [
            {"ac_id": str, "ac_yaml_path": str,
             "resolved_via": "traceability_block" | "source_ac"},
            ...
        ],
        "block_keys_found": [str, ...],
        "block_interpretable": bool,
    }

    verify_ticket_coverage(ticket_path: str) -> {
        "ok": bool,
        "verified_count": int,           # len(resolved_acs) actually loaded+checked
        "resolved_acs": [...],           # same shape as resolve_coverage()
        "block_keys_found": [str, ...],
        "block_interpretable": bool,
        "failures": [{"ac_id": str, "field": str}, ...],
        "message": str,                  # human-readable verdict summary
    }

    compute_verdict(resolved_acs: list[dict], ac_results: list[dict]) -> {
        "ok": bool,
        "verified_count": int,
    }
    # ac_results entries: {"ac_id": str, "passed": bool, "failed_fields": [str]}
    # THE LOAD-BEARING INVARIANT: ok must be False whenever resolved_acs is
    # empty, REGARDLESS of what ac_results contains. This is the vacuous-truth
    # guard: an empty resolved-AC list must never satisfy "every AC passed".

DESIGN ASSUMPTION BINDING ON THE IMPLEMENTER (documented here because the AC
does not pin it down, and exactly one resolver must exist — see it_requirements
"EXACTLY ONE RESOLVER"): repo-root resolution for a repo-relative
``ac_traceability.path`` (or list-form ``ac_path``) is done by walking up from
``ticket_path`` looking for a ``.git`` marker directory — the same strategy
``generate_ticket_from_ac._find_worktree_root`` already uses in this package.
Reuse that helper rather than re-implementing root discovery. Every fixture
below creates a throwaway ``.git`` marker directory at the fake-repo root for
exactly this reason.

TEST DESIGN — real artifacts only, no grep-only proof
------------------------------------------------------
Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep" and the
AC's own TEST CONSTRAINT it_requirements bullet: no test here is satisfiable by
a ``read_text()`` + regex over the gate template or the generator.

- Tests 1 and 2 INVOKE the real generator (``generate_ticket_from_ac.main``)
  to WRITE an actual ticket file to a temp directory, then execute coverage
  resolution against that real, generator-produced artifact. An
  implementation that still reads only the legacy list form resolves 0 ACs
  and fails here — the discriminating assertion is the verified-AC COUNT, not
  the verdict string.
- Tests 3 and 5 hand-construct a ticket's YAML frontmatter via
  ``yaml.safe_dump`` (never a hand-indented literal string) to exercise edge
  shapes the generator itself does not produce (an uninterpretable block; the
  legacy list form used by hand-authored tickets).
- Test 4 is a direct unit test of the vacuous-truth guard on the verdict step,
  independent of any ticket file.

RED BASELINE: ``ac_coverage_resolver`` does not exist yet (doc_links status:
planned). All tests below fail at collection time with
``ModuleNotFoundError: No module named 'ac_coverage_resolver'`` until
python-coder creates ``scripts/ac_store/ac_coverage_resolver.py`` implementing
the three functions above.

DECISION HISTORY
- 2026-08-18 [ACD-1900b-5-i/test-writer]: Initial failing stubs — all 5 tests
  RED (ImportError at collection: ac_coverage_resolver does not exist).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_driven_dev/ is 2 levels below the repo root.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_AC_STORE_DIR = _SCRIPTS_DIR / "ac_store"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))

import generate_ticket_from_ac as _gtfac  # noqa: E402

# THIS IMPORT IS THE RED BASELINE: the module does not exist yet.
import ac_coverage_resolver as _resolver  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_fake_repo(tmp_path: Path) -> Path:
    """Create a throwaway repo root with a ``.git`` marker directory.

    The (not-yet-written) resolver is specified to walk up from a ticket path
    looking for this marker — see the module docstring DESIGN ASSUMPTION.
    """
    root = tmp_path / "fake_repo"
    root.mkdir()
    (root / ".git").mkdir()
    return root


def _write_ac_yaml(
    path: Path,
    ac_id: str,
    work_status: str = "todo",
    implemented_by: list[str] | None = None,
    covered_by: list[str] | None = None,
    level: str = "L3",
) -> None:
    """Write a real AC YAML record via yaml.safe_dump (never a hand-typed literal)."""
    data = {
        "id": ac_id,
        "level": level,
        "work_status": work_status,
        "implemented_by": implemented_by or [],
        "covered_by": covered_by or [],
        "readiness": "approved",
        "title": f"Fixture AC {ac_id}",
        "criteria": "Given a fixture precondition\nWhen the fixture runs\nThen the fixture asserts.\n",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_ticket_frontmatter(ticket_path: Path, frontmatter: dict) -> None:
    """Write a ticket file whose frontmatter is produced by yaml.safe_dump.

    Fixture Authenticity Rule: a hand-indented YAML literal string is never
    used for a serialized-format fixture — the real serializer produces the
    bytes.
    """
    content = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\n# Fake ticket\n\n## Comments\n"
    ticket_path.parent.mkdir(parents=True, exist_ok=True)
    ticket_path.write_text(content, encoding="utf-8")


def _generate_ticket_via_real_generator(
    ac_root: Path,
    tickets_root: Path,
    ac_id: str,
    ac_yaml_path: Path | None = None,
) -> Path:
    """Invoke the REAL generator's main() to WRITE an actual ticket to disk.

    Returns the path to the single ticket file written.

    NOTE — generator back-write side effect: ``generate_ticket_from_ac.main``
    unconditionally appends the newly-written ticket's own path into the
    source AC's ``implemented_by`` list as a back-reference (see
    ``_write_implemented_by``). That back-reference records "a ticket exists
    for this AC" — it is not evidence that production code was written. When
    *ac_yaml_path* is given, this helper resets ``implemented_by`` and
    ``covered_by`` back to empty immediately after generation so the fixture
    matches this AC's literal Given-clause precondition (a todo AC with
    genuinely empty implemented_by/covered_by) rather than accidentally
    passing because the generator's own bookkeeping put a ticket path there.
    """
    tickets_root.mkdir(parents=True, exist_ok=True)
    rc = _gtfac.main(
        [
            "--ac", ac_id,
            "--ac-root", str(ac_root),
            "--tickets-root", str(tickets_root),
        ]
    )
    if rc != 0:
        raise AssertionError(f"generate_ticket_from_ac.main exited {rc} for AC {ac_id!r}")
    written = sorted(tickets_root.glob("*.md"))
    if len(written) != 1:
        raise AssertionError(f"Expected exactly one written ticket, found {written!r}")

    if ac_yaml_path is not None:
        data = yaml.safe_load(ac_yaml_path.read_text(encoding="utf-8"))
        data["implemented_by"] = []
        data["covered_by"] = []
        ac_yaml_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    return written[0]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTwoKeyBlockOnGeneratedTicket(unittest.TestCase):
    """Tests 1-2: a real generator-produced ticket carries the two-key block."""

    def test_two_key_block_resolves_exactly_one_ac_from_a_generated_ticket(self) -> None:
        # covers: ACD-1900b-5-i
        """AC-1/AC-2: the store AC that block names has work_status "todo", an
        empty implemented_by (and covered_by); the gate resolves that AC from
        the traceability block it was actually given.

        Invokes the generator to WRITE a real ticket for a store AC
        (work_status todo, empty implemented_by, empty covered_by — AC-1's
        precondition, embodied here as fixture setup and re-asserted after
        the generator's own back-write side effect), then
        executes coverage resolution on that ticket path: the resolved-AC
        count is exactly 1 and the resolved entry names that AC id.

        MUST be RED: ac_coverage_resolver does not exist yet
        (ModuleNotFoundError at collection).  Once it exists, an
        implementation reading only l2/l3 (the legacy three-key form) would
        resolve 0 ACs on this ticket and fail the count assertion.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_repo = _make_fake_repo(tmp_path)
            ac_id = "TESTFIX-COV-1"
            ac_root = fake_repo / "docs" / "acceptance-criteria"
            ac_yaml_path = ac_root / "test_component" / f"{ac_id}.yaml"
            _write_ac_yaml(
                ac_yaml_path,
                ac_id,
                work_status="todo",
                implemented_by=[],
                covered_by=[],
            )
            tickets_root = fake_repo / "tickets" / "00_inbox"

            ticket_path = _generate_ticket_via_real_generator(
                ac_root, tickets_root, ac_id, ac_yaml_path=ac_yaml_path
            )

            result = _resolver.resolve_coverage(str(ticket_path))

            resolved_acs = result["resolved_acs"]
            self.assertEqual(
                len(resolved_acs),
                1,
                f"Expected exactly 1 resolved AC from the two-key block, got "
                f"{len(resolved_acs)}: {resolved_acs!r}. An implementation that "
                "still reads only l2/l3 resolves 0 on a generator-produced ticket.",
            )
            self.assertEqual(resolved_acs[0]["ac_id"], ac_id)
            self.assertTrue(result["block_interpretable"])
            self.assertIn("id", result["block_keys_found"])
            self.assertIn("path", result["block_keys_found"])

    def test_two_key_block_todo_ac_blocks_and_names_each_failed_field(self) -> None:
        # covers: ACD-1900b-5-i
        """AC-3/AC-4/AC-5: verifies work_status/implemented_by/covered_by and
        returns a blocking verdict naming that AC and each field that failed;
        it does not return ok.

        On the same generated ticket, the emitted verdict is not ok, names
        the AC id, reports a verified-AC count of 1, and lists work_status,
        implemented_by and covered_by as the fields that failed. The count
        assertion prevents a block emitted for an unrelated reason from
        satisfying this test.

        MUST be RED: ac_coverage_resolver does not exist yet.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_repo = _make_fake_repo(tmp_path)
            ac_id = "TESTFIX-COV-2"
            ac_root = fake_repo / "docs" / "acceptance-criteria"
            ac_yaml_path = ac_root / "test_component" / f"{ac_id}.yaml"
            _write_ac_yaml(
                ac_yaml_path,
                ac_id,
                work_status="todo",
                implemented_by=[],
                covered_by=[],
            )
            tickets_root = fake_repo / "tickets" / "00_inbox"

            ticket_path = _generate_ticket_via_real_generator(
                ac_root, tickets_root, ac_id, ac_yaml_path=ac_yaml_path
            )

            result = _resolver.verify_ticket_coverage(str(ticket_path))

            self.assertFalse(
                result["ok"],
                f"Expected a blocking (non-ok) verdict for a todo AC with empty "
                f"implemented_by/covered_by, got ok=True: {result!r}",
            )
            self.assertEqual(
                result["verified_count"],
                1,
                f"Expected verified_count == 1 (one AC actually loaded and "
                f"checked), got {result['verified_count']!r}: {result!r}. "
                "A verdict emitted for an unrelated reason would not carry "
                "this count.",
            )
            self.assertIn(
                ac_id,
                result["message"],
                f"Expected the verdict message to name AC {ac_id!r}: {result['message']!r}",
            )
            failed_fields = {
                f["field"] for f in result["failures"] if f["ac_id"] == ac_id
            }
            for field in ("work_status", "implemented_by", "covered_by"):
                self.assertIn(
                    field,
                    failed_fields,
                    f"Expected {field!r} to be listed as a failed field for "
                    f"{ac_id!r}. failures={result['failures']!r}",
                )


class TestUninterpretableBlock(unittest.TestCase):
    """Test 3: a block with only unrecognised keys, and no rescuing source_ac."""

    def test_uninterpretable_block_is_non_ok_with_zero_verified_and_lists_found_keys(
        self,
    ) -> None:
        # covers: ACD-1900b-5-i
        """AC-6/AC-7/AC-8: the gate returns a non-ok verdict that names the
        traceability block as uninterpretable and lists the keys it found
        there; it does not report "no AC store fields to verify"; it does not
        return ok on the strength of an empty set of ACs to check.

        The ticket's ac_traceability block carries only unrecognised keys
        (no id/path, no l2/l3/ac_path), and source_ac names an AC id that
        does not exist in the store — so the ordered fallback also resolves
        nothing. The verdict must still name the unrecognised keys it found,
        per it_requirements "source_ac must NOT silently rescue an
        unrecognised block ... the verdict must still name the unrecognised
        keys it found".

        MUST be RED: ac_coverage_resolver does not exist yet.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_repo = _make_fake_repo(tmp_path)
            tickets_root = fake_repo / "tickets" / "00_inbox"
            ticket_path = tickets_root / "TICKET-fake-uninterpretable.md"
            frontmatter = {
                "title": "Fake uninterpretable-block ticket",
                "status": "todo",
                "source_ac": "NONEXISTENT-AC-DOES-NOT-EXIST-999",
                "ac_traceability": {
                    "unknown_key_1": "foo",
                    "unknown_key_2": "bar",
                },
            }
            _write_ticket_frontmatter(ticket_path, frontmatter)

            result = _resolver.verify_ticket_coverage(str(ticket_path))

            self.assertFalse(
                result["ok"],
                f"Expected a non-ok verdict for an uninterpretable block, got "
                f"ok=True: {result!r}",
            )
            self.assertEqual(
                result["verified_count"],
                0,
                f"Expected verified_count == 0 (nothing was actually "
                f"resolvable), got {result['verified_count']!r}: {result!r}",
            )
            self.assertFalse(
                result["block_interpretable"],
                f"Expected block_interpretable == False, got {result!r}",
            )
            message = result["message"]
            self.assertIn(
                "unknown_key_1",
                message,
                f"Expected the verdict message to enumerate the found key "
                f"'unknown_key_1': {message!r}",
            )
            self.assertIn(
                "unknown_key_2",
                message,
                f"Expected the verdict message to enumerate the found key "
                f"'unknown_key_2': {message!r}",
            )
            self.assertNotIn(
                "no AC store fields to verify",
                message,
                "The old absent-block skip message must NOT be emitted for a "
                f"PRESENT-but-unrecognised block: {message!r}",
            )


class TestVacuousTruthGuard(unittest.TestCase):
    """Test 4: direct invariant on the verdict step, no ticket file involved."""

    def test_ok_verdict_is_impossible_over_an_empty_resolved_ac_list(self) -> None:
        # covers: ACD-1900b-5-i
        """it_requirements THE LOAD-BEARING CONSTRAINT: coverage resolution
        must return an explicit resolved-AC list whose length is observable,
        and the ok verdict must be conditional on that length being >= 1. An
        empty resolved list must never satisfy the ok condition — whatever
        the per-AC results contain.

        This directly targets today's rule ("ok when every AC in the working
        list is passed or skipped"), which is vacuously true over an empty
        list. Passing a per-AC result that claims "passed": True alongside an
        EMPTY resolved_acs list must still yield ok=False.

        MUST be RED: ac_coverage_resolver does not exist yet.
        """
        verdict = _resolver.compute_verdict(
            resolved_acs=[],
            ac_results=[
                {"ac_id": "PHANTOM-AC-NOT-ACTUALLY-RESOLVED", "passed": True, "failed_fields": []},
            ],
        )

        self.assertFalse(
            verdict["ok"],
            "An empty resolved-AC list must never produce ok=True, regardless "
            f"of what ac_results contains. Got: {verdict!r}",
        )
        self.assertEqual(verdict["verified_count"], 0)

        # Also must not vacuously pass with zero results at all.
        verdict_empty = _resolver.compute_verdict(resolved_acs=[], ac_results=[])
        self.assertFalse(
            verdict_empty["ok"],
            f"An empty resolved-AC list with zero ac_results must still yield "
            f"ok=False (this is exactly the vacuous 'passed or skipped over "
            f"nothing' bug). Got: {verdict_empty!r}",
        )


class TestListFormRegression(unittest.TestCase):
    """Test 5: regression for the previously-accepted list form (BO-201)."""

    def test_list_form_verified_count_equals_number_of_acs_named(self) -> None:
        # covers: ACD-1900b-5-i
        # covers: BO-201
        """AC-9: the gate returns ok, and the count of ACs it reports as
        verified equals the number of ACs the block named — the previously
        accepted form keeps working unchanged.

        A ticket with l2 naming two ACs, l3 naming one, and an ac_path, all
        three store ACs done with non-empty implemented_by and covered_by,
        yields ok AND a verified-AC count of 3 — equal to the number the
        block named. Fails if the fix swapped to the two-key form instead of
        accepting both (BO-201 is a strict superset, never narrowed).

        MUST be RED: ac_coverage_resolver does not exist yet.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_repo = _make_fake_repo(tmp_path)
            component_dir = fake_repo / "docs" / "acceptance-criteria" / "legacy_component"
            ac_ids = ["LEGACY-L2-FIX-1", "LEGACY-L2-FIX-2", "LEGACY-L3-FIX-1"]
            for aid in ac_ids:
                _write_ac_yaml(
                    component_dir / f"{aid}.yaml",
                    aid,
                    work_status="done",
                    implemented_by=["scripts/some_module.py"],
                    covered_by=["unit_tests/some_module/test_some_module.py"],
                    level="L3",
                )

            tickets_root = fake_repo / "tickets" / "00_inbox"
            ticket_path = tickets_root / "TICKET-fake-list-form.md"
            frontmatter = {
                "title": "Fake list-form ticket",
                "status": "todo",
                "ac_traceability": {
                    "l2": ["LEGACY-L2-FIX-1", "LEGACY-L2-FIX-2"],
                    "l3": ["LEGACY-L3-FIX-1"],
                    "ac_path": "docs/acceptance-criteria/legacy_component/",
                },
            }
            _write_ticket_frontmatter(ticket_path, frontmatter)

            result = _resolver.verify_ticket_coverage(str(ticket_path))

            self.assertTrue(
                result["ok"],
                f"Expected ok=True when all 3 named ACs are done with "
                f"non-empty implemented_by/covered_by, got: {result!r}",
            )
            self.assertEqual(
                result["verified_count"],
                3,
                f"Expected verified_count == 3 (equal to the number of ACs "
                f"the block named: l2 has 2, l3 has 1), got "
                f"{result['verified_count']!r}: {result!r}. Fails if the fix "
                "swapped to the two-key form instead of accepting both.",
            )


if __name__ == "__main__":
    unittest.main()
