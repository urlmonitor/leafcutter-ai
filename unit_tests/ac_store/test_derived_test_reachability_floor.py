"""
MODULE: unit_tests/ac_store/test_derived_test_reachability_floor.py
GOAL: Lock in the reachability floor under the derived-test fallback in
    scripts/ac_store/generate_ticket_from_ac.py::_derive_tests_from_criteria.

WHY THIS EXISTS
    Only ~13.6% of the AC store carries an authored ``test_spec`` (394 of 2888
    records measured on 2026-08-14). Every other AC falls through to
    ``_derive_tests_from_criteria``, which — before this change — emitted
    EXACTLY ONE TEST PER GHERKIN ``Then`` CLAUSE, asserting the literal clause
    text and nothing else. That is the AC-literal angle in isolation, and it is
    the mechanical root cause of this repo's documented, repeated phantom-done
    failure mode: code ships unit-tested but is never wired into anything that
    runs it.

    Real instances:
      - 9c58f4550 — BO-2400f-7..10 lifecycle functions shipped unit-tested but
        unreachable: no CLI subcommands, no workflow invocation.
      - fast_lane.py had no CLI, so the runner's ``select_batch`` call was a
        silent no-op; the grep-only structural tests stayed green.
      - done_proof.py was omitted from the build deploy_map, so the DEPLOYED
        hook crashed with ModuleNotFoundError while source-tree unit tests
        passed.

    The fix adds one mandatory ``angle: reachability`` descriptor to every
    derived test contract and tags the Then-clause descriptors
    ``angle: criterion`` so the two are distinguishable.

ARCHITECTURE / ANTI-SYNTHETIC-FIXTURE POSTURE
    The primary gates load REAL AC YAML records from the on-disk store at
    docs/acceptance-criteria/ and drive the generator through its REAL entry
    point (``generate_ticket_from_ac.py --ac <id> --dry-run`` as a subprocess),
    then parse the ``## Test Requirements`` block out of the produced ticket
    exactly as the ticket guard does.

    This follows unit_tests/test_generate_ticket_from_ac.py::
    TestRealStoreComputedMapE2E::test_real_backfilled_ac_gets_architect_review.
    Its docstring explains why a hand-typed dict defeats the purpose: a
    synthetic ``{'criteria': 'Then ...'}`` proves only that the generator CAN
    emit a reachability entry, not that the records actually in the store take
    the fallback path and receive one. Two of the three primary tests here
    DISCOVER their anchor record by scanning the real store, so they cannot be
    satisfied by a fixture that happens to match the author's mental model.

    Two narrow branch tests (idempotency on an authored reachability angle, and
    the slug-collision path) do use constructed records — those branches are
    unreachable from the current store contents, and are explicitly labelled.

COVERS: UNKNOWN (no AC authored for this change)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GEN_SCRIPT = _REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"
_REAL_AC_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"
_SCHEMA_PATH = _REPO_ROOT / "config" / "ac_store_schema.json"

sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))

from generate_ticket_from_ac import (  # noqa: E402
    _build_test_requirements_section,
    _derive_tests_from_criteria,
)

# Angle values are asserted as LITERALS, deliberately not imported from the
# module under test. Importing the module's own constants would make these
# tests pass even if the emitted value silently changed — and on a full revert
# the import itself would raise ImportError at collection time, hiding the
# behavioural failure behind a collection error.
TEST_ANGLE_CRITERION = "criterion"
TEST_ANGLE_REACHABILITY = "reachability"

# Same regex the production ticket guard uses
# (templates/scripts/commit_guardian/check_ticket_test_requirements.py).
_TESTS_BLOCK_RE = re.compile(
    r"##\s+Test\s+Requirements\b.*?```(?:yaml)?\s*(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

_REACHABILITY_NAME_SUFFIX = "reachable_from_entry_point"

# Coder agents whose ACs must never ship without a reachability floor.
_CODER_AGENTS = frozenset({"python-coder", "sql-coder", "frontend-coder"})

# The full angle vocabulary, as literals. Same reasoning as the two constants
# above: asserted, never imported from the code under test.
_ALL_TEST_ANGLES = frozenset({
    "criterion",
    "reachability",
    "seam",
    "real_artifact",
    "deployed",
    "boundary",
    "failure",
})


def _load_schema() -> dict:
    """Read and parse the REAL on-disk config/ac_store_schema.json."""
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _test_spec_item_schema() -> dict:
    """Return the ``test_spec`` array-item subschema from the real schema file."""
    test_spec = _load_schema()["properties"]["test_spec"]
    array_branches = [
        branch for branch in test_spec["oneOf"] if branch.get("type") == "array"
    ]
    assert len(array_branches) == 1, (
        f"test_spec must keep exactly one array branch in its oneOf: {test_spec}"
    )
    return array_branches[0]["items"]


def _schema_errors(record: dict) -> list[str]:
    """Validate *record* against the real AC store schema; return error strings.

    Uses jsonschema.Draft7Validator against config/ac_store_schema.json — the
    identical mechanism and identical schema file used by BOTH the
    ``check-ac-schema`` pre-commit hook (via
    ``templates/scripts/commit_guardian/check_ac_schema.py``) and
    ``scripts/ac_store/validate_ac_schema.py``. Nested ``oneOf`` context errors
    are flattened in, because the top-level message for a failing array branch
    is only "is not valid under any of the given schemas" and hides the actual
    violation.

    Args:
        record: Parsed AC record.

    Returns:
        Human-readable violation strings; empty list when the record is valid.
    """
    import jsonschema  # noqa: PLC0415 — optional dep, imported at call time

    def _fmt(err) -> str:
        loc = ".".join(str(p) for p in err.absolute_path) or "<root>"
        return f"at {loc} — {err.message}"

    errors: list[str] = []
    for err in sorted(jsonschema.Draft7Validator(_load_schema()).iter_errors(record), key=str):
        errors.append(_fmt(err))
        errors.extend(_fmt(sub) for sub in err.context or [])
    return errors


# A constructed record that is nonetheless a FULL, schema-valid AC — the point
# of the schema assertion below is lost if the fixture is a partial dict that
# only happens to satisfy the code path. 'build-pipeline' keeps it out of the
# schema's package-surface if/then branch, which would otherwise demand a
# structured it_requirements object.
_AUTHORED_ANGLE_AC: dict = {
    "id": "ZZ-900a-1",
    "title": "Fixture AC whose it-po authored a reachability-angle test_spec",
    "component": "build-pipeline",
    "components": ["build_pipeline"],
    "status": "active",
    "readiness": "approved",
    "priority": "medium",
    "level": "L2",
    "work_status": "todo",
    "assigned_agent": "python-coder",
    "criteria": "Given a thing\nWhen it happens\nThen the thing is recorded\n",
    "test_spec": [
        {
            "name": "test_zz_900a_1_reachable_from_entry_point",
            "description": "Invoke the CLI and assert the record lands.",
            "target_dir": "unit_tests/zz/",
            "angle": "reachability",
        }
    ],
}


# ---------------------------------------------------------------------------
# Real-store helpers — no synthetic records on the primary path
# ---------------------------------------------------------------------------


def _load_real_records() -> list[tuple[Path, dict]]:
    """Load every parseable AC record from the REAL on-disk store.

    Returns:
        List of ``(path, record)`` tuples. Unparseable / non-mapping files are
        skipped rather than failing the sweep — a malformed unrelated record is
        not this test's concern.
    """
    records: list[tuple[Path, dict]] = []
    for path in sorted(_REAL_AC_ROOT.rglob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(data, dict) and data.get("id"):
            records.append((path, data))
    return records


def _has_test_spec(record: dict) -> bool:
    """Return True when the record carries a non-empty authored ``test_spec``."""
    spec = record.get("test_spec")
    return isinstance(spec, list) and bool(spec)


def _then_clause_count(record: dict) -> int:
    """Count Gherkin ``Then`` clauses in a record's criteria block."""
    criteria = str(record.get("criteria") or "")
    return len(re.findall(r"^\s*Then\b.+$", criteria, re.MULTILINE | re.IGNORECASE))


