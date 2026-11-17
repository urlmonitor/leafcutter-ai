"""Evaluator-discovered cases: configured sources must not disappear from freshness or ownership."""

import json
import re
from pathlib import Path
import pytest
import yaml

from kernel.entity_context import recognize_entities
from kernel.contracts import CallerContext
from kernel.observability.redaction import Redactor
from tests.kernel.entity_context.support import build, config_for, task_for, write, write_repo


def test_new_previously_absent_configured_root_invalidates_snapshot(tmp_path):
    # covers: DK-300c-1
    write_repo(tmp_path)
    config = config_for()
    source = config.sources[0].model_copy(update={"roots": [*config.sources[0].roots, "newpkg"]})
    config = config.model_copy(update={"sources": [source]})
    build(tmp_path, config)
    (tmp_path / "newpkg").mkdir()
    (tmp_path / "newpkg/added.py").write_text("def newDecl():\n    pass\n", encoding="utf-8")
    task = task_for(tmp_path, "newpkg/added.py::newDecl")
    stale = recognize_entities(task, config)
    assert stale.coverage.index_status == "stale", "a newly present configured source must invalidate the prior index"
    assert not stale.entities
    build(tmp_path, config)
    fresh = recognize_entities(task, config)
    assert [card.identity for card in fresh.entities] == ["newpkg.added.newDecl"]


def test_permitted_glossary_uses_configured_owner_path_outside_docs(tmp_path):
    # covers: DK-300a-1
    write_repo(tmp_path)
    paths = json.loads((tmp_path / "config/paths.json").read_text(encoding="utf-8"))
    paths["surfaces"]["glossary"]["path"] = "custom/glossary.md"
    (tmp_path / "config/paths.json").write_text(json.dumps(paths), encoding="utf-8")
    (tmp_path / "custom").mkdir()
    (tmp_path / "custom/glossary.md").write_text(
        "# Glossary\n\n### CustomOwner\n\nA custom owner path.\n", encoding="utf-8")
    config = config_for()
    source = config.sources[0].model_copy(update={"roots": [*config.sources[0].roots, "custom"]})
    config = config.model_copy(update={"sources": [source]})
    build(tmp_path, config)
    result = recognize_entities(task_for(tmp_path, "CustomOwner"), config)
    assert [(card.family, card.identity, card.meaning) for card in result.entities] == [
        ("glossary", "customowner", "A custom owner path.")]
    assert result.entities[0].provenance.locator == "custom/glossary.md#term=customowner"


@pytest.mark.parametrize("reference,expected", [
    ("EC-1100a-1-i-ii", "unknown_id"),
    ("EC-1100a-1-i--1", "invalid_reference"),
    ("ADR-987-invalid", "invalid_reference"),
])
def test_explicit_reference_never_resolves_existing_artifact_prefix(tmp_path, reference, expected):
    # covers: DK-300a-3-i
    write_repo(tmp_path)
    if reference.startswith("EC-"):
        schema = json.loads((tmp_path / "config/ac_store_schema.json").read_text(encoding="utf-8"))
        valid = re.fullmatch(schema["properties"]["id"]["pattern"], reference) is not None
        assert valid == (expected == "unknown_id")
    config = config_for()
    build(tmp_path, config)
    result = recognize_entities(task_for(tmp_path, "Explain " + reference), config)
    assert not result.entities, "an existing ID prefix is not the explicitly referenced identity"
    assert [(u.reference, u.state) for u in result.unresolved] == [(reference, expected)]
    assert result.budgets.lookups == 1


def test_redaction_cannot_expand_admitted_raw_caller_window(tmp_path):
    # covers: DK-300b-3
    # covers: DK-300c-3
    write_repo(tmp_path)
    config = config_for()
    build(tmp_path, config)
    secret = "x" * 99 + "!"
    newest = secret * 40
    assert len(newest) == 4000
    caller = CallerContext(conversation=["Zephyr", newest, newest, newest])
    redactor = Redactor({"fixture": secret}, config.data_policy, [])
    result = recognize_entities(task_for(tmp_path, "ordinary prose", context=caller), config, redactor=redactor)
    assert not any(card.identity == "zephyr" for card in result.entities), "redaction must not admit an older record outside the 12000 raw-character recognition window"
    assert secret not in result.model_dump_json()


def test_denied_parse_error_cannot_change_disclosed_family_coverage(tmp_path):
    # covers: DK-300c-2
    write_repo(tmp_path)
    broad = config_for()
    narrow = broad.model_copy(update={"sources": [
        broad.sources[0].model_copy(update={"deny_globs": ["**/secret.py"]})]})
    task = task_for(tmp_path, "pkg/alpha.py::run")
    build(tmp_path, broad)
    before = recognize_entities(task, narrow)
    (tmp_path / "pkg/secret.py").write_text("def invalid(:\n", encoding="utf-8")
    build(tmp_path, broad)
    after = recognize_entities(task, narrow)
    assert after.coverage == before.coverage, "denied parse state must not influence disclosed family coverage"
    assert after.status == before.status
    assert after.limitations == before.limitations


def test_denied_native_validation_error_cannot_change_narrow_owner_projection(tmp_path):
    # covers: DK-300c-2
    write_repo(tmp_path)
    record = yaml.safe_load((tmp_path / "docs/acceptance-criteria/EC-1100a-1-i.yaml").read_text(encoding="utf-8"))
    record.update(id="EC-1100a-2", title="Denied authored criterion")
    denied_path = "docs/acceptance-criteria/EC-1100a-2.yaml"
    write(tmp_path, denied_path, record)
    broad = config_for()
    narrow = broad.model_copy(update={"sources": [
        broad.sources[0].model_copy(update={"deny_globs": [denied_path]})]})
    task = task_for(tmp_path, "EC-1100a-1-i Zephyr")
    build(tmp_path, broad)
    before = recognize_entities(task, narrow)
    (tmp_path / denied_path).write_text("id: [invalid YAML\n", encoding="utf-8")
    build(tmp_path, broad)
    after = recognize_entities(task, narrow)
    assert after.entities == before.entities
    assert after.coverage == before.coverage, "hidden native validation state must not change narrow coverage"
    assert after.status == before.status
    assert after.limitations == before.limitations
    permitted_failure = recognize_entities(task, broad)
    assert permitted_failure.status == "partial"
    assert permitted_failure.limitations, "a fully permitted invalid store must remain explicitly incomplete"


@pytest.mark.parametrize("goal,reference,expected", [
    ("Explain flow: eval/absent", "eval/absent", "unknown_id"),
    ("Explain flow: eval/Bad_Name", "eval/Bad_Name", "invalid_reference"),
    ("Explain ticket: tickets/TICKET-NONEXISTENT.md", "tickets/TICKET-NONEXISTENT.md", "unknown_id"),
])
def test_typed_absent_flow_and_ticket_follow_their_owners(tmp_path, goal, reference, expected):
    # covers: DK-300a-3-i
    write_repo(tmp_path)
    from knowledge.native_types.flow import _identity as flow_identity
    from knowledge.native_types.ticket import _admitted as ticket_admitted
    if goal.startswith("Explain flow:"):
        if expected == "invalid_reference":
            with pytest.raises(ValueError):
                flow_identity(reference)
        else:
            assert flow_identity(reference) == reference
    else:
        assert ticket_admitted(Path(reference), {"title": "Synthetic prospective ticket"}, True)
    config = config_for()
    build(tmp_path, config)
    result = recognize_entities(task_for(tmp_path, goal), config)
    assert not result.entities
    assert [(u.reference, u.state) for u in result.unresolved] == [(reference, expected)]
    assert result.budgets.lookups == 1
