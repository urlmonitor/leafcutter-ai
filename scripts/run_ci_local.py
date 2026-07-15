#!/usr/bin/env python3
"""
run_ci_local.py — Run the CI gates locally, no GitHub runner required.

Mirrors .github/workflows/ci.yml: the same checks CI runs, executed on your
machine. Useful when GitHub-hosted runners are unavailable, or as a fast
pre-push self-check.

Gates (blocking ones fail the overall run; informational ones only report):
  - lint            : ruff check scripts tests unit_tests          [blocking]
  - component-vocab : python scripts/check_component_vocab.py       [blocking]
  - tests           : pytest tests/ unit_tests/ (collection-tolerant) [informational]
  - typecheck       : mypy on scripts (informational)              [informational]

Exit code: 0 if all BLOCKING gates pass, 1 otherwise. Informational gate
failures are reported but do not change the exit code (matching ci.yml's
continue-on-error jobs).

Usage:
    python3 scripts/run_ci_local.py [--include-informational] [--repo-root <path>]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent


def _gate(name: str, argv: list[str], blocking: bool) -> dict:
    return {"name": name, "argv": argv, "blocking": blocking}


def _run(gate: dict, repo_root: Path) -> tuple[bool, float]:
    """Run one gate; return (passed, seconds). Streams the gate's own output."""
    start = time.monotonic()
    print(f"\n{'=' * 70}\n▶ {gate['name']}  [{'blocking' if gate['blocking'] else 'informational'}]"
          f"\n  $ {' '.join(gate['argv'])}\n{'=' * 70}", flush=True)
    try:
        result = subprocess.run(gate["argv"], cwd=str(repo_root))
        passed = result.returncode == 0
    except OSError as exc:
        print(f"  ERROR: could not run gate: {exc}", file=sys.stderr)
        passed = False
    return passed, time.monotonic() - start


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(_REPO_ROOT),
                        help=f"Repo root. Default: {_REPO_ROOT}")
    parser.add_argument("--include-informational", action="store_true",
                        help="Also run the informational gates (tests, typecheck).")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)
    py = sys.executable

    gates = [
        _gate("lint (ruff)", ["ruff", "check", "scripts", "tests", "unit_tests"], blocking=True),
        _gate("component-vocab", [py, "scripts/check_component_vocab.py"], blocking=True),
    ]
    if args.include_informational:
        gates.append(_gate(
            "tests (pytest)",
            [py, "-m", "pytest", "tests/", "unit_tests/", "-q",
             "--continue-on-collection-errors"],
            blocking=False,
        ))
        gates.append(_gate(
            "typecheck (mypy)",
            [py, "-m", "mypy", "--ignore-missing-imports", "--explicit-package-bases",
             "--no-error-summary", "scripts"],
            blocking=False,
        ))

    results = []
    for gate in gates:
        passed, secs = _run(gate, repo_root)
        results.append((gate, passed, secs))

    print(f"\n{'=' * 70}\nLocal CI summary\n{'=' * 70}")
    blocking_failed = False
    for gate, passed, secs in results:
        status = "PASS" if passed else "FAIL"
        tag = "" if gate["blocking"] else " (informational)"
        print(f"  [{status}] {gate['name']}{tag}  ({secs:.1f}s)")
        if gate["blocking"] and not passed:
            blocking_failed = True

    if blocking_failed:
        print("\n✗ Local CI FAILED — a blocking gate did not pass.")
        return 1
    print("\n✓ Local CI passed (all blocking gates green).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
