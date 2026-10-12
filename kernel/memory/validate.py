"""
MODULE: kernel.memory.validate
GOAL: Validate a decision store: every record against the JSON Schema in config/, then the
    semantic rules (unique ids, resolvable supersede and related links, human approver, filters
    drawn from the existing vocabularies, plain-YAML subset) and finally that the generated index
    is up to date. Also exports the schema file from the record model.
BUSINESS CONTEXT: The format decision asks for a schema "validated at commit". The repository has
    no new pre-commit hook for it (a hook is package surface and needs ACs, which the user
    excluded), so the check runs as `python -m kernel decisions validate`, in a unit test over the
    committed store and in CI (ADR-059).
ARCHITECTURE: Pure over files read once. `config/decision_record.schema.json` is generated from
    `DecisionRecord` (a test keeps the committed copy in sync) and is the structural gate; the
    model then re-validates and the semantic checks use the parsed records. Every finding is a
    `Problem(file, message)`; nothing raises for a bad record, so one run lists everything wrong.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

from kernel.memory.codec import (
    RecordReadError,
    parse_yaml_text,
    plain_subset_problems,
    read_text,
)
from kernel.memory.index import (
    INDEX_NAME,
    IndexEntry,
    build_entries,
    index_problems,
    render_index,
)
from kernel.memory.models import DecisionRecord
from kernel.memory.vocab import Vocabulary

logger = logging.getLogger(__name__)

SCHEMA_NAME = "decision_record.schema.json"
SCHEMA_ID = "leafcutter.decision_record.v1"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
FILTER_FIELDS = ("components", "change_target", "risk_surface", "roadmap_phase", "file_globs")


@dataclass(frozen=True)
class Problem:
    """One finding: the file it concerns and what is wrong."""

    file: str
    message: str

    def as_dict(self) -> dict[str, str]:
        """Return the finding as a JSON-compatible dict."""
        return {"file": self.file, "message": self.message}


@dataclass
class StoreReport:
    """The outcome of validating a store."""

    records: dict[str, DecisionRecord] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    entries: list[IndexEntry] = field(default_factory=list)
    index_text: str = ""
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if no problem was found."""
        return not self.problems


def record_schema() -> dict[str, Any]:
    """Return the JSON Schema generated from the record model."""
    return {"$schema": JSON_SCHEMA_DIALECT, "$id": SCHEMA_ID,
            "title": "Leafcutter decision record",
            "description": ("One human-approved decision filed under docs/decisions/<dec-id>.yaml "
                            "(ADR-059). Generated from kernel/memory/models.py; do not edit."),
            **DecisionRecord.model_json_schema(mode="validation")}


def render_schema() -> str:
    """Return the deterministic text committed as config/decision_record.schema.json."""
    return json.dumps(record_schema(), indent=2, sort_keys=True) + "\n"


def write_schema(path: Path) -> None:
    """Write the generated schema to `path` (IO errors are logged and raised)."""
    try:
        path.write_text(render_schema(), encoding="utf-8", newline="\n")
    except OSError:
        logger.warning("could not write the decision record schema to %s", path, exc_info=True)
        raise


