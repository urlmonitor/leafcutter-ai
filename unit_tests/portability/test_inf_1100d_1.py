"""
MODULE: test_inf_1100d_1
AC: INF-1100d-1 -- "A fresh install carries no test database address"

GOAL: RED-baseline behavioral tests proving a fresh install carries no
    default value for ``testing_context.db_connection_test`` -- neither in
    the resolved settings a fresh project would see, nor in the two shipped
    source files that currently supply one
    (``config/skills_config.default.json`` and
    ``config/skills_config.schema.json``) -- while the schema itself keeps
    accepting a project's own address (user decision Q3: no default
    anywhere, but the field itself stays).

WHY IN-PROCESS, NOT A build.py SUBPROCESS: this AC's own it_requirements
    name ``config_loader.load_config`` (the settings resolver ``build.py``
    uses) as the surface to exercise, and CLAUDE.md's "Tests must not spawn
    their own build.py" forbids a full ``build.py`` subprocess run here.
    ``_inf_1100d_1_settings_harness.py`` performs the one ``scripts/``
    sys.path push both this file and its sibling
    ``test_inf_1100d_1_i.py`` need to import ``config_loader`` (and
    ``build``) as real modules.

FIXTURES: every project fixture is a REAL temp directory, and every project
    config that exists on disk is written via ``json.dump``
    (``unit_tests/README.md`` #4 -- never a hand-typed literal). The
    literal legacy shipped address never appears in this file (see the
    harness module's own note) -- assertions check for an ABSENT/None
    value, never a string comparison against the old address.

MUST_CATCH MAPPING (from this AC's own IT-PO enrichment notes):
    - "remove the default from the defaults file but keep the schema
      default" -> ``test_shipped_schema_offers_no_db_default`` goes red
      (the schema-side half of the split criterion test).
    - "set it to '' as a placeholder" -> reproduced by
      ``test_fresh_project_resolves_no_test_db_connection``: the assertion
      is ``value is None`` (not merely falsy), so a wrong fix that replaces
      the shipped default with an empty string instead of removing it
      still fails this test.
    - "delete the property / forbid it" -> caught by
      ``test_schema_still_accepts_project_owned_db_connection``'s own
      real-schema assertion (its mutation-proof branch demonstrates the
      test's discriminating power -- see that test's docstring).

Per the coordinator's explicit instruction, each must_catch case gets its
    OWN test function (never ``self.subTest``, which this repo's
    red-baseline reader would count as the outer test having passed).
"""
# @ac-tag: INF-1100d-1

from __future__ import annotations

import copy
import json

import pytest

from ._inf_1100d_1_settings_harness import (
    DEFAULTS_PATH,
    PROJECT_OWNED_ADDRESS,
    SCHEMA_PATH,
    resolved_db_setting,
    write_bare_project,
)


def test_fresh_project_resolves_no_test_db_connection():
    # covers: INF-1100d-1
    # angle: reachability
    """AC-1: a fresh install (no .claude/skills_config.json at all) has no
    resolved testing_context.db_connection_test value.

    Invokes the REAL production entry point
    (``config_loader.load_config`` -- this AC's own
    ``surface_invoked``, "the settings resolver build.py uses") against a
    genuinely empty project root, then consumes the result in an assertion
    -- not merely importing the module or checking a symbol exists.

    Asserts ``is None`` rather than merely falsy: a wrong fix that
    replaces the shipped default with the empty string ("set it to '' as a
    placeholder", this AC's own must_catch) would still be falsy but is
    NOT the "absent, not an empty string" shape the AC requires, so this
    assertion must reject it.
    """
    project_root = write_bare_project("inf1100d1_fresh_")

    value = resolved_db_setting(project_root)

    assert value is None, (
        "a fresh install must resolve testing_context.db_connection_test "
        f"as absent (None), never an address and never an empty-string "
        f"placeholder; got {value!r}"
    )


