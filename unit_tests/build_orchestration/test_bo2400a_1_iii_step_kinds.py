"""
MODULE: unit_tests/build_orchestration/test_bo2400a_1_iii_step_kinds.py
GOAL: RED failing tests for BO-2400a-1-iii — the agent registry schema defines
      step_kinds once, and the registry gate that actually runs (not just the
      schema) rejects an unknown or duplicate kind by name, on both the
      commit-time path and the build.py --validate-only path, via one shared
      implementation and one shared reader.
TICKET: none (hand-driven build; AC YAML is the spec) — see
    docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400a-1-iii.yaml

ASSUMED PRODUCTION API (does not exist yet — python-coder must implement this
shape; see _bo2400a1iii_fixtures.py's module docstring for the full rationale):
  - config/agent_registry.schema.json: definitions.agent.properties.step_kinds
    = {"type": "array", "uniqueItems": true,
       "items": {"enum": ["reads_store", "changes_store",
                           "changes_repository", "publishes"]}}
    NOT added to definitions.agent.required.
  - scripts/registry_validator.py gains:
      * get_agent_step_kinds(agent: dict) -> frozenset[str]
        (the one shared reader; absent key and [] both read as frozenset())
      * a step_kinds check wired into validate_agent_registry(package_root),
        reading the allowed-kinds enum from
        package_root/config/agent_registry.schema.json at run time (never a
        hard-coded copy), appending one human-readable error string per
        unknown or duplicated kind that names both the kind and the agent id.
  - This is the ONE implementation reused by both real entry points:
    scripts/commit_guardian/check_agent_registry.py (commit-time gate, via
    `from registry_validator import validate_agent_registry`) and
    scripts/build.py's `_validate_all` -> `validate_agent_registry` (the
    --validate-only path). Neither path may hold a second copy of the check.

Every fixture registry/schema below is built via json.dump from a real,
loaded copy of the shipped schema/registry (never a hand-typed literal) —
see _bo2400a1iii_fixtures.py for the Fixture Authenticity Rule rationale.

RED BASELINE (empirically confirmed before writing this docstring, by running
each fixture directly against the current, unmodified worktree code):
  - validate_agent_registry() returns [] for every step_kinds scenario today
    (no step_kinds check exists yet).
  - get_agent_step_kinds does not exist (ImportError).
  - definitions.agent.properties has no 'step_kinds' key (KeyError on direct
    lookup).
  - `build.py --validate-only` against a fixture package with an unknown-kind
    entry exits 0 today, and "deploys" never appears in its output.
  - The real, unmodified check_agent_registry.py, run against a real git repo
    with the same fixture staged at leafcutter/config/agent_registry.json,
    exits 0 today, and "deploys" never appears in its output.
See the test-writer report for the exact command/output transcripts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TEST_DIR = Path(__file__).resolve().parent
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))

import _bo2400a1iii_fixtures as fx  # noqa: E402

from registry_validator import validate_agent_registry  # noqa: E402
from step_kinds_validator import check_step_kinds  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Schema defines step_kinds as an optional, unique-item, 4-value enum array
# ---------------------------------------------------------------------------


def test_schema_defines_step_kinds_as_optional_unique_enum_array():
    # covers: BO-2400a-1-iii
    # angle: criterion
    """config/agent_registry.schema.json's definitions.agent.properties.step_kinds
    must be an array with uniqueItems: true and an enum of exactly the four
    known kinds, and step_kinds must NOT be in definitions.agent.required
    (must_catch: step_kinds made required would reject every existing entry
    that has never set it).
    """
    schema = fx.load_real_schema()
    agent_def = schema["definitions"]["agent"]

    assert "step_kinds" in agent_def["properties"], (
        "definitions.agent.properties.step_kinds is missing — the schema does "
        "not define step_kinds at all yet."
    )
    step_kinds_def = agent_def["properties"]["step_kinds"]

    assert step_kinds_def.get("type") == "array", (
        f"step_kinds must be type 'array', got {step_kinds_def.get('type')!r}"
    )
    assert step_kinds_def.get("uniqueItems") is True, (
        "step_kinds must set uniqueItems: true so a duplicate kind is a schema "
        "violation, not just a gate-level check."
    )
    actual_enum = step_kinds_def.get("items", {}).get("enum")
    assert actual_enum is not None, "step_kinds.items.enum is missing."
    assert set(actual_enum) == set(fx.KNOWN_KINDS), (
        f"step_kinds enum must be exactly {sorted(fx.KNOWN_KINDS)}, "
        f"got {sorted(actual_enum)!r}"
    )

    # must_catch: step_kinds made required would reject every existing entry.
    assert "step_kinds" not in agent_def.get("required", []), (
        "step_kinds must NOT be in definitions.agent.required — it is optional. "
        "Making it required would reject every agent entry that predates this AC."
    )


# ---------------------------------------------------------------------------
# 2. Each known kind (and all four together) is accepted by the gate, and
#    read back correctly by the shared reader.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kinds",
    [[k] for k in fx.KNOWN_KINDS] + [list(fx.KNOWN_KINDS)],
    ids=[*fx.KNOWN_KINDS, "all-four"],
)
def test_registry_gate_accepts_each_known_step_kind(tmp_path, kinds):
    # covers: BO-2400a-1-iii
    # angle: criterion
    """A fixture registry entry listing any one of the four known kinds, and
    one listing all four, must pass validate_agent_registry() with no
    step_kinds-related error, and the shared reader must read the kinds back
    exactly.

    Import of get_agent_step_kinds fails today (ImportError) — this is the
    stronger assertion that keeps this test genuinely red before
    implementation: validate_agent_registry() alone already returns no error
    for any step_kinds value today (no check exists yet), so "accepted" is
    trivially true without it; requiring the shared reader to exist and agree
    is what the AC's "accepted, and read as declaring" wording actually needs.
    """
    from registry_validator import get_agent_step_kinds  # noqa: E402  (asserted to fail today)

    agent = fx.make_agent(step_kinds=list(kinds))
    pkg = fx.build_min_package(tmp_path, [agent])

    errors = validate_agent_registry(pkg)
    step_kinds_errors = [e for e in errors if "step_kinds" in e or "fixture-agent" in e]
    assert step_kinds_errors == [], (
        f"Expected no step_kinds-related errors for kinds={kinds!r}, got: {step_kinds_errors}"
    )
    assert get_agent_step_kinds(agent) == frozenset(kinds), (
        f"get_agent_step_kinds() must read back exactly {frozenset(kinds)!r}"
    )


# ---------------------------------------------------------------------------
# 3. Unknown kind ('deploys') is rejected by the commit-time registry gate,
#    naming both the kind and the agent id.
# ---------------------------------------------------------------------------


def test_unknown_step_kind_is_rejected_by_the_registry_gate_naming_kind_and_agent(tmp_path):
    # covers: BO-2400a-1-iii
    # angle: failure
    """Reachability/entry-point note: this test invokes the REAL, unmodified
    scripts/commit_guardian/check_agent_registry.py (the check-agent-registry
    hook's own script) as a subprocess against a REAL git repo with the
    fixture registry REALLY staged — "the way the hook does", per this
    ticket's own instructions, rather than calling validate_agent_registry()
    in-process. See _bo2400a1iii_fixtures.build_git_fixture_repo /
    run_check_agent_registry for exactly how package_root and staging are
    reproduced.

    must_catch:
      - the enum is added to the schema file only, and no running gate reads
        it (today's gap) -> this test fails today with returncode 0 and no
        'deploys' in the output, which is exactly that gap.
      - the rejection names only a JSON path (e.g. agents/0/step_kinds/1) and
        not the agent id -> asserting the literal substring 'fixture-agent'
        (not just 'deploys') catches that half-fix.
      - the gate keeps its own copy of the kind list, so it drifts from the
        schema -> covered by test_fifth_kind_added_to_schema_is_accepted_
        without_gate_edit, not duplicated here.
    """
    agent = fx.make_agent(step_kinds=["reads_store", "deploys"])
    repo = fx.build_git_fixture_repo(tmp_path, [agent])

    result = fx.run_check_agent_registry(repo)
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        "check_agent_registry.py must exit non-zero when an agent's step_kinds "
        f"contains an unknown kind. Got returncode={result.returncode}, "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    assert "deploys" in combined, (
        f"Expected the unknown kind 'deploys' named in the gate's output, got: {combined!r}"
    )
    assert "fixture-agent" in combined, (
        f"Expected the agent id 'fixture-agent' named in the gate's output, got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# 4. Unknown kind is ALSO rejected by build.py --validate-only (not just the
#    commit-time path) — proves it is one shared implementation, not two.
# ---------------------------------------------------------------------------


def test_unknown_step_kind_is_rejected_by_build_validate_only(tmp_path):
    # covers: BO-2400a-1-iii
    # angle: reachability
    """Reachability entry-point resolution: build.py resolves its own
    package_root as Path(__file__).resolve().parent.parent with no CLI
    override, so "pointed at a temporary fixture package" means copying the
    real scripts/, config/, templates/ trees into a tmp dir and invoking that
    copy's own scripts/build.py --validate-only as a real subprocess with
    real argv — see _bo2400a1iii_fixtures.build_full_package_copy /
    run_build_validate_only. Calling _validate_all() or
    validate_agent_registry() in-process would NOT satisfy this test's
    reachability angle: it would prove the checker function works, not that
    `build.py --validate-only` — the actual second entry point named by the
    AC — invokes it.

    must_catch: the check is wired into the commit hook only, and the build
    validation path never runs it -> this is exactly today's state: this
    fixture, run through the real build.py --validate-only CLI, exits 0 and
    'deploys' never appears in the output.
    """
    pkg = fx.build_full_package_copy(tmp_path)
    fx.append_agent_to_registry(pkg, fx.make_agent(step_kinds=["reads_store", "deploys"]))

    result = fx.run_build_validate_only(pkg, tmp_path / "target")
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        "build.py --validate-only must exit non-zero when the registry has an "
        f"unknown step_kinds value. Got returncode={result.returncode}\n"
        f"stdout tail: {result.stdout[-1000:]!r}\nstderr tail: {result.stderr[-1000:]!r}"
    )
    assert "deploys" in combined, (
        f"Expected 'deploys' named in build.py --validate-only output, got tail: {combined[-1000:]!r}"
    )
    assert "fixture-agent" in combined, (
        f"Expected 'fixture-agent' named in build.py --validate-only output, got tail: {combined[-1000:]!r}"
    )


# ---------------------------------------------------------------------------
# 5. Duplicate kind is rejected, naming the kind and the agent.
# ---------------------------------------------------------------------------


def test_duplicate_step_kind_is_rejected_naming_kind_and_agent(tmp_path):
    # covers: BO-2400a-1-iii
    # angle: boundary
    """must_catch: the gate checks membership only and ignores uniqueItems ->
    a gate that only validates each kind is one of the four known values
    (membership) would accept ["publishes", "publishes"], since both entries
    are individually valid kinds; this test requires the DUPLICATE itself to
    be rejected, which only a uniqueItems-aware check catches.
    """
    agent = fx.make_agent(step_kinds=["publishes", "publishes"])
    pkg = fx.build_min_package(tmp_path, [agent])

    errors = validate_agent_registry(pkg)
    matching = [e for e in errors if "publishes" in e and "fixture-agent" in e]
    assert matching, (
        "Expected an error naming both the duplicated kind 'publishes' and the "
        f"agent id 'fixture-agent'. Got errors: {errors}"
    )


# ---------------------------------------------------------------------------
# 6. A fifth kind added to a temporary schema copy is accepted without
#    editing the gate; the same entry is rejected against the shipped schema.
# ---------------------------------------------------------------------------


def test_fifth_kind_added_to_schema_is_accepted_without_gate_edit(tmp_path):
    # covers: BO-2400a-1-iii
    # angle: discrimination
    """must_catch: the gate holds its own list of four kinds (a gate like that
    passes test_unknown_step_kind_is_rejected_by_the_registry_gate_naming_kind_
    and_agent and test_duplicate_step_kind_is_rejected_naming_kind_and_agent,
    but fails THIS one) -> this test is the one that discriminates "reads the
    schema at run time" from "copies the schema's four values into the gate's
    own source", by adding a fifth value to a schema COPY the gate's source is
    never touched for.

    fx.schema_with_extra_kind() raises KeyError today (no step_kinds
    definition exists yet in the real schema to mutate) — that is this test's
    honest red signal, not a fixture bug.
    """
    mutated_schema = fx.schema_with_extra_kind("fixture_kind")
    agent = fx.make_agent(step_kinds=["fixture_kind"])

    mutated_pkg = fx.build_min_package(tmp_path / "mutated", [agent], schema=mutated_schema)
    registry_validator_src_before = (fx.REPO_ROOT / "scripts" / "registry_validator.py").read_bytes()

    errors_against_mutated_schema = validate_agent_registry(mutated_pkg)
    matching = [e for e in errors_against_mutated_schema if "fixture_kind" in e or "fixture-agent" in e]
    assert matching == [], (
        "A 5th kind added only to a temporary schema copy must be accepted "
        f"without the gate's own source being edited. Got errors: {errors_against_mutated_schema}"
    )

    registry_validator_src_after = (fx.REPO_ROOT / "scripts" / "registry_validator.py").read_bytes()
    assert registry_validator_src_before == registry_validator_src_after, (
        "validate_agent_registry() must not have modified its own source file "
        "while accepting the temporary schema copy's 5th kind."
    )

    # The same entry, run against the REAL shipped schema (no fixture_kind), must
    # still be rejected.
    shipped_pkg = fx.build_min_package(tmp_path / "shipped", [agent])
    errors_against_shipped_schema = validate_agent_registry(shipped_pkg)
    matching_shipped = [
        e for e in errors_against_shipped_schema if "fixture_kind" in e and "fixture-agent" in e
    ]
    assert matching_shipped, (
        "The same ['fixture_kind'] entry must be rejected against the shipped "
        f"(unmodified) schema. Got errors: {errors_against_shipped_schema}"
    )


# ---------------------------------------------------------------------------
# 7. Absent step_kinds and [] are both valid and both read as no kinds.
# ---------------------------------------------------------------------------


def test_absent_and_empty_step_kinds_are_valid_and_read_as_no_kinds(tmp_path):
    # covers: BO-2400a-1-iii
    # angle: boundary
    """must_catch:
      - absent read as all kinds -> asserted via get_agent_step_kinds(...) ==
        frozenset() for the absent-key entry, not merely "no error".
      - [] rejected as invalid -> asserted via zero step_kinds-related errors
        for the entry that sets step_kinds: [].
    """
    from registry_validator import get_agent_step_kinds  # noqa: E402  (asserted to fail today)

    absent_agent = fx.make_agent(agent_id="fixture-agent-absent")
    empty_agent = fx.make_agent(agent_id="fixture-agent-empty", step_kinds=[])
    pkg = fx.build_min_package(tmp_path, [absent_agent, empty_agent])

    errors = validate_agent_registry(pkg)
    step_kinds_errors = [e for e in errors if "fixture-agent-absent" in e or "fixture-agent-empty" in e]
    assert step_kinds_errors == [], (
        f"Absent step_kinds and step_kinds: [] must both be valid. Got errors: {step_kinds_errors}"
    )

    assert get_agent_step_kinds(absent_agent) == frozenset(), (
        "Absent step_kinds must read as no kinds at all (empty set), not 'all kinds'."
    )
    assert get_agent_step_kinds(empty_agent) == frozenset(), (
        "step_kinds: [] must read as no kinds at all (empty set)."
    )


# ---------------------------------------------------------------------------
# 8. Verdict on fields OTHER than step_kinds is unchanged (scope guard).
# ---------------------------------------------------------------------------


def test_gate_verdict_on_other_fields_is_unchanged(tmp_path):
    # covers: BO-2400a-1-iii
    # angle: discrimination
    """must_catch: whole-registry schema validation switched on as a side
    effect -> a fixture agent with an invalid 'tier' value (schema enum
    violation unrelated to step_kinds) and NO step_kinds field must still
    produce zero errors, exactly as today, proving this AC did not newly
    switch on full-schema validation. The real, shipped registry must also
    still return zero errors (its current, empirically-confirmed baseline).

    NOTE: per this ticket's own rules, this test may legitimately pass both
    before and after the change — it is a scope guard, not a behavior being
    added. Labelled green-at-baseline in the report.
    """
    agent = fx.make_agent(tier="not_a_real_tier")  # no step_kinds field at all
    pkg = fx.build_min_package(tmp_path, [agent])

    errors = validate_agent_registry(pkg)
    assert errors == [], (
        "step_kinds validation must not incidentally switch on whole-schema "
        f"validation for unrelated fields like 'tier'. Got errors: {errors}"
    )

    shipped_errors = validate_agent_registry(fx.REPO_ROOT)
    assert shipped_errors == [], (
        "The real, shipped agent_registry.json must still pass "
        f"validate_agent_registry() with zero errors. Got: {shipped_errors}"
    )


# ---------------------------------------------------------------------------
# 9. The live gate and its packaged copy are in parity.
# ---------------------------------------------------------------------------


def test_live_and_packaged_registry_gate_copies_are_in_parity():
    # covers: BO-2400a-1-iii
    # angle: deployed
    """scripts/commit_guardian/check_agent_registry.py (the live, commit-time
    gate) and templates/scripts/commit_guardian/check_agent_registry.py (the
    copy an installed consumer project actually runs) must be byte-identical,
    so the step_kinds check this AC adds reaches installed projects too.

    NOTE: per this ticket's own rules, this test may legitimately pass both
    before and after the change (the two files are already byte-identical in
    this repo today). Labelled green-at-baseline in the report.
    """
    live_bytes = fx.CHECK_AGENT_REGISTRY_SCRIPT.read_bytes()
    packaged_bytes = fx.TEMPLATES_CHECK_AGENT_REGISTRY_SCRIPT.read_bytes()
    assert live_bytes == packaged_bytes, (
        f"{fx.CHECK_AGENT_REGISTRY_SCRIPT} and {fx.TEMPLATES_CHECK_AGENT_REGISTRY_SCRIPT} "
        "must be byte-identical so the step_kinds check ships to installed projects."
    )


# ---------------------------------------------------------------------------
# 10. Regression guard: an unreadable/invalid/incomplete schema must fail
#     CLOSED (an error), never open (silently allow every kind).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode",
    ["missing", "invalid_json", "no_step_kinds_def"],
    ids=["schema_missing", "schema_invalid_json", "schema_missing_step_kinds_def"],
)
def test_unreadable_or_incomplete_schema_fails_closed_not_open(tmp_path, mode):
    # covers: BO-2400a-1-iii
    # angle: failure
    """Regression guard for it_requirements' fail-closed clause: "The gate
    does not fail open on a step_kinds violation. If the schema itself
    cannot be read or has no step_kinds definition, the gate reports that as
    an error. It never silently treats every kind as allowed."

    This test is EXPECTED TO PASS against the current implementation —
    step_kinds_validator.check_step_kinds() already returns
    [f"step_kinds validation error: {load_error}"] (never []) when
    _load_allowed_step_kinds() fails for any of the three reasons
    parametrized here. It exists because none of the other 9 tests in this
    file ever exercise a broken schema — they all use either the real,
    valid, shipped schema or a validly-mutated copy — so a fail-open
    regression in check_step_kinds() would previously slip through this
    file's entire suite undetected. It was proven to have teeth by manually
    mutating check_step_kinds() to `return []` on a load failure: with that
    mutation in place, this test fails (AssertionError: errors == []) for
    all three parametrized cases, while the other 9 tests in this file keep
    passing (they never hit the load-failure branch). See the test-writer
    report for the mutation transcript; the mutation itself was reverted and
    byte-compared back to the original before this file was finalized.

    Both the direct check_step_kinds() call and the validate_agent_registry()
    wiring are asserted, per the coordinator's "(and/or)" instruction — this
    both pins the unit-level contract and proves it is not lost on the way
    into the wired-up gate.
    """
    agent = fx.make_agent(step_kinds=["reads_store"])
    pkg = fx.build_package_with_broken_schema(tmp_path, [agent], mode)

    direct_errors = check_step_kinds([agent], pkg)
    assert direct_errors != [], (
        f"check_step_kinds() must fail CLOSED (non-empty errors) for a "
        f"{mode!r} schema, not silently allow every kind. Got: {direct_errors!r}"
    )
    assert any("step_kinds" in e for e in direct_errors), (
        f"The fail-closed error must mention 'step_kinds'. Got: {direct_errors!r}"
    )

    wired_errors = validate_agent_registry(pkg)
    assert wired_errors != [], (
        f"validate_agent_registry() must also fail CLOSED for a {mode!r} schema "
        f"(not swallow the step_kinds error). Got: {wired_errors!r}"
    )
    assert any("step_kinds" in e for e in wired_errors), (
        f"The fail-closed error surfaced through validate_agent_registry() must "
        f"mention 'step_kinds'. Got: {wired_errors!r}"
    )
