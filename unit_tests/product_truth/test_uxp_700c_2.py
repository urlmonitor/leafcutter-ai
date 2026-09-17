"""
MODULE: test_uxp_700c_2
GOAL: Pin the contract for the freshness/verdict check UXP-700c-2 adds to
    docs/product-truth/scripts/validate_product_truth.py: every journey that
    carries a `confirmed` record states, per described thing (today: the AC
    ids its steps/branches `implements`), what it was last confirmed against;
    a journey whose described things have moved since that confirmation is
    reported behind, naming the journey and each described thing that
    changed; a journey whose described things have not moved is not
    reported; and the run states how many journeys it actually compared
    (had a `confirmed` record to compare against), a figure that rises by
    exactly one when one further confirmed journey is added.
BUSINESS CONTEXT: UXP-700c-1 is the TIER-1 FLOOR of the "citations"
    sub-surface of the Truthful Project Record epic (does the target exist).
    This AC, UXP-700c-2, is the CONTENT TIER above that floor: does the
    target still say what the record claims. Its own `notes` field rules out
    reusing impl_summary.asof / impl_asof as the freshness stamp, because the
    generator rewrites those on every run, which would make every journey
    permanently current -- so a genuinely new, human/agent-authored
    confirmation record is required. This ticket produces ONLY the verdict
    (behind/current/never-confirmed, omitted-vs-None per the contract
    UXP-700c-2-ii's `_sync_behind_marks` already consumes -- see
    unit_tests/product_truth/test_uxp_700c_2_ii.py). Persisting a `behind`
    verdict as a durable on-disk mark (ADR-043) is UXP-700c-2-ii's own,
    already-specified, separate scope; this ticket does not write to journey
    files at all.
ARCHITECTURE: architect-review (2026-09-16) directed this be built as a
    further extension of validate_product_truth.py's existing `_check_*`
    helper pattern (the same pattern UXP-700c-1's `_check_pointers` already
    established), and bound the shape of the confirmation record's identity
    field by ADR-043 SS3: "the checker MUST NOT flatten, hash, or otherwise
    synthesise an identity at the point of writing the mark" -- the
    confirmation's `against` string MUST be an explicit, caller-supplied
    value (e.g. a commit SHA or an explicit confirmation id), never computed
    by the checker.

    New, additive top-level flow.schema.json property this ticket requires
    (flow.schema.json's `additionalProperties` is `false`, so a `confirmed`
    key on any fixture flow below is REJECTED by the real schema today --
    this is a genuinely current, reproducible red state, exactly as
    UXP-700c-2-ii's own TestReachability describes for its sibling `behind`
    property):

        "confirmed": {
          "type": "object",
          "additionalProperties": false,
          "required": ["against", "state"],
          "properties": {
            "against": {"type": "string", "minLength": 1},
            "state": {
              "type": "object",
              "additionalProperties": {"type": "string"}
            }
          }
        }

    `confirmed.against` is the explicit, non-derived string identity of the
    confirmation event (an author-supplied commit SHA / confirmation id --
    NEVER synthesised by the checker; this is exactly the string ADR-043
    SS3 requires `behind.confirmed_against` to copy verbatim). `confirmed.state`
    is a snapshot, authored at confirmation time by whoever confirmed the
    journey, of one content signature per described thing (today: AC ids
    only -- the Gherkin's "files in the project" clause generalises the same
    mechanism to file paths, but no test below exercises it: architect-review's
    note discusses only AC content, and UXP-700c-1 established the AC-id-only
    precedent for "described things" via `implements`; file-path support is
    left to a follow-on AC rather than speculatively implemented here).

    Two required new module-level symbols this ticket adds to
    docs/product-truth/scripts/validate_product_truth.py (imported here as
    `vpt`) -- every test below is expected to fail until python-coder adds
    them:

        def _ac_content_signature(ac_record: dict) -> str:
            \"\"\"The CURRENT content signature of one AC record, as loaded by
            load_ac_records() (shape: {path, work_status, product_truth,
            implemented_by, covered_by}). MUST be computed EXACTLY as:

                payload = {k: v for k, v in ac_record.items() if k != "path"}
                hashlib.sha256(
                    json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()

            `path` MUST be excluded (it is an absolute filesystem path that
            varies by checkout location and carries no content information;
            including it would falsely report drift between two checkouts of
            the identical commit). This exact recipe is required -- not
            merely "some deterministic hash" -- because
            unit_tests/product_truth/test_uxp_700c_2.py's TestReachability
            below pre-computes matching signatures by hand (production code
            does not exist yet) using this literal recipe; a different
            recipe in the implementation would make that test's "current"
            case spuriously report behind.
            \"\"\"

        def _check_freshness(
            flows: dict, ac_records: dict, warnings: list[str]
        ) -> tuple[dict, int]:
            \"\"\"For every journey that carries a top-level `confirmed`
            record, compare each AC id named in `confirmed['state']` to its
            CURRENT content signature (via `_ac_content_signature`, applied
            to `ac_records[ac_id]`) and report journeys whose described
            things have moved.

            Returns (verdicts, compared):
              verdicts: {flow_id -> None | {"confirmed_against": str,
                         "changed": [str, ...]}} -- a journey with NO
                         `confirmed` record (never-confirmed) is OMITTED
                         from this dict entirely (not included with a None
                         value): this is the exact contract
                         UXP-700c-2-ii's `_sync_behind_marks` already
                         consumes (see its own docstring: "Presence of a
                         flow_id as a KEY of this dict is what 'examined
                         this run' means").
                           * verdicts[id] is None  -> every described thing's
                             current signature matches its recorded one
                             (CURRENT). No warning is appended for this
                             journey.
                           * verdicts[id] is a dict -> at least one described
                             thing's current signature differs from its
                             recorded one (BEHIND). `changed` MUST be the
                             SORTED list of every AC id whose signature
                             moved (deterministic order). `confirmed_against`
                             MUST be `flow["confirmed"]["against"]` copied
                             VERBATIM -- never re-derived. Exactly one
                             message MUST be appended to `warnings`, naming
                             the journey id (holder) and every changed AC id,
                             e.g.
                             f"[freshness] {flow_id}: behind -- changed: {changed}".
                             This is a WARNING, not an error: a stale
                             journey does not itself fail the build (only
                             UXP-700c-2-ii's separate durable-mark write
                             makes the staleness visible on disk); it must
                             NOT be appended to the `errors` list.
              compared: the number of journeys that carried a `confirmed`
                        record and were therefore actually compared this run
                        (never-confirmed journeys are NOT counted). This is
                        the figure main() states unconditionally as
                        "compared N journey(s) for freshness" -- including
                        N == 0 -- mirroring UXP-700c-1's own "resolved N AC
                        pointer(s)" convention (every run states the figure,
                        so a run that compared none it holds is
                        distinguishable, in the text, from a run that held
                        none to compare). N MUST rise by exactly one when one
                        further confirmed journey is added to the store.
            \"\"\"

    main() must:
      * call `ac_records = load_ac_records()` (already loaded once per run
        today) and `_check_freshness(flows, ac_records, warnings)` alongside
        the other `_check_*` calls, feeding its warnings into the SAME
        `warnings` list every other soft-signal check already uses (so a
        behind journey is visible on the WARN channel exactly like an
        unresolvable pointer already is);
      * state the returned compared count in the run's own output, in a form
        containing the literal substring "compared N" (N = the count) on
        EVERY run -- including N == 0.

    Test-file layout:
      * TestCheckFreshnessDirect -- angle: criterion. Calls
        `_check_freshness` directly against hand-built ac_records dicts (no
        filesystem needed): a described AC's content moves between the
        confirmation snapshot and the current record, and the journey is
        reported behind, naming both the journey and the changed AC.
      * TestCheckFreshnessBoundary -- angle: boundary. The described AC's
        content is IDENTICAL between the confirmation snapshot and the
        current record; the journey produces no warning and its verdict is
        None (current, not reported).
      * TestCheckFreshnessSeam -- angle: seam. Pipes the REAL
        `generate_product_truth.load_flows()` producer's on-disk output into
        the REAL `_check_freshness` consumer, proving the compared count
        rises by exactly one when one further on-disk confirmed journey is
        added -- a round trip through real JSON flow files, not a hand-typed
        in-memory dict (Fixture Authenticity Rule, CLAUDE.md / test-writer
        skill SS2h.2).
      * TestReachability -- angle: reachability. Runs the REAL
        validate_product_truth.py CLI as a subprocess (its own pre-existing
        entry point -- this ticket EXTENDS that script, per architect-review,
        rather than adding a new one) against a complete, schema-valid (once
        `confirmed` is registered), self-consistent fixture store built from
        scratch in a tempdir, and asserts the new freshness behaviour is
        visible in the real process's own stdout/stderr and exit code, for
        both a current run and a behind run.

completion_manifest.reachability_entry_point_answer:
  result: resolved
  entry_point: "python docs/product-truth/scripts/validate_product_truth.py
    (CLI via subprocess, main() guarded by if __name__ == '__main__':). This
    is the SAME, already-shipped entry point UXP-700c-1's own
    test_uxp_700c_1.py pins (its TestReachability). UXP-700c-2 extends that
    existing script with a further _check_* helper per architect-review's
    explicit instruction; it does not introduce a second CLI."
completion_manifest.cross_layer_seam_answer:
  result: covered
  producing_side: "The REAL generate_product_truth.load_flows() producer,
    reading on-disk JSON flow files it wrote itself via the module's own
    _write_flow helper, piped into the REAL validate_product_truth._check_freshness
    consumer (TestCheckFreshnessSeam). TestReachability additionally pipes
    the REAL validate_product_truth.py CLI's own schema-validation +
    freshness-check pipeline against a hand-authored on-disk store, through
    to the real process's own stdout/exit-code -- the same two-layer
    (on-disk store -> CLI process) seam UXP-700c-1's own reachability test
    exercises for _check_pointers."
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"

# The scripts directory is not on the default path; add it so we can import,
# mirroring unit_tests/product_truth/test_uxp_700c_1.py's convention for this
# same docs/product-truth/scripts location.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402
import validate_product_truth as vpt  # noqa: E402  (import of _check_freshness / _ac_content_signature is expected to fail until implemented)

# Pure fixture builders live in a sibling module (mirrors test_uxp_700b_1.py's
# _uxp700b1_harness convention) so this file stays inside the check-file-size
# 400-content-line limit.
from ._uxp_700c_2_fixtures import (  # noqa: E402
    ac_record as _ac_record,
    base_flow as _base_flow,
    build_freshness_cli_store as _build_freshness_cli_store,
    expected_ac_signature as _expected_ac_signature,
    step as _step,
    write_flow as _write_flow,
)

_CLI_PATH = _SCRIPTS_DIR / "validate_product_truth.py"


class TestCheckFreshnessDirect(unittest.TestCase):
    """Direct-call tests against validate_product_truth._check_freshness()."""

    def test_journey_is_reported_behind_after_a_described_thing_changes(self):
        # covers: UXP-700c-2
        # angle: criterion
        # A journey confirmed against AC-REAL-1's earlier content is reported
        # behind once AC-REAL-1's content has moved, naming the journey and
        # the changed AC. AttributeError until _check_freshness exists.
        confirmed_ac = _ac_record(work_status="todo")
        recorded_signature = vpt._ac_content_signature(confirmed_ac)
        flow = _base_flow(
            "fixture-product/moved-journey",
            steps=[_step("browse", implements=["AC-REAL-1"], order=1)],
            confirmed={"against": "commit-abc123", "state": {"AC-REAL-1": recorded_signature}},
        )
        flows = {flow["id"]: flow}
        current_ac_records = {"AC-REAL-1": _ac_record(work_status="done")}
        warnings: list[str] = []

        verdicts, compared = vpt._check_freshness(flows, current_ac_records, warnings)

        self.assertEqual(compared, 1)
        self.assertEqual(
            verdicts.get(flow["id"]),
            {"confirmed_against": "commit-abc123", "changed": ["AC-REAL-1"]},
            f"expected a behind verdict naming AC-REAL-1, got {verdicts!r}",
        )
        self.assertEqual(len(warnings), 1, f"expected exactly one freshness warning, got {warnings!r}")
        self.assertIn(
            "fixture-product/moved-journey", warnings[0], "the warning must name the holder journey"
        )
        self.assertIn("AC-REAL-1", warnings[0], "the warning must name the changed described thing")


class TestCheckFreshnessBoundary(unittest.TestCase):
    """boundary: a journey whose described things have NOT moved since
    confirmation produces no warning and is not reported as behind."""

    def test_journey_is_not_reported_when_nothing_it_describes_changed(self):
        # covers: UXP-700c-2
        # angle: boundary
        confirmed_ac = _ac_record(work_status="todo")
        recorded_signature = vpt._ac_content_signature(confirmed_ac)
        flow = _base_flow(
            "fixture-product/unmoved-journey",
            steps=[_step("browse", implements=["AC-REAL-1"], order=1)],
            confirmed={"against": "commit-abc123", "state": {"AC-REAL-1": recorded_signature}},
        )
        flows = {flow["id"]: flow}
        # Identical content to the confirmation snapshot -- nothing changed.
        current_ac_records = {"AC-REAL-1": _ac_record(work_status="todo")}
        warnings: list[str] = []

        verdicts, compared = vpt._check_freshness(flows, current_ac_records, warnings)

        self.assertEqual(compared, 1, "a confirmed journey is compared even when nothing changed")
        self.assertIsNone(
            verdicts.get(flow["id"], "MISSING-SENTINEL"),
            "an unchanged confirmed journey's verdict must be None (current), not absent and not a dict",
        )
        self.assertIn(flow["id"], verdicts, "a confirmed journey must be present as a key in verdicts")
        self.assertEqual(warnings, [], "an unchanged journey must not produce a freshness warning")

    def test_never_confirmed_journey_is_omitted_from_verdicts_and_not_compared(self):
        # covers: UXP-700c-2
        # angle: boundary
        # A journey with no `confirmed` record at all is never-confirmed: it
        # must not appear as a key in verdicts (per the contract
        # UXP-700c-2-ii's _sync_behind_marks already consumes) and must not
        # be counted in `compared`.
        flow = _base_flow(
            "fixture-product/never-confirmed-journey",
            steps=[_step("browse", implements=["AC-REAL-1"], order=1)],
            confirmed=None,
        )
        flows = {flow["id"]: flow}
        warnings: list[str] = []

        verdicts, compared = vpt._check_freshness(flows, {"AC-REAL-1": _ac_record()}, warnings)

        self.assertEqual(compared, 0)
        self.assertNotIn(
            flow["id"],
            verdicts,
            "a never-confirmed journey must be OMITTED from verdicts entirely, not included with a None value",
        )
        self.assertEqual(warnings, [])


class TestFreshnessSurvivesAVanishedCitationTarget(unittest.TestCase):
    """failure: a journey confirmed against an AC id that has since vanished
    from the AC store (renamed, retired, or the record simply moved) must not
    be reported BEHIND for that reason -- reproduces the defect ac-validator
    found in the halted run's own _check_freshness, which fell back to
    `ac_records.get(ac_id, {})` for a missing id, producing an empty
    signature that never matched the recorded one and so wrongly reported the
    journey behind with the vanished id listed as "changed"."""

    def test_a_vanished_confirmed_ac_id_does_not_make_the_journey_behind(self):
        # covers: UXP-700c-2
        # angle: failure
        # The ticket's own reproduction: a journey confirmed against
        # AC-GONE-1, which is no longer in the AC store at all (current
        # ac_records is empty). The buggy fallback (`ac_records.get(ac_id,
        # {})`) computes a signature for `{}` that can never equal the
        # recorded one, so every vanished id was misreported as "changed" --
        # this journey must NOT be reported behind for that reason alone.
        flow = _base_flow(
            "fixture-product/vanished-citation-journey",
            steps=[_step("browse", implements=["AC-GONE-1"], order=1)],
            confirmed={"against": "commit-abc", "state": {"AC-GONE-1": "deadbeef"}},
        )
        flows = {flow["id"]: flow}
        warnings: list[str] = []

        verdicts, compared = vpt._check_freshness(flows, {}, warnings)

        self.assertEqual(compared, 1, "a confirmed journey is compared even when its target vanished")
        self.assertIn(flow["id"], verdicts, "a confirmed journey must be present as a key in verdicts")
        self.assertIsNone(
            verdicts[flow["id"]],
            f"a vanished citation target must not itself produce a BEHIND verdict, got {verdicts!r}",
        )
        self.assertFalse(
            any("[freshness]" in w and "AC-GONE-1" in w for w in warnings),
            f"AC-GONE-1 must not be reported as a CHANGED (behind) described thing: {warnings!r}",
        )
        self.assertTrue(
            any("AC-GONE-1" in w for w in warnings),
            f"the vanished id must still be named, distinctly, not silently dropped: {warnings!r}",
        )


class TestCheckFreshnessSeam(unittest.TestCase):
    """Seam: the REAL load_flows() producer piped into the REAL
    _check_freshness() consumer."""

    def test_compared_journey_count_rises_with_the_number_of_journeys(self):
        # covers: UXP-700c-2
        # angle: seam
        # Adding one further confirmed journey raises the stated compared
        # count by exactly one. Proven by round-tripping through real on-disk
        # JSON flow files (via the real generate_product_truth.load_flows()
        # producer) rather than a hand-built in-memory dict (Fixture
        # Authenticity Rule, CLAUDE.md / test-writer skill SS2h.2).
        ac_records = {"AC-REAL-1": _ac_record(work_status="todo"), "AC-REAL-2": _ac_record(work_status="todo")}
        sig_1 = vpt._ac_content_signature(ac_records["AC-REAL-1"])
        sig_2 = vpt._ac_content_signature(ac_records["AC-REAL-2"])

        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            flows_dir = tmp / "flows"
            flow = _base_flow(
                "fixture-product/growing-journey",
                steps=[_step("browse", implements=["AC-REAL-1"], order=1)],
                confirmed={"against": "commit-abc123", "state": {"AC-REAL-1": sig_1}},
            )
            _write_flow(flows_dir, flow)

            original_store = gpt.STORE
            gpt.STORE = tmp
            try:
                loaded_before, _paths = gpt.load_flows()
                _verdicts_before, compared_before = vpt._check_freshness(loaded_before, ac_records, warnings=[])

                second_flow = _base_flow(
                    "fixture-product/second-confirmed-journey",
                    steps=[_step("checkout", implements=["AC-REAL-2"], order=1)],
                    confirmed={"against": "commit-def456", "state": {"AC-REAL-2": sig_2}},
                )
                _write_flow(flows_dir, second_flow)

                loaded_after, _paths2 = gpt.load_flows()
                _verdicts_after, compared_after = vpt._check_freshness(loaded_after, ac_records, warnings=[])
            finally:
                gpt.STORE = original_store

        self.assertEqual(
            compared_after,
            compared_before + 1,
            "adding exactly one further confirmed journey to the on-disk store must raise "
            "the stated compared count by exactly one on the next run",
        )


class TestReachability(unittest.TestCase):
    """Reachability: the freshness check must be provable through
    validate_product_truth.py's real CLI entry point, not merely through a
    direct call to _check_freshness()."""

    def test_uxp_700c_2_reachable_from_entry_point(self):
        # covers: UXP-700c-2
        # angle: reachability
        #
        # REQUIRED: invoke the production entry point as a subprocess and
        # assert the new freshness behaviour actually occurs in the real
        # process's own output and exit code -- not by importing
        # _check_freshness and calling it directly (that is what
        # TestCheckFreshnessDirect / TestCheckFreshnessBoundary /
        # TestCheckFreshnessSeam do; this test proves those functions are
        # actually wired into main()).
        recorded_signature = _expected_ac_signature(work_status="todo")

        with tempfile.TemporaryDirectory() as current_tmp:
            current_cli = _build_freshness_cli_store(
                Path(current_tmp), ac_work_status="todo", confirmed_signature=recorded_signature
            )
            current_result = subprocess.run(
                [sys.executable, str(current_cli)], capture_output=True, text=True, timeout=30
            )

        with tempfile.TemporaryDirectory() as behind_tmp:
            behind_cli = _build_freshness_cli_store(
                Path(behind_tmp), ac_work_status="done", confirmed_signature=recorded_signature
            )
            behind_result = subprocess.run(
                [sys.executable, str(behind_cli)], capture_output=True, text=True, timeout=30
            )

        current_combined = (current_result.stdout + current_result.stderr).lower()
        behind_combined = (behind_result.stdout + behind_result.stderr).lower()

        self.assertEqual(
            current_result.returncode,
            0,
            f"an unmoved confirmed journey must not fail the run; stdout={current_result.stdout!r} "
            f"stderr={current_result.stderr!r}",
        )
        self.assertIn(
            "compared 1",
            current_combined,
            "the run must state how many journeys it compared (1: the one confirmed journey)",
        )
        self.assertNotIn(
            "behind",
            current_combined,
            "an unmoved confirmed journey must not be reported as behind",
        )

        self.assertIn(
            "compared 1",
            behind_combined,
            "a behind journey is still counted as compared -- the count reflects journeys examined, "
            "not journeys found current",
        )
        self.assertIn(
            "fixture-product/cli-journey",
            behind_combined,
            "the CLI's behind report must name the holder journey",
        )
        self.assertIn(
            "ac-real-1",
            behind_combined,
            "the CLI's behind report must name the described thing that changed",
        )


if __name__ == "__main__":
    unittest.main()
