"""
Tests for reference_pattern resolution failure modes and real-artifact emission.

Companion to test_implementation_notes_emission.py, which covers the
single-match happy path and the zero-match error. This file adds the three
things that file does not assert:

- an AMBIGUOUS pattern (two or more matches) raises an authoring error naming
  the AC id, the pattern, and every match (BO-2000c-3-i)
- NO ``## Implementation Notes`` section is emitted on either failure path —
  the error is not caught and downgraded into a raw pattern in the body
  (BO-2000c-3-i)
- the resolved concrete path reaches the ticket through the PRODUCTION CLI,
  not via a direct _build_ticket_body call (BO-2000c-3)

Covers: BO-2000c-3, BO-2000c-3-i
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    # The mixins below are only ever mixed into a unittest.TestCase, and they
    # call its addCleanup/skipTest. Declaring that base statically lets a type
    # checker resolve those methods; at runtime the base stays ``object`` so the
    # mixins compose freely and unittest never collects a mixin as a test case
    # in its own right.
    _MixinBase = unittest.TestCase
else:
    _MixinBase = object

# ---------------------------------------------------------------------------
# Path bootstrap — make scripts/ importable
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.ac_store.generate_ticket_from_ac import _build_ticket_body  # noqa: E402

_GENERATOR_CLI = os.path.join(
    _REPO_ROOT, "scripts", "ac_store", "generate_ticket_from_ac.py"
)
_REAL_INDEX = os.path.join(
    _REPO_ROOT, "docs", "acceptance-criteria", "index.yaml"
)

# Basenames of the glob targets the fixtures create. Mirrors the ready-made
# audit probes (solo_* = one match, refmod_* = two matches, nosuchthing_* =
# zero matches) so the unit layer and the behavioural CLI probe agree.
_SOLO_TARGET = "solo_unique_target.py"
_MULTI_TARGETS = ("refmod_alpha.py", "refmod_beta.py")


def _make_ac_with_pattern(ac_id: str, reference_pattern: str) -> dict:
    """Build a minimal AC record whose it_requirements carries a reference_pattern."""
    return {
        "id": ac_id,
        "title": "Reference-pattern resolution probe",
        "criteria": (
            "Given an AC whose it_requirements names a reference file via a "
            "reference pattern, the generator resolves it to a concrete path."
        ),
        "assigned_agent": "python-coder",
        "component": "build-orchestration",
        "components": ["build_orchestration"],
        "level": "L2",
        "status": "active",
        "estimated_complexity": "M",
        "it_requirements": {
            "reference_pattern": reference_pattern,
            "n_location_rule": "Resolve before emitting.",
        },
    }


class _GlobFixtureMixin(_MixinBase):
    """Creates a temp directory holding the three glob-target shapes."""

    def _make_glob_dir(self) -> str:
        tmpdir = tempfile.mkdtemp(prefix="gtfa_refpattern_")
        self.addCleanup(shutil.rmtree, tmpdir, True)
        for name in (_SOLO_TARGET, *_MULTI_TARGETS):
            target = os.path.join(tmpdir, name)
            try:
                with open(target, "w", encoding="utf-8") as fh:
                    fh.write("# glob-resolution fixture\n")
            except OSError as exc:
                self.skipTest(f"Could not create glob fixture {name}: {exc}")
        return tmpdir


class TestAmbiguousReferencePatternIsAnAuthoringError(
    _GlobFixtureMixin, unittest.TestCase
):
    """BO-2000c-3-i: a pattern matching MORE THAN ONE file must not be guessed at."""

    def test_pattern_matching_more_than_one_file_raises_an_authoring_error(self):
        # covers: BO-2000c-3-i
        """A reference_pattern matching two files must raise ValueError rather than
        silently picking matches[0].

        glob returns os.scandir order, so matches[0] is an arbitrary,
        non-deterministic file. Writing it into the ticket as though it were
        the answer is worse than emitting the raw glob, because it looks
        correct. The error must name the AC id, the pattern, AND every match,
        so the author can narrow the pattern without re-running the glob.
        """
        glob_dir = self._make_glob_dir()
        pattern = os.path.join(glob_dir, "refmod_*.py")
        ac = _make_ac_with_pattern("BO-2000c-3-i", pattern)

        with self.assertRaises(ValueError) as ctx:
            _build_ticket_body(ac, "BO-2000c-3-i")

        err_msg = str(ctx.exception)
        self.assertIn(
            "BO-2000c-3-i",
            err_msg,
            f"The authoring error must name the AC id. Error was: {err_msg!r}",
        )
        self.assertIn(
            "refmod_*.py",
            err_msg,
            f"The authoring error must name the ambiguous pattern. Error was: {err_msg!r}",
        )
        for match_name in _MULTI_TARGETS:
            self.assertIn(
                match_name,
                err_msg,
                "The authoring error must list EVERY match so the author can see "
                f"what made the pattern ambiguous. {match_name!r} missing from: {err_msg!r}",
            )

    def test_single_match_pattern_still_resolves(self):
        # covers: BO-2000c-3
        """Guard against over-correction: exactly one match must still resolve,
        not be rejected by an off-by-one length check."""
        glob_dir = self._make_glob_dir()
        pattern = os.path.join(glob_dir, "solo_*.py")
        ac = _make_ac_with_pattern("BO-2000c-3", pattern)

        body = _build_ticket_body(ac, "BO-2000c-3")

        self.assertIn(
            _SOLO_TARGET,
            body,
            "A pattern matching exactly one file must still resolve to that path.",
        )
        self.assertNotIn(
            "solo_*.py",
            body,
            "The raw glob must not survive into the ticket body.",
        )


class _CliProbeMixin(_GlobFixtureMixin):
    """Runs the production generator CLI against a real on-disk AC store."""

    def _make_ac_store(self, ac_id: str, reference_pattern: str) -> str:
        """Write a real AC YAML into a real store layout and return the store root.

        The record is serialised with yaml.safe_dump — the same writer the real
        store uses — so the CLI parses the artifact in its production shape
        rather than a hand-indented literal.
        """
        store = tempfile.mkdtemp(prefix="gtfa_acstore_")
        self.addCleanup(shutil.rmtree, store, True)
        feature_dir = os.path.join(store, "build-orchestration", "BO-2000-probe")
        try:
            os.makedirs(feature_dir, exist_ok=True)
            shutil.copy(_REAL_INDEX, os.path.join(store, "index.yaml"))
            with open(
                os.path.join(feature_dir, f"{ac_id}.yaml"), "w", encoding="utf-8"
            ) as fh:
                yaml.safe_dump(
                    _make_ac_with_pattern(ac_id, reference_pattern),
                    fh,
                    sort_keys=False,
                )
        except OSError as exc:
            self.skipTest(f"Could not build temp AC store: {exc}")
        return store

    def _run_cli(self, ac_id: str, store: str) -> subprocess.CompletedProcess:
        """Invoke the generator CLI as a fresh subprocess (production entry point)."""
        try:
            return subprocess.run(
                [
                    sys.executable,
                    _GENERATOR_CLI,
                    "--ac",
                    ac_id,
                    "--ac-root",
                    store,
                    "--dry-run",
                ],
                cwd=_REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self.skipTest(f"Could not invoke generator CLI: {exc}")
            raise


class TestResolvedPathReachesTicketViaCli(_CliProbeMixin, unittest.TestCase):
    """BO-2000c-3, real_artifact angle: the resolved path must survive to the artifact."""

    def test_resolved_path_reaches_the_ticket_via_the_generator_cli(self):
        # covers: BO-2000c-3
        """PRODUCTION ENTRY POINT: run generate_ticket_from_ac.py against a real
        on-disk AC YAML and read the Implementation Notes out of what the CLI
        actually emitted.

        Guards against a fix that is correct in the helper but never reaches the
        emitted artifact — the direct _build_ticket_body tests cannot see that gap.
        """
        glob_dir = self._make_glob_dir()
        pattern = os.path.join(glob_dir, "solo_*.py")
        store = self._make_ac_store("BO-2000c-3", pattern)

        result = self._run_cli("BO-2000c-3", store)

        self.assertEqual(
            result.returncode,
            0,
            f"CLI should succeed on a single-match pattern. stderr: {result.stderr!r}",
        )
        self.assertIn(
            "## Implementation Notes",
            result.stdout,
            "The CLI-emitted ticket must carry an Implementation Notes section.",
        )
        self.assertIn(
            _SOLO_TARGET,
            result.stdout,
            "The CLI-emitted ticket must carry the RESOLVED concrete path.",
        )
        self.assertNotIn(
            "solo_*.py",
            result.stdout,
            "The CLI-emitted ticket must not carry the raw glob pattern.",
        )


class TestNoImplementationNotesEmittedOnFailure(_CliProbeMixin, unittest.TestCase):
    """BO-2000c-3-i, boundary angle: the 'does not silently emit' clause.

    The existing tests assert the raise. They do NOT assert non-emission — which
    is the boundary that stops the error being raised and then swallowed by a
    caller that emits the unresolved value anyway. These run through the CLI so
    a swallow anywhere between the resolver and the artifact is visible.
    """

    def _assert_no_notes_emitted(self, result, raw_pattern_fragment: str) -> None:
        self.assertNotEqual(
            result.returncode,
            0,
            "The CLI must fail on an unresolvable reference_pattern, not emit a ticket.",
        )
        self.assertNotIn(
            "## Implementation Notes",
            result.stdout,
            "No Implementation Notes section may be emitted on the failure path. "
            f"stdout was: {result.stdout!r}",
        )
        self.assertNotIn(
            raw_pattern_fragment,
            result.stdout,
            "The raw unresolved pattern must never reach the ticket body. "
            f"stdout was: {result.stdout!r}",
        )

    def test_no_implementation_notes_emitted_on_zero_match(self):
        # covers: BO-2000c-3-i
        """Zero matches: error surfaces, and no section reaches the artifact."""
        glob_dir = self._make_glob_dir()
        pattern = os.path.join(glob_dir, "nosuchthing_*.py")
        store = self._make_ac_store("BO-2000c-3-i", pattern)

        result = self._run_cli("BO-2000c-3-i", store)

        self._assert_no_notes_emitted(result, "nosuchthing_*.py")

    def test_no_implementation_notes_emitted_on_multi_match(self):
        # covers: BO-2000c-3-i
        """Two matches: error surfaces, and no section — and no arbitrarily
        chosen match — reaches the artifact."""
        glob_dir = self._make_glob_dir()
        pattern = os.path.join(glob_dir, "refmod_*.py")
        store = self._make_ac_store("BO-2000c-3-i", pattern)

        result = self._run_cli("BO-2000c-3-i", store)

        self._assert_no_notes_emitted(result, "refmod_*.py")
        for match_name in _MULTI_TARGETS:
            self.assertNotIn(
                match_name,
                result.stdout,
                f"An arbitrary match {match_name!r} must not be emitted as though "
                "it were the resolved answer.",
            )


if __name__ == "__main__":
    unittest.main()
