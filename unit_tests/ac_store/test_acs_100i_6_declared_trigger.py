"""
MODULE: test_acs_100i_6_declared_trigger
GOAL: Pin ACS-100i-6 — the structured-implementation-spec obligation fires on an
    explicit `package_surface: true` declaration on the record and on NOTHING
    else: not on the assigned agent, not on the `component` scalar, not on the
    `components` list.
BUSINESS CONTEXT: Today the trigger is the proxy `assigned_agent: python-coder`
    AND `component` in {build_pipeline, build-orchestration}. Measured on this
    worktree at 9b16d013: it refuses 243 of the store's 280 refused records,
    including BO-2000d-1 / -2 / -1-i — the three records that *specify* the
    rule. A rule its own specification cannot satisfy is a rule about a
    spelling, not about package surfaces.
ARCHITECTURE: Behavioral only. Verdicts come from `validate_with_jsonschema`,
    the exact helper templates/scripts/commit_guardian/check_ac_schema.py calls,
    run against the real config/ac_store_schema.json; refusal WORDING comes from
    running the two real CLI validators (scripts/ac_store/validate_ac_schema.py
    and scripts/ac_store/validate_ac.py) as subprocesses over YAML written by
    the real yaml.safe_dump serializer. No test in this module reads a source
    file looking for a string (CLAUDE.md, "Gate / Workflow ACs — Verify
    Behaviorally, Not by Grep").

    "Refused on this ground" is computed by attribution, not by matching
    message text: a refusal counts as the package-surface rule's when it
    disappears once the schema's top-level if/then block is removed. See
    _acs_100i_support for the mechanism.

AC: ACS-100i-6 (docs/acceptance-criteria/ac-store/
    ACS-100-structured-requirements/ACS-100i-6.yaml)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acs_100i_support import (  # noqa: E402
    SCHEMA_VALIDATOR_CLI,
    base_ac_record,
    refusal_text,
    run_cli,
    states_structured_spec_obligation,
    top_level_rule_is_present,
    verdict,
    write_ac_yaml,
)

#: Namespaces a declaration must be honoured in. `build-pipeline` (kebab) is the
#: real index.yaml namespace key carried by 440 records and absent from today's
#: trigger enum; `build_pipeline` (underscore) is a components.json graph id on a
#: different axis that the enum does list; `ac-store` is unrelated to the build.
_COMPONENTS = ["ac-store", "build-pipeline", "build_pipeline", "build-orchestration"]

#: Every non-object shape the criterion says must be refused once declared.
_UNSTRUCTURED_SPECS = [
    "A plain string implementation note.",
    ["A list", "of requirement strings"],
    None,
]


@pytest.mark.parametrize("component", _COMPONENTS)
@pytest.mark.parametrize("it_requirements", _UNSTRUCTURED_SPECS, ids=["str", "list", "null"])
def test_declared_package_surface_requires_a_structured_spec(component, it_requirements):
    # covers: ACS-100i-6
    """ACS-100i-6 s1: a record declaring `package_surface: true` whose
    implementation requirements are a plain string, a list of strings or null
    must be refused, and refused *on the package-surface rule*.

    Currently RED. `package_surface` is not a declared property of the schema
    (root additionalProperties is false), so the only thing the declaration
    produces today is an "additional properties are not allowed" error — which
    survives removal of the top-level if/then and is therefore NOT a refusal on
    this ground. For `component: ac-store` and `component: build-pipeline` the
    obligation never fires at all.

    To go green: the top-level `if` must key on `package_surface: true`, and
    `package_surface` must become a recognised boolean property.
    """
    record = base_ac_record(
        component=component,
        package_surface=True,
        it_requirements=it_requirements,
    )

    result = verdict(record)

    assert result.refused, (
        f"a record declaring package_surface: true in component {component!r} "
        f"with it_requirements={it_requirements!r} must be refused; the "
        "validator accepted it"
    )
    assert result.refused_on_package_surface_rule, (
        "the refusal must be attributable to the package-surface obligation "
        "(i.e. it must vanish when the schema's top-level if/then is removed), "
        f"but every message survived that removal: {list(result.messages)}"
    )


def test_refusal_states_the_declared_surface_needs_a_structured_spec(tmp_path):
    # covers: ACS-100i-6
    """ACS-100i-6 s1: the refusal must SAY that a record declaring a package
    surface has to carry a structured implementation spec.

    Currently RED. With `component: ac-store` neither validator recognises the
    record as a package-surface AC, so nothing in the combined output names the
    package surface: validate_ac_schema.py reports only the
    additionalProperties violation and validate_ac.py exits 0.
    """
    path = write_ac_yaml(
        tmp_path,
        "ACS-999.yaml",
        base_ac_record(
            component="ac-store",
            package_surface=True,
            it_requirements="A plain string implementation note.",
        ),
    )

    text = refusal_text(path)

    assert states_structured_spec_obligation(text), (
        "the refusal must name it_requirements, name the package surface, and "
        "say the spec must be structured/an object. Combined validator output "
        f"was:\n{text}"
    )


@pytest.mark.parametrize("component", _COMPONENTS)
@pytest.mark.parametrize("assigned_agent", ["python-coder", "llm-expert"])
@pytest.mark.parametrize("declaration", [{}, {"package_surface": False}], ids=["absent", "false"])
def test_undeclared_record_is_never_refused_on_the_spec_ground(
    component, assigned_agent, declaration
):
    # covers: ACS-100i-6
    """ACS-100i-6 s2: a record that does not declare a package surface — field
    absent or explicitly false — must not be refused for lacking a structured
    spec, whatever its agent, `component` or `components` values.

    Currently RED for `python-coder` + `build_pipeline` / `build-orchestration`:
    the proxy trigger fires there and demands the object form. It is precisely
    those 243 store records the narrowing must release.
    """
    record = base_ac_record(
        component=component,
        assigned_agent=assigned_agent,
        it_requirements=["A list", "of requirement strings"],
        **declaration,
    )

    result = verdict(record)

    assert not result.refused_on_package_surface_rule, (
        f"an undeclared record (agent={assigned_agent}, component={component}, "
        f"declaration={declaration or 'absent'}) must not be refused for "
        "lacking a structured implementation spec, but these messages are "
        f"attributable to that rule: {list(result.rule_messages)}"
    )


def test_assigned_agent_alone_never_decides_the_verdict():
    # covers: ACS-100i-6
    """ACS-100i-6 s3: two records identical except for `assigned_agent`, neither
    declaring a package surface, must receive the same verdict.

    Currently RED: with `component: build-orchestration` the python-coder record
    is refused by the proxy trigger and the llm-expert record is accepted.
    """
    common = {
        "component": "build-orchestration",
        "components": ["build_orchestration"],
        "it_requirements": ["A list", "of requirement strings"],
    }
    coder = verdict(base_ac_record(assigned_agent="python-coder", **common))
    author = verdict(base_ac_record(assigned_agent="llm-expert", **common))

    assert coder.messages == author.messages, (
        "the assigned agent alone must never change the verdict; "
        f"python-coder produced {list(coder.messages)} while llm-expert "
        f"produced {list(author.messages)}"
    )


def test_undeclared_build_record_is_accepted_by_the_real_cli(tmp_path):
    # covers: ACS-100i-6
    """ACS-100i-6 s2, end-to-end through the shipped entry point.

    Reachability floor: the in-memory verdict helpers prove the schema is right;
    this proves the behaviour is reachable through the CLI a human or hook
    actually runs. A python-coder record in the build-orchestration namespace
    that declares no package surface must exit 0.

    Currently RED — validate_ac_schema.py exits 1 on exactly this shape today.
    """
    path = write_ac_yaml(
        tmp_path,
        "ACS-999.yaml",
        base_ac_record(
            component="build-orchestration",
            components=["build_orchestration"],
            assigned_agent="python-coder",
            it_requirements=["A list", "of requirement strings"],
        ),
    )

    run = run_cli(SCHEMA_VALIDATOR_CLI, str(path))

    assert run.returncode == 0, (
        "an undeclared python-coder record in the build-orchestration "
        f"namespace must pass the shipped validator; exit={run.returncode}\n"
        f"{run.output}"
    )


def test_attribution_helper_is_not_vacuous():
    # covers: ACS-100i-6
    """Guard on this module's own instrument, not on production behaviour.

    Every "refused on this ground" assertion above is computed by deleting the
    schema's top-level if/then and diffing the messages. If a future edit
    removes that block entirely instead of narrowing it, the attribution would
    be empty for every record and the whole module would pass vacuously.

    Currently GREEN by design, and must stay green after the narrowing: the
    rule is narrowed, not deleted.
    """
    assert top_level_rule_is_present(), (
        "config/ac_store_schema.json no longer has a top-level if/then pair. "
        "ACS-100i-6 narrows that rule to key on `package_surface`; it does not "
        "delete it. With the block gone, rule attribution is empty for every "
        "record and every ACS-100i-6/-7 assertion becomes vacuous."
    )
