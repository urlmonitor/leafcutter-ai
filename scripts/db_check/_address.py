"""
MODULE: _address
GOAL: ALLOWLIST-validate a configured test-database URL and split it into
    ``(host, port, database)`` -- never userinfo, never anything outside a
    conservative safe charset -- for the shipped test-database checker
    (``checker.py``).
BUSINESS CONTEXT: A string this module rejects can never reach a JSON report
    or a log line, which is the whole safety property INF-1100d-3-i's
    "neither shows a password" criterion depends on. Several rounds of
    pr-reviewer findings (H-1 scheme-less/malformed-scheme, H-3 doubled
    scheme, H-4 path-suffix parameters, H-6 over-long DNS labels) each
    exploited a different way ``urllib.parse.urlsplit()`` can be misled into
    returning credential-bearing or otherwise unsafe text -- this module's
    ALLOWLIST design (round 3: "stop pattern-patching, switch to allowlist
    validation") means a new hostile shape has to defeat every one of host/
    port/database's independent charset and length checks simultaneously to
    leak anything, rather than needing its own bespoke rejection rule added
    after the fact.
ARCHITECTURE: Split out of ``checker.py`` (pr-reviewer/GE-127a-1
    file-size-ratchet follow-up: checker.py exceeded the 400-line
    check-file-size limit) alongside its sibling ``_config.py``. One public
    surface -- the ``DbConnectionTestInvalidAddressError`` exception -- and
    two private functions: ``_is_safe_host()`` (charset + RFC 1035 length
    checks, plus IPv6-literal validation via ``ipaddress``) and
    ``_parse_address()`` (the orchestrating pure validator ``checker.py``'s
    ``check_test_db()`` calls). ``checker.py`` imports all three via a
    ``sys.path`` push to its own directory (see ``checker.py``'s module
    docstring for why: it must resolve identically whether ``checker.py``
    runs as a standalone CLI script or is imported as ``db_check.checker``).
    Deployed as part of the whole ``scripts/db_check/`` directory (already
    declared in ``AGENT_SUPPORT_SCRIPT_DIRS``, ``build_phases_script_deploy.
    py`` -- no new deploy-manifest entry needed).
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

# Private, deliberately duplicated from checker.py's own _SETTING_NAME
# (rather than imported back from it) to avoid a circular import between
# this module and checker.py -- checker.py imports FROM this module, so
# this module must not import anything back from checker.py. A one-line
# string constant duplicated across two private submodules of the same
# package is a fully acceptable trade-off for that (see the build_phases.py
# / build_helpers.py split precedent this repo already follows).
_SETTING_NAME = "testing_context.db_connection_test"

# Generic invalid-address message (H-1/H-3/H-4/H-5/H-6's shared fix point):
# names only the setting, never any part of the raw configured value, so
# every rejection path in _parse_address() raises with the exact same safe
# text regardless of WHICH allowlist check failed.
_INVALID_ADDRESS_MESSAGE = (
    f"{_SETTING_NAME} is not a valid postgres connection URL (expected "
    "postgres:// or postgresql:// with a safe host, port, and database "
    "segment)."
)

# Recognised postgres URL schemes. A value that does not parse with one of
# these AND a non-empty netloc is rejected as "invalid" before urlsplit's
# scheme-vs-path ambiguity for scheme-less input (e.g. "user:pass@host:
# port/db", which urlsplit reads as scheme="user", path="pass@host:port/db")
# can absorb credentials into a field this module reports.
_RECOGNISED_SCHEMES = ("postgres", "postgresql")

# ALLOWLIST charsets (pr-reviewer round 3: "stop pattern-patching, switch to
# allowlist validation"). Rather than special-casing every new hostile shape
# pr-reviewer finds (scheme-less, malformed-scheme, doubled-scheme,
# path-suffix parameters, embedded spaces, ...), every field this module
# returns must positively match one of these conservative charsets before it
# is trusted at all -- an unrecognised shape is rejected outright, not
# guessed at. A bracketed IPv6 host is validated separately via the
# ``ipaddress`` stdlib module in ``_is_safe_host()`` below, since
# ``urlsplit().hostname`` already strips the brackets and lower-cases the
# literal, leaving the same colon-separated hex form ``ipaddress`` parses.
_HOST_SAFE_RE = re.compile(r"^[A-Za-z0-9.-]+$")
_DATABASE_SAFE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_MIN_PORT = 1
_MAX_PORT = 65535

# RFC 1035 DNS length limits (H-6): a single label over 63 chars makes
# socket.create_connection()'s internal getaddrinfo() call raise
# UnicodeEncodeError while idna-encoding the host (not an OSError subclass,
# so it is not caught by checker.py's _probe_tcp_reachable()'s existing
# `except OSError`) -- reject it here, before the socket layer is ever
# reached, rather than relying solely on the defensive catch added to
# _probe_tcp_reachable() there. The 253-char TOTAL limit is enforced for the
# same reason even though Python's idna codec does not itself enforce it (a
# >253 host with every label under 63 chars reaches getaddrinfo() and fails
# cleanly with socket.gaierror, an OSError subclass already handled) --
# rejecting it at the allowlist stage keeps "invalid" the single source of
# truth for a malformed-shaped hostname rather than splitting that decision
# between two call sites.
_MAX_HOSTNAME_LENGTH = 253
_MAX_DNS_LABEL_LENGTH = 63


class DbConnectionTestInvalidAddressError(RuntimeError):
    """Raised by ``_parse_address()`` when the configured value does not
    parse as a proper URL with a recognised postgres scheme, OR when its
    host, port, or database segment fails the ALLOWLIST check (H-1/H-3/H-4/
    H-6: doubled scheme, path-suffix parameters, space-containing database,
    an over-long DNS label, ...). Never carries the raw value or any part of
    it -- only a generic message naming the setting -- so no hostile or
    merely-unanticipated shape ``urlsplit()`` might misparse can ever reach
    a report."""


def _is_safe_host(host: str) -> bool:
    """True when *host* is a plain hostname/IPv4 literal (letters, digits,
    ``.``, ``-``) or a valid IPv6 literal.

    Pure function: no I/O. ``urlsplit()`` only ever produces a
    colon-bearing ``.hostname`` from a BRACKETED IPv6 netloc (a bare
    ``host:port`` uses the colon as the port separator instead), so any
    host reaching this function with a colon in it came from a genuine
    ``[...]`` literal -- validated here via ``ipaddress.IPv6Address``
    rather than trusted on charset alone.

    For a charset-valid hostname, also enforces the RFC 1035 length limits
    (H-6): no single dot-separated label over ``_MAX_DNS_LABEL_LENGTH``
    (63) chars, and no total length over ``_MAX_HOSTNAME_LENGTH`` (253)
    chars -- both otherwise reach ``socket.create_connection()`` (the
    per-label case crashes it; see this module's docstring near those
    constants).

    Args:
        host: The candidate host string (already extracted via
            ``urlsplit().hostname``, so it never contains userinfo).

    Returns:
        ``True`` when *host* is a safe, RFC-1035-length-bounded
        hostname/IPv4 literal or a valid IPv6 literal; ``False`` otherwise.
    """
    if _HOST_SAFE_RE.match(host):
        if len(host) > _MAX_HOSTNAME_LENGTH:
            return False
        return all(len(label) <= _MAX_DNS_LABEL_LENGTH for label in host.split("."))
    try:
        ipaddress.IPv6Address(host)
    except ValueError:
        return False
    return True


def _parse_address(address: str) -> tuple[str, int, str]:
    """Validate *address* against an ALLOWLIST and return ``(host, port,
    database)`` -- never userinfo, never anything outside the validated
    charsets.

    Pure function: no I/O, no external service call. Only returns when
    EVERY field independently passes its own allowlist check; any failure
    -- unrecognised scheme, missing netloc, unsafe host, missing/
    out-of-range/unparseable port, or an empty/unsafe database segment --
    raises rather than guessing or returning a partially-trusted value.
    Query strings and fragments are ignored (never echoed): they carry no
    information this module reports, so a query/fragment-bearing but
    otherwise well-formed URL is still accepted.

    Args:
        address: A configured test-database URL, e.g.
            ``postgresql://user:pass@host:5432/dbname``.

    Returns:
        ``(host, port, database)``, all independently allowlist-validated.
        ``urlsplit().hostname``/``.path`` never include userinfo, and this
        function additionally refuses to return either unless it matches a
        conservative safe charset -- so no delimiter (``@``, ``;``, ``=``,
        space, an extra ``/``, a doubled scheme, ...) from a misparsed or
        hostile value can ever reach a report field.

    Raises:
        DbConnectionTestInvalidAddressError: When *address* does not parse
            with a recognised postgres scheme (``postgres`` /
            ``postgresql``) and a non-empty netloc, or when the resolved
            host, port, or database segment fails its allowlist check.
            Never carries the raw value -- message names only the setting.
        ValueError: Propagated from ``urlsplit().port`` for a non-numeric
            port segment (e.g. ``:not-a-port``) -- a pure re-raise, not
            caught here (Error Handling Policy Rule 4: this function does
            no I/O, so its own exceptions propagate to the caller).
    """
    parsed = urlsplit(address)
    if parsed.scheme not in _RECOGNISED_SCHEMES or not parsed.netloc:
        raise DbConnectionTestInvalidAddressError(_INVALID_ADDRESS_MESSAGE)  # noqa: TRY003

    host = parsed.hostname
    database = parsed.path.lstrip("/")
    port = parsed.port  # may raise ValueError; left to propagate (see Raises above)

    if (
        host is None
        or not _is_safe_host(host)
        or port is None
        or not (_MIN_PORT <= port <= _MAX_PORT)
        or not database
        or not _DATABASE_SAFE_RE.match(database)
    ):
        raise DbConnectionTestInvalidAddressError(_INVALID_ADDRESS_MESSAGE)  # noqa: TRY003

    return host, port, database


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-25 [python-coder/GE-127a-1-split]: Extracted from checker.py
#   verbatim (DbConnectionTestInvalidAddressError, _RECOGNISED_SCHEMES,
#   _HOST_SAFE_RE, _DATABASE_SAFE_RE, _MIN_PORT, _MAX_PORT,
#   _MAX_HOSTNAME_LENGTH, _MAX_DNS_LABEL_LENGTH, _is_safe_host,
#   _parse_address -- including the round-3 allowlist rewrite and the H-6
#   length checks already fixed there) to bring checker.py back under the
#   400-line check-file-size limit (GE-127a-1/pr-reviewer). Also carries a
#   deliberately-duplicated private copy of _SETTING_NAME and the derived
#   _INVALID_ADDRESS_MESSAGE constant (see the comment above _SETTING_NAME
#   for why: avoiding a circular import with checker.py). No behaviour
#   change: checker.py re-imports DbConnectionTestInvalidAddressError,
#   _INVALID_ADDRESS_MESSAGE, and _parse_address via a sys.path push to its
#   own directory (see checker.py's module docstring) so `check_test_db()`
#   calls them exactly as before the split.
#   (#TICKETLESS reason=fast-lane-inf-1100d-3-ac-pair)
# ===========================================================================
