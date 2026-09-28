"""
MODULE: test_inf_1100d_3_i_no_leak
AC: INF-1100d-3-i -- "'Not configured' and 'configured but unreachable' are
    different reports, and neither shows a password"

GOAL: Every credential-leak / crash regression found by pr-reviewer against
    the shipped test-database checker CLI (scripts/db_check/checker.py) --
    the never-leaks-credentials tests, the parametrized property guard over
    a whole table of hostile address shapes, and the H-6 over-long-DNS-label
    crash tests. Split out of ``test_inf_1100d_3_i.py`` (which keeps the
    not_configured / unreachable / config_error report-shape tests) by
    ``check-file-size`` (limit 400 lines; the combined file was 466+ lines).
    The split is organisational only -- no assertion, fixture value, or test
    behaviour changed, and every ``# covers:``/``# angle:`` tag was
    preserved verbatim from the pre-split file.

WHY SUBPROCESS, NOT IMPORT-AND-CALL: this AC's own test_spec names the
    surface as "the shipped test-database checker CLI, run as a subprocess
    the way the test runner invokes it" -- CLAUDE.md's "Gate / Workflow ACs
    -- Verify Behaviorally, Not by Grep" section forbids proving a CLI AC by
    importing its internals and calling a function directly.

FIXTURES: every project is a REAL temp directory with a REAL
    ``.claude/skills_config.json`` written via ``json.dump``
    (unit_tests/README.md #4 -- never a hand-typed literal). No test here
    spawns scripts/build.py (CLAUDE.md "Tests must not spawn their own
    build.py").

MUST_CATCH MAPPING (from this AC's own IT-PO enrichment notes):
    - "echo the full connection string in the unreachable message" ->
      caught by TestDbCheckNeverLeaksCredentials and every
      TestDbCheckNeverLeaksCredentials* sibling below.

PR-REVIEWER ROUND 1 (H-1, angle: failure): ``_parse_address()`` uses
    ``urllib.parse.urlsplit()``, which treats the token before the first
    ``:`` as a SCHEME whenever the value has no ``//`` -- so a scheme-less
    value like ``app:s3cret@db.internal:5432/app_test`` parses to
    ``scheme='app'``, ``path='s3cret@db.internal:5432/app_test'``, and
    ``_parse_address``'s ``database = parsed.path.lstrip('/')`` returns that
    whole path VERBATIM as the ``database`` field. TestDbCheckNeverLeaks
    CredentialsSchemeLess and ...MalformedScheme reproduce this for two
    sibling shapes (confirmed by direct ``urlsplit()`` probing; a third
    candidate, ``//user:pass@host:port/db``, was rejected because
    ``urlsplit().hostname`` already strips userinfo correctly for that
    shape, so a test there would pass on arrival and prove nothing).

PR-REVIEWER ROUND 2 (H-3/H-4/property guard):
    - H-3 (angle: failure): a doubled scheme
      (``postgresql://postgresql://user:pass@host:port/db``) leaks the
      password into ``database`` the same way H-1 did -- ``urlsplit()``
      only strips ONE leading ``scheme://``, so the second
      ``postgresql://`` is left in the path verbatim (credentials
      included). Confirmed by direct probing: reports
      ``host='postgresql', database='app:s3cret@db.internal:5432/app_test'``.
    - H-4 (angle: failure): a path-suffix parameter segment
      (``postgresql://host:port/db;password=s3cret``) is not stripped by
      ``_parse_address`` -- the whole ``;password=...`` suffix rides along
      in ``database`` AND gets echoed into ``message``. Confirmed by direct
      probing: reports ``database='app_test;password=s3cret'``.
    - Property guard (angle: failure, ``pytest.mark.parametrize`` -- NOT
      ``unittest.subTest``; each parametrized case is verified to be its
      own separately reported/failed pytest node, unlike subTest, which
      TestDbCheckNeverLeaksCredentials below proved gets counted as an
      outer PASS in this repo's runner): sweeps every hostile shape found
      so far plus the KNOWN-GOOD address as a positive control, asserting
      ``host``/``database`` only ever contain a conservative safe character
      set and ``message`` never contains the password, the raw configured
      value, or any of ``@``/``;``/``=``. A character-class check cannot by
      itself detect an embedded password made of ordinary letters/digits,
      so this COMPLEMENTS the explicit password/raw-value containment
      checks, catching structural leakage the substring checks alone would
      miss.

PR-REVIEWER ROUND 3 (H-6, angle: failure): an over-long DNS LABEL in the
    host crashes the CLI. A single label >63 chars (``"b"*70``) makes
    ``socket.create_connection()``'s internal ``getaddrinfo()`` call encode
    the hostname with the ``idna`` codec, which raises
    ``UnicodeEncodeError: ... label too long`` -- UNCAUGHT
    (``_probe_tcp_reachable()`` only catches ``OSError``), so it propagates
    as a raw traceback with empty stdout. Reproduces identically for a
    5000-char label. By contrast, a hostname whose TOTAL length exceeds 253
    but whose individual labels all stay under 63 does NOT crash today
    (Python's ``idna`` codec only enforces the per-label limit;
    ``getaddrinfo()`` then fails with ``socket.gaierror``, an ``OSError``
    subclass, already caught) -- TestDbCheckReportsInvalidForOverLongTotal
    Hostname is a POSITIVE CONTROL, confirmed green, not a regression.
"""
# @ac-tag: INF-1100d-3-i

