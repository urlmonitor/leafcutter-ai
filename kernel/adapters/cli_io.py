"""
MODULE: kernel.adapters.cli_io
GOAL: Input and output helpers of the CLI: read one JSON document from a file or stdin, validate
    run ids and actors, and print exactly one JSON document to stdout.
BUSINESS CONTEXT: Request content (a goal, a submission) is untrusted free text; it must reach
    the kernel as data, never through a shell, and the client must be able to parse stdout
    blindly (Rev 3 section 11.2).
ARCHITECTURE: Pure helpers plus small IO wrappers with bounded reads. `CliInputError` carries the
    stable error code and details the CLI prints with exit code 3. Path safety for run ids reuses
    the persistence layer's `safe_component`, so the CLI and the stores agree.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, TextIO

from pydantic import ValidationError

from kernel.contracts.enums import ActorKind
from kernel.contracts.task import Actor
from kernel.persistence.fsutil import UnsafePathComponent, safe_component

logger = logging.getLogger(__name__)

MAX_INPUT_BYTES = 4_000_000
STDIN_MARKER = "-"
MAX_ERROR_ITEMS = 10


class CliInputError(Exception):
    """The request content cannot be used; the CLI reports it with exit code 3."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        """Keep the stable code, message and details."""
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details or {}


def read_json_input(path: str | None, stdin: TextIO | None = None) -> Any:
    """Read one JSON document from `path` (or stdin when `path` is None or "-").

    Raises:
        CliInputError: The file is unreadable, too large, or not valid JSON.
    """
    try:
        if path is None or path == STDIN_MARKER:
            text = (stdin or sys.stdin).read(MAX_INPUT_BYTES + 1)
        else:
            with Path(path).open(encoding="utf-8") as handle:
                text = handle.read(MAX_INPUT_BYTES + 1)
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("could not read the input: %s", exc)
        raise CliInputError("input_unreadable", f"cannot read the input: {type(exc).__name__}",
                            {"path": str(path or STDIN_MARKER)}) from exc
    if len(text) > MAX_INPUT_BYTES:
        raise CliInputError("input_too_large", f"the input exceeds {MAX_INPUT_BYTES} characters")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CliInputError("input_not_json", f"the input is not valid JSON: {exc.msg}",
                            {"line": exc.lineno, "column": exc.colno}) from exc


def validation_details(exc: ValidationError) -> dict[str, Any]:
    """Return a compact, JSON-safe list of the first validation problems."""
    errors = json.loads(exc.json(include_url=False, include_input=False, include_context=False))
    return {"errors": errors[:MAX_ERROR_ITEMS], "error_count": len(errors)}


def safe_run_id(run_id: str) -> str:
    """Return `run_id` if it is a plain path segment; raise CliInputError otherwise."""
    try:
        return safe_component(run_id)
    except UnsafePathComponent as exc:
        raise CliInputError("invalid_run_id", "the run id is not a plain identifier") from exc


def parse_actor(text: str) -> Actor:
    """Parse `human:<id>` or `host:<id>` into an Actor (the id keeps its prefix).

    Raises:
        CliInputError: The text has no known kind prefix or an invalid id.
    """
    kind, sep, rest = text.partition(":")
    if not sep or not rest or kind not in {k.value for k in ActorKind}:
        raise CliInputError("invalid_actor", "an actor looks like human:<id> or host:<id>")
    try:
        return Actor(id=text, kind=ActorKind(kind))
    except ValidationError as exc:
        raise CliInputError("invalid_actor", "the actor id has invalid characters",
                            validation_details(exc)) from exc


def emit(document: dict[str, Any], stream: TextIO) -> None:
    """Print `document` as the single JSON document of the run (ASCII-safe, one line)."""
    stream.write(json.dumps(document, ensure_ascii=True, default=str) + "\n")
    stream.flush()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 12:00 [python-coder]: Output is ASCII-escaped single-line JSON so a Windows
#   console code page can never corrupt it. (#KernelBootstrapV0/P7)
# - 2026-10-01 12:00 [python-coder]: The actor id keeps its `human:`/`host:` prefix, matching how
#   human answers are attributed in submissions. (#KernelBootstrapV0/P7)
# ====================================================================
