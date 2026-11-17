"""
MODULE: unit_tests/commit_guardian/test_ge_132a_1_loader_fail_closed.py
COVERS: GE-132a-1 -- fail-closed handling of unreadable inputs, and the shared
    remedy-declaration loader (owned constraint): seed fallback for an old
    install, local-wins, a malformed skills_config, the deployed check reading
    through the loader, and the loader being deployed and importing cold.

GOAL, REACHABILITY ENTRY POINT, LOADER CONTRACT and MARKERS: see the shared
    harness _ge_132a_1_harness.py, which every GE-132a-1 test file imports.

DECISION HISTORY
- 2026-10-12 [GE-132a-1/test-writer]: Initial RED authoring (in test_ge_132a_1.py).
- 2026-10-12 [GE-132a-1/restructuring-specialist]: Split out of test_ge_132a_1.py
  (file-size limit); tests moved verbatim.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ge_132a_1_harness import (  # noqa: E402
    _DRIVER,
    DECL,
    GIT_TIMEOUT,
    GUARDIAN_DIR,
    LOCAL_REL,
    MANIFEST_RELS,
    SEED_REL,
    SEED_RELS,
    _accepted,
    _all_declared_seed,
    _clean_seed,
    _commit,
    _declared_ids,
    _deployed_guardian,
    _dump,
    _git,
    _head,
    _hooks,
    _lines_naming,
    _old_install_tables,
    _real_manifest,
    _refused,
    _scratch,
    _stage,
    _undeclared,
    _widget_hook,
    _with_parity,
    _write_tables,
)


# ---------------------------------------------------------------------------
# Fail closed
# ---------------------------------------------------------------------------
@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("broken", ["manifest", "seed", "excused_list"])
def test_ge132a1_unreadable_inputs_fail_closed(shared_reference_layout: Path, tmp_path: Path, broken: str) -> None:
    # covers: GE-132a-1
    # angle: failure
    """An unparseable manifest, routing table or excused list is reported as
    could-not-check and refuses; it is never a pass and never 'no declaration'."""
    manifest = _real_manifest()
    seed = _clean_seed(manifest)
    base = _with_parity(manifest, _undeclared(manifest, seed))
    repo, _ = _scratch(shared_reference_layout, tmp_path / broken, base, seed)
    before = _head(repo)
    if broken == "manifest":
        for rel in MANIFEST_RELS[:1]:
            _dump(repo / rel, "{ this is not json")
        _stage(repo, MANIFEST_RELS[0])
    elif broken == "seed":
        for rel in SEED_RELS:
            _dump(repo / rel, "{ this is not json")
        _stage(repo, *SEED_RELS)
    else:
        bad = copy.deepcopy(base)
        bad["hook_parity"]["undeclared_remedy_baseline"] = "check-complexity"
        _write_tables(repo, bad, seed)
        _stage(repo, *MANIFEST_RELS)
    output = _refused(repo, before, _commit(repo))
    assert re.search(r"could[_ ]not[_ ]check", output.lower()), f"not reported as could-not-check: {output!r}"
    assert "needs a remedy declaration" not in output.lower(), f"unreadable input misreported as 'no declaration': {output!r}"


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("broken", ["missing_manifest", "no_hooks_manifest"])
def test_ge132a1_unregistrable_canonical_manifest_is_could_not_check(
    shared_reference_layout: Path, tmp_path: Path, broken: str
) -> None:
    # covers: GE-132a-1
    # angle: failure
    """A canonical manifest that EXISTS but has no hooks_manifest object is
    could-not-check (refused, exit 2), never a silent pass. A MISSING canonical
    manifest is a consumer layout with no registry to judge: the leg prints a
    'not applicable' line naming the path and the commit passes (never silent).

    Wrong versions caught: a stderr WARNING plus ``return []`` for a manifest
    without hooks_manifest (exit 0); a silent ``return []`` for a missing one.
    """
    manifest = _real_manifest()
    seed, _ = _all_declared_seed(manifest)
    base = _with_parity(manifest, set())
    repo, _ = _scratch(shared_reference_layout, tmp_path / broken, base, seed)
    before = _head(repo)
    if broken == "missing_manifest":
        _git(["rm", "-q", MANIFEST_RELS[0]], repo)
    else:
        stripped = {k: v for k, v in base.items() if k != "hooks_manifest"}
        _dump(repo / MANIFEST_RELS[0], stripped)
        _stage(repo, MANIFEST_RELS[0])
    touched = copy.deepcopy(seed)
    touched["_comment"] = touched["_comment"] + " (touched)"
    _dump(repo / SEED_REL, touched)
    _stage(repo, SEED_REL)
    if broken == "missing_manifest":
        # pre-commit hides a passing hook's stderr, so run the deployed check directly.
        ran = subprocess.run(
            [sys.executable, "-I", str(repo / "scripts" / "commit_guardian" / "check_hook_parity.py")],
            cwd=str(repo), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False,
        )
        output = ran.stdout + ran.stderr
        assert ran.returncode == 0, f"missing manifest must be not-applicable, exit 0: {output!r}"
        assert "not applicable" in output.lower() and MANIFEST_RELS[0] in output, f"no not-applicable line: {output!r}"
        return
    output = _refused(repo, before, _commit(repo))
    assert re.search(r"could[_ ]not[_ ]check", output.lower()), f"not reported as could-not-check: {output!r}"
    assert MANIFEST_RELS[0] in output, f"unreadable manifest not named: {output!r}"


# ---------------------------------------------------------------------------
# Shared loader
# ---------------------------------------------------------------------------
def test_ge132a1_shared_loader_falls_back_to_seed_for_an_old_install(tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: real_artifact
    """Owned constraint. (1) an old install's local rule with no disposition
    falls back to the seed, which is named as the source; (2) a local rule that
    declares one wins and names the local file; (3) a hook in neither table
    comes back missing.

    Wrong versions caught: a loader reading only the local table (1 yields
    nothing); a loader reading only the seed (2 ignores the project's own).
    """
    local, seed, _ = _old_install_tables()
    root = tmp_path / "project"
    shutil.copytree(GUARDIAN_DIR, root / "templates" / "scripts" / "commit_guardian", ignore=shutil.ignore_patterns("__pycache__"))
    _dump(root / SEED_REL, seed)
    _dump(root / LOCAL_REL, local)
    driver = tmp_path / "driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-I", str(driver), str(root / "templates" / "scripts" / "commit_guardian"),
         "check-complexity", "check-file-size", "check-widget-names"],
        cwd=str(root), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False,
    )
    assert done.returncode == 0, f"loader failed: {done.stderr}"
    got = json.loads(done.stdout)
    fallback = got["check-complexity"]
    assert fallback and fallback["disposition"] == DECL["disposition"], f"no seed fallback: {fallback!r}"
    assert fallback["source"].replace("\\", "/").endswith(SEED_REL), f"source is not the seed: {fallback!r}"
    winner = got["check-file-size"]
    assert winner and winner["disposition"] == "author-clears", f"local declaration did not win: {winner!r}"
    assert winner["source"].replace("\\", "/").endswith(LOCAL_REL), f"source is not the local file: {winner!r}"
    assert not (got["check-widget-names"] or {}).get("disposition"), f"unknown hook not missing: {got['check-widget-names']!r}"


def test_ge132a1_malformed_skills_config_is_reported_not_defaulted(tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: failure
    """Fail closed. A skills_config.json that exists but is unparseable (or not an
    object) must raise RemedyInputError, never silently resolve to the default
    table. Controls: a valid skills_config without the key, and no skills_config,
    both still load from the default table.

    Wrong version caught: ``except (OSError, ValueError): config = {}`` -- a corrupt
    config that points at another table is judged against the default file.
    """
    local, seed, _ = _old_install_tables()
    root = tmp_path / "project"
    shutil.copytree(GUARDIAN_DIR, root / "templates" / "scripts" / "commit_guardian", ignore=shutil.ignore_patterns("__pycache__"))
    _dump(root / SEED_REL, seed)
    _dump(root / LOCAL_REL, local)
    driver = tmp_path / "driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    guardian = str(root / "templates" / "scripts" / "commit_guardian")
    config = root / ".claude" / "skills_config.json"

    def run() -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-I", str(driver), guardian, "check-file-size"],
            cwd=str(root), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False,
        )

    control = run()
    assert control.returncode == 0, f"no skills_config must load the default table: {control.stderr}"
    _dump(config, {"unrelated_key": 1})
    keyless = run()
    assert keyless.returncode == 0, f"a config without the key must load the default table: {keyless.stderr}"
    assert json.loads(keyless.stdout)["check-file-size"]["disposition"] == "author-clears"
    for bad in ("{ this is not json", "[1, 2]"):
        _dump(config, bad)
        done = run()
        assert done.returncode != 0, f"malformed skills_config {bad!r} silently resolved: {done.stdout!r}"
        assert "RemedyInputError" in done.stderr, f"not reported as unreadable input: {done.stderr!r}"
        assert "skills_config.json" in done.stderr, f"offending file not named: {done.stderr!r}"


@pytest.mark.shared_layout_reader
def test_ge132a1_old_install_commit_passes_through_shared_loader(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: seam
    """Seam: the commit-time legs judge the committed table. The scratch repo's
    local table (.claude/precommit-autofix.json) is the REAL pre-GE-132 one and the
    committed templates/scripts/precommit-autofix.json is the current real table;
    the commit passes with the old-shape local table present beside it, and a
    hook declared in neither table is still refused."""
    local, _, manifest = _old_install_tables()
    seed = _clean_seed(manifest)
    assert "check-complexity" not in _declared_ids(local), "local table must stay the pre-GE-132 shape"
    merged_undeclared = _undeclared(manifest, seed)
    assert "check-complexity" not in merged_undeclared and "check-file-size" not in merged_undeclared
    base = _with_parity(manifest, merged_undeclared)
    repo, stanza = _scratch(shared_reference_layout, tmp_path / "old_install", base, seed, local=local)
    before = _head(repo)
    touched = copy.deepcopy(base)
    touched["_comment"] = touched["_comment"] + " (touched)"
    _write_tables(repo, touched, seed)
    _stage(repo, *MANIFEST_RELS)
    _accepted(repo, before, _commit(repo), stanza)

    # Refusal row (so the pass above is not vacuous): a hook in neither table
    # is still refused on this old install.
    refused_repo, _ = _scratch(shared_reference_layout, tmp_path / "old_install_new_check", base, seed, local=local)
    before = _head(refused_repo)
    grown = copy.deepcopy(base)
    _hooks(grown).append(_widget_hook("check-widget-names"))
    _write_tables(refused_repo, grown, seed)
    _stage(refused_repo, *MANIFEST_RELS)
    output = _refused(refused_repo, before, _commit(refused_repo))
    assert _lines_naming(output, "check-widget-names"), f"undeclared check not named: {output!r}"


@pytest.mark.shared_layout_reader
def test_ge132a1_loader_is_deployed_and_imports_cold(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: GE-132a-1
    # angle: deployed
    """The loader module is in the DEPLOYED guardian dir beside the check and
    imports in a genuinely fresh interpreter (a deploy-manifest gap raises
    ModuleNotFoundError when the hook runs, which a source-tree read cannot see)."""
    deployed = _deployed_guardian(shared_reference_layout)
    assert (deployed / "_remedy_declarations.py").is_file(), f"loader not deployed under {deployed}"
    driver = tmp_path / "driver.py"
    driver.write_text(_DRIVER, encoding="utf-8")
    empty = tmp_path / "empty_project"
    empty.mkdir()
    done = subprocess.run(
        [sys.executable, "-I", str(driver), str(deployed), "check-complexity"],
        cwd=str(empty), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False,
    )
    assert done.returncode == 0, f"cold import / load failed: {done.stderr}"