from __future__ import annotations

import json
import re
import unittest

import pytest

from ._inf_1100d_3_db_check_harness import (
    P3_ADDRESS,
    P3_DATABASE,
    P3_HOST,
    P3_PASSWORD,
    P3_PORT,
    P3_USER,
    make_tmp_dir,
    run_checker_cli,
    write_project,
)

# Conservative whitelist for the STRUCTURED host/database report fields --
# deliberately excludes space, '@', ';', '=', '?', '#', ':' (anything a
# well-formed hostname or database identifier from this module's own valid
# fixtures never needs, and everything a leaking userinfo/query-string
# segment does need).
_HOST_DB_SAFE_CHARS = re.compile(r"^[A-Za-z0-9._-]*$")
# Characters no legitimate MESSAGE template in checker.py ever emits --
# message is free-form prose (spaces/colons/periods/parens are fine), but
# none of its templates ever contain these.
_MESSAGE_UNSAFE_SUBSTRINGS = ("@", ";", "=")


def _assert_report_never_leaks_credential(
    testcase: unittest.TestCase, address: str, *, password: str = P3_PASSWORD, user: str = P3_USER
) -> None:
    """Shared assertion body for the H-1/H-3/H-4 credential-leak
    regression tests.

    Requires a real JSON report (so a checker that crashes before producing
    any output does not make the negative credential check pass vacuously
    -- unit_tests/README.md #1), then asserts the password, the
    ``user:password`` pair, and the RAW configured value never appear
    anywhere in the combined stdout+stderr.
    """
    project_root = write_project(make_tmp_dir("inf1100d3i_h1_"), {"db_connection_test": address})
    result = run_checker_cli(project_root, timeout=8.0)
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        testcase.fail(
            f"checker did not print any JSON report for {address!r} (so the "
            f"credential-absence check below would otherwise pass vacuously): "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    testcase.assertTrue(payload.get("status"), f"checker printed JSON with no status field: {payload!r}")
    testcase.assertNotIn(password, combined, f"password leaked: {combined!r}")
    testcase.assertNotIn(f"{user}:{password}", combined, f"user:password pair leaked: {combined!r}")
    testcase.assertNotIn(
        address,
        combined,
        f"raw configured value echoed verbatim into the report: {combined!r}",
    )


class TestDbCheckNeverLeaksCredentials(unittest.TestCase):
    def test_db_check_output_never_contains_credentials(self):
        # covers: INF-1100d-3-i
        # angle: failure
        """Neither stdout nor stderr ever contains the password (or
        user:password pair) from a P3-shaped address -- for the ordinary
        unreachable case AND for a malformed-port variant designed to push
        a driver toward echoing its raw conninfo/DSN into exception text
        (must_catch: 'echo the full connection string in the unreachable
        message')."""
        cases = [
            P3_ADDRESS,
            f"postgresql://{P3_USER}:{P3_PASSWORD}@{P3_HOST}:not-a-port/{P3_DATABASE}",
        ]
        for address in cases:
            with self.subTest(address=address):
                project_root = write_project(
                    make_tmp_dir("inf1100d3i_creds_"),
                    {"db_connection_test": address},
                )
                result = run_checker_cli(project_root, timeout=8.0)
                combined = (result.stdout or "") + "\n" + (result.stderr or "")
                # Positive check FIRST -- a checker that does not exist (or
                # crashes before producing any report) must not make this
                # test vacuously pass by simply never mentioning the
                # password. The checker must actually have run and reported
                # SOMETHING (a non-empty JSON status on stdout), so this
                # test is not a pure negative control (unit_tests/README.md
                # #1: "a negative control ... is green on arrival by
                # construction").
                try:
                    payload = json.loads(result.stdout)
                except json.JSONDecodeError:
                    self.fail(
                        "checker did not print any JSON report for a P3-shaped "
                        f"address (so the credential-absence check below would "
                        f"otherwise pass vacuously): stdout={result.stdout!r} "
                        f"stderr={result.stderr!r}"
                    )
                self.assertTrue(
                    payload.get("status"),
                    f"checker printed JSON with no status field: {payload!r}",
                )
                self.assertNotIn(P3_PASSWORD, combined, f"password leaked: {combined!r}")
                self.assertNotIn(
                    f"{P3_USER}:{P3_PASSWORD}", combined, f"user:password pair leaked: {combined!r}"
                )


class TestDbCheckNeverLeaksCredentialsSchemeLess(unittest.TestCase):
    def test_db_check_output_never_leaks_credentials_for_scheme_less_value(self):
        # covers: INF-1100d-3-i
        # angle: failure
        """H-1 (pr-reviewer): a scheme-less value with no ``postgresql://``
        prefix must not leak its password. ``urlsplit()`` treats the token
        before the first ``:`` as a SCHEME whenever the value has no
        ``//``, so ``app:s3cret@db.internal:5432/app_test`` parses to
        ``scheme='app'``, ``path='s3cret@db.internal:5432/app_test'`` --
        and the current ``_parse_address()`` returns that whole path
        VERBATIM (password included) as the ``database`` field. Any status
        is acceptable; the password and the raw value must never appear
        anywhere in the report (must_catch: 'echo the connection string
        into the report')."""
        address = f"{P3_USER}:{P3_PASSWORD}@{P3_HOST}:{P3_PORT}/{P3_DATABASE}"
        _assert_report_never_leaks_credential(self, address)


class TestDbCheckNeverLeaksCredentialsMalformedScheme(unittest.TestCase):
    def test_db_check_output_never_leaks_credentials_for_malformed_scheme_value(self):
        # covers: INF-1100d-3-i
        # angle: failure
        """H-1 sibling shape (pr-reviewer): a garbage
        ``scheme:user:pass@host:port/db`` value (an extra leading token
        before the credentials, still no ``//``) hits the SAME
        ``urlsplit()`` scheme-vs-path ambiguity as the scheme-less case --
        the extra token is absorbed as the scheme and the password is
        still returned verbatim in ``database``."""
        address = f"postgres:{P3_USER}:{P3_PASSWORD}@{P3_HOST}:{P3_PORT}/{P3_DATABASE}"
        _assert_report_never_leaks_credential(self, address)


class TestDbCheckNeverLeaksCredentialsDoubledScheme(unittest.TestCase):
    def test_db_check_output_never_leaks_credentials_for_doubled_scheme_value(self):
        # covers: INF-1100d-3-i
        # angle: failure
        """H-3 (pr-reviewer round 2): a doubled scheme
        (``postgresql://postgresql://user:pass@host:port/db``) leaks the
        password. ``urlsplit()`` only strips ONE leading ``scheme://``, so
        the second ``postgresql://...`` remains in ``.path`` verbatim, and
        the current ``_parse_address()`` returns it (credentials included)
        as ``database``. Confirmed by direct probing: reports
        ``host='postgresql'``,
        ``database='app:s3cret@db.internal:5432/app_test'``."""
        address = f"postgresql://postgresql://{P3_USER}:{P3_PASSWORD}@{P3_HOST}:{P3_PORT}/{P3_DATABASE}"
        _assert_report_never_leaks_credential(self, address)


class TestDbCheckNeverLeaksCredentialsPathSuffixParams(unittest.TestCase):
    def test_db_check_output_never_leaks_credentials_for_path_suffix_params_value(self):
        # covers: INF-1100d-3-i
        # angle: failure
        """H-4 (pr-reviewer round 2): a path-suffix parameter segment
        (``postgresql://host:port/db;password=s3cret``) is not stripped by
        ``_parse_address()`` -- the whole ``;password=...`` suffix rides
        along in ``database`` AND is echoed into ``message`` (which
        interpolates ``database`` directly). Confirmed by direct probing:
        reports ``database='app_test;password=s3cret'`` and a ``message``
        containing the same substring."""
        address = f"postgresql://{P3_HOST}:{P3_PORT}/{P3_DATABASE};password={P3_PASSWORD}"
        _assert_report_never_leaks_credential(self, address)


# ---------------------------------------------------------------------------
# Property guard: every report field is safe, across a whole table of
# hostile shapes at once, plus the known-good address as a positive control.
# Uses pytest.mark.parametrize (NOT unittest.subTest) so each row is its own
# separately reported/failed pytest node -- verified directly against this
# repo's pytest (9.1.1): a parametrize failure shows as its own FAILED node
# and moves the run's exit code to 1, unlike a subTest failure under a
# unittest.TestCase, which this file's own
# TestDbCheckNeverLeaksCredentials proved gets counted as an outer PASS.
# ---------------------------------------------------------------------------

_PROPERTY_GUARD_CASES = {
    "scheme_less": f"{P3_USER}:{P3_PASSWORD}@{P3_HOST}:{P3_PORT}/{P3_DATABASE}",
    "malformed_scheme": f"postgres:{P3_USER}:{P3_PASSWORD}@{P3_HOST}:{P3_PORT}/{P3_DATABASE}",
    "doubled_scheme": f"postgresql://postgresql://{P3_USER}:{P3_PASSWORD}@{P3_HOST}:{P3_PORT}/{P3_DATABASE}",
    "path_suffix_params": f"postgresql://{P3_HOST}:{P3_PORT}/{P3_DATABASE};password={P3_PASSWORD}",
    "space_in_database": f"postgresql://{P3_HOST}:{P3_PORT}/app test",
    "query_and_fragment": "postgresql://h:5432/db?x#frag",
    "known_good_control": P3_ADDRESS,
}


@pytest.mark.parametrize("case_id", sorted(_PROPERTY_GUARD_CASES))
def test_db_check_report_fields_never_contain_unsafe_characters_or_raw_value(case_id: str) -> None:
    # covers: INF-1100d-3-i
    # angle: failure
    """Property guard (pr-reviewer round 2): for every hostile shape found
    so far -- plus the known-good address as a positive control -- the
    checker's report must never expose the password, the raw configured
    value, or an unsafe character in a structured field. This does not
    replace the targeted credential tests above; it is a broader net meant
    to stop new hostile shapes from needing their own bespoke test every
    time pr-reviewer finds one.

    ``known_good_control`` documents the OTHER half of the contract: the
    guard must not itself break parsing of a normal, valid address (host
    'db.internal', port 5432, database 'app_test')."""
    address = _PROPERTY_GUARD_CASES[case_id]
    project_root = write_project(make_tmp_dir("inf1100d3i_prop_"), {"db_connection_test": address})
    result = run_checker_cli(project_root, timeout=8.0)
    combined = (result.stdout or "") + "\n" + (result.stderr or "")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            f"checker did not print any JSON report for case {case_id!r} "
            f"({address!r}): stdout={result.stdout!r} stderr={result.stderr!r}"
        )

    if case_id == "known_good_control":
        assert payload.get("host") == P3_HOST, payload
        assert payload.get("port") == P3_PORT, payload
        assert payload.get("database") == P3_DATABASE, payload

    host = payload.get("host")
    database = payload.get("database")
    message = payload.get("message") or ""

    if host is not None:
        assert _HOST_DB_SAFE_CHARS.match(host), (
            f"case {case_id!r}: unsafe character in host field: {host!r} (full report: {payload!r})"
        )
    if database is not None:
        assert _HOST_DB_SAFE_CHARS.match(database), (
            f"case {case_id!r}: unsafe character in database field: {database!r} (full report: {payload!r})"
        )
    for unsafe in _MESSAGE_UNSAFE_SUBSTRINGS:
        assert unsafe not in message, (
            f"case {case_id!r}: unsafe character {unsafe!r} in message: {message!r} (full report: {payload!r})"
        )
    assert P3_PASSWORD not in combined, f"case {case_id!r}: password leaked: {combined!r}"
    assert address not in combined, f"case {case_id!r}: raw configured value echoed verbatim: {combined!r}"


