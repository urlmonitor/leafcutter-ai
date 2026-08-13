"""
MODULE: test_artifact_graph_absent_edges
GOAL: Verify that docs/reference/artifact-knowledge-graph.graph.json records a
relation the map is supposed to answer even when the repo has no backing
field for it, instead of silently dropping it from the `edges` array.

Nature: TDD test stubs — MUST be RED until the coder adds explicit
`status: "absent"` edges for the four reverse lookups named in KM-ADM-002
(source_file->ac, test->source_file, changelog->ac, mockup->ac), gives every
edge (present or absent) a `status` key, enforces the absent-edge invariants
(enforcement == "none", no truthy `field`, non-empty `note`), and documents
the "present" / "absent" vocabulary in the `legend` block.

Symptom (KM-ADM-002): a relation the knowledge graph needs but the repo does
not have is silently omitted from `edges`, so a reader cannot distinguish
"considered and not applicable" from "missing — this is a gap you will hit".

AC: KM-ADM-002
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GRAPH_PATH = (
    _REPO_ROOT / "docs" / "reference" / "artifact-knowledge-graph.graph.json"
)

# The four reverse lookups the map is supposed to answer, each with the
# question a reader is trying to resolve when they look for it.
_REQUIRED_REVERSE_LOOKUPS = [
    ("source_file", "ac", "given this file, which ACs govern it?"),
    ("test", "source_file", "given this test, what code does it exercise?"),
    ("changelog", "ac", "when was this AC shipped?"),
    ("mockup", "ac", "which ACs does this screen realise?"),
]


def _load_graph() -> dict:
    with _GRAPH_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_required_reverse_lookups_are_recorded():
    # covers: KM-ADM-002
    """KM-ADM-002: every reverse lookup a reader needs from the graph must
    have SOME edge recording it — even if the underlying relation does not
    exist in the repo (in which case it should carry status: "absent" rather
    than being omitted entirely). Report every missing pair together with
    the question it exists to answer, not just the first one found.
    """
    graph = _load_graph()
    edges = graph["edges"]
    present_pairs = {(edge.get("source"), edge.get("target")) for edge in edges}

    missing: list[str] = []
    for source, target, question in _REQUIRED_REVERSE_LOOKUPS:
        if (source, target) not in present_pairs:
            missing.append(
                f"({source!r} -> {target!r}): {question!r} has no edge "
                f"recording it at all"
            )

    assert not missing, (
        "artifact-knowledge-graph.graph.json is missing edges for required "
        "reverse lookups (KM-ADM-002 — these must exist explicitly, with "
        "status: \"absent\" if the repo has no backing relation, never be "
        "silently omitted):\n" + "\n".join(f"  - {m}" for m in missing)
    )


def test_every_edge_declares_a_status_and_absent_edges_are_consistent():
    # covers: KM-ADM-002
    """KM-ADM-002: structural invariant over ALL edges, present or absent,
    so this keeps catching drift after the four missing lookups above are
    added:
      - every edge has a `status` of exactly "present" or "absent";
      - every "absent" edge has enforcement == "none";
      - every "absent" edge has no truthy `field` (an absent relation has no
        encoding field to point at);
      - every "absent" edge has a non-empty `note` naming what is missing;
      - every "present" edge has a non-empty `field`.
    Collect every violation and report them together.
    """
    graph = _load_graph()
    edges = graph["edges"]

    violations: list[str] = []
    for edge in edges:
        edge_id = edge.get("id", "<unknown>")
        status = edge.get("status")

        if status not in ("present", "absent"):
            violations.append(
                f"edge '{edge_id}': status={status!r} — must be exactly "
                f"'present' or 'absent'"
            )
            continue

        if status == "absent":
            if edge.get("enforcement") != "none":
                violations.append(
                    f"edge '{edge_id}': status='absent' but "
                    f"enforcement={edge.get('enforcement')!r} (expected "
                    f"'none')"
                )
            if edge.get("field"):
                violations.append(
                    f"edge '{edge_id}': status='absent' but declares a "
                    f"truthy field={edge.get('field')!r} (an absent "
                    f"relation must have no encoding field)"
                )
            if not edge.get("note"):
                violations.append(
                    f"edge '{edge_id}': status='absent' but has no non-empty "
                    f"'note' naming what is missing"
                )
        else:  # status == "present"
            if not edge.get("field"):
                violations.append(
                    f"edge '{edge_id}': status='present' but has no "
                    f"non-empty 'field'"
                )

    assert not violations, (
        "artifact-knowledge-graph.graph.json edges violate the KM-ADM-002 "
        "status vocabulary invariants:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_legend_documents_the_status_vocabulary():
    # covers: KM-ADM-002
    """KM-ADM-002: the "present"/"absent" status vocabulary must be
    self-describing in the `legend` block, not tribal knowledge — a reader
    encountering an edge with status: "absent" should be able to look up
    what that means in the same place `enforcement` and `shape` are
    documented.
    """
    graph = _load_graph()
    legend = graph.get("legend", {})
    status_legend = legend.get("status", {})

    assert isinstance(status_legend, dict) and status_legend, (
        "graph 'legend' block has no 'status' sub-object documenting the "
        "present/absent vocabulary (KM-ADM-002)"
    )

    for key in ("present", "absent"):
        description = status_legend.get(key)
        assert isinstance(description, str) and description.strip(), (
            f"graph legend.status is missing a non-empty description for "
            f"{key!r} (KM-ADM-002)"
        )
