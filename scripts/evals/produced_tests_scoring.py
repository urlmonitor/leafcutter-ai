"""
MODULE: scripts/evals/produced_tests_scoring.py
GOAL: Score one row of a produced-tests eval set: place the agent's recorded output in a
    git sandbox and run the row's assertions against it, deterministically.
BUSINESS CONTEXT: TQ-200d-1 / TQ-200d-1-i. A test-writing agent is judged by what its tests
    do, not by what its report says. Each assertion kind encodes one way a green test lets a
    wrong version through: a fixture that still seeds the old column (incident 2), a
    NULL-skipping check an empty window passes, presence measured instead of correctness
    (incident 8), a regression test that fails only at import, and a test that survives the
    wrong version it claims to catch (incident 1, scored by running it). The judge is optional
    and secondary; it never decides a test half.
ARCHITECTURE: ``score_row`` is the entry point. Assertion kinds are registered in KINDS; the
    kinds that execute code live in produced_tests_runs.py. Static kinds read the produced
    test with ast. A scored row is {"id", "negative", "score": {"passed", "assertions":
    [{"kind", "passed", "detail"}], "judge", "halves"?}}. The two refresh-gate kinds also
    fill score.halves.test / score.halves.report, each {"passed", "detail"}, and the row
    passes only when every assertion (so both halves) passes.
"""

from __future__ import annotations

import ast
import logging
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import designer_eval
import produced_tests_db as db_kinds
import produced_tests_mutants as mutants
import produced_tests_runs as runs
import sql_test_writer_eval
from produced_tests_runs import RowContext, SandboxError

logger = logging.getLogger("run_agent_eval")
REPO_ROOT = Path(__file__).resolve().parents[2]
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)")
UNKNOWN = object()


def _parse(ctx: RowContext, spec: dict) -> tuple[ast.Module | None, str]:
    """Parse the produced test file the spec names; the detail says why it could not be."""
    path = ctx.test_files.get(spec.get("file", ""))
    if path is None:
        return None, f"the output holds no test file {spec.get('file')!r}"
    try:
        return ast.parse(path.read_text(encoding="utf-8")), ""
    except SyntaxError as exc:
        return None, f"{path.name} does not parse: {exc}"


def _literal(node: ast.AST) -> object:
    """Evaluate a literal node; UNKNOWN when it is not a literal."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return UNKNOWN


def _seed_maps(tree: ast.AST) -> list[dict[str, ast.AST]]:
    """Every seeded record: dict literals with string keys and calls with keyword arguments."""
    maps: list[dict[str, ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            maps.append({k.value: v for k, v in zip(node.keys, node.values, strict=True) if isinstance(k, ast.Constant) and isinstance(k.value, str)})
        elif isinstance(node, ast.Call) and node.keywords:
            maps.append({k.arg: k.value for k in node.keywords if k.arg})
    return maps


def fixture_seeds_moved_input(ctx: RowContext, spec: dict) -> dict:
    """The fixture seeds the NEW column, with values distinct from the old one (incident 2)."""
    tree, why = _parse(ctx, spec)
    if tree is None:
        return {"passed": False, "detail": why}
    new, old = spec["column"], spec["old_column"]
    seeded = [m for m in _seed_maps(tree) if new in m]
    if not seeded:
        return {"passed": False, "detail": f"the fixture seeds no '{new}' values (only the old '{old}' column?), so the gate's real input is never exercised"}
    same = [m for m in seeded if old in m and (_literal(m[new]) is UNKNOWN or _literal(m[new]) == _literal(m[old]))]
    if same:
        return {"passed": False, "detail": f"'{new}' is seeded equal to '{old}' (or not as a literal), so a gate still reading '{old}' would pass"}
    return {"passed": True, "detail": f"{len(seeded)} seeded record(s) hold '{new}' with values distinct from '{old}'"}


_COUNT_CALLS = {"len", "sum", "count"}
_CALL_OPS = {"assertEqual": ast.Eq, "assertEquals": ast.Eq, "assertGreater": ast.Gt, "assertGreaterEqual": ast.GtE}


def _assertion_tests(tree: ast.AST) -> list[ast.expr]:
    """Every assertion of the file as the expression it states: a bare assert's test, or the call's comparison.

    ``self.assertEqual(a, b)`` is ``a == b``, ``assertGreater(a, b)`` is ``a > b``, ``assertGreaterEqual`` is
    ``a >= b`` and ``assertTrue(x)`` is ``x``. ``assertIsNotNone`` and any other call state no comparison.
    """
    tests: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            tests.append(node.test)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            name = node.func.attr
            if name in _CALL_OPS and len(node.args) == 2:
                tests.append(ast.Compare(left=node.args[0], ops=[_CALL_OPS[name]()], comparators=[node.args[1]]))
            elif name == "assertTrue" and node.args:
                tests.append(node.args[0])
    return tests


def _resolve(node: ast.AST, assigned: Mapping[str, ast.AST]) -> ast.AST:
    """A name resolved to the expression it was assigned from."""
    return assigned.get(node.id, node) if isinstance(node, ast.Name) else node


def _is_count(node: ast.AST) -> bool:
    """The expression calls the bare function len, sum or count."""
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _COUNT_CALLS for n in ast.walk(node))


def _int_literal(node: ast.AST) -> int | None:
    """The int a node holds as a literal (a bool is not one), else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    return None


