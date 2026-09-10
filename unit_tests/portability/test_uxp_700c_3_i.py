r"""
MODULE: test_uxp_700c_3_i
GOAL: Pin the cross-platform verdict contract for the product-truth store: the
    store-relative paths generate_product_truth.py writes into index.json are
    identifiers, not filesystem paths, and must render identically on every
    platform.
BUSINESS CONTEXT: load_flows() built each path with str(path.relative_to(STORE)),
    which renders with os.sep. The committed index.json was generated on a POSIX
    host and holds 'flows/a/b.flow.json'; a Windows rebuild produced
    'flows\a\b.flow.json', so _check_derived_indexes reported drift against an
    unmodified, correct store. Because check-product-truth-validate fires on
    (^docs/product-truth/|^docs/acceptance-criteria/.*\.yaml$), a Windows
    contributor could not commit ANY acceptance-criteria YAML — the only escape
    being --no-verify, which disables every other gate at the same time. The
    write direction was worse: a Windows run in write mode rewrote index.json
    with backslashes, breaking every POSIX contributor and CI, so the file
    flipped separator on each platform's turn. See KI-BP-20260907-0812.
ARCHITECTURE: Asserts on STRING CONTENT, never on a pathlib round-trip. A
    round-trip comparison would pass vacuously on POSIX — the platform that
    cannot reproduce the bug — and so would never have caught it. Two levels of
    guard: a synthetic tempdir store proves the producer emits POSIX separators
    on the host running the suite, and a check of the committed index.json
    proves no Windows-written path has already landed in the repository.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "docs" / "product-truth" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_product_truth as gpt  # noqa: E402
import validate_product_truth as vpt  # noqa: E402

_BACKSLASH = chr(92)


class TestFlowPathsArePlatformIndependent(unittest.TestCase):
    """The producer must emit POSIX separators regardless of host platform."""

    def test_load_flows_emits_no_backslash_on_any_platform(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            nested = store / "flows" / "demo-product" / "sub"
            nested.mkdir(parents=True)
            (nested / "a-journey.flow.json").write_text(
                json.dumps({"id": "demo-product/a-journey"}), encoding="utf-8"
            )

            original_store = gpt.STORE
            gpt.STORE = store
            try:
                _flows, paths = gpt.load_flows()
            finally:
                gpt.STORE = original_store

        emitted = paths["demo-product/a-journey"]
        self.assertNotIn(
            _BACKSLASH,
            emitted,
            f"store-relative path must use POSIX separators, got {emitted!r}",
        )
        self.assertEqual(emitted, "flows/demo-product/sub/a-journey.flow.json")

    def test_committed_index_holds_no_windows_written_path(self) -> None:
        index_path = _REPO_ROOT / "docs" / "product-truth" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))

        offenders = [
            (flow_id, entry.get("path", ""))
            for flow_id, entry in index.get("by_flow", {}).items()
            if _BACKSLASH in entry.get("path", "")
        ]
        self.assertEqual(
            offenders,
            [],
            "index.json contains platform-separator paths — a Windows write has "
            f"landed in the repository: {offenders}",
        )

    def test_rebuild_is_byte_identical_across_simulated_host_separators(self) -> None:
        # covers: UXP-700c-3-i
        # angle: seam
        """AC-3/AC-1: the keys the record's index uses to name its own files are
        spelled identically on both systems, so a rebuild produced on one is
        byte-identical to a rebuild produced on the other.

        We cannot literally boot two OSes in one test process, so we SIMULATE
        both host flavours the way pathlib itself models a foreign platform:
        `PurePosixPath`/`PureWindowsPath` render the SAME relative-path parts
        without depending on the host running the suite. This is the seam
        between the real producer (generate_product_truth.load_flows, run for
        real against a synthetic on-disk store) and the two possible platform
        renderings of that same path — proving neither can diverge.
        """
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            nested = store / "flows" / "demo-product" / "sub"
            nested.mkdir(parents=True)
            (nested / "a-journey.flow.json").write_text(
                json.dumps({"id": "demo-product/a-journey"}), encoding="utf-8"
            )

            original_store = gpt.STORE
            gpt.STORE = store
            try:
                _flows, paths = gpt.load_flows()
            finally:
                gpt.STORE = original_store

        real_emitted = paths["demo-product/a-journey"]
        parts = ("flows", "demo-product", "sub", "a-journey.flow.json")

        posix_rendering = PurePosixPath(*parts).as_posix()
        windows_rendering = PureWindowsPath(*parts).as_posix()

        # The two simulated host renderings must be byte-identical to each other...
        self.assertEqual(
            posix_rendering.encode("utf-8"),
            windows_rendering.encode("utf-8"),
            "a POSIX-flavoured and a Windows-flavoured rendering of the same "
            "relative path diverged at the byte level",
        )
        # ...and the REAL producer's actual emitted key must match both.
        self.assertEqual(real_emitted, posix_rendering)
        self.assertEqual(real_emitted, windows_rendering)

    def test_uxp_700c_3_i_reachable_from_entry_point(self) -> None:
        # covers: UXP-700c-3-i
        # angle: reachability
        """AC-1: both runs report the same verdict and name the same artifacts.

        Invokes the REAL production entry point named by architect-review on
        this ticket: the check-product-truth-validate pre-commit hook, run via
        its own runner (run_hook.py), exactly as .pre-commit-config.yaml wires
        it — not a direct call into validate_product_truth.main(). Consumes
        the result in control flow: the JSON verdict line on stdout is parsed
        and asserted on, and the exit code is asserted non-degraded.
        """
        run_hook = _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian" / "run_hook.py"
        target = "docs/product-truth/scripts/validate_product_truth.py"

        result = subprocess.run(
            [sys.executable, str(run_hook), target, "--quiet"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )

        self.assertEqual(
            result.returncode,
            0,
            "the real check-product-truth-validate hook entry point exited "
            f"non-zero on this host: stdout={result.stdout!r} stderr={result.stderr!r}",
        )

        verdict_line = None
        for line in reversed(result.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                verdict_line = line
                break
        self.assertIsNotNone(
            verdict_line,
            f"no JSON verdict line found on stdout: {result.stdout!r}",
        )
        verdict = json.loads(verdict_line)
        self.assertEqual(
            verdict.get("outcome"),
            "checked-and-sound",
            f"unexpected verdict from the real entry point: {verdict!r}",
        )


class TestDerivedIndexComparisonIsSeparatorTolerant(unittest.TestCase):
    """The drift comparison itself must not conflate a separator-only spelling
    difference with genuine content drift (AC-2)."""

    def test_separator_only_difference_is_not_reported_as_the_record_being_behind(self) -> None:
        # covers: UXP-700c-3-i
        # angle: boundary
        """AC-2: a difference that consists only of how the two systems spell a
        path is never reported as the record having fallen behind.

        Builds a `stored` by_flow index that is IDENTICAL to a fresh rebuild in
        every field except that its `path` value uses backslashes (the shape a
        legacy/foreign-platform write can leave behind), and asserts
        `_check_derived_indexes` — the D3 drift check `validate_product_truth`
        runs on every commit — does NOT report this as "does not match a fresh
        rebuild". Today it does (exact dict equality with no separator
        normalization), which is the still-missing half of this AC: the FIX
        (generate_product_truth's `.as_posix()`) guarantees a FRESH write is
        always POSIX-spelled, but the COMPARISON that decides "has the record
        fallen behind" has no equivalent tolerance for a foreign-spelled
        artifact that reaches it by any other route.
        """
        flow = {
            "id": "demo/a",
            "component": "demo",
            "level": None,
            "entities": [],
        }
        flows = {"demo/a": flow}
        flow_paths = {"demo/a": "flows/demo/a.flow.json"}
        ac_records: dict = {}
        mocks: dict = {}

        expected_by_flow = gpt.build_by_flow(flows, flow_paths, ac_records)

        stored_by_flow = copy.deepcopy(expected_by_flow)
        stored_by_flow["demo/a"]["path"] = stored_by_flow["demo/a"]["path"].replace("/", _BACKSLASH)

        index = {
            "by_component": gpt.build_by_component([]),
            "by_entity": gpt.build_by_entity(flows, mocks),
            "by_flow": stored_by_flow,
            "by_ac": gpt.build_by_ac(flows),
        }

        errors: list[str] = []
        vpt._check_derived_indexes(index, flows, flow_paths, mocks, ac_records, errors)

        by_flow_errors = [e for e in errors if "by_flow" in e]
        self.assertEqual(
            by_flow_errors,
            [],
            "a separator-only spelling difference in by_flow['path'] was reported "
            f"as the record having fallen behind: {by_flow_errors}",
        )


if __name__ == "__main__":
    unittest.main()
