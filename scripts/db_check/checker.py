"""
MODULE: checker
GOAL: Resolve and verify the shipped test-database connection setting
    (``testing_context.db_connection_test``) -- the ONE reader of that
    setting for both the pre-run reachability CLI (INF-1100d-3-i) and the
    Step 2b DB-test pattern's resolver (INF-1100d-3-ii).
BUSINESS CONTEXT: A test run against an unconfigured or unreachable test
    database used to fail late and unclearly (a driver exception deep in a
    test's setUp, or worse, a hang against a guessed default). This module
    makes "not configured" and "configured but unreachable" two distinct,
    deterministic outcomes -- named clearly, reported without ever leaking a
    password, and decided by exactly one piece of code so the pre-run
    checker and the DB-test pattern's resolver cannot disagree about
    whether a blank value counts as configured.
ARCHITECTURE: Two public functions -- ``resolve_test_db_address()`` (the
    sole reader of ``testing_context.db_connection_test``) and
    ``check_test_db()`` (calls ``resolve_test_db_address()`` first, then
    probes TCP reachability with a bounded timeout) -- plus a ``__main__``
    CLI entry point the test runner invokes as a subprocess
    (``python scripts/db_check/checker.py --target-dir <project>``),
    printing the JSON result described in this AC's ``delivers_to``
    contract and exiting 0 only when reachable. Deployed as a whole
    directory (``scripts/db_check/``) by ``build_agent_support_scripts`` in
    ``build_phases_script_deploy.py``.

    SPLIT ACROSS THREE FILES (GE-127a-1/pr-reviewer, 2026-09-25): this
    module exceeded the 400-line check-file-size limit, so its allowlist
    address-parsing logic moved to ``_address.py`` and its config-file I/O
    moved to ``_config.py`` -- both siblings in this same ``db_check/``
    directory. This file keeps the resolver, ``check_test_db()``, the
    report builders, and the CLI (the pieces the tests and the
    ``delivers_to`` contract name directly); every public/test-visible name
    (``resolve_test_db_address``, ``check_test_db``,
    ``DbConnectionTestNotConfiguredError``,
    ``DbConnectionTestConfigError``, ``DbConnectionTestInvalidAddressError``,
    and this file's own CLI path) stays importable from ``checker.py``
    exactly as before the split -- the two exception classes not defined
    natively here are re-imported from their new homes below.

    THE SIBLING-IMPORT MECHANISM: this file imports ``_address`` and
    ``_config`` via a ``sys.path`` push to its OWN directory
    (``Path(__file__).resolve().parent``) followed by plain (non-relative)
    imports, rather than package-relative imports (``from . import
    _address``). This is deliberate, mirroring the same ``sys.path.insert(0,
    <dir>) + plain import`` pattern already used elsewhere in this repo
    (e.g. ``scripts/goal_to_epic.py``'s sibling-module push, and the AC
    BP-900g-8 closure guard's own documented "third recognised reference
    shape") -- and it is required here, not merely a style choice: this file
    is invoked BOTH as a standalone script (the test runner's subprocess CLI
    call, where Python sets ``__package__`` to ``None`` and package-relative
    imports would raise ``ImportError: attempted relative import with no
    known parent package``) AND as an importable submodule (``from
    db_check.checker import resolve_test_db_address`` / ``import
    db_check.checker``, the Step 2b DB-test pattern's own import shape),
    where only ``scripts/`` (this file's grandparent) is guaranteed to be on
    ``sys.path`` -- ``db_check/`` itself is not, so a plain ``import
    _address`` would otherwise fail to resolve in that second case. Pushing
    this file's own directory covers both.

    ``resolve_test_db_address()`` reads the project's own
    ``skills_config.json`` directly -- the SAME platform-directory
    auto-detection order ``config_loader.load_config()`` uses
    (``.claude``, ``.gemini``, ``.cursor``, ``.github``, ``.cline``, first
    match wins) -- rather than importing ``config_loader`` itself. This is
    deliberate, not a shortcut: ``config_loader.py`` is a "build engine"
    file (see ``build_phases_script_deploy.py``'s own module docstring) that
    is never deployed anywhere, precisely because deploying it makes its OWN
    runtime reads of ``config/skills_config.default.json`` and
    ``config/skills_config.schema.json`` into undeployed intra-package
    dependencies the AC BP-900g-8 closure guard rejects (verified live: a
    first attempt at this module added ``config_loader.py`` to
    ``AGENT_SUPPORT_SCRIPT_FILES`` and it broke
    ``test_consumer_simulation_build_succeeds_in_empty_project`` for exactly
    this reason -- see build_phases_script_deploy.py's DECISION HISTORY).
    Reading only the project's own setting -- never a package default -- is
    deliberate for THIS one key: INF-1100d-1 removes ``db_connection_test``
    from ``config/skills_config.default.json`` so that, from that build
    onward, ``config_loader``'s own "package default merged under the
    project's own settings" behaviour agrees with what this resolver already
    does. Until that build lands, ``config_loader.load_config()`` may still
    surface the legacy shipped default for a project that sets nothing at
    all -- this resolver never will, by design (user decisions Q3/NQ1: no
    shipped default address, no stale-default detection).

    A configured value is only accepted when ``_address._parse_address()``
    (see that module) validates it against an ALLOWLIST -- a recognised
    postgres scheme, a safe host, an in-range port, and a safe database
    segment; anything else is reported as ``status: "invalid"`` without ever
    echoing the raw value.

    The reachability probe is a bare TCP connect, not a full driver-level
    authentication handshake -- this needs no database driver to be
    installed and, since it never constructs a conninfo/DSN string, it
    structurally cannot echo a password the way a driver's own exception
    text can.
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import sys
from pathlib import Path
from typing import Any

# Sibling-import push -- see this module's own docstring ("THE
# SIBLING-IMPORT MECHANISM") for why this is a sys.path push + plain import
# rather than a package-relative import.
_DB_CHECK_DIR = Path(__file__).resolve().parent
if str(_DB_CHECK_DIR) not in sys.path:
    sys.path.insert(0, str(_DB_CHECK_DIR))

from _address import (  # noqa: E402
    DbConnectionTestInvalidAddressError,
    _INVALID_ADDRESS_MESSAGE,
    _parse_address,
)
from _config import (  # noqa: E402
    DbConnectionTestConfigError,
    _find_project_config,
    _read_project_testing_context,
)

_log = logging.getLogger(__name__)

_SETTING_NAME = "testing_context.db_connection_test"
_PROBE_TIMEOUT_SECONDS = 4.0


class DbConnectionTestNotConfiguredError(RuntimeError):
    """Raised by ``resolve_test_db_address()`` when
    ``testing_context.db_connection_test`` is unset, empty, or
    whitespace-only. Never carries an address -- only the setting name."""


def resolve_test_db_address(target_root: Path) -> str:
    """Return the configured test-database address, or raise.

    The SOLE reader of ``testing_context.db_connection_test`` -- both
    ``check_test_db()`` in this module and the Step 2b DB-test pattern's
    ``setUp()`` call this function directly rather than each re-reading the
    setting, so "blank means not configured" is decided in exactly one
    place (INF-1100d-3-ii's own "one reader" requirement).

    Args:
        target_root: Absolute path to the project root whose
            ``skills_config.json`` should be resolved.

    Returns:
        The configured address EXACTLY as the project set it -- no
        trimming, no normalisation, no credential rewriting.

    Raises:
        DbConnectionTestNotConfiguredError: When the setting is unset,
            empty, or whitespace-only (including when the project has no
            ``skills_config.json`` at all). Raised before any database
            driver is imported and before any connection is attempted. The
            message names ``testing_context.db_connection_test`` and
            contains no address.
        DbConnectionTestConfigError: When a ``skills_config.json`` exists
            but cannot be read or parsed as JSON.
    """
    config_path = _find_project_config(Path(target_root))
    testing_context = _read_project_testing_context(config_path) if config_path else {}
    raw_value = testing_context.get("db_connection_test")

    if not isinstance(raw_value, str) or not raw_value.strip():
        raise DbConnectionTestNotConfiguredError(  # noqa: TRY003
            f"{_SETTING_NAME} is not configured (unset, empty, or "
            "whitespace-only). Set it in this project's skills_config.json "
            "before running database tests."
        )
    return raw_value


def _probe_tcp_reachable(host: str, port: int, timeout: float = _PROBE_TIMEOUT_SECONDS) -> bool:
    """Attempt a single bounded TCP connection to ``(host, port)``.

    A TCP-level probe -- not a full database authentication handshake --
    is enough to distinguish "database stopped" from "database reachable"
    without needing a database driver installed, and since it never builds
    a conninfo/DSN string, it cannot leak a password the way a driver's own
    connection-error text can.

    Args:
        host: Hostname or IP address to probe.
        port: TCP port to probe.
        timeout: Bounded wait in seconds (default: module's probe timeout,
            kept under the AC's 5s reachability-probe ceiling).

    Returns:
        ``True`` if a TCP connection was established, ``False`` on any
        connection failure (refused, timed out, unresolvable host, or an
        unencodable host -- see below). A connection failure here is the
        expected, reportable "unreachable" outcome, not an unexpected
        error -- it is converted into this boolean return rather than
        re-raised, mirroring this repo's existing "probe -> boolean"
        precedent (e.g. ``scripts/ac_store/done_proof.py``'s ``except
        OSError: return False`` helpers).

        Defensive (H-6): ``_address._parse_address()``'s allowlist already
        rejects an over-long DNS label as "invalid" before this function is
        ever called, but ``socket.create_connection()``'s internal
        ``getaddrinfo()`` call can itself raise ``UnicodeError`` (e.g.
        ``UnicodeEncodeError`` while idna-encoding an unusual host) for a
        shape the allowlist did not anticipate -- ``UnicodeError`` is NOT
        an ``OSError`` subclass, so it is caught separately here and
        logged at WARNING (Error Handling Policy Rule 3: an unexpected
        exception type reaching this probe is logged, not silently
        swallowed, then converted to the same "unreachable" boolean
        return) rather than crashing the CLI with a raw traceback.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
    except UnicodeError as exc:
        _log.warning(
            "db_check: reachability probe could not encode host %r (%s): %s",
            host,
            type(exc).__name__,
            exc,
        )
        return False


def _not_configured_report(message: str) -> dict[str, Any]:
    """Build the ``not_configured`` JSON report shape."""
    return {
        "status": "not_configured",
        "setting": _SETTING_NAME,
        "host": None,
        "port": None,
        "database": None,
        "message": message,
    }


def _unreachable_report(
    host: str | None, port: int | None, database: str | None, message: str
) -> dict[str, Any]:
    """Build the ``unreachable`` JSON report shape."""
    return {
        "status": "unreachable",
        "setting": _SETTING_NAME,
        "host": host,
        "port": port,
        "database": database,
        "message": message,
    }


def _reachable_report(host: str, port: int, database: str | None) -> dict[str, Any]:
    """Build the ``reachable`` JSON report shape."""
    return {
        "status": "reachable",
        "setting": _SETTING_NAME,
        "host": host,
        "port": port,
        "database": database,
        "message": f"Connected to {host}:{port}/{database}.",
    }


def _invalid_report(message: str) -> dict[str, Any]:
    """Build the ``invalid`` JSON report shape (H-1: configured but not a
    parseable postgres URL -- never carries the raw value)."""
    return {
        "status": "invalid",
        "setting": _SETTING_NAME,
        "host": None,
        "port": None,
        "database": None,
        "message": message,
    }


def _config_error_report(message: str) -> dict[str, Any]:
    """Build the ``config_error`` JSON report shape (H-2: the project's
    ``skills_config.json`` exists but could not be read or parsed)."""
    return {
        "status": "config_error",
        "setting": _SETTING_NAME,
        "host": None,
        "port": None,
        "database": None,
        "message": message,
    }


def check_test_db(target_root: Path) -> dict[str, Any]:
    """Check the shipped test-database setting for *target_root*.

    Calls ``resolve_test_db_address()`` first (the ONE reader of
    ``testing_context.db_connection_test``) so an unconfigured setting is
    reported without ever attempting a connection or importing a database
    driver. When configured, probes TCP reachability with a bounded
    timeout. This is the I/O boundary for the whole check: address parsing
    and the reachability probe are both attempted here, and their
    exceptions are handled here rather than in the pure helpers they call.

    Args:
        target_root: Absolute path to the project root to check.

    Returns:
        A JSON-serialisable dict: ``status`` (``"not_configured"`` |
        ``"invalid"`` | ``"config_error"`` | ``"unreachable"`` |
        ``"reachable"``), ``setting`` (always
        ``"testing_context.db_connection_test"``), ``host``, ``port``,
        ``database`` (``None`` unless configured and parseable), and a
        human-readable ``message``. Never contains a password or
        ``user:password`` pair, and never echoes the raw configured value --
        ``_address._parse_address`` only ever surfaces
        ``urlsplit().hostname``/``.path`` from an already-validated URL
        (never userinfo), and every exception message built in this module
        is generic (names the setting or the config file path, never the
        address).
    """
    try:
        address = resolve_test_db_address(target_root)
    except DbConnectionTestNotConfiguredError as exc:
        return _not_configured_report(str(exc))
    except DbConnectionTestConfigError as exc:
        # H-2: a skills_config.json that exists but is not valid JSON (or
        # cannot be read) must become a JSON report, not an uncaught
        # traceback -- this is the module's I/O boundary catching the
        # specific error its own I/O helper raises (Error Handling Policy
        # Rule 3: caught, reported, never silently dropped).
        return _config_error_report(str(exc))

    try:
        host, port, database = _parse_address(address)
    except (DbConnectionTestInvalidAddressError, ValueError):
        # H-1/H-3/H-4/round-3 allowlist: reject before ever building
        # host/port/database from an address that fails ANY allowlist check
        # -- unrecognised scheme, unsafe host, missing/out-of-range/
        # unparseable port (ValueError from urlsplit().port, e.g.
        # ":not-a-port"), or an empty/unsafe database segment. The report
        # message is always the generic _INVALID_ADDRESS_MESSAGE, never the
        # caught exception's own text -- a bare ValueError from
        # urlsplit().port can echo the offending raw port substring, so it
        # must never reach the report either.
        return _invalid_report(_INVALID_ADDRESS_MESSAGE)

    if _probe_tcp_reachable(host, port):
        return _reachable_report(host, port, database)

    return _unreachable_report(
        host,
        port,
        database,
        f"Could not reach {host}:{port}/{database} within "
        f"{_PROBE_TIMEOUT_SECONDS:.0f}s ({_SETTING_NAME}).",
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the checker entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Check the shipped test-database connection setting "
            "(testing_context.db_connection_test) before running database "
            "tests. Prints a JSON report and exits 0 only when reachable."
        )
    )
    parser.add_argument(
        "--target-dir",
        required=True,
        help="Project root to resolve testing_context.db_connection_test from.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: print the JSON check_test_db() report and exit.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]`` when
            ``None``.

    Returns:
        0 only when ``status`` is ``"reachable"``; 1 otherwise (matching
        this AC's ``delivers_to`` contract: "Exit 0 only when reachable.").
    """
    args = _build_arg_parser().parse_args(argv)
    target_root = Path(args.target_dir).resolve()
    result = check_test_db(target_root)
    print(json.dumps(result))
    return 0 if result.get("status") == "reachable" else 1


if __name__ == "__main__":
    sys.exit(main())


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-25 [python-coder]: Created scripts/db_check/checker.py for
#   INF-1100d-3-i ("'Not configured' and 'configured but unreachable' are
#   different reports, and neither shows a password") and INF-1100d-3-ii
#   ("A database test run without the setting stops and names the missing
#   setting"). resolve_test_db_address() is the single reader of
#   testing_context.db_connection_test; check_test_db() calls it and adds a
#   bounded TCP reachability probe. Added "db_check" to
#   AGENT_SUPPORT_SCRIPT_DIRS (build_phases_script_deploy.py) so build.py
#   deploys this module. Deliberately does NOT import config_loader.py: a
#   first attempt did, and adding config_loader.py to
#   AGENT_SUPPORT_SCRIPT_FILES to deploy it broke
#   test_consumer_simulation_build_succeeds_in_empty_project (the AC
#   BP-900g-8 closure guard correctly flagged config_loader.py's own reads
#   of config/skills_config.default.json and config/skills_config.schema.
#   json as newly-undeployed once config_loader.py itself became a
#   deployed script). Reverted that manifest entry; resolve_test_db_address
#   instead reads the project's skills_config.json directly, needing no
#   package-defaults file since this setting ships no default address
#   (user decisions Q3/NQ1). Verified via a full
#   `unit_tests/portability/test_consumer_simulation.py` re-run after the
#   revert. (#TICKETLESS reason=fast-lane-inf-1100d-3-ac-pair)
# - 2026-09-25 [python-coder/pr-reviewer-followup]: Fixed three pr-reviewer
#   findings (H-1/H-2/H-3), all reproduced red by test-writer's new tests in
#   test_inf_1100d_3_i.py before this fix:
#   H-1 (credential leak) -- _parse_address() now requires a recognised
#   postgres scheme (postgres/postgresql) AND a non-empty netloc before
#   trusting urlsplit()'s output; anything else raises
#   DbConnectionTestInvalidAddressError (message names the setting only,
#   never the raw value) and check_test_db() reports status "invalid".
#   Previously a scheme-less value like "app:s3cret@host:port/db" made
#   urlsplit() treat "app" as the scheme and returned the rest of the
#   string -- password included -- verbatim as the "database" field.
#   H-2 (crash) -- check_test_db() now also catches
#   DbConnectionTestConfigError (raised when skills_config.json exists but
#   is not valid JSON / unreadable) and reports status "config_error"
#   instead of letting it propagate as an uncaught traceback out of main().
#   H-3 (docstring accuracy) -- reworded the module docstring's claim that
#   this setting "ships no default address" as present fact; INF-1100d-1
#   has not yet removed db_connection_test from
#   config/skills_config.default.json, so config_loader itself may still
#   see the legacy default until that build lands. This resolver never
#   reads package defaults regardless (by design), so its own behaviour is
#   unaffected -- only the docstring's framing was inaccurate.
#   (#TICKETLESS reason=fast-lane-inf-1100d-3-ac-pair)
# - 2026-09-25 [python-coder/pr-reviewer-followup-round-3]: Switched
#   _parse_address() from pattern-patching (rejecting each newly-found
#   hostile shape one at a time -- doubled scheme, path-suffix params, ...)
#   to ALLOWLIST validation, per pr-reviewer's explicit round-3 instruction
#   ("stop pattern-patching"). After the scheme/netloc check, host must
#   match a safe charset (letters/digits/./- or a valid IPv6 literal, via
#   the new _is_safe_host() using ipaddress.IPv6Address), port must be an
#   int in 1-65535, and database (path with the leading '/' stripped) must
#   be non-empty and match ^[A-Za-z0-9._-]+$ with nothing further in the
#   path -- the charset itself excludes '/', so a multi-segment or
#   parameter-suffixed path is rejected as a side effect of the regex, not
#   a separate check. Any failure raises DbConnectionTestInvalidAddressError
#   (or lets ValueError propagate from urlsplit().port); check_test_db()
#   now catches both under one branch and ALWAYS reports the fixed
#   _INVALID_ADDRESS_MESSAGE constant, never str(exc) -- a bare ValueError's
#   own text can echo the offending raw port substring, so the caught
#   exception's message is never trusted into a report. This closes H-3
#   (doubled scheme: "postgresql://postgresql://user:pass@host:port/db" --
#   urlsplit only strips one leading "scheme://", so the second one stayed
#   in .path verbatim) and H-4 (path-suffix parameters:
#   "postgresql://host:port/db;password=..." -- the whole ";password=..."
#   suffix rode along in database and into message) by construction, not by
#   adding two more special cases, and is exercised by the round-3 property
#   guard (test_db_check_report_fields_never_contain_unsafe_characters_or_
#   raw_value, parametrized over 7 shapes including a known-good control).
#   Query strings/fragments are deliberately NOT part of the validated
#   path and are silently ignored rather than rejected or echoed (e.g.
#   "postgresql://h:5432/db?x#frag" is still accepted; .query/.fragment are
#   never read). H-5 (non-UTF-8 skills_config.json): widened
#   _read_project_testing_context()'s existing read try/except from
#   `except OSError` to `except (OSError, UnicodeDecodeError)` so a
#   skills_config.json that exists but is not valid UTF-8 (Path.read_text's
#   own decode failure, a UnicodeDecodeError -- not an OSError) is wrapped
#   into DbConnectionTestConfigError and reported as status "config_error"
#   the same way an invalid-JSON config already was, instead of crashing
#   with an uncaught traceback. All six new red tests
#   (TestDbCheckNeverLeaksCredentialsDoubledScheme,
#   TestDbCheckNeverLeaksCredentialsPathSuffixParams,
#   TestDbCheckReportsConfigErrorForNonUtf8, and the 7-case parametrized
#   property guard counted as one red-baseline entry) confirmed green
#   against this fix; all pre-existing tests in this file and
#   test_inf_1100d_3_ii.py / test_consumer_simulation.py stayed green too.
#   (#TICKETLESS reason=fast-lane-inf-1100d-3-ac-pair)
# - 2026-09-25 [python-coder/pr-reviewer-followup-round-4]: Fixed H-6 (the
#   last pr-reviewer finding): an over-long DNS label crashed the CLI.
#   socket.create_connection()'s internal getaddrinfo() call idna-encodes
#   the host; a single label over the RFC 1035 63-char limit makes that
#   encode raise UnicodeEncodeError, which is NOT an OSError subclass, so
#   _probe_tcp_reachable()'s existing `except OSError` did not catch it --
#   uncaught, same crash shape as H-2/H-5/H-6's own earlier siblings (raw
#   traceback, empty stdout), a fourth distinct exception type. Two-part
#   fix: (1) _is_safe_host() now additionally rejects, for any
#   charset-valid hostname, a single dot-separated label over
#   _MAX_DNS_LABEL_LENGTH (63) chars or a total hostname over
#   _MAX_HOSTNAME_LENGTH (253) chars, so both the 70-char and 5000-char
#   single-label cases are now rejected as status "invalid" by
#   _parse_address() BEFORE ever reaching the socket layer -- the crash
#   site is never called for these two red tests. (2) Defensive-in-depth
#   per the coordinator's explicit instruction: _probe_tcp_reachable() also
#   now catches UnicodeError (the shared base of UnicodeEncodeError/
#   UnicodeDecodeError) alongside OSError, logs it at WARNING (Error
#   Handling Policy Rule 3 -- this IS an unanticipated-shape failure,
#   unlike an ordinary refused/timed-out connection, which is why this
#   branch logs and the plain `except OSError` above deliberately does
#   not), and converts it to the same "unreachable" boolean return rather
#   than crashing -- covers any host shape the allowlist did not
#   anticipate. The >253-total-but-every-label-under-63 shape (304 chars,
#   5 labels of 60) already did not crash before this fix (idna only
#   enforces the per-label limit; getaddrinfo() fails cleanly with
#   socket.gaierror, an OSError already handled) -- it now reports
#   "invalid" instead of "unreachable" per the new total-length check, both
#   of which its test (TestDbCheckReportsInvalidForOverLongTotalHostname, a
#   POSITIVE CONTROL per its own docstring) accepts. All three H-6 red
#   tests (70-char label, 5000-char label, positive control) confirmed
#   green against this fix; every earlier round's test stayed green too
#   (26 passed, 5 subtests, full three-file run).
#   (#TICKETLESS reason=fast-lane-inf-1100d-3-ac-pair)
# - 2026-09-25 [python-coder/GE-127a-1-split]: checker.py had grown to 442
#   lines, over the check-file-size 400-line limit (GE-127a-1), blocking
#   commit. Split into three cohesive modules under scripts/db_check/:
#   _address.py (allowlist URL parsing/validation -- scheme/host/port/
#   database checks, RFC 1035 length limits, DbConnectionTestInvalidAddress
#   Error) and _config.py (locating/reading skills_config.json,
#   DbConnectionTestConfigError), leaving this file with the resolver,
#   check_test_db(), the report builders, and the CLI. No behaviour change
#   -- every extracted function/class moved verbatim; this file re-imports
#   them via a sys.path push to its own directory (see this file's own
#   module docstring, "THE SIBLING-IMPORT MECHANISM") rather than a
#   package-relative import, because this file is invoked both as a
#   standalone script (no parent package, relative imports fail) and as an
#   importable submodule (db_check/ itself is not guaranteed to be on
#   sys.path in that case). Every public/test-pinned name
#   (resolve_test_db_address, check_test_db, all three exception classes,
#   this file's own CLI path) stays importable from checker.py exactly as
#   the tests use it -- no test file was touched. The whole db_check/
#   directory was already in AGENT_SUPPORT_SCRIPT_DIRS
#   (build_phases_script_deploy.py), which deploys every .py file under it
#   recursively, so both new modules are deployed with no manifest change.
#   Verified: `ruff check scripts/db_check/` clean; `AC_ENFORCE_STRICT=1
#   python -m pytest unit_tests/portability/test_inf_1100d_3_ii.py
#   unit_tests/portability/test_consumer_simulation.py -q` green.
#   (#TICKETLESS reason=fast-lane-inf-1100d-3-ac-pair)
# ===========================================================================
