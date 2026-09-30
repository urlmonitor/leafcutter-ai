"""
MODULE: test_km_kgs_100a_3_viii
GOAL: TDD stubs for KM-KGS-100a-3-viii — relationship reading is proven
      against a whole-store differential over real store records, not a
      hand-built dictionary or a per-form sample.
BUSINESS CONTEXT: The previous version of this module sampled one exemplar
    record per declared relationship form and missed the one remaining real
    reader/PyYAML divergence in the store: BO-201.yaml, whose covered_by
    block list has a comment line between its items that the production
    reader (scripts/knowledge_query.py::_parse_yaml_file) treats as the end
    of the list, silently dropping every item after it (see KM-KGS-100a-3-ix
    for the dedicated fix). Reading all ~4127 AC YAML files with both the
    production reader and PyYAML (the test-side reference oracle — allowed
    per the KM-KGS-100a-3-viii it_requirements: the stdlib-only gate greps
    only scripts/knowledge_query.py's own import statements, never test
    files) takes on the order of 15-20s end to end (measured locally), so
    the whole-store walk runs exactly once via a module-scoped fixture
    shared by the value-match and form-coverage tests below, rather than
    walking + reading + parsing the store twice.
ARCHITECTURE: `_scan_whole_store()` does one pass over every *.yaml file
    under docs/acceptance-criteria that PyYAML loads as a mapping carrying
    an `id` field (the store's own data-shape rule for "is this a record",
    never a filename allowlist). For each such record it (a) runs the
    shared `_diff_record_fields()` comparison step against
    implemented_by/covered_by and (b) sniffs the raw text, independently of
    the production reader, for which of the declared relationship forms the
    record exhibits. `test_relationship_differential_reports_every_forced_
    disagreement` does NOT depend on any real reader bug: it monkeypatches
    `_parse_yaml_file` itself to force disagreement on two synthetic
    records and asserts the differential's own comparison step
    (`_diff_record_fields`) reports both.
"""

import re
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_AC_STORE = _REPO_ROOT / "docs" / "acceptance-criteria"
sys.path.insert(0, str(_SCRIPTS_DIR))

from knowledge_query import _parse_yaml_file  # noqa: E402

_RELATIONSHIP_FIELDS = ("implemented_by", "covered_by")
_FIELD_HEADER_LINES = tuple(f"{field}:" for field in _RELATIONSHIP_FIELDS)

# The declared relationship-reading forms the whole-store scan must exercise
# at least one real exemplar of (KM-KGS-100a-3-viii test_spec, form-coverage
# entry). Detected from raw text below, independently of the reader under
# test, so an empty store or a wrong store path cannot pass vacuously.
_FORMS = (
    "column_zero_block_list",
    "indented_block_list",
    "quoted_item",
    "test_function_suffix",
    "symbol_anchor",
    "inline_sequence",
    "empty_list",
    "comment_line_in_block_list",
)

_INLINE_FIELD_RE = re.compile(r"^(implemented_by|covered_by):\s*(\[.*\])\s*$")

# Prefer the C-accelerated loader (libyaml) for the whole-store reference
# load — it is available here but not guaranteed on every checkout, so fall
# back to the pure-Python SafeLoader when absent. Same semantics either way;
# this only speeds up the ~4100-file walk's reference parse.
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _normalise(value):
    """Normalise absent/None relationship values to an empty list for comparison."""
    if value is None:
        return []
    return value


def _diff_record_fields(reader_fields, reference_fields):
    """The differential's shared comparison step for one record's fields.

    Returns a list of (field, reader_value, reference_value) tuples for
    every relationship field where the production reader and the reference
    reader disagree. Deliberately a plain function (not inlined into the
    scan loop) so the forced-disagreement test below can exercise the exact
    same comparison step the whole-store scan uses.
    """
    mismatches = []
    for field in _RELATIONSHIP_FIELDS:
        reader_value = _normalise(reader_fields.get(field))
        reference_value = _normalise(reference_fields.get(field))
        if reader_value != reference_value:
            mismatches.append((field, reader_value, reference_value))
    return mismatches


def _load_record_mapping(text):
    """Return the PyYAML mapping for this file's text, or None if it is not
    an AC record (not a mapping, or has no ``id`` field) — a data-shape
    rule, never a filename allowlist."""
    try:
        data = yaml.load(text, Loader=_LOADER)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict) or "id" not in data:
        return None
    return data


def _sniff_forms_for_field_block(lines, header_index):
    """Detect declared forms from the raw lines following a bare field header.

    Does not stop at a comment or blank line (so it can find items that a
    buggy reader would drop) — it stops only at the next non-list,
    non-comment, non-blank line, i.e. the next top-level key. This makes
    the sniff independent of whatever bug the production reader may or may
    not have.
    """
    forms = set()
    j = header_index + 1
    while j < len(lines):
        raw_line = lines[j]
        stripped = raw_line.strip()
        if stripped == "":
            j += 1
            continue
        if stripped.startswith("#"):
            forms.add("comment_line_in_block_list")
            j += 1
            continue
        if stripped.startswith("- "):
            if raw_line.startswith("- "):
                forms.add("column_zero_block_list")
            else:
                forms.add("indented_block_list")
            item_text = stripped[2:].strip()
            if item_text[:1] in ("'", '"'):
                forms.add("quoted_item")
            before_suffix, _, suffix = item_text.partition("::")
            if suffix:
                forms.add("test_function_suffix")
            if "#" in before_suffix:
                forms.add("symbol_anchor")
            j += 1
            continue
        break
    return forms


