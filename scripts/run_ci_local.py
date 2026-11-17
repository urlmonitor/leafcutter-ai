#!/usr/bin/env python3
"""
run_ci_local.py — Run the CI gates locally, no GitHub runner required.

Mirrors .github/workflows/ci.yml: the same checks CI runs, executed on your
machine. Useful when GitHub-hosted runners are unavailable, or as a fast
pre-push self-check.

Gates (blocking ones fail the overall run; informational ones only report):
  - lint            : check_lint_gate.py --mode full (leafcutter-lint.json) [blocking]
  - component-vocab : python scripts/check_component_vocab.py       [blocking]
  - typecheck       : the required "mypy ratchet (new errors only)" check:
                      scripts/ci/mypy_ratchet.py, with the arguments ci.yml's
                      job typecheck gives it, base origin/<base-branch>     [blocking]
  - tests           : pytest tests/ unit_tests/ (collection-tolerant) [informational]

The typecheck gate holds no pathspec list of its own: it reads the ratchet call
out of ci.yml (BP-1300f-1-viii). Its verdicts: PASS; FAIL for a new mypy error or
a new `# type: ignore`; FAIL for could-not-check (ratchet exit 2, or no ratchet
call readable from ci.yml); NOTHING INSPECTED when the branch changes no Python
file in scope, which does not fail the run (CI's check is green then too) but is
never shown as PASS. CI fetches the base branch before it runs the ratchet; this
script does not fetch, so run `git fetch origin main` first for CI's exact merge
base.

Exit code: 0 if all BLOCKING gates pass, 1 otherwise. Informational gate
failures are reported but do not change the exit code (matching ci.yml's
continue-on-error jobs).

Usage:
    python3 scripts/run_ci_local.py [--include-informational] [--repo-root <path>]
        [--base-branch main] [--only lint|component-vocab|typecheck|tests ...]
"""

from __future__ import annotations

import argparse
import logging
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("run_ci_local")

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent

# Exactly the command ci.yml's `lint` job runs (BP-1300e-1-i): what is linted and by which
# rules is declared once in leafcutter-lint.json, so this mirror holds no tree list of its own.
LINT_GATE_COMMAND = ["templates/scripts/commit_guardian/check_lint_gate.py", "--mode", "full"]

# Where the typecheck gate's command comes from (BP-1300f-1-viii): the step of ci.yml's job
# `typecheck` that calls the ratchet. Its pathspecs are written there and nowhere else.
CI_WORKFLOW = Path(".github") / "workflows" / "ci.yml"
CI_TYPECHECK_JOB = "typecheck"
RATCHET_SCRIPT = "scripts/ci/mypy_ratchet.py"
CI_BASE_REF = "${{ github.base_ref }}"

GATE_KEYS = ("lint", "component-vocab", "typecheck", "tests")
PASS, FAIL, NOTHING_INSPECTED = "PASS", "FAIL", "NOTHING INSPECTED"
_RATCHET_NOTHING_INSPECTED = "NOTHING INSPECTED"


class CiMirrorError(Exception):
    """The ratchet call could not be read out of ci.yml."""

    @classmethod
    def unreadable(cls, path: Path, exc: Exception) -> CiMirrorError:
        return cls(f"could not read {path}: {exc}")

    @classmethod
    def no_call(cls, path: Path, detail: str) -> CiMirrorError:
        return cls(f"{path} holds no readable {RATCHET_SCRIPT} call in job {CI_TYPECHECK_JOB!r}: {detail}")


def _gate(key: str, name: str, argv: list[str] | None, blocking: bool,
          error: str | None = None) -> dict[str, Any]:
    return {"key": key, "name": name, "argv": argv, "blocking": blocking, "error": error}


def _ratchet_call_line(run: str) -> str | None:
    """The ratchet call of a ci.yml `run:` script, backslash-newline continuations joined."""
    joined = run.replace("\\\n", " ")
    for line in joined.splitlines():
        if RATCHET_SCRIPT in line and not line.lstrip().startswith("#"):
            return line.strip()
    return None


def _typecheck_run(workflow: Any, path: Path) -> str:
    """The `run:` script of the job-typecheck step that calls the ratchet."""
    jobs = workflow.get("jobs") if isinstance(workflow, dict) else None
    job = jobs.get(CI_TYPECHECK_JOB) if isinstance(jobs, dict) else None
    steps = job.get("steps") if isinstance(job, dict) else None
    if not isinstance(steps, list):
        raise CiMirrorError.no_call(path, f"no job {CI_TYPECHECK_JOB!r} with steps")
    runs = [s["run"] for s in steps if isinstance(s, dict) and RATCHET_SCRIPT in str(s.get("run", ""))]
    if len(runs) != 1:
        raise CiMirrorError.no_call(path, f"{len(runs)} steps call it, expected exactly 1")
    return str(runs[0])


def typecheck_command(repo_root: Path, base_branch: str) -> list[str]:
    """CI's ratchet call, as argv for this interpreter, with the base branch filled in.

    Raises CiMirrorError when ci.yml cannot be read or holds no single ratchet call.
    """
    path = repo_root / CI_WORKFLOW
    try:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        logger.warning("could not read %s: %s", path, exc)
        raise CiMirrorError.unreadable(path, exc) from exc
    line = _ratchet_call_line(_typecheck_run(workflow, path))
    if line is None:
        raise CiMirrorError.no_call(path, "the step's run holds no command line naming it")
    tokens = shlex.split(line)
    if len(tokens) < 2 or tokens[1] != RATCHET_SCRIPT or "--" not in tokens:
        raise CiMirrorError.no_call(path, f"unexpected command {line!r}")
    return [sys.executable, *(token.replace(CI_BASE_REF, base_branch) for token in tokens[1:])]