def _assert_reports_gracefully_no_traceback(testcase: unittest.TestCase, address: str) -> None:
    """Shared assertion body for the H-6 over-long-hostname regression
    tests: whatever the checker decides about a hostile host value, it
    must decide it via a JSON report (never crash), with a non-'reachable'
    status and exit code, and without leaking a raw Python traceback."""
    project_root = write_project(make_tmp_dir("inf1100d3i_h6_"), {"db_connection_test": address})
    result = run_checker_cli(project_root, timeout=8.0)

    testcase.assertNotEqual(
        result.returncode,
        0,
        f"expected a non-zero exit for a hostile host value; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}",
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        testcase.fail(
            "checker must print a JSON report, not a raw traceback, for a "
            f"hostile host value: stdout={result.stdout!r} stderr={result.stderr!r}"
        )
    status = payload.get("status")
    testcase.assertTrue(status, f"checker printed JSON with no status field: {payload!r}")
    testcase.assertNotEqual(status, "reachable", f"a hostile host value cannot be 'reachable': {payload!r}")
    testcase.assertNotIn(
        "Traceback (most recent call last)",
        result.stderr or "",
        f"CLI must not leak a raw Python traceback: stderr={result.stderr!r}",
    )


class TestDbCheckRejectsLongHostLabel(unittest.TestCase):
    def test_db_check_reports_invalid_for_over_long_dns_label_70_chars(self):
        # covers: INF-1100d-3-i
        # angle: failure
        """H-6 (pr-reviewer round 3): a single DNS label of 70 characters
        (over the 63-char RFC 1035 limit) currently crashes the CLI --
        ``socket.create_connection()``'s internal ``getaddrinfo()`` call
        encodes the host with the ``idna`` codec, which raises
        ``UnicodeEncodeError: ... label too long``, uncaught by
        ``_probe_tcp_reachable()``'s ``except OSError`` (UnicodeEncodeError
        is not an OSError subclass). Confirmed by direct probing: RC=1,
        stdout='', stderr ends in
        ``UnicodeEncodeError: 'idna' codec can't encode characters in
        position 0-69: label too long``."""
        address = f"postgresql://{'b' * 70}:5432/app_test"
        _assert_reports_gracefully_no_traceback(self, address)


class TestDbCheckRejectsHugeHostLabel(unittest.TestCase):
    def test_db_check_reports_invalid_for_over_long_dns_label_5000_chars(self):
        # covers: INF-1100d-3-i
        # angle: failure
        """H-6 sibling shape (pr-reviewer round 3): the same
        ``UnicodeEncodeError`` crash as the 70-char label case, at a much
        larger scale (5000-char label) -- proves the fix cannot simply be
        a length cap tuned to one magnitude. Confirmed by direct probing:
        RC=1, stdout='', stderr ends in
        ``UnicodeEncodeError: 'idna' codec can't encode characters in
        position 0-4999: label too long``."""
        address = f"postgresql://{'b' * 5000}:5432/app_test"
        _assert_reports_gracefully_no_traceback(self, address)


class TestDbCheckReportsInvalidForOverLongTotalHostname(unittest.TestCase):
    def test_db_check_reports_invalid_for_over_long_total_hostname(self):
        # covers: INF-1100d-3-i
        # angle: failure
        """H-6 total-length case (pr-reviewer round 3): a hostname made of
        five 60-char labels (304 chars total, over the 253-char total-
        hostname limit) but with every individual label under the 63-char
        per-label limit. POSITIVE CONTROL: confirmed by direct probing that
        this does NOT crash today -- Python's ``idna`` codec only enforces
        the per-label limit, so ``getaddrinfo()`` fails with
        ``socket.gaierror`` (an ``OSError`` subclass), which
        ``_probe_tcp_reachable()``'s existing ``except OSError`` already
        catches, producing a clean JSON 'unreachable' report. Included per
        the coordinator's explicit request so this shape has its own
        regression test rather than being assumed safe; if a future change
        (e.g. switching to a stricter validator that raises before the
        socket layer) ever turns this into a crash, this test will go red
        and catch it."""
        long_host = ".".join(["a" * 60] * 5)
        assert len(long_host) > 253, "fixture sanity: host must exceed the 253-char total limit"
        address = f"postgresql://{long_host}:5432/app_test"
        _assert_reports_gracefully_no_traceback(self, address)


if __name__ == "__main__":
    unittest.main()
