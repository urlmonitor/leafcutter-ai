"""
MODULE: test_km_kgs_100a_3_x
GOAL: TDD stubs for KM-KGS-100a-3-x — continuation lines and trailing
      comments inside a block list neither end the list nor leak into item
      values.
BUSINESS CONTEXT: Measured evidence (2026-09-16) found two divergences from
    PyYAML in scripts/knowledge_query.py's stdlib-only reader. (A) A
    REGRESSION introduced by the in-progress fix for KM-KGS-100a-3-i..-ix: an
    indented line inside a block list that is not itself a list item (a
    wrapped continuation of a plain scalar item, or a mapping item's own
    indented field) ends the list outright, silently dropping every item
    that follows — including on the real store's
    docs/acceptance-criteria/index.yaml, whose `components` list is
    truncated from many real entries to one malformed string. (B) A
    PRE-EXISTING gap, present on main as well: a trailing inline `# comment`
    on a plain (unquoted) list item is kept in the value instead of being
    stripped. Every Then here is proven by reading a real temp file through
    the production file-reading entry point — `_parse_yaml_file` for `.yaml`
    files and `_parse_frontmatter` for `.md` frontmatter — never a hand-built
    dictionary, with PyYAML's `safe_load` used test-side only as the
    reference oracle. Per the it_requirements EXPLICIT NON-GOAL, the mapping
    item's own produced value (record 2's first covered_by item) is never
    asserted — only that it does not truncate the list and does not absorb
    the next top-level key's items.
"""

import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_INDEX_YAML = _REPO_ROOT / "docs" / "acceptance-criteria" / "index.yaml"
sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import _parse_frontmatter, _parse_yaml_file  # noqa: E402


def _read_yaml_fields(tmp_path, filename, content):
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return _parse_yaml_file(p.read_text(encoding="utf-8"))


def _read_md_fields(tmp_path, filename, content):
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return _parse_frontmatter(p.read_text(encoding="utf-8"))


# Record 1 — first plain item of covered_by wraps onto an indented
# continuation line; a second item and the next top-level key follow.
_RECORD_1_FIXTURE = (
    "id: KM-EX-RECORD-1\n"
    "covered_by:\n"
    "  - unit_tests/very/long/path/\n"
    "    that/continues/here.py\n"
    "  - unit_tests/second.py\n"
    "implemented_by:\n"
    "  - scripts/example_module.py\n"
)

# Record 2 — first covered_by item is a mapping ("- path: ..." followed by
# an indented "relationship: covers" continuation), then a plain item, then
# the next top-level key.
_RECORD_2_FIXTURE = (
    "id: KM-EX-RECORD-2\n"
    "covered_by:\n"
    "  - path: unit_tests/test_alpha.py\n"
    "    relationship: covers\n"
    "  - unit_tests/test_beta.py\n"
    "implemented_by:\n"
    "  - scripts/example_module.py\n"
)

# Record 3 — plain and quoted items carrying hash characters, then the next
# top-level key.
_RECORD_3_FIXTURE = (
    "id: KM-EX-RECORD-3\n"
    "covered_by:\n"
    "  - unit_tests/test_gamma.py  # note\n"
    "  - unit_tests/test_delta.py#test_symbol\n"
    '  - "unit_tests/test_epsilon.py #kept"\n'
    "implemented_by:\n"
    "  - scripts/example_module.py\n"
)

# Record 4 — record 1's covered_by list restated with dash items at column
# zero and the continuation line indented two spaces.
_RECORD_4_FIXTURE = (
    "id: KM-EX-RECORD-4\n"
    "covered_by:\n"
    "- unit_tests/very/long/path/\n"
    "  that/continues/here.py\n"
    "- unit_tests/second.py\n"
    "implemented_by:\n"
    "  - scripts/example_module.py\n"
)

