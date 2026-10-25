"""
MODULE: scripts/evals/sql_test_writer_eval/evidence_kinds.py
GOAL: The evidence-reading assertion kinds of the sql-test-writer set: the wrong version named in
    the to-run-later file, and the processed-row and non-NULL counts in the executed SQL.
BUSINESS CONTEXT: TQ-200d-2. "Names a wrong version to run" is checked on the machine-readable
    file the template mandates, never on report prose, which a careless agent can fill without
    writing the file. No database is available to the eval, so the empty-window query is checked
    structurally: a check of ``buy_volume >= 0`` alone passes an empty or all-NULL window.
ARCHITECTURE: The to-run-later file is read from ``<git dir>/leafcutter/to-run-later/<ac-id>.json``
    of the sandbox (place_outputs puts it there). Malformed content fails the kind, never the run.
    The SQL is what reaches ``.execute(...)`` and selects from the spec's view (sql_resolve), so
    counts in comments, prose, assert messages or unexecuted strings do not count.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable
from pathlib import Path

import produced_tests_runs as runs
from produced_tests_runs import RowContext
from sql_test_writer_eval.sql_resolve import executed_queries

LATER_DIR = ("leafcutter", "to-run-later")
ROW_COUNT_RE = re.compile(r"count\(\s*(?:\*|1)\s*\)(?!\s*filter)")


def _outcome(passed: bool, ok: str, bad: str) -> dict:
    """The assertion outcome: *ok* when passed, else *bad*."""
    return {"passed": passed, "detail": ok if passed else bad}


def _entries(data: object) -> list[dict]:
    """The dict entries of ``data["to_run_later"]``; none when the file is not the documented shape."""
    listed = data.get("to_run_later") if isinstance(data, dict) else None
    return [e for e in listed if isinstance(e, dict)] if isinstance(listed, list) else []


def _real_wrong_version(entry: dict, spec: dict) -> bool:
    """The entry names the keyword in its wrong_version and a ``::`` node id of the named function in its test."""
    keyword = spec.get("wrong_version_contains", spec["contains"])
    test = str(entry.get("test", ""))
    return keyword in str(entry.get("wrong_version", "")) and "::" in test and spec["contains"] in test


def to_run_later_names_wrong_version(ctx: RowContext, spec: dict) -> dict:
    """The to-run-later file is for the AC and holds an entry that names a real wrong version of the function."""
    git_dir = Path(runs.git(ctx.sandbox, "rev-parse", "--absolute-git-dir").strip())
    path = git_dir.joinpath(*LATER_DIR, f"{spec['ac_id']}.json")
    if not path.is_file():
        return _outcome(False, "", f"the sandbox's git dir holds no to-run-later file for {spec['ac_id']}")
    try:
        data = json.loads(path.read_bytes().decode("utf-8-sig"))
    except ValueError:
        return _outcome(False, "", "the to-run-later file is not valid JSON")
    inner = data.get("ac_id") if isinstance(data, dict) else None
    if inner not in (None, spec["ac_id"]):
        return _outcome(False, "", f"the to-run-later file is for {inner}, not {spec['ac_id']}")
    needle = spec["contains"]
    hits = [e for e in _entries(data) if _real_wrong_version(e, spec)]
    return _outcome(bool(hits), f"the to-run-later file names a wrong version of {needle}", f"the to-run-later file names no wrong version of {needle}")


def non_null_re(column: str) -> re.Pattern[str]:
    """A count of the non-NULL values of *column*: count(col), a filter on it, or a case-when over it."""
    col = re.escape(column)
    alias = r"(?:\w+\.)?"
    return re.compile(rf"count\(\s*{alias}\"?{col}\"?\s*\)|filter\s*\(\s*where\s+{alias}{col}\s+is\s+not\s+null|case\s+when\s+{alias}{col}\s+is\s+not\s+null")


def counts_rows_and_non_null(ctx: RowContext, spec: dict) -> dict:
    """The executed SQL over the view counts the processed rows and the non-NULL values of the column."""
    path = ctx.test_files.get(spec["file"])
    if path is None:
        return _outcome(False, "", f"the output holds no test file {spec['file']!r}")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return _outcome(False, "", f"{path.name} does not parse, so its SQL cannot be checked: {exc}")
    column = spec["column"]
    from_view = re.compile(rf"\b(?:from|join)\s+(?:\"?\w+\"?\.)?\"?{re.escape(spec['view'])}\"?(?!\w)")
    sql = " ".join(q for q in executed_queries(tree) if from_view.search(q))
    found = {"processed rows": bool(ROW_COUNT_RE.search(sql)), f"non-NULL {column} values": bool(non_null_re(column).search(sql))}
    missing = [what for what, ok in found.items() if not ok]
    return _outcome(not missing, f"the SQL counts the processed rows and the non-NULL {column} values",
                    "the SQL counts no " + " and no ".join(missing) + ", so an empty or all-NULL window passes it")


KINDS: dict[str, Callable[[RowContext, dict], dict]] = {
    "sql_to_run_later_names_wrong_version": to_run_later_names_wrong_version,
    "sql_counts_rows_and_non_null": counts_rows_and_non_null,
}
