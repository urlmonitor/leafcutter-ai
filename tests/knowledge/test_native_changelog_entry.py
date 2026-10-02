"""Changelog metadata keeps historical source values and auditable writer recovery."""

from datetime import date
from importlib import import_module
import json
from pathlib import Path

import pytest
import yaml


def _extract(root):
    return import_module("knowledge.native_types.changelog_entry").extract(root)


def _write(root, name, raw, body="\n## Entry\n"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + raw + "---\n" + body, encoding="utf-8")
    return path


def test_changelog_preserves_every_field_body_and_authored_types(tmp_path):
    # covers: KM-400a-1-xiii
    # covers: KM-400a-3-i
    # angle: criterion
    metadata = {
        "title": "Complete entry",
        "date": date(2026, 8, 1),
        "time": 735,
        "type": "ticket_completion",
        "components": ["finalize", "finalize"],
        "summary": "Business summary",
        "description": "Technical description",
        "epic": "Epic one",
        "ticket": "Single ticket",
        "pr": None,
        "adrs": [],
        "diagrams": ["docs/diagram.md"],
        "tickets": ["Other ticket"],
        "commits": [123456, "123456", "abcdef"],
        "breaking": False,
        "migration_steps": [{"Before status": "done"}, "Then verify"],
        "scope": "source scope",
        "merge_commit": "fedcba",
        "acs": ["FIN-100"],
        "created": "2026-08-01",
        "last_updated": "2026-08-02",
        "status": "active",
        "extension": {"empty": {}, "null": None, "false": False, "zero": 0},
        "current": "authored-current",
        "payload": {"keep": True},
    }
    raw = yaml.safe_dump(metadata, sort_keys=False)
    body = "\n## Entry\n\nAn authored table.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    _write(tmp_path, "changelogs/entry.md", raw, body)
    (record,) = _extract(tmp_path)
    assert record.kind == "ChangelogEntry"
    assert record.native_id == record.source_path == "changelogs/entry.md"
    assert record.locator == ""
    assert record.metadata == metadata
    assert type(record.metadata["date"]) is date
    assert type(record.metadata["time"]) is int
    assert record.title == metadata["title"]
    assert record.description == metadata["description"]
    assert record.derived == {"body": body, "frontmatter_raw": raw, "parsing": {"mode": "strict"}}
    from knowledge.native_properties import decode, encode

    assert decode(encode(record.metadata)) == metadata


def test_changelog_legacy_identity_absence_and_presentation_fallbacks(tmp_path):
    # covers: KM-400a-1-xiii
    # covers: KM-400a-3-i
    # angle: boundary
    raw = "type: fix\nsummary: Historical summary\npr: null\ncommits: []\n"
    _write(tmp_path, "changelogs/same.md", raw)
    _write(tmp_path, "docs/changelog/same.md", "type: ac_authoring\n")
    records = {r.native_id: r for r in _extract(tmp_path)}
    assert set(records) == {"changelogs/same.md", "docs/changelog/same.md"}
    current = records["changelogs/same.md"]
    assert current.title == "same"
    assert current.description == "Historical summary"
    assert current.metadata == {
        "type": "fix",
        "summary": "Historical summary",
        "pr": None,
        "commits": [],
    }
    assert records["docs/changelog/same.md"].metadata == {"type": "ac_authoring"}


@pytest.mark.parametrize("config_prefix", ["", "leafcutter/"])
def test_changelog_configured_store_and_guidance_exclusions(tmp_path, config_prefix):
    # covers: KM-400a-1-xiii
    # covers: KM-400a-3-i
    # angle: seam
    config = tmp_path / (config_prefix + "templates/scripts/commit_guardian/commit_guardian.json")
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"changelogs_dir": "history"}), encoding="utf-8")
    for name in [
        "history/README.md",
        "history/index.md",
        "history/nested/generated.md",
        "changelogs/stale.md",
        "CHANGELOG.md",
    ]:
        _write(tmp_path, name, "title: Excluded\n")
    _write(tmp_path, "history/old-filename.md", "title: Included\n")
    _write(tmp_path, "docs/changelog/legacy.md", "title: Legacy\n")
    assert [r.source_path for r in _extract(tmp_path)] == [
        "docs/changelog/legacy.md",
        "history/old-filename.md",
    ]


def test_changelog_absent_stores_and_overlapping_configuration(tmp_path):
    # covers: KM-400a-1-xiii
    # covers: KM-400a-3-i
    # angle: boundary
    assert _extract(tmp_path) == []
    config = tmp_path / "templates/scripts/commit_guardian/commit_guardian.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"changelogs_dir":"docs/changelog"}', encoding="utf-8")
    _write(tmp_path, "docs/changelog/one.md", "title: One\n")
    assert len(_extract(tmp_path)) == 1


@pytest.mark.parametrize("setting", ["../outside", None, 12, ""])
def test_changelog_rejects_unsafe_or_invalid_store(tmp_path, setting):
    # covers: KM-400a-1-xiii
    # covers: KM-400a-3-i
    # angle: failure
    config = tmp_path / "templates/scripts/commit_guardian/commit_guardian.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"changelogs_dir": setting}), encoding="utf-8")
    with pytest.raises(ValueError):
        _extract(tmp_path)


