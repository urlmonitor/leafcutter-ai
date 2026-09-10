"""
MODULE: test_uxp_700b_1_i
GOAL: Pin that one unreadable journey file degrades the product-truth checker's run
    without stopping it -- the checker must NAME the unreadable journey, STATE that it
    examined the rest, and REPORT an outcome distinct from both "examined nothing" and
    "checked and found sound" -- while still exiting non-blocking (fail-open convention,
    GE-120 / GE-116a-1-iii).
BUSINESS CONTEXT: AC UXP-700b-1-i. depends_on UXP-700b-1 (the sibling record that
    introduces the shared machine-readable outcome vocabulary this record's "degraded"
    value belongs to: checked-and-sound / nothing-examined / degraded / failed -- see
    architect-review's sign-off comment on this ticket). This record is the paired
    acceptable-input control for UXP-700b-1: without it, an implementer could satisfy
    UXP-700b-1 by making ANY imperfect run fail outright, which would repeal the
    project's deliberate fail-open convention and block unrelated work on a single bad
    file. Both halves -- visible AND non-blocking -- must be asserted together or the
    pair is not a control (see the AC's own test_rationale).
ARCHITECTURE: The record's "checker" is docs/product-truth/scripts/validate_product_truth.py
    (identified by architect-review's blast-radius analysis), invoked in production as the
    pre-commit hook check-product-truth-validate via run_hook.py. The per-journey read
    that must fail open lives in generate_product_truth.py::load_flows() (shared by both
    the generator and the validator), per architect-review's design note -- but these
    tests observe ONLY validate_product_truth.py's main() output, not load_flows()'s
    internal signature, so the exact shape of the fix inside load_flows() is left to
    python-coder's design.

CONTRACT THIS FILE PINS ON validate_product_truth.py's main() (does not yet exist --
    this is the RED target for python-coder):
    main() must, as the LAST line written to stdout (via print(), independent of the
    logging module's handler configuration -- logging.basicConfig() is a process-wide
    one-shot call and a second call from a later test in the same process is a documented
    no-op, so nothing here may depend on capturing logger output), print a single JSON
    object:
        {"outcome": "checked-and-sound" | "nothing-examined" | "degraded" | "failed",
         "examined": <int>,        # count of journeys (flow files) successfully read
         "unreadable": [<str>, ...]}  # store-relative-ish paths of journeys that could
                                       # not be parsed; empty when none
    Exit code: 0 for checked-and-sound / nothing-examined / degraded (fail-open -- a
    degraded run must NOT stop the work that triggered it); non-zero only for "failed"
    (a real cross-reference/schema error, never exercised by this file's fixtures).

AC-N MAPPING (this ticket's top-level ## Acceptance Criteria checklist -- there is no
    ## AC Coverage table in this ticket body to fill, and no ### test-writer subsection
    under ## Agent Contracts, so this note is the record of contract-aware AC mapping
    per the test-writer prompt's Contract-Aware Mode / global-AC-list fallback):
    AC-1 (names the unreadable journey)         -> test_one_malformed_journey_is_named_and_the_rest_are_examined
    AC-2 (states it examined the other four)     -> test_one_malformed_journey_is_named_and_the_rest_are_examined
    AC-3 (outcome neither nothing-examined nor
          checked-and-sound)                     -> test_degraded_run_outcome_is_neither_clean_nor_nothing_examined
    AC-4 (does not stop the triggering work)     -> test_degraded_run_does_not_block_the_triggering_work
    All four ACs are additionally exercised end-to-end through the real CLI entry point
    by test_uxp_700b_1_i_reachable_from_entry_point.

FIXTURE STRATEGY: Hand-authoring N internally-consistent flow.json + index.json derived
    maps by hand is exactly the kind of author's-mental-model fixture the Fixture
    Authenticity Rule (test-writer prompt Sec 2h.2) warns against. Instead,
    _make_journey_store() writes only the schema-required minimum for each flow +a matching
    index.json artifacts entry, then runs the REAL generate_product_truth.generate() once
    to derive every impl_status/impl_summary/by_component/by_entity/by_flow/by_ac field
    from the real derivation logic -- the same logic validate_product_truth.py itself
    checks against. Only AFTER that clean baseline is written does the malformed journey
    file get dropped onto disk (deliberately unregistered in index.json, since the whole
    point is that it is a ROGUE file the checker has never been told about) -- generate()
    itself would hit today's exact bug if it saw the malformed file first, so it must
    never be allowed to.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

# The scripts directory is not on the default path; add it so we can import both
# modules directly for the in-process (non-subprocess) tests, mirroring the convention
# already used by unit_tests/test_generate_product_truth_idempotency.py and
# unit_tests/product_truth/test_uxp_700a_2_i.py for this same location.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
_PT_SRC = _REPO_ROOT / "docs" / "product-truth"
_REAL_VALIDATE_SCRIPT = _SCRIPTS_DIR / "validate_product_truth.py"
_REAL_GENERATE_SCRIPT = _SCRIPTS_DIR / "generate_product_truth.py"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402
import validate_product_truth as vpt  # noqa: E402

_MALFORMED_JOURNEY_NAME = "broken.flow.json"


# --------------------------------------------------------------------------- #
# Fixture builders
# --------------------------------------------------------------------------- #
def _write_valid_flow(flows_dir: Path, flow_id: str, component: str) -> None:
    """Write one schema-minimal, valid flow.json (single not_started step)."""
    flow = {
        "id": flow_id,
        "component": component,
        "name": flow_id,
        "summary": "A minimal, schema-valid test journey with a single step.",
        "kind": "user",
        "source": "real",
        "status": "active",
        "readiness": "draft",
        "version": 1,
        "entities": [],
        "steps": [
            {"id": "step-a", "label": "Step A", "human": "User does something.", "order": 1},
        ],
    }
    name = flow_id.split("/")[-1]
    (flows_dir / f"{name}.flow.json").write_text(
        json.dumps(flow, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _make_journey_store(tmp: Path, num_valid: int, include_malformed: bool) -> tuple[Path, Path]:
    """Build a self-consistent product-truth store with num_valid real journeys.

    Returns (store, ac_store). When include_malformed is True, ONE additional
    unreadable journey file (invalid JSON) is dropped in after the real generator has
    already derived a clean baseline from the num_valid well-formed flows -- it is
    deliberately never registered in index.json's artifacts, since it is a rogue file
    the checker has never been told to expect, not a known-and-broken one.
    """
    store = tmp / "product-truth"
    ac_store = tmp / "acceptance-criteria"
    flows_dir = store / "flows" / "widgets"
    flows_dir.mkdir(parents=True)
    (store / "mock-data").mkdir(parents=True)
    (store / "mockups").mkdir(parents=True)
    (store / "classifier").mkdir(parents=True)
    (store / "classifier" / "eval.jsonl").write_text("", encoding="utf-8")
    ac_store.mkdir(parents=True)

    schemas_src = _PT_SRC / "schemas"
    schemas_dst = store / "schemas"
    shutil.copytree(schemas_src, schemas_dst)

    artifacts = []
    for i in range(1, num_valid + 1):
        flow_id = f"widgets/journey-{i}"
        _write_valid_flow(flows_dir, flow_id, "widgets")
        artifacts.append(
            {
                "id": flow_id,
                "type": "flow",
                "component": "widgets",
                "status": "active",
                "readiness": "draft",
                "version": 1,
            }
        )

    index = {"artifacts": artifacts, "entity_registry": []}
    (store / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    original_gpt_store, original_gpt_ac_store = gpt.STORE, gpt.AC_STORE
    gpt.STORE, gpt.AC_STORE = store, ac_store
    try:
        gpt.generate(check=False, run_date="2026-09-09")
    finally:
        gpt.STORE, gpt.AC_STORE = original_gpt_store, original_gpt_ac_store

    if include_malformed:
        (flows_dir / _MALFORMED_JOURNEY_NAME).write_text("{not valid json!!", encoding="utf-8")

    return store, ac_store


def _run_validate_main_in_process(store: Path, ac_store: Path) -> tuple[int, str, str]:
    """Call validate_product_truth.main() directly (real function, real logic).

    Patches BOTH generate_product_truth.STORE/AC_STORE (load_flows/load_mocks/
    build_ac_map look these up as module globals inside generate_product_truth.py, the
    module they are DEFINED in, regardless of who calls them) AND
    validate_product_truth.STORE/AC_STORE (used directly inside main() for
    index.json/schemas/mockups/ac records). Captures stdout/stderr around the call so
    the printed JSON contract can be parsed without depending on logging handler state,
    which -- because logging.basicConfig() is a one-shot, process-wide call -- a second
    test in the same process cannot reliably reconfigure.
    """
    original_vpt_store, original_vpt_ac_store = vpt.STORE, vpt.AC_STORE
    original_gpt_store, original_gpt_ac_store = gpt.STORE, gpt.AC_STORE
    vpt.STORE, vpt.AC_STORE = store, ac_store
    gpt.STORE, gpt.AC_STORE = store, ac_store
    old_argv = sys.argv
    sys.argv = ["validate_product_truth.py", "--quiet"]
    stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exit_code = vpt.main()
    finally:
        vpt.STORE, vpt.AC_STORE = original_vpt_store, original_vpt_ac_store
        gpt.STORE, gpt.AC_STORE = original_gpt_store, original_gpt_ac_store
        sys.argv = old_argv
    return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()


def _parse_outcome_json(stdout: str) -> dict:
    """Parse the last non-blank line of stdout as the outcome JSON contract.

    Fails loudly (not silently) if main() has not yet been implemented to print it --
    this IS the red state until python-coder adds the print(json.dumps(...)) call.
    """
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise AssertionError(f"main() printed no stdout at all; expected a final JSON outcome line. stdout={stdout!r}")
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"main()'s last stdout line is not valid JSON (the outcome contract is not yet "
            f"implemented): {lines[-1]!r}"
        ) from exc


class TestDegradedRunNamesAndCountsJourneys(unittest.TestCase):
    """AC UXP-700b-1-i: one unreadable journey is named; the rest are stated examined."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_one_malformed_journey_is_named_and_the_rest_are_examined(self) -> None:
        # covers: UXP-700b-1-i
        # angle: failure
        """5 journeys, 1 malformed: the checker names it and states 4 were examined.

        Implementation requirement: validate_product_truth.py's main() must, via the
        (now fail-open) load_flows(), read the 4 well-formed journeys, skip the 1
        malformed one instead of letting json.JSONDecodeError propagate and kill the
        whole run, and report both facts in its final JSON stdout line.
        """
        store, ac_store = _make_journey_store(self.tmp, num_valid=4, include_malformed=True)

        exit_code, stdout, stderr = _run_validate_main_in_process(store, ac_store)

        payload = _parse_outcome_json(stdout)
        self.assertEqual(
            payload.get("examined"),
            4,
            f"expected 4 journeys examined (the well-formed ones), got {payload.get('examined')!r}. "
            f"full payload={payload!r}",
        )
        unreadable = payload.get("unreadable") or []
        self.assertTrue(
            any(_MALFORMED_JOURNEY_NAME in entry for entry in unreadable),
            f"the malformed journey '{_MALFORMED_JOURNEY_NAME}' must be NAMED in the "
            f"'unreadable' list, not just silently dropped. unreadable={unreadable!r}",
        )


