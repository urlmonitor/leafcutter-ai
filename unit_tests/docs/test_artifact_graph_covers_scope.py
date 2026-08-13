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
HIGH_WATER_MARK = 244

_WORK_STATUS_DONE_RE = re.compile(r"^work_status:\s*done\s*$", re.M)
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
        if not _WORK_STATUS_DONE_RE.search(text):
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


def test_untagged_done_ac_backlog_does_not_grow():
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
    """
    done_ids = _collect_done_ac_ids()
    tagged_ids = _collect_covers_tagged_ids()
    untagged = sorted(done_ids - tagged_ids)

    assert len(untagged) <= HIGH_WATER_MARK, (
        f"untagged-done AC backlog grew to {len(untagged)}, exceeding "
        f"HIGH_WATER_MARK={HIGH_WATER_MARK}. A new work_status: done AC was "
        "added without a `# covers: <id>` tagged test. New ids pushing the "
        f"count over the mark: {untagged[:20]}{'...' if len(untagged) > 20 else ''}"
    )
