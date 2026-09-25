"""
MODULE: test_inf_1100d_3_i
AC: INF-1100d-3-i -- "'Not configured' and 'configured but unreachable' are
    different reports, and neither shows a password"

GOAL: Behavioral, subprocess-driven tests for the shipped test-database
    checker CLI's THREE core report shapes: not_configured, unreachable, and
    config_error (a config file that exists but cannot be read/parsed/
    decoded). The credential-leak regressions found across several
    pr-reviewer rounds (H-1/H-3/H-4, the property guard, and the H-6
    over-long-host-label crashes) live in the sibling file
    ``test_inf_1100d_3_i_no_leak.py`` -- this file was split out of a single
    466+ line module by ``check-file-size`` (limit 400); the split is
    organisational only, no assertion/fixture/behaviour changed, and every
    ``# covers:``/``# angle:`` tag was preserved verbatim.

WHY SUBPROCESS, NOT IMPORT-AND-CALL: this AC's own test_spec names the
    surface as "the shipped test-database checker CLI, run as a subprocess
    the way the test runner invokes it" -- CLAUDE.md's "Gate / Workflow ACs
    -- Verify Behaviorally, Not by Grep" section forbids proving a CLI AC by
    importing its internals and calling a function directly, since that
    would pass even if the CLI entry point itself were missing or broken.

FIXTURES: every P1/P2/P3 project is a REAL temp directory with a REAL
    ``.claude/skills_config.json`` written via ``json.dump``
    (unit_tests/README.md #4 -- never a hand-typed literal). No test here
    spawns scripts/build.py (CLAUDE.md "Tests must not spawn their own
    build.py").

MUST_CATCH MAPPING (from this AC's own IT-PO enrichment notes):
    - "treat '' as a configured address" -> P2 attempts a connection ->
      caught by TestDbCheckReportsNotConfigured's black-hole-env timeout
      assertion (a real attempt hangs against 192.0.2.1 and the subprocess
      is killed by subprocess.run(timeout=...), failing the test).
    - "report not-configured as unreachable" -> caught by the distinct
      ``status`` field assertions split across the two TestCase classes
      below (a checker that collapses the two statuses fails whichever of
      the two this file runs second).

PR-REVIEWER FOLLOW-UP (2026-09-25, H-2/H-5 -- the config_error shapes kept
    in THIS file; H-1/H-3/H-4/H-6/property-guard moved to
    test_inf_1100d_3_i_no_leak.py):
    - H-2 (angle: failure): ``check_test_db()`` only catches
      ``DbConnectionTestNotConfiguredError`` around its
      ``resolve_test_db_address()`` call; a ``skills_config.json`` that
      EXISTS but is not valid JSON makes ``resolve_test_db_address()``
      raise ``DbConnectionTestConfigError`` instead, which propagates
      UNCAUGHT out of ``check_test_db()`` and ``main()`` -- so the CLI exits
      with a raw Python traceback on stderr and empty stdout instead of a
      JSON report. TestDbCheckReportsConfigErrorNotTraceback below
      reproduces this (confirmed by direct subprocess probing: RC=1,
      stdout='', stderr contains a full traceback ending in
      ``DbConnectionTestConfigError: <path> is not valid JSON: ...``).
    - H-5 (angle: failure): a ``skills_config.json`` that exists but is not
      valid UTF-8 makes ``Path.read_text(encoding="utf-8")`` raise
      ``UnicodeDecodeError`` -- uncaught, same crash shape as H-2 but a
      DIFFERENT exception type, so H-2's fix alone will not close this gap.
      TestDbCheckReportsConfigErrorForNonUtf8 below reproduces this
      (confirmed by direct probing: RC=1, stdout='', stderr ends in
      ``UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff ...``).

    Per the coordinator's explicit instruction, each new case is its OWN
    test function (never ``self.subTest``) -- this repo's red-baseline
    reader counts a subTest-only failure as the outer test PASSED, which
    would silently hide these gaps from the red baseline.
"""
# @ac-tag: INF-1100d-3-i

from __future__ import annotations

import json
import subprocess
import time
import unittest

from ._inf_1100d_3_db_check_harness import (
    BLACKHOLE_HOST,
    BLACKHOLE_PORT,
    P3_ADDRESS,
    P3_DATABASE,
    P3_HOST,
    P3_PORT,
    make_tmp_dir,
    run_checker_cli,
    write_project,
)