def load_schema(path: Path) -> dict[str, Any]:
    """Read the committed schema file.

    Raises:
        RecordReadError: The file is missing, unreadable or not a JSON object.
    """
    text = read_text(path)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RecordReadError(path, f"not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RecordReadError(path, "the schema must be a JSON object")
    return data


def schema_problems(data: Mapping[str, Any], schema: Mapping[str, Any]) -> list[str]:
    """Return one message per JSON Schema violation (path and reason), sorted by path."""
    validator = jsonschema.Draft202012Validator(dict(schema))
    errors = sorted(validator.iter_errors(dict(data)), key=lambda e: list(map(str, e.path)))
    return [f"{'/'.join(map(str, e.path)) or '<record>'}: {e.message}" for e in errors]


def link_problems(records: Mapping[str, DecisionRecord]) -> list[Problem]:
    """Return the link findings over a whole set of records (resolution and consistency)."""
    out: list[Problem] = []
    for rid, record in sorted(records.items()):
        name = f"{rid}.yaml"
        for fld in ("supersedes", "superseded_by", "related"):
            out += [Problem(name, f"{fld} target {t} does not exist")
                    for t in getattr(record, fld) if t not in records]
        for t in record.superseded_by:
            if t in records and rid not in records[t].supersedes:
                out.append(Problem(name, f"superseded_by {t}, but {t} does not list {rid} "
                                         "under supersedes"))
        for correction in record.corrections:
            if correction.superseded_by and correction.superseded_by not in records:
                out.append(Problem(name, f"correction names superseded_by "
                                         f"{correction.superseded_by}, which does not exist"))
    return out


def semantic_problems(record: DecisionRecord, vocab: Vocabulary | None) -> list[Problem]:
    """Return the findings that need the vocabularies (filters must be existing values)."""
    if vocab is None:
        return []
    filters = {name: list(getattr(record, name)) for name in FILTER_FIELDS}
    return [Problem(f"{record.id}.yaml", m) for m in vocab.unknown(filters)]


def _check_file(path: Path, schema: Mapping[str, Any], vocab: Vocabulary | None,
                report: StoreReport) -> None:
    """Validate one record file and add it (when it parses) to the report."""
    name = path.name
    try:
        text = read_text(path)
        data = parse_yaml_text(text, path)
    except RecordReadError as exc:
        report.problems.append(Problem(name, exc.detail))
        return
    report.problems += [Problem(name, f"schema: {m}") for m in schema_problems(data, schema)]
    report.problems += [Problem(name, m) for m in plain_subset_problems(text)]
    try:
        record = DecisionRecord.model_validate(data)
    except ValueError as exc:
        if not any(p.file == name for p in report.problems):
            report.problems.append(Problem(name, f"model: {exc}"))
        return
    if path.stem != record.id:
        report.problems.append(Problem(name, f"file name must be {record.id}.yaml"))
    if record.id in report.records:
        report.problems.append(Problem(name, f"duplicate record id {record.id}"))
        return
    report.records[record.id] = record
    report.texts[record.id] = text
    report.problems += semantic_problems(record, vocab)


def validate_store(decisions_dir: Path, *, schema: Mapping[str, Any],
                   vocab: Vocabulary | None, check_index: bool = True) -> StoreReport:
    """Validate every `dec-*.yaml` of a store, the links between them and the generated index.

    Args:
        decisions_dir: The store folder (may not exist yet: an empty store is valid).
        schema: The record JSON Schema.
        vocab: Existing vocabularies for the filters; None skips the vocabulary check.
        check_index: Also require `index.json` to match the records exactly.

    Returns:
        StoreReport: Parsed records, the expected index and every problem found.
    """
    report = StoreReport()
    try:
        files = sorted(decisions_dir.glob("*.yaml")) if decisions_dir.is_dir() else []
    except OSError as exc:
        report.problems.append(Problem(str(decisions_dir), f"cannot list the store: {exc}"))
        return report
    for path in files:
        _check_file(path, schema, vocab, report)
    report.problems += link_problems(report.records)
    report.entries = build_entries((report.records[i], report.texts[i]) for i in report.records)
    report.index_text = render_index(report.entries)
    if check_index and (files or (decisions_dir / INDEX_NAME).exists()):
        try:
            actual: str | None = (decisions_dir / INDEX_NAME).read_text(encoding="utf-8")
        except FileNotFoundError:
            actual = None
        except (OSError, UnicodeDecodeError) as exc:
            report.problems.append(Problem(INDEX_NAME, f"unreadable: {exc}"))
            return report
        report.problems += [Problem(INDEX_NAME, m)
                            for m in index_problems(report.index_text, actual)]
    return report


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The schema is generated from the model and committed, like
#   config/kernel_config.schema.json; JSON Schema is the structural gate (paths in messages), the
#   model and the semantic checks run behind it. (#KernelDecisionStore)
# ====================================================================
