"""
MODULE: test_ki_cg_024_agent_registry_path
GOAL: Regression test for KI-CG-024 -- check_ticket_signoff_parity's check #6
    (unchecked-tasks parity guard) silently skipped on every ticket commit
    because its agent-registry default path did not exist in any layout.
BUSINESS CONTEXT: config.AGENT_REGISTRY_PATH defaulted to
    "leafcutter/config/agent_registry.json", a path that has never existed
    (the real file is at <project_root>/config/agent_registry.json). Because
    load_agent_registry() in _signoff_parity_checks.py resolves this default
    relative to the project root and fails open (returns {} with a WARNING)
    when the file is absent, check #6 always ran against an empty registry
    and therefore never actually validated anything. This became material
    once the hook was registered by 406375c88 -- before that it skipped
    nothing because it never ran.
ARCHITECTURE: Tests add templates/scripts/commit_guardian/ to sys.path (the
    convention in test_check_ticket_signoff_parity_done_folder.py) and import
    config and _signoff_parity_checks directly, so their own sibling-relative
    imports (e.g. _signoff_parity_checks -> _cross_layer_seam_checks) resolve
    through normal Python import machinery instead of a hand-rolled
    dependency order. Exercises load_agent_registry() against the REAL
    config/agent_registry.json shipped in this repo -- a real on-disk
    artifact, not a synthetic fixture -- per the project's real-artifact
    spot-check convention.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CG_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

if str(_CG_DIR) not in sys.path:
    sys.path.insert(0, str(_CG_DIR))

import config as _config  # noqa: E402
import _signoff_parity_checks  # noqa: E402


class TestAgentRegistryPathDefault(unittest.TestCase):
    """config.AGENT_REGISTRY_PATH must resolve to the real, shipped registry."""

    def test_default_is_project_root_relative_config_path(self):
        """The bare default (no commit_guardian.json override) must be
        'config/agent_registry.json' -- the historical
        'leafcutter/config/agent_registry.json' value never existed anywhere.
        """
        self.assertEqual(
            _config.AGENT_REGISTRY_PATH,
            "config/agent_registry.json",
            "AGENT_REGISTRY_PATH default must be 'config/agent_registry.json' "
            "(project-root-relative, mirrors DOC_FM_COMPONENTS_REGISTRY's "
            "convention). 'leafcutter/config/agent_registry.json' does not "
            "exist in any layout (KI-CG-024).",
        )

    def test_default_path_resolves_to_a_real_file_in_this_repo(self):
        """Joined onto this repo's own root, the default must point at a
        file that actually exists -- this repo's own config/agent_registry.json.
        """
        resolved = _REPO_ROOT / _config.AGENT_REGISTRY_PATH
        self.assertTrue(
            resolved.is_file(),
            f"AGENT_REGISTRY_PATH default resolved to {resolved}, which does "
            "not exist. check_ticket_signoff_parity's check #6 fails open "
            "(skips silently) whenever this file is absent.",
        )


class TestLoadAgentRegistry(unittest.TestCase):
    """load_agent_registry() must actually load entries from the real registry."""

    def test_load_agent_registry_returns_nonempty_dict_for_this_repo(self):
        """
        Given this repo's real root (which genuinely ships
        config/agent_registry.json), when load_agent_registry() is called,
        then it must return a non-empty mapping of agent id -> bool.

        Before KI-CG-024's fix this assertion is false: the old default
        resolves to a path that has never existed, so load_agent_registry()
        always fell into its "registry not found" fail-open branch and
        returned {} -- meaning check #6 silently validated against nothing
        on every real commit.
        """
        registry = _signoff_parity_checks.load_agent_registry(_REPO_ROOT)

        self.assertGreater(
            len(registry), 0,
            "load_agent_registry() returned an empty dict against this "
            "repo's real root, which genuinely ships "
            "config/agent_registry.json with dozens of agents. An empty "
            "result means check #6 is (still) validating nothing.",
        )
        # A spot check on a real, known agent id shipped in this repo's own
        # registry -- proves entries are genuinely parsed, not just present.
        self.assertIn(
            "python-coder", registry,
            "Expected 'python-coder' to be a key in the loaded agent "
            "registry (this repo's config/agent_registry.json declares it).",
        )


if __name__ == "__main__":
    unittest.main()
