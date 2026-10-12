"""
MODULE: unit_tests/commit_guardian/test_ge_113c_1_vi_layouts.py
GOAL: RED failing tests for GE-113c-1-vi — the package-resolution scenarios:
      repo-root layout (invalid / corrected), manifest-named-subdirectory
      layout, the unlocatable-package case, the nothing-in-scope case, and
      the deployed-layout seam test that also covers GE-113c-1's own test 6.

      Split out of the original, single test_ge_113c_1_vi.py (pr-reviewer
      finding H-1: 455 content lines, over the 400-line flat cap for a new
      file per count_content_lines in
      .leafcutter/scripts/commit_guardian/_file_size_ratchet.py). This is a
      PURE MOVE: every test name, body, `covers:` / `angle:` tag, and
      docstring below is unchanged from the original file — only the file
      boundary changed. The commit-time-vs-build-time / live-vs-packaged /
      real-registry-enablement / hook-entry-not-narrowed tests moved to the
      sibling file test_ge_113c_1_vi_integrity.py. Both files import the
      same shared _ge_113c_1_vi_fixtures.py.
TICKET: none (hand-driven build; the AC YAML is the spec) — see
    docs/acceptance-criteria/guardrail-engine/GE-113-artifacts-cant-land-in-
    the-wrong-place/GE-113c-1-vi.yaml and its parent GE-113c-1.yaml (test 6,
    "check_agent_registry resolves the consumer root before locating the
    package", implemented here too — see
    test_agent_registry_guard_finds_package_from_deployed_layout below).

THE DEFECT (KI-CG-20260928): templates/scripts/commit_guardian/
check_agent_registry.py's main() computes
``package_root = repo_root / "leafcutter"`` and returns 0 — without reading
anything — when that literal path is absent. In THIS repository (and in any
consumer project whose package sits somewhere other than a bare "leafcutter/"
child of the repo root) the gate has therefore never actually run.

ASSUMED PRODUCTION API (not presumed in exact shape — see
_ge_113c_1_vi_fixtures.py's module docstring for the full reasoning): the fix
locates the package root via the shared resolver
(scripts/commit_guardian/_resolve_root.py's find_project_root()) joined with
the ``package_root`` offset recorded in ``.build_manifest.json`` — the SAME
manifest field check_build_drift.py / check_output_drift.py already read.
Every test here is layout-based (a real temporary git repo, a real deployed
hook, a real manifest file, a real subprocess) rather than shape-based, so
any correct fix satisfies these tests regardless of its internal structure.

RED BASELINE (empirically confirmed before writing this docstring, by running
each fixture directly against the current, unmodified worktree code — see the
test-writer report for the exact command/output transcripts):
  - In the repo-root layout (package_root ""), the current hook computes
    ``<repo>/leafcutter`` (absent) and returns 0 having checked nothing, no
    matter how invalid the staged registry is.
  - In the "leafcutter-ai" manifest-named-subdirectory layout, the current
    hook's literal "leafcutter" segment does not match, so it also returns 0
    having checked nothing.
  - With no manifest and no locatable package at all, the current hook
    returns 0 (its own comment: "Package not present in this repo — nothing
    to validate") rather than blocking with a distinct message.
  - Some scenarios (the "leafcutter" name specifically in the parametrised
    boundary test, and the nothing-in-scope test) already pass today, some
    by luck of the existing hardcoded literal, some because the current bug
    is fail-open in exactly the direction those scenarios require. Each such
    case is called out at the point it occurs and reported as already-green
    in the test-writer report, per that skill's instructions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TEST_DIR = Path(__file__).resolve().parent
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))

import _ge_113c_1_vi_fixtures as fx  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Repo-root layout: invalid registry (missing template) blocks, naming
#    'fixture-agent' and the missing template.
# ---------------------------------------------------------------------------


def test_repo_root_layout_invalid_registry_blocks_naming_fixture_agent(tmp_path):
    # covers: GE-113c-1-vi
    # angle: failure
    """A temporary git repository has the package at its root (package_root
    "") and the hook deployed under .leafcutter/scripts/commit_guardian/. A
    staged registry adds 'fixture-agent' (empty spawned_by) with a
    template_path that does not exist. The hook must exit non-zero and its
    output must name 'fixture-agent' and the missing template path.

    must_catch:
      - the early exit 0 when <repo root>/leafcutter is absent (today's
        behaviour; this test fails today — the current hook never looks for
        a manifest, so a repo-root-layout package it is never even aware of
        is treated exactly like a repo with no package at all).
      - an exit 0 with a warning instead of a block.
    """
    repo = tmp_path / "repo"
    fx.git_init(repo)
    agent = fx.make_fixture_agent()
    fx.build_minimal_package(repo, [agent], include_fixture_template=False)
    fx.write_manifest(repo, package_root_value="")
    hook_path = fx.deploy_hook(repo)
    fx.git_add(repo, "config/agent_registry.json")

    result = fx.run_hook(hook_path, repo)
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        "check_agent_registry.py must exit non-zero when the staged registry "
        f"has a missing template. Got returncode={result.returncode}, "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    assert "fixture-agent" in combined, (
        f"Expected the agent id 'fixture-agent' named in the output, got: {combined!r}"
    )
    assert "fixture-agent.md" in combined, (
        f"Expected the missing template path named in the output, got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# 2. Repo-root layout: corrected registry (template file added) passes.
# ---------------------------------------------------------------------------


def test_repo_root_layout_corrected_registry_passes(tmp_path):
    # covers: GE-113c-1-vi
    # angle: criterion
    """In the same repository, after the fixture-agent template file is
    added and staged, the hook exits 0.

    ALREADY GREEN TODAY: the current hook returns 0 unconditionally in this
    layout (it never finds <repo>/leafcutter and exits 0 having checked
    nothing), so this assertion holds today for the wrong reason. It is kept
    as its own named test (per the AC's own test_spec) so a future
    regression that makes the FIXED gate block a genuinely valid, corrected
    registry is caught — see the paired blocking test above, which is
    genuinely red today.
    """
    repo = tmp_path / "repo"
    fx.git_init(repo)
    agent = fx.make_fixture_agent()
    fx.build_minimal_package(repo, [agent], include_fixture_template=False)
    fx.write_manifest(repo, package_root_value="")
    hook_path = fx.deploy_hook(repo)
    fx.git_add(repo, "config/agent_registry.json")

    # Correct the registry: add the missing template file and stage it too.
    fx.add_fixture_template(repo)
    fx.git_add(repo, "templates/agents/fixture-agent.md")

    result = fx.run_hook(hook_path, repo)

    assert result.returncode == 0, (
        "check_agent_registry.py must exit 0 once the missing template is "
        f"added and staged. Got returncode={result.returncode}, "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 3. Manifest-named-subdirectory layout ('leafcutter-ai' and 'leafcutter'):
#    invalid registry blocks, corrected registry passes.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("package_dir_name", ["leafcutter-ai", "leafcutter"])
def test_manifest_named_subdirectory_layout_is_validated(tmp_path, package_dir_name):
    # covers: GE-113c-1-vi
    # angle: boundary
    """An outer-project repository with the package in a manifest-recorded
    subdirectory (parametrised over 'leafcutter-ai' and 'leafcutter'): the
    invalid fixture registry blocks naming fixture-agent, and the corrected
    one passes.

    must_catch:
      - a hook that still hard-codes the 'leafcutter' segment passes the
        'leafcutter' case and fails the 'leafcutter-ai' one. CONFIRMED
        empirically: today, the package_dir_name='leafcutter' sub-case
        ALREADY exits non-zero on the invalid registry and ALREADY exits 0
        on the corrected one (today's hook happens to compute
        <repo>/leafcutter, which is exactly where this sub-case's package
        lives) — it is only the 'leafcutter-ai' sub-case that is genuinely
        red today (today's literal 'leafcutter' segment never matches
        'leafcutter-ai/config/agent_registry.json', so the hook exits 0
        having checked nothing, failing the "blocks the invalid registry"
        assertion below). This parametrised test as a whole is still RED
        today because pytest reports a parametrized test failing if any one
        of its instances fails.
    """
    repo = tmp_path / "repo"
    fx.git_init(repo)
    pkg_root = repo / package_dir_name
    agent = fx.make_fixture_agent()
    fx.build_minimal_package(pkg_root, [agent], include_fixture_template=False)
    fx.write_manifest(repo, package_root_value=package_dir_name)
    hook_path = fx.deploy_hook(repo)
    staged_registry = f"{package_dir_name}/config/agent_registry.json"
    fx.git_add(repo, staged_registry)

    invalid_result = fx.run_hook(hook_path, repo)
    invalid_combined = invalid_result.stdout + invalid_result.stderr

    assert invalid_result.returncode != 0, (
        f"[{package_dir_name}] check_agent_registry.py must exit non-zero on "
        f"the invalid registry. Got returncode={invalid_result.returncode}, "
        f"stdout={invalid_result.stdout!r}, stderr={invalid_result.stderr!r}"
    )
    assert "fixture-agent" in invalid_combined, (
        f"[{package_dir_name}] Expected 'fixture-agent' named in the output, "
        f"got: {invalid_combined!r}"
    )

    fx.add_fixture_template(pkg_root)
    fx.git_add(repo, f"{package_dir_name}/templates/agents/fixture-agent.md")

    corrected_result = fx.run_hook(hook_path, repo)

    assert corrected_result.returncode == 0, (
        f"[{package_dir_name}] check_agent_registry.py must exit 0 once the "
        f"missing template is added and staged. Got returncode="
        f"{corrected_result.returncode}, stdout={corrected_result.stdout!r}, "
        f"stderr={corrected_result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 4. Unlocatable package: blocks with its own, distinct message.
# ---------------------------------------------------------------------------


def test_unlocatable_package_blocks_with_its_own_message(tmp_path):
    # covers: GE-113c-1-vi
    # angle: failure
    """A repository with a staged config/agent_registry.json but no manifest
    anywhere and therefore no locatable package makes the hook exit non-zero.
    The output must name the locations tried and the staged file, and must
    share no identifying wording with the registry-invalid message (checked
    here by asserting this output does NOT contain the registry-content-
    specific substring 'fixture-agent', which only ever appears once the
    registry is actually read — see the paired invalid-registry test above,
    whose output DOES contain it).

    must_catch:
      - exit 0 when the package cannot be found (today's behaviour; this
        test fails today — the current hook's own comment is literally
        "Package not present in this repo — nothing to validate" followed
        by `return 0`).
      - the cannot-locate case reusing the 'validation failed' wording (the
        cross-check against the invalid-registry test's output below).
    """
    repo = tmp_path / "repo"
    fx.git_init(repo)
    # A staged in-scope file exists on disk (so `git add` has something real
    # to stage), but NO .build_manifest.json exists anywhere under `repo` —
    # the package is genuinely unlocatable by the shared-resolver convention.
    registry_path = repo / "config" / "agent_registry.json"
    fx.write_json(registry_path, {"agents": []})
    hook_path = fx.deploy_hook(repo)
    fx.git_add(repo, "config/agent_registry.json")

    result = fx.run_hook(hook_path, repo)
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        "check_agent_registry.py must exit non-zero when no package root can "
        f"be located for a staged in-scope file. Got returncode="
        f"{result.returncode}, stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    assert str(repo.resolve()) in combined, (
        "The cannot-locate message must name the location(s) it tried "
        f"(expected the repo root {repo.resolve()} to appear). Got: {combined!r}"
    )
    assert "agent_registry.json" in combined, (
        "The cannot-locate message must name the staged in-scope file it "
        f"therefore did not check. Got: {combined!r}"
    )
    assert "fixture-agent" not in combined, (
        "The cannot-locate message must be distinct from the registry-"
        "invalid message: it never read any registry content, so it must "
        f"not mention 'fixture-agent'. Got: {combined!r}"
    )


# ---------------------------------------------------------------------------
# 5. Nothing in scope staged: passes whether or not the package is found.
# ---------------------------------------------------------------------------


def test_nothing_in_scope_staged_passes_whether_or_not_package_is_found(tmp_path):
    # covers: GE-113c-1-vi
    # angle: boundary
    """With only an out-of-scope file staged, the hook exits 0 both in a
    repository where the package can be located and in one where it cannot.

    must_catch:
      - a fix that blocks every commit in a repository without the package
        (guards the "package not found" side from over-correcting into
        always-block; the empty-scope rule of GE-120a-4 must still win).

    ALREADY GREEN TODAY for both sub-cases: today's `_is_registry_related`
    scope check runs before any package-lookup logic and returns False for
    an out-of-scope staged file regardless of layout, so the hook already
    exits 0 here — for the wrong architectural reason (no manifest-based
    scope decision exists yet), but the observable exit code already
    matches. Kept as its own test (per the AC's own test_spec) to catch a
    future regression where package-lookup is moved ahead of scope
    detection.
    """
    # (a) package IS locatable.
    repo_found = tmp_path / "repo_found"
    fx.git_init(repo_found)
    agent = fx.make_fixture_agent()
    fx.build_minimal_package(repo_found, [agent], include_fixture_template=False)
    fx.write_manifest(repo_found, package_root_value="")
    hook_found = fx.deploy_hook(repo_found)
    (repo_found / "README.md").write_text("out of scope\n", encoding="utf-8")
    fx.git_add(repo_found, "README.md")

    result_found = fx.run_hook(hook_found, repo_found)
    assert result_found.returncode == 0, (
        "Nothing in scope staged must pass even when the package IS "
        f"locatable. Got returncode={result_found.returncode}, "
        f"stdout={result_found.stdout!r}, stderr={result_found.stderr!r}"
    )

    # (b) package is NOT locatable (no manifest anywhere).
    repo_missing = tmp_path / "repo_missing"
    fx.git_init(repo_missing)
    hook_missing = fx.deploy_hook(repo_missing)
    (repo_missing / "README.md").write_text("out of scope\n", encoding="utf-8")
    fx.git_add(repo_missing, "README.md")

    result_missing = fx.run_hook(hook_missing, repo_missing)
    assert result_missing.returncode == 0, (
        "Nothing in scope staged must pass even when the package is NOT "
        f"locatable. Got returncode={result_missing.returncode}, "
        f"stdout={result_missing.stdout!r}, stderr={result_missing.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 10. GE-113c-1's own test 6: check_agent_registry resolves the consumer
#     root before locating the package (composite coverage, implemented here
#     because it is naturally the same subdirectory-layout scenario this AC
#     already builds).
# ---------------------------------------------------------------------------


def test_agent_registry_guard_finds_package_from_deployed_layout(tmp_path):
    # covers: GE-113c-1
    # covers: GE-113c-1-vi
    # angle: seam
    """check_agent_registry, run from .leafcutter/ in a consumer project
    whose manifest records a package subdirectory, resolves the project root
    to the consumer root before locating the package, and blocks a staged
    invalid registry.

    This is GE-113c-1's own test 6 (its test_spec entry
    'test_agent_registry_guard_finds_package_from_deployed_layout', marked
    covers: [GE-113c-1, GE-113c-1-vi]) — implemented here rather than
    duplicated in a GE-113c-1 test file, because it is the identical
    manifest-named-subdirectory scenario GE-113c-1-vi's own test 3 already
    builds, with one added assertion this test contributes on top: a sanity
    guard that the WRONG root (a naive .leafcutter-relative resolution, which
    would never find a sibling package directory) is not what produced the
    block — guarding against a vacuous pass where the hook blocks for an
    unrelated reason and happens to still exit non-zero.

    RED TODAY: today's hook computes <repo>/"leafcutter" literally, which
    does not exist in this "leafcutter-ai" consumer layout, so it exits 0
    having checked nothing — the same gap as test 3's 'leafcutter-ai'
    sub-case.
    """
    repo = tmp_path / "consumer_root"
    fx.git_init(repo)
    pkg_root = repo / "leafcutter-ai"
    agent = fx.make_fixture_agent()
    fx.build_minimal_package(pkg_root, [agent], include_fixture_template=False)
    fx.write_manifest(repo, package_root_value="leafcutter-ai")
    hook_path = fx.deploy_hook(repo)
    fx.git_add(repo, "leafcutter-ai/config/agent_registry.json")

    # Sanity guard against a vacuous pass: a naive resolution that mistook
    # the deployed .leafcutter/ directory itself for the project root would
    # look for the package at .leafcutter/leafcutter-ai, which must not
    # exist in this fixture.
    wrong_nested_path = repo / ".leafcutter" / "leafcutter-ai"
    assert not wrong_nested_path.exists(), (
        "Test setup bug: a naive .leafcutter-relative resolution's target "
        "must not coincidentally exist, or this test cannot distinguish "
        "correct root resolution from incorrect root resolution."
    )

    result = fx.run_hook(hook_path, repo)
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        "check_agent_registry.py must resolve the consumer project root "
        "(not .leafcutter/) and locate the package at leafcutter-ai/, then "
        f"block the invalid staged registry. Got returncode={result.returncode}, "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    assert "fixture-agent" in combined, (
        f"Expected 'fixture-agent' named in the output, got: {combined!r}"
    )
