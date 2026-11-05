"""
MODULE: scripts/evals/sql_test_writer_eval/evidence_kinds.py
GOAL: The evidence-reading assertion kinds of the sql-test-writer set: the wrong version named in
    the to-run-later file (TQ-200d-2-i: the function in the test id, the wrong version free prose), and
    the processed-row and non-NULL counts, in the executed SQL or asserted on the fetched rows (TQ-200d-2-ii).
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
    """The entry's test is a ``::`` test id naming the function, and its wrong version is non-empty prose."""
    test = str(entry.get("test", ""))
    wrong = entry.get("wrong_version")
    return isinstance(wrong, str) and bool(wrong.strip()) and "::" in test and spec["contains"] in test


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


NAME_RE = re.compile(r"\b[A-Za-z_]\w*\b")
NONE_CHECK_RE = re.compile(r"is\s+not\s+None|!=\s*None")


def _equality_statements(tree: ast.AST) -> list[str]:
    """The source of every equality assertion: ``assert a == b`` (each ``==`` of its test) and ``assertEqual(a, b)``."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            found += [ast.unparse(c) for c in ast.walk(node.test) if isinstance(c, ast.Compare) and any(isinstance(o, ast.Eq) for o in c.ops)]
        elif isinstance(node, ast.Call) and getattr(node.func, "attr", "") in ("assertEqual", "assertEquals") and len(node.args) >= 2:
            found.append(" == ".join(ast.unparse(a) for a in node.args[:2]))
    return found


def _python_side_counts(tree: ast.AST) -> dict[str, bool]:
    """Whether the test asserts an equality on a row count and one on a count of non-None values (names expanded one level)."""
    values = {t.targets[0].id: ast.unparse(t.value) for t in ast.walk(tree) if isinstance(t, ast.Assign) and len(t.targets) == 1 and isinstance(t.targets[0], ast.Name)}
    kinds = set()
    for text in _equality_statements(tree):
        expanded = NAME_RE.sub(lambda m: values.get(m.group(0), m.group(0)), text)
        if "len(" in expanded or "sum(" in expanded:
            kinds.add("non_null" if NONE_CHECK_RE.search(expanded) else "rows")
    return {"rows": "rows" in kinds, "non_null": "non_null" in kinds}


def counts_rows_and_non_null(ctx: RowContext, spec: dict) -> dict:
    """The executed SQL over the view, or equality assertions on the fetched rows, count the processed rows and the non-NULL values of the column."""
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
    python = _python_side_counts(tree) if sql.strip() else {"rows": False, "non_null": False}
    found = {"processed rows": bool(ROW_COUNT_RE.search(sql)) or python["rows"], f"non-NULL {column} values": bool(non_null_re(column).search(sql)) or python["non_null"]}
    missing = [what for what, ok in found.items() if not ok]
    return _outcome(not missing, f"the SQL counts the processed rows and the non-NULL {column} values",
                    "the SQL counts no " + " and no ".join(missing) + ", so an empty or all-NULL window passes it")


KINDS: dict[str, Callable[[RowContext, dict], dict]] = {
    "sql_to_run_later_names_wrong_version": to_run_later_names_wrong_version,
    "sql_counts_rows_and_non_null": counts_rows_and_non_null,
}
