"""
MODULE: test_acd_1200b_5_ii
GOAL: Regression tests for ACD-1200b-5-ii / KI-ACS-017 — approve_acs.py must
      not corrupt a leaf AC whose amended_by block already holds a multi-line
      scalar with blank lines, and must never report success for output it
      cannot itself parse.

BUSINESS CONTEXT: On 2026-08-31, approve_acs.py corrupted 5 of 31 GE-123
      records while reporting "promoted <id>" and rc=0 for all 31. Root cause
      part 1: _AMENDED_BY_RE only continues over lines starting with a
      space/tab or a dash, so a blank line inside a multi-line quoted scalar
      truncates the match early, splicing the rebuilt block over only part of
      the original amended_by region and stranding the remainder as invalid
      top-level text. Root cause part 2: _promote_leaf writes, prints
      "promoted <id>", and returns 0 without ever re-parsing its own output.

ARCHITECTURE: Tests write real YAML files in a TemporaryDirectory. The
      multi-line amended_by fixture is NOT hand-typed — it is read verbatim
      from the real on-disk record that KI-ACS-017 actually corrupted
      (docs/acceptance-criteria/guardrail-engine/GE-123-suppression-narrows-
      never-disables/GE-123a-4.yaml), per the Fixture Authenticity Rule. A
      hand-indented approximation would reproduce the exact bias that let the
      original defect through: real amended_by blocks the store writes today
      contain blank lines separating paragraphs inside a single-quoted
      scalar, and only that shape trips the regex truncation.

      Verified by direct reproduction before authoring these tests: running
      the UNMODIFIED approve_acs.py._promote_leaf() against this exact
      fixture raises
          yaml.parser.ParserError: expected <block end>, but found '<scalar>'
      when the written file is re-parsed, while _promote_leaf itself still
      printed "promoted GE-123a-4 readiness reviewed -> approved" and
      returned 0 — the precise KI-ACS-017 symptom.

TICKET AC: ACD-1200b-5-ii
"""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

# approve_acs.py already exists (this is a bug-fix AC, not new-module TDD), so
# this import succeeds today. The RED state for these tests comes from the
# assertions below failing against the current, buggy behaviour — not from
# ImportError.
import approve_acs as approve_acs_module  # noqa: E402
from approve_acs import _promote_leaf  # noqa: E402

# The real on-disk record KI-ACS-017 corrupted. Its amended_by holds a single
# entry whose `entry:` value is a multi-line single-quoted scalar with blank
# lines between paragraphs (file lines 107, 113, 120) — exactly the shape
# that defeats _AMENDED_BY_RE.
_REAL_MULTILINE_FIXTURE_SOURCE = (
    _REPO_ROOT
    / "docs"
    / "acceptance-criteria"
    / "guardrail-engine"
    / "GE-123-suppression-narrows-never-disables"
    / "GE-123a-4.yaml"
)


# ---------------------------------------------------------------------------
# Fixture helper — real artifact, not a hand-indented literal
# ---------------------------------------------------------------------------


def _load_real_multiline_leaf_text() -> str:
    """Return the real GE-123a-4.yaml bytes with readiness flipped to reviewed.

    Sourced verbatim from disk. The only mutation performed here is the same
    single targeted string replacement approve_acs.py itself would perform in
    reverse (approved -> reviewed instead of reviewed -> approved), so the
    fixture is eligible for promotion. Every other byte — including the
    blank lines inside the amended_by scalar — is untouched.
    """
    raw = _REAL_MULTILINE_FIXTURE_SOURCE.read_text(encoding="utf-8")
    assert "readiness: approved" in raw, (
        "expected the real GE-123a-4.yaml record to carry readiness: approved; "
        "the source record's shape may have changed — re-derive this fixture "
        "from the current on-disk record rather than adjusting this assertion"
    )
    return raw.replace("readiness: approved", "readiness: reviewed", 1)


def _write_real_multiline_leaf(ac_root: Path, ac_id: str = "GE-123a-4") -> Path:
    """Materialize the real multi-line-history fixture under ac_root."""
    subdir = ac_root / "guardrail-engine" / "GE-123-suppression-narrows-never-disables"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    path.write_text(_load_real_multiline_leaf_text(), encoding="utf-8")
    return path


