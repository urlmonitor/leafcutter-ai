"""
MODULE: unit_tests/commit_guardian/test_ge_113c_1_vi_integrity.py
GOAL: RED failing tests for GE-113c-1-vi — the cross-entry-point and
      cross-copy integrity scenarios: commit-time hook vs build.py
      --validate-only (seam), live vs packaged hook copies (deployed) plus
      check_hook_parity, the real-repository enablement guard (real_artifact),
      and the hook-entry-not-narrowed regression guard (discrimination).

      Split out of the original, single test_ge_113c_1_vi.py (pr-reviewer
      finding H-1: 455 content lines, over the 400-line flat cap for a new
      file per count_content_lines in
      .leafcutter/scripts/commit_guardian/_file_size_ratchet.py). This is a
      PURE MOVE: every test name, body, `covers:` / `angle:` tag, and
      docstring below is unchanged from the original file — only the file
      boundary changed. The package-resolution-layout tests (repo-root,
      manifest-named-subdirectory, unlocatable, nothing-in-scope, and
      GE-113c-1's deployed-layout seam test) moved to the sibling file
      test_ge_113c_1_vi_layouts.py. Both files import the same shared
      _ge_113c_1_vi_fixtures.py.
TICKET: none (hand-driven build; the AC YAML is the spec) — see
    docs/acceptance-criteria/guardrail-engine/GE-113-artifacts-cant-land-in-
    the-wrong-place/GE-113c-1-vi.yaml.

THE DEFECT (KI-CG-20260928): templates/scripts/commit_guardian/
check_agent_registry.py's main() computes
``package_root = repo_root / "leafcutter"`` and returns 0 — without reading
anything — when that literal path is absent. See test_ge_113c_1_vi_layouts.py
and _ge_113c_1_vi_fixtures.py for the full defect and fix-shape rationale.

RED BASELINE (empirically confirmed before writing this docstring — see the
test-writer report for the exact command/output transcripts):
  - The commit-time half of the seam test fails today (repo-root layout,
    same gap as test_ge_113c_1_vi_layouts.py's invalid-registry test); the
    build.py --validate-only half already passes today.
  - The live-vs-packaged parity test, the real-repository enablement guard,
    and the hook-entry-not-narrowed test are all already green today — each
    is called out at the point it occurs and reported as already-green in
    the test-writer report, per that skill's instructions (a parity check
    between two currently byte-identical, still-unfixed files; a real
    registry that already validates cleanly; and a static config file that
    has not yet been narrowed).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_TEST_DIR = Path(__file__).resolve().parent
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))

import _ge_113c_1_vi_fixtures as fx  # noqa: E402


# ---------------------------------------------------------------------------
# 6. Commit-time hook and build.py --validate-only report the same error.
# ---------------------------------------------------------------------------


def test_commit_time_and_build_validate_only_report_the_same_error(tmp_path):
    # covers: GE-113c-1-vi
    # angle: seam
    """For the invalid fixture package, the hook and build.py --validate-only
    (subprocess, pointed at the fixture) both fail and both name
    fixture-agent and the missing template.

    Reachability/seam note: this pipes the REAL producer's actual behaviour
    (validate_agent_registry, invoked via check_agent_registry.py's own
    subprocess entry point) against the REAL second consumer entry point
    (`build.py --validate-only`, its own real subprocess) — not a single
    in-process call to validate_agent_registry() alone, which would prove
    only that the shared function works, not that both real commit-time and
    build-time callers actually reach it.

    RED TODAY: the commit-time side fails today (see
    test_ge_113c_1_vi_layouts.py's invalid-registry test — same underlying
    scenario) because the current hook never finds the repo-root-layout
    package. The build.py --validate-only side already passes today
    (build.py has always validated the registry; only the commit-time gate
    is broken) — so today this test as a whole is RED, driven entirely by
    the commit-time half.
    """
    # Commit-time side: repo-root layout, same minimal invalid registry as
    # test_ge_113c_1_vi_layouts.py's invalid-registry test.
    repo = tmp_path / "repo"
    fx.git_init(repo)
    agent = fx.make_fixture_agent()
    fx.build_minimal_package(repo, [agent], include_fixture_template=False)
    fx.write_manifest(repo, package_root_value="")
    hook_path = fx.deploy_hook(repo)
    fx.git_add(repo, "config/agent_registry.json")

    hook_result = fx.run_hook(hook_path, repo)
    hook_combined = hook_result.stdout + hook_result.stderr

    # build.py --validate-only side: full real package copy + one appended
    # broken agent (mirrors _bo2400a1iii_fixtures.build_full_package_copy's
    # established pattern for this exact purpose).
    full_pkg = tmp_path / "full_pkg"
    fx.build_full_real_package_copy(full_pkg)
    fx.append_agent_to_registry(full_pkg, fx.make_fixture_agent())

    build_result = fx.run_build_validate_only(full_pkg, tmp_path / "target")
    build_combined = build_result.stdout + build_result.stderr

    assert hook_result.returncode != 0, (
        "check_agent_registry.py must exit non-zero for the invalid fixture "
        f"package. Got returncode={hook_result.returncode}, "
        f"stdout={hook_result.stdout!r}, stderr={hook_result.stderr!r}"
    )
    assert build_result.returncode != 0, (
        "build.py --validate-only must exit non-zero for the invalid "
        f"fixture package. Got returncode={build_result.returncode}, "
        f"stdout tail={build_result.stdout[-1000:]!r}, "
        f"stderr tail={build_result.stderr[-1000:]!r}"
    )
    assert "fixture-agent" in hook_combined and "fixture-agent" in build_combined, (
        "Both the commit-time hook and build.py --validate-only must name "
        f"'fixture-agent'. hook={hook_combined!r} "
        f"build tail={build_combined[-1000:]!r}"
    )
    assert "fixture-agent.md" in hook_combined and "fixture-agent.md" in build_combined, (
        "Both the commit-time hook and build.py --validate-only must name "
        f"the missing template path. hook={hook_combined!r} "
        f"build tail={build_combined[-1000:]!r}"
    )


# ---------------------------------------------------------------------------
# 7. Live and packaged copies give the same verdicts; check_hook_parity passes.
# ---------------------------------------------------------------------------


def _run_scenario_with_hook_source(tmp_path_factory, hook_source: Path, label: str):
    """Run all four scenarios (invalid, corrected, unlocatable, nothing-in-scope)
    with a given hook source copy, returning a dict of returncodes keyed by
    scenario name. Shared body for the live-vs-packaged comparison below.
    """
    results: dict[str, int] = {}

    # invalid / corrected (repo-root layout)
    repo = tmp_path_factory / f"{label}_repo_root"
    fx.git_init(repo)
    agent = fx.make_fixture_agent()
    fx.build_minimal_package(repo, [agent], include_fixture_template=False)
    fx.write_manifest(repo, package_root_value="")
    hook_path = fx.deploy_hook(repo, source=hook_source)
    fx.git_add(repo, "config/agent_registry.json")
    results["invalid"] = fx.run_hook(hook_path, repo).returncode

    fx.add_fixture_template(repo)
    fx.git_add(repo, "templates/agents/fixture-agent.md")
    results["corrected"] = fx.run_hook(hook_path, repo).returncode

    # unlocatable
    repo_unlocatable = tmp_path_factory / f"{label}_unlocatable"
    fx.git_init(repo_unlocatable)
    fx.write_json(repo_unlocatable / "config" / "agent_registry.json", {"agents": []})
    hook_unlocatable = fx.deploy_hook(repo_unlocatable, source=hook_source)
    fx.git_add(repo_unlocatable, "config/agent_registry.json")
    results["unlocatable"] = fx.run_hook(hook_unlocatable, repo_unlocatable).returncode

    # nothing in scope
    repo_scope = tmp_path_factory / f"{label}_nothing_in_scope"
    fx.git_init(repo_scope)
    hook_scope = fx.deploy_hook(repo_scope, source=hook_source)
    (repo_scope / "README.md").write_text("out of scope\n", encoding="utf-8")
    fx.git_add(repo_scope, "README.md")
    results["nothing_in_scope"] = fx.run_hook(hook_scope, repo_scope).returncode

    return results


def test_live_and_packaged_copies_give_the_same_verdicts(tmp_path):
    # covers: GE-113c-1-vi
    # angle: deployed
    """scripts/commit_guardian/check_agent_registry.py and
    templates/scripts/commit_guardian/check_agent_registry.py, each deployed
    into fixture repositories, give the same exit codes on the invalid,
    corrected, unlocatable and nothing-in-scope scenarios, and
    check_hook_parity passes.

    ALREADY GREEN TODAY: as of this worktree's HEAD, the live copy
    (scripts/commit_guardian/check_agent_registry.py) and the templates copy
    (templates/scripts/commit_guardian/check_agent_registry.py) are
    byte-identical (confirmed via filecmp before writing this test) and both
    carry today's unfixed bug, so every scenario's verdict trivially agrees
    between the two copies (both always exit 0, right or wrong) and
    check_hook_parity — which compares content, not correctness — currently
    reports success. This test exists as the regression guard for AFTER the
    fix lands: the it_requirements mandate that the fix is made in the
    templates/ copy only and reaches the live/deployed copies through the
    build (ADR-001), so this test is what would catch a build step that
    forgot to re-sync them.
    """
    live_results = _run_scenario_with_hook_source(tmp_path, fx.LIVE_HOOK_SRC, "live")
    templates_results = _run_scenario_with_hook_source(
        tmp_path, fx.TEMPLATES_HOOK_SRC, "templates"
    )

    assert live_results == templates_results, (
        "Live and templates copies must give the same exit code on every "
        f"scenario. live={live_results!r} templates={templates_results!r}"
    )

    parity_result = fx.run_check_hook_parity_against_real_worktree()
    assert parity_result.returncode == 0, (
        "check_hook_parity must pass against this worktree. Got returncode="
        f"{parity_result.returncode}, stdout={parity_result.stdout!r}, "
        f"stderr={parity_result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 8. Real-repository enablement guard: the real registry passes the enabled gate.
# ---------------------------------------------------------------------------


def test_real_repository_registry_passes_the_enabled_gate(tmp_path):
    # covers: GE-113c-1-vi
    # angle: real_artifact
    """The fixed hook, run over a temporary clone of this repository at its
    real layout with the real config/agent_registry.json staged, exits 0,
    and build.py --validate-only on the real repository exits 0. Turning the
    gate on must not block the registry as it stands.

    ALREADY GREEN TODAY, for two different reasons on its two halves:
      - The hook half is green today by luck of the existing bug: the
        current hook never finds a repo-root-layout package (no bare
        "leafcutter/" subdirectory exists in this repository's own layout
        either) and exits 0 having checked nothing.
      - The build.py --validate-only half is a genuine, valid pass today:
        the real registry has 0 errors under --validate-only (confirmed at
        AC enrichment on 2026-09-28; re-confirmed here against a real copy).
    Both must stay 0 once the fix actually looks — this test is the
    enablement guard the AC's own no-silent-re-disable clause exists to back.
    """
    repo = tmp_path / "repo"
    fx.git_init(repo)
    fx.build_full_real_package_copy(repo)
    fx.write_manifest(repo, package_root_value="")
    hook_path = fx.deploy_hook(repo)
    fx.git_add(repo, "config/agent_registry.json")

    hook_result = fx.run_hook(hook_path, repo)
    assert hook_result.returncode == 0, (
        "The real, unmodified registry must pass the enabled gate. Got "
        f"returncode={hook_result.returncode}, stdout={hook_result.stdout!r}, "
        f"stderr={hook_result.stderr!r}"
    )

    build_result = fx.run_build_validate_only(repo, tmp_path / "target")
    assert build_result.returncode == 0, (
        "build.py --validate-only must pass on the real, unmodified "
        f"registry. Got returncode={build_result.returncode}, stdout tail="
        f"{build_result.stdout[-1000:]!r}, stderr tail={build_result.stderr[-1000:]!r}"
    )


# ---------------------------------------------------------------------------
# 9. The check-agent-registry hook entry is not narrowed, exempted, or
#    softened to warn-only.
# ---------------------------------------------------------------------------


def test_check_agent_registry_hook_entry_is_not_narrowed_or_softened():
    # covers: GE-113c-1-vi
    # angle: discrimination
    """The check-agent-registry entry in the hook configuration (the
    shipped pre-commit config and the commit_guardian hooks manifest) has no
    files: narrowing, no exemption, and no warn-only disposition. The entry
    must never be re-disabled.

    must_catch:
      - a 'fix' that makes the gate pass by narrowing its files: scope, or
        adding it to an exemption/allow-list, or downgrading it to a
        non-blocking/advisory disposition instead of actually locating the
        package.

    ALREADY GREEN TODAY: as of this worktree's HEAD, neither the shipped
    hooks manifest nor .pre-commit-config.yaml narrows, exempts, or
    downgrades check-agent-registry (confirmed by direct inspection before
    writing this test) — the defect is that the gate does not look, not that
    it has been disabled. Kept as a permanent regression guard per the AC's
    own no-silent-re-disable clause: the temptation this test exists to
    block is "the fix caused N pre-existing registry errors to surface, so
    narrow/exempt/downgrade the gate instead of fixing or recording them."
    """
    manifest_path = fx.TEMPLATES_CG_DIR / "commit_guardian.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    hooks = manifest.get("hooks_manifest", {}).get("hooks", [])
    entry = next((h for h in hooks if h.get("id") == "check-agent-registry"), None)
    assert entry is not None, (
        "check-agent-registry must be registered in the canonical hooks "
        f"manifest at {manifest_path}."
    )
    assert "files" not in entry, (
        f"check-agent-registry's manifest entry must not narrow scope via a "
        f"'files' key. Got entry: {entry!r}"
    )
    assert entry.get("enabled", True) is not False, (
        f"check-agent-registry must not be disabled. Got entry: {entry!r}"
    )
    for softening_key in ("warn_only", "advisory", "exempt", "allow_list", "exemptions"):
        assert softening_key not in entry, (
            f"check-agent-registry's manifest entry must not carry a "
            f"softening key {softening_key!r}. Got entry: {entry!r}"
        )
    assert "pre-commit" in entry.get("stages", []), (
        f"check-agent-registry must still run at the pre-commit stage. "
        f"Got entry: {entry!r}"
    )

    pre_commit_config_path = fx.REPO_ROOT / ".pre-commit-config.yaml"
    text = pre_commit_config_path.read_text(encoding="utf-8")
    idx = text.find("id: check-agent-registry")
    assert idx != -1, (
        f"check-agent-registry must be registered in {pre_commit_config_path}."
    )
    # The entry's own block runs from its 'id:' line to the next '- id:' line
    # (or end of file). No 'files:' line may appear inside that block.
    next_entry_idx = text.find("\n      - id:", idx)
    block = text[idx: next_entry_idx if next_entry_idx != -1 else len(text)]
    assert "files:" not in block, (
        f"check-agent-registry's .pre-commit-config.yaml block must not "
        f"narrow scope via a 'files:' line. Got block:\n{block}"
    )
