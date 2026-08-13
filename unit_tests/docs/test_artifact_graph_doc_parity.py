"""
MODULE: test_artifact_graph_doc_parity
GOAL: Verify that the human-readable trust table in
docs/reference/artifact-knowledge-graph-data-map.md agrees with the
machine-readable docs/reference/artifact-knowledge-graph.graph.json, which
the JSON itself names as its `source_doc`.

Nature: TDD test stubs — MUST be RED until the doc is corrected. Five
corrections (KM-ADM-001 through KM-ADM-005) landed on the JSON alone, so the
doc's trust table now disagrees with the SSOT on at least two rows:
  - `TESTED_BY` (`covered_by` test entries): doc says "warn", JSON says "none".
  - `TOUCHES` (`files_touched`): doc says "none", JSON says "warn".

Direction of truth: the JSON is the SSOT (see KM-ADM-006.yaml notes). These
tests assert "doc must agree with JSON", never the reverse.

AC: KM-ADM-006
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GRAPH_JSON_PATH = REPO_ROOT / "docs" / "reference" / "artifact-knowledge-graph.graph.json"
DATA_MAP_DOC_PATH = REPO_ROOT / "docs" / "reference" / "artifact-knowledge-graph-data-map.md"

MIN_MATCHED_ROWS = 12


def _load_graph_json() -> dict:
    return json.loads(GRAPH_JSON_PATH.read_text(encoding="utf-8"))


def _load_doc_text() -> str:
    return DATA_MAP_DOC_PATH.read_text(encoding="utf-8")


def _strip_markdown_noise(cell: str) -> str:
    """Strip backticks and bold markers; collapse whitespace. Parenthetical
    qualifiers are intentionally preserved — they are semantically
    significant (e.g. "covered_by (test entries)" vs
    "covered_by (child-AC entries)" must not be conflated)."""
    text = cell.strip()
    text = text.replace("`", "")
    text = text.replace("**", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_field(cell: str) -> str:
    return _strip_markdown_noise(cell).lower()


def normalize_enforcement(cell: str) -> str:
    """Reduce an Enforcement cell to its leading token.

    "enforced (for `done` ACs)" -> "enforced"
    "derived-validated"          -> "derived-validated"
    "n/a (algorithmic)"          -> "n/a"
    """
    text = _strip_markdown_noise(cell).lower()
    # Cut at the first "(" or at a slash used as a separator (surrounded by
    # whitespace) so that tokens like "n/a" survive intact while
    # alternations like "enforced (AC) / none (others)" still reduce to
    # their first alternative's leading word.
    parts = re.split(r"\(|\s/\s", text, maxsplit=1)
    return parts[0].strip()


def parse_trust_table(doc_text: str) -> list[list[str]]:
    """Parse the pipe-delimited trust table into a list of row-cell-lists.

    Identifies the table by its header row (the one starting with
    "| Canonical Edge |" and containing "Enforcement" and "Shape"), skips
    the separator row, then collects every subsequent "|"-prefixed line
    until the first blank/non-table line.
    """
    lines = doc_text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (
            stripped.startswith("| Canonical Edge |")
            and "Enforcement" in stripped
            and "Shape" in stripped
        ):
            header_idx = i
            break

    assert header_idx is not None, (
        "Could not locate the trust table header row "
        "('| Canonical Edge | ... | Enforcement | Shape | ...') in "
        f"{DATA_MAP_DOC_PATH}"
    )

    rows: list[list[str]] = []
    # lines[header_idx + 1] is expected to be the "|---|---|...|" separator.
    idx = header_idx + 2
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [c.strip() for c in stripped.split("|")]
        # A well-formed "| a | b | c |" line splits to ["", "a", "b", "c", ""]
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        rows.append(cells)
        idx += 1

    return rows


def test_doc_trust_table_agrees_with_the_graph_json():
    # covers: KM-ADM-006
    """AC-KM-ADM-006: for every JSON edge whose encoding field also appears
    in the doc's trust table, the doc row's enforcement value must equal
    the JSON edge's enforcement."""
    graph = _load_graph_json()
    doc_text = _load_doc_text()
    doc_rows = parse_trust_table(doc_text)

    # Build a pool of (normalized_field, enforcement_cell) for doc rows,
    # each usable at most once, so that two JSON edges that happen to share
    # a field string (e.g. "depends_on") are matched to distinct doc rows
    # rather than both colliding on the first one found.
    doc_pool: list[dict] = []
    for cells in doc_rows:
        if len(cells) < 7:
            continue
        field_cell = cells[2]
        enforcement_cell = cells[5]
        doc_pool.append(
            {
                "normalized_field": normalize_field(field_cell),
                "raw_field": field_cell,
                "enforcement": normalize_enforcement(enforcement_cell),
                "raw_enforcement": enforcement_cell,
                "claimed": False,
            }
        )

    mismatches: list[str] = []
    matched_count = 0

    for edge in graph["edges"]:
        if edge.get("status") != "present":
            continue
        field = edge.get("field")
        if not field:
            continue
        normalized_edge_field = normalize_field(field)

        matched_row = None
        for row in doc_pool:
            if row["claimed"]:
                continue
            if row["normalized_field"] == normalized_edge_field:
                matched_row = row
                break

        if matched_row is None:
            # Legitimate: the table holds rows with no JSON counterpart
            # (e.g. ticket `source_ac`), and JSON may hold fields the doc
            # phrases differently. Skip rather than fail.
            continue

        matched_row["claimed"] = True
        matched_count += 1

        json_enforcement = edge.get("enforcement")
        if matched_row["enforcement"] != json_enforcement:
            mismatches.append(
                f"{edge['id']} (field {field}): "
                f"json={json_enforcement} doc={matched_row['enforcement']}"
            )

    assert not mismatches, (
        "Doc trust table disagrees with JSON SSOT on enforcement rating for "
        + "; ".join(mismatches)
    )

    # This assertion is NOT optional set-dressing: a matcher that skips
    # every row it cannot match degrades to vacuously green the moment the
    # table is reformatted (every edge silently "matches nothing"). Pinning
    # a minimum match count keeps the test honest.
    assert matched_count >= MIN_MATCHED_ROWS, (
        f"Only {matched_count} doc rows were matched to JSON edges by field "
        f"(need >= {MIN_MATCHED_ROWS}); the parity check may be silently "
        "matching nothing due to a table-format or normalization drift."
    )