def _count_side(counted: ast.AST, other: ast.AST, assigned: Mapping[str, ast.AST]) -> ast.AST | None:
    """The counted expression of ``<count> == <int or count expression>`` (names resolved), else None.

    The other side must be an int literal or a count expression such as ``len(seed)``, and never the same
    expression as the counted side, which holds for an empty window too.
    """
    side, limit = _resolve(counted, assigned), _resolve(other, assigned)
    if not _is_count(side) or (_int_literal(limit) is None and not _is_count(limit)):
        return None
    return None if ast.dump(side) == ast.dump(limit) else side


def _kind_of_side(side: ast.AST, op: ast.cmpop, bound: int | None) -> str | None:
    """'processed' or 'non_null' for a counted expression compared by *op* with *bound* (None: non-literal)."""
    if not any(isinstance(n, ast.Constant) and n.value is None for n in ast.walk(side)):
        return "processed" if isinstance(op, ast.Eq) else None
    exact = isinstance(op, ast.Eq) or (bound is not None and ((isinstance(op, ast.Gt) and bound >= 0) or (isinstance(op, ast.GtE) and bound >= 1)))
    return "non_null" if exact else None


def _has_none(node: ast.AST, assigned: Mapping[str, ast.AST]) -> bool:
    """The (name-resolved) expression holds a ``None`` constant."""
    return any(isinstance(n, ast.Constant) and n.value is None for n in ast.walk(_resolve(node, assigned)))


def _count_kinds(test: ast.expr, assigned: Mapping[str, ast.AST]) -> set[str | None]:
    """Classify an assertion's comparison as a 'processed' or a 'non_null' count (an == may hold the count on either side).

    When both sides of an == are counts, the side holding a ``None`` is the counted one (a non-NULL count).
    """
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return set()
    op, left, right = test.ops[0], test.left, test.comparators[0]
    pairs = [(left, right), (right, left)] if isinstance(op, ast.Eq) else [(left, right)]
    for counted, other in sorted(pairs, key=lambda p: not _has_none(p[0], assigned)):
        side = _count_side(counted, other, assigned)
        if side is not None and (isinstance(op, ast.Eq) or _int_literal(other) is not None):
            return {_kind_of_side(side, op, _int_literal(other))}
    return set()


def counts_rows_and_non_null(ctx: RowContext, spec: dict) -> dict:
    """The test asserts an exact processed-row count and a non-NULL count (empty window, TQ-500f-4-ii C1)."""
    tree, why = _parse(ctx, spec)
    if tree is None:
        return {"passed": False, "detail": why}
    assigned = {t.id: n.value for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    kinds = set().union(*(_count_kinds(t, assigned) for t in _assertion_tests(tree)))
    missing = [label for label, key in (("an exact processed-row count", "processed"), ("a non-NULL count", "non_null")) if key not in kinds]
    if missing:
        return {"passed": False, "detail": "the test asserts no " + " and no ".join(missing) + ", so an empty or all-NULL window passes it"}
    return {"passed": True, "detail": "asserts the processed-row count and the non-NULL count"}


def _numbers(tree: ast.AST) -> set[float]:
    """Numeric literals the test seeds: constants in assignments (assertions are not seeds)."""
    return {n.value for a in ast.walk(tree) if isinstance(a, ast.Assign) for n in ast.walk(a.value)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)}


def asserts_known_seeded_value(ctx: RowContext, spec: dict) -> dict:
    """The test asserts equality with a value its fixture seeded (presence is not correctness, C2)."""
    tree, why = _parse(ctx, spec)
    if tree is None:
        return {"passed": False, "detail": why}
    seeded = _numbers(tree)
    for test in _assertion_tests(tree):
        for cmp_ in (n for n in ast.walk(test) if isinstance(n, ast.Compare) and all(isinstance(o, ast.Eq) for o in n.ops)):
            hit = [n.value for n in ast.walk(cmp_) if isinstance(n, ast.Constant) and n.value in seeded and not isinstance(n.value, bool)]
            if hit:
                return {"passed": True, "detail": f"asserts the seeded known value {hit[0]!r}"}
    return {"passed": False, "detail": "no assertion compares against a value the fixture seeded; the test measures presence, not correctness"}


def files_present(ctx: RowContext, spec: dict) -> dict:
    """Every named test file is in the output (a test A and a test B were both asked for)."""
    missing = [n for n in spec["files"] if n not in ctx.test_files]
    if missing:
        return {"passed": False, "detail": f"missing test file(s): {missing}"}
    return {"passed": True, "detail": f"all {len(spec['files'])} test file(s) present"}


