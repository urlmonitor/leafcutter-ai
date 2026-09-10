"""
MODULE: test_uxp_700b_1
GOAL: Pin the "a run that examined nothing must not look like a run that examined
    something" contract for docs/product-truth/scripts/validate_product_truth.py.
BUSINESS CONTEXT: UXP-700b-1's own notes DIRECTLY OBSERVED AND REPRODUCED the live
    defect in this repo (2026-09-07): a completely empty product-truth store, with
    its derived index regenerated, produces
        OK: 0 flows, 0 mock-data, 0 mockups, eval + index + derived data valid (0 warnings)
    and exit 0 — character-for-character the shape of a real pass. The pre-commit
    hook that consumes this checker reads only the exit code, so nothing downstream
    can tell the two runs apart either.

    IMPLEMENTATION NOTE (discovered during test authoring, 2026-09-09): this repo's
    EPIC-TruthfulProjectRecord worktree is SHARED across every ticket in the epic
    (not one worktree per ticket). By the time this test file was written,
    python-coder had already landed the fix for this exact contract while
    implementing the sibling ticket UXP-700b-1-ii (ticket #13 — the mixed/partially-
    empty "degraded" extension of this same outcome vocabulary; see
    docs/product-truth/scripts/validate_product_truth.py's DECISION HISTORY entry
    timestamped 2026-09-09 16:15). The tests below were corrected to pin the REAL,
    already-verified contract (confirmed by direct execution against the current
    file — see each assertion's rationale) rather than an invented one, per Rule 5
    (prefer expanding/aligning the test over asserting a design the codebase never
    chose) — NOT because this ticket's own python-coder step is skippable. This
    ticket's Sign-offs still show `python-coder: needed`; python-coder still owns
    reviewing/confirming/documenting this shared implementation against UXP-700b-1's
    own AC text and Sign-offs bookkeeping.
ARCHITECTURE / VERIFIED CONTRACT (already implemented — see IMPLEMENTATION NOTE):
    docs/product-truth/scripts/validate_product_truth.py, on every run, prints
    exactly one JSON object as the LAST non-blank line of STDOUT (never mixed with
    the human log, which goes to stderr via logging.basicConfig's default stream)
    shaped:
        {"outcome": "<token>", "empty_types": [<zero-or-more of "flows",
         "mock-data", "mockups">]}
    The four-token outcome vocabulary is copied VERBATIM from this AC's own
    `delivers_to.contract` field in the AC store (the authoritative source):
    "checked-and-sound / nothing-examined / degraded / failed". `empty_types` uses
    the artifact-type vocabulary the real implementation already established —
    "flows" / "mock-data" / "mockups" — which matches the store's own on-disk
    directory names (see `_ARTIFACT_TYPES` in validate_product_truth.py), NOT the
    singular/underscored "flow"/"mock_data"/"mockup" tokens used elsewhere in this
    same module for a DIFFERENT purpose (`build_by_component`'s `type_key`).

    The exit code is DELIBERATELY unchanged (0) for both "checked-and-sound" and
    "nothing-examined" — this is the fail-open convention UXP-700b-1's own notes
    require ("Failing open on one bad input while the check still ran is fine;
    reporting success when the check never examined anything is not... this does
    NOT repeal the project's fail-open convention"). The distinguishing signal the
    AC's first and third clauses require ("the outcome it reports is not the
    outcome it reports...", "a caller that reads only the outcome... can tell the
    two runs apart") is the `outcome` JSON field, not the process exit code — a
    downstream consumer that wants strict enforcement (UXP-700c-3's gate) reads
    `outcome`, not the exit status. Only "failed" (schema/derived-data errors
    present) changes the exit code, to 1 — an orthogonal, pre-existing contract this
    ticket must not disturb.

    completion_manifest.cross_layer_seam_answer:
      result: covered
      producing_side: "validate_product_truth.py main()'s stdout outcome payload"
      consuming_side: "a caller that reads ONLY payload['outcome'] and ignores any
        message/log text — the shape of the future UXP-700c-3 gate consumer named in
        this AC's own delivers_to contract"
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The scripts directory is not on the default path; add it so we can import,
# mirroring unit_tests/test_generate_product_truth_idempotency.py's convention
# and unit_tests/product_truth/test_uxp_700b_3_i.py's convention for this same
# docs/product-truth/scripts location.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ._uxp700b1_harness import (  # noqa: E402
    _make_empty_store,
    _make_sound_store,
    _parse_outcome_payload,
    _run_validate_in_process,
)

_REAL_SCHEMAS_DIR = _SCRIPTS_DIR.parent / "schemas"

# The exact vocabulary this AC's delivers_to.contract names, verbatim.
_EXPECTED_OUTCOME_SOUND = "checked-and-sound"
_EXPECTED_OUTCOME_EMPTY = "nothing-examined"
_EXPECTED_EMPTY_TYPES = ["flows", "mock-data", "mockups"]












class TestOutcomeDiffersBetweenEmptyAndSoundRuns(unittest.TestCase):
    """AC-1 / AC-3: an empty-artifact run must report a DIFFERENT outcome from a
    populated-and-sound run."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.sound_store = self.tmp / "sound" / "product-truth"
        self.sound_ac = self.tmp / "sound" / "acceptance-criteria"
        _make_sound_store(self.sound_store, self.sound_ac)
        self.empty_store = self.tmp / "empty" / "product-truth"
        self.empty_ac = self.tmp / "empty" / "acceptance-criteria"
        _make_empty_store(self.empty_store, self.empty_ac)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_empty_store_outcome_differs_from_populated_sound_store_outcome(self):
        # covers: UXP-700b-1
        # angle: criterion
        """AC-1: the outcome it reports is not the outcome it reports for a record
        holding at least one artifact of each type that satisfies every check."""
        sound_code, sound_stdout = _run_validate_in_process(self.sound_store, self.sound_ac)
        self.assertEqual(
            sound_code, 0,
            f"the populated-sound fixture must itself validate clean (existing 0 "
            f"exit-code contract preserved); stdout={sound_stdout!r}",
        )
        sound_payload = _parse_outcome_payload(sound_stdout)
        self.assertEqual(
            sound_payload.get("outcome"),
            _EXPECTED_OUTCOME_SOUND,
            "a run over a populated, sound store must report the "
            f"'{_EXPECTED_OUTCOME_SOUND}' outcome named in this AC's own "
            "delivers_to.contract vocabulary",
        )
        self.assertEqual(
            sound_payload.get("empty_types"),
            [],
            "a populated, sound store must report zero empty artifact types",
        )

        empty_code, empty_stdout = _run_validate_in_process(self.empty_store, self.empty_ac)
        empty_payload = _parse_outcome_payload(empty_stdout)
        self.assertEqual(
            empty_payload.get("outcome"),
            _EXPECTED_OUTCOME_EMPTY,
            "a run over a zero-artifact store must report the "
            f"'{_EXPECTED_OUTCOME_EMPTY}' outcome named in this AC's own "
            "delivers_to.contract vocabulary",
        )

        # The exit code is DELIBERATELY unchanged (0) for both outcomes — the
        # project's fail-open convention (see this AC's own notes) means an empty
        # store must not itself become a hard commit-blocking failure. The
        # distinguishing signal the AC requires lives in the `outcome` field, not
        # the exit status — asserted next.
        self.assertEqual(
            empty_code,
            0,
            "an empty-store run must stay fail-open (exit 0) — only the reported "
            f"'outcome' value, not the exit code, must differ; stdout={empty_stdout!r}",
        )
        self.assertNotEqual(
            empty_payload.get("outcome"),
            sound_payload.get("outcome"),
            "a run that examined nothing must not report the same machine-readable "
            "outcome as a run that examined a full, sound artifact set",
        )

    def test_empty_store_report_names_each_zero_record_artifact_type(self):
        # covers: UXP-700b-1
        # angle: criterion
        """AC-2: the reported outcome names each artifact type for which the
        checker read zero records."""
        _, empty_stdout = _run_validate_in_process(self.empty_store, self.empty_ac)
        empty_payload = _parse_outcome_payload(empty_stdout)

        self.assertIn(
            "empty_types",
            empty_payload,
            "the outcome payload must name which artifact types were read as zero "
            "records — required by this AC's second clause",
        )
        self.assertEqual(
            sorted(empty_payload["empty_types"]),
            sorted(_EXPECTED_EMPTY_TYPES),
            "a store with zero journeys, zero example datasets, and zero screens "
            "must name ALL THREE types (flows, mock-data, mockups) as empty — not "
            "just one of them",
        )


