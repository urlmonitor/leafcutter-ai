"""DK-300b: whole-goal admission, deterministic matching and bounded work."""

import itertools
import re
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from kernel.contracts import CallerContext, schema_ids
from kernel.contracts.schema_catalog import validate_payload
from tests.kernel.entity_context.support import (
    AC_ID, api, build, cards, cli_run, compact_size, config_for, long_goal, payload,
    recognize, task_for, write,
)


def test_all_admission_boundaries_preserve_exactly_16000_characters(rig):
    # covers: DK-300b-1
    # angle: boundary
    rig.prepare()
    goal = " \n" + "ü" * 15997 + " "
    assert len(goal) == 16000
    task = task_for(rig.repo, goal)
    assert task.goal == goal
    assert validate_payload(schema_ids.GOAL_REQUEST, {"goal": goal}).goal == goal
    rig.intents = [("change", .95, .95)]
    code, document = cli_run(rig, task.model_dump(mode="json"))
    assert code == 0, document
    values = rig.values(document["run_id"])
    assert values["task"].original_goal == goal
    assert values["entity_context"].original_goal == goal
    assert rig.classified() == [goal]


def test_late_entity_in_thousand_word_goal_is_scanned(rig):
    # covers: DK-300b-1
    # angle: reachability
    rig.prepare()
    goal = long_goal()
    assert len(goal.split()) == 1000 and len(goal) < 16000
    rig.intents = [("change", .95, .95)]
    envelope = rig.start(goal)
    saved = rig.values(envelope.run_id)["entity_context"]
    assert saved.original_goal == goal and saved.coverage.scan_complete
    assert AC_ID in cards(saved, "artifact_id")
    assert cards(saved)[AC_ID].matches[0].start == goal.index(AC_ID)
    assert rig.classified() == [goal]


def test_16001_character_goal_is_rejected_before_classification(rig):
    # covers: DK-300b-1-i
    # angle: boundary
    rig.prepare()
    goal = "g" * 16001
    with pytest.raises(ValidationError, match="16000"):
        task_for(rig.repo, goal)
    with pytest.raises(Exception, match="16000"):
        validate_payload(schema_ids.GOAL_REQUEST, {"goal": goal})
    raw = task_for(rig.repo, "admitted").model_dump(mode="json")
    raw["goal"] = goal
    code, error = cli_run(rig, raw)
    assert code != 0 and "16000" in str(error)
    assert not rig.jev.batches


def test_unicode_boundaries_longest_phrases_and_owner_case_rules(repo):
    # covers: DK-300b-2
    # angle: criterion
    build(repo)
    goal = 'DECISION KERNEL STRASSE CACHE TaskInputExtra préTaskInput ßAC ec-1100a-1-i taskinput'
    result = recognize(repo, goal)
    assert set(cards(result, "glossary")) == {"decision kernel", "straße"}
    assert not cards(result, "symbol") and not cards(result, "artifact_id")
    assert not cards(result, "native_kind")
    for card in result.entities:
        for match in card.matches:
            assert goal[match.start:match.end] == match.surface


def test_generic_types_need_cues_and_quoted_mentions_are_data(repo):
    # covers: DK-300b-2
    # angle: criterion
    build(repo)
    assert not cards(recognize(repo, "Please reference this value"), "doc_type")
    for goal in ('type: reference', 'reference document', '`type: reference`'):
        result = recognize(repo, goal)
        assert set(cards(result, "doc_type")) == {"reference"}
        assert "evidence" not in result.model_dump()
        assert result.original_goal == goal and not result.registered_capabilities


def test_repeated_mentions_keep_exact_original_offsets_and_one_card(repo):
    # covers: DK-300b-2
    # angle: criterion
    build(repo)
    goal = "日本 " + " ".join(['"Zephyr"', "ZEPHYR"] * 40)
    caller = CallerContext(conversation=[" ".join(["zephyr"] * 20)])
    result = recognize(repo, goal, context=caller)
    assert len(result.entities) == 1
    card = cards(result)["zephyr"]
    assert len(card.matches) == 100 and result.budgets.lookups == 1
    for channel, text in (("goal", goal), ("conversation", caller.conversation[0])):
        observed = [(m.start, m.end, m.surface) for m in card.matches if m.channel == channel]
        expected = [(m.start(), m.end(), m.group()) for m in re.finditer("zephyr", text, re.IGNORECASE)]
        assert observed == expected


def test_short_symbol_ambiguity_contains_only_permitted_candidates(repo):
    # covers: DK-300b-2-i
    # angle: criterion
    config = config_for()
    build(repo, config)
    config = config.model_copy(update={"sources": [s.model_copy(update={"deny_globs": ["**/secret.py"]}) for s in config.sources]})
    result = recognize(repo, "Explain run.", config=config)
    item = next(u for u in result.unresolved if u.reference == "run")
    assert item.state == "ambiguous" and set(item.candidates) == {"pkg.alpha.run", "pkg.beta.run"}
    assert not [c for c in result.entities if c.family == "symbol" and c.resolution == "resolved"]
    assert "pkg.secret" not in result.model_dump_json() and "SECRET_" not in result.model_dump_json()


