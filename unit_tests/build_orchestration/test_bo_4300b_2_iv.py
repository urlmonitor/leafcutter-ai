"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_2_iv.py
AC: BO-4300b-2-iv -- a project that declares its own install command gets its workspace built by
    that command (DIAGraph's scripts/rebuild_leafcutter.py wrapper is the motivating case).
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hubs, a real git
submodule, no git mock). Red baseline: the maker ignores any declaration and looks only for
<workspace>/scripts/build.py.

DECISION HISTORY
====================================================================
- 2026-11-17 [test-writer/BO-4300b-2-iv]: Created the red baseline. (#TICKETLESS reason=quick-fix-ac-first)
====================================================================
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300b_2_adopter_fixtures import PACKAGE_STAMP, ensure, make_adopter

_KEY = "workspace_install_command"
_DECLARED = ["{python}", "tools/install.py", "--target-dir", "{workspace}", "--config-path", "{config_path}",
             "--package-dir", "{package_dir}"]

# shop's own wrapper: runs the package's build, then applies shop's own overlay (as DIAGraph's does).
_WRAPPER = '''import argparse
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--target-dir", required=True)
parser.add_argument("--config-path", required=True)
parser.add_argument("--package-dir", required=True)
args, _ignored = parser.parse_known_args()
build = Path(args.package_dir) / "scripts" / "build.py"
code = subprocess.run([sys.executable, str(build), "--target-dir", args.target_dir,
                       "--config-path", args.config_path], check=False).returncode
if code == 0:
    (Path(args.target_dir) / "OVERLAY_APPLIED.txt").write_text("overlay-applied\\n", encoding="utf-8")
sys.exit(code)
'''
_FAILING_WRAPPER = "import sys\nprint('WRAPPER-FAILED-ON-PURPOSE', file=sys.stderr)\nsys.exit(1)\n"


class TestBO4300b2ivDeclaredInstallCommand(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b2iv-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _shop(self, name: str, declared, wrapper: str = _WRAPPER) -> Path:
        config = {"docs_root": "docs/", _KEY: declared}
        return make_adopter(self.tmp / name, config=config, extra={"tools/install.py": wrapper})["project"]

    def test_declared_install_command_builds_the_workspace(self):
        # covers: BO-4300b-2-iv
        # angle: criterion
        """The declared wrapper runs inside the workspace: ok, package build marker and overlay marker present."""
        res = ensure(self._shop("ok", _DECLARED))
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "ok", f"{ans}\n{res['stderr'][-3000:]}")
        ws = Path(ans["workspace_path"])
        self.assertIn(PACKAGE_STAMP, (ws / "INSTALLED_MARKER.txt").read_text(encoding="utf-8"))
        self.assertTrue((ws / "OVERLAY_APPLIED.txt").is_file(), "the declared wrapper did not run")

    def test_failing_declared_command_is_bootstrap_failed_quoting_it(self):
        # covers: BO-4300b-2-iv
        # angle: failure
        """A declared wrapper exiting 1: BOOTSTRAP_FAILED, no location, its own stderr quoted."""
        ans = ensure(self._shop("fail", _DECLARED, wrapper=_FAILING_WRAPPER))["answer"]
        self.assertEqual(ans.get("code"), "BOOTSTRAP_FAILED", ans)
        self.assertNotIn("workspace_path", ans)
        self.assertIn("WRAPPER-FAILED-ON-PURPOSE", ans["bootstrap"]["failure_excerpt"])

    def test_malformed_declaration_is_bootstrap_failed_naming_the_key(self):
        # covers: BO-4300b-2-iv
        # angle: failure
        """A shell string instead of a list: BOOTSTRAP_FAILED naming the setting; nothing is run."""
        ans = ensure(self._shop("bad", "python tools/install.py"))["answer"]
        self.assertEqual(ans.get("code"), "BOOTSTRAP_FAILED", ans)
        self.assertNotIn("workspace_path", ans)
        self.assertIn(_KEY, ans["bootstrap"]["failure_excerpt"])


if __name__ == "__main__":
    unittest.main()