class TestOutcomeReadableWithoutParsingProse(unittest.TestCase):
    """AC-3 (seam angle): a caller that reads ONLY the outcome field — never the
    prose message/log — must still be able to tell the two runs apart. Pipes the
    REAL producer's real stdout into a real (if minimal) consumer that ignores
    everything except payload['outcome'], per Rule 3 (cross-layer seam)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.sound_store = self.tmp / "sound" / "product-truth"
        self.sound_ac = self.tmp / "sound" / "acceptance-criteria"
        _make_sound_store(self.sound_store, self.sound_ac)
        self.empty_store = self.tmp / "empty" / "product-truth"
        self.empty_ac = self.tmp / "empty" / "acceptance-criteria"
        _make_empty_store(self.empty_store, self.empty_ac)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @staticmethod
    def _caller_reads_outcome_only(payload: dict) -> str:
        """A stand-in real consumer mirroring the future UXP-700c-3 gate: reads
        ONLY payload['outcome'], never any 'message' or log text, per this AC's
        own delivers_to contract ("a machine-readable outcome vocabulary ...
        that UXP-700c-3 uses as the gate's verdict")."""
        return payload["outcome"]

    def test_outcome_is_distinguishable_without_parsing_prose(self):
        # covers: UXP-700b-1
        # angle: seam
        """AC-3: a caller that reads only the outcome, without reading the
        message, can tell the two runs apart."""
        _, sound_stdout = _run_validate_in_process(self.sound_store, self.sound_ac)
        _, empty_stdout = _run_validate_in_process(self.empty_store, self.empty_ac)

        sound_payload = _parse_outcome_payload(sound_stdout)
        empty_payload = _parse_outcome_payload(empty_stdout)

        sound_seen_by_caller = self._caller_reads_outcome_only(sound_payload)
        empty_seen_by_caller = self._caller_reads_outcome_only(empty_payload)

        self.assertNotEqual(
            sound_seen_by_caller,
            empty_seen_by_caller,
            "a caller reading ONLY the outcome field (never the message/log text) "
            "must still be able to tell the two runs apart",
        )


class TestReachability(unittest.TestCase):
    """Reachability: the checker must be provable through its real CLI entry point
    — subprocess invocation of the actual script file — not merely a direct,
    in-process call of main() or an inner helper.

    Entry-point resolution (BP-1100g-2 Step 1): validate_product_truth.py is a CLI
    script with a main() guarded by `if __name__ == "__main__":` under
    docs/product-truth/scripts/ (category 1 of the resolution order). It is NOT yet
    wired into any pre-commit hook, slash command, or workflow step — this AC's own
    "Delivers To" contract explicitly defers gate-wiring to UXP-700c-3
    ("the hook that consumes it reads only the exit code ... nothing downstream can
    tell the two apart either" — that wiring is a DIFFERENT ticket's job). So the
    CLI itself, invoked via subprocess, is the correct and only entry point this
    ticket's own code change can be proven through today.

    Because the script resolves its own store location relative to `__file__`
    (STORE = Path(__file__).resolve().parent.parent — no CLI flag or env var exists
    to redirect it), this class copies the REAL, unmodified production script files
    into a temp directory laid out exactly like docs/product-truth/scripts/ (two
    levels under a `product-truth/` root) so that the *same* production code, run
    as a real subprocess, resolves its store to our controlled fixture — never a
    modified copy of the source, and never a monkeypatched STORE (subprocess
    invocation cannot be influenced by in-process patching at all).

    completion_manifest.reachability_entry_point_answer:
      result: resolved
      entry_point: "python docs/product-truth/scripts/validate_product_truth.py
        (CLI via subprocess, main() guarded by if __name__ == '__main__':)"
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _materialize_cli(self, label: str, populate: bool) -> Path:
        root = self.tmp / label
        store_root = root / "product-truth"
        ac_root = root / "acceptance-criteria"
        scripts_dir = store_root / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        # build.py deploys scripts/ as a whole "*.py" glob, and validate/generate
        # import sibling modules; copy the whole set so this fixture matches a
        # real install.
        for _sibling in sorted(_SCRIPTS_DIR.glob("*.py")):
            shutil.copy(_sibling, scripts_dir / _sibling.name)
        if populate:
            _make_sound_store(store_root, ac_root)
        else:
            _make_empty_store(store_root, ac_root)
        return scripts_dir / "validate_product_truth.py"

    @staticmethod
    def _run_cli(script_path: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_uxp_700b_1_reachable_from_entry_point(self):
        # covers: UXP-700b-1
        # angle: reachability
        # REQUIRED: invoke the real production entry point (this module's CLI) as a
        # real subprocess for both arms of the AC's contrast, and assert the
        # outcome is consumed in control flow — this test's own assertions branch
        # on the parsed stdout JSON payload, not merely observe that something was
        # printed. (The exit code stays 0 for both outcomes by deliberate design —
        # see the module docstring's ARCHITECTURE section — so the `outcome` field,
        # not the exit status, is the control-flow-relevant value here.) Importing
        # validate_product_truth and calling main() directly would NOT satisfy this
        # (that is TestOutcomeDiffersBetweenEmptyAndSoundRuns above, the in-process
        # "criterion" test).
        """AC-1/AC-2/AC-3: the same distinguishability contract proved via the
        real CLI entry point, not merely an in-process call."""
        sound_script = self._materialize_cli("sound", populate=True)
        sound_result = self._run_cli(sound_script)
        self.assertEqual(
            sound_result.returncode,
            0,
            f"the real CLI over a populated-sound store must exit 0 (the existing "
            f"contract preserved); stderr={sound_result.stderr!r}",
        )

        empty_script = self._materialize_cli("empty", populate=False)
        empty_result = self._run_cli(empty_script)

        # The exit code is DELIBERATELY unchanged (fail-open) — see the module
        # docstring. Pinning this here too means a regression that accidentally
        # starts failing empty-store runs (breaking every existing caller that
        # reads only the exit code) would be caught by this same test.
        self.assertEqual(
            empty_result.returncode,
            0,
            f"an empty-store CLI run must stay fail-open (exit 0); "
            f"stderr={empty_result.stderr!r}",
        )

        empty_payload = _parse_outcome_payload(empty_result.stdout)
        sound_payload = _parse_outcome_payload(sound_result.stdout)
        self.assertNotEqual(
            empty_payload.get("outcome"),
            sound_payload.get("outcome"),
            "the real CLI's printed outcome — the value a real caller (e.g. the "
            "future UXP-700c-3 gate) consumes in control flow — must differ "
            f"between the two runs; empty stderr={empty_result.stderr!r}",
        )
        self.assertEqual(
            empty_payload.get("outcome"),
            _EXPECTED_OUTCOME_EMPTY,
            f"the real CLI must print the '{_EXPECTED_OUTCOME_EMPTY}' outcome to "
            "stdout when it examined zero artifacts",
        )
        self.assertIn("empty_types", empty_payload)
        self.assertEqual(
            sorted(empty_payload["empty_types"]),
            sorted(_EXPECTED_EMPTY_TYPES),
            "the real CLI must name all three empty artifact types",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