def test_qualified_and_unique_short_symbols_resolve_exactly(repo):
    # covers: DK-300b-2-i
    # angle: criterion
    build(repo)
    result = recognize(repo, "pkg/alpha.py::run pkg.beta.run bare")
    assert set(cards(result, "symbol")) == {"pkg.alpha.run", "pkg.beta.run", "pkg.alpha.bare"}
    assert all(c.resolution == "resolved" for c in result.entities)
    write(repo, "pkg/aaaa.py", "def run():\n    return 'unrelated'\n")
    build(repo)
    again = recognize(repo, "pkg/alpha.py::run pkg.beta.run bare")
    assert set(cards(again, "symbol")) == set(cards(result, "symbol"))


def test_candidate_priority_and_work_caps_do_not_scale_with_prose(repo):
    # covers: DK-300b-3
    # angle: criterion
    build(repo)
    goal = "Zephyr " * 100 + " ".join(f"EC-{2000+i}a-1" for i in range(100)) + " pkg.alpha.run"
    small = recognize(repo, goal, config=config_for(max_lookups=1))
    assert small.budgets.lookups == 1
    assert small.coverage.scan_complete and small.coverage.counts.omitted > 0
    assert small.unresolved[0].reference == "EC-2000a-1"  # explicit ID precedes earlier phrase
    result = recognize(repo, goal)
    assert result.budgets.lookups <= 64
    repeated = recognize(repo, "ordinary " * 600 + "Zephyr " * 100)
    single = recognize(repo, "Zephyr")
    assert repeated.budgets.lookups == single.budgets.lookups == 1


def test_caller_recognition_budget_prefers_newest_after_entire_goal(repo):
    # covers: DK-300b-3
    # angle: criterion
    build(repo)
    caller = CallerContext(conversation=["x" * 4000, "x" * 4000, "x" * 4000, "Zephyr"],
                           observations=["Hostile " + "z" * 3900])
    result = recognize(repo, AC_ID, context=caller)
    assert AC_ID in cards(result) and "zephyr" in cards(result)
    retained = result.caller_context
    assert sum(len(s) for s in [*retained.conversation, *retained.observations, *retained.capabilities]) <= 12000
    match = cards(result)["zephyr"].matches[0]
    assert match.channel == "conversation" and match.record_index == 3
    assert result.original_goal == AC_ID and caller.conversation[0] == "x" * 4000
    assert result.limitations


def test_cards_unknowns_and_meanings_obey_shared_projection_limits(repo):
    # covers: DK-300b-3
    # angle: criterion
    source = "# Glossary\n\n" + "\n".join(f"### Term{i}\n\nShort sentence. " + "Long tail " * 100 for i in range(25))
    write(repo, "docs/glossary.md", source)
    for index in range(5):
        write(repo, f"pkg/extra{index}.py", "def run():\n    return None\n")
    build(repo)
    goal = " ".join(f"Term{i}" for i in range(25)) + " run " + " ".join(f"EC-{4000+i}a-1" for i in range(15))
    result = recognize(repo, goal)
    alternatives = {candidate for u in result.unresolved for candidate in u.candidates}
    assert len(result.entities) + len(alternatives - set(cards(result))) <= 16
    assert len(result.unresolved) <= 8
    assert all(len(u.reference) <= 128 and len(u.candidates) <= 3 for u in result.unresolved)
    assert all(len(c.meaning) <= 300 for c in result.entities)
    assert all(c.meaning == "Short sentence." for c in result.entities if c.family == "glossary")
    assert result.coverage.counts.omitted > 0 and result.coverage.scan_complete
    assert compact_size(payload(result)) <= 8000


def test_compact_entity_serialization_bounds_all_metadata_without_losing_repeats(repo):
    # covers: DK-300b-3
    # angle: criterion
    build(repo)
    result = recognize(repo, " ".join(["Zephyr"] * 100))
    exported = payload(result)
    assert compact_size(exported) <= 8000
    assert result.budgets.serialized_chars == compact_size(exported)
    assert len(cards(result)["zephyr"].matches) == 100
    row = next(c for c in exported["entities"] if c["identity"] == "zephyr")
    assert len(row["matches"]) == 1 and row["occurrence_count"] == 100
    assert "original_goal" not in exported and "caller_context" not in exported


def test_expired_deadline_stops_new_lookups_and_marks_incomplete_scan(repo):
    # covers: DK-300b-3-i
    # angle: failure
    build(repo)
    goal = long_goal()
    run = api("kernel.entity_context", "recognize_entities")
    with patch("time.monotonic", side_effect=itertools.chain([0.0], itertools.repeat(3.0))):
        result = run(task_for(repo, goal), config_for())
    assert result.status == "partial" and not result.coverage.scan_complete
    assert result.budgets.lookups == 0 and result.original_goal == goal
    assert any("deadline" in note.lower() or "time" in note.lower() for note in result.limitations)
