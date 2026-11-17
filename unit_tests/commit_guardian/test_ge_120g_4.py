"""
Tests for templates/scripts/commit_guardian/check_negative_control_liveness.py

GE-120g-4: `main()` calls `_write_manifest(manifest_path, data)`
unconditionally on every run, and `_write_manifest` does
`json.dumps(data, indent=2)` with `ensure_ascii` defaulting True. So a run
that changes nothing still rewrites the manifest it was handed as
`--manifest`, and a write that round-trips through `json.dumps` escapes every
non-ASCII character in the document's prose (measured: 0 -> 110 escaped
em-dashes from a single invocation against a repaired deployed config).

These tests use the REAL deployed manifest
(`.leafcutter/config/commit_guardian/commit_guardian.json` under the repo
root -- the pristine deploy-time copy build.py produced, 0 unresolved
`{{` tokens, literal em-dashes) copied to a temp path, never the repo's own
deployed file in place.

PRE-FLIGHT FACT, verified manually before writing test 3 (2026-10-07,
this checkout): the deployed manifest's ONLY `negative_control` declaration
(`check-negative-control-liveness` itself) was `not_applicable: true` and no
other hook carried one, so the run printed ZERO result lines (exit 0, stdout
`""`). SUPERSEDED by BP-1300e-1: the manifest now also declares a real
`negative_control` on `check-lint-gate`, so the run prints one
`NEGATIVE_CONTROL_RESULT` line for it (state passing, exit 0). Test 3 no
longer hard-codes a count; it derives the examinable hooks from the copied
manifest itself (see `_examinable_check_ids`).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _script_path() -> Path:
    """Resolve the liveness-check script path relative to this test file.

    This test lives at unit_tests/commit_guardian/test_ge_120g_4.py; the
    script lives at
    templates/scripts/commit_guardian/check_negative_control_liveness.py.
    Walk up two levels to reach the repo root, then descend into templates.
    """
    repo_root = Path(__file__).resolve().parents[2]
    return (
        repo_root
        / "templates"
        / "scripts"
        / "commit_guardian"
        / "check_negative_control_liveness.py"
    )


def _deployed_manifest_path() -> Path:
    """Resolve the real, pristine, deploy-time manifest build.py produced.

    This is the fixture source for every test below -- never a hand-typed
    literal, and never the repo's own deployed file run in place (we always
    copy it to a temp path first).
    """
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / ".leafcutter" / "config" / "commit_guardian" / "commit_guardian.json"


def _copy_manifest_to_tmp(tmp_dir: str) -> Path:
    """Copy the real deployed manifest into *tmp_dir* and return its path."""
    source = _deployed_manifest_path()
    dest = Path(tmp_dir) / "commit_guardian.json"
    shutil.copyfile(source, dest)
    return dest


def _run_liveness_check(manifest_path: Path) -> subprocess.CompletedProcess:
    """Run the liveness check as a subprocess against *manifest_path*.

    Invoked directly (never through run_hook.py) per this AC's own test
    requirements.
    """
    return subprocess.run(
        [sys.executable, str(_script_path()), "--manifest", str(manifest_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        # Declared negative_control commands are repo-root-relative
        # (`python .leafcutter/scripts/...`), so run from the repo root
        # regardless of the pytest invocation's cwd.
        cwd=str(Path(__file__).resolve().parents[2]),
    )


def _examinable_check_ids(manifest_path: Path) -> list[str]:
    """Ids of hooks the check examines, in manifest order.

    Mirrors the script's `_build_records()` rule: a hook is examined when its
    `negative_control` is a dict that is not `not_applicable` and the hook
    has a usable (non-blank string) `id`.
    """
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    ids: list[str] = []
    for hook in data["hooks_manifest"]["hooks"]:
        negative_control = hook.get("negative_control")
        if not isinstance(negative_control, dict) or negative_control.get("not_applicable"):
            continue
        hook_id = hook.get("id")
        if isinstance(hook_id, str) and hook_id.strip():
            ids.append(hook_id)
    return ids


class TestLivenessRunLeavesManifestUnchanged(unittest.TestCase):
    """Scenario: A run that changes nothing leaves the file byte-for-byte
    identical."""

    def test_liveness_run_leaves_an_unchanged_manifest_byte_identical(self) -> None:
        # covers: GE-120g-4
        # angle: criterion
        """Hash the temp manifest copy's bytes, run the check, re-hash.

        Asserts the digests are equal -- the only reliable way for a judging
        check to leave a file alone is not to write it, and a run that finds
        no `currently` block needing an update is the overwhelmingly common
        case.

        IMPORTANT: this asserts on the BYTE DIGEST, not an em-dash count.
        Measured: `json.dumps(data, indent=2, ensure_ascii=False) + "\\n"`
        does NOT reproduce this file byte-for-byte even with ensure_ascii
        fixed -- the file carries a hand-indented block json.dumps would
        re-render differently, so an em-dash-only assertion would pass a fix
        that still reformats the file and still trips check-output-drift.

        RED today: `main()` calls `_write_manifest` unconditionally, and the
        measured round-trip differs from the original bytes.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = _copy_manifest_to_tmp(tmp_dir)
            original_bytes = manifest_path.read_bytes()
            original_digest = hashlib.sha256(original_bytes).hexdigest()

            result = _run_liveness_check(manifest_path)

            new_bytes = manifest_path.read_bytes()
            new_digest = hashlib.sha256(new_bytes).hexdigest()

            self.assertEqual(
                original_digest,
                new_digest,
                msg=(
                    "Expected the manifest's bytes to be unchanged after a "
                    "run that found nothing to update, but the sha256 "
                    f"digest changed ({original_digest} -> {new_digest}).\n"
                    f"Check exit code: {result.returncode}\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )


class TestLivenessRunPreservesNonAsciiCharacters(unittest.TestCase):
    """Scenario: A run that must record something preserves the characters
    it read."""

    def test_liveness_run_preserves_non_ascii_characters(self) -> None:
        # covers: GE-120g-4
        # angle: criterion
        """After a run, the manifest still contains its literal non-ASCII
        characters (em-dashes) and zero occurrences of the escaped form.

        The six-character escape sequence is built at runtime from parts
        (a literal backslash concatenated with "u2014") rather than written
        as a `\\u2014`-shaped literal in this source file, so the test file
        itself contains no escape that could confuse a later grep for real
        escaped em-dashes.

        RED today: `_write_manifest`'s `json.dumps(data, indent=2)` leaves
        `ensure_ascii` at its default of True, so every one of the deployed
        manifest's 110 literal em-dashes becomes a `\\u2014` escape on the
        very first run.
        """
        em_dash = chr(0x2014)
        escaped_em_dash = "\\" + "u2014"

        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = _copy_manifest_to_tmp(tmp_dir)
            original_text = manifest_path.read_text(encoding="utf-8")
            original_literal_count = original_text.count(em_dash)
            # Sanity-check the fixture itself carries real em-dashes to lose
            # -- if this ever reaches 0, the test proves nothing.
            self.assertGreater(
                original_literal_count,
                0,
                msg=(
                    "Expected the deployed manifest fixture to contain at "
                    "least one literal em-dash before the run; found none. "
                    "The fixture may have changed -- re-verify this test "
                    "still measures something real."
                ),
            )

            result = _run_liveness_check(manifest_path)

            new_text = manifest_path.read_text(encoding="utf-8")
            new_literal_count = new_text.count(em_dash)
            new_escaped_count = new_text.count(escaped_em_dash)

            self.assertGreater(
                new_literal_count,
                0,
                msg=(
                    "Expected literal em-dash characters to survive the "
                    f"run; found {new_literal_count}.\n"
                    f"Check exit code: {result.returncode}\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
            self.assertEqual(
                new_escaped_count,
                0,
                msg=(
                    "Expected zero backslash-u escapes of em-dashes after "
                    f"the run; found {new_escaped_count}.\n"
                    f"Check exit code: {result.returncode}\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )


class TestLivenessRunStillReportsVerdict(unittest.TestCase):
    """Scenario: The verdict is unaffected -- this criterion governs what the
    check writes, not what it decides."""

    def test_liveness_run_still_reports_its_verdict(self) -> None:
        # covers: GE-120g-4
        # angle: criterion
        """GREEN ON ARRIVAL -- scope fence, not evidence the write-skip fix
        landed.

        The cheapest way to satisfy the two RED tests above is to delete the
        write path entirely, including the case where the check genuinely
        has something to record. This test does not fully forbid that (a
        test that forced a real update would), but it does catch a fix that
        breaks the check's stdout or exit code on the way past.

        Verified fact about THIS real fixture (re-measured with BP-1300e-1):
        the deployed manifest now carries a REAL, examinable
        `negative_control` on `check-lint-gate` (state passing), alongside
        the `not_applicable: true` one on this check itself. So the verdict
        is exit 0 with exactly one `NEGATIVE_CONTROL_RESULT` stdout line per
        examinable hook. The expected set is DERIVED from the copied
        manifest using `_build_records()`'s own rule (a `negative_control`
        dict that is not `not_applicable`, on a hook with a usable string
        `id`) rather than hard-coded, so the next hook that gains a negative
        control does not break this test again.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_path = _copy_manifest_to_tmp(tmp_dir)
            expected_ids = _examinable_check_ids(manifest_path)

            result = _run_liveness_check(manifest_path)

            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "Expected exit 0 (every examined hook ended passing), "
                    f"got {result.returncode}.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
            lines = result.stdout.splitlines()
            for line in lines:
                self.assertTrue(
                    line.startswith("NEGATIVE_CONTROL_RESULT check_id="),
                    msg=f"Unexpected non-result line on stdout: {line!r}",
                )
            reported = [
                re.match(r"NEGATIVE_CONTROL_RESULT check_id=(\S+) state=(\S+) ", line)
                for line in lines
            ]
            self.assertTrue(
                all(reported),
                msg=f"Malformed result line(s) on stdout: {result.stdout!r}",
            )
            matches = [m for m in reported if m is not None]
            self.assertEqual(
                [m.group(1) for m in matches],
                expected_ids,
                msg=(
                    "Expected exactly one NEGATIVE_CONTROL_RESULT line per "
                    "examinable hook, in manifest order.\n"
                    f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                ),
            )
            self.assertEqual(
                [m.group(2) for m in matches],
                ["passing"] * len(expected_ids),
                msg=f"Expected every reported state to be passing: {result.stdout!r}",
            )


def _load_script_module():
    """Import the liveness-check script as a module, by path.

    The script is not importable as a package member from here, so it is
    loaded from its file location. Used only by the direct `_write_manifest`
    test below, which needs to call the writer on a document that genuinely
    differs -- something no run against the real fixture can produce (see
    the PRE-FLIGHT FACT in this module's docstring).

    Returns:
        The loaded module object.
    """
    path = _script_path()
    spec = importlib.util.spec_from_file_location("_ncl_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestWriteManifestPreservesNonAsciiOnAGenuineWrite(unittest.TestCase):
    """The `ensure_ascii` half of GE-120g-4, exercised on a real write.

    The other three tests in this module cannot reach it. Against the real
    deployed fixture `_build_records` mutates nothing, so after the fix
    `_write_manifest` is never called at all and the file survives because
    it was never written -- not because a write round-tripped correctly.
    That leaves `ensure_ascii=False` shipping untested, which this test
    exists to close. It calls the writer directly with a document that
    contains non-ASCII prose, which is the only way to force the path.
    """

    def test_write_manifest_writes_non_ascii_characters_literally(self) -> None:
        # covers: GE-120g-4
        # angle: criterion
        """A genuine write keeps non-ASCII prose as characters, not escapes.

        RED before the fix: `json.dumps` defaults to `ensure_ascii=True`, so
        the em-dash is emitted as its six-character escape.
        """
        module = _load_script_module()
        em_dash = chr(0x2014)
        document = {
            "_comment": f"Commit Guardian {em_dash} Central Configuration",
            "hooks_manifest": {"hooks": []},
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "commit_guardian.json"
            module._write_manifest(target, document)
            written = target.read_text(encoding="utf-8")

        self.assertIn(
            em_dash,
            written,
            msg=(
                "Expected the literal em-dash character to survive a genuine "
                f"_write_manifest call. Got: {written!r}"
            ),
        )
        # Built from parts so this test file contains no literal escape of
        # its own that a later grep over the suite could mistake for one.
        escape = "\\" + "u2014"
        self.assertNotIn(
            escape,
            written,
            msg=(
                "Expected NO escaped em-dash in the written manifest -- "
                "ensure_ascii must be False on the write path. Got: "
                f"{written!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-07 [test-writer/GE-120g-4]: Initial TDD stubs. Three tests per
  GE-120g-4's test_spec, all against the REAL deployed manifest
  (.leafcutter/config/commit_guardian/commit_guardian.json) copied to a
  temp path:
    1. byte-identical round-trip (RED -- json.dumps re-renders the file)
    2. non-ASCII preservation (RED -- ensure_ascii defaults True, 110
       em-dashes become escapes)
    3. verdict unaffected (GREEN ON ARRIVAL -- scope fence; this specific
       fixture examines zero hooks today, so the verdict asserted is exit 0
       / empty stdout, verified by direct manual run before writing the
       test, not invented)
====================================================================
"""
