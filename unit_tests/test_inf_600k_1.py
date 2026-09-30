"""
MODULE: test_inf_600k_1
GOAL: TDD red-baseline tests for AC INF-600k-1 -- "A workflow filename in
    spawned_by passes registry validation as an external caller". Test 2
    (`test_nonexistent_workflow_filename_is_rejected_by_both_checks_as_unknown_agent`)
    also covers INF-600k-3's negative guarantee, per the 2026-09-28 IT-PO
    amendment's test_spec.
BUSINESS CONTEXT: On origin/main 2c000a9e, `_EXTERNAL_CALLERS = {"user",
    "finalize-feature.js"}` is a closed literal set duplicated in both
    scripts/registry_validator.py:47 and
    scripts/commit_guardian/hooks/check_agent_spawn_consistency.py:40
    (packaged copy: templates/scripts/commit_guardian/hooks/; deployed
    copy: .leafcutter/scripts/commit_guardian/hooks/). Every workflow
    filename other than the two literals -- e.g. "fast-lane-ship.js" -- is
    rejected as an unknown agent, which is why command-step-runner had to
    ship with spawned_by: ["user"] instead of naming the workflow that
    actually spawns it (see BO-2400a-1-i). This AC relaxes both checks to
    also recognize any filename that really exists under the package's
    templates/workflows-js/ directory, derived from disk rather than from a
    second hand-maintained list, WITHOUT weakening the genuine-unknown-agent
    guarantee INF-600k-3 pins.
ARCHITECTURE: Every test below invokes the REAL entry points, never an
    in-memory unit of either file's internals:
      - registry_validator.validate_agent_registry(package_root) -- the
        build-time / check-agent-registry path -- called directly against a
        tmp package root (config/agent_registry.json +
        templates/workflows-js/*.js, real files copied from this repo where
        a real counterpart exists, per Fixture Authenticity Rule 2h.2).
      - scripts/commit_guardian/hooks/check_agent_spawn_consistency.py --
        the pre-commit hook -- run as a REAL subprocess against a tmp git
        repo standing in for a package root, with the registry staged via
        `git add`. Today, the hook's own `_check_asymmetric_spawns()` Pass 2
        explicitly skips (does not error on) any spawned_by entry that is
        not a registry agent id ("Unknown agents are caught by other
        validators"), so the observable channel through which the hook
        currently rejects an unrecognized spawned_by name is its
        card<->registry mirror check (`_check_card_registry_mirror`,
        Direction 2b: "registry says X spawns me, but the card does not
        show it"). Every hook-side fixture below therefore ships a matching
        docs/agents/cards/<id>.card.md whose mermaid diagram deliberately
        omits a dispatch edge for the external name under test -- exactly
        how a REAL generated card looks, since workflows and the literal
        'user' trigger are never drawn as agent nodes.

    Shared fixture helpers live in unit_tests/_inf_600k_1_fixtures.py (this
    file was split into three per check-file-size's flat 400-content-line
    cap on new files -- a pure move, see that module's own DECISION HISTORY
    and unit_tests/test_inf_600k_1_regressions.py for the sibling file
    holding the post-review regression tests).

CONTRACT ASSUMED (test-writer's suggested seam for python-coder; NOT
    exercised directly by any test below, since every test instead asserts
    each real entry point's OBSERVABLE accept/reject verdict -- a stronger,
    implementation-agnostic proof per this AC's it_requirement #4): a small
    shared module, e.g. `scripts/agent_spawn_external_callers.py`, exposing
    `is_recognized_external_caller(name: str, package_root: Path) -> bool`
    (true for the literal "user" trigger or any filename present under
    `package_root/templates/workflows-js/`). `registry_validator.py` can
    import it directly. `check_agent_spawn_consistency.py` documents itself
    as "Standalone (no leafcutter-internal imports)" for portability to a
    deployed consumer layout with no `scripts/` package on the Python path;
    if importing the shared module breaks that constraint in some deployed
    layout, the it_requirement's own fallback applies instead: both files
    read the SAME data source (the literal 'user' trigger plus
    `templates/workflows-js/*.js` under the package root located by the
    GE-113c-1-iv / GE-113c-1-vi convention) rather than maintaining two
    independently-derived sets. `test_both_checks_classify_every_spawned_by_entry_identically`
    below pins the OUTCOME of that decision (identical verdicts), not its
    mechanism, so it stays valid regardless of which of the two shapes
    python-coder picks.

RED BASELINE (read before "fixing" any test that looks like it is failing
    for the wrong reason):
    - test_real_workflow_filename_in_spawned_by_is_accepted_by_both_checks:
      RED today (registry_validator rejects 'fast-lane-ship.js').
    - test_nonexistent_workflow_filename_is_rejected_by_both_checks_as_unknown_agent:
      GREEN today (nothing recognizes '*.js' yet, so the negative guarantee
      already holds; must stay green after the relaxation lands).
    - test_user_and_finalize_feature_remain_accepted: GREEN today (regression
      guard on the two pre-existing literals).
    - test_new_workflow_file_is_accepted_without_a_code_change: RED today
      (same reason as test 1, for 'brand-new-flow.js').
    - test_both_checks_classify_every_spawned_by_entry_identically: RED
      today ONLY for the `real_workflow_filename` parametrize id -- the two
      real entry points already disagree on it (registry rejects; the
      hook's asymmetric check silently accepts any non-registry name
      regardless of classification, while its card-mirror check currently
      rejects it) -- every other parametrize id is green today.
    - test_deployed_only_workflow_is_not_accepted_when_package_source_exists:
      GREEN today (no workflow-directory logic exists yet at all).
    - test_shipped_registry_validates_under_both_checks: GREEN today (this
      repo's registry lists no workflow filename other than the
      already-accepted 'finalize-feature.js').
    - test_spawn_consistency_hook_copies_are_in_parity: GREEN today (the two
      copies are already byte-identical prior to this ticket).

DECISION HISTORY
- 2026-09-28 [test-writer/INF-600k-1]: Initial authoring, hand-derived
    directly from the AC YAML's test_spec (8 entries) since this ticket was
    driven by hand with no ticket file. Test 2's must_catch is shared with
    INF-600k-3 per the test_spec's `covers` field.
- 2026-09-28 [test-writer/INF-600k-1]: Split shared fixture helpers out to
    unit_tests/_inf_600k_1_fixtures.py (check-file-size's flat 400-line cap
    on new files). Pure move: no test name, body, tag, or assertion changed.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from _inf_600k_1_fixtures import (
    HOOK_PATH,
    REAL_REGISTRY,
    REAL_WORKFLOWS_DIR,
    REPO_ROOT,
    TEMPLATE_HOOK_PATH,
    _card_text,
    _copy_real_workflow,
    _has_unknown_agent_error,
    _init_git_repo,
    _make_agent,
    _run_hook,
    _stage_all,
    _write_registry,
    _write_schema,
)

# _inf_600k_1_fixtures (imported above) puts scripts/ on sys.path.
import build_phases_lifecycle  # noqa: E402
import registry_validator  # noqa: E402
from template_compiler import inject_config  # noqa: E402

# ---------------------------------------------------------------------------
# Test 1 -- criterion
# ---------------------------------------------------------------------------


def test_real_workflow_filename_in_spawned_by_is_accepted_by_both_checks():
    # covers: INF-600k-1
    # angle: criterion
    """A real workflow filename ('fast-lane-ship.js') in an agent's
    spawned_by must be accepted -- not reported as an unknown agent -- by
    BOTH real entry points: registry_validator.validate_agent_registry()
    and the check_agent_spawn_consistency.py pre-commit hook run as a real
    subprocess. RED today: see module CONTRACT ASSUMED / RED BASELINE.
    """
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp)
        _write_schema(pkg)
        _write_registry(pkg, [_make_agent("spawner-agent", spawned_by=["fast-lane-ship.js"])])
        _copy_real_workflow(pkg / "templates" / "workflows-js", "fast-lane-ship.js")

        errors = registry_validator.validate_agent_registry(pkg)
        assert not _has_unknown_agent_error(errors, "fast-lane-ship.js"), (
            f"registry_validator must accept a real workflow filename; got errors: {errors}"
        )

    with tempfile.TemporaryDirectory() as tmp2:
        repo = Path(tmp2)
        _init_git_repo(repo)
        _write_registry(repo, [_make_agent("spawner-agent", spawned_by=["fast-lane-ship.js"])])
        _copy_real_workflow(repo / "templates" / "workflows-js", "fast-lane-ship.js")
        cards_dir = repo / "docs" / "agents" / "cards"
        cards_dir.mkdir(parents=True)
        (cards_dir / "spawner-agent.card.md").write_text(
            _card_text("spawner-agent"), encoding="utf-8"
        )
        _stage_all(repo)

        result = _run_hook(repo)
        assert result.returncode == 0, (
            f"hook must accept a real workflow filename in spawned_by; "
            f"exit={result.returncode} stderr={result.stderr!r}"
        )


# ---------------------------------------------------------------------------
# Test 2 -- failure (covers INF-600k-1 and INF-600k-3)
# ---------------------------------------------------------------------------


def test_nonexistent_workflow_filename_is_rejected_by_both_checks_as_unknown_agent():
    # covers: INF-600k-1
    # covers: INF-600k-3
    # angle: failure
    """A spawned_by entry with no matching registry agent and no matching
    workflow file ('nonexistent-flow.js') must still be reported as an
    unknown agent by both checks and fail the build -- the relaxation for
    real workflow filenames must never become a blanket accept of any
    '*.js' name (must_catch, shared with INF-600k-3's negative guarantee).
    Expected GREEN today (see module RED BASELINE) -- must stay green.
    """
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp)
        _write_schema(pkg)
        _write_registry(pkg, [_make_agent("spawner-agent", spawned_by=["nonexistent-flow.js"])])
        (pkg / "templates" / "workflows-js").mkdir(parents=True)  # exists, but empty

        errors = registry_validator.validate_agent_registry(pkg)
        assert _has_unknown_agent_error(errors, "nonexistent-flow.js"), (
            f"registry_validator must still reject a nonexistent workflow filename; got: {errors}"
        )

    with tempfile.TemporaryDirectory() as tmp2:
        repo = Path(tmp2)
        _init_git_repo(repo)
        _write_registry(repo, [_make_agent("spawner-agent", spawned_by=["nonexistent-flow.js"])])
        (repo / "templates" / "workflows-js").mkdir(parents=True)
        cards_dir = repo / "docs" / "agents" / "cards"
        cards_dir.mkdir(parents=True)
        (cards_dir / "spawner-agent.card.md").write_text(
            _card_text("spawner-agent"), encoding="utf-8"
        )
        _stage_all(repo)

        result = _run_hook(repo)
        assert result.returncode != 0, "hook must still reject a nonexistent workflow filename"
        assert "nonexistent-flow.js" in result.stderr


# ---------------------------------------------------------------------------
# Test 3 -- boundary
# ---------------------------------------------------------------------------


def test_user_and_finalize_feature_remain_accepted():
    # covers: INF-600k-1
    # angle: boundary
    """The two pre-existing literal external triggers -- 'user' and
    'finalize-feature.js' -- must remain accepted after the relaxation.
    'user' must be accepted even when the workflow directory is empty (it
    is a literal trigger, never a workflow file, so acceptance must never
    depend on the workflows directory's contents). Expected GREEN today
    (regression guard on the two pre-existing literals).
    """
    # -- Scenario A: 'finalize-feature.js', with the real workflow file present.
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp)
        _write_schema(pkg)
        _write_registry(pkg, [_make_agent("agent-one", spawned_by=["finalize-feature.js"])])
        _copy_real_workflow(pkg / "templates" / "workflows-js", "finalize-feature.js")
        errors = registry_validator.validate_agent_registry(pkg)
        assert not _has_unknown_agent_error(errors, "finalize-feature.js")

    # -- Scenario B: 'user', with the workflows directory left deliberately empty.
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp)
        _write_schema(pkg)
        _write_registry(pkg, [_make_agent("agent-two", spawned_by=["user"])])
        (pkg / "templates" / "workflows-js").mkdir(parents=True)
        errors = registry_validator.validate_agent_registry(pkg)
        assert not _has_unknown_agent_error(errors, "user")

    # -- Hook side, both scenarios.
    for agent_id, spawner, workflow_file_exists in (
        ("agent-one", "finalize-feature.js", True),
        ("agent-two", "user", False),
    ):
        with tempfile.TemporaryDirectory() as tmp2:
            repo = Path(tmp2)
            _init_git_repo(repo)
            _write_registry(repo, [_make_agent(agent_id, spawned_by=[spawner])])
            if workflow_file_exists:
                _copy_real_workflow(repo / "templates" / "workflows-js", spawner)
            else:
                (repo / "templates" / "workflows-js").mkdir(parents=True)
            cards_dir = repo / "docs" / "agents" / "cards"
            cards_dir.mkdir(parents=True)
            (cards_dir / f"{agent_id}.card.md").write_text(_card_text(agent_id), encoding="utf-8")
            _stage_all(repo)

            result = _run_hook(repo)
            assert result.returncode == 0, (
                f"'{spawner}' must remain accepted; stderr={result.stderr!r}"
            )


# ---------------------------------------------------------------------------
# Test 4 -- discrimination
# ---------------------------------------------------------------------------


def test_new_workflow_file_is_accepted_without_a_code_change():
    # covers: INF-600k-1
    # angle: discrimination
    """A workflow filename that exists nowhere in the source code
    ('brand-new-flow.js') must be rejected while its file is absent, and
    accepted the moment the file is created on disk under
    templates/workflows-js/ -- with NEITHER check's source touched between
    the two runs. A literal-list fix (must_catch: 'fast-lane-ship.js added
    to a literal list instead of reading the workflow directory') would
    still reject 'brand-new-flow.js' after its file is created, because the
    name was never added to any list -- only a directory-read
    implementation passes both halves. RED today (same reason as test 1).
    """
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp)
        _write_schema(pkg)
        _write_registry(pkg, [_make_agent("spawner-agent", spawned_by=["brand-new-flow.js"])])
        (pkg / "templates" / "workflows-js").mkdir(parents=True)

        errors_before = registry_validator.validate_agent_registry(pkg)
        assert _has_unknown_agent_error(errors_before, "brand-new-flow.js"), (
            f"must reject before the file exists; got: {errors_before}"
        )

        (pkg / "templates" / "workflows-js" / "brand-new-flow.js").write_text(
            "// newly created workflow, never referenced in any literal list\n"
            "module.exports = {};\n",
            encoding="utf-8",
        )

        errors_after = registry_validator.validate_agent_registry(pkg)
        assert not _has_unknown_agent_error(errors_after, "brand-new-flow.js"), (
            f"must accept once the real file exists on disk; got: {errors_after}"
        )

    with tempfile.TemporaryDirectory() as tmp2:
        repo = Path(tmp2)
        _init_git_repo(repo)
        _write_registry(repo, [_make_agent("spawner-agent", spawned_by=["brand-new-flow.js"])])
        (repo / "templates" / "workflows-js").mkdir(parents=True)
        cards_dir = repo / "docs" / "agents" / "cards"
        cards_dir.mkdir(parents=True)
        (cards_dir / "spawner-agent.card.md").write_text(
            _card_text("spawner-agent"), encoding="utf-8"
        )
        _stage_all(repo)

        result_before = _run_hook(repo)
        assert result_before.returncode != 0, "hook must reject before the file exists"

        (repo / "templates" / "workflows-js" / "brand-new-flow.js").write_text(
            "// newly created workflow, never referenced in any literal list\n"
            "module.exports = {};\n",
            encoding="utf-8",
        )
        # No re-staging: classification must read the real workflow directory on
        # disk, not the git index, per the AC's "derived from files on disk" rule.

        result_after = _run_hook(repo)
        assert result_after.returncode == 0, (
            f"hook must accept once the real file exists; stderr={result_after.stderr!r}"
        )


# ---------------------------------------------------------------------------
# Test 5 -- seam (parity between the two real entry points)
# ---------------------------------------------------------------------------

_PARITY_CASES = [
    pytest.param("helper-agent", True, "accept", id="registry_agent_id"),
    pytest.param("user", False, "accept", id="literal_user_trigger"),
    pytest.param("fast-lane-ship.js", False, "accept", id="real_workflow_filename"),
    pytest.param("totally-missing-flow.js", False, "reject", id="missing_workflow_filename"),
    pytest.param("totally-bogus-name", False, "reject", id="arbitrary_non_agent_name"),
]


@pytest.mark.parametrize("case_value, dispatch_edge_shown, expected", _PARITY_CASES)
def test_both_checks_classify_every_spawned_by_entry_identically(case_value, dispatch_edge_shown, expected):
    # covers: INF-600k-1
    # angle: seam
    """registry_validator.validate_agent_registry() and the REAL
    check_agent_spawn_consistency.py hook must reach the SAME accept/reject
    verdict for every kind of spawned_by entry: a real registry agent id,
    the literal 'user' trigger, a real workflow filename, a missing
    workflow filename, and an arbitrary non-agent name. RED today ONLY for
    'real_workflow_filename' -- see module RED BASELINE for why the two
    real entry points currently disagree on it.
    """
    agents = [_make_agent("agent-a", spawned_by=[case_value])]
    if case_value == "helper-agent":
        agents.append(_make_agent("helper-agent", spawn_allowlist=["agent-a"]))

    # -- registry_validator side --
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp)
        _write_schema(pkg)
        _write_registry(pkg, agents)
        if case_value == "fast-lane-ship.js":
            _copy_real_workflow(pkg / "templates" / "workflows-js", case_value)
        else:
            (pkg / "templates" / "workflows-js").mkdir(parents=True)

        errors = registry_validator.validate_agent_registry(pkg)
        registry_verdict = "reject" if _has_unknown_agent_error(errors, case_value) else "accept"

    # -- hook side --
    with tempfile.TemporaryDirectory() as tmp2:
        repo = Path(tmp2)
        _init_git_repo(repo)
        _write_registry(repo, agents)
        if case_value == "fast-lane-ship.js":
            _copy_real_workflow(repo / "templates" / "workflows-js", case_value)
        else:
            (repo / "templates" / "workflows-js").mkdir(parents=True)
        cards_dir = repo / "docs" / "agents" / "cards"
        cards_dir.mkdir(parents=True)
        dispatched_by = (case_value,) if dispatch_edge_shown else ()
        (cards_dir / "agent-a.card.md").write_text(
            _card_text("agent-a", dispatched_by=dispatched_by), encoding="utf-8"
        )
        _stage_all(repo)

        result = _run_hook(repo)
        hook_verdict = "accept" if result.returncode == 0 else "reject"

    assert registry_verdict == expected, (
        f"[{case_value}] registry_validator verdict={registry_verdict}, expected={expected}"
    )
    assert hook_verdict == expected, (
        f"[{case_value}] hook verdict={hook_verdict}, expected={expected}; stderr={result.stderr!r}"
    )
    assert registry_verdict == hook_verdict, (
        f"[{case_value}] checks disagree: registry={registry_verdict} hook={hook_verdict}"
    )


# ---------------------------------------------------------------------------
# Test 6 -- boundary (source-of-truth authority)
# ---------------------------------------------------------------------------


def test_deployed_only_workflow_is_not_accepted_when_package_source_exists():
    # covers: INF-600k-1
    # angle: boundary
    """A workflow filename that exists ONLY in .claude/workflows/ (the
    gitignored build output) and NOT in templates/workflows-js/ (the
    authoritative package source per docs/reference/workflow-constraints.md
    and it_requirement #3) must still be rejected as an unknown agent when
    the package source directory is present -- the source directory is the
    sole authority whenever it exists; the deployed directory is a fallback
    only when the source is entirely absent. Expected GREEN today (no
    workflow-directory logic of any kind exists yet); guards against a
    tempting-but-wrong fix that checks both directories without the source
    directory's precedence.
    """
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp)
        _write_schema(pkg)
        _write_registry(pkg, [_make_agent("spawner-agent", spawned_by=["stale-flow.js"])])
        (pkg / "templates" / "workflows-js").mkdir(parents=True)  # source present, empty
        deployed_dir = pkg / ".claude" / "workflows"
        deployed_dir.mkdir(parents=True)
        (deployed_dir / "stale-flow.js").write_text(
            "// stale deployed-only copy -- must not be treated as authoritative\n",
            encoding="utf-8",
        )

        errors = registry_validator.validate_agent_registry(pkg)
        assert _has_unknown_agent_error(errors, "stale-flow.js"), (
            f"a deployed-only workflow must not be accepted when the source dir exists; got: {errors}"
        )

    with tempfile.TemporaryDirectory() as tmp2:
        repo = Path(tmp2)
        _init_git_repo(repo)
        _write_registry(repo, [_make_agent("spawner-agent", spawned_by=["stale-flow.js"])])
        (repo / "templates" / "workflows-js").mkdir(parents=True)
        deployed_dir = repo / ".claude" / "workflows"
        deployed_dir.mkdir(parents=True)
        (deployed_dir / "stale-flow.js").write_text("// stale deployed-only copy\n", encoding="utf-8")
        cards_dir = repo / "docs" / "agents" / "cards"
        cards_dir.mkdir(parents=True)
        (cards_dir / "spawner-agent.card.md").write_text(
            _card_text("spawner-agent"), encoding="utf-8"
        )
        _stage_all(repo)

        result = _run_hook(repo)
        assert result.returncode != 0, (
            "hook must reject a deployed-only workflow when the package source exists"
        )
        assert "stale-flow.js" in result.stderr


# ---------------------------------------------------------------------------
# Test 7 -- real_artifact
# ---------------------------------------------------------------------------


def test_shipped_registry_validates_under_both_checks():
    # covers: INF-600k-1
    # angle: real_artifact
    """The REAL config/agent_registry.json and REAL templates/workflows-js/
    of this repository must validate cleanly under both real entry points --
    a regression guard proving the relaxation does not merely pass
    synthetic fixtures while breaking the shipped registry. Expected GREEN
    today (this repo's registry lists no workflow filename other than the
    already-accepted 'finalize-feature.js' anywhere in spawned_by).
    """
    errors = registry_validator.validate_agent_registry(REPO_ROOT)
    unknown_agent_errors = [e for e in errors if "unknown agent" in e.lower()]
    assert unknown_agent_errors == [], (
        f"the shipped registry must have zero unknown-agent errors; got: {unknown_agent_errors}"
    )

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _init_git_repo(repo)
        (repo / "config").mkdir()
        shutil.copy(REAL_REGISTRY, repo / "config" / "agent_registry.json")
        workflows_dest = repo / "templates" / "workflows-js"
        workflows_dest.mkdir(parents=True)
        for js_file in REAL_WORKFLOWS_DIR.glob("*.js"):
            shutil.copy(js_file, workflows_dest / js_file.name)
        # No docs/agents/cards/ copied on purpose: the mirror check advisory-skips
        # when the directory is absent, isolating this test to the
        # spawned_by-classification check the fixture targets.
        _stage_all(repo)

        result = _run_hook(repo)
        assert result.returncode == 0, (
            f"the shipped registry must pass the hook cleanly; stderr={result.stderr!r}"
        )


# ---------------------------------------------------------------------------
# Test 8 -- deployed
# ---------------------------------------------------------------------------


def test_spawn_consistency_hook_copies_are_in_parity():
    # covers: INF-600k-1
    # angle: deployed
    """templates/scripts/commit_guardian/hooks/check_agent_spawn_consistency.py
    (the edit site per it_requirement #5) and
    scripts/commit_guardian/hooks/check_agent_spawn_consistency.py (the
    tracked round-trip copy this repo self-hosts with) must be
    byte-identical after running the REAL build deploy step
    (build_phases_lifecycle.build_commit_guardian) into a tmp target
    directory -- a source-tree read alone cannot prove the deploy manifest
    actually ships the edited file. Expected GREEN today (both copies are
    already byte-identical prior to this ticket's implementation work);
    must remain green once python-coder edits the templates/ copy and
    round-trips it via the build.
    """
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        written = build_phases_lifecycle.build_commit_guardian(target, {}, dry_run=False, force=True)
        assert written > 0, "build_commit_guardian must actually deploy files into the tmp target"

        deployed_hook = (
            target / "scripts" / "commit_guardian" / "hooks" / "check_agent_spawn_consistency.py"
        )
        assert deployed_hook.exists(), f"hook was not deployed to {deployed_hook}"

        expected = inject_config(TEMPLATE_HOOK_PATH.read_text(encoding="utf-8"), {})
        deployed_text = deployed_hook.read_text(encoding="utf-8")
        tracked_text = HOOK_PATH.read_text(encoding="utf-8")

        assert deployed_text == expected, (
            "deployed copy must equal the template after the build's normal transform"
        )
        assert deployed_text == tracked_text, (
            "deployed copy must equal the tracked scripts/ copy this repo self-hosts with"
        )