def _find_fallback_anchor(records: list[tuple[Path, dict]]) -> dict:
    """Pick a real record that takes the derived-from-criteria fallback path.

    Requirements: a coder agent (so the ticket is a code ticket), no authored
    ``test_spec`` (so the fallback fires), ``test_required`` not False (so the
    section is emitted at all), and at least two ``Then`` clauses (so the
    criterion/reachability distinction is observable).

    Args:
        records: Real store records.

    Returns:
        The chosen record. Fails the test when the real store holds none —
        never falls back to a synthetic record.
    """
    matches = [
        record
        for _path, record in records
        if record.get("assigned_agent") in _CODER_AGENTS
        and not _has_test_spec(record)
        and record.get("test_required") is not False
        and _then_clause_count(record) >= 2
    ]
    assert matches, (
        "no real AC in docs/acceptance-criteria/ has a coder agent, no "
        "test_spec, and >=2 Then clauses — the fallback anchor is gone"
    )
    return matches[0]


def _find_authored_spec_anchor(records: list[tuple[Path, dict]]) -> dict:
    """Pick a real record that carries an authored ``test_spec``.

    Args:
        records: Real store records.

    Returns:
        The chosen record. Fails the test when the real store holds none.
    """
    matches = [
        record
        for _path, record in records
        if record.get("assigned_agent") in _CODER_AGENTS
        and _has_test_spec(record)
        and record.get("test_required") is not False
    ]
    assert matches, (
        "no real AC in docs/acceptance-criteria/ carries an authored test_spec"
    )
    return matches[0]