def test_shipped_defaults_offer_no_db_default():
    # covers: INF-1100d-1
    # angle: criterion
    """AC-1: the REAL config/skills_config.default.json carries no
    db_connection_test value under testing_context.

    Reads the real on-disk shipped defaults file (never a hand-typed
    literal) and asserts the value is unset -- absent or explicitly null,
    per this AC's it_requirements ("Unset must be represented as absent
    ... never as an empty string or a placeholder address").
    """
    defaults = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))

    testing_context = defaults.get("testing_context", {})
    value = testing_context.get("db_connection_test")

    assert value is None, (
        "config/skills_config.default.json must not ship a "
        f"db_connection_test value; got {value!r}"
    )


def test_shipped_schema_offers_no_db_default():
    # covers: INF-1100d-1
    # angle: criterion
    """AC-1: the REAL config/skills_config.schema.json's db_connection_test
    property carries no 'default' key.

    This is the second half of the split criterion test -- kept as its own
    function (not a self.subTest alongside the defaults-file check) so a
    wrong fix that empties the defaults file but leaves the schema
    'default' in place (this AC's own must_catch, "remove the default from
    the defaults file but keep the schema default") is independently
    visible as its own red test, not swallowed inside a combined pass/fail.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    testing_context_props = (
        schema.get("properties", {}).get("testing_context", {}).get("properties", {})
    )
    db_prop = testing_context_props.get("db_connection_test", {})

    assert "default" not in db_prop, (
        "config/skills_config.schema.json's testing_context."
        f"db_connection_test property must not carry a 'default' key; "
        f"got {db_prop!r}"
    )


def test_schema_still_accepts_project_owned_db_connection():
    # covers: INF-1100d-1
    # angle: boundary
    """AC-1: the schema still validates a project that sets its own
    db_connection_test address (the AC's own control against the cheap
    fix of forbidding the field entirely).

    POSITIVE CONTROL (unit_tests/README.md Section 1, "A passing test is
    not evidence until you know it can fail"): this assertion proves an
    ABSENCE of breakage, so it is green today by construction (nothing
    currently forbids the field) and stays green after INF-1100d-1's fix
    lands (only the DEFAULT is removed, never the property). A red
    baseline is structurally unavailable for a positive control, so the
    proof owed instead is a MUTATION PROOF: forbid the field on a deep
    copy of the REAL schema and confirm that copy rejects the exact same
    instance this test accepts against the real schema.

    wrong impl this catches (must_catch, INF-1100d-1 notes): "delete the
    property / forbid it". If that mutation were ever applied to the REAL
    schema (not just this test's throwaway copy), the first assertion
    below -- validating against ``schema`` loaded straight off disk --
    would go red directly. The second (mutation) branch demonstrates that
    this test's own machinery is capable of detecting exactly that
    failure mode, per the README's "inject the exact leak the test
    forbids, confirm the test goes RED" recipe.
    """
    jsonschema = pytest.importorskip("jsonschema")

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    instance = {
        "testing_context": {
            "test_root": "unit_tests/",
            "readme_path": "unit_tests/README.md",
            "directories": {},
            "max_test_duration_seconds": 5,
            "db_connection_test": PROJECT_OWNED_ADDRESS,
        }
    }

    # Real schema: a project's own address must validate today AND after
    # INF-1100d-1's fix (only the shipped default is removed).
    jsonschema.validate(instance=instance, schema=schema)

    # Mutation proof: forbid the field on a deep copy; the identical
    # instance must now be rejected, proving the assertion above really
    # discriminates "field forbidden" from "field allowed, no default".
    forbidding_schema = copy.deepcopy(schema)
    forbidding_testing_context = forbidding_schema["properties"]["testing_context"]
    del forbidding_testing_context["properties"]["db_connection_test"]
    forbidding_testing_context["additionalProperties"] = False

    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=instance, schema=forbidding_schema)
