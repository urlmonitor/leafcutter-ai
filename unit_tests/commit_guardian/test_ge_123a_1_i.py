"""
MODULE: unit_tests/commit_guardian/test_ge_123a_1_i.py
GOAL: GE-123a-1-i — every sensitively-named file in the same run is read,
    not just the first one, and no finding is lost between the per-file scan
    and the run's report. GE-123a-1's own scenario exercises exactly ONE
    env-named file; this record closes the gap that a fix reading only the
    first sensitively-named file it meets would pass the parent while
    leaving four of the five measured files exactly as they are today.
BUSINESS CONTEXT: see GE-123a-1's MEASURED RED BASELINE — five env-named
    files each carrying the four recognised secret shapes reported ZERO
    problems, one filename finding each is the current baseline (five
    findings total, not twenty-five).
ARCHITECTURE / EXERCISE STRATEGY: per this AC's it_requirements, every
    fixture set is scanned in a SINGLE `scan_files` call (never a loop over
    the per-file scan, which cannot fail the aggregation or order-
    independence arms). `scan_files` is loaded from the canonical template
    copy via `importlib.util.spec_from_file_location` (ADR-001), matching
    the convention in test_scan_secrets_suppression.py and
    test_ge_123a_1.py. Credential-shaped fixture content is assembled at
    runtime from concatenated fragments — the same values already proven in
    the sibling suites to produce exactly one finding per rule.

DECISION HISTORY
- 2026-09-07 [GE-123a-1-i/test-writer]: Initial authoring, written RED
  against the current five-finding baseline (one ENV_FILE finding per
  env-named file, no content findings). Per the AC's own test_rationale:
  test_five_env_named_files_report_twenty_five_findings and
  test_no_finding_is_dropped_or_collapsed_between_files are RED on their
  count/multiset assertions today. test_findings_are_identical_under_
  forward_and_reverse_scan_order is RED on the per-file finding-SET
  equality only insofar as the env-named files' sets are missing their
  content findings today (both runs already agree on the impoverished
  content, so this test is a live regression guard on the STRUCTURAL
  property once the counts change — see the AC's own honesty note).
  test_cli_over_the_five_file_set_exits_nonzero_and_names_every_file is
  SPLIT: the exit-code half and the "every file is named" half are already
  green (five ENV_FILE findings already exit non-zero and already name all
  five files); the load-bearing, currently-red half is the run's own
  reported finding total reaching twenty-five.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import ClassVar

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCAN_SECRETS = (
    _REPO_ROOT
    / "templates"
    / "skills"
    / "security-scanner"
    / "scripts"
    / "scan_secrets.py"
)

_ENV_NAMES = [".env", ".env.local", ".env.production", "config.env", "secrets.env"]
_ORDINARY_NAMES = ["app.py", "utils.py", "config.py"]

_CONTENT_RULE_IDS = frozenset(
    {"PRIVATE_KEY", "AWS_KEY", "GENERIC_SECRET", "ENTROPY_HIGH"}
)


def _load_scan_secrets() -> ModuleType:
    """Load scan_secrets.py from the canonical template path via file spec.

    Returns:
        The loaded scan_secrets module object.
    """
    spec = importlib.util.spec_from_file_location(
        "scan_secrets_under_test_ge123a1i", str(_SCAN_SECRETS)
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _four_recognised_lines() -> str:
    """Build the four content lines the scanner's content rules recognise.

    Assembled at runtime from concatenated fragments, matching the values
    already proven in the sibling suites to produce exactly one finding per
    rule with no cross-triggering.

    Returns:
        The four-line fixture content, newline-terminated.
    """
    pem_header = "-----BEGIN RSA " + "PRIVATE KEY-----"
    aws_key = "AKIA" + "ABCDEFGHIJKLMNOP"
    secret_value = "hunter2" + "pass1"  # exactly twelve characters
    entropy_blob = "xK9vQ2mZ8pL5" + "nR3tW6yB1cF4"
    return (
        pem_header + "\n"
        + 'aws_access_key_id = "' + aws_key + '"\n'
        + 'password = "' + secret_value + '"\n'
        + 'blob_value = "' + entropy_blob + '"\n'
    )


def _write_fixture_set(root: Path) -> tuple[list[Path], list[Path]]:
    """Write the five env-named and three ordinary fixtures into root.

    Args:
        root: Directory to write the fixture files into.

    Returns:
        A (env_paths, ordinary_paths) tuple of the written file paths, in
        the order named by _ENV_NAMES / _ORDINARY_NAMES.
    """
    content = _four_recognised_lines()
    env_paths = []
    for name in _ENV_NAMES:
        p = root / name
        p.write_text(content, encoding="utf-8")
        env_paths.append(p)
    ordinary_paths = []
    for name in _ORDINARY_NAMES:
        p = root / name
        p.write_text(content, encoding="utf-8")
        ordinary_paths.append(p)
    return env_paths, ordinary_paths


class TestFiveFileAggregationAndOrderIndependence(unittest.TestCase):
    """GE-123a-1-i: the fix must hold for a SET of sensitively-named files,

    not just the first one, and no finding may be dropped or collapsed
    between the per-file scan and the run's report.
    """

    _mod: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        if not _SCAN_SECRETS.exists():
            raise FileNotFoundError(
                f"canonical template not found at {_SCAN_SECRETS}"
            )
        cls._mod = _load_scan_secrets()

    def test_five_env_named_files_report_twenty_five_findings(self):
        # covers: GE-123a-1-i
        # angle: boundary
        """Five distinct env-named fixtures, each carrying the same four

        recognised lines, scanned in a single scan_files call, return
        exactly twenty-five findings — five per file, with the filename
        rule and each of the four content rules present once per file.

        FAILS TODAY: the current baseline is five findings total (one
        ENV_FILE finding per file, no content findings), not twenty-five.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_paths, _ = _write_fixture_set(root)

            findings = self._mod.scan_files(env_paths, project_root=root)

            self.assertEqual(
                len(findings),
                25,
                msg=(
                    f"expected 25 findings across 5 files, got {len(findings)}: "
                    f"{[(f.rule_id, f.file_path) for f in findings]!r}"
                ),
            )
            for path in env_paths:
                rule_ids = {f.rule_id for f in findings if f.file_path == str(path)}
                self.assertEqual(
                    rule_ids,
                    {"ENV_FILE"} | _CONTENT_RULE_IDS,
                    msg=f"file {path} must report filename + all 4 content rules, got {rule_ids!r}",
                )

    def test_findings_are_identical_under_forward_and_reverse_scan_order(self):
        # covers: GE-123a-1-i
        # angle: criterion
        """The five env-named fixtures interleaved with three ordinary .py

        fixtures are scanned forwards and then in reverse; the per-file
        finding set for every one of the eight files is equal between the
        two runs.

        One ordinary file precedes all five env-named files and one follows
        all of them in the forward order, so the reverse run genuinely
        inverts their relative positions.

        RED today insofar as the env-named files' finding sets are missing
        their content findings under BOTH orders — this test also functions
        as a standing regression guard against an order-sensitive
        implementation once the fix lands.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_paths, ordinary_paths = _write_fixture_set(root)
            ordinary_a, ordinary_c, ordinary_b = ordinary_paths

            forward_order = [
                ordinary_a,
                env_paths[0],
                env_paths[1],
                ordinary_c,
                env_paths[2],
                env_paths[3],
                env_paths[4],
                ordinary_b,
            ]
            reverse_order = list(reversed(forward_order))

            forward_findings = self._mod.scan_files(forward_order, project_root=root)
            reverse_findings = self._mod.scan_files(reverse_order, project_root=root)

            def per_file_map(findings):
                out: dict[str, frozenset] = {}
                for path in forward_order:
                    key = str(path)
                    out[key] = frozenset(
                        (f.rule_id, f.line_no) for f in findings if f.file_path == key
                    )
                return out

            forward_map = per_file_map(forward_findings)
            reverse_map = per_file_map(reverse_findings)

            for path in forward_order:
                key = str(path)
                self.assertEqual(
                    forward_map[key],
                    reverse_map[key],
                    msg=(
                        f"file {key} must report the same findings regardless "
                        f"of scan order; forward={forward_map[key]!r} "
                        f"reverse={reverse_map[key]!r}"
                    ),
                )

    def test_no_finding_is_dropped_or_collapsed_between_files(self):
        # covers: GE-123a-1-i
        # angle: seam
        """The multiset of (rule_id, file_path) pairs returned for the

        five-file run contains all twenty-five pairs; findings that differ
        only in which file they came from are all present, so an
        aggregator that de-duplicates by rule id across files fails.

        This is the producer (per-file scan) to consumer (run report) seam:
        what scan_file produces for each file must all survive into what
        scan_files reports, with nothing collapsed across files.

        FAILS TODAY: the current multiset has only 5 pairs (one ENV_FILE
        pair per file), not 25.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_paths, _ = _write_fixture_set(root)

            findings = self._mod.scan_files(env_paths, project_root=root)

            pairs = [(f.rule_id, f.file_path) for f in findings]
            expected_pairs = {
                (rule_id, str(path))
                for path in env_paths
                for rule_id in ({"ENV_FILE"} | _CONTENT_RULE_IDS)
            }

            self.assertEqual(
                len(pairs),
                25,
                msg=f"expected 25 (rule_id, file_path) pairs, got {len(pairs)}: {pairs!r}",
            )
            self.assertEqual(
                set(pairs),
                expected_pairs,
                msg=(
                    "every (rule_id, file_path) pair must be present with none "
                    f"dropped or collapsed; missing={expected_pairs - set(pairs)!r} "
                    f"unexpected={set(pairs) - expected_pairs!r}"
                ),
            )

    def test_cli_over_the_five_file_set_exits_nonzero_and_names_every_file(self):
        # covers: GE-123a-1-i
        # angle: reachability
        """The scanner CLI, run in a fresh subprocess with the fixture

        directory as its working directory over all five env-named
        fixtures, exits non-zero and its report names all five files rather
        than a single representative one, and accounts for all twenty-five
        findings.

        SPLIT: the non-zero exit code and "names every file" halves are
        already green today (five ENV_FILE findings already exit non-zero
        and already name all five files individually). The load-bearing,
        currently-red half is the run's own reported total reaching
        twenty-five.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_paths, _ = _write_fixture_set(root)

            result = subprocess.run(
                [sys.executable, str(_SCAN_SECRETS), *[str(p) for p in env_paths]],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertNotEqual(
                result.returncode,
                0,
                msg=f"expected non-zero exit; stdout={result.stdout!r}",
            )
            for path in env_paths:
                self.assertIn(
                    str(path),
                    result.stdout,
                    msg=f"expected {path} to be named in the report; stdout={result.stdout!r}",
                )
            self.assertIn(
                "25 secret(s) detected",
                result.stdout,
                msg=(
                    "expected the run to account for twenty-five findings "
                    f"across the five files; got stdout={result.stdout!r}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
