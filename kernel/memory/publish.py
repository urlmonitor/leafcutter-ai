"""
MODULE: kernel.memory.publish
GOAL: Publish a run's staged decision records into `docs/decisions/` after validation, regenerate
    the index, and (only on explicit request) apply an append-only correction to the record a new
    decision supersedes. Also regenerates the index alone.
BUSINESS CONTEXT: The kernel never writes into the repository during a run (ADR-060). A record
    reaches git only when a person runs `python -m kernel decisions publish --run-id R`, so the
    normal review of the resulting diff is the second human gate. A correction is a deliberate
    edit of an older record, so it happens only with `--correct <old-id>` and only appends.
ARCHITECTURE: Validate first, write second. The store is validated before anything is written (a
    broken store is refused), every staged record is validated against the schema, the plain
    subset, the vocabularies and the links it would have in the merged store, and files are
    written atomically. `apply_correction` changes only `corrections` and `superseded_by` of the
    older record. Nothing here runs unless a CLI command calls it.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kernel.memory.codec import (
    RecordReadError,
    dump_record,
    parse_yaml_text,
    plain_subset_problems,
    read_text,
)
from kernel.memory.file_store import staged_files
from kernel.memory.index import INDEX_NAME
from kernel.memory.models import Correction, DecisionRecord, PreservedOriginal
from kernel.memory.validate import (
    Problem,
    StoreReport,
    link_problems,
    schema_problems,
    semantic_problems,
    validate_store,
)
from kernel.memory.vocab import Vocabulary
from kernel.persistence.fsutil import UnsafePathComponent, atomic_write_bytes

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    """What a publish or index command did (and why it refused, if it did)."""

    published: list[str] = field(default_factory=list)
    already_present: list[str] = field(default_factory=list)
    corrected: list[str] = field(default_factory=list)
    index_written: bool = False
    problems: list[Problem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if nothing was refused."""
        return not self.problems


def _write_text(path: Path, text: str) -> bool:
    """Write text atomically; a failure is logged and reported as False."""
    try:
        atomic_write_bytes(path, text.encode("utf-8"))
    except OSError:
        logger.warning("could not write %s", path, exc_info=True)
        return False
    return True


def rebuild_index(folder: Path, schema: Mapping[str, Any], vocab: Vocabulary | None
                  ) -> tuple[StoreReport, bool]:
    """Validate the records of a store and write the index they produce.

    Returns:
        tuple: (the validation report without the index check, whether the index was written).
            Nothing is written while any record is invalid.
    """
    report = validate_store(folder, schema=schema, vocab=vocab, check_index=False)
    if not report.ok:
        return report, False
    return report, _write_text(folder / INDEX_NAME, report.index_text)


def _load_staged(path: Path, schema: Mapping[str, Any], vocab: Vocabulary | None
                 ) -> tuple[DecisionRecord | None, str, list[Problem]]:
    """Read and validate one staged file; return (record or None, its text, problems)."""
    name = path.name
    try:
        text = read_text(path)
        data = parse_yaml_text(text, path)
    except RecordReadError as exc:
        return None, "", [Problem(name, exc.detail)]
    problems = [Problem(name, f"schema: {m}") for m in schema_problems(data, schema)]
    problems += [Problem(name, m) for m in plain_subset_problems(text)]
    try:
        record = DecisionRecord.model_validate(data)
    except ValueError as exc:
        return None, text, problems or [Problem(name, f"model: {exc}")]
    if path.stem != record.id:
        problems.append(Problem(name, f"file name must be {record.id}.yaml"))
    return record, text, problems + semantic_problems(record, vocab)


def apply_correction(old: DecisionRecord, new: DecisionRecord, reason: str) -> DecisionRecord:
    """Return `old` with one correction appended and `superseded_by` extended; nothing else changes.

    The correction preserves the original selected option, evidence ids and assumptions, so the
    corrected record still shows what it was decided on.
    """
    correction = Correction(
        reason=reason, corrected_at=new.approval.approved_at, corrected_by=new.approval.approved_by,
        superseded_by=new.id, new_selected_option_id=new.selected_option_id,
        preserved=PreservedOriginal(
            selected_option_id=old.selected_option_id,
            evidence_ids=[e.id for e in old.evidence],
            assumptions=list(old.selected_option.assumptions) or list(old.assumptions)))
    return old.model_copy(update={
        "corrections": [*old.corrections, correction],
        "superseded_by": list(dict.fromkeys([*old.superseded_by, new.id]))})


def _default_reason(new: DecisionRecord, old_id: str, run_id: str) -> str:
    """Return the reason a correction gets when none was given: the note on the precedent."""
    for note in new.precedents_considered:
        if note.id == old_id and note.note:
            return note.note
    return (f"decided anew by {new.approval.approved_by} in run {run_id} against this earlier "
            "decision")


