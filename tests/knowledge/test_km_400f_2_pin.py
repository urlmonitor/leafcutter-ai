"""KM-400f-2: the pin rules that decide whether a generation outside the bound may be reclaimed.

An absent pin is reclaimed only once the generation is older than the shared continuation lifetime; a
numeric pin decides by whether it is still in the future; the guard re-checks a pin the evaluation
missed; and issued continuations expire one shared lifetime after issue, never beyond the sync
workflow's declared minimum age. Fixtures live in ``_km_400f_2_support``.
"""

import re

from tests.knowledge._km_400f_2_support import (
    EXPIRED,
    HOUR,
    REPO_ID,
    REPO_ROOT,
    UNEXPIRED,
    UNKNOWN,
    _bound,
    _gen,
    _prepare,
    _reasons,
    _sync,
    small_scenario,
)
from tests.knowledge.test_km_400b_2_i import _load
from tests.knowledge.test_km_400b_2_ii import TARGETS, _commit_repository


def test_absent_pin_is_reclaimed_once_older_than_the_continuation_lifetime(tmp_path):
    # covers: KM-400f-2
    # angle: boundary
    sha, loaded, store = _prepare(tmp_path, small_scenario() + [_gen("G29", ago_h=300, pin=UNKNOWN)])

    result = _sync(tmp_path, sha, store, _bound())

    assert result["reclamation"]["reclaimed_generations"] == ["G29"]
    assert "G29" not in store.generation_ids() and store.tagged(store.scope_key(REPO_ID, "G29")) == (0, 0)


def test_absent_pin_younger_than_the_continuation_lifetime_is_declined(tmp_path):
    # covers: KM-400f-2
    # angle: boundary
    from knowledge.cursors import CONTINUATION_LIFETIME_SECONDS

    young_h = CONTINUATION_LIFETIME_SECONDS / 2 / HOUR  # half the lifetime old
    old_h = CONTINUATION_LIFETIME_SECONDS * 2 / HOUR
    gens = [_gen("G31", ago_h=0.01, active=True), _gen("G30", ago_h=young_h, pin=UNKNOWN),
            _gen("G29", ago_h=old_h, pin=UNKNOWN)]
    sha, loaded, store = _prepare(tmp_path, gens)

    result = _sync(tmp_path, sha, store, _bound(limit=2, min_age=0))

    young = store.scope_key(REPO_ID, "G30")
    assert young in store.snapshots and young not in store.deleted_keys and store.tagged(young) == (2, 1)
    assert _reasons(result)["G30"] == "continuation_may_be_live"
    assert result["reclamation"]["reclaimed_generations"] == ["G29"]  # control: the older one goes


def test_numeric_pin_decides_by_whether_it_is_still_in_the_future(tmp_path):
    # covers: KM-400f-2
    # angle: discrimination
    gens = small_scenario() + [_gen("G29", ago_h=300, pin=UNEXPIRED), _gen("G28", ago_h=310, pin=EXPIRED)]
    sha, loaded, store = _prepare(tmp_path, gens)

    result = _sync(tmp_path, sha, store, _bound())

    assert result["reclamation"]["reclaimed_generations"] == ["G28"]
    assert _reasons(result)["G29"] == "pinned_continuation_unexpired"
    assert store.tagged(store.scope_key(REPO_ID, "G29")) == (2, 1)


def test_guard_defends_against_a_future_pin_the_evaluation_missed():
    # covers: KM-400f-2
    # angle: failure
    from knowledge.adapters.retention.reclaim import _guard

    verdict = {"age_seconds": 10 * HOUR}
    fact = {"publication_status": "ready", "pinned_until": 5000.0}
    assert _guard(verdict, fact, now=4000.0) == "pinned_continuation_unexpired"
    assert _guard(verdict, fact, now=6000.0) is None


def test_disclosure_issues_continuations_expiring_one_shared_lifetime_after_issue(tmp_path, monkeypatch):
    # covers: KM-400f-2
    # angle: criterion
    from knowledge import cursors, disclosure
    from knowledge.contracts import KnowledgeEvidence, KnowledgeRetrievalResult
    from tests.knowledge.test_requested_field_disclosure import request

    loaded = _load(tmp_path, _commit_repository(tmp_path, list(TARGETS)))
    issued = []
    monkeypatch.setattr(cursors, "CONTINUATION_LIFETIME_SECONDS", 123)
    monkeypatch.setattr(disclosure.time, "time", lambda: 1000.0)
    real_encode = cursors.encode

    def recording_encode(payload, secret):
        issued.append(payload)
        return real_encode(payload, secret)

    monkeypatch.setattr(cursors, "encode", recording_encode)
    out = KnowledgeRetrievalResult(
        request_id="r", retrieval_id="r", status="ok", requested_mode="exact", executed_mode="exact",
        evidence=[KnowledgeEvidence(entity=loaded.nodes[0])],
    )

    disclosure.finalize(request(), out, {"more": True, "candidates": 1, "generation": "g"}, b"secret")

    assert issued and {p["expires"] for p in issued} == {1000.0 + 123}  # issue time + the shared constant
    disclosure.finalize(request(), out, {"more": True, "generation": "g", "state": {"expires": 1050.0}}, b"s")
    assert issued[-1]["expires"] == 1050.0  # later rounds keep the first expiry (and so never extend it)


def test_continuation_lifetime_never_exceeds_the_sync_workflows_minimum_age():
    # covers: KM-400f-2
    # angle: boundary
    from knowledge.cursors import CONTINUATION_LIFETIME_SECONDS

    text = (REPO_ROOT / ".github" / "workflows" / "knowledge-sync.yml").read_text(encoding="utf-8")
    declared = re.search(r"^\s*KNOWLEDGE_RETENTION_MIN_AGE_SECONDS:\s*'?(\d+)'?\s*$", text, re.MULTILINE)
    assert declared, "the workflow must declare a minimum age"
    assert "--retention-min-age-seconds" in text and "--retention-max-generations" in text
    assert CONTINUATION_LIFETIME_SECONDS <= int(declared.group(1))
