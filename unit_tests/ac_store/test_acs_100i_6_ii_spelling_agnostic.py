"""
MODULE: test_acs_100i_6_ii_spelling_agnostic
GOAL: Pin ACS-100i-6-ii — how a record spells its `component` must stop
    changing whether the structured-spec obligation applies, and the obligation
    must follow an explicit declaration into ANY namespace.
BUSINESS CONTEXT: `component` is the AC-store namespace key from
    docs/acceptance-criteria/index.yaml, where the namespace is declared as
    `build-pipeline` (kebab). Today's trigger enum lists `build_pipeline`
    (underscore) — a docs/components.json graph id on a different axis.
    Measured on this worktree at 9b16d013: 440 records carry
    `component: build-pipeline` and are invisible to the rule; 65 spelling it
    `build_pipeline` are caught. 239 python-coder records sit in the kebab
    namespace and 215 of those carry no structured spec — the gate has never
    once fired on them.
ARCHITECTURE: Behavioral. This module is the discriminating case for the whole
    tree: an implementation that narrows the trigger but keeps it keyed on a
    spelling enum (for instance by "fixing" the enum to list both spellings)
    passes ACS-100i-6's headline tests and FAILS here. The obligation must not
    consult `component` in either direction.

AC: ACS-100i-6-ii (docs/acceptance-criteria/ac-store/
    ACS-100-structured-requirements/ACS-100i-6-ii.yaml)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acs_100i_support import (  # noqa: E402
    SCHEMA_VALIDATOR_CLI,
    base_ac_record,
    run_cli,
    verdict,
    write_ac_yaml,
)

_UNDERSCORE = "build_pipeline"
_KEBAB = "build-pipeline"


def _pair(**overrides):
    """Return two records byte-identical except for the `component` spelling."""
    return (
        base_ac_record(component=_UNDERSCORE, **overrides),
        base_ac_record(component=_KEBAB, **overrides),
    )


def test_both_component_spellings_are_accepted_when_undeclared():
    # covers: ACS-100i-6-ii
    """ACS-100i-6-ii s1: two records identical except that one spells the
    namespace `build_pipeline` and the other `build-pipeline`, both assigned to
    python-coder, neither declaring a package surface — both must be accepted
    and the two verdicts must be identical.

    Currently RED. The underscore record is refused because the trigger enum
    lists that spelling; the kebab record — the spelling 440 real records
    actually use — sails through. Same record, different spelling, opposite
    verdict.
    """
    underscore, kebab = _pair(
        assigned_agent="python-coder",
        it_requirements=["A list", "of requirement strings"],
    )

    underscore_result = verdict(underscore)
    kebab_result = verdict(kebab)

    assert underscore_result.messages == kebab_result.messages, (
        "the two spellings must produce identical verdicts; "
        f"{_UNDERSCORE} produced {list(underscore_result.messages)} while "
        f"{_KEBAB} produced {list(kebab_result.messages)}"
    )
    assert not underscore_result.refused, (
        "neither record declares a package surface, so both must be accepted; "
        f"{_UNDERSCORE} was refused with {list(underscore_result.messages)}"
    )
    assert not kebab_result.refused, (
        "neither record declares a package surface, so both must be accepted; "
        f"{_KEBAB} was refused with {list(kebab_result.messages)}"
    )


def test_both_component_spellings_are_refused_identically_when_declared(tmp_path):
    # covers: ACS-100i-6-ii
    """ACS-100i-6-ii s2: the same pair, both now carrying
    `package_surface: true` and both supplying implementation requirements as a
    list of strings, must both be refused, with refusal messages identical apart
    from the file path.

    Currently RED twice over. In-memory, the underscore record picks up an extra
    trigger-attributable error the kebab record does not, so the message sets
    differ; and neither refusal is attributable to the declaration — today the
    declaration produces nothing but an "additional properties are not allowed"
    error, which is not a refusal on this ground.
    """
    underscore, kebab = _pair(
        assigned_agent="python-coder",
        package_surface=True,
        it_requirements=["A list", "of requirement strings"],
    )

    underscore_result = verdict(underscore)
    kebab_result = verdict(kebab)

    assert underscore_result.refused and kebab_result.refused, (
        "both declaring records must be refused; "
        f"{_UNDERSCORE} refused={underscore_result.refused}, "
        f"{_KEBAB} refused={kebab_result.refused}"
    )
    assert underscore_result.messages == kebab_result.messages, (
        "the two refusals must be identical; "
        f"{_UNDERSCORE} produced {list(underscore_result.messages)} while "
        f"{_KEBAB} produced {list(kebab_result.messages)}"
    )
    assert underscore_result.refused_on_package_surface_rule, (
        "both must be refused BECAUSE they declared a package surface, not for "
        "some incidental reason; no message was attributable to the rule: "
        f"{list(underscore_result.messages)}"
    )

    # Through the shipped CLI: the refusal text must differ only by file path.
    underscore_path = write_ac_yaml(tmp_path / "u", "ACS-999.yaml", underscore)
    kebab_path = write_ac_yaml(tmp_path / "k", "ACS-999.yaml", kebab)
    underscore_out = run_cli(SCHEMA_VALIDATOR_CLI, str(underscore_path)).output
    kebab_out = run_cli(SCHEMA_VALIDATOR_CLI, str(kebab_path)).output

    normalised_underscore = underscore_out.replace(str(underscore_path), "<AC>")
    normalised_kebab = kebab_out.replace(str(kebab_path), "<AC>")
    assert normalised_underscore == normalised_kebab, (
        "with the file paths normalised away the two refusals must be "
        f"byte-identical.\n{_UNDERSCORE}:\n{normalised_underscore}\n"
        f"{_KEBAB}:\n{normalised_kebab}"
    )


def test_declaration_is_honoured_in_an_unrelated_namespace():
    # covers: ACS-100i-6-ii
    """ACS-100i-6-ii s3: a record declaring `package_surface: true` whose
    `component` is a namespace unrelated to the build — `ac-store` — and whose
    implementation requirements are a list of strings must be refused. A package
    surface can be registered from any component, so the obligation follows the
    declaration into any namespace.

    Currently RED and never covered before: the trigger consults `component`, so
    a package surface registered from outside the two build namespaces has never
    been checked at all. This is the positive half of the same point as s1 — once
    the trigger is a declaration, `component` stops being consulted in EITHER
    direction.
    """
    record = base_ac_record(
        component="ac-store",
        package_surface=True,
        it_requirements=["A list", "of requirement strings"],
    )

    result = verdict(record)

    assert result.refused_on_package_surface_rule, (
        "a declared package surface in the unrelated `ac-store` namespace must "
        "be refused for lacking a structured spec; no message was attributable "
        f"to that rule. All messages: {list(result.messages)}"
    )


def test_component_spelling_never_changes_the_verdict_on_its_own():
    # covers: ACS-100i-6-ii
    """ACS-100i-6-ii, generalised: `component` must not be consulted by the
    obligation for ANY namespace pair, declared or undeclared.

    This is the guard against the wrong-but-plausible fix — narrowing the
    trigger while keeping it keyed on a spelling enum, e.g. by adding
    `build-pipeline` to the enum so both spellings behave "the same". That fix
    makes the two build spellings agree and still refuses `ac-store`
    differently, so this test separates it from the right one.
    """
    namespaces = ["ac-store", "build-pipeline", "build_pipeline", "build-orchestration"]
    for declared in (False, True):
        extra = {"package_surface": True} if declared else {}
        verdicts = {
            namespace: verdict(
                base_ac_record(
                    component=namespace,
                    assigned_agent="python-coder",
                    it_requirements=["A list", "of requirement strings"],
                    **extra,
                )
            ).messages
            for namespace in namespaces
        }
        distinct = set(verdicts.values())
        assert len(distinct) == 1, (
            f"with package_surface {'declared' if declared else 'absent'}, all "
            "namespaces must receive the same verdict — the obligation must not "
            f"read `component` at all. Got: "
            + "; ".join(f"{k}={list(v)}" for k, v in verdicts.items())
        )
