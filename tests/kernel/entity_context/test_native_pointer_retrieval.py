"""Canonical native field references survive the later task-evidence boundary."""

import asyncio
import json
from unittest.mock import patch

import pytest
import yaml

from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.contracts import schema_ids
from kernel.contracts.base import content_hash
from kernel.contracts.enums import EvidenceCategory
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from tests.kernel.capabilities.support import invocation
from tests.kernel.entity_context.support import AC_ID, build, cards, config_for, recognize
from tests.kernel.helpers import bundle_of, make_context


def _fetch(root, locator, config=None):
    """Run real retrieval with no lexical terms that could hide a broken locator."""
    need = EvidenceNeed(id="need.task_context", category=EvidenceCategory.TASK_CONTEXT,
                        question="a b")
    payload = RetrievalRequestPayload(need=need, explicit_locators=[locator])
    request = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST,
                         payload.model_dump(mode="json"))
    result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(
        request, make_context(root, config=config or config_for())))
    return bundle_of(result)


def test_native_ac_reference_reaches_task_evidence_through_service(rig):
    # covers: DK-300d-3
    # angle: reachability
    rig.prepare()
    rig.intents = [("evidence", .95, .95)]
    rig.needs = {"task_context": .95}
    goal = f"What is {AC_ID} about? Explain it in plain language."
    produced = cards(recognize(rig.repo, goal, config=rig.config))[AC_ID]
    locator = produced.provenance.locator
    assert produced.native_kind == "AcceptanceCriterion"
    assert locator.endswith(".yaml#/criteria"), locator
    source = yaml.safe_load((rig.repo / locator.partition("#")[0]).read_text(encoding="utf-8"))
    expected = source["criteria"].strip()
    assert "AC_BODY_SENTINEL" not in produced.meaning
    seen = []
    retrieve = RepositoryRetrievalExecutor.ainvoke

    async def record_real_retrieval(executor, request, context):
        assert any(batch.purpose == "kernel.intent" for batch in rig.jev.batches)
        seen.extend(request.input_payload.get("explicit_locators", []))
        return await retrieve(executor, request, context)

    with patch.object(RepositoryRetrievalExecutor, "ainvoke", new=record_real_retrieval):
        envelope = rig.start(goal)
    saved = rig.values(envelope.run_id)["entity_context"]
    assert cards(saved)[AC_ID].provenance.locator == locator
    assert locator in seen, "research did not consume the real recognizer's canonical hint"
    intent = [batch for batch in rig.jev.batches if batch.purpose == "kernel.intent"]
    assert intent and all("AC_BODY_SENTINEL" not in str(batch.state) for batch in intent)
    assert envelope.output is not None
    evidence = [item for item in envelope.output.payload["evidence"]
                if item["provenance"]["strategy"] == "explicit_locator"
                and "AC_BODY_SENTINEL" in item["excerpt"]]
    assert evidence, envelope.output.payload
    assert len(evidence) == 1
    assert evidence[0]["excerpt"].strip() == expected
    assert evidence[0]["source"]["locator"] == locator
    assert evidence[0]["content_hash"] == content_hash(evidence[0]["excerpt"])


@pytest.mark.parametrize("fragment", ["/missing", "/criteria/child", "/criteria~2"])
def test_invalid_native_pointer_never_falls_back_to_whole_record(repo, fragment):
    # covers: DK-300d-3
    # angle: discrimination
    build(repo)
    locator = cards(recognize(repo, AC_ID))[AC_ID].provenance.locator
    invalid = locator.partition("#")[0] + "#" + fragment
    refused = _fetch(repo, invalid)
    assert refused.evidence == [], "an invalid pointer disclosed unselected record contents"
    assert any(invalid in note and any(word in note.lower() for word in ("not found", "invalid", "refused"))
               for note in refused.limitations), refused.limitations
    # The valid control makes a blanket refusal just as wrong as dropping the fragment.
    valid = _fetch(repo, locator)
    assert len(valid.evidence) == 1, valid.limitations
    assert valid.evidence[0].source.locator == locator
    assert "AC_BODY_SENTINEL" in valid.evidence[0].excerpt
    assert "priority:" not in valid.evidence[0].excerpt


@pytest.mark.parametrize("suffix", ["json", "yaml"])
def test_structured_pointer_selects_nested_value_without_same_line_siblings(repo, suffix):
    # covers: DK-300d-3
    # angle: boundary
    data = {"items": [{"a/b~c": "SELECTED_POINTER_VALUE", "sibling": "SIBLING_MUST_STAY_OUT"}],
            "unrelated": "ROOT_MUST_STAY_OUT"}
    serialized = (json.dumps(data) if suffix == "json"
                  else yaml.safe_dump(data, default_flow_style=True, width=1000))
    path = repo / "docs" / f"pointer-boundary.{suffix}"
    path.write_text(serialized, encoding="utf-8")
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    locator = f"docs/{path.name}#/items/0/a~1b~0c"
    bundle = _fetch(repo, locator)
    assert len(bundle.evidence) == 1, bundle.limitations
    item = bundle.evidence[0]
    assert item.excerpt == data["items"][0]["a/b~c"]
    assert item.source.locator == locator
    assert item.provenance.strategy == "explicit_locator"
    assert item.content_hash == content_hash(item.excerpt)
