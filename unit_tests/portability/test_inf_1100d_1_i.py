"""
MODULE: test_inf_1100d_1_i
AC: INF-1100d-1-i -- "Upgrading keeps a project's own database setting and
    never writes a shipped default back"

GOAL: RED-baseline behavioral tests for the upgrade path's two settings-
    touching steps -- build.py's ``_migrate_skills_config`` step followed by
    ``config_loader.load_config`` -- proving: project A's own
    db_connection_test setting survives an upgrade byte-for-byte, project
    B's (which never set it) resolves as unset afterwards, and the
    downstream test-database checker (INF-1100d-3-i) sees that same
    'unset' as a first-class 'not configured' report rather than a
    connection attempt against a leaked default.

WHY IN-PROCESS, NOT A build.py SUBPROCESS: this AC's own it_requirements
    ("Exercise the upgrade's settings-touching steps in-process: build.py's
    skills-config migration step, then config resolution") and CLAUDE.md's
    "Tests must not spawn their own build.py" both forbid a full
    ``build.py`` subprocess run here.
    ``_inf_1100d_1_settings_harness.py`` (shared with the parent AC's
    ``test_inf_1100d_1.py``) performs the one ``scripts/`` sys.path push
    needed to import ``build`` and ``config_loader`` as real modules, and
    exposes the real ``_migrate_skills_config`` call and the real
    ``load_config`` resolver.

FIXTURES: every project fixture is a REAL temp directory with a REAL
    ``.claude/skills_config.json`` written via ``json.dump``
    (``unit_tests/README.md`` #4 -- never a hand-typed literal). The
    literal legacy shipped address never appears in this file; project A's
    own setting is the AC's own worked example
    (``postgresql://app:app@db.internal:5432/app_test``,
    ``PROJECT_OWNED_ADDRESS`` in the shared harness).

MUST_CATCH MAPPING (from this AC's own IT-PO enrichment notes):
    - "migration step rewrites the settings file with defaults merged in"
      -> ``test_upgrade_leaves_project_owned_db_setting_byte_identical``
      (project A) goes red -- its own mutation-proof branch demonstrates
      the byte-comparison's discriminating power (see that test's
      docstring; it is a positive control, green today by construction,
      per unit_tests/README.md Section 1).
    - "defaults still carry the address" ->
      ``test_upgrade_leaves_project_without_setting_unset`` (project B)
      goes red today, for exactly this reason: config/skills_config.default.json
      still ships the legacy address as of this worktree, so project B's
      resolved setting is NOT yet unset after the upgrade's settings
      steps.

Per the coordinator's explicit instruction, each must_catch case is its OWN
    test function (never ``self.subTest``).

CROSS-LAYER SEAM (Source-of-Truth Discipline Rule 3): this AC's third test,
    ``test_project_b_db_check_reports_not_configured_after_upgrade``, pipes
    the REAL producer (project B's post-upgrade resolved settings, as
    ``config_loader.load_config`` and the migration step actually leave
    them) into the REAL consumer -- INF-1100d-3-i's shipped
    ``scripts/db_check/checker.py`` CLI, invoked as a real subprocess, the
    same way the test runner invokes it. It reuses the project-fixture and
    subprocess-CLI helpers from
    ``_inf_1100d_3_db_check_harness.py`` (INF-1100d-3-i/-3-ii's own
    harness) rather than re-implementing them, so the two AC pairs' tests
    cannot drift on what "run the checker CLI against a project" means.
"""
# @ac-tag: INF-1100d-1-i

from __future__ import annotations

import json

from ._inf_1100d_1_settings_harness import (
    DEFAULTS_PATH,
    PROJECT_OWNED_ADDRESS,
    make_tmp_dir,
    resolved_db_setting,
    run_settings_migration,
    write_project_config,
)
from ._inf_1100d_3_db_check_harness import (
    run_checker_cli,
    write_project as write_seam_project,
)


def test_upgrade_leaves_project_owned_db_setting_byte_identical():
    # covers: INF-1100d-1-i
    # angle: criterion
    """AC-1-i: project A's skills_config.json (db_connection_test =
    postgresql://app:app@db.internal:5432/app_test) is byte-for-byte
    unchanged after the upgrade's settings-migration step, and still
    resolves to the same value.

    POSITIVE CONTROL (unit_tests/README.md Section 1): "the upgrade
    removes and rewrites nothing the project set" is an absence-of-
    breakage claim -- build.py's real ``_migrate_skills_config`` step
    today only ever touches ``frontend.optional_skills``, so this
    assertion is green today by construction. A red baseline is
    structurally unavailable for that reason, so the proof owed instead
    is a MUTATION PROOF, per the README's recipe: build the exact shape a
    wrong migration ("rewrites the settings file with defaults merged in",
    this AC's own must_catch) would produce, and confirm it is
    byte-different from project A's untouched file -- demonstrating that
    the byte-identical assertion above really would have gone red had
    that wrong migration actually run.
    """
    project_root, config_path = write_project_config(
        "inf1100d1i_projA_",
        {"testing_context": {"db_connection_test": PROJECT_OWNED_ADDRESS}},
    )
    before = config_path.read_bytes()

    run_settings_migration(None, project_root)

    after = config_path.read_bytes()
    assert after == before, (
        "the upgrade's settings-migration step must not rewrite anything "
        "in a project's own skills_config.json when there is nothing to "
        "migrate; the file changed byte-for-byte"
    )

    value = resolved_db_setting(project_root)
    assert value == PROJECT_OWNED_ADDRESS, (
        "project A's own db_connection_test setting must resolve "
        f"unchanged after the upgrade; got {value!r}"
    )

    # Mutation proof: the shape a wrong migration ("rewrites the settings
    # file with defaults merged in") would produce must be byte-different
    # from project A's untouched file, or the byte-identical assertion
    # above cannot discriminate that must_catch case.
    defaults = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
    wrongly_merged = {
        **defaults,
        "testing_context": {
            **defaults.get("testing_context", {}),
            "db_connection_test": PROJECT_OWNED_ADDRESS,
        },
    }
    wrongly_merged_bytes = (json.dumps(wrongly_merged, indent=2) + "\n").encode("utf-8")
    assert wrongly_merged_bytes != before, (
        "mutation proof failed: the simulated 'migration merges defaults "
        "in' shape must differ from project A's untouched file, or this "
        "test cannot detect that must_catch case"
    )


