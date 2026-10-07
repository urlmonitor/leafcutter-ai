"""
MODULE: kernel.memory.cli
GOAL: The `python -m kernel decisions validate | index | publish` commands: argument parsing and
    the functions that run them over a repository root and a run root.
BUSINESS CONTEXT: Filing a decision into git is a deliberate act (ADR-060): `publish` writes into
    `docs/decisions/` only when a person invokes it, after validation, so the diff goes through
    normal review. `validate` is what CI and the committed-store test run in place of a new
    pre-commit hook (ADR-059); `index` regenerates the filter index, which is never hand-edited.
ARCHITECTURE: `add_parser` registers the subcommands on the kernel CLI's subparsers; `run_decisions`
    returns (exit code, JSON document) like the other commands (0 ok, 3 refused with the problems
    listed, 5 environment error). The repository root defaults to the kernel checkout and can be
    named with --repo-root (tests and other checkouts); the run root comes from the kernel
    config, never from a flag.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from kernel.bootstrap import resolve_run_root
from kernel.config import ConfigError, load_kernel_config, repo_root
from kernel.memory.codec import RecordReadError
from kernel.memory.publish import PublishResult, publish, rebuild_index
from kernel.memory.validate import SCHEMA_NAME, Problem, load_schema, validate_store
from kernel.memory.vocab import Vocabulary, VocabularyError, load_vocabulary
from kernel.service_errors import CLI_EXIT_CODES

Result = tuple[int, dict[str, Any]]


def add_parser(commands: Any, common: argparse.ArgumentParser) -> None:
    """Register `decisions` and its subcommands on the kernel CLI's subparsers.

    The options sit on each subcommand (`decisions publish --run-id R --config F`), so `common`
    (which also carries --env-file, meaningless here) is not used.
    """
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", help="accepted for compatibility")
    shared.add_argument("--config", type=Path, help="kernel config override file")
    shared.add_argument("--repo-root", type=Path,
                        help="repository holding docs/decisions (default: this checkout)")
    parser = commands.add_parser("decisions", help="validate, index and publish decision records")
    sub = parser.add_subparsers(dest="decisions_command", required=True)
    sub.add_parser("validate", parents=[shared],
                   help="validate every record and that the index is up to date")
    sub.add_parser("index", parents=[shared],
                   help="regenerate docs/decisions/index.json (never hand-edited)")
    pub = sub.add_parser("publish", parents=[shared],
                         help="publish a run's staged record into docs/decisions")
    pub.add_argument("--run-id", required=True)
    pub.add_argument("--correct", action="append", default=[], metavar="OLD_ID",
                     help="also append a correction to this superseded record (explicit only)")
    pub.add_argument("--reason", help="the correction reason (default: the note on the record)")


def _doc(ok: bool, problems: list[Problem], **fields: Any) -> Result:
    """Return (exit code, document): 0 when ok, else 3 with the problems listed."""
    code = CLI_EXIT_CODES["ok"] if ok else CLI_EXIT_CODES["rejected"]
    return code, {"ok": ok, "problems": [p.as_dict() for p in problems], **fields}


def _error(code: str, message: str) -> Result:
    """Return exit code 5 with an error document."""
    return CLI_EXIT_CODES["internal"], {"ok": False, "error": {"code": code, "message": message}}


def _published(result: PublishResult) -> Result:
    """Return the document of a publish run."""
    return _doc(result.ok, result.problems, published=result.published,
                already_present=result.already_present, corrected=result.corrected,
                index_written=result.index_written)


def run_decisions(args: argparse.Namespace, *, root: Path | None = None) -> Result:
    """Run one `decisions` subcommand and return (exit code, JSON document).

    Args:
        args: Parsed arguments (decisions_command, run_id, correct, reason, config, repo_root).
        root: Repository root override (tests); else `--repo-root`, else this checkout.
    """
    base = Path(root or args.repo_root or repo_root()).resolve()
    try:
        config = load_kernel_config(args.config)
        schema = load_schema(base / "config" / SCHEMA_NAME)
        vocab: Vocabulary | None = load_vocabulary(base)
    except (ConfigError, RecordReadError, VocabularyError) as exc:
        return _error("decisions_environment", str(exc))
    folder = config.memory.decisions_folder(base)
    command = args.decisions_command
    if command == "validate":
        report = validate_store(folder, schema=schema, vocab=vocab)
        return _doc(report.ok, report.problems, records=len(report.records))
    if command == "index":
        report, written = rebuild_index(folder, schema, vocab)
        return _doc(report.ok and written, report.problems, records=len(report.records),
                    index_written=written)
    run_root = resolve_run_root(config, base)
    return _published(publish(args.run_id, folder=folder, run_root=run_root, schema=schema,
                              vocab=vocab, correct=args.correct, reason=args.reason))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: `decisions` needs no Jev key and no environment (it never calls a
#   provider), so it bypasses build_environment; the run root is resolved from config exactly as
#   the kernel resolves it, so publish finds what a run staged. (#KernelDecisionStore)
# ====================================================================
