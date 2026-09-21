"""
MODULE: test_uxp_700c_2_ii
GOAL: Pin the contract for UXP-700c-2-ii / ADR-043 -- the durable, on-disk
    `behind` mark a journey carries once a check has reported it behind. This
    ticket owns ONLY the persistence (write/overwrite/remove) of that mark; the
    behind/current/never-confirmed VERDICT itself is UXP-700c-2's separate,
    not-yet-landed scope (this ticket's own `## Agent Contracts -> Expects
    From` names UXP-700c-2 as the producer of the verdict this record makes
    durable).
BUSINESS CONTEXT: A behind verdict that lives only in the checker's console
    output is invisible to every reader who did not run the check -- nearly
    all of them (the Atlas, a reviewer with the file open, an agent loading a
    journey). ADR-043 fixes the mark's name and shape so the producing
    checker (python-coder, this ticket) and the future consuming Atlas
    (frontend-coder, a later ticket under UXP-591) cannot land on different
    spellings.
ARCHITECTURE: Targets ONE new module-level function this ticket adds to the
    EXISTING, already-shipped docs/product-truth/scripts/validate_product_truth.py
    (imported here as `vpt`), colocated with UXP-700c-2's verdict computation
    per ADR-043 SS10 rather than a parallel script.

    Required new symbol (does not exist yet -- every test below is expected to
    fail until python-coder adds it):

        def _sync_behind_marks(
            flows: dict, flow_paths: dict, verdicts: dict, warnings: list[str],
            today: str,
        ) -> list[str]:
            \"\"\"Write, overwrite, or remove each examined journey's durable
            `behind` mark per ADR-043, and persist any change to disk.

            `flows`      -- {flow_id -> flow dict}, EVERY loaded journey (the
                             shape load_flows() returns).
            `flow_paths` -- {flow_id -> store-relative path str} (load_flows()'s
                             second return value).
            `verdicts`   -- {flow_id -> None | {"confirmed_against": str,
                             "changed": [str, ...]}}. Presence of a flow_id as a
                             KEY of this dict is what "examined this run" means
                             for this helper (ADR-043 SS5): a flow_id in `flows`
                             but ABSENT from `verdicts` MUST NOT be read from or
                             written to in any way -- this also covers a
                             never-confirmed journey (ADR-043 SS6), which the
                             verdict computation MUST simply omit from
                             `verdicts` rather than include with a None value.
                               * verdicts[id] is None            -> the journey
                                 is CURRENT. The `behind` key MUST be deleted
                                 outright (`flow.pop("behind", None)`) if
                                 present -- never set to null/{}/false
                                 (ADR-043 SS4) -- and MUST stay absent if it was
                                 already absent.
                               * verdicts[id] is a dict           -> the journey
                                 is BEHIND. The flow's `behind` object MUST be
                                 written/overwritten in place (never appended,
                                 never turned into a list -- ADR-043 SS7) as
                                 exactly:
                                   {"confirmed_against": verdicts[id]["confirmed_against"],
                                    "changed": sorted(verdicts[id]["changed"]),
                                    "since": <preserved or stamped -- see below>}
                                 `since` MUST be copied from the flow's EXISTING
                                 `behind.since` when `confirmed_against` is
                                 unchanged from the existing mark, and MUST be
                                 set to `today` when the mark is newly written
                                 or `confirmed_against` has changed (ADR-043
                                 SS7).
            `today`      -- an ISO-8601 "YYYY-MM-DD" string; the run date used
                             to stamp a new/changed `since`.
            `warnings`   -- an OSError writing any one journey file MUST be
                             appended to this list as a WARNING-shaped message
                             and MUST NOT raise or abort the remaining journeys
                             (ADR-043 SS9 fail-open).

            Serialisation, for every journey actually rewritten, MUST be
            byte-for-byte `json.dumps(flow, indent=2, ensure_ascii=False) +
            "\\n"` -- identical to generate_product_truth.write_flows's own
            serialisation (ADR-043 SS9), and a journey MUST be rewritten ONLY
            when the newly serialised text differs from what is currently on
            disk (write-only-on-change, ADR-043 SS5.3). No other field
            (impl_status / impl_asof / impl_summary) may be touched.

            Returns the list of flow ids whose on-disk file was actually
            rewritten this call.
            \"\"\"

    main() must call `_sync_behind_marks(...)` once, alongside the other
    per-run steps, passing it whatever verdicts UXP-700c-2's own verdict
    computation produces (not yet implemented -- see the "Reachability" note
    below for what IS provable through the real CLI today).

    Test-file layout:
      * TestSyncBehindMarksWritesAndPersists -- angle: real_artifact. Calls
        the REAL `_sync_behind_marks` against a journey written to disk via the
        real `_write_flow` serialiser, then re-reads the journey from disk IN A
        SEPARATE PROCESS (not from the in-memory dict this test mutated) to
        prove the mark is genuinely durable, not merely an in-memory side
        effect.
      * TestSyncBehindMarksRemovesOnCurrent -- angle: criterion. A journey
        already carrying a `behind` mark, re-checked and found current
        (verdict None), has the key genuinely DELETED -- not set to null/{}/
        false -- from both the in-memory dict and the raw on-disk bytes.
      * TestSyncBehindMarksLeavesUnexaminedJourneysUntouched -- angle:
        boundary. Two journeys on disk, only one present in `verdicts`; the
        one absent from `verdicts` (i.e. not examined this run, or
        never-confirmed) is byte-identical on disk after the call, including
        keeping whatever mark it already carried.
      * TestReachability -- angle: reachability. Runs the REAL
        generate_product_truth.py CLI (to derive a self-consistent index.json
        the way an installed project would) and then the REAL
        validate_product_truth.py CLI, both as subprocesses, against a
        fixture store whose one journey ALREADY carries a schema-valid
        `behind` object (ADR-043 SS2 shape). TODAY, before python-coder
        registers `behind` in flow.schema.json's top-level `properties` (that
        schema's `additionalProperties` is `false`), the real checker CLI
        rejects this fixture with a `[schema] flow ...: Additional properties
        are not allowed ('behind' was unexpected)` error and exits non-zero --
        a genuinely current, reproducible red state. It turns green the moment
        python-coder's schema change lands, independent of whether
        UXP-700c-2's verdict computation (a separate, not-yet-started ticket)
        exists -- this test proves the mark's SHAPE is wired into the real,
        already-shipped entry point; TestSyncBehindMarks* above prove the
        write/remove MECHANICS via the same real serialisation. Full
        end-to-end proof that main() itself calls `_sync_behind_marks` with a
        verdict computed from a REAL confirmation record cannot exist until
        UXP-700c-2 lands (ADR-043's own Operational section: "the first run
        [absent UXP-700c-2] MUST write zero marks... A green first run is NOT
        evidence the write path works").

completion_manifest.reachability_entry_point_answer:
  result: resolved
  entry_point: "python docs/product-truth/scripts/validate_product_truth.py
    (CLI via subprocess, main() guarded by if __name__ == '__main__':), run
    after python docs/product-truth/scripts/generate_product_truth.py derives
    a self-consistent index.json -- the same two-CLI installed-project path
    test_uxp_700c_1_i.py's _install_and_check() already established for this
    epic's sibling tickets."
completion_manifest.cross_layer_seam_answer:
  result: covered
  producing_side: "The real generate_product_truth.py CLI (derives index.json
    from an on-disk flow) piped into the real validate_product_truth.py CLI
    (schema-validates that same flow, including its `behind` object) -- both
    run as subprocesses in TestReachability, exactly the two-process seam an
    installed project's pre-commit hook chain exercises."
  reason: "Additionally, TestSyncBehindMarksWritesAndPersists pipes the real
    on-disk write _sync_behind_marks performs into a genuinely separate
    Python process's re-read of that same file, proving the persistence seam
    (checker write -> any future reader) independent of the in-memory dict
    the writer mutated."
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import validate_product_truth as vpt  # noqa: E402  (import of _sync_behind_marks is expected to fail until implemented)

# Pure fixture builders + the two-process CLI installer live in a sibling
# module (mirrors test_uxp_700b_1.py's _uxp700b1_harness convention) so this
# file stays inside the check-file-size 400-content-line limit.
from ._uxp_700c_2_ii_fixtures import (  # noqa: E402
    base_flow as _base_flow,
    install_and_check as _install_and_check,
    read_behind_in_subprocess as _read_behind_in_subprocess,
    write_flow as _write_flow,
)

_TODAY = "2026-09-16"


class TestSyncBehindMarksWritesAndPersists(unittest.TestCase):
    """real_artifact: the REAL _sync_behind_marks, writing through the REAL
    on-disk serialiser, re-read back from disk in a separate process."""

    def test_behind_verdict_writes_a_durable_mark_on_the_journey(self):
        # covers: UXP-700c-2-ii
        # angle: real_artifact
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            flows_dir = tmp / "flows"
            flow = _base_flow("fixture-product/stale-journey")
            path = _write_flow(flows_dir, flow)

            warnings: list[str] = []
            original_store = vpt.STORE
            vpt.STORE = flows_dir.parent
            try:
                rewritten = vpt._sync_behind_marks(
                    flows={flow["id"]: flow},
                    flow_paths={flow["id"]: str(path.relative_to(flows_dir.parent))},
                    verdicts={
                        flow["id"]: {
                            "confirmed_against": "AC-REAL-1@2026-09-01",
                            "changed": ["AC-REAL-1"],
                        }
                    },
                    warnings=warnings,
                    today=_TODAY,
                )
            finally:
                vpt.STORE = original_store

            self.assertEqual(
                rewritten, [flow["id"]], "a newly-behind journey's file must be reported as rewritten"
            )
            self.assertEqual(warnings, [], f"a clean write must not warn: {warnings!r}")

            on_disk = _read_behind_in_subprocess(path)

        self.assertIsNotNone(on_disk, "re-reading the journey from disk must show the mark")
        self.assertEqual(
            on_disk["confirmed_against"],
            "AC-REAL-1@2026-09-01",
            "the mark must state what the journey was last confirmed against",
        )
        self.assertEqual(on_disk["changed"], ["AC-REAL-1"])
        self.assertEqual(on_disk["since"], _TODAY, "a newly-written mark must be stamped with the run date")


class TestSyncBehindMarksRemovesOnCurrent(unittest.TestCase):
    """criterion: the mark is genuinely ABSENT (not null/{}/false) once the
    journey is found current."""

    def test_mark_is_removed_when_the_journey_becomes_current_again(self):
        # covers: UXP-700c-2-ii
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            flows_dir = tmp / "flows"
            flow = _base_flow(
                "fixture-product/formerly-behind-journey",
                behind={
                    "confirmed_against": "AC-REAL-1@2026-08-01",
                    "changed": ["AC-REAL-1"],
                    "since": "2026-08-01",
                },
            )
            path = _write_flow(flows_dir, flow)

            warnings: list[str] = []
            original_store = vpt.STORE
            vpt.STORE = flows_dir.parent
            try:
                rewritten = vpt._sync_behind_marks(
                    flows={flow["id"]: flow},
                    flow_paths={flow["id"]: str(path.relative_to(flows_dir.parent))},
                    verdicts={flow["id"]: None},
                    warnings=warnings,
                    today=_TODAY,
                )
            finally:
                vpt.STORE = original_store

            self.assertEqual(rewritten, [flow["id"]], "removing a stale mark must be reported as a rewrite")
            self.assertNotIn("behind", flow, "the key must be genuinely deleted from the in-memory dict")

            raw_text = path.read_text(encoding="utf-8")

        self.assertNotIn(
            '"behind"', raw_text, "the on-disk bytes must not carry the key at all -- not null, not {}, not false"
        )
        reloaded = json.loads(raw_text)
        self.assertNotIn("behind", reloaded)


class TestSyncBehindMarksLeavesUnexaminedJourneysUntouched(unittest.TestCase):
    """boundary: a journey absent from `verdicts` (not examined this run, or
    never-confirmed) is byte-identical on disk after the call."""

    def test_no_mark_is_written_for_a_journey_the_check_did_not_examine(self):
        # covers: UXP-700c-2-ii
        # angle: boundary
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            flows_dir = tmp / "flows"

            examined = _base_flow("fixture-product/examined-journey")
            examined_path = _write_flow(flows_dir, examined)

            unexamined = _base_flow(
                "fixture-product/unexamined-journey",
                behind={
                    "confirmed_against": "AC-REAL-1@2026-07-01",
                    "changed": ["AC-REAL-1"],
                    "since": "2026-07-01",
                },
            )
            unexamined_path = _write_flow(flows_dir, unexamined)
            original_unexamined_bytes = unexamined_path.read_bytes()

            warnings: list[str] = []
            original_store = vpt.STORE
            vpt.STORE = flows_dir.parent
            try:
                rewritten = vpt._sync_behind_marks(
                    flows={examined["id"]: examined, unexamined["id"]: unexamined},
                    flow_paths={
                        examined["id"]: str(examined_path.relative_to(flows_dir.parent)),
                        unexamined["id"]: str(unexamined_path.relative_to(flows_dir.parent)),
                    },
                    # unexamined["id"] is deliberately ABSENT from verdicts.
                    verdicts={
                        examined["id"]: {
                            "confirmed_against": "AC-REAL-1@2026-09-01",
                            "changed": ["AC-REAL-1"],
                        }
                    },
                    warnings=warnings,
                    today=_TODAY,
                )
            finally:
                vpt.STORE = original_store

            new_unexamined_bytes = unexamined_path.read_bytes()

        self.assertEqual(rewritten, [examined["id"]], "only the examined journey may be reported as rewritten")
        self.assertEqual(
            new_unexamined_bytes,
            original_unexamined_bytes,
            "a journey the check did not examine (or that is never-confirmed) must be left byte-identical, "
            "including whatever mark it already carried",
        )


class TestMainWritesAndRemovesBehindMarksThroughTheRealCli(unittest.TestCase):
    """reachability: main() itself (not a direct _sync_behind_marks call) must
    write a durable behind mark when a confirmed journey's AC content has
    drifted, and remove it once the journey is current again -- resolving
    UXP-700c-2-ii's blocker (the helper existed but was never wired). Also
    proves ADR-043's own Operational-section claim: a never-confirmed journey
    run through the real CLI gets zero marks."""

    def test_never_confirmed_journey_gets_zero_marks_from_the_real_cli(self):
        # covers: UXP-700c-2-ii
        # angle: reachability
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            result = _install_and_check(tmp, behind=None, confirmed=None)
            flow_path = tmp / "docs" / "product-truth" / "flows" / "fixture-product" / "cli-journey.flow.json"
            raw = flow_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, f"stderr={result.stderr!r}")
        self.assertNotIn('"behind"', raw, "a never-confirmed journey run through the real CLI must get zero marks")

    def test_main_writes_then_removes_a_behind_mark_through_the_real_cli(self):
        # covers: UXP-700c-2-ii
        # angle: reachability
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            # Confirmed against a signature that CANNOT match the AC's real,
            # generator-written content (its exact shape, incl. `asof`, is
            # only known once the real generate_product_truth.py CLI has
            # run) -- any mismatch is BEHIND, so an arbitrary wrong value
            # proves the write path without needing to predict it.
            confirmed = {"against": "commit-abc123", "state": {"AC-REAL-1": "0" * 64}}
            behind_result = _install_and_check(tmp, behind=None, confirmed=confirmed)
            pt = tmp / "docs" / "product-truth"
            flow_path = pt / "flows" / "fixture-product" / "cli-journey.flow.json"
            after_behind_run = json.loads(flow_path.read_text(encoding="utf-8"))
            # The REAL signature this AC now carries, to prove removal below.
            real_ac = yaml.safe_load(
                (tmp / "docs" / "acceptance-criteria" / "fixture-product" / "AC-REAL-1.yaml").read_text("utf-8")
            )
            real_signature = vpt._ac_content_signature(
                {
                    "work_status": real_ac.get("work_status"),
                    "product_truth": real_ac.get("product_truth"),
                    "implemented_by": real_ac.get("implemented_by"),
                    "covered_by": real_ac.get("covered_by"),
                }
            )

        self.assertEqual(behind_result.returncode, 0, f"stderr={behind_result.stderr!r}")
        self.assertIn("behind", after_behind_run, "main() must write a durable mark for a drifted confirmed journey")
        self.assertEqual(after_behind_run["behind"]["confirmed_against"], "commit-abc123")
        self.assertEqual(after_behind_run["behind"]["changed"], ["AC-REAL-1"])

        with tempfile.TemporaryDirectory() as tmp_name2:
            tmp2 = Path(tmp_name2)
            # A journey already carrying a stale mark, re-confirmed against
            # the AC's REAL current signature -- nothing has moved -- CURRENT.
            current_result = _install_and_check(
                tmp2,
                behind={"confirmed_against": "commit-abc123", "changed": ["AC-REAL-1"], "since": "2026-09-01"},
                confirmed={"against": "commit-def456", "state": {"AC-REAL-1": real_signature}},
            )
            flow_path2 = tmp2 / "docs" / "product-truth" / "flows" / "fixture-product" / "cli-journey.flow.json"
            raw2 = flow_path2.read_text(encoding="utf-8")

        self.assertEqual(current_result.returncode, 0, f"stderr={current_result.stderr!r}")
        self.assertNotIn('"behind"', raw2, "main() must remove a stale mark once the journey is current again")


class TestReachability(unittest.TestCase):
    """Reachability: the `behind` mark's SHAPE must be provable through
    validate_product_truth.py's real CLI entry point, not merely through a
    direct call to _sync_behind_marks()."""

    def test_uxp_700c_2_ii_reachable_from_entry_point(self):
        # covers: UXP-700c-2-ii
        # angle: reachability
        #
        # REQUIRED: invoke the production entry point as a subprocess and assert
        # the new behaviour actually occurs in the real process's own output and
        # exit code -- not by importing _sync_behind_marks and calling it
        # directly (that is what the TestSyncBehindMarks* classes above do; this
        # test proves the mark's SHAPE is actually wired into the real, already-
        # shipped validate_product_truth.py CLI's flow.schema.json validation).
        with tempfile.TemporaryDirectory() as control_tmp:
            control = _install_and_check(Path(control_tmp), behind=None)
        with tempfile.TemporaryDirectory() as tmp:
            result = _install_and_check(
                Path(tmp),
                behind={
                    "confirmed_against": "AC-REAL-1@2026-09-01",
                    "changed": ["AC-REAL-1"],
                    "since": "2026-09-01",
                },
            )

        self.assertEqual(
            control.returncode,
            0,
            f"control (no `behind` field at all) must pass cleanly; stderr={control.stderr!r}",
        )

        self.assertEqual(
            result.returncode,
            0,
            "a journey carrying a schema-valid ADR-043 `behind` object must not be rejected by the real "
            f"checker CLI once flow.schema.json registers the field; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}",
        )
        combined = result.stdout + result.stderr
        self.assertNotIn(
            "'behind' was unexpected",
            combined,
            "flow.schema.json must register `behind` as a known top-level property (ADR-043 SS1) -- "
            f"got: {combined!r}",
        )
        self.assertNotIn(
            "[schema]",
            combined,
            f"the fixture's `behind` object is otherwise schema-valid and must produce no schema error: {combined!r}",
        )


if __name__ == "__main__":
    unittest.main()
