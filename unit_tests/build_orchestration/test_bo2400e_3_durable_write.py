"""
MODULE: unit_tests/build_orchestration/test_bo2400e_3_durable_write.py
GOAL: RED behavioral tests pinning the durability contract required by
    BO-2400e-3 -- "An interrupted update never destroys the work record it
    was updating" -- for
    scripts/build_orchestration/fast_lane.py::_update_ac_work_status (and,
    transitively, its three lifecycle callers: claim_build_set,
    release_claim, mark_done_built_acs).

BUSINESS CONTEXT: _update_ac_work_status currently opens the target AC YAML
    file with ``yaml_path.open("w", encoding="utf-8")`` -- which TRUNCATES
    the file to zero bytes the instant it is opened, before a single byte of
    the new content has been written. If the write is then interrupted or
    fails, the on-disk record is left empty. Since these YAML records are the
    build system's source of truth and are frequently untracked while being
    authored, this is a real data-loss defect, not a cosmetic one (see
    BO-2400e-3.yaml notes; CLAUDE.md "no destructive one-liners").

FAULT-INJECTION TECHNIQUE (deterministic, not timing-based): several tests
    below run the write in a real forked child process with
    ``resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))`` set BEFORE the
    write is attempted. This makes any write of more than zero bytes to the
    target file raise a genuine ``OSError: [Errno 27] File too large`` from
    the real ``write(2)`` syscall -- a real, reproducible, OS-enforced write
    failure against a real file, deterministic regardless of machine speed
    or scheduling (unlike a SIGKILL-after-N-milliseconds race, which is
    inherently timing-sensitive and flaky across machines). Reading the
    file's ORIGINAL content is unaffected by RLIMIT_FSIZE -- only writing is
    capped -- so the read phase of _update_ac_work_status always succeeds
    first, and the failure is hit exactly where the AC describes it: "the
    write fails partway through". No test here patches ``open()`` or
    otherwise doubles the filesystem; a double would be free to model an
    atomic replacement the current code does not perform, which is exactly
    the bug-hiding bias this AC's test_rationale warns against.

FIXTURE-AUTHENTICITY MANDATE: fixtures are copied byte-for-byte from real,
    on-disk, PO-reviewed AC YAML files in this same ticket's own directory
    (docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/)
    -- never hand-typed. Where a precondition requires work_status to be
    "todo" rather than the fixture's real current "in_progress" value,
    exactly that one line is rewritten (mirroring the KI-BO-003 suite's
    `_write_variant` convention) -- no other byte is fabricated. The
    concurrent-reader test additionally pads the real ``notes: |`` block with
    extra indented lines (a size-only edit) so a single write takes long
    enough for a real background reader thread to have a fighting chance of
    racing it.

Run with AC_ENFORCE_STRICT=1 to see the true (unmasked) result:

    AC_ENFORCE_STRICT=1 python3 -m pytest \\
        unit_tests/build_orchestration/test_bo2400e_3_durable_write.py -v
"""

from __future__ import annotations

import multiprocessing
import re
import resource
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

_AC_STORE_DIR = (
    _REPO_ROOT
    / "docs"
    / "acceptance-criteria"
    / "build-orchestration"
    / "BO-2400-fast-lane-build"
)

# Real, PO-reviewed AC YAML files belonging to this very ticket.
_AC_FIXTURE_SOURCE = _AC_STORE_DIR / "BO-2400e-3.yaml"
_AC_FIXTURE_SOURCE_2 = _AC_STORE_DIR / "BO-2400e-3-i.yaml"

_IMPORT_OK = False
_IMPORT_ERR = ""
_update_ac_work_status: Any = None
claim_build_set: Any = None

try:
    from fast_lane import (  # type: ignore[no-redef]
        _update_ac_work_status,
        claim_build_set,
    )

    _IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _IMPORT_ERR = str(_exc)


def _require_impl(test_case: unittest.TestCase) -> None:
    if not _IMPORT_OK:
        test_case.fail(
            "_update_ac_work_status / claim_build_set not importable from "
            f"fast_lane. Import error: {_IMPORT_ERR}"
        )


_WORK_STATUS_LINE_RE = re.compile(r"^work_status:.*$", re.MULTILINE)