def _generate_ticket_via_cli(ac_id: str) -> str:
    """Run the generator's REAL entry point against the REAL store.

    Uses ``--dry-run`` so the ticket is printed and nothing is written to
    tickets/ or back-written to the AC file.

    Args:
        ac_id: AC id to generate for.

    Returns:
        The generator's stdout (frontmatter + ticket body).
    """
    proc = subprocess.run(
        [
            sys.executable,
            str(_GEN_SCRIPT),
            "--ac",
            ac_id,
            "--ac-root",
            str(_REAL_AC_ROOT),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
    )
    assert proc.returncode == 0, (
        f"generator CLI failed for {ac_id} (exit {proc.returncode})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    return proc.stdout


def _parse_test_entries(ticket_text: str) -> list[dict]:
    """Extract the ``tests:`` list from a generated ticket's Test Requirements.

    Args:
        ticket_text: Full generated ticket text.

    Returns:
        The parsed list of test entry dicts.
    """
    match = _TESTS_BLOCK_RE.search(ticket_text)
    assert match is not None, (
        "generated ticket has no ## Test Requirements fenced block:\n"
        f"{ticket_text[:2000]}"
    )
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict) and isinstance(parsed.get("tests"), list), (
        f"## Test Requirements block did not parse to a tests list: {parsed!r}"
    )
    return [entry for entry in parsed["tests"] if isinstance(entry, dict)]


def _reachability_entries(entries: list[dict]) -> list[dict]:
    """Return the entries tagged ``angle: reachability``."""
    return [e for e in entries if e.get("angle") == TEST_ANGLE_REACHABILITY]


@pytest.fixture(scope="module")
def real_records() -> list[tuple[Path, dict]]:
    """Module-scoped real-store load (the sweep reads ~2900 files once)."""
    if not _REAL_AC_ROOT.is_dir():
        pytest.skip(f"real AC store root absent: {_REAL_AC_ROOT}")
    records = _load_real_records()
    if not records:
        pytest.skip(f"real AC store is empty: {_REAL_AC_ROOT}")
    return records


# ---------------------------------------------------------------------------
# Primary gates — REAL store record, REAL CLI entry point
# ---------------------------------------------------------------------------


class TestRealStoreReachabilityFloor:
    """The derived fallback must emit a reachability entry for real records."""

    def test_real_store_ac_without_test_spec_gets_reachability_entry(
        self, real_records: list[tuple[Path, dict]]
    ) -> None:
        # covers: UNKNOWN
        """A real no-test_spec AC's generated ticket carries the floor entry.

        Discovers the anchor by scanning the actual store (so it cannot be
        satisfied by a fixture), then drives the generator as a subprocess
        through its documented CLI and parses the produced ticket.
        """
        record = _find_fallback_anchor(real_records)
        ac_id = record["id"]

        entries = _parse_test_entries(_generate_ticket_via_cli(ac_id))
        reach = _reachability_entries(entries)

        assert len(reach) == 1, (
            f"real AC {ac_id} (no test_spec) produced {len(reach)} reachability "
            f"entries, expected exactly 1. Without it the derived contract is "
            f"AC-literal unit tests only — the phantom-done shape.\n"
            f"entries: {entries}"
        )
        entry = reach[0]
        assert entry["name"].endswith(_REACHABILITY_NAME_SUFFIX), (
            f"reachability entry name {entry['name']!r} must end with "
            f"{_REACHABILITY_NAME_SUFFIX!r}"
        )
        assert entry["name"].startswith("test_"), entry["name"]
        assert entry["covers"] == [ac_id], entry
        assert entry["file"].endswith(".py"), entry
        # The assertion text must remain an explicit, non-deletable mandate.
        asserts = str(entry.get("asserts", ""))
        assert asserts.startswith("REQUIRED"), asserts
        assert "production entry point" in asserts, asserts
        assert "Do NOT satisfy this by importing the function directly" in asserts, asserts
        assert "do not delete this entry" in asserts, asserts

    def test_real_store_derived_then_clause_entries_are_tagged_criterion(
        self, real_records: list[tuple[Path, dict]]
    ) -> None:
        # covers: UNKNOWN
        """Derived Then-clause entries carry ``angle: criterion``.

        Without the tag the two kinds of derived test are indistinguishable,
        so nothing downstream can tell an AC-literal assertion apart from the
        reachability floor.
        """
        record = _find_fallback_anchor(real_records)
        ac_id = record["id"]

        entries = _parse_test_entries(_generate_ticket_via_cli(ac_id))
        criterion = [e for e in entries if e.get("angle") == TEST_ANGLE_CRITERION]

        assert len(criterion) == _then_clause_count(record), (
            f"real AC {ac_id} has {_then_clause_count(record)} Then clauses but "
            f"{len(criterion)} entries tagged angle: criterion.\nentries: {entries}"
        )
        untagged = [e for e in entries if "angle" not in e]
        assert not untagged, (
            f"every derived entry must carry an angle; untagged: {untagged}"
        )
        assert {e.get("angle") for e in entries} == {
            TEST_ANGLE_CRITERION,
            TEST_ANGLE_REACHABILITY,
        }, entries

    def test_every_sampled_real_store_fallback_ac_gets_the_floor(
        self, real_records: list[tuple[Path, dict]]
    ) -> None:
        # covers: UNKNOWN
        """Sweep real fallback-path records: each gets exactly one floor entry.

        A single anchor could pass by accident (e.g. a criteria block whose
        clause slug happens to match). This drives the section builder over a
        broad sample of the ACTUAL records that take the fallback, which is the
        population the change exists for.
        """
        fallback = [
            record
            for _path, record in real_records
            if record.get("assigned_agent") in _CODER_AGENTS
            and not _has_test_spec(record)
            and record.get("test_required") is not False
        ]
        assert len(fallback) >= 50, (
            f"expected the store to still hold a large fallback population, "
            f"found {len(fallback)} — re-check the sweep filter"
        )

        offenders: list[str] = []
        for record in fallback:
            section = _build_test_requirements_section(record, record["id"])
            entries = _parse_test_entries(f"## Test Requirements\n\n{section}")
            reach = _reachability_entries(entries)
            if len(reach) != 1:
                offenders.append(f"{record['id']}: {len(reach)} reachability entries")

        assert not offenders, (
            f"{len(offenders)} of {len(fallback)} real fallback ACs lack exactly "
            f"one reachability floor entry:\n" + "\n".join(offenders[:20])
        )

    def test_authored_test_spec_ac_is_not_given_a_duplicate_floor(
        self, real_records: list[tuple[Path, dict]]
    ) -> None:
        # covers: UNKNOWN
        """A real AC with an authored test_spec keeps its own contract.

        The floor belongs to the fallback only. An AC whose it-po authored a
        test_spec must not have a second, generator-invented reachability test
        stapled on: at most one reachability entry, and no entry the author did
        not write.
        """
        record = _find_authored_spec_anchor(real_records)
        ac_id = record["id"]

        entries = _parse_test_entries(_generate_ticket_via_cli(ac_id))
        reach = _reachability_entries(entries)

        assert len(reach) <= 1, (
            f"real AC {ac_id} has an authored test_spec but produced "
            f"{len(reach)} reachability entries: {reach}"
        )
        authored_names: set[str] = {
            str(item["name"])
            for item in record["test_spec"]
            if isinstance(item, dict) and item.get("name")
        }
        emitted_names: set[str] = {str(e["name"]) for e in entries}
        assert emitted_names == authored_names, (
            f"generator invented or dropped test entries for {ac_id}.\n"
            f"authored: {sorted(authored_names)}\nemitted: {sorted(emitted_names)}"
        )


# ---------------------------------------------------------------------------
# Branch gates — constructed records for paths the real store cannot reach
# ---------------------------------------------------------------------------


class TestReachabilityFloorEdgeBranches:
    """Idempotency and slug-collision branches.

    These use constructed records ON PURPOSE: no record in the real store
    currently authors an ``angle: reachability`` test_spec entry, and none has a
    Then clause that slugifies onto the floor's own name. Both branches are
    reachable in production the moment an author writes one, so they are
    covered here rather than left untested.
    """

    def test_authored_reachability_angle_is_not_duplicated(self) -> None:
        # covers: UNKNOWN
        """An authored ``angle: reachability`` test_spec entry stands alone."""
        ac = dict(_AUTHORED_ANGLE_AC)

        # The fixture must be a record an author could actually commit. Without
        # this the rest of the test is a claim about a shape the store rejects:
        # test_spec items set additionalProperties: false, so before `angle` was
        # declared this failed with
        #   at test_spec.0 — Additional properties are not allowed
        #   ('angle' was unexpected)
        # and the generator's passthrough was dead on arrival.
        assert _schema_errors(ac) == [], (
            "the authored-angle fixture must validate against the REAL "
            f"config/ac_store_schema.json: {_schema_errors(ac)}"
        )

        section = _build_test_requirements_section(ac, "ZZ-900a-1")
        entries = _parse_test_entries(f"## Test Requirements\n\n{section}")

        reach = _reachability_entries(entries)
        assert len(reach) == 1, f"expected the single authored entry, got {entries}"
        assert reach[0]["name"] == "test_zz_900a_1_reachable_from_entry_point"
        assert len(entries) == 1, entries

    def test_slug_collision_does_not_drop_the_reachability_entry(self) -> None:
        # covers: UNKNOWN
        """A Then clause colliding with the floor's name must not swallow it.

        The pre-existing collision-disambiguation loop carries a comment warning
        that a fixed suffix can still collide and silently drop a test. The floor
        must survive the collision as a distinct, still-reachability-tagged entry.
        """
        ac = {
            "id": "ZZ-901a-1",
            "assigned_agent": "python-coder",
            "criteria": (
                "Given a colliding criteria block\n"
                "When the generator derives tests\n"
                "Then reachable from entry point\n"
                "Then reachable from entry point\n"
            ),
        }
        tests = _derive_tests_from_criteria(ac, "ZZ-901a-1")

        names = [t["name"] for t in tests]
        assert len(names) == len(set(names)), f"duplicate test names emitted: {names}"
        assert len(tests) == 3, f"2 criterion + 1 reachability expected, got {tests}"

        reach = _reachability_entries(tests)
        assert len(reach) == 1, f"reachability floor was dropped by collision: {tests}"
        assert reach[0]["name"] not in {
            t["name"] for t in tests if t.get("angle") == TEST_ANGLE_CRITERION
        }
        assert reach[0]["name"].startswith("test_zz_901a_1_reachable_from_entry_point")
        assert str(reach[0]["asserts"]).startswith("REQUIRED")

    def test_criteria_without_then_clauses_still_gets_the_floor(self) -> None:
        # covers: UNKNOWN
        """The no-Then-clause fallback branch also carries the floor."""
        ac = {"id": "ZZ-902a-1", "assigned_agent": "python-coder", "criteria": "Prose only."}
        tests = _derive_tests_from_criteria(ac, "ZZ-902a-1")

        assert len(tests) == 2, tests
        assert tests[0]["angle"] == TEST_ANGLE_CRITERION, tests
        assert tests[1]["angle"] == TEST_ANGLE_REACHABILITY, tests


# ---------------------------------------------------------------------------
# Schema gates — the authoring surface must actually accept an authored angle
# ---------------------------------------------------------------------------


class TestTestSpecAngleIsSchemaDeclared:
    """``angle`` must be DECLARED on the test_spec item, not merely tolerated.

    The generator passes an authored ``test_spec[].angle`` through onto the
    ticket entry, but the item schema sets ``additionalProperties: false``. Until
    the property was declared, every AC carrying it was rejected by the
    ``check-ac-schema`` pre-commit hook and by
    ``scripts/ac_store/validate_ac_schema.py`` — so the passthrough could never
    fire on real work. This is the same defect class as the undeclared
    ``declares_side_effect`` field (see
    ``test_declares_side_effect_schema_reachability.py``).
    """

    def test_item_schema_keeps_additional_properties_closed(self) -> None:
        # covers: UNKNOWN
        """A closed item schema is what makes the declaration test non-vacuous.

        Flipping this to true would make any unknown key validate, silently
        restoring the discoverability gap while every assertion below still
        passed.
        """
        item_schema = _test_spec_item_schema()
        assert item_schema.get("additionalProperties") is False, (
            "test_spec items must keep additionalProperties: false; loosening it "
            "would make the angle declaration below unverifiable."
        )

    def test_item_schema_declares_angle_with_the_full_vocabulary(self) -> None:
        # covers: UNKNOWN
        """The property exists, is a closed string enum, and is discoverable."""
        angle = _test_spec_item_schema().get("properties", {}).get("angle")
        assert angle is not None, (
            "config/ac_store_schema.json must declare a test_spec[].angle "
            "property. While it is absent and the item schema sets "
            "additionalProperties: false, any AC carrying an angle is REJECTED "
            "at authoring time and generate_ticket_from_ac.py's angle "
            "passthrough is dead code."
        )
        assert angle.get("type") == "string", angle
        assert set(angle.get("enum") or []) == _ALL_TEST_ANGLES, (
            "the angle enum must be exactly the taxonomy's 5 core + 2 "
            f"conditional angles: {sorted(_ALL_TEST_ANGLES)}; found "
            f"{angle.get('enum')!r}"
        )
        assert "docs/testing/test-angles.md" in angle.get("description", ""), (
            "the angle description must point at docs/testing/test-angles.md so "
            "an it-po can find out what the values mean. Current description: "
            f"{angle.get('description', '')!r}"
        )

    def test_an_unknown_angle_value_is_rejected(self) -> None:
        # covers: UNKNOWN
        """Negative control — the enum must actually close the vocabulary.

        Without this, declaring ``angle`` as a free-form string would satisfy
        every assertion above while letting a typo ('reachabilty') through into
        a generated ticket unchallenged.
        """
        record = json.loads(json.dumps(_AUTHORED_ANGLE_AC))
        record["test_spec"][0]["angle"] = "reachabilty"

        errors = _schema_errors(record)
        assert any("is not one of" in err for err in errors), (
            "an angle outside the taxonomy must fail schema validation; "
            f"errors: {errors!r}"
        )

    def test_angle_is_optional(self) -> None:
        # covers: UNKNOWN
        """Omitting the angle stays valid — 2,888 existing records omit it."""
        record = json.loads(json.dumps(_AUTHORED_ANGLE_AC))
        del record["test_spec"][0]["angle"]
        assert _schema_errors(record) == [], _schema_errors(record)


class TestGeneratorAngleVocabularyMatchesSchema:
    """Cross-source set-equality contract between the code and the schema.

    ``generate_ticket_from_ac._TEST_ANGLES`` is a mirror of the schema's enum.
    Two independently-maintained copies of one vocabulary is exactly how
    EPIC-ComputedQualityGates FP-1 layer 3 shipped a hook whose
    ``ALLOWED_CHANGE_TARGETS`` and ``guardrail_gates.yaml`` keys were disjoint:
    each side was tested against its own copy and no cross-source test existed.
    This is that missing test.
    """

    def test_module_vocabulary_equals_schema_enum(self) -> None:
        # covers: UNKNOWN
        from generate_ticket_from_ac import _TEST_ANGLES  # noqa: PLC0415

        schema_enum = set(
            _test_spec_item_schema()["properties"]["angle"]["enum"]
        )
        assert set(_TEST_ANGLES) == schema_enum, (
            "generate_ticket_from_ac._TEST_ANGLES has drifted from the "
            "test_spec[].angle enum in config/ac_store_schema.json. Update both "
            f"together.\ncode:   {sorted(_TEST_ANGLES)}\nschema: {sorted(schema_enum)}"
        )
        assert set(_TEST_ANGLES) == _ALL_TEST_ANGLES, sorted(_TEST_ANGLES)

    def test_unknown_authored_angle_warns_and_still_passes_through(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # covers: UNKNOWN
        """An off-vocabulary angle is logged, not dropped and not rejected.

        The schema is the gate; the generator must not silently discard authored
        data on a vocabulary miss, but must also not pass a typo through in
        total silence — the schema hook does not run on every path an AC can
        reach the store by.
        """
        ac = json.loads(json.dumps(_AUTHORED_ANGLE_AC))
        ac["test_spec"][0]["angle"] = "reachabilty"

        with caplog.at_level("WARNING", logger="generate_ticket_from_ac"):
            section = _build_test_requirements_section(ac, "ZZ-900a-1")
        entries = _parse_test_entries(f"## Test Requirements\n\n{section}")

        assert entries[0]["angle"] == "reachabilty", (
            f"the authored value must survive unchanged: {entries}"
        )
        assert any(
            "unrecognised test angle" in record.getMessage() for record in caplog.records
        ), f"no warning emitted for an off-vocabulary angle: {caplog.records}"
