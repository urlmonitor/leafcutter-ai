"""Glossary source fidelity, discovery boundaries, and identity behavior.

BUSINESS CONTEXT: KM-400a-3-i exposes the authored fields of native terms.
ARCHITECTURE: Unit and real-artifact checks exercise the snapshot-local reader.
"""

from datetime import date
from importlib import import_module
import json
from pathlib import Path
import sys
from urllib.parse import quote

import pytest
import yaml


def _extract(root):
    return import_module("knowledge.native_types.glossary_term").extract(root)


def _write(root, body, metadata=None, name="docs/glossary.md", newline="\n"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    front = "" if metadata is None else "---\n" + yaml.safe_dump(metadata) + "---\n"
    path.write_bytes((front + body).replace("\n", newline).encode("utf-8"))
    return path


def _config(root, value):
    path = root / "config/paths.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_native_glossary_preserves_fields_and_exact_markdown(tmp_path):
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: unit
    # angle: criterion
    metadata = {
        "title": "Whole glossary",
        "status": "active",
        "components": ["finalize"],
        "created": date(2026, 10, 2),
        "quoted_date": "2026-10-02",
        "extension": {"null": None, "empty": [], "map": {}, "flag": False},
    }
    definition = "\n First line with two spaces.  \n\n[link](target.md)\n\n#### Detail\n|a|b|\n|---|---|\n|1|2|\n\n"
    path = _write(
        tmp_path, "# Glossary\n\n###  Mixed Term / A  \n" + definition, metadata, newline="\r\n"
    )
    before = path.read_bytes()
    (record,) = _extract(tmp_path)
    assert record.metadata == {
        "term": "Mixed Term / A",
        "definition": definition.replace("\n", "\r\n"),
    }
    assert record.derived == {"file_frontmatter": metadata}
    assert record.kind == "GlossaryTerm"
    assert record.title == "Mixed Term / A"
    assert record.description == ""
    assert record.native_id == "mixed term / a"
    assert record.locator == "#term=mixed%20term%20%2F%20a"
    assert record.source_path == "docs/glossary.md"
    assert path.read_bytes() == before


def test_native_glossary_ignores_comments_and_fences_without_truncation(tmp_path):
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    prefix = "<!--\n### Comment example\n-->\n```md\n### Fenced introduction\n```\n"
    definition = """\nDefinition before examples.
<!--
### False comment term
## False boundary
```
-->
<!-- same-line ### False term -->
````markdown
### False backtick term
```
## Still inside the longer fence
```` trailing content is not a closing fence
### Still fenced
````
   ~~~~markdown
### False tilde term
````
~~~
## Still inside the tilde fence
~~~~
    ### Indented example
 ### One-space example
> ### Quoted example
#### Nested content
Real final paragraph.
"""
    _write(tmp_path, prefix + "### Real\n" + definition + "### Next\nNext definition.\n")
    records = _extract(tmp_path)
    assert [record.native_id for record in records] == ["real", "next"]
    assert records[0].metadata["definition"] == definition
    assert records[1].metadata["definition"] == "Next definition.\n"


def test_native_glossary_fence_info_does_not_open_html_comment(tmp_path):
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    definition = "```<!--example\n### Fake\n<!-- also fenced\n```\nAfter the fence.\n"
    _write(tmp_path, "### First\n" + definition + "### Second\nVisible.\n")
    records = _extract(tmp_path)
    assert [record.native_id for record in records] == ["first", "second"]
    assert records[0].metadata["definition"] == definition


def test_native_glossary_true_section_boundaries_and_empty_definition(tmp_path):
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    _write(
        tmp_path,
        "### A\nA text.\n#### Nested\nNested text.\n## Group\nGroup intro.\n### Empty\n### C\nC text.\n# Appendix\nNot a term definition.\n",
    )
    records = _extract(tmp_path)
    assert [record.metadata for record in records] == [
        {"term": "A", "definition": "A text.\n#### Nested\nNested text.\n"},
        {"term": "Empty", "definition": ""},
        {"term": "C", "definition": "C text.\n"},
    ]


def test_native_glossary_identities_survive_insertion_and_reordering(tmp_path):
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    terms = ["create-ticket.js", "ticket creation pipeline", "A/B", "A B", "A%2FB"]
    _write(tmp_path, "".join(f"### {term}\nDefinition of {term}.\n" for term in terms))
    before = {record.title: (record.native_id, record.locator) for record in _extract(tmp_path)}
    _write(
        tmp_path,
        "### Added\nNew.\n"
        + "".join(f"### {term}\nDefinition of {term}.\n" for term in reversed(terms)),
    )
    records = _extract(tmp_path)
    after = {record.title: (record.native_id, record.locator) for record in records}
    assert len(records) == len(terms) + 1
    assert len(set(record.locator for record in records)) == len(records)
    assert all(after[term] == before[term] for term in terms)
    assert before["A/B"] == ("a/b", "#term=a%2Fb")


@pytest.mark.parametrize("second", ["Name", "nAmE", "  NAME  "])
def test_native_glossary_duplicate_normalized_terms_fail(tmp_path, second):
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _write(tmp_path, f"### Name\nFirst.\n### {second}\nSecond.\n")
    with pytest.raises(ValueError, match="duplicate.*term"):
        _extract(tmp_path)


def test_native_glossary_custom_path_and_absent_surface_default(tmp_path):
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: unit
    # angle: seam
    _write(tmp_path, "### Default\nDefault definition.\n")
    _config(tmp_path, {"surfaces": {"docs": {"path": "docs/"}}})
    assert [record.native_id for record in _extract(tmp_path)] == ["default"]
    _write(tmp_path, "### Custom\nCustom definition.\n", name="reference/terms.md")
    _config(tmp_path, {"surfaces": {"glossary": {"path": "reference/terms.md"}}})
    (record,) = _extract(tmp_path)
    assert record.native_id == "custom"
    assert record.source_path == "reference/terms.md"


@pytest.mark.parametrize(
    "value",
    [
        [],
        {"surfaces": []},
        {"surfaces": {"glossary": None}},
        {"surfaces": {"glossary": {}}},
        {"surfaces": {"glossary": {"path": ""}}},
        {"surfaces": {"glossary": {"path": "../outside.md"}}},
        {"surfaces": {"glossary": {"path": "C:/outside.md"}}},
        {"surfaces": {"glossary": {"path": 42}}},
    ],
)
def test_native_glossary_invalid_configuration_fails(tmp_path, value):
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _config(tmp_path, value)
    with pytest.raises(ValueError):
        _extract(tmp_path)


def test_native_glossary_symlink_outside_snapshot_fails(tmp_path):
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    source = tmp_path / "snapshot"
    source.mkdir()
    target = _write(tmp_path, "### External\nNot owned.\n", name="external/glossary.md")
    before = target.read_bytes()
    link = source / "docs/glossary.md"
    link.parent.mkdir()
    junction_created = False
    try:
        link.symlink_to(target)
    except OSError as error:
        if sys.platform != "win32" or error.winerror != 1314:
            raise
        # A real directory junction needs no Windows symlink privilege.
        # This is the same filesystem fallback used by BP-900h-6 tests.
        import _winapi

        link.parent.rmdir()
        _winapi.CreateJunction(str(target.parent), str(link.parent))
        junction_created = True
    try:
        assert link.resolve() == target.resolve()
        assert not link.resolve().is_relative_to(source.resolve())
        assert link.read_bytes() == before
        with pytest.raises(ValueError, match=r"not in (the )?subpath"):
            _extract(source)
        assert target.read_bytes() == before
    finally:
        if junction_created:
            # Remove only the owned junction, never its external target.
            link.parent.rmdir()


@pytest.mark.parametrize(
    "text", ["---\ntitle: unfinished\n", "---\n- not\n- mapping\n---\n", "---\nbroken: [\n---\n"]
)
def test_native_glossary_malformed_frontmatter_fails(tmp_path, text):
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: unit
    # angle: failure
    _write(tmp_path, text)
    with pytest.raises(ValueError):
        _extract(tmp_path)


def test_native_glossary_missing_and_empty_store_emit_no_placeholder(tmp_path):
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: unit
    # angle: boundary
    assert _extract(tmp_path) == []
    _write(tmp_path, "# Glossary\nIntroduction.\n### \nNo named term.\n")
    assert _extract(tmp_path) == []
    _write(tmp_path, "### First\nOne.\n")
    assert len(_extract(tmp_path)) == 1
    _write(tmp_path, "### First\nOne.\n### Second\nTwo.\n")
    assert len(_extract(tmp_path)) == 2


def test_native_glossary_real_corpus_matches_all_authored_sections():
    # covers: KM-400a-1-ix
    # covers: KM-400a-3-i
    # type: integration
    # angle: real_artifact
    root = Path(__file__).resolve().parents[2]
    from knowledge.native_types.common import frontmatter

    metadata, body = frontmatter(root / "docs/glossary.md")
    records = _extract(root)
    # Reviewed current corpus: 41 original sections plus ten authored kernel terms.
    assert len(records) == 51
    assert "candle_horizon" not in {record.native_id for record in records}
    assert {
        "create-ticket.js",
        "ticket creation pipeline",
        "negative_control_result",
        "decision kernel",
        "jev",
        "needs_context",
        "out_of_domain",
    } <= {record.native_id for record in records}
    lines = body.splitlines(keepends=True)
    # The reviewed real file has simple top-level sections, independently slice all.
    starts = [i for i, line in enumerate(lines) if line.startswith("### ")]
    assert len(starts) == len(records)
    for index, (start, record) in enumerate(zip(starts, records)):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        term = lines[start][4:].strip()
        assert record.metadata == {"term": term, "definition": "".join(lines[start + 1 : end])}
        assert record.derived == {"file_frontmatter": metadata}
        assert record.native_id == term.lower()
        assert record.locator == "#term=" + quote(term.lower(), safe="")
