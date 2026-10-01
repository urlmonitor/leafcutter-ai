"""
MODULE: kernel.adapters.cli
GOAL: The `python -m kernel` command line: run, resume, status, cancel, gaps and install-skill,
    each printing exactly one JSON document on stdout and returning a documented exit code.
BUSINESS CONTEXT: A cooperative client (the Claude Code skill) drives the kernel as a sequence of
    short processes (Rev 3 section 11.2). It must tell a normal workflow state from a protocol
    failure by exit code alone, and must never need to parse logs.
ARCHITECTURE: Exit codes: 0 an envelope was produced (waiting_*, blocked, partial, failed and
    cancelled are normal states); 2 usage error (argparse); 3 input or submission rejected, state
    unchanged; 4 unknown run; 5 internal or environment error. During a command `sys.stdout` is
    pointed at stderr so a chatty library cannot corrupt the one JSON document. Every command
    except install-skill builds the environment from config only (the run root comes from
    config, never from a flag).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from kernel.adapters.claude_code.install import InstallRefused, install_skill
from kernel.adapters.cli_io import (
    CliInputError,
    emit,
    parse_actor,
    read_json_input,
    safe_run_id,
    validation_details,
)
from kernel.bootstrap import KernelEnvironment, build_environment
from kernel.config import ConfigError
from kernel.contracts.run import CapabilityGap
from kernel.contracts.task import TaskInput
from kernel.observability.redaction import Redactor
from kernel.persistence.gap_store import is_build_opportunity
from kernel.registry.adapter import RegistryError
from kernel.service import KernelService
from kernel.service_errors import (
    CLI_EXIT_CODES,
    InvalidTaskInput,
    ProviderUnavailable,
    RegistryChanged,
    RunNotFound,
    SubmissionRejected,
    error_payload,
)

logger = logging.getLogger(__name__)

EnvironmentFactory = Callable[..., KernelEnvironment]
Result = tuple[int, dict[str, Any]]
INPUT_FLAGS = ("--input-file", "--input", "--response", "--response-file")


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for all commands."""
    parser = argparse.ArgumentParser(
        prog="python -m kernel",
        description="Leafcutter decision kernel. Prints one JSON document on stdout.")
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="accepted for compatibility; "
                        "output is always JSON")
    common.add_argument("--config", type=Path, help="kernel config override file")
    common.add_argument("--env-file", type=Path, help="env file holding credentials")
    run = commands.add_parser("run", parents=[common], help="start a run from a TaskInput")
    run.add_argument(*INPUT_FLAGS, dest="input_file", help="TaskInput JSON file, or - for stdin")
    resume = commands.add_parser("resume", parents=[common], help="answer a pending interaction")
    resume.add_argument("--run-id", required=True)
    resume.add_argument(*INPUT_FLAGS, dest="input_file",
                        help="submission JSON file, or - for stdin")
    status = commands.add_parser("status", parents=[common], help="show the current envelope")
    status.add_argument("--run-id", required=True)
    cancel = commands.add_parser("cancel", parents=[common], help="cancel a run")
    cancel.add_argument("--run-id", required=True)
    cancel.add_argument("--actor", required=True, help="human:<id>")
    commands.add_parser("gaps", parents=[common],
                        help="show the aggregated capability gaps (deduplicated)")
    install = commands.add_parser("install-skill", help="install the Claude Code skill")
    install.add_argument("--json", action="store_true")
    install.add_argument("--target-dir", required=True, type=Path,
                         help="a skills directory such as <project>/.claude/skills")
    install.add_argument("--name", required=True)
    install.add_argument("--force", action="store_true")
    return parser


def _rejected(code: str, message: str, details: dict[str, Any] | None = None,
              envelope: Any = None) -> Result:
    """Return exit code 3 with the error payload."""
    return CLI_EXIT_CODES["rejected"], error_payload(code, message, details, envelope)


def _internal(code: str, message: str) -> Result:
    """Return exit code 5 with the error payload."""
    return CLI_EXIT_CODES["internal"], error_payload(code, message)


def gaps_document(gaps: list[CapabilityGap]) -> dict[str, Any]:
    """Return the JSON document of the aggregated gaps.

    Each gap is marked `build_opportunity` (only unsupported and host_only gaps are); the counts
    let a client see demand without reading every entry.
    """
    rows = [{**gap.model_dump(mode="json"), "build_opportunity": is_build_opportunity(gap)}
            for gap in gaps]
    return {"gaps": rows, "total": len(rows),
            "build_opportunities": sum(1 for row in rows if row["build_opportunity"]),
            "occurrences": sum(gap.occurrence_count for gap in gaps)}