class TestDbCheckReportsNotConfigured(unittest.TestCase):
    """P1 (unset) and P2 ('' / whitespace-only) both report not_configured,
    naming testing_context.db_connection_test, with zero connection
    attempts."""

    def _assert_not_configured_and_no_connection(self, testing_context: dict) -> None:
        project_root = write_project(make_tmp_dir("inf1100d3i_notconf_"), testing_context)
        # A wrong implementation that treats a blank value as "connect using
        # the driver's own defaults" will read these env vars via libpq --
        # pointed at a black-hole address, that hangs rather than failing
        # fast, so an over-timeout subprocess is decisive proof a connection
        # was attempted for an unconfigured setting.
        blackhole_env = {
            "PGHOST": BLACKHOLE_HOST,
            "PGPORT": BLACKHOLE_PORT,
            "PGUSER": "probe",
            "PGPASSWORD": "probe",
            "PGDATABASE": "probe",
            "PGCONNECT_TIMEOUT": "3",
        }
        try:
            result = run_checker_cli(project_root, env_overrides=blackhole_env, timeout=6.0)
        except subprocess.TimeoutExpired:
            self.fail(
                "checker CLI did not return within 6s for an unconfigured "
                "db_connection_test -- PGHOST was pointed at a black-hole "
                "address (192.0.2.1); a hang here means a connection was "
                "attempted against an address the checker guessed itself "
                "(must_catch: 'treat \"\" as a configured address')."
            )
        self.assertNotEqual(
            result.returncode,
            0,
            f"expected a non-zero exit for not_configured; got 0. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"checker did not print JSON on stdout: {result.stdout!r} / {result.stderr!r}")
        self.assertEqual(
            payload.get("status"),
            "not_configured",
            f"must_catch 'report not-configured as unreachable': got {payload!r}",
        )
        self.assertEqual(payload.get("setting"), "testing_context.db_connection_test")
        message = payload.get("message") or ""
        self.assertIn("testing_context.db_connection_test", message)

    def test_db_check_reports_not_configured_for_unset_and_blank(self):
        # covers: INF-1100d-3-i
        # angle: reachability
        """P1: testing_context present (a real key in the written JSON) but
        without a db_connection_test entry at all."""
        self._assert_not_configured_and_no_connection({})

    def test_db_check_reports_not_configured_for_empty_string(self):
        # covers: INF-1100d-3-i
        # angle: reachability
        """P2a: db_connection_test set to the empty string -- an empty value
        counts as missing, not as an address."""
        self._assert_not_configured_and_no_connection({"db_connection_test": ""})

    def test_db_check_reports_not_configured_for_whitespace_only(self):
        # covers: INF-1100d-3-i
        # angle: reachability
        """P2b: db_connection_test set to spaces only."""
        self._assert_not_configured_and_no_connection({"db_connection_test": "   "})


class TestDbCheckReportsUnreachable(unittest.TestCase):
    def test_db_check_reports_unreachable_naming_host_port_database(self):
        # covers: INF-1100d-3-i
        # angle: criterion
        """P3: a configured-but-unreachable address is reported as
        'unreachable' (never 'not_configured' -- must_catch: 'report
        not-configured as unreachable'), naming host/port/database parsed
        from the URL, within the AC's 5s reachability-probe timeout
        bound."""
        project_root = write_project(
            make_tmp_dir("inf1100d3i_unreachable_"),
            {"db_connection_test": P3_ADDRESS},
        )
        start = time.monotonic()
        result = run_checker_cli(project_root, timeout=8.0)
        elapsed = time.monotonic() - start
        self.assertLessEqual(
            elapsed,
            7.0,
            f"checker must bound its reachability probe to <=5s per AC; took {elapsed:.1f}s",
        )
        self.assertNotEqual(result.returncode, 0)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(f"checker did not print JSON on stdout: {result.stdout!r} / {result.stderr!r}")
        self.assertEqual(payload.get("status"), "unreachable")
        self.assertEqual(payload.get("host"), P3_HOST)
        self.assertEqual(payload.get("port"), P3_PORT)
        self.assertEqual(payload.get("database"), P3_DATABASE)
        message = payload.get("message") or ""
        self.assertIn(P3_HOST, message)
        self.assertIn(str(P3_PORT), message)
        self.assertIn(P3_DATABASE, message)


class TestDbCheckReportsConfigErrorNotTraceback(unittest.TestCase):
    def test_db_check_reports_config_error_for_invalid_json_not_traceback(self):
        # covers: INF-1100d-3-i
        # angle: failure
        """H-2 (pr-reviewer): a project whose skills_config.json EXISTS but
        is not valid JSON must be reported as a structured JSON result on
        stdout, with a documented (non-empty, non-'reachable') status and a
        message naming the config-file problem, and exit non-zero --
        never a raw Python traceback on stderr with empty stdout.

        Currently ``check_test_db()`` only catches
        ``DbConnectionTestNotConfiguredError`` around its
        ``resolve_test_db_address()`` call; ``DbConnectionTestConfigError``
        (raised for unparseable JSON) is NOT caught there and propagates
        uncaught through ``main()``, so the CLI crashes with a traceback
        instead of reporting."""
        tmp_root = make_tmp_dir("inf1100d3i_h2_")
        project_root = tmp_root / "adopter_project"
        claude_dir = project_root / ".claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / "skills_config.json").write_text("{not valid json!!!", encoding="utf-8")

        result = run_checker_cli(project_root, timeout=8.0)

        self.assertNotEqual(
            result.returncode,
            0,
            f"expected a non-zero exit for an invalid-JSON config; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(
                "CLI must print a JSON report on stdout for a project whose "
                "skills_config.json exists but is not valid JSON -- not a raw "
                f"traceback: stdout={result.stdout!r} stderr={result.stderr!r}"
            )
        status = payload.get("status")
        self.assertTrue(status, f"checker printed JSON with no status field: {payload!r}")
        self.assertNotEqual(
            status, "reachable", f"a project with an unparseable config cannot be 'reachable': {payload!r}"
        )
        message = payload.get("message") or ""
        self.assertIn(
            "json",
            message.lower(),
            f"message must name the JSON-parse problem with the config file: {payload!r}",
        )
        self.assertIn(
            "skills_config.json",
            message,
            f"message must name the config file: {payload!r}",
        )
        self.assertNotIn(
            "Traceback (most recent call last)",
            result.stderr or "",
            f"CLI must not leak a raw Python traceback: stderr={result.stderr!r}",
        )


class TestDbCheckReportsConfigErrorForNonUtf8(unittest.TestCase):
    def test_db_check_reports_config_error_for_non_utf8_config_not_traceback(self):
        # covers: INF-1100d-3-i
        # angle: failure
        """H-5 (pr-reviewer round 2): a skills_config.json that EXISTS but
        is not valid UTF-8 must be reported as a structured JSON result on
        stdout (a documented, non-'reachable' status, and a message naming
        the config-file problem), exit non-zero, and never leak a raw
        Python traceback -- same contract as
        TestDbCheckReportsConfigErrorNotTraceback's invalid-JSON case, but
        for a DIFFERENT underlying exception
        (``Path.read_text(encoding="utf-8")`` raises
        ``UnicodeDecodeError``, not ``json.JSONDecodeError``), so a fix
        that only catches JSON-parse errors will not close this gap.
        Confirmed by direct probing: RC=1, stdout='', stderr ends in
        ``UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff ...``."""
        tmp_root = make_tmp_dir("inf1100d3i_h5_")
        project_root = tmp_root / "adopter_project"
        claude_dir = project_root / ".claude"
        claude_dir.mkdir(parents=True)
        # A UTF-16 BOM followed by otherwise-plausible JSON bytes -- decodes
        # under utf-8 as invalid, but is not empty/garbage-looking, so this
        # exercises the DECODE failure specifically, not a JSON-parse one.
        (claude_dir / "skills_config.json").write_bytes(
            b'\xff\xfe{"testing_context": {"db_connection_test": "x"}}'
        )

        result = run_checker_cli(project_root, timeout=8.0)

        self.assertNotEqual(
            result.returncode,
            0,
            f"expected a non-zero exit for a non-UTF-8 config; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(
                "CLI must print a JSON report on stdout for a non-UTF-8 "
                "skills_config.json -- not a raw traceback: "
                f"stdout={result.stdout!r} stderr={result.stderr!r}"
            )
        status = payload.get("status")
        self.assertTrue(status, f"checker printed JSON with no status field: {payload!r}")
        self.assertNotEqual(
            status, "reachable", f"a project with an undecodable config cannot be 'reachable': {payload!r}"
        )
        message = payload.get("message") or ""
        self.assertIn(
            "skills_config.json",
            message,
            f"message must name the config file: {payload!r}",
        )
        self.assertNotIn(
            "Traceback (most recent call last)",
            result.stderr or "",
            f"CLI must not leak a raw Python traceback: stderr={result.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
