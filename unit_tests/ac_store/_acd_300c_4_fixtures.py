"""
MODULE: unit_tests/ac_store/_acd_300c_4_fixtures.py
GOAL: Shared batch store, real-CLI runner and byte-level diff oracle for the ACD-300c-4 family
    (tickets 13, 16, 17, 18, 19 of EPIC-RightJobRightAgentFollowUps): the approval step's id-list
    mode with a priority option. Not collected: no test functions live here.
BUSINESS CONTEXT: ACD-300c-4. The final-gate approval is applied by the store's one approval step
    (scripts/ac_store/approve_acs.py) to exactly the ids the hold report releases. Readiness, priority
    and one appended amended_by entry change; every other byte of the record is preserved.
ARCHITECTURE: The tmp repo is laid out like a consumer repo (_rule_check_fixtures.make_store), so the
    step's default `--ac-root docs/acceptance-criteria/` resolves inside it when it runs with cwd = the
    tmp repo root. Record bytes come from the real serializer (yaml.safe_dump) for every field except
    `amended_by`, whose bytes are copied VERBATIM from a real store record (ACS-1100c.yaml, a folded
    multi-line `note`): yaml.dump renders that entry differently, so a step that re-dumps the block is
    caught (Fixture Authenticity Rule: real serializer or verbatim on-disk bytes, never typed YAML).
    Each released record also carries the text "readiness: reviewed" inside a `notes` value that sits
    BEFORE its readiness key, so a first-occurrence text replacement is caught.
    `line_changes` is the oracle for "every other byte is identical": a line diff whose only allowed
    operations are the readiness line, the priority line and lines inserted at the end of the
    amended_by block.

PUBLIC API: BATCH, HELD, RELEASED, PRIOR_PRIORITY, UNDECIDED, PENDING, batch_store, l1_store,
    run_ids, report_of, amended_by_of, approval_entries, line_changes, approval_entry_lines,
    store_bytes, today.
"""

from __future__ import annotations

import difflib
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500b_approval_fixtures import (  # noqa: E402
    PENDING,
    Run,
    json_of,
    reviewed_intent,
    reviewed_no_tests,
    run_approve,
)
from _acd_2500d_3_i_fixtures import UNDECIDED, finding  # noqa: E402
from _rule_check_fixtures import REPO_ROOT, Store, make_store  # noqa: E402

BATCH = ["ACD-9990a-1", "ACD-9990a-2", "ACD-9990a-3", "ACD-9990a-4"]
HELD = "ACD-9990a-3"
RELEASED = ["ACD-9990a-1", "ACD-9990a-2", "ACD-9990a-4"]
PRIOR_PRIORITY = "low"
_VERBATIM_SOURCE = REPO_ROOT / "docs/acceptance-criteria/ac-store/ACS-1100-honest-coverage-answers/ACS-1100c.yaml"
_BLOCK_RE = re.compile(r"^amended_by:\n(?:(?:[ -].*)?\n)+?(?=^[A-Za-z_])", re.MULTILINE)
_NOTES = "Until the hold report cleared it, the planner wrote readiness: reviewed here."

__all__ = [
    "BATCH", "HELD", "PENDING", "PRIOR_PRIORITY", "RELEASED", "UNDECIDED", "Run", "amended_by_of",
    "approval_entries", "approval_entry_lines", "batch_store", "records_store", "strip_lines", "l1_store", "line_changes", "report_of",
    "reviewed_intent", "reviewed_no_tests", "run_ids", "store_bytes", "today",
]


def today() -> str:
    """The date the step stamps on its approval entry (ISO form)."""
    return date.today().isoformat()


def _verbatim_amended_by() -> str:
    """The amended_by block of a real store record, byte for byte (a folded multi-line note)."""
    text = _VERBATIM_SOURCE.read_text(encoding="utf-8")
    match = _BLOCK_RE.search(text)
    assert match, f"no amended_by block in {_VERBATIM_SOURCE}"
    return match.group(0)


def _dump(fields: dict) -> str:
    return yaml.safe_dump(fields, sort_keys=False, allow_unicode=True)


def _record_text(record: dict) -> str:
    """notes first (before readiness), the record body, the verbatim amended_by block, then the tail."""
    body = {key: value for key, value in record.items() if key not in ("id", "superseded_by")}
    head = {"id": record["id"], "notes": _NOTES, **body}
    return _dump(head) + _verbatim_amended_by() + _dump({"superseded_by": record.get("superseded_by")})


def _write_text(store: Store, record: dict) -> None:
    target = store.path(record["id"])
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_record_text(record))


def _store_of(tmp_path: Path, records: list[dict]) -> Store:
    store = make_store(tmp_path, [])
    for record in records:
        _write_text(store, record)
    return store


def records_store(tmp_path: Path, records: list[dict]) -> Store:
    """A tmp consumer-style store holding exactly `records` (the record text of _record_text)."""
    return _store_of(tmp_path, records)


