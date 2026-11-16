"""
MODULE: test_artifact_graph_covers_scope
GOAL: Verify that the "test-covers" edge in
docs/reference/artifact-knowledge-graph.graph.json documents the SCOPE of
its "enforced" enforcement rating, not just the fact that a hook blocks.

Bug (KM-ADM-005): check-done-proof is DIFF-SCOPED — it evaluates only ACs
changed in the current commit/PR and never re-evaluates a pre-existing
work_status: done AC. The edge's current `note` says the hook is "enforced"
with no mention of that scope, so a reader inverting the edge ("which test
proves this AC?") concludes every done AC is test-proven, when a large
share of the store's already-done ACs carry no `# covers:` tag from any
test at all.

Nature: TDD test stubs.
  - test_test_covers_edge_documents_its_diff_scope MUST be RED until the
    edge's `note` is rewritten to state both (a) the diff-scoped nature of
    check-done-proof's enforcement and (b) that a numbered backlog of
    already-done ACs is untagged.
  - test_untagged_done_ac_backlog_does_not_grow is a ratchet against the
    LIVE repo state (not a fixture): it measures the current untagged-done
    backlog and asserts it has not grown past HIGH_WATER_MARK. It is
    expected to PASS today — it guards against the backlog growing, it does
    not (by itself) fix the missing note.

AC: KM-ADM-005
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GRAPH_PATH = (
    _REPO_ROOT / "docs" / "reference" / "artifact-knowledge-graph.graph.json"
)
_AC_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"
_TEST_ROOTS = [
    _REPO_ROOT / "unit_tests",
    _REPO_ROOT / "tests",
    _REPO_ROOT / "leafcutter-web",
]

# Measured on this branch on 2026-08-13 with the quote-stripping fix applied
# (see _strip_quotes below): 607 work_status: done ACs across the store,
# 363 tagged by at least one `# covers:` reference under unit_tests/, tests/
# or leafcutter-web/, 244 untagged. The reference implementation at
# /tmp/count_untagged_done_acs.py reports 248 because it does not strip
# quotes from `id: "GE-114-1"`-style YAML values, so 4 quoted ids are
# spuriously treated as distinct from their bare-token `# covers:` tags.
# Re-measured on origin/main on 2026-10-21 (77354d6e9): 243 untagged under
# the old rule, 240 once a superseded AC (status: superseded or
# superseded_by, see _STATUS_SUPERSEDED_RE below) stops counting, because
# 3 untagged done ACs are superseded. The mark drops to 240.
# KM-ADM-005-1, measured 2026-10-25: 1761 finished records, 1518 tagged, 209 untagged,
# 34 excluded (3 superseded + 31 "waived: declared test-free with a stated reason",
# decided by the shared is_covers_tag_waived predicate). Inclusion rule: a finished
# record counts as untagged only if no test tags it, it is not superseded, and the
# done gate does not waive it. The mark drops from 240 to 209.
HIGH_WATER_MARK = 209

_WORK_STATUS_DONE_RE = re.compile(r"^work_status:\s*done\s*$", re.M)
# A superseded AC (status superseded_by / superseded) has no current behaviour
# left to test, so it is not part of the untagged-done backlog.
_STATUS_SUPERSEDED_RE = re.compile(r"^status:\s*superseded(_by)?\s*$", re.M)
_ID_LINE_RE = re.compile(r"^id:\s*(\S+)\s*$", re.M)
_COVERS_RE = re.compile(r"covers:\s*([A-Za-z0-9\-_,\s\"']+)")

# Scope keywords: any of these phrasings pins the MEANING that enforcement
# only applies to ACs changed in the current commit/PR, not the whole store.
_SCOPE_KEYWORDS = (
    "diff-scoped",
    "diff scoped",
    "only ac",
    "only for ac",
    "changed ac",
    "acs changed",
    "not store-wide",
    "not store wide",
    "pre-existing done ac",
    "never re-evaluate",
    "never reevaluate",
)

# Backlog keywords: the note must also say a share of already-done ACs are
# untagged/uncovered, alongside a numeric mention of how many.
_BACKLOG_KEYWORDS = (
    "backlog",
    "untagged",
    "uncovered",
    "no covering test",
    "no test tag",
    "carry no",
)


def _strip_quotes(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        token = token[1:-1]
    return token.strip()


def _load_graph() -> dict:
    with _GRAPH_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _test_covers_edge() -> dict:
    graph = _load_graph()
    edges_by_id = {edge.get("id"): edge for edge in graph["edges"]}
    return edges_by_id["test-covers"]


def test_test_covers_edge_documents_its_diff_scope():
    # covers: KM-ADM-005
    """KM-ADM-005: the "test-covers" edge's `note` must communicate BOTH:
      (a) that check-done-proof's "enforced" rating is diff-scoped — it
          evaluates only ACs changed in the current commit/PR, and never
          re-evaluates a pre-existing work_status: done AC; and
      (b) that a numbered backlog of already-done ACs carries no covering
          test tag at all, so "enforced" must not be read as a store-wide
          guarantee.

    This is expected to FAIL against the current graph JSON, whose note
    ("Enforced for done ACs by check-done-proof (pre-commit + required CI);
    warn otherwise. Coverage regex truncates hierarchical ids (Gap 11).")
    states WHETHER the hook blocks but not WHAT it blocks over.
    """
    edge = _test_covers_edge()
    note = edge.get("note", "")
    note_lower = note.lower()

    has_scope_language = any(kw in note_lower for kw in _SCOPE_KEYWORDS)
    has_numeric_mention = bool(re.search(r"\d+", note))
    has_backlog_language = any(kw in note_lower for kw in _BACKLOG_KEYWORDS)
    has_backlog_fact = has_numeric_mention and has_backlog_language

    missing = []
    if not has_scope_language:
        missing.append(
            "fact (a) — diff-scoped enforcement: note does not state that "
            "check-done-proof evaluates only ACs changed in the current "
            "commit/PR (no scope keyword found, e.g. 'diff-scoped', "
            "'changed ACs', 'not store-wide')"
        )
    if not has_backlog_fact:
        if not has_numeric_mention:
            missing.append(
                "fact (b) — untagged-done backlog: note contains no numeric "
                "count of untagged already-done ACs"
            )
        if not has_backlog_language:
            missing.append(
                "fact (b) — untagged-done backlog: note contains no backlog "
                "keyword (e.g. 'backlog', 'untagged', 'uncovered')"
            )

    assert not missing, (
        "test-covers edge note does not document its diff scope "
        f"(note={note!r}). Missing:\n"
        + "\n".join(f"  - {m}" for m in missing)
    )


def _collect_done_ac_ids() -> set[str]:
    done_ids: set[str] = set()
    for path in _AC_ROOT.rglob("*.yaml"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _WORK_STATUS_DONE_RE.search(text) or _STATUS_SUPERSEDED_RE.search(text):
            continue
        match = _ID_LINE_RE.search(text)
        if match:
            done_ids.add(_strip_quotes(match.group(1)))
    return done_ids


def _collect_covers_tagged_ids() -> set[str]:
    tagged: set[str] = set()
    for troot in _TEST_ROOTS:
        if not troot.exists():
            continue
        for path in troot.rglob("*"):
            if path.is_dir():
                continue
            if "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix not in {".py", ".ts", ".tsx", ".js"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                match = _COVERS_RE.search(line)
                if not match:
                    continue
                for token in re.split(r"[,\s]+", match.group(1)):
                    token = _strip_quotes(token)
                    if token:
                        tagged.add(token)
    return tagged


def test_untagged_done_ac_backlog_does_not_grow(ac_root=_AC_ROOT):
    # covers: KM-ADM-005
    """KM-ADM-005 ratchet: count every work_status: done AC in the live
    store (docs/acceptance-criteria/) whose `id` (quote-stripped) does not
    appear in any `# covers: <id>` tag across unit_tests/, tests/ or
    leafcutter-web/ (skipping node_modules and __pycache__). This count
    must not exceed HIGH_WATER_MARK.

    This is a floor, not a fix: it stops the untagged-done backlog from
    growing while leaving the existing backlog to be retired separately
    (per KM-ADM-005's notes). Marking a further AC done without a covering
    test must push the count over the mark and fail this test.

    KM-ADM-005-1: the count comes from scripts/ac_store/untagged_done_count.py,
    which leaves out superseded records and records the done gate waives (the
    shared is_covers_tag_waived predicate), prints each exclusion with its ground,
    and asserts untagged + exclusions + tagged == finished. `ac_root` defaults to
    the live store; a test may point it at a copy.
    """
    import sys

    sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))
    import untagged_done_count

    result = untagged_done_count.measure(ac_root, _TEST_ROOTS)
    for line in result.exclusion_lines():
        print(f"untagged-done exclusion: {line}")
    for path in result.unreadable:
        print(f"untagged-done UNREADABLE record file: {path}")
    assert not result.unreadable, f"unreadable done-record files: {result.unreadable}"
    result.assert_sum()
    assert result.unexplained_shortfall == 0, (
        f"{result.unexplained_shortfall} excluded record(s) have no published ground"
    )
    untagged = result.untagged

    assert len(untagged) <= HIGH_WATER_MARK, (
        f"untagged-done AC backlog grew to {len(untagged)}, exceeding "
        f"HIGH_WATER_MARK={HIGH_WATER_MARK}. A new work_status: done AC was "
        "added without a `# covers: <id>` tagged test. New ids pushing the "
        f"count over the mark: {untagged[:20]}{'...' if len(untagged) > 20 else ''}"
    )


def test_waived_close_does_not_raise_the_count_and_an_unwaived_close_still_fails_the_ratchet(tmp_path):
    # covers: KM-ADM-005-1
    # angle: criterion
    """KM-ADM-005-1: on a temp copy of the live store, one more done waived record leaves the count and the
    ratchet unchanged; one more done test-free record with no reason and no tag raises the count by one and
    fails the ratchet. The ratchet check takes the store root through `ac_root` (default: the live store);
    the copy is used only here.
    """
    import shutil
    import sys

    import pytest
    import yaml

    sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))
    import untagged_done_count

    copy = tmp_path / "acs"
    shutil.copytree(_AC_ROOT, copy)

    def record(ac_id, **fields):
        data = {"id": ac_id, "title": ac_id, "component": "x", "level": "L3", "status": "active",
                "work_status": "done", **fields}
        (copy / f"{ac_id}.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    before = len(untagged_done_count.measure(copy, _TEST_ROOTS).untagged)
    record("ZZ-KM5-1", test_required=False, test_rationale="Docs-only change; no executable behaviour to test.")
    assert len(untagged_done_count.measure(copy, _TEST_ROOTS).untagged) == before
    test_untagged_done_ac_backlog_does_not_grow(ac_root=copy)
    record("ZZ-KM5-2", test_required=False)
    assert len(untagged_done_count.measure(copy, _TEST_ROOTS).untagged) == before + 1
    with pytest.raises(AssertionError):
        test_untagged_done_ac_backlog_does_not_grow(ac_root=copy)


def test_ratchet_run_reports_its_exclusions_with_grounds_and_passes_on_the_live_store():
    # covers: KM-ADM-005-1
    # angle: reachability
    """KM-ADM-005-1: pytest run as a subprocess on the ratchet test with output shown exits 0 and states each
    exclusion count paired with its ground, so the ratchet calls the new module and not its old inline count.
    """
    import os
    import subprocess
    import sys

    ratchet = "unit_tests/docs/test_artifact_graph_covers_scope.py::test_untagged_done_ac_backlog_does_not_grow"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", ratchet, "-s", "-q", "-p", "no:cacheprovider"],
        cwd=str(_REPO_ROOT), capture_output=True, text=True, encoding="utf-8", timeout=900,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 0, output[-2000:]
    ground = "waived: declared test-free with a stated reason"
    assert re.search(rf"(\d+\D{{0,6}}{re.escape(ground)}|{re.escape(ground)}\D{{0,6}}\d+)", output), (
        f"the ratchet run does not state the waived exclusion count with its ground: {output[-1500:]}")