# A minimal record isolating the trailing-tab-comment rule: a tab character
# (not a space) precedes the "#" on an otherwise plain item.
_TAB_COMMENT_FIXTURE = (
    "id: KM-EX-TABCOMMENT\n"
    "covered_by:\n"
    "  - unit_tests/test_gamma.py\t# note\n"
    "implemented_by:\n"
    "  - scripts/example_module.py\n"
)

# .md frontmatter carrying record 1's wrapped-continuation shape.
_MD_RECORD_1_FIXTURE = (
    "---\n"
    "id: KM-EX-MD-RECORD-1\n"
    "covered_by:\n"
    "  - unit_tests/very/long/path/\n"
    "    that/continues/here.py\n"
    "  - unit_tests/second.py\n"
    "implemented_by:\n"
    "  - scripts/example_module.py\n"
    "---\n"
    "\n"
    "# Ticket body placeholder\n"
)

# .md frontmatter carrying record 3's trailing-comment/hash shape.
_MD_RECORD_3_FIXTURE = (
    "---\n"
    "id: KM-EX-MD-RECORD-3\n"
    "covered_by:\n"
    "  - unit_tests/test_gamma.py  # note\n"
    "  - unit_tests/test_delta.py#test_symbol\n"
    '  - "unit_tests/test_epsilon.py #kept"\n'
    "implemented_by:\n"
    "  - scripts/example_module.py\n"
    "---\n"
    "\n"
    "# Ticket body placeholder\n"
)

# PyYAML reference values for the fixtures above, obtained once as module
# constants so every test compares read-path against the same oracle bytes
# rather than re-deriving expectations inline.
_RECORD_1_REFERENCE = yaml.safe_load(_RECORD_1_FIXTURE)
_RECORD_3_REFERENCE = yaml.safe_load(_RECORD_3_FIXTURE)