def _correction_problems(staged: Mapping[str, DecisionRecord], store: Mapping[str, DecisionRecord],
                         correct: Sequence[str]) -> list[Problem]:
    """Return why a requested correction cannot be applied."""
    out = []
    for old_id in correct:
        if old_id not in store:
            out.append(Problem(f"{old_id}.yaml", "--correct names a record that is not in the store"))
        elif not any(old_id in r.supersedes for r in staged.values()):
            out.append(Problem(f"{old_id}.yaml", "no staged record supersedes it; a correction is "
                                                 "applied only for a record that does"))
    return out


def publish(run_id: str, *, folder: Path, run_root: Path, schema: Mapping[str, Any],
            vocab: Vocabulary | None, correct: Sequence[str] = (), reason: str | None = None
            ) -> PublishResult:
    """Publish the staged records of a run into the store at `folder`.

    Args:
        run_id: The run whose staged records are published.
        folder: The store folder (`docs/decisions`).
        run_root: The kernel run root holding `runs/<run_id>/staged/decisions/`.
        schema: The record JSON Schema.
        vocab: Existing vocabularies for the filters.
        correct: Ids of older records to correct (each must be superseded by a staged record).
        reason: The correction reason (default: the note the staged record holds, else a sentence).

    Returns:
        PublishResult: What was written, or the problems that refused the publication (then
            nothing was written).
    """
    result = PublishResult()
    try:
        files = staged_files(run_root, run_id)
    except UnsafePathComponent:
        result.problems.append(Problem(run_id, "the run id is not a plain identifier"))
        return result
    if not files:
        result.problems.append(Problem(run_id, "no staged decision record for this run"))
        return result
    store = validate_store(folder, schema=schema, vocab=vocab, check_index=False)
    result.problems += [Problem(p.file, f"store: {p.message}") for p in store.problems]
    staged: dict[str, DecisionRecord] = {}
    texts: dict[str, str] = {}
    for path in files:
        record, text, problems = _load_staged(path, schema, vocab)
        result.problems += problems
        if record is not None:
            staged[record.id], texts[record.id] = record, text
    fresh = {i: r for i, r in staged.items() if i not in store.records}
    result.already_present = sorted(i for i in staged if i in store.records
                                    and store.texts[i] == texts[i])
    result.problems += [Problem(f"{i}.yaml", "a different record with this id is already published")
                        for i in staged if i in store.records and store.texts[i] != texts[i]]
    merged = {**store.records, **fresh}
    result.problems += [p for p in link_problems(merged)
                        if p.file.removesuffix(".yaml") in fresh]
    result.problems += _correction_problems(staged, store.records, correct)
    if result.problems:
        return result
    plan = _Plan(folder=folder, schema=schema, vocab=vocab, store=store, fresh=fresh,
                 texts=texts, correct=list(correct), reason=reason, run_id=run_id)
    _write_all(result, plan)
    return result


@dataclass(frozen=True)
class _Plan:
    """A validated publication, ready to write."""

    folder: Path
    schema: Mapping[str, Any]
    vocab: Vocabulary | None
    store: StoreReport
    fresh: Mapping[str, DecisionRecord]
    texts: Mapping[str, str]
    correct: list[str]
    reason: str | None
    run_id: str


def _write_all(result: PublishResult, plan: _Plan) -> None:
    """Write the new records, apply the corrections and regenerate the index."""
    for rid in sorted(plan.fresh):
        if _write_text(plan.folder / f"{rid}.yaml", plan.texts[rid]):
            result.published.append(rid)
        else:
            result.problems.append(Problem(f"{rid}.yaml", "could not be written"))
    for old_id in plan.correct:
        newer = next(r for r in plan.fresh.values() if old_id in r.supersedes)
        updated = apply_correction(plan.store.records[old_id], newer,
                                   plan.reason or _default_reason(newer, old_id, plan.run_id))
        if _write_text(plan.folder / f"{old_id}.yaml", dump_record(updated)):
            result.corrected.append(old_id)
        else:
            result.problems.append(Problem(f"{old_id}.yaml", "could not be rewritten"))
    after, written = rebuild_index(plan.folder, plan.schema, plan.vocab)
    result.problems += [Problem(p.file, f"after publish: {p.message}") for p in after.problems]
    result.index_written = written


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: publish validates the whole store and every staged record before
#   it writes anything, and a correction touches only `corrections` and `superseded_by` of the
#   older record, so the original evidence and assumptions are preserved. (#KernelDecisionStore)
# ====================================================================