def _rewrite_to_todo_precondition(source: Path) -> str:
    """Real fixture bytes with the column-0 work_status line rewritten to todo.

    KNOWN-DEFECT FIX (found while implementing BO-2400e-3, 2026-08-25): this
    originally hardcoded ``real_text.replace("work_status: in_progress",
    "work_status: todo", 1)`` on the assumption that the real, on-disk AC
    fixtures in this ticket's own directory are always currently
    ``in_progress`` while the ticket is being built. That assumption does
    not hold: the store is live and this ticket's own ACs may legitimately
    be released back to ``todo`` between when this suite was authored and
    when it runs (e.g. after a claim/release cycle), so the fixed-string
    match silently stops finding anything and the setup-sanity-check
    AssertionError fires on every test that uses it -- a false RED
    unrelated to the durability contract these tests exist to pin. The
    fix locates whatever the CURRENT column-0 work_status line actually is
    and rewrites its value to todo, rather than assuming one specific prior
    value -- still exactly one line rewritten, no other byte fabricated,
    matching the KI-BO-003 suite's `_write_variant` convention in spirit.
    """
    real_text = source.read_text(encoding="utf-8")
    match = _WORK_STATUS_LINE_RE.search(real_text)
    if match is None:
        msg = (
            f"Test setup sanity check: expected to find a column-0 "
            f"'work_status:' line in the real {source.name} fixture to "
            "rewrite to the todo precondition."
        )
        raise AssertionError(msg)
    return real_text[: match.start()] + "work_status: todo" + real_text[match.end() :]


def _induce_write_failure(yaml_path: str, new_status: str) -> None:
    """Run in a forked child: cap RLIMIT_FSIZE to 0 so the write raises a
    real, OS-enforced 'File too large' failure the instant it attempts to
    write a single byte -- deterministic, no timing involved. Reading the
    file first (to compute the update) is unaffected by RLIMIT_FSIZE.
    """
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    _update_ac_work_status(Path(yaml_path), new_status)


def _run_induced_failure(yaml_path: Path, new_status: str) -> int | None:
    """Run _induce_write_failure in a real child process; return its exit code."""
    ctx = multiprocessing.get_context("fork")
    proc = ctx.Process(target=_induce_write_failure, args=(str(yaml_path), new_status))
    proc.start()
    proc.join(timeout=15)
    return proc.exitcode


# ---------------------------------------------------------------------------
# Core durability contract: survives a write that fails partway
# ---------------------------------------------------------------------------