async def _command(args: argparse.Namespace, service: KernelService) -> Result:
    """Run one service command and return (exit code, JSON document)."""
    if args.command == "gaps":
        return CLI_EXIT_CODES["ok"], gaps_document(service.list_gaps())
    if args.command == "run":
        raw = read_json_input(args.input_file)
        try:
            task_input = TaskInput.model_validate(raw)
        except ValidationError as exc:
            raise CliInputError("invalid_task_input", "the TaskInput is invalid",
                                validation_details(exc)) from exc
        envelope = await service.start_run(task_input)
    elif args.command == "resume":
        run_id = safe_run_id(args.run_id)
        envelope = await service.resume_run(run_id, read_json_input(args.input_file))
    elif args.command == "status":
        envelope = await service.get_run(safe_run_id(args.run_id))
    else:
        actor = parse_actor(args.actor)
        envelope = await service.cancel_run(safe_run_id(args.run_id), actor)
    return CLI_EXIT_CODES["ok"], envelope.model_dump(mode="json")


async def _guarded(args: argparse.Namespace, service: KernelService,
                   redactor: Redactor) -> Result:
    """Run a command and map every failure to its documented exit code and payload.

    Exit-5 messages carry exception text, so they pass through `redactor` before they are
    printed.
    """
    mask = redactor.mask_text
    try:
        return await _command(args, service)
    except CliInputError as exc:
        return _rejected(exc.code, exc.message, exc.details)
    except InvalidTaskInput as exc:
        return _rejected("invalid_task_input", str(exc))
    except SubmissionRejected as exc:
        return _rejected(exc.code.value, exc.message, exc.details, exc.envelope)
    except RunNotFound as exc:
        return CLI_EXIT_CODES["run_not_found"], error_payload(
            "run_not_found", str(exc), {"run_id": exc.run_id})
    except ProviderUnavailable as exc:
        return _internal("provider_unavailable", mask(str(exc)))
    except RegistryChanged as exc:
        return _internal("registry_changed", mask(str(exc)))
    except Exception as exc:  # noqa: BLE001 - last resort: the client needs exit 5 and JSON
        logger.exception("internal error")
        return _internal("internal", mask(f"{type(exc).__name__}: {exc}"))


def _run_with_environment(args: argparse.Namespace, factory: EnvironmentFactory) -> Result:
    """Build the environment, run the command in one event loop, then shut the tracer down."""
    try:
        env = factory(config_path=args.config, env_file=args.env_file)
    except ConfigError as exc:
        return _internal("config_invalid", str(exc))
    except RegistryError as exc:
        return _internal("registry_invalid", str(exc))
    try:
        return asyncio.run(_guarded(args, KernelService(env), env.redactor))
    finally:
        env.shutdown()


def _install(args: argparse.Namespace) -> Result:
    """Install the skill and report where it went."""
    try:
        path = install_skill(args.target_dir, args.name, force=args.force)
    except InstallRefused as exc:
        return _rejected(exc.code, exc.message)
    except OSError as exc:
        return _internal("install_failed", f"{type(exc).__name__}: {exc.strerror or exc}")
    return CLI_EXIT_CODES["ok"], {"installed": str(path), "name": args.name}


def main(argv: list[str] | None = None, *, environment: EnvironmentFactory = build_environment
         ) -> int:
    """Run the CLI and return its exit code (the one JSON document goes to stdout).

    Args:
        argv: Arguments after the program name (default: sys.argv[1:]).
        environment: Environment factory (tests inject fakes; production composes the real one).

    Returns:
        int: 0 envelope, 2 usage, 3 rejected, 4 unknown run, 5 internal.
    """
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:  # argparse already printed usage to stderr
        return int(exc.code) if isinstance(exc.code, int) else CLI_EXIT_CODES["usage"]
    stdout = sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        code, document = _install(args) if args.command == "install-skill" \
            else _run_with_environment(args, environment)
    emit(document, stdout)
    return code


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 16:30 [python-coder]: Exit-5 messages built from exception text pass through the
#   environment's Redactor; the catch-all would otherwise print a provider error that echoes a
#   credential. (#KernelBootstrapV0/FIXC)
# - 2026-10-01 14:00 [python-coder]: `gaps` reads the aggregated gap store only (no Jev key, no
#   run needed) and marks build opportunities, so a client never has to know which gap types may
#   produce a backlog item. (#KernelBootstrapV0/P9)
# - 2026-10-01 12:10 [python-coder]: --input-file accepts the design's --input/--response
#   spellings as aliases, and reads stdin for "-" or no flag, so one flag shape serves run and
#   resume. (#KernelBootstrapV0/P7)
# - 2026-10-01 12:10 [python-coder]: The catch-all maps unexpected failures to exit 5 with a JSON
#   error and a stderr traceback; it is the only broad handler and sits at the process edge.
#   (#KernelBootstrapV0/P7)
# - 2026-10-01 12:10 [python-coder]: stdout is redirected to stderr while a command runs, so
#   library output cannot break the one-JSON-document contract. (#KernelBootstrapV0/P7)
# ====================================================================