def _unparseable_amended_by_block(existing, new_entry):  # noqa: ANN001, ARG001
    """Stand-in for _build_amended_by_block that returns invalid YAML text.

    Used to drive the "the mechanism's own output does not parse" path
    deterministically, so the guard is tested directly rather than only via
    today's regex-truncation bug (which the fix might close by a different
    route than the one these two tests exercise).
    """
    return "amended_by: [this: is not, valid\n"


class TestApproveAcsMultilineAmendedBy:
    """Regression coverage for KI-ACS-017 (ACD-1200b-5-ii)."""

    def test_multiline_amended_by_record_survives_promotion_and_reparses(self) -> None:
        # covers: ACD-1200b-5-ii
        # angle: real_artifact
        """A reviewed leaf whose amended_by already holds a multi-line, blank-
        line-containing entry (the real GE-123a-4 shape) must still parse as a
        single YAML document after promotion.

        What must be implemented for this test to pass:
        - _AMENDED_BY_RE (or its replacement) must consume the ENTIRE
          amended_by block even when a continuation line inside a multi-line
          scalar is blank, so the rebuilt block is spliced over the whole
          original region and nothing is stranded as invalid top-level text.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            leaf_path = _write_real_multiline_leaf(ac_root)

            result = _promote_leaf(leaf_path)

            written = leaf_path.read_text(encoding="utf-8")
            try:
                data_after = yaml.safe_load(written)
            except yaml.YAMLError as exc:
                pytest.fail(
                    "promotion produced unparseable YAML (KI-ACS-017 "
                    f"regression): {exc}\n--- first 2000 chars written ---\n"
                    f"{written[:2000]}"
                )

            assert result == 0, f"_promote_leaf must return 0 on success, got {result}"
            assert isinstance(data_after, dict)
            assert data_after["readiness"] == "approved"

    def test_promotion_appends_one_entry_and_preserves_prior_multiline_text(self) -> None:
        # covers: ACD-1200b-5-ii
        # angle: criterion
        """After promotion, amended_by holds every prior entry (full text,
        blank lines included) plus exactly one new approval entry, and
        readiness is the only other field that differs from the pre-run
        record.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            leaf_path = _write_real_multiline_leaf(ac_root)

            data_before = yaml.safe_load(leaf_path.read_text(encoding="utf-8"))
            prior_entries = data_before["amended_by"]
            assert len(prior_entries) == 1, (
                "sanity check on the real fixture's shape: GE-123a-4 is expected "
                f"to carry exactly one prior amended_by entry, found {len(prior_entries)}"
            )
            # YAML single-quoted-scalar line folding turns each blank line in the
            # source into exactly one "\n" in the parsed string (not "\n\n" — a
            # single line break folds to a space, a blank line folds to "\n").
            # The real GE-123a-4 record has three blank lines inside this scalar
            # (source lines 107, 113, 120), so the parsed text must contain
            # exactly three folded newlines.
            assert prior_entries[0]["entry"].count("\n") == 3, (
                "sanity check: the prior entry's text must contain exactly three "
                "folded (blank-line-derived) newlines — this is the shape that "
                "triggers KI-ACS-017; if this assertion fails the fixture no "
                "longer reproduces the bug and must be re-derived from the real "
                f"record. Got: {prior_entries[0]['entry']!r}"
            )

            _promote_leaf(leaf_path)

            data_after = yaml.safe_load(leaf_path.read_text(encoding="utf-8"))
            amended_after = data_after.get("amended_by")

            assert isinstance(amended_after, list), (
                f"amended_by must still be a list after promotion, got {amended_after!r}"
            )
            assert len(amended_after) == len(prior_entries) + 1, (
                f"expected exactly one new amended_by entry appended to the "
                f"{len(prior_entries)} prior entries; got {len(amended_after)} total"
            )

            # The prior entry's full multi-line text, blank lines included,
            # must survive byte-for-byte in the re-parsed structure.
            assert amended_after[0] == prior_entries[0], (
                "the pre-existing multi-line amended_by entry must be preserved "
                "exactly (full text, including its blank lines); got "
                f"{amended_after[0]!r} instead of {prior_entries[0]!r}"
            )

            # readiness is the only other field that may differ.
            for field, value_before in data_before.items():
                if field in ("readiness", "amended_by"):
                    continue
                assert data_after.get(field) == value_before, (
                    f"field {field!r} must not be altered by promotion "
                    f"(was {value_before!r}, now {data_after.get(field)!r})"
                )
            assert data_after["readiness"] == "approved"

    def test_unparseable_output_restores_original_bytes_and_exits_nonzero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # covers: ACD-1200b-5-ii
        # angle: failure
        """When the text the mechanism is about to store does not parse as
        YAML, the file on disk must be byte-identical to its pre-run content
        and the run must exit non-zero.

        Drives the path deterministically via a monkeypatched
        _build_amended_by_block, so the guard itself is constrained rather
        than the regex-truncation bug that happens to reach it today.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            leaf_path = _write_real_multiline_leaf(ac_root)
            original_bytes = leaf_path.read_bytes()

            monkeypatch.setattr(
                approve_acs_module,
                "_build_amended_by_block",
                _unparseable_amended_by_block,
            )

            result = _promote_leaf(leaf_path)

            assert leaf_path.read_bytes() == original_bytes, (
                "the record left on disk must be byte-identical to the record "
                "as it stood before the run when the mechanism's own output "
                "does not parse as YAML"
            )
            assert result != 0, (
                f"_promote_leaf must exit non-zero when its own output does "
                f"not parse; got {result}"
            )

    def test_no_promoted_line_reported_for_a_record_left_unwritten(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # covers: ACD-1200b-5-ii
        # angle: failure
        """The report for an unparseable-output record must name it as a
        failure and must contain no line describing it as promoted, so the
        report can be read as proof of the write.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            leaf_path = _write_real_multiline_leaf(ac_root)

            monkeypatch.setattr(
                approve_acs_module,
                "_build_amended_by_block",
                _unparseable_amended_by_block,
            )

            captured_stdout = io.StringIO()
            captured_stderr = io.StringIO()
            with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
                _promote_leaf(leaf_path)

            stdout_text = captured_stdout.getvalue()
            stderr_text = captured_stderr.getvalue()

            assert "promoted" not in stdout_text, (
                "no line describing this record as promoted may appear anywhere "
                f"in the run's report; got stdout: {stdout_text!r}"
            )
            assert "GE-123a-4" in (stdout_text + stderr_text), (
                "the run must name the failing record so the report can be "
                f"read as proof of the write; got stdout: {stdout_text!r}, "
                f"stderr: {stderr_text!r}"
            )

    def test_cli_run_over_a_multiline_history_tree_exits_zero_and_all_records_parse(
        self,
    ) -> None:
        # covers: ACD-1200b-5-ii
        # angle: reachability
        """Invoke approve_acs.py as a subprocess (the real entry point people
        run) over a tree whose reviewed leaf carries the real multi-line
        amended_by history; assert exit status 0 AND that the touched record
        re-parses.

        This is the only test in this file that runs the mechanism as an
        external process rather than by import: the second half of
        KI-ACS-017 (a success-shaped exit code over a file the run just
        destroyed) is observable only from outside — a direct-import call
        that only checks the return value would miss it exactly as the
        2026-08-31 run did (rc=0 reported for all 31 records, 5 of them
        actually corrupted).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            ac_root = Path(tmpdir)
            _write_real_multiline_leaf(ac_root, ac_id="GE-123a-4")

            script_path = _SCRIPTS_DIR / "approve_acs.py"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--ac",
                    "GE-123a-4",
                    "--ac-root",
                    str(ac_root),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            assert proc.returncode == 0, (
                f"CLI run must exit 0 over a multi-line-history tree; "
                f"stdout: {proc.stdout!r}, stderr: {proc.stderr!r}"
            )

            leaf_path = (
                ac_root
                / "guardrail-engine"
                / "GE-123-suppression-narrows-never-disables"
                / "GE-123a-4.yaml"
            )
            written = leaf_path.read_text(encoding="utf-8")
            try:
                yaml.safe_load(written)
            except yaml.YAMLError as exc:
                pytest.fail(
                    "CLI reported success (rc=0) but the written record does "
                    f"not parse as YAML — this is KI-ACS-017: {exc}\n"
                    f"stdout: {proc.stdout!r}\n"
                    f"--- first 2000 chars written ---\n{written[:2000]}"
                )