def _sniff_forms_in_text(text):
    """Sniff which declared relationship forms a raw AC file's text exhibits.

    Text-shape sniff only (not a parse), and deliberately independent of
    `_parse_yaml_file` so the form-coverage proof does not rely on the
    component under test.
    """
    forms = set()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = _INLINE_FIELD_RE.match(stripped)
        if m:
            inner = m.group(2)[1:-1].strip()
            forms.add("empty_list" if inner == "" else "inline_sequence")
            continue
        if stripped in _FIELD_HEADER_LINES:
            forms |= _sniff_forms_for_field_block(lines, i)
    return forms


def _scan_whole_store():
    """Single pass over every AC record in the real store.

    Returns (mismatches, forms_found):
      - mismatches: list of (relative_path, field, reader_value,
        reference_value) for every record/field where the production
        reader and PyYAML disagree, across the WHOLE store (not a sample).
      - forms_found: dict of form name -> one example relative path
        exhibiting it.
    """
    mismatches = []
    forms_found = {}
    for yaml_file in sorted(_AC_STORE.glob("**/*.yaml")):
        try:
            text = yaml_file.read_text(encoding="utf-8")
        except OSError:
            continue
        reference = _load_record_mapping(text)
        if reference is None:
            continue
        rel_path = str(yaml_file.relative_to(_REPO_ROOT))
        reader_fields = _parse_yaml_file(text)
        for field, reader_value, reference_value in _diff_record_fields(
            reader_fields, reference
        ):
            mismatches.append((rel_path, field, reader_value, reference_value))
        for form in _sniff_forms_in_text(text):
            forms_found.setdefault(form, rel_path)
    return mismatches, forms_found


@pytest.fixture(scope="module")
def whole_store_scan():
    """The ~4100-file store walk runs exactly once per test session and is
    shared by the value-match and form-coverage tests, per
    KM-KGS-100a-3-viii's test_spec guidance against re-walking the whole
    store twice."""
    # A missing store must fail, never skip: KM-KGS-100a-3-viii requires that a
    # wrong store path cannot pass vacuously.
    assert _AC_STORE.is_dir(), f"AC store not found at {_AC_STORE}"
    return _scan_whole_store()


def test_whole_store_relationship_values_match_reference_reader(whole_store_scan):
    # covers: KM-KGS-100a-3-viii
    # angle: real_artifact
    """For every AC record in the real store, implemented_by and covered_by
    obtained via the production file-reading entry point equal the values
    PyYAML obtains from the same bytes. All mismatches are collected across
    the whole scan and reported together, not only the first."""
    mismatches, _forms_found = whole_store_scan
    assert not mismatches, "Reader/reference disagreement on real store records:\n" + "\n".join(
        f"{path} field={field}: reader={reader_value!r} reference={reference_value!r}"
        for path, field, reader_value, reference_value in mismatches
    )


def test_whole_store_scan_exercises_every_declared_relationship_form(whole_store_scan):
    # covers: KM-KGS-100a-3-viii
    # angle: real_artifact
    """The set of records scanned by the whole-store differential contains at
    least one exemplar per declared form, detected from raw text
    independently of the production reader. Fails naming any form with no
    exemplar, so an empty store, a wrong store path, or a silently filtered
    scan cannot pass vacuously."""
    _mismatches, forms_found = whole_store_scan
    missing = [form for form in _FORMS if form not in forms_found]
    assert not missing, (
        f"No real store exemplar found for form(s): {missing}. "
        "The differential in this module cannot prove reading correctness "
        "for a form with zero real examples."
    )


def test_relationship_differential_reports_every_forced_disagreement(tmp_path, monkeypatch):
    # covers: KM-KGS-100a-3-viii
    # angle: failure
    """The disagreement is forced synthetically, never by relying on a real
    reader bug: _parse_yaml_file is monkeypatched to disagree with PyYAML
    on two distinct records, and the differential's own comparison step
    (_diff_record_fields) reports both — naming each record and the field
    that differs. This test stays valid whichever reader bugs exist or are
    fixed."""
    record_a = tmp_path / "KM-EX-FORCED-A.yaml"
    record_a.write_text(
        "id: KM-EX-FORCED-A\nimplemented_by:\n- scripts/example_a.py\n",
        encoding="utf-8",
    )
    record_b = tmp_path / "KM-EX-FORCED-B.yaml"
    record_b.write_text(
        "id: KM-EX-FORCED-B\ncovered_by:\n- unit_tests/test_b.py\n",
        encoding="utf-8",
    )

    def _fake_parse_yaml_file(_text):
        return {"implemented_by": ["FORCED-WRONG"], "covered_by": ["FORCED-WRONG"]}

    monkeypatch.setattr(sys.modules[__name__], "_parse_yaml_file", _fake_parse_yaml_file)

    all_mismatches = []
    for record in (record_a, record_b):
        text = record.read_text(encoding="utf-8")
        reference = _load_record_mapping(text)
        reader_fields = _parse_yaml_file(text)
        for field, reader_value, reference_value in _diff_record_fields(
            reader_fields, reference
        ):
            all_mismatches.append((record.name, field, reader_value, reference_value))

    reported_names = {m[0] for m in all_mismatches}
    assert record_a.name in reported_names, "record_a's forced disagreement was not reported"
    assert record_b.name in reported_names, "record_b's forced disagreement was not reported"
    assert len(all_mismatches) >= 2, "expected at least one mismatch reported per forced record"
