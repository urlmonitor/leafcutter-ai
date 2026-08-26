"""
MODULE: test_acs_100i_6_i_declared_completeness
GOAL: Pin ACS-100i-6-i — narrowing the trigger must not become switching the
    gate off. A record that DOES declare a package surface but supplies an
    incomplete structured spec is still refused, and the refusal names each
    field it is missing; and the `it_requirements` object form is held to all
    five fields whatever the declaration says.
BUSINESS CONTEXT: The `it_requirements` `oneOf` object branch carries its own
    `required: [five fields]` list, independently of the top-level if/then. That
    behaviour must survive the narrowing untouched. If an implementer reaches
    the narrowing by loosening the object branch instead of by narrowing the
    `if`, the third test below fails — that is its entire purpose.
ARCHITECTURE: Behavioral. Field-naming is asserted against the real CLI
    validators' output (scripts/ac_store/validate_ac_schema.py and
    scripts/ac_store/validate_ac.py, run as subprocesses over YAML written by
    yaml.safe_dump), never against a grep of their source. The anti-loosening
    guard is asserted by re-validating against the schema with its top-level
    if/then removed, which isolates the object branch.

AC: ACS-100i-6-i (docs/acceptance-criteria/ac-store/
    ACS-100-structured-requirements/ACS-100i-6-i.yaml)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acs_100i_support import (  # noqa: E402
    PKG_SURFACE_VALIDATOR_CLI,
    SCHEMA_VALIDATOR_CLI,
    base_ac_record,
    complete_impl_spec,
    fields_reported_missing,
    refusal_text,
    run_cli,
    verdict,
    write_ac_yaml,
)

_SUPPLIED = ("config_schema_fragment", "reference_file_path", "required_skills")
_OMITTED = ("n_location_rule", "post_write_commands")


def _spec_missing(*omit: str) -> dict:
    """Return a complete impl spec with the named fields removed."""
    spec = complete_impl_spec()
    for key in omit:
        spec.pop(key)
    return spec


def test_declared_record_missing_spec_fields_is_refused_naming_each(tmp_path):
    # covers: ACS-100i-6-i
    """ACS-100i-6-i s1: a declaring record whose structured spec supplies the
    config-schema fragment, the reference-file path and the required-skills list
    but omits the N-location rule and the post-write commands must be refused,
    and the refusal must name exactly those two as missing.

    Currently RED. With `component: ac-store` the top-level if/then does not
    fire, so the only schema error is the `it_requirements` `oneOf` umbrella
    message ("is not valid under any of the given schemas"), which names no
    field at all; and validate_ac.py does not classify the record as a
    package-surface AC, so it exits 0.

    Accepted phrasings for "field X is missing" are listed in
    _acs_100i_support._MISSING_FIELD_PATTERNS — an implementation inventing a
    new phrasing must add it there in the same commit.
    """
    path = write_ac_yaml(
        tmp_path,
        "ACS-999.yaml",
        base_ac_record(package_surface=True, it_requirements=_spec_missing(*_OMITTED)),
    )

    schema_run = run_cli(SCHEMA_VALIDATOR_CLI, str(path))
    text = refusal_text(path)
    reported = fields_reported_missing(text)

    assert schema_run.returncode != 0, (
        "a declaring record missing two of the five spec fields must be "
        f"refused; validator exited 0.\n{schema_run.output}"
    )
    assert reported == set(_OMITTED), (
        f"the refusal must name exactly {sorted(_OMITTED)} as missing and must "
        f"not name any of the three supplied fields {sorted(_SUPPLIED)}; it "
        f"reported {sorted(reported)}. Combined validator output:\n{text}"
    )


def test_declared_record_with_all_five_fields_is_accepted(tmp_path):
    # covers: ACS-100i-6-i
    """ACS-100i-6-i s2: the same record with all five fields supplied is
    accepted.

    Currently RED: `package_surface` is not a recognised property of
    config/ac_store_schema.json (root additionalProperties is false), so the
    declaration itself is rejected regardless of how complete the spec is.
    """
    record = base_ac_record(package_surface=True, it_requirements=complete_impl_spec())
    path = write_ac_yaml(tmp_path, "ACS-999.yaml", record)

    result = verdict(record)
    schema_run = run_cli(SCHEMA_VALIDATOR_CLI, str(path))
    pkg_run = run_cli(PKG_SURFACE_VALIDATOR_CLI, str(path))

    assert not result.refused, (
        "a declaring record supplying all five spec fields must be accepted; "
        f"schema reported {list(result.messages)}"
    )
    assert schema_run.returncode == 0, (
        f"validate_ac_schema.py must accept it; exit={schema_run.returncode}\n"
        f"{schema_run.output}"
    )
    assert pkg_run.returncode == 0, (
        f"validate_ac.py must accept it; exit={pkg_run.returncode}\n{pkg_run.output}"
    )


def test_object_form_is_held_to_all_five_fields_without_any_declaration(tmp_path):
    # covers: ACS-100i-6-i
    """ACS-100i-6-i s3 — the load-bearing anti-loosening guard.

    A record that does NOT declare a package surface, but whose implementation
    requirements are nevertheless a structured object missing the N-location
    rule, must still be refused for that missing field. Narrowing the trigger
    must not become a way to file a half-populated structured spec.

    This is GREEN today and must STAY green: the `it_requirements` `oneOf`
    object branch carries its own five-field `required` list. It fails only if
    the implementation reaches the narrowing by loosening that branch instead of
    by narrowing the top-level `if` — which is exactly the shortcut this test
    exists to block.

    Three assertions, because "refused" alone would be satisfied by an
    unrelated error: the record is refused; the refusal survives removal of the
    top-level if/then (so it comes from the object branch, not the trigger); and
    restoring the one missing field makes it accepted (so the refusal really was
    *for* that field).
    """
    incomplete = base_ac_record(it_requirements=_spec_missing("n_location_rule"))
    complete = base_ac_record(it_requirements=complete_impl_spec())

    incomplete_result = verdict(incomplete)
    complete_result = verdict(complete)
    cli_run = run_cli(
        SCHEMA_VALIDATOR_CLI,
        str(write_ac_yaml(tmp_path, "ACS-999.yaml", incomplete)),
    )

    assert incomplete_result.refused, (
        "an undeclared record whose it_requirements object omits "
        "n_location_rule must still be refused — the object form is held to "
        "its full shape whatever the declaration says"
    )
    assert incomplete_result.other_messages, (
        "the refusal must survive removal of the schema's top-level if/then, "
        "proving it comes from the it_requirements object branch and not from "
        f"the trigger; every message was trigger-attributable: "
        f"{list(incomplete_result.messages)}"
    )
    assert not complete_result.refused, (
        "supplying the missing n_location_rule must make the same record "
        f"acceptable, else the refusal was not for that field; got "
        f"{list(complete_result.messages)}"
    )
    assert cli_run.returncode != 0, (
        "the shipped validator must also refuse it, not just the in-memory "
        f"schema check; exit={cli_run.returncode}\n{cli_run.output}"
    )