def _keywords_arrow_pair_present(doc_text: str, source_variants: list[str], target_variants: list[str]) -> bool:
    """Tolerant check for a "<source> -> <target>" prose pair, as used by
    the doc's "Edges not yet encoded" bullets (e.g. "Changelog -> AC:")."""
    src_pat = "(?:" + "|".join(source_variants) + ")"
    tgt_pat = "(?:" + "|".join(target_variants) + ")"
    pattern = rf"{src_pat}\s*(?:→|->)\s*{tgt_pat}"
    return re.search(pattern, doc_text, re.IGNORECASE) is not None


def test_doc_documents_the_status_axis_and_the_absent_relations():
    # covers: KM-ADM-006
    """AC-KM-ADM-006: the doc documents the status axis (present/absent
    vocabulary) and lists the four recorded absent relations, so a reader
    of the prose learns about the gaps without opening the JSON."""
    doc_text = _load_doc_text()

    missing: list[str] = []

    has_present_keyword = re.search(r"\bpresent\b", doc_text, re.IGNORECASE) is not None
    has_absent_keyword = re.search(r"\babsent\b", doc_text, re.IGNORECASE) is not None
    has_status_axis_language = has_present_keyword and has_absent_keyword
    if not has_status_axis_language:
        missing.append(
            "status axis vocabulary (doc must describe edges using "
            "'present'/'absent' status terms, mirroring the JSON legend.status axis)"
        )

    ac_variants = [r"\bAC\b", r"Acceptance Criterion"]
    absent_relation_pairs = {
        "source file -> AC": ([r"source[\s_-]*file"], ac_variants),
        "test -> source file": ([r"\btest\b"], [r"source[\s_-]*file"]),
        "changelog -> AC": ([r"changelog"], ac_variants),
        "mockup -> AC": ([r"mockup"], ac_variants),
    }

    for label, (src, tgt) in absent_relation_pairs.items():
        if not _keywords_arrow_pair_present(doc_text, src, tgt):
            missing.append(f"absent relation not documented: {label}")

    assert not missing, (
        "Doc is missing required status-axis / absent-relation documentation: "
        + "; ".join(missing)
    )