def test_wrapped_plain_item_folds_continuation_with_single_space(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: criterion
    """Record 1's covered_by reads to exactly the PyYAML value: the wrapped
    continuation is joined to the preceding text with a single space and its
    own leading indentation removed."""
    fields = _read_yaml_fields(tmp_path, "record1.yaml", _RECORD_1_FIXTURE)
    assert fields.get("covered_by") == _RECORD_1_REFERENCE["covered_by"]
    assert fields.get("covered_by") == [
        "unit_tests/very/long/path/ that/continues/here.py",
        "unit_tests/second.py",
    ]


def test_items_after_wrapped_continuation_are_still_read(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: failure
    """Regression shape: unit_tests/second.py is present in record 1's
    covered_by value after the wrapped item, so the continuation line does
    not end the list (the in-progress reader returns only the first item's
    truncated fragment)."""
    fields = _read_yaml_fields(tmp_path, "record1.yaml", _RECORD_1_FIXTURE)
    value = fields.get("covered_by") or []
    assert "unit_tests/second.py" in value


def test_column_zero_dash_wrapped_item_matches_indented_form(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: criterion
    """Record 4 (same covered_by list, dash items at column zero, the
    continuation line indented two spaces) reads covered_by and
    implemented_by to the same values as record 1, compared read-path
    against read-path and against the expected literal lists."""
    fields_1 = _read_yaml_fields(tmp_path, "record1.yaml", _RECORD_1_FIXTURE)
    fields_4 = _read_yaml_fields(tmp_path, "record4.yaml", _RECORD_4_FIXTURE)
    assert fields_4.get("covered_by") == fields_1.get("covered_by")
    assert fields_4.get("implemented_by") == fields_1.get("implemented_by")
    assert fields_4.get("covered_by") == [
        "unit_tests/very/long/path/ that/continues/here.py",
        "unit_tests/second.py",
    ]
    assert fields_4.get("implemented_by") == ["scripts/example_module.py"]


def test_mapping_item_does_not_truncate_covered_by_list(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: criterion
    """Record 2's covered_by reads with 'unit_tests/test_beta.py' as its
    last item; neither the item count nor the value produced for the
    mapping item is asserted (stated non-goal)."""
    fields = _read_yaml_fields(tmp_path, "record2.yaml", _RECORD_2_FIXTURE)
    value = fields.get("covered_by") or []
    assert value[-1] == "unit_tests/test_beta.py"


def test_mapping_item_list_keeps_implemented_by_separate(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: boundary
    """Record 2's implemented_by reads to exactly
    ['scripts/example_module.py'] and no item of implemented_by appears in
    covered_by, so the mapping item's continuation never absorbs the next
    top-level key's items."""
    fields = _read_yaml_fields(tmp_path, "record2.yaml", _RECORD_2_FIXTURE)
    covered = fields.get("covered_by") or []
    implemented = fields.get("implemented_by") or []
    assert implemented == ["scripts/example_module.py"]
    assert not any(item in covered for item in implemented)


def test_list_still_ends_at_next_column_zero_key(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: boundary
    """For each of the four record files, no implemented_by item appears in
    the covered_by value and no string covered_by item appears in the
    implemented_by value, so continuation handling does not move the list
    end past the next column-zero key."""
    fixtures = {
        "record1.yaml": _RECORD_1_FIXTURE,
        "record2.yaml": _RECORD_2_FIXTURE,
        "record3.yaml": _RECORD_3_FIXTURE,
        "record4.yaml": _RECORD_4_FIXTURE,
    }
    for filename, content in fixtures.items():
        fields = _read_yaml_fields(tmp_path, filename, content)
        covered = fields.get("covered_by") or []
        implemented = fields.get("implemented_by") or []
        assert not any(item in covered for item in implemented), filename
        assert not any(
            isinstance(item, str) and item in implemented for item in covered
        ), filename


def test_trailing_space_comment_stripped_from_unquoted_item(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: criterion
    """In record 3's value, the unquoted item
    '- unit_tests/test_gamma.py  # note' reads to exactly
    'unit_tests/test_gamma.py'; no item contains the comment text 'note'
    and no item ends in whitespace."""
    fields = _read_yaml_fields(tmp_path, "record3.yaml", _RECORD_3_FIXTURE)
    value = fields.get("covered_by") or []
    assert "unit_tests/test_gamma.py" in value
    for item in value:
        assert "note" not in item
        assert item == item.rstrip()


def test_trailing_tab_comment_stripped_from_unquoted_item(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: boundary
    """A temp AC file whose covered_by item has a tab before '#' (allowed by
    the it_requirements trailing comment rule) reads covered_by to exactly
    ['unit_tests/test_gamma.py'].

    Note: PyYAML's own scanner rejects a raw tab character in this position
    (ScannerError: "found character '\\t' that cannot start any token"), so
    PyYAML cannot serve as the test-side oracle for this specific fixture —
    the expected value below is the literal value stated by the
    it_requirements trailing-comment rule (mirroring the space-comment case,
    which PyYAML does accept and which is asserted against PyYAML in
    test_trailing_space_comment_stripped_from_unquoted_item)."""
    fields = _read_yaml_fields(tmp_path, "tabcomment.yaml", _TAB_COMMENT_FIXTURE)
    assert fields.get("covered_by") == ["unit_tests/test_gamma.py"]


def test_hash_glued_to_token_is_not_a_comment(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: boundary
    """In record 3's value, 'unit_tests/test_delta.py#test_symbol' is
    present in full, not truncated at '#' (consistent with
    KM-KGS-100a-3-v)."""
    fields = _read_yaml_fields(tmp_path, "record3.yaml", _RECORD_3_FIXTURE)
    value = fields.get("covered_by") or []
    assert "unit_tests/test_delta.py#test_symbol" in value


def test_hash_inside_quoted_item_is_not_a_comment(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: boundary
    """In record 3's value, the double-quoted item reads to exactly
    'unit_tests/test_epsilon.py #kept', with the surrounding quotes stripped
    and the whitespace-preceded '#' kept (consistent with
    KM-KGS-100a-3-iii)."""
    fields = _read_yaml_fields(tmp_path, "record3.yaml", _RECORD_3_FIXTURE)
    value = fields.get("covered_by") or []
    assert "unit_tests/test_epsilon.py #kept" in value


def test_hash_record_reads_exact_lists(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: criterion
    """Record 3's file reads covered_by and implemented_by to exactly the
    PyYAML safe_load values of the same bytes."""
    fields = _read_yaml_fields(tmp_path, "record3.yaml", _RECORD_3_FIXTURE)
    assert fields.get("covered_by") == _RECORD_3_REFERENCE["covered_by"]
    assert fields.get("implemented_by") == _RECORD_3_REFERENCE["implemented_by"]
    assert fields.get("covered_by") == [
        "unit_tests/test_gamma.py",
        "unit_tests/test_delta.py#test_symbol",
        "unit_tests/test_epsilon.py #kept",
    ]
    assert fields.get("implemented_by") == ["scripts/example_module.py"]


def test_md_frontmatter_wrapped_continuation_does_not_truncate_list(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: criterion
    """A temp .md file whose frontmatter carries record 1's covered_by and
    implemented_by lists, read through the production .md frontmatter entry
    point, yields the full untruncated values."""
    fields = _read_md_fields(tmp_path, "record1.md", _MD_RECORD_1_FIXTURE)
    assert fields.get("covered_by") == [
        "unit_tests/very/long/path/ that/continues/here.py",
        "unit_tests/second.py",
    ]
    assert fields.get("implemented_by") == ["scripts/example_module.py"]


def test_md_frontmatter_trailing_comment_stripped(tmp_path):
    # covers: KM-KGS-100a-3-x
    # angle: boundary
    """A temp .md file whose frontmatter carries record 3's covered_by list,
    read through the production .md frontmatter entry point, yields the same
    three-item covered_by value as record 3's .yaml file."""
    fields = _read_md_fields(tmp_path, "record3.md", _MD_RECORD_3_FIXTURE)
    assert fields.get("covered_by") == [
        "unit_tests/test_gamma.py",
        "unit_tests/test_delta.py#test_symbol",
        "unit_tests/test_epsilon.py #kept",
    ]


def test_real_index_yaml_components_list_not_truncated():
    # covers: KM-KGS-100a-3-x
    # angle: real_artifact
    """Reading the real docs/acceptance-criteria/index.yaml through the
    production file-reading entry point yields a components value with at
    least as many items as there are top-level dash entries of the
    components list counted from the raw file text (independent of the
    production reader; the raw count must be greater than 1 so the check
    cannot pass vacuously). Only the count is asserted, never the item
    values, because the items are mappings (non-goal)."""
    # A missing file must fail, never skip: a skipped real-artifact check proves nothing.
    assert _INDEX_YAML.is_file(), f"AC store index not found at {_INDEX_YAML}"
    text = _INDEX_YAML.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Raw-text count, independent of _parse_yaml_file: find the top-level
    # "components:" key, then count immediately-following lines starting
    # with the list's own "  - " dash marker, stopping at the next
    # non-blank, non-comment, non-indented (i.e. column-zero) line.
    start = None
    for i, line in enumerate(lines):
        if line == "components:":
            start = i
            break
    assert start is not None, "docs/acceptance-criteria/index.yaml has no top-level 'components:' key"

    raw_count = 0
    j = start + 1
    while j < len(lines):
        line = lines[j]
        if line.startswith("  - "):
            raw_count += 1
            j += 1
            continue
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            j += 1
            continue
        if line.startswith(" "):
            j += 1
            continue
        break

    assert raw_count > 1, "raw dash count must exceed 1 so this check cannot pass vacuously"

    fields = _parse_yaml_file(text)
    components = fields.get("components") or []
    assert len(components) >= raw_count, (
        f"reader returned {len(components)} components item(s), "
        f"raw text has {raw_count} top-level dash entries"
    )
