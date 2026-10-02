"""
MODULE: kernel.memory.codec
GOAL: Read and write a decision record as plain YAML: a stable dump (field order, indented block
    lists, quoted timestamps) and a safe load with a lint for constructs outside the plain subset.
BUSINESS CONTEXT: Records are reviewed as diffs in git, so one record always dumps to the same
    bytes, and the stdlib knowledge-map parser (`scripts/knowledge_query.py`) must be able to read
    its id and filter fields without PyYAML (the project's stdlib-only parser policy).
ARCHITECTURE: PyYAML `safe_dump` with an indenting dumper (the stdlib parser reads `  - item` block
    lists, not PyYAML's column-0 default) and no key sorting. `plain_subset_problems` walks the
    YAML event stream and names anchors, aliases, explicit tags, flow mappings and extra
    documents, none of which the stdlib parser supports.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from kernel.memory.models import DecisionRecord
from kernel.persistence.fsutil import atomic_write_bytes

logger = logging.getLogger(__name__)

YAML_WIDTH = 120
MAX_RECORD_BYTES = 400_000


class RecordReadError(Exception):
    """A record file could not be read or is not a YAML mapping."""

    def __init__(self, path: Path | str, detail: str) -> None:
        """Build the message from the path and the problem."""
        super().__init__(f"decision record {path}: {detail}")
        self.path = str(path)
        self.detail = detail


class _IndentedDumper(yaml.SafeDumper):
    """SafeDumper that indents block sequences under their key (the stdlib-readable layout)."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        """Never use an indentless sequence."""
        return super().increase_indent(flow, False)


def _plain(value: Any) -> Any:
    """Return value with None-valued mapping entries kept and tuples turned into lists."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


def record_to_dict(record: DecisionRecord) -> dict[str, Any]:
    """Return the record as a JSON-compatible dict in field order (the file's content)."""
    return _plain(record.model_dump(mode="json"))


def dump_record(record: DecisionRecord) -> str:
    """Return the record as YAML text: field order kept, UTF-8, LF, one trailing newline."""
    return yaml.dump(record_to_dict(record), Dumper=_IndentedDumper, sort_keys=False,
                     allow_unicode=True, default_flow_style=False, width=YAML_WIDTH, indent=2)


def parse_yaml_text(text: str, source: Path | str) -> dict[str, Any]:
    """Parse YAML text into a mapping.

    Raises:
        RecordReadError: The text is not valid YAML or not a mapping.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RecordReadError(source, f"not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise RecordReadError(source, "the top level must be a YAML mapping")
    return data


def read_text(path: Path) -> str:
    """Read a record file as UTF-8 (bounded).

    Raises:
        RecordReadError: The file is unreadable, not UTF-8 or larger than the bound.
    """
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_RECORD_BYTES:
            raise RecordReadError(path, f"larger than {MAX_RECORD_BYTES} bytes")
        return raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("cannot read decision record %s: %s", path, exc)
        raise RecordReadError(path, f"{type(exc).__name__}: cannot read it") from exc


def load_record_file(path: Path) -> DecisionRecord:
    """Read, parse and model-validate one record file.

    Raises:
        RecordReadError: The file cannot be read or parsed, or does not fit the model.
    """
    data = parse_yaml_text(read_text(path), path)
    try:
        return DecisionRecord.model_validate(data)
    except ValueError as exc:  # pydantic.ValidationError is a ValueError
        raise RecordReadError(path, f"not a valid record: {exc}") from exc


def write_record_file(record: DecisionRecord, path: Path) -> None:
    """Write the record atomically (tmp file, fsync, replace); IO errors are logged and raised."""
    try:
        atomic_write_bytes(path, dump_record(record).encode("utf-8"))
    except OSError:
        logger.warning("could not write decision record %s", path, exc_info=True)
        raise


def plain_subset_problems(text: str) -> list[str]:
    """Return the constructs in `text` that the stdlib knowledge-map parser cannot read."""
    problems: list[str] = []
    try:
        events = list(yaml.parse(text))
    except yaml.YAMLError as exc:
        return [f"not valid YAML: {exc}"]
    documents = sum(isinstance(e, yaml.DocumentStartEvent) for e in events)
    if documents > 1:
        problems.append("more than one YAML document")
    for event in events:
        if isinstance(event, yaml.AliasEvent):
            problems.append("alias (*name) is outside the plain subset")
        elif getattr(event, "anchor", None):
            problems.append("anchor (&name) is outside the plain subset")
        elif getattr(event, "tag", None):
            problems.append(f"explicit tag {event.tag} is outside the plain subset")
        elif isinstance(event, yaml.MappingStartEvent) and event.flow_style:
            problems.append("flow mapping ({...}) is outside the plain subset")
    return list(dict.fromkeys(problems))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Sequences are indented under their key: PyYAML's column-0 default
#   (`key:` then `- item` at column 0) is the layout the stdlib knowledge-map parser reads least
#   reliably, while the AC store already uses indented block lists. (#KernelDecisionStore)
# ====================================================================
