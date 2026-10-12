"""Literal canonical ADR names retain their full identity at the host boundary."""

import pytest

from kernel.contracts.retrieval_needs import prepare_request
from tests.kernel.retrieval.test_retrieval_needs_llm import source_request


@pytest.mark.parametrize("known", [False, True])
def test_full_adr_stem_is_offered_without_an_ungrounded_short_prefix(known):
    # covers: KM-500e-1-i
    # angle: discrimination
    # angle: boundary
    identifier = "ADR-012-retire-create-ticket-js"
    request = source_request(f"Explain {identifier} in plain language.")
    if known:
        request = request.model_copy(update={"known_ids": [identifier]})
    prepared = prepare_request(request)
    assert set(prepared.catalog["target_ids"]) == {identifier}
    assert prepared.original_question == request.original_question
    assert prepared.source_scope == request.source_scope


@pytest.mark.parametrize("question,expected", [
    ("Explain notADR-012-retire-create-ticket-js.", set()),
    ("Explain ADR-012-retire-create-ticket-js_extra.", set()),
    ("Explain ADR-012-retire-create-ticket-js-extra.", {"ADR-012-retire-create-ticket-js-extra"}),
])
def test_literal_candidates_do_not_extract_embedded_or_neighbor_prefixes(question, expected):
    # covers: KM-500e-1-i
    # angle: boundary
    prepared = prepare_request(source_request(question))
    assert set(prepared.catalog["target_ids"]) == expected
    assert prepared.original_question == question
