"""
MODULE: kernel.capabilities.research.limitations
GOAL: Tidy the limitation lines a research bundle collects: collapse the retrieval cut notes of
    one need into a single summary line, and drop exact repeats.
BUSINESS CONTEXT: A live decision report carried 56 limitation lines, 37 of them retrieval cut
    notes ("repo.docs: 779 lower-ranked section(s) cut at the source cap ...") and many repeated
    because a resumed collect re-reads every child bundle (round 8 defect d). The limitations that
    matter (a need was not answered, a source was unavailable) were buried. Retrieval keeps the
    detail in its own bundle; the run report needs one line per need.
ARCHITECTURE: Pure functions over strings. A retrieval cut note is recognised by its fixed
    wording (the wording is produced by `retrieval/pool.py`, `rerank.py`, `repository.py`,
    `knowledge_map.py` and `executor.py`); the summary line starts with `retrieval cut for need
    <id>:` so a later round's line for the same need can replace the earlier one.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

SUMMARY_PREFIX = "retrieval cut for need "
_POOL = re.compile(r"candidate pool capped at (\d+) .*?: (\d+) of (\d+) candidate\(s\)")
_JUDGED = re.compile(r"(\d+) of (\d+) candidate\(s\) were not judged")
_STRONGEST = re.compile(r"strongest not judged: (\S+)")
_SOURCE = re.compile(r"^(\S+): (\d+) (?:lower-ranked section\(s\)|nodes) cut at the source cap")
_SKIPPED = re.compile(r"^(\S+): (\d+) item\(s\) skipped")
_MARKERS = ("candidate pool capped", "candidate(s) were not judged",
            "lower-ranked section(s) cut at the source cap", "nodes cut at the source cap",
            "item(s) skipped")


def is_cut_note(text: str) -> bool:
    """True if the line is one of retrieval's per-source or per-pool cut notes."""
    return any(marker in text for marker in _MARKERS)


def _parts(notes: Iterable[str]) -> list[str]:
    """Return the summary phrases for a need's cut notes (counts only, no per-file detail)."""
    parts: list[str] = []
    cuts: list[str] = []
    skipped = 0
    for note in notes:
        if m := _POOL.search(note):
            parts.append(f"pool capped ({m[2]} of {m[3]} candidates not offered)")
        elif m := _JUDGED.search(note):
            strongest = _STRONGEST.search(note)
            tail = f", strongest: {strongest[1]}" if strongest else ""
            parts.append(f"{m[1]} of {m[2]} candidates not judged{tail}")
        elif m := _SOURCE.match(note):
            cuts.append(f"{m[1]} {m[2]}")
        elif m := _SKIPPED.match(note):
            skipped += int(m[2])
        else:
            parts.append(note.strip())
    if cuts:
        parts.append("cut at the source cap: " + ", ".join(cuts))
    if skipped:
        parts.append(f"{skipped} unreadable item(s) skipped")
    return parts


def summarise_cut_notes(need_id: str, notes: list[str]) -> str:
    """Return the one summary line for a need's cut notes (the detail stays in the child bundle)."""
    return f"{SUMMARY_PREFIX}{need_id}: " + "; ".join(_parts(notes))


def collapse_for_decision(lines: Iterable[str], need_notes: Mapping[str, list[str]]
                          ) -> list[str]:
    """Return the limitation lines a decision shows: one cut summary per need, repeats dropped.

    Every retrieval cut note is replaced by one summary line for the need its child reported it
    under (`need_notes`); a cut note no need claims is summarised under `unattributed`. Other
    limitations keep their order and wording.
    """
    claimed = {note for notes in need_notes.values() for note in notes}
    kept: list[str] = []
    stray: list[str] = []
    for line in lines:
        if not is_cut_note(line):
            kept.append(line)
        elif line not in claimed:
            stray.append(line)
    summaries = [summarise_cut_notes(need, notes) for need, notes in need_notes.items() if notes]
    if stray:
        summaries.append(summarise_cut_notes("unattributed", stray))
    return list(dict.fromkeys([*kept, *summaries]))


def merge_limitations(existing: list[str], new: Iterable[str]) -> list[str]:
    """Return `existing` plus `new` without repeats; a newer cut summary for a need replaces the old.

    Used where a decision absorbs bundles round after round: the same need's summary is
    re-issued with new counts each round and must not pile up.
    """
    merged = list(existing)
    for line in new:
        if line.startswith(SUMMARY_PREFIX):
            key = line.split(":", 1)[0]
            merged = [x for x in merged if not x.startswith(key + ":")]
        if line not in merged:
            merged.append(line)
    return merged


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The research bundle keeps every raw line and names the cut notes
#   per need; the decision collapses them to one summary per need and deduplicates across rounds,
#   so the report shows what matters and nothing is lost from the bundle. (#KernelDecisionStore)
# ====================================================================