def strip_lines(store: Store, record_id: str, *keys: str) -> None:
    """Delete the top-level `key:` line of each key from a record's file (a record that lacks the field)."""
    path = store.path(record_id)
    text = path.read_bytes().decode("utf-8")
    for key in keys:
        text = re.sub(rf"^{key}:[^\n]*\n", "", text, count=1, flags=re.MULTILINE)
    path.write_bytes(text.encode("utf-8"))


def batch_store(tmp_path: Path, held_reason: str = UNDECIDED) -> Store:
    """The 4-record batch at readiness reviewed and priority `low`; ACD-9990a-3 is held.

    `held_reason` is UNDECIDED (an undecided file finding) or PENDING (test intent, no design).
    """
    records = [reviewed_no_tests(rid, priority=PRIOR_PRIORITY) for rid in RELEASED]
    if held_reason == UNDECIDED:
        held = reviewed_no_tests(
            HELD, priority=PRIOR_PRIORITY,
            file_findings=[finding(verdict="describes, does not implement")],
            file_findings_opened_files=["scripts/ac_store/existing_mod.py"],
        )
    else:
        held = reviewed_intent(HELD, priority=PRIOR_PRIORITY)
    records.insert(2, held)
    return _store_of(tmp_path, records)


def l1_store(tmp_path: Path) -> Store:
    """ACD-9990a (L1, covered_by its two children) and ACD-9990a-1/-2, all reviewed, none held."""
    children = ["ACD-9990a-1", "ACD-9990a-2"]
    l1 = reviewed_no_tests("ACD-9990a", level="L1", covered_by=children, priority=PRIOR_PRIORITY)
    kids = [reviewed_no_tests(rid, depends_on=["ACD-9990a"], priority=PRIOR_PRIORITY) for rid in children]
    return _store_of(tmp_path, [l1, *kids])


def store_bytes(store: Store, ids: list[str]) -> dict[str, bytes]:
    """{id: raw on-disk bytes} (byte-identity assertions)."""
    return {rid: store.path(rid).read_bytes() for rid in ids}


def run_ids(store: Store, ids: list[str], *extra: str, priority: str = "high") -> Run:
    """`python scripts/ac_store/approve_acs.py --ids A,B --priority P --json <extra>`, cwd = tmp repo."""
    return run_approve(store, "--ids", ",".join(ids), "--priority", priority, "--json", *extra)


def report_of(run: Run) -> dict:
    """The step's --json report; a usage error (no id-list mode yet) fails with stderr shown."""
    assert run.exit_code == 0, f"approve_acs.py exited {run.exit_code}: {run.stderr[-600:]!r}"
    return json_of(run)


def amended_by_of(store: Store, record_id: str) -> list[Any]:
    """The parsed amended_by list of a record as it is on disk now."""
    return list(store.read(record_id).get("amended_by") or [])


def approval_entries(entries: list[Any]) -> list[dict]:
    """The approval entries of an amended_by list (action approved)."""
    return [e for e in entries if isinstance(e, dict) and e.get("action") == "approved"]


def line_changes(before: bytes, after: bytes) -> list[tuple[str, list[str], list[str]]]:
    """Every changed region of a record as (op, before_lines, after_lines), in file order."""
    old = before.decode("utf-8").splitlines(keepends=True)
    new = after.decode("utf-8").splitlines(keepends=True)
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    return [
        (op, old[i1:i2], new[j1:j2])
        for op, i1, i2, j1, j2 in matcher.get_opcodes()
        if op != "equal"
    ]


def approval_entry_lines(before: bytes, after: bytes, priority: str = "high") -> list[str]:
    """Assert the field-targeted shape of one approval write; return the appended entry's lines.

    The record is HEAD + BLOCK + TAIL (BLOCK = the verbatim amended_by block). After the write it must
    be HEAD' + BLOCK + ENTRY + TAIL, where HEAD' is HEAD with only the top-level readiness and priority
    lines changed, and ENTRY is non-empty. Anything else (a re-dumped note, a rewritten notes value,
    reordered keys, an entry placed first) fails the assertion and names what changed.
    """
    block = _verbatim_amended_by()
    old, new = before.decode("utf-8"), after.decode("utf-8")
    head, tail = old[: old.index(block)], old[old.index(block) + len(block):]
    head_after = re.sub(r"^readiness: reviewed$", "readiness: approved", head, count=1, flags=re.MULTILINE)
    head_after = re.sub(rf"^priority: {PRIOR_PRIORITY}$", f"priority: {priority}", head_after, count=1, flags=re.MULTILINE)
    changes = line_changes(before, after)
    assert new.startswith(head_after + block), f"bytes before the end of amended_by changed: {changes}"
    assert new.endswith(tail), f"bytes after amended_by changed: {changes}"
    entry = new[len(head_after + block): len(new) - len(tail)]
    assert entry.strip(), f"no entry was appended at the end of amended_by: {changes}"
    return entry.splitlines(keepends=True)
