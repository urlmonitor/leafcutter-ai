#!/usr/bin/env python3
"""
MODULE: check_shipped_addresses
AC: INF-1100d-4 -- "The package refuses to ship a database address again"
    INF-1100d-4-i -- "The address check flags real-looking addresses, allows
    obvious placeholders, and leaves unshipped history alone"
GOAL: Prove, deterministically and permanently, that nothing a build copies
    into a consumer install carries a ready-made database connection
    address. Scans exactly the DECLARED shipped roots -- ``templates/``
    (including ``templates/docs/``) and ``config/`` -- for any
    ``<scheme>://[<user>[:<password>]@]<host>:<port>[/<database>]`` address
    with scheme ``postgresql``, ``postgres`` or ``mysql``, and reports every
    hit as ``<path>:<line>: ...``. Also accepts an already-built output
    directory (``--build-root``) so a deployed layout can be scanned in
    full, without any ``templates/``/``config/`` segmentation of its own.
BUSINESS CONTEXT: The package template propagated one adopter's local
    address (``postgresql://trader:trader@localhost:5403/LIVE``) into every
    install (docs/analysis/2026-09-25-test-writers-prove-failure-not-
    discrimination.md, Incident 7). INF-1100d-1/-2 remove the address from
    the shipped sources; this script is the behavioural proof that it
    cannot silently come back -- it must fail on the real pre-fix bytes of
    the five named shipped files at commit e919a24f, and it must stay
    correct on both sides of the edge cases INF-1100d-4-i names: a bare
    ``host:port`` with no credentials is still an address (S1), both
    ``postgres`` and ``postgresql`` scheme spellings count (S2), and
    angle-bracket placeholders, ``${ENV}`` references, ``{{config.*}}``
    placeholders and prose naming the setting are not addresses (S3-S6).
    Being a documentation page or "just history" is no exemption (S7) --
    this check carries NO exclusion list of any kind; the only reason a
    file is never visited is that it falls outside the two declared roots
    (S8, the seam case), never a path-based skip inside them.
ARCHITECTURE: A single small CLI module: ``iter_shipped_files`` walks the
    declared roots (or a build-output tree in full) and yields every
    regular file found; ``scan_file`` reads one file and yields
    ``Finding`` records for every address-shaped match on any line;
    ``main`` composes the two, prints one line per finding, and prints a
    scanned-file-count summary on a clean run. Runs as a real Python
    subprocess (the CLI contract documented in
    ``unit_tests/portability/_inf_1100d_4_shipped_address_harness.py``) --
    never imported by ``build.py``, and never spawns ``build.py`` itself
    (CLAUDE.md's "tests must not spawn their own build.py"). This script is
    not deployed to consumer installs (it guards *this* repository's own
    shipped sources before merge, mirroring ``scripts/ci/
    check_declaring_files.py``'s shape), so no ``scripts/build_phases.py``
    deploy-map entry is required.

Usage::

    python scripts/portability/check_shipped_addresses.py \\
        [--source-root PATH] [--build-root PATH]

    - No flags: scan the declared shipped roots (``templates/`` -- including
      ``templates/docs/`` -- and ``config/``) relative to the current
      working directory. This is the normal-suite entry point.
    - ``--source-root PATH``: treat ``PATH`` as a repo-root-shaped directory
      and scan only ``PATH/templates`` and ``PATH/config`` -- the same
      declared-roots rule as the no-flags case, just rooted elsewhere.
      Anything else under ``PATH`` is never visited, by construction, not
      by an exclusion list.
    - ``--build-root PATH``: treat ``PATH`` as an already-built output
      directory and scan it in full.

Exit codes:
    0 -- a clean run: at least one shipped file was scanned and none
        contained a matching address.
    1 -- one or more addresses were found (named on stdout, one per line),
        OR the scan visited zero files (a zero-file scan must never report
        success).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Concrete schemes this AC pair names -- both accepted spellings of the
# Postgres scheme, plus mysql. No other scheme is in scope (INF-1100d-4's
# own criteria: "scheme postgresql, postgres or mysql").
_SCHEMES = ("postgresql", "postgres", "mysql")

# A "concrete" credential/host/database token: letters, digits, dots,
# underscores and hyphens only. Deliberately excludes every character an
# allowed placeholder form uses -- ``<``/``>`` (angle-bracket placeholders),
# ``$``/``{``/``}`` (``${ENV}`` and ``{{config.*}}`` placeholders) -- so
# S3-S5 fail to match by construction, not via a second placeholder-
# detection pass. The port is matched separately as digits-only, which is
# what excludes S3's ``<port>`` (letters, not digits) without a special
# case.
_TOKEN = r"[A-Za-z0-9_.\-]+"

_ADDRESS_RE = re.compile(
    r"(?P<scheme>" + "|".join(_SCHEMES) + r")://"
    r"(?:(?P<user>" + _TOKEN + r")(?::(?P<password>" + _TOKEN + r"))?@)?"
    r"(?P<host>" + _TOKEN + r")"
    r":(?P<port>\d+)"
    r"(?:/(?P<database>" + _TOKEN + r"))?"
)

# The two declared shipped roots (INF-1100d-4's it_requirements: "Declare
# these roots positively in ONE place that the check and its tests share").
# There is no exclusion list anywhere in this module -- everything outside
# these two directory names, under whichever root is being scanned, is
# simply never walked.
SHIPPED_SUBDIRS = ("templates", "config")


@dataclass(frozen=True)
class Finding:
    """One address-shaped match: the file it was found in, its 1-indexed
    line number, and the matched text (for a human-readable report line).
    """

    path: Path
    line: int
    matched_text: str


def iter_shipped_files(root: Path) -> list[Path]:
    """Yield every regular file under the declared shipped roots
    (``root/templates`` and ``root/config``), sorted for deterministic
    output. A root whose ``templates``/``config`` subdirectory does not
    exist simply contributes no files from that subdirectory -- this is
    the positive declaration INF-1100d-4-i's seam test exists to prove:
    nothing outside these two names, anywhere under ``root``, is ever
    visited.

    Args:
        root: The repo-root-shaped directory to resolve ``templates`` and
            ``config`` under (either the real repo root or a
            ``--source-root`` temp tree).

    Returns:
        A sorted list of every regular file found under ``root/templates``
        and ``root/config``.
    """
    files: list[Path] = []
    for subdir in SHIPPED_SUBDIRS:
        base = root / subdir
        if not base.is_dir():
            continue
        files.extend(p for p in base.rglob("*") if p.is_file())
    return sorted(files)


def iter_build_output_files(root: Path) -> list[Path]:
    """Yield every regular file under an already-built ``root``, in full --
    a deployed layout has no ``templates``/``config`` segmentation of its
    own, so the whole tree is the scan scope.
    """
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file())


def _read_text(path: Path) -> str | None:
    """Read *path* as UTF-8 text. Returns ``None`` (never raises) when the
    file cannot be decoded as text -- a binary asset under a shipped root
    (an image, for example) is still counted as scanned, just contributes
    no findings.
    """
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return None


def scan_file(path: Path) -> list[Finding]:
    """Return every address-shaped match found in *path*, one ``Finding``
    per match, in file order. A file that cannot be read as text yields no
    findings (see ``_read_text``).

    Args:
        path: The file to scan.

    Returns:
        A list of ``Finding`` records, one per address-shaped match, in the
        order they appear in the file. Empty when no match is found or the
        file cannot be decoded as text.
    """
    text = _read_text(path)
    if text is None:
        return []
    findings = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in _ADDRESS_RE.finditer(line):
            findings.append(Finding(path=path, line=lineno, matched_text=match.group(0)))
    return findings


def _format_finding(finding: Finding) -> str:
    return f"{finding.path}:{finding.line}: possible database connection address ({finding.matched_text!r})"


def run_scan(files: list[Path]) -> tuple[list[Finding], int]:
    """Scan every file in *files*, returning ``(findings, scanned_count)``.
    ``scanned_count`` is the number of files actually visited, independent
    of whether any of them produced a finding -- this is what lets a clean
    run's summary state a real, non-zero count (INF-1100d-4's own
    it_requirement: "a scan that found zero files must not report
    success").
    """
    findings: list[Finding] = []
    for path in files:
        findings.extend(scan_file(path))
    return findings, len(files)


def _resolve_files(args: argparse.Namespace) -> list[Path]:
    if args.build_root is not None:
        return iter_build_output_files(args.build_root)
    if args.source_root is not None:
        return iter_shipped_files(args.source_root)
    return iter_shipped_files(Path.cwd())


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        help="Repo-root-shaped directory; scans only PATH/templates and PATH/config.",
    )
    parser.add_argument(
        "--build-root",
        type=Path,
        help="Already-built output directory; scanned in full.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Command-line arguments (``--source-root`` / ``--build-root``),
            or ``None`` to parse ``sys.argv``.

    Returns:
        0 on a clean run over at least one shipped file; 1 when any address
        is found or the scan visited zero files.
    """
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    files = _resolve_files(args)
    findings, scanned_count = run_scan(files)

    if scanned_count == 0:
        print(
            "SHIPPED ADDRESS CHECK FAILED: scanned 0 shipped files -- a "
            "zero-file scan must never report success.",
            file=sys.stderr,
        )
        return 1

    if findings:
        print(
            f"SHIPPED ADDRESS CHECK FAILED: {len(findings)} finding(s) across "
            f"{scanned_count} scanned shipped file(s):",
            file=sys.stderr,
        )
        for finding in findings:
            print(_format_finding(finding), file=sys.stderr)
        return 1

    print(f"SHIPPED ADDRESS CHECK OK: {scanned_count} shipped file(s) scanned, no addresses found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-28 14:00 [python-coder/fast-lane]: Created for INF-1100d-4 /
#   INF-1100d-4-i. Declares the shipped roots (templates/, config/) in one
#   place (SHIPPED_SUBDIRS) shared by both --source-root and the no-flags
#   default, so the check and the tests that assert its scope cannot drift
#   apart. Detection is a single regex requiring a scheme, a concrete
#   (non-placeholder) host, and a digits-only port -- credentials optional,
#   database suffix optional -- which is what makes a bare host:port (S1)
#   and both accepted scheme spellings (S2) match while angle-bracket,
#   ${ENV} and {{config.*}} placeholders (S3-S5) and plain prose (S6) fail
#   to match by construction, never via a second placeholder-detection
#   pass or an exclusion list. No literal of the old shipped address
#   appears anywhere in this module (NQ1).
# ====================================================================