def test_doc_reflects_the_corrected_ratings():
    # covers: KM-ADM-006
    """AC-KM-ADM-006 (narrow regression pin, KM-ADM-001/KM-ADM-005): TESTED_BY
    is none, TOUCHES is warn, and COVERS names its diff scope. Expectations
    for enforcement are derived from the JSON SSOT rather than hardcoded."""
    graph = _load_graph_json()
    doc_text = _load_doc_text()
    doc_rows = parse_trust_table(doc_text)

    edges_by_id = {edge["id"]: edge for edge in graph["edges"]}
    tested_by_json_enforcement = edges_by_id["ac-tested"]["enforcement"]
    touches_json_enforcement = edges_by_id["ticket-touches"]["enforcement"]

    tested_by_row = None
    touches_row = None
    covers_row = None
    for cells in doc_rows:
        if len(cells) < 7:
            continue
        canonical_edge = cells[0]
        field = cells[2]
        if "TESTED_BY" in canonical_edge and "covered_by" in field:
            tested_by_row = cells
        elif "TOUCHES" in canonical_edge:
            touches_row = cells
        elif "COVERS" in canonical_edge and "covers" in field.lower():
            covers_row = cells

    assert tested_by_row is not None, "Could not find the TESTED_BY row in the doc trust table"
    assert touches_row is not None, "Could not find the TOUCHES row in the doc trust table"
    assert covers_row is not None, "Could not find the COVERS row in the doc trust table"

    tested_by_doc_enforcement = normalize_enforcement(tested_by_row[5])
    touches_doc_enforcement = normalize_enforcement(touches_row[5])

    assert tested_by_doc_enforcement != "warn", (
        "TESTED_BY row must not be rated 'warn' (KM-ADM-001 corrected the "
        f"JSON to '{tested_by_json_enforcement}'); doc still says "
        f"'{tested_by_doc_enforcement}'"
    )
    assert tested_by_doc_enforcement == tested_by_json_enforcement, (
        f"TESTED_BY doc enforcement '{tested_by_doc_enforcement}' does not "
        f"match JSON SSOT '{tested_by_json_enforcement}'"
    )

    assert touches_doc_enforcement != "none", (
        "TOUCHES row must not be rated 'none' (KM-ADM-001 corrected the "
        f"JSON to '{touches_json_enforcement}'); doc still says "
        f"'{touches_doc_enforcement}'"
    )
    assert touches_doc_enforcement == touches_json_enforcement, (
        f"TOUCHES doc enforcement '{touches_doc_enforcement}' does not "
        f"match JSON SSOT '{touches_json_enforcement}'"
    )

    covers_notes = covers_row[-1]
    scope_keywords = ("diff", "diff-scoped", "scope")
    assert any(kw in covers_notes.lower() for kw in scope_keywords), (
        "COVERS row's Notes cell must mention its diff scope (the JSON note "
        "explains COVERS is DIFF-SCOPED: it evaluates only ACs changed in "
        "the current commit/PR and never re-evaluates a pre-existing done "
        f"AC); doc Notes currently reads: {covers_notes!r}"
    )