class TestDegradedOutcomeVocabulary(unittest.TestCase):
    """AC UXP-700b-1-i: the degraded outcome is neither the clean nor the empty outcome."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_degraded_run_outcome_is_neither_clean_nor_nothing_examined(self) -> None:
        # covers: UXP-700b-1-i
        # angle: boundary
        """Runs the checker over three fixtures -- zero journeys, all-clean journeys,
        and one-malformed-among-many -- and asserts the three reported outcomes are
        pairwise distinguishable, per the shared machine-readable outcome vocabulary
        this record shares with sibling AC UXP-700b-1 (checked-and-sound /
        nothing-examined / degraded / failed; see architect-review's sign-off note on
        this ticket, which instructs reuse of 'degraded' rather than a locally-scoped
        third value).
        """
        empty_dir = self.tmp / "empty"
        empty_dir.mkdir()
        empty_store, empty_ac_store = _make_journey_store(empty_dir, num_valid=0, include_malformed=False)
        empty_exit, empty_stdout, _ = _run_validate_main_in_process(empty_store, empty_ac_store)
        empty_payload = _parse_outcome_json(empty_stdout)

        clean_dir = self.tmp / "clean"
        clean_dir.mkdir()
        clean_store, clean_ac_store = _make_journey_store(clean_dir, num_valid=5, include_malformed=False)
        clean_exit, clean_stdout, _ = _run_validate_main_in_process(clean_store, clean_ac_store)
        clean_payload = _parse_outcome_json(clean_stdout)

        degraded_dir = self.tmp / "degraded"
        degraded_dir.mkdir()
        degraded_store, degraded_ac_store = _make_journey_store(degraded_dir, num_valid=4, include_malformed=True)
        degraded_exit, degraded_stdout, _ = _run_validate_main_in_process(degraded_store, degraded_ac_store)
        degraded_payload = _parse_outcome_json(degraded_stdout)

        empty_outcome = empty_payload.get("outcome")
        clean_outcome = clean_payload.get("outcome")
        degraded_outcome = degraded_payload.get("outcome")

        self.assertEqual(
            empty_outcome,
            "nothing-examined",
            f"a zero-journey store must report outcome 'nothing-examined', got {empty_outcome!r}",
        )
        self.assertEqual(
            clean_outcome,
            "checked-and-sound",
            f"an all-clean store must report outcome 'checked-and-sound', got {clean_outcome!r}",
        )
        self.assertNotEqual(
            degraded_outcome,
            empty_outcome,
            "a run that examined 4 real journeys and skipped 1 bad one must NOT report "
            "the same outcome as a run that examined nothing",
        )
        self.assertNotEqual(
            degraded_outcome,
            clean_outcome,
            "a run with one unreadable journey must NOT report the same outcome as a "
            "fully clean run -- the degraded state must stay visible",
        )
        self.assertEqual(
            degraded_outcome,
            "degraded",
            f"expected the shared vocabulary's 'degraded' value, got {degraded_outcome!r}",
        )


class TestDegradedRunDoesNotBlock(unittest.TestCase):
    """AC UXP-700b-1-i: a single unreadable journey does not stop the triggering work."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp_dir.name)

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_degraded_run_does_not_block_the_triggering_work(self) -> None:
        # covers: UXP-700b-1-i
        # angle: criterion
        """The checker must exit 0 (non-blocking) on a run degraded ONLY by one
        unreadable journey among several good ones -- the project's deliberate
        fail-open convention (GE-120 / GE-116a-1-iii): fail-open on ONE bad input while
        the check still ran is fine; only a run that genuinely could not be trusted
        (schema/cross-reference errors) should block. A non-zero exit here would stop
        the pre-commit commit (or whatever CI step invoked the checker) purely because
        of a single malformed input file -- exactly what this AC forbids.
        """
        store, ac_store = _make_journey_store(self.tmp, num_valid=4, include_malformed=True)

        exit_code, stdout, stderr = _run_validate_main_in_process(store, ac_store)

        self.assertEqual(
            exit_code,
            0,
            f"a run degraded only by one unreadable journey must exit 0 (non-blocking); "
            f"got exit_code={exit_code}. stdout={stdout!r} stderr={stderr!r}",
        )
        payload = _parse_outcome_json(stdout)
        self.assertEqual(
            payload.get("outcome"),
            "degraded",
            "exit 0 alone is not enough -- the outcome must also be visibly 'degraded', "
            "not silently folded into 'checked-and-sound'",
        )