def test_upgrade_leaves_project_without_setting_unset():
    # covers: INF-1100d-1-i
    # angle: reachability
    """AC-1-i: project B (a pre-existing adopter project whose own
    settings never mention db_connection_test at all -- no
    ``testing_context`` key in its own file) resolves the setting as
    unset after the upgrade's settings steps run.

    Invokes the REAL production entry points named by this AC's own
    ``surface_invoked``: build.py's real ``_migrate_skills_config`` step,
    followed by ``config_loader.load_config``, called in-process (no
    build.py subprocess spawn) -- and consumes the resolved value in an
    assertion, not merely a call.

    RED TODAY FOR THE RIGHT REASON (must_catch: "defaults still carry the
    address"): config/skills_config.default.json still ships the legacy
    address as of this worktree, and project B's config has no
    ``testing_context`` key of its own, so ``config_loader``'s shallow
    top-level merge falls through to the package default's whole
    ``testing_context`` object -- which still carries the address today.
    This deliberately does NOT use a project file with an explicit-but-
    empty ``testing_context: {}`` (INF-1100d-1's own architecture note:
    "the fix must not depend on that quirk" -- an empty-but-present
    ``testing_context`` key would already hide today's leak via the same
    shallow-merge quirk, independent of whether INF-1100d-1 has landed).
    """
    project_root, config_path = write_project_config(
        "inf1100d1i_projB_",
        {"output_root": "."},
    )
    before = config_path.read_bytes()

    run_settings_migration(None, project_root)

    after = config_path.read_bytes()
    assert after == before, (
        "the upgrade's settings-migration step must not write anything "
        "into project B's own skills_config.json (it never had a "
        "testing_context section, and nothing about that upgrade step "
        "should introduce one)"
    )

    value = resolved_db_setting(project_root)
    assert value is None, (
        "project B, which never set db_connection_test, must resolve the "
        "setting as unset after the upgrade -- nothing from the shipped "
        f"defaults may be merged in; got {value!r}"
    )


def test_project_b_db_check_reports_not_configured_after_upgrade():
    # covers: INF-1100d-1-i
    # angle: seam
    """AC-1-i: after the upgrade's settings steps run for project B,
    INF-1100d-3-i's real shipped checker CLI (``scripts/db_check/checker.py``,
    invoked as a real subprocess -- never imported and called directly)
    reports 'not_configured', names ``testing_context.db_connection_test``,
    and makes no connection attempt (no host/port/database in the report --
    those fields are only ever populated for the 'unreachable'/'reachable'
    shapes, which require a successful address parse first).

    CROSS-LAYER SEAM (Source-of-Truth Discipline Rule 3): pipes the REAL
    producer (project B's post-upgrade settings, as the migration step and
    ``config_loader`` actually leave them on disk) into the REAL consumer
    (the checker CLI subprocess) and asserts the consumer's own observable
    output -- not a mocked call, not an inspected argument.

    POSITIVE CONTROL (unit_tests/README.md Section 1): this seam is green
    today by design, independent of whether INF-1100d-1's own fix has
    landed -- ``checker.resolve_test_db_address()`` reads project B's OWN
    ``skills_config.json`` directly and never merges package defaults (see
    ``scripts/db_check/checker.py``'s own module docstring, "this resolver
    never will [see the default], by design"). A red baseline is
    structurally unavailable for that reason, so the proof owed instead is
    a MUTATION PROOF: a sibling project whose OWN file has a leaked
    (non-empty) db_connection_test value -- simulating exactly the failure
    this AC forbids, "the old shipped address ... reappear[ing] from ... a
    leftover default" -- must NOT be reported as not_configured, proving
    the not_configured assertions above really do discriminate an unset
    setting from a leaked one.
    """
    project_root = write_seam_project(make_tmp_dir("inf1100d1i_seamB_"), {})
    run_settings_migration(None, project_root)

    result = run_checker_cli(project_root)

    assert result.returncode != 0, (
        f"checker CLI must exit non-zero for an unconfigured setting; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    payload = json.loads(result.stdout)
    assert payload.get("status") == "not_configured", (
        f"expected status 'not_configured' for project B after the "
        f"upgrade; got {payload!r}"
    )
    assert payload.get("setting") == "testing_context.db_connection_test"
    assert payload.get("host") is None
    assert payload.get("port") is None
    assert payload.get("database") is None

    # Mutation proof: a sibling project whose own file leaks a real
    # address must NOT be reported as not_configured, or the assertions
    # above cannot discriminate "unset" from "leaked default value" -- the
    # exact failure mode this AC forbids.
    leaked_root = write_seam_project(
        make_tmp_dir("inf1100d1i_seamLeak_"),
        {"db_connection_test": PROJECT_OWNED_ADDRESS},
    )
    leaked_result = run_checker_cli(leaked_root)
    leaked_payload = json.loads(leaked_result.stdout)
    assert leaked_payload.get("status") != "not_configured", (
        "mutation proof failed: a project with a real db_connection_test "
        "value must not be reported as not_configured, or this test's "
        "not_configured assertions above cannot discriminate the leak "
        "this AC forbids"
    )