class TestRecordSurvivesInterruptedWrite(unittest.TestCase):
    """BO-2400e-3: a write that fails partway through must never destroy the
    record it was updating.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.fixture_path = self.tmp_path / "BO-2400e-3.yaml"
        todo_text = _rewrite_to_todo_precondition(_AC_FIXTURE_SOURCE)
        self.fixture_path.write_text(todo_text, encoding="utf-8")
        self.original_bytes = self.fixture_path.read_bytes()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_record_survives_a_write_that_fails_partway(self) -> None:
        # covers: BO-2400e-3
        """After a real, OS-enforced write failure partway through, the file
        on disk must still contain exactly its pre-update content --
        byte-identical, not merely "close enough" or "still valid YAML".

        RED today: _update_ac_work_status truncates the file at open("w"),
        so a write failure any time after that leaves an empty file, never
        the original bytes.
        """
        _require_impl(self)

        exitcode = _run_induced_failure(self.fixture_path, "done")
        self.assertNotEqual(
            exitcode,
            0,
            "Test setup sanity check: the induced RLIMIT_FSIZE=0 write "
            "failure must actually make the child process exit non-zero "
            "(an unhandled OSError), otherwise no real failure was induced.",
        )

        after = self.fixture_path.read_bytes()
        self.assertEqual(
            after,
            self.original_bytes,
            "A write that fails partway through must leave the record "
            "byte-identical to its pre-update content (BO-2400e-3). Got a "
            f"{len(after)}-byte file; expected {len(self.original_bytes)} "
            "bytes of untouched original content.",
        )

    def test_record_is_never_zero_length_after_a_failed_update(self) -> None:
        # covers: BO-2400e-3
        """The record's size on disk must be greater than zero after a
        failed update, and it must still parse as YAML.

        Stated separately from byte-identity because an empty file is the
        SPECIFIC observed failure mode of the current implementation
        (open("w") truncates at open time) -- a looser check could miss a
        regression that produces a short-but-nonempty stub instead.
        """
        _require_impl(self)

        _run_induced_failure(self.fixture_path, "done")

        size = self.fixture_path.stat().st_size
        self.assertGreater(
            size,
            0,
            "The record must never be left at zero length after a failed "
            "update (BO-2400e-3) -- got a zero-byte file, the exact "
            "data-loss failure mode this AC exists to prevent.",
        )
        try:
            data = yaml.safe_load(self.fixture_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            self.fail(
                "The record must still parse as valid YAML after a failed "
                f"update (BO-2400e-3). Parse error: {exc}"
            )
        self.assertIsInstance(
            data,
            dict,
            "The record must parse back to a dict after a failed update.",
        )


# ---------------------------------------------------------------------------
# Concurrent-reader contract
# ---------------------------------------------------------------------------


class TestConcurrentReaderNeverSeesPartialRecord(unittest.TestCase):
    """BO-2400e-3: a reader racing an in-flight (successful, uninterrupted)
    update must always see either the whole old content or the whole new
    content -- never a half-written mixture. This is a property of the file
    the reader opens, not of any lock the writer holds (hooks/CI/humans read
    the store without a lock), so a large real write is used to widen the
    race window for a genuine background reader thread.
    """

    # Kept modest (not the multi-hundred-thousand-line size that would give a
    # background reader thread its best chance of winning the race) because
    # this file's tests collectively feed a fixed-budget red-baseline gate;
    # this is still a real write of a real, non-trivially-sized document, not
    # a toy no-op.
    _PADDING_LINES = 20_000

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.fixture_path = self.tmp_path / "BO-2400e-3-i.yaml"
        text = _AC_FIXTURE_SOURCE_2.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        header_index = next(
            i for i, line in enumerate(lines) if line.startswith("notes: |")
        )
        padding = [
            f"  padding line {n} injected only to make a single write take "
            "measurable wall-clock time, widening the window for a real "
            "concurrent reader to race it (BO-2400e-3 test setup).\n"
            for n in range(self._PADDING_LINES)
        ]
        padded = "".join(lines[: header_index + 1] + padding + lines[header_index + 1 :])
        self.fixture_path.write_text(padded, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_concurrent_reader_never_sees_a_partial_record(self) -> None:
        # covers: BO-2400e-3
        """A real background thread repeatedly reads the file on disk while
        a real write runs in the foreground. Every read must either fully
        parse as YAML or be skipped as a transient I/O race -- it must never
        observe a zero-length file or an unparsable truncated document while
        the write it is racing is the one under test.
        """
        _require_impl(self)
        problems: list[str] = []
        stop = threading.Event()

        def _reader() -> None:
            while not stop.is_set():
                try:
                    data = self.fixture_path.read_bytes()
                except OSError:
                    continue
                if len(data) == 0:
                    problems.append("observed a zero-length record mid-update")
                    continue
                try:
                    yaml.safe_load(data)
                except yaml.YAMLError as exc:
                    problems.append(f"observed an unparsable partial record: {exc}")

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()
        try:
            _update_ac_work_status(self.fixture_path, "done")
        finally:
            stop.set()
            reader_thread.join(timeout=10)

        self.assertEqual(
            problems,
            [],
            "A concurrent reader must never observe a partial or empty "
            f"record (BO-2400e-3). Observed {len(problems)} problem(s), "
            f"first few: {problems[:5]}",
        )


# ---------------------------------------------------------------------------
# Production entry point (reachability) contract
# ---------------------------------------------------------------------------


class TestInterruptionDuringRealRunLeavesEveryRecordReadable(unittest.TestCase):
    """BO-2400e-3: PRODUCTION ENTRY POINT test. Drives claim_build_set --
    the lane's real progress-recording surface (BO-2400f-7) -- over a temp
    store of several requirements with a real, OS-enforced write failure
    induced for the whole run, then reads every record back and asserts all
    parse and none is empty.

    A durable write helper that the lane does not actually call from
    claim_build_set / release_claim / mark_done_built_acs would pass every
    other test in this file while this one stays RED.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name)
        self.ac_ids = ["BO-2400e-3", "BO-2400e-3-i"]
        self.record_paths: dict[str, Path] = {}
        sources = {
            "BO-2400e-3": _AC_FIXTURE_SOURCE,
            "BO-2400e-3-i": _AC_FIXTURE_SOURCE_2,
        }
        for ac_id, source in sources.items():
            todo_text = _rewrite_to_todo_precondition(source)
            path = self.ac_root / f"{ac_id}.yaml"
            path.write_text(todo_text, encoding="utf-8")
            self.record_paths[ac_id] = path
        self.originals = {
            ac_id: path.read_bytes() for ac_id, path in self.record_paths.items()
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_interruption_during_a_real_run_leaves_every_record_readable(self) -> None:
        # covers: BO-2400e-3
        """After a real, OS-enforced write failure strikes claim_build_set
        mid-run, every AC record in the temp store must still parse as YAML
        and be nonempty -- the real lifecycle surface must inherit the same
        durability guarantee as the raw write helper.
        """
        _require_impl(self)

        def _child(ac_ids: list[str], ac_root: str) -> None:
            resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
            claim_build_set(ac_ids, ac_root=Path(ac_root))

        ctx = multiprocessing.get_context("fork")
        proc = ctx.Process(target=_child, args=(self.ac_ids, str(self.ac_root)))
        proc.start()
        proc.join(timeout=15)

        failures = []
        for ac_id, path in self.record_paths.items():
            data = path.read_bytes()
            if len(data) == 0:
                failures.append(f"{ac_id}: record is empty after interruption")
                continue
            try:
                yaml.safe_load(data)
            except yaml.YAMLError as exc:
                failures.append(f"{ac_id}: record does not parse: {exc}")

        self.assertEqual(
            failures,
            [],
            "Every AC record must remain readable after a claim_build_set "
            f"run hit a real write failure (BO-2400e-3). Failures: {failures}",
        )


# ---------------------------------------------------------------------------
# Deployed-layout contract
# ---------------------------------------------------------------------------


class TestDurableWriterPresentInDeployedLayout(unittest.TestCase):
    """BO-2400e-3 (it-po deployed-angle test, added 2026-08-17): after a real
    build into a temp target dir, the deployed fast_lane.py must import
    cleanly and expose the durable write entry point -- a helper module
    that only exists in the source tree would leave the DEPLOYED lane still
    truncating while every source-tree test above passes.
    """

    def test_durable_writer_is_present_in_the_deployed_layout(self) -> None:
        # covers: BO-2400e-3
        """Build into a fresh temp target dir, then import fast_lane from
        the DEPLOYED location (not the source tree) in a fresh subprocess
        and confirm _update_ac_work_status resolves without
        ModuleNotFoundError.

        Runs the real ``build_ac_store`` and ``build_build_orchestration_scripts``
        deploy-phase functions directly (from scripts/build_phases.py) rather
        than the full ``build.py --target-dir`` pipeline: those two phases are
        the ones that actually deploy the files this test cares about, and
        the full pipeline additionally deploys agents/hooks/docs/skills that
        are irrelevant here and cost ~15s of wall-clock time this test does
        not need -- a cost that matters because the fast-lane red-baseline
        gate this file's tests feed into has a fixed internal test-run budget.
        """
        scripts_dir = _REPO_ROOT / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        try:
            import build_phases  # noqa: PLC0415
        except ImportError as exc:
            self.fail(f"Cannot import scripts/build_phases.py: {exc}")

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "consumer" / ".leafcutter"
            output_root.mkdir(parents=True, exist_ok=True)
            build_phases.build_ac_store(output_root, config={}, dry_run=False, force=True)
            build_phases.build_build_orchestration_scripts(
                output_root, config={}, dry_run=False, force=True
            )

            deployed_fast_lane_dir = output_root / "scripts" / "build_orchestration"
            deployed_ac_store_dir = output_root / "scripts" / "ac_store"
            deployed_release_dir = output_root / "scripts" / "release"

            probe = (
                "import sys; "
                f"sys.path.insert(0, {str(deployed_release_dir)!r}); "
                f"sys.path.insert(0, {str(deployed_ac_store_dir)!r}); "
                f"sys.path.insert(0, {str(deployed_fast_lane_dir)!r}); "
                "import fast_lane; "
                "assert hasattr(fast_lane, '_update_ac_work_status'), "
                "'deployed fast_lane.py has no _update_ac_work_status'; "
                "print('DEPLOYED_IMPORT_OK')"
            )
            result = subprocess.run(
                [sys.executable, "-c", probe],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                result.returncode,
                0,
                "Importing the deployed fast_lane.py (and its durable write "
                f"entry point) must succeed in a fresh subprocess (BO-2400e-3). "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            self.assertIn(
                "DEPLOYED_IMPORT_OK",
                result.stdout,
                f"Deployed import probe did not print the expected marker. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )


if __name__ == "__main__":
    unittest.main()
