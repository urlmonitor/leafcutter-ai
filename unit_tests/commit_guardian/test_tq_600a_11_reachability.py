"""
RED test stub for TQ-600a-11's fourth test_spec entry -- "the accessor is
reachable from a deployed commit hook."

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-11.yaml
(test_spec entry `test_tq600a_11_the_accessor_is_reachable_from_a_deployed_commit_hook`;
that record's YAML wins wherever a summary here differs).

======================================================================
ASSUMED PRODUCTION CONTRACT:

- scripts/ac_store/yaml_safe_loader.py (new module; see
  unit_tests/ac_store/test_tq_600a_11.py's module docstring for its
  get_safe_yaml_loader() / load_yaml_text() / load_yaml_file() contract).
- MUST be added to AC_STORE_DEPLOY_MAP in scripts/build_phases_ac_store.py
  (the deploy declaration scripts/build_phases.py re-exports) so it exists
  at <deployed_root>/scripts/ac_store/yaml_safe_loader.py in every built
  layout. Omitting this reproduces the exact ModuleNotFoundError-at-hook-
  runtime defect class CLAUDE.md's "New Hook / Gate Dependencies Must Be in
  the Build Deploy-Manifest" section documents (done_proof.py's own prior
  incident, same repo).
- Reachable from a commit-guardian hook via the EXISTING
  `_ac_store_locator.ensure_ac_store_on_syspath()` convention --
  templates/scripts/commit_guardian/check_done_proof.py already uses this
  exact mechanism to import `done_proof` from the sibling ac_store/
  directory. This works unchanged for yaml_safe_loader.py once it is a file
  inside the same ac_store/ directory done_proof.py already lives in -- no
  locator changes needed, because resolve_ac_store_dir() returns the
  DIRECTORY, and any caller may import any sibling module from it.

Per CLAUDE.md's "Tests must not spawn their own build.py" (this test only
READS the deployed layout -- it never mutates the package before building),
this test consumes the shared, cross-process-cached `shared_reference_layout`
fixture (declared via @pytest.mark.shared_layout_reader) rather than running
its own build.py subprocess.

Pre-implementation, this test is expected to go RED with a ModuleNotFoundError
for `yaml_safe_loader` surfaced inside the child subprocess's stderr (and a
non-zero returncode asserted below) -- that is the correct RED state: the
module does not exist in the deployed layout yet because it does not exist
in the source tree yet.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


@pytest.mark.shared_layout_reader
def test_tq600a_11_the_accessor_is_reachable_from_a_deployed_commit_hook(shared_reference_layout):
    # covers: TQ-600a-11
    # angle: reachability
    """
    From the DEPLOYED layout (never the source tree -- a source-tree import
    would be structurally blind to a deploy-manifest gap), in a FRESH
    subprocess, reach scripts/ac_store/yaml_safe_loader.py the EXACT way a
    real commit-guardian hook reaches its ac_store siblings: via
    _ac_store_locator.ensure_ac_store_on_syspath() (the identical mechanism
    check_done_proof.py already uses for `done_proof`). A ModuleNotFoundError
    here is the documented deploy-manifest failure named in this file's
    module docstring, and must be RED before the fix -- not discovered only
    when the required "AC store valid" PR gate starts crashing on every
    merge.
    """
    layout_root = Path(shared_reference_layout)
    commit_guardian_dir = layout_root / "scripts" / "commit_guardian"
    assert commit_guardian_dir.is_dir(), f"{commit_guardian_dir} missing from deployed layout"
    assert (commit_guardian_dir / "_ac_store_locator.py").is_file(), (
        f"_ac_store_locator.py missing from deployed {commit_guardian_dir}"
    )

    wrapper = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(commit_guardian_dir)!r})
        from _ac_store_locator import ensure_ac_store_on_syspath
        ensure_ac_store_on_syspath()
        from yaml_safe_loader import get_safe_yaml_loader
        loader = get_safe_yaml_loader()
        print("REACHED:", loader)
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", wrapper],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"could not reach yaml_safe_loader from the deployed commit-guardian "
        f"hook directory {commit_guardian_dir} -- stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert "REACHED:" in result.stdout, f"unexpected stdout: {result.stdout!r}"