def _typecheck_gate(repo_root: Path, base_branch: str) -> dict[str, Any]:
    name = "typecheck (mypy ratchet)"
    try:
        return _gate("typecheck", name, typecheck_command(repo_root, base_branch), blocking=True)
    except CiMirrorError as exc:
        return _gate("typecheck", name, None, blocking=True, error=str(exc))


def build_gates(repo_root: Path, include_informational: bool, base_branch: str) -> list[dict[str, Any]]:
    """Every gate this run would execute, in order, before any --only filter."""
    py = sys.executable
    gates = [
        _gate("lint", "lint (ruff)", [py, *LINT_GATE_COMMAND], blocking=True),
        _gate("component-vocab", "component-vocab", [py, "scripts/check_component_vocab.py"], blocking=True),
        _typecheck_gate(repo_root, base_branch),
    ]
    if include_informational:
        gates.append(_gate(
            "tests", "tests (pytest)",
            [py, "-m", "pytest", "tests/", "unit_tests/", "-q", "--continue-on-collection-errors"],
            blocking=False,
        ))
    return gates


def _verdict(gate: dict[str, Any], returncode: int, output: str) -> str:
    """PASS / FAIL / NOTHING INSPECTED for one finished gate."""
    if returncode != 0:
        return FAIL
    if gate["key"] == "typecheck" and _RATCHET_NOTHING_INSPECTED in output:
        return NOTHING_INSPECTED
    return PASS


def _stream(argv: list[str], repo_root: Path) -> tuple[int, str]:
    """Run *argv*, echoing its combined output line by line; return (exit code, output)."""
    kept: list[str] = []
    try:
        with subprocess.Popen(argv, cwd=str(repo_root), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, errors="replace") as proc:
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line, end="", flush=True)
                kept.append(line)
            returncode = proc.wait()
    except OSError as exc:
        logger.warning("could not run %s: %s", argv[0], exc)
        raise
    return returncode, "".join(kept)


def _run(gate: dict[str, Any], repo_root: Path) -> tuple[str, float]:
    """Run one gate; return (verdict, seconds). Streams the gate's own output."""
    start = time.monotonic()
    shown = " ".join(gate["argv"]) if gate["argv"] else "(no command)"
    print(f"\n{'=' * 70}\n▶ {gate['name']}  [{'blocking' if gate['blocking'] else 'informational'}]"
          f"\n  $ {shown}\n{'=' * 70}", flush=True)
    if gate["error"] is not None:
        print(f"  COULD NOT CHECK -- {gate['error']}", flush=True)
        return FAIL, time.monotonic() - start
    try:
        returncode, output = _stream(gate["argv"], repo_root)
    except OSError as exc:
        logger.warning("gate %s could not start: %s", gate["name"], exc)
        print(f"  ERROR: could not run gate {gate['name']}: {exc}", file=sys.stderr)
        return FAIL, time.monotonic() - start
    if gate["key"] == "typecheck" and returncode not in (0, 1):
        print(f"  COULD NOT CHECK -- the ratchet exited {returncode}; this is a failure, not a pass.")
    return _verdict(gate, returncode, output), time.monotonic() - start


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", default=str(_REPO_ROOT),
                        help=f"Repo root. Default: {_REPO_ROOT}")
    parser.add_argument("--include-informational", action="store_true",
                        help="Also run the informational gate (tests).")
    parser.add_argument("--base-branch", default="main",
                        help="Branch the typecheck gate compares against, as origin/<branch>. Default: main.")
    parser.add_argument("--only", action="append", choices=GATE_KEYS, default=None,
                        help="Run only this gate (repeatable). 'tests' implies --include-informational.")
    return parser


def _summarise(results: list[tuple[dict[str, Any], str, float]]) -> int:
    print(f"\n{'=' * 70}\nLocal CI summary\n{'=' * 70}")
    blocking_failed = False
    for gate, verdict, secs in results:
        tag = "" if gate["blocking"] else " (informational)"
        print(f"  [{verdict}] {gate['name']}{tag}  ({secs:.1f}s)")
        if gate["blocking"] and verdict == FAIL:
            blocking_failed = True
    if blocking_failed:
        print("\n✗ Local CI FAILED — a blocking gate did not pass.")
        return 1
    empty = [gate["name"] for gate, verdict, _secs in results if verdict == NOTHING_INSPECTED]
    if empty:
        print(f"\n✓ Local CI passed (no blocking gate failed); {', '.join(empty)} inspected nothing.")
        return 0
    print("\n✓ Local CI passed (all blocking gates green).")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = Path(args.repo_root)
    include_informational = args.include_informational or "tests" in (args.only or [])
    gates = build_gates(repo_root, include_informational, args.base_branch)
    if args.only:
        gates = [gate for gate in gates if gate["key"] in args.only]

    results = []
    for gate in gates:
        verdict, secs = _run(gate, repo_root)
        results.append((gate, verdict, secs))
    return _summarise(results)


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-11-17 [BrainCandy/BP-1300f-1-viii]: The typecheck gate was
#   informational `mypy ... scripts`, which aborts at once on "Duplicate module
#   named window_total" and so checked nothing, and was not the check CI
#   requires. It now runs the ratchet call read out of ci.yml's job typecheck
#   (no pathspec copy here), blocking and on by default; exit 2 and an
#   unreadable ci.yml are FAIL (could not check); NOTHING INSPECTED is shown
#   as such, never as PASS. Added --only and --base-branch.
#   (#TICKETLESS reason=bp-1300f-ac-driven-no-ticket-file)
# ====================================================================