def test_changelog_recovers_only_failing_literal_description(tmp_path):
    # covers: KM-400a-1-xiii
    # covers: KM-400a-3-i
    # angle: boundary
    description = r'Regex \.yaml and C:\new\test, with "quotes" and \\tail'
    fragment = 'description: "' + description.replace('"', '\\"') + '"\n'
    raw = "title: Recovered\ntime: 12:15\npr: null\n" + fragment + "commits: [123456, abcdef]\n"
    _write(tmp_path, "changelogs/escaped.md", raw)
    (record,) = _extract(tmp_path)
    assert record.metadata == {
        "title": "Recovered",
        "time": 735,
        "pr": None,
        "description": description,
        "commits": [123456, "abcdef"],
    }
    assert record.derived["frontmatter_raw"] == raw
    parsing = record.derived["parsing"]
    assert parsing["mode"] == "compatibility"
    assert parsing["field"] == "description"
    assert parsing["rule"] == "emitter_literal_description"
    assert parsing["raw_fragment"] == fragment
    assert "unknown escape character" in parsing["original_error"]


def test_changelog_recovers_failing_literal_list_but_retains_valid_maps(tmp_path):
    # covers: KM-400a-1-xiii
    # covers: KM-400a-3-i
    # angle: boundary
    items = [
        "Run the build.",
        "Set `output_root: .leafcutter` and `shim_strategy: symlink`.",
        "Then verify.",
    ]
    fragment = "migration_steps: \n" + "".join("  - " + item + "\n" for item in items)
    _write(
        tmp_path,
        "changelogs/broken-list.md",
        "title: Recovered\nbreaking: false\n" + fragment + "pr: null\n",
    )
    _write(
        tmp_path,
        "changelogs/valid-map.md",
        "title: Map\nmigration_steps:\n  - Before status: done\n",
    )
    records = {r.title: r for r in _extract(tmp_path)}
    recovered = records["Recovered"]
    assert recovered.metadata == {
        "title": "Recovered",
        "breaking": False,
        "migration_steps": items,
        "pr": None,
    }
    assert recovered.derived["parsing"]["raw_fragment"] == fragment
    assert recovered.derived["parsing"]["rule"] == "emitter_literal_migration_list"
    assert recovered.derived["parsing"]["field"] == "migration_steps"
    assert "mapping values are not allowed here" in recovered.derived["parsing"]["original_error"]
    assert records["Map"].metadata["migration_steps"] == [{"Before status": "done"}]
    assert records["Map"].derived["parsing"] == {"mode": "strict"}


def test_changelog_recovery_payload_is_independent_of_checkout_path(tmp_path):
    # covers: KM-400a-1-xiii
    # covers: KM-400a-3-i
    # angle: seam
    raw = 'title: Stable\ndescription: "literal\\.expression"\n'
    _write(tmp_path / "checkout-one", "changelogs/stable.md", raw)
    _write(tmp_path / "checkout-two", "changelogs/stable.md", raw)
    assert _extract(tmp_path / "checkout-one") == _extract(tmp_path / "checkout-two")


@pytest.mark.parametrize(
    "raw",
    [
        'title: "bad\\.escape"\n',
        'description: "unclosed\\.escape\n',
        'description: "first\\.bad"\ndescription: "second\\.bad"\n',
        "migration_steps:\n  - Set x: one and y: two\n    continuation\n",
        "migration_steps:\n  - Set x: one and y: two\n  - |\n",
        'description: "recoverable\\.escape"\nother: [broken\n',
        "- not a mapping\n",
    ],
)
def test_changelog_rejects_ambiguous_or_unrelated_malformations(tmp_path, raw):
    # covers: KM-400a-1-xiii
    # covers: KM-400a-3-i
    # angle: failure
    _write(tmp_path, "changelogs/ambiguous.md", raw)
    with pytest.raises(ValueError, match="ambiguous.md"):
        _extract(tmp_path)


def test_changelog_real_corpus_accounts_for_all_fields_and_three_recoveries():
    # covers: KM-400a-1-xiii
    # covers: KM-400a-3-i
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    records = _extract(root)
    paths = {
        path.relative_to(root).as_posix()
        for folder in ("changelogs", "docs/changelog")
        for path in (root / folder).glob("*.md")
        if path.name.lower() not in {"readme.md", "index.md"}
    }
    assert len(records) == len(paths) == 550
    assert {record.source_path for record in records} == paths
    assert len({r.native_id for r in records}) == 550
    recovered = []
    for record in records:
        raw = record.derived["frontmatter_raw"]
        if record.derived["parsing"]["mode"] == "strict":
            assert record.metadata == yaml.safe_load(raw)
        else:
            recovered.append(record)
        from knowledge.native_properties import decode, encode

        assert decode(encode(record.metadata)) == record.metadata
    assert len(recovered) == 3
    assert sorted(r.derived["parsing"]["rule"] for r in recovered) == [
        "emitter_literal_description",
        "emitter_literal_description",
        "emitter_literal_migration_list",
    ]
    migration = next(r for r in recovered if r.derived["parsing"]["field"] == "migration_steps")
    assert len(migration.metadata["migration_steps"]) == 5
    assert (
        "`output_root: .leafcutter` and `shim_strategy: symlink`"
        in migration.metadata["migration_steps"][1]
    )


# DECISION HISTORY
# ========================================
# - 2026-10-02 17:00 [test-writer]: Account for the two incoming main changelogs with the exact independent source census. (#TICKETLESS reason=main-integration-oracle-refresh)