def report_mentions(ctx: RowContext, spec: dict) -> dict:
    """The completion report names the thing the row is about (``contains``, or any ``also_accepts`` wording)."""
    terms = [spec["contains"], *spec.get("also_accepts", [])]
    report = ctx.report.lower()
    found = next((term for term in terms if term.lower() in report), None)
    if found is not None:
        return {"passed": True, "detail": f"report names '{found}'"}
    return {"passed": False, "detail": "report does not name " + " or ".join(f"'{term}'" for term in terms)}


def _wrong_version_items(report: str) -> list[str]:
    """The list items under the report's 'Wrong versions the tests now catch' heading."""
    items: list[str] = []
    inside = False
    for line in report.splitlines():
        if re.search(r"wrong versions the tests now catch", line, re.IGNORECASE):
            inside = True
        elif inside and line.lstrip().startswith("#"):
            break
        elif inside and (item := LIST_ITEM_RE.match(line)):
            items.append(item.group(1))
    return items


def report_lists_wrong_version(ctx: RowContext, spec: dict) -> dict:
    """The report's 'Wrong versions the tests now catch' list names the wrong version (deterministic, no judge)."""
    items = _wrong_version_items(ctx.report)
    hit = [i for i in items if spec["contains"].lower() in i.lower()]
    if hit:
        return {"passed": True, "detail": f"the report lists the wrong version: '{hit[0]}'"}
    return {"passed": False, "detail": f"the report's wrong-versions list ({items or 'empty or absent'}) names no '{spec['contains']}'"}


KINDS: dict[str, Callable[[RowContext, dict], dict]] = {
    "fixture_seeds_moved_input": fixture_seeds_moved_input,
    "counts_rows_and_non_null": counts_rows_and_non_null,
    "asserts_known_seeded_value": asserts_known_seeded_value,
    "test_files_present": files_present,
    "test_fails_on_wrong_result": mutants.fails_on_wrong_result,
    "fails_on_mutants": mutants.fails_on_mutants,
    "produced_test_green": mutants.produced_test_green,
    "report_mentions": report_mentions,
    "report_lists_wrong_version": report_lists_wrong_version,
    "wrong_version_run": runs.wrong_version_run,
    **db_kinds.KINDS,
    **sql_test_writer_eval.KINDS,
    **designer_eval.KINDS,
}
HALF_OF = {"wrong_version_run": "test", "report_lists_wrong_version": "report"}


def run_assertion(ctx: RowContext, spec: dict) -> dict:
    """Run one assertion spec; an unknown kind or a sandbox failure is a failed assertion, never a skip."""
    kind = spec.get("kind", "")
    check = KINDS.get(kind)
    if check is None:
        return {"passed": False, "detail": f"unknown assertion kind {kind!r}"}
    try:
        return check(ctx, spec)
    except (SandboxError, OSError, KeyError, ValueError, TypeError, SyntaxError) as exc:
        logger.warning("assertion %s could not run: %r", kind, exc)
        return {"passed": False, "detail": f"{kind} could not run: {exc!r}"}


def score_row(row: dict[str, Any], output_dir: Path, work_dir: Path, *, repo_root: Path | None = None,
              judge: Callable[..., dict] | None = None, expected_field: str = "expected",
              support: tuple[tuple[Path, str], ...] = ()) -> dict[str, Any]:
    """Score one recorded (or live) output for *row* in a fresh git sandbox at ``work_dir/sandbox``.

    *expected_field* names the row key that holds the expectations; *support* is the ``(source dir,
    relative dir)`` scripts a live agent had, so the scoring sandbox holds the same files.
    """
    root = repo_root or REPO_ROOT
    expected = row[expected_field]
    specs = expected.get("assertions", [])
    sandbox = work_dir / runs.SANDBOX_NAME
    base = runs.build_sandbox(root / expected["fixture"], sandbox, runs.hold_back_dirs(specs), support)
    try:
        ctx = RowContext(sandbox, work_dir, root / expected["fixture"], base)
        runs.place_outputs(output_dir, ctx)
        outcomes = [(spec["kind"], run_assertion(ctx, spec)) for spec in specs]
    finally:
        runs.remove_tree_quietly(sandbox)
    score: dict[str, Any] = {
        "passed": all(o["passed"] for _, o in outcomes),
        "assertions": [{"kind": k, "passed": o["passed"], "detail": o["detail"]} for k, o in outcomes],
        "judge": None,
    }
    halves = {HALF_OF[k]: o for k, o in outcomes if k in HALF_OF}
    if halves:
        score["halves"] = halves
    if judge is not None and expected.get("rubric"):
        score["judge"] = judge(ctx.report, expected["rubric"])
        score["passed"] = score["passed"] and bool(score["judge"].get("passed", score["judge"].get("verdict") == "pass"))
    return {"id": row["id"], "negative": bool(expected.get("negative")), "score": score}