class TestReachability(unittest.TestCase):
    """Reachability: the fix must be provable through the real CLI entry point."""

    def test_uxp_700b_1_i_reachable_from_entry_point(self) -> None:
        # covers: UXP-700b-1-i
        # angle: reachability
        # REQUIRED: invoke the real production entry point as a subprocess and assert
        # the new behaviour actually occurs. Do NOT satisfy this by importing
        # validate_product_truth / generate_product_truth and calling their functions
        # directly (that is what the three tests above already do, deliberately, for
        # the criterion/boundary/failure angles).
        #
        # completion_manifest.reachability_entry_point_answer:
        #   result: resolved
        #   entry_point: "python <fixture>/scripts/validate_product_truth.py --quiet
        #     (CLI via subprocess; main() guarded by if __name__ == '__main__': --
        #     Reachability Entry-Point Resolution Step 1, category 1). In production
        #     this same script is invoked as the pre-commit hook
        #     check-product-truth-validate via scripts/commit_guardian/run_hook.py,
        #     which is a pure argv passthrough / exit-code proxy around the target
        #     script (see run_hook.py's own docstring) -- subprocessing the real script
        #     directly, as this test does, exercises the identical code path the hook
        #     wrapper delegates to, without needing to also stand up commit_guardian's
        #     manifest-resolution machinery in the fixture.
        """Copies both real scripts (verbatim bytes) into a fixture store shaped like
        the real docs/product-truth/ layout, then runs validate_product_truth.py as a
        real subprocess against a fixture with 4 good journeys + 1 malformed one.
        Asserts exit 0 and the same JSON outcome contract the in-process tests pin.
        """
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            store, ac_store = _make_journey_store(tmp, num_valid=4, include_malformed=True)

            scripts_dir = store / "scripts"
            scripts_dir.mkdir(parents=True)
            (scripts_dir / "generate_product_truth.py").write_bytes(_REAL_GENERATE_SCRIPT.read_bytes())
            (scripts_dir / "validate_product_truth.py").write_bytes(_REAL_VALIDATE_SCRIPT.read_bytes())
            # build.py deploys scripts/ as a whole "*.py" glob, and validate/generate
            # import sibling modules (product_truth_checks, product_truth_index_checks,
            # product_truth_derivations). Copy the whole set so this fixture matches
            # what a real install actually contains.
            for _sibling in sorted(_SCRIPTS_DIR.glob("*.py")):
                (scripts_dir / _sibling.name).write_bytes(_sibling.read_bytes())

            # validate_product_truth.py computes STORE = Path(__file__).resolve().parent.parent
            # and AC_STORE = STORE.parent / "acceptance-criteria", so the script must live at
            # <root>/scripts/validate_product_truth.py with the fixture store contents directly
            # under <root>/ and acceptance-criteria/ as a sibling of <root>/ -- matching the
            # real repo's docs/product-truth/ + docs/acceptance-criteria/ layout. Relocate the
            # store contents from tmp/product-truth (the in-process fixture layout) to that
            # shape. ac_store (tmp/acceptance-criteria) is ALREADY a sibling of fixture_root
            # (both direct children of tmp), i.e. already at its correct final position -- it
            # is deliberately left untouched, not moved.
            fixture_root = tmp / "fixture_root"
            fixture_root.mkdir()
            for child in store.iterdir():
                if child.name == "scripts":
                    continue
                shutil.move(str(child), str(fixture_root / child.name))
            shutil.move(str(scripts_dir), str(fixture_root / "scripts"))

            result = subprocess.run(
                [sys.executable, str(fixture_root / "scripts" / "validate_product_truth.py"), "--quiet"],
                capture_output=True,
                text=True,
                timeout=30,
            )

        self.assertEqual(
            result.returncode,
            0,
            f"real CLI entry point must exit 0 (non-blocking) on a run degraded only by "
            f"one unreadable journey.\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )

        payload = _parse_outcome_json(result.stdout)
        self.assertEqual(payload.get("outcome"), "degraded")
        self.assertEqual(payload.get("examined"), 4)
        unreadable = payload.get("unreadable") or []
        self.assertTrue(
            any(_MALFORMED_JOURNEY_NAME in entry for entry in unreadable),
            f"the malformed journey must be named via the real CLI entry point too. "
            f"unreadable={unreadable!r}",
        )


if __name__ == "__main__":
    unittest.main()
