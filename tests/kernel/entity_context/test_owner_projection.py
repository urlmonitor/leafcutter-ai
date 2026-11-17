"""DK-300a: canonical owners are the oracle, and initial cards contain meanings only."""

import hashlib
import json

from tests.kernel.entity_context.support import AC_ID, build, cards, recognize


def test_owner_meanings_and_namespaces_are_source_driven(repo):
    # covers: DK-300a-1
    # angle: criterion
    build(repo)
    result = recognize(repo, "Decision Kernel; type: how_to; entry_kind: glossary; native_kind: AcceptanceCriterion")
    assert set((c.family, c.identity) for c in result.entities) >= {
        ("glossary", "decision kernel"), ("doc_type", "how_to"),
        ("entry_kind", "glossary"), ("native_kind", "AcceptanceCriterion")}
    assert cards(result, "glossary")["decision kernel"].meaning == "A scheduler that forms supported repository judgments."
    assert "Task-oriented procedure" in cards(result, "doc_type")["how_to"].meaning
    assert cards(result, "entry_kind")["glossary"].meaning
    assert cards(result, "native_kind")["AcceptanceCriterion"].meaning


def test_declared_aliases_resolve_without_record_bodies(repo):
    # covers: DK-300a-1
    # angle: criterion
    build(repo)
    result = recognize(repo, "Write a how-to document about AC.")
    assert "how_to" in cards(result, "doc_type")
    assert "AcceptanceCriterion" in cards(result, "native_kind")
    exported = json.dumps([c.model_dump(mode="json") for c in result.entities])
    assert "writer_agent" not in exported and "default_path" not in exported
    assert "BODY_SENTINEL" not in exported


def test_undeclared_aliases_and_uncued_genres_are_not_invented(repo):
    # covers: DK-300a-1-i
    # angle: criterion
    build(repo)
    ordinary = recognize(repo, "Please reference this value in the kernel.")
    assert not cards(ordinary, "glossary") and not cards(ordinary, "doc_type")
    cued = recognize(repo, "type: reference")
    assert set(cards(cued, "doc_type")) == {"reference"}


def test_same_spelling_owner_namespaces_remain_distinct(repo):
    # covers: DK-300a-1-i
    # angle: criterion
    build(repo)
    result = recognize(repo, "type: reference and entry_kind: reference")
    assert ("doc_type", "reference") in {(c.family, c.identity) for c in result.entities}
    assert ("entry_kind", "reference") in {(c.family, c.identity) for c in result.entities}
    assert cards(result, "doc_type")["reference"].provenance.locator != cards(result, "entry_kind")["reference"].provenance.locator


def test_python_declaration_cards_have_qualified_identity_and_bounded_signature(repo):
    # covers: DK-300a-2
    # angle: criterion
    build(repo)
    result = recognize(repo, "pkg/alpha.py::run pkg.alpha.TaskInput pkg/alpha.py::TaskInput.perform")
    found = cards(result, "symbol")
    assert set(found) == {"pkg.alpha.run", "pkg.alpha.TaskInput", "pkg.alpha.TaskInput.perform"}
    assert "value: str" in found["pkg.alpha.run"].signature
    assert "count: int" in found["pkg.alpha.TaskInput.perform"].signature
    assert all(c.signature and len(c.signature) <= 300 for c in found.values())


def test_symbol_purpose_uses_only_first_authored_sentence(repo):
    # covers: DK-300a-2
    # angle: criterion
    build(repo)
    found = cards(recognize(repo, "pkg.alpha.run and pkg.alpha.bare"), "symbol")
    assert found["pkg.alpha.run"].meaning == "Return a normalized value."
    assert found["pkg.alpha.bare"].meaning == ""
    assert "SECOND_SENTENCE" not in str(found)


def test_symbol_indexing_never_executes_or_emits_bodies(repo):
    # covers: DK-300a-2
    # angle: criterion
    path = repo / "pkg/alpha.py"
    marker = repo / "source-executed.txt"
    original = path.read_text(encoding="utf-8")
    path.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('bad')\n" + original, encoding="utf-8")
    build(repo)
    result = recognize(repo, "pkg.alpha.run")
    assert "pkg.alpha.run" in cards(result, "symbol")
    assert not marker.exists()
    assert "FUNCTION_BODY_SENTINEL" not in result.model_dump_json()
    assert not any(key in result.model_dump() for key in ("callers", "relations", "evidence"))


def test_non_python_symbol_reference_is_explicitly_unsupported(repo):
    # covers: DK-300a-2-i
    # angle: criterion
    build(repo)
    result = recognize(repo, "Explain pkg/foreign.ts::externalRun.")
    assert not cards(result, "symbol")
    item = next(u for u in result.unresolved if u.reference == "pkg/foreign.ts::externalRun")
    assert item.state == "unsupported_kind" and not item.candidates
    assert "FOREIGN_BODY_SENTINEL" not in result.model_dump_json()


def test_artifact_identity_uses_canonical_owner_and_membership(repo):
    # covers: DK-300a-3
    # angle: criterion
    build(repo)
    result = recognize(repo, f"{AC_ID} ADR-987 dec-0123456789abcdef eval/meaning tickets/TICKET-EC-1100.md")
    found = cards(result, "artifact_id")
    assert {identity: c.native_kind for identity, c in found.items()} == {
        AC_ID: "AcceptanceCriterion", "ADR-987": "ADR", "dec-0123456789abcdef": "Decision",
        "eval/meaning": "Flow", "tickets/TICKET-EC-1100.md": "Ticket"}


def test_artifact_cards_are_metadata_only_with_real_provenance(repo):
    # covers: DK-300a-3
    # angle: criterion
    build(repo)
    result = recognize(repo, f"{AC_ID} ADR-987 dec-0123456789abcdef eval/meaning tickets/TICKET-EC-1100.md")
    assert len(cards(result, "artifact_id")) == 5
    assert "Preserve interpretation context" in cards(result)[AC_ID].meaning
    assert "BODY_SENTINEL" not in result.model_dump_json()
    for card in result.entities:
        source = card.provenance
        assert source.source_id == "eval.entities" and source.snapshot
        relative = source.locator.split("#", 1)[0].split("::", 1)[0]
        if not (repo / relative).is_file():
            relative = next(p.relative_to(repo).as_posix() for p in repo.rglob("*")
                            if p.is_file() and source.locator.startswith(p.relative_to(repo).as_posix()))
        assert source.source_hash.removeprefix("sha256:") == hashlib.sha256((repo / relative).read_bytes()).hexdigest()
        assert len(source.projection_hash.removeprefix("sha256:")) == 64


def test_absent_and_malformed_ids_have_distinct_unresolved_states(repo):
    # covers: DK-300a-3-i
    # angle: criterion
    build(repo)
    result = recognize(repo, "EC-9999a-1-i EC-1100a--1")
    assert {(u.reference, u.state) for u in result.unresolved} == {
        ("EC-9999a-1-i", "unknown_id"), ("EC-1100a--1", "invalid_reference")}
    assert not cards(result, "artifact_id")
    assert all(not u.candidates for u in result.unresolved)
